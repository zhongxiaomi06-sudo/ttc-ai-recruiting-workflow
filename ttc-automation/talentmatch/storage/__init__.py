"""Storage module — provides a global Storage singleton for talentmatch."""
from __future__ import annotations
from typing import Optional

from .db import Storage

_backend: Optional[Storage] = None


def init_storage(db_path: Optional[str] = None, **kwargs) -> Storage:
    """Initialize the global storage backend. Call once at startup."""
    global _backend
    if _backend is None:
        _backend = Storage(db_path=db_path, **kwargs)
    return _backend


def get_storage() -> Storage:
    """Get the initialized storage backend."""
    assert _backend is not None, "Storage not initialized — call init_storage() first"
    return _backend


__all__ = ["Storage", "init_storage", "get_storage"]
