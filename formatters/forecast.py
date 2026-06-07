"""
Formatters for today/tomorrow/5-day forecasts and deterministic two-city comparison.
"""

from weather.descriptions import normalize_weather_description

from formatters.common import wind_direction_ru, _wind_text_from_values


def _format_temp_range(values: list[float]) -> str:
    """Форматирует диапазон значений температуры."""
    if not values:
        return "н/д"
    min_value = min(values)
    max_value = max(values)
    if round(min_value, 1) == round(max_value, 1):
        return f"{min_value:.1f} °C"
    return f"{min_value:.1f}...{max_value:.1f} °C"


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
