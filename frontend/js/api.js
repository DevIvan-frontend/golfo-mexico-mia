/**
 * @module api
 * Cliente de la API del backend (FastAPI). Por defecto usa el mismo origen; `?api=http://host:puerto` en la URL
 * permite apuntar a otro servidor. Las respuestas GET se guardan en una caché en memoria (máx. 160) para que la
 * animación y el cambio de pestañas no repitan peticiones.
 * Las selecciones viajan como `bbox=oeste,sur,este,norte` o `poly=lon,lat;lon,lat;…`.
 */
const params = new URLSearchParams(location.search);
const BASE = (params.get("api") || "").replace(/\/$/, "");
const cache = new Map();
const MAX_CACHE = 160;

async function get(path, { useCache = true } = {}) {
  const url = `${BASE}${path}`;
  if (useCache && cache.has(url)) return cache.get(url);
  const p = fetch(url).then(async (r) => {
    if (!r.ok) {
      let detail = r.statusText;
      try { detail = (await r.json()).detail || detail; } catch (_) { /* cuerpo no JSON */ }
      throw new Error(`${r.status} · ${detail}`);
    }
    return r.json();
  });
  if (useCache) {
    cache.set(url, p);
    p.catch(() => cache.delete(url));
    if (cache.size > MAX_CACHE) cache.delete(cache.keys().next().value);
  }
  return p;
}

/** Selección → parámetro de consulta. sel = {type:'bbox', bbox:[w,s,e,n]} | {type:'poly', coords:[[lon,lat],…]} */
export function selQuery(sel) {
  if (sel.type === "bbox") return `bbox=${sel.bbox.map((v) => v.toFixed(4)).join(",")}`;
  return `poly=${sel.coords.map(([lo, la]) => `${lo.toFixed(4)},${la.toFixed(4)}`).join(";")}`;
}

export const api = {
  meta: () => get("/api/meta"),
  grid: (v, month) => get(v === "depth" ? "/api/grid/depth"
    : v.startsWith("sar_") ? `/api/sar/grid/${v}?year=${month.slice(0, 4)}` : `/api/grid/${v}?month=${month}`),
  // Radar SAR (backend/sar.py)
  sarArea: (sel) => get(`/api/sar/area?${selQuery(sel)}`),
  sarScenes: (sel, month, months = 1) => get(`/api/sar/scenes?month=${month}&months=${months}&${selQuery(sel)}`),
  sarEvent: (id) => get(`/api/sar/events/${encodeURIComponent(id)}`),
  sarSlicks: () => get("/api/sar/slicks"),
  summary: (sel, month) => get(`/api/area/summary?month=${month}&${selQuery(sel)}`),
  timeseries: (sel, v, month) => get(`/api/area/timeseries?var=${v}&month=${month}&${selQuery(sel)}`),
  depth: (sel) => get(`/api/area/depth?${selQuery(sel)}`),
  surface: (sel, v, month) => get(`/api/area/surface?var=${v}&month=${month}&${selQuery(sel)}`),
  cells: (sel, month) => get(`/api/area/cells?month=${month}&${selQuery(sel)}`),
  fauna: (sel, year) => get(`/api/fauna?${year ? `year=${year}&` : ""}${selQuery(sel)}`),
  fauna_all: (sel) => get(`/api/fauna?${selQuery(sel)}`),
  obisGrid: (year) => get(`/api/obis/grid/${year}`),
  events: () => get("/api/events"),
  impact: (id) => get(`/api/events/${encodeURIComponent(id)}/impact`),
  places: () => get("/api/places"),
  /** Envía un informe y devuelve el .xlsx como Blob (ver backend/export.py). */
  exportXlsx: async (payload) => {
    const r = await fetch(`${BASE}/api/export/xlsx`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
    });
    if (!r.ok) throw new Error(`${r.status} · ${r.statusText}`);
    return r.blob();
  },
};
