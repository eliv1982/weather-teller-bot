from datetime import datetime

from weather_app import analyze_air_pollution
from weather.descriptions import normalize_weather_description
from weather.pressure import get_pressure_note_hpa


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
    if numeric and wind_text:
        return f"{numeric}, {wind_text}"
    return numeric or (wind_text if wind_text else None)


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
        lines.append(f"• количество осадков: {precipitation_amount_text}")
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
            if ow_text and om_text and ow_text != om_text:
                return (
                    "По ветру прогнозы различаются: "
                    f"OpenWeather даёт {ow_wind}, Open-Meteo — {om_wind}. "
                    f"У Open-Meteo ветер {om_text}, у OpenWeather — {ow_text}."
                )
            return f"По ветру прогнозы различаются: OpenWeather даёт {ow_wind}, Open-Meteo — {om_wind}."
        if ow_wind or om_wind:
            return "По ветру различия небольшие."
        return "По ветру данных недостаточно."

    ow_precip = str(openweather_payload.get("precipitation_text") or "").strip()
    om_precip = str(open_meteo_payload.get("precipitation_text") or "").strip()
    temperature_sentence = _temperature_sentence()
    wind_sentence = _wind_sentence()
    if ow_precip and om_precip and ow_precip != om_precip:
        return (
            "Источники расходятся по осадкам: "
            f"OpenWeather показывает {ow_precip}, Open-Meteo — {om_precip}. "
            f"{temperature_sentence} {wind_sentence}"
        )

    if ow_precip == "без существенных осадков":
        if temperature_sentence == "По температуре прогнозы близки.":
            return f"Источники в целом сходятся: температура близкая, существенных осадков не ожидается. {wind_sentence}"
        return f"Источники в целом сходятся: существенных осадков не ожидается. {temperature_sentence} {wind_sentence}"
    if ow_precip:
        return f"Источники в целом сходятся: оба прогноза показывают {ow_precip}. {temperature_sentence} {wind_sentence}"
    return f"Источники в целом сходятся. {temperature_sentence} {wind_sentence}"


def format_source_compare_response(city_label: str, openweather_payload: dict, open_meteo_payload: dict) -> str:
    """Formats deterministic tomorrow comparison between OpenWeather and Open-Meteo."""
    lines = [
        "🔎 Сравнение прогнозов на завтра",
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
