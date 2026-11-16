# Gulf of Mexico · EIA Observatory

**English** · [Español](README.es.md) · **Live demo:** https://golfo-mexico-mia.onrender.com/?lang=en ·
NASA Space Apps Challenge 2026: *Dancing with the SARs*

> **AI usage:** Generative AI (Claude Code) was used as a tool to generate code and link resources.

A bilingual (English / Spanish) web application to explore the Gulf of Mexico in support of an Environmental Impact
Assessment (EIA): **depth, sea surface temperature, chlorophyll (phytoplankton), marine life and natural and human
events** (hurricanes, oil spills, red tides, hypoxia, marine heatwaves…) from 2003 to 2024, plus **synthetic aperture
radar (SAR)** from Sentinel-1 and an **oil-slick detector with NISAR L-band radar** (2025–2026). All data are real.

*Free hosting: the first load may take ~1 minute while the server wakes up.*

## What it does
- **Interactive map** with sea surface temperature, its anomaly and year-over-year change, chlorophyll-a and its
  anomaly, bathymetry, and three SAR layers (2017–2024): *damped surface* (possible oil slicks or films), *bright
  targets* (ships and platforms) and *radar-measured wind*. Overlays: events, protected areas, OBIS biodiversity,
  NASA GIBS daily imagery, monthly SAR scenes (Sentinel-1, ALOS PALSAR, UAVSAR, NISAR) and the NISAR slick detector.
- **Select a 1° cell or draw an area** → floating window with temperature, chlorophyll, depth, marine life, radar,
  2003–2024 trend and related events. Each feature opens **up/down tables**, **time series** and **3D charts** that
  follow the **timeline** (▶ to animate).
- **Event analysis**: anomalies 3 months before vs. after each event, plus SAR before/after (wind, damped surface,
  bright targets) and the radar wind field (e.g. hurricanes). *Coincidence does not imply causation.*
- **🛢 Slick detector (NISAR L-band)**: radar does not measure water density; it measures the echo of short surface
  waves. Oil and other films are more viscous than water and change surface tension, damping those waves, so the
  echo drops and the area looks dark. Damping ratio DR = σ⁰(surroundings)/σ⁰(area) ≥ 2 dB, ≥ 1 km², sea > 2 km from
  land; confidence *high* (elongated, narrow, DR ≥ 3.5 dB), *medium* or *calm sea (inconclusive)*. 70 NISAR scenes,
  13 high-confidence areas, several over known natural seeps in the Campeche Knolls (near the *Chapopote* asphalt volcano).
- **Search and filters**, **Excel export** of every table and chart, and a **Jupyter notebook** that runs in the
  browser (JupyterLite) or locally, with the same data and calculations as the map.

## Data sources (all open)
| Variable | Source | Access |
|---|---|---|
| Sea surface temperature (monthly) | NASA JPL MUR SST v4.1 | NOAA CoastWatch ERDDAP `jplMURSST41mday` |
| Chlorophyll-a (monthly) | NASA MODIS-Aqua L3 R2022 | NOAA CoastWatch ERDDAP `erdMH1chlamday_R2022SQ` |
| Bathymetry | NOAA ETOPO1 | NOAA CoastWatch ERDDAP `etopo180` |
| Biodiversity | OBIS (Ocean Biodiversity Information System) | API v3 (live, cached) |
| Daily imagery | NASA GIBS | WMTS |
| SAR radar | Sentinel-1 OCN/GRD (ESA), ALOS PALSAR (JAXA), UAVSAR and NISAR (NASA / NASA-ISRO) | NASA ASF DAAC |
| Events | NOAA NHC, NOAA OR&R, USACE, FWC, NPS, NOAA Coral Reef Watch, Pemex | `data/events.json` (curated, approximate locations) |

## Run locally
```bash
pip install -r requirements.txt
uvicorn backend.main:app --port 8000      # http://localhost:8000  ·  API docs: /docs
```
Processed data are included in `data/processed`. To rebuild them: `scripts/build_dataset.py` (ERDDAP/OBIS),
`scripts/build_sar.py` and `scripts/build_slicks.py` (need a NASA Earthdata token in `~/.earthdata_token`; never
committed), `scripts/build_jupyterlite.py` (in-browser Jupyter). Deployment: `render.yaml` (Render Blueprint).

## Structure
```
backend/   FastAPI API · analysis (service.py) · SAR (sar.py, asf.py) · Excel export · Jupyter notebook generator
frontend/  index.html · css · js (map, panels, figures, SAR, notebook, search, i18n)
data/      events, places and processed data (NetCDF, JSON, PNG)
scripts/   data pipelines (ERDDAP, OBIS, Sentinel-1, NISAR, JupyterLite)
notebooks/ Jupyter notebooks (ES/EN) · jupyterlite/ in-browser Jupyter · tests/ API tests · docs/ technical docs (ES)
```
Technical documentation (formulas, API, methods): [docs/DOCUMENTACION.md](docs/DOCUMENTACION.md) (Spanish).

## Limitations
- Monthly 0.25° (~25 km) ocean data: no daily or fine coastal processes. Satellite chlorophyll can be overestimated in
  turbid river waters. OBIS records reflect sampling effort, not abundance.
- SAR layers use a sample (~1,080 Sentinel-1 scenes); damped surfaces have look-alikes (calm, rain, biogenic films).
  NISAR products are provisional. The slick detector is an **alert and exploration tool**; confirmation requires
  other sources (NOAA OR&R, optical imagery).

## AI usage
Generative AI (Claude Code) was used as a tool to generate code and link resources. The idea, the approach to the
challenge, the event research and the data selection are the team's own. All data are real measurements from the
cited sources; no data or image in the application was generated by AI.

## Credits and references
- **NASA:** JPL MUR SST v4.1 (PO.DAAC); MODIS-Aqua L3 chlorophyll-a R2022 (OBPG); GIBS/EOSDIS; NISAR L2 GCOV
  (provisional data, NASA-ISRO); UAVSAR (JPL); ASF DAAC (SAR archive).
- **Space Agency Partners:** *Contains modified Copernicus Sentinel data 2017–2024, processed by ESA* (Sentinel-1 OCN
  and GRD, via NASA ASF) · ALOS PALSAR © JAXA/METI (via NASA ASF) · NISAR, joint NASA-ISRO mission.
- **Other sources:** NOAA ETOPO1 and NOAA CoastWatch ERDDAP; OBIS – Ocean Biodiversity Information System
  (UNESCO-IOC), www.obis.org; events: NOAA NHC, NOAA OR&R, NOAA Coral Reef Watch, USACE, FWC, NPS, Pemex; maps
  © OpenStreetMap contributors and OpenTopoMap (CC-BY-SA).
- **Open-source software:** Python, FastAPI, Uvicorn, NumPy, SciPy, pandas, xarray, h5py, h5netcdf, SQLAlchemy,
  requests, openpyxl, Pillow, matplotlib, Jupyter/JupyterLite, Pyodide, Leaflet, Leaflet.draw, Plotly.js.
- Colour palettes inspired by cmocean and ColorBrewer.

## License
Code released under the MIT License (see [LICENSE](LICENSE)). Data keep the licenses and credits of their sources.
