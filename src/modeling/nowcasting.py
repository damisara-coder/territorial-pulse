"""Modèle de nowcasting (prévision à court terme) avec validation glissante et incertitude."""

from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from src.config import FORECAST_DATE, PROVINCES


def _fit_ridge(X: np.ndarray, y: np.ndarray, alpha: float = 4.0) -> Tuple[np.ndarray, float, np.ndarray, np.ndarray]:
    """Régression Ridge L2 en forme fermée avec standardisation des variables."""
    mean_x = X.mean(axis=0)
    std_x = np.where(X.std(axis=0) > 1e-8, X.std(axis=0), 1.0)
    Xs = (X - mean_x) / std_x
    mean_y = float(y.mean())
    yc = y - mean_y
    n_feat = Xs.shape[1]
    coef = np.linalg.solve(Xs.T @ Xs + alpha * np.eye(n_feat), Xs.T @ yc)
    return coef, mean_y, mean_x, std_x


def _predict_ridge(X: np.ndarray, coef: np.ndarray, mean_y: float, mean_x: np.ndarray, std_x: np.ndarray) -> np.ndarray:
    Xs = (X - mean_x) / std_x
    return mean_y + Xs @ coef


def run_nowcasting(df: pd.DataFrame) -> dict:
    """Exécute le nowcasting glissant pour l'emploi HCP et le TPI du mois suivant (nov. 2025)."""
    work = df.sort_values(["province_id", "date"]).copy()

    # Variables disponibles en temps quasi réel (sans délai de publication HCP)
    work["nl_lag1"] = work.groupby("province_id")["nightlights_sa"].shift(1)
    work["trends_lag1"] = work.groupby("province_id")["web_trends_sa"].shift(1)
    work["jobs_lag0"] = work.groupby("province_id")["job_offers_count"].transform(
        lambda s: 100.0 * (s - s.min()) / max(float(s.max() - s.min()), 1.0)
    )
    work["hcp_lag2"] = work.groupby("province_id")["hcp_employment_index"].shift(2)
    work["tpi_lag1"] = work.groupby("province_id")["tpi_score"].shift(1)
    work["tpi_lag2"] = work.groupby("province_id")["tpi_score"].shift(2)
    work["tpi_next"] = work.groupby("province_id")["tpi_score"].shift(-1)

    dates = sorted(work["date"].unique())

    # 1) Nowcast temps quasi réel de l'indice d'emploi HCP (en supposant un décalage de publication de 2 mois)
    hcp_features = [
        "nightlights_sa",
        "nl_lag1",
        "web_trends_sa",
        "trends_lag1",
        "business_creations_sa",
        "tourism_nights_sa",
        "port_traffic_sa",
        "jobs_lag0",
        "hcp_lag2",
    ]
    hcp_eval = work.dropna(subset=hcp_features + ["hcp_employment_index"]).copy()
    backtest_dates = dates[24:]  # 2021-01 -> 2025-10

    preds_hcp = []
    for dt in backtest_dates:
        train = hcp_eval[hcp_eval["date"] < dt]
        test = hcp_eval[hcp_eval["date"] == dt]
        if len(train) < 32 or len(test) == 0:
            continue
        coef, my, mx, sx = _fit_ridge(train[hcp_features].to_numpy(), train["hcp_employment_index"].to_numpy(), alpha=6.0)
        y_hat = _predict_ridge(test[hcp_features].to_numpy(), coef, my, mx, sx)
        for idx, pred_val in zip(test.index, y_hat):
            preds_hcp.append(
                {
                    "province_id": test.loc[idx, "province_id"],
                    "province_name": test.loc[idx, "province_name"],
                    "date": dt,
                    "actual_hcp": float(test.loc[idx, "hcp_employment_index"]),
                    "pred_hcp": round(float(pred_val), 2),
                    "naive_hcp": float(test.loc[idx, "hcp_lag2"]),
                }
            )

    hcp_bt = pd.DataFrame(preds_hcp)
    rmse_model = float(np.sqrt(np.mean((hcp_bt["actual_hcp"] - hcp_bt["pred_hcp"]) ** 2)))
    rmse_naive = float(np.sqrt(np.mean((hcp_bt["actual_hcp"] - hcp_bt["naive_hcp"]) ** 2)))
    mae_model = float(np.mean(np.abs(hcp_bt["actual_hcp"] - hcp_bt["pred_hcp"])))
    mae_naive = float(np.mean(np.abs(hcp_bt["actual_hcp"] - hcp_bt["naive_hcp"])))
    mape_model = float(np.mean(np.abs((hcp_bt["actual_hcp"] - hcp_bt["pred_hcp"]) / hcp_bt["actual_hcp"])) * 100.0)
    mape_naive = float(np.mean(np.abs((hcp_bt["actual_hcp"] - hcp_bt["naive_hcp"]) / hcp_bt["actual_hcp"])) * 100.0)

    # Importance des variables (modèle complet sur tout l'historique disponible)
    coef_full, my_full, mx_full, sx_full = _fit_ridge(
        hcp_eval[hcp_features].to_numpy(), hcp_eval["hcp_employment_index"].to_numpy(), alpha=6.0
    )
    abs_imp = np.abs(coef_full)
    abs_imp_norm = 100.0 * abs_imp / max(float(abs_imp.sum()), 1e-9)
    feature_labels = {
        "nightlights_sa": "Lumière nocturne (VIIRS t)",
        "nl_lag1": "Lumière nocturne (t-1)",
        "web_trends_sa": "Recherches web (Trends t)",
        "trends_lag1": "Recherches web (t-1)",
        "business_creations_sa": "Créations d'entreprises (OMPIC)",
        "tourism_nights_sa": "Nuitées touristiques",
        "port_traffic_sa": "Trafic portuaire",
        "jobs_lag0": "Offres d'emploi en ligne",
        "hcp_lag2": "Emploi HCP retardé (t-2)",
    }
    feature_importance = sorted(
        [
            {"feature": f, "label": feature_labels[f], "importance_pct": round(float(imp), 1), "coef_std": round(float(c), 3)}
            for f, imp, c in zip(hcp_features, abs_imp_norm, coef_full)
        ],
        key=lambda x: x["importance_pct"],
        reverse=True,
    )

    # 2) Prévision du TPI du mois suivant (2025-11-01) avec intervalle de confiance à 90 %
    tpi_features = [
        "tpi_score",
        "tpi_lag1",
        "tpi_lag2",
        "nightlights_sa",
        "web_trends_sa",
        "business_creations_sa",
        "tourism_nights_sa",
        "port_traffic_sa",
        "employment_idx",
    ]
    tpi_train_all = work.dropna(subset=tpi_features + ["tpi_next"]).copy()

    # Backtest glissant du TPI t+1 pour calibrer l'intervalle d'incertitude
    tpi_bt_rows = []
    for dt in dates[24:-1]:
        tr = tpi_train_all[tpi_train_all["date"] < dt]
        te = tpi_train_all[tpi_train_all["date"] == dt]
        if len(tr) < 32 or len(te) == 0:
            continue
        c_t, my_t, mx_t, sx_t = _fit_ridge(tr[tpi_features].to_numpy(), tr["tpi_next"].to_numpy(), alpha=8.0)
        p_t = _predict_ridge(te[tpi_features].to_numpy(), c_t, my_t, mx_t, sx_t)
        for idx, pv in zip(te.index, p_t):
            tpi_bt_rows.append(
                {
                    "province_id": te.loc[idx, "province_id"],
                    "date": dt,
                    "actual_tpi_next": float(te.loc[idx, "tpi_next"]),
                    "pred_tpi_next": round(float(pv), 2),
                    "naive_tpi_next": float(te.loc[idx, "tpi_score"]),
                }
            )
    tpi_bt = pd.DataFrame(tpi_bt_rows)
    residuals = np.abs(tpi_bt["actual_tpi_next"] - tpi_bt["pred_tpi_next"])
    margin_90_prov = float(np.quantile(residuals, 0.90))
    tpi_rmse_model = float(np.sqrt(np.mean((tpi_bt["actual_tpi_next"] - tpi_bt["pred_tpi_next"]) ** 2)))
    tpi_rmse_naive = float(np.sqrt(np.mean((tpi_bt["actual_tpi_next"] - tpi_bt["naive_tpi_next"]) ** 2)))

    # Modèle final pour prédire 2025-11-01 à partir d'octobre 2025
    c_final, my_final, mx_final, sx_final = _fit_ridge(
        tpi_train_all[tpi_features].to_numpy(), tpi_train_all["tpi_next"].to_numpy(), alpha=8.0
    )
    latest_date = dates[-1]
    latest_rows = work[work["date"] == latest_date].sort_values("province_id").copy()
    latest_preds = _predict_ridge(latest_rows[tpi_features].to_numpy(), c_final, my_final, mx_final, sx_final)

    province_nowcasts: List[dict] = []
    for (_, row), pred_tpi in zip(latest_rows.iterrows(), latest_preds):
        pred_clamped = float(np.clip(pred_tpi, 5.0, 98.0))
        q_low = float(np.clip(pred_clamped - margin_90_prov, 0.0, 100.0))
        q_high = float(np.clip(pred_clamped + margin_90_prov, 0.0, 100.0))
        province_nowcasts.append(
            {
                "province_id": row["province_id"],
                "province_name": row["province_name"],
                "latest_date": latest_date,
                "forecast_date": FORECAST_DATE,
                "current_tpi": round(float(row["tpi_score"]), 2),
                "forecast_tpi": round(pred_clamped, 2),
                "uncertainty_halfwidth": round(margin_90_prov, 2),
                "ci_low": round(q_low, 2),
                "ci_high": round(q_high, 2),
                "delta_vs_current": round(pred_clamped - float(row["tpi_score"]), 2),
            }
        )

    reg_current = float(latest_rows["tpi_score"].mean())
    reg_forecast = float(np.mean([x["forecast_tpi"] for x in province_nowcasts]))
    # Incertitude régionale agrégée (réduction par moyenne sur 8 territoires avec corrélation inter-provinciale)
    reg_margin = round(max(1.2, margin_90_prov * 0.55), 1)

    return {
        "forecast_date": FORECAST_DATE,
        "regional_nowcast": {
            "current_tpi": round(reg_current, 1),
            "forecast_tpi": round(reg_forecast, 1),
            "uncertainty_halfwidth": reg_margin,
            "ci_low": round(reg_forecast - reg_margin, 1),
            "ci_high": round(reg_forecast + reg_margin, 1),
        },
        "province_nowcasts": province_nowcasts,
        "hcp_nowcast_metrics": {
            "rmse_model": round(rmse_model, 3),
            "rmse_naive": round(rmse_naive, 3),
            "rmse_gain_pct": round(100.0 * (rmse_naive - rmse_model) / max(rmse_naive, 1e-9), 1),
            "mae_model": round(mae_model, 3),
            "mae_naive": round(mae_naive, 3),
            "mape_model_pct": round(mape_model, 2),
            "mape_naive_pct": round(mape_naive, 2),
            "beats_naive": bool(rmse_model < rmse_naive),
        },
        "tpi_forecast_metrics": {
            "rmse_model": round(tpi_rmse_model, 3),
            "rmse_naive": round(tpi_rmse_naive, 3),
            "beats_naive": bool(tpi_rmse_model < tpi_rmse_naive),
            "interval_90_halfwidth": round(margin_90_prov, 2),
        },
        "feature_importance": feature_importance,
        "backtest_series": hcp_bt.to_dict(orient="records"),
    }
