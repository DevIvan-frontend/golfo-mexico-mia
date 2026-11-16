/**
 * @module search
 * Búsqueda global de la barra superior. Acepta:
 *   - coordenadas en grados decimales o con hemisferio: "28.7, -88.4", "28.7N 88.4W", "28,7 -88,4" no (usa punto);
 *   - texto: busca en nombres y descripciones de eventos (en ambos idiomas) y en nombres de lugares.
 * Al elegir un resultado: coordenadas → centra y analiza la celda de 1°; evento → salta a su fecha y lo analiza;
 * lugar → centra el mapa y abre su ficha.
 */
import { t, tx, fmtDate, fmtNum } from "./i18n.js";

const RE_COORD = /^\s*(-?\d{1,2}(?:\.\d+)?)\s*°?\s*([NnSs])?\s*[,;\s]\s*(-?\d{1,3}(?:\.\d+)?)\s*°?\s*([EeWwOo])?\s*$/;
const normalizar = (s) => (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

/** Interpreta un texto como coordenadas; devuelve {lat, lon} o null. */
export function parseCoords(q) {
  const m = RE_COORD.exec(q);
  if (!m) return null;
  let lat = +m[1], lon = +m[3];
  if (m[2] && /[Ss]/.test(m[2])) lat = -Math.abs(lat);
  if (m[4] && /[WwOo]/.test(m[4])) lon = -Math.abs(lon);
  if (Math.abs(lat) > 90 || Math.abs(lon) > 180) return null;
  return { lat, lon };
}

export function initSearch(ctx) {
  const input = document.getElementById("search");
  const box = document.getElementById("search-results");
  let resultados = [];
  let activo = -1;

  function buscar(q) {
    const out = [];
    const c = parseCoords(q);
    if (c) out.push({ kind: "coord", label: t("search_coords", { lat: fmtNum(c.lat, 2), lon: fmtNum(c.lon, 2) }), ...c });
    const n = normalizar(q.trim());
    if (n.length >= 2) {
      for (const ev of ctx.events) {
        const texto = normalizar(`${ev.name.es} ${ev.name.en} ${ev.description.es} ${ev.description.en} ${t(`cat_${ev.category}`)}`);
        if (texto.includes(n)) out.push({ kind: "event", id: ev.id, label: tx(ev.name), sub: `${t("event")} · ${fmtDate(ev.start)}`, type: ev.type });
      }
      for (const p of ctx.places) {
        if (normalizar(`${p.name.es} ${p.name.en}`).includes(n)) out.push({ kind: "place", id: p.id, label: tx(p.name), sub: t("place") });
      }
    }
    return out.slice(0, 9);
  }

  function pintar() {
    if (!input.value.trim()) { box.classList.add("hidden"); return; }
    box.innerHTML = resultados.length
      ? resultados.map((r, i) => `<button type="button" class="sr ${i === activo ? "active" : ""}" data-i="${i}">
          <span class="dot ${r.kind === "event" ? r.type : r.kind}"></span><span><b>${r.label}</b>${r.sub ? `<small>${r.sub}</small>` : ""}</span></button>`).join("")
      : `<div class="sr empty">${t("search_none")}</div>`;
    box.classList.remove("hidden");
    box.querySelectorAll("[data-i]").forEach((b) => b.addEventListener("mousedown", (e) => { e.preventDefault(); elegir(+b.dataset.i); }));
  }

  function elegir(i) {
    const r = resultados[i];
    if (!r) return;
    box.classList.add("hidden");
    input.blur();
    if (r.kind === "coord") ctx.selectCellAt(r.lat, r.lon);
    if (r.kind === "event") ctx.goToEvent(r.id, { analyze: true });
    if (r.kind === "place") ctx.focusPlace(r.id);
  }

  input.addEventListener("input", () => { resultados = buscar(input.value); activo = resultados.length ? 0 : -1; pintar(); });
  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") { activo = Math.min(resultados.length - 1, activo + 1); pintar(); e.preventDefault(); }
    if (e.key === "ArrowUp") { activo = Math.max(0, activo - 1); pintar(); e.preventDefault(); }
    if (e.key === "Enter") { elegir(activo); e.preventDefault(); }
    if (e.key === "Escape") { box.classList.add("hidden"); input.blur(); }
  });
  input.addEventListener("blur", () => setTimeout(() => box.classList.add("hidden"), 150));
  input.addEventListener("focus", () => { if (input.value.trim()) pintar(); });
}
