from datetime import datetime

from weather_app import analyze_air_pollution
from weather.descriptions import normalize_weather_description
from weather.pressure import format_pressure_mmhg, get_pressure_note_hpa


def wind_direction_ru(deg: float) -> str:
    """Переводит градусы направления ветра в русское направление."""
    directions = [
        "северный",
        "северо-восточный",
        "восточный",
        "юго-восточный",
        "южный",
        "юго-западный",
        "западный",
        "северо-западный",
    ]
    index = round(deg / 45) % 8
    return directions[index]


def help_text() -> str:
    """Возвращает текст справки по командам бота."""
    return (
        "ℹ️ Доступные команды:\n"
        "/start — главное меню\n"
        "/weather — прогноз погоды\n"
        "/locations — локации\n"
        "/subscriptions — подписки\n"
        "/help — помощь\n\n"
        "Дополнительно работают быстрые команды: /current, /tomorrow, /forecast, /details, /compare, /geo."
    )


def format_saved_locations(user_data: dict) -> str:
    """Форматирует список сохранённых локаций пользователя."""
    saved_locations = user_data.get("saved_locations", [])
    if not isinstance(saved_locations, list) or not saved_locations:
        return "Сохранённых локаций пока нет."

    lines = ["Мои локации:"]
    for item in saved_locations:
        if not isinstance(item, dict):
            continue
        title = (item.get("title") or "Без названия").strip()
        label = (item.get("label") or "Без подписи").strip()
        lines.append(f"{title} — {label}")

    if len(lines) == 1:
        return "Сохранённых локаций пока нет."
    return "\n".join(lines)


def format_alerts_status(user_data: dict) -> str:
    """Форматирует статус уведомлений пользователя."""
    city = user_data.get("city") or "Не выбрана"
    notifications = user_data.get("notifications", {}) if isinstance(user_data.get("notifications"), dict) else {}
    enabled = notifications.get("enabled", False)
    interval_h = notifications.get("interval_h", 2)
    if not isinstance(interval_h, int) or interval_h <= 0:
        interval_h = 2

    return (
        "🔔 Статус уведомлений:\n"
        f"• 📍 Локация: {city}\n"
        f"• 🔔 Уведомления: {'включены' if enabled else 'выключены'}\n"
        f"• 🕒 Интервал проверки: {interval_h} ч"
    )


def format_alert_subscriptions(user_data: dict) -> str:
    """Форматирует список подписок уведомлений пользователя."""
    subscriptions = user_data.get("alert_subscriptions", [])
    if not isinstance(subscriptions, list) or not subscriptions:
        return "Подписок на уведомления пока нет."

    lines = ["Подписки на уведомления:"]
    for item in subscriptions:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        label = str(item.get("label") or "Без подписи").strip()
        if not title or title == label:
            header = f"• {label}"
        else:
            header = f"• {title} — {label}"
        interval_h = item.get("interval_h", 2)
        if not isinstance(interval_h, int) or interval_h <= 0:
            interval_h = 2
        status = "включены" if bool(item.get("enabled", True)) else "выключены"
        lines.append(header)
        lines.append(f"  Статус: {status}")
        lines.append(f"  Интервал: {interval_h} ч")
        lines.append("")

    if len(lines) == 1:
        return "Подписок на уведомления пока нет."

    if lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def _wind_text_from_values(wind_speed: float | None, wind_deg: float | None) -> str:
    """Собирает строку с ветром для ответов."""
    if wind_speed is None:
        return "н/д"
    if wind_deg is None:
        return f"{wind_speed} м/с"
    return f"{wind_speed} м/с, {wind_direction_ru(wind_deg)}"


def _format_temp_range(values: list[float]) -> str:
    """Форматирует диапазон значений температуры."""
    if not values:
        return "н/д"
    min_value = min(values)
    max_value = max(values)
    if round(min_value, 1) == round(max_value, 1):
        return f"{min_value:.1f} °C"
    return f"{min_value:.1f}...{max_value:.1f} °C"


def _format_temp_band(min_temp: object, max_temp: object) -> str:
    """Formats min/max temperatures for deterministic day summaries."""
    if not isinstance(min_temp, (int, float)) and not isinstance(max_temp, (int, float)):
        return "н/д"
    if not isinstance(min_temp, (int, float)):
        return f"{float(max_temp):.0f} °C"
    if not isinstance(max_temp, (int, float)):
        return f"{float(min_temp):.0f} °C"
    min_value = round(float(min_temp))
    max_value = round(float(max_temp))
    if min_value == max_value:
        return f"{min_value} °C"
    return f"{min_value}-{max_value} °C"


def _average_numeric(values: list[object]) -> float | None:
    numeric_values = [float(value) for value in values if isinstance(value, (int, float))]
    if not numeric_values:
        return None
    return sum(numeric_values) / len(numeric_values)


def _forecast_main_description(day_items: list[dict]) -> str:
    descriptions: dict[str, int] = {}
    for item in day_items:
        weather_list = item.get("weather") if isinstance(item, dict) else None
        weather_item = weather_list[0] if isinstance(weather_list, list) and weather_list and isinstance(weather_list[0], dict) else {}
        description = normalize_weather_description(weather_item.get("description") or "без описания")
        descriptions[description] = descriptions.get(description, 0) + 1
    if not descriptions:
        return "без описания"
    return max(descriptions, key=descriptions.get)


def _format_direct_day_forecast_response(title: str, city_label: str, day: str, day_items: list[dict]) -> str:
    """Собирает отдельный экран прогноза дня из 3-часовых слотов."""
    if not isinstance(day_items, list):
        day_items = []

    main_blocks = [item.get("main", {}) for item in day_items if isinstance(item, dict)]
    wind_blocks = [item.get("wind", {}) for item in day_items if isinstance(item, dict)]
    temps = [float(main.get("temp")) for main in main_blocks if isinstance(main.get("temp"), (int, float))]
    feels_like_values = [
        float(main.get("feels_like"))
        for main in main_blocks
        if isinstance(main.get("feels_like"), (int, float))
    ]
    avg_humidity = _average_numeric([main.get("humidity") for main in main_blocks])
    avg_pressure = _average_numeric([main.get("pressure") for main in main_blocks])
    pressure_mmhg = round(avg_pressure * 0.75006) if avg_pressure is not None else None

    wind_speeds = [float(wind.get("speed")) for wind in wind_blocks if isinstance(wind.get("speed"), (int, float))]
    max_wind_speed = max(wind_speeds) if wind_speeds else None
    wind_deg = next((wind.get("deg") for wind in wind_blocks if isinstance(wind.get("deg"), (int, float))), None)

    lines = [
        title,
        f"📍 Населённый пункт: {city_label}",
        f"📅 Дата: {day}",
        f"🌡 Температура: {_format_temp_range(temps)}",
        f"🤔 Ощущается как: {_format_temp_range(feels_like_values)}",
        f"☁️ Описание: {_forecast_main_description(day_items)}",
        f"💧 Влажность: {round(avg_humidity) if avg_humidity is not None else 'н/д'}%",
        f"🩺 Давление: {pressure_mmhg if pressure_mmhg is not None else 'н/д'} мм рт. ст.",
        f"🌬 Ветер: {_wind_text_from_values(max_wind_speed, wind_deg)}",
    ]
    return "\n".join(lines)


def format_tomorrow_forecast_response(city_label: str, day: str, day_items: list[dict]) -> str:
    """Собирает отдельный экран прогноза на завтра из 3-часовых слотов."""
    return _format_direct_day_forecast_response("🌤 Прогноз на завтра", city_label, day, day_items)


def format_today_forecast_response(
    city_label: str,
    day: str,
    day_items: list[dict],
    *,
    is_remaining_day: bool = False,
) -> str:
    """Собирает отдельный экран прогноза на сегодня по доступным слотам."""
    title = "☀️ Прогноз на оставшуюся часть дня" if is_remaining_day else "☀️ Прогноз на сегодня"
    return _format_direct_day_forecast_response(title, city_label, day, day_items)


def format_weather_response(city_label: str, weather: dict) -> str:
    """Собирает текст ответа с текущей погодой."""
    main_data = weather.get("main", {})
    weather_data = weather.get("weather", [{}])
    wind_data = weather.get("wind", {})

    temp = main_data.get("temp")
    feels_like = main_data.get("feels_like")
    description = normalize_weather_description(weather_data[0].get("description", "без описания"))
    humidity = main_data.get("humidity")
    pressure = main_data.get("pressure")
    wind_speed = wind_data.get("speed")
    wind_deg = wind_data.get("deg")

    pressure_mmhg = round(pressure * 0.75006) if pressure is not None else None
    pressure_note = get_pressure_note_hpa(pressure)
    wind_text = _wind_text_from_values(wind_speed, wind_deg)

    lines = [
        f"📍 Населённый пункт: {city_label}",
        f"🌡 Температура: {temp if temp is not None else 'н/д'} °C",
        f"🤔 Ощущается как: {feels_like if feels_like is not None else 'н/д'} °C",
        f"☁️ Описание: {description}",
        f"💧 Влажность: {humidity if humidity is not None else 'н/д'}%",
        f"🩺 Давление: {pressure_mmhg if pressure_mmhg is not None else 'н/д'} мм рт. ст.",
    ]
    if pressure_note:
        lines.append(pressure_note)
    lines.append(f"🌬 Ветер: {wind_text}")
    return "\n".join(lines)


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


def _format_hh_mm_from_unix(unix_ts: int | None) -> str:
    """Преобразует unix timestamp в формат ЧЧ:ММ."""
    if unix_ts is None:
        return "н/д"
    return datetime.fromtimestamp(unix_ts).strftime("%H:%M")


def _format_visibility(visibility_meters: int | float | None) -> str:
    """Возвращает видимость в метрах или километрах в удобном формате."""
    if visibility_meters is None:
        return "н/д"

    try:
        value = float(visibility_meters)
    except (TypeError, ValueError):
        return str(visibility_meters)

    if value < 1000:
        return f"{int(value)} м"
    return f"{value / 1000:.1f} км"


def _format_air_component_value(value: object) -> str:
    """Форматирует значение компонента воздуха до 1 знака, если это число."""
    if isinstance(value, (int, float)):
        return f"{value:.1f}"
    return str(value)


def format_details_response(city_label: str, weather: dict, air_components: dict | None) -> str:
    """Собирает текст ответа с расширенными данными о погоде и воздухе."""
    main_data = weather.get("main", {})
    weather_data = weather.get("weather", [{}])
    wind_data = weather.get("wind", {})
    clouds_data = weather.get("clouds", {})
    sys_data = weather.get("sys", {})

    temp = main_data.get("temp")
    feels_like = main_data.get("feels_like")
    description = normalize_weather_description(weather_data[0].get("description", "без описания"))
    humidity = main_data.get("humidity")
    pressure = main_data.get("pressure")
    pressure_mmhg = round(pressure * 0.75006) if pressure is not None else None
    pressure_note = get_pressure_note_hpa(pressure)
    wind_speed = wind_data.get("speed")
    wind_deg = wind_data.get("deg")
    clouds = clouds_data.get("all")
    visibility = weather.get("visibility")
    sunrise = _format_hh_mm_from_unix(sys_data.get("sunrise"))
    sunset = _format_hh_mm_from_unix(sys_data.get("sunset"))

    if wind_speed is None:
        wind_text = "н/д"
    elif wind_deg is None:
        wind_text = f"{wind_speed} м/с"
    else:
        wind_text = f"{wind_speed} м/с, {wind_direction_ru(wind_deg)}"

    lines = [
        f"📍 Населённый пункт: {city_label}",
        f"🌡 Температура: {temp if temp is not None else 'н/д'} °C",
        f"🤔 Ощущается как: {feels_like if feels_like is not None else 'н/д'} °C",
        f"☁️ Описание: {description}",
        f"💧 Влажность: {humidity if humidity is not None else 'н/д'}%",
        f"🩺 Давление: {pressure_mmhg if pressure_mmhg is not None else 'н/д'} мм рт. ст.",
        f"🌬 Ветер: {wind_text}",
        f"🌥 Облачность: {clouds if clouds is not None else 'н/д'}%",
        f"👀 Видимость: {_format_visibility(visibility)}",
        f"🌅 Восход солнца: {sunrise}",
        f"🌇 Закат солнца: {sunset}",
    ]
    if pressure_note:
        lines.insert(6, pressure_note)

    if not air_components:
        lines.append("🌫 Данные о качестве воздуха недоступны.")
        return "\n".join(lines)

    air_analysis = analyze_air_pollution(air_components, extended=True)
    lines.append(f"🌫 Качество воздуха: {air_analysis.get('overall_status', 'Нет данных')}")
    details = air_analysis.get("details")

    if isinstance(details, dict):
        for component in details.values():
            name = component.get("name", "Компонент")
            value = _format_air_component_value(component.get("value", "н/д"))
            status = component.get("status", "Нет данных")
            lines.append(f"• {name} — {value} мкг/м³ ({status})")
    else:
        lines.append(str(details))

    return "\n".join(lines)


def format_compare_response(city_1: str, weather_1: dict, city_2: str, weather_2: dict) -> str:
    """Собирает текст сравнения двух населённых пунктов."""
    main_1 = weather_1.get("main", {})
    weather_data_1 = weather_1.get("weather", [{}])
    wind_data_1 = weather_1.get("wind", {})

    main_2 = weather_2.get("main", {})
    weather_data_2 = weather_2.get("weather", [{}])
    wind_data_2 = weather_2.get("wind", {})

    w1 = {
        "temp": main_1.get("temp"),
        "feels_like": main_1.get("feels_like"),
        "description": normalize_weather_description(weather_data_1[0].get("description", "без описания")),
        "humidity": main_1.get("humidity"),
        "wind_speed": wind_data_1.get("speed"),
        "wind_deg": wind_data_1.get("deg"),
    }
    w2 = {
        "temp": main_2.get("temp"),
        "feels_like": main_2.get("feels_like"),
        "description": normalize_weather_description(weather_data_2[0].get("description", "без описания")),
        "humidity": main_2.get("humidity"),
        "wind_speed": wind_data_2.get("speed"),
        "wind_deg": wind_data_2.get("deg"),
    }

    wind_text_1 = _wind_text_from_values(w1["wind_speed"], w1["wind_deg"])
    wind_text_2 = _wind_text_from_values(w2["wind_speed"], w2["wind_deg"])

    temp_1 = w1["temp"]
    temp_2 = w2["temp"]
    wind_1 = w1["wind_speed"] if w1["wind_speed"] is not None else 0
    wind_2 = w2["wind_speed"] if w2["wind_speed"] is not None else 0

    if temp_1 is None or temp_2 is None:
        temp_summary = "По температуре недостаточно данных для точного сравнения."
    elif temp_1 == temp_2:
        temp_summary = "Температура в обоих населённых пунктах одинаковая."
    elif temp_1 > temp_2:
        temp_summary = f"Теплее в населённом пункте {city_1}."
    else:
        temp_summary = f"Теплее в населённом пункте {city_2}."

    if wind_1 == wind_2:
        wind_summary = "Скорость ветра в обоих населённых пунктах одинаковая."
    elif wind_1 > wind_2:
        wind_summary = f"Сильнее ветер в населённом пункте {city_1}."
    else:
        wind_summary = f"Сильнее ветер в населённом пункте {city_2}."

    return (
        "🏙 Сравнение населённых пунктов\n\n"
        f"1) {city_1}\n"
        f"🌡 Температура: {w1['temp'] if w1['temp'] is not None else 'н/д'} °C\n"
        f"🤔 Ощущается как: {w1['feels_like'] if w1['feels_like'] is not None else 'н/д'} °C\n"
        f"☁️ Описание: {w1['description']}\n"
        f"💧 Влажность: {w1['humidity'] if w1['humidity'] is not None else 'н/д'}%\n"
        f"🌬 Ветер: {wind_text_1}\n\n"
        f"2) {city_2}\n"
        f"🌡 Температура: {w2['temp'] if w2['temp'] is not None else 'н/д'} °C\n"
        f"🤔 Ощущается как: {w2['feels_like'] if w2['feels_like'] is not None else 'н/д'} °C\n"
        f"☁️ Описание: {w2['description']}\n"
        f"💧 Влажность: {w2['humidity'] if w2['humidity'] is not None else 'н/д'}%\n"
        f"🌬 Ветер: {wind_text_2}\n\n"
        f"📌 Итог:\n• {temp_summary}\n• {wind_summary}"
    )


def _source_compare_precip_line(text: str) -> str:
    normalized = str(text or "").strip()
    if not normalized:
        return "н/д"
    if normalized == "без существенных осадков":
        return "не ожидаются"
    return normalized


def _normalize_precip_text(value: object) -> str:
    return str(value or "").strip().lower()


def _detect_precipitation_type(description: object, precipitation_text: object) -> str:
    combined = " ".join(
        part for part in (
            _normalize_precip_text(description),
            _normalize_precip_text(precipitation_text),
        ) if part
    )
    if any(marker in combined for marker in ("гроза",)):
        return "thunderstorm"
    if "мокрый снег" in combined:
        return "sleet"
    if any(marker in combined for marker in ("снег",)):
        return "snow"
    if any(marker in combined for marker in ("дожд", "лив", "морось")):
        return "rain"
    return "unknown"


def _precipitation_type_label(precip_type: str, *, current: bool = False, likely: bool = False) -> str:
    if precip_type == "thunderstorm":
        return "возможна гроза" if likely or current else "гроза"
    if precip_type == "sleet":
        return "возможен мокрый снег" if likely or current else "мокрый снег"
    if precip_type == "snow":
        return "идёт снег" if current else ("возможен снег" if likely else "снег")
    if precip_type == "rain":
        return "идёт дождь" if current else ("возможен дождь" if likely else "дождь")
    return "возможны осадки" if likely else "осадки"


def _build_precipitation_profile(payload: dict, *, current: bool = False) -> dict[str, object]:
    precipitation_text = _normalize_precip_text(payload.get("precipitation_text"))
    description = payload.get("dominant_description")
    precip_type = _detect_precipitation_type(description, precipitation_text)
    signal = payload.get("precipitation_signal") if isinstance(payload.get("precipitation_signal"), dict) else {}
    max_pop = signal.get("max_pop") if isinstance(signal, dict) else None
    has_probability = isinstance(max_pop, (int, float))
    max_pop_value = float(max_pop) if has_probability else None
    no_precip = any(
        marker in precipitation_text
        for marker in ("без осадков", "без существенных осадков", "не ожидаются")
    )
    high = any(marker in precipitation_text for marker in ("высокий шанс",)) or (has_probability and max_pop_value >= 0.7)
    medium = any(marker in precipitation_text for marker in ("возможен", "возможна", "умеренный")) or (
        has_probability and max_pop_value >= 0.35
    )
    low = any(marker in precipitation_text for marker in ("маловероят", "низкий")) or (
        has_probability and 0.0 < max_pop_value < 0.35
    )
    if no_precip:
        presence = "none"
        confidence = "none"
    elif precip_type != "unknown" or high or medium or low or (has_probability and max_pop_value >= 0.2):
        presence = "risk"
        if high:
            confidence = "high"
        elif medium:
            confidence = "medium"
        elif low:
            confidence = "low"
        else:
            confidence = "risk"
    else:
        presence = "unknown"
        confidence = "unknown"
    return {
        "type": precip_type,
        "presence": presence,
        "confidence": confidence,
        "probability": max_pop_value,
        "display": _source_compare_precip_line(str(payload.get("precipitation_text") or "")),
        "specific": _precipitation_type_label(
            precip_type,
            current=current,
            likely=presence == "risk",
        ) if precip_type != "unknown" else ("без осадков" if presence == "none" else "возможны осадки"),
    }


def _precipitation_amount_label(payload: dict) -> str:
    precip_type = _detect_precipitation_type(
        payload.get("dominant_description"),
        payload.get("precipitation_text"),
    )
    if precip_type == "rain":
        return "количество дождя"
    if precip_type == "snow":
        return "количество снега"
    if precip_type == "sleet":
        return "количество мокрого снега"
    return "количество осадков"


def _format_percent(value: object) -> str | None:
    if isinstance(value, (int, float)):
        return f"до {round(float(value) * 100):.0f}%"
    return None


def _format_mm(value: object) -> str | None:
    if isinstance(value, (int, float)):
        return f"до {float(value):.1f} мм"
    return None


def _format_humidity_band(min_value: object, max_value: object) -> str | None:
    if not isinstance(min_value, (int, float)) and not isinstance(max_value, (int, float)):
        return None
    if not isinstance(min_value, (int, float)):
        return f"{round(float(max_value))}%"
    if not isinstance(max_value, (int, float)):
        return f"{round(float(min_value))}%"
    min_h = round(float(min_value))
    max_h = round(float(max_value))
    if min_h == max_h:
        return f"{min_h}%"
    return f"{min_h}-{max_h}%"


def _format_pressure_band_mmhg(min_value: object, max_value: object) -> str | None:
    if not isinstance(min_value, (int, float)) and not isinstance(max_value, (int, float)):
        return None
    if not isinstance(min_value, (int, float)):
        mmhg = round(float(max_value) * 0.75006)
        return f"{mmhg} мм рт. ст."
    if not isinstance(max_value, (int, float)):
        mmhg = round(float(min_value) * 0.75006)
        return f"{mmhg} мм рт. ст."
    min_mmhg = round(float(min_value) * 0.75006)
    max_mmhg = round(float(max_value) * 0.75006)
    if min_mmhg == max_mmhg:
        return f"{min_mmhg} мм рт. ст."
    return f"{min_mmhg}-{max_mmhg} мм рт. ст."


def _format_wind_numeric_band(payload: dict) -> str | None:
    signal = payload.get("wind_signal") if isinstance(payload, dict) else {}
    if not isinstance(signal, dict):
        return None
    min_speed = signal.get("min_speed")
    max_speed = signal.get("max_speed")
    avg_speed = signal.get("avg_speed")
    wind_text = str(payload.get("wind_text") or "").strip()
    numeric = None
    if isinstance(min_speed, (int, float)) and isinstance(max_speed, (int, float)):
        min_s = float(min_speed)
        max_s = float(max_speed)
        if round(min_s, 1) == round(max_s, 1):
            numeric = f"{min_s:.1f} м/с"
        else:
            numeric = f"{min_s:.1f}-{max_s:.1f} м/с"
    elif isinstance(avg_speed, (int, float)):
        numeric = f"{float(avg_speed):.1f} м/с"
    direction_text = str(payload.get("wind_direction_text") or "").strip()
    parts = [part for part in (numeric, wind_text, direction_text) if part]
    if not parts:
        return None
    return ", ".join(parts)


def _format_source_compare_temp_sentence(payload: dict) -> str | None:
    band = _format_temp_band(payload.get("min_temp"), payload.get("max_temp"))
    if band == "н/д":
        return None
    return band


def _format_source_compare_provider_block(provider_name: str, payload: dict) -> list[str]:
    lines = [f"{provider_name}:"]
    lines.append(f"• температура: {_format_temp_band(payload.get('min_temp'), payload.get('max_temp'))}")
    feels_like_band = _format_temp_band(payload.get("min_feels_like"), payload.get("max_feels_like"))
    if feels_like_band != "н/д":
        lines.append(f"• ощущается как: {feels_like_band}")
    lines.append(f"• условия: {payload.get('dominant_description') or 'н/д'}")
    lines.append(f"• осадки: {_source_compare_precip_line(str(payload.get('precipitation_text') or ''))}")
    probability_text = _format_percent((payload.get("precipitation_signal") or {}).get("max_pop") if isinstance(payload.get("precipitation_signal"), dict) else None)
    if probability_text:
        lines.append(f"• вероятность осадков: {probability_text}")
    precipitation_amount_text = _format_mm((payload.get("precipitation_signal") or {}).get("max_amount") if isinstance(payload.get("precipitation_signal"), dict) else None)
    if precipitation_amount_text:
        lines.append(f"• {_precipitation_amount_label(payload)}: {precipitation_amount_text}")
    wind_line = _format_wind_numeric_band(payload)
    if wind_line:
        lines.append(f"• ветер: {wind_line}")
    humidity_line = _format_humidity_band(payload.get("min_humidity"), payload.get("max_humidity"))
    if humidity_line:
        lines.append(f"• влажность: {humidity_line}")
    pressure_line = _format_pressure_band_mmhg(payload.get("min_pressure"), payload.get("max_pressure"))
    if pressure_line:
        lines.append(f"• давление: {pressure_line}")
    return lines


def _format_source_compare_current_provider_block(provider_name: str, payload: dict) -> list[str]:
    lines = [f"{provider_name}:"]
    temperature = payload.get("temperature")
    feels_like = payload.get("feels_like")
    humidity = payload.get("humidity")
    pressure = payload.get("pressure")
    wind_line = _format_wind_numeric_band(payload)
    if isinstance(temperature, (int, float)):
        lines.append(f"• температура: {float(temperature):.1f} °C")
    if isinstance(feels_like, (int, float)):
        lines.append(f"• ощущается как: {float(feels_like):.1f} °C")
    lines.append(f"• условия: {payload.get('dominant_description') or 'н/д'}")
    if isinstance(humidity, (int, float)):
        lines.append(f"• влажность: {round(float(humidity))}%")
    pressure_line = _format_pressure_band_mmhg(pressure, pressure)
    if pressure_line:
        lines.append(f"• давление: {pressure_line}")
    if wind_line:
        lines.append(f"• ветер: {wind_line}")
    return lines


def _temperature_gap_label(openweather_payload: dict, open_meteo_payload: dict) -> str:
    ow_values = [
        value
        for value in (openweather_payload.get("min_temp"), openweather_payload.get("max_temp"))
        if isinstance(value, (int, float))
    ]
    om_values = [
        value
        for value in (open_meteo_payload.get("min_temp"), open_meteo_payload.get("max_temp"))
        if isinstance(value, (int, float))
    ]
    if len(ow_values) < 2 or len(om_values) < 2:
        return "разница по температуре неочевидна"
    delta = max(
        abs(float(openweather_payload["min_temp"]) - float(open_meteo_payload["min_temp"])),
        abs(float(openweather_payload["max_temp"]) - float(open_meteo_payload["max_temp"])),
    )
    if delta <= 2:
        return "температура близкая"
    if delta <= 4:
        return "температура отличается умеренно"
    return "температура заметно отличается"


def _build_source_compare_summary(openweather_payload: dict, open_meteo_payload: dict) -> str:
    def _wind_rank(text: str) -> int | None:
        mapping = {"слабый": 0, "умеренный": 1, "сильный": 2, "очень сильный": 3}
        return mapping.get(text.strip().lower())

    def _wind_bounds(payload: dict) -> tuple[float | None, float | None]:
        signal = payload.get("wind_signal") if isinstance(payload, dict) else {}
        if not isinstance(signal, dict):
            return None, None
        min_speed = signal.get("min_speed")
        max_speed = signal.get("max_speed")
        avg_speed = signal.get("avg_speed")
        if isinstance(min_speed, (int, float)) and isinstance(max_speed, (int, float)):
            return float(min_speed), float(max_speed)
        if isinstance(avg_speed, (int, float)):
            speed = float(avg_speed)
            return speed, speed
        return None, None

    def _temperature_sentence() -> str:
        temp_label = _temperature_gap_label(openweather_payload, open_meteo_payload)
        ow_band = _format_source_compare_temp_sentence(openweather_payload)
        om_band = _format_source_compare_temp_sentence(open_meteo_payload)
        if temp_label == "температура близкая":
            return "По температуре прогнозы близки."
        if temp_label == "температура отличается умеренно":
            if ow_band and om_band:
                return f"По температуре есть умеренное расхождение: OpenWeather даёт {ow_band}, Open-Meteo — {om_band}."
            return "По температуре есть умеренное расхождение."
        if temp_label == "температура заметно отличается":
            if ow_band and om_band:
                return f"По температуре есть заметное расхождение: OpenWeather даёт {ow_band}, Open-Meteo — {om_band}."
            return "По температуре есть заметное расхождение."
        return "По температуре данных недостаточно для уверенного вывода."

    def _wind_sentence() -> str:
        ow_wind = _format_wind_numeric_band(openweather_payload)
        om_wind = _format_wind_numeric_band(open_meteo_payload)
        ow_text = str(openweather_payload.get("wind_text") or "").strip()
        om_text = str(open_meteo_payload.get("wind_text") or "").strip()
        ow_rank = _wind_rank(ow_text)
        om_rank = _wind_rank(om_text)
        ow_min, ow_max = _wind_bounds(openweather_payload)
        om_min, om_max = _wind_bounds(open_meteo_payload)
        overlap = (
            isinstance(ow_min, float)
            and isinstance(ow_max, float)
            and isinstance(om_min, float)
            and isinstance(om_max, float)
            and max(ow_min, om_min) <= min(ow_max, om_max)
        )
        close_numeric = (
            isinstance(ow_min, float)
            and isinstance(ow_max, float)
            and isinstance(om_min, float)
            and isinstance(om_max, float)
            and abs(ow_min - om_min) <= 1.2
            and abs(ow_max - om_max) <= 1.2
        )
        same_category = ow_text and om_text and ow_text == om_text
        nearby_category = (
            ow_rank is not None
            and om_rank is not None
            and abs(ow_rank - om_rank) == 1
        )

        if same_category and (overlap or close_numeric):
            if ow_wind and om_wind and ow_wind != om_wind:
                return f"По ветру различия небольшие: OpenWeather даёт {ow_wind}, Open-Meteo — {om_wind}."
            return f"По ветру прогнозы близки: оба источника показывают {ow_text} ветер."
        if nearby_category and (overlap or close_numeric) and ow_wind and om_wind:
            return f"По ветру есть небольшое расхождение: OpenWeather даёт {ow_wind}, Open-Meteo — {om_wind}."
        if ow_wind and om_wind and ow_wind != om_wind:
            return f"По ветру прогнозы различаются: OpenWeather даёт {ow_wind}, Open-Meteo — {om_wind}."
        if ow_wind or om_wind:
            return "По ветру различия небольшие."
        return "По ветру данных недостаточно."

    ow_precip = _build_precipitation_profile(openweather_payload)
    om_precip = _build_precipitation_profile(open_meteo_payload)
    temperature_sentence = _temperature_sentence()
    wind_sentence = _wind_sentence()

    def _prob_text(profile: dict[str, object], fallback: str) -> str:
        probability = profile.get("probability")
        if isinstance(probability, float):
            return f"до {round(probability * 100):.0f}%"
        confidence = str(profile.get("confidence") or "")
        mapping = {
            "high": "высокий шанс",
            "medium": "умеренную вероятность",
            "low": "низкую вероятность",
            "risk": "возможный риск",
        }
        return mapping.get(confidence, fallback)

    def _precip_sentence() -> str:
        def _presence_phrase(profile: dict[str, object]) -> str:
            presence = str(profile.get("presence") or "")
            precip_type = str(profile.get("type") or "")
            if presence != "risk":
                return "без существенных осадков"
            risk_names = {
                "rain": "риск дождя",
                "snow": "риск снега",
                "thunderstorm": "риск грозы",
                "sleet": "риск мокрого снега",
            }
            return risk_names.get(precip_type, "риск осадков")

        ow_presence = str(ow_precip.get("presence") or "")
        om_presence = str(om_precip.get("presence") or "")
        ow_type = str(ow_precip.get("type") or "")
        om_type = str(om_precip.get("type") or "")
        type_names = {
            "rain": "дождь",
            "snow": "снег",
            "thunderstorm": "грозу",
            "sleet": "мокрый снег",
        }
        if ow_presence == "none" and om_presence == "none":
            return "По осадкам источники сходятся: существенных осадков не ожидается."
        if ow_presence == "risk" and om_presence == "risk":
            if ow_type == om_type and ow_type != "unknown":
                shared_type = type_names.get(ow_type, "осадки")
                if isinstance(ow_precip.get("probability"), float) and isinstance(om_precip.get("probability"), float):
                    ow_prob = _prob_text(ow_precip, "высокую")
                    om_prob = _prob_text(om_precip, "умеренную")
                    if ow_prob != om_prob:
                        return (
                            f"По осадкам источники в целом сходятся: оба допускают {shared_type}, "
                            f"но OpenWeather оценивает вероятность выше — {ow_prob} против {om_prob}."
                        )
                if str(ow_precip.get("confidence")) != str(om_precip.get("confidence")):
                    return (
                        f"По осадкам источники в целом сходятся: оба допускают {shared_type}, "
                        f"но по-разному оценивают вероятность: "
                        f"OpenWeather показывает {_prob_text(ow_precip, 'высокий шанс')}, "
                        f"Open-Meteo — {_prob_text(om_precip, 'умеренную вероятность')}."
                    )
                return f"По осадкам источники в целом сходятся: оба допускают {shared_type}."
            if ow_type == om_type == "unknown":
                return (
                    "По осадкам источники в целом сходятся: оба показывают риск осадков, "
                    "но тип осадков в данных не уточнён."
                )
            if ow_type != om_type and ow_type != "unknown" and om_type != "unknown":
                return (
                    "Источники расходятся по типу осадков: "
                    f"OpenWeather показывает {_precipitation_type_label(ow_type)}, "
                    f"Open-Meteo — {_precipitation_type_label(om_type)}."
                )
        if ow_presence != om_presence:
            return (
                "Источники расходятся по осадкам: "
                f"OpenWeather показывает {_presence_phrase(ow_precip)}, "
                f"Open-Meteo — {_presence_phrase(om_precip)}."
            )
        if ow_type != om_type and ow_type != "unknown" and om_type != "unknown":
            return (
                "Источники расходятся по типу осадков: "
                f"OpenWeather показывает {_precipitation_type_label(ow_type)}, "
                f"Open-Meteo — {_precipitation_type_label(om_type)}."
            )
        if ow_presence == "risk" and om_presence == "risk":
            return (
                "По осадкам источники в целом сходятся: оба показывают риск осадков, "
                "но тип осадков в данных не уточнён."
            )
        return "По осадкам данных недостаточно для уверенного вывода."

    return f"{_precip_sentence()} {temperature_sentence} {wind_sentence}"


def _build_source_compare_current_summary(openweather_payload: dict, open_meteo_payload: dict) -> str:
    def _temp_value(payload: dict) -> float | None:
        value = payload.get("temperature")
        if isinstance(value, (int, float)):
            return float(value)
        value = payload.get("min_temp")
        return float(value) if isinstance(value, (int, float)) else None

    temp_ow = _temp_value(openweather_payload)
    temp_om = _temp_value(open_meteo_payload)
    if isinstance(temp_ow, float) and isinstance(temp_om, float):
        temp_delta = abs(temp_ow - temp_om)
        if temp_delta <= 2:
            temperature_sentence = "Источники в целом сходятся по температуре."
        elif temp_delta <= 4:
            temperature_sentence = (
                f"По температуре есть умеренное расхождение: OpenWeather даёт {temp_ow:.1f} °C, "
                f"Open-Meteo — {temp_om:.1f} °C."
            )
        else:
            temperature_sentence = (
                f"По температуре есть заметное расхождение: OpenWeather даёт {temp_ow:.1f} °C, "
                f"Open-Meteo — {temp_om:.1f} °C."
            )
    else:
        temperature_sentence = "По температуре данных недостаточно для уверенного вывода."

    full_summary = _build_source_compare_summary(openweather_payload, open_meteo_payload)
    parts = [part.strip() for part in full_summary.split(". ") if part.strip()]
    precipitation_sentence = next((part for part in parts if "осадк" in part), "По осадкам данных недостаточно.")
    wind_sentence = next((part for part in parts if "ветру" in part), "По ветру данных недостаточно.")
    if not precipitation_sentence.endswith("."):
        precipitation_sentence += "."
    if not wind_sentence.endswith("."):
        wind_sentence += "."
    return f"{temperature_sentence} {wind_sentence} {precipitation_sentence}"


def format_source_compare_response(
    city_label: str,
    openweather_payload: dict,
    open_meteo_payload: dict,
    *,
    title: str = "🔎 Сравнение прогнозов на завтра",
) -> str:
    """Formats deterministic forecast comparison between OpenWeather and Open-Meteo."""
    lines = [
        title,
        "",
        f"📍 {city_label}",
        "",
        *_format_source_compare_provider_block("OpenWeather", openweather_payload),
        "",
        *_format_source_compare_provider_block("Open-Meteo", open_meteo_payload),
        "",
        f"✨ {_build_source_compare_summary(openweather_payload, open_meteo_payload)}",
    ]
    return "\n".join(lines)


def format_source_compare_current_response(city_label: str, openweather_payload: dict, open_meteo_payload: dict) -> str:
    """Formats deterministic current-conditions comparison between OpenWeather and Open-Meteo."""
    lines = [
        "🔎 Сравнение погоды сейчас",
        "",
        f"📍 {city_label}",
        "",
        *_format_source_compare_current_provider_block("OpenWeather", openweather_payload),
        "",
        *_format_source_compare_current_provider_block("Open-Meteo", open_meteo_payload),
        "",
        f"✨ {_build_source_compare_current_summary(openweather_payload, open_meteo_payload)}",
    ]
    return "\n".join(lines)
