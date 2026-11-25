"""Point d'entrée Streamlit alternatif pour déploiement rapide sur Streamlit Community Cloud.

Usage : streamlit run app/streamlit_app.py
Pour l'interface complète haute fluidité (Vue Nuit + Simulateur + Export API), utilisez :
python -m uvicorn app.server:app --reload
"""

from __future__ import annotations

import streamlit as st

from src.model import TerritorialPulseModel
from src.pdf_export import generate_province_fiche_pdf

st.set_page_config(page_title="Territorial Pulse — TTA 2026", layout="wide")
st.title("TERRITORIAL PULSE — Baromètre de l'économie territoriale")
st.caption("Région Tanger-Tétouan-Al Hoceïma (2019–2025)")

model = TerritorialPulseModel()
df = model.df
meta = model.metadata

dates = sorted(df["date"].unique().tolist())
selected_date = st.select_slider("Mois d'observation", options=dates, value=dates[-1])
snap = df[df["date"] == selected_date].sort_values("tpi_score", ascending=False)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Indice régional TPI", f"{snap['tpi_score'].mean():.1f} / 100")
c2.metric("Territoires Moteurs", f"{(snap['cluster_label'] == 'Moteur').sum()} / 8")
c3.metric("Territoires Fragiles", f"{(snap['cluster_label'] == 'Fragile').sum()} / 8")
nc = meta["nowcasting"]["regional_nowcast"]
c4.metric("Nowcast Nov. 2025", f"{nc['forecast_tpi']} ± {nc['uncertainty_halfwidth']}")

st.subheader(f"Classement TPI — {selected_date}")
st.bar_chart(snap.set_index("province_name")["tpi_score"])

st.subheader("Fiche Territoire (Export PDF)")
prov_map = dict(zip(snap["province_name"], snap["province_id"]))
sel_name = st.selectbox("Choisir une province", list(prov_map.keys()))
pdf_bytes = generate_province_fiche_pdf(prov_map[sel_name], model=model)
st.download_button(
    label=f"Télécharger la Fiche PDF — {sel_name}",
    data=pdf_bytes,
    file_name=f"Fiche_{sel_name}.pdf",
    mime="application/pdf",
)
