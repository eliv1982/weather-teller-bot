def handle_favorite_pick_callback(
    call,
    *,
    bot,
    logger,
    user_states: dict,
    LOCATIONS_MENU,
    load_user,
    save_user,
    format_saved_locations,
    locations_menu,
) -> None:
    """Обрабатывает выбор основной локации из списка сохранённых."""
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    location_id = call.data.split(":", 1)[1] if ":" in call.data else ""
    if not location_id:
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "⚠️ Не удалось выбрать основную локацию.", reply_markup=locations_menu())
        return

    user_data = load_user(user_id)
    saved_locations = user_data.get("saved_locations", [])
    if not isinstance(saved_locations, list) or not saved_locations:
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "Сохранённых локаций пока нет.", reply_markup=locations_menu())
        return

    location_exists = any(
        isinstance(item, dict) and item.get("id") == location_id
        for item in saved_locations
    )
    if not location_exists:
        bot.answer_callback_query(call.id)
        bot.send_message(
            chat_id,
            "⚠️ Выбранная локация не найдена. Попробуй снова.",
            reply_markup=locations_menu(),
        )
        return

    user_data["favorite_location_id"] = location_id
    save_user(user_id, user_data)
    user_states[user_id] = LOCATIONS_MENU
    logger.info("Пользователь %s выбрал основную локацию: %s", user_id, location_id)

    bot.answer_callback_query(call.id)
    bot.send_message(
        chat_id,
        "✅ Основная локация обновлена.\n\n" + format_saved_locations(user_data),
        reply_markup=locations_menu(),
    )


def handle_delete_location_pick_callback(
    call,
    *,
    bot,
    user_states: dict,
    rename_location_drafts: dict,
    LOCATIONS_MENU,
    load_user,
    save_user,
    format_saved_locations,
    locations_menu,
) -> None:
    """Удаляет выбранную сохранённую локацию."""
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    location_id = call.data.split(":", 1)[1] if ":" in call.data else ""

    if not location_id:
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "⚠️ Не удалось удалить локацию.", reply_markup=locations_menu())
        return

    user_data = load_user(user_id)
    saved_locations = user_data.get("saved_locations", [])
    if not isinstance(saved_locations, list) or not saved_locations:
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "Сохранённых локаций пока нет.", reply_markup=locations_menu())
        return

    filtered_locations = [
        item
        for item in saved_locations
        if not (isinstance(item, dict) and item.get("id") == location_id)
    ]

    if len(filtered_locations) == len(saved_locations):
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "⚠️ Выбранная локация не найдена.", reply_markup=locations_menu())
        return

    user_data["saved_locations"] = filtered_locations
    if user_data.get("favorite_location_id") == location_id:
        user_data["favorite_location_id"] = None
    save_user(user_id, user_data)
    user_states[user_id] = LOCATIONS_MENU
    rename_location_drafts.pop(user_id, None)

    bot.answer_callback_query(call.id)
    bot.send_message(
        chat_id,
        "✅ Локация удалена.\n\n" + format_saved_locations(user_data),
        reply_markup=locations_menu(),
    )


def handle_rename_location_pick_callback(
    call,
    *,
    bot,
    user_states: dict,
    rename_location_drafts: dict,
    LOCATIONS_MENU,
    WAITING_RENAME_LOCATION_TITLE,
    load_user,
    locations_menu,
    types,
) -> None:
    """Запоминает выбранную локацию и запрашивает новое имя."""
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    location_id = call.data.split(":", 1)[1] if ":" in call.data else ""

    if not location_id:
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "⚠️ Не удалось выбрать локацию.", reply_markup=locations_menu())
        return

    user_data = load_user(user_id)
    saved_locations = user_data.get("saved_locations", [])
    if not isinstance(saved_locations, list) or not saved_locations:
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "Сохранённых локаций пока нет.", reply_markup=locations_menu())
        return

    location_exists = any(
        isinstance(item, dict) and item.get("id") == location_id
        for item in saved_locations
    )
    if not location_exists:
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "⚠️ Выбранная локация не найдена.", reply_markup=locations_menu())
        return

    rename_location_drafts[user_id] = {"location_id": location_id}
    user_states[user_id] = WAITING_RENAME_LOCATION_TITLE
    bot.answer_callback_query(call.id)
    bot.send_message(
        chat_id,
        "Введи новое название для локации.",
        reply_markup=types.ReplyKeyboardRemove(),
    )


def handle_saved_location_pick_callback(
    call,
    *,
    bot,
    user_states: dict,
    saved_location_drafts: dict,
    LOCATIONS_MENU,
    WAITING_NEW_SAVED_LOCATION_TITLE,
    build_geocode_item_with_disambiguated_label,
    build_location_label,
    locations_menu,
    types,
) -> None:
    """Обрабатывает выбор локации при добавлении новой сохранённой локации."""
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    if call.data == "savedloc_cancel":
        saved_location_drafts.pop(user_id, None)
        user_states[user_id] = LOCATIONS_MENU
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "Выбор отменён.", reply_markup=locations_menu())
        return

    if call.data.startswith("savedloc_pick:"):
        try:
            index = int(call.data.split(":", 1)[1])
        except (ValueError, IndexError):
            saved_location_drafts.pop(user_id, None)
            user_states[user_id] = LOCATIONS_MENU
            bot.answer_callback_query(call.id)
            bot.send_message(
                chat_id,
                "⚠️ Список вариантов устарел. Начни добавление заново.",
                reply_markup=locations_menu(),
            )
            return

        draft = saved_location_drafts.get(user_id)
        locations = draft.get("locations") if isinstance(draft, dict) else None
        if not isinstance(locations, list) or index < 0 or index >= len(locations):
            saved_location_drafts.pop(user_id, None)
            user_states[user_id] = LOCATIONS_MENU
            bot.answer_callback_query(call.id)
            bot.send_message(
                chat_id,
                "⚠️ Список вариантов устарел. Начни добавление заново.",
                reply_markup=locations_menu(),
            )
            return

        location_item = build_geocode_item_with_disambiguated_label(locations, index)
        lat = location_item.get("lat")
        lon = location_item.get("lon")
        label = location_item.get("label") or build_location_label(location_item, show_coords=False)
        if lat is None or lon is None:
            saved_location_drafts.pop(user_id, None)
            user_states[user_id] = LOCATIONS_MENU
            bot.answer_callback_query(call.id)
            bot.send_message(
                chat_id,
                "Не удалось определить локацию. Попробуй снова.",
                reply_markup=locations_menu(),
            )
            return

        saved_location_drafts[user_id] = {
            "lat": float(lat),
            "lon": float(lon),
            "label": label,
        }
        user_states[user_id] = WAITING_NEW_SAVED_LOCATION_TITLE
        bot.answer_callback_query(call.id)
        bot.send_message(
            chat_id,
            "Введи название для этой локации, например: Дом",
            reply_markup=types.ReplyKeyboardRemove(),
        )
        return

    bot.answer_callback_query(call.id)
