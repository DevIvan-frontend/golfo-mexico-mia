-- Esquema de producción para PostgreSQL + PostGIS (equivalente a backend/db/models.py, con geometrías e índices
-- espaciales). Úsalo si quieres consultas espaciales nativas (ST_Intersects, ST_DWithin) desde otras herramientas.
-- La API funciona igual con el esquema de models.py (crea las tablas solo: python scripts/load_to_sql.py).

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS cells (
    cell_id   INTEGER PRIMARY KEY,
    iy        INTEGER NOT NULL,
    ix        INTEGER NOT NULL,
    lat       DOUBLE PRECISION NOT NULL,
    lon       DOUBLE PRECISION NOT NULL,
    geom      geometry(Polygon, 4326)      -- celda de 0.25°: ST_MakeEnvelope(lon-0.125, lat-0.125, lon+0.125, lat+0.125, 4326)
);
CREATE INDEX IF NOT EXISTS cells_geom_idx ON cells USING GIST (geom);

CREATE TABLE IF NOT EXISTS grid_axes (axis VARCHAR(8), idx INTEGER, value DOUBLE PRECISION NOT NULL, PRIMARY KEY (axis, idx));
CREATE TABLE IF NOT EXISTS months (month_idx INTEGER PRIMARY KEY, month CHAR(7) NOT NULL UNIQUE);

CREATE TABLE IF NOT EXISTS ocean_monthly (
    month_idx INTEGER REFERENCES months(month_idx),
    cell_id   INTEGER REFERENCES cells(cell_id),
    sst       REAL,          -- °C   (NASA JPL MUR)
    chl       REAL,          -- mg m-3 (NASA MODIS-Aqua)
    PRIMARY KEY (month_idx, cell_id)
);
CREATE INDEX IF NOT EXISTS ocean_monthly_cell_idx ON ocean_monthly (cell_id);

CREATE TABLE IF NOT EXISTS climatology (
    cell_id INTEGER REFERENCES cells(cell_id), month_of_year SMALLINT, sst REAL, logchl REAL,
    PRIMARY KEY (cell_id, month_of_year)
);

CREATE TABLE IF NOT EXISTS bathymetry (
    iy INTEGER, ix INTEGER, lat DOUBLE PRECISION NOT NULL, lon DOUBLE PRECISION NOT NULL,
    altitude REAL, depth REAL, geom geometry(Point, 4326),
    PRIMARY KEY (iy, ix)
);
CREATE INDEX IF NOT EXISTS bathymetry_geom_idx ON bathymetry USING GIST (geom);

CREATE TABLE IF NOT EXISTS obis_grid (year INTEGER PRIMARY KEY, geojson TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS events (
    id VARCHAR(64) PRIMARY KEY, start CHAR(10), data TEXT NOT NULL,
    geom geometry(Point, 4326), radius_km REAL
);
CREATE INDEX IF NOT EXISTS events_geom_idx ON events USING GIST (geom);

CREATE TABLE IF NOT EXISTS places (id VARCHAR(64) PRIMARY KEY, data TEXT NOT NULL, geom geometry(Point, 4326));
CREATE TABLE IF NOT EXISTS meta (key VARCHAR(64) PRIMARY KEY, value TEXT NOT NULL);

-- Tras cargar los datos con scripts/load_to_sql.py, rellena las geometrías:
-- UPDATE cells SET geom = ST_MakeEnvelope(lon-0.125, lat-0.125, lon+0.125, lat+0.125, 4326);
-- UPDATE bathymetry SET geom = ST_SetSRID(ST_MakePoint(lon, lat), 4326);
-- UPDATE events SET geom = ST_SetSRID(ST_MakePoint((data::json->>'lon')::float, (data::json->>'lat')::float), 4326),
--                   radius_km = (data::json->>'radius_km')::float;
--
-- Ejemplo: celdas afectadas por un evento (radio en metros sobre el geoide)
-- SELECT c.cell_id FROM cells c JOIN events e ON ST_DWithin(c.geom::geography, e.geom::geography, e.radius_km * 1000)
-- WHERE e.id = 'deepwater-2010';
