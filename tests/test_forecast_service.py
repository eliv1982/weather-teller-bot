from datetime import date

from forecast_service import get_tomorrow_forecast_day


def test_get_tomorrow_forecast_day_returns_matching_day():
    grouped = {
        "02.05": [{"dt_txt": "2026-05-02 12:00:00"}],
        "03.05": [{"dt_txt": "2026-05-03 12:00:00"}],
    }

    result = get_tomorrow_forecast_day(grouped, today=date(2026, 5, 2))

    assert result == ("03.05", grouped["03.05"])


def test_get_tomorrow_forecast_day_returns_none_when_missing():
    grouped = {"04.05": [{"dt_txt": "2026-05-04 12:00:00"}]}

    assert get_tomorrow_forecast_day(grouped, today=date(2026, 5, 2)) is None


def test_get_tomorrow_forecast_day_is_deterministic_with_injected_today():
    grouped = {
        "01.01": [{"dt_txt": "2027-01-01 12:00:00"}],
    }

    result = get_tomorrow_forecast_day(grouped, today=date(2026, 12, 31))

    assert result == ("01.01", grouped["01.01"])
