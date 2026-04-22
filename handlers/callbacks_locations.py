def handle_favorite_pick_callback(
    call,
    *,
    ctx,
    session_store,
    LOCATIONS_MENU,
) -> None:
    """Обрабатывает выбор основной локации из списка сохранённых."""
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    location_id = call.data.split(":", 1)[1] if ":" in call.data else ""
    if not location_id:
        ctx.bot.answer_callback_query(call.id)
        ctx.bot.send_message(chat_id, "⚠️ Не удалось выбрать основную локацию.", reply_markup=ctx.locations_menu())
        return

    user_data = ctx.load_user(user_id)
    saved_locations = user_data.get("saved_locations", [])
    if not isinstance(saved_locations, list) or not saved_locations:
        ctx.bot.answer_callback_query(call.id)
        ctx.bot.send_message(chat_id, "Сохранённых локаций пока нет.", reply_markup=ctx.locations_menu())
        return

    location_exists = any(
        isinstance(item, dict) and item.get("id") == location_id
        for item in saved_locations
    )
    if not location_exists:
        ctx.bot.answer_callback_query(call.id)
        ctx.bot.send_message(
            chat_id,
            "⚠️ Выбранная локация не найдена. Попробуй снова.",
            reply_markup=ctx.locations_menu(),
        )
        return

    user_data["favorite_location_id"] = location_id
    ctx.save_user(user_id, user_data)
    session_store.user_states[user_id] = LOCATIONS_MENU
    ctx.logger.info("Пользователь %s выбрал основную локацию: %s", user_id, location_id)

    ctx.bot.answer_callback_query(call.id)
    ctx.bot.send_message(
        chat_id,
        "✅ Основная локация обновлена.\n\n" + ctx.format_saved_locations(user_data),
        reply_markup=ctx.locations_menu(),
    )


def handle_delete_location_pick_callback(
    call,
    *,
    ctx,
    session_store,
    LOCATIONS_MENU,
) -> None:
    """Удаляет выбранную сохранённую локацию."""
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    location_id = call.data.split(":", 1)[1] if ":" in call.data else ""

    if not location_id:
        ctx.bot.answer_callback_query(call.id)
        ctx.bot.send_message(chat_id, "⚠️ Не удалось удалить локацию.", reply_markup=ctx.locations_menu())
        return

    user_data = ctx.load_user(user_id)
    saved_locations = user_data.get("saved_locations", [])
    if not isinstance(saved_locations, list) or not saved_locations:
        ctx.bot.answer_callback_query(call.id)
        ctx.bot.send_message(chat_id, "Сохранённых локаций пока нет.", reply_markup=ctx.locations_menu())
        return

    filtered_locations = [
        item
        for item in saved_locations
        if not (isinstance(item, dict) and item.get("id") == location_id)
    ]

    if len(filtered_locations) == len(saved_locations):
        ctx.bot.answer_callback_query(call.id)
        ctx.bot.send_message(chat_id, "⚠️ Выбранная локация не найдена.", reply_markup=ctx.locations_menu())
        return

    user_data["saved_locations"] = filtered_locations
    if user_data.get("favorite_location_id") == location_id:
        user_data["favorite_location_id"] = None
    ctx.save_user(user_id, user_data)
    session_store.user_states[user_id] = LOCATIONS_MENU
    session_store.rename_location_drafts.pop(user_id, None)

    ctx.bot.answer_callback_query(call.id)
    ctx.bot.send_message(
        chat_id,
        "✅ Локация удалена.\n\n" + ctx.format_saved_locations(user_data),
        reply_markup=ctx.locations_menu(),
    )


def handle_rename_location_pick_callback(
    call,
    *,
    ctx,
    session_store,
    LOCATIONS_MENU,
    WAITING_RENAME_LOCATION_TITLE,
    types,
) -> None:
    """Запоминает выбранную локацию и запрашивает новое имя."""
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    location_id = call.data.split(":", 1)[1] if ":" in call.data else ""

    if not location_id:
        ctx.bot.answer_callback_query(call.id)
        ctx.bot.send_message(chat_id, "⚠️ Не удалось выбрать локацию.", reply_markup=ctx.locations_menu())
        return

    user_data = ctx.load_user(user_id)
    saved_locations = user_data.get("saved_locations", [])
    if not isinstance(saved_locations, list) or not saved_locations:
        ctx.bot.answer_callback_query(call.id)
        ctx.bot.send_message(chat_id, "Сохранённых локаций пока нет.", reply_markup=ctx.locations_menu())
        return

    location_exists = any(
        isinstance(item, dict) and item.get("id") == location_id
        for item in saved_locations
    )
    if not location_exists:
        ctx.bot.answer_callback_query(call.id)
        ctx.bot.send_message(chat_id, "⚠️ Выбранная локация не найдена.", reply_markup=ctx.locations_menu())
        return

    session_store.rename_location_drafts[user_id] = {"location_id": location_id}
    session_store.user_states[user_id] = WAITING_RENAME_LOCATION_TITLE
    ctx.bot.answer_callback_query(call.id)
    ctx.bot.send_message(
        chat_id,
        "Введи новое название для локации.",
        reply_markup=types.ReplyKeyboardRemove(),
    )


def handle_saved_location_pick_callback(
    call,
    *,
    ctx,
    session_store,
    LOCATIONS_MENU,
    WAITING_NEW_SAVED_LOCATION_TITLE,
    types,
) -> None:
    """Обрабатывает выбор локации при добавлении новой сохранённой локации."""
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    if call.data == "savedloc_cancel":
        session_store.saved_location_drafts.pop(user_id, None)
        session_store.user_states[user_id] = LOCATIONS_MENU
        ctx.bot.answer_callback_query(call.id)
        ctx.bot.send_message(chat_id, "Выбор отменён.", reply_markup=ctx.locations_menu())
        return

    if call.data.startswith("savedloc_pick:"):
        try:
            index = int(call.data.split(":", 1)[1])
        except (ValueError, IndexError):
            session_store.saved_location_drafts.pop(user_id, None)
            session_store.user_states[user_id] = LOCATIONS_MENU
            ctx.bot.answer_callback_query(call.id)
            ctx.bot.send_message(
                chat_id,
                "⚠️ Список вариантов устарел. Начни добавление заново.",
                reply_markup=ctx.locations_menu(),
            )
            return

        draft = session_store.saved_location_drafts.get(user_id)
        locations = draft.get("locations") if isinstance(draft, dict) else None
        if not isinstance(locations, list) or index < 0 or index >= len(locations):
            session_store.saved_location_drafts.pop(user_id, None)
            session_store.user_states[user_id] = LOCATIONS_MENU
            ctx.bot.answer_callback_query(call.id)
            ctx.bot.send_message(
                chat_id,
                "⚠️ Список вариантов устарел. Начни добавление заново.",
                reply_markup=ctx.locations_menu(),
            )
            return

        location_item = ctx.build_geocode_item_with_disambiguated_label(locations, index)
        lat = location_item.get("lat")
        lon = location_item.get("lon")
        label = location_item.get("label") or ctx.build_location_label(location_item, show_coords=False)
        if lat is None or lon is None:
            session_store.saved_location_drafts.pop(user_id, None)
            session_store.user_states[user_id] = LOCATIONS_MENU
            ctx.bot.answer_callback_query(call.id)
            ctx.bot.send_message(
                chat_id,
                "Не удалось определить локацию. Попробуй снова.",
                reply_markup=ctx.locations_menu(),
            )
            return

        session_store.saved_location_drafts[user_id] = {
            "lat": float(lat),
            "lon": float(lon),
            "label": label,
        }
        session_store.user_states[user_id] = WAITING_NEW_SAVED_LOCATION_TITLE
        ctx.bot.answer_callback_query(call.id)
        ctx.bot.send_message(
            chat_id,
            "Введи название для этой локации, например: Дом",
            reply_markup=types.ReplyKeyboardRemove(),
        )
        return

    ctx.bot.answer_callback_query(call.id)
