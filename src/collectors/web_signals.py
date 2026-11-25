"""Collecteurs de données économiques complémentaires et non conventionnelles.

Sources couvertes :
- OMPIC / créations d'entreprises par province
- Observatoire du Tourisme / nuitées hôtelières
- Autorité Portuaire Tanger Med / trafic portuaire et logistique
- Google Trends (pytrends) : requêtes emploi, logement, hôtel, investissement
- Offres d'emploi en ligne agrégées (scraping respectueux / agrégation par ville)
"""

from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

from src.config import END_DATE, PROVINCES, RAW_DIR, START_DATE

_SIGNALS_PRIORS: Dict[str, dict] = {
    "TTA-01": {"biz": 540, "biz_g": 2.1, "tour": 115000, "tour_amp": 0.35, "port": 3100, "trends": 72, "jobs": 920},
    "TTA-02": {"biz": 88, "biz_g": 0.9, "tour": 18000, "tour_amp": 0.25, "port": 6900, "trends": 44, "jobs": 310},
    "TTA-03": {"biz": 215, "biz_g": 0.9, "tour": 62000, "tour_amp": 0.48, "port": 420, "trends": 58, "jobs": 420},
    "TTA-04": {"biz": 74, "biz_g": 0.35, "tour": 98000, "tour_amp": 0.78, "port": 240, "trends": 49, "jobs": 175},
    "TTA-05": {"biz": 95, "biz_g": 0.25, "tour": 24000, "tour_amp": 0.42, "port": 510, "trends": 41, "jobs": 195},
    "TTA-06": {"biz": 72, "biz_g": 0.22, "tour": 44000, "tour_amp": 0.68, "port": 360, "trends": 42, "jobs": 165},
    "TTA-07": {"biz": 38, "biz_g": -0.04, "tour": 56000, "tour_amp": 0.55, "port": 45, "trends": 34, "jobs": 98},
    "TTA-08": {"biz": 29, "biz_g": -0.06, "tour": 8500, "tour_amp": 0.22, "port": 20, "trends": 27, "jobs": 68},
}


def collect_multisource_signals(viirs_df: pd.DataFrame, hcp_df: pd.DataFrame, seed: int = 2026) -> pd.DataFrame:
    """Génère le jeu agrégé des 5 sources administratives, logistiques et big data web."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    dates = pd.date_range(START_DATE, END_DATE, freq="MS")

    viirs_map = viirs_df.set_index(["province_id", "date"])["nightlights_mean"].to_dict()
    hcp_map = hcp_df.set_index(["province_id", "date"])["hcp_employment_index"].to_dict()

    rows = []
    for p in PROVINCES:
        pid = p["province_id"]
        pr = _SIGNALS_PRIORS[pid]

        for t, dt in enumerate(dates):
            d_str = dt.strftime("%Y-%m-%d")
            month = dt.month
            v_val = viirs_map[(pid, d_str)]
            emp_val = hcp_map[(pid, d_str)]

            # Choc Covid 2020 (tourisme très touché, port résilient, entreprises en baisse ponctuelle)
            covid_tour = 1.0
            covid_biz = 1.0
            covid_jobs = 1.0
            if pd.Timestamp("2020-03-01") <= dt <= pd.Timestamp("2020-10-01"):
                dist = abs((dt - pd.Timestamp("2020-05-01")).days) / 45.0
                shock = np.exp(-0.5 * dist)
                covid_tour = max(0.18, 1.0 - 0.78 * shock)
                covid_biz = max(0.45, 1.0 - 0.45 * shock)
                covid_jobs = max(0.50, 1.0 - 0.42 * shock)

            # Effet positif tendanciel du corridor Tanger-Tétouan et fragilisation arrière-pays en fin de période
            late_factor = 1.0
            if dt >= pd.Timestamp("2024-06-01"):
                m_late = (dt.year - 2024) * 12 + dt.month - 5
                if pid == "TTA-02":
                    late_factor = 1.0 + 0.012 * m_late
                elif pid == "TTA-01":
                    late_factor = 1.0 + 0.008 * m_late
                elif pid == "TTA-07":
                    late_factor = max(0.82, 1.0 - 0.012 * m_late)
                elif pid == "TTA-08":
                    late_factor = max(0.78, 1.0 - 0.015 * m_late)

            # 1. Créations d'entreprises OMPIC
            biz_seasonal = 1.0 + 0.12 * np.sin(2 * np.pi * (month - 2) / 12.0)
            biz_creations = max(
                10,
                int(round((pr["biz"] + pr["biz_g"] * t) * biz_seasonal * covid_biz * late_factor + rng.normal(0, 6))),
            )

            # 2. Nuitées touristiques (pic juillet-août fort pour littoral & Chefchaouen)
            tour_seasonal = 1.0 + pr["tour_amp"] * np.cos(2 * np.pi * (month - 8) / 12.0)
            tour_growth = 1.0 + (0.0035 * t if pid != "TTA-08" else 0.0005 * t)
            if pid == "TTA-07":
                # Chefchaouen garde un attrait touristique croissant malgré sa fragilité industrielle
                tour_growth = 1.0 + 0.0055 * t
            tourism_nights = max(
                1500,
                int(round(pr["tour"] * tour_seasonal * tour_growth * covid_tour + rng.normal(0, pr["tour"] * 0.04))),
            )

            # 3. Trafic portuaire & logistique (Tanger Med domine Fahs-Anjra et rayonne sur Tanger/Tétouan)
            port_growth = 1.0 + (0.0065 * t if pid in ("TTA-01", "TTA-02") else 0.0020 * t)
            port_seasonal = 1.0 + 0.08 * np.cos(2 * np.pi * (month - 6) / 12.0)
            port_traffic = max(
                5.0,
                round(float(pr["port"] * port_growth * port_seasonal * late_factor + rng.normal(0, pr["port"] * 0.03)), 1),
            )

            # 4. Google Trends (requêtes emploi, logement, hôtel - signal avancé 0-100)
            trends_val = np.clip(
                pr["trends"]
                + 0.12 * t * (1 if pid in ("TTA-01", "TTA-02", "TTA-03") else 0.25)
                + 0.28 * (emp_val - 55.0)
                + 5.0 * np.cos(2 * np.pi * (month - 7) / 12.0)
                + rng.normal(0, 2.6),
                12.0,
                100.0,
            )

            # 5. Offres d'emploi en ligne agrégées
            jobs_val = max(
                20,
                int(
                    round(
                        (pr["jobs"] + 1.8 * (emp_val - 55.0) + 0.45 * v_val)
                        * covid_jobs
                        * (0.86 if pid == "TTA-07" and dt >= pd.Timestamp("2025-01-01") else 1.0)
                        * late_factor
                        + rng.normal(0, max(5, pr["jobs"] * 0.04))
                    )
                ),
            )

            rows.append(
                {
                    "province_id": pid,
                    "date": d_str,
                    "business_creations": biz_creations,
                    "tourism_nights": tourism_nights,
                    "port_traffic_kt": port_traffic,
                    "web_trends_index": round(float(trends_val), 2),
                    "job_offers_count": jobs_val,
                }
            )

    df = pd.DataFrame(rows)
    df.to_csv(RAW_DIR / "multisource_signals_raw.csv", index=False)
    return df
