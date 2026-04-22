from telebot import types

from .states import (
    ALERTS_MENU,
    WAITING_ALERTS_INTERVAL,
    WAITING_ALERTS_LOCATION_GEO,
    WAITING_ALERTS_LOCATION_MENU,
    WAITING_ALERTS_LOCATION_PICK,
    WAITING_ALERTS_LOCATION_TEXT,
)
from weather_app import get_locations


def handle_alerts_text(
    message: types.Message,
    user_id: int,
    state: str | None,
    *,
    bot,
    logger,
    user_states: dict,
    alerts_location_choices: dict,
    load_user,
    save_user,
    ensure_notifications_defaults,
    complete_alerts_location_from_item,
    format_alerts_status,
    alerts_menu,
    alerts_location_menu,
    build_location_pick_keyboard,
    geo_request_menu,
) -> bool:
    """Обрабатывает текстовые состояния сценария уведомлений."""
    if state == WAITING_ALERTS_LOCATION_TEXT:
        query = (message.text or "").strip()
        logger.info("Пользователь %s ввёл запрос локации для уведомлений: %s", user_id, query)
        if not query:
            bot.send_message(message.chat.id, "⚠️ Введи название населённого пункта.")
            return True

        locations = get_locations(query, limit=5)
        if not locations:
            bot.send_message(
                message.chat.id,
                "⚠️ Населённый пункт не найден. Попробуй указать название точнее, например с регионом, или отправь геолокацию.",
            )
            return True

        if len(locations) == 1:
            complete_alerts_location_from_item(
                bot,
                message.chat.id,
                user_id,
                locations[0],
                user_states=user_states,
                alerts_location_choices=alerts_location_choices,
            )
            return True

        alerts_location_choices[user_id] = locations
        user_states[user_id] = WAITING_ALERTS_LOCATION_PICK
        bot.send_message(
            message.chat.id,
            "Найдено несколько вариантов. Выбери нужный населённый пункт:",
            reply_markup=build_location_pick_keyboard(locations, "alerts_pick", "alerts_cancel"),
        )
        return True

    if state == WAITING_ALERTS_LOCATION_PICK:
        if not alerts_location_choices.get(user_id):
            user_states[user_id] = ALERTS_MENU
            ensure_notifications_defaults(load_user(user_id))
            bot.send_message(
                message.chat.id,
                "⚠️ Список вариантов устарел. Введи населённый пункт заново.",
                reply_markup=alerts_menu(),
            )
            return True
        bot.send_message(
            message.chat.id,
            "Выбери населённый пункт кнопкой ниже или нажми «⬅️ Отмена».",
        )
        return True

    if state == WAITING_ALERTS_LOCATION_GEO:
        bot.send_message(
            message.chat.id,
            "Пожалуйста, отправь геолокацию через кнопку ниже или вернись в меню.",
            reply_markup=geo_request_menu(),
        )
        return True

    if state == WAITING_ALERTS_LOCATION_MENU:
        if message.text == "Ввести населённый пункт":
            user_states[user_id] = WAITING_ALERTS_LOCATION_TEXT
            bot.send_message(
                message.chat.id,
                "Введи населённый пункт для уведомлений.",
                reply_markup=types.ReplyKeyboardRemove(),
            )
            return True
        if message.text == "Отправить геолокацию":
            user_states[user_id] = WAITING_ALERTS_LOCATION_GEO
            bot.send_message(
                message.chat.id,
                "Отправь геолокацию для уведомлений.",
                reply_markup=geo_request_menu(),
            )
            return True
        bot.send_message(
            message.chat.id,
            "Выбери действие кнопкой ниже или нажми «⬅️ В меню», чтобы вернуться в меню уведомлений.",
            reply_markup=alerts_location_menu(),
        )
        return True

    if state in {ALERTS_MENU, WAITING_ALERTS_INTERVAL}:
        user_data = ensure_notifications_defaults(load_user(user_id))

        if message.text == "Показать статус":
            bot.send_message(message.chat.id, format_alerts_status(user_data), reply_markup=alerts_menu())
            return True

        if message.text == "Изменить локацию":
            user_states[user_id] = WAITING_ALERTS_LOCATION_MENU
            bot.send_message(
                message.chat.id,
                "Выбери способ указания локации для уведомлений:",
                reply_markup=alerts_location_menu(),
            )
            return True

        if message.text == "Включить уведомления":
            user_data["notifications"]["enabled"] = True
            save_user(user_id, user_data)
            logger.info("Пользователь %s включил уведомления.", user_id)
            user_states[user_id] = ALERTS_MENU
            bot.send_message(message.chat.id, "✅ Уведомления включены.", reply_markup=alerts_menu())
            return True

        if message.text == "Выключить уведомления":
            user_data["notifications"]["enabled"] = False
            save_user(user_id, user_data)
            logger.info("Пользователь %s выключил уведомления.", user_id)
            user_states[user_id] = ALERTS_MENU
            bot.send_message(message.chat.id, "✅ Уведомления выключены.", reply_markup=alerts_menu())
            return True

        if message.text == "Изменить интервал":
            user_states[user_id] = WAITING_ALERTS_INTERVAL
            bot.send_message(
                message.chat.id,
                "Введи интервал проверки в часах, например: 2",
                reply_markup=alerts_menu(),
            )
            return True

        if state == WAITING_ALERTS_INTERVAL:
            try:
                interval = int((message.text or "").strip())
            except ValueError:
                bot.send_message(
                    message.chat.id,
                    "⚠️ Введите положительное число часов.",
                    reply_markup=alerts_menu(),
                )
                return True

            if interval <= 0:
                bot.send_message(
                    message.chat.id,
                    "⚠️ Введите положительное число часов.",
                    reply_markup=alerts_menu(),
                )
                return True

            user_data["notifications"]["interval_h"] = interval
            save_user(user_id, user_data)
            logger.info("Пользователь %s изменил интервал уведомлений на %s ч.", user_id, interval)
            user_states[user_id] = ALERTS_MENU
            bot.send_message(
                message.chat.id,
                f"✅ Интервал обновлён: {interval} ч.",
                reply_markup=alerts_menu(),
            )
            return True

        bot.send_message(
            message.chat.id,
            "Выбери действие в меню уведомлений.",
            reply_markup=alerts_menu(),
        )
        return True

    return False
