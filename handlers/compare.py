from telebot import types

from .states import (
    WAITING_COMPARE_CITY_1,
    WAITING_COMPARE_CITY_2,
    WAITING_COMPARE_LOCATION_PICK,
)
from weather_app import get_locations


def handle_compare_text(
    message: types.Message,
    user_id: int,
    state: str | None,
    *,
    ctx,
    session_store,
    complete_compare_two_locations,
) -> bool:
    """Обрабатывает текстовые состояния сценария сравнения."""
    if state == WAITING_COMPARE_CITY_1:
        query = (message.text or "").strip()
        ctx.logger.info("Пользователь %s ввёл первый населённый пункт для сравнения: %s", user_id, query)
        if not query:
            ctx.bot.send_message(message.chat.id, "⚠️ Введи название населённого пункта.")
            return True

        locations = get_locations(query, limit=5)
        locations = ctx.rank_locations(query, locations)[:3]
        if not locations:
            ctx.bot.send_message(
                message.chat.id,
                "⚠️ Населённый пункт не найден. Попробуй указать название точнее, например с регионом, или отправь геолокацию.",
            )
            return True

        if len(locations) == 1:
            loc = ctx.build_geocode_item_with_disambiguated_label(locations, 0)
            lat = loc.get("lat")
            lon = loc.get("lon")
            label = loc.get("label") or ctx.build_location_label(loc, show_coords=False)
            if lat is None or lon is None:
                ctx.bot.send_message(
                    message.chat.id,
                    "Не удалось получить данные для сравнения. Попробуй позже.",
                    reply_markup=ctx.main_menu(),
                )
                return True
            session_store.compare_drafts[user_id] = {
                "coordinates_1": (float(lat), float(lon)),
                "city_1_input": label,
                "city_1_label": label,
            }
            session_store.user_states[user_id] = WAITING_COMPARE_CITY_2
            ctx.bot.send_message(message.chat.id, "Теперь введи второй населённый пункт.")
            return True

        session_store.compare_location_choices[user_id] = {"step": 1, "locations": locations}
        session_store.user_states[user_id] = WAITING_COMPARE_LOCATION_PICK
        ctx.logger.info(
            "Найдено несколько вариантов (%s) для первого населённого пункта у пользователя %s: %s",
            len(locations),
            user_id,
            query,
        )
        ctx.bot.send_message(
            message.chat.id,
            "Найдено несколько вариантов. Выбери нужный населённый пункт:",
            reply_markup=ctx.build_scenario_location_choice_keyboard(locations, "compare", compare_step=1),
        )
        return True

    if state == WAITING_COMPARE_CITY_2:
        query = (message.text or "").strip()
        ctx.logger.info("Пользователь %s ввёл второй населённый пункт для сравнения: %s", user_id, query)
        if not query:
            ctx.bot.send_message(message.chat.id, "⚠️ Введи название населённого пункта.")
            return True

        draft = session_store.compare_drafts.get(user_id)
        if not draft or "coordinates_1" not in draft:
            session_store.user_states.pop(user_id, None)
            session_store.compare_drafts.pop(user_id, None)
            ctx.bot.send_message(
                message.chat.id,
                "Не удалось получить данные для сравнения. Попробуй позже.",
                reply_markup=ctx.main_menu(),
            )
            return True

        locations = get_locations(query, limit=5)
        locations = ctx.rank_locations(query, locations)[:3]
        if not locations:
            ctx.bot.send_message(
                message.chat.id,
                "⚠️ Населённый пункт не найден. Попробуй указать название точнее, например с регионом, или отправь геолокацию.",
            )
            return True

        if len(locations) == 1:
            loc = ctx.build_geocode_item_with_disambiguated_label(locations, 0)
            lat_2 = loc.get("lat")
            lon_2 = loc.get("lon")
            city_label_2 = loc.get("label") or ctx.build_location_label(loc, show_coords=False)
            if lat_2 is None or lon_2 is None:
                session_store.user_states.pop(user_id, None)
                session_store.compare_drafts.pop(user_id, None)
                ctx.bot.send_message(
                    message.chat.id,
                    "Не удалось получить данные для сравнения. Попробуй позже.",
                    reply_markup=ctx.main_menu(),
                )
                return True
            lat_1, lon_1 = draft["coordinates_1"]
            city_label_1 = draft.get("city_1_label") or draft.get("city_1_input") or "Первый населённый пункт"
            complete_compare_two_locations(
                message.chat.id,
                user_id,
                lat_1,
                lon_1,
                city_label_1,
                float(lat_2),
                float(lon_2),
                city_label_2,
            )
            return True

        session_store.compare_location_choices[user_id] = {"step": 2, "locations": locations}
        session_store.user_states[user_id] = WAITING_COMPARE_LOCATION_PICK
        ctx.logger.info(
            "Найдено несколько вариантов (%s) для второго населённого пункта у пользователя %s: %s",
            len(locations),
            user_id,
            query,
        )
        ctx.bot.send_message(
            message.chat.id,
            "Найдено несколько вариантов. Выбери нужный населённый пункт:",
            reply_markup=ctx.build_scenario_location_choice_keyboard(locations, "compare", compare_step=2),
        )
        return True

    if state == WAITING_COMPARE_LOCATION_PICK:
        if not session_store.compare_location_choices.get(user_id):
            session_store.user_states.pop(user_id, None)
            session_store.compare_drafts.pop(user_id, None)
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

    return False
