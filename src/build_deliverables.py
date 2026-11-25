"""Génération des livrables finaux : Rapport PDF (7 pages) et Pitch Deck PPTX (8 slides) à partir des vrais résultats."""

from __future__ import annotations

import io
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from src.config import DOCS_DIR
from src.model import TerritorialPulseModel


def _chart_regional_evolution(df: pd.DataFrame) -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(7.2, 2.8), dpi=240)
    dates = sorted(df["date"].unique())
    x = np.arange(len(dates))
    palette = {"TTA-01": "#0A192F", "TTA-02": "#157F5F", "TTA-03": "#3B82F6", "TTA-07": "#E06A47", "TTA-08": "#D1495B"}
    for pid, col in palette.items():
        sub = df[df["province_id"] == pid].sort_values("date")
        ax.plot(x, sub["tpi_score"], label=sub["province_name"].iloc[0], color=col, linewidth=2.0)
    tick_idx = [0, 12, 24, 36, 48, 60, 72, len(dates) - 1]
    ax.set_xticks(tick_idx)
    ax.set_xticklabels([dates[i][:4] for i in tick_idx], fontsize=8)
    ax.set_ylabel("Indice TPI (0-100)", fontsize=8.5)
    ax.set_title("Trajectoires TPI (2019–2025) : Corridor vs Arrière-pays", loc="left", fontsize=10, fontweight="bold", color="#0A192F")
    ax.grid(axis="y", linestyle=":", alpha=0.4)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(frameon=False, ncol=3, fontsize=8, loc="upper left")
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=240)
    plt.close(fig)
    buf.seek(0)
    return buf


def _chart_validation_scatter(df: pd.DataFrame, r_val: float) -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(6.8, 2.7), dpi=240)
    x = np.log1p(df["nightlights_mean"])
    y = df["hcp_employment_index"]
    ax.scatter(x, y, alpha=0.45, s=18, color="#157F5F", edgecolors="none")
    m, b = np.polyfit(x, y, 1)
    xs = np.linspace(x.min(), x.max(), 50)
    ax.plot(xs, m * xs + b, color="#F4B43A", linewidth=2.2, label=f"Régression linéaire (r = {r_val:.3f})")
    ax.set_xlabel("log(1 + Radiance VIIRS moyenne)", fontsize=8.5)
    ax.set_ylabel("Indice d'emploi HCP", fontsize=8.5)
    ax.set_title("Validation scientifique : Luminosité nocturne vs Emploi officiel HCP", loc="left", fontsize=10, fontweight="bold", color="#0A192F")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(True, linestyle=":", alpha=0.35)
    ax.legend(frameon=False, fontsize=8.5)
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=240)
    plt.close(fig)
    buf.seek(0)
    return buf


def build_report_pdf(model: TerritorialPulseModel | None = None) -> Path:
    """Génère le rapport PDF (7 pages) aligné sur les chiffres calculés du modèle."""
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    tp = model or TerritorialPulseModel()
    df = tp.df
    meta = tp.metadata
    out_path = DOCS_DIR / "Rapport_Territorial_Pulse_2026.pdf"

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("TP_H1", parent=styles["Heading1"], fontSize=15, textColor=colors.HexColor("#0A192F"), spaceBefore=10, spaceAfter=6)
    h2 = ParagraphStyle("TP_H2", parent=styles["Heading2"], fontSize=11.5, textColor=colors.HexColor("#157F5F"), spaceBefore=8, spaceAfter=4)
    body = ParagraphStyle("TP_Body", parent=styles["Normal"], fontSize=9.8, leading=14, textColor=colors.HexColor("#1E293B"), spaceAfter=6)
    title_big = ParagraphStyle("TP_Title", parent=styles["Title"], fontSize=24, leading=28, textColor=colors.HexColor("#0A192F"), alignment=0)
    subtitle_st = ParagraphStyle("TP_Sub", parent=styles["Normal"], fontSize=12, leading=16, textColor=colors.HexColor("#475569"))

    doc = SimpleDocTemplate(str(out_path), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=18 * mm, bottomMargin=18 * mm)
    story = []

    # Page de garde
    story.append(Spacer(1, 22 * mm))
    story.append(Paragraph("DATATHON DATA-TERRITOIRES 2026 • THÉMATIQUE 05", ParagraphStyle("Eyebrow", fontSize=10, textColor=colors.HexColor("#D97706"), fontName="Helvetica-Bold")))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Territorial Pulse", title_big))
    story.append(Paragraph("Baromètre intelligent de l'économie territoriale en temps quasi réel — Région Tanger-Tétouan-Al Hoceïma", subtitle_st))
    story.append(Spacer(1, 10 * mm))

    nc = meta["nowcasting"]["regional_nowcast"]
    val = meta["validation"]
    hm = meta["nowcasting"]["hcp_nowcast_metrics"]
    summary_tbl = Table(
        [
            ["Indicateur clé", "Résultat calculé (2019–2025)"],
            ["Couverture du panel", f"{meta['metadata']['n_provinces']} provinces × {meta['metadata']['n_months']} mois ({meta['metadata']['n_rows']} observations)"],
            ["Indice régional TPI (Oct. 2025)", f"{meta['regional_summary']['latest_tpi']} / 100 (Nowcast Nov. : {nc['forecast_tpi']} ± {nc['uncertainty_halfwidth']})"],
            ["Corrélation Lumière VIIRS vs Emploi HCP", f"r = {val['global_correlations']['nightlights_vs_hcp_pearson']} (Spearman ρ = {val['global_correlations']['nightlights_vs_hcp_spearman']})"],
            ["Performance Nowcasting vs Modèle Naïf", f"RMSE = {hm['rmse_model']} vs {hm['rmse_naive']} (gain {hm['rmse_gain_pct']} %)"],
            ["Écart territorial Tanger / arrière-pays", f"×{val['territorial_gap']['gap_ratio']} ({val['territorial_gap']['tanger_tpi']} vs {val['territorial_gap']['hinterland_mean_tpi']})"],
        ],
        colWidths=[75 * mm, 98 * mm],
    )
    summary_tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0A192F")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F8FAFC")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(summary_tbl)
    story.append(Spacer(1, 12 * mm))
    story.append(Paragraph("Question centrale : Comment mesurer, chaque mois et pour chaque province, le dynamisme économique de la région, détecter précocement les territoires qui décrochent, et orienter l'investissement public vers ceux qui en ont le plus besoin ?", body))
    story.append(PageBreak())

    # Section 1 & 2
    story.append(Paragraph("1. Contexte, problématique et enjeux territoriaux", h1))
    story.append(Paragraph("La région Tanger-Tétouan-Al Hoceïma connaît une transformation économique rapide portée par le complexe portuaire Tanger Med, les zones franches industrielles (TFZ, TAC) et le tourisme littoral. Toutefois, cette dynamique accentue les disparités territoriales entre le corridor nord-ouest (Tanger-Assilah, Fahs-Anjra, Tétouan) et les provinces de l'arrière-pays (Chefchaouen, Ouezzane). Les statistiques officielles (HCP) étant publiées avec un décalage temporel et à une granularité souvent trimestrielle ou annuelle, les décideurs manquent d'un baromètre mensuel homogène.", body))
    story.append(Paragraph("Territorial Pulse répond à ce besoin en croisant les données officielles du HCP avec des sources non conventionnelles à haute fréquence (luminosité nocturne satellitaire VIIRS, recherches web Google Trends, offres d'emploi en ligne agrégées) afin de produire un pilotage territorial en temps quasi réel.", body))

    story.append(Paragraph("2. Données, sources et chaîne de traitement", h1))
    sources_tbl = Table(
        [
            ["Source", "Type", "Variable", "Fréquence"],
            ["HCP (Enquêtes emploi, RGPH)", "Officielle", "Indice emploi, chômage, activité", "Mensualisée"],
            ["NASA Black Marble / VIIRS", "Satellite (Non conv.)", "Radiance nocturne zonale (nW/cm²/sr)", "Mensuelle"],
            ["OMPIC", "Administrative", "Créations d'entreprises", "Mensuelle"],
            ["Observatoire du Tourisme", "Administrative", "Nuitées hôtelières", "Mensuelle"],
            ["Autorité Portuaire Tanger Med", "Logistique", "Trafic portuaire et conteneurs", "Mensuelle"],
            ["Google Trends & Portails emploi", "Big Data Web (Non conv.)", "Requêtes d'intention & offres d'emploi", "Mensuelle"],
        ],
        colWidths=[52 * mm, 36 * mm, 55 * mm, 30 * mm],
    )
    sources_tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0A192F")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("PADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(sources_tbl)
    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph("L'ensemble des séries est harmonisé sur la clé unique (province_id, date) au format Parquet et stocké dans une base analytique DuckDB, après désaisonnalisation de type STL (tendance centrée + médiane saisonnière mensuelle) et contrôles qualité automatisés (0 valeur manquante sur 656 lignes).", body))

    # Section 3
    story.append(Paragraph("3. Méthodologie : TPI, Validation, Typologie et Nowcasting", h1))
    story.append(Paragraph("3.1 Indice composite TPI et test de sensibilité", h2))
    story.append(Paragraph(f"L'indice Territorial Pulse Index (TPI, 0 à 100) agrège 6 composantes désaisonnalisées et normalisées : Lumière VIIRS (25 %), Emploi & offres (25 %), Créations d'entreprises (15 %), Trafic portuaire (13 %), Tourisme (12 %) et Recherches web (10 %). La comparaison avec une pondération objective par Analyse en Composantes Principales (ACP) obtient une corrélation de r = {meta['tpi_methodology']['expert_vs_pca_corr']}. Un test de sensibilité Monte Carlo (200 tirages à ±25 % sur les poids) confirme une stabilité du Top 3 de {meta['tpi_methodology']['sensitivity']['top3_stability_pct']} % et une corrélation de rang moyenne de {meta['tpi_methodology']['sensitivity']['mean_spearman_rank_corr']}.", body))

    story.append(Paragraph("3.2 Nowcasting et Typologie", h2))
    story.append(Paragraph(f"Pour simuler le délai réel de publication des statistiques officielles, le modèle de nowcasting (Régression Ridge L2) estime l'emploi HCP du mois courant t en utilisant uniquement les signaux temps réel et l'historique HCP à t-2. En validation glissante sur 2021–2025, le modèle atteint un RMSE de {hm['rmse_model']} contre {hm['rmse_naive']} pour la référence naïve (gain de {hm['rmse_gain_pct']} %). La classification K-Means (k=3) segmente automatiquement les 8 provinces en 3 profils : Moteurs, En transition et Fragiles.", body))
    story.append(PageBreak())

    # Section 4: Résultats et graphiques
    story.append(Paragraph("4. Résultats empiriques et visualisations clés", h1))
    evo_img = _chart_regional_evolution(df)
    val_img = _chart_validation_scatter(df, val["global_correlations"]["nightlights_vs_hcp_pearson"])
    story.append(Image(evo_img, width=170 * mm, height=66 * mm))
    story.append(Spacer(1, 4 * mm))
    story.append(Image(val_img, width=162 * mm, height=64 * mm))
    story.append(Spacer(1, 4 * mm))

    # Classement final Oct 2025
    prov_rows = [["Province", "Profil K-Means", "TPI Oct. 2025", "Var. 12 mois", "Nowcast Nov. 2025"]]
    nc_map = {x["province_id"]: x for x in meta["nowcasting"]["province_nowcasts"]}
    for p in sorted(meta["typology"]["provinces"], key=lambda r: r["tpi_latest"], reverse=True):
        nc_p = nc_map[p["province_id"]]
        prov_rows.append(
            [
                p["province_name"],
                p["cluster_label"],
                f"{p['tpi_latest']:.1f}",
                f"{p['tpi_delta_12m']:+.1f} pts",
                f"{nc_p['forecast_tpi']:.1f} ± {nc_p['uncertainty_halfwidth']:.1f}",
            ]
        )
    rank_tbl = Table(prov_rows, colWidths=[40 * mm, 34 * mm, 30 * mm, 30 * mm, 39 * mm])
    rank_tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0A192F")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("PADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(rank_tbl)
    story.append(PageBreak())

    # Section 5 & 6
    story.append(Paragraph("5. Présentation de l'application Territorial Pulse", h1))
    story.append(Paragraph("L'application web déployée réunit 7 modules opérationnels : (1) Vue Nuit satellitaire animée mois par mois (2019–2025) avec nuage de points lumineux et jauge TPI ; (2) Tableau de bord exécutif clair avec carte choroplèthe ; (3) Comparateur multi-provinces avec graphique radar ; (4) Page Prévisions & validation glissante ; (5) Alertes précoces paramétrables (détectant notamment le choc Covid-19 de 2020) et Typologie ; (6) Simulateur de politique publique « Et si ? » ; (7) Export PDF automatique en 1 clic de la Fiche Territoire.", body))

    story.append(Paragraph("6. Recommandations, limites et perspectives", h1))
    story.append(Paragraph("6.1 Recommandations par groupe de territoires", h2))
    story.append(Paragraph("• Territoires Moteurs (Tanger-Assilah, Fahs-Anjra, Tétouan) : fluidifier l'intégration des PME sous-traitantes autour de Tanger Med et orienter les nouveaux parcs fonciers vers les zones limitrophes en transition.", body))
    story.append(Paragraph("• Territoires En transition (M'diq-Fnideq, Larache, Al Hoceïma) : lisser la forte saisonnalité estivale via la transformation agro-industrielle (Loukkos), l'économie bleue et la diversification des services.", body))
    story.append(Paragraph("• Territoires Fragiles (Chefchaouen, Ouezzane) : accélérer le désenclavement routier vers le corridor Tanger–Tétouan, soutenir les coopératives touristiques/artisanales et déployer un suivi mensuel des alertes emploi.", body))

    story.append(Paragraph("6.2 Limites méthodologiques assumées", h2))
    story.append(Paragraph("La luminosité nocturne mesure efficacement l'activité industrielle, logistique et urbaine, mais sous-estime l'économie agricole rurale (où la production génère peu d'éclairage nocturne) et peut saturer dans les centres denses. L'architecture multi-sources du TPI corrige ce biais en intégrant le HCP, les offres d'emploi et les nuitées touristiques. À terme, l'ajout de l'indice de bâti Sentinel-2 (NDBI) et le passage à l'échelle communale constituent les axes d'extension naturelle vers les 12 régions du Royaume.", body))

    doc.build(story)
    return out_path


def build_pitch_deck_pptx(model: TerritorialPulseModel | None = None) -> Path:
    """Génère le support de présentation PPTX (8 slides, peu de texte, visuels forts)."""
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    tp = model or TerritorialPulseModel()
    meta = tp.metadata
    df = tp.df
    out_path = DOCS_DIR / "Territorial_Pulse_Pitch_Deck.pptx"

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    NAVY = RGBColor(10, 25, 47)
    DARK = RGBColor(8, 18, 33)
    GOLD = RGBColor(244, 180, 58)
    TEAL = RGBColor(21, 127, 95)
    WHITE = RGBColor(248, 250, 252)
    SLATE = RGBColor(148, 163, 184)

    def add_bg(slide, dark: bool = True):
        fill = slide.background.fill
        fill.solid()
        fill.fore_color.rgb = DARK if dark else RGBColor(246, 243, 234)

    def add_title(slide, eyebrow: str, title: str, dark: bool = True):
        tb = slide.shapes.add_textbox(Inches(0.8), Inches(0.5), Inches(11.5), Inches(1.4))
        tf = tb.text_frame
        tf.word_wrap = True
        p0 = tf.paragraphs[0]
        p0.text = eyebrow.upper()
        p0.font.size = Pt(13)
        p0.font.bold = True
        p0.font.color.rgb = GOLD if dark else TEAL
        p1 = tf.add_paragraph()
        p1.text = title
        p1.font.size = Pt(34)
        p1.font.bold = True
        p1.font.color.rgb = WHITE if dark else NAVY

    # Slide 1: Accroche
    s1 = prs.slides.add_slide(blank)
    add_bg(s1, True)
    add_title(s1, "Datathon Data-Territoires 2026 • Thématique 05", "TERRITORIAL PULSE", True)
    tb1 = s1.shapes.add_textbox(Inches(0.8), Inches(2.6), Inches(11.5), Inches(2.5))
    tf1 = tb1.text_frame
    tf1.word_wrap = True
    p = tf1.paragraphs[0]
    p.text = "« Les lumières de la région racontent son économie. »"
    p.font.size = Pt(30)
    p.font.bold = True
    p.font.color.rgb = WHITE
    p2 = tf1.add_paragraph()
    p2.text = "Baromètre intelligent en temps quasi réel — Région Tanger-Tétouan-Al Hoceïma (2019–2025)"
    p2.font.size = Pt(18)
    p2.font.color.rgb = SLATE

    # Slide 2: Problème
    s2 = prs.slides.add_slide(blank)
    add_bg(s2, True)
    add_title(s2, "1. Le Constat", "Un angle mort temporel et un déséquilibre territorial", True)
    gap = meta["validation"]["territorial_gap"]
    tb2 = s2.shapes.add_textbox(Inches(0.8), Inches(2.3), Inches(11.5), Inches(4.2))
    tf2 = tb2.text_frame
    tf2.word_wrap = True
    for txt, col, sz in [
        (f"×{gap['gap_ratio']} d'écart entre Tanger-Assilah ({gap['tanger_tpi']}/100) et l'arrière-pays ({gap['hinterland_mean_tpi']}/100)", GOLD, 26),
        ("• Les statistiques officielles sont publiées avec plusieurs mois/trimestres de décalage.", WHITE, 20),
        ("• Besoin : détecter précocement les décrochages pour orienter l'investissement public.", WHITE, 20),
    ]:
        pr = tf2.add_paragraph()
        pr.text = txt
        pr.font.size = Pt(sz)
        pr.font.color.rgb = col
        pr.space_after = Pt(18)

    # Slide 3: Sources & Pipeline
    s3 = prs.slides.add_slide(blank)
    add_bg(s3, False)
    add_title(s3, "2. Architecture Multi-Sources", "Croiser les données officielles HCP et le Big Data spatial", False)
    tb3 = s3.shapes.add_textbox(Inches(0.8), Inches(2.2), Inches(11.5), Inches(4.5))
    tf3 = tb3.text_frame
    tf3.word_wrap = True
    for line in [
        "1. Satellite : Luminosité nocturne VIIRS (NASA Black Marble) — signal industriel & urbain mensuel",
        "2. Officiel & Admin : HCP (emploi, activité), OMPIC (entreprises), Tourisme (nuitées), Tanger Med",
        "3. Signaux Web : Google Trends & offres d'emploi agrégées — tension avancée de la demande",
        "4. Pipeline reproductible : 1 commande → Parquet / DuckDB → TPI + K-Means + Ridge Nowcasting",
    ]:
        pr = tf3.add_paragraph()
        pr.text = line
        pr.font.size = Pt(20)
        pr.font.color.rgb = NAVY
        pr.space_after = Pt(16)

    # Slide 4: Démo en direct
    s4 = prs.slides.add_slide(blank)
    add_bg(s4, True)
    add_title(s4, "3. Démonstration en direct (3 minutes)", "De la Vue Nuit satellitaire à la Fiche Décideur PDF", True)
    tb4 = s4.shapes.add_textbox(Inches(0.8), Inches(2.3), Inches(11.5), Inches(4.2))
    tf4 = tb4.text_frame
    for step in [
        "1. Vue Nuit animée (2019–2025) : observer l'essor du corridor Tanger–Fahs-Anjra",
        "2. Clic sur Chefchaouen / Ouezzane : alertes actives et composantes",
        "3. Nowcasting : prévision du mois suivant avec intervalle de confiance",
        "4. Simulateur « Et si ? » : simuler un plan d'investissement sectoriel",
        "5. Export 1-clic : Fiche Territoire PDF prête pour le Wali ou le Conseil Régional",
    ]:
        pr = tf4.add_paragraph()
        pr.text = step
        pr.font.size = Pt(20)
        pr.font.color.rgb = WHITE
        pr.space_after = Pt(14)

    # Slide 5: Résultats & Validation
    s5 = prs.slides.add_slide(blank)
    add_bg(s5, False)
    add_title(s5, "4. Validation Scientifique", "Des signaux alternatifs validés sur les données HCP", False)
    evo_img = _chart_regional_evolution(df)
    val_img = _chart_validation_scatter(df, meta["validation"]["global_correlations"]["nightlights_vs_hcp_pearson"])
    s5.shapes.add_picture(evo_img, Inches(0.6), Inches(2.1), width=Inches(6.0))
    s5.shapes.add_picture(val_img, Inches(6.8), Inches(2.1), width=Inches(5.9))

    # Slide 6: Nowcasting & Typologie
    s6 = prs.slides.add_slide(blank)
    add_bg(s6, True)
    add_title(s6, "5. Nowcasting & Typologie K-Means", "Prédire mieux que le modèle naïf et segmenter les territoires", True)
    hm = meta["nowcasting"]["hcp_nowcast_metrics"]
    nc = meta["nowcasting"]["regional_nowcast"]
    tb6 = s6.shapes.add_textbox(Inches(0.8), Inches(2.3), Inches(11.5), Inches(4.5))
    tf6 = tb6.text_frame
    for line, col in [
        (f"• Nowcast régional Nov. 2025 : {nc['forecast_tpi']} ± {nc['uncertainty_halfwidth']} / 100", GOLD),
        (f"• Validation glissante (2021–2025) : RMSE = {hm['rmse_model']} vs Naïf = {hm['rmse_naive']} (-{hm['rmse_gain_pct']} % d'erreur)", WHITE),
        ("• Moteurs (3) : Tanger-Assilah, Fahs-Anjra, Tétouan", WHITE),
        ("• En transition (3) : M'diq-Fnideq, Larache, Al Hoceïma", WHITE),
        ("• Fragiles (2) : Chefchaouen, Ouezzane (alertes emploi & décrochage détectées)", WHITE),
    ]:
        pr = tf6.add_paragraph()
        pr.text = line
        pr.font.size = Pt(20)
        pr.font.color.rgb = col
        pr.space_after = Pt(14)

    # Slide 7: Impact Décideurs
    s7 = prs.slides.add_slide(blank)
    add_bg(s7, False)
    add_title(s7, "6. Impact & Aide à la Décision", "Passer de l'observation à l'action territoriale ciblée", False)
    tb7 = s7.shapes.add_textbox(Inches(0.8), Inches(2.3), Inches(11.5), Inches(4.5))
    tf7 = tb7.text_frame
    for line in [
        "• CRI & Conseil Régional : cibler les zones d'activités et incitations vers Larache, Chefchaouen, Ouezzane",
        "• HCP & Observatoires : disposer d'un nowcast mensuel avant la publication officielle",
        "• Investisseurs : comparer les 8 provinces sur 6 piliers objectifs + simulateur de scénarios",
    ]:
        pr = tf7.add_paragraph()
        pr.text = line
        pr.font.size = Pt(21)
        pr.font.color.rgb = NAVY
        pr.space_after = Pt(18)

    # Slide 8: Perspectives & Conclusion
    s8 = prs.slides.add_slide(blank)
    add_bg(s8, True)
    add_title(s8, "7. Perspectives", "Une brique réplicable aux 12 régions du Maroc", True)
    tb8 = s8.shapes.add_textbox(Inches(0.8), Inches(2.5), Inches(11.5), Inches(4.0))
    tf8 = tb8.text_frame
    for line, col in [
        ("• Extension Sentinel-2 (NDBI bâti) et passage à la maille communale", WHITE),
        ("• Intégration automatisée mensuelle via Earthdata & APIs publiques", WHITE),
        ("Territorial Pulse : voir la région s'allumer, mesurer sans délai, agir là où ça compte.", GOLD),
    ]:
        pr = tf8.add_paragraph()
        pr.text = line
        pr.font.size = Pt(23)
        pr.font.color.rgb = col
        pr.space_after = Pt(20)

    prs.save(str(out_path))
    return out_path


if __name__ == "__main__":
    tp = TerritorialPulseModel()
    r_path = build_report_pdf(tp)
    p_path = build_pitch_deck_pptx(tp)
    print("Livrables générés :", r_path, p_path)
