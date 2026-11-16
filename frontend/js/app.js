/**
 * @module app
 * Punto de entrada del frontend. Gestiona:
 *   - el mapa Leaflet (mapas base, malla de la variable dibujada en un canvas reproyectado a Web Mercator,
 *     eventos, áreas protegidas, registros OBIS e imágenes diarias de NASA GIBS);
 *   - la selección (clic = celda de 1°, o rectángulo/polígono con Leaflet.draw) → panels.open();
 *   - la barra lateral (variables, capas, filtros de eventos, guía) y la búsqueda global (search.js);
 *   - la línea de tiempo (mes a mes 2003–2024, reproducción y marcas de eventos).
 * El estado compartido con los demás módulos viaja en el objeto `ctx`.
 */
import { t, tx, setLang, getLang, applyTranslations, fmtMonth, fmtDate, fmtNum } from "./i18n.js";
import { api } from "./api.js";
import { colorAt, norm, cssGradient, legendTicks } from "./palettes.js";
import { initPanels } from "./panels.js";
import { initSearch } from "./search.js";
import { initNotebook } from "./notebook.js";
import { initSar } from "./sar.js";

const VARS = ["sst", "sst_anom", "sst_change", "chl", "chl_anom", "depth"];
const VARS_SAR = ["sar_damped", "sar_bright", "sar_wind"];     // radar Sentinel-1 (si se generaron los productos)
const OVERLAYS = ["events", "places", "obis", "sar", "slicks", "outline", "gibs_true", "gibs_sst", "gibs_chl"];
const esSar = (v) => v.startsWith("sar_");
const GIBS = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best";
const ACTIVE_WINDOW = 6;   // meses alrededor de un evento en los que se resalta

const state = {
  var: "sst", mi: 0, months: [], opacity: 0.85, mode: "cell", playing: false, timer: null, autoScale: false,
  overlays: { events: true, places: true, obis: false, sar: false, slicks: false, outline: true, gibs_true: false, gibs_sst: false, gibs_chl: false },
  /** Filtros de eventos: tipo, texto, categoría, rango de años y "solo activos en la fecha del mapa". */
  evf: { type: "all", q: "", cat: "", from: 2003, to: 2024, onlyActive: false },
};
const ctx = { state, month: () => state.months[state.mi] };
let map, gridOverlay, currentGrid = null, selLayer = null, drawer = null, panels, gridToken = 0;
const L_ = {};          // capas
const evLayers = new Map();
const placeLayers = new Map();

/* ------------------------------------------------------------------ utilidades */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const monthDiff = (a, b) => (+a.slice(0, 4) - +b.slice(0, 4)) * 12 + (+a.slice(5, 7) - +b.slice(5, 7));
const debounce = (fn, ms) => { let h; return (...a) => { clearTimeout(h); h = setTimeout(() => fn(...a), ms); }; };

/** Aviso flotante. kind: "error" (rojo, por defecto), "info" o "ok". ms = 0 lo deja fijo. */
function toast(msg, ms = 5000, kind = "error") {
  const el = $("#toast");
  el.textContent = msg;
  el.className = `toast ${kind}`;
  clearTimeout(toast.h);
  if (ms) toast.h = setTimeout(() => el.classList.add("hidden"), ms);
}
ctx.toast = toast;
ctx.varMeta = (v) => ctx.meta.variables[v];

/* ------------------------------------------------------------------ arranque */
boot();

async function boot() {
  applyTranslations();
  markLang();
  try {
    ctx.meta = await api.meta();
  } catch (e) {
    toast(`${t("api_error")} (${e.message}). ${t("backend_hint")}`, 0);
    return;
  }
  state.months = ctx.meta.months;
  const inicial = state.months.indexOf("2024-03");
  state.mi = inicial >= 0 ? inicial : state.months.length - 1;
  [ctx.events, ctx.places] = await Promise.all([api.events(), api.places().catch(() => [])]);
  state.evf.from = +state.months[0].slice(0, 4);
  state.evf.to = +state.months.at(-1).slice(0, 4);
  initMap();
  ctx.sarUI = initSar(ctx);
  initSidebar();
  initTimeline();
  ctx.notebook = initNotebook(ctx);
  panels = initPanels(ctx);
  ctx.closeModal = panels.closeModal;
  initSearch(ctx);
  renderManifest();
  setMonth(state.mi, { force: true });
}

/* ------------------------------------------------------------------ mapa */
function gibsLayer(layer, tms, ext, zoom, date, opts = {}) {
  return L.tileLayer(`${GIBS}/${layer}/default/${date}/${tms}/{z}/{y}/{x}.${ext}`,
    { maxNativeZoom: zoom, maxZoom: 10, attribution: "Imagery: NASA GIBS / EOSDIS", ...opts });
}

function initMap() {
  map = L.map("map", { center: [24.6, -90], zoom: 5, minZoom: 3, maxZoom: 10, worldCopyJump: true });
  ctx.map = map;
  const bases = {
    bluemarble: gibsLayer("BlueMarble_ShadedRelief_Bathymetry", "GoogleMapsCompatible_Level8", "jpeg", 8, "2004-08-01"),
    osm: L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 10, attribution: "© OpenStreetMap contributors" }),
    topo: L.tileLayer("https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png", { maxZoom: 10, attribution: "© OpenStreetMap, SRTM · © OpenTopoMap (CC-BY-SA)" }),
  };
  L_.bases = bases;
  bases.bluemarble.addTo(map);

  const blank = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7";
  const b = ctx.meta.bbox;
  gridOverlay = L.imageOverlay(blank, [[b.south, b.west], [b.north, b.east]], { opacity: state.opacity, interactive: false, zIndex: 5 }).addTo(map);

  L_.outline = L.polygon(ctx.meta.gulf_polygon.map(([lo, la]) => [la, lo]),
    { color: "#35c2d6", weight: 1.3, dashArray: "6 5", fill: false, interactive: false });
  L_.events = L.layerGroup();
  L_.places = L.layerGroup();
  L_.obis = L.geoJSON(null, { style: obisStyle, onEachFeature: (f, l) => l.bindTooltip(() => `${fmtNum(f.properties.n, 0)} ${t("records")} OBIS`) });
  L_.gibs_true = null; L_.gibs_sst = null; L_.gibs_chl = null;
  buildEventLayers();
  buildPlaces();
  for (const k of ["outline", "events", "places"]) if (state.overlays[k]) L_[k].addTo(map);
  map.fitBounds(L_.outline.getBounds(), { padding: [12, 12] });

  // Control de selección en el propio mapa (útil en móvil)
  const SelCtl = L.Control.extend({
    options: { position: "topleft" },
    onAdd() {
      const div = L.DomUtil.create("div", "leaflet-bar sel-ctl");
      div.innerHTML = `<a href="#" data-mode="cell" title="1°">▦</a><a href="#" data-mode="rect" title="▭">▭</a><a href="#" data-mode="poly" title="⬠">⬠</a>`;
      L.DomEvent.disableClickPropagation(div);
      div.addEventListener("click", (e) => { const m = e.target.closest("a")?.dataset.mode; if (m) { e.preventDefault(); setMode(m); } });
      return div;
    },
  });
  map.addControl(new SelCtl());
  L.control.scale({ imperial: false, position: "bottomright" }).addTo(map);

  map.on("click", (e) => { if (state.mode === "cell" && !drawer) selectCell(e.latlng); });
  map.on("mousemove", (e) => readout(e.latlng));
  map.on("mouseout", () => readout(null));
  map.on(L.Draw.Event.CREATED, (e) => {
    drawer = null;
    const lay = e.layer;
    if (e.layerType === "rectangle") {
      const bb = lay.getBounds();
      selectArea({ type: "bbox", bbox: [bb.getWest(), bb.getSouth(), bb.getEast(), bb.getNorth()], kind: "rect" });
    } else {
      selectArea({ type: "poly", coords: lay.getLatLngs()[0].map((p) => [p.lng, p.lat]), kind: "poly" });
    }
    setMode("cell");
  });
  map.on(L.Draw.Event.DRAWSTOP, () => { drawer = null; });

  // Acciones dentro de los popups de Leaflet (delegación)
  map.getContainer().addEventListener("click", (e) => {
    const btn = e.target.closest("[data-act]");
    if (!btn) return;
    const id = btn.dataset.id;
    if (btn.dataset.act === "analyze") goToEvent(id, { analyze: true });
    if (btn.dataset.act === "goto") goToEvent(id, { analyze: false });
  });
}

function setMode(mode) {
  state.mode = mode;
  $$("#sel-mode button").forEach((b) => b.classList.toggle("active", b.dataset.mode === mode));
  $$(".sel-ctl a").forEach((a) => a.classList.toggle("active", a.dataset.mode === mode));
  if (drawer) { drawer.disable(); drawer = null; }
  const shape = { color: "#f0b44c", weight: 2, fillOpacity: 0.08 };
  if (mode === "rect") drawer = new L.Draw.Rectangle(map, { shapeOptions: shape, showArea: false, metric: true });
  if (mode === "poly") drawer = new L.Draw.Polygon(map, { shapeOptions: shape, showArea: false, allowIntersection: false });
  if (drawer) drawer.enable();
}

/** Selecciona la celda de 1°×1° que contiene el punto (esquina SO = parte entera de lat/lon). */
function selectCell(ll) {
  const b = ctx.meta.bbox;
  if (ll.lat < b.south || ll.lat >= b.north || ll.lng < b.west || ll.lng >= b.east) return false;
  const s = Math.floor(ll.lat), w = Math.floor(ll.lng);
  selectArea({ type: "bbox", bbox: [w, s, w + 1, s + 1], kind: "cell" });
  return true;
}
/** Usado por la búsqueda de coordenadas: centra el mapa y analiza la celda (avisa si está fuera del golfo). */
ctx.selectCellAt = (lat, lon) => {
  map.flyTo([lat, lon], Math.max(map.getZoom(), 6), { duration: 0.7 });
  if (!selectCell(L.latLng(lat, lon))) toast(`${fmtNum(lat, 2)}, ${fmtNum(lon, 2)}: ${t("land")}`, 4000, "info");
};
/** Usado por la búsqueda de lugares: centra el mapa y abre la ficha del lugar. */
ctx.focusPlace = (id) => {
  const m = placeLayers.get(id);
  if (!m) return;
  if (!map.hasLayer(L_.places)) { state.overlays.places = true; L_.places.addTo(map); renderOverlayList(); }
  map.flyTo(m.getLatLng(), 7, { duration: 0.7 });
  setTimeout(() => m.openPopup(), 750);
};

function selectArea(sel) {
  if (selLayer) map.removeLayer(selLayer);
  const style = { color: "#f0b44c", weight: 2.2, fillOpacity: 0.06, dashArray: sel.kind === "cell" ? null : "4 4", interactive: false };
  selLayer = sel.type === "bbox"
    ? L.rectangle([[sel.bbox[1], sel.bbox[0]], [sel.bbox[3], sel.bbox[2]]], style)
    : L.polygon(sel.coords.map(([lo, la]) => [la, lo]), style);
  selLayer.addTo(map);
  panels.open(sel);
}
ctx.selectArea = selectArea;
ctx.clearSelection = () => { if (selLayer) map.removeLayer(selLayer); selLayer = null; };

/* ------------------------------------------------------------------ malla de datos */
function merc(lat) { return Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360)); }
function invMerc(y) { return (Math.atan(Math.exp(y)) * 360) / Math.PI - 90; }

/** Rango de color: fijo (comparable entre meses) o ajustado al mes (percentiles 2–98 del campo visible). */
function rangeFor(v, grid) {
  const meta = ctx.varMeta(v);
  if (!state.autoScale || !grid) return meta.range;
  const vals = grid.values.flat().filter((x) => x !== null && x !== undefined && (meta.scale !== "log" || x > 0));
  if (vals.length < 10) return meta.range;
  const tr = meta.scale === "log" ? vals.map(Math.log10) : vals;
  tr.sort((a, b) => a - b);
  const q = (p) => tr[Math.min(tr.length - 1, Math.floor(p * tr.length))];
  let lo = q(0.02), hi = q(0.98);
  if (meta.palette.startsWith("diverging")) { const m = Math.max(Math.abs(lo), Math.abs(hi)) || 1; lo = -m; hi = m; }
  if (hi - lo < 1e-6) hi = lo + 1;
  return meta.scale === "log" ? [10 ** lo, 10 ** hi] : [lo, hi];
}
ctx.rangeFor = (v) => rangeFor(v, currentGrid && currentGrid.var === v ? currentGrid : null);

function gridToImage(grid, v) {
  const meta = { ...ctx.varMeta(v), range: rangeFor(v, grid) };
  const { lats, lons, values, res } = grid;
  const ny = lats.length, nx = lons.length;
  const south = lats[0] - res / 2, north = lats[ny - 1] + res / 2;
  const yS = merc(south), yN = merc(north);
  const H = ny * 3, W = nx;
  const cv = document.createElement("canvas");
  cv.width = W; cv.height = H;
  const g = cv.getContext("2d");
  const img = g.createImageData(W, H);
  for (let r = 0; r < H; r++) {
    const lat = invMerc(yN - ((r + 0.5) / H) * (yN - yS));
    const iy = Math.min(ny - 1, Math.max(0, Math.floor((lat - south) / res)));
    const row = values[iy];
    for (let c = 0; c < W; c++) {
      const val = row[c];
      const o = (r * W + c) * 4;
      if (val === null || val === undefined) { img.data[o + 3] = 0; continue; }
      const [R, G, B] = colorAt(meta.palette, norm(val, meta.range, meta.scale));
      img.data[o] = R; img.data[o + 1] = G; img.data[o + 2] = B; img.data[o + 3] = 255;
    }
  }
  g.putImageData(img, 0, 0);
  return { url: cv.toDataURL("image/png"), bounds: [[south, lons[0] - res / 2], [north, lons[nx - 1] + res / 2]] };
}

async function refreshGrid() {
  const token = ++gridToken;
  const v = state.var, m = ctx.month();
  try {
    const grid = await api.grid(v, m);
    if (token !== gridToken) return;
    currentGrid = { ...grid, var: v };
    const { url, bounds } = gridToImage(grid, v);
    gridOverlay.setUrl(url);
    gridOverlay.setBounds(bounds);
  } catch (e) {
    toast(`${t("api_error")}: ${e.message}`);
  }
  renderLegend();
  if (state.playing && v !== "depth" && !esSar(v)) {   // precarga de los próximos meses (SAR es anual: ya en caché)
    for (let k = 1; k <= 3; k++) if (state.mi + k < state.months.length) api.grid(v, state.months[state.mi + k]).catch(() => {});
  }
}

function valueAt(ll) {
  if (!currentGrid) return null;
  const { lats, lons, values, res } = currentGrid;
  const iy = Math.floor((ll.lat - (lats[0] - res / 2)) / res);
  const ix = Math.floor((ll.lng - (lons[0] - res / 2)) / res);
  if (iy < 0 || ix < 0 || iy >= lats.length || ix >= lons.length) return undefined;
  return values[iy][ix];
}

function fmtValue(v, val) {
  if (val === null || val === undefined) return t("land");
  const u = ctx.varMeta(v).units;
  const d = v === "chl" ? (val < 1 ? 2 : 1) : v === "depth" || v === "chl_anom" ? 0 : 1;
  const sign = v.endsWith("anom") || v === "sst_change" ? (val > 0 ? "+" : "") : "";
  return `${sign}${fmtNum(val, d)} ${u}`;
}

function readout(ll) {
  const el = $("#readout");
  if (!ll) { el.innerHTML = `<span class="hint">${t("readout_hint")}</span>`; return; }
  const ns = ll.lat >= 0 ? "N" : "S", ew = ll.lng >= 0 ? "E" : (getLang() === "es" ? "O" : "W");
  const val = valueAt(ll);
  el.innerHTML = `${fmtNum(Math.abs(ll.lat), 2)}°${ns}, ${fmtNum(Math.abs(ll.lng), 2)}°${ew}<br>` +
    (val === undefined ? `<span class="hint">—</span>` : `<b>${fmtValue(state.var, val)}</b>`);
}

/** Línea bajo el título de la leyenda: mes, o año y escenas de radar para las variables SAR (anuales). */
function legendHint(v) {
  if (v === "depth") return "";
  if (!esSar(v)) return fmtMonth(ctx.month());
  const g = currentGrid && currentGrid.var === v ? currentGrid : null;
  if (g?.note === "no_sar_year") return `⚠ ${t("sar_no_year", { y: ctx.month().slice(0, 4) })}`;
  return `${ctx.month().slice(0, 4)} · Sentinel-1 · ${t("sar_n_scenes", { n: g?.scenes ?? "…" })}`;
}

function renderLegend() {
  const v = state.var, meta = { ...ctx.varMeta(v), range: ctx.rangeFor(v) };
  const ticks = legendTicks(meta.range, meta.scale);
  const pos = (x) => `${(norm(x, meta.range, meta.scale) * 100).toFixed(1)}%`;
  const fmt = (x) => (meta.scale === "log" ? (x < 1 ? String(+x.toFixed(2)) : String(+x.toFixed(0))) : fmtNum(x, Math.abs(x) < 10 && x % 1 ? 1 : 0));
  const keys = [];
  if (state.overlays.events) keys.push(`<span class="key"><i style="background:var(--natural)"></i>${t("natural")}</span><span class="key"><i style="background:var(--human)"></i>${t("human")}</span>`);
  if (state.overlays.places) keys.push(`<span class="key"><i style="background:#7ee08a;border-radius:2px"></i>${t("ov_places")}</span>`);
  if (state.overlays.slicks) {
    const C = ctx.sarUI.CONF;
    keys.push(`<span class="key"><b>NISAR:</b></span>` + ["high", "medium", "calm"].map((c) =>
      `<span class="key"><i style="background:${C[c]}"></i>${t(`slk_conf_${c}`)}</span>`).join(""));
  }
  $("#legend").innerHTML = `
    <div class="lg-title">${t(`var_${v}`)} <span class="hint">(${meta.units})</span></div>
    <div class="hint">${legendHint(v)}</div>
    <div class="lg-bar" style="background:${cssGradient(meta.palette)}"></div>
    <div class="lg-ticks" style="position:relative;height:14px">${ticks.map((x) => `<span style="position:absolute;left:${pos(x)};transform:translateX(-50%)">${fmt(x)}</span>`).join("")}</div>
    ${keys.length ? `<div class="lg-keys">${keys.join("")}</div>` : ""}
    <div class="lg-dyk"><b>${t("legend_dyk")}</b> ${t(`dyk_${v}`)}</div>`;
}

/* ------------------------------------------------------------------ capas superpuestas */
function obisStyle(f) {
  const n = f.properties.n || 1;
  const c = colorAt("obis", Math.log10(n) / 5);
  return { color: "rgba(255,255,255,0.25)", weight: 0.5, fillColor: `rgb(${c.join(",")})`, fillOpacity: 0.55 };
}

async function refreshObis() {
  if (!state.overlays.obis) return;
  const year = +ctx.month().slice(0, 4);
  if (L_.obis._year === year) return;
  try {
    const fc = await api.obisGrid(year);
    L_.obis.clearLayers(); L_.obis.addData(fc); L_.obis._year = year;
  } catch (e) { toast(`OBIS: ${e.message}`); }
}

function refreshGibs() {
  const date = `${ctx.month()}-15`;
  const defs = {
    gibs_true: ["MODIS_Terra_CorrectedReflectance_TrueColor", "GoogleMapsCompatible_Level9", "jpg", 9, 1],
    gibs_sst: ["GHRSST_L4_MUR_Sea_Surface_Temperature", "GoogleMapsCompatible_Level7", "png", 7, 0.85],
    gibs_chl: ["MODIS_Aqua_L2_Chlorophyll_A", "GoogleMapsCompatible_Level7", "png", 7, 0.9],
  };
  for (const [k, [layer, tms, ext, z, op]] of Object.entries(defs)) {
    if (!state.overlays[k]) { if (L_[k]) { map.removeLayer(L_[k]); L_[k] = null; } continue; }
    if (L_[k] && L_[k]._date === date) continue;
    if (L_[k]) map.removeLayer(L_[k]);
    L_[k] = gibsLayer(layer, tms, ext, z, date, { opacity: op, zIndex: 4 });
    L_[k]._date = date;
    L_[k].addTo(map);
  }
}

function eventPopup(ev) {
  return `<h4>${tx(ev.name)}</h4>
    <div class="muted">${fmtDate(ev.start)}${ev.end ? ` – ${fmtDate(ev.end)}` : ""} · ${t(`cat_${ev.category}`)} · ${t(ev.type)}${ev.approx ? ` · ${t("approx")}` : ""}</div>
    <p>${tx(ev.description)}</p>
    <div class="muted">${t("source")}: <a href="${ev.source.url}" target="_blank" rel="noopener">${ev.source.name}</a></div>
    <div class="pop-actions"><button class="btn" data-act="analyze" data-id="${ev.id}">${t("analyze")}</button>
    <button class="btn ghost" data-act="goto" data-id="${ev.id}">${t("go_date")}</button></div>`;
}

function buildEventLayers() {
  L_.events.clearLayers(); evLayers.clear();
  for (const ev of ctx.events) {
    const color = ev.type === "human" ? "#ff5f8f" : "#f0b44c";
    const circle = L.circle([ev.lat, ev.lon], { radius: ev.radius_km * 1000, color, weight: 1.2, fillColor: color, fillOpacity: 0.04, opacity: 0.35, interactive: false });
    const dot = L.circleMarker([ev.lat, ev.lon], { radius: 6, color: "#fff", weight: 1.5, fillColor: color, fillOpacity: 0.95 });
    dot.bindPopup(() => eventPopup(ev), { maxWidth: 300 });
    dot.bindTooltip(() => tx(ev.name));
    L_.events.addLayer(circle); L_.events.addLayer(dot);
    evLayers.set(ev.id, { circle, dot, ev });
  }
}

function buildPlaces() {
  L_.places.clearLayers();
  const color = { protected: "#7ee08a", reference: "#9fd6df", industrial: "#c8a2ff" };
  for (const p of ctx.places) {
    const m = L.circleMarker([p.lat, p.lon], { radius: 5, color: "#062", weight: 1, fillColor: color[p.kind] || "#ccc", fillOpacity: 0.95 });
    m.bindPopup(() => `<h4>${tx(p.name)}</h4><div class="muted">${t("approx")}</div><p>${tx(p.note)}</p>`);
    m.bindTooltip(() => tx(p.name));
    L_.places.addLayer(m);
    placeLayers.set(p.id, m);
  }
}

const isActive = (ev, month) => {
  const a = monthDiff(month, ev.start.slice(0, 7));
  const b = monthDiff(month, (ev.end || ev.start).slice(0, 7));
  return a >= -ACTIVE_WINDOW && b <= ACTIVE_WINDOW;
};

/** ¿El evento cumple los filtros de la pestaña Eventos? (se aplica a la lista, al mapa y a la línea de tiempo) */
function eventMatches(ev) {
  const f = state.evf;
  const anio = +ev.start.slice(0, 4);
  if (f.type !== "all" && ev.type !== f.type) return false;
  if (f.cat && ev.category !== f.cat) return false;
  if (anio < f.from || anio > f.to) return false;
  if (f.onlyActive && !isActive(ev, ctx.month())) return false;
  if (f.q) {
    const n = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
    const texto = n(`${ev.name.es} ${ev.name.en} ${ev.description.es} ${ev.description.en} ${t(`cat_${ev.category}`)}`);
    if (!texto.includes(n(f.q))) return false;
  }
  return true;
}

/** Muestra en el mapa solo los eventos que cumplen los filtros y resalta los activos en el mes del mapa. */
function updateEventStyles() {
  const m = ctx.month();
  for (const { circle, dot, ev } of evLayers.values()) {
    const visible = eventMatches(ev);
    for (const capa of [circle, dot]) {
      if (visible && !L_.events.hasLayer(capa)) L_.events.addLayer(capa);
      if (!visible && L_.events.hasLayer(capa)) L_.events.removeLayer(capa);
    }
    if (!visible) continue;
    const act = isActive(ev, m);
    circle.setStyle({ opacity: act ? 0.95 : 0.25, fillOpacity: act ? 0.14 : 0.03, weight: act ? 2 : 1 });
    dot.setStyle({ radius: act ? 8 : 5, fillOpacity: act ? 1 : 0.6 });
    circle.getElement()?.classList.toggle("ev-active", act);
  }
}

/* ------------------------------------------------------------------ barra lateral */
function initSidebar() {
  $$(".tabs[role=tablist] button").forEach((b) => b.addEventListener("click", () => {
    $$(".tabs[role=tablist] button").forEach((x) => x.classList.toggle("active", x === b));
    $$(".tab-panel").forEach((p) => p.classList.toggle("active", p.id === `tab-${b.dataset.tab}`));
  }));
  $$(".lang-switch button").forEach((b) => b.addEventListener("click", () => { setLang(b.dataset.lang); markLang(); rerenderAll(); }));
  $("#btn-sidebar").addEventListener("click", () => $("#sidebar").classList.toggle("open"));
  $$("#sel-mode button").forEach((b) => b.addEventListener("click", () => setMode(b.dataset.mode)));
  // Filtros de eventos (lista + mapa + línea de tiempo)
  $$("#ev-filter button").forEach((b) => b.addEventListener("click", () => {
    state.evf.type = b.dataset.f;
    $$("#ev-filter button").forEach((x) => x.classList.toggle("active", x === b));
    applyEventFilters();
  }));
  $("#ev-q").addEventListener("input", debounce((e) => { state.evf.q = e.target.value.trim(); applyEventFilters(); }, 150));
  $("#ev-cat").addEventListener("change", (e) => { state.evf.cat = e.target.value; applyEventFilters(); });
  $("#ev-only-active").addEventListener("change", (e) => { state.evf.onlyActive = e.target.checked; applyEventFilters(); });
  for (const id of ["ev-from", "ev-to"]) {
    $(`#${id}`).addEventListener("change", () => {
      let a = +$("#ev-from").value, b = +$("#ev-to").value;
      if (a > b) [a, b] = [b, a];
      Object.assign(state.evf, { from: a, to: b });
      applyEventFilters();
    });
  }
  renderEventFilterOptions();
  $("#opacity").addEventListener("input", (e) => { state.opacity = +e.target.value; gridOverlay.setOpacity(state.opacity); });
  $("#autoscale").addEventListener("change", (e) => { state.autoScale = e.target.checked; refreshGrid(); });
  $("#basemap").addEventListener("change", (e) => {
    for (const l of Object.values(L_.bases)) map.removeLayer(l);
    L_.bases[e.target.value].addTo(map).bringToBack();
  });
  renderVarList(); renderOverlayList(); renderBasemaps(); renderEventList();
}

function renderVarList() {
  const item = (v) => `
    <button type="button" class="var-item ${v === state.var ? "active" : ""}" data-var="${v}">
      <span class="sw" style="background:${cssGradient(ctx.varMeta(v).palette)}"></span>
      <b>${t(`var_${v}`)}</b><small>${t(`desc_${v}`)}</small>
    </button>`;
  const sar = ctx.meta.sar?.available
    ? `<div class="var-group">📡 ${t("sar_group")}</div>${VARS_SAR.map(item).join("")}` : "";
  $("#var-list").innerHTML = VARS.map(item).join("") + sar;
  $$("#var-list .var-item").forEach((b) => b.addEventListener("click", () => {
    state.var = b.dataset.var; renderVarList(); refreshGrid();
  }));
}

function renderOverlayList() {
  const disponibles = OVERLAYS.filter((k) => k !== "slicks" || ctx.meta.sar?.slicks?.available);
  $("#overlay-list").innerHTML = disponibles.map((k) => `
    <label class="${k === "slicks" ? "ov-slicks" : ""}"><input type="checkbox" data-ov="${k}" ${state.overlays[k] ? "checked" : ""}> ${t(`ov_${k}`)}</label>
    ${k === "slicks" ? `<small class="hint ov-note">${t("slk_ov_hint", { s: ctx.meta.sar.slicks.scenes, n: ctx.meta.sar.slicks.detections })}</small>` : ""}`).join("");
  $$("#overlay-list input").forEach((i) => i.addEventListener("change", () => {
    const k = i.dataset.ov; state.overlays[k] = i.checked;
    if (k === "sar") ctx.sarUI.refrescarCapa();
    else if (k === "slicks") ctx.sarUI.refrescarManchas();
    else if (["outline", "events", "places", "obis"].includes(k)) {
      if (i.checked) { L_[k].addTo(map); if (k === "obis") { L_.obis._year = null; refreshObis(); } } else map.removeLayer(L_[k]);
    } else refreshGibs();
    renderLegend();
  }));
}

function renderBasemaps() {
  const cur = $("#basemap").value || "bluemarble";
  $("#basemap").innerHTML = ["bluemarble", "osm", "topo"].map((k) => `<option value="${k}" ${k === cur ? "selected" : ""}>${t(`base_${k}`)}</option>`).join("");
}

/** Opciones de los selectores de categoría y años (se regeneran al cambiar de idioma). */
function renderEventFilterOptions() {
  const cats = [...new Set(ctx.events.map((e) => e.category))].sort((a, b) => t(`cat_${a}`).localeCompare(t(`cat_${b}`)));
  $("#ev-cat").innerHTML = `<option value="">${t("ev_category_all")}</option>` +
    cats.map((c) => `<option value="${c}" ${c === state.evf.cat ? "selected" : ""}>${t(`cat_${c}`)}</option>`).join("");
  const anios = [...new Set(state.months.map((m) => +m.slice(0, 4)))];
  const opts = (sel) => anios.map((y) => `<option value="${y}" ${y === sel ? "selected" : ""}>${y}</option>`).join("");
  $("#ev-from").innerHTML = opts(state.evf.from);
  $("#ev-to").innerHTML = opts(state.evf.to);
}

/** Aplica los filtros de eventos a la lista, al mapa y a las marcas de la línea de tiempo. */
function applyEventFilters() {
  renderEventList();
  updateEventStyles();
  renderTicks();
}

function renderEventList() {
  const m = ctx.month();
  const lista = ctx.events.filter(eventMatches);
  $("#ev-count").textContent = t("ev_count", { n: lista.length });
  $("#ev-list").innerHTML = lista.map((ev) => `
    <li class="ev-item ${isActive(ev, m) ? "is-active" : ""}" data-id="${ev.id}">
      <span class="ev-dot ${ev.type}"></span>
      <div><b>${tx(ev.name)}</b><small>${fmtDate(ev.start)} · ${t(`cat_${ev.category}`)}</small></div>
    </li>`).join("");
  $$("#ev-list .ev-item").forEach((li) => li.addEventListener("click", () => goToEvent(li.dataset.id, { analyze: true })));
  const activos = ctx.events.filter((e) => isActive(e, m) && eventMatches(e));
  $("#ev-active").innerHTML = activos.length
    ? activos.map((e) => `<a href="#" data-id="${e.id}" class="chip ${e.type}">${tx(e.name)}</a>`).join(" ")
    : t("none");
  $$("#ev-active a").forEach((a) => a.addEventListener("click", (e) => { e.preventDefault(); goToEvent(a.dataset.id, { analyze: true }); }));
}

function goToEvent(id, { analyze = true } = {}) {
  const ev = ctx.events.find((e) => e.id === id);
  if (!ev) return;
  const idx = state.months.indexOf(ev.start.slice(0, 7));
  if (idx >= 0) setMonth(idx);
  map.flyTo([ev.lat, ev.lon], 6, { duration: 0.8 });
  evLayers.get(id)?.dot.openPopup();
  if (analyze) panels.openEvent(ev);
}
ctx.goToEvent = goToEvent;

function renderManifest() {
  const m = ctx.meta.manifest || {};
  if (m.generado_utc) $("#manifest-info").textContent = `Dataset: ${m.meses?.join(" – ")} · ${m.generado_utc}`;
}

/* ------------------------------------------------------------------ línea de tiempo */
function initTimeline() {
  const n = state.months.length;
  const sl = $("#tl-slider");
  sl.max = n - 1;
  sl.addEventListener("input", () => setMonth(+sl.value));
  $("#tl-back").addEventListener("click", () => setMonth(Math.max(0, state.mi - 1)));
  $("#tl-fwd").addEventListener("click", () => setMonth(Math.min(n - 1, state.mi + 1)));
  $("#tl-play").addEventListener("click", togglePlay);
  $("#tl-speed").addEventListener("change", () => { if (state.playing) { togglePlay(); togglePlay(); } });
  document.addEventListener("keydown", (e) => {
    if (["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement?.tagName)) return;
    if (e.key === "ArrowRight") setMonth(Math.min(n - 1, state.mi + 1));
    if (e.key === "ArrowLeft") setMonth(Math.max(0, state.mi - 1));
    if (e.key === " ") { e.preventDefault(); togglePlay(); }
  });
  const pct = (i) => `${((i / (n - 1)) * 100).toFixed(3)}%`;
  $("#tl-years").innerHTML = state.months.map((m, i) => (m.endsWith("-01") && +m.slice(0, 4) % 2 === 1 ? `<span style="left:${pct(i)}">${m.slice(0, 4)}</span>` : "")).join("");
  renderTicks();
}

function renderTicks() {
  const n = state.months.length;
  $("#tl-ticks").innerHTML = ctx.events.filter(eventMatches).map((ev) => {
    const i = state.months.indexOf(ev.start.slice(0, 7));
    if (i < 0) return "";
    return `<button type="button" class="tl-tick ${ev.type}" style="left:${((i / (n - 1)) * 100).toFixed(3)}%" data-id="${ev.id}" title="${tx(ev.name)} · ${fmtDate(ev.start)}"></button>`;
  }).join("");
  $$("#tl-ticks .tl-tick").forEach((b) => b.addEventListener("click", () => goToEvent(b.dataset.id, { analyze: true })));
}

function togglePlay() {
  state.playing = !state.playing;
  $("#tl-play").textContent = state.playing ? "❚❚" : "▶";
  $("#tl-play").title = t(state.playing ? "pause" : "play");
  clearInterval(state.timer);
  if (state.playing) {
    state.timer = setInterval(() => {
      if (state.mi >= state.months.length - 1) { togglePlay(); return; }
      setMonth(state.mi + 1);
    }, +$("#tl-speed").value);
  }
}

const refreshGridDebounced = debounce(refreshGrid, 60);
const refreshSarDebounced = debounce(() => ctx.sarUI.refrescarCapa(), 500);

function setMonth(i, { force = false } = {}) {
  const prevYear = ctx.month()?.slice(0, 4);
  state.mi = i;
  $("#tl-slider").value = i;
  $("#tl-label").textContent = fmtMonth(ctx.month());
  updateEventStyles();
  renderEventList();
  if (state.evf.onlyActive) renderTicks();
  if (state.var !== "depth" || force) refreshGridDebounced(); else renderLegend();
  refreshGibs();
  if (force || ctx.month().slice(0, 4) !== prevYear) refreshObis();
  if (state.overlays.sar && !state.playing) refreshSarDebounced();   // búsqueda en ASF: no en cada paso de la animación
  panels?.onMonthChange();
}
ctx.setMonth = setMonth;
ctx.setMonthByName = (m) => { const i = state.months.indexOf(m); if (i >= 0) setMonth(i); };

/* ------------------------------------------------------------------ idioma */
function markLang() {
  $$(".lang-switch button").forEach((b) => b.classList.toggle("active", b.dataset.lang === getLang()));
}

function rerenderAll() {
  renderVarList(); renderOverlayList(); renderBasemaps(); renderEventFilterOptions(); renderEventList(); renderTicks(); renderLegend();
  $("#tl-label").textContent = fmtMonth(ctx.month());
  $("#tl-play").title = t(state.playing ? "pause" : "play");
  readout(null);
  panels?.rerender();
  const abierto = map._popup && map._popup.isOpen() ? map._popup._source : null;   // re-traduce el globo abierto
  if (abierto) { map.closePopup(); abierto.openPopup(); }
}
