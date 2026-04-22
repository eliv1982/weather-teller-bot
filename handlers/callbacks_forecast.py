def handle_forecast_callback(
    call,
    *,
    bot,
    logger,
    user_states: dict,
    forecast_saved_drafts: dict,
    forecast_location_choices: dict,
    forecast_cache: dict,
    _message_stub_for_chat,
    build_geocode_item_with_disambiguated_label,
    build_location_label,
    send_forecast_by_coordinates,
    main_menu,
    build_forecast_days_keyboard,
    build_forecast_day_keyboard,
    format_forecast_day,
) -> None:
    """Обрабатывает inline-навигацию прогноза и выбор локации перед прогнозом."""
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    if call.data == "forecast_cancel":
        forecast_location_choices.pop(user_id, None)
        user_states.pop(user_id, None)
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "Выбор отменён.", reply_markup=main_menu())
        return

    if call.data.startswith("forecast_pick:"):
        try:
            index = int(call.data.split(":", 1)[1])
        except (ValueError, IndexError):
            bot.answer_callback_query(call.id)
            user_states.pop(user_id, None)
            forecast_location_choices.pop(user_id, None)
            bot.send_message(
                chat_id,
                "⚠️ Список вариантов устарел. Введи населённый пункт заново.",
                reply_markup=main_menu(),
            )
            return

        choices = forecast_location_choices.get(user_id)
        if not choices or index < 0 or index >= len(choices):
            bot.answer_callback_query(call.id)
            user_states.pop(user_id, None)
            forecast_location_choices.pop(user_id, None)
            bot.send_message(
                chat_id,
                "⚠️ Список вариантов устарел. Введи населённый пункт заново.",
                reply_markup=main_menu(),
            )
            return

        location_item = build_geocode_item_with_disambiguated_label(choices, index)
        logger.info(
            "Пользователь %s выбрал локацию для прогноза #%s: %s",
            user_id,
            index,
            location_item.get("label"),
        )
        bot.answer_callback_query(call.id)
        stub = _message_stub_for_chat(chat_id)
        city = location_item.get("label") or build_location_label(location_item, show_coords=False)
        lat = location_item.get("lat")
        lon = location_item.get("lon")
        if lat is None or lon is None:
            forecast_location_choices.pop(user_id, None)
            user_states.pop(user_id, None)
            bot.send_message(
                chat_id,
                "Не удалось получить прогноз. Попробуй позже.",
                reply_markup=main_menu(),
            )
            return
        send_forecast_by_coordinates(
            stub,
            user_id,
            float(lat),
            float(lon),
            city,
            save_location=True,
            preferred_city_label=city,
        )
        return

    cache = forecast_cache.get(user_id)
    if not cache:
        bot.answer_callback_query(call.id, "Данные прогноза устарели.")
        return

    if call.data == "forecast_back":
        days = list(cache["grouped"].keys())
        keyboard = build_forecast_days_keyboard(days)
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"Выбери день прогноза для {cache['city']}:",
            reply_markup=keyboard,
        )
        bot.answer_callback_query(call.id)
        return

    if call.data == "forecast_menu":
        user_states.pop(user_id, None)
        forecast_saved_drafts.pop(user_id, None)
        forecast_cache.pop(user_id, None)
        bot.send_message(call.message.chat.id, "Главное меню.", reply_markup=main_menu())
        bot.answer_callback_query(call.id)
        return

    if call.data.startswith("forecast_day:"):
        day = call.data.split(":", 1)[1]
        logger.info("Пользователь %s выбрал день прогноза: %s", user_id, day)
        day_items = cache["grouped"].get(day)
        if not day_items:
            bot.answer_callback_query(call.id, "День прогноза не найден.")
            return

        text = format_forecast_day(day, day_items, cache["city"])
        keyboard = build_forecast_day_keyboard(list(cache["grouped"].keys()), day)
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=text,
            reply_markup=keyboard,
        )
        bot.answer_callback_query(call.id)
        return

    bot.answer_callback_query(call.id)
