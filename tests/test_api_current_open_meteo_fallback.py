"""Tests for Open-Meteo current-weather fallback in weather.api.get_current_weather (mocked)."""

from unittest.mock import MagicMock, patch

import pytest

import weather.api as api
from formatters import format_weather_response


def _om_current_fixture() -> dict:
    return {
        "utc_offset_seconds": 0,
        "current": {
            "time": "2026-05-03T12:00",
            "interval": 900,
            "temperature_2m": 15.2,
            "apparent_temperature": 14.0,
            "relative_humidity_2m": 55.0,
            "pressure_msl": 1012.3,
            "weather_code": 0,
            "wind_speed_10m": 4.5,
            "wind_direction_10m": 180,
        },
    }


@pytest.fixture(autouse=True)
def _clear_api_cache():
    api.API_CACHE._store.clear()
    yield
    api.API_CACHE._store.clear()


@pytest.fixture
def fake_ow_key(monkeypatch):
    monkeypatch.setattr(api, "OW_API_KEY", "test_openweather_key")


def test_current_fallback_disabled_ow_failure_no_open_meteo(fake_ow_key, monkeypatch):
    monkeypatch.delenv("OPEN_METEO_FALLBACK", raising=False)
    with patch.object(api, "fetch_open_meteo_forecast_bundle") as om_fetch:
        with patch.object(api, "safe_request", return_value=None):
            assert api.get_current_weather(55.0, 37.0) is None
        om_fetch.assert_not_called()


def test_current_fallback_enabled_ow_failure_uses_open_meteo(fake_ow_key, monkeypatch):
    monkeypatch.setenv("OPEN_METEO_FALLBACK", "1")

    def _fetch(lat, lon, **_kwargs):
        assert lat == 55.0 and lon == 37.0
        return _om_current_fixture()

    with patch.object(api, "safe_request", return_value=None):
        with patch.object(api, "fetch_open_meteo_forecast_bundle", side_effect=_fetch):
            out = api.get_current_weather(55.0, 37.0)
    assert out is not None
    assert out["main"]["temp"] == 15.2
    text = format_weather_response("Test City", out)
    assert "Test City" in text
    assert "15.2" in text
    assert "Описание:" in text


def test_current_fallback_enabled_open_meteo_fails_returns_none(fake_ow_key, monkeypatch):
    monkeypatch.setenv("OPEN_METEO_FALLBACK", "1")
    with patch.object(api, "safe_request", return_value=None):
        with patch.object(api, "fetch_open_meteo_forecast_bundle", return_value=None):
            assert api.get_current_weather(1.0, 2.0) is None


def test_current_fallback_enabled_unusable_map_returns_none(fake_ow_key, monkeypatch):
    monkeypatch.setenv("OPEN_METEO_FALLBACK", "1")
    with patch.object(api, "safe_request", return_value=None):
        with patch.object(api, "fetch_open_meteo_forecast_bundle", return_value={"current": {}}):
            assert api.get_current_weather(1.0, 2.0) is None


def test_openweather_success_does_not_call_open_meteo(fake_ow_key, monkeypatch):
    monkeypatch.setenv("OPEN_METEO_FALLBACK", "1")
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "main": {"temp": 5.0, "feels_like": 4.0, "humidity": 50, "pressure": 1000},
        "weather": [{"description": "пасмурно"}],
        "wind": {"speed": 1.0, "deg": 90},
    }
    with patch.object(api, "safe_request", return_value=resp):
        with patch.object(api, "fetch_open_meteo_forecast_bundle") as om_fetch:
            out = api.get_current_weather(10.0, 20.0)
    om_fetch.assert_not_called()
    assert out == resp.json.return_value


def test_current_fallback_cached_second_call_no_providers(fake_ow_key, monkeypatch):
    monkeypatch.setenv("OPEN_METEO_FALLBACK", "1")
    calls = {"ow": 0, "om": 0}

    def ow_request(*_a, **_k):
        calls["ow"] += 1
        return None

    def om_fetch(*_a, **_k):
        calls["om"] += 1
        return _om_current_fixture()

    with patch.object(api, "safe_request", side_effect=ow_request):
        with patch.object(api, "fetch_open_meteo_forecast_bundle", side_effect=om_fetch):
            first = api.get_current_weather(1.0, 2.0)
            second = api.get_current_weather(1.0, 2.0)
    assert first == second
    assert calls["ow"] == 1
    assert calls["om"] == 1
