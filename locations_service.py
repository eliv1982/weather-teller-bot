import logging
import time
from math import asin, cos, radians, sin, sqrt

from alerts_service import ensure_notifications_defaults
from formatters import format_alerts_status, format_weather_response
from keyboards import alerts_menu, build_ai_action_keyboard, main_menu
from postgres_storage import load_user, save_user
from weather_app import build_location_label, get_current_weather


logger = logging.getLogger(__name__)


def normalize_text(value: object) -> str:
    """Нормализует текст для устойчивого сравнения названий/подписей локаций."""
    text = str(value or "").strip().lower().replace("ё", "е")
    text = " ".join(text.split())
    if "—" in text:
        text = text.split("—")[-1].strip()
    return text


def normalize_saved_location_name(value: object) -> str:
    """Совместимое имя-алиас для старых вызовов."""
    return normalize_text(value)


def calculate_distance_km(lat_1: float, lon_1: float, lat_2: float, lon_2: float) -> float:
    """Считает расстояние между точками по формуле гаверсинусов."""
    earth_radius_km = 6371.0
    d_lat = radians(lat_2 - lat_1)
    d_lon = radians(lon_2 - lon_1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat_1)) * cos(radians(lat_2)) * sin(d_lon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return earth_radius_km * c


def _extract_label_parts(label: object) -> tuple[str, str, str]:
    """Разбирает label вида 'Город (Страна, Регион)' в нормализованные части."""
    raw = str(label or "").strip()
    if not raw:
        return "", "", ""
    city_raw = raw
    country_raw = ""
    state_raw = ""
    if "(" in raw and ")" in raw:
        city_raw = raw.split("(", 1)[0].strip()
        inside = raw.split("(", 1)[1].rsplit(")", 1)[0]
        parts = [p.strip() for p in inside.split(",")]
        if parts:
            country_raw = parts[0]
        if len(parts) > 1:
            state_raw = parts[1]
    return (
        normalize_saved_location_name(city_raw),
        normalize_saved_location_name(country_raw),
        normalize_saved_location_name(state_raw),
    )


def find_duplicate_saved_location_by_geo(
    saved_locations: list[dict],
    *,
    label: str,
    lat: float,
    lon: float,
    distance_threshold_km: float = 2.0,
) -> dict | None:
    """Ищет дубль локации по близости координат или по нормализованному label."""
    new_city, new_country, new_state = _extract_label_parts(label)
    for item in saved_locations:
        if not isinstance(item, dict):
            continue
        item_lat = item.get("lat")
        item_lon = item.get("lon")
        if isinstance(item_lat, (int, float)) and isinstance(item_lon, (int, float)):
            distance_km = calculate_distance_km(float(item_lat), float(item_lon), float(lat), float(lon))
            if distance_km < distance_threshold_km:
                return item

        item_city, item_country, item_state = _extract_label_parts(item.get("label"))
        if new_city and item_city and new_city == item_city:
            if new_country and item_country and new_country != item_country:
                continue
            if new_state and item_state and new_state != item_state:
                continue
            return item
    return None


def find_duplicate_saved_location_by_title(saved_locations: list[dict], *, title: str) -> dict | None:
    """Ищет дубль по нормализованному title."""
    target = normalize_text(title)
    if not target:
        return None
    for item in saved_locations:
        if not isinstance(item, dict):
            continue
        item_title = normalize_text(item.get("title"))
        if item_title and item_title == target:
            return item
    return None


def format_saved_location_item(item: dict) -> str:
    """Формирует строку 'title — label' для UX-сообщений."""
    title = str(item.get("title") or "").strip()
    label = str(item.get("label") or "").strip()
    if title and label:
        return f"{title} — {label}"
    return title or label or "Локация"


def find_duplicate_saved_location(
    saved_locations: list[dict],
    *,
    label: str,
    lat: float,
    lon: float,
    distance_threshold_km: float = 2.0,
) -> dict | None:
    """Совместимый wrapper: ищет геодубль."""
    return find_duplicate_saved_location_by_geo(
        saved_locations,
        label=label,
        lat=lat,
        lon=lon,
        distance_threshold_km=distance_threshold_km,
    )


def save_saved_location_item(user_id: int, title: str, label: str, lat: float, lon: float) -> dict:
    """Сохраняет новую локацию и возвращает статус операции."""
    user_data = load_user(user_id)
    saved_locations = user_data.get("saved_locations", [])
    if not isinstance(saved_locations, list):
        saved_locations = []

    duplicate_location = find_duplicate_saved_location_by_geo(
        saved_locations,
        label=label,
        lat=float(lat),
        lon=float(lon),
    )
    if duplicate_location is not None:
        return {"status": "duplicate_location", "item": duplicate_location}

    duplicate_title = find_duplicate_saved_location_by_title(saved_locations, title=title)
    if duplicate_title is not None:
        return {"status": "duplicate_title", "item": duplicate_title}

    location_id = f"loc_{int(time.time() * 1000)}_{len(saved_locations) + 1}"
    new_item = {
        "id": location_id,
        "title": title,
        "label": label,
        "lat": float(lat),
        "lon": float(lon),
    }
    saved_locations.append(new_item)

    user_data["saved_locations"] = saved_locations
    save_user(user_id, user_data)
    return {"status": "added", "item": new_item}


def save_user_location_from_geocode_item(
    user_id: int,
    location_item: dict,
    *,
    load_user_fn=load_user,
    save_user_fn=save_user,
) -> bool:
    """Сохраняет city, lat, lon из элемента геокодинга в данные пользователя. Возвращает True при успехе."""
    lat = location_item.get("lat")
    lon = location_item.get("lon")
    city_label = location_item.get("label") or build_location_label(location_item, show_coords=False)

    if lat is None or lon is None:
        return False

    user_data = load_user_fn(user_id)
    user_data["city"] = city_label
    user_data["lat"] = lat
    user_data["lon"] = lon
    save_user_fn(user_id, user_data)
    return True


def complete_current_weather_from_location(
    bot,
    chat_id: int,
    user_id: int,
    location_item: dict,
    *,
    user_states: dict,
    current_location_choices: dict,
    ai_current_snapshots: dict | None = None,
    create_ai_snapshot_id_fn=None,
    cleanup_ai_snapshots_fn=None,
    load_user_fn=load_user,
    save_user_fn=save_user,
) -> None:
    """Загружает текущую погоду по выбранной локации, сохраняет данные и отправляет ответ."""
    lat = location_item.get("lat")
    lon = location_item.get("lon")
    city_label = location_item.get("label") or build_location_label(location_item, show_coords=False)

    if lat is None or lon is None:
        logger.warning("У локации нет координат для пользователя %s.", user_id)
        user_states.pop(user_id, None)
        current_location_choices.pop(user_id, None)
        bot.send_message(
            chat_id,
            "Не удалось получить данные о погоде. Попробуй позже.",
            reply_markup=main_menu(),
        )
        return

    weather = get_current_weather(lat, lon)
    if not weather:
        logger.warning(
            "Не удалось получить данные о погоде для пользователя %s (lat: %s, lon: %s).",
            user_id,
            lat,
            lon,
        )
        user_states.pop(user_id, None)
        current_location_choices.pop(user_id, None)
        bot.send_message(
            chat_id,
            "Не удалось получить данные о погоде. Попробуй позже.",
            reply_markup=main_menu(),
        )
        return

    if not save_user_location_from_geocode_item(
        user_id,
        location_item,
        load_user_fn=load_user_fn,
        save_user_fn=save_user_fn,
    ):
        user_states.pop(user_id, None)
        current_location_choices.pop(user_id, None)
        bot.send_message(
            chat_id,
            "Не удалось сохранить локацию. Попробуй позже.",
            reply_markup=main_menu(),
        )
        return

    answer = format_weather_response(city_label, weather)
    logger.info(
        "Успешно получена погода для пользователя %s: %s (lat: %s, lon: %s).",
        user_id,
        city_label,
        lat,
        lon,
    )
    user_states.pop(user_id, None)
    current_location_choices.pop(user_id, None)
    callback_data = "ai_current_explain"
    if ai_current_snapshots is not None and callable(create_ai_snapshot_id_fn):
        snapshot_id = str(create_ai_snapshot_id_fn(user_id))
        ai_current_snapshots[snapshot_id] = {
            "user_id": user_id,
            "city_label": city_label,
            "weather": weather,
            "created_at": time.time(),
        }
        if callable(cleanup_ai_snapshots_fn):
            cleanup_ai_snapshots_fn()
        callback_data = f"ai_current_explain:{snapshot_id}"
    bot.send_message(chat_id, answer, reply_markup=main_menu())
    bot.send_message(
        chat_id,
        "✨ Хочешь короткий и понятный разбор?",
        reply_markup=build_ai_action_keyboard("✨ Объяснить по-человечески", callback_data),
    )


def complete_alerts_location_from_item(
    bot,
    chat_id: int,
    user_id: int,
    location_item: dict,
    *,
    user_states: dict,
    alerts_location_choices: dict,
    enable_notifications: bool = False,
    success_text: str = "✅ Локация для уведомлений обновлена.",
    load_user_fn=load_user,
    save_user_fn=save_user,
) -> None:
    """Сохраняет локацию из геокодинга для уведомлений и показывает статус."""
    if not save_user_location_from_geocode_item(
        user_id,
        location_item,
        load_user_fn=load_user_fn,
        save_user_fn=save_user_fn,
    ):
        logger.warning("Не удалось сохранить локацию уведомлений для пользователя %s.", user_id)
        alerts_location_choices.pop(user_id, None)
        user_states[user_id] = "alerts_menu"
        bot.send_message(
            chat_id,
            "Не удалось сохранить локацию. Попробуй позже.",
            reply_markup=alerts_menu(),
        )
        return

    alerts_location_choices.pop(user_id, None)
    user_states[user_id] = "alerts_menu"
    user_data = ensure_notifications_defaults(load_user_fn(user_id))
    if enable_notifications:
        user_data["notifications"]["enabled"] = True
        save_user_fn(user_id, user_data)
    bot.send_message(
        chat_id,
        success_text + "\n\n" + format_alerts_status(user_data),
        reply_markup=alerts_menu(),
    )
