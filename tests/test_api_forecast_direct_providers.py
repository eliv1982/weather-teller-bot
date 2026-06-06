from unittest.mock import MagicMock, patch

import pytest

import weather.api as api


@pytest.fixture(autouse=True)
def _clear_api_cache():
    api.API_CACHE._store.clear()
    yield
    api.API_CACHE._store.clear()


@pytest.fixture
def fake_ow_key(monkeypatch):
    monkeypatch.setattr(api, "OW_API_KEY", "test_openweather_key")


def test_openweather_only_helper_does_not_call_open_meteo(fake_ow_key, monkeypatch):
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
            out = api.get_forecast_5d3h_openweather_only(10.0, 20.0)
    om_fetch.assert_not_called()
    assert out is not None
    assert out[0]["_timezone_offset"] == 10800


def test_open_meteo_direct_helper_uses_existing_mapper(monkeypatch):
    slots = [{"dt_txt": "2026-05-03 12:00:00", "main": {"temp": 7.0}, "weather": [{"description": "ясно"}]}]
    with patch.object(api, "fetch_open_meteo_forecast_bundle", return_value={"hourly": {"time": ["2026-05-03T12:00:00"]}}):
        with patch.object(api, "map_open_meteo_to_forecast_slots", return_value=slots) as mapper:
            out = api.get_forecast_5d3h_open_meteo_direct(55.0, 37.0)
    mapper.assert_called_once()
    assert out == slots
