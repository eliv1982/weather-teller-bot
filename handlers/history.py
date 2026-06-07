from telebot import types

from coordinates_parser import parse_coordinates
from keyboards import build_history_section_keyboard, build_history_year_clarification_keyboard
from location_query_assist import find_locations_with_assist
from utils.date_parsing import month_name
from weather_history_service import resolve_history_date_input, build_two_digit_year_future_warning
from weather_monthly_service import parse_monthly_history_year_input
from .callbacks_common import try_delete_message
from .states import (
    WAITING_HISTORY_CITY,
    WAITING_HISTORY_CLIMATE_MODE,
    WAITING_HISTORY_CLIMATE_MONTH,
    WAITING_HISTORY_CLIMATE_YEAR,
    WAITING_HISTORY_COORDS,
    WAITING_HISTORY_CUSTOM_DATE,
    WAITING_HISTORY_DATE_PICK,
    WAITING_HISTORY_GEO,
    WAITING_HISTORY_PICK,
    WAITING_HISTORY_SAVED_PICK,
    WAITING_HISTORY_SECTION,
)


def _clear_history_runtime(session_store, user_id: int) -> None:
    session_store.history_drafts.pop(user_id, None)
    session_store.clear_state(user_id)


def _history_restart_markup(ctx):
    main_menu = getattr(ctx, "main_menu", None)
    return main_menu() if callable(main_menu) else None


def handle_history_text(
    message: types.Message,
    user_id: int,
    state: str | None,
    *,
    ctx,
    session_store,
    prepare_weather_history_by_coordinates,
    send_weather_history_by_date,
    send_history_monthly_report=None,
) -> bool:
    """Handles location and date input for the archive weather flow."""
    if state == WAITING_HISTORY_CITY:
        query = (message.text or "").strip()
        normalized_query = query.translate({1105: 1077, 1025: 1045})
        if normalized_query == "⭐ Из сохраненных":
            user_data = ctx.load_user(user_id)
            saved_locations = user_data.get("saved_locations", [])
            if not isinstance(saved_locations, list) or not saved_locations:
                ctx.bot.send_message(
                    message.chat.id,
                    "Сохраненных локаций пока нет.",
                    reply_markup=ctx.location_input_menu(has_saved_locations=False),
                )
                return True
            session_store.user_states[user_id] = WAITING_HISTORY_SAVED_PICK
            ctx.bot.send_message(
                message.chat.id,
                "Выбери сохраненную локацию:",
                reply_markup=ctx.build_saved_locations_keyboard(saved_locations, "history_saved_pick"),
            )
            return True
        if query in {"🧭 Координаты", "Ввести координаты"}:
            session_store.user_states[user_id] = WAITING_HISTORY_COORDS
            ctx.bot.send_message(
                message.chat.id,
                "Введи координаты в формате: 55.5789, 37.9051",
                reply_markup=types.ReplyKeyboardRemove(),
            )
            return True
        if query in {"📍 Отправить геолокацию", "📍 Геолокация", "Отправить геолокацию"}:
            session_store.user_states[user_id] = WAITING_HISTORY_GEO
            ctx.bot.send_message(
                message.chat.id,
                "Отправь геолокацию через кнопку ниже.",
                reply_markup=ctx.geo_request_menu(),
            )
            return True

        parsed = parse_coordinates(query)
        if parsed is not None:
            lat, lon = parsed
            location = ctx.get_location_by_coordinates(lat, lon)
            city = ctx.build_location_label(location, show_coords=False) if location else f"Координаты: {lat:.4f}, {lon:.4f}"
            _draft = session_store.history_drafts.get(user_id)
            _loc_prompt_id = _draft.get("location_prompt_message_id") if isinstance(_draft, dict) else None
            prepare_weather_history_by_coordinates(
                message,
                user_id,
                float(lat),
                float(lon),
                city,
                preferred_city_label=city,
            )
            try_delete_message(ctx, message.chat.id, _loc_prompt_id)
            try_delete_message(ctx, message.chat.id, getattr(message, "message_id", None))
            return True

        if not query:
            ctx.bot.send_message(message.chat.id, "⚠️ Введи название населенного пункта.")
            return True

        search_result = find_locations_with_assist(
            query,
            scenario="history",
            ctx=ctx,
        )
        clarification_text = search_result.get("clarification_text")
        if clarification_text:
            ctx.bot.send_message(message.chat.id, str(clarification_text))
            return True
        locations = search_result.get("locations") if isinstance(search_result, dict) else []
        if not locations:
            ctx.bot.send_message(
                message.chat.id,
                "Не нашла такую локацию. Уточни город, страну или отправь геолокацию.",
            )
            return True

        if len(locations) == 1:
            loc = ctx.build_geocode_item_with_disambiguated_label(locations, 0)
            lat = loc.get("lat")
            lon = loc.get("lon")
            city = loc.get("label") or ctx.build_location_label(loc, show_coords=False)
            if lat is None or lon is None:
                ctx.bot.send_message(
                    message.chat.id,
                    "Не удалось подготовить архивную справку по этой локации. Попробуй позже.",
                    reply_markup=ctx.main_menu(),
                )
                return True
            _draft = session_store.history_drafts.get(user_id)
            _loc_prompt_id = _draft.get("location_prompt_message_id") if isinstance(_draft, dict) else None
            prepare_weather_history_by_coordinates(
                message,
                user_id,
                float(lat),
                float(lon),
                city,
                preferred_city_label=city,
            )
            try_delete_message(ctx, message.chat.id, _loc_prompt_id)
            try_delete_message(ctx, message.chat.id, getattr(message, "message_id", None))
            return True

        session_store.history_location_choices[user_id] = locations
        session_store.user_states[user_id] = WAITING_HISTORY_PICK
        ctx.bot.send_message(
            message.chat.id,
            "Найдено несколько вариантов. Выбери нужный населенный пункт:",
            reply_markup=ctx.build_scenario_location_choice_keyboard(locations, "history"),
        )
        return True

    if state == WAITING_HISTORY_COORDS:
        parsed = parse_coordinates(message.text or "")
        if parsed is None:
            ctx.bot.send_message(message.chat.id, "⚠️ Некорректный формат. Введи координаты в формате: 55.5789, 37.9051")
            return True
        lat, lon = parsed
        location = ctx.get_location_by_coordinates(lat, lon)
        city = ctx.build_location_label(location, show_coords=False) if location else f"Координаты: {lat:.4f}, {lon:.4f}"
        _draft = session_store.history_drafts.get(user_id)
        _loc_prompt_id = _draft.get("location_prompt_message_id") if isinstance(_draft, dict) else None
        prepare_weather_history_by_coordinates(
            message,
            user_id,
            float(lat),
            float(lon),
            city,
            preferred_city_label=city,
        )
        try_delete_message(ctx, message.chat.id, _loc_prompt_id)
        try_delete_message(ctx, message.chat.id, getattr(message, "message_id", None))
        return True

    if state == WAITING_HISTORY_PICK:
        if not session_store.history_location_choices.get(user_id):
            session_store.user_states.pop(user_id, None)
            ctx.bot.send_message(
                message.chat.id,
                "⚠️ Список вариантов устарел. Введи населенный пункт заново.",
                reply_markup=ctx.main_menu(),
            )
            return True
        ctx.bot.send_message(
            message.chat.id,
            "Выбери населенный пункт кнопкой ниже или нажми «⬅️ Отмена».",
        )
        return True

    if state == WAITING_HISTORY_SAVED_PICK:
        ctx.bot.send_message(
            message.chat.id,
            "Выбери сохраненную локацию кнопкой ниже или нажми «⬅️ В меню».",
        )
        return True

    if state == WAITING_HISTORY_GEO:
        ctx.bot.send_message(
            message.chat.id,
            "Отправь геолокацию через кнопку ниже.",
            reply_markup=ctx.geo_request_menu(),
        )
        return True

    if state == WAITING_HISTORY_SECTION:
        keyboard_builder = getattr(ctx, "build_history_section_keyboard", build_history_section_keyboard)
        ctx.bot.send_message(
            message.chat.id,
            "Выбери раздел кнопкой ниже или нажми «⬅️ В меню».",
            reply_markup=keyboard_builder(),
        )
        return True

    if state == WAITING_HISTORY_DATE_PICK:
        ctx.bot.send_message(
            message.chat.id,
            "Выбери дату кнопкой ниже или нажми «⬅️ В меню».",
        )
        return True

    if state == WAITING_HISTORY_CUSTOM_DATE:
        draft = session_store.history_drafts.get(user_id)
        if not isinstance(draft, dict):
            _clear_history_runtime(session_store, user_id)
            ctx.bot.send_message(
                message.chat.id,
                "Начни историю погоды заново.",
                reply_markup=_history_restart_markup(ctx),
            )
            return True
        draft.pop("pending_history_date_options", None)
        resolution = resolve_history_date_input(message.text or "")
        if resolution.clarification_dates:
            draft["pending_history_date_options"] = [
                option.isoformat() for option in resolution.clarification_dates
            ]
            session_store.history_drafts[user_id] = draft
            keyboard_builder = getattr(
                ctx,
                "build_history_year_clarification_keyboard",
                build_history_year_clarification_keyboard,
            )
            future_warning = build_two_digit_year_future_warning(message.text or "")
            clarification_prompt = "Уточни год:"
            if future_warning:
                clarification_prompt = f"{future_warning}\nУточни год:"
            ctx.bot.send_message(
                message.chat.id,
                clarification_prompt,
                reply_markup=keyboard_builder(resolution.clarification_dates),
            )
            return True
        if resolution.error_message:
            ctx.bot.send_message(
                message.chat.id,
                f"{resolution.error_message}\nНапример: 2026-06-05, 05.06.2026, 8/6/2025 или 5 июня 2026.",
            )
            return True
        session_store.history_drafts[user_id] = draft
        try_delete_message(ctx, message.chat.id, getattr(message, "message_id", None))
        return send_weather_history_by_date(message, user_id, resolution.parsed_date)

    if state == WAITING_HISTORY_CLIMATE_MODE:
        ctx.bot.send_message(
            message.chat.id,
            "Выбери режим климатической справки кнопкой ниже или нажми «⬅️ В меню».",
        )
        return True

    if state == WAITING_HISTORY_CLIMATE_MONTH:
        ctx.bot.send_message(
            message.chat.id,
            "Выбери месяц кнопкой ниже или нажми «⬅️ В меню».",
        )
        return True

    if state == WAITING_HISTORY_CLIMATE_YEAR:
        draft = session_store.history_drafts.get(user_id)
        if not isinstance(draft, dict):
            _clear_history_runtime(session_store, user_id)
            ctx.bot.send_message(
                message.chat.id,
                "Начни историю погоды заново.",
                reply_markup=_history_restart_markup(ctx),
            )
            return True
        selected_month = draft.get("monthly_month") if isinstance(draft, dict) else None
        parsed, error_message = parse_monthly_history_year_input(
            message.text or "",
            selected_month=selected_month if isinstance(selected_month, int) else None,
        )
        if error_message:
            ctx.bot.send_message(
                message.chat.id,
                f"{error_message}\nПоддерживаются варианты: 2020, январь 2020, янв 2020, 01.2020, 2020-01.",
            )
            return True
        parsed_month = int(parsed["month"])
        month_changed = draft.get("monthly_month") != parsed_month
        draft["monthly_month"] = parsed_month
        draft["monthly_year"] = int(parsed["year"])
        session_store.history_drafts[user_id] = draft
        try_delete_message(ctx, message.chat.id, getattr(message, "message_id", None))
        if month_changed:
            ctx.bot.send_message(
                message.chat.id,
                f"✅ Месяц выбран: {month_name(parsed_month)}",
            )
        if send_history_monthly_report is None:
            from flows import send_history_monthly_report as monthly_sender

            return monthly_sender(message, user_id, ctx=ctx, session_store=session_store)
        return send_history_monthly_report(message, user_id)

    return False
