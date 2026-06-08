"""Deterministic fallback text helpers extracted from AiWeatherService."""

from datetime import datetime
import re

from weather.descriptions import normalize_weather_description
from weather.pressure import get_pressure_note_hpa


def fallback_current(city_label: str, weather_data: dict) -> str:
    main_data = weather_data.get("main", {}) if isinstance(weather_data, dict) else {}
    weather_list = weather_data.get("weather", []) if isinstance(weather_data, dict) else []
    wind_data = weather_data.get("wind", {}) if isinstance(weather_data, dict) else {}
    temp = main_data.get("temp")
    feels_like = main_data.get("feels_like")
    pressure_note = get_pressure_note_hpa(main_data.get("pressure"))
    description = normalize_weather_description((weather_list[0].get("description") if weather_list else "") or "без описания")
    wind_speed = wind_data.get("speed")
    desc_lower = str(description).lower()
    has_rain = any(x in desc_lower for x in ("дожд", "лив", "морось"))
    has_snow = "снег" in desc_lower
    has_thunder = "гроза" in desc_lower
    precipitation_note = (
        "По текущим данным, сейчас идёт дождь."
        if has_rain
        else (
            "По текущим данным, сейчас идёт снег."
            if has_snow
            else (
                "По текущим данным, сейчас возможна гроза."
                if has_thunder
                else "По текущим данным, осадков сейчас нет."
            )
        )
    )
    cold_advice = False
    if isinstance(feels_like, (int, float)):
        if feels_like <= 0:
            clothes = "Лучше одеться заметно теплее."
            cold_advice = True
        elif feels_like <= 12:
            clothes = "Лучше накинуть что-то тёплое."
            cold_advice = True
        else:
            clothes = "Можно выбрать более лёгкую одежду."
    else:
        clothes = "Одежду лучше выбрать по ощущениям на месте."
    wind_note = ""
    meaningful_wind = False
    if isinstance(wind_speed, (int, float)):
        ws = float(wind_speed)
        if ws < 3:
            wind_note = " Ветер слабый, почти не мешает."
        elif ws <= 5:
            wind_note = " Ветер умеренный: заметный, но без сильного влияния на комфорт."
        elif ws < 8:
            meaningful_wind = True
            if any(x in desc_lower for x in ("дожд", "лив", "гроза", "снег")) or (
                isinstance(feels_like, (int, float)) and float(feels_like) < 8
            ):
                wind_note = " Ветер заметный: при осадках или прохладе может быть менее комфортно."
            else:
                wind_note = " Ветер заметный и может ощущаться сильнее обычного."
        else:
            meaningful_wind = True
            wind_note = " Ветер сильный и заметно влияет на комфорт на улице."
    has_caution = has_rain or has_snow or has_thunder or cold_advice or meaningful_wind or bool(pressure_note)
    comfort = "" if has_caution else "По ощущениям погода без явного дискомфорта."
    advice_parts = [precipitation_note, clothes]
    if pressure_note:
        advice_parts.append(pressure_note)
    if comfort:
        advice_parts.append(comfort)
    return (
        f"Сейчас в локации {city_label}: {description}, температура {temp if temp is not None else 'н/д'}°C, "
        f"ощущается как {feels_like if feels_like is not None else 'н/д'}°C.{wind_note} "
        f"{' '.join(advice_parts)}"
    )


def fallback_day_forecast(city_label: str, day_items: list[dict]) -> str:
    if not isinstance(day_items, list) or not day_items:
        return f"По {city_label} пока недостаточно данных, чтобы дать понятную рекомендацию на день."
    rain_slots = 0
    best_slot = None
    best_temp = None
    pressure_values = []
    for item in day_items:
        weather_list = item.get("weather")
        weather_item = weather_list[0] if isinstance(weather_list, list) and weather_list and isinstance(weather_list[0], dict) else {}
        weather_desc = str(weather_item.get("description", "")).lower()
        if any(x in weather_desc for x in ("дожд", "лив", "гроза", "снег")):
            rain_slots += 1
        main_data = item.get("main", {})
        temp = main_data.get("temp")
        pressure = main_data.get("pressure")
        if isinstance(pressure, (int, float)):
            pressure_values.append(float(pressure))
        dt_txt = str(item.get("dt_txt") or "")
        if isinstance(temp, (int, float)) and (best_temp is None or temp > best_temp):
            best_temp = float(temp)
            best_slot = dt_txt
    rain_note = "В течение дня возможны осадки." if rain_slots > 0 else "Существенных осадков по прогнозу не видно."
    slot_note = ""
    if best_slot and " " in best_slot:
        try:
            slot_dt = datetime.strptime(best_slot, "%Y-%m-%d %H:%M:%S")
            slot_note = f"Лучшее окно для выхода — около {slot_dt.strftime('%H:%M')}."
        except ValueError:
            slot_note = ""
    pressure_note = ""
    if pressure_values:
        avg_pressure = sum(pressure_values) / len(pressure_values)
        pressure_mmhg = round(avg_pressure * 0.75006)
        if avg_pressure <= 1000:
            pressure_note = f"Давление около {pressure_mmhg} мм рт. ст., заметно ниже обычного."
        elif avg_pressure >= 1025:
            pressure_note = f"Давление около {pressure_mmhg} мм рт. ст., заметно выше обычного."
        else:
            pressure_note = "Давление в пределах нормы."
    notes = [rain_note]
    if slot_note:
        notes.append(slot_note)
    if pressure_note:
        notes.append(pressure_note)
    notes.append("В течение дня температура может заметно меняться, поэтому перед выходом лучше быстро проверить прогноз ещё раз.")
    return f"По {city_label}: {' '.join(notes)}"


def _range_text(values: list[float], suffix: str = "") -> str:
    if not values:
        return "н/д"
    min_value = min(values)
    max_value = max(values)
    if round(min_value, 1) == round(max_value, 1):
        return f"{min_value:.1f}{suffix}"
    return f"{min_value:.1f}...{max_value:.1f}{suffix}"


def _dominant_description(day_items: list[dict]) -> str:
    descriptions: dict[str, int] = {}
    for item in day_items:
        weather_list = item.get("weather") if isinstance(item, dict) else None
        weather_item = weather_list[0] if isinstance(weather_list, list) and weather_list and isinstance(weather_list[0], dict) else {}
        description = normalize_weather_description(weather_item.get("description") or "без описания")
        descriptions[description] = descriptions.get(description, 0) + 1
    if not descriptions:
        return "без описания"
    return max(descriptions, key=descriptions.get)


def _tomorrow_pressure_note(pressure_values: list[float]) -> str:
    if not pressure_values:
        return "Данные по давлению ограничены."
    min_pressure = min(pressure_values)
    max_pressure = max(pressure_values)
    avg_pressure = sum(pressure_values) / len(pressure_values)
    min_mmhg = round(min_pressure * 0.75006)
    max_mmhg = round(max_pressure * 0.75006)
    avg_mmhg = round(avg_pressure * 0.75006)
    if max_mmhg - min_mmhg <= 2:
        pressure_text = f"{avg_mmhg} мм рт. ст."
    else:
        pressure_text = f"{min_mmhg}-{max_mmhg} мм рт. ст."
    if avg_pressure <= 1000:
        return f"Давление: {pressure_text}, ниже обычного."
    if avg_pressure >= 1025:
        return f"Давление: {pressure_text}, выше обычного."
    return f"Давление: {pressure_text}, в пределах нормы."


def _tomorrow_wind_note(wind_speeds: list[float]) -> str:
    if not wind_speeds:
        return "Данные по ветру ограничены."
    max_wind = max(wind_speeds)
    if max_wind < 3:
        return "Ветер слабый."
    if max_wind <= 5:
        return "Ветер умеренный."
    if max_wind < 8:
        return "Ветер заметный, но не сильный."
    return "Ветер сильный."


def fallback_tomorrow_forecast(city_label: str, day_items: list[dict]) -> str:
    if not isinstance(day_items, list) or not day_items:
        return f"По {city_label} пока недостаточно данных, чтобы пояснить прогноз на завтра."
    temps: list[float] = []
    feels_like_values: list[float] = []
    pressure_values: list[float] = []
    wind_speeds: list[float] = []
    precip_slots = 0
    for item in day_items:
        main_data = item.get("main", {}) if isinstance(item, dict) else {}
        wind_data = item.get("wind", {}) if isinstance(item, dict) else {}
        weather_list = item.get("weather") if isinstance(item, dict) else None
        weather_item = weather_list[0] if isinstance(weather_list, list) and weather_list and isinstance(weather_list[0], dict) else {}
        weather_desc = str(weather_item.get("description") or "").lower()
        if any(x in weather_desc for x in ("дожд", "лив", "гроза", "снег")):
            precip_slots += 1
        temp = main_data.get("temp")
        feels_like = main_data.get("feels_like")
        pressure = main_data.get("pressure")
        wind_speed = wind_data.get("speed")
        if isinstance(temp, (int, float)):
            temps.append(float(temp))
        if isinstance(feels_like, (int, float)):
            feels_like_values.append(float(feels_like))
        if isinstance(pressure, (int, float)):
            pressure_values.append(float(pressure))
        if isinstance(wind_speed, (int, float)):
            wind_speeds.append(float(wind_speed))

    dominant = _dominant_description(day_items).lower()
    if "снег" in dominant:
        precip_note = "Ожидается снег." if precip_slots else "Существенных осадков не ожидается."
    elif any(x in dominant for x in ("дожд", "лив", "гроза", "морось")):
        precip_note = f"Ожидается {dominant}." if precip_slots else "Существенных осадков не ожидается."
    else:
        precip_note = "Возможны осадки." if precip_slots else "Существенных осадков не ожидается."
    return (
        f"Завтра в локации {city_label} ожидается {_dominant_description(day_items)}. "
        f"Температура будет примерно {_range_text(temps, '°C')}, "
        f"по ощущениям {_range_text(feels_like_values, '°C')}. "
        f"{precip_note} {_tomorrow_wind_note(wind_speeds)} {_tomorrow_pressure_note(pressure_values)}"
    )


def fallback_today_forecast(city_label: str, day_items: list[dict], *, is_remaining_day: bool = False) -> str:
    if not isinstance(day_items, list) or not day_items:
        period_hint = "сегодня" if is_remaining_day else "на сегодня"
        return f"По {city_label} пока недостаточно данных, чтобы пояснить прогноз {period_hint}."
    temps: list[float] = []
    feels_like_values: list[float] = []
    pressure_values: list[float] = []
    wind_speeds: list[float] = []
    precip_slots = 0
    for item in day_items:
        main_data = item.get("main", {}) if isinstance(item, dict) else {}
        wind_data = item.get("wind", {}) if isinstance(item, dict) else {}
        weather_list = item.get("weather") if isinstance(item, dict) else None
        weather_item = weather_list[0] if isinstance(weather_list, list) and weather_list and isinstance(weather_list[0], dict) else {}
        weather_desc = str(weather_item.get("description") or "").lower()
        if any(x in weather_desc for x in ("дожд", "лив", "гроза", "снег")):
            precip_slots += 1
        temp = main_data.get("temp")
        feels_like = main_data.get("feels_like")
        pressure = main_data.get("pressure")
        wind_speed = wind_data.get("speed")
        if isinstance(temp, (int, float)):
            temps.append(float(temp))
        if isinstance(feels_like, (int, float)):
            feels_like_values.append(float(feels_like))
        if isinstance(pressure, (int, float)):
            pressure_values.append(float(pressure))
        if isinstance(wind_speed, (int, float)):
            wind_speeds.append(float(wind_speed))

    prefix = "Сегодня"
    dominant = _dominant_description(day_items).lower()
    if "снег" in dominant:
        precip_note = "Ожидается снег." if precip_slots else "Существенных осадков не ожидается."
    elif any(x in dominant for x in ("дожд", "лив", "гроза", "морось")):
        precip_note = f"Ожидается {dominant}." if precip_slots else "Существенных осадков не ожидается."
    else:
        precip_note = "Возможны осадки." if precip_slots else "Существенных осадков не ожидается."
    return (
        f"{prefix} в локации {city_label} ожидается {_dominant_description(day_items)}. "
        f"Температура будет примерно {_range_text(temps, '°C')}, "
        f"по ощущениям {_range_text(feels_like_values, '°C')}. "
        f"{precip_note} {_tomorrow_wind_note(wind_speeds)} {_tomorrow_pressure_note(pressure_values)}"
    )


def fallback_details(city_label: str, weather_data: dict, air_quality_data: dict | None) -> str:
    main_data = weather_data.get("main", {}) if isinstance(weather_data, dict) else {}
    wind_data = weather_data.get("wind", {}) if isinstance(weather_data, dict) else {}
    humidity = main_data.get("humidity")
    visibility = weather_data.get("visibility") if isinstance(weather_data, dict) else None
    wind_speed = wind_data.get("speed")
    pressure_note = get_pressure_note_hpa(main_data.get("pressure"))
    pm25 = air_quality_data.get("pm2_5") if isinstance(air_quality_data, dict) else None
    humidity_note = (
        "Влажность высокая, поэтому воздух может ощущаться тяжёлым."
        if isinstance(humidity, (int, float)) and humidity >= 75
        else "Влажность сейчас в комфортном диапазоне."
    )
    if isinstance(wind_speed, (int, float)):
        ws = float(wind_speed)
        weather_list = weather_data.get("weather", []) if isinstance(weather_data, dict) else []
        description = normalize_weather_description((weather_list[0].get("description") if weather_list else "") or "")
        desc_lower = str(description).lower()
        temp = main_data.get("temp")
        if ws < 3:
            wind_note = "Ветер слабый, почти не мешает."
        elif ws <= 5:
            wind_note = "Ветер умеренный: заметный, но без сильного влияния на комфорт."
        elif ws < 8:
            if any(x in desc_lower for x in ("дожд", "лив", "гроза", "снег")) or (
                isinstance(temp, (int, float)) and float(temp) < 8
            ):
                wind_note = "Ветер заметный: при осадках или прохладе может быть менее комфортно."
            else:
                wind_note = "Ветер заметный и ощущается сильнее обычного."
        else:
            wind_note = "Ветер сильный и заметно влияет на комфорт."
    else:
        wind_note = "Данные о ветре ограничены."
    visibility_note = (
        f"Видимость примерно {int(visibility)} м." if isinstance(visibility, (int, float)) else "Данные по видимости ограничены."
    )
    if isinstance(pm25, (int, float)):
        air_note = (
            "Качество воздуха хорошее: пыль и основные загрязнители на низком уровне."
            if pm25 <= 35
            else "Качество воздуха сейчас ниже комфортного."
        )
    else:
        air_note = "Данные о качестве воздуха сейчас неполные."
    return (
        f"По {city_label}: {humidity_note} {wind_note} {visibility_note} {air_note} "
        f"{pressure_note + ' ' if pressure_note else ''}"
        "Сейчас больше всего влияют влажность, ветер, видимость и качество воздуха."
    )
def fallback_weather_alert(location_label: str, alert_payload: dict) -> str:
    payload = alert_payload if isinstance(alert_payload, dict) else {}
    slot_local = str(payload.get("slot_local") or "").strip()
    description = normalize_weather_description(payload.get("description")).lower()
    event_type = str(payload.get("event_type") or "").strip().lower()
    temperature = payload.get("temperature")
    feels_like = payload.get("feels_like")
    wind_speed = payload.get("wind_speed")
    precip_probability = payload.get("precip_probability")
    if any(x in description for x in ("дожд", "лив", "гроза", "снег")) or event_type == "precipitation":
        when = f"К {slot_local} " if slot_local else "Скоро "
        tail = ""
        if isinstance(precip_probability, (int, float)) and float(precip_probability) >= 0.6:
            tail = " Осадки выглядят вероятными."
        wind_tail = ""
        if isinstance(wind_speed, (int, float)):
            ws = float(wind_speed)
            if ws < 3:
                wind_tail = " Ветер слабый."
            elif ws <= 5:
                wind_tail = " Ветер умеренный."
            elif ws < 8:
                wind_tail = " Ветер заметный."
            else:
                wind_tail = " Ветер сильный."
        return (
            f"{when}ожидаются осадки, пригодятся зонт или непромокаемая верхняя одежда."
            f"{tail}{wind_tail}"
        ).strip()
    if event_type == "wind" or (isinstance(wind_speed, (int, float)) and float(wind_speed) >= 8):
        speed_hint = f" до {round(float(wind_speed), 1)} м/с" if isinstance(wind_speed, (int, float)) else ""
        return (
            f"К {slot_local} ветер усилится{speed_hint}."
            if slot_local
            else f"Ветер усилится{speed_hint}."
        ) + " На улице может ощущаться прохладнее из-за ветра."
    if event_type == "temperature_drop":
        feels_note = f" По ощущениям около {round(float(feels_like), 1)}°C." if isinstance(feels_like, (int, float)) else ""
        return ("Температура снизится, лучше взять дополнительный верхний слой одежды." f"{feels_note}").strip()
    if isinstance(temperature, (int, float)) and isinstance(feels_like, (int, float)):
        if float(feels_like) <= float(temperature) - 2.0:
            return (
                f"К {slot_local} может ощущаться прохладнее фактической температуры, лучше одеться теплее."
                if slot_local
                else "Может ощущаться прохладнее фактической температуры, лучше одеться теплее."
            )
    if slot_local and description:
        return f"К {slot_local} ожидается {description}, стоит учесть это при выходе."
    if description:
        return f"Ожидается {description}, стоит заранее учесть это при выходе."
    return ""


def postprocess_weather_alert_text(text: str) -> str:
    normalized = " ".join(str(text or "").split())
    if not normalized:
        return ""
    replacements = {
        "короткий маршрут под крышей": "короткий выход",
        "маршрут под крышей": "короткий выход",
        "маршрут под укрытием": "выход с учётом погоды",
        "идти под крышей": "сократить время на улице",
        "ветер усиливает холод": "ветер делает воздух прохладнее",
        "ветер усиливает сырость": "при осадках на улице может быть менее комфортно",
        "сильно влияет на комфорт": "заметно влияет на комфорт",
    }
    for src, dst in replacements.items():
        normalized = re.sub(rf"\b{re.escape(src)}\b", dst, normalized, flags=re.IGNORECASE)
    return normalized.strip()


def fallback_compare_forecast_day(service, payload_1: dict, payload_2: dict, selected_day: str) -> str:
    _ = selected_day
    profile_1 = service._build_forecast_day_risk_profile(payload_1)
    profile_2 = service._build_forecast_day_risk_profile(payload_2)
    verdict = service._build_forecast_compare_verdict(profile_1, profile_2)
    return service._build_deterministic_compare_forecast_day_text(profile_1, profile_2, verdict)

