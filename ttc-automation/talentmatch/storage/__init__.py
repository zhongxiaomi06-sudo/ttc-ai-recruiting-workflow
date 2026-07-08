"""Storage module — provides StorageBackend via factory"""
from __future__ import annotations
from typing import Optional
from loguru import logger

from .base import StorageBackend
from .sqlite_backend import SqliteBackend

_backend: Optional[StorageBackend] = None


def init_storage(db_path: Optional[str] = None) -> StorageBackend:
    """Initialize the storage backend. Call once at startup."""
    global _backend
    _backend = SqliteBackend(db_path=db_path)
    logger.info(f"Storage initialized: SQLite at {_backend.db_path}")
    return _backend


def get_storage() -> StorageBackend:
    """Get the initialized storage backend."""
    assert _backend is not None, "Storage not initialized — call init_storage() first"
    return _backend


__all__ = ["StorageBackend", "SqliteBackend", "init_storage", "get_storage"]
