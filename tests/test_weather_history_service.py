from datetime import date

import weather_history_service as service


def test_parse_history_date_input_accepts_iso_format():
    parsed, error = service.parse_history_date_input("2026-05-01", today=date(2026, 6, 6))

    assert parsed == date(2026, 5, 1)
    assert error is None


def test_parse_history_date_input_accepts_dotted_format():
    parsed, error = service.parse_history_date_input("01.05.2026", today=date(2026, 6, 6))

    assert parsed == date(2026, 5, 1)
    assert error is None


def test_parse_history_date_input_rejects_invalid_date():
    parsed, error = service.parse_history_date_input("2026-02-31", today=date(2026, 6, 6))

    assert parsed is None
    assert "Не получилось распознать дату" in error


def test_parse_history_date_input_rejects_future_date():
    parsed, error = service.parse_history_date_input("2026-06-07", today=date(2026, 6, 6))

    assert parsed is None
    assert "Нужна дата из прошлого" in error


def test_get_weather_history_by_date_normalizes_open_meteo_payload(monkeypatch):
    monkeypatch.setattr(
        service,
        "fetch_open_meteo_history_daily",
        lambda lat, lon, target_date: {
            "timezone": "Europe/Moscow",
            "daily": {
                "time": ["2026-05-01"],
                "temperature_2m_max": [18.4],
                "temperature_2m_min": [9.1],
                "temperature_2m_mean": [13.2],
                "precipitation_sum": [5.4],
                "rain_sum": [5.4],
                "snowfall_sum": [0.0],
                "wind_speed_10m_max": [8.6],
                "wind_direction_10m_dominant": [225],
                "relative_humidity_2m_mean": [71],
                "pressure_msl_mean": [1012.8],
                "weather_code": [61],
            },
        },
    )

    result = service.get_weather_history_by_date(55.75, 37.61, "Москва", date(2026, 5, 1))

    assert result["ok"] is True
    assert result["city_label"] == "Москва"
    assert result["history"] == {
        "date": "2026-05-01",
        "date_label": "01.05.2026",
        "timezone": "Europe/Moscow",
        "temperature_max": 18.4,
        "temperature_min": 9.1,
        "temperature_mean": 13.2,
        "precipitation_sum": 5.4,
        "rain_sum": 5.4,
        "snowfall_sum": 0.0,
        "wind_speed_max": 8.6,
        "wind_direction_dominant": 225.0,
        "relative_humidity_mean": 71.0,
        "pressure_mean": 1012.8,
        "pressure_source": "pressure_msl_mean",
        "weather_code": 61,
        "weather_description": "дождь",
    }


def test_get_weather_history_by_date_returns_error_when_requested_date_missing(monkeypatch):
    monkeypatch.setattr(
        service,
        "fetch_open_meteo_history_daily",
        lambda lat, lon, target_date: {
            "timezone": "Europe/Moscow",
            "daily": {
                "time": ["2026-05-01"],
                "temperature_2m_max": [18.4],
                "temperature_2m_min": [9.1],
                "temperature_2m_mean": [13.2],
                "precipitation_sum": [5.4],
                "rain_sum": [5.4],
                "snowfall_sum": [0.0],
                "wind_speed_10m_max": [8.6],
                "wind_direction_10m_dominant": [225],
                "relative_humidity_2m_mean": [71],
                "pressure_msl_mean": [1012.8],
                "weather_code": [61],
            },
        },
    )

    result = service.get_weather_history_by_date(55.75, 37.61, "Москва", date(2026, 5, 2))

    assert result == {
        "ok": False,
        "error_code": "history_invalid_payload",
        "error_message": "Не удалось разобрать архивные данные за эту дату. Попробуй выбрать другой день.",
        "city_label": "Москва",
        "history": None,
    }


def test_get_weather_history_by_date_returns_error_when_archive_is_unavailable(monkeypatch):
    monkeypatch.setattr(service, "fetch_open_meteo_history_daily", lambda lat, lon, target_date: None)

    result = service.get_weather_history_by_date(55.75, 37.61, "Москва", date(2026, 5, 2))

    assert result == {
        "ok": False,
        "error_code": "history_unavailable",
        "error_message": "Не удалось получить архивную погоду. Попробуй позже.",
        "city_label": "Москва",
        "history": None,
    }
