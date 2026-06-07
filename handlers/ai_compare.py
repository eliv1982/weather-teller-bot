from telebot import types

from coordinates_parser import parse_coordinates
from location_query_assist import find_locations_with_assist

from . import location_compare_helpers
from .states import (
    LOCATIONS_MENU,
    WAITING_AI_COMPARE_DATE_PICK,
    WAITING_AI_COMPARE_LOC1_COORDS,
    WAITING_AI_COMPARE_LOC1_GEO,
    WAITING_AI_COMPARE_LOC1_METHOD,
    WAITING_AI_COMPARE_LOC1_PICK,
    WAITING_AI_COMPARE_LOC1_SAVED_PICK,
    WAITING_AI_COMPARE_LOC1_TEXT,
    WAITING_AI_COMPARE_LOC2_COORDS,
    WAITING_AI_COMPARE_LOC2_GEO,
    WAITING_AI_COMPARE_LOC2_METHOD,
    WAITING_AI_COMPARE_LOC2_PICK,
    WAITING_AI_COMPARE_LOC2_SAVED_PICK,
    WAITING_AI_COMPARE_LOC2_TEXT,
    WAITING_AI_COMPARE_MODE,
)


def start_ai_compare_flow(message: types.Message, user_id: int, *, ctx, session_store) -> None:
    """Запускает сценарий «Умное сравнение локаций»."""
    _ai_compare_reset(user_id, session_store=session_store)
    session_store.ai_compare_drafts[user_id] = {}
    session_store.user_states[user_id] = WAITING_AI_COMPARE_MODE
    ctx.bot.send_message(
        message.chat.id,
        "✨ Умное сравнение локаций\n\nВыбери режим:",
        reply_markup=ctx.ai_compare_mode_menu(),
    )


def _ai_compare_reset(user_id: int, *, session_store) -> None:
    """Очищает runtime-данные сценария AI-сравнения для пользователя."""
    session_store.ai_compare_drafts.pop(user_id, None)
    session_store.ai_compare_location_choices.pop(user_id, None)


def _ai_compare_current_payload(city_label: str, weather: dict, *, location_meta: dict | None = None) -> dict:
    return location_compare_helpers._ai_compare_current_payload(city_label, weather, location_meta=location_meta)


def _format_number(value: object, suffix: str = "") -> str:
    return location_compare_helpers._format_number(value, suffix)


def _format_ai_compare_current_snapshot(payload: dict) -> str:
    """Краткая сводка текущей погоды по одной локации."""
    city = str(payload.get("city_label") or "Локация")
    temperature = _format_number(payload.get("temperature"), "°C")
    feels_like = _format_number(payload.get("feels_like"), "°C")
    description = location_compare_helpers.normalize_weather_description(payload.get("description") or "без описания")
    return f"• {city}: {temperature}, ощущается как {feels_like}, {description}"


def _ai_compare_day_payload(
    city_label: str,
    selected_day: str,
    day_items: list[dict],
    *,
    location_meta: dict | None = None,
) -> dict:
    return location_compare_helpers._ai_compare_day_payload(
        city_label,
        selected_day,
        day_items,
        location_meta=location_meta,
    )


def _format_precipitation_summary(payload: dict) -> str:
    return location_compare_helpers._format_precipitation_summary(payload)


def format_ai_compare_day_summary(payload: dict) -> str:
    return location_compare_helpers.format_ai_compare_day_summary(payload)


def format_ai_compare_day_summary_message(payload: dict, selected_day: str, location_index: int) -> str:
    return location_compare_helpers.format_ai_compare_day_summary_message(payload, selected_day, location_index)


def normalize_location_name(value: object) -> str:
    return location_compare_helpers.normalize_location_name(value)


def calculate_distance_km(lat_1: float, lon_1: float, lat_2: float, lon_2: float) -> float:
    return location_compare_helpers.calculate_distance_km(lat_1, lon_1, lat_2, lon_2)


def is_same_location(loc_1: dict, loc_2: dict, *, distance_threshold_km: float = 2.5) -> bool:
    return location_compare_helpers.is_same_location(
        loc_1,
        loc_2,
        distance_threshold_km=distance_threshold_km,
    )


def validate_second_compare_location(loc_1: dict, loc_2: dict) -> str | None:
    return location_compare_helpers.validate_second_compare_location(loc_1, loc_2)


def _sorted_day_keys(day_keys: set[str]) -> list[str]:
    return location_compare_helpers._sorted_day_keys(day_keys)


def _ai_compare_set_location(
    message: types.Message,
    user_id: int,
    *,
    step: int,
    city_label: str,
    lat: float,
    lon: float,
    announce_selection: bool = True,
    ctx,
    session_store,
    validate_second_compare_location_fn=None,
    _ai_compare_after_two_locations_fn=None,
) -> bool:
    """Сохраняет выбранную локацию шага и переводит к следующему шагу/финализации."""
    validate_second_compare_location_fn = validate_second_compare_location_fn or validate_second_compare_location
    _ai_compare_after_two_locations_fn = _ai_compare_after_two_locations_fn or _ai_compare_after_two_locations

    # Сразу выходим из geo/text/pick-состояния шага, чтобы исключить повторный запрос
    # при повторной доставке одного и того же update.
    session_store.user_states.pop(user_id, None)
    draft = session_store.ai_compare_drafts.get(user_id)
    if not isinstance(draft, dict):
        draft = {}
        session_store.ai_compare_drafts[user_id] = draft

    draft[f"loc_{step}"] = {
        "city_label": city_label,
        "lat": float(lat),
        "lon": float(lon),
    }

    session_store.ai_compare_location_choices.pop(user_id, None)
    if announce_selection:
        ctx.bot.send_message(message.chat.id, f"✅ Выбрано: {city_label}")
    if step == 1:
        session_store.user_states[user_id] = WAITING_AI_COMPARE_LOC2_METHOD
        ctx.bot.send_message(
            message.chat.id,
            "Теперь выбери вторую локацию.",
            reply_markup=ctx.ai_compare_location_method_menu(),
        )
        return True

    loc_1 = draft.get("loc_1")
    loc_2 = draft.get("loc_2")
    if isinstance(loc_1, dict) and isinstance(loc_2, dict):
        duplicate_error = validate_second_compare_location_fn(loc_1, loc_2)
        if duplicate_error:
            draft.pop("loc_2", None)
            session_store.user_states[user_id] = WAITING_AI_COMPARE_LOC2_METHOD
            city_label = str(loc_2.get("city_label") or "выбранная точка")
            ctx.bot.send_message(
                message.chat.id,
                f"Похоже, это та же самая локация: {city_label}.\n"
                "Для сравнения нужна другая точка — выбери вторую локацию ещё раз.",
                reply_markup=ctx.ai_compare_location_method_menu(),
            )
            return True

    ctx.bot.send_message(message.chat.id, "Сравниваю погоду.")
    return _ai_compare_after_two_locations_fn(message, user_id, ctx=ctx, session_store=session_store)


def _ai_compare_process_text_query(
    message: types.Message,
    user_id: int,
    *,
    step: int,
    query: str,
    ctx,
    session_store,
    find_locations_with_assist_fn=None,
    _ai_compare_set_location_fn=None,
) -> bool:
    """Обрабатывает прямой текстовый ввод локации для шага AI-сравнения."""
    find_locations_with_assist_fn = find_locations_with_assist_fn or find_locations_with_assist
    _ai_compare_set_location_fn = _ai_compare_set_location_fn or _ai_compare_set_location

    if not query:
        ctx.bot.send_message(message.chat.id, "⚠️ Введи населённый пункт.")
        return True
    search_result = find_locations_with_assist_fn(
        query,
        scenario=f"ai_compare_loc_{step}",
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
        location_item = ctx.build_geocode_item_with_disambiguated_label(locations, 0)
        lat = location_item.get("lat")
        lon = location_item.get("lon")
        if lat is None or lon is None:
            ctx.bot.send_message(message.chat.id, "Не удалось определить локацию. Попробуй снова.")
            return True
        city_label = location_item.get("label") or ctx.build_location_label(location_item, show_coords=False)
        return _ai_compare_set_location_fn(
            message,
            user_id,
            step=step,
            city_label=city_label,
            lat=float(lat),
            lon=float(lon),
            ctx=ctx,
            session_store=session_store,
        )

    session_store.ai_compare_location_choices[user_id] = locations
    session_store.user_states[user_id] = WAITING_AI_COMPARE_LOC1_PICK if step == 1 else WAITING_AI_COMPARE_LOC2_PICK
    ctx.bot.send_message(
        message.chat.id,
        "Найдено несколько вариантов. Выбери нужный населённый пункт:",
        reply_markup=ctx.build_location_pick_keyboard(
            locations,
            f"aicmp_geo_pick:{step}",
            "aicmp_geo_cancel",
        ),
    )
    return True


def _ai_compare_after_two_locations(
    message: types.Message,
    user_id: int,
    *,
    ctx,
    session_store,
    _ai_compare_reset_fn=None,
    _ai_compare_current_payload_fn=None,
    _sorted_day_keys_fn=None,
) -> bool:
    """Финализирует сравнение после выбора обеих локаций (сразу или через выбор даты)."""
    _ai_compare_reset_fn = _ai_compare_reset_fn or _ai_compare_reset
    _ai_compare_current_payload_fn = _ai_compare_current_payload_fn or _ai_compare_current_payload
    _sorted_day_keys_fn = _sorted_day_keys_fn or _sorted_day_keys

    draft = session_store.ai_compare_drafts.get(user_id)
    if not isinstance(draft, dict):
        session_store.user_states.pop(user_id, None)
        ctx.bot.send_message(
            message.chat.id,
            "Данные сравнения устарели. Начни заново.",
            reply_markup=ctx.main_menu(),
        )
        return True

    loc_1 = draft.get("loc_1")
    loc_2 = draft.get("loc_2")
    mode = draft.get("mode")
    if not isinstance(loc_1, dict) or not isinstance(loc_2, dict) or mode not in {"current", "date"}:
        _ai_compare_reset_fn(user_id, session_store=session_store)
        session_store.user_states.pop(user_id, None)
        ctx.bot.send_message(
            message.chat.id,
            "Данные сравнения устарели. Начни заново.",
            reply_markup=ctx.main_menu(),
        )
        return True

    if mode == "current":
        weather_1 = ctx.get_current_weather(loc_1["lat"], loc_1["lon"])
        weather_2 = ctx.get_current_weather(loc_2["lat"], loc_2["lon"])
        if not weather_1 or not weather_2:
            _ai_compare_reset_fn(user_id, session_store=session_store)
            session_store.user_states.pop(user_id, None)
            ctx.bot.send_message(
                message.chat.id,
                "Не удалось получить данные для умного сравнения. Попробуй позже.",
                reply_markup=ctx.main_menu(),
            )
            return True

        payload_1 = _ai_compare_current_payload_fn(loc_1["city_label"], weather_1, location_meta=loc_1)
        payload_2 = _ai_compare_current_payload_fn(loc_2["city_label"], weather_2, location_meta=loc_2)
        text = ctx.ai_weather_service.compare_two_locations_current_with_ai(payload_1, payload_2)

        _ai_compare_reset_fn(user_id, session_store=session_store)
        session_store.user_states.pop(user_id, None)
        ctx.bot.send_message(
            message.chat.id,
            f"✨ Сравнение локаций (сейчас)\n\n{text}",
            reply_markup=ctx.main_menu(),
        )
        return True

    forecast_1 = ctx.get_forecast_5d3h(loc_1["lat"], loc_1["lon"])
    forecast_2 = ctx.get_forecast_5d3h(loc_2["lat"], loc_2["lon"])
    grouped_1 = ctx.group_forecast_by_day(forecast_1 or [])
    grouped_2 = ctx.group_forecast_by_day(forecast_2 or [])
    if not grouped_1 or not grouped_2:
        _ai_compare_reset_fn(user_id, session_store=session_store)
        session_store.user_states.pop(user_id, None)
        ctx.bot.send_message(
            message.chat.id,
            "Не удалось подготовить сравнение на дату. Попробуй позже.",
            reply_markup=ctx.main_menu(),
        )
        return True

    common_days = set(grouped_1.keys()) & set(grouped_2.keys())
    if not common_days:
        _ai_compare_reset_fn(user_id, session_store=session_store)
        session_store.user_states.pop(user_id, None)
        ctx.bot.send_message(
            message.chat.id,
            "Для выбранных локаций нет общих доступных дат в ближайшие 5 дней.",
            reply_markup=ctx.main_menu(),
        )
        return True

    draft["grouped_1"] = grouped_1
    draft["grouped_2"] = grouped_2
    draft["available_days"] = _sorted_day_keys_fn(common_days)
    session_store.user_states[user_id] = WAITING_AI_COMPARE_DATE_PICK
    ctx.bot.send_message(
        message.chat.id,
        "Выбери дату для умного сравнения:",
        reply_markup=ctx.build_ai_compare_days_keyboard(draft["available_days"]),
    )
    return True


def handle_ai_compare_text(
    message: types.Message,
    user_id: int,
    state: str | None,
    *,
    ctx,
    session_store,
    types_module=None,
    parse_coordinates_fn=None,
    _ai_compare_reset_fn=None,
    _ai_compare_process_text_query_fn=None,
    _ai_compare_set_location_fn=None,
) -> bool:
    """Обрабатывает AI compare ветки внутри большого text-dispatcher."""
    types_module = types_module or types
    parse_coordinates_fn = parse_coordinates_fn or parse_coordinates
    _ai_compare_reset_fn = _ai_compare_reset_fn or _ai_compare_reset
    _ai_compare_process_text_query_fn = _ai_compare_process_text_query_fn or _ai_compare_process_text_query
    _ai_compare_set_location_fn = _ai_compare_set_location_fn or _ai_compare_set_location

    if state == WAITING_AI_COMPARE_MODE:
        choice = (message.text or "").strip()
        if choice == "⬅️ Назад":
            _ai_compare_reset_fn(user_id, session_store=session_store)
            session_store.user_states[user_id] = LOCATIONS_MENU
            ctx.bot.send_message(message.chat.id, "Раздел локаций.", reply_markup=ctx.locations_menu())
            return True
        if choice in {"⚖️ Сравнить сейчас", "Сравнить сейчас", "🌤 Сейчас", "Сейчас"}:
            draft = session_store.ai_compare_drafts.get(user_id)
            if not isinstance(draft, dict):
                draft = {}
            draft["mode"] = "current"
            session_store.ai_compare_drafts[user_id] = draft
            session_store.user_states[user_id] = WAITING_AI_COMPARE_LOC1_METHOD
            ctx.bot.send_message(
                message.chat.id,
                "Введи название первой локации или выбери другой способ ниже:",
                reply_markup=ctx.ai_compare_location_method_menu(),
            )
            return True
        if choice in {"📅 Сравнить на дату", "Сравнить на дату", "📅 На дату", "На дату"}:
            draft = session_store.ai_compare_drafts.get(user_id)
            if not isinstance(draft, dict):
                draft = {}
            draft["mode"] = "date"
            session_store.ai_compare_drafts[user_id] = draft
            session_store.user_states[user_id] = WAITING_AI_COMPARE_LOC1_METHOD
            ctx.bot.send_message(
                message.chat.id,
                "Введи название первой локации или выбери другой способ ниже:",
                reply_markup=ctx.ai_compare_location_method_menu(),
            )
            return True

        ctx.bot.send_message(
            message.chat.id,
            "Выбери режим кнопкой ниже или вернись в меню.",
            reply_markup=ctx.ai_compare_mode_menu(),
        )
        return True

    if state in {WAITING_AI_COMPARE_LOC1_METHOD, WAITING_AI_COMPARE_LOC2_METHOD}:
        step = 1 if state == WAITING_AI_COMPARE_LOC1_METHOD else 2
        choice = (message.text or "").strip()
        if choice == "⬅️ Отмена":
            _ai_compare_reset_fn(user_id, session_store=session_store)
            session_store.user_states.pop(user_id, None)
            ctx.bot.send_message(message.chat.id, "Сравнение отменено.", reply_markup=ctx.main_menu())
            return True
        if choice in {"⭐ Из сохранённых", "Из сохранённых"}:
            user_data = ctx.load_user(user_id)
            saved_locations = user_data.get("saved_locations", [])
            if not isinstance(saved_locations, list) or not saved_locations:
                ctx.bot.send_message(message.chat.id, "Сохранённых локаций пока нет.")
                return True
            session_store.user_states[user_id] = (
                WAITING_AI_COMPARE_LOC1_SAVED_PICK if step == 1 else WAITING_AI_COMPARE_LOC2_SAVED_PICK
            )
            ctx.bot.send_message(
                message.chat.id,
                f"Выбери {'первую' if step == 1 else 'вторую'} локацию из сохранённых:",
                reply_markup=ctx.build_ai_compare_saved_locations_keyboard(saved_locations, step),
            )
            return True
        if choice in {"🧭 Координаты", "Ввести координаты"}:
            session_store.user_states[user_id] = (
                WAITING_AI_COMPARE_LOC1_COORDS if step == 1 else WAITING_AI_COMPARE_LOC2_COORDS
            )
            ctx.bot.send_message(
                message.chat.id,
                "Введи координаты в формате: 55.5789, 37.9051",
                reply_markup=types_module.ReplyKeyboardRemove(),
            )
            return True
        if choice in {"📍 Геолокация", "Отправить геолокацию"}:
            session_store.user_states[user_id] = WAITING_AI_COMPARE_LOC1_GEO if step == 1 else WAITING_AI_COMPARE_LOC2_GEO
            ctx.bot.send_message(
                message.chat.id,
                f"Отправь {'первую' if step == 1 else 'вторую'} геолокацию.",
                reply_markup=ctx.geo_request_menu(),
            )
            return True

        return _ai_compare_process_text_query_fn(
            message,
            user_id,
            step=step,
            query=choice,
            ctx=ctx,
            session_store=session_store,
        )

    if state in {WAITING_AI_COMPARE_LOC1_TEXT, WAITING_AI_COMPARE_LOC2_TEXT}:
        step = 1 if state == WAITING_AI_COMPARE_LOC1_TEXT else 2
        query = (message.text or "").strip()
        return _ai_compare_process_text_query_fn(
            message,
            user_id,
            step=step,
            query=query,
            ctx=ctx,
            session_store=session_store,
        )

    if state in {WAITING_AI_COMPARE_LOC1_COORDS, WAITING_AI_COMPARE_LOC2_COORDS}:
        step = 1 if state == WAITING_AI_COMPARE_LOC1_COORDS else 2
        parsed = parse_coordinates_fn(message.text or "")
        if parsed is None:
            ctx.bot.send_message(message.chat.id, "⚠️ Некорректный формат. Введи координаты в формате: 55.5789, 37.9051")
            return True
        lat, lon = parsed
        location = ctx.get_location_by_coordinates(lat, lon)
        city_label = (
            ctx.build_location_label(location, show_coords=False)
            if location
            else f"Координаты: {lat:.4f}, {lon:.4f}"
        )
        return _ai_compare_set_location_fn(
            message,
            user_id,
            step=step,
            city_label=city_label,
            lat=lat,
            lon=lon,
            ctx=ctx,
            session_store=session_store,
        )

    if state in {WAITING_AI_COMPARE_LOC1_PICK, WAITING_AI_COMPARE_LOC2_PICK}:
        ctx.bot.send_message(
            message.chat.id,
            "Выбери населённый пункт кнопкой ниже или нажми «⬅️ Отмена».",
        )
        return True

    if state in {WAITING_AI_COMPARE_LOC1_SAVED_PICK, WAITING_AI_COMPARE_LOC2_SAVED_PICK}:
        ctx.bot.send_message(
            message.chat.id,
            "Выбери сохранённую локацию кнопкой ниже или нажми «⬅️ Отмена».",
        )
        return True

    if state in {WAITING_AI_COMPARE_LOC1_GEO, WAITING_AI_COMPARE_LOC2_GEO}:
        step_label = "первую" if state == WAITING_AI_COMPARE_LOC1_GEO else "вторую"
        ctx.bot.send_message(
            message.chat.id,
            f"Нажми кнопку и отправь {step_label} геолокацию.",
            reply_markup=ctx.geo_request_menu(),
        )
        return True

    if state == WAITING_AI_COMPARE_DATE_PICK:
        ctx.bot.send_message(
            message.chat.id,
            "Выбери дату кнопкой ниже или нажми «⬅️ Отмена».",
        )
        return True

    return False
