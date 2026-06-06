import source_compare_service as service


def test_compare_current_sources_uses_explicit_current_provider_helpers(monkeypatch):
    helper_calls = []
    monkeypatch.setattr(
        service,
        "get_current_weather_openweather_only",
        lambda lat, lon: helper_calls.append("ow_current") or {
            "main": {"temp": 10, "feels_like": 9, "humidity": 60, "pressure": 1010},
            "weather": [{"description": "ясно"}],
            "wind": {"speed": 4.5},
        },
    )
    monkeypatch.setattr(
        service,
        "get_current_weather_open_meteo_direct",
        lambda lat, lon: helper_calls.append("om_current") or {
            "main": {"temp": 11, "feels_like": 10, "humidity": 58, "pressure": 1009},
            "weather": [{"description": "ясно"}],
            "wind": {"speed": 2.8},
        },
    )

    result = service.compare_current_sources(55.75, 37.61, "Москва")

    assert helper_calls == ["ow_current", "om_current"]
    assert result["ok"] is True
    assert result["title"] == "🔎 Сравнение погоды сейчас"
    assert result["openweather"]["provider_name"] == "OpenWeather"
    assert result["open_meteo"]["provider_name"] == "Open-Meteo"


def test_get_source_compare_available_dates_uses_explicit_forecast_helpers(monkeypatch):
    helper_calls = []
    ow_slots = [
        {"dt_txt": "2026-05-10 21:00:00", "_timezone_offset": 10800, "main": {"temp": 10}, "weather": [{"description": "ясно"}], "wind": {"speed": 3}},
        {"dt_txt": "2026-05-11 12:00:00", "_timezone_offset": 10800, "main": {"temp": 11}, "weather": [{"description": "ясно"}], "wind": {"speed": 4}},
    ]
    om_slots = [
        {"dt_txt": "2026-05-10 21:00:00", "_timezone_offset": 10800, "main": {"temp": 9}, "weather": [{"description": "ясно"}], "wind": {"speed": 2}},
        {"dt_txt": "2026-05-11 12:00:00", "_timezone_offset": 10800, "main": {"temp": 10}, "weather": [{"description": "ясно"}], "wind": {"speed": 3}},
    ]
    monkeypatch.setattr(service, "get_forecast_5d3h_openweather_only", lambda lat, lon: helper_calls.append("ow_forecast") or ow_slots)
    monkeypatch.setattr(service, "get_forecast_5d3h_open_meteo_direct", lambda lat, lon: helper_calls.append("om_forecast") or om_slots)

    result = service.get_source_compare_available_dates(55.75, 37.61, "Москва")

    assert helper_calls == ["ow_forecast", "om_forecast"]
    assert result["ok"] is True
    assert result["available_days"] == ["11.05"]


def test_compare_tomorrow_sources_success(monkeypatch):
    ow_slots = [
        {"dt_txt": "2026-05-04 12:00:00", "main": {"temp": 10, "feels_like": 8, "humidity": 60, "pressure": 1008}, "weather": [{"description": "ясно"}], "wind": {"speed": 3}, "pop": 0.1, "rain": {"3h": 0.4}},
        {"dt_txt": "2026-05-04 15:00:00", "main": {"temp": 18, "feels_like": 16, "humidity": 78, "pressure": 1012}, "weather": [{"description": "ясно"}], "wind": {"speed": 4}, "pop": 0.3, "rain": {"3h": 1.2}},
    ]
    om_slots = [
        {"dt_txt": "2026-05-04 12:00:00", "main": {"temp": 9, "humidity": 58, "pressure": 1009}, "weather": [{"description": "ясно"}], "wind": {"speed": 3}, "pop": 0.1},
        {"dt_txt": "2026-05-04 15:00:00", "main": {"temp": 17, "humidity": 74, "pressure": 1011}, "weather": [{"description": "ясно"}], "wind": {"speed": 5}, "pop": 0.4},
    ]
    monkeypatch.setattr(service, "get_forecast_5d3h_openweather_only", lambda lat, lon: ow_slots)
    monkeypatch.setattr(service, "get_forecast_5d3h_open_meteo_direct", lambda lat, lon: om_slots)
    monkeypatch.setattr(service, "get_tomorrow_forecast_day", lambda grouped: ("04.05", grouped["04.05"]))

    result = service.compare_tomorrow_sources(55.75, 37.61, "Москва")

    assert result["ok"] is True
    assert result["city_label"] == "Москва"
    assert result["openweather"]["provider_name"] == "OpenWeather"
    assert result["open_meteo"]["provider_name"] == "Open-Meteo"
    assert result["openweather"]["min_feels_like"] == 8
    assert result["openweather"]["max_feels_like"] == 16
    assert result["openweather"]["precipitation_signal"]["max_amount"] == 1.2
    assert result["openweather"]["wind_signal"]["min_speed"] == 3
    assert result["openweather"]["min_humidity"] == 60
    assert result["openweather"]["max_pressure"] == 1012


def test_compare_tomorrow_sources_uses_explicit_provider_helpers_and_local_grouping(monkeypatch):
    ow_slots = [
        {"dt_txt": "2026-05-10 22:00:00", "_timezone_offset": 10800, "main": {"temp": 10}, "weather": [{"description": "ясно"}], "wind": {"speed": 3}, "pop": 0.1},
        {"dt_txt": "2026-05-11 12:00:00", "_timezone_offset": 10800, "main": {"temp": 12}, "weather": [{"description": "ясно"}], "wind": {"speed": 4}, "pop": 0.1},
    ]
    om_slots = [
        {"dt_txt": "2026-05-10 22:00:00", "_timezone_offset": 10800, "main": {"temp": 9}, "weather": [{"description": "ясно"}], "wind": {"speed": 3}, "pop": 0.1},
        {"dt_txt": "2026-05-11 12:00:00", "_timezone_offset": 10800, "main": {"temp": 11}, "weather": [{"description": "ясно"}], "wind": {"speed": 4}, "pop": 0.1},
    ]
    helper_calls = []

    monkeypatch.setattr(
        service,
        "get_forecast_5d3h_openweather_only",
        lambda lat, lon: helper_calls.append("ow") or ow_slots,
    )
    monkeypatch.setattr(
        service,
        "get_forecast_5d3h_open_meteo_direct",
        lambda lat, lon: helper_calls.append("om") or om_slots,
    )
    monkeypatch.setattr(service, "get_tomorrow_forecast_day", lambda grouped: ("11.05", grouped["11.05"]))

    result = service.compare_tomorrow_sources(55.75, 37.61, "Москва")

    assert helper_calls == ["ow", "om"]
    assert result["ok"] is True
    assert result["selected_day"] == "11.05"
    assert result["openweather"]["provider_name"] == "OpenWeather"
    assert result["openweather"]["selected_day"] == "11.05"
    assert result["openweather"]["wind_text"] == "умеренный"


def test_compare_tomorrow_sources_handles_openweather_missing(monkeypatch):
    monkeypatch.setattr(service, "get_forecast_5d3h_openweather_only", lambda lat, lon: None)
    monkeypatch.setattr(service, "get_forecast_5d3h_open_meteo_direct", lambda lat, lon: [{"dt_txt": "2026-05-04 12:00:00"}])

    result = service.compare_tomorrow_sources(55.75, 37.61, "Москва")

    assert result["ok"] is False
    assert result["error_code"] == "provider_unavailable"
    assert "OpenWeather сейчас не ответил" in result["error_message"]


def test_compare_tomorrow_sources_handles_open_meteo_missing(monkeypatch):
    monkeypatch.setattr(service, "get_forecast_5d3h_openweather_only", lambda lat, lon: [{"dt_txt": "2026-05-04 12:00:00"}])
    monkeypatch.setattr(service, "get_forecast_5d3h_open_meteo_direct", lambda lat, lon: None)

    result = service.compare_tomorrow_sources(55.75, 37.61, "Москва")

    assert result["ok"] is False
    assert result["error_code"] == "provider_unavailable"
    assert "Open-Meteo сейчас не ответил" in result["error_message"]


def test_compare_tomorrow_sources_handles_missing_tomorrow(monkeypatch):
    slots = [{"dt_txt": "2026-05-06 12:00:00", "main": {"temp": 10}, "weather": [{"description": "ясно"}], "wind": {"speed": 3}, "pop": 0.1}]
    monkeypatch.setattr(service, "get_forecast_5d3h_openweather_only", lambda lat, lon: slots)
    monkeypatch.setattr(service, "get_forecast_5d3h_open_meteo_direct", lambda lat, lon: slots)
    monkeypatch.setattr(service, "get_tomorrow_forecast_day", lambda grouped: None)

    result = service.compare_tomorrow_sources(55.75, 37.61, "Москва")

    assert result["ok"] is False
    assert result["error_code"] == "tomorrow_missing"
    assert "прогноз на завтра" in result["error_message"]


def test_compare_today_sources_uses_local_day_helper(monkeypatch):
    ow_slots = [{"dt_txt": "2026-05-10 12:00:00", "_timezone_offset": 10800, "main": {"temp": 10}, "weather": [{"description": "ясно"}], "wind": {"speed": 3}}]
    om_slots = [{"dt_txt": "2026-05-10 12:00:00", "_timezone_offset": 10800, "main": {"temp": 9}, "weather": [{"description": "ясно"}], "wind": {"speed": 2}}]
    calls = []
    monkeypatch.setattr(service, "get_forecast_5d3h_openweather_only", lambda lat, lon: calls.append("ow") or ow_slots)
    monkeypatch.setattr(service, "get_forecast_5d3h_open_meteo_direct", lambda lat, lon: calls.append("om") or om_slots)
    monkeypatch.setattr(service, "get_today_forecast_day", lambda grouped: ("10.05", grouped["10.05"]))
    monkeypatch.setattr(service, "is_remaining_day_forecast", lambda items: False)

    result = service.compare_today_sources(55.75, 37.61, "Москва")

    assert calls == ["ow", "om"]
    assert result["ok"] is True
    assert result["title"] == "🔎 Сравнение прогнозов на сегодня"


def test_compare_sources_by_date_uses_explicit_provider_helpers(monkeypatch):
    ow_slots = [{"dt_txt": "2026-05-11 12:00:00", "_timezone_offset": 10800, "main": {"temp": 10}, "weather": [{"description": "ясно"}], "wind": {"speed": 3}}]
    om_slots = [{"dt_txt": "2026-05-11 12:00:00", "_timezone_offset": 10800, "main": {"temp": 9}, "weather": [{"description": "ясно"}], "wind": {"speed": 2}}]
    calls = []
    monkeypatch.setattr(service, "get_forecast_5d3h_openweather_only", lambda lat, lon: calls.append("ow") or ow_slots)
    monkeypatch.setattr(service, "get_forecast_5d3h_open_meteo_direct", lambda lat, lon: calls.append("om") or om_slots)

    result = service.compare_sources_by_date(55.75, 37.61, "Москва", "11.05")

    assert calls == ["ow", "om"]
    assert result["ok"] is True
    assert result["title"] == "🔎 Сравнение прогнозов на 11.05"
