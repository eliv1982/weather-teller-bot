import logging
import time

from alerts_service import ensure_notifications_defaults
from formatters import format_alerts_status, format_weather_response
from keyboards import alerts_menu, build_ai_action_keyboard, main_menu
from postgres_storage import load_user, save_user
from weather_app import build_location_label, get_current_weather


logger = logging.getLogger(__name__)


def save_saved_location_item(user_id: int, title: str, label: str, lat: float, lon: float) -> None:
    """Сохраняет локацию в список пользователя или обновляет title у дубля по координатам."""
    user_data = load_user(user_id)
    saved_locations = user_data.get("saved_locations", [])
    if not isinstance(saved_locations, list):
        saved_locations = []

    existing_location = None
    for item in saved_locations:
        if not isinstance(item, dict):
            continue
        item_lat = item.get("lat")
        item_lon = item.get("lon")
        if item_lat is None or item_lon is None:
            continue
        if abs(float(item_lat) - float(lat)) < 1e-6 and abs(float(item_lon) - float(lon)) < 1e-6:
            existing_location = item
            break

    if existing_location is not None:
        existing_location["title"] = title
        existing_location["label"] = label
        existing_location["lat"] = float(lat)
        existing_location["lon"] = float(lon)
    else:
        location_id = f"loc_{int(time.time() * 1000)}_{len(saved_locations) + 1}"
        saved_locations.append(
            {
                "id": location_id,
                "title": title,
                "label": label,
                "lat": float(lat),
                "lon": float(lon),
            }
        )

    user_data["saved_locations"] = saved_locations
    save_user(user_id, user_data)


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
