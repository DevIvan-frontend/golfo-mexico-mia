"""
Lógica de análisis, independiente del origen de datos (solo usa la interfaz DataRepository).

Definiciones usadas en toda la aplicación (malla de 0,25°, meses 2003-01 … 2024-12):

* Media de un área
    - TSM: media ponderada por el área real de cada celda (las celdas se encogen hacia el norte).
    - Clorofila: media GEOMÉTRICA ponderada, 10^(media de log10), porque la clorofila es log-normal
      (unas pocas celdas costeras con valores altísimos dominarían una media aritmética).
* Climatología ("normal") de un mes del año = media 2003–2024 de ese mes (enero con eneros, etc.).
* Anomalía
    - TSM: valor − normal del mismo mes (°C).
    - Clorofila: (valor / normal − 1) × 100 (%), calculada en escala logarítmica.
* Cambio frente al año anterior = mismo mes de 12 meses antes (elimina el ciclo estacional).
* Media anual = media de los meses con dato si hay al menos ANIO_MIN_MESES (si no, el año queda vacío).
* Dirección (sube/baja/estable): |cambio| > 0,1 °C (TSM) o > 5 % (clorofila); si no, "estable".
* Tendencia = regresión lineal de las medias anuales contra el año (scipy.stats.linregress);
  se expresa por década (TSM: °C/década; clorofila: %/década sobre log10) con su valor p.
* Impacto de un evento = media de anomalías de los 3 meses previos frente a los 3 meses desde el inicio,
  dentro de un círculo de radio `radius_km` alrededor del evento.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy import stats

from .config import BBOX, CLIM_YEARS, VARIABLES
from .geo import GULF_POLYGON, area_celdas_km2, area_poligono_km2, haversine_km, puntos_en_poligono
from .repositories.base import DataRepository

VARS_MENSUALES = ("sst", "chl", "sst_anom", "chl_anom", "sst_change")
ANIO_MIN_MESES = 10   # meses válidos mínimos para que un año cuente en la tabla anual


class ErrorSolicitud(ValueError):
    """Error de parámetros del cliente (se traduce a HTTP 400)."""


@dataclass
class Seleccion:
    poligono: list[tuple[float, float]]   # (lon, lat), cerrado
    tipo: str                             # 'bbox' | 'poly'

    @property
    def limites(self):
        xs = [p[0] for p in self.poligono]; ys = [p[1] for p in self.poligono]
        return min(xs), min(ys), max(xs), max(ys)

    @property
    def centro(self):
        w, s, e, n = self.limites
        return (s + n) / 2, (w + e) / 2

    def a_wkt(self) -> str:
        return "POLYGON((" + ",".join(f"{x:.4f} {y:.4f}" for x, y in self.poligono) + "))"


def parse_seleccion(bbox: str | None, poly: str | None) -> Seleccion:
    try:
        if bbox:
            w, s, e, n = (float(v) for v in bbox.split(","))
            if not (-180 <= w < e <= 180 and -90 <= s < n <= 90):
                raise ErrorSolicitud("bbox inválido: se espera oeste,sur,este,norte con oeste<este y sur<norte")
            return Seleccion([(w, s), (e, s), (e, n), (w, n), (w, s)], "bbox")
        if poly:
            pts = [tuple(float(v) for v in par.split(",")) for par in poly.split(";") if par.strip()]
            if len(pts) < 3:
                raise ErrorSolicitud("poly necesita al menos 3 vértices 'lon,lat;lon,lat;…'")
            for lo, la in pts:
                if not (-180 <= lo <= 180 and -90 <= la <= 90):
                    raise ErrorSolicitud(f"Vértice fuera de rango: {lo},{la}")
            if pts[0] != pts[-1]:
                pts.append(pts[0])
            return Seleccion(pts, "poly")
    except (TypeError, ValueError) as err:
        if isinstance(err, ErrorSolicitud):
            raise
        raise ErrorSolicitud(f"Selección mal formada: {err}") from err
    raise ErrorSolicitud("Indica bbox=oeste,sur,este,norte o poly=lon,lat;lon,lat;…")


def _f(x, nd=3):
    """Convierte a float JSON-serializable (None si no es finito)."""
    if x is None:
        return None
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return round(x, nd) if math.isfinite(x) else None


def _lista(a, nd=3):
    a = np.asarray(a, dtype=float)
    return [[_f(v, nd) for v in fila] for fila in a] if a.ndim == 2 else [_f(v, nd) for v in a]


def _direccion(delta, umbral):
    if delta is None or not math.isfinite(delta):
        return "nd"
    return "up" if delta > umbral else "down" if delta < -umbral else "flat"


class OceanService:
    def __init__(self, repo: DataRepository):
        self.repo = repo
        ej = repo.axes()
        self.lats, self.lons, self.months = ej.lats, ej.lons, ej.months
        self.midx = {m: i for i, m in enumerate(self.months)}
        self.res = float(np.median(np.diff(self.lats)))
        self.oceano = repo.ocean_mask()
        self.area_fila = area_celdas_km2(self.lats, self.res, self.res)
        self.bat = repo.bathymetry()
        self.lon2, self.lat2 = np.meshgrid(self.lons, self.lats)
        self.blon2, self.blat2 = np.meshgrid(self.bat.lons, self.bat.lats)
        self.prof_celda = self._profundidad_por_celda()
        self.anios = np.array([int(m[:4]) for m in self.months])
        self.moy = np.array([int(m[5:7]) for m in self.months])
        # Solo eventos que empiezan dentro del periodo con datos satelitales (la línea de tiempo). Los anteriores
        # (p. ej. Ixtoc I, 1979) siguen en data/events.json y reaparecerían solos si se amplía el periodo.
        self.eventos = [e for e in repo.events() if self.months[0] <= e["start"][:7] <= self.months[-1]]

    # ------------------------------------------------------------------ utilidades
    def _idx_mes(self, mes: str) -> int:
        if mes not in self.midx:
            raise ErrorSolicitud(f"Mes fuera de rango: {mes} (disponible {self.months[0]} – {self.months[-1]})")
        return self.midx[mes]

    def _profundidad_por_celda(self):
        """Profundidad media de cada celda de 0.25° a partir de la batimetría de 1/12°."""
        iy = np.floor((self.bat.lats - (self.lats[0] - self.res / 2)) / self.res).astype(int)
        ix = np.floor((self.bat.lons - (self.lons[0] - self.res / 2)) / self.res).astype(int)
        suma = np.zeros((self.lats.size, self.lons.size)); n = np.zeros_like(suma)
        for a, fila in enumerate(iy):
            if 0 <= fila < self.lats.size:
                ok = (ix >= 0) & (ix < self.lons.size) & np.isfinite(self.bat.depth[a])
                np.add.at(suma, (fila, ix[ok]), self.bat.depth[a][ok])
                np.add.at(n, (fila, ix[ok]), 1)
        with np.errstate(invalid="ignore"):
            return np.where(n > 0, suma / n, np.nan)

    def _celdas(self, sel: Seleccion):
        """Índices (iy, ix) de las celdas oceánicas cuyo CENTRO cae dentro del polígono de la selección."""
        m = puntos_en_poligono(self.lon2, self.lat2, sel.poligono) & self.oceano
        if not m.any():   # área menor que una celda: usa la celda oceánica más cercana al centro (≤ 0.5°)
            la, lo = sel.centro
            d = np.where(self.oceano, (self.lat2 - la) ** 2 + (self.lon2 - lo) ** 2, np.inf)
            k = np.unravel_index(np.argmin(d), d.shape)
            if d[k] <= 0.5 ** 2:
                m[k] = True
        return np.nonzero(m)

    def _serie_area(self, var: str, iy, ix):
        """Media mensual del área (TSM: media ponderada por área; clorofila: media geométrica)."""
        S = self.repo.series(var, iy, ix).astype(float)
        w = np.broadcast_to(self.area_fila[iy], S.shape)
        ok = np.isfinite(S)
        with np.errstate(invalid="ignore", divide="ignore"):
            if var == "chl":
                v = 10 ** (np.nansum(np.where(ok, np.log10(S), 0) * w, axis=1) / np.sum(w * ok, axis=1))
            else:
                v = np.nansum(np.where(ok, S, 0) * w, axis=1) / np.sum(w * ok, axis=1)
        return v, ok.mean(axis=1)

    def _anomalia_serie(self, var: str, v: np.ndarray):
        """Anomalía y climatología mensual de una serie de área (ver definiciones en la cabecera del módulo)."""
        en_clim = (self.anios >= CLIM_YEARS[0]) & (self.anios <= CLIM_YEARS[1])
        anom = np.full(v.shape, np.nan)
        clim = np.full(v.shape, np.nan)
        with np.errstate(invalid="ignore", divide="ignore"):
            for k in range(1, 13):
                sel = self.moy == k
                if var == "chl":
                    c = np.nanmean(np.log10(v[sel & en_clim]))
                    clim[sel] = 10 ** c
                    anom[sel] = (10 ** (np.log10(v[sel]) - c) - 1) * 100
                else:
                    c = np.nanmean(v[sel & en_clim])
                    clim[sel] = c
                    anom[sel] = v[sel] - c
        return anom, clim

    def _tendencia(self, var, v):
        """Pendiente por década y valor p de la regresión lineal de las medias anuales (≥ 8 años con dato)."""
        anios, medias = self._anuales(var, v)
        ok = np.isfinite(medias)
        if ok.sum() < 8:
            return None, None
        y = np.log10(medias[ok]) if var == "chl" else medias[ok]
        r = stats.linregress(anios[ok], y)
        pend = (10 ** (r.slope * 10) - 1) * 100 if var == "chl" else r.slope * 10
        return pend, r.pvalue

    def _anuales(self, var, v):
        """Medias anuales (geométrica para clorofila); NaN si el año tiene menos de ANIO_MIN_MESES meses."""
        anios = np.unique(self.anios)
        medias = []
        for y in anios:
            s = v[self.anios == y]
            s = s[np.isfinite(s)]
            if s.size < ANIO_MIN_MESES:
                medias.append(np.nan)
            elif var == "chl":
                medias.append(10 ** np.mean(np.log10(s)))
            else:
                medias.append(np.mean(s))
        return anios, np.array(medias)

    # ------------------------------------------------------------------ API pública
    def meta(self) -> dict:
        """Metadatos para el frontend: límites, polígono del golfo, meses, variables y procedencia."""
        return {"bbox": BBOX, "gulf_polygon": GULF_POLYGON, "months": self.months, "grid_res": self.res,
                "variables": VARIABLES, "clim_years": CLIM_YEARS, "manifest": self.repo.manifest(),
                "obis_years": [int(y) for y in sorted(set(self.anios))]}

    def grid(self, var: str, mes: str | None) -> dict:
        """Campo completo del mapa para un mes: lats, lons y matriz `values` (filas de sur a norte, None = sin dato).

        sst/chl: valor mensual · sst_anom: TSM − normal · chl_anom: % sobre la normal (en log) ·
        sst_change: TSM − TSM de 12 meses antes · depth: batimetría de 1/12° (no depende del mes).
        """
        if var == "depth":
            return {"var": var, "lats": _lista(self.bat.lats, 4), "lons": _lista(self.bat.lons, 4),
                    "values": _lista(self.bat.depth, 0), "res": float(np.median(np.diff(self.bat.lats)))}
        if var not in VARS_MENSUALES:
            raise ErrorSolicitud(f"Variable desconocida: {var}")
        k = self._idx_mes(mes)
        moy = self.moy[k]
        with np.errstate(invalid="ignore", divide="ignore"):
            if var in ("sst", "chl"):
                a = self.repo.month_grid(var, k)
            elif var == "sst_anom":
                a = self.repo.month_grid("sst", k) - self.repo.climatology("sst", moy)
            elif var == "chl_anom":
                a = (10 ** (np.log10(self.repo.month_grid("chl", k)) - self.repo.climatology("logchl", moy)) - 1) * 100
            else:   # sst_change: frente al mismo mes del año anterior
                a = (self.repo.month_grid("sst", k) - self.repo.month_grid("sst", k - 12)) if k >= 12 \
                    else np.full(self.oceano.shape, np.nan)
        return {"var": var, "month": mes, "lats": _lista(self.lats, 4), "lons": _lista(self.lons, 4),
                "values": _lista(a, 4 if var == "chl" else 3), "res": self.res}

    def summary(self, sel: Seleccion, mes: str) -> dict:
        """Ventana del área: profundidad (min/media/máx/% plataforma) y, para TSM y clorofila, valor del mes,
        normal, anomalía, mismo mes del año anterior y su cambio, dirección, tendencia 2003–2024 y cobertura;
        además, los eventos cuyo radio toca el área."""
        k = self._idx_mes(mes)
        iy, ix = self._celdas(sel)
        out = {"selection": {"type": sel.tipo, "bounds": sel.limites, "center": sel.centro,
                             "area_km2": _f(area_poligono_km2(sel.poligono), 0),
                             "ocean_cells": int(iy.size),
                             "ocean_area_km2": _f(self.area_fila[iy].sum(), 0) if iy.size else 0},
               "month": mes, "variables": {}, "events": self.eventos_cercanos(sel, mes)}
        # Profundidad (batimetría 1/12°)
        mb = puntos_en_poligono(self.blon2, self.blat2, sel.poligono) & np.isfinite(self.bat.depth)
        if not mb.any() and iy.size:
            d = self.prof_celda[iy, ix]
            d = d[np.isfinite(d)]
        else:
            d = self.bat.depth[mb]
        if d.size:
            out["variables"]["depth"] = {"min": _f(d.min(), 0), "mean": _f(d.mean(), 0), "max": _f(d.max(), 0),
                                         "shelf_pct": _f(100 * np.mean(d < 200), 1)}
        if iy.size == 0:
            return out
        for var in ("sst", "chl"):
            v, cob = self._serie_area(var, iy, ix)
            anom, clim = self._anomalia_serie(var, v)
            prev = v[k - 12] if k >= 12 else np.nan
            if var == "chl":
                delta = (v[k] / prev - 1) * 100 if np.isfinite(prev) else np.nan
            else:
                delta = v[k] - prev
            pend, p = self._tendencia(var, v)
            umbral = 5.0 if var == "chl" else 0.1
            out["variables"][var] = {
                "value": _f(v[k], 3), "clim": _f(clim[k], 3), "anom": _f(anom[k], 2),
                "prev_year": _f(prev, 3), "delta_prev_year": _f(delta, 2),
                "direction": _direccion(_f(anom[k], 3), umbral), "direction_prev": _direccion(float(delta), umbral),
                "trend_per_decade": _f(pend, 3), "trend_p": _f(p, 4), "coverage_pct": _f(100 * cob[k], 0),
            }
        return out

    def timeseries(self, sel: Seleccion, var: str, mes: str | None = None) -> dict:
        """Serie mensual del área (valor, normal, anomalía, cobertura) + tabla anual (media, cambio frente al año
        anterior, dirección, anomalía media) + tabla del mismo mes en cada año + tendencia + eventos de la zona."""
        base = "chl" if var.startswith("chl") else "sst"
        iy, ix = self._celdas(sel)
        if iy.size == 0:
            raise ErrorSolicitud("La selección no contiene celdas oceánicas del golfo.")
        v, cob = self._serie_area(base, iy, ix)
        anom, clim = self._anomalia_serie(base, v)
        anios, medias = self._anuales(base, v)
        _, anom_anual = self._anuales("sst", anom)   # media aritmética de anomalías
        filas, previo = [], np.nan
        umbral = 5.0 if base == "chl" else 0.1
        for y, mu, an in zip(anios, medias, anom_anual):
            if base == "chl":
                delta = (mu / previo - 1) * 100 if np.isfinite(previo) and np.isfinite(mu) else np.nan
            else:
                delta = mu - previo if np.isfinite(previo) and np.isfinite(mu) else np.nan
            filas.append({"year": int(y), "mean": _f(mu, 3), "anom": _f(an, 2), "delta": _f(delta, 2),
                          "direction": _direccion(delta, umbral)})
            if np.isfinite(mu):
                previo = mu
        mismo_mes = []
        if mes:
            k = self._idx_mes(mes)
            previo = np.nan
            for j in np.nonzero(self.moy == self.moy[k])[0]:
                x = v[j]
                delta = ((x / previo - 1) * 100 if base == "chl" else x - previo) if np.isfinite(previo) else np.nan
                mismo_mes.append({"month": self.months[j], "value": _f(x, 3), "anom": _f(anom[j], 2),
                                  "delta": _f(delta, 2), "direction": _direccion(delta, umbral)})
                if np.isfinite(x):
                    previo = x
        pend, p = self._tendencia(base, v)
        return {"var": base, "months": self.months, "values": _lista(v, 3), "anom": _lista(anom, 2),
                "clim": _lista(clim, 3), "coverage_pct": _lista(100 * cob, 0), "annual": filas,
                "same_month": mismo_mes, "trend_per_decade": _f(pend, 3), "trend_p": _f(p, 4),
                "events": self.eventos_cercanos(sel, None)}

    def depth_profile(self, sel: Seleccion) -> dict:
        """Porcentaje de puntos de batimetría (1/12°) del área en cada clase de profundidad."""
        mb = puntos_en_poligono(self.blon2, self.blat2, sel.poligono) & np.isfinite(self.bat.depth)
        d = self.bat.depth[mb]
        clases = [(0, 50), (50, 200), (200, 1000), (1000, 2000), (2000, 3000), (3000, 5000)]
        return {"n": int(d.size), "classes": [{"from": a, "to": b, "pct": _f(100 * np.mean((d >= a) & (d < b)), 1) if d.size else None}
                                               for a, b in clases]}

    def surface(self, sel: Seleccion, var: str, mes: str, max_puntos: int = 110) -> dict:
        """Relieve (altitud ETOPO) dentro de los límites de la selección + variable en las celdas oceánicas."""
        w, s, e, n = sel.limites
        cx, cy = (w + e) / 2, (s + n) / 2
        mitad_x, mitad_y = max((e - w) / 2, 0.75), max((n - s) / 2, 0.75)
        fy = (self.bat.lats >= cy - mitad_y) & (self.bat.lats <= cy + mitad_y)
        fx = (self.bat.lons >= cx - mitad_x) & (self.bat.lons <= cx + mitad_x)
        lats, lons = self.bat.lats[fy], self.bat.lons[fx]
        paso = max(1, int(math.ceil(max(lats.size, lons.size) / max_puntos)))
        lats, lons = lats[::paso], lons[::paso]
        alt = self.bat.altitude[np.ix_(fy, fx)][::paso, ::paso]
        prof = self.bat.depth[np.ix_(fy, fx)][::paso, ::paso]
        campo = self.grid(var, mes)["values"] if var in VARS_MENSUALES else None
        valores = np.full(alt.shape, np.nan)
        if campo is not None:
            C = np.array([[np.nan if x is None else x for x in fila] for fila in campo], dtype=float)
            iy = np.clip(np.floor((lats - (self.lats[0] - self.res / 2)) / self.res).astype(int), 0, self.lats.size - 1)
            ix = np.clip(np.floor((lons - (self.lons[0] - self.res / 2)) / self.res).astype(int), 0, self.lons.size - 1)
            valores = np.where(np.isfinite(prof), C[np.ix_(iy, ix)], np.nan)
        return {"var": var, "month": mes, "lats": _lista(lats, 4), "lons": _lista(lons, 4),
                "altitude": _lista(alt, 0), "values": _lista(valores, 3)}

    def cells(self, sel: Seleccion, mes: str) -> dict:
        """Valores por celda de 0,25° del mes (TSM, clorofila, anomalías y profundidad media): base del 3D de propiedades."""
        k = self._idx_mes(mes)
        iy, ix = self._celdas(sel)
        moy = self.moy[k]
        with np.errstate(invalid="ignore", divide="ignore"):
            sst = self.repo.month_grid("sst", k)[iy, ix]
            chl = self.repo.month_grid("chl", k)[iy, ix]
            sst_a = sst - self.repo.climatology("sst", moy)[iy, ix]
            chl_a = (10 ** (np.log10(chl) - self.repo.climatology("logchl", moy)[iy, ix]) - 1) * 100
        return {"month": mes, "lat": _lista(self.lats[iy], 3), "lon": _lista(self.lons[ix], 3),
                "depth": _lista(self.prof_celda[iy, ix], 0), "sst": _lista(sst, 2), "chl": _lista(chl, 3),
                "sst_anom": _lista(sst_a, 2), "chl_anom": _lista(chl_a, 1)}

    # ------------------------------------------------------------------ eventos
    @staticmethod
    def _mes_de(fecha: str) -> str:
        return fecha[:7]

    def _offset_meses(self, a: str, b: str) -> int:
        return (int(a[:4]) - int(b[:4])) * 12 + int(a[5:7]) - int(b[5:7])

    def eventos_cercanos(self, sel: Seleccion, mes: str | None) -> list[dict]:
        """Eventos cuya distancia al centro de la selección es menor que su radio + media diagonal de la selección.
        Si se da `mes`, incluye cuántos meses separan el evento del mes seleccionado."""
        w, s, e, n = sel.limites
        la, lo = sel.centro
        semidiag = haversine_km(s, w, n, e) / 2
        out = []
        for ev in self.eventos:
            d = float(haversine_km(la, lo, ev["lat"], ev["lon"]))
            if d <= ev.get("radius_km", 100) + semidiag:
                item = {"id": ev["id"], "distance_km": round(d), "type": ev["type"], "category": ev["category"],
                        "start": ev["start"], "end": ev.get("end"), "name": ev["name"]}
                if mes:
                    item["months_from_selected"] = self._offset_meses(self._mes_de(ev["start"]), mes)
                out.append(item)
        return sorted(out, key=lambda x: x["start"])

    def event_impact(self, ev_id: str, ventana: int = 24) -> dict:
        """Serie de anomalías ±`ventana` meses dentro del radio del evento y comparación 3 meses antes / después."""
        ev = next((e for e in self.eventos if e["id"] == ev_id), None)
        if ev is None:
            raise ErrorSolicitud(f"Evento desconocido: {ev_id}")
        m0 = self._mes_de(ev["start"])
        base = {"event": ev, "month": m0}
        if m0 not in self.midx:
            base["note"] = "out_of_range"
            return base
        d = haversine_km(self.lat2, self.lon2, ev["lat"], ev["lon"])
        iy, ix = np.nonzero((d <= ev.get("radius_km", 100)) & self.oceano)
        if iy.size == 0:
            base["note"] = "no_ocean_cells"
            return base
        k0 = self.midx[m0]
        a, b = max(0, k0 - ventana), min(len(self.months), k0 + ventana + 1)
        res = {"months": self.months[a:b], "event_index": k0 - a, "cells": int(iy.size)}
        for var in ("sst", "chl"):
            v, _ = self._serie_area(var, iy, ix)
            anom, _ = self._anomalia_serie(var, v)
            antes = anom[max(0, k0 - 3):k0]
            despues = anom[k0:k0 + 3]
            mu_a = np.nanmean(antes) if np.isfinite(antes).any() else np.nan
            mu_d = np.nanmean(despues) if np.isfinite(despues).any() else np.nan
            umbral = 5.0 if var == "chl" else 0.1
            res[var] = {"values": _lista(v[a:b], 3), "anom": _lista(anom[a:b], 2),
                        "before_anom": _f(mu_a, 2), "after_anom": _f(mu_d, 2),
                        "change": _f(mu_d - mu_a, 2), "direction": _direccion(mu_d - mu_a, umbral)}
        base.update(res)
        return base
