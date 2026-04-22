from telebot import types

from .states import (
    WAITING_DETAILS_CITY,
    WAITING_DETAILS_PICK,
    WAITING_DETAILS_USE_SAVED_LOCATION,
)
from weather_app import get_locations


def handle_details_text(
    message: types.Message,
    user_id: int,
    state: str | None,
    *,
    ctx,
    session_store,
    send_details_by_coordinates,
) -> bool:
    """Обрабатывает текстовые состояния сценария расширенных данных."""
    if state == WAITING_DETAILS_CITY:
        query = (message.text or "").strip()
        ctx.logger.info("Пользователь %s ввёл населённый пункт для расширенных данных: %s", user_id, query)
        if not query:
            ctx.bot.send_message(message.chat.id, "⚠️ Введи название населённого пункта.")
            return True

        locations = get_locations(query, limit=5)
        locations = ctx.rank_locations(query, locations)
        if not locations:
            ctx.logger.info("Населённый пункт не найден для расширенных данных у пользователя %s: %s", user_id, query)
            ctx.bot.send_message(
                message.chat.id,
                "⚠️ Населённый пункт не найден. Попробуй указать название точнее, например с регионом, или отправь геолокацию.",
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
                    "Не удалось получить расширенные данные. Попробуй позже.",
                    reply_markup=ctx.main_menu(),
                )
                return True
            if send_details_by_coordinates(
                message,
                user_id,
                float(lat),
                float(lon),
                city,
                preferred_city_label=city,
            ):
                ctx.logger.info(
                    "Успешно получены расширенные данные для пользователя %s по введённому населённому пункту %s.",
                    user_id,
                    query,
                )
            return True

        session_store.details_location_choices[user_id] = locations
        session_store.user_states[user_id] = WAITING_DETAILS_PICK
        ctx.logger.info(
            "Найдено несколько вариантов (%s) для расширенных данных у пользователя %s: %s",
            len(locations),
            user_id,
            query,
        )
        ctx.bot.send_message(
            message.chat.id,
            "Найдено несколько вариантов. Выбери нужный населённый пункт:",
            reply_markup=ctx.build_scenario_location_choice_keyboard(locations, "details"),
        )
        return True

    if state == WAITING_DETAILS_PICK:
        if not session_store.details_location_choices.get(user_id):
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

    if state == WAITING_DETAILS_USE_SAVED_LOCATION:
        answer = (message.text or "").strip().lower()

        yes_values = {"да", "д", "yes", "y"}
        no_values = {"нет", "н", "no"}

        if answer in yes_values:
            ctx.logger.info("Пользователь %s выбрал: Да (использовать сохранённую локацию).", user_id)
            draft = session_store.details_saved_drafts.get(user_id)
            if not draft:
                session_store.user_states[user_id] = WAITING_DETAILS_CITY
                ctx.bot.send_message(message.chat.id, "Введи название населённого пункта для расширенных данных.")
                return True

            if send_details_by_coordinates(
                message,
                user_id,
                draft["lat"],
                draft["lon"],
                draft["city"],
                preferred_city_label=draft["city"],
            ):
                ctx.logger.info(
                    "Успешно получены расширенные данные по сохранённой локации для пользователя %s.",
                    user_id,
                )
            return True

        if answer in no_values:
            ctx.logger.info("Пользователь %s выбрал: Нет (ввести новый населённый пункт).", user_id)
            session_store.details_saved_drafts.pop(user_id, None)
            session_store.user_states[user_id] = WAITING_DETAILS_CITY
            ctx.bot.send_message(message.chat.id, "Введи название населённого пункта для расширенных данных.")
            return True

        ctx.bot.send_message(message.chat.id, "Пожалуйста, ответь: Да или Нет.")
        return True

    return False
