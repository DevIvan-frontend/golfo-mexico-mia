"""
Protecciones para publicar la API en internet (p. ej. detrás de un túnel de Cloudflare).

* Límite de tamaño del cuerpo de las peticiones (la exportación a Excel es el único POST).
* Límite de peticiones por visitante (ventana deslizante en memoria). Detrás de Cloudflare la IP real llega en la
  cabecera ``CF-Connecting-IP``; en local se usa la IP de la conexión.
* Cabeceras de seguridad básicas en todas las respuestas.

Configurable con variables de entorno:
  GOLFO_MAX_BODY_MB   (por defecto 30)    tamaño máximo de un POST
  GOLFO_RATE_API      (por defecto 300)   peticiones /api por minuto y visitante
  GOLFO_RATE_EXPORT   (por defecto 6)     exportaciones a Excel por minuto y visitante
"""
from __future__ import annotations

import os
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

MAX_BODY = int(float(os.getenv("GOLFO_MAX_BODY_MB", "30")) * 1024 * 1024)
LIMITE_API = int(os.getenv("GOLFO_RATE_API", "300"))
LIMITE_EXPORT = int(os.getenv("GOLFO_RATE_EXPORT", "6"))
VENTANA_S = 60

CABECERAS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Frame-Options": "SAMEORIGIN",
    "Permissions-Policy": "geolocation=(), camera=(), microphone=()",
}


def ip_cliente(request: Request) -> str:
    """IP real del visitante: Cloudflare la envía en CF-Connecting-IP; detrás de otros proxies (Render, Fly, Cloud
    Run…) va primera en X-Forwarded-For; si no hay proxy, la de la conexión. Sin esto, todos los visitantes
    compartirían el límite de peticiones del proxy."""
    cf = request.headers.get("cf-connecting-ip")
    if cf:
        return cf
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "desconocida"


class Protecciones(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self._historial: dict[tuple[str, str], deque] = defaultdict(deque)

    def _excede(self, clave: tuple[str, str], limite: int) -> bool:
        ahora = time.monotonic()
        cola = self._historial[clave]
        while cola and ahora - cola[0] > VENTANA_S:
            cola.popleft()
        if len(cola) >= limite:
            return True
        cola.append(ahora)
        if len(self._historial) > 20_000:          # evita crecer sin límite con muchas IPs
            self._historial.clear()
        return False

    async def dispatch(self, request: Request, call_next):
        ruta = request.url.path
        if request.method == "POST":
            largo = request.headers.get("content-length")
            if largo is None or not largo.isdigit():
                return JSONResponse({"detail": "Se requiere Content-Length."}, status_code=411)
            if int(largo) > MAX_BODY:
                return JSONResponse({"detail": "Petición demasiado grande."}, status_code=413)
        if ruta.startswith("/api/"):
            ip = ip_cliente(request)
            if ruta.startswith("/api/export") and self._excede((ip, "export"), LIMITE_EXPORT):
                return JSONResponse({"detail": "Demasiadas exportaciones; espera un minuto."}, status_code=429,
                                    headers={"Retry-After": str(VENTANA_S)})
            if self._excede((ip, "api"), LIMITE_API):
                return JSONResponse({"detail": "Demasiadas peticiones; espera un minuto."}, status_code=429,
                                    headers={"Retry-After": str(VENTANA_S)})
        respuesta = await call_next(request)
        for k, v in CABECERAS.items():
            respuesta.headers.setdefault(k, v)
        if not ruta.startswith(("/api/", "/jupyter/")):
            # HTML/JS/CSS de la interfaz: el navegador revalida siempre (ETag), así una actualización nunca mezcla
            # módulos JS viejos y nuevos.
            respuesta.headers.setdefault("Cache-Control", "no-cache")
        return respuesta
