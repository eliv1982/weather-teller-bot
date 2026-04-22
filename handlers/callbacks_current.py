def handle_current_weather_callback(
    call,
    *,
    bot,
    logger,
    user_states: dict,
    current_location_choices: dict,
    complete_current_weather_from_location,
    main_menu,
    build_geocode_item_with_disambiguated_label,
) -> None:
    """Обрабатывает выбор локации или отмену в сценарии «Текущая погода»."""
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    if call.data == "current_cancel":
        current_location_choices.pop(user_id, None)
        user_states.pop(user_id, None)
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "Выбор отменён.", reply_markup=main_menu())
        return

    if call.data.startswith("current_pick:"):
        try:
            index = int(call.data.split(":", 1)[1])
        except (ValueError, IndexError):
            bot.answer_callback_query(call.id)
            user_states.pop(user_id, None)
            current_location_choices.pop(user_id, None)
            bot.send_message(
                chat_id,
                "⚠️ Список вариантов устарел. Введи населённый пункт заново.",
                reply_markup=main_menu(),
            )
            return

        choices = current_location_choices.get(user_id)
        if not choices or index < 0 or index >= len(choices):
            bot.answer_callback_query(call.id)
            user_states.pop(user_id, None)
            current_location_choices.pop(user_id, None)
            bot.send_message(
                chat_id,
                "⚠️ Список вариантов устарел. Введи населённый пункт заново.",
                reply_markup=main_menu(),
            )
            return

        location_item = build_geocode_item_with_disambiguated_label(choices, index)
        logger.info(
            "Пользователь %s выбрал вариант текущей погоды #%s: %s",
            user_id,
            index,
            location_item.get("label"),
        )
        bot.answer_callback_query(call.id)
        complete_current_weather_from_location(
            bot,
            chat_id,
            user_id,
            location_item,
            user_states=user_states,
            current_location_choices=current_location_choices,
        )
        return

    bot.answer_callback_query(call.id)
