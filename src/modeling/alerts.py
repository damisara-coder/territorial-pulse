"""Détection automatique d'anomalies, de ruptures (Covid 2020) et d'alertes territoriales."""

from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd

from src.config import ALERT_THRESHOLDS


def detect_alerts(df: pd.DataFrame, thresholds: Dict[str, float] | None = None) -> dict:
    """Produit les alertes en direct (dernier mois) et l'historique des ruptures majeures."""
    cfg = {**ALERT_THRESHOLDS, **(thresholds or {})}
    work = df.sort_values(["province_id", "date"]).copy()

    # Calcul des variations glissantes désaisonnalisées par province
    work["nl_pct_3m"] = work.groupby("province_id")["nightlights_raw_sa"].pct_change(3) * 100.0
    work["nl_pct_12m"] = work.groupby("province_id")["nightlights_raw_sa"].pct_change(12) * 100.0
    jobs_col = "jobs_raw_sa" if "jobs_raw_sa" in work.columns else "job_offers_count"
    work["jobs_pct_3m"] = work.groupby("province_id")[jobs_col].pct_change(3) * 100.0
    work["jobs_pct_12m"] = work.groupby("province_id")[jobs_col].pct_change(12) * 100.0
    work["tpi_delta_3m"] = work.groupby("province_id")["tpi_score"].diff(3)
    work["tpi_delta_12m"] = work.groupby("province_id")["tpi_score"].diff(12)

    # Z-score glissant sur la variation mensuelle du TPI (détection de chocs exogènes comme Covid-19)
    work["tpi_diff_1m"] = work.groupby("province_id")["tpi_score"].diff(1)
    roll_mean = work.groupby("province_id")["tpi_diff_1m"].transform(lambda s: s.rolling(12, min_periods=4).mean())
    roll_std = work.groupby("province_id")["tpi_diff_1m"].transform(lambda s: s.rolling(12, min_periods=4).std()).fillna(1.0)
    work["anomaly_z"] = (work["tpi_diff_1m"] - roll_mean) / np.where(roll_std > 0.2, roll_std, 1.0)

    # Historique des ruptures régionales / chocs (ex. mars-mai 2020)
    historical_events: List[dict] = []
    shocks = work[work["anomaly_z"] <= cfg["anomaly_zscore"]].copy()
    for _, row in shocks.iterrows():
        historical_events.append(
            {
                "date": row["date"],
                "province_id": row["province_id"],
                "province_name": row["province_name"],
                "severity": "critical",
                "type": "rupture",
                "z_score": round(float(row["anomaly_z"]), 2),
                "message": f"{row['province_name']} : rupture brutale d'activité ({row['tpi_diff_1m']:+.1f} pts TPI en 1 mois)",
            }
        )

    # Alertes actives à la date la plus récente
    latest_date = work["date"].max()
    latest = work[work["date"] == latest_date].copy()
    live_alerts: List[dict] = []

    for _, row in latest.iterrows():
        pid = row["province_id"]
        pname = row["province_name"]
        hist_p = work[work["province_id"] == pid].tail(int(cfg["stagnation_months"]))

        nl_3m = float(row["nl_pct_3m"]) if pd.notna(row["nl_pct_3m"]) else 0.0
        nl_12m = float(row["nl_pct_12m"]) if pd.notna(row["nl_pct_12m"]) else 0.0
        jobs_3m = float(row["jobs_pct_3m"]) if pd.notna(row["jobs_pct_3m"]) else 0.0
        jobs_12m = float(row["jobs_pct_12m"]) if pd.notna(row["jobs_pct_12m"]) else 0.0
        tpi_12m = float(row["tpi_delta_12m"]) if pd.notna(row["tpi_delta_12m"]) else 0.0
        tpi_3m = float(row["tpi_delta_3m"]) if pd.notna(row["tpi_delta_3m"]) else 0.0
        tpi_curr = float(row["tpi_score"])

        # 1. Alerte décrochage luminosité / TPI
        if nl_3m <= cfg["drop_3m_pct"] or tpi_12m <= -1.2 or tpi_3m <= -1.0:
            live_alerts.append(
                {
                    "province_id": pid,
                    "province_name": pname,
                    "severity": "danger",
                    "badge": "Décrochage",
                    "metric_value": round(nl_3m if abs(nl_3m) >= 1.5 else tpi_12m, 1),
                    "message": f"{pname} : luminosité {nl_3m:+.1f} % sur 3 mois (TPI {tpi_12m:+.1f} pts/an)",
                }
            )
        # 2. Alerte repli offres d'emploi (glissement annuel pour neutraliser la saisonnalité)
        if jobs_12m <= cfg["drop_3m_pct"]:
            live_alerts.append(
                {
                    "province_id": pid,
                    "province_name": pname,
                    "severity": "danger",
                    "badge": "Tension emploi",
                    "metric_value": round(jobs_12m, 1),
                    "message": f"{pname} : offres d'emploi {jobs_12m:+.1f} % sur 12 mois",
                }
            )
        # 3. Alerte accélération
        if nl_12m >= cfg["surge_12m_pct"] or tpi_12m >= 1.8:
            live_alerts.append(
                {
                    "province_id": pid,
                    "province_name": pname,
                    "severity": "success",
                    "badge": "Accélération",
                    "metric_value": round(tpi_12m, 1),
                    "message": f"{pname} : accélération ({tpi_12m:+.1f} pts TPI, lumière {nl_12m:+.1f} % sur 12 mois)",
                }
            )
        # 4. Stagnation sur N mois (hors pôles moteurs déjà au sommet)
        tpi_span = float(hist_p["tpi_score"].max() - hist_p["tpi_score"].min())
        if tpi_curr < 65.0 and tpi_span <= cfg["stagnation_band_pts"] and abs(tpi_3m) < 1.2 and len(
            [a for a in live_alerts if a["province_id"] == pid]
        ) == 0:
            live_alerts.append(
                {
                    "province_id": pid,
                    "province_name": pname,
                    "severity": "warning",
                    "badge": "Stagnation",
                    "metric_value": round(tpi_span, 2),
                    "message": f"{pname} : stagnation depuis {int(cfg['stagnation_months']) // 3} trimestres (amplitude {tpi_span:.1f} pts)",
                }
            )

    # Tri : danger -> success -> warning
    sev_order = {"danger": 0, "success": 1, "warning": 2}
    live_alerts.sort(key=lambda a: (sev_order.get(a["severity"], 3), -abs(a["metric_value"])))

    return {
        "latest_date": latest_date,
        "live_alerts": live_alerts,
        "historical_shocks_count": len(historical_events),
        "historical_shocks": sorted(historical_events, key=lambda x: x["date"]),
        "covid_2020_detected": any(e["date"].startswith("2020-") for e in historical_events),
    }
