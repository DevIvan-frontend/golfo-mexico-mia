"""Fábrica del repositorio de datos según GOLFO_DATA_BACKEND."""
from __future__ import annotations

from ..config import DATA_BACKEND, DATABASE_URL, EVENTS_FILE, PLACES_FILE, PROCESSED_DIR
from .base import DataRepository


def get_repository() -> DataRepository:
    if DATA_BACKEND == "sql":
        from .sql_repository import SQLRepository
        return SQLRepository(DATABASE_URL)
    from .file_repository import FileRepository
    return FileRepository(PROCESSED_DIR, EVENTS_FILE, PLACES_FILE)
