"""
Radar de apertura sintética (SAR) Sentinel-1 → productos del golfo para la aplicación.

Requiere un token de NASA Earthdata (EARTHDATA_TOKEN o ~/.earthdata_token; ver backend/asf.py).

    python scripts/build_sar.py                 # descarga, procesa y agrega (reanudable)
    python scripts/build_sar.py --solo-agregar  # rehace los productos con las escenas ya procesadas
    python scripts/build_sar.py --por-huella 1 --hilos 4

Fuente: productos Sentinel-1 Level-2 OCN (Ocean, ESA/Copernicus) distribuidos por NASA ASF DAAC. Cada producto trae,
en celdas de ~1 km: viento medido por el radar (owiWindSpeed), retrodispersión normalizada observada (owiNrcs, σ⁰),
la σ⁰ que predice el modelo CMOD con el viento del modelo ECMWF (owiNrcsCmod), el % de píxeles brillantes (owiPBright)
y una máscara (0 = mar válido).

Métricas por celda de 0,1° (~11 km):
  * viento_sar      media de owiWindSpeed (m/s).
  * amortiguada     % de observaciones con σ⁰_VV / σ⁰_CMOD < 0,5 (≈ −3 dB) con viento ECMWF entre 3 y 10 m/s y sin
                    objetos brillantes. Una superficie «amortiguada» (lisa) es el criterio clásico de detección de
                    manchas de petróleo o películas superficiales en SAR; también la producen algas, lluvia o calma
                    local (falsos positivos), por eso se presenta como «posibles manchas».
  * brillantes      % de observaciones con objetos brillantes (owiPBright > 0): barcos y plataformas.
  * n               número de observaciones de ~1 km que aportan a la celda.

Muestreo (el archivo completo pesa ~15 GB por año): por cada año 2017–2024 y cada huella (órbita relativa + marco),
`--por-huella` escenas repartidas en el año → mapas anuales y del periodo. Además, para cada evento documentado desde
2017, hasta 12 escenas en los 45 días previos y 12 en los 45 posteriores dentro de su radio → comparación antes/después
y un mapa de viento del radar.

Salida:  data/processed/sar_composite.nc · data/processed/sar_events.json · data/processed/sar_img/<evento>.png
Caché:   data/cache/sar/escenas/<escena>.npz (resultados por escena; los .zip se descargan a memoria y se descartan)
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import threading
import time
import zipfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import requests

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from backend import asf  # noqa: E402
from backend.config import BBOX, CACHE_DIR, EVENTS_FILE, PROCESSED_DIR  # noqa: E402
from backend.geo import GULF_POLYGON, haversine_km, mascara_golfo  # noqa: E402

RES = 0.1
LATS = np.round(np.arange(BBOX["south"] + RES / 2, BBOX["north"], RES), 4)
LONS = np.round(np.arange(BBOX["west"] + RES / 2, BBOX["east"], RES), 4)
NY, NX = LATS.size, LONS.size
ANIOS = list(range(2017, 2025))
DIR_ESC = CACHE_DIR / "sar" / "escenas"
SALIDA_NC = PROCESSED_DIR / "sar_composite.nc"
SALIDA_EV = PROCESSED_DIR / "sar_events.json"
DIR_IMG = PROCESSED_DIR / "sar_img"
UMBRAL_RATIO = 0.5                 # σ⁰ observada / σ⁰ esperada (≈ −3 dB; en celdas de 1 km la mancha no las llena)
VIENTO_MIN, VIENTO_MAX = 3.0, 10.0  # m/s (ECMWF) en los que una mancha se distingue del mar
CAMPOS = ("n", "viento_sum", "viento_n", "amort_n", "amort_validas", "brillo_n")
GOLFO_WKT = asf.wkt(GULF_POLYGON)
_bloqueo = threading.Lock()


# ------------------------------------------------------------------------------------------- procesamiento
def leer_ocn(contenido: bytes):
    """Extrae los campos owi* del NetCDF de un producto OCN (zip en memoria)."""
    from scipy.io import netcdf_file
    with zipfile.ZipFile(io.BytesIO(contenido)) as z:
        nombre = next(n for n in z.namelist() if "/measurement/" in n and n.endswith(".nc"))
        datos = z.read(nombre)
    with netcdf_file(io.BytesIO(datos), "r", mmap=False) as nc:
        v = nc.variables
        # Dos formatos: IPF ≥ 2.9 (owiMask, owiNrcsNeszCorr con dimensión de polarización) e IPF 2.8x de 2017–2018
        # (owiLandFlag y owiNrcs 2D de la polarización indicada en el atributo global 'polarisation').
        if "owiPolarisationName" in v:
            pol = [int(p) for p in np.asarray(v["owiPolarisationName"][:]).ravel()]
            ivv = pol.index(0) if 0 in pol else None
            bruto = np.asarray(v["owiNrcsNeszCorr" if "owiNrcsNeszCorr" in v else "owiNrcs"][:], dtype=np.float32)
            nrcs = bruto[..., ivv] if ivv is not None else None
        else:
            pol_global = nc._attributes.get("polarisation", b"")
            pol_global = pol_global.decode() if isinstance(pol_global, bytes) else str(pol_global)
            nrcs = np.asarray(v["owiNrcs"][:], dtype=np.float32) if pol_global.upper().startswith("VV") else None
        mascara = np.asarray(v["owiMask"][:]) if "owiMask" in v else np.asarray(v["owiLandFlag"][:])
        return {
            "lat": np.asarray(v["owiLat"][:], dtype=np.float32), "lon": np.asarray(v["owiLon"][:], dtype=np.float32),
            "mask": mascara, "viento": np.asarray(v["owiWindSpeed"][:], dtype=np.float32),
            "ecmwf": np.asarray(v["owiEcmwfWindSpeed"][:], dtype=np.float32),
            "nrcs": nrcs,
            "cmod": np.asarray(v["owiNrcsCmod"][:], dtype=np.float32),
            "brillo": np.asarray(v["owiPBright"][:], dtype=np.float32),
        }


BORDE_ESCENA = 3   # celdas (~1 km) descartadas en los bordes de la franja: allí owiPBright y σ⁰ tienen artefactos
BORDE_COSTA = 2    # celdas descartadas junto a tierra (eco contaminado / agua resguardada)


def clasificar(d):
    """Máscaras por celda de ~1 km: válida, viento válido, apta para manchas, amortiguada y brillante."""
    from scipy import ndimage
    with np.errstate(invalid="ignore", divide="ignore"):
        huella = np.isfinite(d["lat"]) & np.isfinite(d["lon"]) & (d["mask"] != 4)     # 4 = sin dato
        mar = d["mask"] == 0
        interior = ndimage.binary_erosion(huella, iterations=BORDE_ESCENA, border_value=0)
        lejos_costa = ndimage.binary_erosion(mar | ~huella, iterations=BORDE_COSTA, border_value=1)
        ok = mar & huella & interior & lejos_costa
        viento_ok = ok & np.isfinite(d["viento"]) & (d["viento"] >= 0) & (d["viento"] < 80)
        brillo = np.nan_to_num(d["brillo"], nan=0.0)
        brillante = ok & (brillo > 0)
        if d["nrcs"] is None:
            apta = np.zeros_like(ok)
            amort = apta
        else:
            apta = ok & ~brillante & (d["ecmwf"] >= VIENTO_MIN) & (d["ecmwf"] <= VIENTO_MAX) & (d["cmod"] > 0) \
                & np.isfinite(d["nrcs"]) & (d["nrcs"] > 0)
            amort = apta & (d["nrcs"] / d["cmod"] < UMBRAL_RATIO)
    return ok, viento_ok, apta, amort, brillante


def resumen_escena(d) -> dict:
    """Sumas por celda de 0,1° (formato disperso) de una escena."""
    ok, viento_ok, apta, amort, brillante = clasificar(d)
    iy = np.floor((d["lat"] - BBOX["south"]) / RES).astype(int)
    ix = np.floor((d["lon"] - BBOX["west"]) / RES).astype(int)
    dentro = ok & (iy >= 0) & (iy < NY) & (ix >= 0) & (ix < NX)
    k = (iy * NX + ix)[dentro]
    tam = NY * NX
    sumas = {
        "n": np.bincount(k, minlength=tam),
        "viento_sum": np.bincount(k, weights=np.where(viento_ok, d["viento"], 0)[dentro], minlength=tam),
        "viento_n": np.bincount(k, weights=viento_ok[dentro].astype(float), minlength=tam),
        "amort_n": np.bincount(k, weights=amort[dentro].astype(float), minlength=tam),
        "amort_validas": np.bincount(k, weights=apta[dentro].astype(float), minlength=tam),
        "brillo_n": np.bincount(k, weights=brillante[dentro].astype(float), minlength=tam),
    }
    idx = np.nonzero(sumas["n"])[0]
    return {"idx": idx.astype(np.int32), **{c: sumas[c][idx].astype(np.float32) for c in CAMPOS}}


def estadisticas_circulo(d, lat0, lon0, radio_km) -> dict:
    """Estadísticas de una escena dentro del radio de un evento."""
    ok, viento_ok, apta, amort, brillante = clasificar(d)
    with np.errstate(invalid="ignore"):
        cerca = haversine_km(lat0, lon0, d["lat"], d["lon"]) <= radio_km
    m = ok & cerca
    if m.sum() < 50:
        return {}
    v = d["viento"][viento_ok & cerca]
    a = apta & cerca
    return {"cells_km2": int(m.sum()), "wind_mean": round(float(v.mean()), 2) if v.size else None,
            "wind_p95": round(float(np.percentile(v, 95)), 2) if v.size else None,
            "damped_pct": round(float(100 * amort[a].mean()), 2) if a.sum() >= 50 else None,
            "bright_pct": round(float(100 * brillante[m].mean()), 3)}


# ------------------------------------------------------------------------------------------- descarga
def ruta_cache(gid: str) -> Path:
    return DIR_ESC / f"{gid}.npz"


def descargar_y_procesar(sesion, esc: dict, evento: dict | None = None):
    """Descarga (en memoria), procesa y guarda el resumen de una escena. Devuelve las estadísticas del evento."""
    gid = esc["granuleName"]
    ruta = ruta_cache(gid)
    estad = {}
    if ruta.exists() and evento is None:
        return gid, None
    for intento in range(4):                      # la red de ASF/CloudFront falla a ratos: reintentos con espera
        try:
            r = sesion.get(esc["downloadUrl"], timeout=(30, 180))
            r.raise_for_status()
            break
        except (requests.ConnectionError, requests.Timeout, requests.exceptions.ChunkedEncodingError):
            if intento == 3:
                raise
            time.sleep(10 * (intento + 1))
    d = leer_ocn(r.content)
    if evento is None:          # solo las escenas del muestreo entran en el compuesto (no las de eventos)
        res = resumen_escena(d)
        np.savez_compressed(ruta, start=esc["startTime"], **res)
    else:
        estad = estadisticas_circulo(d, evento["lat"], evento["lon"], evento["radius_km"])
        if estad and evento.get("_imagen"):
            evento["_candidatas"].append((estad.get("wind_p95") or 0, estad.get("damped_pct") or 0, gid, d))
    return gid, estad


def repartir(lista, n):
    """n elementos repartidos a lo largo de la lista (ordenada por fecha)."""
    if len(lista) <= n:
        return lista
    return [lista[int(round(i))] for i in np.linspace(0, len(lista) - 1, n)]


def escenas_compuesto(por_huella: int) -> list[dict]:
    elegidas = []
    for anio in ANIOS:
        try:
            res = asf.buscar(platform="Sentinel-1", processingLevel="OCN", start=f"{anio}-01-01T00:00:00Z",
                             end=f"{anio}-12-31T23:59:59Z", intersectsWith=GOLFO_WKT)
        except requests.RequestException as err:
            print(f"  {anio}: búsqueda fallida ({type(err).__name__}); se omite por ahora", flush=True)
            continue
        grupos = defaultdict(list)
        for r in res:
            if r.get("beamMode") in ("IW", "EW"):     # franjas continuas (WV son viñetas de 20 km en mar abierto)
                grupos[(r.get("path"), r.get("frame"))].append(r)
        n0 = len(elegidas)
        for g in grupos.values():
            elegidas += repartir(sorted(g, key=lambda r: r["startTime"]), por_huella)
        print(f"  {anio}: {len(res)} escenas OCN, {len(grupos)} huellas → {len(elegidas) - n0} elegidas", flush=True)
    return elegidas


def ejecutar(sesion, tareas, hilos, etiqueta):
    hechas, fallos = 0, 0
    resultados = {}
    with ThreadPoolExecutor(max_workers=hilos) as ex:
        futuros = {ex.submit(descargar_y_procesar, sesion, esc, ev): (esc, ev) for esc, ev in tareas}
        for f in as_completed(futuros):
            esc, ev = futuros[f]
            try:
                gid, estad = f.result()
                resultados[(gid, ev["id"] if ev else None)] = estad
            except Exception as err:   # se reintenta en la siguiente ejecución (la caché lo hace reanudable)
                fallos += 1
                print(f"    ! {esc['granuleName'][:40]}: {type(err).__name__} {str(err)[:120]}", flush=True)
            hechas += 1
            if hechas % 25 == 0 or hechas == len(futuros):
                print(f"  {etiqueta}: {hechas}/{len(futuros)} (fallos {fallos})", flush=True)
    return resultados


# ------------------------------------------------------------------------------------------- eventos
def imagen_viento(d, gid, evento) -> dict:
    """PNG del viento medido por el radar (0–35 m/s, transparente fuera del mar) y sus límites geográficos."""
    from matplotlib import colormaps
    from PIL import Image
    ok, viento_ok, *_ = clasificar(d)
    lat, lon, v = d["lat"][viento_ok], d["lon"][viento_ok], d["viento"][viento_ok]
    paso = 0.02
    s, n, w, e = float(lat.min()), float(lat.max()), float(lon.min()), float(lon.max())
    ny, nx = int((n - s) / paso) + 1, int((e - w) / paso) + 1
    iy = ((n - lat) / paso).astype(int)
    ix = ((lon - w) / paso).astype(int)
    suma = np.zeros((ny, nx)); cuenta = np.zeros((ny, nx))
    np.add.at(suma, (iy, ix), v); np.add.at(cuenta, (iy, ix), 1)
    with np.errstate(invalid="ignore"):
        campo = suma / cuenta
    rgba = (colormaps["turbo"](np.clip(np.nan_to_num(campo) / 35.0, 0, 1)) * 255).astype(np.uint8)
    rgba[..., 3] = np.where(cuenta > 0, 235, 0)
    DIR_IMG.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgba, "RGBA").save(DIR_IMG / f"{evento['id']}.png", optimize=True)
    return {"scene": gid, "bounds": [[s - paso / 2, w - paso / 2], [n + paso / 2, e + paso / 2]],
            "var": "wind", "range": [0, 35], "units": "m/s", "palette": "turbo"}


def procesar_eventos(sesion, hilos):
    eventos = [e for e in json.loads(EVENTS_FILE.read_text(encoding="utf-8")) if "2017-01" <= e["start"][:7] <= "2024-12"]
    dir_ev = CACHE_DIR / "sar" / "eventos"
    dir_ev.mkdir(parents=True, exist_ok=True)
    salida = []
    for ev in eventos:
        cache_ev = dir_ev / f"{ev['id']}.json"
        if cache_ev.exists():
            salida.append(json.loads(cache_ev.read_text(encoding="utf-8")))
            print(f"  {ev['id']}: en caché", flush=True)
            continue
        t0 = datetime.fromisoformat(ev["start"][:10]).replace(tzinfo=timezone.utc)
        area = asf.wkt(asf.circulo(ev["lat"], ev["lon"], ev["radius_km"]))
        try:
            res = asf.buscar(platform="Sentinel-1", processingLevel="OCN", intersectsWith=area,
                             start=(t0 - timedelta(days=45)).strftime("%Y-%m-%dT00:00:00Z"),
                             end=(t0 + timedelta(days=45)).strftime("%Y-%m-%dT23:59:59Z"))
        except requests.RequestException as err:      # ASF no responde: se reintenta en la próxima ejecución
            print(f"  {ev['id']}: búsqueda fallida ({type(err).__name__}); se omite por ahora", flush=True)
            continue
        res = sorted(res, key=lambda r: r["startTime"])
        antes = repartir([r for r in res if r["startTime"] < t0.isoformat()], 12)
        despues = repartir([r for r in res if r["startTime"] >= t0.isoformat()], 12)
        ev_trabajo = {**ev, "_imagen": True, "_candidatas": []}
        print(f"  {ev['id']}: {len(res)} escenas OCN ±45 días → {len(antes)} antes, {len(despues)} después", flush=True)
        resultados = ejecutar(sesion, [(r, ev_trabajo) for r in antes + despues], hilos, ev["id"])
        filas = []
        for r in antes + despues:
            estad = resultados.get((r["granuleName"], ev["id"]))
            if estad:
                filas.append({"scene": r["granuleName"], "start": r["startTime"],
                              "period": "before" if r in antes else "after", **estad})

        def media(periodo, clave):
            xs = [f[clave] for f in filas if f["period"] == periodo and f.get(clave) is not None]
            return round(float(np.mean(xs)), 3) if xs else None

        resumen = {k: {"before": media("before", k), "after": media("after", k)}
                   for k in ("wind_mean", "wind_p95", "damped_pct", "bright_pct")}
        imagen = None
        cand = [c for c in ev_trabajo["_candidatas"] if any(f["scene"] == c[2] and f["period"] == "after" for f in filas)]
        if cand:
            huracan = ev["category"] in ("hurricane", "cold_event")
            mejor = max(cand, key=lambda c: c[0] if huracan else c[1])
            imagen = imagen_viento(mejor[3], mejor[2], ev)
            imagen["start"] = next(f["start"] for f in filas if f["scene"] == mejor[2])
        item = {"id": ev["id"], "start": ev["start"], "radius_km": ev["radius_km"], "scenes": filas,
                "summary": resumen, "image": imagen}
        completas = sum((r["granuleName"], ev["id"]) in resultados for r in antes + despues)
        if completas == len(antes) + len(despues):       # sin fallos → a la caché (si hubo fallos, se reintenta)
            cache_ev.write_text(json.dumps(item, ensure_ascii=False), encoding="utf-8")
        salida.append(item)
    SALIDA_EV.write_text(json.dumps({"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                     "source": "Sentinel-1 Level-2 OCN (ESA/Copernicus) via NASA ASF DAAC",
                                     "events": salida}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"eventos → {SALIDA_EV.relative_to(RAIZ)} ({len(salida)})", flush=True)


# ------------------------------------------------------------------------------------------- agregación
def agregar():
    """Suma las escenas en caché por año y para todo el periodo → sar_composite.nc."""
    import xarray as xr
    acum = {a: {c: np.zeros(NY * NX) for c in CAMPOS} for a in ANIOS}
    escenas = defaultdict(int)
    for ruta in sorted(DIR_ESC.glob("*.npz")):
        with np.load(ruta) as z:
            anio = int(str(z["start"])[:4])
            if anio not in acum:
                continue
            for c in CAMPOS:
                acum[anio][c][z["idx"]] += z[c]
            escenas[anio] += 1
    golfo = mascara_golfo(LATS, LONS)

    def productos(s):
        with np.errstate(invalid="ignore", divide="ignore"):
            n = s["n"].reshape(NY, NX)
            viento = (s["viento_sum"] / s["viento_n"]).reshape(NY, NX)
            amort = (100 * s["amort_n"] / s["amort_validas"]).reshape(NY, NX)
            brillo = (100 * s["brillo_n"] / s["n"]).reshape(NY, NX)
        valido = golfo & (n >= 20)
        amort = np.where(valido & (s["amort_validas"].reshape(NY, NX) >= 20), amort, np.nan)
        return [np.where(valido, x, np.nan).astype(np.float32) for x in (viento, amort, brillo)] + [
            np.where(golfo, n, 0).astype(np.float32)]

    por_anio = [productos(acum[a]) for a in ANIOS]
    total = productos({c: sum(acum[a][c] for a in ANIOS) for c in CAMPOS})
    nombres = ("sar_wind", "sar_damped", "sar_bright", "sar_n")
    ds = xr.Dataset(
        {**{f"{v}": (("year", "lat", "lon"), np.stack([p[i] for p in por_anio])) for i, v in enumerate(nombres)},
         **{f"{v}_all": (("lat", "lon"), total[i]) for i, v in enumerate(nombres)},
         "scenes": (("year",), np.array([escenas[a] for a in ANIOS], dtype=np.int32))},
        coords={"year": ANIOS, "lat": LATS, "lon": LONS},
        attrs={"source": "Sentinel-1 Level-2 OCN (ESA/Copernicus) via NASA ASF DAAC",
               "method": f"0.1° bins; damped = sigma0_VV/sigma0_CMOD < {UMBRAL_RATIO} with ECMWF wind "
                         f"{VIENTO_MIN}-{VIENTO_MAX} m/s; bright = owiPBright > 0",
               "generated": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    for v in ds.data_vars:
        ds[v].encoding.update({"zlib": True, "complevel": 4})
    tmp = SALIDA_NC.with_suffix(".tmp.nc")
    ds.to_netcdf(tmp, engine="h5netcdf")
    tmp.replace(SALIDA_NC)
    print(f"compuesto → {SALIDA_NC.relative_to(RAIZ)} · escenas por año: {dict(escenas)}", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--por-huella", type=int, default=2, help="escenas por huella y año para el compuesto")
    ap.add_argument("--hilos", type=int, default=6, help="descargas simultáneas")
    ap.add_argument("--solo-agregar", action="store_true", help="solo rehace los productos con la caché")
    ap.add_argument("--sin-eventos", action="store_true")
    ap.add_argument("--sin-compuesto", action="store_true")
    a = ap.parse_args()
    DIR_ESC.mkdir(parents=True, exist_ok=True)
    if not a.solo_agregar:
        sesion = asf.sesion_earthdata()
        if not a.sin_eventos:
            print("Eventos (antes / después):", flush=True)
            procesar_eventos(sesion, a.hilos)
        if not a.sin_compuesto:
            print("Compuesto anual del golfo:", flush=True)
            tareas = [(e, None) for e in escenas_compuesto(a.por_huella) if not ruta_cache(e["granuleName"]).exists()]
            print(f"  por descargar: {len(tareas)}", flush=True)
            ejecutar(sesion, tareas, a.hilos, "compuesto")
    agregar()


if __name__ == "__main__":
    main()
