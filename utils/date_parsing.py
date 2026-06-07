from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

_MONTH_CASES = {
    1: {"nominative": "январь", "genitive": "января", "short": "янв"},
    2: {"nominative": "февраль", "genitive": "февраля", "short": "фев"},
    3: {"nominative": "март", "genitive": "марта", "short": "мар"},
    4: {"nominative": "апрель", "genitive": "апреля", "short": "апр"},
    5: {"nominative": "май", "genitive": "мая", "short": "май"},
    6: {"nominative": "июнь", "genitive": "июня", "short": "июн"},
    7: {"nominative": "июль", "genitive": "июля", "short": "июл"},
    8: {"nominative": "август", "genitive": "августа", "short": "авг"},
    9: {"nominative": "сентябрь", "genitive": "сентября", "short": "сен"},
    10: {"nominative": "октябрь", "genitive": "октября", "short": "окт"},
    11: {"nominative": "ноябрь", "genitive": "ноября", "short": "ноя"},
    12: {"nominative": "декабрь", "genitive": "декабря", "short": "дек"},
}

_MONTH_LOOKUP: dict[str, int] = {}
for month_number, forms in _MONTH_CASES.items():
    for form in forms.values():
        _MONTH_LOOKUP[form] = month_number


@dataclass(frozen=True)
class ParsedMonthReference:
    month: int | None
    year: int | None


@dataclass(frozen=True)
class ParsedShortYearDate:
    day: int
    month: int
    year_two_digits: int


def normalize_russian_text(value: object) -> str:
    text = str(value or "").strip().lower()
    text = text.translate({1105: 1077, 1025: 1045})
    return " ".join(text.split())


def month_name(month: int, *, grammatical_case: str = "nominative", capitalize: bool = False) -> str:
    forms = _MONTH_CASES.get(int(month), {})
    text = forms.get(grammatical_case, "")
    if capitalize and text:
        return text[0].upper() + text[1:]
    return text


def parse_month_value(value: object) -> int | None:
    if isinstance(value, int):
        return value if 1 <= value <= 12 else None
    if not isinstance(value, str):
        return None
    text = normalize_russian_text(value).replace(".", "")
    if not text:
        return None
    if text.isdigit():
        month_number = int(text)
        return month_number if 1 <= month_number <= 12 else None
    return _MONTH_LOOKUP.get(text)


def parse_calendar_date(raw_value: str) -> date | None:
    text = normalize_russian_text(raw_value)
    if not text:
        return None

    year_first_match = re.fullmatch(r"(?P<year>\d{4})[-/._\s](?P<month>\d{1,2})[-/._\s](?P<day>\d{1,2})", text)
    if year_first_match:
        return _build_date(
            int(year_first_match.group("year")),
            int(year_first_match.group("month")),
            int(year_first_match.group("day")),
        )

    day_first_match = re.fullmatch(r"(?P<day>\d{1,2})[-/._\s](?P<month>\d{1,2})[-/._\s](?P<year>\d{4})", text)
    if day_first_match:
        return _build_date(
            int(day_first_match.group("year")),
            int(day_first_match.group("month")),
            int(day_first_match.group("day")),
        )

    text_match = re.fullmatch(r"(?P<day>\d{1,2})\s+(?P<month>[а-я.]+)\s+(?P<year>\d{4})", text)
    if not text_match:
        return None
    month_number = parse_month_value(text_match.group("month"))
    if month_number is None:
        return None
    return _build_date(int(text_match.group("year")), month_number, int(text_match.group("day")))


def parse_day_first_short_year_date(raw_value: str) -> ParsedShortYearDate | None:
    text = normalize_russian_text(raw_value)
    if not text:
        return None

    short_year_match = re.fullmatch(r"(?P<day>\d{1,2})[-/._\s](?P<month>\d{1,2})[-/._\s](?P<year>\d{2})", text)
    if not short_year_match:
        return None

    day_value = int(short_year_match.group("day"))
    month_value = int(short_year_match.group("month"))
    year_two_digits = int(short_year_match.group("year"))
    if not 1 <= month_value <= 12:
        return None

    # Reject obviously invalid day/month pairs before offering clarification.
    if _build_date(2000 + year_two_digits, month_value, day_value) is None and _build_date(
        1900 + year_two_digits,
        month_value,
        day_value,
    ) is None:
        return None

    return ParsedShortYearDate(day=day_value, month=month_value, year_two_digits=year_two_digits)


def parse_month_reference(raw_value: str) -> ParsedMonthReference | None:
    text = normalize_russian_text(raw_value)
    if not text:
        return None

    if re.fullmatch(r"\d{4}", text):
        return ParsedMonthReference(month=None, year=int(text))

    year_first_match = re.fullmatch(r"(?P<year>\d{4})[-/.](?P<month>\d{1,2})", text)
    if year_first_match:
        month_number = parse_month_value(year_first_match.group("month"))
        if month_number is None:
            return None
        return ParsedMonthReference(month=month_number, year=int(year_first_match.group("year")))

    month_first_numeric_match = re.fullmatch(r"(?P<month>\d{1,2})[-/.](?P<year>\d{4})", text)
    if month_first_numeric_match:
        month_number = parse_month_value(month_first_numeric_match.group("month"))
        if month_number is None:
            return None
        return ParsedMonthReference(month=month_number, year=int(month_first_numeric_match.group("year")))

    month_text_match = re.fullmatch(r"(?P<month>[а-я.]+|\d{1,2})\s+(?P<year>\d{4})", text)
    if month_text_match:
        month_number = parse_month_value(month_text_match.group("month"))
        if month_number is None:
            return None
        return ParsedMonthReference(month=month_number, year=int(month_text_match.group("year")))

    month_number = parse_month_value(text)
    if month_number is None:
        return None
    return ParsedMonthReference(month=month_number, year=None)


def _build_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None
