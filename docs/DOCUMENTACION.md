# Documentación técnica · Golfo de México · Observatorio MIA

## 1. Arquitectura

```
 Fuentes abiertas                Ingesta (una vez)              Almacén                 API (FastAPI)               Navegador
 ───────────────                 ─────────────────              ───────                 ─────────────               ─────────
 NASA JPL MUR (ERDDAP) ─┐                                     data/processed/*.nc   ┌─ backend/main.py  (rutas) ─┐  index.html
 NASA MODIS-Aqua (ERDDAP)├─► scripts/build_dataset.py ──────►  (o SQL vía           │  backend/service.py (análisis)│  js/app.js     mapa, capas, tiempo
 NOAA ETOPO1 (ERDDAP)  ─┘    (recorte, malla 0,25°,          load_to_sql.py) ──────►│  backend/repositories/*      │  js/panels.js  ventanas, tablas, 3D
 OBIS (API)  ───────────────► máscara del golfo y del mar)                          │  backend/obis.py (en vivo)   │  js/figures.js gráficos Plotly
 data/events.json, places.json (curados) ─────────────────────────────────────────►│  backend/export.py (Excel)  ◄┼─ js/exporter.js informe Excel
                                                                                    └──────────────────────────────┘  js/search.js  búsqueda
```

- **Capa de datos intercambiable** (`backend/repositories/`): `DataRepository` define 10 métodos (ejes, máscara, campo
  mensual, series de celdas, climatología, batimetría, OBIS, eventos, lugares, procedencia). Hay dos implementaciones:
  `FileRepository` (NetCDF/JSON) y `SQLRepository` (SQLAlchemy: SQLite, PostgreSQL/PostGIS). Ambas devuelven resultados
  idénticos (comprobado por `tests/test_api.py`). Se elige con `GOLFO_DATA_BACKEND=file|sql`.
- **Servicio de análisis** (`backend/service.py`): toda la estadística vive aquí y no sabe de dónde vienen los datos.
- **Frontend sin compilación**: módulos ES nativos; Leaflet 1.9.4, Leaflet.draw 1.0.4 y Plotly 2.35.2 desde CDN.

## 2. Ingesta de datos (`scripts/build_dataset.py`)

| Paso | Detalle |
|---|---|
| Descarga | Peticiones ERDDAP `.csv` por año (12 meses en una petición) con *stride*: TSM cada 25 puntos de 0,01° (centros de 0,25°); clorofila cada 3 puntos de 4 km. Reintentos ante 429/5xx y servidor espejo (`upwell`). |
| Agregación | Cada muestra se asigna a su celda de 0,25° (`floor`) y se promedia por celda y mes. |
| Máscara del golfo | `backend/geo.py: GULF_POLYGON` (límites OHI: Canal de Yucatán y Estrecho de Florida) excluye Caribe y Atlántico. |
| Agua continental | `scipy.ndimage.label` con vecindad 8: se conserva solo la mayor componente de agua (el mar); presas y lagos fuera. |
| Batimetría | ETOPO1 cada 5' (1/12°); profundidad = −altitud donde altitud < 0, solo dentro del golfo. |
| OBIS | `/occurrence/grid/3` por año: número de registros por celda geohash (≈1,4° × 0,7°). |
| Caché | `data/raw/` guarda cada año; si se interrumpe, se reanuda. `manifest.json` registra fuentes y fecha. |

## 3. Cálculos (`backend/service.py`)

| Concepto | Fórmula / método |
|---|---|
| Celdas de una selección | Celdas oceánicas cuyo **centro** cae dentro del rectángulo o polígono (ray casting vectorizado). Si ninguna, la más cercana al centro (≤ 0,5°). |
| Media de área TSM | Σ(valor·área celda) / Σ(área celda) con área esférica exacta de cada celda. |
| Media de área clorofila | 10^( Σ(log10 valor·área) / Σ área ) — media geométrica (datos log-normales). |
| Normal (climatología) | Media 2003–2024 del mismo mes del año. |
| Anomalía TSM | valor − normal (°C). |
| Anomalía clorofila | (10^(log10 valor − log10 normal) − 1) × 100 (%). |
| Cambio vs. año anterior | valor(mes) − valor(mes − 12) (TSM, °C) o (valor/valor₋₁₂ − 1)·100 (clorofila, %). |
| Media anual | Media de los meses con dato si hay ≥ 10; si no, vacío (no se rellena). |
| Dirección | Sube / Baja si \|cambio\| > 0,1 °C (TSM) o > 5 % (clorofila / registros OBIS); si no, Estable. |
| Tendencia | `scipy.stats.linregress(año, media anual)` (clorofila sobre log10) → pendiente × 10 = por década; valor p. Significativa si p < 0,05. |
| Profundidad del área | Puntos ETOPO de 1/12° dentro de la selección: mín., media, máx., % < 200 m (plataforma) y clases. |
| Eventos de una zona | Distancia (haversine) del evento al centro ≤ radio del evento + media diagonal de la selección. |
| Evento activo | Mes del mapa entre (inicio − 6 meses) y (fin + 6 meses). |
| Impacto de un evento | Celdas a ≤ `radius_km`; anomalía media de los 3 meses anteriores vs. 3 meses desde el inicio; serie ±24 meses. |
| Superficie 3D | Altitud ETOPO de la caja de la selección (mín. 1,5° × 1,5°, ≤ 110 puntos por eje) + valor de la variable de la celda de 0,25° que contiene cada punto de mar. |

## 4. API REST

| Método y ruta | Parámetros | Devuelve |
|---|---|---|
| `GET /api/health` | — | estado y periodo |
| `GET /api/meta` | — | bbox, polígono del golfo, meses, variables, años OBIS, procedencia |
| `GET /api/grid/{var}` | `month=YYYY-MM` | `lats`, `lons`, `values` (filas S→N, `null` = sin dato). `var`: sst, sst_anom, sst_change, chl, chl_anom, depth |
| `GET /api/area/summary` | `month` + `bbox`/`poly` | contenido de la ventana del área |
| `GET /api/area/timeseries` | `var=sst\|chl`, `month` + selección | serie mensual, tabla anual, mismo mes, tendencia, eventos |
| `GET /api/area/depth` | selección | clases de profundidad |
| `GET /api/area/surface` | `var`, `month` + selección | malla para el relieve 3D |
| `GET /api/area/cells` | `month` + selección | valores por celda (3D de propiedades) |
| `GET /api/fauna` | `year` (opcional) + selección | OBIS: registros, especies, top 15, Lista Roja, registros por año |
| `GET /api/obis/grid/{año}` | — | GeoJSON de registros por celda |
| `GET /api/events` · `GET /api/events/{id}/impact` | — | eventos dentro de 2003–2024 · análisis antes/después |
| `GET /api/places` | — | áreas protegidas y referencias |
| `POST /api/export/xlsx` | JSON `Exportacion` (ver `backend/export.py`) | archivo `.xlsx` |
| `GET /api/notebook[/{nombre}.ipynb]` | `lang=es\|en`, `month`, selección, `title`, `base` (URL de la API), `target=local\|lite` | cuaderno de Jupyter con esos parámetros |
| `GET /api/sar/meta` | — | disponibilidad de productos SAR, años, escenas, método, eventos con análisis |
| `GET /api/sar/grid/{var}` | `year` (opcional) | mapa SAR de 0,1° (`sar_damped`, `sar_bright`, `sar_wind`, `sar_n`) |
| `GET /api/sar/area` | selección | valores SAR del área por año y del periodo |
| `GET /api/sar/scenes` | `month`, `months` (1–3) + selección | escenas de cada misión en NASA ASF con vista previa y enlace a Vertex |
| `GET /api/sar/browse` | `u` (URL de ASF), `w`, `alpha` | vista previa (proxy con lista blanca) |
| `GET /api/sar/events/{id}[/image.png]` | — | antes/después con Sentinel-1 y mapa de viento del radar |
| `GET /api/sar/slicks` · `GET /api/sar/slicks/{escena}.png` | — | detector de manchas NISAR: escenas, zonas y su imagen |
| `GET /api/dataset/grid.npz` | — | malla mensual completa (TSM, clorofila, máscara, profundidad) en NumPy `.npz` (≈ 4 MB) |
| `GET /jupyter/…` | — | JupyterLite (archivos estáticos), si existe la carpeta `jupyterlite/` |

Documentación interactiva generada por FastAPI: `http://localhost:8000/docs`.

## 5. Exportación a Excel

1. `frontend/js/exporter.js` pide los mismos datos que la interfaz, aplica el **filtro de años**, traduce columnas al
   idioma activo y convierte los gráficos de Plotly a PNG con fondo claro (`figures.figureToPng`).
2. `POST /api/export/xlsx` → `backend/export.py` valida (Pydantic: ≤ 30 hojas, ≤ 50 000 filas/hoja, ≤ 12 imágenes de
   ≤ 6 MB), escribe cada hoja con cabecera fija, añade **gráficos nativos de Excel** (líneas/barras, editables) y una
   hoja «Gráficos» con las imágenes (incluidos los 3D). Las celdas que empiezan con `=` se guardan como texto
   (protección contra inyección de fórmulas).

## 5 ter. Radar de apertura sintética (SAR)

```
NASA ASF DAAC ──(token Earthdata)──► scripts/build_sar.py ──► data/processed/sar_composite.nc · sar_events.json · sar_img/
      │                                (Sentinel-1 OCN)                      └──► backend/sar.py ──► /api/sar/grid · area · events
      └────(público, sin cuenta)────────────────────────────────────────────────► /api/sar/scenes · /api/sar/browse (proxy)
```

| Paso | Detalle |
|---|---|
| Acceso | `backend/asf.py`: búsqueda `api.daac.asf.alaska.edu` (jsonlite); descarga con `Authorization: Bearer <token>`, conservado solo en redirecciones a dominios NASA/ASF (`rebuild_auth`). Token desde `EARTHDATA_TOKEN` o `~/.earthdata_token`; nunca se imprime. |
| Muestreo | Por año 2017–2024: todas las escenas OCN que tocan el golfo, agrupadas por huella (órbita relativa + marco, ~128); 2 por huella repartidas en el año. Eventos desde 2017: hasta 12 escenas en los 45 días previos y 12 posteriores dentro del radio. |
| Lectura | NetCDF de `measurement/` dentro del .zip (en memoria, `scipy.io.netcdf_file`). Dos formatos: IPF 2.8x (2017–18, `owiLandFlag`, `owiNrcs` 2D) e IPF ≥ 2.9 (`owiMask`, `owiNrcsNeszCorr[...,VV]`). |
| Métricas (celdas ~1 km) | válida = máscara 0; *amortiguada* = apta (viento ECMWF 3–10 m/s, sin brillo, σ⁰ > 0) y σ⁰_VV/σ⁰_CMOD < 0,5; *brillante* = owiPBright > 0; viento = owiWindSpeed. |
| Agregación | Suma por celda de 0,1° y año: viento medio, % amortiguada (sobre aptas), % brillante (sobre válidas); celdas con ≥ 20 observaciones y dentro de `GULF_POLYGON`. |
| Eventos | Por escena dentro del radio: viento medio y p95, % amortiguada, % brillante; medias antes/después. Imagen: viento del radar (0–35 m/s, paleta turbo) de la escena posterior con más viento (huracanes) o más amortiguación. |
| En vivo | `/api/sar/scenes`: hasta 12 escenas por misión (Sentinel-1 GRD, ALOS PALSAR L1.5, UAVSAR, NISAR) en 1–3 meses; caché 7 días. `/api/sar/browse`: solo `https://` de `datapool.asf.alaska.edu` y `cumulus.asf.earthdatacloud.nasa.gov`, máx. 12 MB, redimensiona y opcionalmente vuelve transparente el negro. |

Limitaciones: muestra (no todas las escenas); la amortiguación tiene falsos positivos (algas, lluvia, calma); las
imágenes sobre el mapa se colocan en el rectángulo de la huella (posición aproximada).

### Detector de manchas con NISAR (`scripts/build_slicks.py`)

| Paso | Detalle |
|---|---|
| Productos | NISAR L2 GCOV provisionales (`NISAR_L2_PR_GCOV_*`), búsqueda mes a mes desde 2025-07 sobre el golfo; se conservan los que tienen ≥ 25 % de mar (muestreo 25×25 de la huella con ETOPO1); hasta 3 por huella (órbita + marco) repartidos en el tiempo, máx. 70. |
| Lectura parcial | `backend/asf.py: ArchivoRemoto` (objeto de archivo sobre HTTP Range, bloques de 4 MB) + `h5py`: se leen solo `frequencyB/{HHHH\|VVVV, HVHV\|VHVH, mask, x/yCoordinates, projection}` (80 m, fragmentos gzip de 512²) → ~30 MB de ~6 GB. |
| Geometría | UTM WGS84 (EPSG 326xx) ↔ lat/lon con las fórmulas de Snyder (USGS PP 1395), vectorizadas; verificado ida y vuelta. |
| Mar | válido (σ⁰ > −35 dB y no relleno), a > 2 km del borde de la franja, profundidad ≥ 10 m, dentro del golfo y a > 2 km de tierra brillante (media 9×9 > −12 dB). |
| Detección | multilook 2×2 (160 m); fondo = convolución normalizada 41×41 (6,5 km) sobre mar; DR = 10·log10(fondo/σ⁰); DR suavizado 3×3 ≥ 2 dB; cierre morfológico; componentes ≥ 1 km²; se descartan rectángulos casi llenos y sin moteado (huecos de procesado). |
| Atributos | área, largo y ancho (ejes de la covarianza de los píxeles × 4), DR co-polar y cruzado, eco de fondo (dB), centroide. |
| Confianza | calma (fondo < −24 dB) · alta (DR ≥ 3,5 dB, ≥ 2 km², ≥ 4:1, ≤ 3 km de ancho) · media; escena con > 1,5 % del mar amortiguado → `variable_weather` y sin altas. |
| Salida | `slicks.json` (escenas, huella WKT, enlaces Vertex, zonas) y `slicks/<escena>.png` (eco en grises con contraste propio + zonas en rojo/naranja/azul, en lat/lon a 0,003°). API: `/api/sar/slicks`, `/api/sar/slicks/<escena>.png`. |

## 5 bis. Cuaderno de Jupyter

```
backend/notebook.py ──► scripts/build_jupyterlite.py ──► notebooks/*.ipynb          (Jupyter local, kernel python3)
   (celdas ES/EN)                                   └──► jupyterlite/ → /jupyter     (navegador, kernel Pyodide)
        └──────────► GET /api/notebook?bbox=…&month=… ──► js/notebook.js guarda el cuaderno del área en JupyterLite
```

- **Una sola definición** (`CELDAS` en `backend/notebook.py`): textos en español e inglés y código común; la celda de
  parámetros (etiqueta `parameters`, compatible con papermill) se genera con `repr()` a partir de valores validados
  (`seleccion_a_texto`, `limpiar_titulo`, `validar_base`), nunca concatenando texto del usuario como código.
- **Acceso a datos** (`conectar(API)`): `ClienteHTTP` (urllib en Jupyter; `XMLHttpRequest` síncrono en Pyodide, permitido
  porque el kernel corre en un Web Worker) o `ClienteLocal` (importa `backend/` y llama a `OceanService` sin servidor).
  Ambos exponen `get(ruta, **params)` y `get_bytes(ruta)` con las rutas de la API, así que los resultados coinciden.
- **Secciones**: resumen · series con eventos · tablas anual/mismo mes con dirección · anomalías + media móvil · ciclo
  estacional · dispersión y correlación con desfase TSM→clorofila (0–6 meses) · clases de profundidad · OBIS · impacto
  de eventos (3 meses antes/después) · mapas del golfo del mes · tendencia por celda (regresión de medias anuales, prueba t)
  · Hovmöller (anomalía media por latitud) · área vs. golfo (diferencia y z del mes) · exportación CSV/Excel.
- **Cálculos propios del cuaderno** (sobre la malla `.npz`, mismas definiciones de la sección 3): normal por celda y mes,
  anomalías, pendiente por celda `b = Σ(t−t̄)(y−ȳ)/Σ(t−t̄)²` con `p` de la t de Student (n−2 g.l.; ≥ 8 años), media del
  golfo ponderada por cos(latitud), `z = (dif_mes − media(dif)) / σ(dif)`.
- **En la interfaz** (`js/notebook.js`): el panel carga `jupyter/notebooks/index.html?path=…` en un iframe del mismo
  origen; para un área pide `/api/notebook?target=lite`, espera a `window.jupyterapp` (opción `exposeAppInBrowser`) y
  guarda el cuaderno con `serviceManager.contents.save` (almacenamiento del navegador). «⤓ .ipynb» pide `target=local`.
- **Compilación** (`scripts/build_jupyterlite.py`): compila en una carpeta temporal y copia a `jupyterlite/` (OneDrive
  bloquea borrar la carpeta); si `sqlite3` no está disponible (Control de aplicaciones de Windows) usa la caché JSON de
  doit; añade las extensiones de `share/jupyter/labextensions` visibles (incluido el kernel Pyodide).

## 6. Interfaz

| Elemento | Archivo | Notas |
|---|---|---|
| Malla de la variable | `app.js: gridToImage` | Canvas reproyectado fila a fila a Web Mercator (las filas de latitud regular no coinciden con las teselas). Escala fija o ajustada al mes (percentiles 2–98). |
| Ventana del área | `panels.js` | Vidrio al 20 %, movible por su barra (pointer events, limitada al mapa y por encima de la línea de tiempo), minimizable, botón Excel. |
| Detalle | `panels.js` + `figures.js` | Pestañas tabla / serie / 3D, filtro de años, Excel. |
| Filtros de eventos | `app.js: eventMatches` | Texto (ES+EN, sin acentos), tipo, categoría, años, solo activos; se aplican a lista, mapa y línea de tiempo. |
| Búsqueda global | `search.js` | Coordenadas (`28.7, -88.4` o `28.7N 88.4W`), eventos y lugares; flechas + Enter. |
| Idiomas | `i18n.js` | `data-i18n`, `data-i18n-title`, `data-i18n-placeholder`; textos de datos con `{es, en}`. |

## 7. Cómo extender

- **Nueva variable mensual** (p. ej. salinidad SMAP): añadir la fuente en `FUENTES` de `build_dataset.py`, la variable en
  `config.VARIABLES`, su cálculo en `service.grid`, y textos `var_*`, `desc_*`, `dyk_*` en `i18n.js`.
- **Nuevos eventos**: editar `data/events.json` (`id`, `type` natural/human, `category`, `start`, `end`, `lat`, `lon`,
  `radius_km`, `approx`, `name{es,en}`, `description{es,en}`, `source{name,url}`). Solo se muestran los que empiezan
  dentro del periodo con datos.
- **Otra base de datos**: `GOLFO_DATA_BACKEND=sql` + `DATABASE_URL`; o una clase nueva que herede de `DataRepository`.
- **Datos directos de NASA Earthdata**: sustituir `anio_variable` en `build_dataset.py` por una lectura con `earthaccess`
  de `MODISA_L3m_CHL` (`*.L3m.MO.CHL.chlor_a.4km*`) y `MODIS_AQUA_L3_SST_THERMAL_MONTHLY_4KM_DAYTIME_V2019.0`.

## 8. Pruebas

`python tests/test_api.py` (o `pytest`): metadatos y mallas, resumen de área (bbox y polígono), series y tablas, 3D,
eventos (incluido que no haya eventos anteriores a 2003), exportación a Excel (hojas, gráfico nativo, imagen, nombre
de archivo, sin fórmulas), cuaderno de Jupyter (malla `.npz`, parámetros como literales seguros, URL maliciosa
rechazada, nombre `.ipynb`) y errores 400/404/422. Para el cuaderno completo:
`jupyter nbconvert --to notebook --execute notebooks/Golfo_Mexico_MIA_es.ipynb --output-dir /tmp`. Con `GOLFO_DATA_BACKEND=sql` las mismas pruebas validan la base SQL.
