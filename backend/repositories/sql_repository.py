"""
Repositorio SQL (SQLAlchemy). Funciona con SQLite (por defecto) y PostgreSQL/PostGIS cambiando DATABASE_URL.

Carga de datos:  python scripts/load_to_sql.py          (lee data/processed y data/*.json)
Uso en la API:   GOLFO_DATA_BACKEND=sql  [DATABASE_URL=postgresql+psycopg://usuario:clave@host/golfo]
"""
from __future__ import annotations

import json
from functools import lru_cache

import numpy as np
from sqlalchemy import create_engine, select

from ..db import models as M
from .base import Batimetria, DataRepository, Ejes


class SQLRepository(DataRepository):
    def __init__(self, database_url: str):
        self.engine = create_engine(database_url, future=True)
        with self.engine.connect() as c:
            ejes = c.execute(select(M.grid_axes.c.axis, M.grid_axes.c.idx, M.grid_axes.c.value)).all()
            meses = c.execute(select(M.months.c.month).order_by(M.months.c.month_idx)).scalars().all()
            celdas = c.execute(select(M.cells.c.cell_id, M.cells.c.iy, M.cells.c.ix)).all()
        if not meses:
            raise RuntimeError("La base de datos está vacía. Ejecuta: python scripts/load_to_sql.py")
        lats = np.array([v for a, i, v in sorted(ejes, key=lambda r: r[1]) if a == "lat"])
        lons = np.array([v for a, i, v in sorted(ejes, key=lambda r: r[1]) if a == "lon"])
        self._ejes = Ejes(lats=lats, lons=lons, months=list(meses))
        self._oceano = np.zeros((lats.size, lons.size), dtype=bool)
        self._cell_id = np.full((lats.size, lons.size), -1, dtype=np.int64)
        for cid, iy, ix in celdas:
            self._oceano[iy, ix] = True
            self._cell_id[iy, ix] = cid
        self._pos = {cid: (iy, ix) for cid, iy, ix in celdas}

    # --- utilidades
    def _vacio(self):
        return np.full((self._ejes.lats.size, self._ejes.lons.size), np.nan, dtype="float32")

    def axes(self) -> Ejes:
        return self._ejes

    def ocean_mask(self) -> np.ndarray:
        return self._oceano

    def month_grid(self, var: str, month_idx: int) -> np.ndarray:
        col = M.ocean_monthly.c[var]
        q = select(M.ocean_monthly.c.cell_id, col).where(M.ocean_monthly.c.month_idx == int(month_idx))
        out = self._vacio()
        with self.engine.connect() as c:
            for cid, v in c.execute(q):
                if v is not None:
                    out[self._pos[cid]] = v
        return out

    def series(self, var: str, iy: np.ndarray, ix: np.ndarray) -> np.ndarray:
        ids = self._cell_id[iy, ix]
        columna = {int(cid): j for j, cid in enumerate(ids)}
        out = np.full((len(self._ejes.months), len(ids)), np.nan, dtype="float32")
        col = M.ocean_monthly.c[var]
        with self.engine.connect() as c:
            for lote in np.array_split(ids, max(1, len(ids) // 500 + 1)):
                q = (select(M.ocean_monthly.c.month_idx, M.ocean_monthly.c.cell_id, col)
                     .where(M.ocean_monthly.c.cell_id.in_([int(x) for x in lote])))
                for k, cid, v in c.execute(q):
                    if v is not None:
                        out[k, columna[cid]] = v
        return out

    def climatology(self, var: str, month_of_year: int) -> np.ndarray:
        return self._climatologia(var, int(month_of_year))   # int(): los drivers SQL no aceptan numpy.int64

    @lru_cache(maxsize=24)
    def _climatologia(self, var: str, month_of_year: int) -> np.ndarray:
        col = M.climatology.c[var]
        q = select(M.climatology.c.cell_id, col).where(M.climatology.c.month_of_year == month_of_year)
        out = self._vacio()
        with self.engine.connect() as c:
            for cid, v in c.execute(q):
                if v is not None:
                    out[self._pos[cid]] = v
        return out

    @lru_cache(maxsize=1)
    def bathymetry(self) -> Batimetria:
        with self.engine.connect() as c:
            filas = c.execute(select(M.bathymetry.c.iy, M.bathymetry.c.ix, M.bathymetry.c.lat, M.bathymetry.c.lon,
                                     M.bathymetry.c.altitude, M.bathymetry.c.depth)).all()
        ny, nx = max(r[0] for r in filas) + 1, max(r[1] for r in filas) + 1
        lats, lons = np.zeros(ny), np.zeros(nx)
        alt = np.full((ny, nx), np.nan, dtype="float32"); dep = alt.copy()
        for iy, ix, la, lo, a, d in filas:
            lats[iy], lons[ix] = la, lo
            alt[iy, ix] = np.nan if a is None else a
            dep[iy, ix] = np.nan if d is None else d
        return Batimetria(lats=lats, lons=lons, depth=dep, altitude=alt)

    def obis_grid(self, year: int) -> dict:
        with self.engine.connect() as c:
            txt = c.execute(select(M.obis_grid.c.geojson).where(M.obis_grid.c.year == year)).scalar()
        return json.loads(txt) if txt else {"type": "FeatureCollection", "features": []}

    def events(self) -> list[dict]:
        with self.engine.connect() as c:
            return [json.loads(t) for t in c.execute(select(M.events.c.data).order_by(M.events.c.start)).scalars()]

    def places(self) -> list[dict]:
        with self.engine.connect() as c:
            return [json.loads(t) for t in c.execute(select(M.places.c.data)).scalars()]

    def manifest(self) -> dict:
        with self.engine.connect() as c:
            txt = c.execute(select(M.meta.c.value).where(M.meta.c.key == "manifest")).scalar()
        return json.loads(txt) if txt else {}
