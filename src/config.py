"""Configuration centrale du projet Territorial Pulse."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
GEO_DIR = DATA_DIR / "geo"
DOCS_DIR = BASE_DIR / "docs"
FICHES_DIR = DOCS_DIR / "fiches_exemple"

START_DATE = "2019-01-01"
END_DATE = "2025-10-01"
FORECAST_DATE = "2025-11-01"

PROVINCES = [
    {
        "province_id": "TTA-01",
        "name": "Tanger-Assilah",
        "type": "Préfecture",
        "centroid": [-5.84, 35.63],
        "urban_hub": [-5.81, 35.76],
        "population_2024": 1358000,
        "area_km2": 952,
        "base_profile": "Moteur",
        "description": "Pôle industriel, tertiaire et urbain majeur (TFZ, TAC, littoral atlantique).",
    },
    {
        "province_id": "TTA-02",
        "name": "Fahs-Anjra",
        "type": "Province",
        "centroid": [-5.52, 35.75],
        "urban_hub": [-5.50, 35.80],
        "population_2024": 98000,
        "area_km2": 799,
        "base_profile": "Moteur",
        "description": "Corridor logistique et industriel autour du complexe portuaire Tanger Med.",
    },
    {
        "province_id": "TTA-03",
        "name": "Tétouan",
        "type": "Province",
        "centroid": [-5.39, 35.51],
        "urban_hub": [-5.37, 35.57],
        "population_2024": 625000,
        "area_km2": 2541,
        "base_profile": "Moteur",
        "description": "Centre administratif, universitaire et industriel (Tetouan Park, axe Martil).",
    },
    {
        "province_id": "TTA-04",
        "name": "M'diq-Fnideq",
        "type": "Préfecture",
        "centroid": [-5.33, 35.77],
        "urban_hub": [-5.34, 35.78],
        "population_2024": 256000,
        "area_km2": 213,
        "base_profile": "En transition",
        "description": "Littoral méditerranéen à forte saisonnalité touristique en reconversion post-frontière.",
    },
    {
        "province_id": "TTA-05",
        "name": "Larache",
        "type": "Province",
        "centroid": [-5.90, 35.15],
        "urban_hub": [-6.05, 35.18],
        "population_2024": 540000,
        "area_km2": 2783,
        "base_profile": "En transition",
        "description": "Bassin agro-industriel du Loukkos, pêche et pôle urbain Larache–Ksar El Kebir.",
    },
    {
        "province_id": "TTA-06",
        "name": "Al Hoceïma",
        "type": "Province",
        "centroid": [-4.22, 35.06],
        "urban_hub": [-3.94, 35.24],
        "population_2024": 418000,
        "area_km2": 3550,
        "base_profile": "En transition",
        "description": "Pôle oriental du Rif porté par l'infrastructure maritime, le tourisme estival et la diaspora.",
    },
    {
        "province_id": "TTA-07",
        "name": "Chefchaouen",
        "type": "Province",
        "centroid": [-5.10, 35.10],
        "urban_hub": [-5.26, 35.17],
        "population_2024": 485000,
        "area_km2": 4350,
        "base_profile": "Fragile",
        "description": "Territoire montagneux à fort attrait touristique mais faible densité industrielle.",
    },
    {
        "province_id": "TTA-08",
        "name": "Ouezzane",
        "type": "Province",
        "centroid": [-5.56, 34.84],
        "urban_hub": [-5.58, 34.80],
        "population_2024": 318000,
        "area_km2": 1861,
        "base_profile": "Fragile",
        "description": "Arrière-pays rural et agricole à faible intensité lumineuse nocturne et enclavement routier.",
    },
]

PROVINCE_BY_ID = {p["province_id"]: p for p in PROVINCES}
PROVINCE_BY_NAME = {p["name"]: p for p in PROVINCES}

# Composantes de l'indice TPI (somme des poids experts = 1.0)
TPI_COMPONENTS = [
    "nightlights_sa",
    "employment_idx",
    "business_creations_sa",
    "tourism_nights_sa",
    "port_traffic_sa",
    "web_trends_sa",
]

TPI_COMPONENT_LABELS = {
    "nightlights_sa": "Lumière nocturne (VIIRS)",
    "employment_idx": "Emploi & offres d'emploi",
    "business_creations_sa": "Créations d'entreprises",
    "tourism_nights_sa": "Nuitées touristiques",
    "port_traffic_sa": "Trafic portuaire & logistique",
    "web_trends_sa": "Recherches web (Trends)",
}

EXPERT_WEIGHTS = {
    "nightlights_sa": 0.25,
    "employment_idx": 0.25,
    "business_creations_sa": 0.15,
    "tourism_nights_sa": 0.12,
    "port_traffic_sa": 0.13,
    "web_trends_sa": 0.10,
}

# Seuils d'alertes par défaut
ALERT_THRESHOLDS = {
    "drop_3m_pct": -5.0,
    "surge_12m_pct": 10.0,
    "stagnation_months": 6,
    "stagnation_band_pts": 1.2,
    "anomaly_zscore": -2.0,
}

# Palettes visuelles fidèles aux maquettes
COLORS = {
    "navy": "#0A192F",
    "dark_bg": "#081221",
    "dark_card": "#101E33",
    "gold": "#F4B43A",
    "gold_soft": "#FDE68A",
    "cream": "#F7F4EC",
    "teal": "#157F5F",
    "emerald": "#33A876",
    "mint": "#7AD1A5",
    "amber": "#E8AA33",
    "coral": "#E06A47",
    "crimson": "#D1495B",
    "slate": "#64748B",
}
