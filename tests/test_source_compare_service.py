from datetime import date

import source_compare_service as service


def test_compare_tomorrow_sources_success(monkeypatch):
    ow_slots = [
        {"dt_txt": "2026-05-04 12:00:00", "main": {"temp": 10}, "weather": [{"description": "ясно"}], "wind": {"speed": 3}, "pop": 0.1},
        {"dt_txt": "2026-05-04 15:00:00", "main": {"temp": 18}, "weather": [{"description": "ясно"}], "wind": {"speed": 4}, "pop": 0.1},
    ]
    om_slots = [
        {"dt_txt": "2026-05-04 12:00:00", "main": {"temp": 9}, "weather": [{"description": "ясно"}], "wind": {"speed": 3}, "pop": 0.1},
        {"dt_txt": "2026-05-04 15:00:00", "main": {"temp": 17}, "weather": [{"description": "ясно"}], "wind": {"speed": 5}, "pop": 0.1},
    ]
    monkeypatch.setattr(service, "get_forecast_5d3h_openweather_only", lambda lat, lon: ow_slots)
    monkeypatch.setattr(service, "get_forecast_5d3h_open_meteo_direct", lambda lat, lon: om_slots)
    monkeypatch.setattr(service, "get_tomorrow_forecast_day", lambda grouped: ("04.05", grouped["04.05"]))

    result = service.compare_tomorrow_sources(55.75, 37.61, "Москва")

    assert result["ok"] is True
    assert result["city_label"] == "Москва"
    assert result["openweather"]["provider_name"] == "OpenWeather"
    assert result["open_meteo"]["provider_name"] == "Open-Meteo"


def test_compare_tomorrow_sources_handles_openweather_missing(monkeypatch):
    monkeypatch.setattr(service, "get_forecast_5d3h_openweather_only", lambda lat, lon: None)
    monkeypatch.setattr(service, "get_forecast_5d3h_open_meteo_direct", lambda lat, lon: [{"dt_txt": "2026-05-04 12:00:00"}])

    result = service.compare_tomorrow_sources(55.75, 37.61, "Москва")

    assert result["ok"] is False
    assert result["error_code"] == "provider_unavailable"
    assert "OpenWeather недоступен" in result["error_message"]


def test_compare_tomorrow_sources_handles_open_meteo_missing(monkeypatch):
    monkeypatch.setattr(service, "get_forecast_5d3h_openweather_only", lambda lat, lon: [{"dt_txt": "2026-05-04 12:00:00"}])
    monkeypatch.setattr(service, "get_forecast_5d3h_open_meteo_direct", lambda lat, lon: None)

    result = service.compare_tomorrow_sources(55.75, 37.61, "Москва")

    assert result["ok"] is False
    assert result["error_code"] == "provider_unavailable"
    assert "Open-Meteo недоступен" in result["error_message"]


def test_compare_tomorrow_sources_handles_missing_tomorrow(monkeypatch):
    slots = [{"dt_txt": "2026-05-06 12:00:00", "main": {"temp": 10}, "weather": [{"description": "ясно"}], "wind": {"speed": 3}, "pop": 0.1}]
    monkeypatch.setattr(service, "get_forecast_5d3h_openweather_only", lambda lat, lon: slots)
    monkeypatch.setattr(service, "get_forecast_5d3h_open_meteo_direct", lambda lat, lon: slots)
    monkeypatch.setattr(service, "get_tomorrow_forecast_day", lambda grouped: None)

    result = service.compare_tomorrow_sources(55.75, 37.61, "Москва")

    assert result["ok"] is False
    assert result["error_code"] == "tomorrow_missing"
    assert "прогноз на завтра" in result["error_message"]
