/**
 * @module notebook
 * Cuaderno de Jupyter dentro de la aplicación: JupyterLite servido en /jupyter, con Python (Pyodide) ejecutándose en
 * el navegador de cada visitante (el servidor solo entrega archivos estáticos).
 *
 *  - Botón 📓 de la barra superior → cuaderno general (ES/EN) en un panel a pantalla completa.
 *  - Botón 📓 de la ventana del área → la API genera un cuaderno con los parámetros del área (GET /api/notebook,
 *    backend/notebook.py); se guarda en el almacenamiento de JupyterLite de este navegador y se abre.
 *  - En el panel: «⤓ .ipynb» descarga el cuaderno abierto para usarlo en Jupyter local (kernel python3) y «↗» lo abre
 *    en una pestaña nueva.
 *
 * Para guardar archivos se usa la aplicación de JupyterLite, que se expone como `window.jupyterapp` dentro del iframe
 * (opción exposeAppInBrowser, ver scripts/build_jupyterlite.py). Si Jupyter no está instalado en el servidor, el botón
 * del área descarga directamente el .ipynb.
 */
import { t, getLang, fmtSel, fmtMonth } from "./i18n.js";
import { selQuery } from "./api.js";

const $ = (s, r = document) => r.querySelector(s);
const BASE = "jupyter/notebooks/index.html";
const general = (lang) => `Golfo_Mexico_MIA_${lang}.ipynb`;
const espera = (ms) => new Promise((r) => setTimeout(r, ms));

/** Centro aproximado de la selección (para el nombre del archivo). */
function centro(sel) {
  if (sel.type === "bbox") { const [w, s, e, n] = sel.bbox; return [(s + n) / 2, (w + e) / 2]; }
  const c = sel.coords, k = c.length;
  return [c.reduce((a, p) => a + p[1], 0) / k, c.reduce((a, p) => a + p[0], 0) / k];
}

function nombreArea(sel, month, lang) {
  const [la, lo] = centro(sel);
  const ns = la >= 0 ? "N" : "S", ew = lo >= 0 ? "E" : "W";
  return `Area_${month}_${Math.abs(la).toFixed(2)}${ns}_${Math.abs(lo).toFixed(2)}${ew}_${lang}.ipynb`;
}

export function initNotebook(ctx) {
  const panel = $("#nb-panel"), frame = $("#nb-frame");
  const disponible = !!ctx.meta.jupyter;
  $("#btn-notebook").classList.toggle("hidden", !disponible);
  let actual = null;   // { path, download, title }

  /** URL del cuaderno en la API. target: 'lite' (Pyodide) o 'local' (Jupyter en la computadora). */
  function urlApi(lang, target, area) {
    const q = new URLSearchParams({ lang, target, base: location.origin });
    if (!area) return `/api/notebook/${general(lang)}?${q}`;
    q.set("month", area.month);
    q.set("title", area.title);
    return `/api/notebook/${area.file}?${q}&${selQuery(area.sel)}`;
  }

  function mostrar(titulo) {
    $("#nb-sub").textContent = titulo;
    panel.classList.remove("hidden");
    document.body.classList.add("nb-open");
  }

  function cerrar() {
    panel.classList.add("hidden");
    document.body.classList.remove("nb-open");
  }

  function cargar(path) {
    const src = `${BASE}?path=${encodeURIComponent(path)}`;
    if (frame.getAttribute("src") !== src) frame.setAttribute("src", src);
    $("#nb-newtab").href = src;
  }

  /** Espera a que JupyterLite (dentro del iframe) esté listo y devuelve su aplicación. */
  async function appJupyter(maxMs = 90000) {
    if (!frame.getAttribute("src")) cargar(general(getLang()));
    const t0 = Date.now();
    while (Date.now() - t0 < maxMs) {
      const app = frame.contentWindow && frame.contentWindow.jupyterapp;
      if (app && app.serviceManager) {
        await app.serviceManager.ready;
        return app;
      }
      await espera(300);
    }
    throw new Error("JupyterLite timeout");
  }

  function setDescarga(url, archivo) {
    const a = $("#nb-download");
    a.href = url;
    a.setAttribute("download", archivo);
  }

  /** Cuaderno general en el idioma activo. */
  function openGeneral() {
    const lang = getLang();
    actual = { path: general(lang) };
    setDescarga(urlApi(lang, "local"), general(lang));
    cargar(actual.path);
    mostrar(t("nb_general"));
  }

  /** Cuaderno con los parámetros del área seleccionada en el mapa. */
  async function openArea(sel, titulo) {
    const lang = getLang(), month = ctx.month();
    const area = { sel, month, file: nombreArea(sel, month, lang), title: `${titulo} · ${fmtSel(sel)}` };
    const descarga = urlApi(lang, "local", area);
    if (!disponible) {                       // sin JupyterLite en el servidor: solo descarga
      const a = document.createElement("a");
      a.href = descarga; a.download = area.file; a.click();
      ctx.toast(t("nb_downloaded"), 5000, "ok");
      return;
    }
    setDescarga(descarga, area.file);
    mostrar(`${area.title} · ${fmtMonth(month)}`);
    ctx.toast(t("nb_loading"), 0, "info");
    try {
      const [nb, app] = await Promise.all([fetch(urlApi(lang, "lite", area)).then((r) => {
        if (!r.ok) throw new Error(`${r.status}`);
        return r.json();
      }), appJupyter()]);
      await app.serviceManager.contents.save(area.file, { type: "notebook", format: "json", content: nb });
      actual = { path: area.file };
      cargar(area.file);
      ctx.toast(t("nb_area_ready"), 7000, "ok");
    } catch (e) {
      ctx.toast(`${t("nb_area_error")} (${e.message})`, 8000);
    }
  }

  $("#btn-notebook").addEventListener("click", openGeneral);
  $("#nb-close").addEventListener("click", cerrar);
  $("#nb-general").addEventListener("click", openGeneral);
  // Escape cierra el panel (fase de captura: antes de que panels.js cierre la ventana del área)
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !panel.classList.contains("hidden")) { cerrar(); e.stopImmediatePropagation(); }
  }, true);

  return { openGeneral, openArea, close: cerrar, available: disponible };
}
