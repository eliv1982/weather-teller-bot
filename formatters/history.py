"""
Formatters for daily weather history and monthly/climate-normal reports.
"""

from weather.descriptions import normalize_weather_description
from weather.pressure import format_pressure_mmhg

from formatters.common import wind_direction_ru


def _format_history_metric(value: object, *, digits: int = 1, suffix: str = "") -> str:
    if not isinstance(value, (int, float)):
        return "н/д"
    rounded = round(float(value), digits)
    if rounded == 0:
        rounded = 0.0
    formatted = f"{rounded:.{digits}f}"
    return f"{formatted}{suffix}" if suffix else formatted


def _format_history_humidity(value: object) -> str:
    if not isinstance(value, (int, float)):
        return "н/д"
    return f"{round(float(value))}%"


def _format_history_pressure_mmhg(value: object) -> str:
    return format_pressure_mmhg(value)


def _format_history_share(value: object) -> str:
    if not isinstance(value, (int, float)):
        return "н/д"
    percent = round(float(value) * 100)
    return f"{percent}%"


def _format_history_count(value: object) -> str:
    if not isinstance(value, (int, float)):
        return "н/д"
    rounded = round(float(value), 1)
    if rounded == 0:
        rounded = 0.0
    if float(rounded).is_integer():
        return str(int(rounded))
    return f"{rounded:.1f}"


def _history_precipitation_type(history: dict) -> str:
    rain_sum = history.get("rain_sum")
    snowfall_sum = history.get("snowfall_sum")
    precipitation_sum = history.get("precipitation_sum")

    has_rain = isinstance(rain_sum, (int, float)) and float(rain_sum) > 0
    has_snow = isinstance(snowfall_sum, (int, float)) and float(snowfall_sum) > 0
    has_precipitation = isinstance(precipitation_sum, (int, float)) and float(precipitation_sum) > 0

    if has_rain and has_snow:
        return "дождь и снег"
    if has_snow:
        return "снег"
    if has_rain:
        return "дождь"
    if has_precipitation:
        return "осадки"
    return "без существенных осадков"


def _history_temperature_tone(history: dict) -> str | None:
    mean_temp = history.get("temperature_mean")
    min_temp = history.get("temperature_min")
    max_temp = history.get("temperature_max")

    reference = None
    if isinstance(mean_temp, (int, float)):
        reference = float(mean_temp)
    elif isinstance(min_temp, (int, float)) and isinstance(max_temp, (int, float)):
        reference = (float(min_temp) + float(max_temp)) / 2
    elif isinstance(max_temp, (int, float)):
        reference = float(max_temp)
    elif isinstance(min_temp, (int, float)):
        reference = float(min_temp)

    if reference is None:
        return None
    if reference <= 0:
        return "холодно"
    if reference < 10:
        return "прохладно"
    if reference < 22:
        return "умеренно тепло"
    return "тепло"


def _history_temperature_phrase(temperature_tone: str | None) -> str | None:
    mapping = {
        "холодно": "холодным",
        "прохладно": "прохладным",
        "умеренно тепло": "умеренно теплым",
        "тепло": "теплым",
    }
    return mapping.get(temperature_tone or "")


def _history_wind_phrase(wind_speed: object) -> str | None:
    if not isinstance(wind_speed, (int, float)):
        return None
    value = float(wind_speed)
    if value < 3:
        return "ветер был слабым"
    if value <= 5:
        return "ветер был умеренным"
    if value < 8:
        return f"ветер был заметным, до {value:.1f} м/с"
    return f"ветер усиливался до {value:.1f} м/с"


def build_history_brief_summary(history: dict) -> str:
    weather_description = normalize_weather_description(history.get("weather_description") or "без описания")
    precipitation_type = _history_precipitation_type(history)
    wind_speed = history.get("wind_speed_max")
    humidity = history.get("relative_humidity_mean")
    pressure_text = _format_history_pressure_mmhg(history.get("pressure_mean"))
    temperature_phrase = _history_temperature_phrase(_history_temperature_tone(history))

    if temperature_phrase and weather_description != "без описания":
        sentence_1 = (
            f"По архивным данным день выглядел {temperature_phrase}, "
            f"а основные условия были такими: {weather_description}."
        )
    elif temperature_phrase:
        sentence_1 = f"По архивным данным день выглядел {temperature_phrase}."
    elif weather_description != "без описания":
        sentence_1 = f"По архивным данным основные условия в течение дня были такими: {weather_description}."
    else:
        sentence_1 = "По архивным данным это примерная картина дня."

    if precipitation_type == "без существенных осадков":
        sentence_2 = "Существенных осадков по архивным данным не видно"
    elif precipitation_type == "дождь":
        sentence_2 = "По архивным данным в течение дня отмечался дождь"
    elif precipitation_type == "снег":
        sentence_2 = "По архивным данным в течение дня отмечался снег"
    else:
        sentence_2 = f"По архивным данным в течение дня отмечались {precipitation_type}"

    wind_phrase = _history_wind_phrase(wind_speed)
    if wind_phrase:
        sentence_2 = f"{sentence_2}, {wind_phrase}."
    else:
        sentence_2 = f"{sentence_2}."

    extra_parts: list[str] = []
    if isinstance(humidity, (int, float)):
        humidity_value = round(float(humidity))
        if humidity_value >= 85:
            extra_parts.append(f"влажность была высокой: около {humidity_value}%")
        else:
            extra_parts.append(f"влажность держалась около {humidity_value}%")
    if pressure_text != "н/д":
        extra_parts.append(f"давление было около {pressure_text}")

    sentence_3 = ""
    if extra_parts:
        sentence_3 = " и ".join(extra_parts)
        sentence_3 = sentence_3[0].upper() + sentence_3[1:] + "."

    return " ".join(part for part in (sentence_1, sentence_2, sentence_3) if part)


def format_history_weather_response(city_label: str, history: dict, *, short_summary: str | None = None) -> str:
    """Собирает человекочитаемую историческую справку по дневным архивным данным."""
    date_label = str(history.get("date_label") or history.get("date") or "н/д")
    weather_description = normalize_weather_description(history.get("weather_description") or "без описания")
    precipitation_type = _history_precipitation_type(history)
    wind_speed = history.get("wind_speed_max")
    wind_direction = history.get("wind_direction_dominant")
    wind_direction_text = wind_direction_ru(float(wind_direction)) if isinstance(wind_direction, (int, float)) else "н/д"
    short_summary_text = str(short_summary or "").strip() or build_history_brief_summary(history)

    lines = [
        f"🕰 История погоды: {city_label}",
        f"📅 {date_label}",
        "",
        "🌡 Температура",
        f"• Максимум: {_format_history_metric(history.get('temperature_max'), suffix=' °C')}",
        f"• Минимум: {_format_history_metric(history.get('temperature_min'), suffix=' °C')}",
        f"• Средняя: {_format_history_metric(history.get('temperature_mean'), suffix=' °C')}",
        "",
        "🌧 Осадки",
        f"• По архивным данным: {precipitation_type}",
        f"• Сумма осадков: {_format_history_metric(history.get('precipitation_sum'), suffix=' мм')}",
        f"• Дождь: {_format_history_metric(history.get('rain_sum'), suffix=' мм')}",
        f"• Снег: {_format_history_metric(history.get('snowfall_sum'), suffix=' см')}",
        "",
        "💨 Ветер",
        f"• Максимальная скорость: {_format_history_metric(wind_speed, suffix=' м/с')}",
        f"• Преобладающее направление: {wind_direction_text}",
        "",
        "📊 Дополнительно",
        f"• Влажность: {_format_history_humidity(history.get('relative_humidity_mean'))}",
        f"• Давление: {_format_history_pressure_mmhg(history.get('pressure_mean'))}",
        f"• Условия по архивным данным: {weather_description}",
        "",
        "✨ Коротко",
        short_summary_text,
    ]
    return "\n".join(lines)


def _format_monthly_temperature_peak(value: object, date_label: object) -> str:
    metric_text = _format_history_metric(value, suffix=" °C")
    if not isinstance(date_label, str) or not date_label.strip():
        return metric_text
    return f"{metric_text} ({date_label})"


def _format_monthly_wind_peak(value: object, date_label: object) -> str:
    metric_text = _format_history_metric(value, suffix=" м/с")
    if not isinstance(date_label, str) or not date_label.strip():
        return metric_text
    return f"{metric_text} ({date_label})"


def build_monthly_climate_brief_summary(report: dict) -> str:
    mode = str(report.get("mode") or "")
    month_label = str(report.get("month_label_lower") or "месяца")
    weather_description = normalize_weather_description(report.get("dominant_weather_description") or "без описания")
    temperature_mean = _format_history_metric(report.get("temperature_month_mean"), suffix=" °C")
    precipitation_share = _format_history_share(
        report.get("precipitation_days_share_mean")
        if mode == "monthly_normals"
        else report.get("precipitation_days_share")
    )
    wind_mean = _format_history_metric(report.get("wind_daily_max_mean"), suffix=" м/с")
    pressure_text = _format_history_pressure_mmhg(report.get("pressure_mean"))
    used_years_count = report.get("used_years_count")
    expected_years_count = report.get("expected_years_count")
    coverage_text = ""
    if isinstance(used_years_count, int) and isinstance(expected_years_count, int):
        coverage_text = f" Использовано {used_years_count} из {expected_years_count} лет."

    if mode == "monthly_normals":
        sentence_1 = (
            f"По архивным данным за 1991-2020 для {month_label} обычно характерна средняя температура "
            f"около {temperature_mean}."
        )
        sentence_2 = (
            f"Доля дней с осадками по архивным данным составляет около {precipitation_share}, "
            f"а средняя максимальная скорость ветра за день держится около {wind_mean}."
        )
        sentence_3 = f"Это архивная справка по данным за 1991-2020.{coverage_text}"
        if weather_description != "без описания":
            sentence_1 = (
                f"По архивным данным за 1991-2020 для {month_label} обычно характерны условия "
                f"вроде «{weather_description}», а средняя температура месяца около {temperature_mean}."
            )
        if pressure_text != "н/д":
            sentence_3 = (
                f"Это архивная справка по данным за 1991-2020.{coverage_text} "
                f"Давление в среднем около {pressure_text}."
            )
        return " ".join((sentence_1, sentence_2, sentence_3))

    year = report.get("year")
    sentence_1 = f"По архивным данным {month_label} {year} года в среднем дал около {temperature_mean}."
    if weather_description != "без описания":
        sentence_1 = (
            f"По архивным данным {month_label} {year} года в среднем выглядел как месяц с условиями "
            f"вроде «{weather_description}» и средней температурой около {temperature_mean}."
        )
    sentence_2 = (
        f"Доля дней с осадками по архивным данным составила {precipitation_share}, "
        f"а средняя максимальная скорость ветра за день была около {wind_mean}."
    )
    if pressure_text == "н/д":
        return " ".join((sentence_1, sentence_2))
    sentence_3 = f"Среднее давление за месяц было около {pressure_text}."
    return " ".join((sentence_1, sentence_2, sentence_3))


def format_history_monthly_climate_response(
    city_label: str,
    report: dict,
    *,
    short_summary: str | None = None,
) -> str:
    """Formats monthly archive or climate-normal summaries."""
    mode = str(report.get("mode") or "")
    short_summary_text = str(short_summary or "").strip() or build_monthly_climate_brief_summary(report)
    if mode == "monthly_normals":
        used_years_count = report.get("used_years_count")
        expected_years_count = report.get("expected_years_count")
        lines = [
            "📆 Среднемесячные показатели",
            f"📍 {city_label}",
            f"🗓 {report.get('month_label')}, период {report.get('reference_period') or '1991-2020'}",
        ]
        if isinstance(used_years_count, int) and isinstance(expected_years_count, int):
            lines.append(
                f"ℹ️ Расчет по архивным данным за 1991-2020, использовано {used_years_count} из {expected_years_count} лет."
            )
        lines.extend(
            [
                "",
                "🌡 Температура",
                f"• Средняя температура месяца: {_format_history_metric(report.get('temperature_month_mean'), suffix=' °C')}",
                f"• Средний дневной максимум: {_format_history_metric(report.get('temperature_daily_max_mean'), suffix=' °C')}",
                f"• Средний дневной минимум: {_format_history_metric(report.get('temperature_daily_min_mean'), suffix=' °C')}",
                f"• Средний максимум самого теплого дня: {_format_history_metric(report.get('temperature_extreme_high_mean'), suffix=' °C')}",
                f"• Средний минимум самого холодного дня: {_format_history_metric(report.get('temperature_extreme_low_mean'), suffix=' °C')}",
                "",
                "🌧 Осадки",
                f"• Средняя сумма осадков за месяц: {_format_history_metric(report.get('precipitation_month_sum'), suffix=' мм')}",
                f"• Среднее число дней с заметными осадками: {_format_history_count(report.get('precipitation_days_mean'))}",
                f"• Доля дней с осадками по архивным данным: {_format_history_share(report.get('precipitation_days_share_mean'))}",
                f"• Средний дождь за месяц: {_format_history_metric(report.get('rain_month_sum'), suffix=' мм')}",
                f"• Средний снег за месяц: {_format_history_metric(report.get('snowfall_month_sum'), suffix=' см')}",
                "",
                "💨 Ветер",
                f"• Средняя максимальная скорость за день: {_format_history_metric(report.get('wind_daily_max_mean'), suffix=' м/с')}",
                f"• Средний пик ветра в месяце: {_format_history_metric(report.get('wind_month_peak_mean'), suffix=' м/с')}",
                "",
                "📊 Дополнительно",
                f"• Средняя влажность: {_format_history_humidity(report.get('relative_humidity_mean'))}",
                f"• Среднее давление: {_format_history_pressure_mmhg(report.get('pressure_mean'))}",
                f"• Основные условия по архивным данным: {normalize_weather_description(report.get('dominant_weather_description') or 'без описания')}",
                "",
                "✨ Коротко",
                short_summary_text,
            ]
        )
        return "\n".join(lines)

    lines = [
        "📊 Средние климатические показатели",
        f"📍 {city_label}",
        f"🗓 {report.get('month_label')} {report.get('year')}",
        "",
        "🌡 Температура",
        f"• Средняя за месяц: {_format_history_metric(report.get('temperature_month_mean'), suffix=' °C')}",
        f"• Средний максимум: {_format_history_metric(report.get('temperature_daily_max_mean'), suffix=' °C')}",
        f"• Средний минимум: {_format_history_metric(report.get('temperature_daily_min_mean'), suffix=' °C')}",
        f"• Самый теплый день: {_format_monthly_temperature_peak(report.get('temperature_absolute_max'), report.get('warmest_day_label'))}",
        f"• Самый холодный день: {_format_monthly_temperature_peak(report.get('temperature_absolute_min'), report.get('coldest_day_label'))}",
        "",
        "🌧 Осадки",
        f"• Сумма за месяц: {_format_history_metric(report.get('precipitation_month_sum'), suffix=' мм')}",
        f"• Дней с заметными осадками: {_format_history_count(report.get('precipitation_days'))}",
        f"• Доля дней с осадками: {_format_history_share(report.get('precipitation_days_share'))}",
        f"• Дождь: {_format_history_metric(report.get('rain_month_sum'), suffix=' мм')}",
        f"• Снег: {_format_history_metric(report.get('snowfall_month_sum'), suffix=' см')}",
        "",
        "💨 Ветер",
        f"• Средняя максимальная скорость за день: {_format_history_metric(report.get('wind_daily_max_mean'), suffix=' м/с')}",
        f"• Самый ветреный день: {_format_monthly_wind_peak(report.get('wind_month_peak'), report.get('windiest_day_label'))}",
        "",
        "📊 Дополнительно",
        f"• Средняя влажность: {_format_history_humidity(report.get('relative_humidity_mean'))}",
        f"• Среднее давление: {_format_history_pressure_mmhg(report.get('pressure_mean'))}",
        f"• Основные условия по архивным данным: {normalize_weather_description(report.get('dominant_weather_description') or 'без описания')}",
        "",
        "✨ Коротко",
        short_summary_text,
    ]
    return "\n".join(lines)
