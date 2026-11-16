"""
Radar de apertura sintética (SAR) en la API.

Dos fuentes:

1. **Productos procesados** (scripts/build_sar.py, con token de Earthdata), en ``data/processed``:
   * ``sar_composite.nc``: mapas anuales 2017–2024 y del periodo en celdas de 0,1° a partir de Sentinel-1 OCN:
     ``sar_wind`` (viento medido por el radar, m/s), ``sar_damped`` (% de superficie amortiguada = posibles manchas
     de petróleo o películas), ``sar_bright`` (% de observaciones con objetos brillantes = barcos y plataformas) y
     ``sar_n`` (observaciones de ~1 km).
   * ``sar_events.json`` + ``sar_img/<evento>.png``: antes / después de cada evento desde 2017 y un mapa de viento.
2. **Búsqueda en vivo** en NASA ASF (sin cuenta, backend/asf.py): escenas Sentinel-1, ALOS PALSAR, UAVSAR y NISAR
   que cubren un área en un mes, con sus vistas previas públicas (servidas por un proxy con lista blanca).

Si los productos procesados no existen, la API responde ``available: false`` y la búsqueda en vivo sigue funcionando.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

import numpy as np
import requests

from . import asf
from .config import CACHE_DIR, PROCESSED_DIR
from .service import ErrorSolicitud, Seleccion, _f, _lista

SLICKS_JSON = PROCESSED_DIR / "slicks.json"      # detector de manchas NISAR (scripts/build_slicks.py)
SLICKS_DIR = PROCESSED_DIR / "slicks"
_RE_ESCENA = re.compile(r"^[A-Za-z0-9_]{10,160}$")
SAR_NC = PROCESSED_DIR / "sar_composite.nc"
SAR_EVENTOS = PROCESSED_DIR / "sar_events.json"
SAR_IMG = PROCESSED_DIR / "sar_img"
CACHE_BUSQUEDA = CACHE_DIR / "sar" / "busquedas"
CACHE_VISTAS = CACHE_DIR / "sar" / "vistas"
VARS_SAR = ("sar_damped", "sar_bright", "sar_wind", "sar_n")
TTL_BUSQUEDA_S = 7 * 86400
MAX_VISTA_BYTES = 12 * 1024 * 1024


@lru_cache(maxsize=1)
def _compuesto():
    """Carga sar_composite.nc en memoria (o None si no se ha generado)."""
    if not SAR_NC.exists():
        return None
    import xarray as xr
    with xr.open_dataset(SAR_NC, engine="h5netcdf") as ds:
        datos = {k: ds[k].values for k in ds.data_vars}
        datos.update(years=[int(y) for y in ds["year"].values], lats=ds["lat"].values.astype(float),
                     lons=ds["lon"].values.astype(float), attrs=dict(ds.attrs))
    return datos


@lru_cache(maxsize=1)
def _eventos() -> dict:
    if not SAR_EVENTOS.exists():
        return {}
    contenido = json.loads(SAR_EVENTOS.read_text(encoding="utf-8"))
    return {e["id"]: e for e in contenido.get("events", [])}


@lru_cache(maxsize=1)
def _manchas() -> dict | None:
    if not SLICKS_JSON.exists():
        return None
    return json.loads(SLICKS_JSON.read_text(encoding="utf-8"))


def manchas() -> dict:
    """Detector de manchas (NISAR banda L): escenas procesadas y zonas de superficie amortiguada detectadas."""
    m = _manchas()
    if m is None:
        return {"available": False, "scenes": []}
    escenas = [{**{k: v for k, v in e.items() if k != "image"}, "image": f"/api/sar/slicks/{e['scene']}.png"}
               for e in m["scenes"]]
    return {"available": True, "source": m.get("source"), "method": m.get("method"), "generated": m.get("generated"),
            "scenes": escenas}


def imagen_mancha(escena: str) -> bytes:
    m = _manchas()
    if not _RE_ESCENA.match(escena) or m is None or not any(e["scene"] == escena for e in m["scenes"]):
        raise ErrorSolicitud("Escena NISAR desconocida")
    ruta = SLICKS_DIR / f"{escena}.png"
    if not ruta.exists():
        raise ErrorSolicitud("Imagen no disponible")
    return ruta.read_bytes()


def meta() -> dict:
    c = _compuesto()
    mm = _manchas()
    base = {"missions": {k: {"from": v["desde"], "to": v.get("hasta")} for k, v in asf.MISIONES.items()},
            "events": sorted(k for k, e in _eventos().items() if e.get("scenes")),   # solo con escenas útiles
            "slicks": {"available": mm is not None, "scenes": len(mm["scenes"]) if mm else 0,
                       "detections": sum(len(e["detections"]) for e in mm["scenes"]) if mm else 0}}
    if c is None:
        return {"available": False, **base}
    return {"available": True, "years": c["years"], "scenes": [int(x) for x in c["scenes"]], "res": 0.1,
            "source": c["attrs"].get("source"), "method": c["attrs"].get("method"),
            "generated": c["attrs"].get("generated"), **base}


def _requiere():
    c = _compuesto()
    if c is None:
        raise FileNotFoundError("Productos SAR no generados: ejecuta scripts/build_sar.py (requiere token Earthdata).")
    return c


def grid(var: str, anio: int | None) -> dict:
    """Mapa SAR de un año (o de todo el periodo si `anio` es None) con el mismo formato que /api/grid."""
    if var not in VARS_SAR:
        raise ErrorSolicitud(f"Variable SAR desconocida: {var}")
    c = _requiere()
    if anio is None:
        a, etiqueta = c[f"{var}_all"], "all"
    elif anio in c["years"]:
        a, etiqueta = c[var][c["years"].index(anio)], anio
    else:
        a, etiqueta = np.full((c["lats"].size, c["lons"].size), np.nan), anio
    out = {"var": var, "year": etiqueta, "lats": _lista(c["lats"], 3), "lons": _lista(c["lons"], 3),
           "values": _lista(a, 2), "res": 0.1}
    if anio is not None and anio not in c["years"]:
        out["note"] = "no_sar_year"
    else:
        out["scenes"] = int(c["scenes"].sum() if anio is None else c["scenes"][c["years"].index(anio)])
    return out


def area(sel: Seleccion) -> dict:
    """Valores SAR del área por año y del periodo (media ponderada por número de observaciones)."""
    from .geo import puntos_en_poligono
    c = _requiere()
    lon2, lat2 = np.meshgrid(c["lons"], c["lats"])
    m = puntos_en_poligono(lon2, lat2, sel.poligono)
    if not m.any():
        la, lo = sel.centro
        d = (lat2 - la) ** 2 + (lon2 - lo) ** 2
        m[np.unravel_index(np.argmin(d), d.shape)] = True

    def resumen(n, viento, amort, brillo):
        w = np.where(m & np.isfinite(viento), n, 0.0)
        if w.sum() == 0:
            return {"n": 0, "wind": None, "damped_pct": None, "bright_pct": None}
        pond = lambda x: _f(np.nansum(np.where(m & np.isfinite(x), x * n, 0)) / max(np.sum(np.where(m & np.isfinite(x), n, 0)), 1), 2)  # noqa: E731
        return {"n": int(np.sum(np.where(m, n, 0))), "wind": pond(viento), "damped_pct": pond(amort), "bright_pct": pond(brillo)}

    filas = [{"year": y, **resumen(c["sar_n"][i], c["sar_wind"][i], c["sar_damped"][i], c["sar_bright"][i])}
             for i, y in enumerate(c["years"])]
    total = resumen(c["sar_n_all"], c["sar_wind_all"], c["sar_damped_all"], c["sar_bright_all"])
    return {"cells": int(m.sum()), "years": filas, "all": total, "method": c["attrs"].get("method")}


def evento(ev_id: str) -> dict:
    e = _eventos().get(ev_id)
    if e is None:
        raise ErrorSolicitud(f"Sin análisis SAR para el evento: {ev_id}")
    out = dict(e)
    if e.get("image"):
        out["image"] = {**e["image"], "url": f"/api/sar/events/{ev_id}/image.png"}
    return out


def imagen_evento(ev_id: str) -> bytes:
    if ev_id not in _eventos() or not (SAR_IMG / f"{ev_id}.png").exists():
        raise ErrorSolicitud(f"Sin imagen SAR para el evento: {ev_id}")
    return (SAR_IMG / f"{ev_id}.png").read_bytes()


# --------------------------------------------------------------------------------- búsqueda en vivo (sin cuenta)
def _mes_rango(mes: str, meses: int):
    y, m = int(mes[:4]), int(mes[5:7])
    m2 = m + meses
    y2, m2 = y + (m2 - 1) // 12, (m2 - 1) % 12 + 1
    return f"{y:04d}-{m:02d}-01T00:00:00Z", f"{y2:04d}-{m2:02d}-01T00:00:00Z"


def escenas(sel: Seleccion, mes: str, meses: int = 1, por_mision: int = 12) -> dict:
    """Escenas SAR de todas las misiones que cubren la selección entre `mes` y `mes + meses`."""
    if not (1 <= meses <= 3):
        raise ErrorSolicitud("meses debe estar entre 1 y 3")
    inicio, fin = _mes_rango(mes, meses)
    area_wkt = asf.wkt(sel.poligono)
    clave = hashlib.sha1(f"{area_wkt}|{inicio}|{fin}|{por_mision}".encode()).hexdigest()
    ruta = CACHE_BUSQUEDA / f"{clave}.json"
    if ruta.exists() and time.time() - ruta.stat().st_mtime < TTL_BUSQUEDA_S:
        return json.loads(ruta.read_text(encoding="utf-8"))

    def una(nombre_param):
        nombre, p = nombre_param
        if inicio[:7] < p["desde"] or (p.get("hasta") and inicio[:7] > p["hasta"]):
            return nombre, [], 0
        params = {k: v for k, v in p.items() if k in ("platform", "processingLevel")}
        try:
            res = asf.buscar(**params, intersectsWith=area_wkt, start=inicio, end=fin, maxResults=200)
        except requests.RequestException:
            return nombre, None, 0
        # Pares interferométricos (UAVSAR): la fecha útil es la adquisición que cae dentro del periodo buscado
        def fecha_util(r):
            for clave in ("startTime", "stopTime"):
                f = (r.get(clave) or "")[:19] + "Z"
                if inicio <= f < fin:
                    return f
            return None
        res = sorted(((fecha_util(r), r) for r in res if fecha_util(r)), key=lambda x: x[0])
        paso = max(1, len(res) // por_mision)
        return nombre, [{**asf.escena_publica(r), "start": f} for f, r in res[::paso][:por_mision]], len(res)

    with ThreadPoolExecutor(max_workers=4) as ex:
        resultados = list(ex.map(una, asf.MISIONES.items()))
    salida = {"from": inicio[:10], "to": fin[:10], "missions": {}}
    completo = True
    for nombre, lista, total in resultados:
        if lista is None:
            completo = False
            salida["missions"][nombre] = {"error": True, "total": 0, "scenes": []}
        else:
            salida["missions"][nombre] = {"total": total, "scenes": lista}
    if completo:
        CACHE_BUSQUEDA.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps(salida, ensure_ascii=False), encoding="utf-8")
    return salida


def vista_previa(url: str, ancho: int = 900, transparente: bool = False) -> tuple[bytes, str]:
    """Descarga (con caché) una vista previa pública de ASF; opcionalmente reduce tamaño y hace transparente el
    fondo negro (para superponerla al mapa). Solo URLs de los servidores de vistas previas de ASF."""
    if not asf.vista_previa_permitida(url):
        raise ErrorSolicitud("URL de vista previa no permitida")
    ancho = int(min(max(ancho, 120), 1600))
    clave = hashlib.sha1(f"{url}|{ancho}|{transparente}".encode()).hexdigest()
    ext = "png" if transparente else "jpg"
    ruta = CACHE_VISTAS / f"{clave}.{ext}"
    tipo = "image/png" if transparente else "image/jpeg"
    if ruta.exists():
        return ruta.read_bytes(), tipo
    r = requests.get(url, headers=asf.AGENTE, timeout=60, stream=True)
    r.raise_for_status()
    datos = r.raw.read(MAX_VISTA_BYTES + 1, decode_content=True)
    if len(datos) > MAX_VISTA_BYTES:
        raise ErrorSolicitud("Vista previa demasiado grande")
    from PIL import Image
    img = Image.open(io.BytesIO(datos))
    img.thumbnail((ancho, ancho * 4))
    buf = io.BytesIO()
    if transparente:
        rgba = np.array(img.convert("RGBA"))
        negro = rgba[..., :3].max(axis=2) < 12
        rgba[negro, 3] = 0
        Image.fromarray(rgba, "RGBA").save(buf, "PNG", optimize=True)
    else:
        img.convert("RGB").save(buf, "JPEG", quality=85)
    CACHE_VISTAS.mkdir(parents=True, exist_ok=True)
    ruta.write_bytes(buf.getvalue())
    return buf.getvalue(), tipo
