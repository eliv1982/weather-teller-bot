from datetime import date

from keyboards import (
    build_history_climate_mode_keyboard,
    build_history_date_keyboard,
    build_history_month_keyboard,
    build_history_section_keyboard,
)
from utils.date_parsing import month_name
from weather_history_service import format_history_date_label, resolve_history_preset_date

from .callbacks_common import clear_inline_choice_message, try_delete_message
from .states import (
    WAITING_HISTORY_CITY,
    WAITING_HISTORY_CLIMATE_MODE,
    WAITING_HISTORY_CLIMATE_MONTH,
    WAITING_HISTORY_CLIMATE_YEAR,
    WAITING_HISTORY_CUSTOM_DATE,
    WAITING_HISTORY_DATE_PICK,
    WAITING_HISTORY_SECTION,
)


def _clear_history_runtime(session_store, user_id: int) -> None:
    session_store.history_drafts.pop(user_id, None)
    session_store.clear_state(user_id)


def _notify_stale_history_flow(call, *, chat_id: int, user_id: int, ctx, session_store) -> None:
    _clear_history_runtime(session_store, user_id)
    ctx.bot.answer_callback_query(call.id, "Данные устарели.")
    clear_inline_choice_message(call, ctx)
    main_menu = getattr(ctx, "main_menu", None)
    reply_markup = main_menu() if callable(main_menu) else None
    ctx.bot.send_message(chat_id, "Начни историю погоды заново.", reply_markup=reply_markup)


def handle_history_callback(
    call,
    *,
    ctx,
    session_store,
    prepare_weather_history_by_coordinates,
    send_weather_history_by_date,
    send_history_monthly_report=None,
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
        loc_prompt_msg = ctx.bot.send_message(
            chat_id,
            "Введи название населенного пункта или выбери другой способ ниже:",
            reply_markup=ctx.location_input_menu(has_saved_locations=has_saved),
        )
        _draft = session_store.history_drafts.get(user_id)
        if isinstance(_draft, dict):
            _loc_prompt_id = getattr(loc_prompt_msg, "message_id", None)
            if _loc_prompt_id is not None:
                _draft["location_prompt_message_id"] = _loc_prompt_id
                session_store.history_drafts[user_id] = _draft
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

    if call.data.startswith("history_section:"):
        section = call.data.split(":", 1)[1] if ":" in call.data else ""
        if section not in {"daily", "climate"}:
            ctx.bot.answer_callback_query(call.id, "Не удалось определить раздел.")
            return
        draft = session_store.history_drafts.get(user_id)
        if not isinstance(draft, dict):
            draft = {}
        draft["history_section"] = section
        for key in ("monthly_mode", "monthly_month", "monthly_year", "pending_history_date_options"):
            draft.pop(key, None)
        session_store.history_drafts[user_id] = draft
        ctx.bot.answer_callback_query(call.id)
        clear_inline_choice_message(call, ctx)
        section_label = "на дату" if section == "daily" else "средние климатические показатели"
        ctx.bot.send_message(chat_id, f"✅ Раздел выбран: {section_label}")
        lat = draft.get("lat")
        lon = draft.get("lon")
        city_label = str(draft.get("city_label") or "выбранной локации")
        if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
            if section == "climate":
                session_store.user_states[user_id] = WAITING_HISTORY_CLIMATE_MODE
                keyboard_builder = getattr(ctx, "build_history_climate_mode_keyboard", build_history_climate_mode_keyboard)
                ctx.bot.send_message(
                    chat_id,
                    f"Выбери режим климатической справки по {city_label}:",
                    reply_markup=keyboard_builder(),
                )
                return
            session_store.user_states[user_id] = WAITING_HISTORY_DATE_PICK
            keyboard_builder = getattr(ctx, "build_history_date_keyboard", build_history_date_keyboard)
            ctx.bot.send_message(
                chat_id,
                f"Выбери дату для архивной справки по {city_label}:",
                reply_markup=keyboard_builder(),
            )
            return
        user_data = ctx.load_user(user_id)
        has_saved = isinstance(user_data.get("saved_locations"), list) and bool(user_data.get("saved_locations"))
        session_store.user_states[user_id] = WAITING_HISTORY_CITY
        loc_prompt_msg = ctx.bot.send_message(
            chat_id,
            "Введи название населенного пункта или выбери другой способ ниже:",
            reply_markup=ctx.location_input_menu(has_saved_locations=has_saved),
        )
        _loc_prompt_id = getattr(loc_prompt_msg, "message_id", None)
        if _loc_prompt_id is not None:
            draft["location_prompt_message_id"] = _loc_prompt_id
            session_store.history_drafts[user_id] = draft
        return

    if call.data == "history_date_custom":
        draft = session_store.history_drafts.get(user_id)
        if not isinstance(draft, dict):
            _notify_stale_history_flow(call, chat_id=chat_id, user_id=user_id, ctx=ctx, session_store=session_store)
            return
        for key in ("monthly_mode", "monthly_month", "monthly_year", "pending_history_date_options"):
            draft.pop(key, None)
        session_store.history_drafts[user_id] = draft
        session_store.user_states[user_id] = WAITING_HISTORY_CUSTOM_DATE
        ctx.bot.answer_callback_query(call.id)
        clear_inline_choice_message(call, ctx)
        ctx.bot.send_message(chat_id, "✅ Ввод даты вручную")
        date_prompt_msg = ctx.bot.send_message(
            chat_id,
            "Введи дату в формате YYYY-MM-DD, DD.MM.YYYY, 8/6/2025 или 5 июня 2026.\nНужна дата из прошлого.",
        )
        _date_prompt_id = getattr(date_prompt_msg, "message_id", None)
        if _date_prompt_id is not None:
            draft["date_prompt_message_id"] = _date_prompt_id
            session_store.history_drafts[user_id] = draft
        return

    if call.data == "history_climate_open":
        draft = session_store.history_drafts.get(user_id)
        if not isinstance(draft, dict):
            _notify_stale_history_flow(call, chat_id=chat_id, user_id=user_id, ctx=ctx, session_store=session_store)
            return
        draft["history_section"] = "climate"
        for key in ("monthly_mode", "monthly_month", "monthly_year", "pending_history_date_options"):
            draft.pop(key, None)
        session_store.history_drafts[user_id] = draft
        session_store.user_states[user_id] = WAITING_HISTORY_CLIMATE_MODE
        ctx.bot.answer_callback_query(call.id)
        clear_inline_choice_message(call, ctx)
        city_label = str(draft.get("city_label") or "выбранной локации")
        keyboard_builder = getattr(ctx, "build_history_climate_mode_keyboard", build_history_climate_mode_keyboard)
        ctx.bot.send_message(
            chat_id,
            f"Выбери режим климатической справки по {city_label}:",
            reply_markup=keyboard_builder(),
        )
        return

    if call.data == "history_climate_back_to_actions":
        draft = session_store.history_drafts.get(user_id)
        if not isinstance(draft, dict):
            _notify_stale_history_flow(call, chat_id=chat_id, user_id=user_id, ctx=ctx, session_store=session_store)
            return
        for key in ("monthly_mode", "monthly_month", "monthly_year", "pending_history_date_options"):
            draft.pop(key, None)
        session_store.history_drafts[user_id] = draft
        session_store.user_states[user_id] = WAITING_HISTORY_SECTION
        ctx.bot.answer_callback_query(call.id)
        clear_inline_choice_message(call, ctx)
        city_label = str(draft.get("city_label") or "выбранной локации")
        keyboard_builder = getattr(ctx, "build_history_section_keyboard", build_history_section_keyboard)
        ctx.bot.send_message(
            chat_id,
            f"Что посмотрим для {city_label}?",
            reply_markup=keyboard_builder(),
        )
        return

    if call.data.startswith("history_climate_mode:"):
        mode = call.data.split(":", 1)[1] if ":" in call.data else ""
        draft = session_store.history_drafts.get(user_id)
        if not isinstance(draft, dict):
            _notify_stale_history_flow(call, chat_id=chat_id, user_id=user_id, ctx=ctx, session_store=session_store)
            return
        if mode not in {"monthly_year", "monthly_normals"}:
            ctx.bot.answer_callback_query(call.id, "Не удалось определить режим.")
            return
        draft["monthly_mode"] = mode
        draft.pop("monthly_month", None)
        draft.pop("monthly_year", None)
        session_store.history_drafts[user_id] = draft
        session_store.user_states[user_id] = WAITING_HISTORY_CLIMATE_MONTH
        ctx.bot.answer_callback_query(call.id)
        clear_inline_choice_message(call, ctx)
        mode_label = "месяц конкретного года" if mode == "monthly_year" else "среднемесячные показатели"
        keyboard_builder = getattr(ctx, "build_history_month_keyboard", build_history_month_keyboard)
        ctx.bot.send_message(chat_id, f"✅ Режим выбран: {mode_label}")
        ctx.bot.send_message(
            chat_id,
            "Выбери месяц:",
            reply_markup=keyboard_builder(),
        )
        return

    if call.data == "history_climate_back_to_modes":
        draft = session_store.history_drafts.get(user_id)
        if not isinstance(draft, dict):
            _notify_stale_history_flow(call, chat_id=chat_id, user_id=user_id, ctx=ctx, session_store=session_store)
            return
        prompt_msg_id = draft.pop("prompt_message_id", None)
        draft.pop("monthly_month", None)
        draft.pop("monthly_year", None)
        session_store.history_drafts[user_id] = draft
        session_store.user_states[user_id] = WAITING_HISTORY_CLIMATE_MODE
        ctx.bot.answer_callback_query(call.id)
        clear_inline_choice_message(call, ctx)
        if prompt_msg_id:
            try_delete_message(ctx, chat_id, prompt_msg_id)
        keyboard_builder = getattr(ctx, "build_history_climate_mode_keyboard", build_history_climate_mode_keyboard)
        ctx.bot.send_message(
            chat_id,
            "Выбери режим климатической справки:",
            reply_markup=keyboard_builder(),
        )
        return

    if call.data.startswith("history_climate_month:"):
        month_raw = call.data.split(":", 1)[1] if ":" in call.data else ""
        draft = session_store.history_drafts.get(user_id)
        if not isinstance(draft, dict):
            _notify_stale_history_flow(call, chat_id=chat_id, user_id=user_id, ctx=ctx, session_store=session_store)
            return
        try:
            month_value = int(month_raw)
        except ValueError:
            ctx.bot.answer_callback_query(call.id, "Не удалось определить месяц.")
            return
        if not 1 <= month_value <= 12:
            ctx.bot.answer_callback_query(call.id, "Не удалось определить месяц.")
            return
        mode = str(draft.get("monthly_mode") or "")
        if mode not in {"monthly_year", "monthly_normals"}:
            ctx.bot.answer_callback_query(call.id, "Сначала выбери режим.")
            return
        draft["monthly_month"] = month_value
        session_store.history_drafts[user_id] = draft
        ctx.bot.answer_callback_query(call.id)
        clear_inline_choice_message(call, ctx)
        ctx.bot.send_message(chat_id, f"✅ Месяц выбран: {month_name(month_value)}")
        if mode == "monthly_year":
            session_store.user_states[user_id] = WAITING_HISTORY_CLIMATE_YEAR
            year_prompt_msg = ctx.bot.send_message(
                chat_id,
                "Введи год, например 2020.",
            )
            year_prompt_msg_id = getattr(year_prompt_msg, "message_id", None)
            if year_prompt_msg_id is not None:
                draft["prompt_message_id"] = year_prompt_msg_id
                session_store.history_drafts[user_id] = draft
            return
        stub = _message_stub_for_chat(chat_id)
        if send_history_monthly_report is None:
            from flows import send_history_monthly_report as monthly_sender

            monthly_sender(
                stub,
                user_id,
                send_year_confirmation=False,
                ctx=ctx,
                session_store=session_store,
            )
        else:
            send_history_monthly_report(stub, user_id, send_year_confirmation=False)
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

    if call.data.startswith("history_date_year:"):
        draft = session_store.history_drafts.get(user_id)
        if not isinstance(draft, dict):
            _notify_stale_history_flow(call, chat_id=chat_id, user_id=user_id, ctx=ctx, session_store=session_store)
            return
        raw_date = call.data.split(":", 1)[1] if ":" in call.data else ""
        options = draft.get("pending_history_date_options")
        if not isinstance(options, list) or raw_date not in options:
            _notify_stale_history_flow(call, chat_id=chat_id, user_id=user_id, ctx=ctx, session_store=session_store)
            return
        try:
            target_date = date.fromisoformat(raw_date)
        except ValueError:
            ctx.bot.answer_callback_query(call.id, "Не удалось определить дату.")
            return
        draft.pop("pending_history_date_options", None)
        session_store.history_drafts[user_id] = draft
        ctx.bot.answer_callback_query(call.id)
        clear_inline_choice_message(call, ctx)
        ctx.bot.send_message(chat_id, f"✅ Выбрано: {format_history_date_label(target_date)}")
        stub = _message_stub_for_chat(chat_id)
        send_weather_history_by_date(stub, user_id, target_date, send_confirmation=False)
        return

    ctx.bot.answer_callback_query(call.id)
