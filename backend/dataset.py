"""
Malla mensual completa del golfo en un solo archivo .npz (para el cuaderno de Jupyter).

Sale del repositorio de datos activo (archivos o SQL), así que el cuaderno analiza exactamente los mismos valores que
el mapa. Contenido (NumPy, sin pickle):

  months  (T,)        'YYYY-MM'                       lats (Y,) / lons (X,)  centros de celda de 0,25°
  sst     (T, Y, X)   °C, NaN fuera del mar           chl  (T, Y, X)  mg/m³, NaN fuera del mar o sin dato
  ocean   (Y, X)      bool, celdas del golfo          depth (Y, X)    profundidad media de la celda (m)
  grid_res ()         tamaño de celda en grados

≈ 3 MB comprimido. Se genera una vez por proceso y se guarda en memoria.
"""
from __future__ import annotations

import io

import numpy as np

_CACHE: dict[int, bytes] = {}


def malla_npz(servicio) -> bytes:
    """Devuelve el .npz (bytes) con la malla mensual de TSM y clorofila del servicio dado."""
    clave = id(servicio)
    if clave not in _CACHE:
        iy, ix = np.nonzero(servicio.oceano)
        forma = (len(servicio.months),) + servicio.oceano.shape
        campos = {}
        for var in ("sst", "chl"):
            A = np.full(forma, np.nan, dtype=np.float32)
            A[:, iy, ix] = servicio.repo.series(var, iy, ix).astype(np.float32)   # (T, n celdas)
            campos[var] = A
        buf = io.BytesIO()
        np.savez_compressed(
            buf, months=np.array(servicio.months), lats=servicio.lats.astype(np.float32),
            lons=servicio.lons.astype(np.float32), ocean=servicio.oceano.astype(bool),
            depth=servicio.prof_celda.astype(np.float32), grid_res=np.float32(servicio.res), **campos)
        _CACHE[clave] = buf.getvalue()
    return _CACHE[clave]
