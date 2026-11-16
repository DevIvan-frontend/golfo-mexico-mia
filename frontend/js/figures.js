/**
 * @module figures
 * Constructores de figuras de Plotly. Se usan en dos sitios:
 *   1. panels.js  → para dibujar los gráficos en la ventana de detalle.
 *   2. exporter.js → para generar imágenes PNG que se incrustan en el Excel (con fondo claro).
 * Cada función devuelve un objeto `{ data, layout }` listo para `Plotly.newPlot` o `Plotly.toImage`.
 */
import { t, tx, getLang } from "./i18n.js";
import { plotlyScale } from "./palettes.js";

/** Unidades de cada variable tal como se muestran en la interfaz. */
export const UNITS = { sst: "°C", chl: "mg m⁻³", sst_anom: "°C", chl_anom: "%" };
const GRID = "rgba(140,190,220,0.14)";
const AXIS = "#9bb6c6";

/** Plantilla oscura común a todos los gráficos de la interfaz. */
export function baseLayout(extra = {}) {
  const ax = { gridcolor: GRID, zerolinecolor: "rgba(140,190,220,0.35)", color: AXIS };
  return {
    paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
    font: { color: "#e6f1f7", family: "Segoe UI, system-ui, sans-serif", size: 12 },
    margin: { l: 60, r: 60, t: 30, b: 45 }, xaxis: { ...ax }, yaxis: { ...ax },
    legend: { orientation: "h", y: 1.12, x: 0 }, hovermode: "x unified", ...extra,
  };
}

/** Rango del eje X a partir del filtro de años `{from, to}`. */
const xRange = (range) => (range ? [`${range.from}-01-01`, `${range.to}-12-31`] : undefined);

/**
 * Serie mensual de un área: valores, climatología (línea punteada) y anomalías (barras, eje derecho),
 * con líneas verticales para el mes seleccionado y los eventos de la zona.
 * @param {object} ts respuesta de /api/area/timeseries
 * @param {"sst"|"chl"} v variable
 * @param {string} month mes seleccionado "YYYY-MM"
 * @param {{from:number,to:number}} [range] filtro de años
 */
export function seriesFigure(ts, v, month, range) {
  const isChl = v === "chl";
  const unidad = isChl ? "%" : "°C";
  const shapes = [{ type: "line", x0: month, x1: month, yref: "paper", y0: 0, y1: 1, line: { color: "#f0b44c", width: 2, dash: "dot" } }];
  const annotations = [];
  for (const e of ts.events || []) {
    const m0 = e.start.slice(0, 7);
    if (m0 < ts.months[0] || m0 > ts.months.at(-1)) continue;
    if (range && (+m0.slice(0, 4) < range.from || +m0.slice(0, 4) > range.to)) continue;
    shapes.push({ type: "line", x0: m0, x1: m0, yref: "paper", y0: 0, y1: 1, line: { color: e.type === "human" ? "#ff5f8f" : "#f0b44c", width: 1 } });
    annotations.push({ x: m0, yref: "paper", y: 1.02, text: tx(e.name), showarrow: false, textangle: -30, font: { size: 9, color: AXIS }, xanchor: "left" });
  }
  return {
    data: [
      { x: ts.months, y: ts.values, name: `${t(v)} (${UNITS[v]})`, mode: "lines", line: { color: isChl ? "#5cc76b" : "#f2845f", width: 1.8 } },
      { x: ts.months, y: ts.clim, name: getLang() === "es" ? "Normal 2003–2024" : "2003–2024 normal", mode: "lines", line: { color: AXIS, width: 1, dash: "dot" } },
      { x: ts.months, y: ts.anom, name: `${t("anomaly")} (${unidad})`, type: "bar", yaxis: "y2",
        marker: { color: ts.anom.map((a) => (a > 0 ? "rgba(255,122,107,.55)" : "rgba(88,182,255,.55)")) } },
    ],
    layout: baseLayout({
      shapes, annotations, margin: { l: 60, r: 60, t: 60, b: 45 },
      xaxis: { gridcolor: GRID, color: AXIS, range: xRange(range) },
      yaxis: { title: UNITS[v], type: isChl ? "log" : "linear", gridcolor: GRID, color: AXIS },
      yaxis2: { title: unidad, overlaying: "y", side: "right", showgrid: false, color: AXIS, zeroline: true },
    }),
  };
}

/** Barras de registros OBIS por año (eje logarítmico); resalta el año seleccionado. */
export function faunaFigure(serie, year) {
  return {
    data: [{ x: serie.map((r) => r.year), y: serie.map((r) => r.records || null), type: "bar", name: t("records"),
             marker: { color: serie.map((r) => (r.year === year ? "#f0b44c" : "#35c2d6")) } }],
    layout: baseLayout({ yaxis: { title: t("records"), type: "log", gridcolor: GRID, color: AXIS }, hovermode: "closest" }),
  };
}

/** Radar SAR por año: superficie amortiguada y objetos brillantes (barras, %) y viento del radar (línea, m/s). */
export function sarFigure(filas, year) {
  const x = filas.map((r) => r.year);
  return {
    data: [
      { x, y: filas.map((r) => r.damped_pct), type: "bar", name: `${t("var_sar_damped")} (%)`,
        marker: { color: x.map((y) => (y === year ? "#f0b44c" : "#c9302c")) } },
      { x, y: filas.map((r) => r.bright_pct), type: "bar", name: `${t("var_sar_bright")} (%)`,
        marker: { color: x.map((y) => (y === year ? "#fde99a" : "#8f2e7a")) } },
      { x, y: filas.map((r) => r.wind), name: `${t("var_sar_wind")} (m/s)`, mode: "lines+markers", yaxis: "y2",
        line: { color: "#41b6c4", width: 2 } },
    ],
    layout: baseLayout({ barmode: "group", xaxis: { dtick: 1, gridcolor: GRID, color: AXIS },
      yaxis: { title: "%", gridcolor: GRID, color: AXIS, rangemode: "tozero" },
      yaxis2: { title: "m/s", overlaying: "y", side: "right", showgrid: false, color: AXIS, rangemode: "tozero" } }),
  };
}

/**
 * Relieve 3D (altitud ETOPO1) coloreado por una variable en el mar; la tierra se dibuja en tonos tierra.
 * @param {object} s respuesta de /api/area/surface
 * @param {{colorVar:string, conColor:boolean, meta:object, autoScale:boolean, exag:number}} o opciones
 */
export function reliefFigure(s, o) {
  const alt = s.altitude, val = s.values;
  const isLog = o.colorVar === "chl";
  const oceanZ = alt.map((r) => r.map((a) => (a !== null && a < 0 ? a : null)));
  const landZ = alt.map((r) => r.map((a) => (a !== null && a >= 0 ? a : null)));
  const color = val.map((r, i) => r.map((x, j) => (alt[i][j] !== null && alt[i][j] < 0
    ? (o.conColor && x !== null ? (isLog ? Math.log10(Math.max(x, 0.01)) : x) : alt[i][j]) : null)));
  const cscale = o.conColor ? plotlyScale(o.meta.palette)
    : plotlyScale("deep").slice().reverse().map(([, c], i, a) => [i / (a.length - 1), c]);
  const rango = o.conColor && !o.autoScale ? (isLog ? o.meta.range.map(Math.log10) : o.meta.range) : [undefined, undefined];
  const ratioY = (s.lats.at(-1) - s.lats[0]) / ((s.lons.at(-1) - s.lons[0]) || 1);
  return {
    data: [
      { type: "surface", x: s.lons, y: s.lats, z: oceanZ, surfacecolor: color, colorscale: cscale, cmin: rango[0], cmax: rango[1],
        name: t("depth"), colorbar: { title: o.conColor ? (isLog ? "log₁₀ mg m⁻³" : o.meta.units) : "m", len: 0.7 },
        hovertemplate: `${t("lat")} %{y:.2f}<br>${t("lon")} %{x:.2f}<br>${t("elevation")} %{z:.0f}<extra></extra>` },
      { type: "surface", x: s.lons, y: s.lats, z: landZ, showscale: false, colorscale: [[0, "#6b5b3e"], [1, "#d8c9a3"]],
        hovertemplate: `${t("elevation")} %{z:.0f} m<extra></extra>`, name: "land" },
    ],
    layout: {
      ...baseLayout({ margin: { l: 0, r: 0, t: 10, b: 0 } }),
      scene: { aspectmode: "manual", aspectratio: { x: 1, y: ratioY, z: o.exag },
        xaxis: { title: t("lon"), color: AXIS, gridcolor: "rgba(140,190,220,.2)" },
        yaxis: { title: t("lat"), color: AXIS, gridcolor: "rgba(140,190,220,.2)" },
        zaxis: { title: t("elevation"), color: AXIS, gridcolor: "rgba(140,190,220,.2)" },
        camera: { eye: { x: 1.3, y: -1.5, z: 0.9 } }, bgcolor: "rgba(0,0,0,0)" },
    },
  };
}

/** Nube 3D de celdas del mes: X = TSM, Y = log10(clorofila), Z = −profundidad, color = anomalía de TSM. */
export function propsFigure(c) {
  const idx = c.sst.map((_, i) => i).filter((i) => c.sst[i] !== null && c.chl[i] !== null && c.depth[i] !== null);
  const g = (arr) => idx.map((i) => arr[i]);
  const s = (x, d) => (x === null ? "—" : `${x > 0 ? "+" : ""}${x.toFixed(d)}`);
  return {
    data: [{
      type: "scatter3d", mode: "markers",
      x: g(c.sst), y: g(c.chl).map((v) => Math.log10(v)), z: g(c.depth).map((d) => -d),
      text: idx.map((i) => `${c.lat[i]}°, ${c.lon[i]}° · ${t("anomaly")}: ${s(c.sst_anom[i], 2)} °C / ${s(c.chl_anom[i], 0)} %`),
      marker: { size: 6, color: g(c.sst_anom), colorscale: plotlyScale("diverging"), cmin: -3, cmax: 3,
                colorbar: { title: `${t("anomaly")} °C`, len: 0.7 }, line: { width: 0 } },
      hovertemplate: `${t("sst")}: %{x:.2f} °C<br>log₁₀ ${t("chl")}: %{y:.2f}<br>${t("depth")}: %{z:.0f} m<br>%{text}<extra></extra>`,
    }],
    layout: {
      ...baseLayout({ margin: { l: 0, r: 0, t: 10, b: 0 } }),
      scene: { xaxis: { title: `${t("sst")} (°C)`, color: AXIS }, yaxis: { title: `log₁₀ ${t("chl")}`, color: AXIS },
               zaxis: { title: t("depth_m"), color: AXIS }, bgcolor: "rgba(0,0,0,0)", camera: { eye: { x: 1.5, y: 1.4, z: 0.8 } } },
    },
  };
}

/** Anomalías de TSM (eje izq.) y de clorofila (eje der.) del área, para comparar ambas propiedades. */
export function propsSeriesFigure(a, b, month, range) {
  return {
    data: [
      { x: a.months, y: a.anom, name: `${t("sst")} · ${t("anomaly")} (°C)`, line: { color: "#f2845f" } },
      { x: b.months, y: b.anom, name: `${t("chl")} · ${t("anomaly")} (%)`, yaxis: "y2", line: { color: "#5cc76b" } },
    ],
    layout: baseLayout({
      shapes: [{ type: "line", x0: month, x1: month, yref: "paper", y0: 0, y1: 1, line: { color: "#f0b44c", dash: "dot" } }],
      xaxis: { gridcolor: GRID, color: AXIS, range: xRange(range) },
      yaxis: { title: "°C", color: "#f2845f", gridcolor: GRID },
      yaxis2: { title: "%", overlaying: "y", side: "right", color: "#5cc76b", showgrid: false },
    }),
  };
}

/** Anomalías ±24 meses alrededor de un evento, con el periodo del evento sombreado. */
export function eventFigure(imp, ev) {
  const m0 = imp.months[imp.event_index];
  const m1 = (ev.end || ev.start).slice(0, 7);
  const col = ev.type === "human" ? "#ff5f8f" : "#f0b44c";
  return {
    data: [
      { x: imp.months, y: imp.sst.anom, name: `${t("sst")} · ${t("anomaly")} (°C)`, line: { color: "#f2845f", width: 2 } },
      { x: imp.months, y: imp.chl.anom, name: `${t("chl")} · ${t("anomaly")} (%)`, yaxis: "y2", line: { color: "#5cc76b", width: 2 } },
    ],
    layout: baseLayout({
      shapes: [{ type: "rect", x0: m0, x1: m1 > m0 ? m1 : m0, yref: "paper", y0: 0, y1: 1,
                 fillcolor: ev.type === "human" ? "rgba(255,95,143,.18)" : "rgba(240,180,76,.18)", line: { color: col, width: 2 } }],
      annotations: [{ x: m0, yref: "paper", y: 1.05, text: t("event_line"), showarrow: false, font: { color: "#f0b44c" } }],
      yaxis: { title: "°C", color: "#f2845f", gridcolor: GRID, zeroline: true },
      yaxis2: { title: "%", overlaying: "y", side: "right", color: "#5cc76b", showgrid: false, zeroline: false },
    }),
  };
}

/**
 * Versión de fondo claro de una figura (para Excel, donde el fondo es blanco) y su PNG en base64.
 * @returns {Promise<string>} data URL "data:image/png;base64,…"
 */
export async function figureToPng(fig, width = 1100, height = 520) {
  const lay = JSON.parse(JSON.stringify(fig.layout));
  lay.paper_bgcolor = "#ffffff"; lay.plot_bgcolor = "#ffffff";
  lay.font = { ...(lay.font || {}), color: "#1b2733" };
  const claro = (ax) => ax && Object.assign(ax, { color: "#33434f", gridcolor: "#dde5ea", zerolinecolor: "#9aa9b3" });
  for (const k of Object.keys(lay)) if (/^[xy]axis\d*$/.test(k)) claro(lay[k]);
  if (lay.scene) { ["xaxis", "yaxis", "zaxis"].forEach((k) => claro(lay.scene[k] || (lay.scene[k] = {}))); lay.scene.bgcolor = "#ffffff"; }
  const data = fig.data.map((d) => (d.colorbar ? { ...d, colorbar: { ...d.colorbar, tickfont: { color: "#1b2733" } } } : d));
  return Plotly.toImage({ data, layout: lay }, { format: "png", width, height });
}
