"""
Generador del cuaderno de Jupyter «Golfo de México · Observatorio MIA».

Un solo origen para todos los usos:

* ``notebooks/Golfo_Mexico_MIA_{es,en}.ipynb``  → Jupyter en la computadora (los escribe scripts/build_jupyterlite.py).
* JupyterLite dentro de la aplicación (``/jupyter``) → el mismo cuaderno con el kernel Pyodide (Python en el navegador).
* ``GET /api/notebook?…``                         → cuaderno con los parámetros de un área elegida en el mapa
  (botón 📓 de la ventana del área).

El cuaderno obtiene TODO de la misma API que el mapa (o, en Jupyter local, importando ``backend/`` directamente), de
modo que los números coinciden con la aplicación. Para el análisis de todo el golfo descarga la malla mensual completa
(``/api/dataset/grid.npz``, ver backend/dataset.py).

Seguridad: los parámetros recibidos por la API se validan y se insertan con ``repr()`` (literales de texto de Python),
nunca como código.
"""
from __future__ import annotations

import re
import textwrap
import unicodedata

from .service import Seleccion

NOMBRE_BASE = "Golfo_Mexico_MIA"
DEFECTO = {
    "seleccion": "bbox=-89.0000,28.0000,-88.0000,29.0000",
    "mes": "2010-05",
    "titulo": {"es": "Celda de 1° del pozo Macondo (Deepwater Horizon)",
               "en": "1° cell at the Macondo well (Deepwater Horizon)"},
}
KERNELS = {
    "local": {"display_name": "Python 3 (ipykernel)", "language": "python", "name": "python3"},
    "lite": {"display_name": "Python (Pyodide)", "language": "python", "name": "python"},
}
_RE_BASE = re.compile(r"^https?://[A-Za-z0-9.\-]+(:\d{1,5})?$")


# ---------------------------------------------------------------------------------------------- validación
def seleccion_a_texto(sel: Seleccion) -> str:
    """Selección validada → texto canónico 'bbox=…' o 'poly=…' (solo números formateados)."""
    if sel.tipo == "bbox":
        w, s, e, n = sel.limites
        return f"bbox={w:.4f},{s:.4f},{e:.4f},{n:.4f}"
    return "poly=" + ";".join(f"{x:.4f},{y:.4f}" for x, y in sel.poligono[:-1])


def limpiar_titulo(titulo: str | None, lang: str) -> str:
    """Quita caracteres de control y limita la longitud; vacío → título por defecto."""
    t = "".join(c for c in (titulo or "") if not unicodedata.category(c).startswith("C")).strip()[:160]
    return t or DEFECTO["titulo"][lang]


def validar_base(base: str | None) -> str:
    """URL de la API para un cuaderno descargado: solo 'esquema://host[:puerto]'; si no, 'auto'."""
    return base.rstrip("/") if base and _RE_BASE.match(base.rstrip("/")) else "auto"


def nombre_archivo(lang: str, seleccion: str | None = None, mes: str | None = None) -> str:
    if not seleccion:
        return f"{NOMBRE_BASE}_{lang}.ipynb"
    corto = re.sub(r"[^0-9A-Za-z.-]+", "_", seleccion.split("=", 1)[1])[:60].strip("_")
    return f"{NOMBRE_BASE}_{mes}_{corto}_{lang}.ipynb"


# ---------------------------------------------------------------------------------------------- celdas
def _md(es: str, en: str):
    return ("markdown", {"es": textwrap.dedent(es).strip(), "en": textwrap.dedent(en).strip()})


def _code(src: str):
    return ("code", textwrap.dedent(src).strip())


PARAMETROS = "__parametros__"

CELDAS = [
    _md("""
        # Golfo de México · Observatorio MIA — cuaderno de análisis

        Este cuaderno usa **los mismos datos y cálculos que el mapa de la aplicación** (temperatura superficial NASA JPL
        MUR, clorofila NASA MODIS-Aqua, batimetría NOAA ETOPO1, biodiversidad OBIS y eventos documentados) para estudiar
        un área con más libertad: tablas completas, gráficos propios, comparación con todo el golfo y exportación.

        | Dónde se ejecuta | Cómo | De dónde lee los datos |
        |---|---|---|
        | Dentro de la aplicación (botón 📓) | JupyterLite: Python corre en tu navegador, no hay que instalar nada | API de la misma página |
        | Jupyter en tu computadora, dentro de `golfo_mexico_app/` | `pip install -r requirements.txt jupyterlab matplotlib` y `jupyter lab` | importa `backend/` directamente (sin servidor) |
        | Jupyter en cualquier otra computadora | basta con `numpy pandas matplotlib` | API pública de la aplicación (`API = "https://…"`) |

        **Uso:** cambia los parámetros de la sección 1 y ejecuta todo (*Run ▸ Run All Cells*). En el navegador, la primera
        ejecución tarda alrededor de un minuto porque descarga Python (Pyodide) y las librerías.

        > Coincidir en el tiempo no implica causalidad: los cruces con eventos sirven para plantear hipótesis, no para
        > atribuir impactos.
        """, """
        # Gulf of Mexico · EIA Observatory — analysis notebook

        This notebook uses **the same data and calculations as the app's map** (NASA JPL MUR sea surface temperature,
        NASA MODIS-Aqua chlorophyll, NOAA ETOPO1 bathymetry, OBIS biodiversity and documented events) to study an area
        more freely: full tables, custom charts, comparison with the whole gulf and export.

        | Where it runs | How | Where the data comes from |
        |---|---|---|
        | Inside the app (📓 button) | JupyterLite: Python runs in your browser, nothing to install | the same page's API |
        | Jupyter on your computer, inside `golfo_mexico_app/` | `pip install -r requirements.txt jupyterlab matplotlib` and `jupyter lab` | imports `backend/` directly (no server) |
        | Jupyter on any other computer | just `numpy pandas matplotlib` | the app's public API (`API = "https://…"`) |

        **Usage:** change the parameters in section 1 and run everything (*Run ▸ Run All Cells*). In the browser the first
        run takes about a minute because it downloads Python (Pyodide) and the libraries.

        > Coinciding in time does not imply causation: overlaps with events help build hypotheses, not attribute impacts.
        """),
    _md("""
        ## 1. Parámetros

        * `SELECCION`: `"bbox=oeste,sur,este,norte"` (rectángulo o celda de 1°) o `"poly=lon,lat;lon,lat;…"` (polígono).
          Longitudes oeste en negativo.
        * `MES`: mes de referencia, de `2003-01` a `2024-12`.
        * `API`: `"auto"` elige solo (navegador → esta página; Jupyter local dentro del proyecto → `backend/`; si no →
          `http://localhost:8000`). También acepta `"local"` o una URL como `"https://….trycloudflare.com"`.
        * `IDIOMA`: `"es"` o `"en"` (etiquetas de tablas y gráficos).
        """, """
        ## 1. Parameters

        * `SELECCION` (selection): `"bbox=west,south,east,north"` (rectangle or 1° cell) or `"poly=lon,lat;lon,lat;…"`
          (polygon). West longitudes are negative.
        * `MES` (month): reference month, from `2003-01` to `2024-12`.
        * `API`: `"auto"` decides by itself (browser → this page; local Jupyter inside the project → `backend/`;
          otherwise → `http://localhost:8000`). It also accepts `"local"` or a URL such as `"https://….trycloudflare.com"`.
        * `IDIOMA` (language): `"es"` or `"en"` (table and chart labels).
        """),
    ("code", PARAMETROS),
    _md("""
        ## 2. Preparación y conexión con los datos

        `conectar()` devuelve un cliente con dos métodos, `get(ruta, **parámetros)` (JSON) y `get_bytes(ruta)` (archivos),
        con las mismas rutas que la API REST de la aplicación (`/api/area/summary`, `/api/area/timeseries`, …; ver
        `docs/DOCUMENTACION.md`). En Jupyter local dentro del proyecto llama directamente a `backend/service.py`, así que
        no necesita el servidor encendido.
        """, """
        ## 2. Setup and data connection

        `conectar()` returns a client with two methods, `get(route, **params)` (JSON) and `get_bytes(route)` (files), using
        the same routes as the app's REST API (`/api/area/summary`, `/api/area/timeseries`, …; see
        `docs/DOCUMENTACION.md`). In local Jupyter inside the project it calls `backend/service.py` directly, so the server
        does not need to be running.
        """),
    _code(r'''
        import io, json, re, sys, warnings
        from pathlib import Path
        from urllib.parse import urlencode

        import numpy as np
        import pandas as pd
        import matplotlib.pyplot as plt
        from matplotlib import colors as mcolors
        from matplotlib.patches import Patch

        warnings.filterwarnings("ignore", category=RuntimeWarning)      # medias de celdas sin dato (NaN)
        pd.set_option("display.max_rows", 60)
        pd.set_option("display.width", 160)
        plt.rcParams.update({"figure.figsize": (11, 4), "figure.dpi": 100, "axes.grid": True, "grid.alpha": 0.25,
                             "axes.spines.top": False, "axes.spines.right": False, "font.size": 10})

        EN_NAVEGADOR = sys.platform == "emscripten"       # True en JupyterLite (Python compilado a WebAssembly)

        TXT = {
            "es": dict(variable="Variable", value="Valor", clim="Normal 2003–2024", anom="Anomalía",
                       prev_year="Mismo mes del año anterior", delta_prev="Cambio vs. año anterior",
                       trend="Tendencia por década", p="valor p", coverage="Cobertura %", direction="Dirección",
                       year="Año", month="Mes", mean="Media", change="Cambio", sst="Temperatura superficial",
                       chl="Clorofila-a", sst_s="TSM", chl_s="Clorofila", up="sube", down="baja", flat="estable",
                       nd="sin dato", series="Serie mensual del área", anomalies="Anomalías mensuales",
                       roll="media móvil 12 meses", seasonal="Ciclo estacional", range="rango 2003–2024",
                       scatter="Anomalías TSM vs. clorofila", lag="Desfase (meses, clorofila después de la TSM)",
                       corr="Correlación r", n="n", depth="Profundidad", depth_cls="Clases de profundidad del área",
                       pct="% del área", min="Mínima", max="Máxima", mean_depth="Media", shelf="% plataforma (<200 m)",
                       records="Registros", species="Especies", top="Especies con más registros",
                       by_year="Registros OBIS por año", redlist="Lista Roja UICN", event="Evento", type="Tipo",
                       category="Categoría", start="Inicio", distance="Distancia km", natural="natural",
                       human="humano", before="3 meses antes", after="3 meses después",
                       impact="Anomalías alrededor del evento", months_rel="Meses respecto al inicio del evento",
                       sst_anom="Anomalía TSM", chl_anom="Anomalía clorofila", trend_map="tendencia 2003–2024",
                       per_dec="/década", signif="puntos = significativa (p < 0,05)",
                       hov="Anomalía de TSM promediada por latitud", lat="Latitud", lon="Longitud",
                       area="Área seleccionada", gulf="Promedio del golfo", diff="Área − golfo",
                       local_vs_gulf="¿Cambio local o de todo el golfo?", sel_month="Mes elegido",
                       active="eventos activos (±6 meses)", cells="celdas", ocean_area="Área oceánica km²",
                       no_fauna="OBIS no respondió; vuelve a ejecutar la celda más tarde.",
                       no_events="No hay eventos documentados cuyo radio toque esta área.",
                       no_ocean="La selección no contiene celdas del golfo (¿tierra?). Cambia SELECCION.",
                       local_sig="señal LOCAL inusual (|z| > 2): el área se aparta del resto del golfo",
                       gulf_sig="sin señal local destacada: el área sigue al conjunto del golfo",
                       saved="Guardado en", gulf_cells="celdas del golfo con tendencia significativa",
                       sar_damped="Superficie amortiguada", sar_bright="Objetos brillantes", sar_wind="Viento del radar",
                       mission="Misión",
                       no_sar="Productos SAR no generados en el servidor (scripts/build_sar.py); solo se listan escenas."),
            "en": dict(variable="Variable", value="Value", clim="2003–2024 normal", anom="Anomaly",
                       prev_year="Same month previous year", delta_prev="Change vs. previous year",
                       trend="Trend per decade", p="p-value", coverage="Coverage %", direction="Direction",
                       year="Year", month="Month", mean="Mean", change="Change", sst="Sea surface temperature",
                       chl="Chlorophyll-a", sst_s="SST", chl_s="Chlorophyll", up="up", down="down", flat="stable",
                       nd="no data", series="Area monthly series", anomalies="Monthly anomalies",
                       roll="12-month rolling mean", seasonal="Seasonal cycle", range="2003–2024 range",
                       scatter="SST vs. chlorophyll anomalies", lag="Lag (months, chlorophyll after SST)",
                       corr="Correlation r", n="n", depth="Depth", depth_cls="Depth classes of the area",
                       pct="% of area", min="Minimum", max="Maximum", mean_depth="Mean", shelf="% shelf (<200 m)",
                       records="Records", species="Species", top="Species with most records",
                       by_year="OBIS records per year", redlist="IUCN Red List", event="Event", type="Type",
                       category="Category", start="Start", distance="Distance km", natural="natural",
                       human="human", before="3 months before", after="3 months after",
                       impact="Anomalies around the event", months_rel="Months from event start",
                       sst_anom="SST anomaly", chl_anom="Chlorophyll anomaly", trend_map="2003–2024 trend",
                       per_dec="/decade", signif="dots = significant (p < 0.05)",
                       hov="SST anomaly averaged by latitude", lat="Latitude", lon="Longitude",
                       area="Selected area", gulf="Gulf average", diff="Area − gulf",
                       local_vs_gulf="Local or gulf-wide change?", sel_month="Selected month",
                       active="active events (±6 months)", cells="cells", ocean_area="Ocean area km²",
                       no_fauna="OBIS did not respond; run the cell again later.",
                       no_events="No documented events whose radius touches this area.",
                       no_ocean="The selection contains no gulf cells (land?). Change SELECCION.",
                       local_sig="unusual LOCAL signal (|z| > 2): the area departs from the rest of the gulf",
                       gulf_sig="no notable local signal: the area follows the gulf as a whole",
                       saved="Saved to", gulf_cells="gulf cells with a significant trend",
                       sar_damped="Damped surface", sar_bright="Bright targets", sar_wind="Radar wind",
                       mission="Mission",
                       no_sar="SAR products not generated on the server (scripts/build_sar.py); only scenes are listed."),
        }
        L = TXT.get(IDIOMA, TXT["es"])
        MESES_ABR = {"es": "Ene Feb Mar Abr May Jun Jul Ago Sep Oct Nov Dic".split(),
                     "en": "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()}[IDIOMA if IDIOMA in TXT else "es"]
        UNI = {"sst": "°C", "chl": "mg/m³"}
        UNI_ANOM = {"sst": "°C", "chl": "%"}
        FLECHA = {"up": "▲", "down": "▼", "flat": "●", "nd": "·"}
        COLOR = {"sst": "#c8553d", "chl": "#2a9d6f", "natural": "#e09f3e", "human": "#9e2a2b"}


        def dir_txt(d):
            """'up' → '▲ sube'."""
            return f"{FLECHA.get(d, '·')} {L.get(d, d)}"


        def nombre(x):
            """Texto bilingüe {es, en} → idioma elegido."""
            return (x.get(IDIOMA) or x.get("es")) if isinstance(x, dict) else x


        def fecha(m):
            """'YYYY-MM[-DD]' → Timestamp a mitad de mes (así se dibujan las series mensuales)."""
            return pd.Timestamp(m[:7] + "-15")
        '''),
    _code(r'''
        class ClienteHTTP:
            """Lee la API REST de la aplicación (la misma que usa el mapa)."""

            def __init__(self, base):
                self.base = base.rstrip("/")
                self.origen = self.base

            def _url(self, ruta, params):
                q = urlencode({k: v for k, v in params.items() if v is not None}, safe=",;")
                return f"{self.base}{ruta}" + (f"?{q}" if q else "")

            def _bajar(self, url):
                if EN_NAVEGADOR:
                    # El kernel Pyodide corre en un Web Worker, donde se permite una petición síncrona.
                    from js import XMLHttpRequest
                    x = XMLHttpRequest.new()
                    x.open("GET", url, False)
                    x.responseType = "arraybuffer"
                    x.send()
                    if x.status != 200:
                        raise RuntimeError(f"HTTP {x.status}: {url}")
                    return x.response.to_bytes()
                from urllib.request import Request, urlopen
                with urlopen(Request(url, headers={"User-Agent": "golfo-mia-notebook"}), timeout=180) as r:
                    return r.read()

            def get(self, ruta, **params):
                return json.loads(self._bajar(self._url(ruta, params)).decode("utf-8"))

            def get_bytes(self, ruta, **params):
                return self._bajar(self._url(ruta, params))


        class ClienteLocal:
            """Usa backend/ del proyecto sin servidor: mismas funciones que la API, mismo formato de respuesta."""

            def __init__(self, raiz):
                if str(raiz) not in sys.path:
                    sys.path.insert(0, str(raiz))
                from backend import dataset, obis, sar
                from backend.main import servicio
                from backend.service import parse_seleccion
                self.s, self._parse, self._obis, self._dataset = servicio(), parse_seleccion, obis, dataset
                self._sar = sar
                self.origen = f"backend/ local ({raiz})"

            def _sel(self, p):
                return self._parse(p.get("bbox"), p.get("poly"))

            def get(self, ruta, **p):
                s = self.s
                if ruta == "/api/meta":
                    r = {**s.meta(), "sar": self._sar.meta()}
                elif ruta == "/api/sar/slicks":
                    r = self._sar.manchas()
                elif ruta == "/api/sar/area":
                    r = self._sar.area(self._sel(p))
                elif ruta.startswith("/api/sar/grid/"):
                    r = self._sar.grid(ruta.rsplit("/", 1)[1], p.get("year"))
                elif ruta == "/api/sar/scenes":
                    r = self._sar.escenas(self._sel(p), p["month"], int(p.get("months", 1)))
                elif ruta == "/api/area/summary":
                    r = s.summary(self._sel(p), p["month"])
                elif ruta == "/api/area/timeseries":
                    r = s.timeseries(self._sel(p), p["var"], p.get("month"))
                elif ruta == "/api/area/depth":
                    r = s.depth_profile(self._sel(p))
                elif ruta == "/api/area/cells":
                    r = s.cells(self._sel(p), p["month"])
                elif ruta == "/api/fauna":
                    r = self._obis.fauna(self._sel(p).a_wkt(), p.get("year"))
                elif ruta == "/api/events":
                    r = s.eventos
                elif ruta.startswith("/api/events/") and ruta.endswith("/impact"):
                    r = s.event_impact(ruta.split("/")[3])
                else:
                    raise ValueError(f"Ruta no disponible en modo local: {ruta}")
                return json.loads(json.dumps(r, default=float))     # mismo formato que la respuesta JSON

            def get_bytes(self, ruta, **p):
                if ruta == "/api/dataset/grid.npz":
                    return self._dataset.malla_npz(self.s)
                raise ValueError(f"Ruta no disponible en modo local: {ruta}")


        def raiz_proyecto():
            """Carpeta golfo_mexico_app/ si el cuaderno se abre dentro del proyecto."""
            for p in (Path.cwd(), *Path.cwd().parents):
                if (p / "backend" / "service.py").exists():
                    return p
            return None


        def conectar(api):
            if api not in ("auto", "local"):
                return ClienteHTTP(api)
            if EN_NAVEGADOR:
                import js
                return ClienteHTTP(str(js.location.origin))
            raiz = raiz_proyecto()
            if raiz is None:
                if api == "local":
                    raise FileNotFoundError("No se encuentra backend/: abre el cuaderno dentro de golfo_mexico_app/")
                return ClienteHTTP("http://localhost:8000")
            try:
                return ClienteLocal(raiz)
            except ImportError as err:
                print(f"No se pudo importar backend/ ({err}); se usa http://localhost:8000")
                return ClienteHTTP("http://localhost:8000")


        clave_sel, _, valor_sel = SELECCION.partition("=")
        if clave_sel not in ("bbox", "poly") or not valor_sel:
            raise ValueError('SELECCION debe ser "bbox=oeste,sur,este,norte" o "poly=lon,lat;lon,lat;…"')
        SEL = {clave_sel: valor_sel}
        if clave_sel == "bbox":
            _w, _s, _e, _n = map(float, valor_sel.split(","))
            POLI = np.array([(_w, _s), (_e, _s), (_e, _n), (_w, _n), (_w, _s)])
        else:
            _pts = [tuple(map(float, p.split(","))) for p in valor_sel.split(";") if p.strip()]
            POLI = np.array(_pts + _pts[:1])

        cli = conectar(API)
        meta = cli.get("/api/meta")
        MESES = meta["months"]
        if MES not in MESES:
            raise ValueError(f"MES fuera de rango: {MES} ({MESES[0]} … {MESES[-1]})")
        EVENTOS = cli.get("/api/events")
        print(f"Datos: {cli.origen}")
        print(f"Periodo: {MESES[0]} … {MESES[-1]} · {len(MESES)} meses · malla {meta['grid_res']}° · {len(EVENTOS)} eventos")
        print(f"Área: {TITULO} · {SELECCION} · {MES}")
        '''),
    _md("""
        ## 3. Resumen del área en el mes elegido

        Lo mismo que muestra la ventana del área en el mapa:

        * **Valor**: media del área en el mes. TSM: media ponderada por la superficie de cada celda. Clorofila: media
          geométrica (los datos son log-normales).
        * **Normal**: media 2003–2024 del mismo mes del año. **Anomalía** = valor − normal (TSM, °C) o % sobre la normal
          (clorofila).
        * **Cambio vs. año anterior**: frente al mismo mes 12 meses antes (elimina el ciclo estacional).
        * **Tendencia por década**: regresión lineal de las medias anuales 2003–2024; significativa si p < 0,05.
        * **Dirección**: ▲ sube / ▼ baja si |anomalía| > 0,1 °C (TSM) o > 5 % (clorofila); si no, ● estable.
        """, """
        ## 3. Area summary for the selected month

        The same as the area window on the map:

        * **Value**: area mean for the month. SST: mean weighted by each cell's surface. Chlorophyll: geometric mean (the
          data are log-normal).
        * **Normal**: 2003–2024 mean of the same calendar month. **Anomaly** = value − normal (SST, °C) or % above the
          normal (chlorophyll).
        * **Change vs. previous year**: against the same month 12 months earlier (removes the seasonal cycle).
        * **Trend per decade**: linear regression of the 2003–2024 annual means; significant if p < 0.05.
        * **Direction**: ▲ up / ▼ down if |anomaly| > 0.1 °C (SST) or > 5 % (chlorophyll); otherwise ● stable.
        """),
    _code(r'''
        res = cli.get("/api/area/summary", month=MES, **SEL)
        v, info = res["variables"], res["selection"]
        print(f"{info['ocean_cells']} {L['cells']} · {L['ocean_area']}: {info['ocean_area_km2'] or 0:,.0f}")
        if not info["ocean_cells"]:
            print(L["no_ocean"])

        filas = []
        for var in ("sst", "chl"):
            x = v.get(var)
            if not x:
                continue
            ua = UNI_ANOM[var]
            filas.append({L["variable"]: f"{L[var]} ({UNI[var]})", L["value"]: x["value"], L["clim"]: x["clim"],
                          f"{L['anom']} ({ua})": x["anom"], L["direction"]: dir_txt(x["direction"]),
                          L["prev_year"]: x["prev_year"], f"{L['delta_prev']} ({ua})": x["delta_prev_year"],
                          f"{L['trend']} ({ua})": x["trend_per_decade"], L["p"]: x["trend_p"],
                          L["coverage"]: x["coverage_pct"]})
        tabla_resumen = pd.DataFrame(filas).set_index(L["variable"]).T if filas else pd.DataFrame()
        display(tabla_resumen)

        if "depth" in v:
            d = v["depth"]
            display(pd.Series({L["min"]: d["min"], L["mean_depth"]: d["mean"], L["max"]: d["max"],
                               L["shelf"]: d["shelf_pct"]}, name=f"{L['depth']} (m)").to_frame())
        '''),
    _md("""
        ## 4. Series mensuales 2003–2024

        Línea de color: valor del área cada mes. Línea discontinua: la normal de cada mes. Bandas: eventos documentados
        cuyo radio toca el área (naranja = natural, rojo oscuro = humano). Línea negra: el mes elegido.
        """, """
        ## 4. Monthly series 2003–2024

        Coloured line: area value each month. Dashed line: each month's normal. Bands: documented events whose radius
        touches the area (orange = natural, dark red = human). Black line: the selected month.
        """),
    _code(r'''
        def serie(var):
            t = cli.get("/api/area/timeseries", var=var, month=MES, **SEL)
            df = pd.DataFrame({"valor": t["values"], "normal": t["clim"], "anomalia": t["anom"],
                               "cobertura_pct": t["coverage_pct"]},
                              index=pd.to_datetime([m + "-15" for m in t["months"]]), dtype=float)
            df.index.name = "mes"
            return t, df


        ts, mensual = {}, {}
        for var in ("sst", "chl"):
            ts[var], mensual[var] = serie(var)
        eventos_zona = ts["sst"]["events"]


        def marcar_eventos(ax, eventos, rotulos=True):
            y_alto = ax.get_ylim()[1]
            for ev in eventos:
                a = fecha(ev["start"])
                b = max(fecha(ev["end"]) if ev.get("end") else a, a + pd.Timedelta(days=25))
                largo = (b - a).days > 365                # eventos crónicos (años): banda tenue + marca de inicio
                ax.axvspan(a, b, color=COLOR[ev["type"]], alpha=0.07 if largo else 0.22, lw=0)
                if largo:
                    ax.axvline(a, color=COLOR[ev["type"]], lw=1, alpha=0.6)
                if rotulos:
                    ax.text(a, y_alto, " " + nombre(ev["name"])[:30], rotation=90, va="top", ha="right",
                            fontsize=7, color=COLOR[ev["type"]])


        fig, axs = plt.subplots(2, 1, figsize=(12, 7.5), sharex=True)
        for ax, var in zip(axs, ("sst", "chl")):
            df = mensual[var]
            ax.plot(df.index, df["normal"], color="0.55", lw=1, ls="--", label=L["clim"])
            ax.plot(df.index, df["valor"], color=COLOR[var], lw=1.4, label=L["value"])
            if var == "chl":
                ax.set_yscale("log")
            ax.set_ylabel(f"{L[var]} ({UNI[var]})")
            ax.axvline(fecha(MES), color="k", lw=1.2, alpha=0.7, label=L["sel_month"])
            marcar_eventos(ax, eventos_zona, rotulos=(var == "sst"))
            t = ts[var]
            if t["trend_per_decade"] is not None:
                ax.set_title(f"{L[var]} · {L['trend']}: {t['trend_per_decade']:+.2f} {UNI_ANOM[var]} "
                             f"(p = {t['trend_p']:.3f})", loc="left", fontsize=10)
        manejadores = axs[0].get_legend_handles_labels()[0] + [
            Patch(color=COLOR["natural"], alpha=0.4, label=L["natural"]),
            Patch(color=COLOR["human"], alpha=0.4, label=L["human"])]
        axs[0].legend(handles=manejadores, loc="lower left", ncol=5, fontsize=8)
        fig.suptitle(f"{TITULO} — {L['series']}", fontweight="bold")
        fig.tight_layout()
        plt.show()
        '''),
    _md("""
        ## 5. ¿Sube o baja? Tablas anuales y del mismo mes

        * **Tabla anual**: media de cada año (solo si tiene ≥ 10 meses con dato), anomalía media y cambio frente al año
          anterior con su dirección.
        * **Mismo mes**: el mes elegido en cada año (p. ej. todos los mayos), para comparar sin efecto estacional.
        """, """
        ## 5. Up or down? Annual and same-month tables

        * **Annual table**: mean of each year (only if it has ≥ 10 months with data), mean anomaly and change from the
          previous year with its direction.
        * **Same month**: the selected month in every year (e.g. every May), to compare without the seasonal effect.
        """),
    _code(r'''
        def tabla_dir(filas, var, por="year"):
            df = pd.DataFrame(filas)
            if df.empty:
                return df
            ua = UNI_ANOM[var]
            col_val, txt_val = ("mean", L["mean"]) if por == "year" else ("value", L["value"])
            df[L["direction"]] = df["direction"].map(dir_txt)
            df = df.drop(columns="direction").rename(columns={
                "year": L["year"], "month": L["month"], col_val: f"{txt_val} ({UNI[var]})",
                "anom": f"{L['anom']} ({ua})", "delta": f"{L['change']} ({ua})"})
            return df.set_index(L["year"] if por == "year" else L["month"])


        anual = {var: tabla_dir(ts[var]["annual"], var) for var in ("sst", "chl")}
        mismo_mes = {var: tabla_dir(ts[var]["same_month"], var, por="month") for var in ("sst", "chl")}
        for var in ("sst", "chl"):
            conteo = pd.Series([r["direction"] for r in ts[var]["annual"]]).value_counts()
            print(f"\n{L[var]} — {L['year']}: " + " · ".join(f"{dir_txt(k)}: {n}" for k, n in conteo.items()))
            display(anual[var])
        for var in ("sst", "chl"):
            print(f"\n{L[var]} — {L['month']} {MES[5:]}")
            display(mismo_mes[var])
        '''),
    _md("""
        ## 6. Anomalías mensuales

        Barras: anomalía de cada mes (TSM: rojo = más cálido, azul = más frío; clorofila: verde = más, marrón = menos).
        Línea negra: media móvil de 12 meses, que muestra cambios persistentes.
        """, """
        ## 6. Monthly anomalies

        Bars: each month's anomaly (SST: red = warmer, blue = cooler; chlorophyll: green = more, brown = less). Black
        line: 12-month rolling mean, which shows persistent changes.
        """),
    _code(r'''
        COLORES_ANOM = {"sst": ("#c0392b", "#2c7fb8"), "chl": ("#2a9d6f", "#a6611a")}
        fig, axs = plt.subplots(2, 1, figsize=(12, 6.5), sharex=True)
        for ax, var in zip(axs, ("sst", "chl")):
            a = mensual[var]["anomalia"]
            pos, neg = COLORES_ANOM[var]
            ax.bar(a.index, a.values, width=25, color=np.where(a.values > 0, pos, neg), alpha=0.85)
            ax.plot(a.index, a.rolling(12, center=True, min_periods=8).mean(), color="k", lw=1.3, label=L["roll"])
            ax.axhline(0, color="0.3", lw=0.8)
            ax.axvline(fecha(MES), color="k", lw=1, ls=":")
            marcar_eventos(ax, eventos_zona, rotulos=False)
            ax.set_ylabel(f"{L['anom']} ({UNI_ANOM[var]})")
            ax.set_title(L[var], loc="left", fontsize=10)
        axs[0].legend(loc="upper left", fontsize=8)
        fig.suptitle(f"{TITULO} — {L['anomalies']}", fontweight="bold")
        fig.tight_layout()
        plt.show()
        '''),
    _md("""
        ## 7. Ciclo estacional

        Banda: mínimo y máximo de cada mes del año en 2003–2024. Discontinua: normal. Línea gruesa: el año elegido.
        """, """
        ## 7. Seasonal cycle

        Band: minimum and maximum of each calendar month in 2003–2024. Dashed: normal. Thick line: the selected year.
        """),
    _code(r'''
        anio_sel = int(MES[:4])
        x12 = np.arange(1, 13)
        fig, axs = plt.subplots(1, 2, figsize=(12, 4))
        for ax, var in zip(axs, ("sst", "chl")):
            df = mensual[var]
            g = df["valor"].groupby(df.index.month)
            ax.fill_between(x12, g.min().reindex(x12), g.max().reindex(x12), color=COLOR[var], alpha=0.15, label=L["range"])
            ax.plot(x12, df["normal"].groupby(df.index.month).first().reindex(x12), color="0.4", ls="--", label=L["clim"])
            este = df.loc[df.index.year == anio_sel, "valor"]
            ax.plot(este.index.month, este.values, color=COLOR[var], lw=2, marker="o", ms=3, label=str(anio_sel))
            if var == "chl":
                ax.set_yscale("log")
            ax.set_xticks(x12)
            ax.set_xticklabels(MESES_ABR)
            ax.set_ylabel(f"{L[var]} ({UNI[var]})")
            ax.set_title(f"{L['seasonal']} · {L[var]}", loc="left", fontsize=10)
            ax.legend(fontsize=8)
        fig.tight_layout()
        plt.show()
        '''),
    _md("""
        ## 8. Relación temperatura–clorofila

        Izquierda: anomalías de TSM frente a anomalías de clorofila de cada mes (color = año) y su recta de regresión.
        Derecha: correlación cuando la clorofila se compara con la TSM de 0 a 6 meses antes. En mar abierto, un
        calentamiento suele estratificar la columna de agua y reducir nutrientes (correlación negativa); cerca de la
        costa dominan los ríos.
        """, """
        ## 8. Temperature–chlorophyll relationship

        Left: each month's SST anomaly against its chlorophyll anomaly (colour = year) with the regression line. Right:
        correlation when chlorophyll is compared with SST 0 to 6 months earlier. In the open ocean, warming tends to
        stratify the water column and reduce nutrients (negative correlation); near the coast rivers dominate.
        """),
    _code(r'''
        sa, ca = mensual["sst"]["anomalia"], mensual["chl"]["anomalia"]
        par = pd.DataFrame({"sst": sa, "chl": ca}).dropna()
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.5, 4.5), gridspec_kw={"width_ratios": [1.3, 1]})
        if len(par) > 3:
            sc = ax1.scatter(par["sst"], par["chl"], c=par.index.year, cmap="viridis", s=14, alpha=0.8)
            fig.colorbar(sc, ax=ax1, label=L["year"])
            b, c0 = np.polyfit(par["sst"], par["chl"], 1)
            xs = np.linspace(par["sst"].min(), par["sst"].max(), 50)
            ax1.plot(xs, b * xs + c0, color="k", lw=1)
            ax1.set_title(f"{L['scatter']} · r = {par['sst'].corr(par['chl']):.2f} · n = {len(par)}", loc="left", fontsize=10)
        ax1.axhline(0, color="0.5", lw=0.7)
        ax1.axvline(0, color="0.5", lw=0.7)
        ax1.set_xlabel(f"{L['sst_anom']} (°C)")
        ax1.set_ylabel(f"{L['chl_anom']} (%)")

        desfases = list(range(0, 7))
        corr = pd.DataFrame({L["lag"]: desfases,
                             L["corr"]: [sa.corr(ca.shift(-k)) for k in desfases],
                             L["n"]: [int((sa.notna() & ca.shift(-k).notna()).sum()) for k in desfases]}).set_index(L["lag"])
        ax2.bar(corr.index, corr[L["corr"]], color="#577590")
        ax2.axhline(0, color="0.3", lw=0.8)
        ax2.set_xlabel(L["lag"])
        ax2.set_ylabel(L["corr"])
        fig.tight_layout()
        plt.show()
        display(corr.round(3))
        '''),
    _md("""
        ## 9. Profundidad del área

        Porcentaje de puntos de batimetría NOAA ETOPO1 (1/12°, ~9 km) del área en cada clase. La plataforma
        continental (< 200 m) concentra pesca, plataformas petroleras y efectos de ríos.
        """, """
        ## 9. Area depth

        Percentage of NOAA ETOPO1 bathymetry points (1/12°, ~9 km) of the area in each class. The continental shelf
        (< 200 m) concentrates fisheries, oil platforms and river effects.
        """),
    _code(r'''
        prof = cli.get("/api/area/depth", **SEL)
        clases = pd.DataFrame(prof["classes"])
        clases[L["depth"]] = [f"{a}–{b} m" for a, b in zip(clases["from"], clases["to"])]
        clases = clases.set_index(L["depth"])[["pct"]].rename(columns={"pct": L["pct"]})
        if prof["n"]:
            ax = clases[L["pct"]].plot.barh(color="#1d4e89", figsize=(8, 3.2))
            ax.invert_yaxis()
            ax.set_xlabel(L["pct"])
            ax.set_title(L["depth_cls"], loc="left", fontsize=10)
            plt.show()
        display(clases)
        '''),
    _md("""
        ## 10. Vida marina (OBIS)

        Registros de especies del Ocean Biodiversity Information System dentro del área (todos los años). El número de
        registros refleja el **esfuerzo de muestreo**, no la abundancia: úsalo para saber qué especies hay y cuáles
        están en la Lista Roja de la UICN.
        """, """
        ## 10. Marine life (OBIS)

        Species records from the Ocean Biodiversity Information System inside the area (all years). The number of
        records reflects **sampling effort**, not abundance: use it to know which species occur and which are on the
        IUCN Red List.
        """),
    _code(r'''
        try:
            fauna = cli.get("/api/fauna", **SEL)
        except Exception as err:          # OBIS es un servicio externo: puede tardar o fallar
            fauna = {"available": False, "error": str(err)}

        top = por_anio = roja = pd.DataFrame()
        if fauna.get("available"):
            print(f"{L['records']}: {fauna.get('records') or 0:,} · {L['species']}: {fauna.get('species') or 0:,} · "
                  f"{L['redlist']}: {fauna.get('redlist_total') or 0}")
            top, por_anio, roja = (pd.DataFrame(fauna[k]) for k in ("top", "by_year", "redlist"))
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 4.8), gridspec_kw={"width_ratios": [1.2, 1]})
            if not top.empty:
                t12 = top.head(12).iloc[::-1]
                ax1.barh(t12["scientificName"], t12["records"], color="#2a9d8f")
                ax1.set_title(L["top"], loc="left", fontsize=10)
                ax1.set_xlabel(L["records"])
                ax1.tick_params(axis="y", labelsize=8)
            if not por_anio.empty:
                ax2.bar(por_anio["year"], por_anio["records"], color="#264653")
                ax2.axvspan(2002.5, 2024.5, color="#e9c46a", alpha=0.15)
                ax2.set_title(L["by_year"], loc="left", fontsize=10)
            fig.tight_layout()
            plt.show()
            cols = [c for c in ("scientificName", "class", "family", "category", "records") if c in roja.columns]
            if cols:
                display(roja[cols].head(25))
        else:
            print(L["no_fauna"], fauna.get("error", ""))
        '''),
    _md("""
        ## 11. Eventos cercanos: antes y después

        Para cada evento documentado cuyo radio toca el área: anomalía media de los **3 meses anteriores** frente a los
        **3 meses desde el inicio**, dentro del radio del evento (no solo en el área). El gráfico muestra ±24 meses del
        evento más cercano al mes elegido.
        """, """
        ## 11. Nearby events: before and after

        For each documented event whose radius touches the area: mean anomaly of the **3 months before** against the
        **3 months from the start**, inside the event's radius (not only in the area). The chart shows ±24 months around
        the event closest to the selected month.
        """),
    _code(r'''
        impactos = pd.DataFrame()
        series_ev = {}
        if not eventos_zona:
            print(L["no_events"])
        else:
            filas = []
            for ev in eventos_zona[:15]:
                imp = cli.get(f"/api/events/{ev['id']}/impact")
                if "sst" not in imp:
                    continue
                series_ev[ev["id"]] = (ev, imp)
                fila = {L["event"]: nombre(ev["name"]), L["type"]: L[ev["type"]], L["category"]: ev["category"],
                        L["start"]: ev["start"], L["distance"]: ev["distance_km"], L["cells"]: imp["cells"]}
                for var in ("sst", "chl"):
                    x, ua, c = imp[var], UNI_ANOM[var], L[var + "_s"]
                    fila[f"{c} {L['before']} ({ua})"] = x["before_anom"]
                    fila[f"{c} {L['after']} ({ua})"] = x["after_anom"]
                    fila[f"{c} {L['change']} ({ua})"] = x["change"]
                    fila[f"{c} {L['direction']}"] = dir_txt(x["direction"])
                filas.append(fila)
            impactos = pd.DataFrame(filas).set_index(L["event"])
            display(impactos)

        if series_ev:
            ev, imp = min(series_ev.values(), key=lambda p: abs((fecha(p[0]["start"]) - fecha(MES)).days))
            rel = np.arange(len(imp["months"])) - imp["event_index"]
            fig, ax = plt.subplots(figsize=(12, 4))
            ax2 = ax.twinx()
            ax.axvspan(-3.5, -0.5, color="0.88", lw=0)
            ax.axvspan(-0.5, 2.5, color="#f6d8cc", lw=0)
            a_sst = np.array(imp["sst"]["anom"], dtype=float)
            a_chl = np.array(imp["chl"]["anom"], dtype=float)
            ax.bar(rel - 0.2, a_sst, width=0.4, color=COLOR["sst"], label=f"{L['sst_anom']} (°C)")
            ax2.bar(rel + 0.2, a_chl, width=0.4, color=COLOR["chl"], label=f"{L['chl_anom']} (%)")
            for eje, a in ((ax, a_sst), (ax2, a_chl)):      # ceros alineados en los dos ejes
                tope = 1.1 * (np.nanmax(np.abs(a)) if np.isfinite(a).any() else 1.0)
                eje.set_ylim(-tope, tope)
            ax.axvline(-0.5, color="k", lw=1.2)
            ax.axhline(0, color="0.3", lw=0.8)
            ax.set_xlabel(L["months_rel"])
            ax.set_ylabel(f"{L['sst_anom']} (°C)", color=COLOR["sst"])
            ax2.set_ylabel(f"{L['chl_anom']} (%)", color=COLOR["chl"])
            ax2.grid(False)
            ax.set_title(f"{L['impact']}: {nombre(ev['name'])} ({ev['start'][:7]})", loc="left", fontsize=10)
            fig.legend(loc="upper right", fontsize=8)
            fig.tight_layout()
            plt.show()
        '''),
    _md("""
        ## 12. Todo el golfo: mapas del mes

        Se descarga la malla mensual completa (0,25° × 264 meses, ≈ 3 MB, `/api/dataset/grid.npz`) y se calculan aquí las
        normales y anomalías de cada celda, con las mismas definiciones que el mapa. Contorno negro: el área elegida.
        Estrellas: eventos que empiezan ±6 meses alrededor del mes. Gris: tierra o fuera del golfo.
        """, """
        ## 12. The whole gulf: maps of the month

        The full monthly grid is downloaded (0.25° × 264 months, ≈ 3 MB, `/api/dataset/grid.npz`) and each cell's normals
        and anomalies are computed here, with the same definitions as the map. Black outline: the selected area. Stars:
        events starting within ±6 months of the month. Grey: land or outside the gulf.
        """),
    _code(r'''
        crudo = cli.get_bytes("/api/dataset/grid.npz")
        with np.load(io.BytesIO(crudo), allow_pickle=False) as z:
            G = {k: z[k] for k in z.files}
        G_MESES = [str(m) for m in G["months"]]
        LATS, LONS, SST, CHL = G["lats"].astype(float), G["lons"].astype(float), G["sst"], G["chl"]
        ANIO = np.array([int(m[:4]) for m in G_MESES])
        MDA = np.array([int(m[5:7]) for m in G_MESES])
        FECHAS = pd.to_datetime([m + "-15" for m in G_MESES])
        print(f"{SST.shape[0]} × {SST.shape[1]} × {SST.shape[2]} · {len(crudo) / 1e6:.1f} MB")

        with np.errstate(all="ignore"):
            CLIM_SST = np.stack([np.nanmean(SST[MDA == k], axis=0) for k in range(1, 13)])
            LOG_CHL = np.log10(CHL)
            CLIM_LCHL = np.stack([np.nanmean(LOG_CHL[MDA == k], axis=0) for k in range(1, 13)])
            ANOM_SST = SST - CLIM_SST[MDA - 1]
            LR_CHL = LOG_CHL - CLIM_LCHL[MDA - 1]                 # log10(valor / normal)
            ANOM_CHL = (10 ** LR_CHL - 1) * 100

        RES = float(G["grid_res"])
        LON_B = np.r_[LONS - RES / 2, LONS[-1] + RES / 2]
        LAT_B = np.r_[LATS - RES / 2, LATS[-1] + RES / 2]


        def mapa(ax, campo, titulo, cmap, norm=None, etiqueta="", eventos=()):
            ax.set_facecolor("#dcd6c8")
            m = ax.pcolormesh(LON_B, LAT_B, np.ma.masked_invalid(campo), cmap=cmap, norm=norm, shading="flat")
            ax.plot(POLI[:, 0], POLI[:, 1], color="k", lw=1.6)
            for e in eventos:
                ax.plot(e["lon"], e["lat"], marker="*", ms=12, mfc=COLOR[e["type"]], mec="k", mew=0.6, ls="none")
            ax.set_aspect(1 / np.cos(np.deg2rad(LATS.mean())))
            ax.set_xlim(LON_B[0], LON_B[-1])
            ax.set_ylim(LAT_B[0], LAT_B[-1])
            ax.grid(False)
            ax.set_title(titulo, loc="left", fontsize=10)
            plt.colorbar(m, ax=ax, shrink=0.85, label=etiqueta)
            return m


        k = G_MESES.index(MES)
        activos = [e for e in EVENTOS if abs((fecha(e["start"]) - fecha(MES)).days) <= 183]
        fig, axs = plt.subplots(2, 2, figsize=(13, 9))
        mapa(axs[0, 0], SST[k], f"{L['sst']} · {MES}", "turbo", None, "°C", activos)
        mapa(axs[0, 1], ANOM_SST[k], f"{L['sst_anom']} · {MES}", "RdBu_r", mcolors.TwoSlopeNorm(0, -3, 3), "°C", activos)
        mapa(axs[1, 0], CHL[k], f"{L['chl']} · {MES}", "viridis", mcolors.LogNorm(0.03, 10), "mg/m³", activos)
        mapa(axs[1, 1], ANOM_CHL[k], f"{L['chl_anom']} · {MES}", "BrBG", mcolors.TwoSlopeNorm(0, -75, 150), "%", activos)
        fig.suptitle(f"{TITULO} · {len(activos)} {L['active']}", fontweight="bold")
        fig.tight_layout()
        plt.show()
        '''),
    _md("""
        ## 13. Tendencias 2003–2024 en cada celda

        Para cada celda: medias anuales (años con ≥ 10 meses), regresión lineal contra el año y pendiente × 10 = cambio por
        década (clorofila en escala logarítmica, expresada en %). Puntos negros: tendencia significativa (p < 0,05,
        prueba t). Sirve para ver si el área elegida es un punto caliente o sigue el patrón regional.
        """, """
        ## 13. 2003–2024 trends in every cell

        For each cell: annual means (years with ≥ 10 months), linear regression against the year and slope × 10 = change
        per decade (chlorophyll on a log scale, expressed in %). Black dots: significant trend (p < 0.05, t-test). Use it
        to see whether the selected area is a hotspot or follows the regional pattern.
        """),
    _code(r'''
        def tendencia_celdas(A, log=False):
            anios = np.unique(ANIO).astype(float)
            Y = np.full((anios.size,) + A.shape[1:], np.nan)
            with np.errstate(all="ignore"):
                B = np.log10(A) if log else A
                for i, a in enumerate(anios):
                    bloque = B[ANIO == a]
                    Y[i] = np.where(np.isfinite(bloque).sum(axis=0) >= 10, np.nanmean(bloque, axis=0), np.nan)
                ok = np.isfinite(Y)
                n = ok.sum(axis=0)
                T = np.broadcast_to(anios[:, None, None], Y.shape)
                tm = np.where(ok, T, 0).sum(axis=0) / n
                ym = np.where(ok, Y, 0).sum(axis=0) / n
                dt, dy = np.where(ok, T - tm, 0.0), np.where(ok, Y - ym, 0.0)
                sxx = (dt ** 2).sum(axis=0)
                b = (dt * dy).sum(axis=0) / sxx
                s2 = (np.where(ok, dy - b * dt, 0.0) ** 2).sum(axis=0) / (n - 2)
                tstat = b / np.sqrt(s2 / sxx)
            try:
                from scipy import stats
                p = 2 * stats.t.sf(np.abs(tstat), np.maximum(n - 2, 1))
            except ImportError:                       # sin scipy: umbral aproximado de t para ~20 grados de libertad
                p = np.where(np.abs(tstat) > 2.09, 0.01, 1.0)
            valido = n >= 8
            b, p = np.where(valido, b, np.nan), np.where(valido, p, np.nan)
            return ((10 ** (b * 10) - 1) * 100 if log else b * 10), p


        TEND_SST, P_SST = tendencia_celdas(SST)
        TEND_CHL, P_CHL = tendencia_celdas(CHL, log=True)
        fig, axs = plt.subplots(1, 2, figsize=(14, 5))
        for ax, (tend, p, var, cmap) in zip(axs, ((TEND_SST, P_SST, "sst", "RdBu_r"), (TEND_CHL, P_CHL, "chl", "BrBG"))):
            lim = float(np.nanpercentile(np.abs(tend), 98)) or 1.0
            mapa(ax, tend, f"{L[var]} · {L['trend_map']} ({L['signif']})", cmap,
                 mcolors.TwoSlopeNorm(0, -lim, lim), f"{UNI_ANOM[var]}{L['per_dec']}")
            jj, ii = np.nonzero(p < 0.05)
            ax.scatter(LONS[ii], LATS[jj], s=1.2, c="k", alpha=0.45)
        fig.tight_layout()
        plt.show()

        tabla_tend = pd.DataFrame({
            f"{L[var]} ({UNI_ANOM[var]}{L['per_dec']})": {
                L["area"]: ts[var]["trend_per_decade"],
                f"{L['gulf']} (P50)": float(np.nanmedian(t)),
                f"% {L['gulf_cells']}": float(100 * np.mean(p[np.isfinite(p)] < 0.05)) if np.isfinite(p).any() else np.nan}
            for var, t, p in (("sst", TEND_SST, P_SST), ("chl", TEND_CHL, P_CHL))})
        display(tabla_tend.round(3))
        '''),
    _md("""
        ## 14. Diagrama de Hovmöller

        Anomalía de TSM promediada en longitud para cada latitud (eje vertical) y cada mes (eje horizontal). Las franjas
        verticales son episodios de todo el golfo (p. ej. olas de calor); los triángulos marcan el inicio y la latitud
        de los eventos documentados. Franja sombreada: latitudes del área elegida.
        """, """
        ## 14. Hovmöller diagram

        SST anomaly averaged over longitude for each latitude (vertical axis) and month (horizontal axis). Vertical
        stripes are gulf-wide episodes (e.g. heatwaves); triangles mark the start and latitude of documented events.
        Shaded band: latitudes of the selected area.
        """),
    _code(r'''
        with np.errstate(all="ignore"):
            hov = np.nanmean(ANOM_SST, axis=2)                      # (meses, latitudes)
        filas_ok = np.isfinite(hov).any(axis=0)
        fig, ax = plt.subplots(figsize=(13, 4.8))
        m = ax.pcolormesh(FECHAS, LATS[filas_ok], hov[:, filas_ok].T, cmap="RdBu_r",
                          norm=mcolors.TwoSlopeNorm(0, -2, 2), shading="nearest")
        fig.colorbar(m, ax=ax, label="°C")
        ax.axhspan(POLI[:, 1].min(), POLI[:, 1].max(), color="k", alpha=0.08)
        for e in EVENTOS:
            ax.plot(fecha(e["start"]), e["lat"], marker="v", ms=6, mfc=COLOR[e["type"]], mec="k", mew=0.5, ls="none")
        ax.axvline(fecha(MES), color="k", lw=1, ls=":")
        ax.set_ylabel(L["lat"])
        ax.grid(False)
        ax.set_title(L["hov"], loc="left", fontsize=10)
        plt.show()
        '''),
    _md("""
        ## 15. ¿Cambio local o de todo el golfo?

        Compara la anomalía del área con la anomalía media de todo el golfo (ponderada por superficie). Si la diferencia
        área − golfo en el mes elegido es mucho mayor que su variación habitual (|z| > 2), el área tiene una **señal
        local** que conviene investigar (descargas, derrames, surgencias…); si no, el cambio es regional (clima).
        """, """
        ## 15. Local or gulf-wide change?

        Compares the area's anomaly with the mean anomaly of the whole gulf (area-weighted). If the area − gulf
        difference in the selected month is much larger than its usual variation (|z| > 2), the area has a **local
        signal** worth investigating (discharges, spills, upwelling…); otherwise the change is regional (climate).
        """),
    _code(r'''
        PESO_LAT = np.cos(np.deg2rad(LATS))[None, :, None]


        def media_golfo(A):
            ok = np.isfinite(A)
            w = np.where(ok, PESO_LAT, 0.0)
            return (np.where(ok, A, 0.0) * w).sum(axis=(1, 2)) / w.sum(axis=(1, 2))


        with np.errstate(all="ignore"):
            golfo = {"sst": pd.Series(media_golfo(ANOM_SST), index=FECHAS),
                     "chl": pd.Series((10 ** media_golfo(LR_CHL) - 1) * 100, index=FECHAS)}
        comp, resumen_lg = {}, {}
        fig, axs = plt.subplots(2, 1, figsize=(12, 6.5), sharex=True)
        for ax, var in zip(axs, ("sst", "chl")):
            c = pd.DataFrame({L["area"]: mensual[var]["anomalia"], L["gulf"]: golfo[var]})
            c[L["diff"]] = c[L["area"]] - c[L["gulf"]]
            comp[var] = c
            suave = c.rolling(12, center=True, min_periods=8).mean()
            ax.fill_between(c.index, 0, c[L["diff"]], color="0.6", alpha=0.35, lw=0, label=L["diff"])
            ax.plot(suave.index, suave[L["area"]], color=COLOR[var], lw=1.6, label=f"{L['area']} ({L['roll']})")
            ax.plot(suave.index, suave[L["gulf"]], color="k", lw=1.2, ls="--", label=f"{L['gulf']} ({L['roll']})")
            ax.axhline(0, color="0.3", lw=0.8)
            ax.axvline(fecha(MES), color="k", lw=1, ls=":")
            ax.set_ylabel(f"{L['anom']} ({UNI_ANOM[var]})")
            ax.set_title(L[var], loc="left", fontsize=10)
            d = c[L["diff"]]
            dm = d.get(fecha(MES), np.nan)
            z = (dm - d.mean()) / d.std() if d.std() else np.nan
            resumen_lg[L[var]] = {"r": round(c[L["area"]].corr(c[L["gulf"]]), 3),
                                  f"{L['diff']} {MES}": round(float(dm), 2), "z": round(float(z), 2),
                                  "→": L["local_sig"] if abs(z) > 2 else L["gulf_sig"]}
        axs[0].legend(loc="upper left", fontsize=8, ncol=3)
        fig.suptitle(f"{TITULO} — {L['local_vs_gulf']}", fontweight="bold")
        fig.tight_layout()
        plt.show()
        resumen_lg = pd.DataFrame(resumen_lg)
        display(resumen_lg)
        '''),
    _md("""
        ## 16. Radar de apertura sintética (SAR)

        El SAR emite microondas y mide el eco del mar: funciona de día, de noche y a través de las nubes.

        * **Superficie amortiguada (posibles manchas):** % de observaciones en que el eco es < 50 % del esperado por el
          modelo CMOD para el viento del momento (ECMWF, 3–10 m/s). El petróleo y otras películas alisan el oleaje;
          algas, lluvia o calma local producen el mismo efecto.
        * **Objetos brillantes:** % de observaciones con ecos muy fuertes (barcos y plataformas).
        * **Viento del radar:** velocidad media del viento estimada por la rugosidad del mar.

        Fuente: Sentinel-1 Level-2 OCN (ESA/Copernicus) vía NASA ASF DAAC, procesado con `scripts/build_sar.py`
        (2 escenas por huella y año, 2017–2024). La segunda tabla lista las escenas SAR de todas las misiones que cubren
        el área en el mes elegido (búsqueda en vivo, sin cuenta), con su enlace de descarga en ASF Vertex.
        """, """
        ## 16. Synthetic aperture radar (SAR)

        SAR sends microwaves and measures the sea's echo: it works day and night and through clouds.

        * **Damped surface (possible slicks):** % of observations where the echo is < 50 % of what the CMOD model
          expects for the current wind (ECMWF, 3–10 m/s). Oil and other films smooth the waves; algae, rain or local
          calm do the same.
        * **Bright targets:** % of observations with very strong echoes (ships and platforms).
        * **Radar wind:** mean wind speed estimated from sea roughness.

        Source: Sentinel-1 Level-2 OCN (ESA/Copernicus) via NASA ASF DAAC, processed with `scripts/build_sar.py`
        (2 scenes per footprint and year, 2017–2024). The second table lists the SAR scenes of every mission covering
        the area in the selected month (live search, no account) with their ASF Vertex download link.
        """),
    _code(r'''
        tabla_sar = tabla_escenas = pd.DataFrame()
        if meta.get("sar", {}).get("available"):
            sa = cli.get("/api/sar/area", **SEL)
            cols = {"damped_pct": L["sar_damped"] + " (%)", "bright_pct": L["sar_bright"] + " (%)",
                    "wind": L["sar_wind"] + " (m/s)", "n": L["n"]}
            tabla_sar = pd.DataFrame(sa["years"] + [{"year": "2017–2024", **sa["all"]}]).set_index("year")
            tabla_sar = tabla_sar.rename(columns=cols)[list(cols.values())]
            tabla_sar.index.name = L["year"]
            display(tabla_sar)

            fig, axs = plt.subplots(1, 3, figsize=(16, 4.8))
            for ax, (var, cmap, norm) in zip(axs, (("sar_damped", "YlOrRd", mcolors.PowerNorm(0.5, 0, 10)),
                                                   ("sar_bright", "magma", mcolors.PowerNorm(0.5, 0, 10)),
                                                   ("sar_wind", "viridis", mcolors.Normalize(3, 9)))):
                g = cli.get(f"/api/sar/grid/{var}")
                A = np.array(g["values"], dtype=float)
                la, lo, r = np.array(g["lats"]), np.array(g["lons"]), g["res"]
                ax.set_facecolor("#dcd6c8")
                m = ax.pcolormesh(np.r_[lo - r / 2, lo[-1] + r / 2], np.r_[la - r / 2, la[-1] + r / 2],
                                  np.ma.masked_invalid(A), cmap=cmap, norm=norm, shading="flat")
                ax.plot(POLI[:, 0], POLI[:, 1], color="k", lw=1.5)
                ax.set_aspect(1 / np.cos(np.deg2rad(la.mean())))
                ax.grid(False)
                ax.set_title(f"{L[var]} · 2017–2024", loc="left", fontsize=10)
                plt.colorbar(m, ax=ax, shrink=0.8, label="m/s" if var == "sar_wind" else "%")
            fig.tight_layout()
            plt.show()
        else:
            print(L["no_sar"])

        try:
            esc = cli.get("/api/sar/scenes", month=MES, **SEL)
            tabla_escenas = pd.DataFrame([{L["mission"]: m, L["start"]: s["start"], "id": s["id"], "ASF Vertex": s["vertex"]}
                                          for m, d in esc["missions"].items() for s in d.get("scenes", [])])
            print(" · ".join(f"{m}: {d.get('total', 0)}" for m, d in esc["missions"].items()), f"({esc['from']} → {esc['to']})")
            if not tabla_escenas.empty:
                display(tabla_escenas)
        except Exception as err:          # ASF es un servicio externo
            print("ASF:", err)

        # Detector de manchas NISAR (banda L, 2025–2026): zonas donde una película viscosa alisa el mar
        tabla_manchas = pd.DataFrame()
        mm = cli.get("/api/sar/slicks")
        if mm.get("available"):
            tabla_manchas = pd.DataFrame([{"fecha": e["start"][:10], "pol": e.get("pol"), **x}
                                          for e in mm["scenes"] for x in e["detections"]])
            if not tabla_manchas.empty:
                tabla_manchas = tabla_manchas.sort_values(["confidence", "area_km2"], ascending=[True, False])
                print(f"NISAR: {len(mm['scenes'])} escenas · {len(tabla_manchas)} zonas ·",
                      tabla_manchas["confidence"].value_counts().to_dict())
                display(tabla_manchas.head(20))
        '''),
    _md("""
        ## 17. Exportar resultados

        Guarda todas las tablas en la carpeta `resultados/` como CSV (UTF-8, se abren en Excel) y, si `openpyxl` está
        disponible, en un único libro de Excel. En el navegador (JupyterLite) los archivos aparecen en el panel de
        archivos de la izquierda: clic derecho ▸ *Download*.
        """, """
        ## 17. Export results

        Saves every table to the `resultados/` folder as CSV (UTF-8, opens in Excel) and, if `openpyxl` is available, into
        a single Excel workbook. In the browser (JupyterLite) the files appear in the file panel on the left:
        right-click ▸ *Download*.
        """),
    _code(r'''
        carpeta = Path("resultados")
        carpeta.mkdir(exist_ok=True)
        base = re.sub(r"[^0-9A-Za-z_.-]+", "_", f"golfo_{MES}_{valor_sel}")[:70].strip("_")
        tablas = {
            "resumen": tabla_resumen, "TSM_mensual": mensual["sst"], "clorofila_mensual": mensual["chl"],
            "TSM_anual": anual["sst"], "clorofila_anual": anual["chl"],
            "TSM_mismo_mes": mismo_mes["sst"], "clorofila_mismo_mes": mismo_mes["chl"],
            "correlacion_desfase": corr, "profundidad": clases, "eventos_impacto": impactos,
            "especies_top": top, "OBIS_por_anio": por_anio, "lista_roja": roja,
            "tendencias": tabla_tend, "area_vs_golfo_TSM": comp["sst"], "area_vs_golfo_clorofila": comp["chl"],
            "area_vs_golfo_resumen": resumen_lg, "radar_SAR": tabla_sar, "radar_escenas": tabla_escenas,
            "manchas_NISAR": tabla_manchas,
        }
        tablas = {k: t for k, t in tablas.items() if isinstance(t, pd.DataFrame) and not t.empty}
        for clave_t, t in tablas.items():
            t.to_csv(carpeta / f"{base}_{clave_t}.csv", encoding="utf-8-sig")
        print(f"{L['saved']} {carpeta.resolve()} · {len(tablas)} CSV")
        if EN_NAVEGADOR:             # en JupyterLite, openpyxl (Excel) se instala desde PyPI la primera vez
            try:
                import piplite
                await piplite.install("openpyxl")
            except Exception as err:
                print("openpyxl:", err)
        try:
            import openpyxl  # noqa: F401
            ruta_xlsx = carpeta / f"{base}.xlsx"
            with pd.ExcelWriter(ruta_xlsx) as libro:
                for clave_t, t in tablas.items():
                    t.to_excel(libro, sheet_name=clave_t[:31])
            print(f"{L['saved']} {ruta_xlsx.resolve()}")
        except ImportError:
            print("openpyxl no está instalado: solo se guardaron los CSV (pip install openpyxl)")
        '''),
    _md("""
        ## Notas y fuentes

        * **Temperatura superficial:** NASA JPL MUR SST v4.1 (mensual), vía NOAA CoastWatch ERDDAP `jplMURSST41mday`.
        * **Clorofila-a:** NASA OBPG MODIS-Aqua L3 R2022 (mensual, 4 km), vía ERDDAP `erdMH1chlamday_R2022SQ`. Puede
          sobrestimarse en aguas turbias cerca de ríos y lagunas.
        * **Batimetría:** NOAA ETOPO1. **Biodiversidad:** OBIS (obis.org). **Eventos:** NOAA NHC, NOAA OR&R, USACE, FWC,
          NPS, NOAA Coral Reef Watch, Pemex (ubicaciones y radios aproximados).
        * Malla de 0,25° (~25 km) y datos mensuales: no resuelven fenómenos de días ni de escala costera fina.
        * **Ampliar:** añade tus propios datos (muestreos de campo, estaciones) con `pd.read_csv(...)` y compáralos con
          `mensual["sst"]` o `mensual["chl"]`, que tienen índice mensual.
        """, """
        ## Notes and sources

        * **Sea surface temperature:** NASA JPL MUR SST v4.1 (monthly), via NOAA CoastWatch ERDDAP `jplMURSST41mday`.
        * **Chlorophyll-a:** NASA OBPG MODIS-Aqua L3 R2022 (monthly, 4 km), via ERDDAP `erdMH1chlamday_R2022SQ`. It can be
          overestimated in turbid water near rivers and lagoons.
        * **Bathymetry:** NOAA ETOPO1. **Biodiversity:** OBIS (obis.org). **Events:** NOAA NHC, NOAA OR&R, USACE, FWC,
          NPS, NOAA Coral Reef Watch, Pemex (approximate locations and radii).
        * 0.25° grid (~25 km) and monthly data: they do not resolve day-scale or fine coastal phenomena.
        * **Extend:** add your own data (field samples, stations) with `pd.read_csv(...)` and compare it with
          `mensual["sst"]` or `mensual["chl"]`, which have a monthly index.
        """),
]


def _parametros(lang: str, seleccion: str, mes: str, titulo: str, api: str) -> str:
    return "\n".join([
        "# Parámetros del análisis · Analysis parameters",
        f"SELECCION = {seleccion!r}   # \"bbox=oeste,sur,este,norte\" o \"poly=lon,lat;lon,lat;…\"",
        f"MES = {mes!r}                       # 2003-01 … 2024-12",
        f"TITULO = {titulo!r}",
        f"API = {api!r}                          # \"auto\" · \"local\" · \"http://localhost:8000\" · \"https://…\"",
        f"IDIOMA = {lang!r}                       # \"es\" · \"en\"",
    ])


def _fuente(texto: str) -> list[str]:
    lineas = texto.split("\n")
    return [ln + "\n" for ln in lineas[:-1]] + [lineas[-1]]


def construir_cuaderno(lang: str = "es", seleccion: str | None = None, mes: str | None = None,
                       titulo: str | None = None, api: str = "auto", destino: str = "local") -> dict:
    """Devuelve el cuaderno (formato nbformat 4.5 como dict) con los parámetros dados.

    `seleccion` debe venir ya validada (``seleccion_a_texto``) y `titulo` limpio (``limpiar_titulo``);
    `destino` = 'local' (kernel python3) o 'lite' (kernel Pyodide de JupyterLite).
    """
    lang = lang if lang in ("es", "en") else "es"
    params = _parametros(lang, seleccion or DEFECTO["seleccion"], mes or DEFECTO["mes"],
                         titulo or DEFECTO["titulo"][lang], api)
    celdas = []
    for i, celda in enumerate(CELDAS, start=1):
        tipo = celda[0]
        if tipo == "markdown":
            celdas.append({"cell_type": "markdown", "id": f"c{i:02d}", "metadata": {},
                           "source": _fuente(celda[1][lang])})
            continue
        es_param = celda[1] == PARAMETROS
        celdas.append({"cell_type": "code", "execution_count": None, "id": f"c{i:02d}",
                       "metadata": {"tags": ["parameters"]} if es_param else {}, "outputs": [],
                       "source": _fuente(params if es_param else celda[1])})
    return {
        "cells": celdas,
        "metadata": {
            "kernelspec": KERNELS.get(destino, KERNELS["local"]),
            "language_info": {"name": "python", "pygments_lexer": "ipython3"},
            "title": "Golfo de México · Observatorio MIA" if lang == "es" else "Gulf of Mexico · EIA Observatory",
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
