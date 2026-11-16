"""
Generación de libros de Excel (.xlsx) a partir de lo que muestra la interfaz.

El frontend (frontend/js/exporter.js) envía un JSON con:
  * ``info``    pares clave/valor para la hoja de portada (área, mes, filtros, fuentes…);
  * ``sheets``  tablas (columnas + filas) y, opcionalmente, un gráfico NATIVO de Excel (líneas o barras)
                construido sobre los datos de esa misma hoja, de modo que el gráfico sigue siendo editable;
  * ``images``  PNG de los gráficos de la web (incluidos los 3D, que Excel no puede reproducir) generados
                con ``Plotly.toImage``; se colocan en una hoja «Gráficos».

Este módulo valida el contenido con Pydantic, limita tamaños y evita la inyección de fórmulas.
"""
from __future__ import annotations

import base64
import binascii
import io
import math
import re
import unicodedata
from typing import Any, Literal, Optional
from urllib.parse import quote

from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from pydantic import BaseModel, Field

MAX_FILAS = 50_000                     # por hoja
MAX_IMAGEN_BYTES = 6 * 1024 * 1024     # por imagen PNG
ANCHO_MAX_IMAGEN = 960                 # px dentro de Excel
MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

_COLOR_CABECERA = PatternFill("solid", fgColor="0E6E8C")
_FUENTE_CABECERA = Font(bold=True, color="FFFFFF")


class GraficoNativo(BaseModel):
    """Gráfico de Excel construido sobre las columnas de la hoja (índices base 0)."""
    type: Literal["line", "bar"] = "line"
    title: str = ""
    x_col: int = Field(0, ge=0)
    y_cols: list[int] = Field(default_factory=list, max_length=8)
    x_title: str = ""
    y_title: str = ""


class Hoja(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    columns: list[str] = Field(..., min_length=1, max_length=60)
    rows: list[list[Any]] = Field(default_factory=list, max_length=MAX_FILAS)
    chart: Optional[GraficoNativo] = None
    note: str = ""


class Imagen(BaseModel):
    title: str = ""
    png_base64: str


class Exportacion(BaseModel):
    filename: str = "golfo_mexico.xlsx"
    title: str = ""
    info: list[list[str]] = Field(default_factory=list, max_length=60)
    sheets: list[Hoja] = Field(default_factory=list, max_length=30)
    images: list[Imagen] = Field(default_factory=list, max_length=12)
    images_sheet: str = "Gráficos"


def nombre_archivo_seguro(nombre: str, ext: str = ".xlsx") -> str:
    """Nombre ASCII (letras, números, guiones y puntos) que siempre termina en `ext`."""
    normal = unicodedata.normalize("NFKD", nombre or "").encode("ascii", "ignore").decode()
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", normal).strip("._")[:120] or "golfo_mexico"
    return base if base.lower().endswith(ext) else f"{base}{ext}"


def cabecera_descarga(nombre: str, ext: str = ".xlsx") -> str:
    """Content-Disposition con nombre ASCII y, para navegadores modernos, el nombre UTF-8 (RFC 5987).
    `ext` = extensión obligatoria (.xlsx para los informes, .ipynb para los cuadernos de Jupyter)."""
    seguro = nombre_archivo_seguro(nombre, ext)
    original = nombre if (nombre or "").lower().endswith(ext) else f"{nombre or seguro}{ext}"
    return f"attachment; filename=\"{seguro}\"; filename*=UTF-8''{quote(original, safe='')}"


def _nombre_hoja(nombre: str, usados: set[str]) -> str:
    """Excel limita los nombres a 31 caracteres y prohíbe []:*?/\\ ; además deben ser únicos."""
    limpio = re.sub(r"[\[\]:*?/\\]", " ", nombre).strip()[:31] or "Hoja"
    final, k = limpio, 2
    while final.lower() in usados:
        sufijo = f" ({k})"
        final = limpio[: 31 - len(sufijo)] + sufijo
        k += 1
    usados.add(final.lower())
    return final


def _valor(v: Any) -> Any:
    """Normaliza valores: NaN/inf → vacío; listas/dicts → texto."""
    if isinstance(v, float) and not math.isfinite(v):
        return None
    if isinstance(v, (list, dict)):
        return str(v)
    return v


def _escribir_celda(ws, fila: int, col: int, valor: Any):
    c = ws.cell(row=fila, column=col, value=_valor(valor))
    if isinstance(c.value, str) and c.value.startswith("="):
        c.data_type = "s"          # texto literal: evita la inyección de fórmulas
    return c


def _ajustar_columnas(ws, n_cols: int, filas_muestra: int = 300):
    for j in range(1, n_cols + 1):
        largo = max((len(str(ws.cell(row=i, column=j).value or "")) for i in range(1, min(ws.max_row, filas_muestra) + 1)),
                    default=8)
        ws.column_dimensions[get_column_letter(j)].width = min(55, max(9, largo + 2))


def _anadir_grafico(ws, hoja: Hoja, n_filas: int):
    g = hoja.chart
    n_cols = len(hoja.columns)
    ys = [c for c in g.y_cols if 0 <= c < n_cols]
    if not ys or n_filas == 0 or g.x_col >= n_cols:
        return
    grafico = LineChart() if g.type == "line" else BarChart()
    grafico.title = g.title or None
    grafico.y_axis.title = g.y_title or None
    grafico.x_axis.title = g.x_title or None
    grafico.x_axis.delete = False      # Excel reciente oculta los ejes de openpyxl si no se indica
    grafico.y_axis.delete = False
    grafico.height, grafico.width = 9, 24
    for c in ys:
        grafico.add_data(Reference(ws, min_col=c + 1, min_row=1, max_row=n_filas + 1), titles_from_data=True)
    grafico.set_categories(Reference(ws, min_col=g.x_col + 1, min_row=2, max_row=n_filas + 1))
    if g.type == "line":
        for serie in grafico.series:
            serie.smooth = False
            serie.marker.symbol = "none"
    ws.add_chart(grafico, f"{get_column_letter(n_cols + 2)}2")


def construir_xlsx(exp: Exportacion) -> bytes:
    """Devuelve el contenido binario del libro .xlsx."""
    wb = Workbook()
    usados: set[str] = set()

    portada = wb.active
    portada.title = _nombre_hoja("Info", usados)
    portada["A1"] = exp.title or "Golfo de México · Observatorio MIA"
    portada["A1"].font = Font(bold=True, size=14)
    for i, par in enumerate(exp.info, start=3):
        _escribir_celda(portada, i, 1, par[0] if par else "").font = Font(bold=True)
        _escribir_celda(portada, i, 2, par[1] if len(par) > 1 else "")
        portada.cell(row=i, column=2).alignment = Alignment(wrap_text=True, vertical="top")
    portada.column_dimensions["A"].width = 28
    portada.column_dimensions["B"].width = 110

    for hoja in exp.sheets:
        ws = wb.create_sheet(_nombre_hoja(hoja.name, usados))
        for j, nombre in enumerate(hoja.columns, start=1):
            c = _escribir_celda(ws, 1, j, nombre)
            c.font, c.fill = _FUENTE_CABECERA, _COLOR_CABECERA
            c.alignment = Alignment(wrap_text=True, vertical="center")
        for i, fila in enumerate(hoja.rows, start=2):
            for j, valor in enumerate(fila[: len(hoja.columns)], start=1):
                _escribir_celda(ws, i, j, valor)
        ws.freeze_panes = "A2"
        _ajustar_columnas(ws, len(hoja.columns))
        if hoja.note:
            _escribir_celda(ws, len(hoja.rows) + 3, 1, hoja.note).font = Font(italic=True, color="666666")
        if hoja.chart:
            _anadir_grafico(ws, hoja, len(hoja.rows))

    if exp.images:
        ws = wb.create_sheet(_nombre_hoja(exp.images_sheet or "Gráficos", usados))
        fila = 1
        for img in exp.images:
            datos = img.png_base64.split(",", 1)[-1]          # admite "data:image/png;base64,…"
            try:
                crudo = base64.b64decode(datos, validate=True)
            except (binascii.Error, ValueError):
                continue
            if len(crudo) > MAX_IMAGEN_BYTES or not crudo.startswith(b"\x89PNG"):
                continue
            xl = XLImage(io.BytesIO(crudo))
            if xl.width > ANCHO_MAX_IMAGEN:
                escala = ANCHO_MAX_IMAGEN / xl.width
                xl.width, xl.height = int(xl.width * escala), int(xl.height * escala)
            _escribir_celda(ws, fila, 1, img.title).font = Font(bold=True, size=12)
            xl.anchor = f"A{fila + 1}"
            ws.add_image(xl)
            fila += int(math.ceil(xl.height / 20)) + 4      # ~20 px por fila

    salida = io.BytesIO()
    wb.save(salida)
    return salida.getvalue()
