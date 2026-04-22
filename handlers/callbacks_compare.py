def handle_compare_location_callback(
    call,
    *,
    ctx,
    session_store,
    WAITING_COMPARE_CITY_2,
    complete_compare_two_locations,
) -> None:
    """Обрабатывает выбор населённого пункта при сравнении (inline) или отмену."""
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    if call.data == "compare_cancel":
        session_store.compare_location_choices.pop(user_id, None)
        session_store.compare_drafts.pop(user_id, None)
        session_store.user_states.pop(user_id, None)
        ctx.bot.answer_callback_query(call.id)
        ctx.bot.send_message(chat_id, "Выбор отменён.", reply_markup=ctx.main_menu())
        return

    parts = call.data.split(":")
    if len(parts) != 3 or parts[0] != "compare_pick":
        ctx.bot.answer_callback_query(call.id)
        return

    try:
        step = int(parts[1])
        index = int(parts[2])
    except ValueError:
        ctx.bot.answer_callback_query(call.id)
        session_store.compare_location_choices.pop(user_id, None)
        session_store.compare_drafts.pop(user_id, None)
        session_store.user_states.pop(user_id, None)
        ctx.bot.send_message(
            chat_id,
            "⚠️ Список вариантов устарел. Введи населённый пункт заново.",
            reply_markup=ctx.main_menu(),
        )
        return

    meta = session_store.compare_location_choices.get(user_id)
    if not meta or not isinstance(meta.get("locations"), list):
        ctx.bot.answer_callback_query(call.id)
        session_store.compare_location_choices.pop(user_id, None)
        session_store.compare_drafts.pop(user_id, None)
        session_store.user_states.pop(user_id, None)
        ctx.bot.send_message(
            chat_id,
            "⚠️ Список вариантов устарел. Введи населённый пункт заново.",
            reply_markup=ctx.main_menu(),
        )
        return

    if meta.get("step") != step:
        ctx.bot.answer_callback_query(call.id)
        session_store.compare_location_choices.pop(user_id, None)
        session_store.compare_drafts.pop(user_id, None)
        session_store.user_states.pop(user_id, None)
        ctx.bot.send_message(
            chat_id,
            "⚠️ Список вариантов устарел. Введи населённый пункт заново.",
            reply_markup=ctx.main_menu(),
        )
        return

    locations = meta["locations"]
    if index < 0 or index >= len(locations):
        ctx.bot.answer_callback_query(call.id)
        session_store.compare_location_choices.pop(user_id, None)
        session_store.compare_drafts.pop(user_id, None)
        session_store.user_states.pop(user_id, None)
        ctx.bot.send_message(
            chat_id,
            "⚠️ Список вариантов устарел. Введи населённый пункт заново.",
            reply_markup=ctx.main_menu(),
        )
        return

    location_item = ctx.build_geocode_item_with_disambiguated_label(locations, index)
    lat = location_item.get("lat")
    lon = location_item.get("lon")
    if lat is None or lon is None:
        ctx.bot.answer_callback_query(call.id)
        session_store.compare_location_choices.pop(user_id, None)
        session_store.user_states.pop(user_id, None)
        ctx.bot.send_message(
            chat_id,
            "Не удалось получить данные для сравнения. Попробуй позже.",
            reply_markup=ctx.main_menu(),
        )
        return

    city_label = location_item.get("label") or ctx.build_location_label(location_item, show_coords=False)
    ctx.logger.info(
        "Пользователь %s выбрал населённый пункт для сравнения (шаг %s) #%s: %s",
        user_id,
        step,
        index,
        city_label,
    )
    ctx.bot.answer_callback_query(call.id)

    if step == 1:
        session_store.compare_drafts[user_id] = {
            "coordinates_1": (float(lat), float(lon)),
            "city_1_input": city_label,
            "city_1_label": city_label,
        }
        session_store.compare_location_choices.pop(user_id, None)
        session_store.user_states[user_id] = WAITING_COMPARE_CITY_2
        ctx.bot.send_message(chat_id, "Теперь введи второй населённый пункт.")
        return

    if step == 2:
        draft = session_store.compare_drafts.get(user_id)
        if not draft or "coordinates_1" not in draft:
            session_store.compare_location_choices.pop(user_id, None)
            session_store.compare_drafts.pop(user_id, None)
            session_store.user_states.pop(user_id, None)
            ctx.bot.send_message(
                chat_id,
                "⚠️ Список вариантов устарел. Введи населённый пункт заново.",
                reply_markup=ctx.main_menu(),
            )
            return

        lat_1, lon_1 = draft["coordinates_1"]
        city_label_1 = draft.get("city_1_label") or draft.get("city_1_input") or "Первый населённый пункт"
        complete_compare_two_locations(
            chat_id,
            user_id,
            lat_1,
            lon_1,
            city_label_1,
            float(lat),
            float(lon),
            city_label,
        )
