"""Sentry monitoring setup for the TTC daemon."""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def init_sentry() -> bool:
    """Initialize Sentry when TTC_SENTRY_DSN is configured."""
    dsn = os.getenv("TTC_SENTRY_DSN", "").strip()
    if not dsn:
        logger.info("Sentry disabled: TTC_SENTRY_DSN is not configured")
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
    except Exception as e:
        logger.warning("Sentry disabled: sentry-sdk is not installed: %s", e)
        return False

    sentry_sdk.init(
        dsn=dsn,
        environment=os.getenv("TTC_SENTRY_ENVIRONMENT", os.getenv("TTC_ENV", "production")),
        release=os.getenv("TTC_SENTRY_RELEASE", os.getenv("TTC_RELEASE", "ttc-daemon@0.3.0")),
        traces_sample_rate=_float_env("TTC_SENTRY_TRACES_SAMPLE_RATE", 0.1),
        profiles_sample_rate=_float_env("TTC_SENTRY_PROFILES_SAMPLE_RATE", 0.0),
        send_default_pii=os.getenv("TTC_SENTRY_SEND_PII", "false").lower() == "true",
        integrations=[
            StarletteIntegration(),
            FastApiIntegration(),
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
    )
    logger.info("Sentry enabled for TTC daemon")
    return True


def sentry_status() -> dict:
    try:
        import sentry_sdk

        return {
            "enabled": sentry_sdk.is_initialized(),
            "environment": os.getenv("TTC_SENTRY_ENVIRONMENT", os.getenv("TTC_ENV", "production")),
            "release": os.getenv("TTC_SENTRY_RELEASE", os.getenv("TTC_RELEASE", "ttc-daemon@0.3.0")),
        }
    except Exception:
        return {"enabled": False}
