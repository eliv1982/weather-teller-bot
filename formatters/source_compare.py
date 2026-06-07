"""
Formatters for deterministic OpenWeather vs Open-Meteo source comparison.
"""


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
