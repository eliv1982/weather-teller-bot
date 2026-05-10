from datetime import UTC, date, datetime, timedelta


def _extract_slot_timezone_offset(item: dict) -> int:
    """Возвращает timezone offset слота в секундах."""
    if not isinstance(item, dict):
        return 0
    raw = item.get("_timezone_offset")
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float):
        return int(raw)
    return 0


def _extract_slot_utc_datetime(item: dict) -> datetime | None:
    """Возвращает UTC datetime слота без привязки к локальному timezone сервера."""
    if not isinstance(item, dict):
        return None
    raw_dt = item.get("dt")
    if isinstance(raw_dt, (int, float)):
        return datetime.fromtimestamp(int(raw_dt), UTC).replace(tzinfo=None)

    dt_txt = item.get("dt_txt", "")
    if not isinstance(dt_txt, str) or not dt_txt.strip():
        return None
    try:
        # В проекте OpenWeather-shaped dt_txt трактуется как UTC timestamp слота.
        return datetime.strptime(dt_txt, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def get_slot_local_datetime(item: dict) -> datetime | None:
    """Возвращает локальный datetime слота с учётом _timezone_offset."""
    slot_utc = _extract_slot_utc_datetime(item)
    if slot_utc is None:
        return None
    return slot_utc + timedelta(seconds=_extract_slot_timezone_offset(item))


def group_forecast_by_day(forecast_items: list[dict]) -> dict[str, list[dict]]:
    """Группирует прогноз по локальным календарным дням локации в формате ДД.ММ."""
    grouped: dict[str, list[dict]] = {}
    for item in forecast_items:
        local_dt = get_slot_local_datetime(item)
        if local_dt is None:
            continue
        day_key = local_dt.strftime("%d.%m")
        grouped.setdefault(day_key, []).append(item)
    return grouped


def _extract_timezone_offset(grouped: dict[str, list[dict]]) -> int:
    """Возвращает timezone offset локации в секундах из сгруппированного прогноза."""
    for items in grouped.values() if isinstance(grouped, dict) else []:
        if not isinstance(items, list):
            continue
        for item in items:
            offset = _extract_slot_timezone_offset(item)
            if offset:
                return offset
    return 0


def get_forecast_day_by_offset(
    grouped: dict[str, list[dict]],
    *,
    day_offset: int,
    today: date | None = None,
    now_utc: datetime | None = None,
) -> tuple[str, list[dict]] | None:
    """Возвращает прогноз на локальную дату локации с указанным смещением в днях."""
    if not isinstance(grouped, dict):
        return None

    if today is not None:
        base_day = today
    else:
        reference_utc = now_utc or datetime.utcnow()
        base_day = (reference_utc + timedelta(seconds=_extract_timezone_offset(grouped))).date()

    target_key = (base_day + timedelta(days=day_offset)).strftime("%d.%m")
    day_items = grouped.get(target_key)
    if not isinstance(day_items, list) or not day_items:
        return None
    return target_key, day_items


def get_tomorrow_forecast_day(
    grouped: dict[str, list[dict]],
    *,
    today: date | None = None,
    now_utc: datetime | None = None,
) -> tuple[str, list[dict]] | None:
    """Возвращает прогноз на завтра из уже сгруппированного 5-дневного прогноза."""
    return get_forecast_day_by_offset(grouped, day_offset=1, today=today, now_utc=now_utc)


def get_today_forecast_day(
    grouped: dict[str, list[dict]],
    *,
    today: date | None = None,
    now_utc: datetime | None = None,
) -> tuple[str, list[dict]] | None:
    """Возвращает прогноз на сегодня из уже сгруппированного 5-дневного прогноза."""
    return get_forecast_day_by_offset(grouped, day_offset=0, today=today, now_utc=now_utc)


def is_remaining_day_forecast(day_items: list[dict], *, morning_cutoff: str = "06:00") -> bool:
    """Определяет, что доступен прогноз только на оставшуюся часть локального дня."""
    if not isinstance(day_items, list) or not day_items:
        return False
    first_item = day_items[0] if isinstance(day_items[0], dict) else {}
    local_dt = get_slot_local_datetime(first_item)
    if local_dt is None:
        return False
    return local_dt.strftime("%H:%M") >= morning_cutoff


def _forecast_min_temp(day_items: list[dict]) -> float | None:
    """Возвращает минимальную температуру за день."""
    temps = [
        item.get("main", {}).get("temp")
        for item in day_items
        if isinstance(item.get("main", {}).get("temp"), (int, float))
    ]
    return min(temps) if temps else None


def _forecast_max_temp(day_items: list[dict]) -> float | None:
    """Возвращает максимальную температуру за день."""
    temps = [
        item.get("main", {}).get("temp")
        for item in day_items
        if isinstance(item.get("main", {}).get("temp"), (int, float))
    ]
    return max(temps) if temps else None


def _forecast_main_description(day_items: list[dict]) -> str:
    """Определяет самое частое описание погоды за день."""
    descriptions: dict[str, int] = {}
    for item in day_items:
        description = item.get("weather", [{}])[0].get("description", "без описания")
        descriptions[description] = descriptions.get(description, 0) + 1

    if not descriptions:
        return "без описания"

    return max(descriptions, key=descriptions.get)


def format_forecast_day(day: str, day_items: list[dict], city_label: str) -> str:
    """Красиво форматирует прогноз одного дня по интервалам 3 часа."""
    min_temp = _forecast_min_temp(day_items)
    max_temp = _forecast_max_temp(day_items)
    main_description = _forecast_main_description(day_items)

    min_text = f"{min_temp:.1f}" if min_temp is not None else "н/д"
    max_text = f"{max_temp:.1f}" if max_temp is not None else "н/д"

    lines = [
        f"📅 Прогноз на {day} для {city_label}",
        "",
        f"🌡 Минимум: {min_text} °C",
        f"🌡 Максимум: {max_text} °C",
        f"☁️ Чаще всего: {main_description}",
        "",
        "🕒 По времени:",
    ]
    for item in day_items:
        dt_txt = item.get("dt_txt", "")
        time_part = dt_txt.split(" ")[1][:5] if " " in dt_txt else "--:--"
        temp = item.get("main", {}).get("temp")
        description = item.get("weather", [{}])[0].get("description", "без описания")
        temp_text = f"{temp:.1f}" if isinstance(temp, (int, float)) else "н/д"
        lines.append(f"• {time_part} — {temp_text}°C, {description}")
    return "\n".join(lines)
