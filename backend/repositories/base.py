"""
Contrato de acceso a datos.

La API y la lógica de análisis (backend/service.py) solo usan estos métodos. Para conectar una base de datos
nueva basta con escribir otra clase que herede de DataRepository (ver sql_repository.py como ejemplo funcional).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np

VARIABLES_BASE = ("sst", "chl")   # variables almacenadas; las anomalías se derivan en el servicio


@dataclass
class Ejes:
    lats: np.ndarray       # centros de celda (ascendente), malla de 0.25°
    lons: np.ndarray
    months: list[str]      # "YYYY-MM"


@dataclass
class Batimetria:
    lats: np.ndarray       # ascendente
    lons: np.ndarray
    depth: np.ndarray      # m (positivo hacia abajo), NaN en tierra o fuera del golfo
    altitude: np.ndarray   # m (negativo en el mar), relieve completo para el 3D


class DataRepository(ABC):
    """Interfaz que debe implementar cualquier origen de datos (archivos, SQLite, PostgreSQL/PostGIS…)."""

    @abstractmethod
    def axes(self) -> Ejes: ...

    @abstractmethod
    def ocean_mask(self) -> np.ndarray:
        """Matriz booleana (lat, lon) de celdas oceánicas del golfo con datos."""

    @abstractmethod
    def month_grid(self, var: str, month_idx: int) -> np.ndarray:
        """Campo (lat, lon) de 'sst' o 'chl' para un mes."""

    @abstractmethod
    def series(self, var: str, iy: np.ndarray, ix: np.ndarray) -> np.ndarray:
        """Serie mensual (meses, celdas) de 'sst' o 'chl' para las celdas indicadas."""

    @abstractmethod
    def climatology(self, var: str, month_of_year: int) -> np.ndarray:
        """Climatología (lat, lon) del mes del año (1-12): 'sst' (°C) o 'logchl' (log10 mg m-3)."""

    @abstractmethod
    def bathymetry(self) -> Batimetria: ...

    @abstractmethod
    def obis_grid(self, year: int) -> dict:
        """GeoJSON con el número de registros OBIS por celda geohash para un año."""

    @abstractmethod
    def events(self) -> list[dict]: ...

    @abstractmethod
    def places(self) -> list[dict]: ...

    @abstractmethod
    def manifest(self) -> dict: ...
