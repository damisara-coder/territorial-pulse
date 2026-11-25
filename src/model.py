"""Interface Python unifiée pour charger les résultats et exécuter le simulateur « Et si ? »."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd

from src.config import EXPERT_WEIGHTS, GEO_DIR, PROCESSED_DIR, PROVINCE_BY_ID, TPI_COMPONENTS


class TerritorialPulseModel:
    """Façade importable par l'application web, l'export PDF et les tests."""

    def __init__(self, processed_dir: Path | None = None, geo_dir: Path | None = None):
        self.processed_dir = processed_dir or PROCESSED_DIR
        self.geo_dir = geo_dir or GEO_DIR
        self._df: pd.DataFrame | None = None
        self._meta: dict | None = None

    @property
    def df(self) -> pd.DataFrame:
        if self._df is None:
            csv_path = self.processed_dir / "dataset_panel.csv"
            if not csv_path.exists():
                raise FileNotFoundError(
                    f"Dataset introuvable à {csv_path}. Exécutez d'abord `python run_pipeline.py`."
                )
            self._df = pd.read_csv(csv_path)
        return self._df

    @property
    def metadata(self) -> dict:
        if self._meta is None:
            meta_path = self.processed_dir / "model_results.json"
            if not meta_path.exists():
                raise FileNotFoundError(
                    f"Résultats du modèle introuvables à {meta_path}. Exécutez d'abord `python run_pipeline.py`."
                )
            self._meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return self._meta

    def get_geojson(self) -> dict:
        return json.loads((self.geo_dir / "tta_provinces.geojson").read_text(encoding="utf-8"))

    def get_nightlight_points(self) -> dict:
        return json.loads((self.geo_dir / "nightlight_points.json").read_text(encoding="utf-8"))

    def get_province_profile(self, province_id: str) -> dict:
        """Construit le profil complet d'une province pour la Fiche Territoire ou le tiroir carte."""
        sub = self.df[self.df["province_id"] == province_id].sort_values("date").copy()
        if sub.empty:
            raise KeyError(f"Province inconnue : {province_id}")

        reg_series = (
            self.df.groupby("date")["tpi_score"].mean().round(2).reset_index().rename(columns={"tpi_score": "regional_mean"})
        )
        sub = sub.merge(reg_series, on="date")

        latest = sub.iloc[-1]
        prev_12 = sub.iloc[-13] if len(sub) >= 13 else sub.iloc[0]
        delta_12m = round(float(latest["tpi_score"] - prev_12["tpi_score"]), 1)

        # Composantes pour Maquette B (5 à 6 barres)
        components = {
            "Lumière": round(float(latest["nightlights_sa"]), 1),
            "Emploi": round(float(latest["employment_idx"]), 1),
            "Entreprises": round(float(latest["business_creations_sa"]), 1),
            "Tourisme": round(float(latest["tourism_nights_sa"]), 1),
            "Trafic portuaire": round(float(latest["port_traffic_sa"]), 1),
            "Recherches web": round(float(latest["web_trends_sa"]), 1),
        }

        strengths, watchpoints = self._derive_insights(province_id, components, delta_12m, sub)
        recommendations = self._derive_recommendations(province_id, str(latest["cluster_label"]), components, delta_12m)

        return {
            "province_id": province_id,
            "province_name": str(latest["province_name"]),
            "province_type": str(latest["province_type"]),
            "description": PROVINCE_BY_ID[province_id]["description"],
            "latest_date": str(latest["date"]),
            "tpi_score": round(float(latest["tpi_score"]), 1),
            "tpi_rank": int(latest["tpi_rank"]),
            "total_provinces": int(self.df["province_id"].nunique()),
            "delta_12m": delta_12m,
            "cluster_label": str(latest["cluster_label"]),
            "components": components,
            "series": {
                "dates": sub["date"].tolist(),
                "province_tpi": sub["tpi_score"].round(2).tolist(),
                "regional_mean": sub["regional_mean"].round(2).tolist(),
            },
            "strengths": strengths,
            "watchpoints": watchpoints,
            "recommendations": recommendations,
        }

    def _derive_insights(self, province_id: str, components: dict, delta_12m: float, sub: pd.DataFrame) -> tuple:
        sorted_comp = sorted(components.items(), key=lambda x: x[1], reverse=True)
        strengths = []
        watchpoints = []

        # Points forts déduits des composantes les plus élevées et dynamiques récentes
        for name, val in sorted_comp[:2]:
            if val >= 55:
                strengths.append(f"{name} solide ({val:.0f}/100)")
            else:
                strengths.append(f"Potentiel relatif sur {name.lower()} ({val:.0f}/100)")

        if len(sub) >= 13:
            tour_diff = float(sub["tourism_nights_sa"].iloc[-1] - sub["tourism_nights_sa"].iloc[-13])
            if tour_diff > 1.5 and not any("Tourisme" in s for s in strengths):
                strengths.append(f"Attractivité touristique en hausse ({tour_diff:+.1f} pts/an)")

        if province_id == "TTA-07":
            strengths.append("Patrimoine et écotourisme de montagne porteurs")
        elif province_id == "TTA-02":
            strengths.append("Effet d'entraînement logistique de Tanger Med")

        # Points de vigilance
        for name, val in sorted_comp[-2:]:
            if val < 50:
                watchpoints.append(f"Faible niveau sur {name.lower()} ({val:.0f}/100)")

        if delta_12m < 0:
            watchpoints.append(f"Tendance annuelle baissière ({delta_12m:+.1f} pts)")
        if len(sub) >= 4:
            jobs_3m = (sub["job_offers_count"].iloc[-1] / max(sub["job_offers_count"].iloc[-4], 1) - 1) * 100
            if jobs_3m < -4.0:
                watchpoints.append(f"Offres d'emploi en recul ({jobs_3m:+.1f} % sur 3 mois)")

        if not watchpoints:
            watchpoints.append("Risque de saturation foncière et pression sur les infrastructures")

        return strengths[:3], watchpoints[:3]

    def _derive_recommendations(self, province_id: str, cluster: str, components: dict, delta_12m: float) -> list[str]:
        recs = []
        if cluster == "Fragile":
            if components["Tourisme"] >= components["Entreprises"]:
                recs.append("Soutenir la création de TPE/PME et coopératives liées au tourisme durable et à l'artisanat.")
            else:
                recs.append("Déployer des zones d'activités rurales et un accompagnement financier ciblé (CRI / Tamwilcom).")
            recs.append("Améliorer la connectivité routière et numérique vers le corridor Tanger–Tétouan.")
            recs.append("Activer un suivi mensuel de l'alerte « emploi » avec revue opérationnelle à 6 mois.")
        elif cluster == "En transition":
            recs.append("Diversifier l'économie locale hors saison estivale via l'agro-industrie et les services numériques.")
            recs.append("Renforcer les formations professionnelles alignées sur les besoins logistiques et touristiques régionaux.")
            recs.append("Cibler des incitations à l'investissement productif pour converger vers la moyenne régionale.")
        else:
            recs.append("Optimiser l'intégration des sous-traitants locaux autour des zones industrielles et de Tanger Med.")
            recs.append("Anticiper la saturation urbaine par des pôles secondaires vers les provinces voisines en transition.")
            recs.append("Maintenir le pilotage en temps quasi réel des tensions sur les compétences et le foncier.")
        return recs

    def simulate_what_if(self, province_id: str, shocks_pct: Dict[str, float]) -> dict:
        """Simulateur « Et si ? » : estime l'impact d'une variation de facteurs sur le TPI et le rang."""
        latest_date = self.df["date"].max()
        latest_all = self.df[self.df["date"] == latest_date].copy()
        row = latest_all[latest_all["province_id"] == province_id].iloc[0]

        base_components = {c: float(row[c]) for c in TPI_COMPONENTS}
        sim_components = {}
        for comp in TPI_COMPONENTS:
            pct = float(shocks_pct.get(comp, 0.0))
            sim_val = float(np.clip(base_components[comp] * (1.0 + pct / 100.0), 0.0, 100.0))
            sim_components[comp] = round(sim_val, 2)

        sim_tpi = round(sum(EXPERT_WEIGHTS[c] * sim_components[c] for c in TPI_COMPONENTS), 2)
        base_tpi = round(float(row["tpi_score"]), 2)
        delta_tpi = round(sim_tpi - base_tpi, 2)

        # Recalcul du classement simulé dans la région
        scores = latest_all[["province_id", "province_name", "tpi_score"]].copy()
        scores.loc[scores["province_id"] == province_id, "tpi_score"] = sim_tpi
        scores["sim_rank"] = scores["tpi_score"].rank(ascending=False, method="min").astype(int)
        new_rank = int(scores[scores["province_id"] == province_id]["sim_rank"].iloc[0])
        old_rank = int(row["tpi_rank"])

        new_cluster = "Moteur" if sim_tpi >= 64 else ("En transition" if sim_tpi >= 47 else "Fragile")
        return {
            "province_id": province_id,
            "province_name": str(row["province_name"]),
            "base_tpi": base_tpi,
            "simulated_tpi": sim_tpi,
            "delta_tpi": delta_tpi,
            "base_rank": old_rank,
            "simulated_rank": new_rank,
            "rank_change": old_rank - new_rank,
            "base_cluster": str(row["cluster_label"]),
            "simulated_cluster": new_cluster,
            "simulated_components": sim_components,
        }
