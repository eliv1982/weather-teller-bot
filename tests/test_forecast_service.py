from datetime import date
from datetime import datetime, timezone

from forecast_service import get_forecast_day_by_offset, get_today_forecast_day, get_tomorrow_forecast_day, group_forecast_by_day


def test_get_tomorrow_forecast_day_returns_matching_day():
    grouped = group_forecast_by_day(
        [
            {"dt_txt": "2026-05-02 12:00:00", "_timezone_offset": 0},
            {"dt_txt": "2026-05-03 12:00:00", "_timezone_offset": 0},
        ]
    )

    result = get_tomorrow_forecast_day(grouped, today=date(2026, 5, 2))

    assert result == ("03.05", grouped["03.05"])


def test_get_tomorrow_forecast_day_returns_none_when_missing():
    grouped = group_forecast_by_day([{"dt_txt": "2026-05-04 12:00:00", "_timezone_offset": 0}])

    assert get_tomorrow_forecast_day(grouped, today=date(2026, 5, 2)) is None


def test_get_tomorrow_forecast_day_is_deterministic_with_injected_today():
    grouped = group_forecast_by_day([{"dt_txt": "2027-01-01 12:00:00", "_timezone_offset": 0}])

    result = get_tomorrow_forecast_day(grouped, today=date(2026, 12, 31))

    assert result == ("01.01", grouped["01.01"])


def test_get_today_forecast_day_returns_matching_day():
    grouped = group_forecast_by_day(
        [
            {"dt_txt": "2026-05-02 12:00:00", "_timezone_offset": 0},
            {"dt_txt": "2026-05-03 12:00:00", "_timezone_offset": 0},
        ]
    )

    result = get_today_forecast_day(grouped, today=date(2026, 5, 2))

    assert result == ("02.05", grouped["02.05"])


def test_group_forecast_by_day_uses_local_date_for_positive_timezone_boundary():
    grouped = group_forecast_by_day(
        [
            {"dt": 1778450400, "dt_txt": "2026-05-10 22:00:00", "_timezone_offset": 10800},
        ]
    )

    assert list(grouped.keys()) == ["11.05"]
    assert grouped["11.05"][0]["dt_txt"] == "2026-05-10 22:00:00"


def test_group_forecast_by_day_uses_local_date_for_negative_timezone_boundary():
    grouped = group_forecast_by_day(
        [
            {"dt": 1778374800, "dt_txt": "2026-05-10 01:00:00", "_timezone_offset": -14400},
        ]
    )

    assert list(grouped.keys()) == ["09.05"]
    assert grouped["09.05"][0]["dt_txt"] == "2026-05-10 01:00:00"


def test_get_forecast_day_by_offset_zero_selects_local_today():
    grouped = group_forecast_by_day(
        [
            {"dt_txt": "2026-05-03 21:00:00", "_timezone_offset": 10800},
            {"dt_txt": "2026-05-04 12:00:00", "_timezone_offset": 10800},
        ]
    )
    now_utc = datetime(2026, 5, 3, 22, 30, tzinfo=timezone.utc).replace(tzinfo=None)

    result = get_forecast_day_by_offset(grouped, day_offset=0, now_utc=now_utc)

    assert result == ("04.05", grouped["04.05"])


def test_get_forecast_day_by_offset_one_selects_local_tomorrow():
    grouped = group_forecast_by_day(
        [
            {"dt_txt": "2026-05-03 21:00:00", "_timezone_offset": 10800},
            {"dt_txt": "2026-05-04 12:00:00", "_timezone_offset": 10800},
            {"dt_txt": "2026-05-05 12:00:00", "_timezone_offset": 10800},
        ]
    )
    now_utc = datetime(2026, 5, 3, 22, 30, tzinfo=timezone.utc).replace(tzinfo=None)

    result = get_forecast_day_by_offset(grouped, day_offset=1, now_utc=now_utc)

    assert result == ("05.05", grouped["05.05"])
