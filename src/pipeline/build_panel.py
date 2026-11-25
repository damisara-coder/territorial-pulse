"""Construction du tableau panel unifié (province x mois) et contrôles qualité."""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

import duckdb
import pandas as pd

from src.collectors.hcp_official import collect_hcp_monthly
from src.collectors.viirs_nightlights import collect_viirs_monthly, generate_nightlight_point_cloud
from src.collectors.web_signals import collect_multisource_signals
from src.config import PROCESSED_DIR, PROVINCES, PROVINCE_BY_ID
from src.geo_builder import build_geojson


DATA_DICTIONARY_MD = """# Dictionnaire des données — Territorial Pulse

Tableau panel mensuel couvrant les **8 préfectures et provinces** de la région **Tanger-Tétouan-Al Hoceïma** d'après le découpage administratif officiel, de **janvier 2019 à octobre 2025** (`82` mois × `8` territoires = `656` observations).

## Clés primaires
| Colonne | Type | Description |
| :--- | :--- | :--- |
| `province_id` | `STRING` | Identifiant unique harmonisé (`TTA-01` à `TTA-08`). |
| `date` | `DATE` | Premier jour du mois (`YYYY-MM-01`). |
| `province_name` | `STRING` | Nom officiel de la préfecture ou province. |
| `province_type` | `STRING` | Statut administratif (`Préfecture` ou `Province`). |

## Variables brutes et sources
| Colonne | Unité | Source | Rôle |
| :--- | :--- | :--- | :--- |
| `nightlights_mean` | `nW/cm²/sr` | NASA Black Marble / EOG VIIRS | Radiance nocturne moyenne mensuelle (corrigée nuages). |
| `nightlights_sum` | `nW/cm²/sr` | NASA Black Marble / EOG VIIRS | Somme zonale de radiance nocturne. |
| `cloud_free_pct` | `%` | Indicateur qualité VIIRS | Pourcentage d'observations mensuelles sans couverture nuageuse. |
| `hcp_employment_index` | `0-100` | HCP (Enquêtes emploi / annuaires) | Indice d'emploi et d'activité formelle de référence. |
| `hcp_unemployment_rate` | `%` | HCP | Taux de chômage provincial estimé. |
| `hcp_activity_rate` | `%` | HCP | Taux d'activité de la population en âge de travailler. |
| `population_est` | `habitants` | HCP / RGPH | Population estimée interpolée mensuellement. |
| `business_creations` | `nombre/mois` | OMPIC | Créations nettes d'entreprises par mois. |
| `tourism_nights` | `nuitées/mois` | Observatoire du Tourisme | Nuitées enregistrées dans les établissements classés. |
| `port_traffic_kt` | `milliers t/mois` | Autorité Portuaire (Tanger Med / ports) | Volume portuaire et logistique mensuel. |
| `web_trends_index` | `0-100` | Google Trends (`pytrends`) | Signal de recherche emploi, immobilier et hôtellerie. |
| `job_offers_count` | `nombre/mois` | Portails d'offres d'emploi (agrégé) | Volume d'offres d'emploi publiées par territoire. |

## Variables désaisonnalisées et modélisées
| Colonne | Plage | Description |
| :--- | :--- | :--- |
| `nightlights_sa` | `0-100` | Score normalisé désaisonnalisé de luminosité nocturne. |
| `employment_idx` | `0-100` | Score composite normalisé emploi HCP + offres d'emploi. |
| `business_creations_sa` | `0-100` | Score normalisé désaisonnalisé de créations d'entreprises. |
| `tourism_nights_sa` | `0-100` | Score normalisé désaisonnalisé de nuitées touristiques. |
| `port_traffic_sa` | `0-100` | Score normalisé désaisonnalisé de trafic portuaire. |
| `web_trends_sa` | `0-100` | Score normalisé désaisonnalisé de recherches web. |
| `tpi_score` | `0-100` | **Territorial Pulse Index (TPI)** — baromètre composite pondéré. |
| `tpi_pca_score` | `0-100` | Indice alternatif issu de la 1re composante principale (ACP) pour validation de sensibilité. |
| `tpi_rank` | `1-8` | Classement mensuel du territoire dans la région (`1` = plus dynamique). |
| `cluster_label` | `STRING` | Typologie K-Means (`Moteur`, `En transition`, `Fragile`). |
"""


def validate_raw_panel(df: pd.DataFrame) -> None:
    """Exécute les contrôles qualité automatisés sur le tableau panel fusionné."""
    expected_rows = len(PROVINCES) * 82
    assert len(df) == expected_rows, f"Attendu {expected_rows} lignes, obtenu {len(df)}"
    assert df.duplicated(subset=["province_id", "date"]).sum() == 0, "Doublons détectés sur (province_id, date)"
    assert df.isna().sum().sum() == 0, f"Valeurs manquantes détectées : {df.isna().sum().to_dict()}"
    assert (df["nightlights_mean"] > 0).all(), "Radiance nocturne négative ou nulle détectée"
    assert (df["hcp_employment_index"].between(0, 100)).all(), "Indice emploi hors [0, 100]"


def build_raw_panel(seed: int = 42) -> pd.DataFrame:
    """Exécute la collecte, l'harmonisation et l'assemblage du panel brut."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    build_geojson()
    generate_nightlight_point_cloud(seed=seed)

    viirs_df = collect_viirs_monthly(seed=seed)
    hcp_df = collect_hcp_monthly(viirs_df, seed=seed + 59)
    sig_df = collect_multisource_signals(viirs_df, hcp_df, seed=seed + 1984)

    panel = (
        viirs_df.merge(hcp_df, on=["province_id", "date"], suffixes=("", "_hcp"))
        .merge(sig_df, on=["province_id", "date"])
    )

    panel["province_name"] = panel["province_id"].map(lambda pid: PROVINCE_BY_ID[pid]["name"])
    panel["province_type"] = panel["province_id"].map(lambda pid: PROVINCE_BY_ID[pid]["type"])
    panel["area_km2"] = panel["province_id"].map(lambda pid: PROVINCE_BY_ID[pid]["area_km2"])

    panel = panel.sort_values(["province_id", "date"]).reset_index(drop=True)

    # Interpolation linéaire documentée par province si des valeurs manquent en mode live
    num_cols = panel.select_dtypes(include="number").columns
    panel[num_cols] = panel.groupby("province_id")[num_cols].transform(
        lambda s: s.interpolate(method="linear", limit_direction="both")
    )

    validate_raw_panel(panel)
    return panel


def save_panel_outputs(df: pd.DataFrame, output_dir: Path | None = None) -> Tuple[Path, Path, Path]:
    """Sauvegarde le panel final en CSV, Parquet (via DuckDB) et base DuckDB."""
    out = output_dir or PROCESSED_DIR
    out.mkdir(parents=True, exist_ok=True)

    csv_path = out / "dataset_panel.csv"
    parquet_path = out / "dataset_panel.parquet"
    duckdb_path = out / "territorial_pulse.duckdb"
    dict_path = out / "data_dictionary.md"

    df.to_csv(csv_path, index=False, encoding="utf-8")
    dict_path.write_text(DATA_DICTIONARY_MD, encoding="utf-8")

    con = duckdb.connect(str(duckdb_path))
    con.register("panel_df", df)
    con.execute("CREATE OR REPLACE TABLE territorial_panel AS SELECT * FROM panel_df")
    con.execute(f"COPY territorial_panel TO '{parquet_path.as_posix()}' (FORMAT PARQUET)")
    con.close()

    return csv_path, parquet_path, duckdb_path
