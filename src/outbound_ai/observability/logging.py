"""Structured, privacy-aware application logging."""

from __future__ import annotations

import logging
from typing import Any

_REDACT_KEYS = {
    "authorization",
    "auth_token",
    "openai_api_key",
    "supabase_service_role_key",
    "phone",
    "phone_e164",
    "content",
    "text_raw",
}


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def _safe(value: Any, key: str) -> Any:
    if key.lower() in _REDACT_KEYS:
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): _safe(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_safe(item, key) for item in value]
    return value


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    safe_fields = {key: _safe(value, key) for key, value in fields.items()}
    logger.info("%s %s", event, safe_fields)
