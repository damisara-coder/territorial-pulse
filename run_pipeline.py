"""Script principal exécutant la chaîne complète de Territorial Pulse en une commande.

Collecte -> Panel unifié -> Indice TPI & ACP -> Typologie -> Nowcasting -> Validation -> Alertes -> Export DuckDB/Parquet/JSON.
"""

from __future__ import annotations

import json
import time

from src.config import PROCESSED_DIR
from src.modeling.alerts import detect_alerts
from src.modeling.nowcasting import run_nowcasting
from src.modeling.tpi_index import compute_tpi
from src.modeling.typology import build_typology
from src.modeling.validation import compute_validation_report
from src.pipeline.build_panel import build_raw_panel, save_panel_outputs


def run_all() -> dict:
    t0 = time.perf_counter()
    print("[1/6] Construction du GeoJSON, nuage VIIRS et assemblage du panel brut...")
    raw_panel = build_raw_panel(seed=42)

    print("[2/6] Désaisonnalisation (STL), normalisation et calcul du TPI (+ ACP & sensibilité)...")
    tpi_panel, tpi_meta = compute_tpi(raw_panel)

    print("[3/6] Classification territoriale K-Means (Moteurs, En transition, Fragiles)...")
    full_panel, typology_summary = build_typology(tpi_panel)

    print("[4/6] Entraînement et backtesting glissant du modèle de nowcasting...")
    nowcast_results = run_nowcasting(full_panel)

    print("[5/6] Validation scientifique croisée avec le HCP et détection d'alertes...")
    validation_report = compute_validation_report(full_panel, nowcast_results)
    alerts_report = detect_alerts(full_panel)

    print("[6/6] Export CSV, Parquet, DuckDB et artefacts JSON...")
    csv_path, parquet_path, duckdb_path = save_panel_outputs(full_panel)

    # Synthèse régionale du dernier mois et évolution trimestrielle
    dates = sorted(full_panel["date"].unique())
    latest_date = dates[-1]
    prev_q_date = dates[-4]
    reg_latest = float(full_panel[full_panel["date"] == latest_date]["tpi_score"].mean())
    reg_prev_q = float(full_panel[full_panel["date"] == prev_q_date]["tpi_score"].mean())

    model_results = {
        "metadata": {
            "region": "Tanger-Tétouan-Al Hoceïma",
            "n_provinces": int(full_panel["province_id"].nunique()),
            "n_months": int(full_panel["date"].nunique()),
            "n_rows": int(len(full_panel)),
            "start_date": dates[0],
            "latest_date": latest_date,
        },
        "regional_summary": {
            "latest_tpi": round(reg_latest, 1),
            "delta_vs_prev_quarter": round(reg_latest - reg_prev_q, 1),
            "n_moteurs": len(typology_summary["clusters"][0]["provinces"]),
            "n_transition": len(typology_summary["clusters"][1]["provinces"]),
            "n_fragiles": len(typology_summary["clusters"][2]["provinces"]),
        },
        "tpi_methodology": tpi_meta,
        "typology": typology_summary,
        "nowcasting": nowcast_results,
        "validation": validation_report,
        "alerts": alerts_report,
    }

    (PROCESSED_DIR / "model_results.json").write_text(
        json.dumps(model_results, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    elapsed = time.perf_counter() - t0
    print(f"\nPipeline terminé avec succès en {elapsed:.2f} s !")
    print(f" - Panel CSV     : {csv_path}")
    print(f" - Panel Parquet : {parquet_path}")
    print(f" - Base DuckDB   : {duckdb_path}")
    print(f" - TPI régional  : {model_results['regional_summary']['latest_tpi']}/100 ({model_results['regional_summary']['delta_vs_prev_quarter']:+.1f} pts vs trim. préc.)")
    print(f" - Nowcast nov.  : {nowcast_results['regional_nowcast']['forecast_tpi']} ± {nowcast_results['regional_nowcast']['uncertainty_halfwidth']}")
    print(f" - Corrélation r : {validation_report['global_correlations']['nightlights_vs_hcp_pearson']} (lumière vs emploi HCP)")
    print(f" - Nowcast RMSE  : {nowcast_results['hcp_nowcast_metrics']['rmse_model']} vs naïf {nowcast_results['hcp_nowcast_metrics']['rmse_naive']} (gain {nowcast_results['hcp_nowcast_metrics']['rmse_gain_pct']} %)")
    return model_results


if __name__ == "__main__":
    run_all()
