from telebot import types

from .states import (
    ALERTS_MENU,
    WAITING_ALERTS_ADD_GEO,
    WAITING_ALERTS_ADD_MENU,
    WAITING_ALERTS_ADD_PICK,
    WAITING_ALERTS_ADD_SAVED_PICK,
    WAITING_ALERTS_ADD_TEXT,
    WAITING_ALERTS_DELETE_PICK,
    WAITING_ALERTS_INTERVAL_PICK,
    WAITING_ALERTS_INTERVAL_VALUE,
    WAITING_ALERTS_SUBSCRIPTION_MENU,
    WAITING_ALERTS_TOGGLE_PICK,
)


def _show_subscriptions_status(chat_id: int, *, ctx, user_data: dict) -> None:
    """Отправляет пользователю текущий список подписок уведомлений."""
    ctx.bot.send_message(
        chat_id,
        ctx.format_alert_subscriptions(user_data),
        reply_markup=ctx.alerts_menu(),
    )


def _add_subscription_and_reply(
    chat_id: int,
    user_id: int,
    *,
    location_id: str,
    title: str,
    label: str,
    lat: float,
    lon: float,
    ctx,
    session_store,
) -> None:
    """Пытается добавить подписку и отправляет результат пользователю."""
    user_data = ctx.ensure_notifications_defaults(ctx.load_user(user_id))
    user_data = ctx.ensure_alert_subscriptions_defaults(user_data)
    user_data, added = ctx.add_alert_subscription(
        user_data,
        location_id=location_id,
        title=title,
        label=label,
        lat=lat,
        lon=lon,
    )
    session_store.alerts_location_choices.pop(user_id, None)
    session_store.alerts_subscription_drafts.pop(user_id, None)
    session_store.user_states[user_id] = ALERTS_MENU

    if added:
        ctx.save_user(user_id, user_data)
        ctx.bot.send_message(chat_id, "✅ Подписка добавлена.", reply_markup=ctx.alerts_menu())
    else:
        ctx.bot.send_message(chat_id, "Такая подписка уже существует.", reply_markup=ctx.alerts_menu())

    _show_subscriptions_status(chat_id, ctx=ctx, user_data=user_data)


def _build_geocode_subscription_id(lat: float, lon: float) -> str:
    """Формирует стабильный id подписки по нормализованным координатам."""
    lat_n = round(float(lat), 5)
    lon_n = round(float(lon), 5)
    lat_part = f"{abs(lat_n):.5f}".replace(".", "")
    lon_part = f"{abs(lon_n):.5f}".replace(".", "")
    lat_prefix = "n" if lat_n >= 0 else "s"
    lon_prefix = "e" if lon_n >= 0 else "w"
    return f"geo_{lat_prefix}{lat_part}_{lon_prefix}{lon_part}"


def handle_alerts_text(
    message: types.Message,
    user_id: int,
    state: str | None,
    *,
    ctx,
    session_store,
) -> bool:
    """Обрабатывает текстовые состояния сценария уведомлений."""
    alerts_menu_actions = {
        "Показать подписки",
        "Добавить локацию в уведомления",
        "Включить/выключить подписку",
        "Изменить интервал подписки",
        "Удалить подписку",
    }

    if state == WAITING_ALERTS_ADD_TEXT:
        query = (message.text or "").strip()
        ctx.logger.info("Пользователь %s ввёл запрос локации для подписки уведомлений: %s", user_id, query)
        if not query:
            ctx.bot.send_message(message.chat.id, "⚠️ Введи название населённого пункта.")
            return True

        locations = ctx.get_locations(query, limit=5)
        locations = ctx.rank_locations(query, locations)
        if not locations:
            ctx.bot.send_message(
                message.chat.id,
                "⚠️ Населённый пункт не найден. Попробуй указать название точнее, например с регионом, или отправь геолокацию.",
            )
            return True

        if len(locations) == 1:
            location_item = ctx.build_geocode_item_with_disambiguated_label(locations, 0)
            lat = location_item.get("lat")
            lon = location_item.get("lon")
            label = location_item.get("label") or ctx.build_location_label(location_item, show_coords=False)
            if lat is None or lon is None:
                ctx.bot.send_message(
                    message.chat.id,
                    "Не удалось определить локацию. Попробуй снова.",
                    reply_markup=ctx.alerts_menu(),
                )
                session_store.user_states[user_id] = ALERTS_MENU
                return True

            _add_subscription_and_reply(
                message.chat.id,
                user_id,
                location_id=_build_geocode_subscription_id(float(lat), float(lon)),
                title=(
                    str(location_item.get("local_name") or location_item.get("name") or "").strip()
                    or label
                ),
                label=label,
                lat=float(lat),
                lon=float(lon),
                ctx=ctx,
                session_store=session_store,
            )
            return True

        session_store.alerts_location_choices[user_id] = locations
        session_store.user_states[user_id] = WAITING_ALERTS_ADD_PICK
        ctx.bot.send_message(
            message.chat.id,
            "Найдено несколько вариантов. Выбери нужный населённый пункт:",
            reply_markup=ctx.build_location_pick_keyboard(locations, "alerts_add_pick", "alerts_add_cancel"),
        )
        return True

    if state == WAITING_ALERTS_ADD_PICK:
        if not session_store.alerts_location_choices.get(user_id):
            session_store.user_states[user_id] = ALERTS_MENU
            ctx.bot.send_message(
                message.chat.id,
                "⚠️ Список вариантов устарел. Введи населённый пункт заново.",
                reply_markup=ctx.alerts_menu(),
            )
            return True
        ctx.bot.send_message(message.chat.id, "Выбери населённый пункт кнопкой ниже или нажми «⬅️ Отмена».")
        return True

    if state == WAITING_ALERTS_ADD_GEO:
        ctx.bot.send_message(
            message.chat.id,
            "Пожалуйста, отправь геолокацию через кнопку ниже или вернись в меню.",
            reply_markup=ctx.geo_request_menu(),
        )
        return True

    if state == WAITING_ALERTS_ADD_MENU:
        if message.text == "Выбрать из сохранённых":
            user_data = ctx.load_user(user_id)
            saved_locations = user_data.get("saved_locations", [])
            if not isinstance(saved_locations, list) or not saved_locations:
                ctx.bot.send_message(
                    message.chat.id,
                    "Сохранённых локаций пока нет.",
                    reply_markup=ctx.alerts_add_location_menu(),
                )
                return True

            session_store.user_states[user_id] = WAITING_ALERTS_ADD_SAVED_PICK
            ctx.bot.send_message(
                message.chat.id,
                "Выбери сохранённую локацию для подписки:",
                reply_markup=ctx.build_saved_locations_keyboard(saved_locations, "alerts_sub_add_saved"),
            )
            return True

        if message.text == "Ввести населённый пункт":
            session_store.user_states[user_id] = WAITING_ALERTS_ADD_TEXT
            ctx.bot.send_message(
                message.chat.id,
                "Введи населённый пункт для подписки уведомлений.",
                reply_markup=types.ReplyKeyboardRemove(),
            )
            return True

        if message.text == "Отправить геолокацию":
            session_store.user_states[user_id] = WAITING_ALERTS_ADD_GEO
            ctx.bot.send_message(
                message.chat.id,
                "Отправь геолокацию для подписки уведомлений.",
                reply_markup=ctx.geo_request_menu(),
            )
            return True

        ctx.bot.send_message(
            message.chat.id,
            "Выбери действие кнопкой ниже или нажми «⬅️ В меню».",
            reply_markup=ctx.alerts_add_location_menu(),
        )
        return True

    if state in {WAITING_ALERTS_ADD_SAVED_PICK, WAITING_ALERTS_TOGGLE_PICK, WAITING_ALERTS_INTERVAL_PICK, WAITING_ALERTS_DELETE_PICK}:
        # Если пользователь нажал кнопку из меню уведомлений, выходим из текущего pick-сценария
        # и даём отработать стандартным веткам ALERTS_MENU.
        if (message.text or "").strip() in alerts_menu_actions:
            session_store.user_states[user_id] = ALERTS_MENU
            state = ALERTS_MENU
        else:
            ctx.bot.send_message(message.chat.id, "Выбери подписку кнопкой ниже или нажми «⬅️ В меню».")
            return True

    if state in {ALERTS_MENU, WAITING_ALERTS_SUBSCRIPTION_MENU}:
        user_data = ctx.ensure_notifications_defaults(ctx.load_user(user_id))
        user_data = ctx.ensure_alert_subscriptions_defaults(user_data)

        if message.text == "Показать подписки":
            session_store.user_states[user_id] = ALERTS_MENU
            _show_subscriptions_status(message.chat.id, ctx=ctx, user_data=user_data)
            return True

        if message.text == "Добавить локацию в уведомления":
            session_store.alerts_location_choices.pop(user_id, None)
            session_store.alerts_subscription_drafts.pop(user_id, None)
            session_store.user_states[user_id] = WAITING_ALERTS_ADD_MENU
            ctx.bot.send_message(
                message.chat.id,
                "Выбери способ добавления локации в уведомления:",
                reply_markup=ctx.alerts_add_location_menu(),
            )
            return True

        subscriptions = user_data.get("alert_subscriptions", [])
        if message.text == "Включить/выключить подписку":
            if not subscriptions:
                ctx.bot.send_message(message.chat.id, "Подписок на уведомления пока нет.", reply_markup=ctx.alerts_menu())
                return True
            session_store.user_states[user_id] = WAITING_ALERTS_TOGGLE_PICK
            ctx.bot.send_message(
                message.chat.id,
                "Выбери подписку для изменения статуса:",
                reply_markup=ctx.build_alert_subscriptions_keyboard(subscriptions, "alerts_sub_toggle"),
            )
            return True

        if message.text == "Изменить интервал подписки":
            if not subscriptions:
                ctx.bot.send_message(message.chat.id, "Подписок на уведомления пока нет.", reply_markup=ctx.alerts_menu())
                return True
            session_store.user_states[user_id] = WAITING_ALERTS_INTERVAL_PICK
            ctx.bot.send_message(
                message.chat.id,
                "Выбери подписку для изменения интервала:",
                reply_markup=ctx.build_alert_subscriptions_keyboard(subscriptions, "alerts_sub_interval"),
            )
            return True

        if message.text == "Удалить подписку":
            if not subscriptions:
                ctx.bot.send_message(message.chat.id, "Подписок на уведомления пока нет.", reply_markup=ctx.alerts_menu())
                return True
            session_store.user_states[user_id] = WAITING_ALERTS_DELETE_PICK
            ctx.bot.send_message(
                message.chat.id,
                "Выбери подписку для удаления:",
                reply_markup=ctx.build_alert_subscriptions_keyboard(subscriptions, "alerts_sub_delete"),
            )
            return True

        ctx.bot.send_message(message.chat.id, "Выбери действие в меню уведомлений.")
        return True

    if state == WAITING_ALERTS_INTERVAL_VALUE:
        draft = session_store.alerts_subscription_drafts.get(user_id)
        subscription_id = draft.get("location_id") if isinstance(draft, dict) else None
        if not isinstance(subscription_id, str) or not subscription_id:
            session_store.alerts_subscription_drafts.pop(user_id, None)
            session_store.user_states[user_id] = ALERTS_MENU
            ctx.bot.send_message(message.chat.id, "⚠️ Выбор подписки устарел.", reply_markup=ctx.alerts_menu())
            return True

        try:
            interval = int((message.text or "").strip())
        except ValueError:
            ctx.bot.send_message(message.chat.id, "⚠️ Введите положительное число часов.", reply_markup=ctx.alerts_menu())
            return True
        if interval <= 0:
            ctx.bot.send_message(message.chat.id, "⚠️ Введите положительное число часов.", reply_markup=ctx.alerts_menu())
            return True

        user_data = ctx.ensure_alert_subscriptions_defaults(ctx.ensure_notifications_defaults(ctx.load_user(user_id)))
        subscriptions = user_data["alert_subscriptions"]
        target = next((item for item in subscriptions if item.get("location_id") == subscription_id), None)
        if not isinstance(target, dict):
            session_store.alerts_subscription_drafts.pop(user_id, None)
            session_store.user_states[user_id] = ALERTS_MENU
            ctx.bot.send_message(message.chat.id, "⚠️ Подписка не найдена.", reply_markup=ctx.alerts_menu())
            return True

        target["interval_h"] = interval
        target["last_check_ts"] = 0
        ctx.save_user(user_id, user_data)
        session_store.alerts_subscription_drafts.pop(user_id, None)
        session_store.user_states[user_id] = ALERTS_MENU
        ctx.bot.send_message(message.chat.id, "✅ Интервал подписки обновлён.", reply_markup=ctx.alerts_menu())
        _show_subscriptions_status(message.chat.id, ctx=ctx, user_data=user_data)
        return True

    return False
