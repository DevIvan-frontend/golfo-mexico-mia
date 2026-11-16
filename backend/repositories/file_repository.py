"""Repositorio basado en archivos (NetCDF + JSON) generados por scripts/build_dataset.py."""
from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import xarray as xr

from ..config import CLIM_YEARS
from .base import Batimetria, DataRepository, Ejes


class FileRepository(DataRepository):
    def __init__(self, processed_dir: Path, events_file: Path, places_file: Path):
        ocean = processed_dir / "ocean_monthly.nc"
        if not ocean.exists():
            raise FileNotFoundError(f"No existe {ocean}. Ejecuta primero: python scripts/build_dataset.py")
        with xr.open_dataset(ocean, engine="h5netcdf") as ds:
            ds = ds.load()
        self._ejes = Ejes(lats=ds["lat"].values.astype(float), lons=ds["lon"].values.astype(float),
                          months=[str(m) for m in ds["month"].values])
        self._datos = {"sst": ds["sst"].values.astype("float32"), "chl": ds["chl"].values.astype("float32")}
        self._oceano = np.isfinite(self._datos["sst"]).any(axis=0) | np.isfinite(self._datos["chl"]).any(axis=0)

        anios = np.array([int(m[:4]) for m in self._ejes.months])
        moy = np.array([int(m[5:7]) for m in self._ejes.months])
        en_clim = (anios >= CLIM_YEARS[0]) & (anios <= CLIM_YEARS[1])
        with np.errstate(divide="ignore", invalid="ignore"), warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)   # celdas de tierra: media de cortes vacíos
            logchl = np.log10(self._datos["chl"])
            self._clim = {
                "sst": np.stack([np.nanmean(self._datos["sst"][en_clim & (moy == k)], axis=0) for k in range(1, 13)]),
                "logchl": np.stack([np.nanmean(logchl[en_clim & (moy == k)], axis=0) for k in range(1, 13)]),
            }

        with xr.open_dataset(processed_dir / "bathymetry.nc", engine="h5netcdf") as b:
            b = b.load()
        self._bat = Batimetria(lats=b["lat"].values.astype(float), lons=b["lon"].values.astype(float),
                               depth=b["depth"].values.astype("float32"), altitude=b["altitude"].values.astype("float32"))
        obis = processed_dir / "obis_grid.json"
        self._obis = json.loads(obis.read_text(encoding="utf-8")) if obis.exists() else {}
        self._events = json.loads(events_file.read_text(encoding="utf-8")) if events_file.exists() else []
        self._places = json.loads(places_file.read_text(encoding="utf-8")) if places_file.exists() else []
        man = processed_dir / "manifest.json"
        self._manifest = json.loads(man.read_text(encoding="utf-8")) if man.exists() else {}

    def axes(self) -> Ejes:
        return self._ejes

    def ocean_mask(self) -> np.ndarray:
        return self._oceano

    def month_grid(self, var: str, month_idx: int) -> np.ndarray:
        return self._datos[var][month_idx]

    def series(self, var: str, iy: np.ndarray, ix: np.ndarray) -> np.ndarray:
        return self._datos[var][:, iy, ix]

    def climatology(self, var: str, month_of_year: int) -> np.ndarray:
        return self._clim[var][month_of_year - 1]

    def bathymetry(self) -> Batimetria:
        return self._bat

    def obis_grid(self, year: int) -> dict:
        return self._obis.get(str(year), {"type": "FeatureCollection", "features": []})

    def events(self) -> list[dict]:
        return self._events

    def places(self) -> list[dict]:
        return self._places

    def manifest(self) -> dict:
        return self._manifest
