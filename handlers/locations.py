from telebot import types

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
    WAITING_LOCATION_TITLE,
    WAITING_NEW_SAVED_LOCATION_GEO,
    WAITING_NEW_SAVED_LOCATION_COORDS,
    WAITING_NEW_SAVED_LOCATION_COORDS_UNRESOLVED,
    WAITING_NEW_SAVED_LOCATION_MENU,
    WAITING_NEW_SAVED_LOCATION_PICK,
    WAITING_NEW_SAVED_LOCATION_TEXT,
    WAITING_NEW_SAVED_LOCATION_TITLE,
    WAITING_RENAME_LOCATION_TITLE,
)
from coordinates_parser import parse_coordinates
from location_query_assist import find_locations_with_assist
from . import location_compare_helpers
from locations_service import (
    find_duplicate_saved_location_by_geo,
    format_saved_location_item,
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


def _set_new_saved_location_candidate(
    message: types.Message,
    user_id: int,
    *,
    lat: float,
    lon: float,
    label: str,
    ctx,
    session_store,
) -> bool:
    """Проверяет геодубль и либо просит title, либо сообщает о дубле сразу."""
    user_data = ctx.load_user(user_id)
    saved_locations = user_data.get("saved_locations", [])
    if not isinstance(saved_locations, list):
        saved_locations = []
    duplicate = find_duplicate_saved_location_by_geo(
        saved_locations,
        label=str(label),
        lat=float(lat),
        lon=float(lon),
        distance_threshold_km=2.0,
    )
    if duplicate is not None:
        session_store.saved_location_drafts.pop(user_id, None)
        session_store.user_states[user_id] = WAITING_NEW_SAVED_LOCATION_MENU
        ctx.bot.send_message(
            message.chat.id,
            "Эта локация уже есть в сохранённых:\n"
            f"{format_saved_location_item(duplicate)}",
            reply_markup=ctx.add_saved_location_menu(),
        )
        ctx.bot.send_message(
            message.chat.id,
            ctx.format_saved_locations(user_data),
            reply_markup=ctx.add_saved_location_menu(),
        )
        return True

    session_store.saved_location_drafts[user_id] = {
        "lat": float(lat),
        "lon": float(lon),
        "label": str(label),
    }
    session_store.user_states[user_id] = WAITING_NEW_SAVED_LOCATION_TITLE
    ctx.bot.send_message(
        message.chat.id,
        "Введи название для этой локации, например: Дом",
        reply_markup=types.ReplyKeyboardRemove(),
    )
    return True


def _unresolved_coords_menu(types_module) -> types.ReplyKeyboardMarkup:
    """Клавиатура действий, если по координатам не найден населённый пункт."""
    keyboard = types_module.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(types_module.KeyboardButton("💾 Сохранить как точку"))
    keyboard.row(
        types_module.KeyboardButton("🧭 Ввести координаты заново"),
        types_module.KeyboardButton("🏙 Ввести населённый пункт"),
    )
    keyboard.row(types_module.KeyboardButton("⬅️ В меню"))
    return keyboard


def _ai_compare_set_location(
    message: types.Message,
    user_id: int,
    *,
    step: int,
    city_label: str,
    lat: float,
    lon: float,
    ctx,
    session_store,
) -> bool:
    """Сохраняет выбранную локацию шага и переводит к следующему шагу/финализации."""
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
    if step == 1:
        session_store.user_states[user_id] = WAITING_AI_COMPARE_LOC2_METHOD
        ctx.bot.send_message(
            message.chat.id,
            "Локация 1 сохранена. Введи название второй локации или выбери другой способ ниже:",
            reply_markup=ctx.ai_compare_location_method_menu(),
        )
        return True

    loc_1 = draft.get("loc_1")
    loc_2 = draft.get("loc_2")
    if isinstance(loc_1, dict) and isinstance(loc_2, dict):
        duplicate_error = validate_second_compare_location(loc_1, loc_2)
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

    return _ai_compare_after_two_locations(message, user_id, ctx=ctx, session_store=session_store)


def _ai_compare_current_payload(city_label: str, weather: dict, *, location_meta: dict | None = None) -> dict:
    return location_compare_helpers._ai_compare_current_payload(city_label, weather, location_meta=location_meta)


def _format_number(value: object, suffix: str = "") -> str:
    return location_compare_helpers._format_number(value, suffix)


def _format_ai_compare_current_snapshot(payload: dict) -> str:
    """Краткая сводка текущей погоды по одной локации."""
    city = str(payload.get("city_label") or "Локация")
    temperature = _format_number(payload.get("temperature"), "°C")
    feels_like = _format_number(payload.get("feels_like"), "°C")
    description = str(payload.get("description") or "без описания")
    return (
        f"• {city}: {temperature}, ощущается как {feels_like}, {description}"
    )


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


def _ai_compare_process_text_query(
    message: types.Message,
    user_id: int,
    *,
    step: int,
    query: str,
    ctx,
    session_store,
) -> bool:
    """Обрабатывает прямой текстовый ввод локации для шага AI-сравнения."""
    if not query:
        ctx.bot.send_message(message.chat.id, "⚠️ Введи населённый пункт.")
        return True
    search_result = find_locations_with_assist(
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
        return _ai_compare_set_location(
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


def _sorted_day_keys(day_keys: set[str]) -> list[str]:
    return location_compare_helpers._sorted_day_keys(day_keys)


def _ai_compare_after_two_locations(message: types.Message, user_id: int, *, ctx, session_store) -> bool:
    """Финализирует сравнение после выбора обеих локаций (сразу или через выбор даты)."""
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
        _ai_compare_reset(user_id, session_store=session_store)
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
            _ai_compare_reset(user_id, session_store=session_store)
            session_store.user_states.pop(user_id, None)
            ctx.bot.send_message(
                message.chat.id,
                "Не удалось получить данные для умного сравнения. Попробуй позже.",
                reply_markup=ctx.main_menu(),
            )
            return True

        payload_1 = _ai_compare_current_payload(loc_1["city_label"], weather_1, location_meta=loc_1)
        payload_2 = _ai_compare_current_payload(loc_2["city_label"], weather_2, location_meta=loc_2)
        text = ctx.ai_weather_service.compare_two_locations_current_with_ai(payload_1, payload_2)
        card_1 = ctx.format_weather_response(loc_1["city_label"], weather_1)
        card_2 = ctx.format_weather_response(loc_2["city_label"], weather_2)

        _ai_compare_reset(user_id, session_store=session_store)
        session_store.user_states.pop(user_id, None)
        ctx.bot.send_message(
            message.chat.id,
            card_1,
            reply_markup=ctx.main_menu(),
        )
        ctx.bot.send_message(
            message.chat.id,
            card_2,
            reply_markup=ctx.main_menu(),
        )
        ctx.bot.send_message(
            message.chat.id,
            f"✨ Сравнить локации (сейчас)\n\n🪄 Вывод:\n{text}",
            reply_markup=ctx.main_menu(),
        )
        return True

    forecast_1 = ctx.get_forecast_5d3h(loc_1["lat"], loc_1["lon"])
    forecast_2 = ctx.get_forecast_5d3h(loc_2["lat"], loc_2["lon"])
    grouped_1 = ctx.group_forecast_by_day(forecast_1 or [])
    grouped_2 = ctx.group_forecast_by_day(forecast_2 or [])
    if not grouped_1 or not grouped_2:
        _ai_compare_reset(user_id, session_store=session_store)
        session_store.user_states.pop(user_id, None)
        ctx.bot.send_message(
            message.chat.id,
            "Не удалось подготовить сравнение на дату. Попробуй позже.",
            reply_markup=ctx.main_menu(),
        )
        return True

    common_days = set(grouped_1.keys()) & set(grouped_2.keys())
    if not common_days:
        _ai_compare_reset(user_id, session_store=session_store)
        session_store.user_states.pop(user_id, None)
        ctx.bot.send_message(
            message.chat.id,
            "Для выбранных локаций нет общих доступных дат в ближайшие 5 дней.",
            reply_markup=ctx.main_menu(),
        )
        return True

    draft["grouped_1"] = grouped_1
    draft["grouped_2"] = grouped_2
    draft["available_days"] = _sorted_day_keys(common_days)
    session_store.user_states[user_id] = WAITING_AI_COMPARE_DATE_PICK
    ctx.bot.send_message(
        message.chat.id,
        "Выбери дату для умного сравнения:",
        reply_markup=ctx.build_ai_compare_days_keyboard(draft["available_days"]),
    )
    return True


def handle_locations_text(
    message: types.Message,
    user_id: int,
    state: str | None,
    *,
    ctx,
    session_store,
) -> bool:
    """Обрабатывает текстовые состояния сценария «Мои локации»."""
    if state == WAITING_LOCATION_TITLE:
        title = (message.text or "").strip()
        if not title:
            ctx.bot.send_message(message.chat.id, "⚠️ Введи название локации, например: Дом")
            return True

        user_data = ctx.load_user(user_id)
        current_city = user_data.get("city")
        current_lat = user_data.get("lat")
        current_lon = user_data.get("lon")

        if current_lat is None or current_lon is None or not current_city:
            session_store.user_states[user_id] = LOCATIONS_MENU
            ctx.bot.send_message(
                message.chat.id,
                "Сначала нужно получить погоду или выбрать локацию.",
                reply_markup=ctx.locations_menu(),
            )
            return True

        save_result = ctx.save_saved_location_item(
            user_id=user_id,
            title=title,
            label=current_city,
            lat=float(current_lat),
            lon=float(current_lon),
        )
        status = str((save_result or {}).get("status") or "")
        if status == "duplicate_title":
            ctx.bot.send_message(
                message.chat.id,
                f"Локация с названием «{title}» уже есть. Введи другое название.",
                reply_markup=types.ReplyKeyboardRemove(),
            )
            return True
        if status == "duplicate_location":
            existing = save_result.get("item") if isinstance(save_result, dict) else {}
            card = format_saved_location_item(existing if isinstance(existing, dict) else {})
            session_store.user_states[user_id] = LOCATIONS_MENU
            ctx.bot.send_message(
                message.chat.id,
                f"Эта локация уже есть в сохранённых: {card}. Дубль не добавляю.",
                reply_markup=ctx.locations_menu(),
            )
            return True
        if status != "added":
            session_store.user_states[user_id] = LOCATIONS_MENU
            ctx.bot.send_message(
                message.chat.id,
                "Не удалось сохранить локацию. Попробуй позже.",
                reply_markup=ctx.locations_menu(),
            )
            return True
        session_store.user_states[user_id] = LOCATIONS_MENU
        ctx.logger.info("Пользователь %s сохранил локацию с title=%s.", user_id, title)
        user_data = ctx.load_user(user_id)
        ctx.bot.send_message(message.chat.id, "✅ Локация сохранена.", reply_markup=ctx.locations_menu())
        ctx.bot.send_message(message.chat.id, ctx.format_saved_locations(user_data), reply_markup=ctx.locations_menu())
        return True

    if state == WAITING_NEW_SAVED_LOCATION_TITLE:
        title = (message.text or "").strip()
        if not title:
            ctx.bot.send_message(message.chat.id, "⚠️ Введи название локации, например: Дом")
            return True

        draft = session_store.saved_location_drafts.get(user_id)
        if not isinstance(draft, dict):
            session_store.user_states[user_id] = LOCATIONS_MENU
            ctx.bot.send_message(
                message.chat.id,
                "⚠️ Данные локации устарели. Начни добавление заново.",
                reply_markup=ctx.locations_menu(),
            )
            return True

        lat = draft.get("lat")
        lon = draft.get("lon")
        label = draft.get("label")
        if lat is None or lon is None or not label:
            session_store.saved_location_drafts.pop(user_id, None)
            session_store.user_states[user_id] = LOCATIONS_MENU
            ctx.bot.send_message(
                message.chat.id,
                "⚠️ Данные локации устарели. Начни добавление заново.",
                reply_markup=ctx.locations_menu(),
            )
            return True

        save_result = ctx.save_saved_location_item(
            user_id=user_id,
            title=title,
            label=str(label),
            lat=float(lat),
            lon=float(lon),
        )
        status = str((save_result or {}).get("status") or "")
        if status == "duplicate_title":
            ctx.bot.send_message(
                message.chat.id,
                f"Локация с названием «{title}» уже есть. Введи другое название.",
                reply_markup=types.ReplyKeyboardRemove(),
            )
            return True
        if status == "duplicate_location":
            existing = save_result.get("item") if isinstance(save_result, dict) else {}
            card = format_saved_location_item(existing if isinstance(existing, dict) else {})
            session_store.saved_location_drafts.pop(user_id, None)
            session_store.user_states[user_id] = LOCATIONS_MENU
            ctx.bot.send_message(
                message.chat.id,
                f"Эта локация уже есть в сохранённых: {card}. Дубль не добавляю.",
                reply_markup=ctx.locations_menu(),
            )
            return True
        if status != "added":
            session_store.saved_location_drafts.pop(user_id, None)
            session_store.user_states[user_id] = LOCATIONS_MENU
            ctx.bot.send_message(
                message.chat.id,
                "Не удалось сохранить локацию. Попробуй позже.",
                reply_markup=ctx.locations_menu(),
            )
            return True
        session_store.saved_location_drafts.pop(user_id, None)
        session_store.user_states[user_id] = LOCATIONS_MENU
        ctx.logger.info("Пользователь %s добавил новую сохранённую локацию с title=%s.", user_id, title)
        user_data = ctx.load_user(user_id)
        ctx.bot.send_message(
            message.chat.id,
            "✅ Локация сохранена.",
            reply_markup=ctx.locations_menu(),
        )
        ctx.bot.send_message(message.chat.id, ctx.format_saved_locations(user_data), reply_markup=ctx.locations_menu())
        return True

    if state == WAITING_RENAME_LOCATION_TITLE:
        new_title = (message.text or "").strip()
        if not new_title:
            ctx.bot.send_message(message.chat.id, "⚠️ Введи новое название локации.")
            return True

        draft = session_store.rename_location_drafts.get(user_id)
        location_id = draft.get("location_id") if isinstance(draft, dict) else None
        if not isinstance(location_id, str) or not location_id:
            session_store.rename_location_drafts.pop(user_id, None)
            session_store.user_states[user_id] = LOCATIONS_MENU
            ctx.bot.send_message(
                message.chat.id,
                "⚠️ Данные для переименования устарели. Попробуй снова.",
                reply_markup=ctx.locations_menu(),
            )
            return True

        user_data = ctx.load_user(user_id)
        saved_locations = user_data.get("saved_locations", [])
        if not isinstance(saved_locations, list) or not saved_locations:
            session_store.rename_location_drafts.pop(user_id, None)
            session_store.user_states[user_id] = LOCATIONS_MENU
            ctx.bot.send_message(
                message.chat.id,
                "Сохранённых локаций пока нет.",
                reply_markup=ctx.locations_menu(),
            )
            return True

        target_location = next(
            (item for item in saved_locations if isinstance(item, dict) and item.get("id") == location_id),
            None,
        )
        if not isinstance(target_location, dict):
            session_store.rename_location_drafts.pop(user_id, None)
            session_store.user_states[user_id] = LOCATIONS_MENU
            ctx.bot.send_message(
                message.chat.id,
                "⚠️ Выбранная локация не найдена.",
                reply_markup=ctx.locations_menu(),
            )
            return True

        target_location["title"] = new_title
        user_data["saved_locations"] = saved_locations
        ctx.save_user(user_id, user_data)
        session_store.rename_location_drafts.pop(user_id, None)
        session_store.user_states[user_id] = LOCATIONS_MENU
        ctx.bot.send_message(
            message.chat.id,
            "✅ Локация переименована.",
            reply_markup=ctx.locations_menu(),
        )
        ctx.bot.send_message(
            message.chat.id,
            ctx.format_saved_locations(user_data),
            reply_markup=ctx.locations_menu(),
        )
        return True

    if state == LOCATIONS_MENU:
        if message.text == "Сохранить текущую локацию":
            user_data = ctx.load_user(user_id)
            city = user_data.get("city")
            lat = user_data.get("lat")
            lon = user_data.get("lon")
            if lat is None or lon is None or not city:
                ctx.bot.send_message(
                    message.chat.id,
                    "Сначала нужно получить погоду или выбрать локацию.",
                    reply_markup=ctx.locations_menu(),
                )
                return True

            session_store.user_states[user_id] = WAITING_LOCATION_TITLE
            ctx.bot.send_message(
                message.chat.id,
                f"Сохраняю текущую локацию: {city}.\n"
                "Введи название для этой локации, например: Дом",
                reply_markup=types.ReplyKeyboardRemove(),
            )
            return True

        if message.text == "➕ Добавить локацию":
            session_store.saved_location_drafts.pop(user_id, None)
            session_store.rename_location_drafts.pop(user_id, None)
            session_store.user_states[user_id] = WAITING_NEW_SAVED_LOCATION_MENU
            ctx.bot.send_message(
                message.chat.id,
                "Введи название населённого пункта или выбери другой способ ниже:",
                reply_markup=ctx.add_saved_location_menu(),
            )
            return True

        if message.text == "📋 Показать мои локации":
            user_data = ctx.load_user(user_id)
            ctx.bot.send_message(
                message.chat.id,
                ctx.format_saved_locations(user_data),
                reply_markup=ctx.locations_menu(),
            )
            return True

        if message.text == "🗑 Удалить":
            user_data = ctx.load_user(user_id)
            saved_locations = user_data.get("saved_locations", [])
            if not isinstance(saved_locations, list) or not saved_locations:
                ctx.bot.send_message(
                    message.chat.id,
                    "Сохранённых локаций пока нет.",
                    reply_markup=ctx.locations_menu(),
                )
                return True
            ctx.bot.send_message(
                message.chat.id,
                "Выбери локацию для удаления:",
                reply_markup=ctx.build_saved_locations_keyboard(saved_locations, "delete_location_pick"),
            )
            return True

        if message.text == "✏️ Переименовать":
            user_data = ctx.load_user(user_id)
            saved_locations = user_data.get("saved_locations", [])
            if not isinstance(saved_locations, list) or not saved_locations:
                ctx.bot.send_message(
                    message.chat.id,
                    "Сохранённых локаций пока нет.",
                    reply_markup=ctx.locations_menu(),
                )
                return True
            ctx.bot.send_message(
                message.chat.id,
                "Выбери локацию для переименования:",
                reply_markup=ctx.build_saved_locations_keyboard(saved_locations, "rename_location_pick"),
            )
            return True

        ctx.bot.send_message(
            message.chat.id,
            "Выбери действие в разделе локаций или нажми «⬅️ В меню».",
            reply_markup=ctx.locations_menu(),
        )
        return True

    if state == WAITING_NEW_SAVED_LOCATION_MENU:
        query = (message.text or "").strip()
        if query in {"📍 Отправить геолокацию", "📍 Геолокация", "Отправить геолокацию"}:
            session_store.user_states[user_id] = WAITING_NEW_SAVED_LOCATION_GEO
            ctx.bot.send_message(
                message.chat.id,
                "Отправь геолокацию, которую хочешь сохранить.",
                reply_markup=ctx.geo_request_menu(),
            )
            return True
        if query in {"🧭 Координаты", "Ввести координаты"}:
            session_store.user_states[user_id] = WAITING_NEW_SAVED_LOCATION_COORDS
            ctx.bot.send_message(
                message.chat.id,
                "Введи координаты в формате: 55.5789, 37.9051",
                reply_markup=types.ReplyKeyboardRemove(),
            )
            return True
        if not query:
            ctx.bot.send_message(message.chat.id, "⚠️ Введи название населённого пункта.")
            return True

        session_store.user_states[user_id] = WAITING_NEW_SAVED_LOCATION_TEXT
        message.text = query
        return handle_locations_text(
            message,
            user_id,
            WAITING_NEW_SAVED_LOCATION_TEXT,
            ctx=ctx,
            session_store=session_store,
        )

    if state == WAITING_NEW_SAVED_LOCATION_TEXT:
        query = (message.text or "").strip()
        if not query:
            ctx.bot.send_message(message.chat.id, "⚠️ Введи название населённого пункта.")
            return True

        search_result = find_locations_with_assist(
            query,
            scenario="saved_location_add",
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
            label = location_item.get("label") or ctx.build_location_label(location_item, show_coords=False)
            if lat is None or lon is None:
                session_store.user_states[user_id] = LOCATIONS_MENU
                ctx.bot.send_message(
                    message.chat.id,
                    "Не удалось определить локацию. Попробуй снова.",
                    reply_markup=ctx.locations_menu(),
                )
                return True
            return _set_new_saved_location_candidate(
                message,
                user_id,
                lat=float(lat),
                lon=float(lon),
                label=str(label),
                ctx=ctx,
                session_store=session_store,
            )

        session_store.saved_location_drafts[user_id] = {"locations": locations}
        session_store.user_states[user_id] = WAITING_NEW_SAVED_LOCATION_PICK
        ctx.bot.send_message(
            message.chat.id,
            "Найдено несколько вариантов. Выбери нужный населённый пункт:",
            reply_markup=ctx.build_location_pick_keyboard(locations, "savedloc_pick", "savedloc_cancel"),
        )
        return True

    if state == WAITING_NEW_SAVED_LOCATION_PICK:
        draft = session_store.saved_location_drafts.get(user_id)
        if not isinstance(draft, dict) or not isinstance(draft.get("locations"), list):
            session_store.user_states[user_id] = LOCATIONS_MENU
            session_store.saved_location_drafts.pop(user_id, None)
            ctx.bot.send_message(
                message.chat.id,
                "⚠️ Список вариантов устарел. Начни добавление заново.",
                reply_markup=ctx.locations_menu(),
            )
            return True
        ctx.bot.send_message(
            message.chat.id,
            "Выбери населённый пункт кнопкой ниже или нажми «⬅️ Отмена».",
        )
        return True

    if state == WAITING_NEW_SAVED_LOCATION_GEO:
        ctx.bot.send_message(
            message.chat.id,
            "Отправь геолокацию, которую хочешь сохранить.",
            reply_markup=ctx.geo_request_menu(),
        )
        return True

    if state == WAITING_NEW_SAVED_LOCATION_COORDS:
        parsed = parse_coordinates(message.text or "")
        if parsed is None:
            ctx.bot.send_message(message.chat.id, "⚠️ Некорректный формат. Введи координаты в формате: 55.5789, 37.9051")
            return True
        lat, lon = parsed
        location = ctx.get_location_by_coordinates(lat, lon)
        label = ctx.build_location_label(location, show_coords=False) if location else f"Координаты: {lat:.4f}, {lon:.4f}"
        if not location:
            session_store.saved_location_drafts[user_id] = {
                "lat": float(lat),
                "lon": float(lon),
                "label": label,
            }
            session_store.user_states[user_id] = WAITING_NEW_SAVED_LOCATION_COORDS_UNRESOLVED
            ctx.bot.send_message(
                message.chat.id,
                "По этим координатам не удалось определить населённый пункт.\n\n"
                "Можно ввести координаты ещё раз, указать город текстом или сохранить точку только по координатам.",
                reply_markup=_unresolved_coords_menu(types),
            )
            return True
        return _set_new_saved_location_candidate(
            message,
            user_id,
            lat=float(lat),
            lon=float(lon),
            label=str(label),
            ctx=ctx,
            session_store=session_store,
        )

    if state == WAITING_NEW_SAVED_LOCATION_COORDS_UNRESOLVED:
        choice = (message.text or "").strip()
        draft = session_store.saved_location_drafts.get(user_id)
        if not isinstance(draft, dict):
            session_store.user_states[user_id] = WAITING_NEW_SAVED_LOCATION_MENU
            ctx.bot.send_message(
                message.chat.id,
                "Данные координат устарели. Введи название населённого пункта или выбери другой способ ниже:",
                reply_markup=ctx.add_saved_location_menu(),
            )
            return True
        if choice == "💾 Сохранить как точку":
            lat = draft.get("lat")
            lon = draft.get("lon")
            label = draft.get("label")
            if lat is None or lon is None or not label:
                session_store.saved_location_drafts.pop(user_id, None)
                session_store.user_states[user_id] = WAITING_NEW_SAVED_LOCATION_MENU
                ctx.bot.send_message(
                    message.chat.id,
                    "Данные координат устарели. Введи название населённого пункта или выбери другой способ ниже:",
                    reply_markup=ctx.add_saved_location_menu(),
                )
                return True
            return _set_new_saved_location_candidate(
                message,
                user_id,
                lat=float(lat),
                lon=float(lon),
                label=str(label),
                ctx=ctx,
                session_store=session_store,
            )
        if choice == "🧭 Ввести координаты заново":
            session_store.user_states[user_id] = WAITING_NEW_SAVED_LOCATION_COORDS
            ctx.bot.send_message(
                message.chat.id,
                "Введи координаты в формате: 55.5789, 37.9051",
                reply_markup=types.ReplyKeyboardRemove(),
            )
            return True
        if choice == "🏙 Ввести населённый пункт":
            session_store.user_states[user_id] = WAITING_NEW_SAVED_LOCATION_MENU
            ctx.bot.send_message(
                message.chat.id,
                "Введи название населённого пункта или выбери другой способ ниже:",
                reply_markup=ctx.add_saved_location_menu(),
            )
            return True
        ctx.bot.send_message(
            message.chat.id,
            "Выбери действие кнопкой ниже.",
            reply_markup=_unresolved_coords_menu(types),
        )
        return True

    if state == WAITING_AI_COMPARE_MODE:
        choice = (message.text or "").strip()
        if choice in {"🌤 Сейчас", "Сейчас"}:
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
        if choice in {"📅 На дату", "На дату"}:
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
            _ai_compare_reset(user_id, session_store=session_store)
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
                reply_markup=types.ReplyKeyboardRemove(),
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

        return _ai_compare_process_text_query(
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
        return _ai_compare_process_text_query(
            message,
            user_id,
            step=step,
            query=query,
            ctx=ctx,
            session_store=session_store,
        )

    if state in {WAITING_AI_COMPARE_LOC1_COORDS, WAITING_AI_COMPARE_LOC2_COORDS}:
        step = 1 if state == WAITING_AI_COMPARE_LOC1_COORDS else 2
        parsed = parse_coordinates(message.text or "")
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
        return _ai_compare_set_location(
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
