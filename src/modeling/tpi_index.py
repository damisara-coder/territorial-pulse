"""Calcul de l'indice composite Territorial Pulse Index (TPI), désaisonnalisation et test de sensibilité."""

from __future__ import annotations

from typing import Dict, Tuple

import numpy as np
import pandas as pd

from src.config import EXPERT_WEIGHTS, TPI_COMPONENTS


def seasonal_adjust_group(series: pd.Series, dates: pd.Series) -> pd.Series:
    """Désaisonnalisation robuste de type STL (tendance centrée + médiane saisonnière mensuelle)."""
    s = series.astype(float).copy()
    trend = s.rolling(window=12, center=True, min_periods=4).mean()
    detrended = s - trend
    months = pd.to_datetime(dates).dt.month
    seasonal_pattern = detrended.groupby(months).transform("median").fillna(0.0)
    seasonal_pattern = seasonal_pattern - seasonal_pattern.mean()
    return (s - seasonal_pattern).clip(lower=0.01)


def _scale_0_100(series: pd.Series, log_transform: bool = False, floor: float = 16.0, ceil: float = 88.0) -> pd.Series:
    """Normalisation robuste sur [floor, ceil] avec marge haute pour éviter la saturation des pôles moteurs."""
    vals = np.log1p(series.clip(lower=0.0)) if log_transform else series.astype(float)
    q_low = float(vals.quantile(0.01))
    q_high = float(vals.max())
    denom = (q_high - q_low) if abs(q_high - q_low) > 1e-9 else 1.0
    norm = ((vals - q_low) / denom).clip(0.0, 1.0)
    return (floor + norm * (ceil - floor)).round(2)


def compute_pca_weights(df_norm: pd.DataFrame) -> Dict[str, float]:
    """Calcule les poids issus de la 1re composante principale (ACP par SVD)."""
    X = df_norm[TPI_COMPONENTS].to_numpy(dtype=float)
    X_std = (X - X.mean(axis=0)) / np.where(X.std(axis=0) > 1e-9, X.std(axis=0), 1.0)
    _, _, vt = np.linalg.svd(X_std, full_matrices=False)
    loadings = np.abs(vt[0])
    weights = loadings / loadings.sum()
    return {col: round(float(w), 4) for col, w in zip(TPI_COMPONENTS, weights)}


def run_weight_sensitivity(df: pd.DataFrame, n_draws: int = 200, perturbation: float = 0.25, seed: int = 7) -> dict:
    """Évalue la stabilité du classement provincial sous perturbation aléatoire des poids (±25 %)."""
    rng = np.random.default_rng(seed)
    latest_date = df["date"].max()
    latest = df[df["date"] == latest_date].sort_values("province_id").reset_index(drop=True)
    base_scores = latest["tpi_score"].to_numpy()
    base_ranks = pd.Series(base_scores).rank(ascending=False).to_numpy()

    X = latest[TPI_COMPONENTS].to_numpy(dtype=float)
    w_vec = np.array([EXPERT_WEIGHTS[c] for c in TPI_COMPONENTS])

    rank_corrs = []
    max_score_shift = []
    exact_top3_matches = 0
    base_top3 = set(np.argsort(-base_scores)[:3])

    for _ in range(n_draws):
        noise = rng.uniform(1.0 - perturbation, 1.0 + perturbation, size=len(w_vec))
        w_p = (w_vec * noise)
        w_p = w_p / w_p.sum()
        scores_p = X @ w_p
        ranks_p = pd.Series(scores_p).rank(ascending=False).to_numpy()
        corr = float(np.corrcoef(base_ranks, ranks_p)[0, 1])
        rank_corrs.append(corr)
        max_score_shift.append(float(np.max(np.abs(scores_p - base_scores))))
        if set(np.argsort(-scores_p)[:3]) == base_top3:
            exact_top3_matches += 1

    return {
        "n_simulations": n_draws,
        "perturbation_pct": int(perturbation * 100),
        "mean_spearman_rank_corr": round(float(np.mean(rank_corrs)), 4),
        "min_spearman_rank_corr": round(float(np.min(rank_corrs)), 4),
        "mean_max_score_diff_pts": round(float(np.mean(max_score_shift)), 2),
        "top3_stability_pct": round(100.0 * exact_top3_matches / n_draws, 1),
    }


def compute_tpi(panel: pd.DataFrame) -> Tuple[pd.DataFrame, dict]:
    """Calcule les composantes désaisonnalisées, l'indice TPI (0-100), l'ACP et la sensibilité."""
    df = panel.copy()

    # Désaisonnalisation par province
    sa_specs = [
        ("nightlights_mean", "nightlights_raw_sa"),
        ("business_creations", "business_raw_sa"),
        ("tourism_nights", "tourism_raw_sa"),
        ("port_traffic_kt", "port_raw_sa"),
        ("web_trends_index", "trends_raw_sa"),
        ("job_offers_count", "jobs_raw_sa"),
        ("hcp_employment_index", "hcp_emp_raw_sa"),
    ]
    for raw_col, sa_col in sa_specs:
        df[sa_col] = df.groupby("province_id", group_keys=False).apply(
            lambda g: seasonal_adjust_group(g[raw_col], g["date"]), include_groups=False
        ).reindex(df.index)

    # Normalisation sur [0, 100]
    df["nightlights_sa"] = _scale_0_100(df["nightlights_raw_sa"], log_transform=True, floor=20.0, ceil=90.0)
    df["business_creations_sa"] = _scale_0_100(df["business_raw_sa"], log_transform=True, floor=22.0, ceil=89.0)
    df["tourism_nights_sa"] = _scale_0_100(df["tourism_raw_sa"], log_transform=True, floor=18.0, ceil=88.0)
    df["port_traffic_sa"] = _scale_0_100(df["port_raw_sa"], log_transform=True, floor=15.0, ceil=92.0)
    df["web_trends_sa"] = _scale_0_100(df["trends_raw_sa"], log_transform=False, floor=24.0, ceil=89.0)

    emp_hcp_scaled = _scale_0_100(df["hcp_emp_raw_sa"], log_transform=False, floor=24.0, ceil=90.0)
    jobs_scaled = _scale_0_100(df["jobs_raw_sa"], log_transform=True, floor=22.0, ceil=90.0)
    df["employment_idx"] = (0.55 * emp_hcp_scaled + 0.45 * jobs_scaled).round(2)

    # Indice TPI pondéré (avis expert)
    tpi_vals = np.zeros(len(df), dtype=float)
    for col, w in EXPERT_WEIGHTS.items():
        tpi_vals += w * df[col].to_numpy(dtype=float)
    df["tpi_score"] = np.round(tpi_vals, 2)

    # Indice alternatif par ACP
    pca_weights = compute_pca_weights(df)
    pca_vals = np.zeros(len(df), dtype=float)
    for col, w in pca_weights.items():
        pca_vals += w * df[col].to_numpy(dtype=float)
    df["tpi_pca_score"] = np.round(pca_vals, 2)

    # Classement mensuel (1 = meilleur)
    df["tpi_rank"] = df.groupby("date")["tpi_score"].rank(ascending=False, method="min").astype(int)

    # Corrélation TPI expert vs TPI ACP
    pca_corr = float(np.corrcoef(df["tpi_score"], df["tpi_pca_score"])[0, 1])
    sensitivity = run_weight_sensitivity(df)

    meta = {
        "expert_weights": EXPERT_WEIGHTS,
        "pca_weights": pca_weights,
        "expert_vs_pca_corr": round(pca_corr, 4),
        "sensitivity": sensitivity,
    }
    return df, meta
