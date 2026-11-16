# Golfo de México · Observatorio MIA

[English](README.md) · **Español** · Demo: https://golfo-mexico-mia.onrender.com · Reto NASA Space Apps 2026:
*Dancing with the SARs*

> **Uso de IA:** Se usó IA generativa (Claude Code) como herramienta para generar código y enlazar recursos.

Aplicación web bilingüe (español / inglés) para explorar el Golfo de México como apoyo a un Manifiesto de Impacto
Ambiental: **profundidad, temperatura superficial, clorofila (fitoplancton), vida marina y eventos naturales y
humanos** (huracanes, derrames, marea roja, hipoxia, olas de calor…) entre 2003 y 2024, con datos reales.

## Qué hace
- **Mapa interactivo** (Leaflet) con 6 variables: TSM, anomalía de TSM, cambio de TSM frente al año anterior,
  clorofila-a, anomalía de clorofila y batimetría; capas de eventos, áreas protegidas, registros de biodiversidad
  (OBIS) e imágenes diarias de NASA GIBS.
- **Selección por celda de 1°** (clic) o **área** (rectángulo / polígono) → **ventana emergente** con temperatura,
  clorofila, profundidad, vida marina, tendencia 2003–2024 y eventos relacionados con la zona.
- Al hacer clic en una característica: **tabla de cambios** (sube / baja / estable por año y por mes), **serie
  temporal** con los eventos marcados y **gráfico 3D** (relieve coloreado por la variable, o espacio
  TSM–clorofila–profundidad). Todo cambia con la **línea de tiempo** (▶ para animar).
- **Análisis de eventos**: compara las anomalías 3 meses antes y después de cada evento en su radio de impacto, con
  gráfico ±24 meses. Las marcas sobre la línea de tiempo permiten buscar relaciones entre cambios y desastres.
  *Coincidencia no implica causalidad*; la interfaz lo recuerda. Solo se muestran eventos dentro de 2003–2024.
- **Búsqueda y filtros**: buscador global (eventos, lugares o coordenadas como `28.7, -88.4`) y filtros de eventos
  (texto, natural/humano, categoría, años, solo activos) que se aplican a la lista, al mapa y a la línea de tiempo;
  filtro de años en las tablas y gráficos del detalle.
- **Descarga a Excel**: botón ⤓ en la ventana del área y en el detalle → informe .xlsx con todas las tablas (filtradas),
  gráficos nativos de Excel e imágenes de los gráficos (incluidos los 3D); también para el análisis de cada evento.
- **Radar de apertura sintética (SAR)**: mapas anuales 2017–2024 de *superficie amortiguada* (posibles manchas de
  petróleo o películas), *objetos brillantes* (barcos y plataformas) y *viento medido por el radar* a partir de
  Sentinel-1 OCN; capa con las escenas de radar de cada mes (Sentinel-1, ALOS PALSAR, UAVSAR, NISAR) y sus imágenes
  sobre el mapa; fila «Radar SAR» en la ventana del área; y en cada evento, comparación antes/después con el radar y el
  mapa de viento del radar (p. ej. huracanes).
- **Cuaderno de Jupyter**: botón 📓 *Cuaderno* (arriba) abre Jupyter dentro de la página (JupyterLite: Python corre en
  el navegador del visitante, sin instalar nada); el botón 📓 de la ventana del área abre un cuaderno ya preparado para
  esa área y mes (16 secciones: resumen, series, tablas sube/baja, anomalías, ciclo estacional, relación TSM–clorofila,
  profundidad, OBIS, eventos antes/después, mapas del golfo, tendencias por celda, Hovmöller, señal local vs. golfo y
  exportación a CSV/Excel). «⤓ .ipynb» lo descarga para Jupyter en la computadora.
- **Interfaz**: ventanas semitransparentes (fondo al 20 % con desenfoque), ventana del área compacta, movible y
  minimizable, y línea de tiempo baja y transparente sobre el mapa.

Documentación técnica completa (arquitectura, fórmulas, API, exportación, cómo extender): [docs/DOCUMENTACION.md](docs/DOCUMENTACION.md).

## Fuentes de datos (todas abiertas y reales)
| Variable | Fuente | Acceso |
|---|---|---|
| Temperatura superficial (mensual) | NASA JPL MUR SST v4.1 | NOAA CoastWatch ERDDAP `jplMURSST41mday` |
| Clorofila-a (mensual) | NASA MODIS-Aqua L3 R2022 | NOAA CoastWatch ERDDAP `erdMH1chlamday_R2022SQ` |
| Batimetría | NOAA ETOPO1 | NOAA CoastWatch ERDDAP `etopo180` |
| Biodiversidad | OBIS (Ocean Biodiversity Information System) | API v3 (en vivo, con caché) |
| Imágenes diarias | NASA GIBS | WMTS |
| Radar SAR | Sentinel-1 OCN/GRD (ESA/Copernicus), ALOS PALSAR (JAXA), UAVSAR y NISAR (NASA) | NASA ASF DAAC (búsqueda pública; descarga con token Earthdata) |
| Eventos | NOAA NHC, NOAA OR&R, USACE, FWC, NPS, NOAA Coral Reef Watch, Pemex | `data/events.json` (curado, ubicaciones aproximadas) |

Malla de análisis de 0,25°, solo dentro del Golfo (Caribe y Atlántico enmascarados) y solo agua conectada al mar
(se excluyen presas y lagos).

## Puesta en marcha
```bash
pip install -r requirements.txt
python scripts/build_dataset.py          # descarga y procesa (≈10 min la 1.ª vez; ya incluido en data/processed)
uvicorn backend.main:app --port 8000     # abre http://localhost:8000  ·  documentación API: /docs
```

## Radar SAR
| Parte | Fuente | Cuenta |
|---|---|---|
| Escenas del mes, vistas previas, enlaces de descarga | NASA ASF DAAC (búsqueda en vivo) | no |
| Mapas anuales y antes/después de eventos | Sentinel-1 Level-2 OCN procesado por `scripts/build_sar.py` | token NASA Earthdata |

```bash
# token: https://urs.earthdata.nasa.gov → Generate Token, guardado en ~/.earthdata_token (o variable EARTHDATA_TOKEN)
python scripts/build_sar.py            # ≈ 2 300 escenas (~16 GB descargados y descartados); reanudable
python scripts/build_sar.py --solo-agregar
```
- El token solo se envía a dominios de NASA/ASF y nunca se guarda en el proyecto ni se publica; los visitantes solo ven
  los resultados procesados (`data/processed/sar_composite.nc`, `sar_events.json`, `sar_img/`).
- *Superficie amortiguada*: σ⁰ observada < 50 % de la esperada por el modelo CMOD con viento ECMWF de 3–10 m/s. Es el
  criterio clásico de manchas en SAR, pero algas, lluvia o calma local dan falsos positivos: «posibles manchas».
- Cobertura: Sentinel-1 desde 2014 (útil desde 2017), ALOS PALSAR 2006–2011, UAVSAR desde 2009 (vuelos), NISAR desde
  2025. No hay SAR de 2003–2005 en ASF.
- Limitaciones: es una muestra (≈ 1 080 escenas de ~13 000); se descartan 3 km en los bordes de cada franja y 2 km junto
  a la costa, pero quedan algunas trazas en bordes y diferencias entre pasadas; la amortiguación es alta en plataformas
  someras con calma frecuente (Florida, Yucatán), donde también hay películas biológicas.

## Detector de manchas · NISAR banda L
Capa *🛢 Detector de manchas* (Capas): zonas donde el mar se ve **alisado** por una película más viscosa que el agua
(petróleo, emulsión o película biológica), con el radar **NISAR** (NASA-ISRO, banda L de 24 cm, 2025–2026).

- **Qué mide**: el radar no mide la densidad del agua; mide el eco de las ondas cortas (de cm a dm). Un derrame cambia
  la **viscosidad y la tensión superficial**, amortigua esas ondas y el eco cae: la zona se ve oscura. Se calcula la
  razón de amortiguamiento DR = σ⁰(mar alrededor) / σ⁰(zona) en dB (co-polar HH o VV) y también en la cruzada (HV/VH).
- **Cómo**: de cada producto NISAR L2 GCOV (6 GB) se leen por rangos HTTP solo las bandas de 80 m (~30 MB). Mar a
  > 2 km de tierra y ≥ 10 m de profundidad; fondo local de 6,5 km; zonas con DR ≥ 2 dB y ≥ 1 km² (umbral calibrado:
  el 99 % del mar abierto queda < 1,4 dB). Confianza: **alta** (DR ≥ 3,5 dB, alargada ≥ 4:1 y ≤ 3 km de ancho, como una
  mancha a la deriva), **media** (resto) o **calma** (fondo < −24 dB: sin viento todo se ve oscuro). Si > 1,5 % del mar
  de una escena está amortiguado se marca *tiempo variable* (lluvia, ráfagas) y ninguna zona queda como alta.
- **Regenerar**: `python scripts/build_slicks.py --max 70` (token Earthdata) → `data/processed/slicks.json` y
  `data/processed/slicks/*.png`.
- **Limitaciones**: productos NISAR provisionales; falsos positivos por calma, lluvia, surgencias y películas
  biológicas. Es un sistema de **alerta y exploración**: la confirmación requiere otras fuentes (NOAA OR&R, ópticas).

## Jupyter
| Uso | Cómo |
|---|---|
| En la aplicación (sin instalar nada) | botón 📓 *Cuaderno* o 📓 en la ventana del área → JupyterLite en `/jupyter` |
| En tu computadora, con los datos del proyecto | `pip install jupyterlab matplotlib` y abre `notebooks/Golfo_Mexico_MIA_es.ipynb` (o `_en`): importa `backend/` directamente, no necesita el servidor |
| En otra computadora | descarga el .ipynb con «⤓ .ipynb»; lee la API pública (`API = "https://…"`) y solo necesita `numpy pandas matplotlib` |

```bash
pip install "jupyterlite-core==0.6.*" "jupyterlite-pyodide-kernel==0.6.*"
python scripts/build_jupyterlite.py      # regenera notebooks/*.ipynb y jupyterlite/ (≈ 26 MB) tras cambiar backend/notebook.py
```
- El cuaderno se define una sola vez en `backend/notebook.py` (español e inglés); la API genera la versión de cada área
  (`GET /api/notebook`) y la malla mensual completa para el análisis de todo el golfo (`GET /api/dataset/grid.npz`, ≈ 4 MB).
- En JupyterLite el código se ejecuta en el navegador de cada visitante (Pyodide/WebAssembly): el servidor solo entrega
  archivos, así que publicar `/jupyter` no permite ejecutar código en esta computadora. Pyodide y las librerías se
  descargan del CDN jsDelivr la primera vez (≈ 1 min); los cambios y resultados quedan solo en ese navegador.

## Publicar en Render (enlace fijo, gratis)
1. https://render.com → *Sign up with GitHub*.
2. *New → Blueprint* → elegir este repositorio → *Apply*. Render lee `render.yaml`: instala `requirements.txt` y
   arranca `uvicorn` (≈ 10 min la primera vez). Jupyter en el navegador (`jupyterlite/`) ya va generado en el
   repositorio; si cambias el cuaderno, regenéralo con `python scripts/build_jupyterlite.py` y súbelo.
3. El enlace queda como `https://golfo-mexico-mia.onrender.com`. Cada `git push` a `main` vuelve a desplegar.
- Plan gratuito: se duerme tras 15 min sin visitas; la siguiente visita tarda ~1 min. Usa ~200 MB de RAM (límite 512 MB).

## Publicar en internet desde esta computadora (túnel temporal de Cloudflare)
```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --no-server-header
cloudflared tunnel --url http://127.0.0.1:8000 --no-autoupdate      # imprime https://…trycloudflare.com
```
- `cloudflared` se descarga del GitHub oficial de Cloudflare (`cloudflared-windows-amd64.exe`); no requiere cuenta.
- La dirección cambia cada vez y solo funciona mientras la computadora y ambos procesos estén encendidos.
- El servidor ya incluye protecciones para uso público (`backend/security.py`): límite de 30 MB por petición,
  300 peticiones/min y 6 exportaciones/min por visitante (IP real vía `CF-Connecting-IP`) y cabeceras de seguridad.
- Para una dirección fija: túnel con nombre de Cloudflare (cuenta + dominio) o un hosting como Render/Fly.io.

## Base de datos (preparado para Python + SQL)
La API usa una capa de acceso a datos intercambiable (`backend/repositories/`):

| Modo | Variable | Origen |
|---|---|---|
| `file` (por defecto) | `GOLFO_DATA_BACKEND=file` | NetCDF/JSON en `data/processed` |
| `sql` | `GOLFO_DATA_BACKEND=sql` + `DATABASE_URL` | SQLite, PostgreSQL/PostGIS… (SQLAlchemy) |

```bash
python scripts/load_to_sql.py                                   # crea data/golfo.sqlite con todas las tablas
GOLFO_DATA_BACKEND=sql uvicorn backend.main:app --port 8000

# PostgreSQL / PostGIS
pip install "psycopg[binary]"
DATABASE_URL=postgresql+psycopg://usuario:clave@host/golfo python scripts/load_to_sql.py
GOLFO_DATA_BACKEND=sql DATABASE_URL=postgresql+psycopg://usuario:clave@host/golfo uvicorn backend.main:app
```
- Esquema: `backend/db/models.py` (SQLAlchemy Core) y `backend/db/schema_postgis.sql` (geometrías e índices GIST).
- Para otro origen (API propia, MongoDB, sensores…) crea una clase que herede de `DataRepository`
  (`backend/repositories/base.py`); la lógica de análisis (`backend/service.py`) no cambia.
- Los dos modos están probados y devuelven resultados idénticos: `python tests/test_api.py`.

## Estructura
```
backend/   main.py (API FastAPI) · service.py (análisis) · export.py (Excel) · notebook.py (cuaderno Jupyter)
           dataset.py (malla .npz) · sar.py + asf.py (radar SAR) · obis.py · geo.py · config.py
           repositories/ (base, archivos, SQL) · db/ (modelos y esquema PostGIS)
frontend/  index.html · css/styles.css · js/ (app, panels, figures, exporter, notebook, search, i18n, api, palettes)
notebooks/ Golfo_Mexico_MIA_es.ipynb · Golfo_Mexico_MIA_en.ipynb (Jupyter local)
jupyterlite/  Jupyter en el navegador (generado) → /jupyter
docs/      DOCUMENTACION.md
scripts/   build_dataset.py (descarga) · load_to_sql.py (carga a base de datos) · build_jupyterlite.py (Jupyter)
           build_sar.py (radar Sentinel-1) · build_slicks.py (detector de manchas NISAR) — requieren token Earthdata
data/      events.json · places.json · processed/ (datos listos)
tests/     test_api.py
```

## Endpoints principales
`/api/meta` · `/api/grid/{var}?month=YYYY-MM` · `/api/area/summary` · `/api/area/timeseries` · `/api/area/surface`
· `/api/area/cells` · `/api/area/depth` · `/api/fauna` · `/api/events` · `/api/events/{id}/impact` · `/api/obis/grid/{año}`
· `POST /api/export/xlsx` · `/api/notebook` · `/api/dataset/grid.npz` · `/api/sar/{meta,grid/{var},area,scenes,browse,events/{id}}`.
Las áreas se indican con `bbox=oeste,sur,este,norte` o `poly=lon,lat;lon,lat;…`.

## Limitaciones
- Datos mensuales a 0,25° (~25 km): no resuelven fenómenos de días o de escala costera fina.
- La clorofila satelital puede sobrestimarse en aguas turbias cerca de ríos y lagunas.
- Los registros OBIS reflejan el esfuerzo de muestreo, no la abundancia.
- Las ubicaciones y radios de los eventos son aproximados y sirven para explorar, no para atribuir causas.
- Para añadir eventos, edita `data/events.json` (campos bilingües `name` y `description`, y `source`).

## Uso de inteligencia artificial
Se usó IA generativa (Claude Code) como herramienta para generar código y enlazar recursos. La idea, el enfoque del
reto, la investigación de eventos y la selección de datos son del equipo. Los datos son mediciones reales de las
fuentes citadas; ningún dato ni imagen de la aplicación fue generado por IA.

## Créditos y referencias
- **NASA:** JPL MUR SST v4.1 (PO.DAAC); MODIS-Aqua L3 clorofila-a R2022 (OBPG); GIBS/EOSDIS; NISAR L2 GCOV (datos
  provisionales, NASA-ISRO); UAVSAR (JPL); ASF DAAC (archivo SAR).
- **Agencias socias:** *Contains modified Copernicus Sentinel data 2017–2024, processed by ESA* (Sentinel-1 OCN y GRD,
  vía NASA ASF) · ALOS PALSAR © JAXA/METI (vía NASA ASF) · NISAR, misión conjunta NASA-ISRO.
- **Otras fuentes:** NOAA ETOPO1 y NOAA CoastWatch ERDDAP; OBIS – Ocean Biodiversity Information System (UNESCO-IOC),
  www.obis.org; eventos: NOAA NHC, NOAA OR&R, NOAA Coral Reef Watch, USACE, FWC, NPS, Pemex; mapas © OpenStreetMap
  contributors y OpenTopoMap (CC-BY-SA).
- **Software de código abierto:** Python, FastAPI, Uvicorn, NumPy, SciPy, pandas, xarray, h5py, h5netcdf, SQLAlchemy,
  requests, openpyxl, Pillow, matplotlib, Jupyter/JupyterLite, Pyodide, Leaflet, Leaflet.draw, Plotly.js.
- Las paletas de color están inspiradas en cmocean y ColorBrewer.

## Licencia
Código bajo licencia MIT (ver [LICENSE](LICENSE)). Los datos conservan las licencias y créditos de sus fuentes.
