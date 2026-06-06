"""Tests for Open-Meteo forecast fallback in weather.api.get_forecast_5d3h (mocked)."""

from unittest.mock import MagicMock, patch

import pytest

import weather.api as api
from forecast_service import group_forecast_by_day


def _om_fixture() -> dict:
    return {
        "utc_offset_seconds": 0,
        "hourly": {
            "time": [
                "2026-05-03T09:00:00",
                "2026-05-03T10:00:00",
                "2026-05-03T11:00:00",
            ],
            "temperature_2m": [10.0, 11.0, 12.0],
            "apparent_temperature": [9.0, 10.0, 11.0],
            "relative_humidity_2m": [60.0, 61.0, 62.0],
            "pressure_msl": [1010.0, 1011.0, 1012.0],
            "weather_code": [0, 1, 3],
            "wind_speed_10m": [2.0, 2.1, 2.2],
            "wind_direction_10m": [0, 90, 180],
            "precipitation_probability": [0, 5, 10],
            "precipitation": [0.0, 0.0, 0.0],
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


def test_fallback_disabled_ow_failure_no_open_meteo(fake_ow_key, monkeypatch):
    monkeypatch.delenv("OPEN_METEO_FALLBACK", raising=False)
    with patch.object(api, "fetch_open_meteo_forecast_bundle") as om_fetch:
        with patch.object(api, "safe_request", return_value=None):
            assert api.get_forecast_5d3h(55.0, 37.0) is None
        om_fetch.assert_not_called()


def test_fallback_enabled_ow_failure_uses_open_meteo(fake_ow_key, monkeypatch):
    monkeypatch.setenv("OPEN_METEO_FALLBACK", "1")
    om_data = _om_fixture()

    def _fetch(lat, lon, **_kwargs):
        assert lat == 55.0 and lon == 37.0
        return om_data

    with patch.object(api, "safe_request", return_value=None):
        with patch.object(api, "fetch_open_meteo_forecast_bundle", side_effect=_fetch):
            slots = api.get_forecast_5d3h(55.0, 37.0)
    assert slots is not None
    assert len(slots) == 1
    assert slots[0]["dt_txt"].startswith("2026-05-03")
    grouped = group_forecast_by_day(slots)
    assert "03.05" in grouped


def test_fallback_enabled_open_meteo_fails_returns_none(fake_ow_key, monkeypatch):
    monkeypatch.setenv("OPEN_METEO_FALLBACK", "1")
    with patch.object(api, "safe_request", return_value=None):
        with patch.object(api, "fetch_open_meteo_forecast_bundle", return_value=None):
            assert api.get_forecast_5d3h(1.0, 2.0) is None


def test_fallback_enabled_mapper_empty_returns_none(fake_ow_key, monkeypatch):
    monkeypatch.setenv("OPEN_METEO_FALLBACK", "1")
    with patch.object(api, "safe_request", return_value=None):
        with patch.object(api, "fetch_open_meteo_forecast_bundle", return_value={"hourly": {"time": []}}):
            assert api.get_forecast_5d3h(1.0, 2.0) is None


def test_openweather_success_does_not_call_open_meteo(fake_ow_key, monkeypatch):
    monkeypatch.setenv("OPEN_METEO_FALLBACK", "1")
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "list": [
            {
                "dt": 100,
                "dt_txt": "2026-05-03 12:00:00",
                "main": {"temp": 5.0},
                "weather": [{"description": "ясно"}],
            }
        ],
        "city": {"timezone": 10800},
    }
    with patch.object(api, "safe_request", return_value=resp):
        with patch.object(api, "fetch_open_meteo_forecast_bundle") as om_fetch:
            out = api.get_forecast_5d3h(10.0, 20.0)
    om_fetch.assert_not_called()
    assert out is not None
    assert len(out) == 1
    assert out[0].get("_timezone_offset") == 10800


def test_fallback_result_cached_same_key(fake_ow_key, monkeypatch):
    monkeypatch.setenv("OPEN_METEO_FALLBACK", "1")
    calls = {"ow": 0, "om": 0}

    def ow_request(*_a, **_k):
        calls["ow"] += 1
        return None

    def om_fetch(*_a, **_k):
        calls["om"] += 1
        return _om_fixture()

    with patch.object(api, "safe_request", side_effect=ow_request):
        with patch.object(api, "fetch_open_meteo_forecast_bundle", side_effect=om_fetch):
            first = api.get_forecast_5d3h(1.0, 2.0)
            second = api.get_forecast_5d3h(1.0, 2.0)
    assert first == second
    assert calls["ow"] == 1
    assert calls["om"] == 1
