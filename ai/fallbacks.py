"""Deterministic fallback text helpers extracted from AiWeatherService."""

from datetime import datetime
import re


def fallback_current(city_label: str, weather_data: dict) -> str:
    main_data = weather_data.get("main", {}) if isinstance(weather_data, dict) else {}
    weather_list = weather_data.get("weather", []) if isinstance(weather_data, dict) else []
    wind_data = weather_data.get("wind", {}) if isinstance(weather_data, dict) else {}
    temp = main_data.get("temp")
    feels_like = main_data.get("feels_like")
    description = (weather_list[0].get("description") if weather_list else "") or "без описания"
    wind_speed = wind_data.get("speed")
    desc_lower = str(description).lower()
    umbrella = (
        "Лучше взять зонт на всякий случай."
        if any(x in desc_lower for x in ("дожд", "лив", "гроза", "снег"))
        else "Скорее всего, можно обойтись без зонта."
    )
    if isinstance(feels_like, (int, float)):
        if feels_like <= 0:
            clothes = "Лучше одеться заметно теплее."
        elif feels_like <= 12:
            clothes = "Лучше накинуть что-то тёплое."
        else:
            clothes = "Можно выбрать более лёгкую одежду."
    else:
        clothes = "Одежду лучше выбрать по ощущениям на месте."
    comfort = (
        "На улице в целом довольно комфортно."
        if isinstance(temp, (int, float)) and -5 <= temp <= 25
        else "На улице может быть не слишком комфортно."
    )
    wind_note = ""
    if isinstance(wind_speed, (int, float)):
        ws = float(wind_speed)
        if ws < 3:
            wind_note = " Ветер слабый, почти не мешает."
        elif ws <= 5:
            wind_note = " Ветер умеренный: заметный, но без сильного влияния на комфорт."
        elif ws < 8:
            if any(x in desc_lower for x in ("дожд", "лив", "гроза", "снег")) or (
                isinstance(feels_like, (int, float)) and float(feels_like) < 8
            ):
                wind_note = " Ветер заметный: при осадках или прохладе может быть менее комфортно."
            else:
                wind_note = " Ветер заметный, на открытых участках может ощущаться сильнее."
        else:
            wind_note = " Ветер сильный и заметно влияет на комфорт на улице."
    return (
        f"Сейчас в {city_label}: {description}, температура {temp if temp is not None else 'н/д'}°C, "
        f"ощущается как {feels_like if feels_like is not None else 'н/д'}°C.{wind_note} "
        f"{umbrella} {clothes} {comfort}"
    )


def fallback_day_forecast(city_label: str, day_items: list[dict]) -> str:
    if not isinstance(day_items, list) or not day_items:
        return f"По {city_label} пока недостаточно данных, чтобы дать понятную рекомендацию на день."
    rain_slots = 0
    best_slot = None
    best_temp = None
    for item in day_items:
        weather_list = item.get("weather")
        weather_item = weather_list[0] if isinstance(weather_list, list) and weather_list and isinstance(weather_list[0], dict) else {}
        weather_desc = str(weather_item.get("description", "")).lower()
        if any(x in weather_desc for x in ("дожд", "лив", "гроза", "снег")):
            rain_slots += 1
        temp = item.get("main", {}).get("temp")
        dt_txt = str(item.get("dt_txt") or "")
        if isinstance(temp, (int, float)) and (best_temp is None or temp > best_temp):
            best_temp = float(temp)
            best_slot = dt_txt
    rain_note = (
        "В течение дня возможны осадки, зонт лучше взять с собой."
        if rain_slots > 0
        else "Существенных осадков по прогнозу не видно."
    )
    slot_note = ""
    if best_slot and " " in best_slot:
        try:
            slot_dt = datetime.strptime(best_slot, "%Y-%m-%d %H:%M:%S")
            slot_note = f"Лучшее окно для выхода — около {slot_dt.strftime('%H:%M')}."
        except ValueError:
            slot_note = ""
    return (
        f"По {city_label}: {rain_note} {slot_note} В течение дня температура может заметно меняться, "
        "поэтому перед выходом лучше быстро проверить прогноз ещё раз."
    ).strip()


def fallback_details(city_label: str, weather_data: dict, air_quality_data: dict | None) -> str:
    main_data = weather_data.get("main", {}) if isinstance(weather_data, dict) else {}
    wind_data = weather_data.get("wind", {}) if isinstance(weather_data, dict) else {}
    humidity = main_data.get("humidity")
    visibility = weather_data.get("visibility") if isinstance(weather_data, dict) else None
    wind_speed = wind_data.get("speed")
    pm25 = air_quality_data.get("pm2_5") if isinstance(air_quality_data, dict) else None
    humidity_note = (
        "Влажность высокая, поэтому воздух может ощущаться тяжёлым."
        if isinstance(humidity, (int, float)) and humidity >= 75
        else "Влажность сейчас в комфортном диапазоне."
    )
    if isinstance(wind_speed, (int, float)):
        ws = float(wind_speed)
        weather_list = weather_data.get("weather", []) if isinstance(weather_data, dict) else []
        description = (weather_list[0].get("description") if weather_list else "") or ""
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
                wind_note = "Ветер заметный, на открытых участках ощущается сильнее."
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
        "Если планируешь долгую прогулку, ориентируйся в первую очередь на эти факторы."
    )


def fallback_compare_current(service, payload_1: dict, payload_2: dict) -> str:
    city_1_label = str(payload_1.get("city_label") or "Локация 1")
    city_2_label = str(payload_2.get("city_label") or "Локация 2")
    name_1 = service._get_short_location_name(city_1_label)
    name_2 = service._get_short_location_name(city_2_label)
    temp_1 = payload_1.get("temperature")
    temp_2 = payload_2.get("temperature")
    wind_1 = payload_1.get("wind_speed")
    wind_2 = payload_2.get("wind_speed")
    hum_1 = payload_1.get("humidity")
    hum_2 = payload_2.get("humidity")
    desc_1 = str(payload_1.get("description") or "").lower()
    desc_2 = str(payload_2.get("description") or "").lower()
    rain_markers = ("дожд", "лив", "гроза", "снег")
    precip_1 = any(m in desc_1 for m in rain_markers)
    precip_2 = any(m in desc_2 for m in rain_markers)

    def _signed(a: object, b: object) -> float | None:
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            return float(a) - float(b)
        return None

    d_temp = _signed(temp_1, temp_2)
    d_wind = _signed(wind_1, wind_2)
    d_hum = _signed(hum_1, hum_2)
    warmer = 1 if d_temp is not None and abs(d_temp) >= 1.0 and d_temp > 0 else (2 if d_temp is not None and abs(d_temp) >= 1.0 else None)
    calmer = 1 if d_wind is not None and abs(d_wind) >= 1.0 and d_wind < 0 else (2 if d_wind is not None and abs(d_wind) >= 1.0 else None)
    drier = 1 if d_hum is not None and abs(d_hum) >= 8 and d_hum < 0 else (2 if d_hum is not None and abs(d_hum) >= 8 else None)
    no_rain = 2 if (precip_1 and not precip_2) else (1 if (precip_2 and not precip_1) else None)
    signals = [s for s in (warmer, calmer, drier, no_rain) if s is not None]
    adv_1 = sum(1 for s in signals if s == 1)
    adv_2 = sum(1 for s in signals if s == 2)
    near_identical = (
        no_rain is None
        and (d_temp is None or abs(d_temp) < 1.0)
        and (d_wind is None or abs(d_wind) < 1.5)
        and (d_hum is None or abs(d_hum) < 10)
    )
    clear_winner = None
    if not near_identical:
        if adv_1 >= 2 and adv_2 == 0:
            clear_winner = 1
        elif adv_2 >= 2 and adv_1 == 0:
            clear_winner = 2
    if clear_winner is not None:
        return service._render_compare_current_clear(
            clear_winner, city_1_label, city_2_label, name_1, name_2, warmer, calmer, drier, no_rain
        )
    if near_identical:
        return service._render_compare_current_near_identical(name_1, name_2, d_wind, d_hum)
    return service._render_compare_current_mixed(
        city_1_label, city_2_label, name_1, name_2, warmer, calmer, drier, no_rain
    )


def fallback_weather_alert(location_label: str, alert_payload: dict) -> str:
    payload = alert_payload if isinstance(alert_payload, dict) else {}
    slot_local = str(payload.get("slot_local") or "").strip()
    description = str(payload.get("description") or "").strip().lower()
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
            f"{when}ожидаются осадки, лучше взять зонт и непромокаемую верхнюю одежду."
            " Если планируешь прогулку, лучше выбрать короткий маршрут или перенести её на более сухое время."
            f"{tail}{wind_tail}"
        ).strip()
    if event_type == "wind" or (isinstance(wind_speed, (int, float)) and float(wind_speed) >= 8):
        speed_hint = f" до {round(float(wind_speed), 1)} м/с" if isinstance(wind_speed, (int, float)) else ""
        return (
            f"К {slot_local} ветер усилится{speed_hint}, на открытых участках будет менее комфортно."
            if slot_local
            else f"Ветер усилится{speed_hint}, на открытых участках будет менее комфортно."
        ) + " Для прогулки лучше идти там, где меньше открытых участков."
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
        return f"К {slot_local} ожидается {description}, лучше скорректировать маршрут и одежду под условия."
    if description:
        return f"Ожидается {description}, лучше заранее учесть это в планах на выход."
    return ""


def postprocess_weather_alert_text(text: str) -> str:
    normalized = " ".join(str(text or "").split())
    if not normalized:
        return ""
    replacements = {
        "короткий маршрут под крышей": "короткий маршрут",
        "маршрут под крышей": "короткий маршрут",
        "маршрут под укрытием": "маршрут, где меньше открытых участков",
        "идти под крышей": "идти там, где меньше открытых участков",
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

