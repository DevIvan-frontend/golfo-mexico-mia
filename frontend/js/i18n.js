/**
 * @module i18n
 * Textos de la interfaz en español e inglés y formateadores dependientes del idioma (fechas, números, áreas).
 * - En el HTML: `data-i18n="clave"` (texto), `data-i18n-title` (tooltip) y `data-i18n-placeholder`.
 * - En JS: `t("clave", {n: 3})` para textos de la interfaz y `tx({es, en})` para textos bilingües de los datos.
 * Para añadir un idioma, copia un bloque de DICT y tradúcelo; el selector usa la clave de dos letras.
 */
export const DICT = {
  es: {
    title: "Golfo de México · Observatorio MIA",
    subtitle: "Profundidad, temperatura, clorofila, vida marina y eventos · 2003–2024",
    help: "Guía",
    tab_layers: "Capas", tab_events: "Eventos", tab_guide: "Guía",
    variable: "Variable del mapa",
    var_sst: "Temperatura superficial", var_sst_anom: "Anomalía de temperatura", var_sst_change: "Cambio de temperatura vs. año anterior",
    var_chl: "Clorofila-a (fitoplancton)", var_chl_anom: "Anomalía de clorofila", var_depth: "Profundidad (batimetría)",
    desc_sst: "Media mensual NASA JPL MUR.", desc_sst_anom: "Diferencia con el promedio 2003–2024 de ese mes.",
    desc_sst_change: "Diferencia con el mismo mes del año anterior.", desc_chl: "Media mensual NASA MODIS-Aqua.",
    desc_chl_anom: "% sobre o bajo lo normal de ese mes.", desc_depth: "NOAA ETOPO1 (no cambia con el tiempo).",
    overlays: "Capas superpuestas",
    ov_events: "Eventos naturales y humanos", ov_places: "Áreas protegidas y referencias", ov_obis: "Registros de biodiversidad (OBIS, por año)",
    ov_outline: "Límite del golfo", ov_gibs_true: "Imagen satelital del día (NASA GIBS)", ov_gibs_sst: "TSM diaria MUR (NASA GIBS)", ov_gibs_chl: "Clorofila diaria MODIS (NASA GIBS)",
    basemap: "Mapa base", base_bluemarble: "NASA Blue Marble + batimetría", base_osm: "OpenStreetMap", base_topo: "OpenTopoMap",
    opacity: "Opacidad de la variable",
    autoscale: "Escala de color ajustada al mes",
    autoscale_hint: "Desactivada, la escala es fija y los colores se pueden comparar entre meses (ideal para la animación).",
    selection: "Selección", sel_cell: "Celda 1°", sel_rect: "Rectángulo", sel_poly: "Polígono",
    sel_hint: "Haz clic en el mar para analizar una celda de 1°×1°, o dibuja un rectángulo o polígono.",
    legend_dyk: "¿Sabías que…?",
    dyk_sst: "Los huracanes se intensifican sobre aguas de más de ~26 °C; por eso la TSM ayuda a entender su fuerza.",
    dyk_sst_anom: "Una anomalía positiva persistente puede indicar una ola de calor marina, que provoca blanqueamiento de corales.",
    dyk_sst_change: "Comparar con el mismo mes del año anterior elimina el ciclo estacional y resalta cambios bruscos.",
    dyk_chl: "La clorofila indica fitoplancton: la base de la red alimentaria marina. Valores muy altos cerca de ríos pueden señalar exceso de nutrientes.",
    dyk_chl_anom: "Tras grandes crecidas del Mississippi suele aumentar la clorofila y, después, la hipoxia (zona muerta).",
    dyk_depth: "La plataforma continental (< 200 m) concentra la pesca y las plataformas petroleras; el centro del golfo supera los 3 000 m.",
    readout_hint: "Pasa el cursor sobre el mar",
    loading: "Cargando…", no_data: "Sin datos", land: "Tierra / fuera del golfo",
    cell_title: "Celda de 1°", area_title: "Área seleccionada", polygon: "polígono", rectangle: "rectángulo",
    ocean_area: "Área oceánica", cells: "celdas de 0,25°", close: "Cerrar",
    depth: "Profundidad", sst: "Temperatura superficial", chl: "Clorofila-a", fauna: "Vida marina (OBIS)",
    events_rel: "Eventos en esta zona", trend: "Tendencia 2003–2024",
    vs_clim: "vs. normal", vs_prev: "vs. año anterior", per_decade: "por década",
    significant: "significativa", not_significant: "no significativa",
    mean: "media", min: "mín.", max: "máx.", shelf: "plataforma (<200 m)",
    records: "registros", species: "especies", redlist: "en Lista Roja UICN",
    click_detail: "Haz clic en una característica para ver su tabla de cambios y el gráfico 3D.",
    open3d: "Ver en 3D", compare_props: "Comparar propiedades",
    up: "Sube", down: "Baja", flat: "Estable", nd: "Sin dato",
    tab_table: "Tabla de cambios", tab_chart: "Serie temporal", tab_3d: "Gráfico 3D",
    year: "Año", month_col: "Mes", value: "Valor", change: "Cambio", anomaly: "Anomalía", direction: "Tendencia",
    annual_title: "Promedio anual y cambio frente al año anterior", same_month_title: "Mismo mes en cada año",
    trend_text: "Tendencia lineal", coverage: "cobertura",
    mode_relief: "Relieve coloreado", mode_props: "Espacio de propiedades",
    exaggeration: "Exageración vertical", lon: "Longitud", lat: "Latitud", elevation: "Elevación (m)",
    depth_m: "Profundidad (m)", color_by: "Color", relief_only: "Solo relieve",
    depth_classes: "Distribución de profundidades", range_m: "Rango (m)", pct_area: "% del área",
    fauna_title: "Biodiversidad registrada en OBIS", top_species: "Especies con más registros", redlist_title: "Especies en la Lista Roja de la UICN",
    by_year_title: "Registros por año y cambio", scientific_name: "Nombre científico", class: "Clase", category: "Categoría",
    sampling_caveat: "Los registros reflejan el esfuerzo de muestreo (campañas, museos), no la abundancia real.",
    fauna_unavailable: "OBIS no respondió. Inténtalo más tarde.",
    iucn_CR: "En peligro crítico", iucn_EN: "En peligro", iucn_VU: "Vulnerable", iucn_NT: "Casi amenazada", iucn_LC: "Preocupación menor", iucn_DD: "Datos insuficientes",
    filter_all: "Todos", filter_natural: "Naturales", filter_human: "Humanos",
    natural: "Natural", human: "Humano",
    cat_hurricane: "Huracán", cat_oil_spill: "Derrame de petróleo", cat_industrial: "Accidente industrial", cat_hypoxia: "Hipoxia (zona muerta)",
    cat_algal_bloom: "Floración algal nociva", cat_flood: "Crecida de río", cat_freshwater_diversion: "Desvío de agua dulce",
    cat_marine_heatwave: "Ola de calor marina", cat_cold_event: "Evento de frío extremo",
    analyze: "Analizar impacto", go_date: "Ir a la fecha", source: "Fuente", approx: "ubicación aproximada",
    active_now: "Activo en la fecha", months_ago: "hace {n} meses", months_ahead: "en {n} meses", same_month: "este mes",
    impact_title: "Análisis antes / después", before: "3 meses antes", after: "3 meses después",
    impact_area: "Zona analizada: radio de {r} km ({c} celdas oceánicas)",
    impact_out: "Este evento ocurrió fuera del periodo con datos satelitales (2003–2024).",
    impact_nocells: "El área del evento no contiene celdas oceánicas del golfo.",
    disclaimer: "Coincidencia en el tiempo no implica causalidad: compara con otros años y con la variabilidad estacional antes de concluir.",
    event_line: "Evento", current_month: "Mes seleccionado",
    play: "Reproducir", pause: "Pausa", speed: "Velocidad", step_back: "Mes anterior", step_fwd: "Mes siguiente",
    events_in_window: "Eventos activos (±6 meses)", none: "Ninguno",
    guide_title: "Cómo usar el observatorio",
    guide_1: "Elige una variable en Capas y mueve la línea de tiempo (abajo) o pulsa ▶ para animar 2003–2024.",
    guide_2: "Haz clic en el mar para abrir la ventana de una celda de 1°; o dibuja un rectángulo o polígono con la barra del mapa.",
    guide_3: "En la ventana, haz clic en una característica (temperatura, clorofila, profundidad, vida marina) para ver si sube o baja año con año y su gráfico 3D.",
    guide_4: "En Eventos, elige un huracán, derrame u otro suceso: el mapa salta a esa fecha y lugar y compara los datos antes y después.",
    guide_5: "Las marcas sobre la línea de tiempo señalan eventos: úsalas para buscar relaciones entre los cambios del mapa y los desastres.",
    sources_title: "Fuentes de datos",
    src_sst: "Temperatura: NASA JPL MUR SST v4.1 (mensual), vía NOAA CoastWatch ERDDAP.",
    src_chl: "Clorofila: NASA MODIS-Aqua L3 R2022 (mensual), vía NOAA CoastWatch ERDDAP.",
    src_depth: "Profundidad: NOAA ETOPO1.", src_obis: "Vida marina: OBIS (Ocean Biodiversity Information System).",
    src_events: "Eventos: NOAA NHC, NOAA OR&R, USACE, FWC, NPS, NOAA Coral Reef Watch, Pemex (ubicaciones aproximadas).",
    src_gibs: "Imágenes diarias: NASA GIBS.",
    data_res: "Malla de análisis: 0,25° (~25 km). Batimetría: 1/12° (~9 km).",
    api_error: "No se pudo contactar con la API", backend_hint: "Arranca el servidor: uvicorn backend.main:app",
    // búsqueda y filtros
    search_placeholder: "Buscar evento, lugar o coordenadas (28.7, -88.4)…", search_coords: "Ir a {lat}, {lon} y analizar la celda",
    search_none: "Sin resultados", ev_search_placeholder: "Buscar en eventos…", ev_category_all: "Todas las categorías",
    ev_from: "Desde", ev_to: "Hasta", ev_only_active: "Solo activos en la fecha del mapa", ev_count: "{n} eventos",
    filter_years: "Años", place: "Lugar", event: "Evento",
    // ventana
    minimize: "Minimizar", restore: "Restaurar", drag_hint: "Arrastra la barra superior para mover la ventana",
    // cuaderno de Jupyter
    notebook: "Cuaderno", nb_title: "Cuaderno de Jupyter", nb_general: "Cuaderno general",
    nb_open_area: "Analizar esta área en un cuaderno de Jupyter",
    nb_hint: "Python se ejecuta en tu navegador (JupyterLite). La primera vez tarda ~1 min en cargar; tus cambios se guardan solo en este navegador. Ejecuta todo con Run ▸ Run All Cells.",
    nb_download_hint: "Descargar el cuaderno para Jupyter en tu computadora", nb_newtab: "Abrir en una pestaña nueva",
    nb_loading: "Preparando el cuaderno del área…", nb_area_ready: "Cuaderno del área listo: ejecuta Run ▸ Run All Cells",
    nb_area_error: "No se pudo abrir el cuaderno del área; usa ⤓ .ipynb para descargarlo", nb_downloaded: "Cuaderno .ipynb descargado",
    // radar SAR
    sar_title: "Radar SAR", sar_group: "Radar SAR · Sentinel-1 (2017–2024)", ov_sar: "Escenas de radar SAR del mes (NASA ASF)",
    var_sar_damped: "Superficie amortiguada (posibles manchas)", var_sar_bright: "Objetos brillantes (barcos y plataformas)",
    var_sar_wind: "Viento medido por el radar",
    desc_sar_damped: "% de veces que el mar se ve «liso» en el radar con viento suficiente.",
    desc_sar_bright: "% de observaciones con ecos muy fuertes: barcos y plataformas.",
    desc_sar_wind: "Velocidad media del viento sobre el mar estimada con el radar.",
    dyk_sar_damped: "El petróleo y otras películas alisan el oleaje: el radar recibe menos eco y la mancha se ve oscura. Algas, lluvia o calma local producen el mismo efecto, por eso son «posibles» manchas.",
    dyk_sar_bright: "El metal de barcos y plataformas refleja el radar como un espejo: las zonas petroleras del norte del golfo y la Sonda de Campeche brillan.",
    dyk_sar_wind: "El radar mide el viento por la rugosidad del mar, de día y de noche y a través de las nubes, incluso dentro de un huracán.",
    sar_no_year: "Sin datos de radar procesados para {y} (2017–2024)", sar_n_scenes: "{n} escenas",
    sar_images_only: "Imágenes de radar del mes", sar_sub: "Sentinel-1 · ALOS · UAVSAR · NISAR",
    sar_damped_short: "Amortiguada", sar_bright_short: "Brillantes", sar_wind_short: "Viento", sar_obs: "Observaciones (~1 km)",
    tab_images: "Imágenes",
    sar_explain: "El radar de apertura sintética (SAR) emite microondas y mide el eco del mar: ve de día y de noche y a través de las nubes. Un mar «liso» (eco débil) puede indicar petróleo o películas; los ecos muy fuertes son barcos y plataformas.",
    sar_method: "Sentinel-1 Level-2 OCN (ESA/Copernicus) vía NASA ASF DAAC. Amortiguada: σ⁰ observada < 50 % de la esperada por el modelo CMOD con viento ECMWF de 3–10 m/s. Brillantes: owiPBright > 0. Muestra de 2 escenas por huella y año.",
    sar_no_preview: "Sin vista previa", sar_on_map: "Ver sobre el mapa", sar_overlay_hint: "posición aproximada; 📡✕ la quita",
    sar_searching: "Buscando escenas de radar en NASA ASF…", sar_search_error: "búsqueda no disponible",
    sar_none: "No hay escenas de radar de esta zona entre {a} y {b}.", sar_none_month: "No hay escenas de radar este mes",
    sar_gallery_note: "Vistas previas públicas de NASA ASF. Los datos completos se descargan en ASF Vertex con una cuenta gratuita de NASA Earthdata.",
    sar_wind_mean: "Viento medio (radar)", sar_wind_p95: "Viento fuerte (percentil 95)", sar_wind_map: "Viento del radar en el mapa",
    sar_event_intro: "Sentinel-1 dentro de {r} km: {a} escenas en los 45 días previos y {b} en los 45 posteriores.",
    sar_event_live: "Escenas de radar de la zona en las semanas del evento (búsqueda en vivo en NASA ASF).",
    sar_clear: "Quitar la imagen de radar", sar_before: "45 días antes", sar_after: "45 días después",
    // detector de manchas NISAR
    ov_slicks: "🛢 Detector de manchas · NISAR banda L (2025–2026)",
    slk_ov_hint: "Zonas donde una película más viscosa que el agua (petróleo, emulsión o película biológica) alisa el mar y el eco del radar cae. {s} escenas · {n} zonas.",
    slk_conf_high: "Posible mancha (alta)", slk_conf_medium: "Superficie amortiguada (media)", slk_conf_calm: "Mar en calma (no concluyente)",
    slk_hint_high: "Contraste fuerte y forma alargada, típica de una mancha a la deriva. Confirmar con otras fuentes (NOAA OR&R, imágenes ópticas).",
    slk_hint_medium: "El mar está más liso que su entorno: puede ser petróleo, película biológica, lluvia o una zona de calma local.",
    slk_hint_calm: "El viento era muy débil: sin oleaje todo el mar se ve oscuro y no se puede distinguir una mancha.",
    slk_area: "Área", slk_size: "Largo × ancho", slk_dr: "Amortiguamiento HH/VV", slk_dr_hv: "Amortiguamiento HV/VH",
    slk_bg: "Eco del mar alrededor", slk_view_scene: "Ver escena NISAR", slk_scene: "Escena procesada", slk_sea: "Mar analizado",
    slk_zones: "zonas", slk_none_scene: "Sin zonas amortiguadas en esta escena.",
    slk_variable: "Escena con tiempo variable (celdas de lluvia, ráfagas o calmas): muchas zonas oscuras a la vez suelen ser atmosféricas, por eso ninguna se marca como alta.",
    slk_loaded: "Detector NISAR: {s} escenas y {n} zonas. Clic en un punto para ver los detalles y la escena.",
    guide_slicks: "🛢 Detector de manchas (NISAR): activa la capa en Capas. Cada punto es una zona donde el radar de banda L ve el mar alisado por una película viscosa (posible petróleo); el color indica la confianza. «Ver escena NISAR» superpone la imagen de radar con las zonas marcadas.",
    guide_sar: "📡 Radar SAR: elige «Superficie amortiguada», «Objetos brillantes» o «Viento medido por el radar» en Capas (mapas anuales 2017–2024), activa «Escenas de radar SAR del mes» para ver las imágenes de cada mes, o abre la fila «Radar SAR» de un área o la ventana de un evento.",
    src_sar: "Radar SAR: Sentinel-1 (ESA/Copernicus), ALOS PALSAR (JAXA), UAVSAR y NISAR (NASA) vía NASA ASF DAAC.",
    // exportación
    export_excel: "Descargar Excel", exporting: "Generando Excel…", export_done: "Excel descargado", export_error: "No se pudo generar el Excel",
    report_area: "Informe del área", description: "Descripción",
    col_feature: "Característica", col_unit: "Unidad", col_clim: "Normal 2003–2024", col_prev: "Mismo mes del año anterior",
    col_delta_prev: "Cambio vs. año anterior", col_trend: "Tendencia por década", col_p: "Valor p",
    col_anom_note: "Anomalía de TSM en °C y de clorofila en %, respecto al promedio 2003–2024 del mismo mes.",
    col_event: "Evento", col_type: "Tipo", col_start: "Inicio", col_end: "Fin", col_distance: "Distancia al centro (km)",
    sh_summary: "Resumen", sh_sst_annual: "TSM anual", sh_sst_same: "TSM mismo mes", sh_chl_annual: "Clorofila anual",
    sh_chl_same: "Clorofila mismo mes", sh_monthly: "Serie mensual", sh_depth: "Profundidad", sh_fauna_year: "Vida marina por año",
    sh_redlist: "Lista Roja UICN", sh_species: "Especies del año", sh_events: "Eventos", sh_cells: "Celdas del mes",
    sh_charts: "Gráficos", sh_event_compare: "Antes-después", sh_event_series: "Serie del evento",
    info_area: "Área", info_month: "Mes del mapa", info_filter: "Filtro de años", info_generated: "Generado",
    info_sources: "Fuentes", info_note: "Nota",
  },
  en: {
    title: "Gulf of Mexico · EIA Observatory",
    subtitle: "Depth, temperature, chlorophyll, marine life and events · 2003–2024",
    help: "Guide",
    tab_layers: "Layers", tab_events: "Events", tab_guide: "Guide",
    variable: "Map variable",
    var_sst: "Sea surface temperature", var_sst_anom: "Temperature anomaly", var_sst_change: "Temperature change vs. previous year",
    var_chl: "Chlorophyll-a (phytoplankton)", var_chl_anom: "Chlorophyll anomaly", var_depth: "Depth (bathymetry)",
    desc_sst: "NASA JPL MUR monthly mean.", desc_sst_anom: "Difference from that month's 2003–2024 average.",
    desc_sst_change: "Difference from the same month of the previous year.", desc_chl: "NASA MODIS-Aqua monthly mean.",
    desc_chl_anom: "% above or below normal for that month.", desc_depth: "NOAA ETOPO1 (does not change over time).",
    overlays: "Overlays",
    ov_events: "Natural and human events", ov_places: "Protected areas and landmarks", ov_obis: "Biodiversity records (OBIS, per year)",
    ov_outline: "Gulf boundary", ov_gibs_true: "Satellite image of the day (NASA GIBS)", ov_gibs_sst: "Daily MUR SST (NASA GIBS)", ov_gibs_chl: "Daily MODIS chlorophyll (NASA GIBS)",
    basemap: "Base map", base_bluemarble: "NASA Blue Marble + bathymetry", base_osm: "OpenStreetMap", base_topo: "OpenTopoMap",
    opacity: "Variable opacity",
    autoscale: "Color scale fitted to the month",
    autoscale_hint: "When off, the scale is fixed so colors can be compared across months (best for the animation).",
    selection: "Selection", sel_cell: "1° cell", sel_rect: "Rectangle", sel_poly: "Polygon",
    sel_hint: "Click on the sea to analyze a 1°×1° cell, or draw a rectangle or polygon.",
    legend_dyk: "Did you know…?",
    dyk_sst: "Hurricanes intensify over water warmer than ~26 °C, so SST helps explain their strength.",
    dyk_sst_anom: "A persistent positive anomaly can signal a marine heatwave, which causes coral bleaching.",
    dyk_sst_change: "Comparing with the same month of the previous year removes the seasonal cycle and highlights abrupt changes.",
    dyk_chl: "Chlorophyll indicates phytoplankton, the base of the marine food web. Very high values near rivers can signal excess nutrients.",
    dyk_chl_anom: "After large Mississippi floods chlorophyll often rises, followed by hypoxia (the dead zone).",
    dyk_depth: "The continental shelf (< 200 m) concentrates fishing and oil platforms; the center of the Gulf is deeper than 3,000 m.",
    readout_hint: "Hover over the sea",
    loading: "Loading…", no_data: "No data", land: "Land / outside the Gulf",
    cell_title: "1° cell", area_title: "Selected area", polygon: "polygon", rectangle: "rectangle",
    ocean_area: "Ocean area", cells: "0.25° cells", close: "Close",
    depth: "Depth", sst: "Sea surface temperature", chl: "Chlorophyll-a", fauna: "Marine life (OBIS)",
    events_rel: "Events in this area", trend: "2003–2024 trend",
    vs_clim: "vs. normal", vs_prev: "vs. previous year", per_decade: "per decade",
    significant: "significant", not_significant: "not significant",
    mean: "mean", min: "min", max: "max", shelf: "shelf (<200 m)",
    records: "records", species: "species", redlist: "on the IUCN Red List",
    click_detail: "Click a feature to see its change table and 3D chart.",
    open3d: "View in 3D", compare_props: "Compare properties",
    up: "Rising", down: "Falling", flat: "Stable", nd: "No data",
    tab_table: "Change table", tab_chart: "Time series", tab_3d: "3D chart",
    year: "Year", month_col: "Month", value: "Value", change: "Change", anomaly: "Anomaly", direction: "Trend",
    annual_title: "Annual mean and change from the previous year", same_month_title: "Same month in every year",
    trend_text: "Linear trend", coverage: "coverage",
    mode_relief: "Colored relief", mode_props: "Property space",
    exaggeration: "Vertical exaggeration", lon: "Longitude", lat: "Latitude", elevation: "Elevation (m)",
    depth_m: "Depth (m)", color_by: "Color", relief_only: "Relief only",
    depth_classes: "Depth distribution", range_m: "Range (m)", pct_area: "% of area",
    fauna_title: "Biodiversity recorded in OBIS", top_species: "Most recorded species", redlist_title: "Species on the IUCN Red List",
    by_year_title: "Records per year and change", scientific_name: "Scientific name", class: "Class", category: "Category",
    sampling_caveat: "Records reflect sampling effort (surveys, museums), not actual abundance.",
    fauna_unavailable: "OBIS did not respond. Try again later.",
    iucn_CR: "Critically endangered", iucn_EN: "Endangered", iucn_VU: "Vulnerable", iucn_NT: "Near threatened", iucn_LC: "Least concern", iucn_DD: "Data deficient",
    filter_all: "All", filter_natural: "Natural", filter_human: "Human",
    natural: "Natural", human: "Human",
    cat_hurricane: "Hurricane", cat_oil_spill: "Oil spill", cat_industrial: "Industrial accident", cat_hypoxia: "Hypoxia (dead zone)",
    cat_algal_bloom: "Harmful algal bloom", cat_flood: "River flood", cat_freshwater_diversion: "Freshwater diversion",
    cat_marine_heatwave: "Marine heatwave", cat_cold_event: "Extreme cold event",
    analyze: "Analyze impact", go_date: "Go to date", source: "Source", approx: "approximate location",
    active_now: "Active on this date", months_ago: "{n} months ago", months_ahead: "in {n} months", same_month: "this month",
    impact_title: "Before / after analysis", before: "3 months before", after: "3 months after",
    impact_area: "Analyzed zone: {r} km radius ({c} ocean cells)",
    impact_out: "This event happened outside the period with satellite data (2003–2024).",
    impact_nocells: "The event area contains no Gulf ocean cells.",
    disclaimer: "Coincidence in time does not imply causation: compare with other years and with seasonal variability before concluding.",
    event_line: "Event", current_month: "Selected month",
    play: "Play", pause: "Pause", speed: "Speed", step_back: "Previous month", step_fwd: "Next month",
    events_in_window: "Active events (±6 months)", none: "None",
    guide_title: "How to use the observatory",
    guide_1: "Pick a variable in Layers and move the timeline (bottom) or press ▶ to animate 2003–2024.",
    guide_2: "Click on the sea to open the window for a 1° cell, or draw a rectangle or polygon with the map toolbar.",
    guide_3: "In the window, click a feature (temperature, chlorophyll, depth, marine life) to see whether it rises or falls year by year and its 3D chart.",
    guide_4: "In Events, pick a hurricane, spill or other incident: the map jumps to that date and place and compares the data before and after.",
    guide_5: "The marks above the timeline show events: use them to look for links between map changes and disasters.",
    sources_title: "Data sources",
    src_sst: "Temperature: NASA JPL MUR SST v4.1 (monthly), via NOAA CoastWatch ERDDAP.",
    src_chl: "Chlorophyll: NASA MODIS-Aqua L3 R2022 (monthly), via NOAA CoastWatch ERDDAP.",
    src_depth: "Depth: NOAA ETOPO1.", src_obis: "Marine life: OBIS (Ocean Biodiversity Information System).",
    src_events: "Events: NOAA NHC, NOAA OR&R, USACE, FWC, NPS, NOAA Coral Reef Watch, Pemex (approximate locations).",
    src_gibs: "Daily imagery: NASA GIBS.",
    data_res: "Analysis grid: 0.25° (~25 km). Bathymetry: 1/12° (~9 km).",
    api_error: "Could not reach the API", backend_hint: "Start the server: uvicorn backend.main:app",
    search_placeholder: "Search event, place or coordinates (28.7, -88.4)…", search_coords: "Go to {lat}, {lon} and analyze the cell",
    search_none: "No results", ev_search_placeholder: "Search events…", ev_category_all: "All categories",
    ev_from: "From", ev_to: "To", ev_only_active: "Only active on the map date", ev_count: "{n} events",
    filter_years: "Years", place: "Place", event: "Event",
    minimize: "Minimize", restore: "Restore", drag_hint: "Drag the top bar to move the window",
    notebook: "Notebook", nb_title: "Jupyter notebook", nb_general: "General notebook",
    nb_open_area: "Analyse this area in a Jupyter notebook",
    nb_hint: "Python runs in your browser (JupyterLite). The first load takes ~1 min; your changes are saved only in this browser. Run everything with Run ▸ Run All Cells.",
    nb_download_hint: "Download the notebook for Jupyter on your computer", nb_newtab: "Open in a new tab",
    nb_loading: "Preparing the area notebook…", nb_area_ready: "Area notebook ready: run Run ▸ Run All Cells",
    nb_area_error: "Could not open the area notebook; use ⤓ .ipynb to download it", nb_downloaded: "Notebook .ipynb downloaded",
    sar_title: "SAR radar", sar_group: "SAR radar · Sentinel-1 (2017–2024)", ov_sar: "SAR radar scenes of the month (NASA ASF)",
    var_sar_damped: "Damped surface (possible slicks)", var_sar_bright: "Bright targets (ships and platforms)",
    var_sar_wind: "Radar-measured wind",
    desc_sar_damped: "% of times the sea looks \"smooth\" to the radar with enough wind.",
    desc_sar_bright: "% of observations with very strong echoes: ships and platforms.",
    desc_sar_wind: "Mean wind speed over the sea estimated by the radar.",
    dyk_sar_damped: "Oil and other films smooth the waves: the radar gets a weaker echo and the slick looks dark. Algae, rain or local calm do the same, so these are \"possible\" slicks.",
    dyk_sar_bright: "The metal of ships and platforms reflects radar like a mirror: the oil fields of the northern gulf and the Bay of Campeche light up.",
    dyk_sar_wind: "Radar measures wind from sea roughness, day and night and through clouds, even inside a hurricane.",
    sar_no_year: "No processed radar data for {y} (2017–2024)", sar_n_scenes: "{n} scenes",
    sar_images_only: "Radar images of the month", sar_sub: "Sentinel-1 · ALOS · UAVSAR · NISAR",
    sar_damped_short: "Damped", sar_bright_short: "Bright", sar_wind_short: "Wind", sar_obs: "Observations (~1 km)",
    tab_images: "Images",
    sar_explain: "Synthetic aperture radar (SAR) sends microwaves and measures the sea's echo: it sees day and night and through clouds. A \"smooth\" sea (weak echo) may indicate oil or films; very strong echoes are ships and platforms.",
    sar_method: "Sentinel-1 Level-2 OCN (ESA/Copernicus) via NASA ASF DAAC. Damped: observed σ⁰ < 50 % of the CMOD-model σ⁰ with 3–10 m/s ECMWF wind. Bright: owiPBright > 0. Sample of 2 scenes per footprint and year.",
    sar_no_preview: "No preview", sar_on_map: "Show on map", sar_overlay_hint: "approximate position; 📡✕ removes it",
    sar_searching: "Searching radar scenes at NASA ASF…", sar_search_error: "search unavailable",
    sar_none: "No radar scenes of this area between {a} and {b}.", sar_none_month: "No radar scenes this month",
    sar_gallery_note: "Public previews from NASA ASF. Full data can be downloaded in ASF Vertex with a free NASA Earthdata account.",
    sar_wind_mean: "Mean wind (radar)", sar_wind_p95: "Strong wind (95th percentile)", sar_wind_map: "Radar wind on the map",
    sar_event_intro: "Sentinel-1 within {r} km: {a} scenes in the previous 45 days and {b} in the following 45.",
    sar_event_live: "Radar scenes of the area in the weeks of the event (live search at NASA ASF).",
    sar_clear: "Remove the radar image", sar_before: "45 days before", sar_after: "45 days after",
    ov_slicks: "🛢 Slick detector · NISAR L-band (2025–2026)",
    slk_ov_hint: "Areas where a film more viscous than water (oil, emulsion or biological film) smooths the sea and the radar echo drops. {s} scenes · {n} areas.",
    slk_conf_high: "Possible slick (high)", slk_conf_medium: "Damped surface (medium)", slk_conf_calm: "Calm sea (inconclusive)",
    slk_hint_high: "Strong contrast and elongated shape, typical of a drifting slick. Confirm with other sources (NOAA OR&R, optical imagery).",
    slk_hint_medium: "The sea is smoother than its surroundings: it may be oil, a biological film, rain or a local calm patch.",
    slk_hint_calm: "Wind was very weak: without waves the whole sea looks dark and a slick cannot be distinguished.",
    slk_area: "Area", slk_size: "Length × width", slk_dr: "Damping HH/VV", slk_dr_hv: "Damping HV/VH",
    slk_bg: "Surrounding sea echo", slk_view_scene: "Show NISAR scene", slk_scene: "Processed scene", slk_sea: "Sea analysed",
    slk_zones: "areas", slk_none_scene: "No damped areas in this scene.",
    slk_variable: "Scene with variable weather (rain cells, gusts or calms): many dark areas at once are usually atmospheric, so none is marked high.",
    slk_loaded: "NISAR detector: {s} scenes and {n} areas. Click a dot for details and the scene.",
    guide_slicks: "🛢 Slick detector (NISAR): turn on the layer in Layers. Each dot is an area where the L-band radar sees the sea smoothed by a viscous film (possible oil); colour shows confidence. \"Show NISAR scene\" overlays the radar image with the areas marked.",
    guide_sar: "📡 SAR radar: pick \"Damped surface\", \"Bright targets\" or \"Radar-measured wind\" in Layers (annual maps 2017–2024), turn on \"SAR radar scenes of the month\" to see each month's images, or open the \"SAR radar\" row of an area or an event window.",
    src_sar: "SAR radar: Sentinel-1 (ESA/Copernicus), ALOS PALSAR (JAXA), UAVSAR and NISAR (NASA) via NASA ASF DAAC.",
    export_excel: "Download Excel", exporting: "Building Excel…", export_done: "Excel downloaded", export_error: "Could not build the Excel file",
    report_area: "Area report", description: "Description",
    col_feature: "Feature", col_unit: "Unit", col_clim: "2003–2024 normal", col_prev: "Same month previous year",
    col_delta_prev: "Change vs. previous year", col_trend: "Trend per decade", col_p: "p-value",
    col_anom_note: "SST anomaly in °C and chlorophyll anomaly in %, relative to the 2003–2024 mean of the same month.",
    col_event: "Event", col_type: "Type", col_start: "Start", col_end: "End", col_distance: "Distance to center (km)",
    sh_summary: "Summary", sh_sst_annual: "SST annual", sh_sst_same: "SST same month", sh_chl_annual: "Chlorophyll annual",
    sh_chl_same: "Chlorophyll same month", sh_monthly: "Monthly series", sh_depth: "Depth", sh_fauna_year: "Marine life by year",
    sh_redlist: "IUCN Red List", sh_species: "Species of the year", sh_events: "Events", sh_cells: "Cells of the month",
    sh_charts: "Charts", sh_event_compare: "Before-after", sh_event_series: "Event series",
    info_area: "Area", info_month: "Map month", info_filter: "Year filter", info_generated: "Generated",
    info_sources: "Sources", info_note: "Note",
  },
};

let lang = "es";
try { lang = localStorage.getItem("golfo_lang") || (navigator.language || "es").slice(0, 2); } catch (_) { /* almacenamiento bloqueado */ }
if (!DICT[lang]) lang = "es";

export const getLang = () => lang;

export function t(key, vars = {}) {
  let s = (DICT[lang] && DICT[lang][key]) ?? DICT.es[key] ?? key;
  for (const [k, v] of Object.entries(vars)) s = s.replace(`{${k}}`, v);
  return s;
}

/** Texto bilingüe de los datos ({es, en}). */
export const tx = (obj) => (obj && typeof obj === "object" ? obj[lang] ?? obj.es ?? "" : obj ?? "");

export function setLang(nuevo) {
  if (!DICT[nuevo]) return;
  lang = nuevo;
  try { localStorage.setItem("golfo_lang", nuevo); } catch (_) { /* sin persistencia */ }
  applyTranslations();
}

export function applyTranslations(root = document) {
  document.documentElement.lang = lang;
  root.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
  root.querySelectorAll("[data-i18n-title]").forEach((el) => { el.title = t(el.dataset.i18nTitle); el.setAttribute("aria-label", t(el.dataset.i18nTitle)); });
  root.querySelectorAll("[data-i18n-placeholder]").forEach((el) => { el.placeholder = t(el.dataset.i18nPlaceholder); });
  document.title = t("title");
}

export function fmtMonth(month) {
  const [y, m] = month.split("-").map(Number);
  const s = new Intl.DateTimeFormat(lang === "es" ? "es-MX" : "en-US", { month: "long", year: "numeric", timeZone: "UTC" })
    .format(new Date(Date.UTC(y, m - 1, 15)));
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function fmtDate(iso) {
  if (!iso) return "";
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);   // acepta 'YYYY-MM', 'YYYY-MM-DD' o ISO con hora
  return new Intl.DateTimeFormat(lang === "es" ? "es-MX" : "en-US", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" })
    .format(new Date(Date.UTC(y, m - 1, d || 1)));
}

/** Describe una selección: "24°N–25°N, 90°O–89°O" (bbox) o "5 vértices" (polígono). */
export function fmtSel(sel) {
  const ew = lang === "es" ? "O" : "W";
  const f = (v, pos, neg) => `${fmtNum(Math.abs(v), Number.isInteger(v) ? 0 : 2)}°${v >= 0 ? pos : neg}`;
  if (sel.type === "bbox") {
    const [w, s, e, n] = sel.bbox;
    return `${f(s, "N", "S")}–${f(n, "N", "S")}, ${f(w, "E", ew)}–${f(e, "E", ew)}`;
  }
  return `${sel.coords.length} ${lang === "es" ? "vértices" : "vertices"}`;
}

export function fmtNum(x, digits = 1) {
  if (x === null || x === undefined || Number.isNaN(x)) return "—";
  return new Intl.NumberFormat(lang === "es" ? "es-MX" : "en-US", { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(x);
}
