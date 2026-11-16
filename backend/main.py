"""
API del Golfo de México (MIA) + servidor del frontend.

Ejecutar:  uvicorn backend.main:app --reload --port 8000      →  http://localhost:8000
Docs OpenAPI interactivas:                                   →  http://localhost:8000/docs
"""
from __future__ import annotations

from functools import lru_cache

import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from . import dataset, export, notebook, obis, sar
from .config import DATA_BACKEND, FRONTEND_DIR, JUPYTERLITE_DIR
from .security import Protecciones
from .repositories import get_repository
from .service import ErrorSolicitud, OceanService, parse_seleccion

app = FastAPI(title="Golfo de México · MIA — API de datos oceánicos",
              description="TSM (NASA JPL MUR), clorofila (NASA MODIS-Aqua), batimetría (NOAA ETOPO1), "
                          "biodiversidad (OBIS) y eventos documentados.", version="1.0.0")
app.add_middleware(GZipMiddleware, minimum_size=2000)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])
app.add_middleware(Protecciones)   # límites de tamaño y de peticiones + cabeceras de seguridad (backend/security.py)


@lru_cache(maxsize=1)
def servicio() -> OceanService:
    return OceanService(get_repository())


@app.exception_handler(ErrorSolicitud)
async def _error_solicitud(_, exc: ErrorSolicitud):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(requests.RequestException)
async def _servicio_externo(_, exc: requests.RequestException):
    return JSONResponse(status_code=502, content={"detail": f"Servicio externo no disponible: {type(exc).__name__}"})


@app.exception_handler(FileNotFoundError)
async def _sin_datos(_, exc: FileNotFoundError):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


SEL = {"bbox": Query(None, description="oeste,sur,este,norte"),
       "poly": Query(None, description="lon,lat;lon,lat;… (polígono)")}


@app.get("/api/health")
def health():
    s = servicio()
    return {"status": "ok", "backend": DATA_BACKEND, "months": [s.months[0], s.months[-1]]}


@app.get("/api/meta")
def meta():
    return {**servicio().meta(), "jupyter": (JUPYTERLITE_DIR / "index.html").exists(), "sar": sar.meta()}


@app.get("/api/grid/{var}")
def grid(var: str, month: str | None = Query(None, pattern=r"^\d{4}-\d{2}$")):
    return servicio().grid(var, month)


@app.get("/api/area/summary")
def area_summary(month: str = Query(..., pattern=r"^\d{4}-\d{2}$"), bbox: str | None = SEL["bbox"],
                 poly: str | None = SEL["poly"]):
    return servicio().summary(parse_seleccion(bbox, poly), month)


@app.get("/api/area/timeseries")
def area_timeseries(var: str = Query(..., pattern="^(sst|chl)$"), month: str | None = None,
                    bbox: str | None = SEL["bbox"], poly: str | None = SEL["poly"]):
    return servicio().timeseries(parse_seleccion(bbox, poly), var, month)


@app.get("/api/area/depth")
def area_depth(bbox: str | None = SEL["bbox"], poly: str | None = SEL["poly"]):
    return servicio().depth_profile(parse_seleccion(bbox, poly))


@app.get("/api/area/surface")
def area_surface(var: str = "sst", month: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
                 bbox: str | None = SEL["bbox"], poly: str | None = SEL["poly"]):
    return servicio().surface(parse_seleccion(bbox, poly), var, month)


@app.get("/api/area/cells")
def area_cells(month: str = Query(..., pattern=r"^\d{4}-\d{2}$"), bbox: str | None = SEL["bbox"],
               poly: str | None = SEL["poly"]):
    return servicio().cells(parse_seleccion(bbox, poly), month)


@app.get("/api/fauna")
def fauna(year: int | None = None, bbox: str | None = SEL["bbox"], poly: str | None = SEL["poly"]):
    return obis.fauna(parse_seleccion(bbox, poly).a_wkt(), year)


@app.get("/api/obis/grid/{year}")
def obis_grid(year: int):
    return servicio().repo.obis_grid(year)


@app.get("/api/events")
def events():
    """Eventos dentro del periodo con datos (los anteriores a la línea de tiempo se excluyen)."""
    return servicio().eventos


@app.post("/api/export/xlsx")
def export_xlsx(payload: export.Exportacion):
    """Genera un .xlsx con las tablas, gráficos nativos de Excel e imágenes enviadas por el frontend."""
    return Response(content=export.construir_xlsx(payload), media_type=export.MIME_XLSX,
                    headers={"Content-Disposition": export.cabecera_descarga(payload.filename)})


@app.get("/api/events/{event_id}/impact")
def event_impact(event_id: str):
    return servicio().event_impact(event_id)


@app.get("/api/places")
def places():
    return servicio().repo.places()


# ------------------------------------------------------------------ radar SAR (backend/sar.py)
@app.get("/api/sar/meta")
def sar_meta():
    return sar.meta()


@app.get("/api/sar/grid/{var}")
def sar_grid(var: str, year: int | None = Query(None, ge=1990, le=2100)):
    """Mapa SAR anual (year) o de todo el periodo (sin year), mismo formato que /api/grid."""
    return sar.grid(var, year)


@app.get("/api/sar/area")
def sar_area(bbox: str | None = SEL["bbox"], poly: str | None = SEL["poly"]):
    return sar.area(parse_seleccion(bbox, poly))


@app.get("/api/sar/scenes")
def sar_scenes(month: str = Query(..., pattern=r"^\d{4}-\d{2}$"), months: int = Query(1, ge=1, le=3),
               bbox: str | None = SEL["bbox"], poly: str | None = SEL["poly"]):
    """Escenas SAR (Sentinel-1, ALOS PALSAR, UAVSAR, NISAR) del área en NASA ASF, con vistas previas públicas."""
    return sar.escenas(parse_seleccion(bbox, poly), month, months)


@app.get("/api/sar/browse")
def sar_browse(u: str = Query(..., max_length=400), w: int = Query(900, ge=120, le=1600), alpha: bool = False):
    """Proxy de vistas previas de ASF (solo servidores de ASF), con caché; alpha=true vuelve transparente el negro."""
    datos, tipo = sar.vista_previa(u, w, alpha)
    return Response(content=datos, media_type=tipo, headers={"Cache-Control": "public, max-age=604800"})


@app.get("/api/sar/slicks")
def sar_slicks():
    """Detector de manchas con NISAR (banda L): escenas y zonas de superficie amortiguada (scripts/build_slicks.py)."""
    return sar.manchas()


@app.get("/api/sar/slicks/{escena}.png")
def sar_slick_image(escena: str):
    return Response(content=sar.imagen_mancha(escena), media_type="image/png",
                    headers={"Cache-Control": "public, max-age=86400"})


@app.get("/api/sar/events/{event_id}")
def sar_event(event_id: str):
    return sar.evento(event_id)


@app.get("/api/sar/events/{event_id}/image.png")
def sar_event_image(event_id: str):
    return Response(content=sar.imagen_evento(event_id), media_type="image/png",
                    headers={"Cache-Control": "public, max-age=86400"})


@app.get("/api/dataset/grid.npz")
def dataset_grid():
    """Malla mensual completa (TSM, clorofila, máscara, profundidad) en .npz para el cuaderno de Jupyter."""
    return Response(content=dataset.malla_npz(servicio()), media_type="application/octet-stream",
                    headers={"Content-Disposition": 'attachment; filename="golfo_malla_mensual.npz"',
                             "Cache-Control": "public, max-age=3600"})


@app.get("/api/notebook")
@app.get("/api/notebook/{nombre}")
def notebook_ipynb(nombre: str | None = None, lang: str = Query("es", pattern="^(es|en)$"),
                   month: str | None = Query(None, pattern=r"^\d{4}-\d{2}$"),
                   bbox: str | None = SEL["bbox"], poly: str | None = SEL["poly"],
                   title: str | None = Query(None, max_length=300),
                   base: str | None = Query(None, max_length=200, description="URL de la API para el cuaderno"),
                   target: str = Query("local", pattern="^(local|lite)$")):
    """Cuaderno de Jupyter (.ipynb) con los parámetros de un área: lo descarga el botón 📓 de la ventana del área.
    Todos los valores se validan y se insertan como literales de texto (backend/notebook.py)."""
    sel_txt = None
    if bbox or poly:
        sel_txt = notebook.seleccion_a_texto(parse_seleccion(bbox, poly))
    if month:
        servicio()._idx_mes(month)                     # 400 si el mes está fuera del periodo
    nb = notebook.construir_cuaderno(lang, sel_txt, month, notebook.limpiar_titulo(title, lang),
                                     notebook.validar_base(base), target)
    archivo = notebook.nombre_archivo(lang, sel_txt, month)
    return JSONResponse(nb, media_type="application/x-ipynb+json",
                        headers={"Content-Disposition": export.cabecera_descarga(archivo, ".ipynb")})


@app.get("/api/{rest:path}")
def no_encontrado(rest: str):
    raise HTTPException(status_code=404, detail=f"Ruta de API desconocida: /api/{rest}")


# Jupyter en el navegador (JupyterLite), si se ha generado con scripts/build_jupyterlite.py
if JUPYTERLITE_DIR.is_dir():
    app.mount("/jupyter", StaticFiles(directory=JUPYTERLITE_DIR, html=True), name="jupyter")

# Frontend estático (debe ir al final para no ocultar /api)
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
