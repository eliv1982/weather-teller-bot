def handle_alerts_location_callback(
    call,
    *,
    ctx,
    session_store,
    ALERTS_MENU,
    WAITING_ALERTS_ADD_MENU,
    WAITING_ALERTS_INTERVAL_VALUE,
) -> None:
    """Обрабатывает callback-сценарии раздела уведомлений."""
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    service = ctx.alerts_subscription_service

    user_data = service.ensure_defaults(ctx.ensure_notifications_defaults(ctx.load_user(user_id)))
    subscriptions = service.list_subscriptions(user_data)

    if call.data == "alerts_add_cancel":
        session_store.alerts_location_choices.pop(user_id, None)
        ctx.bot.answer_callback_query(call.id)
        session_store.user_states[user_id] = ALERTS_MENU
        ctx.bot.send_message(chat_id, "Добавление подписки отменено.", reply_markup=ctx.alerts_menu())
        ctx.bot.send_message(chat_id, ctx.format_alert_subscriptions(user_data), reply_markup=ctx.alerts_menu())
        return

    if call.data.startswith("alerts_add_pick:"):
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
        lat = location_item.get("lat")
        lon = location_item.get("lon")
        label = location_item.get("label") or ctx.build_location_label(location_item, show_coords=False)
        if lat is None or lon is None:
            ctx.bot.answer_callback_query(call.id)
            session_store.alerts_location_choices.pop(user_id, None)
            session_store.user_states[user_id] = ALERTS_MENU
            ctx.bot.send_message(chat_id, "Не удалось определить локацию. Попробуй снова.", reply_markup=ctx.alerts_menu())
            return

        user_data, added = service.add_subscription(
            user_data,
            location_id=service.build_subscription_id(float(lat), float(lon)),
            title=(
                str(location_item.get("local_name") or location_item.get("name") or "").strip()
                or label
            ),
            label=label,
            lat=float(lat),
            lon=float(lon),
        )
        if added:
            ctx.save_user(user_id, user_data)
        ctx.bot.answer_callback_query(call.id)
        session_store.alerts_location_choices.pop(user_id, None)
        session_store.user_states[user_id] = ALERTS_MENU
        ctx.bot.send_message(chat_id, "✅ Подписка добавлена." if added else "Такая подписка уже существует.", reply_markup=ctx.alerts_menu())
        ctx.bot.send_message(chat_id, ctx.format_alert_subscriptions(user_data), reply_markup=ctx.alerts_menu())
        return

    if call.data.startswith("alerts_sub_add_saved:"):
        location_id = call.data.split(":", 1)[1] if ":" in call.data else ""
        if not location_id:
            ctx.bot.answer_callback_query(call.id)
            ctx.bot.send_message(
                chat_id,
                "⚠️ Не удалось выбрать локацию.",
                reply_markup=ctx.alerts_add_location_menu(),
            )
            return

        user_data = ctx.load_user(user_id)
        saved_locations = user_data.get("saved_locations", [])
        if not isinstance(saved_locations, list) or not saved_locations:
            ctx.bot.answer_callback_query(call.id)
            session_store.user_states[user_id] = WAITING_ALERTS_ADD_MENU
            ctx.bot.send_message(
                chat_id,
                "Сохранённых локаций пока нет.",
                reply_markup=ctx.alerts_add_location_menu(),
            )
            return

        selected_item = next(
            (item for item in saved_locations if isinstance(item, dict) and item.get("id") == location_id),
            None,
        )
        if not isinstance(selected_item, dict):
            ctx.bot.answer_callback_query(call.id)
            session_store.user_states[user_id] = WAITING_ALERTS_ADD_MENU
            ctx.bot.send_message(
                chat_id,
                "⚠️ Выбранная локация не найдена. Попробуй снова.",
                reply_markup=ctx.alerts_add_location_menu(),
            )
            return

        lat = selected_item.get("lat")
        lon = selected_item.get("lon")
        label = selected_item.get("label") or selected_item.get("title") or "Выбранная локация"
        if lat is None or lon is None:
            ctx.bot.answer_callback_query(call.id)
            session_store.user_states[user_id] = WAITING_ALERTS_ADD_MENU
            ctx.bot.send_message(
                chat_id,
                "⚠️ У выбранной локации отсутствуют координаты. Выбери другую.",
                reply_markup=ctx.alerts_add_location_menu(),
            )
            return

        user_data, added = service.add_subscription(
            user_data,
            location_id=str(selected_item.get("id") or location_id),
            title=str(selected_item.get("title") or label),
            label=str(label),
            lat=float(lat),
            lon=float(lon),
        )
        if added:
            ctx.save_user(user_id, user_data)
        session_store.alerts_location_choices.pop(user_id, None)
        session_store.user_states[user_id] = ALERTS_MENU

        ctx.bot.answer_callback_query(call.id)
        ctx.bot.send_message(
            chat_id,
            "✅ Подписка добавлена." if added else "Такая подписка уже существует.",
            reply_markup=ctx.alerts_menu(),
        )
        ctx.bot.send_message(
            chat_id,
            ctx.format_alert_subscriptions(user_data),
            reply_markup=ctx.alerts_menu(),
        )
        return

    if call.data.startswith("alerts_sub_toggle:"):
        subscription_id = call.data.split(":", 1)[1] if ":" in call.data else ""
        ctx.bot.answer_callback_query(call.id)
        user_data, toggled = service.toggle_subscription(user_data, subscription_id)
        if not toggled:
            ctx.bot.send_message(chat_id, "⚠️ Подписка не найдена.", reply_markup=ctx.alerts_menu())
            return
        ctx.save_user(user_id, user_data)
        session_store.user_states[user_id] = ALERTS_MENU
        ctx.bot.send_message(chat_id, "✅ Статус подписки обновлён.", reply_markup=ctx.alerts_menu())
        ctx.bot.send_message(chat_id, ctx.format_alert_subscriptions(user_data), reply_markup=ctx.alerts_menu())
        return

    if call.data.startswith("alerts_sub_interval:"):
        subscription_id = call.data.split(":", 1)[1] if ":" in call.data else ""
        ctx.bot.answer_callback_query(call.id)
        target = service.get_subscription(user_data, subscription_id)
        if target is None:
            ctx.bot.send_message(chat_id, "⚠️ Подписка не найдена.", reply_markup=ctx.alerts_menu())
            return
        session_store.alerts_subscription_drafts[user_id] = {"location_id": subscription_id}
        session_store.user_states[user_id] = WAITING_ALERTS_INTERVAL_VALUE
        title = str(target.get("title") or target.get("label") or "подписка")
        ctx.bot.send_message(
            chat_id,
            f"Введи новый интервал в часах для подписки {title}",
            reply_markup=ctx.alerts_menu(),
        )
        return

    if call.data.startswith("alerts_sub_delete:"):
        subscription_id = call.data.split(":", 1)[1] if ":" in call.data else ""
        ctx.bot.answer_callback_query(call.id)
        user_data, deleted = service.delete_subscription(user_data, subscription_id)
        if not deleted:
            ctx.bot.send_message(chat_id, "⚠️ Подписка не найдена.", reply_markup=ctx.alerts_menu())
            return
        ctx.save_user(user_id, user_data)
        session_store.user_states[user_id] = ALERTS_MENU
        ctx.bot.send_message(chat_id, "✅ Подписка удалена.", reply_markup=ctx.alerts_menu())
        ctx.bot.send_message(chat_id, ctx.format_alert_subscriptions(user_data), reply_markup=ctx.alerts_menu())
        return

    ctx.bot.answer_callback_query(call.id)
