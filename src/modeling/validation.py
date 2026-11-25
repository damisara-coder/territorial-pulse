"""Validation scientifique : corrélations avec les données officielles HCP et analyse par décalage."""

from __future__ import annotations

import numpy as np
import pandas as pd


def _pearson(a: pd.Series, b: pd.Series) -> float:
    valid = a.notna() & b.notna()
    if valid.sum() < 5:
        return 0.0
    x = a[valid].to_numpy(dtype=float)
    y = b[valid].to_numpy(dtype=float)
    if np.std(x) < 1e-9 or np.std(y) < 1e-9:
        return 0.0
    return float(np.corrcoef(x, y)[0, 1])


def _spearman(a: pd.Series, b: pd.Series) -> float:
    valid = a.notna() & b.notna()
    if valid.sum() < 5:
        return 0.0
    return _pearson(a[valid].rank(), b[valid].rank())


def compute_validation_report(df: pd.DataFrame, nowcast_results: dict) -> dict:
    """Calcule les corrélations panel et intra-provinciales entre sources alternatives et HCP."""
    work = df.sort_values(["province_id", "date"]).copy()
    work["log_nl"] = np.log1p(work["nightlights_mean"])

    # Corrélations globales sur l'ensemble du panel (656 observations)
    global_corrs = {
        "nightlights_vs_hcp_pearson": round(_pearson(work["log_nl"], work["hcp_employment_index"]), 3),
        "nightlights_vs_hcp_spearman": round(_spearman(work["log_nl"], work["hcp_employment_index"]), 3),
        "tpi_vs_hcp_pearson": round(_pearson(work["tpi_score"], work["hcp_employment_index"]), 3),
        "trends_vs_hcp_pearson": round(_pearson(work["web_trends_index"], work["hcp_employment_index"]), 3),
        "jobs_vs_hcp_pearson": round(_pearson(np.log1p(work["job_offers_count"]), work["hcp_employment_index"]), 3),
    }

    # Corrélation temporelle par province & analyse urbain vs rural (discussion honnête des limites)
    prov_rows = []
    for pid, grp in work.groupby("province_id"):
        grp = grp.sort_values("date")
        r_nl = _pearson(grp["nightlights_sa"], grp["hcp_employment_index"])
        r_tpi = _pearson(grp["tpi_score"], grp["hcp_employment_index"])
        r_nl_lead1 = _pearson(grp["nightlights_sa"].shift(1), grp["hcp_employment_index"])
        prov_rows.append(
            {
                "province_id": pid,
                "province_name": grp["province_name"].iloc[0],
                "cluster_label": grp["cluster_label"].iloc[0],
                "r_nightlights_hcp": round(r_nl, 3),
                "r_nightlights_lead1_hcp": round(r_nl_lead1, 3),
                "r_tpi_hcp": round(r_tpi, 3),
            }
        )

    # Écart corridor Tanger-Tétouan vs arrière-pays (Chefchaouen + Ouezzane)
    latest_date = work["date"].max()
    latest = work[work["date"] == latest_date]
    tanger_tpi = float(latest[latest["province_id"] == "TTA-01"]["tpi_score"].iloc[0])
    hinterland_tpi = float(latest[latest["province_id"].isin(["TTA-07", "TTA-08"])]["tpi_score"].mean())
    gap_ratio = round(tanger_tpi / max(hinterland_tpi, 1.0), 2)

    return {
        "global_correlations": global_corrs,
        "province_correlations": prov_rows,
        "territorial_gap": {
            "latest_date": latest_date,
            "tanger_tpi": round(tanger_tpi, 1),
            "hinterland_mean_tpi": round(hinterland_tpi, 1),
            "gap_ratio": gap_ratio,
        },
        "nowcast_comparison": nowcast_results["hcp_nowcast_metrics"],
    }
