def handle_details_location_callback(
    call,
    *,
    ctx,
    session_store,
    send_details_by_coordinates,
    _message_stub_for_chat,
) -> None:
    """Обрабатывает выбор локации для расширенных данных (inline) или отмену."""
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    if call.data == "details_cancel":
        session_store.details_location_choices.pop(user_id, None)
        session_store.user_states.pop(user_id, None)
        ctx.bot.answer_callback_query(call.id)
        ctx.bot.send_message(chat_id, "Выбор отменён.", reply_markup=ctx.main_menu())
        return

    if call.data.startswith("details_pick:"):
        try:
            index = int(call.data.split(":", 1)[1])
        except (ValueError, IndexError):
            ctx.bot.answer_callback_query(call.id)
            session_store.user_states.pop(user_id, None)
            session_store.details_location_choices.pop(user_id, None)
            ctx.bot.send_message(
                chat_id,
                "⚠️ Список вариантов устарел. Введи населённый пункт заново.",
                reply_markup=ctx.main_menu(),
            )
            return

        choices = session_store.details_location_choices.get(user_id)
        if not choices or index < 0 or index >= len(choices):
            ctx.bot.answer_callback_query(call.id)
            session_store.user_states.pop(user_id, None)
            session_store.details_location_choices.pop(user_id, None)
            ctx.bot.send_message(
                chat_id,
                "⚠️ Список вариантов устарел. Введи населённый пункт заново.",
                reply_markup=ctx.main_menu(),
            )
            return

        location_item = ctx.build_geocode_item_with_disambiguated_label(choices, index)
        ctx.logger.info(
            "Пользователь %s выбрал локацию для расширенных данных #%s: %s",
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
            session_store.details_location_choices.pop(user_id, None)
            session_store.user_states.pop(user_id, None)
            ctx.bot.send_message(
                chat_id,
                "Не удалось получить расширенные данные. Попробуй позже.",
                reply_markup=ctx.main_menu(),
            )
            return
        send_details_by_coordinates(
            stub,
            user_id,
            float(lat),
            float(lon),
            city,
            preferred_city_label=city,
        )
        return

    ctx.bot.answer_callback_query(call.id)
