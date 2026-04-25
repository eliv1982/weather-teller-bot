from .locations import (
    _ai_compare_day_payload,
    _ai_compare_reset,
    _ai_compare_set_location,
    format_ai_compare_day_summary_message,
)
from .states import (
    LOCATIONS_MENU,
    WAITING_AI_COMPARE_DATE_PICK,
    WAITING_AI_COMPARE_LOC1_METHOD,
    WAITING_AI_COMPARE_LOC1_PICK,
    WAITING_AI_COMPARE_LOC1_SAVED_PICK,
    WAITING_AI_COMPARE_LOC2_METHOD,
    WAITING_AI_COMPARE_LOC2_PICK,
    WAITING_AI_COMPARE_LOC2_SAVED_PICK,
)


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


def handle_ai_compare_callback(
    call,
    *,
    ctx,
    session_store,
) -> None:
    """Обрабатывает callback-ветки умного AI-сравнения локаций."""
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    data = call.data
    state = session_store.get_state(user_id)

    if data == "aicmp_geo_cancel":
        if state == WAITING_AI_COMPARE_LOC1_PICK:
            session_store.ai_compare_location_choices.pop(user_id, None)
            session_store.user_states[user_id] = WAITING_AI_COMPARE_LOC1_METHOD
            ctx.bot.answer_callback_query(call.id)
            ctx.bot.send_message(
                chat_id,
                "Выбор населённого пункта отменён. Введи название первой локации или выбери другой способ ниже:",
                reply_markup=ctx.ai_compare_location_method_menu(),
            )
            return
        if state == WAITING_AI_COMPARE_LOC2_PICK:
            session_store.ai_compare_location_choices.pop(user_id, None)
            session_store.user_states[user_id] = WAITING_AI_COMPARE_LOC2_METHOD
            ctx.bot.answer_callback_query(call.id)
            ctx.bot.send_message(
                chat_id,
                "Выбор населённого пункта отменён. Введи название второй локации или выбери другой способ ниже:",
                reply_markup=ctx.ai_compare_location_method_menu(),
            )
            return
        _ai_compare_reset(user_id, session_store=session_store)
        session_store.user_states.pop(user_id, None)
        ctx.bot.answer_callback_query(call.id)
        ctx.bot.send_message(chat_id, "Сравнение отменено.", reply_markup=ctx.main_menu())
        return

    if data == "aicmp_saved_cancel":
        if state == WAITING_AI_COMPARE_LOC1_SAVED_PICK:
            session_store.user_states[user_id] = WAITING_AI_COMPARE_LOC1_METHOD
            ctx.bot.answer_callback_query(call.id)
            ctx.bot.send_message(
                chat_id,
                "Выбор сохранённой локации отменён. Введи название первой локации или выбери другой способ ниже:",
                reply_markup=ctx.ai_compare_location_method_menu(),
            )
            return
        if state == WAITING_AI_COMPARE_LOC2_SAVED_PICK:
            session_store.user_states[user_id] = WAITING_AI_COMPARE_LOC2_METHOD
            ctx.bot.answer_callback_query(call.id)
            ctx.bot.send_message(
                chat_id,
                "Выбор сохранённой локации отменён. Введи название второй локации или выбери другой способ ниже:",
                reply_markup=ctx.ai_compare_location_method_menu(),
            )
            return
        _ai_compare_reset(user_id, session_store=session_store)
        session_store.user_states.pop(user_id, None)
        ctx.bot.answer_callback_query(call.id)
        ctx.bot.send_message(chat_id, "Сравнение отменено.", reply_markup=ctx.main_menu())
        return

    if data == "aicmp_date_cancel":
        _ai_compare_reset(user_id, session_store=session_store)
        session_store.user_states.pop(user_id, None)
        ctx.bot.answer_callback_query(call.id)
        ctx.bot.send_message(chat_id, "Сравнение отменено.", reply_markup=ctx.main_menu())
        return

    if data.startswith("aicmp_geo_pick:"):
        parts = data.split(":")
        if len(parts) != 3:
            ctx.bot.answer_callback_query(call.id)
            return
        try:
            step = int(parts[1])
            index = int(parts[2])
        except (TypeError, ValueError):
            ctx.bot.answer_callback_query(call.id)
            return
        if step not in (1, 2):
            ctx.bot.answer_callback_query(call.id)
            return
        expected_state = WAITING_AI_COMPARE_LOC1_PICK if step == 1 else WAITING_AI_COMPARE_LOC2_PICK
        if state != expected_state:
            ctx.bot.answer_callback_query(call.id, "Данные устарели. Начни сравнение заново.")
            return
        locations = session_store.ai_compare_location_choices.get(user_id)
        if not isinstance(locations, list) or index < 0 or index >= len(locations):
            ctx.bot.answer_callback_query(call.id, "Данные устарели. Начни сравнение заново.")
            return
        location_item = ctx.build_geocode_item_with_disambiguated_label(locations, index)
        lat = location_item.get("lat")
        lon = location_item.get("lon")
        if lat is None or lon is None:
            ctx.bot.answer_callback_query(call.id, "Не удалось определить локацию.")
            return
        city_label = location_item.get("label") or ctx.build_location_label(location_item, show_coords=False)
        ctx.bot.answer_callback_query(call.id)
        stub = type("MsgStub", (), {"chat": type("ChatStub", (), {"id": chat_id})()})()
        _ai_compare_set_location(
            stub,
            user_id,
            step=step,
            city_label=str(city_label),
            lat=float(lat),
            lon=float(lon),
            ctx=ctx,
            session_store=session_store,
        )
        return

    if data.startswith("aicmp_saved_pick:"):
        parts = data.split(":", 2)
        if len(parts) != 3:
            ctx.bot.answer_callback_query(call.id)
            return
        try:
            step = int(parts[1])
        except (TypeError, ValueError):
            ctx.bot.answer_callback_query(call.id)
            return
        location_id = parts[2]
        if step not in (1, 2) or not location_id:
            ctx.bot.answer_callback_query(call.id)
            return
        expected_state = WAITING_AI_COMPARE_LOC1_SAVED_PICK if step == 1 else WAITING_AI_COMPARE_LOC2_SAVED_PICK
        if state != expected_state:
            ctx.bot.answer_callback_query(call.id, "Данные устарели. Начни сравнение заново.")
            return
        user_data = ctx.load_user(user_id)
        saved_locations = user_data.get("saved_locations", [])
        if not isinstance(saved_locations, list) or not saved_locations:
            ctx.bot.answer_callback_query(call.id, "Сохранённых локаций пока нет.")
            return
        target = next(
            (item for item in saved_locations if isinstance(item, dict) and item.get("id") == location_id),
            None,
        )
        if not isinstance(target, dict):
            ctx.bot.answer_callback_query(call.id, "Локация не найдена.")
            return
        lat = target.get("lat")
        lon = target.get("lon")
        if lat is None or lon is None:
            ctx.bot.answer_callback_query(call.id, "У локации нет координат.")
            return
        city_label = str(target.get("label") or target.get("title") or "Локация")
        ctx.bot.answer_callback_query(call.id)
        stub = type("MsgStub", (), {"chat": type("ChatStub", (), {"id": chat_id})()})()
        _ai_compare_set_location(
            stub,
            user_id,
            step=step,
            city_label=city_label,
            lat=float(lat),
            lon=float(lon),
            ctx=ctx,
            session_store=session_store,
        )
        return

    if data.startswith("aicmp_date_pick:"):
        selected_day = data.split(":", 1)[1]
        if state != WAITING_AI_COMPARE_DATE_PICK:
            ctx.bot.answer_callback_query(call.id, "Данные устарели. Начни сравнение заново.")
            return
        draft = session_store.ai_compare_drafts.get(user_id)
        if not isinstance(draft, dict):
            ctx.bot.answer_callback_query(call.id, "Данные устарели. Начни сравнение заново.")
            return
        available_days = draft.get("available_days")
        grouped_1 = draft.get("grouped_1")
        grouped_2 = draft.get("grouped_2")
        loc_1 = draft.get("loc_1")
        loc_2 = draft.get("loc_2")
        if (
            not isinstance(available_days, list)
            or selected_day not in available_days
            or not isinstance(grouped_1, dict)
            or not isinstance(grouped_2, dict)
            or not isinstance(loc_1, dict)
            or not isinstance(loc_2, dict)
        ):
            ctx.bot.answer_callback_query(call.id, "Данные устарели. Начни сравнение заново.")
            return
        day_items_1 = grouped_1.get(selected_day)
        day_items_2 = grouped_2.get(selected_day)
        if not isinstance(day_items_1, list) or not isinstance(day_items_2, list):
            ctx.bot.answer_callback_query(call.id, "День недоступен для сравнения.")
            return
        payload_1 = _ai_compare_day_payload(
            str(loc_1.get("city_label")),
            selected_day,
            day_items_1,
            location_meta=loc_1,
        )
        payload_2 = _ai_compare_day_payload(
            str(loc_2.get("city_label")),
            selected_day,
            day_items_2,
            location_meta=loc_2,
        )
        text = ctx.ai_weather_service.compare_two_locations_forecast_day_with_ai(
            payload_1,
            payload_2,
            selected_day,
        )
        _ai_compare_reset(user_id, session_store=session_store)
        session_store.user_states.pop(user_id, None)
        ctx.bot.answer_callback_query(call.id)
        ctx.bot.send_message(
            chat_id,
            format_ai_compare_day_summary_message(payload_1, selected_day, 1),
            reply_markup=ctx.main_menu(),
        )
        ctx.bot.send_message(
            chat_id,
            format_ai_compare_day_summary_message(payload_2, selected_day, 2),
            reply_markup=ctx.main_menu(),
        )
        ctx.bot.send_message(
            chat_id,
            f"✨ Сравнить локации ({selected_day})\n\n🪄 Вывод:\n{text}",
            reply_markup=ctx.main_menu(),
        )
        return

    ctx.bot.answer_callback_query(call.id)
