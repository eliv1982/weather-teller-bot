def handle_alerts_location_callback(
    call,
    *,
    ctx,
    session_store,
    ALERTS_MENU,
) -> None:
    """Обрабатывает выбор локации для уведомлений (inline) или отмену."""
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    if call.data == "alerts_cancel":
        session_store.alerts_location_choices.pop(user_id, None)
        session_store.user_states[user_id] = ALERTS_MENU
        user_data = ctx.ensure_notifications_defaults(ctx.load_user(user_id))
        ctx.bot.answer_callback_query(call.id)
        ctx.bot.send_message(chat_id, ctx.format_alerts_status(user_data), reply_markup=ctx.alerts_menu())
        return

    if call.data.startswith("alerts_pick:"):
        try:
            index = int(call.data.split(":", 1)[1])
        except (ValueError, IndexError):
            ctx.bot.answer_callback_query(call.id)
            session_store.alerts_location_choices.pop(user_id, None)
            session_store.user_states[user_id] = ALERTS_MENU
            ctx.bot.send_message(
                chat_id,
                "⚠️ Список вариантов устарел. Введи населённый пункт заново.",
                reply_markup=ctx.alerts_menu(),
            )
            return

        choices = session_store.alerts_location_choices.get(user_id)
        if not choices or index < 0 or index >= len(choices):
            ctx.bot.answer_callback_query(call.id)
            session_store.alerts_location_choices.pop(user_id, None)
            session_store.user_states[user_id] = ALERTS_MENU
            ctx.bot.send_message(
                chat_id,
                "⚠️ Список вариантов устарел. Введи населённый пункт заново.",
                reply_markup=ctx.alerts_menu(),
            )
            return

        location_item = ctx.build_geocode_item_with_disambiguated_label(choices, index)
        ctx.logger.info(
            "Пользователь %s выбрал локацию для уведомлений #%s: %s",
            user_id,
            index,
            location_item.get("label"),
        )
        ctx.bot.answer_callback_query(call.id)
        ctx.complete_alerts_location_from_item(
            ctx.bot,
            chat_id,
            user_id,
            location_item,
            user_states=session_store.user_states,
            alerts_location_choices=session_store.alerts_location_choices,
        )
        return

    ctx.bot.answer_callback_query(call.id)
