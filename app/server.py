"""Serveur FastAPI de Territorial Pulse exposant l'API analytique, l'export PDF et l'interface web."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Dict, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.config import PROCESSED_DIR
from src.model import TerritorialPulseModel
from src.modeling.alerts import detect_alerts
from src.pdf_export import generate_province_fiche_pdf

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"

app = FastAPI(
    title="Territorial Pulse API",
    description="Baromètre intelligent de l'économie territoriale — Tanger-Tétouan-Al Hoceïma",
    version="1.0.0",
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

_MODEL = TerritorialPulseModel()


class SimulationRequest(BaseModel):
    province_id: str
    shocks_pct: Dict[str, float]


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    html_path = STATIC_DIR / "index.html"
    if not html_path.exists():
        return HTMLResponse("<h1>Territorial Pulse</h1><p>Interface en cours d'initialisation.</p>")
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": "1.0.0"}


@app.get("/api/bootstrap")
def bootstrap() -> dict:
    """Charge en une requête tout le nécessaire pour une animation fluide à 60 fps côté client."""
    df = _MODEL.df
    dates = sorted(df["date"].unique().tolist())

    # Indexation compacte par date -> liste des enregistrements provinciaux
    frames: Dict[str, list] = {}
    cols = [
        "province_id",
        "province_name",
        "province_type",
        "tpi_score",
        "tpi_rank",
        "cluster_label",
        "nightlights_mean",
        "nightlights_sa",
        "employment_idx",
        "hcp_employment_index",
        "hcp_unemployment_rate",
        "business_creations",
        "business_creations_sa",
        "tourism_nights",
        "tourism_nights_sa",
        "port_traffic_kt",
        "port_traffic_sa",
        "web_trends_index",
        "web_trends_sa",
        "job_offers_count",
    ]
    for dt, grp in df.groupby("date"):
        frames[dt] = grp[cols].to_dict(orient="records")

    return {
        "dates": dates,
        "frames": frames,
        "geojson": _MODEL.get_geojson(),
        "nightlight_points": _MODEL.get_nightlight_points(),
        "results": _MODEL.metadata,
    }


@app.get("/api/province/{province_id}")
def province_detail(province_id: str) -> dict:
    try:
        return _MODEL.get_province_profile(province_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/simulate")
def simulate(req: SimulationRequest) -> dict:
    try:
        return _MODEL.simulate_what_if(req.province_id, req.shocks_pct)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/alerts")
def custom_alerts(
    drop_3m_pct: Annotated[float, Query(ge=-30.0, le=0.0)] = -5.0,
    surge_12m_pct: Annotated[float, Query(ge=1.0, le=40.0)] = 10.0,
    stagnation_months: Annotated[int, Query(ge=3, le=18)] = 6,
) -> dict:
    return detect_alerts(
        _MODEL.df,
        thresholds={
            "drop_3m_pct": drop_3m_pct,
            "surge_12m_pct": surge_12m_pct,
            "stagnation_months": stagnation_months,
        },
    )


@app.get("/api/fiche/{province_id}.pdf")
def export_fiche_pdf(province_id: str) -> Response:
    try:
        pdf_bytes = generate_province_fiche_pdf(province_id, model=_MODEL)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    filename = f"Fiche_Territoire_{province_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/download/{artifact}")
def download_dataset(artifact: str) -> FileResponse:
    mapping = {
        "csv": PROCESSED_DIR / "dataset_panel.csv",
        "parquet": PROCESSED_DIR / "dataset_panel.parquet",
        "duckdb": PROCESSED_DIR / "territorial_pulse.duckdb",
        "dictionary": PROCESSED_DIR / "data_dictionary.md",
    }
    path = mapping.get(artifact)
    if path is None or not path.exists():
        raise HTTPException(status_code=404, detail="Artefact introuvable")
    return FileResponse(path=str(path), filename=path.name)
