"""Configuración central. Todo se puede sobrescribir con variables de entorno."""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("GOLFO_DATA_DIR", BASE_DIR / "data"))
PROCESSED_DIR = DATA_DIR / "processed"
RAW_DIR = DATA_DIR / "raw"
CACHE_DIR = DATA_DIR / "cache"
FRONTEND_DIR = BASE_DIR / "frontend"
JUPYTERLITE_DIR = BASE_DIR / "jupyterlite"     # Jupyter en el navegador (scripts/build_jupyterlite.py) → /jupyter
EVENTS_FILE = DATA_DIR / "events.json"
PLACES_FILE = DATA_DIR / "places.json"

# "file" = NetCDF/JSON de data/processed ; "sql" = base de datos SQLAlchemy (SQLite, PostgreSQL/PostGIS…)
DATA_BACKEND = os.getenv("GOLFO_DATA_BACKEND", "file").lower()
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{(DATA_DIR / 'golfo.sqlite').as_posix()}")

BBOX = {"west": -98.0, "south": 18.0, "east": -80.0, "north": 31.0}   # Golfo de México
GRID_RES = 0.25        # grados, malla de TSM y clorofila
BATHY_RES = 1 / 12     # grados, malla de batimetría (5 minutos de arco)
YEAR_START, YEAR_END = 2003, 2024
CLIM_YEARS = (2003, 2024)   # referencia para climatologías y anomalías
OBIS_API = "https://api.obis.org/v3"
OBIS_CACHE_DAYS = 30

# Metadatos de variables (las etiquetas de interfaz están en frontend/js/i18n.js)
VARIABLES = {
    "sst": {"units": "°C", "palette": "thermal", "range": [18, 31], "scale": "linear", "kind": "monthly"},
    "sst_anom": {"units": "°C", "palette": "diverging", "range": [-3, 3], "scale": "linear", "kind": "monthly"},
    "sst_change": {"units": "°C", "palette": "diverging", "range": [-3, 3], "scale": "linear", "kind": "monthly"},
    "chl": {"units": "mg m⁻³", "palette": "algae", "range": [0.03, 10], "scale": "log", "kind": "monthly"},
    "chl_anom": {"units": "%", "palette": "diverging_green", "range": [-100, 100], "scale": "linear", "kind": "monthly"},
    "depth": {"units": "m", "palette": "deep", "range": [0, 4000], "scale": "linear", "kind": "static"},
    # Radar SAR Sentinel-1 (scripts/build_sar.py): mapas anuales 2017–2024 en celdas de 0,1°
    "sar_damped": {"units": "%", "palette": "slick", "range": [0, 10], "scale": "linear", "kind": "sar"},
    "sar_bright": {"units": "%", "palette": "bright", "range": [0, 10], "scale": "linear", "kind": "sar"},
    "sar_wind": {"units": "m/s", "palette": "wind", "range": [3, 9], "scale": "linear", "kind": "sar"},
}
