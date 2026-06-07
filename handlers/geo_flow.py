import time
from typing import Any


def handle_geo_current_weather(
    message: Any,
    user_id: int,
    *,
    ctx: Any,
    session_store: Any,
    ai_current_explain_prefix: str,
    received_log_message: str,
) -> None:
    """Handles current-weather delivery for a Telegram location message."""
    session_store.clear_location_choices(user_id)
    location_data = message.location
    lat = location_data.latitude
    lon = location_data.longitude
    ctx.logger.info(
        received_log_message,
        user_id,
        lat,
        lon,
    )

    weather = ctx.get_current_weather(lat, lon)
    if not weather:
        ctx.logger.warning(
            "Не удалось получить погоду по геолокации для пользователя %s (lat=%s, lon=%s).",
            user_id,
            lat,
            lon,
        )
        session_store.user_states.pop(user_id, None)
        ctx.bot.send_message(
            message.chat.id,
            "Не удалось получить данные о погоде по геолокации. Попробуй позже.",
            reply_markup=ctx.main_menu(),
        )
        return

    location = ctx.get_location_by_coordinates(lat, lon)
    if location:
        city_label = ctx.build_location_label(location, show_coords=False)
    else:
        city_label = "Выбранная геолокация"

    user_data = ctx.load_user(user_id)
    user_data["city"] = city_label
    user_data["lat"] = lat
    user_data["lon"] = lon
    ctx.save_user(user_id, user_data)

    answer = ctx.format_weather_response(city_label, weather)
    ctx.logger.info(
        "Успешно получена погода по геолокации для пользователя %s: %s (lat=%s, lon=%s).",
        user_id,
        city_label,
        lat,
        lon,
    )
    session_store.user_states.pop(user_id, None)
    snapshot_id = session_store.generate_ai_snapshot_id(user_id)
    session_store.ai_current_snapshots[snapshot_id] = {
        "user_id": user_id,
        "city_label": city_label,
        "weather": weather,
        "created_at": time.time(),
    }
    session_store.cleanup_ai_snapshots()
    ctx.bot.send_message(message.chat.id, answer, reply_markup=ctx.main_menu())
    ctx.bot.send_message(
        message.chat.id,
        "✨ Хочешь короткое пояснение погоды?",
        reply_markup=ctx.build_ai_action_keyboard(
            "✨ Короткое пояснение погоды",
            f"{ai_current_explain_prefix}:{snapshot_id}",
        ),
    )
