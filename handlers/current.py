from telebot import types

from .states import WAITING_CURRENT_USE_FAVORITE, WAITING_CURRENT_WEATHER_CITY, WAITING_CURRENT_WEATHER_PICK
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
    if state == WAITING_CURRENT_USE_FAVORITE:
        answer = (message.text or "").strip().lower()
        yes_values = {"да", "д", "yes", "y"}
        no_values = {"нет", "н", "no"}

        if answer in yes_values:
            draft = session_store.current_favorite_drafts.get(user_id)
            location_item = draft.get("location") if isinstance(draft, dict) else None
            if not isinstance(location_item, dict):
                session_store.current_favorite_drafts.pop(user_id, None)
                session_store.user_states[user_id] = WAITING_CURRENT_WEATHER_CITY
                ctx.bot.send_message(message.chat.id, "Введи название населённого пункта.")
                return True

            ctx.complete_current_weather_from_location(
                ctx.bot,
                message.chat.id,
                user_id,
                location_item,
                user_states=session_store.user_states,
                current_location_choices=session_store.current_location_choices,
            )
            session_store.current_favorite_drafts.pop(user_id, None)
            return True

        if answer in no_values:
            session_store.current_favorite_drafts.pop(user_id, None)
            session_store.user_states[user_id] = WAITING_CURRENT_WEATHER_CITY
            ctx.bot.send_message(message.chat.id, "Введи название населённого пункта.")
            return True

        ctx.bot.send_message(message.chat.id, "Пожалуйста, ответь: Да или Нет.", reply_markup=ctx.yes_no_menu())
        return True

    if state == WAITING_CURRENT_WEATHER_CITY:
        query = (message.text or "").strip()
        ctx.logger.info("Пользователь %s ввёл запрос для текущей погоды: %s", user_id, query)
        if not query:
            ctx.logger.info("Пустой ввод для текущей погоды: пользователь %s.", user_id)
            ctx.bot.send_message(message.chat.id, "⚠️ Введи название населённого пункта.")
            return True

        locations = get_locations(query, limit=5)
        locations = ctx.rank_locations(query, locations)
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

    return False
