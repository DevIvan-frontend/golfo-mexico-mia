"""
Consulta en vivo a la API de OBIS (biodiversidad marina) con caché en disco.

Importante: el número de registros refleja el ESFUERZO DE MUESTREO (campañas, museos, censos), no la abundancia real.
"""
from __future__ import annotations

import hashlib
import json
import time

import requests

from .config import CACHE_DIR, OBIS_API, OBIS_CACHE_DAYS

_HTTP = requests.Session()
_HTTP.headers["User-Agent"] = "golfo-mexico-mia-app/1.0"


def _consulta(ruta: str, params: dict) -> dict | list:
    clave = hashlib.sha1((ruta + json.dumps(params, sort_keys=True)).encode()).hexdigest()
    cache = CACHE_DIR / "obis" / f"{clave}.json"
    if cache.exists() and time.time() - cache.stat().st_mtime < OBIS_CACHE_DAYS * 86400:
        return json.loads(cache.read_text(encoding="utf-8"))
    r = _HTTP.get(f"{OBIS_API}/{ruta}", params=params, timeout=60)
    r.raise_for_status()
    datos = r.json()
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(datos), encoding="utf-8")
    return datos


CAMPOS = ("scientificName", "taxonRank", "kingdom", "phylum", "class", "order", "family", "records", "category")


def fauna(wkt: str, year: int | None, size: int = 15) -> dict:
    """Resumen de biodiversidad del área: registros/especies, especies más registradas y especies en Lista Roja UICN."""
    params = {"geometry": wkt}
    if year:
        params.update(startdate=f"{year}-01-01", enddate=f"{year}-12-31")
    try:
        est = _consulta("statistics", params)
        lista = _consulta("checklist", {**params, "size": size})
        roja = _consulta("checklist/redlist", {"geometry": wkt, "size": 50})
        anual = _consulta("statistics/years", {"geometry": wkt})
    except requests.RequestException as err:
        return {"available": False, "error": f"OBIS no disponible: {type(err).__name__}"}
    filtrar = lambda r: {k: r.get(k) for k in CAMPOS if r.get(k) is not None}  # noqa: E731
    return {
        "available": True, "year": year,
        "records": est.get("records"), "species": est.get("species"), "taxa": est.get("taxa"),
        "datasets": est.get("datasets"),
        "top": [filtrar(r) for r in lista.get("results", [])],
        "redlist_total": roja.get("total"),
        "redlist": [filtrar(r) for r in roja.get("results", [])],
        "by_year": [{"year": d["year"], "records": d["records"]} for d in anual if d.get("year") and d["year"] >= 1990],
        "source": "OBIS — Ocean Biodiversity Information System (https://obis.org), API v3",
    }
