"""
Carga los datos procesados (data/processed + data/events.json + data/places.json) en una base de datos SQL.

  python scripts/load_to_sql.py                                   # SQLite en data/golfo.sqlite
  DATABASE_URL=postgresql+psycopg://user:pass@host/golfo python scripts/load_to_sql.py

Después arranca la API con GOLFO_DATA_BACKEND=sql.
"""
from __future__ import annotations

import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.config import CLIM_YEARS, DATABASE_URL, EVENTS_FILE, PLACES_FILE, PROCESSED_DIR  # noqa: E402
from backend.db import models as M  # noqa: E402
from backend.repositories.file_repository import FileRepository  # noqa: E402


def main():
    t0 = time.time()
    repo = FileRepository(PROCESSED_DIR, EVENTS_FILE, PLACES_FILE)
    ej = repo.axes()
    engine = create_engine(DATABASE_URL, future=True)
    M.metadata.drop_all(engine)
    M.metadata.create_all(engine)
    print("Base de datos:", engine.url.render_as_string(hide_password=True))

    iy, ix = np.nonzero(repo.ocean_mask())
    celdas = pd.DataFrame({"cell_id": np.arange(iy.size), "iy": iy, "ix": ix,
                           "lat": ej.lats[iy], "lon": ej.lons[ix]})
    ejes = pd.concat([pd.DataFrame({"axis": "lat", "idx": range(ej.lats.size), "value": ej.lats}),
                      pd.DataFrame({"axis": "lon", "idx": range(ej.lons.size), "value": ej.lons})])
    meses = pd.DataFrame({"month_idx": range(len(ej.months)), "month": ej.months})

    sst = np.stack([repo.month_grid("sst", k)[iy, ix] for k in range(len(ej.months))])
    chl = np.stack([repo.month_grid("chl", k)[iy, ix] for k in range(len(ej.months))])
    obs = pd.DataFrame({"month_idx": np.repeat(np.arange(len(ej.months)), iy.size),
                        "cell_id": np.tile(celdas["cell_id"].values, len(ej.months)),
                        "sst": sst.ravel(), "chl": chl.ravel()}).dropna(subset=["sst", "chl"], how="all")

    clim = pd.DataFrame({"cell_id": np.tile(celdas["cell_id"].values, 12),
                         "month_of_year": np.repeat(np.arange(1, 13), iy.size),
                         "sst": np.concatenate([repo.climatology("sst", k)[iy, ix] for k in range(1, 13)]),
                         "logchl": np.concatenate([repo.climatology("logchl", k)[iy, ix] for k in range(1, 13)])})

    b = repo.bathymetry()
    by, bx = np.meshgrid(np.arange(b.lats.size), np.arange(b.lons.size), indexing="ij")
    bat = pd.DataFrame({"iy": by.ravel(), "ix": bx.ravel(), "lat": b.lats[by.ravel()], "lon": b.lons[bx.ravel()],
                        "altitude": b.altitude.ravel(), "depth": b.depth.ravel()})

    obis = pd.DataFrame([{"year": int(y), "geojson": json.dumps(repo.obis_grid(int(y)))}
                         for y in sorted({int(m[:4]) for m in ej.months})])
    eventos = pd.DataFrame([{"id": e["id"], "start": e["start"], "data": json.dumps(e, ensure_ascii=False)}
                            for e in repo.events()])
    lugares = pd.DataFrame([{"id": p["id"], "data": json.dumps(p, ensure_ascii=False)} for p in repo.places()])
    meta = pd.DataFrame([{"key": "manifest", "value": json.dumps(repo.manifest(), ensure_ascii=False)},
                         {"key": "clim_years", "value": json.dumps(CLIM_YEARS)}])

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for nombre, df in (("cells", celdas), ("grid_axes", ejes), ("months", meses), ("ocean_monthly", obs),
                           ("climatology", clim), ("bathymetry", bat), ("obis_grid", obis), ("events", eventos),
                           ("places", lugares), ("meta", meta)):
            df.to_sql(nombre, engine, if_exists="append", index=False, chunksize=20000)   # executemany (portable)
            print(f"   ✅ {nombre}: {len(df):,} filas")
    print(f"Listo en {time.time() - t0:.0f} s. Arranca la API con GOLFO_DATA_BACKEND=sql")


if __name__ == "__main__":
    main()
