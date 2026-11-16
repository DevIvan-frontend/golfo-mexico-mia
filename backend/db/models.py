"""
Esquema relacional (SQLAlchemy Core), válido para SQLite (desarrollo) y PostgreSQL (producción).
Para PostGIS hay un DDL equivalente con geometrías en backend/db/schema_postgis.sql.
"""
from sqlalchemy import Column, Float, Integer, MetaData, String, Table, Text

metadata = MetaData()

# Malla de 0.25°: una fila por celda oceánica del golfo
cells = Table(
    "cells", metadata,
    Column("cell_id", Integer, primary_key=True),
    Column("iy", Integer, nullable=False, index=True),
    Column("ix", Integer, nullable=False, index=True),
    Column("lat", Float, nullable=False),
    Column("lon", Float, nullable=False),
)

# Ejes de la malla (para reconstruir matrices completas, incluidas celdas de tierra)
grid_axes = Table(
    "grid_axes", metadata,
    Column("axis", String(8), primary_key=True),      # 'lat' | 'lon'
    Column("idx", Integer, primary_key=True),
    Column("value", Float, nullable=False),
)

months = Table(
    "months", metadata,
    Column("month_idx", Integer, primary_key=True),
    Column("month", String(7), nullable=False, unique=True),   # 'YYYY-MM'
)

# Observaciones mensuales (formato ancho: una fila por celda y mes)
ocean_monthly = Table(
    "ocean_monthly", metadata,
    Column("month_idx", Integer, primary_key=True),
    Column("cell_id", Integer, primary_key=True),
    Column("sst", Float),      # °C
    Column("chl", Float),      # mg m-3
)

climatology = Table(
    "climatology", metadata,
    Column("cell_id", Integer, primary_key=True),
    Column("month_of_year", Integer, primary_key=True),
    Column("sst", Float),
    Column("logchl", Float),
)

bathymetry = Table(
    "bathymetry", metadata,
    Column("iy", Integer, primary_key=True),
    Column("ix", Integer, primary_key=True),
    Column("lat", Float, nullable=False),
    Column("lon", Float, nullable=False),
    Column("altitude", Float),   # m, negativo en el mar
    Column("depth", Float),      # m, solo dentro del golfo
)

obis_grid = Table(
    "obis_grid", metadata,
    Column("year", Integer, primary_key=True),
    Column("geojson", Text, nullable=False),
)

events = Table(
    "events", metadata,
    Column("id", String(64), primary_key=True),
    Column("start", String(10), index=True),
    Column("data", Text, nullable=False),   # JSON completo (bilingüe)
)

places = Table(
    "places", metadata,
    Column("id", String(64), primary_key=True),
    Column("data", Text, nullable=False),
)

meta = Table(
    "meta", metadata,
    Column("key", String(64), primary_key=True),
    Column("value", Text, nullable=False),
)
