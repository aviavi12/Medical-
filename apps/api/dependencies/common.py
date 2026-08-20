"""Shared FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy.orm import Session

from apps.api.config import get_settings
from apps.api.services.storage import StorageProvider, get_storage
from database.base import get_db
from ml.common.config import get_ml_config


def get_db_session() -> Iterator[Session]:
    yield from get_db()


def get_storage_provider() -> StorageProvider:
    return get_storage(get_settings())


def get_config():
    return get_ml_config()
