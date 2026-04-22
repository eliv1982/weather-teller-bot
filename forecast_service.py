from datetime import datetime


def group_forecast_by_day(forecast_items: list[dict]) -> dict[str, list[dict]]:
    """Группирует прогноз по календарным дням в формате ДД.ММ."""
    grouped: dict[str, list[dict]] = {}
    for item in forecast_items:
        dt_txt = item.get("dt_txt", "")
        if not dt_txt:
            continue
        date_part = dt_txt.split(" ")[0]
        try:
            day_key = datetime.strptime(date_part, "%Y-%m-%d").strftime("%d.%m")
        except ValueError:
            continue
        grouped.setdefault(day_key, []).append(item)
    return grouped


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
