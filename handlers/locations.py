from telebot import types

from .states import (
    LOCATIONS_MENU,
    WAITING_LOCATION_TITLE,
    WAITING_NEW_SAVED_LOCATION_GEO,
    WAITING_NEW_SAVED_LOCATION_MENU,
    WAITING_NEW_SAVED_LOCATION_PICK,
    WAITING_NEW_SAVED_LOCATION_TEXT,
    WAITING_NEW_SAVED_LOCATION_TITLE,
    WAITING_RENAME_LOCATION_TITLE,
)
from weather_app import (
    build_geocode_item_with_disambiguated_label,
    build_location_label,
    get_locations,
)


def handle_locations_text(
    message: types.Message,
    user_id: int,
    state: str | None,
    *,
    bot,
    logger,
    user_states: dict,
    saved_location_drafts: dict,
    rename_location_drafts: dict,
    load_user,
    save_user,
    save_saved_location_item,
    format_saved_locations,
    locations_menu,
    add_saved_location_menu,
    build_saved_locations_keyboard,
    build_favorite_pick_keyboard,
    build_location_pick_keyboard,
    geo_request_menu,
) -> bool:
    """Обрабатывает текстовые состояния сценария «Мои локации»."""
    if state == WAITING_LOCATION_TITLE:
        title = (message.text or "").strip()
        if not title:
            bot.send_message(message.chat.id, "⚠️ Введи название локации, например: Дом")
            return True

        user_data = load_user(user_id)
        current_city = user_data.get("city")
        current_lat = user_data.get("lat")
        current_lon = user_data.get("lon")

        if current_lat is None or current_lon is None or not current_city:
            user_states[user_id] = LOCATIONS_MENU
            bot.send_message(
                message.chat.id,
                "Сначала нужно получить погоду или выбрать локацию.",
                reply_markup=locations_menu(),
            )
            return True

        save_saved_location_item(
            user_id=user_id,
            title=title,
            label=current_city,
            lat=float(current_lat),
            lon=float(current_lon),
        )
        user_states[user_id] = LOCATIONS_MENU
        logger.info("Пользователь %s сохранил локацию с title=%s.", user_id, title)
        bot.send_message(message.chat.id, "✅ Локация сохранена.", reply_markup=locations_menu())
        return True

    if state == WAITING_NEW_SAVED_LOCATION_TITLE:
        title = (message.text or "").strip()
        if not title:
            bot.send_message(message.chat.id, "⚠️ Введи название локации, например: Дом")
            return True

        draft = saved_location_drafts.get(user_id)
        if not isinstance(draft, dict):
            user_states[user_id] = LOCATIONS_MENU
            bot.send_message(
                message.chat.id,
                "⚠️ Данные локации устарели. Начни добавление заново.",
                reply_markup=locations_menu(),
            )
            return True

        lat = draft.get("lat")
        lon = draft.get("lon")
        label = draft.get("label")
        if lat is None or lon is None or not label:
            saved_location_drafts.pop(user_id, None)
            user_states[user_id] = LOCATIONS_MENU
            bot.send_message(
                message.chat.id,
                "⚠️ Данные локации устарели. Начни добавление заново.",
                reply_markup=locations_menu(),
            )
            return True

        save_saved_location_item(
            user_id=user_id,
            title=title,
            label=str(label),
            lat=float(lat),
            lon=float(lon),
        )
        saved_location_drafts.pop(user_id, None)
        user_states[user_id] = LOCATIONS_MENU
        logger.info("Пользователь %s добавил новую сохранённую локацию с title=%s.", user_id, title)
        bot.send_message(
            message.chat.id,
            "✅ Локация сохранена.",
            reply_markup=locations_menu(),
        )
        return True

    if state == WAITING_RENAME_LOCATION_TITLE:
        new_title = (message.text or "").strip()
        if not new_title:
            bot.send_message(message.chat.id, "⚠️ Введи новое название локации.")
            return True

        draft = rename_location_drafts.get(user_id)
        location_id = draft.get("location_id") if isinstance(draft, dict) else None
        if not isinstance(location_id, str) or not location_id:
            rename_location_drafts.pop(user_id, None)
            user_states[user_id] = LOCATIONS_MENU
            bot.send_message(
                message.chat.id,
                "⚠️ Данные для переименования устарели. Попробуй снова.",
                reply_markup=locations_menu(),
            )
            return True

        user_data = load_user(user_id)
        saved_locations = user_data.get("saved_locations", [])
        if not isinstance(saved_locations, list) or not saved_locations:
            rename_location_drafts.pop(user_id, None)
            user_states[user_id] = LOCATIONS_MENU
            bot.send_message(
                message.chat.id,
                "Сохранённых локаций пока нет.",
                reply_markup=locations_menu(),
            )
            return True

        target_location = next(
            (item for item in saved_locations if isinstance(item, dict) and item.get("id") == location_id),
            None,
        )
        if not isinstance(target_location, dict):
            rename_location_drafts.pop(user_id, None)
            user_states[user_id] = LOCATIONS_MENU
            bot.send_message(
                message.chat.id,
                "⚠️ Выбранная локация не найдена.",
                reply_markup=locations_menu(),
            )
            return True

        target_location["title"] = new_title
        user_data["saved_locations"] = saved_locations
        save_user(user_id, user_data)
        rename_location_drafts.pop(user_id, None)
        user_states[user_id] = LOCATIONS_MENU
        bot.send_message(
            message.chat.id,
            "✅ Название локации обновлено.",
            reply_markup=locations_menu(),
        )
        return True

    if state == LOCATIONS_MENU:
        if message.text == "Сохранить текущую локацию":
            user_data = load_user(user_id)
            city = user_data.get("city")
            lat = user_data.get("lat")
            lon = user_data.get("lon")
            if lat is None or lon is None or not city:
                bot.send_message(
                    message.chat.id,
                    "Сначала нужно получить погоду или выбрать локацию.",
                    reply_markup=locations_menu(),
                )
                return True

            user_states[user_id] = WAITING_LOCATION_TITLE
            bot.send_message(
                message.chat.id,
                "Введи название для этой локации, например: Дом",
                reply_markup=types.ReplyKeyboardRemove(),
            )
            return True

        if message.text == "Добавить новую локацию":
            saved_location_drafts.pop(user_id, None)
            rename_location_drafts.pop(user_id, None)
            user_states[user_id] = WAITING_NEW_SAVED_LOCATION_MENU
            bot.send_message(
                message.chat.id,
                "Выбери способ добавления новой локации:",
                reply_markup=add_saved_location_menu(),
            )
            return True

        if message.text == "Показать мои локации":
            user_data = load_user(user_id)
            bot.send_message(
                message.chat.id,
                format_saved_locations(user_data),
                reply_markup=locations_menu(),
            )
            return True

        if message.text == "Сделать основной":
            user_data = load_user(user_id)
            saved_locations = user_data.get("saved_locations", [])
            if not isinstance(saved_locations, list) or not saved_locations:
                bot.send_message(
                    message.chat.id,
                    "Сохранённых локаций пока нет.",
                    reply_markup=locations_menu(),
                )
                return True

            bot.send_message(
                message.chat.id,
                "Выбери основную локацию:",
                reply_markup=build_favorite_pick_keyboard(saved_locations),
            )
            return True

        if message.text == "Удалить локацию":
            user_data = load_user(user_id)
            saved_locations = user_data.get("saved_locations", [])
            if not isinstance(saved_locations, list) or not saved_locations:
                bot.send_message(
                    message.chat.id,
                    "Сохранённых локаций пока нет.",
                    reply_markup=locations_menu(),
                )
                return True
            bot.send_message(
                message.chat.id,
                "Выбери локацию для удаления:",
                reply_markup=build_saved_locations_keyboard(saved_locations, "delete_location_pick"),
            )
            return True

        if message.text == "Переименовать локацию":
            user_data = load_user(user_id)
            saved_locations = user_data.get("saved_locations", [])
            if not isinstance(saved_locations, list) or not saved_locations:
                bot.send_message(
                    message.chat.id,
                    "Сохранённых локаций пока нет.",
                    reply_markup=locations_menu(),
                )
                return True
            bot.send_message(
                message.chat.id,
                "Выбери локацию для переименования:",
                reply_markup=build_saved_locations_keyboard(saved_locations, "rename_location_pick"),
            )
            return True

        bot.send_message(
            message.chat.id,
            "Выбери действие в разделе локаций или нажми «⬅️ В меню».",
            reply_markup=locations_menu(),
        )
        return True

    if state == WAITING_NEW_SAVED_LOCATION_MENU:
        if message.text == "Ввести населённый пункт":
            user_states[user_id] = WAITING_NEW_SAVED_LOCATION_TEXT
            bot.send_message(
                message.chat.id,
                "Введи населённый пункт, который хочешь сохранить.",
                reply_markup=types.ReplyKeyboardRemove(),
            )
            return True

        if message.text == "Отправить геолокацию":
            user_states[user_id] = WAITING_NEW_SAVED_LOCATION_GEO
            bot.send_message(
                message.chat.id,
                "Отправь геолокацию, которую хочешь сохранить.",
                reply_markup=geo_request_menu(),
            )
            return True

        bot.send_message(
            message.chat.id,
            "Выбери действие кнопкой ниже или нажми «⬅️ В меню».",
            reply_markup=add_saved_location_menu(),
        )
        return True

    if state == WAITING_NEW_SAVED_LOCATION_TEXT:
        query = (message.text or "").strip()
        if not query:
            bot.send_message(message.chat.id, "⚠️ Введи название населённого пункта.")
            return True

        locations = get_locations(query, limit=5)
        if not locations:
            bot.send_message(
                message.chat.id,
                "⚠️ Населённый пункт не найден. Попробуй указать название точнее.",
            )
            return True

        if len(locations) == 1:
            location_item = build_geocode_item_with_disambiguated_label(locations, 0)
            lat = location_item.get("lat")
            lon = location_item.get("lon")
            label = location_item.get("label") or build_location_label(location_item, show_coords=False)
            if lat is None or lon is None:
                user_states[user_id] = LOCATIONS_MENU
                bot.send_message(
                    message.chat.id,
                    "Не удалось определить локацию. Попробуй снова.",
                    reply_markup=locations_menu(),
                )
                return True
            saved_location_drafts[user_id] = {
                "lat": float(lat),
                "lon": float(lon),
                "label": label,
            }
            user_states[user_id] = WAITING_NEW_SAVED_LOCATION_TITLE
            bot.send_message(
                message.chat.id,
                "Введи название для этой локации, например: Дом",
                reply_markup=types.ReplyKeyboardRemove(),
            )
            return True

        saved_location_drafts[user_id] = {"locations": locations}
        user_states[user_id] = WAITING_NEW_SAVED_LOCATION_PICK
        bot.send_message(
            message.chat.id,
            "Найдено несколько вариантов. Выбери нужный населённый пункт:",
            reply_markup=build_location_pick_keyboard(locations, "savedloc_pick", "savedloc_cancel"),
        )
        return True

    if state == WAITING_NEW_SAVED_LOCATION_PICK:
        draft = saved_location_drafts.get(user_id)
        if not isinstance(draft, dict) or not isinstance(draft.get("locations"), list):
            user_states[user_id] = LOCATIONS_MENU
            saved_location_drafts.pop(user_id, None)
            bot.send_message(
                message.chat.id,
                "⚠️ Список вариантов устарел. Начни добавление заново.",
                reply_markup=locations_menu(),
            )
            return True
        bot.send_message(
            message.chat.id,
            "Выбери населённый пункт кнопкой ниже или нажми «⬅️ Отмена».",
        )
        return True

    if state == WAITING_NEW_SAVED_LOCATION_GEO:
        bot.send_message(
            message.chat.id,
            "Отправь геолокацию, которую хочешь сохранить.",
            reply_markup=geo_request_menu(),
        )
        return True

    return False
