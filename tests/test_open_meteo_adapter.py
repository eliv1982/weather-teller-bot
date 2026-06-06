"""Tests for Open-Meteo client + OpenWeather-shaped adapters (no live HTTP)."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from forecast_service import get_tomorrow_forecast_day, group_forecast_by_day
from formatters import format_tomorrow_forecast_response, format_weather_response
from weather.open_meteo import (
    fetch_open_meteo_forecast_bundle,
    map_open_meteo_to_current_weather,
    map_open_meteo_to_forecast_slots,
    weather_code_to_description_ru,
)


def _sample_om_root() -> dict:
    """Minimal Open-Meteo-shaped fixture (UTC)."""
    return {
        "latitude": 55.75,
        "longitude": 37.62,
        "generationtime_ms": 1.0,
        "utc_offset_seconds": 0,
        "timezone": "UTC",
        "timezone_abbreviation": "UTC",
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
        "hourly": {
            "time": [
                "2026-05-03T09:00:00",
                "2026-05-03T10:00:00",
                "2026-05-03T11:00:00",
                "2026-05-03T12:00:00",
                "2026-05-03T13:00:00",
                "2026-05-03T14:00:00",
                "2026-05-03T15:00:00",
            ],
            "temperature_2m": [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0],
            "apparent_temperature": [9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0],
            "relative_humidity_2m": [60.0] * 7,
            "pressure_msl": [1010.0] * 7,
            "weather_code": [1, 2, 3, 61, 61, 61, 95],
            "wind_speed_10m": [3.0, 3.1, 3.2, 3.3, 3.4, 3.5, 5.0],
            "wind_direction_10m": [90, 91, 92, 93, 94, 95, 270],
            "precipitation_probability": [0, 10, 20, 40, 50, 60, 80],
            "precipitation": [0.0, 0.0, 0.0, 0.2, 0.3, 0.0, 1.0],
        },
    }


def test_weather_code_mapping_russian():
    assert weather_code_to_description_ru(0) == "ясно"
    assert weather_code_to_description_ru(2) == "переменная облачность"
    assert weather_code_to_description_ru(3) == "пасмурно"
    assert weather_code_to_description_ru(45) == "туман"
    assert weather_code_to_description_ru(51) == "небольшой дождь"
    assert weather_code_to_description_ru(61) == "дождь"
    assert weather_code_to_description_ru(71) == "снег"
    assert weather_code_to_description_ru(95) == "гроза"
    assert weather_code_to_description_ru(9999) == "без описания"
    assert weather_code_to_description_ru(None) == "без описания"


def test_map_current_compatible_with_format_weather_response():
    om = _sample_om_root()
    ow_like = map_open_meteo_to_current_weather(om)
    assert ow_like is not None
    text = format_weather_response("Москва", ow_like)
    assert "Москва" in text
    assert "15.2" in text or "15.2 °C" in text.replace(" ", "")
    assert "14" in text
    assert "ясно" in text.lower()
    assert "55" in text
    assert "759" in text or "мм рт" in text
    assert "4.5" in text or "4,5" in text


def test_map_current_uses_surface_pressure_if_msl_missing():
    om = _sample_om_root()
    cur = om["current"]
    del cur["pressure_msl"]
    cur["surface_pressure"] = 1000.0
    ow_like = map_open_meteo_to_current_weather(om)
    assert ow_like["main"]["pressure"] == 1000.0


def test_map_current_partial_fields():
    ow_like = map_open_meteo_to_current_weather({"current": {"weather_code": 0}})
    assert ow_like is not None
    assert ow_like["main"]["temp"] is None
    text = format_weather_response("X", ow_like)
    assert "н/д" in text


def test_map_current_returns_none_without_current_block():
    assert map_open_meteo_to_current_weather({}) is None
    assert map_open_meteo_to_current_weather({"hourly": {}}) is None


def test_forecast_slots_have_required_keys_and_pop():
    slots = map_open_meteo_to_forecast_slots(_sample_om_root(), every_nth_hour=3)
    assert len(slots) == 3
    for s in slots:
        assert isinstance(s["dt"], int)
        assert isinstance(s["dt_txt"], str)
        assert len(s["dt_txt"]) >= 16
        assert s["_timezone_offset"] == 0
        assert "main" in s and "weather" in s and "wind" in s
        assert "pop" in s
        assert isinstance(s["weather"], list) and s["weather"][0].get("description")


def test_forecast_wind_speed_ms_and_pressure_hpa():
    slots = map_open_meteo_to_forecast_slots(_sample_om_root(), every_nth_hour=3)
    assert slots[0]["wind"]["speed"] == 3.0
    assert slots[0]["main"]["pressure"] == 1010.0
    assert slots[2]["wind"]["speed"] == 5.0


def test_forecast_pop_fraction_from_probability():
    slots = map_open_meteo_to_forecast_slots(_sample_om_root(), every_nth_hour=1)
    assert slots[3]["pop"] == pytest.approx(0.4)


def test_forecast_group_by_day():
    slots = map_open_meteo_to_forecast_slots(_sample_om_root(), every_nth_hour=3)
    grouped = group_forecast_by_day(slots)
    assert "03.05" in grouped
    assert len(grouped["03.05"]) == 3


def test_forecast_format_forecast_day_smoke():
    from forecast_service import format_forecast_day

    slots = map_open_meteo_to_forecast_slots(_sample_om_root(), every_nth_hour=3)
    text = format_forecast_day("03.05", slots, "Москва")
    assert "03.05" in text
    assert "Москва" in text


def test_forecast_format_tomorrow_from_mapped_slots():
    slots = map_open_meteo_to_forecast_slots(_sample_om_root(), every_nth_hour=1)
    grouped = group_forecast_by_day(slots)
    pair = get_tomorrow_forecast_day(grouped, today=date(2026, 5, 2))
    assert pair is not None
    day_key, day_items = pair
    assert day_key == "03.05"
    text = format_tomorrow_forecast_response("Москва", day_key, day_items)
    assert "завтра" in text.lower()
    assert "Москва" in text


def test_deterministic_three_hour_stride():
    om = _sample_om_root()
    slots_all = map_open_meteo_to_forecast_slots(om, every_nth_hour=1)
    slots_3 = map_open_meteo_to_forecast_slots(om, every_nth_hour=3)
    assert len(slots_3) == (len(slots_all) + 2) // 3
    assert [s["dt_txt"] for s in slots_3] == [slots_all[i]["dt_txt"] for i in range(0, len(slots_all), 3)]


def test_hourly_misaligned_length_trims_safely():
    om = _sample_om_root()
    om["hourly"]["precipitation_probability"] = [0, 10]
    slots = map_open_meteo_to_forecast_slots(om, every_nth_hour=1)
    assert len(slots) == 2


def test_map_forecast_empty_on_bad_hourly():
    assert map_open_meteo_to_forecast_slots({}) == []
    assert map_open_meteo_to_forecast_slots({"hourly": {}}) == []


def test_non_utc_timezone_offset_propagates():
    om = _sample_om_root()
    om["utc_offset_seconds"] = 10800
    slots = map_open_meteo_to_forecast_slots(om, every_nth_hour=3)
    assert all(s["_timezone_offset"] == 10800 for s in slots)


@patch("weather.open_meteo.requests.get")
def test_fetch_open_meteo_success(mock_get: MagicMock):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"current": {}, "hourly": {"time": []}}
    mock_get.return_value = mock_resp
    out = fetch_open_meteo_forecast_bundle(1.0, 2.0)
    assert out == {"current": {}, "hourly": {"time": []}}
    mock_get.assert_called_once()
    args, kwargs = mock_get.call_args
    assert "api.open-meteo.com" in args[0]
    assert kwargs["params"]["wind_speed_unit"] == "ms"


@patch("weather.open_meteo.requests.get")
def test_fetch_open_meteo_returns_none_on_http_error(mock_get: MagicMock):
    mock_resp = MagicMock()
    mock_resp.status_code = 503
    mock_get.return_value = mock_resp
    assert fetch_open_meteo_forecast_bundle(0.0, 0.0) is None
