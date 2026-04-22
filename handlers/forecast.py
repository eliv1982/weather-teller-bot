from telebot import types

from .states import (
    WAITING_FORECAST_CITY,
    WAITING_FORECAST_PICK,
    WAITING_FORECAST_USE_SAVED_LOCATION,
)
from weather_app import get_locations


def handle_forecast_text(
    message: types.Message,
    user_id: int,
    state: str | None,
    *,
    ctx,
    session_store,
    send_forecast_by_coordinates,
) -> bool:
    """Обрабатывает текстовые состояния сценария прогноза."""
    if state == WAITING_FORECAST_USE_SAVED_LOCATION:
        answer = (message.text or "").strip().lower()
        yes_values = {"да", "д", "yes", "y"}
        no_values = {"нет", "н", "no"}

        if answer in yes_values:
            ctx.logger.info("Пользователь %s выбрал: Да (прогноз по сохранённой локации).", user_id)
            draft = session_store.forecast_saved_drafts.get(user_id)
            if not draft:
                session_store.user_states[user_id] = WAITING_FORECAST_CITY
                ctx.bot.send_message(message.chat.id, "Введи название населённого пункта для прогноза на 5 дней.")
                return True

            if send_forecast_by_coordinates(
                message,
                user_id,
                draft["lat"],
                draft["lon"],
                draft["city"],
                save_location=False,
                preferred_city_label=draft["city"],
            ):
                ctx.logger.info(
                    "Успешно получен прогноз по сохранённой локации для пользователя %s.",
                    user_id,
                )
            return True

        if answer in no_values:
            ctx.logger.info("Пользователь %s выбрал: Нет (ввести населённый пункт для прогноза).", user_id)
            session_store.forecast_saved_drafts.pop(user_id, None)
            session_store.user_states[user_id] = WAITING_FORECAST_CITY
            ctx.bot.send_message(message.chat.id, "Введи название населённого пункта для прогноза на 5 дней.")
            return True

        ctx.bot.send_message(message.chat.id, "Пожалуйста, ответь: Да или Нет.")
        return True

    if state == WAITING_FORECAST_CITY:
        query = (message.text or "").strip()
        ctx.logger.info("Пользователь %s ввёл населённый пункт для прогноза: %s", user_id, query)
        if not query:
            ctx.bot.send_message(message.chat.id, "⚠️ Введи название населённого пункта.")
            return True

        locations = get_locations(query, limit=5)
        if not locations:
            ctx.bot.send_message(
                message.chat.id,
                "⚠️ Населённый пункт не найден. Попробуй указать название точнее, например с регионом.",
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
                    "Не удалось получить прогноз. Попробуй позже.",
                    reply_markup=ctx.main_menu(),
                )
                return True
            if send_forecast_by_coordinates(
                message,
                user_id,
                float(lat),
                float(lon),
                city,
                save_location=True,
                preferred_city_label=city,
            ):
                ctx.logger.info("Успешно получен прогноз для пользователя %s по населённому пункту %s.", user_id, query)
            return True

        session_store.forecast_location_choices[user_id] = locations
        session_store.user_states[user_id] = WAITING_FORECAST_PICK
        ctx.logger.info(
            "Найдено несколько вариантов (%s) для прогноза у пользователя %s: %s",
            len(locations),
            user_id,
            query,
        )
        ctx.bot.send_message(
            message.chat.id,
            "Найдено несколько вариантов. Выбери нужный населённый пункт:",
            reply_markup=ctx.build_scenario_location_choice_keyboard(locations, "forecast"),
        )
        return True

    if state == WAITING_FORECAST_PICK:
        if not session_store.forecast_location_choices.get(user_id):
            session_store.user_states.pop(user_id, None)
            ctx.bot.send_message(
                message.chat.id,
                "⚠️ Список вариантов устарел. Введи населённый пункт заново.",
                reply_markup=ctx.main_menu(),
            )
            return True
        ctx.bot.send_message(
            message.chat.id,
            "Выбери населённый пункт кнопкой ниже или нажми «⬅️ Отмена».",
        )
        return True

    return False
