"""Générateur PDF de la Fiche Territoire (Maquette B) et du Rapport scientifique."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from src.config import FICHES_DIR, PROVINCES
from src.model import TerritorialPulseModel


def _render_evolution_chart(profile: dict) -> io.BytesIO:
    """Rend la courbe 2019-2025 comparée à la moyenne régionale en PNG haute résolution."""
    dates = profile["series"]["dates"]
    prov_vals = profile["series"]["province_tpi"]
    reg_vals = profile["series"]["regional_mean"]
    x = np.arange(len(dates))

    fig, ax = plt.subplots(figsize=(7.6, 2.35), dpi=260)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    line_color = "#D1495B" if profile["cluster_label"] == "Fragile" else ("#157F5F" if profile["cluster_label"] == "Moteur" else "#D97706")
    ax.plot(x, prov_vals, color=line_color, linewidth=2.2, label=profile["province_name"])
    ax.plot(x, reg_vals, color="#0A192F", linewidth=1.8, linestyle="--", label="Moyenne régionale")

    tick_idx = [0, 12, 24, 36, 48, 60, 72, len(dates) - 1]
    tick_lbl = [dates[i][:4] for i in tick_idx]
    ax.set_xticks(tick_idx)
    ax.set_xticklabels(tick_lbl, fontsize=8, color="#334155")
    ax.tick_params(axis="y", labelsize=8, colors="#334155")

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#475569")
    ax.spines["bottom"].set_color("#475569")
    ax.grid(axis="y", linestyle=":", alpha=0.35, color="#94A3B8")
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    ax.set_title("Évolution de l'indice TPI (2019–2025)", loc="left", fontsize=10.5, fontweight="bold", color="#0A192F", pad=8)

    plt.tight_layout(pad=0.6)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=260)
    plt.close(fig)
    buf.seek(0)
    return buf


def _render_components_chart(profile: dict) -> io.BytesIO:
    """Rend l'histogramme horizontal des composantes de l'indice."""
    comps = profile["components"]
    labels = list(comps.keys())[::-1]
    values = list(comps.values())[::-1]
    bar_colors = ["#33A876" if v >= 60 else ("#E8AA33" if v >= 45 else "#E06A47") for v in values]

    fig, ax = plt.subplots(figsize=(4.2, 2.55), dpi=260)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    y = np.arange(len(labels))
    bars = ax.barh(y, values, height=0.58, color=bar_colors, edgecolor="none")
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=8.2, color="#1E293B")
    ax.set_xlim(0, 105)
    ax.tick_params(axis="x", labelsize=7.5, colors="#475569")

    for bar, val in zip(bars, values):
        ax.text(min(val + 2.5, 96), bar.get_y() + bar.get_height() / 2, f"{val:.0f}", va="center", fontsize=7.5, color="#0A192F", fontweight="bold")

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#475569")
    ax.spines["bottom"].set_color("#475569")
    ax.set_title("Composantes de l'indice", loc="left", fontsize=10, fontweight="bold", color="#0A192F", pad=8)

    plt.tight_layout(pad=0.5)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=260)
    plt.close(fig)
    buf.seek(0)
    return buf


def _wrap_text(c: canvas.Canvas, text: str, max_width: float, font_name: str, font_size: float) -> list[str]:
    words = text.split()
    lines = []
    current = ""
    for w in words:
        cand = f"{current} {w}".strip()
        if c.stringWidth(cand, font_name, font_size) <= max_width:
            current = cand
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)
    return lines


def generate_province_fiche_pdf(
    province_id: str,
    model: Optional[TerritorialPulseModel] = None,
    output_path: Optional[Path] = None,
) -> bytes:
    """Génère la Fiche Territoire PDF (1 page A4, fidèle à Maquette B) et retourne les octets PDF."""
    tp = model or TerritorialPulseModel()
    profile = tp.get_province_profile(province_id)

    evo_img = _render_evolution_chart(profile)
    comp_img = _render_components_chart(profile)

    from reportlab.lib.utils import ImageReader

    buf = io.BytesIO()
    w, h = A4  # 595.27 x 841.89 pt
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle(f"Fiche Territoire — {profile['province_name']} | Territorial Pulse")

    # 1. En-tête marine foncé
    header_h = 34 * mm
    c.setFillColor(colors.HexColor("#0A192F"))
    c.rect(0, h - header_h, w, header_h, fill=1, stroke=0)

    c.setFillColor(colors.HexColor("#F4B43A"))
    c.setFont("Helvetica-Bold", 9)
    c.drawString(16 * mm, h - 12 * mm, "FICHE TERRITOIRE")

    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 24)
    c.drawString(16 * mm, h - 23.5 * mm, profile["province_name"])

    c.setFillColor(colors.HexColor("#CBD5E1"))
    c.setFont("Helvetica", 9.5)
    c.drawRightString(w - 16 * mm, h - 14 * mm, "Territorial Pulse")
    c.drawRightString(w - 16 * mm, h - 19.5 * mm, "Novembre 2026")

    # 2. Trois cartes KPI
    card_y = h - 66 * mm
    card_h = 24 * mm
    gap = 5 * mm
    margin = 16 * mm
    card_w = (w - 2 * margin - 2 * gap) / 3.0

    cluster = profile["cluster_label"]
    score_color = "#157F5F" if cluster == "Moteur" else ("#D97706" if cluster == "En transition" else "#D1495B")
    delta_color = "#157F5F" if profile["delta_12m"] >= 0 else "#D1495B"
    delta_sub = "en hausse" if profile["delta_12m"] > 0.3 else ("en baisse" if profile["delta_12m"] < -0.3 else "stable")
    prof_sub = (
        "pôle régional moteur"
        if cluster == "Moteur"
        else ("dynamique intermédiaire" if cluster == "En transition" else "territoire en transition lente")
    )

    cards = [
        ("Indice TPI", f"{profile['tpi_score']:.0f} / 100", f"{profile['tpi_rank']}e sur {profile['total_provinces']}", score_color),
        ("Tendance 12 mois", f"{profile['delta_12m']:+.1f} pts", delta_sub, delta_color),
        ("Profil", cluster, prof_sub, "#0A192F"),
    ]

    for i, (title, main_val, sub_val, col_hex) in enumerate(cards):
        cx = margin + i * (card_w + gap)
        c.setFillColor(colors.HexColor("#F3F0E8"))
        c.setStrokeColor(colors.HexColor("#D8D2C5"))
        c.setLineWidth(0.8)
        c.roundRect(cx, card_y, card_w, card_h, 4, fill=1, stroke=1)

        c.setFillColor(colors.HexColor("#64748B"))
        c.setFont("Helvetica", 8.5)
        c.drawString(cx + 5 * mm, card_y + card_h - 6.5 * mm, title)

        c.setFillColor(colors.HexColor(col_hex))
        c.setFont("Helvetica-Bold", 17)
        c.drawString(cx + 5 * mm, card_y + card_h - 15.5 * mm, main_val)

        c.setFillColor(colors.HexColor("#64748B"))
        c.setFont("Helvetica", 7.8)
        c.drawString(cx + 5 * mm, card_y + 3.2 * mm, sub_val)

    # 3. Courbe d'évolution 2019-2025
    evo_y = card_y - 62 * mm
    c.drawImage(ImageReader(evo_img), margin - 2 * mm, evo_y, width=w - 2 * margin + 4 * mm, height=56 * mm, preserveAspectRatio=True)

    # 4. Composantes à gauche + Points forts / vigilance à droite
    mid_y = evo_y - 67 * mm
    c.drawImage(ImageReader(comp_img), margin - 2 * mm, mid_y, width=95 * mm, height=60 * mm, preserveAspectRatio=True)

    rx = margin + 100 * mm
    ry = mid_y + 56 * mm
    max_rw = w - margin - rx

    c.setFillColor(colors.HexColor("#157F5F"))
    c.setFont("Helvetica-Bold", 10.5)
    c.drawString(rx, ry, "Points forts")
    ry -= 6 * mm
    c.setFillColor(colors.HexColor("#1E293B"))
    c.setFont("Helvetica", 8.5)
    for st in profile["strengths"]:
        for line in _wrap_text(c, f"+ {st}", max_rw, "Helvetica", 8.5):
            c.drawString(rx, ry, line)
            ry -= 4.2 * mm
        ry -= 1.2 * mm

    ry -= 4 * mm
    c.setFillColor(colors.HexColor("#D1495B"))
    c.setFont("Helvetica-Bold", 10.5)
    c.drawString(rx, ry, "Points de vigilance")
    ry -= 6 * mm
    c.setFillColor(colors.HexColor("#1E293B"))
    c.setFont("Helvetica", 8.5)
    for wp in profile["watchpoints"]:
        for line in _wrap_text(c, f"- {wp}", max_rw, "Helvetica", 8.5):
            c.drawString(rx, ry, line)
            ry -= 4.2 * mm
        ry -= 1.2 * mm

    # 5. Bloc Recommandations doré en bas
    rec_y = 22 * mm
    rec_h = 52 * mm
    c.setFillColor(colors.HexColor("#FFF6D8"))
    c.setStrokeColor(colors.HexColor("#EAB308"))
    c.setLineWidth(1.0)
    c.roundRect(margin, rec_y, w - 2 * margin, rec_h, 5, fill=1, stroke=1)

    c.setFillColor(colors.HexColor("#0A192F"))
    c.setFont("Helvetica-Bold", 10.5)
    c.drawString(margin + 6 * mm, rec_y + rec_h - 8.5 * mm, "Recommandations (générées à partir des données)")

    c.setFont("Helvetica", 9.0)
    c.setFillColor(colors.HexColor("#1E293B"))
    curr_y = rec_y + rec_h - 17 * mm
    for idx, rec in enumerate(profile["recommendations"], start=1):
        lines = _wrap_text(c, f"{idx}. {rec}", w - 2 * margin - 12 * mm, "Helvetica", 9.0)
        for line in lines:
            c.drawString(margin + 6 * mm, curr_y, line)
            curr_y -= 4.6 * mm
        curr_y -= 2.2 * mm

    # 6. Pied de page
    c.setFillColor(colors.HexColor("#94A3B8"))
    c.setFont("Helvetica", 7.8)
    c.drawCentredString(
        w / 2.0,
        11 * mm,
        f"Territorial Pulse • Datathon Data-Territoires 2026 • Données panel 2019–2025 ({profile['province_id']})",
    )

    c.showPage()
    c.save()

    pdf_bytes = buf.getvalue()
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(pdf_bytes)
    return pdf_bytes


def generate_all_sample_fiches(model: Optional[TerritorialPulseModel] = None) -> list[Path]:
    """Génère les fiches PDF pour les 8 provinces dans docs/fiches_exemple/."""
    FICHES_DIR.mkdir(parents=True, exist_ok=True)
    tp = model or TerritorialPulseModel()
    paths = []
    for p in PROVINCES:
        slug = p["name"].lower().replace(" ", "_").replace("'", "").replace("ï", "i").replace("é", "e")
        out = FICHES_DIR / f"Fiche_{slug}.pdf"
        generate_province_fiche_pdf(p["province_id"], model=tp, output_path=out)
        paths.append(out)
    return paths


if __name__ == "__main__":
    generated = generate_all_sample_fiches()
    print(f"{len(generated)} fiches PDF générées dans {FICHES_DIR}")
