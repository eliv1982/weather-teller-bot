import logging

from ai import response_cache


def test_get_cached_response_returns_backend_value(monkeypatch):
    calls = []

    def _fake_get(cache_key):
        calls.append(cache_key)
        return "cached text"

    monkeypatch.setattr(response_cache, "get_ai_cached_response", _fake_get)

    result = response_cache.get_cached_response("cache-key", logger=logging.getLogger("test.ai.response_cache"))

    assert result == "cached text"
    assert calls == ["cache-key"]


def test_get_cached_response_returns_none_on_backend_exception(monkeypatch, caplog):
    def _boom(cache_key):
        raise RuntimeError(f"boom:{cache_key}")

    monkeypatch.setattr(response_cache, "get_ai_cached_response", _boom)

    with caplog.at_level(logging.WARNING):
        result = response_cache.get_cached_response("cache-key", logger=logging.getLogger("test.ai.response_cache"))

    assert result is None
    assert "Ошибка чтения AI-кэша PostgreSQL" in caplog.text


def test_save_cached_response_passes_arguments_to_backend(monkeypatch):
    calls = []

    def _fake_save(cache_key, scenario, text, *, ttl_seconds):
        calls.append(
            {
                "cache_key": cache_key,
                "scenario": scenario,
                "text": text,
                "ttl_seconds": ttl_seconds,
            }
        )

    monkeypatch.setattr(response_cache, "save_ai_cached_response", _fake_save)

    result = response_cache.save_cached_response(
        "cache-key",
        "scenario-name",
        "response text",
        ttl_seconds=3600,
        logger=logging.getLogger("test.ai.response_cache"),
    )

    assert result is None
    assert calls == [
        {
            "cache_key": "cache-key",
            "scenario": "scenario-name",
            "text": "response text",
            "ttl_seconds": 3600,
        }
    ]


def test_save_cached_response_swallows_backend_exception(monkeypatch, caplog):
    def _boom(cache_key, scenario, text, *, ttl_seconds):
        raise RuntimeError(f"boom:{cache_key}:{scenario}:{ttl_seconds}:{text}")

    monkeypatch.setattr(response_cache, "save_ai_cached_response", _boom)

    with caplog.at_level(logging.WARNING):
        result = response_cache.save_cached_response(
            "cache-key",
            "scenario-name",
            "response text",
            ttl_seconds=3600,
            logger=logging.getLogger("test.ai.response_cache"),
        )

    assert result is None
    assert "Ошибка записи AI-кэша PostgreSQL" in caplog.text
