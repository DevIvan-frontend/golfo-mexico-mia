"""Utilidades geográficas sin dependencias pesadas (NumPy)."""
from __future__ import annotations

import math

import numpy as np

R_TIERRA_KM = 6371.0088

# Límite aproximado del Golfo de México (lon, lat), inspirado en los límites de la OHI:
# Canal de Yucatán (Cabo Catoche – Cabo San Antonio) y Estrecho de Florida (Cuba – Cayo Hueso).
# Los tramos que cruzan tierra (Yucatán, Cuba, Florida) no afectan porque la tierra no tiene datos.
GULF_POLYGON = [
    (-98.0, 18.0), (-90.0, 18.0), (-89.0, 19.5), (-88.0, 20.8), (-87.08, 21.6),
    (-84.95, 21.87), (-83.0, 22.6), (-82.4, 23.0), (-81.8, 24.55), (-80.9, 25.2),
    (-80.6, 26.0), (-81.6, 31.0), (-98.0, 31.0), (-98.0, 18.0),
]


def puntos_en_poligono(lon: np.ndarray, lat: np.ndarray, poligono) -> np.ndarray:
    """Prueba par-impar (ray casting) vectorizada. lon/lat pueden ser arreglos de cualquier forma."""
    lon = np.asarray(lon, dtype=float)
    lat = np.asarray(lat, dtype=float)
    dentro = np.zeros(lon.shape, dtype=bool)
    pts = list(poligono)
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    for (x1, y1), (x2, y2) in zip(pts[:-1], pts[1:]):
        cruza = (y1 > lat) != (y2 > lat)
        with np.errstate(divide="ignore", invalid="ignore"):
            x_corte = (x2 - x1) * (lat - y1) / (y2 - y1) + x1
        dentro ^= cruza & (lon < x_corte)
    return dentro


def mascara_golfo(lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    lon2, lat2 = np.meshgrid(lons, lats)
    return puntos_en_poligono(lon2, lat2, GULF_POLYGON)


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    h = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(np.asarray(lon2) - lon1) / 2) ** 2
    return 2 * R_TIERRA_KM * np.arcsin(np.sqrt(h))


def area_celdas_km2(lats: np.ndarray, res_lat: float, res_lon: float) -> np.ndarray:
    lats = np.asarray(lats, dtype=float)
    return (R_TIERRA_KM ** 2) * math.radians(res_lon) * np.abs(
        np.sin(np.radians(lats + res_lat / 2)) - np.sin(np.radians(lats - res_lat / 2)))


def area_poligono_km2(poligono) -> float:
    """Área geodésica aproximada (esfera) de un polígono lon/lat, fórmula de exceso esférico por trapecios."""
    pts = list(poligono)
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    total = 0.0
    for (x1, y1), (x2, y2) in zip(pts[:-1], pts[1:]):
        total += math.radians(x2 - x1) * (2 + math.sin(math.radians(y1)) + math.sin(math.radians(y2)))
    return abs(total) * R_TIERRA_KM ** 2 / 2
