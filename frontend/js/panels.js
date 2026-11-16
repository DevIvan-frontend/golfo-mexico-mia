/**
 * @module panels
 * Ventanas de análisis:
 *   - Ventana del área (#popup): flotante, semitransparente, MOVIBLE (arrastrando su barra superior) y minimizable.
 *     Resume la celda o el área seleccionada para el mes del mapa: TSM, clorofila, profundidad, vida marina y eventos.
 *   - Ventana de detalle (#modal): al hacer clic en una característica muestra su tabla de cambios, su serie temporal
 *     y/o su gráfico 3D, con filtro de años y botón de descarga a Excel.
 *   - Análisis de evento (#modal): antes/después de un evento con gráfico ±24 meses y descarga a Excel.
 * Todo se re-dibuja cuando cambia el mes de la línea de tiempo (onMonthChange) o el idioma (rerender).
 */
import { t, tx, fmtMonth, fmtDate, fmtNum, fmtSel } from "./i18n.js";
import { api } from "./api.js";
import * as F from "./figures.js";
import { exportAreaReport, exportEventReport } from "./exporter.js";

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const debounce = (fn, ms) => { let h; return (...a) => { clearTimeout(h); h = setTimeout(() => fn(...a), ms); }; };
const clamp = (x, a, b) => Math.min(Math.max(x, a), b);
const ARROW = { up: "▲", down: "▼", flat: "●", nd: "·" };
const PLOT_CFG = { responsive: true, displaylogo: false, modeBarButtonsToRemove: ["lasso2d", "select2d"] };

/** Insignia de dirección (sube / baja / estable / sin dato). */
export function badge(dir, txt) {
  const d = dir || "nd";
  return `<span class="badge ${d}">${ARROW[d]} ${txt ?? t(d)}</span>`;
}
/** Número con signo explícito (+0,4 / −1,2). */
const signed = (x, d = 1) => (x === null || x === undefined ? "—" : `${x > 0 ? "+" : ""}${fmtNum(x, d)}`);

export function initPanels(ctx) {
  const pop = $("#popup");
  const modal = $("#modal");
  const anios = ctx.meta.obis_years;                   // 2003…2024
  const rango = { from: anios[0], to: anios.at(-1) };  // filtro de años compartido por el detalle y el Excel
  let cur = null;      // ventana del área: { sel, summary, fauna, error, collapsed }
  let det = null;      // ventana de detalle: { kind:'feature'|'event', feature?, ev?, tab, threeMode, threeColor, exag }
  let tok = 0;         // descarta respuestas de peticiones antiguas

  $("#modal-close").addEventListener("click", closeModal);
  modal.addEventListener("click", (e) => { if (e.target === modal) closeModal(); });
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    if (!modal.classList.contains("hidden")) closeModal(); else close();
  });
  habilitarArrastre();

  /* ============================================================ ventana del área */
  function open(sel) {
    cur = { sel, summary: null, fauna: null, sar: null, error: null, collapsed: false };
    pop.classList.remove("hidden", "collapsed");
    renderPopup();
    load();
  }

  function close() {
    pop.classList.add("hidden");
    cur = null;
    ctx.clearSelection();
  }

  /** Pide el resumen del área (y la vida marina en paralelo, que es más lenta) para el mes actual. */
  async function load() {
    if (!cur) return;
    const my = ++tok;
    const month = ctx.month();
    const year = +month.slice(0, 4);
    try {
      const s = await api.summary(cur.sel, month);
      if (my !== tok || !cur) return;
      cur.summary = s; cur.error = null;
    } catch (e) {
      if (my !== tok || !cur) return;
      cur.error = e.message;
    }
    renderPopup();
    if (ctx.meta.sar?.available && !cur.sar) {          // el compuesto SAR no depende del mes: una vez por selección
      api.sarArea(cur.sel).then((r) => { if (cur && my === tok) { cur.sar = r; renderPopup(); } })
        .catch(() => { if (cur && my === tok) { cur.sar = { error: true }; renderPopup(); } });
    }
    if (!cur.fauna || cur.fauna.year !== year) {
      api.fauna(cur.sel, year).then((f) => { if (cur && my === tok) { cur.fauna = f; renderPopup(); } })
        .catch(() => { if (cur && my === tok) { cur.fauna = { available: false }; renderPopup(); } });
    }
  }

  function title(sel) {
    if (sel.kind === "cell") return t("cell_title");
    if (sel.kind === "event") return tx(sel.ev.name);
    return `${t("area_title")} (${t(sel.type === "bbox" ? "rectangle" : "polygon")})`;
  }

  function renderPopup() {
    if (!cur) return;
    const s = cur.summary, sel = cur.sel;
    const head = `<header class="pp-head" title="${t("drag_hint")}">
        <div class="pp-title"><h2>${title(sel)}</h2><p>${fmtSel(sel)} · ${fmtMonth(ctx.month())}</p></div>
        <div class="pp-btns">
          <button type="button" class="icon-btn sm" data-nb title="${t("nb_open_area")}">📓</button>
          <button type="button" class="icon-btn sm" data-export title="${t("export_excel")}">⤓</button>
          <button type="button" class="icon-btn sm" data-min title="${t(cur.collapsed ? "restore" : "minimize")}">${cur.collapsed ? "▢" : "–"}</button>
          <button type="button" class="icon-btn sm" data-close title="${t("close")}">✕</button>
        </div></header>`;
    let body;
    if (cur.error) body = `<p class="pp-hint">${t("api_error")}: ${cur.error}</p>`;
    else if (!s) body = `<p class="pp-hint"><span class="spinner"></span> ${t("loading")}</p>`;
    else body = renderFeatures(s);
    pop.innerHTML = head + `<div class="pp-body">${body}</div>`;
    pop.classList.toggle("collapsed", cur.collapsed);
    $("[data-close]", pop).addEventListener("click", close);
    $("[data-min]", pop).addEventListener("click", () => { cur.collapsed = !cur.collapsed; renderPopup(); });
    $("[data-export]", pop).addEventListener("click", (e) => exportar(e.currentTarget, () => exportAreaReport(ctx, cur.sel, rango)));
    $("[data-nb]", pop).addEventListener("click", () => ctx.notebook.openArea(cur.sel, title(cur.sel)));
    $$("[data-feature]", pop).forEach((b) => b.addEventListener("click", () => openDetail(b.dataset.feature)));
    $$("[data-ev]", pop).forEach((b) => b.addEventListener("click", () => {
      const ev = ctx.events.find((e) => e.id === b.dataset.ev); if (ev) openEvent(ev);
    }));
  }

  /** Filas compactas de la ventana del área: una por característica, cada una abre su detalle. */
  function renderFeatures(s) {
    const v = s.variables, rows = [];
    if (!v.sst && !v.chl) rows.push(`<p class="pp-hint">${t("no_data")} — ${t("land")}</p>`);
    for (const k of ["sst", "chl"]) {
      const x = v[k];
      if (!x) continue;
      const isChl = k === "chl";
      const val = x.value === null ? t("no_data") : `${fmtNum(x.value, isChl ? 2 : 1)} ${F.UNITS[k]}`;
      const anom = x.anom === null ? t("nd") : `${signed(x.anom, isChl ? 0 : 1)}${isChl ? "%" : "°"}`;
      const sub = x.trend_per_decade === null ? "" :
        `${t("trend")}: ${signed(x.trend_per_decade, isChl ? 1 : 2)}${isChl ? " %" : " °C"}/${t("per_decade").replace(/^(por |per )/, "")}${x.trend_p < 0.05 ? " *" : ""}`;
      rows.push(`<button type="button" class="feat" data-feature="${k}" title="${t("click_detail")}">
        <span class="ic">${isChl ? "🌿" : "🌡️"}</span>
        <span class="tx"><span class="nm">${t(k)}</span><span class="val">${val}</span><span class="sub">${sub}</span></span>
        ${badge(x.direction, anom)}</button>`);
    }
    if (v.depth) {
      rows.push(`<button type="button" class="feat" data-feature="depth"><span class="ic">🌊</span>
        <span class="tx"><span class="nm">${t("depth")}</span><span class="val">${fmtNum(v.depth.mean, 0)} m</span>
        <span class="sub">${fmtNum(v.depth.min, 0)}–${fmtNum(v.depth.max, 0)} m · ${t("shelf")}: ${fmtNum(v.depth.shelf_pct, 0)} %</span></span>
        <span class="badge flat">3D</span></button>`);
    }
    const f = cur.fauna;
    const faunaVal = !f ? `<span class="spinner"></span>` : f.available === false ? t("fauna_unavailable")
      : `${fmtNum(f.records ?? 0, 0)} ${t("records")} · ${fmtNum(f.species ?? 0, 0)} ${t("species")}`;
    const faunaSub = f && f.available ? `${fmtNum(f.redlist_total ?? 0, 0)} ${t("redlist")}` : "";
    rows.push(`<button type="button" class="feat" data-feature="fauna"><span class="ic">🐢</span>
      <span class="tx"><span class="nm">${t("fauna")}</span><span class="val small">${faunaVal}</span><span class="sub">${faunaSub}</span></span>
      <span class="badge flat">OBIS</span></button>`);
    // Radar SAR: valores del año (productos Sentinel-1) o, si no se generaron, solo galería de escenas
    const sr = cur.sar, anioSar = +ctx.month().slice(0, 4);
    const filaAnio = sr && sr.years ? sr.years.find((r) => r.year === anioSar) : null;
    const base = filaAnio && filaAnio.n ? filaAnio : sr?.all;
    const sarVal = !ctx.meta.sar?.available ? t("sar_images_only")
      : !sr ? `<span class="spinner"></span>` : sr.error ? t("no_data")
      : base && base.n ? `${t("sar_damped_short")} ${fmtNum(base.damped_pct, 1)} % · ${t("sar_bright_short")} ${fmtNum(base.bright_pct, 1)} %` : t("no_data");
    const sarSub = sr && base && base.n ? `${t("sar_wind_short")} ${fmtNum(base.wind, 1)} m/s · ${base === filaAnio ? anioSar : "2017–2024"}` : t("sar_sub");
    rows.push(`<button type="button" class="feat" data-feature="sar"><span class="ic">📡</span>
      <span class="tx"><span class="nm">${t("sar_title")}</span><span class="val small">${sarVal}</span><span class="sub">${sarSub}</span></span>
      <span class="badge flat">SAR</span></button>`);
    const evs = s.events || [];
    if (evs.length) {
      const chip = (e) => {
        const n = e.months_from_selected;
        const when = n === 0 ? t("same_month") : n < 0 ? t("months_ago", { n: -n }) : t("months_ahead", { n });
        return `<button type="button" class="chip ${e.type}" data-ev="${e.id}" title="${fmtDate(e.start)} · ${when}">${tx(e.name)}</button>`;
      };
      rows.push(`<div class="pp-events"><div class="section-title">${t("events_rel")}</div><div class="chips">${evs.map(chip).join("")}</div></div>`);
    }
    rows.push(`<div class="pp-actions"><button type="button" class="btn sm" data-feature="relief">${t("open3d")}</button>
      <button type="button" class="btn ghost sm" data-feature="props">${t("compare_props")}</button></div>`);
    return rows.join("");
  }

  /** Arrastre de la ventana del área por su barra superior (ratón, lápiz o táctil), sin salir del mapa. */
  function habilitarArrastre() {
    let ini = null;
    pop.addEventListener("pointerdown", (e) => {
      const head = e.target.closest(".pp-head");
      if (!head || e.target.closest("button")) return;
      const caja = pop.getBoundingClientRect();
      const marco = pop.parentElement.getBoundingClientRect();
      ini = { x: e.clientX, y: e.clientY, left: caja.left - marco.left, top: caja.top - marco.top, marco, w: caja.width };
      head.setPointerCapture(e.pointerId);
      pop.classList.add("dragging");
      e.preventDefault();
    });
    pop.addEventListener("pointermove", (e) => {
      if (!ini) return;
      const alturaTimeline = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--tl-h")) || 50;
      const libre = ini.marco.height - alturaTimeline;          // la ventana nunca queda bajo la línea de tiempo
      const left = clamp(ini.left + e.clientX - ini.x, 0, ini.marco.width - ini.w);
      const top = clamp(ini.top + e.clientY - ini.y, 0, libre - 60);
      Object.assign(pop.style, { left: `${left}px`, top: `${top}px`, right: "auto", maxHeight: `${Math.max(120, libre - top - 10)}px` });
    });
    const fin = () => { ini = null; pop.classList.remove("dragging"); };
    pop.addEventListener("pointerup", fin);
    pop.addEventListener("pointercancel", fin);
  }

  /** Ejecuta una exportación mostrando el estado en el botón y avisos de error. */
  async function exportar(boton, tarea) {
    const original = boton.textContent;
    boton.disabled = true;
    boton.innerHTML = `<span class="spinner"></span>`;
    ctx.toast(t("exporting"), 2500, "info");
    try {
      await tarea();
      ctx.toast(t("export_done"), 2500, "ok");
    } catch (e) {
      ctx.toast(`${t("export_error")}: ${e.message}`);
    } finally {
      boton.disabled = false;
      boton.textContent = original;
    }
  }

  /* ============================================================ ventana de detalle */
  const TABS = {
    sst: ["table", "chart", "3d"], chl: ["table", "chart", "3d"], depth: ["table", "3d"],
    fauna: ["table", "chart"], relief: ["3d"], props: ["3d", "chart"],
    sar: ctx.meta.sar?.available ? ["table", "chart", "images"] : ["images"],
  };
  const TAB_LABEL = { table: "tab_table", chart: "tab_chart", "3d": "tab_3d", images: "tab_images" };

  function openDetail(feature) {
    if (!cur) return;
    det = { kind: "feature", feature, tab: TABS[feature][0], threeColor: ["sst", "chl"].includes(feature) ? feature : "sst",
            threeMode: feature === "props" ? "props" : "relief", exag: 0.35 };
    modal.classList.remove("hidden");
    renderModal();
  }

  function closeModal() {
    $$(".plot", modal).forEach((p) => window.Plotly && Plotly.purge(p));
    modal.classList.add("hidden");
    det = null;
  }

  /** Pestañas + barra de herramientas (filtro de años y descarga) del detalle. */
  function renderTabs(tabs, conFiltro) {
    const opciones = (sel) => anios.map((y) => `<option value="${y}" ${y === sel ? "selected" : ""}>${y}</option>`).join("");
    $("#modal-tabs").innerHTML = tabs.map((k) => `<button type="button" data-tab="${k}" class="${k === det.tab ? "active" : ""}">${t(TAB_LABEL[k])}</button>`).join("") +
      `<span class="spacer"></span>
       ${conFiltro ? `<label class="mini">${t("filter_years")} <select id="f-from" class="select small">${opciones(rango.from)}</select>
         – <select id="f-to" class="select small">${opciones(rango.to)}</select></label>` : ""}
       <button type="button" class="btn sm" id="modal-export">⤓ ${t("export_excel")}</button>`;
    $$("#modal-tabs [data-tab]").forEach((b) => b.addEventListener("click", () => { det.tab = b.dataset.tab; renderModal(); }));
    const cambiarRango = () => {
      let a = +$("#f-from").value, b = +$("#f-to").value;
      if (a > b) [a, b] = [b, a];
      rango.from = a; rango.to = b;
      renderModal();
    };
    $("#f-from")?.addEventListener("change", cambiarRango);
    $("#f-to")?.addEventListener("change", cambiarRango);
    $("#modal-export").addEventListener("click", (e) => exportar(e.currentTarget,
      () => (det.kind === "event" ? exportEventReport(ctx, det.ev) : exportAreaReport(ctx, cur.sel, rango))));
  }

  async function renderModal() {
    if (!det) return;
    const body = $("#modal-body");
    if (det.kind === "event") return renderEvent();
    const names = { sst: t("sst"), chl: t("chl"), depth: t("depth"), fauna: t("fauna"), relief: t("tab_3d"),
                    props: t("compare_props"), sar: t("sar_title") };
    $("#modal-title").textContent = `${names[det.feature]} · ${title(cur.sel)}`;
    $("#modal-sub").textContent = `${fmtSel(cur.sel)} · ${fmtMonth(ctx.month())}`;
    renderTabs(TABS[det.feature], det.tab !== "3d");
    body.innerHTML = `<p><span class="spinner"></span> ${t("loading")}</p>`;
    try {
      if (det.tab === "3d") return await render3D(body);
      if (det.feature === "sst" || det.feature === "chl") return await renderSeries(body, det.tab);
      if (det.feature === "depth") return await renderDepth(body);
      if (det.feature === "fauna") return await renderFauna(body, det.tab);
      if (det.feature === "props") return await renderProps(body);
      if (det.feature === "sar") return await renderSar(body, det.tab);
    } catch (e) {
      body.innerHTML = `<p>${t("api_error")}: ${e.message}</p>`;
    }
  }

  const enRango = (anio) => anio >= rango.from && anio <= rango.to;

  /** TSM o clorofila: indicadores, tabla anual y del mismo mes (filtradas por años) o serie temporal. */
  async function renderSeries(body, tab) {
    const v = det.feature, isChl = v === "chl", month = ctx.month();
    const ts = await api.timeseries(cur.sel, v, month);
    if (!det || det.feature !== v) return;
    const k = ts.months.indexOf(month);
    const unidad = isChl ? "%" : "°C";
    const kpis = `<div class="kpis">
      <div class="kpi"><small>${fmtMonth(month)}</small><b>${fmtNum(ts.values[k], 2)} ${F.UNITS[v]}</b></div>
      <div class="kpi"><small>${t("anomaly")}</small><b>${signed(ts.anom[k], isChl ? 0 : 2)} ${unidad}</b></div>
      <div class="kpi"><small>${t("trend_text")} (${t("per_decade")})</small><b>${signed(ts.trend_per_decade, 2)} ${unidad}</b>
        <small>${ts.trend_p === null ? "" : `p = ${fmtNum(ts.trend_p, 3)} · ${ts.trend_p < 0.05 ? t("significant") : t("not_significant")}`}</small></div>
      <div class="kpi"><small>${t("coverage")}</small><b>${fmtNum(ts.coverage_pct[k], 0)} %</b></div></div>`;
    if (tab === "table") {
      const fila = (etq, actual, r, val) => `<tr class="${actual ? "current" : ""}"><td>${etq}</td><td>${val === null ? "—" : fmtNum(val, isChl ? 3 : 2)}</td>
        <td>${r.delta === null ? "—" : `${signed(r.delta, isChl ? 1 : 2)} ${unidad}`}</td><td>${badge(r.direction)}</td>
        <td>${r.anom === null ? "—" : `${signed(r.anom, isChl ? 0 : 2)} ${unidad}`}</td></tr>`;
      const anual = ts.annual.filter((r) => enRango(r.year)).map((r) => fila(r.year, String(r.year) === month.slice(0, 4), r, r.mean)).join("");
      const mismo = ts.same_month.filter((r) => enRango(+r.month.slice(0, 4))).map((r) => fila(fmtMonth(r.month), r.month === month, r, r.value)).join("");
      const th = (c1) => `<tr><th>${c1}</th><th>${t("value")} (${F.UNITS[v]})</th><th>${t("change")}</th><th>${t("direction")}</th><th>${t("anomaly")}</th></tr>`;
      body.innerHTML = `${kpis}<div class="grid-2">
        <div><div class="section-title">${t("annual_title")}</div><div class="tbl-wrap"><table class="data">${th(t("year"))}${anual}</table></div></div>
        <div><div class="section-title">${t("same_month_title")}</div><div class="tbl-wrap"><table class="data">${th(t("month_col"))}${mismo}</table></div></div></div>`;
      return;
    }
    body.innerHTML = `${kpis}<div id="plot-series" class="plot"></div><p class="hint">${t("disclaimer")}</p>`;
    const fig = F.seriesFigure(ts, v, month, rango);
    Plotly.newPlot("plot-series", fig.data, fig.layout, PLOT_CFG);
  }

  /** Profundidad: indicadores y distribución por clases (no depende del tiempo). */
  async function renderDepth(body) {
    const d = await api.depth(cur.sel);
    const s = cur.summary?.variables?.depth;
    const filas = d.classes.map((c) => `<tr><td>${fmtNum(c.from, 0)} – ${fmtNum(c.to, 0)}</td><td>${c.pct === null ? "—" : `${fmtNum(c.pct, 1)} %`}</td>
      <td><div class="bar" style="width:${c.pct || 0}%"></div></td></tr>`).join("");
    body.innerHTML = `${s ? `<div class="kpis"><div class="kpi"><small>${t("mean")}</small><b>${fmtNum(s.mean, 0)} m</b></div>
      <div class="kpi"><small>${t("min")} / ${t("max")}</small><b>${fmtNum(s.min, 0)} / ${fmtNum(s.max, 0)} m</b></div>
      <div class="kpi"><small>${t("shelf")}</small><b>${fmtNum(s.shelf_pct, 0)} %</b></div></div>` : ""}
      <div class="section-title">${t("depth_classes")}</div>
      <table class="data"><tr><th>${t("range_m")}</th><th>${t("pct_area")}</th><th style="width:45%"></th></tr>${filas}</table>
      <p class="hint">${t("dyk_depth")}</p>`;
  }

  /** Vida marina (OBIS): registros por año con cambio, especies del año y Lista Roja; o gráfico de barras. */
  async function renderFauna(body, tab) {
    const year = +ctx.month().slice(0, 4);
    const [anio, todo] = await Promise.all([api.fauna(cur.sel, year), api.fauna(cur.sel, null)]);
    if (!anio.available || !todo.available) { body.innerHTML = `<p>${t("fauna_unavailable")}</p>`; return; }
    // Años sin registros = 0 (no se omiten), para que el cambio sea siempre frente al año anterior
    const porAnio = new Map(todo.by_year.map((r) => [r.year, r.records]));
    const serie = anios.filter(enRango).map((y) => ({ year: y, records: porAnio.get(y) ?? 0 }));
    if (tab === "chart") {
      body.innerHTML = `<div id="plot-fauna" class="plot"></div><p class="hint">${t("sampling_caveat")}</p>`;
      const fig = F.faunaFigure(serie, year);
      Plotly.newPlot("plot-fauna", fig.data, fig.layout, PLOT_CFG);
      return;
    }
    let prev = null;
    const filas = serie.map((r) => {
      const delta = prev ? (r.records / prev - 1) * 100 : null;
      const dir = prev === null ? "nd" : prev === 0 ? (r.records > 0 ? "up" : "flat") : delta > 5 ? "up" : delta < -5 ? "down" : "flat";
      prev = r.records;
      return `<tr class="${r.year === year ? "current" : ""}"><td>${r.year}</td><td>${fmtNum(r.records, 0)}</td><td>${delta === null ? "—" : `${signed(delta, 0)} %`}</td><td>${badge(dir)}</td></tr>`;
    }).join("");
    const top = anio.top.map((s) => `<tr><td><i>${s.scientificName}</i></td><td>${s.class || s.phylum || "—"}</td><td>${fmtNum(s.records, 0)}</td></tr>`).join("");
    const roja = todo.redlist.map((s) => `<tr><td><i>${s.scientificName}</i></td><td>${s.class || "—"}</td>
      <td><span class="iucn ${s.category}" title="${t(`iucn_${s.category}`)}">${s.category}</span> ${t(`iucn_${s.category}`)}</td></tr>`).join("");
    body.innerHTML = `<div class="kpis"><div class="kpi"><small>${t("records")} ${year}</small><b>${fmtNum(anio.records ?? 0, 0)}</b></div>
      <div class="kpi"><small>${t("species")} ${year}</small><b>${fmtNum(anio.species ?? 0, 0)}</b></div>
      <div class="kpi"><small>${t("redlist")}</small><b>${fmtNum(todo.redlist_total ?? 0, 0)}</b></div></div>
      <p class="note">${t("sampling_caveat")}</p>
      <div class="grid-2"><div><div class="section-title">${t("by_year_title")}</div><div class="tbl-wrap" style="max-height:420px">
        <table class="data"><tr><th>${t("year")}</th><th>${t("records")}</th><th>${t("change")}</th><th>${t("direction")}</th></tr>${filas}</table></div></div>
      <div><div class="section-title">${t("top_species")} · ${year}</div><div class="tbl-wrap"><table class="data">
        <tr><th>${t("scientific_name")}</th><th>${t("class")}</th><th>${t("records")}</th></tr>${top || `<tr><td colspan="3">${t("no_data")}</td></tr>`}</table></div>
      <div class="section-title">${t("redlist_title")}</div><div class="tbl-wrap" style="max-height:260px"><table class="data">
        <tr><th>${t("scientific_name")}</th><th>${t("class")}</th><th>${t("category")}</th></tr>${roja || `<tr><td colspan="3">${t("none")}</td></tr>`}</table></div></div></div>
      <p class="hint">${anio.source}</p>`;
  }

  /** Gráfico 3D: relieve coloreado por una variable, o nube de propiedades de las celdas del mes. */
  async function render3D(body) {
    const month = ctx.month();
    const colores = ["sst", "sst_anom", "chl", "chl_anom", "none"];
    const etiqueta = (c) => (c === "none" ? t("relief_only") : t(`var_${c}`));
    body.innerHTML = `<div class="controls-row">
        <div class="seg" id="three-mode" style="min-width:300px"><button type="button" data-m="relief" class="${det.threeMode === "relief" ? "active" : ""}">${t("mode_relief")}</button>
          <button type="button" data-m="props" class="${det.threeMode === "props" ? "active" : ""}">${t("mode_props")}</button></div>
        ${det.threeMode === "relief" ? `<label>${t("color_by")} <select id="three-color" class="select small">${colores.map((c) => `<option value="${c}" ${c === det.threeColor ? "selected" : ""}>${etiqueta(c)}</option>`).join("")}</select></label>
        <label>${t("exaggeration")} <input type="range" id="three-exag" min="0.05" max="1" step="0.05" value="${det.exag}"></label>` : ""}
      </div><div id="plot-3d" class="plot tall"></div><p class="hint">${fmtMonth(month)} · ${t("disclaimer")}</p>`;
    $$("#three-mode button").forEach((b) => b.addEventListener("click", () => { det.threeMode = b.dataset.m; renderModal(); }));
    $("#three-color")?.addEventListener("change", (e) => { det.threeColor = e.target.value; renderModal(); });
    $("#three-exag")?.addEventListener("input", (e) => {
      det.exag = +e.target.value;
      Plotly.relayout("plot-3d", { "scene.aspectratio.z": det.exag });
    });
    let fig;
    if (det.threeMode === "props") {
      fig = F.propsFigure(await api.cells(cur.sel, month));
    } else {
      const colorVar = det.threeColor === "none" ? "sst" : det.threeColor;
      const s = await api.surface(cur.sel, colorVar, month);
      fig = F.reliefFigure(s, { colorVar, conColor: det.threeColor !== "none", meta: ctx.varMeta(colorVar),
                                autoScale: ctx.state.autoScale, exag: det.exag });
    }
    if (!det) return;
    Plotly.newPlot("plot-3d", fig.data, fig.layout, PLOT_CFG);
  }

  /** Comparación de anomalías de TSM y clorofila del área en el mismo gráfico. */
  async function renderProps(body) {
    const month = ctx.month();
    const [a, b] = await Promise.all([api.timeseries(cur.sel, "sst", month), api.timeseries(cur.sel, "chl", month)]);
    body.innerHTML = `<div id="plot-props" class="plot"></div><p class="hint">${t("disclaimer")}</p>`;
    const fig = F.propsSeriesFigure(a, b, month, rango);
    Plotly.newPlot("plot-props", fig.data, fig.layout, PLOT_CFG);
  }

  /** Radar SAR del área: tabla por año, gráfico o galería de escenas del mes (ASF, sin cuenta). */
  async function renderSar(body, tab) {
    const month = ctx.month(), year = +month.slice(0, 4);
    if (tab === "images") {
      body.innerHTML = `<p class="note">${t("sar_explain")}</p><div id="sar-gal"></div>`;
      return ctx.sarUI.galeria($("#sar-gal"), cur.sel, month, 1);
    }
    const r = cur.sar && !cur.sar.error ? cur.sar : await api.sarArea(cur.sel);
    if (!det || det.feature !== "sar") return;
    const filas = r.years.filter((x) => enRango(x.year));
    if (tab === "chart") {
      body.innerHTML = `<div id="plot-sar" class="plot"></div><p class="hint">${t("sar_method")}</p>`;
      const fig = F.sarFigure(filas, year);
      Plotly.newPlot("plot-sar", fig.data, fig.layout, PLOT_CFG);
      return;
    }
    const v = (x, d) => (x === null || x === undefined ? "—" : fmtNum(x, d));
    const tr = (x, etq, actual) => `<tr class="${actual ? "current" : ""}"><td>${etq}</td><td>${v(x.damped_pct, 2)}</td><td>${v(x.bright_pct, 2)}</td>
      <td>${v(x.wind, 1)}</td><td>${fmtNum(x.n, 0)}</td></tr>`;
    body.innerHTML = `<p class="note">${t("sar_explain")}</p>
      <div class="kpis"><div class="kpi"><small>${t("var_sar_damped")} · 2017–2024</small><b>${v(r.all.damped_pct, 2)} %</b></div>
        <div class="kpi"><small>${t("var_sar_bright")} · 2017–2024</small><b>${v(r.all.bright_pct, 2)} %</b></div>
        <div class="kpi"><small>${t("var_sar_wind")} · 2017–2024</small><b>${v(r.all.wind, 1)} m/s</b></div></div>
      <div class="tbl-wrap"><table class="data"><tr><th>${t("year")}</th><th>${t("var_sar_damped")} (%)</th><th>${t("var_sar_bright")} (%)</th>
        <th>${t("var_sar_wind")} (m/s)</th><th>${t("sar_obs")}</th></tr>
        ${filas.map((x) => tr(x, x.year, x.year === year)).join("")}${tr(r.all, "2017–2024", false)}</table></div>
      <p class="hint">${t("sar_method")}</p>`;
  }

  /* ============================================================ análisis de eventos */
  function openEvent(ev) {
    det = { kind: "event", ev, tab: "chart" };
    modal.classList.remove("hidden");
    renderModal();
  }

  async function renderEvent() {
    const ev = det.ev;
    $("#modal-title").textContent = tx(ev.name);
    $("#modal-sub").textContent = `${fmtDate(ev.start)}${ev.end ? ` – ${fmtDate(ev.end)}` : ""} · ${t(`cat_${ev.category}`)} · ${t(ev.type)}${ev.approx ? ` · ${t("approx")}` : ""}`;
    renderTabs([], false);
    const body = $("#modal-body");
    body.innerHTML = `<p>${tx(ev.description)}</p><p class="hint">${t("source")}: <a href="${ev.source.url}" target="_blank" rel="noopener" style="color:var(--accent)">${ev.source.name}</a></p>
      <div class="pp-actions"><button type="button" class="btn" id="ev-goto">${t("go_date")}</button>
      <button type="button" class="btn ghost" id="ev-area">${t("analyze")} · ${t("area_title")}</button></div>
      <div id="ev-impact"><p><span class="spinner"></span> ${t("loading")}</p></div>
      <div id="ev-sar" class="ev-sar"></div>`;
    ctx.sarUI.panelEvento($("#ev-sar"), ev).catch((e) => { const b = $("#ev-sar"); if (b) b.innerHTML = `<p class="hint">SAR: ${e.message}</p>`; });
    $("#ev-goto").addEventListener("click", () => { closeModal(); ctx.goToEvent(ev.id, { analyze: false }); });
    $("#ev-area").addEventListener("click", () => {
      const dLat = ev.radius_km / 111, dLon = ev.radius_km / (111 * Math.cos((ev.lat * Math.PI) / 180));
      closeModal();
      ctx.setMonthByName(ev.start.slice(0, 7));
      ctx.selectArea({ type: "bbox", bbox: [ev.lon - dLon, ev.lat - dLat, ev.lon + dLon, ev.lat + dLat], kind: "event", ev });
    });
    let imp;
    try { imp = await api.impact(ev.id); } catch (e) { $("#ev-impact").innerHTML = `<p>${t("api_error")}: ${e.message}</p>`; return; }
    if (!det || det.ev !== ev) return;
    const box = $("#ev-impact");
    if (imp.note === "out_of_range") { box.innerHTML = `<p class="note">${t("impact_out")}</p>`; return; }
    if (imp.note === "no_ocean_cells") { box.innerHTML = `<p class="note">${t("impact_nocells")}</p>`; return; }
    const fila = (k, nombre, u, d) => `<tr><td>${nombre}</td><td>${signed(imp[k].before_anom, d)} ${u}</td><td>${signed(imp[k].after_anom, d)} ${u}</td>
      <td>${signed(imp[k].change, d)} ${u}</td><td>${badge(imp[k].direction)}</td></tr>`;
    box.innerHTML = `<div class="section-title">${t("impact_title")}</div>
      <p class="hint">${t("impact_area", { r: ev.radius_km, c: imp.cells })}</p>
      <table class="data"><tr><th></th><th>${t("anomaly")} · ${t("before")}</th><th>${t("anomaly")} · ${t("after")}</th><th>${t("change")}</th><th>${t("direction")}</th></tr>
      ${fila("sst", t("sst"), "°C", 2)}${fila("chl", t("chl"), "%", 0)}</table>
      <div id="plot-event" class="plot"></div><p class="note">${t("disclaimer")}</p>`;
    const fig = F.eventFigure(imp, ev);
    Plotly.newPlot("plot-event", fig.data, fig.layout, PLOT_CFG);
  }

  /* ============================================================ línea de tiempo e idioma */
  const refrescarDetalle = debounce(() => { if (det && det.kind === "feature") renderModal(); }, 350);
  const refrescarPopup = debounce(() => { if (cur) load(); }, 250);

  /** Al cambiar el mes: actualiza la ventana del área y, si está abierto, el detalle. */
  function onMonthChange() {
    if (cur) {
      const p = $(".pp-title p", pop);
      if (p) p.textContent = `${fmtSel(cur.sel)} · ${fmtMonth(ctx.month())}`;
      refrescarPopup();
    }
    if (det && det.kind === "feature" && !modal.classList.contains("hidden")) {
      if (ctx.state.playing && det.tab !== "3d") {   // durante la animación solo se mueve la marca del mes
        const p = $(".plot", modal);
        if (p && p.layout) Plotly.relayout(p, { "shapes[0].x0": ctx.month(), "shapes[0].x1": ctx.month() });
        $("#modal-sub").textContent = `${fmtSel(cur.sel)} · ${fmtMonth(ctx.month())}`;
      } else refrescarDetalle();
    }
  }

  function rerender() {
    renderPopup();
    if (det && !modal.classList.contains("hidden")) renderModal();
  }

  return { open, close, openEvent, onMonthChange, rerender, closeModal };
}
