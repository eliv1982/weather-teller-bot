from weather_history_service import format_history_date_label, resolve_history_preset_date

from .callbacks_common import clear_inline_choice_message
from .states import WAITING_HISTORY_CITY, WAITING_HISTORY_CUSTOM_DATE


def handle_history_callback(
    call,
    *,
    ctx,
    session_store,
    prepare_weather_history_by_coordinates,
    send_weather_history_by_date,
    _message_stub_for_chat,
) -> None:
    """Handles inline location/date callbacks for the archive weather flow."""
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    if call.data == "history_cancel":
        session_store.history_location_choices.pop(user_id, None)
        ctx.bot.answer_callback_query(call.id)
        clear_inline_choice_message(call, ctx)
        user_data = ctx.load_user(user_id)
        has_saved = isinstance(user_data.get("saved_locations"), list) and bool(user_data.get("saved_locations"))
        session_store.user_states[user_id] = WAITING_HISTORY_CITY
        ctx.bot.send_message(
            chat_id,
            "Введи название населенного пункта или выбери другой способ ниже:",
            reply_markup=ctx.location_input_menu(has_saved_locations=has_saved),
        )
        return

    if call.data.startswith("history_pick:"):
        try:
            index = int(call.data.split(":", 1)[1])
        except (ValueError, IndexError):
            ctx.bot.answer_callback_query(call.id)
            clear_inline_choice_message(call, ctx)
            session_store.user_states.pop(user_id, None)
            session_store.history_location_choices.pop(user_id, None)
            ctx.bot.send_message(
                chat_id,
                "⚠️ Список вариантов устарел. Введи населенный пункт заново.",
                reply_markup=ctx.main_menu(),
            )
            return

        choices = session_store.history_location_choices.get(user_id)
        if not choices or index < 0 or index >= len(choices):
            ctx.bot.answer_callback_query(call.id)
            clear_inline_choice_message(call, ctx)
            session_store.user_states.pop(user_id, None)
            session_store.history_location_choices.pop(user_id, None)
            ctx.bot.send_message(
                chat_id,
                "⚠️ Список вариантов устарел. Введи населенный пункт заново.",
                reply_markup=ctx.main_menu(),
            )
            return

        location_item = ctx.build_geocode_item_with_disambiguated_label(choices, index)
        city = location_item.get("label") or ctx.build_location_label(location_item, show_coords=False)
        lat = location_item.get("lat")
        lon = location_item.get("lon")
        if lat is None or lon is None:
            session_store.history_location_choices.pop(user_id, None)
            session_store.user_states.pop(user_id, None)
            ctx.bot.answer_callback_query(call.id)
            ctx.bot.send_message(
                chat_id,
                "Не удалось подготовить архивную справку по этой локации. Попробуй позже.",
                reply_markup=ctx.main_menu(),
            )
            return
        ctx.bot.answer_callback_query(call.id)
        clear_inline_choice_message(call, ctx)
        stub = _message_stub_for_chat(chat_id)
        prepare_weather_history_by_coordinates(
            stub,
            user_id,
            float(lat),
            float(lon),
            city,
            preferred_city_label=city,
        )
        return

    if call.data.startswith("history_saved_pick:"):
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
            ctx.bot.send_message(chat_id, "⚠️ Сохраненная локация не найдена.", reply_markup=ctx.main_menu())
            return
        lat = target.get("lat")
        lon = target.get("lon")
        city = str(target.get("label") or target.get("title") or "Сохраненная локация")
        if lat is None or lon is None:
            ctx.bot.answer_callback_query(call.id)
            session_store.user_states.pop(user_id, None)
            ctx.bot.send_message(chat_id, "⚠️ У сохраненной локации нет координат.", reply_markup=ctx.main_menu())
            return
        ctx.bot.answer_callback_query(call.id)
        clear_inline_choice_message(call, ctx)
        stub = _message_stub_for_chat(chat_id)
        prepare_weather_history_by_coordinates(
            stub,
            user_id,
            float(lat),
            float(lon),
            city,
            preferred_city_label=city,
        )
        return

    if call.data == "history_menu":
        session_store.history_location_choices.pop(user_id, None)
        session_store.history_drafts.pop(user_id, None)
        session_store.user_states.pop(user_id, None)
        ctx.bot.answer_callback_query(call.id)
        clear_inline_choice_message(call, ctx)
        ctx.bot.send_message(chat_id, "Главное меню.", reply_markup=ctx.main_menu())
        return

    if call.data == "history_date_custom":
        draft = session_store.history_drafts.get(user_id)
        if not isinstance(draft, dict):
            ctx.bot.answer_callback_query(call.id, "Данные устарели. Начни историю погоды заново.")
            return
        session_store.user_states[user_id] = WAITING_HISTORY_CUSTOM_DATE
        ctx.bot.answer_callback_query(call.id)
        clear_inline_choice_message(call, ctx)
        ctx.bot.send_message(chat_id, "✅ Выбрано: ввести дату вручную")
        ctx.bot.send_message(
            chat_id,
            "Введи дату в формате YYYY-MM-DD или DD.MM.YYYY.\nНужна дата из прошлого.",
        )
        return

    if call.data.startswith("history_date_preset:"):
        preset = call.data.split(":", 1)[1] if ":" in call.data else ""
        target_date = resolve_history_preset_date(preset)
        if target_date is None:
            ctx.bot.answer_callback_query(call.id, "Не удалось определить дату.")
            return
        ctx.bot.answer_callback_query(call.id)
        clear_inline_choice_message(call, ctx)
        ctx.bot.send_message(chat_id, f"✅ Выбрано: {format_history_date_label(target_date)}")
        stub = _message_stub_for_chat(chat_id)
        send_weather_history_by_date(stub, user_id, target_date, send_confirmation=False)
        return

    ctx.bot.answer_callback_query(call.id)
