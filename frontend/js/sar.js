/**
 * @module sar
 * Radar de apertura sintética (SAR) en la interfaz.
 *  - Capa «Escenas de radar del mes»: huellas de las escenas Sentinel-1, ALOS PALSAR, UAVSAR y NISAR que cubren el
 *    golfo en el mes de la línea de tiempo (búsqueda en vivo en NASA ASF, sin cuenta). Clic → vista previa, enlace de
 *    descarga en ASF Vertex y «Ver sobre el mapa» (la imagen de radar se superpone en su huella, posición aproximada).
 *  - Galería de escenas de un área o de un evento (mismas tarjetas).
 *  - Panel SAR de un evento: antes / después (viento, superficie amortiguada, objetos brillantes) con Sentinel-1 OCN
 *    procesado por scripts/build_sar.py y su mapa de viento del radar.
 *  - Capa «Detector de manchas · NISAR»: zonas donde una película viscosa (petróleo, emulsión, película biológica)
 *    amortigua las ondas cortas y el eco de banda L cae (scripts/build_slicks.py). Puntos por zona coloreados por
 *    confianza, huellas de las escenas e imagen de la escena con las zonas marcadas.
 */
import { t, fmtDate, fmtNum } from "./i18n.js";
import { api, selQuery } from "./api.js";

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const COLOR = { "Sentinel-1": "#35c2d6", "ALOS PALSAR": "#f0b44c", UAVSAR: "#ff5f8f", NISAR: "#9b8cff" };
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

/** 'POLYGON((x y, …))' → [[lat, lon], …] */
export function wktLatLngs(wkt) {
  const m = /\(\(([^)]+)\)\)/.exec(wkt || "");
  if (!m) return [];
  return m[1].split(",").map((p) => p.trim().split(/\s+/).map(Number)).filter((p) => p.length >= 2 && p.every(Number.isFinite)).map(([x, y]) => [y, x]);
}

const vistaUrl = (u, w = 360, alpha = false) => `/api/sar/browse?u=${encodeURIComponent(u)}&w=${w}${alpha ? "&alpha=true" : ""}`;

/** Tarjeta HTML de una escena (galerías y ventana emergente del mapa). */
export function sceneCard(sc, mision) {
  const fecha = sc.start ? fmtDate(sc.start) : "—";
  const img = sc.browse
    ? `<img loading="lazy" src="${vistaUrl(sc.browse)}" alt="${esc(mision)} ${esc(fecha)}">`
    : `<div class="sar-noimg">${t("sar_no_preview")}</div>`;
  return `<figure class="sar-card" data-id="${esc(sc.id)}">
    ${img}
    <figcaption><span><b style="color:${COLOR[mision] || "inherit"}">${esc(mision)}</b> · ${esc(fecha)}</span>
      <small>${esc([sc.beam, sc.direction, sc.polarization].filter(Boolean).join(" · "))}</small>
      <span class="sar-actions">${sc.browse ? `<button type="button" class="btn ghost sm" data-sar-ver="${esc(sc.id)}">${t("sar_on_map")}</button>` : ""}
        <a class="btn ghost sm" href="${esc(sc.vertex)}" target="_blank" rel="noopener">ASF Vertex ↗</a></span>
    </figcaption></figure>`;
}

export function initSar(ctx) {
  const map = ctx.map;
  const capa = L.layerGroup();
  let imagen = null;         // imagen de radar superpuesta
  let mesCapa = null;
  const porId = new Map();   // escenas mostradas → para «Ver sobre el mapa»

  /** Superpone una vista previa (o el mapa de viento de un evento) en sus límites. */
  function mostrarImagen(url, bounds, etiqueta) {
    quitarImagen();
    imagen = L.imageOverlay(url, bounds, { opacity: 0.9, zIndex: 6, interactive: false }).addTo(map);
    map.fitBounds(bounds, { padding: [30, 30], maxZoom: 8 });
    ctx.toast(`${etiqueta} · ${t("sar_overlay_hint")}`, 6000, "info");
    $("#sar-clear")?.classList.remove("hidden");
  }

  function quitarImagen() {
    if (imagen) map.removeLayer(imagen);
    imagen = null;
    $("#sar-clear")?.classList.add("hidden");
  }

  function verEscena(id) {
    const x = porId.get(id);
    if (!x || !x.sc.browse) return;
    const ll = wktLatLngs(x.sc.wkt);
    if (!ll.length) return;
    ctx.closeModal?.();
    map.closePopup();
    mostrarImagen(vistaUrl(x.sc.browse, 1400, true), L.latLngBounds(ll), `${x.mision} · ${fmtDate(x.sc.start)}`);
  }

  /** Conecta los botones «Ver sobre el mapa» de un contenedor. */
  function enlazar(raiz) {
    $$("[data-sar-ver]", raiz).forEach((b) => b.addEventListener("click", () => verEscena(b.dataset.sarVer)));
  }

  function registrar(res) {
    for (const [mision, m] of Object.entries(res.missions || {})) for (const sc of m.scenes || []) porId.set(sc.id, { sc, mision });
  }

  /** Galería de escenas del área `sel` (selección del mapa) desde `month` durante `months` meses. */
  async function galeria(contenedor, sel, month, months = 1) {
    contenedor.innerHTML = `<p><span class="spinner"></span> ${t("sar_searching")}</p>`;
    const res = await api.sarScenes(sel, month, months);
    registrar(res);
    const bloques = Object.entries(res.missions).map(([mision, m]) => {
      if (m.error) return `<p class="hint">${mision}: ${t("sar_search_error")}</p>`;
      if (!m.total) return "";
      return `<div class="section-title">${mision} · ${t("sar_n_scenes", { n: m.total })}</div>
        <div class="sar-grid">${m.scenes.map((sc) => sceneCard(sc, mision)).join("")}</div>`;
    }).join("");
    contenedor.innerHTML = bloques || `<p class="note">${t("sar_none", { a: res.from, b: res.to })}</p>`;
    contenedor.insertAdjacentHTML("beforeend", `<p class="hint">${t("sar_gallery_note")}</p>`);
    enlazar(contenedor);
  }

  /** Capa del mapa: huellas de las escenas del mes en todo el golfo. */
  async function refrescarCapa() {
    if (!ctx.state.overlays.sar) { map.removeLayer(capa); return; }
    if (!map.hasLayer(capa)) capa.addTo(map);
    const m = ctx.month();
    if (m === mesCapa) return;
    mesCapa = m;
    const b = ctx.meta.bbox;
    let res;
    try {
      res = await api.sarScenes({ type: "bbox", bbox: [b.west, b.south, b.east, b.north] }, m, 1);
    } catch (e) { ctx.toast(`SAR: ${e.message}`); return; }
    if (m !== ctx.month() || !ctx.state.overlays.sar) return;
    capa.clearLayers();
    registrar(res);
    let n = 0;
    for (const [mision, mm] of Object.entries(res.missions)) {
      for (const sc of mm.scenes || []) {
        const ll = wktLatLngs(sc.wkt);
        if (!ll.length) continue;
        n++;
        L.polygon(ll, { color: COLOR[mision] || "#fff", weight: 1.2, fillOpacity: 0.04, dashArray: "3 3", bubblingMouseEvents: false })
          .bindPopup(() => { const div = document.createElement("div"); div.className = "sar-pop"; div.innerHTML = sceneCard(sc, mision); enlazar(div); return div; }, { maxWidth: 300 })
          .bindTooltip(`${mision} · ${fmtDate(sc.start)}`, { sticky: true })
          .addTo(capa);
      }
    }
    if (!n) ctx.toast(t("sar_none_month"), 3500, "info");
  }

  /* ---------------------------------------------- detector de manchas NISAR (banda L) */
  const capaManchas = L.layerGroup();
  const CONF = { high: "#e62828", medium: "#ff961e", calm: "#5a96ff" };
  let manchas = null;

  function verEscenaNisar(e) {
    map.closePopup();
    mostrarImagen(e.image, e.bounds, `NISAR · ${fmtDate(e.start)}`);
  }

  function popupDeteccion(x, e) {
    const div = document.createElement("div");
    div.className = "slk-pop";
    div.innerHTML = `<b style="color:${CONF[x.confidence]}">● ${t(`slk_conf_${x.confidence}`)}</b>
      <div class="muted">NISAR · ${fmtDate(e.start)} · ${esc(e.pol || "")}</div>
      <table class="data mini"><tr><td>${t("slk_area")}</td><td>${fmtNum(x.area_km2, 1)} km²</td></tr>
        <tr><td>${t("slk_size")}</td><td>${fmtNum(x.length_km, 1)} × ${fmtNum(x.width_km, 1)} km</td></tr>
        <tr><td>${t("slk_dr")}</td><td>${fmtNum(x.dr_db, 1)} dB</td></tr>
        <tr><td>${t("slk_dr_hv")}</td><td>${fmtNum(x.dr_hv_db, 1)} dB</td></tr>
        <tr><td>${t("slk_bg")}</td><td>${fmtNum(x.background_db, 1)} dB</td></tr>
        <tr><td>${t("lat")}, ${t("lon")}</td><td>${fmtNum(x.lat, 3)}, ${fmtNum(x.lon, 3)}</td></tr></table>
      <p class="hint">${t(`slk_hint_${x.confidence}`)}</p>
      ${e.variable_weather ? `<p class="hint">⛈ ${t("slk_variable")}</p>` : ""}
      <span class="sar-actions"><button type="button" class="btn ghost sm" data-ver>${t("slk_view_scene")}</button>
        <a class="btn ghost sm" href="${esc(e.vertex)}" target="_blank" rel="noopener">ASF Vertex ↗</a></span>`;
    div.querySelector("[data-ver]").addEventListener("click", () => verEscenaNisar(e));
    return div;
  }

  function popupEscena(e) {
    const div = document.createElement("div");
    div.className = "slk-pop";
    const c = e.counts || {};
    div.innerHTML = `<b>NISAR · ${fmtDate(e.start)}</b><div class="muted">${t("slk_scene")} · ${esc(e.pol || "")} · ${esc(e.direction || "")}</div>
      <p>${t("slk_sea")}: ${fmtNum(e.sea_km2, 0)} km² · ${t("slk_bg")}: ${fmtNum(e.background_db, 1)} dB<br>
      ${e.detections.length ? `<span style="color:${CONF.high}">● ${c.high || 0}</span> · <span style="color:${CONF.medium}">● ${c.medium || 0}</span> ·
        <span style="color:${CONF.calm}">● ${c.calm || 0}</span> ${t("slk_zones")}` : t("slk_none_scene")}</p>
      ${e.variable_weather ? `<p class="hint">⛈ ${t("slk_variable")}</p>` : ""}
      <span class="sar-actions"><button type="button" class="btn ghost sm" data-ver>${t("slk_view_scene")}</button>
        <a class="btn ghost sm" href="${esc(e.vertex)}" target="_blank" rel="noopener">ASF Vertex ↗</a></span>`;
    div.querySelector("[data-ver]").addEventListener("click", () => verEscenaNisar(e));
    return div;
  }

  /** Capa del detector: huellas de las escenas NISAR procesadas y zonas amortiguadas (independiente del mes). */
  async function refrescarManchas() {
    if (!ctx.state.overlays.slicks) { map.removeLayer(capaManchas); return; }
    if (!map.hasLayer(capaManchas)) capaManchas.addTo(map);
    if (manchas) return;
    try { manchas = await api.sarSlicks(); } catch (e) { ctx.toast(`NISAR: ${e.message}`); return; }
    const huellas = L.layerGroup().addTo(capaManchas);
    let n = 0;
    for (const e of manchas.scenes) {
      const ll = wktLatLngs(e.wkt);
      if (ll.length) {
        L.polygon(ll, { color: "#9b8cff", weight: 1, dashArray: "2 4", fillOpacity: 0.02, bubblingMouseEvents: false })
          .bindPopup(() => popupEscena(e), { maxWidth: 300 }).addTo(huellas);
      }
      for (const x of e.detections) {
        // En el mapa: altas y medias de escenas sin tiempo variable (las demás se ven en la imagen de la escena)
        if (x.confidence === "calm" || (x.confidence === "medium" && e.variable_weather)) continue;
        n++;
        const alta = x.confidence === "high";
        L.circleMarker([x.lat, x.lon], { radius: alta ? Math.min(16, 6 + Math.sqrt(x.area_km2) * 1.6) : Math.min(9, 3 + Math.sqrt(x.area_km2)),
                                          color: "#fff", weight: alta ? 1.5 : 0.6, fillColor: CONF[x.confidence],
                                          fillOpacity: alta ? 0.95 : 0.6, bubblingMouseEvents: false })
          .bindTooltip(`${t(`slk_conf_${x.confidence}`)} · ${fmtNum(x.area_km2, 1)} km² · ${fmtDate(e.start)}`)
          .bindPopup(() => popupDeteccion(x, e), { maxWidth: 300 }).addTo(capaManchas);
      }
    }
    ctx.toast(t("slk_loaded", { s: manchas.scenes.length, n }), 6000, "info");
  }

  /** Sección SAR de la ventana de un evento. */
  async function panelEvento(contenedor, ev) {
    const conAnalisis = (ctx.meta.sar?.events || []).includes(ev.id);
    let html = `<div class="section-title">📡 ${t("sar_title")}</div>`;
    if (conAnalisis) {
      const r = await api.sarEvent(ev.id);
      const s = r.summary;
      const fila = (k, nombre, u, d) => {
        const a = s[k]?.before, b = s[k]?.after;
        const delta = a !== null && b !== null && a !== undefined && b !== undefined ? b - a : null;
        return `<tr><td>${nombre}</td><td>${a == null ? "—" : `${fmtNum(a, d)} ${u}`}</td><td>${b == null ? "—" : `${fmtNum(b, d)} ${u}`}</td>
          <td>${delta === null ? "—" : `${delta > 0 ? "+" : ""}${fmtNum(delta, d)} ${u}`}</td></tr>`;
      };
      const nAntes = r.scenes.filter((x) => x.period === "before").length, nDesp = r.scenes.length - nAntes;
      html += `<p class="hint">${t("sar_event_intro", { a: nAntes, b: nDesp, r: ev.radius_km })}</p>
        <table class="data"><tr><th></th><th>${t("sar_before")}</th><th>${t("sar_after")}</th><th>${t("change")}</th></tr>
        ${fila("wind_mean", t("sar_wind_mean"), "m/s", 1)}${fila("wind_p95", t("sar_wind_p95"), "m/s", 1)}
        ${fila("damped_pct", t("var_sar_damped"), "%", 2)}${fila("bright_pct", t("var_sar_bright"), "%", 2)}</table>`;
      if (r.image) {
        html += `<div class="pp-actions"><button type="button" class="btn sm" id="sar-ev-img">🛰 ${t("sar_wind_map")} · ${fmtDate(r.image.start)}</button></div>`;
      }
    } else {
      html += `<p class="hint">${t("sar_event_live")}</p>`;
    }
    html += `<div id="sar-ev-gal"></div>`;
    contenedor.innerHTML = html;
    if (conAnalisis) {
      const r = await api.sarEvent(ev.id);
      $("#sar-ev-img", contenedor)?.addEventListener("click", () => {
        ctx.closeModal?.();
        mostrarImagen(r.image.url, r.image.bounds, `${t("sar_wind_map")} (0–35 m/s)`);
      });
    }
    const dLat = ev.radius_km / 111, dLon = ev.radius_km / (111 * Math.cos((ev.lat * Math.PI) / 180));
    const sel = { type: "bbox", bbox: [ev.lon - dLon, ev.lat - dLat, ev.lon + dLon, ev.lat + dLat] };
    await galeria($("#sar-ev-gal", contenedor), sel, ev.start.slice(0, 7), 2);
  }

  // Botón flotante para quitar la imagen de radar del mapa
  const QuitarCtl = L.Control.extend({
    options: { position: "topleft" },
    onAdd() {
      const div = L.DomUtil.create("div", "leaflet-bar");
      div.innerHTML = `<a href="#" id="sar-clear" class="hidden" title="${t("sar_clear")}">📡✕</a>`;
      L.DomEvent.disableClickPropagation(div);
      div.addEventListener("click", (e) => { e.preventDefault(); quitarImagen(); });
      return div;
    },
  });
  map.addControl(new QuitarCtl());

  return { refrescarCapa, refrescarManchas, galeria, panelEvento, quitarImagen, selQuery, CONF };
}
