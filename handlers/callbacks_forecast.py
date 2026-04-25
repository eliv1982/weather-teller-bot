def handle_forecast_callback(
    call,
    *,
    ctx,
    session_store,
    _message_stub_for_chat,
    send_forecast_by_coordinates,
) -> None:
    """Обрабатывает inline-навигацию прогноза и выбор локации перед прогнозом."""
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    if call.data == "forecast_cancel":
        session_store.forecast_location_choices.pop(user_id, None)
        session_store.user_states.pop(user_id, None)
        ctx.bot.answer_callback_query(call.id)
        ctx.bot.send_message(chat_id, "Выбор отменён.", reply_markup=ctx.main_menu())
        return

    if call.data.startswith("forecast_pick:"):
        try:
            index = int(call.data.split(":", 1)[1])
        except (ValueError, IndexError):
            ctx.bot.answer_callback_query(call.id)
            session_store.user_states.pop(user_id, None)
            session_store.forecast_location_choices.pop(user_id, None)
            ctx.bot.send_message(
                chat_id,
                "⚠️ Список вариантов устарел. Введи населённый пункт заново.",
                reply_markup=ctx.main_menu(),
            )
            return

        choices = session_store.forecast_location_choices.get(user_id)
        if not choices or index < 0 or index >= len(choices):
            ctx.bot.answer_callback_query(call.id)
            session_store.user_states.pop(user_id, None)
            session_store.forecast_location_choices.pop(user_id, None)
            ctx.bot.send_message(
                chat_id,
                "⚠️ Список вариантов устарел. Введи населённый пункт заново.",
                reply_markup=ctx.main_menu(),
            )
            return

        location_item = ctx.build_geocode_item_with_disambiguated_label(choices, index)
        ctx.logger.info(
            "Пользователь %s выбрал локацию для прогноза #%s: %s",
            user_id,
            index,
            location_item.get("label"),
        )
        ctx.bot.answer_callback_query(call.id)
        stub = _message_stub_for_chat(chat_id)
        city = location_item.get("label") or ctx.build_location_label(location_item, show_coords=False)
        lat = location_item.get("lat")
        lon = location_item.get("lon")
        if lat is None or lon is None:
            session_store.forecast_location_choices.pop(user_id, None)
            session_store.user_states.pop(user_id, None)
            ctx.bot.send_message(
                chat_id,
                "Не удалось получить прогноз. Попробуй позже.",
                reply_markup=ctx.main_menu(),
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

    if call.data.startswith("forecast_saved_pick:"):
        location_id = call.data.split(":", 1)[1] if ":" in call.data else ""
        user_data = ctx.load_user(user_id)
        saved_locations = user_data.get("saved_locations", [])
        target = next(
            (
                item
                for item in saved_locations
                if isinstance(item, dict) and isinstance(location_id, str) and item.get("id") == location_id
            ),
            None,
        )
        if not isinstance(target, dict):
            ctx.bot.answer_callback_query(call.id)
            session_store.user_states.pop(user_id, None)
            ctx.bot.send_message(chat_id, "⚠️ Сохранённая локация не найдена.", reply_markup=ctx.main_menu())
            return
        lat = target.get("lat")
        lon = target.get("lon")
        city = str(target.get("label") or target.get("title") or "Сохранённая локация")
        if lat is None or lon is None:
            ctx.bot.answer_callback_query(call.id)
            session_store.user_states.pop(user_id, None)
            ctx.bot.send_message(chat_id, "⚠️ У сохранённой локации нет координат.", reply_markup=ctx.main_menu())
            return
        ctx.bot.answer_callback_query(call.id)
        stub = _message_stub_for_chat(chat_id)
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

    cache = session_store.forecast_cache.get(user_id)
    if not cache:
        ctx.bot.answer_callback_query(call.id, "Данные прогноза устарели.")
        return

    if call.data == "forecast_back":
        days = list(cache["grouped"].keys())
        keyboard = ctx.build_forecast_days_keyboard(days)
        ctx.bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"Выбери день прогноза для {cache['city']}:",
            reply_markup=keyboard,
        )
        ctx.bot.answer_callback_query(call.id)
        return

    if call.data == "forecast_menu":
        session_store.user_states.pop(user_id, None)
        session_store.forecast_saved_drafts.pop(user_id, None)
        session_store.forecast_cache.pop(user_id, None)
        ctx.bot.send_message(call.message.chat.id, "Главное меню.", reply_markup=ctx.main_menu())
        ctx.bot.answer_callback_query(call.id)
        return

    if call.data.startswith("forecast_day:"):
        day = call.data.split(":", 1)[1]
        ctx.logger.info("Пользователь %s выбрал день прогноза: %s", user_id, day)
        day_items = cache["grouped"].get(day)
        if not day_items:
            ctx.bot.answer_callback_query(call.id, "День прогноза не найден.")
            return

        text = ctx.format_forecast_day(day, day_items, cache["city"])
        keyboard = ctx.build_forecast_day_keyboard(list(cache["grouped"].keys()), day)
        ctx.bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=text,
            reply_markup=keyboard,
        )
        ctx.bot.answer_callback_query(call.id)
        return

    ctx.bot.answer_callback_query(call.id)
