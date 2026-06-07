"""Deterministic factual compare rendering helpers for AiWeatherService."""

from __future__ import annotations

from typing import Protocol


class _CompareRenderContext(Protocol):
    def _format_number(self, value: object, suffix: str = "") -> str: ...
    def _temperature_absolute_note(self, value: object) -> str: ...
    def _humidity_absolute_note(self, value: object) -> str: ...
    def _wind_absolute_note(self, value: object) -> str: ...
    def _capitalize_phrase(self, text: object) -> str: ...
    def _normalize_description(self, value: object) -> str: ...
    def _get_short_location_name(self, city_label: str) -> str: ...


def _clean_compare_description(value: object) -> str:
    text = str(value or "").strip()
    return text if text else "н/д"


def _current_precipitation_summary(context: _CompareRenderContext, description: object) -> str:
    desc = context._normalize_description(description)
    if "небольшой дождь" in desc:
        return "идёт небольшой дождь"
    if "снег" in desc:
        return "идёт снег"
    if "гроза" in desc:
        return "идёт гроза"
    if any(marker in desc for marker in ("дожд", "лив", "морось")):
        return "идёт дождь"
    return "осадков по текущим данным нет"


def _compare_location_label(context: _CompareRenderContext, city_label: str) -> str:
    return context._get_short_location_name(city_label)


def _location_prefix(context: _CompareRenderContext, city_label: str) -> str:
    return f"В локации {_compare_location_label(context, city_label)}"


def _compare_current_lead(
    context: _CompareRenderContext,
    city_label: str,
    temperature_note: str,
    description: str,
) -> str:
    label = _location_prefix(context, city_label)
    clean_description = str(description or "").strip()
    if not clean_description or clean_description == "н/д":
        return f"{label}: {temperature_note}"
    desc_lower = clean_description.lower()
    if "небольшой дождь" in desc_lower:
        return f"{label}: {temperature_note}, идёт небольшой дождь"
    if "снег" in desc_lower:
        return f"{label}: {temperature_note}, идёт снег"
    if "гроза" in desc_lower:
        return f"{label}: {temperature_note}, идёт гроза"
    if any(marker in desc_lower for marker in ("дожд", "лив", "морось")):
        return f"{label}: {temperature_note}, идёт дождь"
    return f"{label}: {temperature_note} и {desc_lower}"


def _temperature_weather_adjective(temperature_note: str) -> str:
    mapping = {
        "холодно": "холодная",
        "прохладно": "прохладная",
        "свежо": "свежая",
        "тепло": "тёплая",
        "жарко": "жаркая",
    }
    return mapping.get(temperature_note, "спокойная")


def _forecast_description_adjective(description: str) -> str | None:
    desc = str(description or "").strip().lower()
    mapping = {
        "ясно": "ясная",
        "солнечно": "солнечная",
        "облачно": "облачная",
        "пасмурно": "пасмурная",
        "переменная облачность": "облачная",
    }
    return mapping.get(desc)


def _compare_forecast_lead(
    context: _CompareRenderContext,
    city_label: str,
    temperature_note: str,
    description: str,
) -> str:
    label = _location_prefix(context, city_label)
    clean_description = str(description or "").strip()
    weather_note = _temperature_weather_adjective(temperature_note)
    description_adjective = _forecast_description_adjective(clean_description)
    if description_adjective:
        return f"{label}: ожидается {weather_note} {description_adjective} погода"
    return f"{label}: ожидается {weather_note} погода"


def _forecast_short_precipitation_summary(
    context: _CompareRenderContext,
    description: object,
    probability: object,
) -> str:
    desc = context._normalize_description(description)
    if "гроза" in desc:
        return "возможна гроза"
    if "снег" in desc:
        return "ожидается снег"
    if any(marker in desc for marker in ("дожд", "лив", "морось")):
        likely = isinstance(probability, (int, float)) and float(probability) >= 0.45
        return f"ожидается {desc}" if likely else "возможен дождь"
    if isinstance(probability, (int, float)) and float(probability) >= 0.2:
        return "возможны осадки"
    return "без осадков"


def _forecast_probability_phrase(probability: object) -> str | None:
    if isinstance(probability, (int, float)) and float(probability) >= 0.2:
        return f"вероятность до {round(float(probability) * 100):.0f}%"
    return None


def _forecast_probability_text(payload: dict) -> str:
    signal = payload.get("precipitation_signal") if isinstance(payload.get("precipitation_signal"), dict) else {}
    max_pop = signal.get("max_pop") if isinstance(signal, dict) else None
    if isinstance(max_pop, (int, float)):
        return f"{round(float(max_pop) * 100):.0f}%"
    return "н/д"


def _precipitation_absolute_note(
    context: _CompareRenderContext,
    description: object,
    *,
    probability: object = None,
    current: bool = False,
) -> str:
    desc = context._normalize_description(description)
    if "небольшой дождь" in desc:
        return "идёт небольшой дождь" if current else "ожидается небольшой дождь"
    if "сильный дождь" in desc:
        return "идёт сильный дождь" if current else "ожидается сильный дождь"
    if "гроза" in desc:
        return "идёт гроза" if current else "возможна гроза"
    has_snow = "снег" in desc
    has_rain = any(marker in desc for marker in ("дожд", "лив", "морось"))
    likely = isinstance(probability, (int, float)) and float(probability) >= 0.2
    if has_snow:
        return "идёт снег" if current else "возможен снег"
    if has_rain:
        return "идёт дождь" if current else "возможен дождь"
    if likely:
        return "возможны осадки"
    return "без осадков"


def _forecast_precipitation_note(context: _CompareRenderContext, payload: dict) -> str:
    signal = payload.get("precipitation_signal") if isinstance(payload.get("precipitation_signal"), dict) else {}
    probability = signal.get("max_pop") if isinstance(signal, dict) else None
    return _precipitation_absolute_note(
        context,
        payload.get("dominant_description"),
        probability=probability,
        current=False,
    )


def _forecast_avg_temp(payload: dict) -> float | None:
    min_temp = payload.get("min_temp")
    max_temp = payload.get("max_temp")
    if isinstance(min_temp, (int, float)) and isinstance(max_temp, (int, float)):
        return (float(min_temp) + float(max_temp)) / 2.0
    return None


def _render_compare_current_block(
    context: _CompareRenderContext,
    payload: dict,
    fallback_name: str,
) -> str:
    city = str(payload.get("city_label") or fallback_name)
    temperature = payload.get("temperature")
    feels_like = payload.get("feels_like")
    humidity = payload.get("humidity")
    wind_speed = payload.get("wind_speed")
    description = _clean_compare_description(payload.get("description"))
    precipitation_note = _current_precipitation_summary(context, description)
    temperature_note = context._temperature_absolute_note(
        feels_like if isinstance(feels_like, (int, float)) else temperature
    )
    humidity_note = context._humidity_absolute_note(humidity)
    wind_note = context._wind_absolute_note(wind_speed)
    feels_like_note = (
        f", ощущается около {round(float(feels_like))} °C"
        if isinstance(feels_like, (int, float))
        else ""
    )
    has_precip_in_lead = precipitation_note != "осадков по текущим данным нет"
    details_sentence = (
        f"{context._capitalize_phrase(humidity_note)}, {wind_note}."
        if has_precip_in_lead
        else f"{context._capitalize_phrase(humidity_note)}, {wind_note}, {precipitation_note}."
    )
    short = (
        f"✨ {context._capitalize_phrase(_compare_current_lead(context, city, temperature_note, description))}{feels_like_note}. "
        f"{details_sentence}"
    )
    return "\n".join([
        f"📍 {city}",
        f"🌡 Температура: {context._format_number(temperature, '°C')}",
        f"🤔 Ощущается как: {context._format_number(feels_like, '°C')}",
        f"☁️ Описание: {description}",
        f"💧 Влажность: {context._format_number(humidity, '%')}",
        f"🌬 Ветер: {context._format_number(wind_speed, ' м/с')}",
        "",
        short,
    ])


def _render_compare_current_factual(
    context: _CompareRenderContext,
    payload_1: dict,
    payload_2: dict,
) -> str:
    return "\n\n".join([
        _render_compare_current_block(context, payload_1, "Локация A"),
        _render_compare_current_block(context, payload_2, "Локация B"),
    ])


def _render_compare_forecast_block(
    context: _CompareRenderContext,
    payload: dict,
    selected_day: str,
    fallback_name: str,
) -> str:
    city = str(payload.get("city_label") or fallback_name)
    description = _clean_compare_description(payload.get("dominant_description"))
    min_temp = payload.get("min_temp")
    max_temp = payload.get("max_temp")
    avg_temp = _forecast_avg_temp(payload)
    wind_signal = payload.get("wind_signal") if isinstance(payload.get("wind_signal"), dict) else {}
    avg_wind = wind_signal.get("avg_speed") if isinstance(wind_signal, dict) else None
    max_wind = wind_signal.get("max_speed") if isinstance(wind_signal, dict) else None
    precipitation_note = _forecast_precipitation_note(context, payload)
    probability = payload.get("precipitation_signal", {}).get("max_pop") if isinstance(payload.get("precipitation_signal"), dict) else None
    short_precipitation = _forecast_short_precipitation_summary(context, description, probability)
    precipitation_probability = _forecast_probability_phrase(probability)
    temp_band = f"{context._format_number(min_temp, '°C')}-{context._format_number(max_temp, '°C')}"
    second_sentence = (
        f"{context._capitalize_phrase(short_precipitation)}, {precipitation_probability}. {context._capitalize_phrase(context._wind_absolute_note(avg_wind))}."
        if precipitation_probability
        else f"{context._capitalize_phrase(short_precipitation)}. {context._capitalize_phrase(context._wind_absolute_note(avg_wind))}."
    )
    short = (
        f"✨ {context._capitalize_phrase(_compare_forecast_lead(context, city, context._temperature_absolute_note(avg_temp), description))}, "
        f"температура около {temp_band}. {second_sentence}"
    )
    lines = [
        f"📍 {city}",
        f"📅 Дата: {selected_day}",
        f"🌡 Температура: от {context._format_number(min_temp, '°C')} до {context._format_number(max_temp, '°C')}",
        f"🌡 Средняя температура: {context._format_number(avg_temp, '°C')}",
        f"☁️ Описание: {description}",
        f"🌧 Осадки: {precipitation_note}",
        f"☔ Вероятность осадков: {_forecast_probability_text(payload)}",
    ]
    if isinstance(avg_wind, (int, float)) and isinstance(max_wind, (int, float)):
        lines.append(
            f"🌬 Ветер: в среднем {context._format_number(avg_wind, ' м/с')}, до {context._format_number(max_wind, ' м/с')}"
        )
    elif isinstance(avg_wind, (int, float)):
        lines.append(f"🌬 Ветер: в среднем {context._format_number(avg_wind, ' м/с')}")
    elif isinstance(max_wind, (int, float)):
        lines.append(f"🌬 Ветер: до {context._format_number(max_wind, ' м/с')}")
    else:
        lines.append("🌬 Ветер: н/д")
    lines.extend(["", short])
    return "\n".join(lines)


def _render_compare_forecast_factual(
    context: _CompareRenderContext,
    payload_1: dict,
    payload_2: dict,
    selected_day: str,
) -> str:
    return "\n\n".join([
        _render_compare_forecast_block(context, payload_1, selected_day, "Локация A"),
        _render_compare_forecast_block(context, payload_2, selected_day, "Локация B"),
    ])
