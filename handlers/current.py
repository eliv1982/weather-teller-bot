from telebot import types

from .states import WAITING_CURRENT_WEATHER_CITY, WAITING_CURRENT_WEATHER_PICK
from weather_app import get_locations


def handle_current_text(
    message: types.Message,
    user_id: int,
    state: str | None,
    *,
    bot,
    logger,
    user_states: dict,
    current_location_choices: dict,
    complete_current_weather_from_location,
    main_menu,
    build_current_weather_location_keyboard,
) -> bool:
    """Обрабатывает текстовые состояния сценария текущей погоды."""
    if state == WAITING_CURRENT_WEATHER_CITY:
        query = (message.text or "").strip()
        logger.info("Пользователь %s ввёл запрос для текущей погоды: %s", user_id, query)
        if not query:
            logger.info("Пустой ввод для текущей погоды: пользователь %s.", user_id)
            bot.send_message(message.chat.id, "⚠️ Введи название населённого пункта.")
            return True

        locations = get_locations(query, limit=5)
        if not locations:
            logger.info("Населённый пункт не найден для пользователя %s: %s", user_id, query)
            bot.send_message(
                message.chat.id,
                "⚠️ Населённый пункт не найден. Попробуй указать название точнее, например с регионом, или отправь геолокацию.",
            )
            return True

        if len(locations) == 1:
            complete_current_weather_from_location(
                bot,
                message.chat.id,
                user_id,
                locations[0],
                user_states=user_states,
                current_location_choices=current_location_choices,
            )
            return True

        current_location_choices[user_id] = locations
        user_states[user_id] = WAITING_CURRENT_WEATHER_PICK
        logger.info(
            "Найдено несколько вариантов (%s) для пользователя %s: %s",
            len(locations),
            user_id,
            query,
        )
        bot.send_message(
            message.chat.id,
            "Найдено несколько вариантов. Выбери нужный населённый пункт:",
            reply_markup=build_current_weather_location_keyboard(locations),
        )
        return True

    if state == WAITING_CURRENT_WEATHER_PICK:
        if not current_location_choices.get(user_id):
            user_states.pop(user_id, None)
            bot.send_message(
                message.chat.id,
                "⚠️ Список вариантов устарел. Введи населённый пункт заново.",
                reply_markup=main_menu(),
            )
            return True
        bot.send_message(
            message.chat.id,
            "Выбери населённый пункт кнопкой ниже или нажми «⬅️ Отмена».",
        )
        return True

    return False
