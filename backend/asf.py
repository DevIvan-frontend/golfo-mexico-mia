"""
Acceso al Alaska Satellite Facility (ASF DAAC), el archivo de radar de apertura sintética (SAR) de la NASA.

* Búsqueda de escenas (``buscar``/``contar``): API pública, sin cuenta. Devuelve huella, fecha, satélite e imagen de
  vista previa (las vistas previas también son públicas).
* Descarga de productos (``sesion_earthdata``): requiere un token de NASA Earthdata. Se lee de la variable de entorno
  ``EARTHDATA_TOKEN`` o del archivo ``~/.earthdata_token``. El token nunca se imprime ni se guarda en el proyecto y
  solo se envía a dominios de NASA/ASF (también tras redirecciones).

Misiones SAR con cobertura del golfo en ASF: ALOS PALSAR (JAXA, 2006–2011), UAVSAR (avión de la NASA, 2009–),
Sentinel-1 (ESA/Copernicus, 2014–) y NISAR (NASA-ISRO, 2025–).
"""
from __future__ import annotations

import io
import math
import os
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

API = "https://api.daac.asf.alaska.edu/services/search/param"
VERTEX = "https://search.asf.alaska.edu/#/?searchType=List%20Search&searchList={}&resultsLoaded=true"
HOSTS_NASA = ("asf.alaska.edu", "earthdata.nasa.gov", "earthdatacloud.nasa.gov")
HOSTS_VISTA_PREVIA = ("datapool.asf.alaska.edu", "cumulus.asf.earthdatacloud.nasa.gov")
AGENTE = {"User-Agent": "golfo-mia-observatorio/1.0 (+ASF search)"}

# Misiones y producto de imagen que se busca para las vistas previas (uno por misión)
MISIONES = {
    "Sentinel-1": {"platform": "Sentinel-1", "processingLevel": "GRD_HD", "desde": "2014-04"},
    "ALOS PALSAR": {"platform": "ALOS", "processingLevel": "L1.5", "desde": "2006-05", "hasta": "2011-04"},
    "UAVSAR": {"platform": "UAVSAR", "desde": "2009-01"},     # campañas del golfo (2010) solo como KMZ/PNG
    "NISAR": {"platform": "NISAR", "desde": "2025-07"},
}


def _host_de(url: str, permitidos) -> bool:
    host = urlparse(url).hostname or ""
    return any(host == h or host.endswith("." + h) for h in permitidos)


def vista_previa_permitida(url: str) -> bool:
    """Solo se sirven (proxy) imágenes https de los servidores de vistas previas de ASF."""
    return url.startswith("https://") and _host_de(url, HOSTS_VISTA_PREVIA)


def poligono_ccw(puntos) -> list[tuple[float, float]]:
    """ASF espera polígonos en sentido antihorario; invierte si hace falta (área con signo, fórmula del zapato)."""
    pts = list(puntos)
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    area = sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(pts[:-1], pts[1:]))
    return pts if area > 0 else pts[::-1]


def wkt(puntos) -> str:
    return "POLYGON((" + ",".join(f"{x:.4f} {y:.4f}" for x, y in poligono_ccw(puntos)) + "))"


def circulo(lat: float, lon: float, radio_km: float, n: int = 24) -> list[tuple[float, float]]:
    """Polígono de n lados que aproxima un círculo (para buscar escenas alrededor de un evento)."""
    dlat = radio_km / 111.32
    dlon = radio_km / (111.32 * max(math.cos(math.radians(lat)), 0.2))
    return [(lon + dlon * math.cos(2 * math.pi * k / n), lat + dlat * math.sin(2 * math.pi * k / n)) for k in range(n)]


def _get(params: dict, intentos: int = 4) -> requests.Response:
    for k in range(intentos):
        try:
            r = requests.get(API, params=params, headers=AGENTE, timeout=90)
            if r.status_code < 500 and r.status_code != 429:
                r.raise_for_status()
                return r
        except (requests.ConnectionError, requests.Timeout):
            if k == intentos - 1:
                raise
        time.sleep(5 * (k + 1))
    r.raise_for_status()
    return r


def buscar(**params) -> list[dict]:
    """Búsqueda ASF (formato jsonlite). Parámetros típicos: platform, processingLevel, start, end, intersectsWith."""
    params.setdefault("output", "jsonlite")
    params.setdefault("maxResults", 5000)
    return _get(params).json().get("results", [])


def contar(**params) -> int:
    params["output"] = "count"
    return int(_get(params).text.strip() or 0)


def escena_publica(r: dict) -> dict:
    """Campos de una escena que se pueden mostrar sin cuenta (sin URL de descarga)."""
    vista = r.get("browse")
    vista = (vista[0] if isinstance(vista, list) and vista else vista) or None
    return {"id": r.get("granuleName") or r.get("productID"), "platform": r.get("missionName") or r.get("dataset"),
            "dataset": r.get("dataset"), "start": r.get("startTime"), "beam": r.get("beamMode"),
            "direction": r.get("flightDirection"), "polarization": r.get("polarization"),
            "wkt": r.get("wkt"), "browse": vista if vista and vista_previa_permitida(vista) else None,
            "vertex": VERTEX.format(r.get("granuleName") or "")}


# --------------------------------------------------------------------------------- descarga con token (opcional)
def leer_token() -> str | None:
    tok = os.getenv("EARTHDATA_TOKEN")
    if not tok:
        f = Path.home() / ".earthdata_token"
        tok = f.read_text(encoding="utf-8-sig").strip() if f.exists() else None
    return tok or None


class _SesionNASA(requests.Session):
    """Sesión que conserva el token solo en dominios de NASA/ASF (requests lo quitaría al redirigir)."""

    def __init__(self, token: str):
        super().__init__()
        self._token = token
        self.headers.update({**AGENTE, "Authorization": f"Bearer {token}"})

    def rebuild_auth(self, prepared, response):
        if _host_de(prepared.url, HOSTS_NASA):
            prepared.headers["Authorization"] = f"Bearer {self._token}"
        else:
            prepared.headers.pop("Authorization", None)


class ArchivoRemoto(io.RawIOBase):
    """Archivo remoto de solo lectura sobre peticiones HTTP Range (con caché de bloques).

    Permite abrir un HDF5 de varios GB (p. ej. NISAR GCOV, 6 GB) con ``h5py`` y leer solo los conjuntos de datos
    necesarios: h5py pide los bytes de los fragmentos (chunks) que usa y el resto nunca se descarga."""
    BLOQUE = 4 * 1024 * 1024

    def __init__(self, sesion: requests.Session, url: str, max_bloques: int = 400):
        super().__init__()
        self.s, self.url, self.pos, self.leidos = sesion, url, 0, 0
        self.cache: dict[int, bytes] = {}
        self.max_bloques = max_bloques
        r = self.s.get(url, headers={"Range": "bytes=0-0"}, timeout=90)
        r.raise_for_status()
        self.tam = int(r.headers["Content-Range"].split("/")[1])
        self.url_final = r.url            # URL firmada (S3/CloudFront) tras las redirecciones de Earthdata

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else self.tam + off
        return self.pos

    def _bloque(self, i: int) -> bytes:
        if i not in self.cache:
            a = i * self.BLOQUE
            b = min(self.tam, a + self.BLOQUE) - 1
            for intento in range(4):
                try:
                    r = self.s.get(self.url_final, headers={"Range": f"bytes={a}-{b}"}, timeout=120)
                    if r.status_code == 403:          # firma caducada: se vuelve a pasar por Earthdata
                        r = self.s.get(self.url, headers={"Range": f"bytes={a}-{b}"}, timeout=120)
                        self.url_final = r.url
                    r.raise_for_status()
                    break
                except (requests.ConnectionError, requests.Timeout):
                    if intento == 3:
                        raise
                    time.sleep(5 * (intento + 1))
            if len(self.cache) >= self.max_bloques:
                self.cache.pop(next(iter(self.cache)))
            self.cache[i] = r.content
            self.leidos += len(r.content)
        return self.cache[i]

    def readinto(self, buf):
        n = min(len(buf), max(self.tam - self.pos, 0))
        hechos = 0
        while hechos < n:
            i = (self.pos + hechos) // self.BLOQUE
            blk = self._bloque(i)
            o = self.pos + hechos - i * self.BLOQUE
            trozo = blk[o:o + (n - hechos)]
            buf[hechos:hechos + len(trozo)] = trozo
            hechos += len(trozo)
        self.pos += n
        return n


def sesion_earthdata() -> requests.Session:
    tok = leer_token()
    if not tok:
        raise RuntimeError("Falta el token de NASA Earthdata: define EARTHDATA_TOKEN o crea ~/.earthdata_token "
                           "(https://urs.earthdata.nasa.gov → Generate Token).")
    return _SesionNASA(tok)
