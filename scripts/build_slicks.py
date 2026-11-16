"""
Detector de manchas superficiales con NISAR (radar de banda L, NASA-ISRO) → capa «Detector de manchas».

Requiere el token de NASA Earthdata (EARTHDATA_TOKEN o ~/.earthdata_token; ver backend/asf.py).

    python scripts/build_slicks.py                     # busca, lee y procesa (reanudable)
    python scripts/build_slicks.py --max 80 --por-huella 3

Física (qué «ve» el radar): el SAR no mide la densidad del agua. Mide el eco de microondas que devuelven las ondas
cortas de la superficie (ondas de Bragg, de cm a dm). Una película más viscosa que el agua —petróleo, emulsiones o
películas biológicas— cambia la tensión superficial y la viscosidad, amortigua esas ondas y la superficie se vuelve
lisa: el eco cae y la zona se ve oscura. Por eso el radar detecta los CAMBIOS DE VISCOSIDAD/TENSIÓN que produce un
derrame. Aquí se mide con la razón de amortiguamiento DR = σ⁰(fondo) / σ⁰(píxel), en dB, en la polarización HH de
banda L (24 cm), y se informa también la HV.

Método por escena (NISAR L2 GCOV, frecuencia B: HH y HV a 80 m, leída por rangos del HDF5 de ~6 GB → ~30 MB):
  1. Multilook 2×2 (160 m) para reducir el moteado.
  2. Mar: dentro del golfo, profundidad ≥ 10 m (ETOPO1) y a > 2 km de tierra brillante en el propio radar.
  3. Fondo: media local del eco del mar en una ventana de ~6,5 km (convolución normalizada, ignora tierra).
  4. Zonas amortiguadas: DR (suavizado 3×3) ≥ 2 dB, unidas morfológicamente; se conservan las de ≥ 1 km². Umbral
     calibrado con escenas del golfo: el 99 % del mar abierto queda por debajo de 1,4 dB.
  5. Confianza: con fondo < −24 dB el mar está casi en calma (sin viento todo se ve oscuro) → «calma, no concluyente».
     Alta: DR medio ≥ 3,5 dB, ≥ 2 km², alargada (≥ 4:1) y estrecha (≤ 3 km), forma típica de una mancha a la
     deriva. Media: el resto. Si > 1,5 % del mar de la escena está amortiguado, la causa probable es el tiempo
     (celdas de lluvia, ráfagas, calmas): la escena se marca «tiempo variable» y ninguna zona queda como alta.
  Se descartan 2 km en el borde de la franja y los valores bajo −35 dB (ruido o relleno).
  6. Imagen en lat/lon (≈ 320 m): eco HH en grises y zonas detectadas en color.

Salida: data/processed/slicks.json · data/processed/slicks/<escena>.png
Caché:  data/cache/slicks/<escena>.json (resultado por escena)
Limitaciones: productos NISAR provisionales; falsos positivos por calma local, lluvia, surgencias, algas y aguas
resguardadas; la confirmación requiere otras fuentes (avistamientos, NOAA OR&R, imágenes ópticas).
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import requests
from scipy import ndimage

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from backend import asf  # noqa: E402
from backend.config import CACHE_DIR, PROCESSED_DIR  # noqa: E402
from backend.geo import GULF_POLYGON, puntos_en_poligono  # noqa: E402

G = "science/LSAR/GCOV/grids/frequencyB/"
ML = 2                    # multilook 2×2 → 160 m
UMBRAL_DR_DB = 2.0        # calibrado: el 99 % del mar abierto queda < 1,4 dB en banda L; los filamentos, 1,5–3 dB
DR_ALTA_DB = 3.5
AREA_MIN_KM2 = 1.0
FONDO_CALMA_DB = -24.0
VENTANA_FONDO = 41        # píxeles de 160 m ≈ 6,5 km
PASO_IMG = 0.003          # grados (~320 m) de la imagen superpuesta
PISO_RUIDO = 10 ** -3.5   # σ⁰ lineal (−35 dB): por debajo es ruido o relleno
BORDE_PX = 13             # píxeles de 160 m (~2 km) descartados en el borde de la franja
FRAC_VARIABLE = 0.015     # > 1,5 % del mar amortiguado → escena con lluvia / viento variable (baja la confianza)
DIR_SAL = PROCESSED_DIR / "slicks"
SALIDA = PROCESSED_DIR / "slicks.json"
DIR_CACHE = CACHE_DIR / "slicks"
GOLFO_WKT = asf.wkt(GULF_POLYGON)

# ------------------------------------------------------------------------------------------- UTM (WGS84)
A, F, K0 = 6378137.0, 1 / 298.257223563, 0.9996
E2 = F * (2 - F)
EP2 = E2 / (1 - E2)


def utm_a_latlon(x, y, zona, norte=True):
    """UTM → lat/lon (grados), fórmulas de Snyder (USGS PP 1395), vectorizado."""
    e1 = (1 - np.sqrt(1 - E2)) / (1 + np.sqrt(1 - E2))
    m = (np.asarray(y, float) - (0 if norte else 10_000_000)) / K0
    mu = m / (A * (1 - E2 / 4 - 3 * E2 ** 2 / 64 - 5 * E2 ** 3 / 256))
    f1 = (mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * np.sin(2 * mu) + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * np.sin(4 * mu)
          + (151 * e1 ** 3 / 96) * np.sin(6 * mu) + (1097 * e1 ** 4 / 512) * np.sin(8 * mu))
    c1, t1 = EP2 * np.cos(f1) ** 2, np.tan(f1) ** 2
    n1 = A / np.sqrt(1 - E2 * np.sin(f1) ** 2)
    r1 = A * (1 - E2) / (1 - E2 * np.sin(f1) ** 2) ** 1.5
    d = (np.asarray(x, float) - 500_000) / (n1 * K0)
    lat = f1 - (n1 * np.tan(f1) / r1) * (d ** 2 / 2 - (5 + 3 * t1 + 10 * c1 - 4 * c1 ** 2 - 9 * EP2) * d ** 4 / 24
                                          + (61 + 90 * t1 + 298 * c1 + 45 * t1 ** 2 - 252 * EP2 - 3 * c1 ** 2) * d ** 6 / 720)
    lon0 = np.radians((zona - 1) * 6 - 180 + 3)
    lon = lon0 + (d - (1 + 2 * t1 + c1) * d ** 3 / 6
                  + (5 - 2 * c1 + 28 * t1 - 3 * c1 ** 2 + 8 * EP2 + 24 * t1 ** 2) * d ** 5 / 120) / np.cos(f1)
    return np.degrees(lat), np.degrees(lon)


def latlon_a_utm(lat, lon, zona, norte=True):
    """lat/lon → UTM (m), vectorizado."""
    p, lam = np.radians(np.asarray(lat, float)), np.radians(np.asarray(lon, float))
    lam0 = np.radians((zona - 1) * 6 - 180 + 3)
    n = A / np.sqrt(1 - E2 * np.sin(p) ** 2)
    t, c, a_ = np.tan(p) ** 2, EP2 * np.cos(p) ** 2, (lam - lam0) * np.cos(p)
    m = A * ((1 - E2 / 4 - 3 * E2 ** 2 / 64 - 5 * E2 ** 3 / 256) * p - (3 * E2 / 8 + 3 * E2 ** 2 / 32 + 45 * E2 ** 3 / 1024) * np.sin(2 * p)
             + (15 * E2 ** 2 / 256 + 45 * E2 ** 3 / 1024) * np.sin(4 * p) - (35 * E2 ** 3 / 3072) * np.sin(6 * p))
    x = K0 * n * (a_ + (1 - t + c) * a_ ** 3 / 6 + (5 - 18 * t + t ** 2 + 72 * c - 58 * EP2) * a_ ** 5 / 120) + 500_000
    y = K0 * (m + n * np.tan(p) * (a_ ** 2 / 2 + (5 - t + 9 * c + 4 * c ** 2) * a_ ** 4 / 24
                                   + (61 - 58 * t + t ** 2 + 600 * c - 330 * EP2) * a_ ** 6 / 720))
    return x, (y if norte else y + 10_000_000)


# ------------------------------------------------------------------------------------------- búsqueda
def _wkt_puntos(wkt: str):
    cuerpo = wkt[wkt.index("((") + 2: wkt.rindex("))")]
    return [tuple(map(float, p.split())) for p in cuerpo.split(",")]


def fraccion_mar(wkt: str, bat) -> float:
    """Fracción de la huella que es mar del golfo con ≥ 10 m de profundidad (muestreo 25×25)."""
    pts = _wkt_puntos(wkt)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    lon2, lat2 = np.meshgrid(np.linspace(min(xs), max(xs), 25), np.linspace(min(ys), max(ys), 25))
    dentro = puntos_en_poligono(lon2, lat2, pts)
    if not dentro.any():
        return 0.0
    prof = profundidad(bat, lat2, lon2)
    mar = dentro & puntos_en_poligono(lon2, lat2, GULF_POLYGON) & (prof >= 10)
    return float(mar.sum() / dentro.sum())


def productos(desde: str, hasta: str) -> list[dict]:
    """Productos NISAR GCOV (.h5) sobre el golfo, buscando mes a mes (búsquedas grandes fallan en ASF)."""
    out, vistos = [], set()
    y, m = int(desde[:4]), int(desde[5:7])
    while f"{y:04d}-{m:02d}" <= hasta:
        y2, m2 = (y + 1, 1) if m == 12 else (y, m + 1)
        try:
            res = asf.buscar(platform="NISAR", processingLevel="GCOV", intersectsWith=GOLFO_WKT,
                             start=f"{y:04d}-{m:02d}-01T00:00:00Z", end=f"{y2:04d}-{m2:02d}-01T00:00:00Z", maxResults=2000)
        except requests.RequestException as err:
            print(f"  {y}-{m:02d}: búsqueda fallida ({type(err).__name__})", flush=True)
            res = []
        for r in res:
            url = r.get("downloadUrl") or ""
            if url.endswith(".h5") and r["granuleName"] not in vistos:
                vistos.add(r["granuleName"])
                out.append(r)
        print(f"  {y}-{m:02d}: {len(res)} resultados", flush=True)
        y, m = y2, m2
    return out


# ------------------------------------------------------------------------------------------- batimetría
def cargar_batimetria():
    import xarray as xr
    with xr.open_dataset(PROCESSED_DIR / "bathymetry.nc", engine="h5netcdf") as ds:
        return {"lats": ds.lat.values, "lons": ds.lon.values, "depth": ds.depth.values}


def profundidad(bat, lat, lon):
    la, lo = bat["lats"], bat["lons"]
    iy = np.clip(np.round((lat - la[0]) / (la[1] - la[0])).astype(int), 0, la.size - 1)
    ix = np.clip(np.round((lon - lo[0]) / (lo[1] - lo[0])).astype(int), 0, lo.size - 1)
    return np.nan_to_num(bat["depth"][iy, ix], nan=-1.0)


# ------------------------------------------------------------------------------------------- procesamiento
def leer(sesion, url: str) -> dict:
    import h5py
    f = asf.ArchivoRemoto(sesion, url)
    with h5py.File(io.BufferedReader(f, buffer_size=1 << 20), "r") as h:
        if G + "projection" not in h:
            raise ValueError("sin frecuencia B")
        g = h[G]
        # Modos de polarización: DH (HH/HV) o DV (VV/VH); la co-polar es la que muestra el amortiguamiento
        co = next((p for p in ("HHHH", "VVVV") if p in g), None)
        cruz = next((p for p in ("HVHV", "VHVH") if p in g), None)
        if co is None:
            raise ValueError(f"sin polarización co-polar en frecuencia B: {list(g.keys())[:8]}")
        attrs = g["projection"].attrs
        d = {"x": g["xCoordinates"][:], "y": g["yCoordinates"][:],
             "hh": g[co][:], "hv": g[cruz][:] if cruz else np.full(g[co].shape, np.nan, np.float32),
             "mask": g["mask"][:], "pol": f"{co[:2]}/{cruz[:2] if cruz else '—'}",
             "zona": int(attrs.get("utm_zone_number", 0)), "epsg": int(g["projection"][()])}
    d["norte"] = 32600 < d["epsg"] < 32700
    if not d["zona"]:
        d["zona"] = d["epsg"] % 100
    d["mb"] = f.leidos / 1e6
    return d


def multilook(a, k=ML):
    a = a[: a.shape[0] // k * k, : a.shape[1] // k * k]
    with np.errstate(invalid="ignore"):
        return np.nanmean(a.reshape(a.shape[0] // k, k, a.shape[1] // k, k), axis=(1, 3))


def media_local(valor, peso, k):
    """Convolución normalizada: media local de `valor` usando solo los píxeles con peso 1."""
    num = ndimage.uniform_filter(np.where(peso, valor, 0.0), k)
    den = ndimage.uniform_filter(peso.astype(float), k)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(den > 0.2, num / den, np.nan)


def procesar(d: dict, bat, gid: str, inicio: str) -> dict:
    with np.errstate(invalid="ignore", divide="ignore"):
        # por debajo de −35 dB (ruido / relleno del borde) el valor no es medida del mar
        hh = multilook(np.where((d["hh"] > PISO_RUIDO) & (d["mask"] != 255), d["hh"], np.nan))
        hv = multilook(np.where((d["hv"] > PISO_RUIDO / 10) & (d["mask"] != 255), d["hv"], np.nan))
    xs = d["x"][: hh.shape[1] * ML].reshape(-1, ML).mean(axis=1)        # centros de los píxeles de 160 m
    ys = d["y"][: hh.shape[0] * ML].reshape(-1, ML).mean(axis=1)
    X, Y = np.meshgrid(xs, ys)
    lat, lon = utm_a_latlon(X, Y, d["zona"], d["norte"])
    valido = np.isfinite(hh)
    db = 10 * np.log10(np.where(valido, hh, np.nan))
    tierra_radar = ndimage.uniform_filter(np.nan_to_num(db, nan=-40.0), 9) > -12.0      # tierra = eco fuerte
    mar_bat = (profundidad(bat, lat, lon) >= 10) & puntos_en_poligono(lon, lat, GULF_POLYGON)
    zona_tierra = ndimage.binary_dilation(tierra_radar | ~mar_bat, iterations=13)          # 13 × 160 m ≈ 2 km
    interior = ndimage.binary_erosion(valido, iterations=BORDE_PX, border_value=0)         # sin el borde de la franja
    mar = valido & interior & ~zona_tierra
    px_km2 = (abs(xs[1] - xs[0]) / 1000) * (abs(ys[1] - ys[0]) / 1000)
    base = {"scene": gid, "start": inicio, "zone": d["zona"], "mb_read": round(d["mb"], 1), "pol": d.get("pol"),
            "sea_km2": round(float(mar.sum() * px_km2), 1)}
    if mar.sum() * px_km2 < 200:
        return {**base, "detections": [], "note": "poco mar"}
    fondo = media_local(hh, mar, VENTANA_FONDO)
    fondo_hv = media_local(hv, mar & np.isfinite(hv), VENTANA_FONDO)
    with np.errstate(invalid="ignore", divide="ignore"):
        dr = 10 * np.log10(fondo / hh)
        dr_hv = 10 * np.log10(fondo_hv / hv)
        fondo_db = 10 * np.log10(fondo)
    # suavizado 3×3 (reduce el moteado sin borrar filamentos finos) y cierre morfológico
    dr_s = media_local(dr, mar & np.isfinite(dr), 3)
    cand = mar & (dr_s >= UMBRAL_DR_DB)
    cand = ndimage.binary_closing(cand, iterations=1) & mar
    lab, n = ndimage.label(cand)
    dets = []
    cajas = ndimage.find_objects(lab)
    if n:
        idx = np.arange(1, n + 1)
        areas = ndimage.sum(np.ones_like(lab), lab, idx) * px_km2
        for k in idx[areas >= AREA_MIN_KM2]:
            caja = cajas[k - 1]
            sel = np.zeros(lab.shape, bool)
            sel[caja] = lab[caja] == k
            yy, xx = np.nonzero(sel[caja])
            cov = np.cov(np.vstack([xx, yy])) if yy.size > 2 else np.eye(2)
            ev = np.sort(np.linalg.eigvalsh(cov))[::-1]
            largo = 4 * np.sqrt(max(ev[0], 1e-6)) * abs(xs[1] - xs[0]) / 1000
            ancho = 4 * np.sqrt(max(ev[1], 1e-6)) * abs(xs[1] - xs[0]) / 1000
            area = float(sel.sum() * px_km2)
            # Huecos/relleno del procesado: rectángulos casi llenos y con eco sin moteado → no es el mar
            relleno = sel[caja].mean()
            if relleno > 0.85 and min(sel[caja].shape) >= 5 and np.nanstd(db[sel]) < 0.6:
                continue
            dr_m, fondo_m = float(np.nanmean(dr[sel])), float(np.nanmean(fondo_db[sel]))
            alargada = largo / max(ancho, 0.16)
            if fondo_m < FONDO_CALMA_DB:
                conf = "calm"
            elif dr_m >= DR_ALTA_DB and area >= 2 and alargada >= 4 and ancho <= 3.0:   # forma de mancha a la deriva
                conf = "high"
            else:
                conf = "medium"
            dets.append({"lat": round(float(lat[sel].mean()), 4), "lon": round(float(lon[sel].mean()), 4),
                         "area_km2": round(area, 2), "length_km": round(float(largo), 1), "width_km": round(float(ancho), 1),
                         "dr_db": round(dr_m, 1), "dr_hv_db": round(float(np.nanmean(dr_hv[sel])), 1),
                         "background_db": round(fondo_m, 1), "confidence": conf, "_k": int(k)})
    dets.sort(key=lambda x: -x["area_km2"] * x["dr_db"])
    # Escena con tiempo convectivo: muchas zonas oscuras a la vez suelen ser lluvia / ráfagas / calmas, no petróleo
    frac = sum(x["area_km2"] for x in dets if x["confidence"] != "calm") / max(float(mar.sum() * px_km2), 1.0)
    variable = frac > FRAC_VARIABLE
    if variable:
        for x in dets:
            if x["confidence"] == "high":
                x["confidence"] = "medium"
    clases = np.zeros(lab.shape, np.uint8)            # 1 alta · 2 media · 3 calma
    for x in dets:
        k = x.pop("_k")
        caja = cajas[k - 1]
        clases[caja][lab[caja] == k] = {"high": 1, "medium": 2, "calm": 3}[x["confidence"]]
    dets = dets[:60]
    imagen = renderizar(db, mar, clases, xs, ys, lat, lon, d, gid)
    resumen = {c: sum(1 for x in dets if x["confidence"] == c) for c in ("high", "medium", "calm")}
    return {**base, "background_db": round(float(np.nanmedian(fondo_db[mar])), 1), "detections": dets,
            "damped_fraction": round(frac, 4), "variable_weather": bool(variable),
            "counts": resumen, "damped_km2": round(float(sum(x["area_km2"] for x in dets if x["confidence"] != "calm")), 1),
            **imagen}


def renderizar(db, mar, clases, xs, ys, lat, lon, d, gid) -> dict:
    """Imagen RGBA en lat/lon: eco HH en grises (solo mar), zonas en rojo (alta), naranja (media) y azul (calma)."""
    from PIL import Image
    ok = np.isfinite(db)
    s, n = float(np.nanmin(lat[ok])), float(np.nanmax(lat[ok]))
    w, e = float(np.nanmin(lon[ok])), float(np.nanmax(lon[ok]))
    glat = np.arange(n, s, -PASO_IMG)
    glon = np.arange(w, e, PASO_IMG)
    LO, LA = np.meshgrid(glon, glat)
    X, Y = latlon_a_utm(LA, LO, d["zona"], d["norte"])
    ix = np.round((X - xs[0]) / (xs[1] - xs[0])).astype(int)
    iy = np.round((Y - ys[0]) / (ys[1] - ys[0])).astype(int)
    dentro = (ix >= 0) & (ix < xs.size) & (iy >= 0) & (iy < ys.size)
    ixc, iyc = np.clip(ix, 0, xs.size - 1), np.clip(iy, 0, ys.size - 1)
    v = np.where(dentro, db[iyc, ixc], np.nan)
    m = dentro & mar[iyc, ixc]
    c = np.where(dentro, clases[iyc, ixc], 0)
    lo, hi = np.nanpercentile(db[mar], [1, 99.5]) if mar.any() else (-28.0, -10.0)   # contraste propio de la escena
    gris = np.clip((np.nan_to_num(v, nan=lo) - lo) / max(hi - lo, 1.0), 0, 1) ** 0.8 * 255
    rgba = np.zeros(v.shape + (4,), np.uint8)
    rgba[..., 0] = rgba[..., 1] = rgba[..., 2] = gris.astype(np.uint8)
    rgba[..., 3] = np.where(m, 215, np.where(np.isfinite(v), 70, 0))
    for clase, color in ((1, (230, 40, 40)), (2, (255, 150, 30)), (3, (90, 150, 255))):
        sel = c == clase
        rgba[sel, :3] = color
        rgba[sel, 3] = 235
    DIR_SAL.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgba, "RGBA").save(DIR_SAL / f"{gid}.png", optimize=True)
    return {"bounds": [[round(s, 4), round(w, 4)], [round(n, 4), round(e, 4)]], "image": f"slicks/{gid}.png"}


def limpiar(o):
    """NaN/inf → None (JSON estándar; p. ej. escenas de una sola polarización no tienen amortiguamiento cruzado)."""
    if isinstance(o, float):
        return o if np.isfinite(o) else None
    if isinstance(o, dict):
        return {k: limpiar(v) for k, v in o.items()}
    if isinstance(o, list):
        return [limpiar(v) for v in o]
    return o


def una_escena(sesion, bat, r) -> dict:
    gid = r["granuleName"]
    cache = DIR_CACHE / f"{gid}.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    d = leer(sesion, r["downloadUrl"])
    res = procesar(d, bat, gid, r["startTime"])
    res.update({"track": r.get("path"), "frame": r.get("frame"), "direction": r.get("flightDirection"),
                "wkt": r.get("wkt"), "vertex": asf.VERTEX.format(gid)})
    res = limpiar(res)
    cache.write_text(json.dumps(res, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--desde", default="2025-07")
    ap.add_argument("--hasta", default=datetime.now(timezone.utc).strftime("%Y-%m"))
    ap.add_argument("--max", type=int, default=70, help="escenas a procesar")
    ap.add_argument("--por-huella", type=int, default=3)
    ap.add_argument("--mar-min", type=float, default=0.25, help="fracción mínima de mar en la huella")
    ap.add_argument("--hilos", type=int, default=3)
    a = ap.parse_args()
    DIR_CACHE.mkdir(parents=True, exist_ok=True)
    bat = cargar_batimetria()
    print("Buscando productos NISAR GCOV sobre el golfo:", flush=True)
    todos = productos(a.desde, a.hasta)
    con_mar = [(fraccion_mar(r["wkt"], bat), r) for r in todos if r.get("wkt")]
    con_mar = [(fm, r) for fm, r in con_mar if fm >= a.mar_min]
    print(f"  {len(todos)} productos · {len(con_mar)} con ≥ {a.mar_min:.0%} de mar", flush=True)
    grupos = defaultdict(list)
    for fm, r in con_mar:
        grupos[(r.get("path"), r.get("frame"))].append((fm, r))
    elegidas = []
    for g in grupos.values():                         # por huella: las más recientes, repartidas en el tiempo
        g = sorted(g, key=lambda x: x[1]["startTime"])
        idx = np.unique(np.linspace(0, len(g) - 1, min(a.por_huella, len(g))).round().astype(int))
        elegidas += [g[i] for i in idx]
    elegidas = [r for fm, r in sorted(elegidas, key=lambda x: -x[0])[: a.max]]
    print(f"  {len(grupos)} huellas → {len(elegidas)} escenas elegidas", flush=True)
    sesion = asf.sesion_earthdata()
    escenas, fallos = [], 0
    with ThreadPoolExecutor(max_workers=a.hilos) as ex:
        futuros = {ex.submit(una_escena, sesion, bat, r): r for r in elegidas}
        for i, fut in enumerate(as_completed(futuros), 1):
            r = futuros[fut]
            try:
                res = fut.result()
                escenas.append(res)
                print(f"  [{i}/{len(elegidas)}] {r['startTime'][:10]} {r['granuleName'][17:45]} mar {res['sea_km2']:.0f} km² · "
                      f"{len(res['detections'])} zonas {res.get('counts', {})}", flush=True)
            except Exception as err:   # se reintenta en la próxima ejecución
                fallos += 1
                print(f"  ! {r['granuleName'][:50]}: {type(err).__name__} {str(err)[:120]}", flush=True)
    escenas = [e for e in escenas if e.get("image")]
    escenas.sort(key=lambda e: e["start"], reverse=True)
    escenas = limpiar(escenas)
    SALIDA.write_text(json.dumps({
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "NISAR L2 GCOV (provisional), L-band HH/HV, NASA-ISRO, via NASA ASF DAAC",
        "method": f"frequency B 80 m → 160 m; damping ratio DR = σ0_background/σ0_HH ≥ {UMBRAL_DR_DB} dB "
                  f"({VENTANA_FONDO * 0.16:.1f} km window); ≥ {AREA_MIN_KM2} km²; sea ≥ 10 m deep and > 2 km from land; "
                  f"background < {FONDO_CALMA_DB} dB = calm (inconclusive)",
        "scenes": escenas}, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    print(f"→ {SALIDA.relative_to(RAIZ)}: {len(escenas)} escenas, "
          f"{sum(len(e['detections']) for e in escenas)} zonas (fallos {fallos})", flush=True)


if __name__ == "__main__":
    main()
