"""safe_request must never write OpenWeather API keys (query-string secrets) to logs."""

import logging

import pytest
import requests

import weather.api as api

FAKE_KEY = "FAKE_OW_KEY_MARKER_9f3a1c"


def _leaky_error() -> requests.ConnectionError:
    # Mirrors the real requests/urllib3 message, which embeds the full request URL.
    return requests.ConnectionError(
        "HTTPSConnectionPool(host='api.openweathermap.org', port=443): Max retries exceeded with url: "
        f"/data/2.5/weather?lat=55.75&lon=37.61&appid={FAKE_KEY}&units=metric&lang=ru "
        "(Caused by NewConnectionError('Failed to establish a new connection'))"
    )


def _full_log_output(caplog) -> str:
    """Everything a handler could emit: message text, formatted traceback, exception details."""
    formatter = logging.Formatter("%(levelname)s %(name)s %(message)s")
    parts = [caplog.text]
    for record in caplog.records:
        parts.append(formatter.format(record))
        parts.append(record.getMessage())
        parts.append(str(record.args))
        parts.append(str(record.exc_text))
        if record.exc_info:
            parts.append(repr(record.exc_info[1]))
            parts.append(str(record.exc_info[1]))
    return "\n".join(parts)


@pytest.fixture(autouse=True)
def _no_sleep_and_clean_cache(monkeypatch):
    monkeypatch.setattr(api.time, "sleep", lambda _seconds: None)
    api.API_CACHE._store.clear()
    yield
    api.API_CACHE._store.clear()


def test_safe_request_network_error_does_not_log_api_key(monkeypatch, caplog):
    def _raise(*_args, **_kwargs):
        raise _leaky_error()

    monkeypatch.setattr(api.requests, "get", _raise)

    with caplog.at_level(logging.DEBUG):
        result = api.safe_request(
            "https://api.openweathermap.org/data/2.5/weather",
            {"lat": 55.75, "lon": 37.61, "appid": FAKE_KEY},
        )

    assert result is None
    assert api.LAST_ERROR_TYPE == "network"
    output = _full_log_output(caplog)
    assert FAKE_KEY not in output
    assert "appid=" not in output
    # Still useful for diagnostics: which endpoint failed and with what kind of error.
    assert "https://api.openweathermap.org/data/2.5/weather" in output
    assert "ConnectionError" in output
    assert any(record.levelno >= logging.ERROR for record in caplog.records)


def test_safe_request_retries_do_not_log_api_key(monkeypatch, caplog):
    calls = {"n": 0}

    def _raise(*_args, **_kwargs):
        calls["n"] += 1
        raise _leaky_error()

    monkeypatch.setattr(api.requests, "get", _raise)

    with caplog.at_level(logging.DEBUG):
        api.safe_request("https://api.openweathermap.org/data/2.5/forecast", {"appid": FAKE_KEY}, retries=3)

    assert calls["n"] == 3
    assert FAKE_KEY not in _full_log_output(caplog)


def test_public_openweather_call_with_network_error_does_not_log_api_key(monkeypatch, caplog):
    monkeypatch.setattr(api, "OW_API_KEY", FAKE_KEY)
    monkeypatch.delenv("OPEN_METEO_FALLBACK", raising=False)

    def _raise(*_args, **_kwargs):
        raise _leaky_error()

    monkeypatch.setattr(api.requests, "get", _raise)

    with caplog.at_level(logging.DEBUG):
        assert api.get_current_weather(55.75, 37.61) is None
        assert api.get_forecast_5d3h(55.75, 37.61) is None
        assert api.get_air_pollution(55.75, 37.61) is None
        assert api.get_location_by_coordinates(55.75, 37.61) is None
        assert api.get_locations("Москва") is None

    assert caplog.records, "expected at least the network error to be logged"
    assert FAKE_KEY not in _full_log_output(caplog)


def test_endpoint_for_log_strips_query_and_fragment():
    assert (
        api._endpoint_for_log(f"https://api.openweathermap.org/geo/1.0/direct?q=Moscow&appid={FAKE_KEY}#x")
        == "https://api.openweathermap.org/geo/1.0/direct"
    )
    assert api._endpoint_for_log("https://api.openweathermap.org/data/2.5/weather") == (
        "https://api.openweathermap.org/data/2.5/weather"
    )
