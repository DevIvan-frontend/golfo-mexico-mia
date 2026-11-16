/**
 * @module exporter
 * Arma los informes de Excel y los descarga. El navegador reúne los datos (los mismos endpoints que usa la
 * interfaz), les aplica el filtro de años, traduce las columnas al idioma activo y genera PNG de los gráficos
 * con Plotly; el backend (POST /api/export/xlsx, backend/export.py) escribe el .xlsx con openpyxl.
 *
 * Contenido del informe de un área:
 *   Info · Resumen · TSM anual · TSM mismo mes · Clorofila anual · Clorofila mismo mes · Serie mensual ·
 *   Profundidad · Vida marina por año · Especies del año · Lista Roja UICN · Eventos · Celdas del mes · Gráficos
 * Las hojas anuales, mensual, de profundidad y de vida marina llevan además un gráfico nativo de Excel.
 */
import { t, tx, fmtMonth, fmtDate, fmtSel } from "./i18n.js";
import { api } from "./api.js";
import * as F from "./figures.js";

const dirTxt = (d) => t(d || "nd");
const enRango = (anio, r) => !r || (anio >= r.from && anio <= r.to);

/** Añade un PNG del gráfico a la lista de imágenes; si falla (p. ej. sin WebGL) se omite sin romper el informe. */
async function agregarImagen(lista, titulo, fig, w, h) {
  try { lista.push({ title: titulo, png_base64: await F.figureToPng(fig, w, h) }); } catch (e) { console.warn("Imagen omitida:", titulo, e); }
}

/** Envía el informe al backend y dispara la descarga del archivo. */
async function descargar(payload) {
  const blob = await api.exportXlsx(payload);
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = payload.filename;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 2000);
}

const nombreSeguro = (s) => s.normalize("NFKD").replace(/[^\w.-]+/g, "_").replace(/_+/g, "_");

function infoComun(range) {
  return [
    [t("info_filter"), range ? `${range.from} – ${range.to}` : "—"],
    [t("info_generated"), new Date().toLocaleString()],
    [t("info_sources"), [t("src_sst"), t("src_chl"), t("src_depth"), t("src_obis"), t("src_events")].join(" ")],
    [t("info_note"), t("disclaimer")],
  ];
}

/**
 * Informe completo de un área (celda de 1°, rectángulo o polígono).
 * @param {object} ctx contexto de la app (mes, eventos, metadatos)
 * @param {object} sel selección {type:'bbox'|'poly', …}
 * @param {{from:number,to:number}} range filtro de años aplicado a tablas y gráficos
 */
export async function exportAreaReport(ctx, sel, range) {
  const month = ctx.month();
  const year = +month.slice(0, 4);
  const [sum, sst, chl, dep, cells] = await Promise.all([
    api.summary(sel, month), api.timeseries(sel, "sst", month), api.timeseries(sel, "chl", month), api.depth(sel), api.cells(sel, month),
  ]);
  const [faunaAnio, faunaTodo] = await Promise.all([api.fauna(sel, year).catch(() => null), api.fauna(sel, null).catch(() => null)]);
  const sheets = [];
  const v = sum.variables;

  // 1. Resumen del mes seleccionado
  const cols = [t("col_feature"), t("value"), t("col_unit"), t("col_clim"), t("anomaly"), t("col_prev"), t("col_delta_prev"),
                t("col_trend"), t("col_p"), t("direction"), `${t("coverage")} (%)`];
  const filas = [];
  if (v.sst) filas.push([t("sst"), v.sst.value, "°C", v.sst.clim, v.sst.anom, v.sst.prev_year, v.sst.delta_prev_year, v.sst.trend_per_decade, v.sst.trend_p, dirTxt(v.sst.direction), v.sst.coverage_pct]);
  if (v.chl) filas.push([t("chl"), v.chl.value, "mg m-3", v.chl.clim, v.chl.anom, v.chl.prev_year, v.chl.delta_prev_year, v.chl.trend_per_decade, v.chl.trend_p, dirTxt(v.chl.direction), v.chl.coverage_pct]);
  if (v.depth) {
    filas.push([`${t("depth")} · ${t("mean")}`, v.depth.mean, "m"], [`${t("depth")} · ${t("min")}`, v.depth.min, "m"],
               [`${t("depth")} · ${t("max")}`, v.depth.max, "m"], [t("shelf"), v.depth.shelf_pct, "%"]);
  }
  if (faunaAnio?.available) {
    filas.push([`${t("fauna")} · ${t("records")} ${year}`, faunaAnio.records, ""], [`${t("fauna")} · ${t("species")} ${year}`, faunaAnio.species, ""]);
  }
  if (faunaTodo?.available) filas.push([`${t("fauna")} · ${t("redlist")}`, faunaTodo.redlist_total, ""]);
  sheets.push({ name: t("sh_summary"), columns: cols, rows: filas, note: `${fmtMonth(month)} · ${t("col_anom_note")}` });

  // 2. Tablas anuales y del mismo mes (TSM y clorofila) con gráfico nativo
  for (const [ts, k, u] of [[sst, "sst", "°C"], [chl, "chl", "mg m-3"]]) {
    const du = k === "chl" ? "%" : "°C";
    sheets.push({
      name: t(`sh_${k}_annual`),
      columns: [t("year"), `${t(k)} (${u})`, `${t("change")} (${du})`, t("direction"), `${t("anomaly")} (${du})`],
      rows: ts.annual.filter((r) => enRango(r.year, range)).map((r) => [r.year, r.mean, r.delta, dirTxt(r.direction), r.anom]),
      chart: { type: "line", title: `${t(k)} · ${t("annual_title")}`, x_col: 0, y_cols: [1], y_title: u, x_title: t("year") },
    });
    sheets.push({
      name: t(`sh_${k}_same`),
      columns: [t("month_col"), `${t(k)} (${u})`, `${t("change")} (${du})`, t("direction"), `${t("anomaly")} (${du})`],
      rows: ts.same_month.filter((r) => enRango(+r.month.slice(0, 4), range)).map((r) => [r.month, r.value, r.delta, dirTxt(r.direction), r.anom]),
    });
  }

  // 3. Serie mensual completa
  sheets.push({
    name: t("sh_monthly"),
    columns: [t("month_col"), `${t("sst")} (°C)`, `${t("col_clim")} (°C)`, `${t("anomaly")} (°C)`,
              `${t("chl")} (mg m-3)`, `${t("col_clim")} (mg m-3)`, `${t("anomaly")} (%)`, `${t("coverage")} (%)`],
    rows: sst.months.map((m, i) => [m, sst.values[i], sst.clim[i], sst.anom[i], chl.values[i], chl.clim[i], chl.anom[i], sst.coverage_pct[i]])
      .filter((r) => enRango(+r[0].slice(0, 4), range)),
    chart: { type: "line", title: `${t("anomaly")} · ${t("sst")}`, x_col: 0, y_cols: [3], y_title: "°C" },
  });

  // 4. Profundidad
  sheets.push({ name: t("sh_depth"), columns: [t("range_m"), t("pct_area")],
                rows: dep.classes.map((c) => [`${c.from}–${c.to}`, c.pct]),
                chart: { type: "bar", title: t("depth_classes"), x_col: 0, y_cols: [1], y_title: "%" } });

  // 5. Vida marina (OBIS)
  let serieFauna = null;
  if (faunaTodo?.available) {
    const porAnio = new Map(faunaTodo.by_year.map((r) => [r.year, r.records]));
    serieFauna = ctx.meta.obis_years.filter((y) => enRango(y, range)).map((y) => ({ year: y, records: porAnio.get(y) ?? 0 }));
    let prev = null;
    sheets.push({
      name: t("sh_fauna_year"), columns: [t("year"), t("records"), `${t("change")} (%)`, t("direction")],
      rows: serieFauna.map((r) => {
        const delta = prev ? (r.records / prev - 1) * 100 : null;
        const dir = prev === null ? "nd" : prev === 0 ? (r.records > 0 ? "up" : "flat") : delta > 5 ? "up" : delta < -5 ? "down" : "flat";
        prev = r.records;
        return [r.year, r.records, delta === null ? null : Math.round(delta), dirTxt(dir)];
      }),
      chart: { type: "bar", title: t("by_year_title"), x_col: 0, y_cols: [1], y_title: t("records") },
      note: t("sampling_caveat"),
    });
    sheets.push({ name: t("sh_redlist"), columns: [t("scientific_name"), t("class"), t("category"), t("category")],
                  rows: faunaTodo.redlist.map((s) => [s.scientificName, s.class || "", s.category, t(`iucn_${s.category}`)]) });
  }
  if (faunaAnio?.available) {
    sheets.push({ name: t("sh_species"), columns: [t("scientific_name"), t("class"), t("records")],
                  rows: faunaAnio.top.map((s) => [s.scientificName, s.class || s.phylum || "", s.records]) });
  }

  // 6. Eventos relacionados y celdas del mes
  // Radar SAR (Sentinel-1, por año) si el servidor tiene los productos
  if (ctx.meta.sar?.available) {
    const sr = await api.sarArea(sel).catch(() => null);
    if (sr) {
      const filas = sr.years.filter((r) => enRango(r.year, range)).map((r) => [r.year, r.damped_pct, r.bright_pct, r.wind, r.n]);
      filas.push(["2017–2024", sr.all.damped_pct, sr.all.bright_pct, sr.all.wind, sr.all.n]);
      sheets.push({ name: t("sar_title"), columns: [t("year"), `${t("var_sar_damped")} (%)`, `${t("var_sar_bright")} (%)`,
                                                    `${t("var_sar_wind")} (m/s)`, t("sar_obs")],
                    rows: filas, note: t("sar_method"),
                    chart: { type: "bar", title: t("sar_title"), x_col: 0, y_cols: [1, 2], y_title: "%" } });
    }
  }

  sheets.push({
    name: t("sh_events"),
    columns: [t("col_event"), t("col_type"), t("category"), t("col_start"), t("col_end"), t("col_distance"), t("source")],
    rows: sum.events.map((e) => [tx(e.name), t(e.type), t(`cat_${e.category}`), e.start, e.end || "", e.distance_km,
                                 ctx.events.find((x) => x.id === e.id)?.source?.name || ""]),
  });
  sheets.push({
    name: t("sh_cells"),
    columns: [t("lat"), t("lon"), t("depth_m"), `${t("sst")} (°C)`, `${t("anomaly")} (°C)`, `${t("chl")} (mg m-3)`, `${t("anomaly")} (%)`],
    rows: cells.lat.map((la, i) => [la, cells.lon[i], cells.depth[i], cells.sst[i], cells.sst_anom[i], cells.chl[i], cells.chl_anom[i]]),
    note: fmtMonth(month),
  });

  // 7. Imágenes de los gráficos de la web (incluidos los 3D)
  const images = [];
  await agregarImagen(images, `${t("sst")} · ${t("tab_chart")}`, F.seriesFigure(sst, "sst", month, range));
  await agregarImagen(images, `${t("chl")} · ${t("tab_chart")}`, F.seriesFigure(chl, "chl", month, range));
  await agregarImagen(images, t("compare_props"), F.propsSeriesFigure(sst, chl, month, range));
  try {
    const sup = await api.surface(sel, "sst", month);
    await agregarImagen(images, `${t("tab_3d")} · ${t("mode_relief")} (${fmtMonth(month)})`,
      F.reliefFigure(sup, { colorVar: "sst", conColor: true, meta: ctx.varMeta("sst"), autoScale: ctx.state.autoScale, exag: 0.35 }), 1000, 700);
  } catch (e) { console.warn(e); }
  await agregarImagen(images, `${t("tab_3d")} · ${t("mode_props")} (${fmtMonth(month)})`, F.propsFigure(cells), 1000, 700);
  if (serieFauna) await agregarImagen(images, t("by_year_title"), F.faunaFigure(serieFauna, year));

  const [w, s] = sum.selection.bounds;
  await descargar({
    filename: nombreSeguro(`golfo_${Math.abs(s).toFixed(1)}N_${Math.abs(w).toFixed(1)}W_${month}.xlsx`),
    title: `${t("title")} · ${t("report_area")}`,
    info: [[t("info_area"), `${fmtSel(sel)} · ${t("ocean_area")}: ${sum.selection.ocean_area_km2} km²`], [t("info_month"), fmtMonth(month)], ...infoComun(range)],
    sheets, images, images_sheet: t("sh_charts"),
  });
}

/** Informe de un evento: comparación antes/después y serie de anomalías ±24 meses. */
export async function exportEventReport(ctx, ev) {
  const imp = await api.impact(ev.id);
  const sheets = [];
  const images = [];
  if (imp.sst) {
    sheets.push({
      name: t("sh_event_compare"),
      columns: ["", `${t("anomaly")} · ${t("before")}`, `${t("anomaly")} · ${t("after")}`, t("change"), t("direction"), t("col_unit")],
      rows: [[t("sst"), imp.sst.before_anom, imp.sst.after_anom, imp.sst.change, dirTxt(imp.sst.direction), "°C"],
             [t("chl"), imp.chl.before_anom, imp.chl.after_anom, imp.chl.change, dirTxt(imp.chl.direction), "%"]],
      note: t("impact_area", { r: ev.radius_km, c: imp.cells }),
    });
    sheets.push({
      name: t("sh_event_series"),
      columns: [t("month_col"), `${t("sst")} (°C)`, `${t("anomaly")} (°C)`, `${t("chl")} (mg m-3)`, `${t("anomaly")} (%)`],
      rows: imp.months.map((m, i) => [m, imp.sst.values[i], imp.sst.anom[i], imp.chl.values[i], imp.chl.anom[i]]),
      chart: { type: "line", title: `${tx(ev.name)} · ${t("anomaly")}`, x_col: 0, y_cols: [2], y_title: "°C" },
    });
    await agregarImagen(images, tx(ev.name), F.eventFigure(imp, ev));
  }
  await descargar({
    filename: nombreSeguro(`evento_${ev.id}.xlsx`),
    title: `${tx(ev.name)} · ${t("impact_title")}`,
    info: [[t("col_event"), tx(ev.name)], [t("col_start"), fmtDate(ev.start)], [t("col_end"), ev.end ? fmtDate(ev.end) : "—"],
           [t("category"), `${t(`cat_${ev.category}`)} · ${t(ev.type)}`], [t("info_area"), `${ev.lat}, ${ev.lon} · r = ${ev.radius_km} km${ev.approx ? ` (${t("approx")})` : ""}`],
           [t("description"), tx(ev.description)], [t("source"), `${ev.source.name} — ${ev.source.url}`], ...infoComun(null)],
    sheets, images, images_sheet: t("sh_charts"),
  });
}
