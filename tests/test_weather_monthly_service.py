from datetime import date

from weather_monthly_service import get_monthly_climate_normals, get_monthly_history_for_month


def _monthly_daily_payload(year: int, month: int = 1) -> dict:
    return {
        "daily": {
            "time": [f"{year}-{month:02d}-01", f"{year}-{month:02d}-02"],
            "temperature_2m_mean": [0.0, 2.0],
            "temperature_2m_max": [1.0, 3.0],
            "temperature_2m_min": [-1.0, 1.0],
            "precipitation_sum": [0.0, 2.0],
            "rain_sum": [0.0, 1.5],
            "snowfall_sum": [0.0, 0.5],
            "wind_speed_10m_max": [3.0, 5.0],
            "wind_direction_10m_dominant": [90, 180],
            "relative_humidity_2m_mean": [70, 80],
            "pressure_msl_mean": [1010.0, 1014.0],
            "weather_code": [0, 61],
        }
    }


def test_get_monthly_history_for_month_aggregates_daily_rows(monkeypatch):
    monkeypatch.setattr(
        "weather_monthly_service.fetch_open_meteo_history_daily_range",
        lambda lat, lon, start_date, end_date: {
            "daily": {
                "time": ["2020-01-01", "2020-01-02", "2020-01-03"],
                "temperature_2m_mean": [1.0, 3.0, 5.0],
                "temperature_2m_max": [2.0, 4.0, 6.0],
                "temperature_2m_min": [0.0, 2.0, 4.0],
                "precipitation_sum": [0.0, 1.2, 0.3],
                "rain_sum": [0.0, 1.2, 0.0],
                "snowfall_sum": [0.0, 0.0, 0.5],
                "wind_speed_10m_max": [4.0, 6.0, 8.0],
                "wind_direction_10m_dominant": [90, 120, 180],
                "relative_humidity_2m_mean": [70, 80, 90],
                "pressure_msl_mean": [1010.0, 1012.0, 1014.0],
                "weather_code": [0, 61, 71],
            }
        },
    )

    result = get_monthly_history_for_month(55.75, 37.61, "Москва", 2020, 1)

    assert result["ok"] is True
    report = result["report"]
    assert report["temperature_month_mean"] == 3.0
    assert report["precipitation_month_sum"] == 1.5
    assert report["precipitation_days"] == 2
    assert round(report["precipitation_days_share"], 3) == 0.667
    assert report["pressure_mean_mmhg"] == "759 мм рт. ст."
    assert report["wind_month_peak"] == 8.0


def test_get_monthly_history_for_month_normalizes_negative_zero(monkeypatch):
    monkeypatch.setattr(
        "weather_monthly_service.fetch_open_meteo_history_daily_range",
        lambda lat, lon, start_date, end_date: {
            "daily": {
                "time": ["2020-02-01"],
                "temperature_2m_mean": [-0.0],
                "temperature_2m_max": [-0.0],
                "temperature_2m_min": [-0.0],
                "precipitation_sum": [0.0],
                "rain_sum": [0.0],
                "snowfall_sum": [0.0],
                "wind_speed_10m_max": [0.0],
                "wind_direction_10m_dominant": [0],
                "relative_humidity_2m_mean": [50],
                "pressure_msl_mean": [1012.0],
                "weather_code": [0],
            }
        },
    )

    result = get_monthly_history_for_month(55.75, 37.61, "Москва", 2020, 2)
    report = result["report"]

    assert report["temperature_month_mean"] == 0.0
    assert report["temperature_absolute_max"] == 0.0
    assert report["temperature_absolute_min"] == 0.0


def test_get_monthly_climate_normals_requests_one_year_at_a_time_and_tolerates_partial_failures(monkeypatch):
    calls = []

    def fake_fetch(lat, lon, start_date, end_date):
        calls.append((start_date, end_date))
        if start_date.year in {1993, 1997}:
            raise RuntimeError("temporary archive error")
        if 1991 <= start_date.year <= 2012:
            return _monthly_daily_payload(start_date.year, start_date.month)
        return {"daily": {"time": []}}

    monkeypatch.setattr("weather_monthly_service.fetch_open_meteo_history_daily_range", fake_fetch)

    result = get_monthly_climate_normals(55.75, 37.61, "Москва", 1)

    assert result["ok"] is True
    report = result["report"]
    assert calls[0] == (date(1991, 1, 1), date(1991, 1, 31))
    assert all(start.year == end.year for start, end in calls)
    assert all(start.month == 1 and end.month == 1 for start, end in calls)
    assert (date(1991, 1, 1), date(2020, 1, 31)) not in calls
    assert report["sample_years"] == 20
    assert report["used_years_count"] == 20
    assert report["expected_years_count"] == 30
    assert report["temperature_month_mean"] == 1.0
    assert report["precipitation_month_sum"] == 2.0
    assert report["precipitation_days_mean"] == 1.0
    assert round(report["precipitation_days_share_mean"], 2) == 0.5
    assert report["pressure_mean_mmhg"] == "759 мм рт. ст."


def test_get_monthly_climate_normals_returns_controlled_error_when_too_few_years_are_available(monkeypatch):
    def fake_fetch(lat, lon, start_date, end_date):
        if 1991 <= start_date.year <= 2009:
            return _monthly_daily_payload(start_date.year, start_date.month)
        raise RuntimeError("archive timeout")

    monkeypatch.setattr("weather_monthly_service.fetch_open_meteo_history_daily_range", fake_fetch)

    result = get_monthly_climate_normals(55.75, 37.61, "Москва", 1)

    assert result["ok"] is False
    assert result["error_code"] == "monthly_normals_unavailable"
    assert "Не удалось получить достаточно архивных данных" in result["error_message"]
