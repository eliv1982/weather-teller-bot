from __future__ import annotations

from calendar import monthrange
from collections import Counter
from datetime import date
from typing import Any

from utils.date_parsing import ParsedMonthReference, month_name, parse_month_reference
from weather.open_meteo import fetch_open_meteo_history_daily_range, weather_code_to_description_ru
from weather.pressure import format_pressure_mmhg

CLIMATE_NORMALS_START_YEAR = 1991
CLIMATE_NORMALS_END_YEAR = 2020
MIN_CLIMATE_NORMALS_YEARS = 20
_PRECIPITATION_DAY_THRESHOLD_MM = 0.1


def parse_monthly_history_year_input(
    raw_value: str,
    *,
    selected_month: int | None,
    today: date | None = None,
) -> tuple[dict[str, int] | None, str | None]:
    """Parses year or month-year input for the monthly history mode."""
    text = str(raw_value or "").strip()
    if not text:
        return None, "Не увидела год. Введи год, например 2020."

    parsed = parse_month_reference(text)
    if not isinstance(parsed, ParsedMonthReference) or parsed.year is None:
        return None, "Не получилось распознать год. Введи год, например 2020."

    month_value = parsed.month or selected_month
    if month_value is None:
        return None, "Сначала выбери месяц кнопкой ниже."

    today_value = today or date.today()
    if parsed.year > today_value.year or (parsed.year == today_value.year and month_value > today_value.month):
        return None, "Нужен прошедший или текущий месяц. Будущий месяц пока недоступен."

    return {"year": parsed.year, "month": month_value}, None


def get_monthly_history_for_month(lat: float, lon: float, city_label: str, year: int, month: int) -> dict[str, Any]:
    """Builds a monthly archive summary for one month of a concrete year."""
    start_date = date(year, month, 1)
    end_date = date(year, month, monthrange(year, month)[1])
    root = fetch_open_meteo_history_daily_range(float(lat), float(lon), start_date=start_date, end_date=end_date)
    rows = _extract_daily_rows(root)
    month_rows = [row for row in rows if row["date"].year == year and row["date"].month == month]
    if not month_rows:
        return _monthly_error(
            city_label,
            error_code="monthly_unavailable",
            error_message="Не удалось получить архивные данные за этот месяц. Попробуй выбрать другой месяц или год.",
        )

    summary = _aggregate_single_month(
        month_rows,
        month=month,
        year=year,
        mode="monthly_year",
    )
    return {
        "ok": True,
        "error_code": None,
        "error_message": None,
        "city_label": city_label,
        "report": summary,
    }


def get_monthly_climate_normals(lat: float, lon: float, city_label: str, month: int) -> dict[str, Any]:
    """Builds a 1991-2020 monthly climate summary for the selected month."""
    expected_years_count = CLIMATE_NORMALS_END_YEAR - CLIMATE_NORMALS_START_YEAR + 1
    yearly_summaries: list[dict[str, Any]] = []
    successful_rows: list[dict[str, Any]] = []
    for year_value in range(CLIMATE_NORMALS_START_YEAR, CLIMATE_NORMALS_END_YEAR + 1):
        remaining_years_count = CLIMATE_NORMALS_END_YEAR - year_value + 1
        if len(yearly_summaries) + remaining_years_count < MIN_CLIMATE_NORMALS_YEARS:
            break
        start_date = date(year_value, month, 1)
        end_date = date(year_value, month, monthrange(year_value, month)[1])
        try:
            root = fetch_open_meteo_history_daily_range(float(lat), float(lon), start_date=start_date, end_date=end_date)
        except Exception:
            continue
        rows = _extract_daily_rows(root)
        month_rows = [row for row in rows if row["date"].year == year_value and row["date"].month == month]
        if not month_rows:
            continue
        summary = _aggregate_single_month(month_rows, month=month, year=year_value, mode="monthly_year")
        yearly_summaries.append(summary)
        successful_rows.extend(month_rows)

    used_years_count = len(yearly_summaries)
    if used_years_count < MIN_CLIMATE_NORMALS_YEARS:
        return _monthly_error(
            city_label,
            error_code="monthly_normals_unavailable",
            error_message=(
                "Не удалось получить достаточно архивных данных для этого месяца. "
                "Попробуй выбрать другой месяц или повторить позже."
            ),
        )

    summary = _aggregate_climate_normals(
        yearly_summaries,
        month=month,
        rows=successful_rows,
        used_years_count=used_years_count,
        expected_years_count=expected_years_count,
    )
    return {
        "ok": True,
        "error_code": None,
        "error_message": None,
        "city_label": city_label,
        "report": summary,
    }


def _monthly_error(city_label: str, *, error_code: str, error_message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "error_code": error_code,
        "error_message": error_message,
        "city_label": city_label,
        "report": None,
    }


def _extract_daily_rows(root: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(root, dict):
        return []
    daily = root.get("daily")
    if not isinstance(daily, dict):
        return []

    raw_times = daily.get("time")
    if not isinstance(raw_times, list):
        return []

    rows: list[dict[str, Any]] = []
    for index, raw_day in enumerate(raw_times):
        if not isinstance(raw_day, str):
            continue
        try:
            row_date = date.fromisoformat(raw_day)
        except ValueError:
            continue
        pressure_value = _to_float(_pick_daily_value(daily, "pressure_msl_mean", index=index))
        if pressure_value is None:
            pressure_value = _to_float(_pick_daily_value(daily, "surface_pressure_mean", index=index))
        weather_code = _to_int(_pick_daily_value(daily, "weather_code", index=index))
        rows.append(
            {
                "date": row_date,
                "date_iso": raw_day,
                "temperature_mean": _to_float(_pick_daily_value(daily, "temperature_2m_mean", index=index)),
                "temperature_max": _to_float(_pick_daily_value(daily, "temperature_2m_max", index=index)),
                "temperature_min": _to_float(_pick_daily_value(daily, "temperature_2m_min", index=index)),
                "precipitation_sum": _to_float(_pick_daily_value(daily, "precipitation_sum", index=index)),
                "rain_sum": _to_float(_pick_daily_value(daily, "rain_sum", index=index)),
                "snowfall_sum": _to_float(_pick_daily_value(daily, "snowfall_sum", index=index)),
                "wind_speed_max": _to_float(_pick_daily_value(daily, "wind_speed_10m_max", index=index)),
                "wind_direction_dominant": _to_float(
                    _pick_daily_value(daily, "wind_direction_10m_dominant", index=index)
                ),
                "relative_humidity_mean": _to_float(_pick_daily_value(daily, "relative_humidity_2m_mean", index=index)),
                "pressure_mean": pressure_value,
                "weather_code": weather_code,
                "weather_description": weather_code_to_description_ru(weather_code) if weather_code is not None else None,
            }
        )
    return rows


def _aggregate_single_month(rows: list[dict[str, Any]], *, month: int, year: int, mode: str) -> dict[str, Any]:
    temperature_mean_values = _numeric_values(rows, "temperature_mean")
    temperature_max_values = _numeric_values(rows, "temperature_max")
    temperature_min_values = _numeric_values(rows, "temperature_min")
    precipitation_values = _numeric_values(rows, "precipitation_sum")
    rain_values = _numeric_values(rows, "rain_sum")
    snowfall_values = _numeric_values(rows, "snowfall_sum")
    wind_values = _numeric_values(rows, "wind_speed_max")
    humidity_values = _numeric_values(rows, "relative_humidity_mean")
    pressure_values = _numeric_values(rows, "pressure_mean")
    pressure_mean = _normalize_zero(_mean(pressure_values))

    warmest_day = _max_row(rows, "temperature_max")
    coldest_day = _min_row(rows, "temperature_min")
    windiest_day = _max_row(rows, "wind_speed_max")
    precipitation_days = sum(1 for value in precipitation_values if value > _PRECIPITATION_DAY_THRESHOLD_MM)
    days_count = len(rows)
    precipitation_share = (precipitation_days / days_count) if days_count else None

    return {
        "mode": mode,
        "month": month,
        "month_label": month_name(month, capitalize=True),
        "month_label_lower": month_name(month),
        "month_label_genitive": month_name(month, grammatical_case="genitive"),
        "year": year,
        "sample_days": days_count,
        "temperature_month_mean": _normalize_zero(_mean(temperature_mean_values)),
        "temperature_daily_max_mean": _normalize_zero(_mean(temperature_max_values)),
        "temperature_daily_min_mean": _normalize_zero(_mean(temperature_min_values)),
        "temperature_absolute_max": _normalize_zero(_safe_max(temperature_max_values)),
        "temperature_absolute_min": _normalize_zero(_safe_min(temperature_min_values)),
        "warmest_day_label": _format_day_label(warmest_day),
        "coldest_day_label": _format_day_label(coldest_day),
        "precipitation_month_sum": _normalize_zero(sum(precipitation_values)),
        "rain_month_sum": _normalize_zero(sum(rain_values)),
        "snowfall_month_sum": _normalize_zero(sum(snowfall_values)),
        "precipitation_days": precipitation_days,
        "precipitation_days_share": _normalize_zero(precipitation_share),
        "wind_daily_max_mean": _normalize_zero(_mean(wind_values)),
        "wind_month_peak": _normalize_zero(_safe_max(wind_values)),
        "windiest_day_label": _format_day_label(windiest_day),
        "relative_humidity_mean": _normalize_zero(_mean(humidity_values)),
        "pressure_mean": pressure_mean,
        "pressure_mean_mmhg": format_pressure_mmhg(pressure_mean),
        "dominant_weather_description": _dominant_description(rows),
    }


def _aggregate_climate_normals(
    yearly_summaries: list[dict[str, Any]],
    *,
    month: int,
    rows: list[dict[str, Any]],
    used_years_count: int,
    expected_years_count: int,
) -> dict[str, Any]:
    pressure_mean = _normalize_zero(_mean_from_items(yearly_summaries, "pressure_mean"))
    return {
        "mode": "monthly_normals",
        "month": month,
        "month_label": month_name(month, capitalize=True),
        "month_label_lower": month_name(month),
        "month_label_genitive": month_name(month, grammatical_case="genitive"),
        "reference_period": f"{CLIMATE_NORMALS_START_YEAR}-{CLIMATE_NORMALS_END_YEAR}",
        "sample_days": sum(int(item.get("sample_days") or 0) for item in yearly_summaries),
        "sample_years": len(yearly_summaries),
        "used_years_count": used_years_count,
        "expected_years_count": expected_years_count,
        "temperature_month_mean": _normalize_zero(_mean_from_items(yearly_summaries, "temperature_month_mean")),
        "temperature_daily_max_mean": _normalize_zero(_mean_from_items(yearly_summaries, "temperature_daily_max_mean")),
        "temperature_daily_min_mean": _normalize_zero(_mean_from_items(yearly_summaries, "temperature_daily_min_mean")),
        "temperature_extreme_high_mean": _normalize_zero(_mean_from_items(yearly_summaries, "temperature_absolute_max")),
        "temperature_extreme_low_mean": _normalize_zero(_mean_from_items(yearly_summaries, "temperature_absolute_min")),
        "precipitation_month_sum": _normalize_zero(_mean_from_items(yearly_summaries, "precipitation_month_sum")),
        "rain_month_sum": _normalize_zero(_mean_from_items(yearly_summaries, "rain_month_sum")),
        "snowfall_month_sum": _normalize_zero(_mean_from_items(yearly_summaries, "snowfall_month_sum")),
        "precipitation_days_mean": _normalize_zero(_mean_from_items(yearly_summaries, "precipitation_days")),
        "precipitation_days_share_mean": _normalize_zero(_mean_from_items(yearly_summaries, "precipitation_days_share")),
        "wind_daily_max_mean": _normalize_zero(_mean_from_items(yearly_summaries, "wind_daily_max_mean")),
        "wind_month_peak_mean": _normalize_zero(_mean_from_items(yearly_summaries, "wind_month_peak")),
        "relative_humidity_mean": _normalize_zero(_mean_from_items(yearly_summaries, "relative_humidity_mean")),
        "pressure_mean": pressure_mean,
        "pressure_mean_mmhg": format_pressure_mmhg(pressure_mean),
        "dominant_weather_description": _dominant_description(rows),
    }


def _numeric_values(rows: list[dict[str, Any]], key: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        value = row.get(key)
        if isinstance(value, (int, float)):
            values.append(float(value))
    return values


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _mean_from_items(items: list[dict[str, Any]], key: str) -> float | None:
    values: list[float] = []
    for item in items:
        value = item.get(key)
        if isinstance(value, (int, float)):
            values.append(float(value))
    return _mean(values)


def _safe_max(values: list[float]) -> float | None:
    return max(values) if values else None


def _safe_min(values: list[float]) -> float | None:
    return min(values) if values else None


def _max_row(rows: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
    candidates = [row for row in rows if isinstance(row.get(key), (int, float))]
    if not candidates:
        return None
    return max(candidates, key=lambda row: float(row[key]))


def _min_row(rows: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
    candidates = [row for row in rows if isinstance(row.get(key), (int, float))]
    if not candidates:
        return None
    return min(candidates, key=lambda row: float(row[key]))


def _format_day_label(row: dict[str, Any] | None) -> str | None:
    if not isinstance(row, dict):
        return None
    row_date = row.get("date")
    if not isinstance(row_date, date):
        return None
    return row_date.strftime("%d.%m.%Y")


def _dominant_description(rows: list[dict[str, Any]]) -> str:
    descriptions = Counter(
        str(row.get("weather_description") or "").strip()
        for row in rows
        if str(row.get("weather_description") or "").strip()
    )
    if not descriptions:
        return "без описания"
    return descriptions.most_common(1)[0][0]


def _normalize_zero(value: float | int | None) -> float | int | None:
    if not isinstance(value, (int, float)):
        return None
    normalized = float(value)
    if round(normalized, 6) == 0:
        return 0.0
    return normalized


def _to_float(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _to_int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _pick_daily_value(daily: dict[str, Any], key: str, *, index: int) -> object | None:
    raw = daily.get(key)
    if not isinstance(raw, list) or index < 0 or index >= len(raw):
        return None
    return raw[index]
