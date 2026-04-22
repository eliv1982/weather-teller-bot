def handle_current_weather_callback(
    call,
    *,
    ctx,
    session_store,
) -> None:
    """Обрабатывает выбор локации или отмену в сценарии «Текущая погода»."""
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    if call.data == "current_cancel":
        session_store.current_location_choices.pop(user_id, None)
        session_store.user_states.pop(user_id, None)
        ctx.bot.answer_callback_query(call.id)
        ctx.bot.send_message(chat_id, "Выбор отменён.", reply_markup=ctx.main_menu())
        return

    if call.data.startswith("current_pick:"):
        try:
            index = int(call.data.split(":", 1)[1])
        except (ValueError, IndexError):
            ctx.bot.answer_callback_query(call.id)
            session_store.user_states.pop(user_id, None)
            session_store.current_location_choices.pop(user_id, None)
            ctx.bot.send_message(
                chat_id,
                "⚠️ Список вариантов устарел. Введи населённый пункт заново.",
                reply_markup=ctx.main_menu(),
            )
            return

        choices = session_store.current_location_choices.get(user_id)
        if not choices or index < 0 or index >= len(choices):
            ctx.bot.answer_callback_query(call.id)
            session_store.user_states.pop(user_id, None)
            session_store.current_location_choices.pop(user_id, None)
            ctx.bot.send_message(
                chat_id,
                "⚠️ Список вариантов устарел. Введи населённый пункт заново.",
                reply_markup=ctx.main_menu(),
            )
            return

        location_item = ctx.build_geocode_item_with_disambiguated_label(choices, index)
        ctx.logger.info(
            "Пользователь %s выбрал вариант текущей погоды #%s: %s",
            user_id,
            index,
            location_item.get("label"),
        )
        ctx.bot.answer_callback_query(call.id)
        ctx.complete_current_weather_from_location(
            ctx.bot,
            chat_id,
            user_id,
            location_item,
            user_states=session_store.user_states,
            current_location_choices=session_store.current_location_choices,
            load_user_fn=ctx.load_user,
            save_user_fn=ctx.save_user,
        )
        return

    ctx.bot.answer_callback_query(call.id)
