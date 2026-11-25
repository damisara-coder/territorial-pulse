"""Construction du fond de carte GeoJSON des 8 préfectures/provinces de Tanger-Tétouan-Al Hoceïma."""

import json
from pathlib import Path
from typing import Dict, List, Tuple

from src.config import GEO_DIR, PROVINCE_BY_ID


# Polygones réalistes et contigus (coordonnées WGS84 lon, lat) fidèles à la géographie du Nord du Maroc
PROVINCE_POLYGONS: Dict[str, List[List[float]]] = {
    "TTA-01": [  # Tanger-Assilah (littoral atlantique nord-ouest & détroit ouest)
        [-6.06, 35.42],
        [-5.96, 35.62],
        [-5.93, 35.79],
        [-5.78, 35.81],
        [-5.67, 35.83],
        [-5.64, 35.62],
        [-5.69, 35.45],
        [-6.06, 35.42],
    ],
    "TTA-02": [  # Fahs-Anjra (détroit central - Tanger Med)
        [-5.67, 35.83],
        [-5.52, 35.91],
        [-5.41, 35.90],
        [-5.39, 35.72],
        [-5.48, 35.63],
        [-5.64, 35.62],
        [-5.67, 35.83],
    ],
    "TTA-04": [  # M'diq-Fnideq (côte méditerranéenne nord-est)
        [-5.41, 35.90],
        [-5.34, 35.90],
        [-5.27, 35.63],
        [-5.36, 35.61],
        [-5.39, 35.72],
        [-5.41, 35.90],
    ],
    "TTA-03": [  # Tétouan (corridor central & littoral méditerranéen)
        [-5.64, 35.62],
        [-5.48, 35.63],
        [-5.39, 35.72],
        [-5.36, 35.61],
        [-5.27, 35.63],
        [-5.12, 35.46],
        [-5.17, 35.34],
        [-5.42, 35.37],
        [-5.62, 35.38],
        [-5.69, 35.45],
        [-5.64, 35.62],
    ],
    "TTA-05": [  # Larache (littoral atlantique sud & plaine du Loukkos)
        [-6.22, 35.02],
        [-6.06, 35.42],
        [-5.69, 35.45],
        [-5.62, 35.38],
        [-5.58, 35.06],
        [-5.82, 34.93],
        [-6.16, 34.89],
        [-6.22, 35.02],
    ],
    "TTA-08": [  # Ouezzane (arrière-pays sud-central)
        [-5.82, 34.93],
        [-5.58, 35.06],
        [-5.35, 35.02],
        [-5.32, 34.71],
        [-5.56, 34.62],
        [-5.80, 34.72],
        [-5.82, 34.93],
    ],
    "TTA-07": [  # Chefchaouen (chaîne du Rif centrale & côte Ghomara)
        [-5.62, 35.38],
        [-5.42, 35.37],
        [-5.17, 35.34],
        [-5.12, 35.46],
        [-4.85, 35.30],
        [-4.64, 35.19],
        [-4.69, 34.82],
        [-5.02, 34.78],
        [-5.32, 34.71],
        [-5.35, 35.02],
        [-5.58, 35.06],
        [-5.62, 35.38],
    ],
    "TTA-06": [  # Al Hoceïma (Rif oriental & baie d'Al Hoceïma)
        [-4.64, 35.19],
        [-4.35, 35.22],
        [-3.95, 35.28],
        [-3.79, 35.15],
        [-3.84, 34.86],
        [-4.18, 34.81],
        [-4.69, 34.82],
        [-4.64, 35.19],
    ],
}


def point_in_polygon(lon: float, lat: float, polygon: List[List[float]]) -> bool:
    """Ray-casting point-in-polygon check."""
    inside = False
    n = len(polygon)
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > lat) != (yj > lat)) and (
            lon < (xj - xi) * (lat - yi) / ((yj - yi) if abs(yj - yi) > 1e-12 else 1e-12) + xi
        ):
            inside = not inside
        j = i
    return inside


def build_geojson(output_path: Path | None = None) -> dict:
    """Génère et sauvegarde le fichier GeoJSON des 8 provinces."""
    GEO_DIR.mkdir(parents=True, exist_ok=True)
    target = output_path or (GEO_DIR / "tta_provinces.geojson")

    features = []
    for pid, ring in PROVINCE_POLYGONS.items():
        meta = PROVINCE_BY_ID[pid]
        features.append(
            {
                "type": "Feature",
                "id": pid,
                "properties": {
                    "province_id": pid,
                    "name": meta["name"],
                    "type": meta["type"],
                    "centroid": meta["centroid"],
                    "urban_hub": meta["urban_hub"],
                    "population_2024": meta["population_2024"],
                    "area_km2": meta["area_km2"],
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [ring],
                },
            }
        )

    geojson = {
        "type": "FeatureCollection",
        "name": "Tanger-Tetouan-AlHoceima_Provinces",
        "features": features,
    }
    target.write_text(json.dumps(geojson, ensure_ascii=False, indent=2), encoding="utf-8")
    return geojson


if __name__ == "__main__":
    gj = build_geojson()
    print(f"GeoJSON généré avec {len(gj['features'])} provinces.")
