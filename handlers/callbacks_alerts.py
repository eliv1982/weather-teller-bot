def handle_alerts_location_callback(
    call,
    *,
    bot,
    logger,
    user_states: dict,
    alerts_location_choices: dict,
    ALERTS_MENU,
    load_user,
    ensure_notifications_defaults,
    format_alerts_status,
    alerts_menu,
    build_geocode_item_with_disambiguated_label,
    complete_alerts_location_from_item,
) -> None:
    """Обрабатывает выбор локации для уведомлений (inline) или отмену."""
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    if call.data == "alerts_cancel":
        alerts_location_choices.pop(user_id, None)
        user_states[user_id] = ALERTS_MENU
        user_data = ensure_notifications_defaults(load_user(user_id))
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, format_alerts_status(user_data), reply_markup=alerts_menu())
        return

    if call.data.startswith("alerts_pick:"):
        try:
            index = int(call.data.split(":", 1)[1])
        except (ValueError, IndexError):
            bot.answer_callback_query(call.id)
            alerts_location_choices.pop(user_id, None)
            user_states[user_id] = ALERTS_MENU
            bot.send_message(
                chat_id,
                "⚠️ Список вариантов устарел. Введи населённый пункт заново.",
                reply_markup=alerts_menu(),
            )
            return

        choices = alerts_location_choices.get(user_id)
        if not choices or index < 0 or index >= len(choices):
            bot.answer_callback_query(call.id)
            alerts_location_choices.pop(user_id, None)
            user_states[user_id] = ALERTS_MENU
            bot.send_message(
                chat_id,
                "⚠️ Список вариантов устарел. Введи населённый пункт заново.",
                reply_markup=alerts_menu(),
            )
            return

        location_item = build_geocode_item_with_disambiguated_label(choices, index)
        logger.info(
            "Пользователь %s выбрал локацию для уведомлений #%s: %s",
            user_id,
            index,
            location_item.get("label"),
        )
        bot.answer_callback_query(call.id)
        complete_alerts_location_from_item(
            bot,
            chat_id,
            user_id,
            location_item,
            user_states=user_states,
            alerts_location_choices=alerts_location_choices,
        )
        return

    bot.answer_callback_query(call.id)
