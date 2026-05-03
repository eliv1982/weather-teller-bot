from .callbacks_common import mark_location_choice_selected


def handle_source_compare_callback(
    call,
    *,
    ctx,
    session_store,
    send_source_compare_by_coordinates,
    _message_stub_for_chat,
) -> None:
    """Handles inline location choice for source-compare flow."""
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    if call.data == "source_compare_cancel":
        session_store.source_compare_location_choices.pop(user_id, None)
        session_store.user_states.pop(user_id, None)
        ctx.bot.answer_callback_query(call.id)
        ctx.bot.send_message(chat_id, "Выбор отменён.", reply_markup=ctx.main_menu())
        return

    if call.data.startswith("source_compare_pick:"):
        try:
            index = int(call.data.split(":", 1)[1])
        except (ValueError, IndexError):
            ctx.bot.answer_callback_query(call.id)
            session_store.user_states.pop(user_id, None)
            session_store.source_compare_location_choices.pop(user_id, None)
            ctx.bot.send_message(
                chat_id,
                "⚠️ Список вариантов устарел. Введи населённый пункт заново.",
                reply_markup=ctx.main_menu(),
            )
            return

        choices = session_store.source_compare_location_choices.get(user_id)
        if not choices or index < 0 or index >= len(choices):
            ctx.bot.answer_callback_query(call.id)
            session_store.user_states.pop(user_id, None)
            session_store.source_compare_location_choices.pop(user_id, None)
            ctx.bot.send_message(
                chat_id,
                "⚠️ Список вариантов устарел. Введи населённый пункт заново.",
                reply_markup=ctx.main_menu(),
            )
            return

        location_item = ctx.build_geocode_item_with_disambiguated_label(choices, index)
        city = location_item.get("label") or ctx.build_location_label(location_item, show_coords=False)
        lat = location_item.get("lat")
        lon = location_item.get("lon")
        if lat is None or lon is None:
            session_store.source_compare_location_choices.pop(user_id, None)
            session_store.user_states.pop(user_id, None)
            ctx.bot.answer_callback_query(call.id)
            ctx.bot.send_message(
                chat_id,
                "Не удалось сверить источники: один из прогнозов сейчас недоступен.",
                reply_markup=ctx.main_menu(),
            )
            return
        ctx.bot.answer_callback_query(call.id)
        mark_location_choice_selected(call, ctx, str(city))
        stub = _message_stub_for_chat(chat_id)
        send_source_compare_by_coordinates(
            stub,
            user_id,
            float(lat),
            float(lon),
            city,
            preferred_city_label=city,
        )
        return

    if call.data.startswith("source_compare_saved_pick:"):
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
        mark_location_choice_selected(call, ctx, city)
        stub = _message_stub_for_chat(chat_id)
        send_source_compare_by_coordinates(
            stub,
            user_id,
            float(lat),
            float(lon),
            city,
            preferred_city_label=city,
        )
        return

    ctx.bot.answer_callback_query(call.id)
