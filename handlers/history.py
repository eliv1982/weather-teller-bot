from telebot import types

from coordinates_parser import parse_coordinates
from location_query_assist import find_locations_with_assist
from weather_history_service import parse_history_date_input
from .states import (
    WAITING_HISTORY_CITY,
    WAITING_HISTORY_COORDS,
    WAITING_HISTORY_CUSTOM_DATE,
    WAITING_HISTORY_DATE_PICK,
    WAITING_HISTORY_GEO,
    WAITING_HISTORY_PICK,
    WAITING_HISTORY_SAVED_PICK,
)


def handle_history_text(
    message: types.Message,
    user_id: int,
    state: str | None,
    *,
    ctx,
    session_store,
    prepare_weather_history_by_coordinates,
    send_weather_history_by_date,
) -> bool:
    """Handles location and date input for the archive weather flow."""
    if state == WAITING_HISTORY_CITY:
        query = (message.text or "").strip()
        normalized_query = query.translate({1105: 1077, 1025: 1045})
        if normalized_query == "⭐ Из сохраненных":
            user_data = ctx.load_user(user_id)
            saved_locations = user_data.get("saved_locations", [])
            if not isinstance(saved_locations, list) or not saved_locations:
                ctx.bot.send_message(
                    message.chat.id,
                    "Сохраненных локаций пока нет.",
                    reply_markup=ctx.location_input_menu(has_saved_locations=False),
                )
                return True
            session_store.user_states[user_id] = WAITING_HISTORY_SAVED_PICK
            ctx.bot.send_message(
                message.chat.id,
                "Выбери сохраненную локацию:",
                reply_markup=ctx.build_saved_locations_keyboard(saved_locations, "history_saved_pick"),
            )
            return True
        if query in {"🧭 Координаты", "Ввести координаты"}:
            session_store.user_states[user_id] = WAITING_HISTORY_COORDS
            ctx.bot.send_message(
                message.chat.id,
                "Введи координаты в формате: 55.5789, 37.9051",
                reply_markup=types.ReplyKeyboardRemove(),
            )
            return True
        if query in {"📍 Отправить геолокацию", "📍 Геолокация", "Отправить геолокацию"}:
            session_store.user_states[user_id] = WAITING_HISTORY_GEO
            ctx.bot.send_message(
                message.chat.id,
                "Отправь геолокацию через кнопку ниже.",
                reply_markup=ctx.geo_request_menu(),
            )
            return True

        parsed = parse_coordinates(query)
        if parsed is not None:
            lat, lon = parsed
            location = ctx.get_location_by_coordinates(lat, lon)
            city = ctx.build_location_label(location, show_coords=False) if location else f"Координаты: {lat:.4f}, {lon:.4f}"
            prepare_weather_history_by_coordinates(
                message,
                user_id,
                float(lat),
                float(lon),
                city,
                preferred_city_label=city,
            )
            return True

        if not query:
            ctx.bot.send_message(message.chat.id, "⚠️ Введи название населенного пункта.")
            return True

        search_result = find_locations_with_assist(
            query,
            scenario="history",
            ctx=ctx,
        )
        clarification_text = search_result.get("clarification_text")
        if clarification_text:
            ctx.bot.send_message(message.chat.id, str(clarification_text))
            return True
        locations = search_result.get("locations") if isinstance(search_result, dict) else []
        if not locations:
            ctx.bot.send_message(
                message.chat.id,
                "Не нашла такую локацию. Уточни город, страну или отправь геолокацию.",
            )
            return True

        if len(locations) == 1:
            loc = ctx.build_geocode_item_with_disambiguated_label(locations, 0)
            lat = loc.get("lat")
            lon = loc.get("lon")
            city = loc.get("label") or ctx.build_location_label(loc, show_coords=False)
            if lat is None or lon is None:
                ctx.bot.send_message(
                    message.chat.id,
                    "Не удалось подготовить архивную справку по этой локации. Попробуй позже.",
                    reply_markup=ctx.main_menu(),
                )
                return True
            prepare_weather_history_by_coordinates(
                message,
                user_id,
                float(lat),
                float(lon),
                city,
                preferred_city_label=city,
            )
            return True

        session_store.history_location_choices[user_id] = locations
        session_store.user_states[user_id] = WAITING_HISTORY_PICK
        ctx.bot.send_message(
            message.chat.id,
            "Найдено несколько вариантов. Выбери нужный населенный пункт:",
            reply_markup=ctx.build_scenario_location_choice_keyboard(locations, "history"),
        )
        return True

    if state == WAITING_HISTORY_COORDS:
        parsed = parse_coordinates(message.text or "")
        if parsed is None:
            ctx.bot.send_message(message.chat.id, "⚠️ Некорректный формат. Введи координаты в формате: 55.5789, 37.9051")
            return True
        lat, lon = parsed
        location = ctx.get_location_by_coordinates(lat, lon)
        city = ctx.build_location_label(location, show_coords=False) if location else f"Координаты: {lat:.4f}, {lon:.4f}"
        prepare_weather_history_by_coordinates(
            message,
            user_id,
            float(lat),
            float(lon),
            city,
            preferred_city_label=city,
        )
        return True

    if state == WAITING_HISTORY_PICK:
        if not session_store.history_location_choices.get(user_id):
            session_store.user_states.pop(user_id, None)
            ctx.bot.send_message(
                message.chat.id,
                "⚠️ Список вариантов устарел. Введи населенный пункт заново.",
                reply_markup=ctx.main_menu(),
            )
            return True
        ctx.bot.send_message(
            message.chat.id,
            "Выбери населенный пункт кнопкой ниже или нажми «⬅️ Отмена».",
        )
        return True

    if state == WAITING_HISTORY_SAVED_PICK:
        ctx.bot.send_message(
            message.chat.id,
            "Выбери сохраненную локацию кнопкой ниже или нажми «⬅️ В меню».",
        )
        return True

    if state == WAITING_HISTORY_GEO:
        ctx.bot.send_message(
            message.chat.id,
            "Отправь геолокацию через кнопку ниже.",
            reply_markup=ctx.geo_request_menu(),
        )
        return True

    if state == WAITING_HISTORY_DATE_PICK:
        ctx.bot.send_message(
            message.chat.id,
            "Выбери дату кнопкой ниже или нажми «⬅️ В меню».",
        )
        return True

    if state == WAITING_HISTORY_CUSTOM_DATE:
        target_date, error_message = parse_history_date_input(message.text or "")
        if error_message:
            ctx.bot.send_message(
                message.chat.id,
                f"{error_message}\nНапример: 2026-06-05 или 05.06.2026.",
            )
            return True
        return send_weather_history_by_date(message, user_id, target_date)

    return False
