from datetime import date

from utils.date_parsing import parse_calendar_date, parse_month_reference
from weather_history_service import (
    build_two_digit_year_clarification_dates,
    build_two_digit_year_future_warning,
    parse_history_date_input,
    resolve_history_date_input,
)
from weather_monthly_service import parse_monthly_history_year_input


def test_parse_calendar_date_accepts_year_first_separators():
    assert parse_calendar_date("2026-06-05") == date(2026, 6, 5)
    assert parse_calendar_date("2026/06/05") == date(2026, 6, 5)
    assert parse_calendar_date("2026.06.05") == date(2026, 6, 5)


def test_parse_calendar_date_accepts_day_first_separators():
    assert parse_calendar_date("05.06.2026") == date(2026, 6, 5)
    assert parse_calendar_date("05/06/2026") == date(2026, 6, 5)
    assert parse_calendar_date("05-06-2026") == date(2026, 6, 5)


def test_parse_calendar_date_accepts_textual_russian_months():
    assert parse_calendar_date("5 июня 2026") == date(2026, 6, 5)
    assert parse_calendar_date("5 июн 2026") == date(2026, 6, 5)
    assert parse_calendar_date("05 июн 2026") == date(2026, 6, 5)


def test_parse_calendar_date_accepts_day_first_numeric_formats_with_four_digit_year():
    assert parse_calendar_date("8/6/2025") == date(2025, 6, 8)
    assert parse_calendar_date("8.6.2025") == date(2025, 6, 8)
    assert parse_calendar_date("08/06/2025") == date(2025, 6, 8)


def test_parse_calendar_date_never_switches_to_american_month_first_order():
    assert parse_calendar_date("6/8/2025") == date(2025, 8, 6)


def test_parse_month_reference_accepts_text_and_numeric_forms():
    assert parse_month_reference("январь 2020").month == 1
    assert parse_month_reference("янв 2020").year == 2020
    assert parse_month_reference("01.2020").month == 1
    assert parse_month_reference("2020-01").year == 2020


def test_parse_history_date_input_rejects_invalid_date():
    parsed, error = parse_history_date_input("2026-02-31", today=date(2026, 6, 6))

    assert parsed is None
    assert "Не получилось распознать дату" in error


def test_parse_history_date_input_rejects_future_date():
    parsed, error = parse_history_date_input("2026-06-07", today=date(2026, 6, 6))

    assert parsed is None
    assert "Нужна дата из прошлого" in error


def test_parse_history_date_input_requests_year_clarification_for_two_digit_year():
    parsed, error = parse_history_date_input("8/06/25", today=date(2026, 6, 7))

    assert parsed is None
    assert error == "Нужно уточнить год."


def test_resolve_history_date_input_returns_two_day_first_year_options():
    resolution = resolve_history_date_input("8.06.25", today=date(2026, 6, 7))

    assert resolution.error_message is None
    assert resolution.parsed_date is None
    assert resolution.clarification_dates == [date(2025, 6, 8), date(1925, 6, 8)]


def test_build_two_digit_year_clarification_filters_future_option():
    assert build_two_digit_year_clarification_dates("8-06-50", today=date(2026, 6, 7)) == [date(1950, 6, 8)]


def test_parse_monthly_history_year_input_rejects_future_month():
    parsed, error = parse_monthly_history_year_input("2026-07", selected_month=6, today=date(2026, 6, 7))

    assert parsed is None
    assert "Будущий месяц" in error


class TestBuildTwoDigitYearFutureWarning:
    def test_returns_warning_when_20yy_is_future(self):
        warning = build_two_digit_year_future_warning("15.07.26", today=date(2026, 6, 7))
        assert warning is not None
        assert "15.07.2026" in warning
        assert "15.07.1926" in warning
        assert "пока будущая дата" in warning

    def test_returns_none_when_20yy_is_past(self):
        # 8/06/25 → 2025-06-08 is past (today is 2026-06-07)
        warning = build_two_digit_year_future_warning("8/06/25", today=date(2026, 6, 7))
        assert warning is None

    def test_returns_none_for_non_short_year_input(self):
        warning = build_two_digit_year_future_warning("2026-06-05", today=date(2026, 6, 7))
        assert warning is None

    def test_returns_none_for_empty_string(self):
        warning = build_two_digit_year_future_warning("", today=date(2026, 6, 7))
        assert warning is None

    def test_warning_message_references_archive(self):
        warning = build_two_digit_year_future_warning("15.07.26", today=date(2026, 6, 7))
        assert warning is not None
        assert "архивной справки" in warning or "архив" in warning.lower()


# ---------------------------------------------------------------------------
# Extended date separators: space and underscore
# ---------------------------------------------------------------------------

def test_parse_calendar_date_accepts_space_separator_day_first():
    assert parse_calendar_date("17 03 2026") == date(2026, 3, 17)


def test_parse_calendar_date_accepts_underscore_separator_day_first():
    assert parse_calendar_date("17_03_2026") == date(2026, 3, 17)


def test_parse_calendar_date_accepts_space_separator_year_first():
    assert parse_calendar_date("2026 03 17") == date(2026, 3, 17)


def test_parse_calendar_date_accepts_underscore_separator_year_first():
    assert parse_calendar_date("2026_03_17") == date(2026, 3, 17)


def test_parse_calendar_date_space_separator_single_digit_parts():
    assert parse_calendar_date("7 7 2025") == date(2025, 7, 7)


def test_parse_day_first_short_year_date_accepts_space_separator():
    from utils.date_parsing import parse_day_first_short_year_date

    result = parse_day_first_short_year_date("7 7 25")
    assert result is not None
    assert result.day == 7
    assert result.month == 7
    assert result.year_two_digits == 25


def test_parse_day_first_short_year_date_accepts_underscore_separator():
    from utils.date_parsing import parse_day_first_short_year_date

    result = parse_day_first_short_year_date("07_05_23")
    assert result is not None
    assert result.day == 7
    assert result.month == 5
    assert result.year_two_digits == 23
