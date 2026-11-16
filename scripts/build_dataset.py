"""
Construye el conjunto de datos procesado del Golfo de México a partir de fuentes oficiales y abiertas.

Fuentes (todas reales, sin datos simulados):
  * TSM mensual  : NASA JPL MUR SST v4.1 (jplMURSST41mday) — vía NOAA CoastWatch ERDDAP
  * Clorofila-a  : NASA MODIS-Aqua L3 mensual R2022 (erdMH1chlamday_R2022SQ) — vía NOAA CoastWatch ERDDAP
  * Batimetría   : NOAA ETOPO1 (etopo180) — vía NOAA CoastWatch ERDDAP
  * Biodiversidad: OBIS (Ocean Biodiversity Information System) — API v3, registros por celda geohash

Salidas en data/processed/:
  ocean_monthly.nc   (sst, chl) dims (month, lat, lon) en malla de 0.25°
  bathymetry.nc      (depth) en malla de 1/12°
  obis_grid.json     {año: GeoJSON FeatureCollection con n registros por celda}
  manifest.json      procedencia (servidores, conjuntos, fechas de descarga)

Uso:
  python scripts/build_dataset.py                 # todo 2003-2024
  python scripts/build_dataset.py --years 2009 2011
Cada año se guarda en data/raw/ como caché: si se interrumpe, al relanzar continúa donde quedó.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import numpy as np
import pandas as pd
import requests
import xarray as xr
from requests.adapters import HTTPAdapter
from scipy import ndimage
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.config import BBOX, GRID_RES, BATHY_RES, PROCESSED_DIR, RAW_DIR, YEAR_START, YEAR_END  # noqa: E402
from backend.geo import mascara_golfo  # noqa: E402

ERDDAP_SERVERS = ["https://coastwatch.pfeg.noaa.gov/erddap", "https://upwell.pfeg.noaa.gov/erddap"]
FUENTES = {
    "sst": {"ids": ["jplMURSST41mday"], "var": "sst", "stride": 25, "offset": True,
            "nombre": "NASA JPL MUR SST v4.1, compuesto mensual (0.01°)"},
    "chl": {"ids": ["erdMH1chlamday_R2022SQ", "erdMH1chlamday_R2022NRT"], "var": "chlor_a", "stride": 3, "offset": False,
            "nombre": "NASA MODIS-Aqua clorofila-a L3 mensual R2022 (4 km)"},
}
OBIS_API = "https://api.obis.org/v3"


def sesion() -> requests.Session:
    s = requests.Session()
    s.mount("https://", HTTPAdapter(max_retries=Retry(total=3, backoff_factor=2,
                                                      status_forcelist=(429, 500, 502, 503, 504),
                                                      allowed_methods=frozenset(["GET"]))))
    s.headers["User-Agent"] = "golfo-mexico-mia-app/1.0 (data pipeline)"
    return s


HTTP = sesion()
LAT_EDGES = np.round(np.arange(BBOX["south"], BBOX["north"] + GRID_RES / 2, GRID_RES), 4)
LON_EDGES = np.round(np.arange(BBOX["west"], BBOX["east"] + GRID_RES / 2, GRID_RES), 4)
LATS = (LAT_EDGES[:-1] + LAT_EDGES[1:]) / 2
LONS = (LON_EDGES[:-1] + LON_EDGES[1:]) / 2


def erddap_csv(dsid: str, consulta: str) -> pd.DataFrame | None:
    for servidor in ERDDAP_SERVERS:
        url = f"{servidor}/griddap/{dsid}.csv?{quote(consulta, safe='():,.-')}"
        try:
            r = HTTP.get(url, timeout=300)
        except requests.RequestException as err:
            print(f"      {servidor}: {type(err).__name__}")
            continue
        if r.ok:
            return pd.read_csv(io.StringIO(r.text), skiprows=[1])
        print(f"      {servidor}: HTTP {r.status_code}")
    return None


def anio_variable(clave: str, anio: int) -> pd.DataFrame | None:
    """Descarga 12 meses de una variable y los agrega a la malla de 0.25° (media por celda y mes)."""
    cache = RAW_DIR / f"{clave}_{anio}.csv.gz"
    if cache.exists():
        return pd.read_csv(cache)
    f = FUENTES[clave]
    off = GRID_RES / 2 if f["offset"] else 0.0
    s, n = BBOX["south"] + off, BBOX["north"] - off
    w, e = BBOX["west"] + off, BBOX["east"] - off
    for dsid in f["ids"]:
        for orden in ((s, n), (n, s)):   # algunos conjuntos tienen la latitud descendente
            consulta = (f"{f['var']}[({anio}-01-10):1:({anio}-12-20)]"
                        f"[({orden[0]}):{f['stride']}:({orden[1]})][({w}):{f['stride']}:({e})]")
            df = erddap_csv(dsid, consulta)
            if df is None or df.empty:
                continue
            df["time"] = pd.to_datetime(df["time"])
            df = df[df["time"].dt.year == anio].dropna(subset=[f["var"]])
            df["mes"] = df["time"].dt.strftime("%Y-%m")
            df["iy"] = np.floor((df["latitude"] - BBOX["south"]) / GRID_RES).astype(int)
            df["ix"] = np.floor((df["longitude"] - BBOX["west"]) / GRID_RES).astype(int)
            df = df[(df.iy >= 0) & (df.iy < LATS.size) & (df.ix >= 0) & (df.ix < LONS.size)]
            agg = df.groupby(["mes", "iy", "ix"])[f["var"]].mean().rename("valor").reset_index()
            agg["fuente"] = dsid
            agg.to_csv(cache, index=False)
            return agg
    return None


def construir_oceano(anios: list[int]) -> xr.Dataset:
    meses = [f"{y}-{m:02d}" for y in anios for m in range(1, 13)]
    idx_mes = {m: i for i, m in enumerate(meses)}
    datos, usados = {}, {}
    for clave in FUENTES:
        arr = np.full((len(meses), LATS.size, LONS.size), np.nan, dtype="float32")
        usados[clave] = set()
        for y in anios:
            t0 = time.time()
            agg = anio_variable(clave, y)
            if agg is None:
                print(f"   ❌ {clave} {y}: sin datos (servidores no disponibles o fuera de cobertura)")
                continue
            k = agg["mes"].map(idx_mes).values
            arr[k, agg["iy"].values, agg["ix"].values] = agg["valor"].values
            usados[clave].update(agg["fuente"].unique())
            print(f"   ✅ {clave} {y}: {agg['mes'].nunique()} meses, {len(agg):,} celdas-mes ({time.time() - t0:.0f} s)")
        datos[clave] = arr
    # Solo el Golfo de México (fuera Caribe y Atlántico) y solo agua conectada con el mar (fuera lagos y presas)
    golfo = mascara_golfo(LATS, LONS)
    agua = np.zeros((LATS.size, LONS.size), dtype=bool)
    for a in datos.values():
        a[:, ~golfo] = np.nan
        agua |= np.isfinite(a).any(axis=0)
    etiquetas, _ = ndimage.label(agua, structure=np.ones((3, 3), dtype=int))
    tam = np.bincount(etiquetas.ravel()); tam[0] = 0
    oceano = etiquetas == tam.argmax()
    for a in datos.values():
        a[:, ~oceano] = np.nan
    print(f"   Máscara oceánica: {int(oceano.sum())} celdas; eliminadas {int((agua & ~oceano).sum())} de agua continental")
    ds = xr.Dataset({k: (("month", "lat", "lon"), v) for k, v in datos.items()},
                    coords={"month": meses, "lat": LATS, "lon": LONS})
    ds.attrs["fuentes_usadas"] = json.dumps({k: sorted(v) for k, v in usados.items()})
    return ds


def construir_batimetria() -> xr.Dataset:
    destino = PROCESSED_DIR / "bathymetry.nc"
    paso = int(round(BATHY_RES * 60))   # ETOPO1 = 1 minuto de arco
    consulta = (f"altitude[({BBOX['south']}):{paso}:({BBOX['north']})]"
                f"[({BBOX['west']}):{paso}:({BBOX['east']})]")
    df = erddap_csv("etopo180", consulta)
    if df is None:
        raise RuntimeError("No se pudo descargar ETOPO (etopo180) de ningún servidor ERDDAP.")
    tabla = df.pivot(index="latitude", columns="longitude", values="altitude").sort_index()
    alt = tabla.values.astype("float32")
    profundidad = np.where(alt < 0, -alt, np.nan).astype("float32")   # metros positivos hacia abajo; tierra = NaN
    profundidad[~mascara_golfo(tabla.index.values, tabla.columns.values)] = np.nan   # fuera del golfo
    ds = xr.Dataset({"depth": (("lat", "lon"), profundidad), "altitude": (("lat", "lon"), alt)},
                    coords={"lat": tabla.index.values, "lon": tabla.columns.values})
    ds.to_netcdf(destino, engine="h5netcdf")
    print(f"   ✅ Batimetría ETOPO1: {profundidad.shape}, prof. máx {np.nanmax(profundidad):.0f} m")
    return ds


def construir_obis(anios: list[int]) -> dict:
    wkt = (f"POLYGON(({BBOX['west']} {BBOX['south']},{BBOX['east']} {BBOX['south']},"
           f"{BBOX['east']} {BBOX['north']},{BBOX['west']} {BBOX['north']},{BBOX['west']} {BBOX['south']}))")
    salida = {}
    for y in anios:
        cache = RAW_DIR / f"obis_grid_{y}.json"
        if cache.exists():
            salida[str(y)] = json.loads(cache.read_text(encoding="utf-8"))
            continue
        try:
            r = HTTP.get(f"{OBIS_API}/occurrence/grid/3", timeout=180,
                         params={"geometry": wkt, "startdate": f"{y}-01-01", "enddate": f"{y}-12-31"})
            r.raise_for_status()
            fc = r.json()
            cache.write_text(json.dumps(fc), encoding="utf-8")
            salida[str(y)] = fc
            print(f"   ✅ OBIS {y}: {len(fc.get('features', []))} celdas")
        except requests.RequestException as err:
            print(f"   ❌ OBIS {y}: {err}")
    return salida


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--years", nargs=2, type=int, default=[YEAR_START, YEAR_END], metavar=("INICIO", "FIN"))
    args = ap.parse_args()
    anios = list(range(args.years[0], args.years[1] + 1))
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    print("1/3 Batimetría (NOAA ETOPO1)")
    construir_batimetria()
    print(f"2/3 TSM y clorofila mensuales {anios[0]}–{anios[-1]}")
    ds = construir_oceano(anios)
    ds.to_netcdf(PROCESSED_DIR / "ocean_monthly.nc", engine="h5netcdf")
    print("3/3 Biodiversidad OBIS por año")
    obis = construir_obis(anios)
    (PROCESSED_DIR / "obis_grid.json").write_text(json.dumps(obis), encoding="utf-8")

    manifest = {
        "generado_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "bbox": BBOX, "resolucion_grados": GRID_RES, "resolucion_batimetria_grados": BATHY_RES,
        "meses": [str(ds["month"].values[0]), str(ds["month"].values[-1])],
        "servidores_erddap": ERDDAP_SERVERS,
        "fuentes": {
            "sst": FUENTES["sst"]["nombre"], "chl": FUENTES["chl"]["nombre"],
            "depth": "NOAA ETOPO1 Global Relief Model (etopo180)", "obis": "OBIS API v3 /occurrence/grid/3",
        },
        "conjuntos_erddap_usados": json.loads(ds.attrs["fuentes_usadas"]),
        "metodo": "Muestreo ERDDAP con salto (stride) y media por celda de 0.25°; solo agua conectada al océano.",
    }
    (PROCESSED_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print("✅ Listo:", PROCESSED_DIR)


if __name__ == "__main__":
    main()
