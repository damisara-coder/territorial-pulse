"""Typologie automatique des territoires par clustering K-Means (Moteurs, En transition, Fragiles)."""

from __future__ import annotations

from typing import Tuple

import numpy as np
import pandas as pd

from src.config import PROVINCE_BY_ID, TPI_COMPONENTS


def _kmeans_numpy(X: np.ndarray, k: int = 3, max_iter: int = 100, seed: int = 42) -> Tuple[np.ndarray, np.ndarray]:
    """K-Means déterministe (initialisation par quantiles du 1er axe) en NumPy pur."""
    order = np.argsort(X[:, 0])
    idx = [order[int((i + 0.5) * len(order) / k)] for i in range(k)]
    centroids = X[idx].copy()

    labels = np.zeros(len(X), dtype=int)
    for _ in range(max_iter):
        dists = np.linalg.norm(X[:, None, :] - centroids[None, :, :], axis=2)
        new_labels = np.argmin(dists, axis=1)
        if np.array_equal(new_labels, labels):
            break
        labels = new_labels
        for c in range(k):
            mask = labels == c
            if np.any(mask):
                centroids[c] = X[mask].mean(axis=0)
    return labels, centroids


def build_typology(df: pd.DataFrame) -> Tuple[pd.DataFrame, dict]:
    """Classifie les 8 provinces en 3 profils économiques à partir des données récentes (12 derniers mois)."""
    dates = sorted(df["date"].unique())
    recent_dates = dates[-12:]
    recent = df[df["date"].isin(recent_dates)].copy()

    rows = []
    for pid, grp in recent.groupby("province_id"):
        grp = grp.sort_values("date")
        tpi_mean = float(grp["tpi_score"].mean())
        tpi_latest = float(grp["tpi_score"].iloc[-1])
        tpi_delta_12m = float(grp["tpi_score"].iloc[-1] - grp["tpi_score"].iloc[0])
        comp_means = {c: float(grp[c].mean()) for c in TPI_COMPONENTS}
        rows.append(
            {
                "province_id": pid,
                "province_name": PROVINCE_BY_ID[pid]["name"],
                "tpi_mean_12m": round(tpi_mean, 2),
                "tpi_latest": round(tpi_latest, 2),
                "tpi_delta_12m": round(tpi_delta_12m, 2),
                **{c: round(v, 2) for c, v in comp_means.items()},
            }
        )

    prof_df = pd.DataFrame(rows).sort_values("province_id").reset_index(drop=True)
    feat_cols = ["tpi_mean_12m", "tpi_delta_12m", "nightlights_sa", "business_creations_sa", "employment_idx"]
    X = prof_df[feat_cols].to_numpy(dtype=float)
    X_std = (X - X.mean(axis=0)) / np.where(X.std(axis=0) > 1e-9, X.std(axis=0), 1.0)

    raw_labels, _ = _kmeans_numpy(X_std, k=3)
    prof_df["raw_cluster"] = raw_labels

    # Ordonner les clusters du plus bas au plus haut TPI moyen
    cluster_order = (
        prof_df.groupby("raw_cluster")["tpi_mean_12m"]
        .mean()
        .sort_values(ascending=True)
        .index.tolist()
    )
    label_names = {
        cluster_order[0]: "Fragile",
        cluster_order[1]: "En transition",
        cluster_order[2]: "Moteur",
    }
    cluster_descriptions = {
        "Moteur": "Pôles industriels, logistiques et tertiaires à forte intensité lumineuse et création d'entreprises soutenue.",
        "En transition": "Territoires intermédiaires à potentiel agro-industriel ou touristique soumis à une forte saisonnalité.",
        "Fragile": "Arrière-pays rural ou montagneux à faible densité industrielle nécessitant un désenclavement ciblé.",
    }

    prof_df["cluster_label"] = prof_df["raw_cluster"].map(label_names)
    prof_df = prof_df.drop(columns=["raw_cluster"])

    # Joindre au panel complet
    cluster_map = prof_df.set_index("province_id")["cluster_label"].to_dict()
    df_out = df.copy()
    df_out["cluster_label"] = df_out["province_id"].map(cluster_map)

    summary = {
        "clusters": [
            {
                "label": lbl,
                "description": cluster_descriptions[lbl],
                "provinces": prof_df[prof_df["cluster_label"] == lbl]["province_name"].tolist(),
                "province_ids": prof_df[prof_df["cluster_label"] == lbl]["province_id"].tolist(),
                "mean_tpi": round(float(prof_df[prof_df["cluster_label"] == lbl]["tpi_mean_12m"].mean()), 2),
                "mean_delta_12m": round(float(prof_df[prof_df["cluster_label"] == lbl]["tpi_delta_12m"].mean()), 2),
            }
            for lbl in ["Moteur", "En transition", "Fragile"]
        ],
        "provinces": prof_df.to_dict(orient="records"),
    }
    return df_out, summary
