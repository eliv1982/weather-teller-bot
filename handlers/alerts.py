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
    ctx,
    session_store,
) -> bool:
    """Обрабатывает текстовые состояния сценария уведомлений."""
    if state == WAITING_ALERTS_LOCATION_TEXT:
        query = (message.text or "").strip()
        ctx.logger.info("Пользователь %s ввёл запрос локации для уведомлений: %s", user_id, query)
        if not query:
            ctx.bot.send_message(message.chat.id, "⚠️ Введи название населённого пункта.")
            return True

        locations = get_locations(query, limit=5)
        if not locations:
            ctx.bot.send_message(
                message.chat.id,
                "⚠️ Населённый пункт не найден. Попробуй указать название точнее, например с регионом, или отправь геолокацию.",
            )
            return True

        if len(locations) == 1:
            ctx.complete_alerts_location_from_item(
                ctx.bot,
                message.chat.id,
                user_id,
                locations[0],
                user_states=session_store.user_states,
                alerts_location_choices=session_store.alerts_location_choices,
            )
            return True

        session_store.alerts_location_choices[user_id] = locations
        session_store.user_states[user_id] = WAITING_ALERTS_LOCATION_PICK
        ctx.bot.send_message(
            message.chat.id,
            "Найдено несколько вариантов. Выбери нужный населённый пункт:",
            reply_markup=ctx.build_location_pick_keyboard(locations, "alerts_pick", "alerts_cancel"),
        )
        return True

    if state == WAITING_ALERTS_LOCATION_PICK:
        if not session_store.alerts_location_choices.get(user_id):
            session_store.user_states[user_id] = ALERTS_MENU
            ctx.ensure_notifications_defaults(ctx.load_user(user_id))
            ctx.bot.send_message(
                message.chat.id,
                "⚠️ Список вариантов устарел. Введи населённый пункт заново.",
                reply_markup=ctx.alerts_menu(),
            )
            return True
        ctx.bot.send_message(
            message.chat.id,
            "Выбери населённый пункт кнопкой ниже или нажми «⬅️ Отмена».",
        )
        return True

    if state == WAITING_ALERTS_LOCATION_GEO:
        ctx.bot.send_message(
            message.chat.id,
            "Пожалуйста, отправь геолокацию через кнопку ниже или вернись в меню.",
            reply_markup=ctx.geo_request_menu(),
        )
        return True

    if state == WAITING_ALERTS_LOCATION_MENU:
        if message.text == "Ввести населённый пункт":
            session_store.user_states[user_id] = WAITING_ALERTS_LOCATION_TEXT
            ctx.bot.send_message(
                message.chat.id,
                "Введи населённый пункт для уведомлений.",
                reply_markup=types.ReplyKeyboardRemove(),
            )
            return True
        if message.text == "Отправить геолокацию":
            session_store.user_states[user_id] = WAITING_ALERTS_LOCATION_GEO
            ctx.bot.send_message(
                message.chat.id,
                "Отправь геолокацию для уведомлений.",
                reply_markup=ctx.geo_request_menu(),
            )
            return True
        ctx.bot.send_message(
            message.chat.id,
            "Выбери действие кнопкой ниже или нажми «⬅️ В меню», чтобы вернуться в меню уведомлений.",
            reply_markup=ctx.alerts_location_menu(),
        )
        return True

    if state in {ALERTS_MENU, WAITING_ALERTS_INTERVAL}:
        user_data = ctx.ensure_notifications_defaults(ctx.load_user(user_id))

        if message.text == "Показать статус":
            ctx.bot.send_message(message.chat.id, ctx.format_alerts_status(user_data), reply_markup=ctx.alerts_menu())
            return True

        if message.text == "Изменить локацию":
            session_store.user_states[user_id] = WAITING_ALERTS_LOCATION_MENU
            ctx.bot.send_message(
                message.chat.id,
                "Выбери способ указания локации для уведомлений:",
                reply_markup=ctx.alerts_location_menu(),
            )
            return True

        if message.text == "Включить уведомления":
            user_data["notifications"]["enabled"] = True
            ctx.save_user(user_id, user_data)
            ctx.logger.info("Пользователь %s включил уведомления.", user_id)
            session_store.user_states[user_id] = ALERTS_MENU
            ctx.bot.send_message(message.chat.id, "✅ Уведомления включены.", reply_markup=ctx.alerts_menu())
            return True

        if message.text == "Выключить уведомления":
            user_data["notifications"]["enabled"] = False
            ctx.save_user(user_id, user_data)
            ctx.logger.info("Пользователь %s выключил уведомления.", user_id)
            session_store.user_states[user_id] = ALERTS_MENU
            ctx.bot.send_message(message.chat.id, "✅ Уведомления выключены.", reply_markup=ctx.alerts_menu())
            return True

        if message.text == "Изменить интервал":
            session_store.user_states[user_id] = WAITING_ALERTS_INTERVAL
            ctx.bot.send_message(
                message.chat.id,
                "Введи интервал проверки в часах, например: 2",
                reply_markup=ctx.alerts_menu(),
            )
            return True

        if state == WAITING_ALERTS_INTERVAL:
            try:
                interval = int((message.text or "").strip())
            except ValueError:
                ctx.bot.send_message(
                    message.chat.id,
                    "⚠️ Введите положительное число часов.",
                    reply_markup=ctx.alerts_menu(),
                )
                return True

            if interval <= 0:
                ctx.bot.send_message(
                    message.chat.id,
                    "⚠️ Введите положительное число часов.",
                    reply_markup=ctx.alerts_menu(),
                )
                return True

            user_data["notifications"]["interval_h"] = interval
            ctx.save_user(user_id, user_data)
            ctx.logger.info("Пользователь %s изменил интервал уведомлений на %s ч.", user_id, interval)
            session_store.user_states[user_id] = ALERTS_MENU
            ctx.bot.send_message(
                message.chat.id,
                f"✅ Интервал обновлён: {interval} ч.",
                reply_markup=ctx.alerts_menu(),
            )
            return True

        ctx.bot.send_message(
            message.chat.id,
            "Выбери действие в меню уведомлений.",
            reply_markup=ctx.alerts_menu(),
        )
        return True

    return False
