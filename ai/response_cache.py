"""Low-level PostgreSQL-backed AI response cache helpers."""

from __future__ import annotations

import logging

from postgres_storage import get_ai_cached_response, save_ai_cached_response


def get_cached_response(cache_key: str, *, logger: logging.Logger) -> str | None:
    """Safely reads a cached AI response from PostgreSQL."""
    try:
        return get_ai_cached_response(cache_key)
    except Exception as exc:
        logger.warning("Ошибка чтения AI-кэша PostgreSQL: %s", exc)
        return None


def save_cached_response(
    cache_key: str,
    scenario: str,
    text: str,
    *,
    ttl_seconds: int,
    logger: logging.Logger,
) -> None:
    """Safely saves an AI response to PostgreSQL."""
    try:
        save_ai_cached_response(
            cache_key,
            scenario,
            text,
            ttl_seconds=ttl_seconds,
        )
    except Exception as exc:
        logger.warning("Ошибка записи AI-кэша PostgreSQL: %s", exc)
