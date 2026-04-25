import time
from telebot import types

from .states import (
    WAITING_CURRENT_WEATHER_CITY,
    WAITING_CURRENT_WEATHER_COORDS,
    WAITING_CURRENT_WEATHER_GEO,
    WAITING_CURRENT_WEATHER_PICK,
    WAITING_CURRENT_WEATHER_SAVED_PICK,
)
from coordinates_parser import parse_coordinates
from weather_app import get_locations


def handle_current_text(
    message: types.Message,
    user_id: int,
    state: str | None,
    *,
    ctx,
    session_store,
) -> bool:
    """Обрабатывает текстовые состояния сценария текущей погоды."""
    if state == WAITING_CURRENT_WEATHER_CITY:
        query = (message.text or "").strip()
        if query == "⭐ Из сохранённых":
            user_data = ctx.load_user(user_id)
            saved_locations = user_data.get("saved_locations", [])
            if not isinstance(saved_locations, list) or not saved_locations:
                ctx.bot.send_message(
                    message.chat.id,
                    "Сохранённых локаций пока нет.",
                    reply_markup=ctx.location_input_menu(has_saved_locations=False),
                )
                return True
            session_store.user_states[user_id] = WAITING_CURRENT_WEATHER_SAVED_PICK
            ctx.bot.send_message(
                message.chat.id,
                "Выбери сохранённую локацию:",
                reply_markup=ctx.build_saved_locations_keyboard(saved_locations, "current_saved_pick"),
            )
            return True
        if query in {"🧭 Координаты", "Ввести координаты"}:
            session_store.user_states[user_id] = WAITING_CURRENT_WEATHER_COORDS
            ctx.bot.send_message(
                message.chat.id,
                "Введи координаты в формате: 55.5789, 37.9051",
                reply_markup=types.ReplyKeyboardRemove(),
            )
            return True
        if query in {"📍 Отправить геолокацию", "📍 Геолокация", "Отправить геолокацию"}:
            session_store.user_states[user_id] = WAITING_CURRENT_WEATHER_GEO
            ctx.bot.send_message(
                message.chat.id,
                "Отправь геолокацию через кнопку ниже.",
                reply_markup=ctx.geo_request_menu(),
            )
            return True

        coords = parse_coordinates(query)
        if coords is not None:
            lat, lon = coords
            weather = ctx.get_current_weather(lat, lon)
            if not weather:
                ctx.bot.send_message(
                    message.chat.id,
                    "Не удалось получить данные о погоде по координатам. Попробуй позже.",
                    reply_markup=ctx.main_menu(),
                )
                session_store.user_states.pop(user_id, None)
                return True

            location = ctx.get_location_by_coordinates(lat, lon)
            city_label = (
                ctx.build_location_label(location, show_coords=False)
                if location
                else f"Координаты: {lat:.4f}, {lon:.4f}"
            )
            user_data = ctx.load_user(user_id)
            user_data["city"] = city_label
            user_data["lat"] = lat
            user_data["lon"] = lon
            ctx.save_user(user_id, user_data)
            session_store.user_states.pop(user_id, None)
            snapshot_id = session_store.generate_ai_snapshot_id(user_id)
            session_store.ai_current_snapshots[snapshot_id] = {
                "user_id": user_id,
                "city_label": city_label,
                "weather": weather,
                "created_at": time.time(),
            }
            session_store.cleanup_ai_snapshots()
            ctx.bot.send_message(message.chat.id, ctx.format_weather_response(city_label, weather), reply_markup=ctx.main_menu())
            ctx.bot.send_message(
                message.chat.id,
                "✨ Хочешь короткий и понятный разбор?",
                reply_markup=ctx.build_ai_action_keyboard(
                    "✨ Объяснить по-человечески",
                    f"ai_current_explain:{snapshot_id}",
                ),
            )
            return True

        ctx.logger.info("Пользователь %s ввёл запрос для текущей погоды: %s", user_id, query)
        if not query:
            ctx.logger.info("Пустой ввод для текущей погоды: пользователь %s.", user_id)
            ctx.bot.send_message(message.chat.id, "⚠️ Введи название населённого пункта.")
            return True

        locations = get_locations(query, limit=5)
        locations = ctx.rank_locations(query, locations)[:3]
        if not locations:
            ctx.logger.info("Населённый пункт не найден для пользователя %s: %s", user_id, query)
            ctx.bot.send_message(
                message.chat.id,
                "⚠️ Населённый пункт не найден. Попробуй указать название точнее, например с регионом, или отправь геолокацию.",
            )
            return True

        if len(locations) == 1:
            ctx.complete_current_weather_from_location(
                ctx.bot,
                message.chat.id,
                user_id,
                locations[0],
                user_states=session_store.user_states,
                current_location_choices=session_store.current_location_choices,
                ai_current_snapshots=session_store.ai_current_snapshots,
                create_ai_snapshot_id_fn=session_store.generate_ai_snapshot_id,
                cleanup_ai_snapshots_fn=session_store.cleanup_ai_snapshots,
                load_user_fn=ctx.load_user,
                save_user_fn=ctx.save_user,
            )
            return True

        session_store.current_location_choices[user_id] = locations
        session_store.user_states[user_id] = WAITING_CURRENT_WEATHER_PICK
        ctx.logger.info(
            "Найдено несколько вариантов (%s) для пользователя %s: %s",
            len(locations),
            user_id,
            query,
        )
        ctx.bot.send_message(
            message.chat.id,
            "Найдено несколько вариантов. Выбери нужный населённый пункт:",
            reply_markup=ctx.build_current_weather_location_keyboard(locations),
        )
        return True

    if state == WAITING_CURRENT_WEATHER_COORDS:
        parsed = parse_coordinates(message.text or "")
        if parsed is None:
            ctx.bot.send_message(message.chat.id, "⚠️ Некорректный формат. Введи координаты в формате: 55.5789, 37.9051")
            return True
        lat, lon = parsed
        weather = ctx.get_current_weather(lat, lon)
        if not weather:
            session_store.user_states.pop(user_id, None)
            ctx.bot.send_message(
                message.chat.id,
                "Не удалось получить данные о погоде по координатам. Попробуй позже.",
                reply_markup=ctx.main_menu(),
            )
            return True
        location = ctx.get_location_by_coordinates(lat, lon)
        city_label = (
            ctx.build_location_label(location, show_coords=False)
            if location
            else f"Координаты: {lat:.4f}, {lon:.4f}"
        )
        user_data = ctx.load_user(user_id)
        user_data["city"] = city_label
        user_data["lat"] = lat
        user_data["lon"] = lon
        ctx.save_user(user_id, user_data)
        session_store.user_states.pop(user_id, None)
        snapshot_id = session_store.generate_ai_snapshot_id(user_id)
        session_store.ai_current_snapshots[snapshot_id] = {
            "user_id": user_id,
            "city_label": city_label,
            "weather": weather,
            "created_at": time.time(),
        }
        session_store.cleanup_ai_snapshots()
        ctx.bot.send_message(message.chat.id, ctx.format_weather_response(city_label, weather), reply_markup=ctx.main_menu())
        ctx.bot.send_message(
            message.chat.id,
            "✨ Хочешь короткий и понятный разбор?",
            reply_markup=ctx.build_ai_action_keyboard(
                "✨ Объяснить по-человечески",
                f"ai_current_explain:{snapshot_id}",
            ),
        )
        return True

    if state == WAITING_CURRENT_WEATHER_PICK:
        if not session_store.current_location_choices.get(user_id):
            session_store.user_states.pop(user_id, None)
            ctx.bot.send_message(
                message.chat.id,
                "⚠️ Список вариантов устарел. Введи населённый пункт заново.",
                reply_markup=ctx.main_menu(),
            )
            return True
        ctx.bot.send_message(
            message.chat.id,
            "Выбери населённый пункт кнопкой ниже или нажми «⬅️ Отмена».",
        )
        return True

    if state == WAITING_CURRENT_WEATHER_SAVED_PICK:
        ctx.bot.send_message(
            message.chat.id,
            "Выбери сохранённую локацию кнопкой ниже или нажми «⬅️ В меню».",
        )
        return True

    if state == WAITING_CURRENT_WEATHER_GEO:
        ctx.bot.send_message(
            message.chat.id,
            "Отправь геолокацию через кнопку ниже.",
            reply_markup=ctx.geo_request_menu(),
        )
        return True

    return False
