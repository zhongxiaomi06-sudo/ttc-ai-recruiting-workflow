"""Configuration loader for matching rules — reads JSON from matching/config/"""
from __future__ import annotations
import json
import os
from typing import Optional, Any
from loguru import logger

_CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)))
_cache: dict = {}


def load_config(name: str) -> Optional[dict]:
    """Load a JSON config file from matching/config/.
    Results are cached in memory; call reload_configs() to refresh.
    """
    if name in _cache:
        return _cache[name]

    path = os.path.join(_CONFIG_DIR, name)
    if not os.path.exists(path):
        logger.warning(f"Config not found: {path}")
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            _cache[name] = data
            logger.info(f"Loaded config: {name}")
            return data
    except Exception as e:
        logger.error(f"Failed to load config {name}: {e}")
        return None


def reload_configs():
    """Clear config cache so next load_config() re-reads from disk."""
    _cache.clear()
    logger.info("Config cache cleared — next reads will reload from disk")


def get_config_dir() -> str:
    return _CONFIG_DIR
