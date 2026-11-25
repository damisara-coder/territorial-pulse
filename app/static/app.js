/* Territorial Pulse — Frontend interactif (Vue Nuit, Dashboard Clair, Comparateur, Nowcast, Alertes, Simulateur) */

const STATE = {
  data: null,
  currentIdx: 81,
  layer: "nightlights_mean",
  view: "night",
  theme: "dark",
  lang: "fr",
  playing: false,
  timer: null,
  hoveredPid: null,
  compareIds: ["TTA-01", "TTA-08"],
  dashSelectedPid: "TTA-01",
  simPid: "TTA-07",
  simShocks: {
    nightlights_sa: 0,
    employment_idx: 0,
    business_creations_sa: 0,
    tourism_nights_sa: 0,
    port_traffic_sa: 0,
    web_trends_sa: 0,
  },
};

const PROVINCE_COLORS = ["#F4B43A", "#34D399", "#60A5FA", "#F87171"];
const COMP_META = [
  { key: "nightlights_sa", label: "Lumière VIIRS" },
  { key: "employment_idx", label: "Emploi & offres" },
  { key: "business_creations_sa", label: "Entreprises" },
  { key: "tourism_nights_sa", label: "Tourisme" },
  { key: "port_traffic_sa", label: "Trafic portuaire" },
  { key: "web_trends_sa", label: "Recherches web" },
];

const I18N = {
  fr: {
    nav_night: "Vue Nuit",
    nav_dash: "Tableau de bord",
    nav_compare: "Comparateur",
    nav_nowcast: "Prévisions",
    nav_alerts: "Alertes & Typologie",
    nav_sim: "Simulateur",
    nav_method: "Méthodologie",
    layer_light: "Lumière",
    layer_tpi: "TPI",
    layer_emp: "Emploi",
    layer_tour: "Tourisme",
    regional_tpi: "INDICE RÉGIONAL TPI",
    vs_prev_q: "vs trim. précédent",
    forecast_nov: "Prévision nov.",
    live_alerts: "ALERTES EN DIRECT",
    model_validation: "VALIDATION DU MODÈLE",
    sub_night: "Vue nuit : la région vue du ciel, mois par mois",
    sub_light: "Baromètre intelligent de l'économie territoriale — Tanger-Tétouan-Al Hoceïma",
  },
  en: {
    nav_night: "Night View",
    nav_dash: "Dashboard",
    nav_compare: "Comparator",
    nav_nowcast: "Nowcasting",
    nav_alerts: "Alerts & Typology",
    nav_sim: "Simulator",
    nav_method: "Methodology",
    layer_light: "Nightlights",
    layer_tpi: "TPI",
    layer_emp: "Employment",
    layer_tour: "Tourism",
    regional_tpi: "REGIONAL TPI INDEX",
    vs_prev_q: "vs prev. quarter",
    forecast_nov: "Nov. forecast",
    live_alerts: "LIVE ALERTS",
    model_validation: "MODEL VALIDATION",
    sub_night: "Night view: the region seen from space, month by month",
    sub_light: "Smart Territorial Economy Barometer — Tangier-Tetouan-Al Hoceima",
  },
};

function formatMonthLabel(isoDate) {
  const [y, m] = isoDate.split("-");
  const monthsFr = ["Janv.", "Févr.", "Mars", "Avr.", "Mai", "Juin", "Juil.", "Août", "Sept.", "Oct.", "Nov.", "Déc."];
  const monthsEn = ["Jan.", "Feb.", "Mar.", "Apr.", "May", "Jun.", "Jul.", "Aug.", "Sep.", "Oct.", "Nov.", "Dec."];
  const arr = STATE.lang === "fr" ? monthsFr : monthsEn;
  return `${arr[parseInt(m, 10) - 1]} ${y}`;
}

function getFrame(idx) {
  const dt = STATE.data.dates[idx];
  return { date: dt, rows: STATE.data.frames[dt] };
}

function getBounds(geojson) {
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  geojson.features.forEach((f) => {
    f.geometry.coordinates[0].forEach(([lon, lat]) => {
      if (lon < minX) minX = lon;
      if (lon > maxX) maxX = lon;
      if (lat < minY) minY = lat;
      if (lat > maxY) maxY = lat;
    });
  });
  return { minX, maxX, minY, maxY };
}

function projectPoint(lon, lat, bounds, w, h, pad = 42) {
  const scaleX = (w - pad * 2) / (bounds.maxX - bounds.minX);
  const scaleY = (h - pad * 2) / (bounds.maxY - bounds.minY);
  const scale = Math.min(scaleX, scaleY);
  const offX = (w - (bounds.maxX - bounds.minX) * scale) / 2;
  const offY = (h - (bounds.maxY - bounds.minY) * scale) / 2;
  const x = offX + (lon - bounds.minX) * scale;
  const y = h - (offY + (lat - bounds.minY) * scale);
  return [x, y];
}

function pointInPolyXY(x, y, poly) {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const xi = poly[i][0], yi = poly[i][1];
    const xj = poly[j][0], yj = poly[j][1];
    const intersect = yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi + 1e-12) + xi;
    if (intersect) inside = !inside;
  }
  return inside;
}

function drawNightMap() {
  const canvas = document.getElementById("night-canvas");
  if (!canvas || !STATE.data) return;
  const rect = canvas.parentElement.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);
  const w = rect.width;
  const h = rect.height;

  // Deep night background
  const bg = ctx.createRadialGradient(w * 0.42, h * 0.36, 20, w * 0.45, h * 0.5, w * 0.72);
  bg.addColorStop(0, "#102240");
  bg.addColorStop(1, "#060e1c");
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, w, h);

  const { date, rows } = getFrame(STATE.currentIdx);
  const rowMap = Object.fromEntries(rows.map((r) => [r.province_id, r]));
  const geo = STATE.data.geojson;
  const bounds = getBounds(geo);

  // Store projected polygons for hit testing
  canvas._hitPolys = [];

  // 1. Draw province polygons
  geo.features.forEach((f) => {
    const pid = f.properties.province_id;
    const rec = rowMap[pid];
    const ring = f.geometry.coordinates[0].map(([lon, lat]) => projectPoint(lon, lat, bounds, w, h, 46));
    canvas._hitPolys.push({ pid, ring, rec });

    ctx.beginPath();
    ring.forEach(([px, py], i) => (i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py)));
    ctx.closePath();

    if (STATE.layer === "nightlights_mean") {
      ctx.fillStyle = STATE.hoveredPid === pid ? "rgba(244, 180, 58, 0.08)" : "rgba(15, 32, 60, 0.42)";
    } else {
      const val = rec[STATE.layer] || 50;
      const alpha = 0.16 + 0.58 * Math.min(1, Math.max(0, val / 100));
      const colorBase = STATE.layer === "tpi_score" ? "244, 180, 58" : STATE.layer === "employment_idx" ? "52, 211, 153" : "96, 165, 250";
      ctx.fillStyle = `rgba(${colorBase}, ${alpha.toFixed(2)})`;
    }
    ctx.fill();

    ctx.lineWidth = STATE.hoveredPid === pid ? 2.2 : 1.1;
    ctx.strokeStyle = STATE.hoveredPid === pid ? "#F4B43A" : "rgba(100, 145, 210, 0.38)";
    ctx.stroke();
  });

  // 2. Draw glowing VIIRS nightlight points
  const pointsMap = STATE.data.nightlight_points;
  const layerWeight = STATE.layer === "nightlights_mean" ? 1.0 : 0.35;

  geo.features.forEach((f) => {
    const pid = f.properties.province_id;
    const rec = rowMap[pid];
    const pts = pointsMap[pid] || [];
    const nlRatio = Math.min(1.35, Math.max(0.14, rec.nightlights_mean / 36.0));
    const activeCount = Math.floor(pts.length * Math.min(1.0, 0.18 + 0.82 * nlRatio));

    for (let i = 0; i < activeCount; i++) {
      const p = pts[i];
      const [px, py] = projectPoint(p.lon, p.lat, bounds, w, h, 46);
      const strength = p.w * nlRatio * layerWeight;
      const radius = 1.3 + strength * 2.5;

      // Glow halo
      if (strength > 0.35) {
        const g = ctx.createRadialGradient(px, py, 0, px, py, radius * 4.2);
        g.addColorStop(0, `rgba(255, 226, 140, ${(0.45 * strength).toFixed(2)})`);
        g.addColorStop(1, "rgba(244, 180, 58, 0)");
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.arc(px, py, radius * 4.2, 0, Math.PI * 2);
        ctx.fill();
      }

      // Bright core
      ctx.fillStyle = `rgba(255, 244, 200, ${Math.min(0.98, 0.32 + strength * 0.72).toFixed(2)})`;
      ctx.beginPath();
      ctx.arc(px, py, Math.max(1.0, radius * 0.7), 0, Math.PI * 2);
      ctx.fill();
    }
  });

  // 3. Province Labels
  ctx.textAlign = "center";
  geo.features.forEach((f) => {
    const pid = f.properties.province_id;
    const rec = rowMap[pid];
    const [cx, cy] = projectPoint(f.properties.centroid[0], f.properties.centroid[1], bounds, w, h, 46);

    ctx.font = "700 11.5px Inter, Segoe UI, sans-serif";
    ctx.fillStyle = "rgba(6, 14, 28, 0.75)";
    ctx.fillText(rec.province_name, cx + 1, cy + 1);
    ctx.fillStyle = "#F8FAFC";
    ctx.fillText(rec.province_name, cx, cy);

    if (STATE.layer !== "nightlights_mean") {
      ctx.font = "700 10.5px Inter, Segoe UI, sans-serif";
      ctx.fillStyle = "#FDE68A";
      const suffix = STATE.layer === "tpi_score" ? `${rec.tpi_score.toFixed(0)}/100` : `${rec[STATE.layer].toFixed(0)}`;
      ctx.fillText(suffix, cx, cy + 14);
    }
  });

  // 4. Automatic dynamic annotations (green corridor vs coral hinterland)
  const fahs = rowMap["TTA-02"];
  const ouez = rowMap["TTA-08"];
  const idx12 = Math.max(0, STATE.currentIdx - 12);
  const idx3 = Math.max(0, STATE.currentIdx - 3);
  const fahs12 = STATE.data.frames[STATE.data.dates[idx12]].find((r) => r.province_id === "TTA-02");
  const ouez3 = STATE.data.frames[STATE.data.dates[idx3]].find((r) => r.province_id === "TTA-08");
  const fahsPct = fahs12 ? (((fahs.nightlights_mean - fahs12.nightlights_mean) / fahs12.nightlights_mean) * 100) : 0;
  const ouezPct = ouez3 ? (((ouez.nightlights_mean - ouez3.nightlights_mean) / ouez3.nightlights_mean) * 100) : 0;

  // Green callout on Fahs-Anjra
  const [fx, fy] = projectPoint(-5.52, 35.75, bounds, w, h, 46);
  ctx.save();
  ctx.setLineDash([4, 3]);
  ctx.strokeStyle = "#34D399";
  ctx.lineWidth = 1.6;
  ctx.beginPath();
  ctx.arc(fx, fy, 25, 0, Math.PI * 2);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.beginPath();
  ctx.moveTo(fx - 18, fy - 18);
  ctx.lineTo(fx - 70, fy - 48);
  ctx.stroke();
  ctx.fillStyle = "#34D399";
  ctx.textAlign = "left";
  ctx.font = "700 11px Inter, sans-serif";
  ctx.fillText("Zone industrielle et portuaire", Math.max(14, fx - 175), Math.max(22, fy - 66));
  ctx.fillText(`${fahsPct >= 0 ? "+" : ""}${fahsPct.toFixed(1)} % de luminosité sur 12 mois`, Math.max(14, fx - 175), Math.max(36, fy - 52));
  ctx.restore();

  // Coral callout on hinterland
  const [ox, oy] = projectPoint(-5.56, 34.84, bounds, w, h, 46);
  ctx.save();
  ctx.strokeStyle = "#F87171";
  ctx.lineWidth = 1.4;
  ctx.beginPath();
  ctx.moveTo(ox + 12, oy + 6);
  ctx.lineTo(ox + 128, oy + 46);
  ctx.stroke();
  ctx.fillStyle = "#F87171";
  ctx.textAlign = "left";
  ctx.font = "700 11px Inter, sans-serif";
  ctx.fillText(`Arrière-pays : ${ouezPct >= 0 ? "+" : ""}${ouezPct.toFixed(1)} % sur 3 mois`, ox + 100, Math.min(h - 14, oy + 62));
  ctx.restore();
}

function drawDashChoropleth() {
  const canvas = document.getElementById("dash-canvas");
  if (!canvas || !STATE.data) return;
  const rect = canvas.parentElement.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);
  const w = rect.width;
  const h = rect.height;

  ctx.fillStyle = STATE.theme === "light" ? "#FAF8F3" : "#0b172b";
  ctx.fillRect(0, 0, w, h);

  const { rows } = getFrame(STATE.currentIdx);
  const rowMap = Object.fromEntries(rows.map((r) => [r.province_id, r]));
  const geo = STATE.data.geojson;
  const bounds = getBounds(geo);
  canvas._hitPolys = [];

  const getColor = (score) => {
    if (score >= 70) return "#157F5F";
    if (score >= 54) return "#5EC492";
    if (score >= 42) return "#E8AA33";
    return "#D1495B";
  };

  geo.features.forEach((f) => {
    const pid = f.properties.province_id;
    const rec = rowMap[pid];
    const ring = f.geometry.coordinates[0].map(([lon, lat]) => projectPoint(lon, lat, bounds, w, h, 28));
    canvas._hitPolys.push({ pid, ring, rec });

    ctx.beginPath();
    ring.forEach(([px, py], i) => (i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py)));
    ctx.closePath();
    ctx.fillStyle = getColor(rec.tpi_score);
    ctx.fill();
    ctx.lineWidth = STATE.hoveredPid === pid || STATE.dashSelectedPid === pid ? 3 : 1.5;
    ctx.strokeStyle = STATE.hoveredPid === pid || STATE.dashSelectedPid === pid ? "#0A192F" : "#FFFFFF";
    ctx.stroke();

    const [cx, cy] = projectPoint(f.properties.centroid[0], f.properties.centroid[1], bounds, w, h, 28);
    ctx.textAlign = "center";
    ctx.font = "700 11px Inter, sans-serif";
    ctx.fillStyle = "#FFFFFF";
    ctx.fillText(rec.province_name, cx, cy);
    ctx.font = "600 10px Inter, sans-serif";
    ctx.fillText(`${rec.tpi_score.toFixed(1)}`, cx, cy + 13);
  });
}

function attachCanvasEvents(canvasId, tooltipId, onClickProvince) {
  const canvas = document.getElementById(canvasId);
  const tooltip = document.getElementById(tooltipId);
  if (!canvas) return;

  canvas.addEventListener("mousemove", (e) => {
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const hit = (canvas._hitPolys || []).find((p) => pointInPolyXY(x, y, p.ring));

    if (hit) {
      if (STATE.hoveredPid !== hit.pid) {
        STATE.hoveredPid = hit.pid;
        drawNightMap();
        drawDashChoropleth();
      }
      const r = hit.rec;
      tooltip.style.display = "block";
      tooltip.style.left = `${Math.min(rect.width - 210, x + 14)}px`;
      tooltip.style.top = `${Math.max(10, y - 20)}px`;
      tooltip.innerHTML = `
        <strong>${r.province_name}</strong> (${r.cluster_label})<br/>
        TPI : <b>${r.tpi_score.toFixed(1)} / 100</b> (#${r.tpi_rank})<br/>
        Lumière VIIRS : <b>${r.nightlights_mean.toFixed(1)}</b> nW/cm²/sr<br/>
        Emploi HCP : <b>${r.hcp_employment_index.toFixed(1)}</b> • Tourisme : <b>${r.tourism_nights.toLocaleString()}</b>
      `;
    } else {
      if (STATE.hoveredPid !== null) {
        STATE.hoveredPid = null;
        drawNightMap();
        drawDashChoropleth();
      }
      tooltip.style.display = "none";
    }
  });

  canvas.addEventListener("mouseleave", () => {
    STATE.hoveredPid = null;
    tooltip.style.display = "none";
    drawNightMap();
    drawDashChoropleth();
  });

  canvas.addEventListener("click", (e) => {
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const hit = (canvas._hitPolys || []).find((p) => pointInPolyXY(x, y, p.ring));
    if (hit && onClickProvince) onClickProvince(hit.pid);
  });
}

function renderGauge(score) {
  const svg = document.getElementById("tpi-gauge-svg");
  const cx = 110, cy = 110, r = 78;
  const startAngle = Math.PI;
  const endAngle = 2 * Math.PI;
  const valAngle = startAngle + (Math.min(100, Math.max(0, score)) / 100) * Math.PI;

  const arcPath = (a1, a2) => {
    const x1 = cx + r * Math.cos(a1), y1 = cy + r * Math.sin(a1);
    const x2 = cx + r * Math.cos(a2), y2 = cy + r * Math.sin(a2);
    const large = a2 - a1 > Math.PI ? 1 : 0;
    return `M ${x1.toFixed(1)} ${y1.toFixed(1)} A ${r} ${r} 0 ${large} 1 ${x2.toFixed(1)} ${y2.toFixed(1)}`;
  };

  svg.innerHTML = `
    <path d="${arcPath(startAngle, endAngle)}" fill="none" stroke="rgba(148,163,184,0.22)" stroke-width="20" stroke-linecap="butt"/>
    <path d="${arcPath(startAngle, valAngle)}" fill="none" stroke="#F4B43A" stroke-width="20" stroke-linecap="butt"/>
    <text x="${cx}" y="${cy - 18}" text-anchor="middle" fill="currentColor" font-size="30" font-weight="800">${Math.round(score)}</text>
    <text x="${cx}" y="${cy + 6}" text-anchor="middle" fill="#94A3B8" font-size="13">/ 100</text>
  `;
}

function updateTimelineUI() {
  const { date, rows } = getFrame(STATE.currentIdx);
  const label = formatMonthLabel(date);
  document.getElementById("night-date-badge").textContent = label;
  document.getElementById("dash-date-badge").textContent = label;
  document.getElementById("night-slider").value = STATE.currentIdx;
  document.getElementById("dash-slider").value = STATE.currentIdx;

  // Regional TPI at currentIdx
  const regTpi = rows.reduce((acc, r) => acc + r.tpi_score, 0) / rows.length;
  const prevQIdx = Math.max(0, STATE.currentIdx - 3);
  const prevRows = getFrame(prevQIdx).rows;
  const prevReg = prevRows.reduce((acc, r) => acc + r.tpi_score, 0) / prevRows.length;
  const deltaQ = regTpi - prevReg;

  renderGauge(regTpi);
  const deltaEl = document.getElementById("gauge-delta");
  deltaEl.textContent = `${deltaQ >= 0 ? "+" : ""}${deltaQ.toFixed(1)} pts`;
  deltaEl.className = `stat-delta ${deltaQ >= 0 ? "pos" : "neg"}`;

  // Update Light Dashboard KPIs
  document.getElementById("dash-kpi-tpi").textContent = `${regTpi.toFixed(1)} / 100`;
  const dKpi = document.getElementById("dash-kpi-delta");
  dKpi.textContent = `${deltaQ >= 0 ? "+" : ""}${deltaQ.toFixed(1)} pts vs trim. préc.`;
  dKpi.className = `kpi-sub ${deltaQ >= 0 ? "pos" : "neg"}`;

  const moteurs = rows.filter((r) => r.cluster_label === "Moteur");
  const fragiles = rows.filter((r) => r.cluster_label === "Fragile");
  document.getElementById("dash-kpi-moteurs").textContent = `${moteurs.length} sur 8`;
  document.getElementById("dash-kpi-moteurs-list").textContent = moteurs.map((m) => m.province_name).join(", ");
  document.getElementById("dash-kpi-fragiles").textContent = `${fragiles.length} sur 8`;
  document.getElementById("dash-kpi-fragiles-list").textContent = fragiles.map((f) => f.province_name).join(", ");

  const tanger = rows.find((r) => r.province_id === "TTA-01").tpi_score;
  const hinter = fragiles.reduce((a, f) => a + f.tpi_score, 0) / Math.max(1, fragiles.length);
  document.getElementById("dash-kpi-gap").textContent = `×${(tanger / Math.max(1, hinter)).toFixed(2)}`;

  drawNightMap();
  drawDashChoropleth();
  renderDashRankChart(rows);
  renderDashEvoChart();
}

function renderNightSidebarStatic() {
  const res = STATE.data.results;
  const nc = res.nowcasting.regional_nowcast;
  document.getElementById("gauge-forecast").textContent = `${nc.forecast_tpi.toFixed(1)} ± ${nc.uncertainty_halfwidth.toFixed(1)}`;

  const ul = document.getElementById("night-alerts-list");
  ul.innerHTML = res.alerts.live_alerts
    .slice(0, 5)
    .map(
      (a) => `<li class="alert-item"><span class="dot ${a.severity}"></span><span>${a.message}</span></li>`
    )
    .join("");

  const rVal = res.validation.global_correlations.nightlights_vs_hcp_pearson;
  const gain = res.nowcasting.hcp_nowcast_metrics.rmse_gain_pct;
  document.getElementById("val-r-value").textContent = `r = ${rVal.toFixed(2).replace(".", ",")}*`;
  document.getElementById("val-rmse-msg").textContent = `erreur de prévision < modèle naïf (-${gain} % RMSE)`;

  const topAlert = res.alerts.live_alerts[0];
  if (topAlert) {
    document.getElementById("dash-alert-banner").textContent = `Alerte active : ${topAlert.message} — signal de fragilité à surveiller`;
  }
}

function renderDashRankChart(rows) {
  const svg = document.getElementById("dash-rank-svg");
  const sorted = [...rows].sort((a, b) => b.tpi_score - a.tpi_score);
  const w = 540, rowH = 25, left = 118, right = 34;
  const maxW = w - left - right;

  let html = "";
  sorted.forEach((r, i) => {
    const y = 10 + i * rowH;
    const bw = (r.tpi_score / 100) * maxW;
    const col = r.tpi_score >= 70 ? "#157F5F" : r.tpi_score >= 54 ? "#5EC492" : r.tpi_score >= 42 ? "#E8AA33" : "#D1495B";
    html += `
      <text x="${left - 8}" y="${y + 13}" text-anchor="end" fill="currentColor" font-size="11.5" font-weight="600">${r.province_name}</text>
      <rect x="${left}" y="${y + 2}" width="${bw.toFixed(1)}" height="16" rx="3" fill="${col}"/>
      <text x="${left + bw + 6}" y="${y + 13}" fill="currentColor" font-size="11" font-weight="700">${r.tpi_score.toFixed(1)}</text>
    `;
  });
  svg.innerHTML = html;
}

function renderDashEvoChart() {
  const svg = document.getElementById("dash-evo-svg");
  const dates = STATE.data.dates;
  const selPid = STATE.dashSelectedPid;
  const selSeries = dates.map((d) => STATE.data.frames[d].find((r) => r.province_id === selPid).tpi_score);
  const ouezSeries = dates.map((d) => STATE.data.frames[d].find((r) => r.province_id === "TTA-08").tpi_score);
  const nc = STATE.data.results.nowcasting.province_nowcasts.find((n) => n.province_id === selPid);

  const w = 540, h = 230, padL = 40, padR = 26, padT = 24, padB = 28;
  const plotW = w - padL - padR, plotH = h - padT - padB;
  const totalPts = dates.length + 1;
  const xOf = (i) => padL + (i / (totalPts - 1)) * plotW;
  const yOf = (v) => padT + (1 - v / 100) * plotH;

  const pathOf = (arr) => arr.map((v, i) => `${i === 0 ? "M" : "L"} ${xOf(i).toFixed(1)} ${yOf(v).toFixed(1)}`).join(" ");

  const lastX = xOf(dates.length - 1), nextX = xOf(dates.length);
  const lastY = yOf(selSeries[selSeries.length - 1]);
  const ciPoly = `${lastX.toFixed(1)},${lastY.toFixed(1)} ${nextX.toFixed(1)},${yOf(nc.ci_high).toFixed(1)} ${nextX.toFixed(1)},${yOf(nc.ci_low).toFixed(1)}`;

  let grid = "";
  [20, 40, 60, 80, 100].forEach((v) => {
    const yy = yOf(v);
    grid += `<line x1="${padL}" y1="${yy}" x2="${w - padR}" y2="${yy}" stroke="rgba(148,163,184,0.2)" stroke-dasharray="3 3"/>
             <text x="${padL - 6}" y="${yy + 4}" text-anchor="end" fill="#94A3B8" font-size="10">${v}</text>`;
  });

  svg.innerHTML = `
    ${grid}
    <polygon points="${ciPoly}" fill="rgba(244, 180, 58, 0.35)"/>
    <path d="${pathOf(selSeries)}" fill="none" stroke="#157F5F" stroke-width="2.4"/>
    <line x1="${lastX}" y1="${lastY}" x2="${nextX}" y2="${yOf(nc.forecast_tpi)}" stroke="#F4B43A" stroke-width="2.4" stroke-dasharray="4 3"/>
    <path d="${pathOf(ouezSeries)}" fill="none" stroke="#D1495B" stroke-width="2"/>
    <line x1="${lastX}" y1="${padT}" x2="${lastX}" y2="${h - padB}" stroke="#94A3B8" stroke-dasharray="2 3"/>
    <text x="${padL + 6}" y="14" fill="#157F5F" font-size="11" font-weight="700">● ${nc.province_name} (Nowcast ${nc.forecast_tpi.toFixed(1)})</text>
    <text x="${padL + 235}" y="14" fill="#D1495B" font-size="11" font-weight="700">● Ouezzane</text>
    <text x="${padL}" y="${h - 8}" fill="#94A3B8" font-size="10">2019</text>
    <text x="${w - padR - 25}" y="${h - 8}" fill="#94A3B8" font-size="10">2025</text>
  `;
}

function renderComparator() {
  const latest = getFrame(STATE.data.dates.length - 1).rows;
  const chips = document.getElementById("compare-chips");
  chips.innerHTML = latest
    .map(
      (r) => `<button class="chip ${STATE.compareIds.includes(r.province_id) ? "selected" : ""}" data-pid="${r.province_id}">${r.province_name}</button>`
    )
    .join("");

  chips.querySelectorAll(".chip").forEach((btn) => {
    btn.onclick = () => {
      const pid = btn.dataset.pid;
      if (STATE.compareIds.includes(pid)) {
        if (STATE.compareIds.length > 2) STATE.compareIds = STATE.compareIds.filter((x) => x !== pid);
      } else {
        if (STATE.compareIds.length >= 4) STATE.compareIds.shift();
        STATE.compareIds.push(pid);
      }
      renderComparator();
    };
  });

  // Overlaid line chart
  const svgLine = document.getElementById("compare-line-svg");
  const dates = STATE.data.dates;
  const w = 580, h = 280, padL = 40, padR = 20, padT = 30, padB = 26;
  const plotW = w - padL - padR, plotH = h - padT - padB;
  const xOf = (i) => padL + (i / (dates.length - 1)) * plotW;
  const yOf = (v) => padT + (1 - v / 100) * plotH;

  let linesSvg = "";
  [20, 40, 60, 80].forEach((v) => {
    const yy = yOf(v);
    linesSvg += `<line x1="${padL}" y1="${yy}" x2="${w - padR}" y2="${yy}" stroke="rgba(148,163,184,0.2)"/>
                 <text x="${padL - 6}" y="${yy + 4}" text-anchor="end" fill="#94A3B8" font-size="10">${v}</text>`;
  });

  STATE.compareIds.forEach((pid, idx) => {
    const col = PROVINCE_COLORS[idx % PROVINCE_COLORS.length];
    const pts = dates.map((d) => STATE.data.frames[d].find((r) => r.province_id === pid).tpi_score);
    const pName = latest.find((r) => r.province_id === pid).province_name;
    const dStr = pts.map((v, i) => `${i === 0 ? "M" : "L"} ${xOf(i).toFixed(1)} ${yOf(v).toFixed(1)}`).join(" ");
    linesSvg += `<path d="${dStr}" fill="none" stroke="${col}" stroke-width="2.4"/>`;
    linesSvg += `<text x="${padL + idx * 130}" y="16" fill="${col}" font-size="11" font-weight="700">● ${pName}</text>`;
  });
  svgLine.innerHTML = linesSvg;

  // Radar chart
  const svgRad = document.getElementById("compare-radar-svg");
  const cx = 210, cy = 148, rad = 98;
  let radSvg = "";
  [0.25, 0.5, 0.75, 1.0].forEach((s) => {
    const pts = COMP_META.map((_, i) => {
      const a = -Math.PI / 2 + (i * 2 * Math.PI) / COMP_META.length;
      return `${(cx + rad * s * Math.cos(a)).toFixed(1)},${(cy + rad * s * Math.sin(a)).toFixed(1)}`;
    }).join(" ");
    radSvg += `<polygon points="${pts}" fill="none" stroke="rgba(148,163,184,0.25)"/>`;
  });

  COMP_META.forEach((m, i) => {
    const a = -Math.PI / 2 + (i * 2 * Math.PI) / COMP_META.length;
    const lx = cx + (rad + 22) * Math.cos(a);
    const ly = cy + (rad + 22) * Math.sin(a);
    radSvg += `<line x1="${cx}" y1="${cy}" x2="${cx + rad * Math.cos(a)}" y2="${cy + rad * Math.sin(a)}" stroke="rgba(148,163,184,0.25)"/>
               <text x="${lx}" y="${ly}" text-anchor="middle" fill="currentColor" font-size="10.5">${m.label}</text>`;
  });

  STATE.compareIds.forEach((pid, idx) => {
    const col = PROVINCE_COLORS[idx % PROVINCE_COLORS.length];
    const rec = latest.find((r) => r.province_id === pid);
    const pts = COMP_META.map((m, i) => {
      const a = -Math.PI / 2 + (i * 2 * Math.PI) / COMP_META.length;
      const s = rec[m.key] / 100;
      return `${(cx + rad * s * Math.cos(a)).toFixed(1)},${(cy + rad * s * Math.sin(a)).toFixed(1)}`;
    }).join(" ");
    radSvg += `<polygon points="${pts}" fill="${col}33" stroke="${col}" stroke-width="2"/>`;
  });
  svgRad.innerHTML = radSvg;

  // Comparison table
  const tbl = document.getElementById("compare-table");
  const selectedRows = STATE.compareIds.map((id) => latest.find((r) => r.province_id === id));
  tbl.innerHTML = `
    <thead><tr><th>Territoire</th><th>Profil</th><th>TPI</th><th>Rang</th><th>Lumière VIIRS</th><th>Emploi HCP</th><th>Entreprises/mois</th><th>Nuitées/mois</th></tr></thead>
    <tbody>
      ${selectedRows
        .map(
          (r) => `<tr>
            <td><strong>${r.province_name}</strong></td>
            <td>${r.cluster_label}</td>
            <td><strong>${r.tpi_score.toFixed(1)}</strong></td>
            <td>#${r.tpi_rank}</td>
            <td>${r.nightlights_mean.toFixed(1)}</td>
            <td>${r.hcp_employment_index.toFixed(1)}</td>
            <td>${r.business_creations}</td>
            <td>${r.tourism_nights.toLocaleString()}</td>
          </tr>`
        )
        .join("")}
    </tbody>
  `;
}

function renderNowcastView() {
  const nc = STATE.data.results.nowcasting;
  const m = nc.hcp_nowcast_metrics;

  document.getElementById("nowcast-kpis").innerHTML = `
    <div class="card kpi-card"><div class="kpi-label">Nowcast TPI Nov. 2025</div><div class="kpi-value">${nc.regional_nowcast.forecast_tpi} ± ${nc.regional_nowcast.uncertainty_halfwidth}</div><div class="kpi-sub">Intervalle [${nc.regional_nowcast.ci_low}, ${nc.regional_nowcast.ci_high}]</div></div>
    <div class="card kpi-card"><div class="kpi-label">RMSE Nowcast (vs Naïf)</div><div class="kpi-value teal">${m.rmse_model} <small>(naïf ${m.rmse_naive})</small></div><div class="kpi-sub pos">Gain de précision : -${m.rmse_gain_pct} %</div></div>
    <div class="card kpi-card"><div class="kpi-label">MAPE hors échantillon</div><div class="kpi-value">${m.mape_model_pct} %</div><div class="kpi-sub">vs ${m.mape_naive_pct} % modèle naïf</div></div>
    <div class="card kpi-card"><div class="kpi-label">Corrélation Lumière / HCP</div><div class="kpi-value amber">${STATE.data.results.validation.global_correlations.nightlights_vs_hcp_pearson}</div><div class="kpi-sub">Panel 2019–2025 (n=656)</div></div>
  `;

  const sel = document.getElementById("nowcast-prov-select");
  if (!sel.options.length) {
    nc.province_nowcasts.forEach((p) => {
      const opt = document.createElement("option");
      opt.value = p.province_id;
      opt.textContent = p.province_name;
      sel.appendChild(opt);
    });
    sel.onchange = renderNowcastBacktestChart;
  }
  renderNowcastBacktestChart();

  // Feature importance bars
  const impSvg = document.getElementById("nowcast-imp-svg");
  let impHtml = "";
  nc.feature_importance.slice(0, 7).forEach((f, i) => {
    const y = 14 + i * 34;
    const bw = (f.importance_pct / 45) * 240;
    impHtml += `
      <text x="195" y="${y + 14}" text-anchor="end" fill="currentColor" font-size="11">${f.label}</text>
      <rect x="205" y="${y + 2}" width="${Math.min(280, bw).toFixed(1)}" height="16" rx="4" fill="#F4B43A"/>
      <text x="${212 + Math.min(280, bw)}" y="${y + 14}" fill="currentColor" font-size="11" font-weight="700">${f.importance_pct.toFixed(1)} %</text>
    `;
  });
  impSvg.innerHTML = impHtml;

  // Table
  document.getElementById("nowcast-table").innerHTML = `
    <thead><tr><th>Territoire</th><th>TPI Oct. 2025</th><th>Nowcast Nov. 2025</th><th>Variation</th><th>Intervalle 90 %</th></tr></thead>
    <tbody>
      ${nc.province_nowcasts
        .map(
          (p) => `<tr>
            <td><strong>${p.province_name}</strong></td>
            <td>${p.current_tpi.toFixed(1)}</td>
            <td><strong>${p.forecast_tpi.toFixed(1)} ± ${p.uncertainty_halfwidth.toFixed(1)}</strong></td>
            <td class="${p.delta_vs_current >= 0 ? "pos" : "neg"}">${p.delta_vs_current >= 0 ? "+" : ""}${p.delta_vs_current.toFixed(2)} pts</td>
            <td>[${p.ci_low.toFixed(1)} – ${p.ci_high.toFixed(1)}]</td>
          </tr>`
        )
        .join("")}
    </tbody>
  `;
}

function renderNowcastBacktestChart() {
  const pid = document.getElementById("nowcast-prov-select").value || "TTA-01";
  const series = STATE.data.results.nowcasting.backtest_series.filter((b) => b.province_id === pid);
  const svg = document.getElementById("nowcast-bt-svg");
  const w = 580, h = 270, padL = 40, padR = 20, padT = 28, padB = 24;
  const plotW = w - padL - padR, plotH = h - padT - padB;
  const vals = series.flatMap((s) => [s.actual_hcp, s.pred_hcp]);
  const minV = Math.min(...vals) - 4, maxV = Math.max(...vals) + 4;
  const xOf = (i) => padL + (i / Math.max(1, series.length - 1)) * plotW;
  const yOf = (v) => padT + (1 - (v - minV) / Math.max(1, maxV - minV)) * plotH;

  const pActual = series.map((s, i) => `${i === 0 ? "M" : "L"} ${xOf(i).toFixed(1)} ${yOf(s.actual_hcp).toFixed(1)}`).join(" ");
  const pPred = series.map((s, i) => `${i === 0 ? "M" : "L"} ${xOf(i).toFixed(1)} ${yOf(s.pred_hcp).toFixed(1)}`).join(" ");

  svg.innerHTML = `
    <path d="${pActual}" fill="none" stroke="#60A5FA" stroke-width="2.2"/>
    <path d="${pPred}" fill="none" stroke="#F4B43A" stroke-width="2.2" stroke-dasharray="5 3"/>
    <text x="${padL}" y="15" fill="#60A5FA" font-size="11" font-weight="700">● Emploi HCP officiel</text>
    <text x="${padL + 160}" y="15" fill="#F4B43A" font-size="11" font-weight="700">--- Nowcast (temps quasi réel)</text>
    <text x="${padL}" y="${h - 6}" fill="#94A3B8" font-size="10">2021-01</text>
    <text x="${w - padR - 44}" y="${h - 6}" fill="#94A3B8" font-size="10">2025-10</text>
  `;
}

async function renderAlertsAndTypology() {
  const drop = parseFloat(document.getElementById("rng-drop").value);
  const surge = parseFloat(document.getElementById("rng-surge").value);
  const stag = parseInt(document.getElementById("rng-stag").value, 10);
  document.getElementById("lbl-drop").textContent = `${drop} %`;
  document.getElementById("lbl-surge").textContent = `+${surge} %`;
  document.getElementById("lbl-stag").textContent = `${stag} mois`;

  const resp = await fetch(`/api/alerts?drop_3m_pct=${drop}&surge_12m_pct=${surge}&stagnation_months=${stag}`);
  const alertsData = await resp.json();

  const grid = document.getElementById("alerts-filtered-grid");
  grid.innerHTML = alertsData.live_alerts.length
    ? alertsData.live_alerts
        .map(
          (a) => `<div class="alert-card"><span class="dot ${a.severity}"></span><div><strong>${a.badge}</strong><br/>${a.message}</div></div>`
        )
        .join("")
    : `<div class="muted">Aucune alerte active avec ces seuils.</div>`;

  const res = STATE.data.results;
  document.getElementById("typology-clusters").innerHTML = res.typology.clusters
    .map(
      (c) => `<div class="cluster-box">
        <div class="card-header-row"><strong>${c.label}</strong><span class="pill-badge">TPI moy. ${c.mean_tpi} (${c.mean_delta_12m >= 0 ? "+" : ""}${c.mean_delta_12m} pts)</span></div>
        <p class="muted" style="margin:4px 0 6px">${c.description}</p>
        <div><strong>Territoires :</strong> ${c.provinces.join(" • ")}</div>
      </div>`
    )
    .join("");

  document.getElementById("historical-shocks-list").innerHTML = res.alerts.historical_shocks
    .map((s) => `<li><strong>${s.date}</strong> — ${s.message} (z = ${s.z_score})</li>`)
    .join("");
}

function initSimulator() {
  const sel = document.getElementById("sim-prov-select");
  const latest = getFrame(STATE.data.dates.length - 1).rows;
  sel.innerHTML = latest.map((r) => `<option value="${r.province_id}" ${r.province_id === STATE.simPid ? "selected" : ""}>${r.province_name}</option>`).join("");
  sel.onchange = () => {
    STATE.simPid = sel.value;
    runSimulation();
  };

  const container = document.getElementById("sim-sliders");
  container.innerHTML = COMP_META.map(
    (m) => `<div class="sim-slider-row">
      <span>${m.label}</span>
      <input type="range" class="sim-rng" data-comp="${m.key}" min="-40" max="60" step="2" value="0" />
      <strong id="sim-val-${m.key}">+0 %</strong>
    </div>`
  ).join("");

  container.querySelectorAll(".sim-rng").forEach((inp) => {
    inp.oninput = () => {
      const k = inp.dataset.comp;
      const v = parseFloat(inp.value);
      STATE.simShocks[k] = v;
      document.getElementById(`sim-val-${k}`).textContent = `${v >= 0 ? "+" : ""}${v} %`;
      runSimulation();
    };
  });

  document.getElementById("sim-reset").onclick = () => {
    Object.keys(STATE.simShocks).forEach((k) => {
      STATE.simShocks[k] = 0;
      document.getElementById(`sim-val-${k}`).textContent = "+0 %";
    });
    container.querySelectorAll(".sim-rng").forEach((el) => (el.value = 0));
    runSimulation();
  };
  runSimulation();
}

async function runSimulation() {
  const resp = await fetch("/api/simulate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ province_id: STATE.simPid, shocks_pct: STATE.simShocks }),
  });
  const sim = await resp.json();
  document.getElementById("sim-base-tpi").textContent = `${sim.base_tpi.toFixed(1)} / 100`;
  document.getElementById("sim-new-tpi").textContent = `${sim.simulated_tpi.toFixed(1)} / 100`;
  const d = document.getElementById("sim-delta-tpi");
  d.textContent = `${sim.delta_tpi >= 0 ? "+" : ""}${sim.delta_tpi.toFixed(2)} pts`;
  d.className = `kpi-sub ${sim.delta_tpi >= 0 ? "pos" : "neg"}`;
  document.getElementById("sim-rank").textContent = `#${sim.base_rank} → #${sim.simulated_rank}`;
  document.getElementById("sim-cluster").textContent = `${sim.base_cluster} → ${sim.simulated_cluster}`;

  const svg = document.getElementById("sim-bar-svg");
  let html = "";
  COMP_META.forEach((m, i) => {
    const y = 12 + i * 33;
    const v = sim.simulated_components[m.key];
    const bw = (v / 100) * 280;
    html += `
      <text x="138" y="${y + 14}" text-anchor="end" fill="currentColor" font-size="11">${m.label}</text>
      <rect x="148" y="${y + 2}" width="${bw.toFixed(1)}" height="16" rx="4" fill="#34D399"/>
      <text x="${156 + bw}" y="${y + 14}" fill="currentColor" font-size="11" font-weight="700">${v.toFixed(0)}</text>
    `;
  });
  svg.innerHTML = html;
}

function renderMethodologyView() {
  const latest = getFrame(STATE.data.dates.length - 1).rows;
  document.getElementById("pdf-export-grid").innerHTML = latest
    .map(
      (r) => `<a class="btn-outline" href="/api/fiche/${r.province_id}.pdf" target="_blank">📄 Fiche ${r.province_name} (${r.tpi_score.toFixed(0)}/100)</a>`
    )
    .join("");

  const meth = STATE.data.results.tpi_methodology;
  document.getElementById("m-pca-corr").textContent = `r = ${meth.expert_vs_pca_corr}`;
  document.getElementById("sensitivity-summary").innerHTML = `
    <strong>Test de sensibilité des poids (${meth.sensitivity.n_simulations} tirages ±${meth.sensitivity.perturbation_pct} %) :</strong><br/>
    Corrélation de rang moyenne : <b>${meth.sensitivity.mean_spearman_rank_corr}</b> •
    Stabilité du Top 3 : <b>${meth.sensitivity.top3_stability_pct} %</b> •
    Écart moyen maximal de score : <b>±${meth.sensitivity.mean_max_score_diff_pts} pts</b>.
  `;
}

async function openProvinceDrawer(pid) {
  const resp = await fetch(`/api/province/${pid}`);
  const prof = await resp.json();
  document.getElementById("drw-type").textContent = `${prof.province_type} • ${prof.cluster_label}`;
  document.getElementById("drw-name").textContent = prof.province_name;
  document.getElementById("drw-body").innerHTML = `
    <p class="muted">${prof.description}</p>
    <div class="sim-kpi-row">
      <div class="sim-box"><div class="kpi-label">Indice TPI</div><div class="kpi-value">${prof.tpi_score} / 100</div><div class="kpi-sub">Rang ${prof.tpi_rank}e / ${prof.total_provinces}</div></div>
      <div class="sim-box"><div class="kpi-label">Tendance 12 mois</div><div class="kpi-value ${prof.delta_12m >= 0 ? "teal" : "crimson"}">${prof.delta_12m >= 0 ? "+" : ""}${prof.delta_12m} pts</div></div>
    </div>
    <h4>Points forts</h4>
    <ul>${prof.strengths.map((s) => `<li>${s}</li>`).join("")}</ul>
    <h4>Points de vigilance</h4>
    <ul>${prof.watchpoints.map((w) => `<li>${w}</li>`).join("")}</ul>
    <h4>Recommandations</h4>
    <ol>${prof.recommendations.map((r) => `<li>${r}</li>`).join("")}</ol>
    <div style="margin-top:16px">
      <a class="btn-primary" href="/api/fiche/${prof.province_id}.pdf" target="_blank">Télécharger la Fiche Territoire PDF</a>
    </div>
  `;
  document.getElementById("drawer-backdrop").classList.add("open");
  document.getElementById("province-drawer").classList.add("open");
}

function closeDrawer() {
  document.getElementById("drawer-backdrop").classList.remove("open");
  document.getElementById("province-drawer").classList.remove("open");
}

function togglePlayback() {
  STATE.playing = !STATE.playing;
  const lbl = STATE.playing ? "❚❚" : "▶";
  document.getElementById("night-play").textContent = lbl;
  document.getElementById("dash-play").textContent = lbl;

  if (STATE.playing) {
    const speed = parseInt(document.getElementById("play-speed").value, 10);
    STATE.timer = setInterval(() => {
      STATE.currentIdx = (STATE.currentIdx + 1) % STATE.data.dates.length;
      updateTimelineUI();
    }, speed);
  } else {
    clearInterval(STATE.timer);
  }
}

function switchView(viewName) {
  STATE.view = viewName;
  document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
  document.getElementById(`view-${viewName}`).classList.add("active");
  document.querySelectorAll(".nav-tab").forEach((t) => t.classList.toggle("active", t.dataset.view === viewName));

  // Auto-switch theme cleanly between Vue Nuit & Tableau de bord Clair unless user toggled manually
  if (viewName === "night" && STATE.theme !== "dark") setTheme("dark");
  if (viewName === "dashboard" && STATE.theme !== "light") setTheme("light");

  setTimeout(() => {
    drawNightMap();
    drawDashChoropleth();
  }, 30);
}

function setTheme(mode) {
  STATE.theme = mode;
  document.documentElement.setAttribute("data-theme", mode);
  document.getElementById("theme-icon").textContent = mode === "dark" ? "☀" : "🌙";
  document.getElementById("theme-label").textContent = mode === "dark" ? "Mode clair" : "Mode nuit";
  document.getElementById("brand-subtitle").textContent =
    mode === "dark" ? I18N[STATE.lang].sub_night : I18N[STATE.lang].sub_light;
  drawDashChoropleth();
}

function toggleLanguage() {
  STATE.lang = STATE.lang === "fr" ? "en" : "fr";
  document.getElementById("btn-lang").textContent = STATE.lang.toUpperCase();
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.dataset.i18n;
    if (I18N[STATE.lang][key]) el.textContent = I18N[STATE.lang][key];
  });
  updateTimelineUI();
}

async function initApp() {
  const resp = await fetch("/api/bootstrap");
  STATE.data = await resp.json();
  STATE.currentIdx = STATE.data.dates.length - 1;

  // Populate dashboard province selector
  const dashSel = document.getElementById("dash-prov-select");
  getFrame(STATE.currentIdx).rows.forEach((r) => {
    const opt = document.createElement("option");
    opt.value = r.province_id;
    opt.textContent = r.province_name;
    dashSel.appendChild(opt);
  });
  dashSel.value = STATE.dashSelectedPid;
  dashSel.onchange = () => {
    STATE.dashSelectedPid = dashSel.value;
    drawDashChoropleth();
    renderDashEvoChart();
  };
  document.getElementById("dash-export-btn").onclick = () => {
    window.open(`/api/fiche/${STATE.dashSelectedPid}.pdf`, "_blank");
  };

  // Layer pills
  document.querySelectorAll(".layer-pill").forEach((pill) => {
    pill.onclick = () => {
      STATE.layer = pill.dataset.layer;
      document.querySelectorAll(".layer-pill").forEach((p) => p.classList.toggle("active", p === pill));
      drawNightMap();
    };
  });

  // Nav tabs
  document.querySelectorAll(".nav-tab").forEach((tab) => {
    tab.onclick = () => switchView(tab.dataset.view);
  });

  // Sliders & playback
  const onSlide = (val) => {
    STATE.currentIdx = parseInt(val, 10);
    updateTimelineUI();
  };
  document.getElementById("night-slider").oninput = (e) => onSlide(e.target.value);
  document.getElementById("dash-slider").oninput = (e) => onSlide(e.target.value);
  document.getElementById("night-play").onclick = togglePlayback;
  document.getElementById("dash-play").onclick = togglePlayback;
  document.getElementById("btn-theme").onclick = () => setTheme(STATE.theme === "dark" ? "light" : "dark");
  document.getElementById("btn-lang").onclick = toggleLanguage;
  document.getElementById("drw-close").onclick = closeDrawer;
  document.getElementById("drawer-backdrop").onclick = closeDrawer;

  // Alert threshold listeners
  ["rng-drop", "rng-surge", "rng-stag"].forEach((id) => {
    document.getElementById(id).oninput = renderAlertsAndTypology;
  });

  attachCanvasEvents("night-canvas", "night-tooltip", openProvinceDrawer);
  attachCanvasEvents("dash-canvas", "dash-tooltip", (pid) => {
    STATE.dashSelectedPid = pid;
    dashSel.value = pid;
    drawDashChoropleth();
    renderDashEvoChart();
  });

  window.addEventListener("resize", () => {
    drawNightMap();
    drawDashChoropleth();
  });

  renderNightSidebarStatic();
  updateTimelineUI();
  renderComparator();
  renderNowcastView();
  renderAlertsAndTypology();
  initSimulator();
  renderMethodologyView();
}

initApp();
