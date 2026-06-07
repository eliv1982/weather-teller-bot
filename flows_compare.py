from telebot import types

from handlers.states import WAITING_COMPARE_CITY_1


def start_compare_flow(message: types.Message, *, ctx, session_store) -> None:
    """Запускает сценарий сравнения двух населённых пунктов."""
    user_id = message.from_user.id
    ctx.logger.info("Запущен сценарий сравнения населённых пунктов для пользователя %s.", user_id)
    session_store.compare_drafts.pop(user_id, None)
    session_store.compare_location_choices.pop(user_id, None)
    session_store.user_states[user_id] = WAITING_COMPARE_CITY_1
    ctx.bot.send_message(message.chat.id, "Введи первый населённый пункт для сравнения.")


def complete_compare_two_locations(
    chat_id: int,
    user_id: int,
    lat_1: float,
    lon_1: float,
    city_label_1: str,
    lat_2: float,
    lon_2: float,
    city_label_2: str,
    *,
    ctx,
    session_store,
) -> None:
    """Загружает погоду по двум точкам и отправляет текст сравнения."""
    weather_1 = ctx.get_current_weather(lat_1, lon_1)
    weather_2 = ctx.get_current_weather(lat_2, lon_2)

    if not weather_1 or not weather_2:
        ctx.logger.warning("Не удалось получить данные для сравнения у пользователя %s.", user_id)
        session_store.user_states.pop(user_id, None)
        session_store.compare_drafts.pop(user_id, None)
        session_store.compare_location_choices.pop(user_id, None)
        ctx.bot.send_message(
            chat_id,
            "Не удалось получить данные для сравнения. Попробуй позже.",
            reply_markup=ctx.main_menu(),
        )
        return

    answer = ctx.format_compare_response(city_label_1, weather_1, city_label_2, weather_2)
    ctx.logger.info(
        "Успешно выполнено сравнение для пользователя %s: %s vs %s.",
        user_id,
        city_label_1,
        city_label_2,
    )
    session_store.user_states.pop(user_id, None)
    session_store.compare_drafts.pop(user_id, None)
    session_store.compare_location_choices.pop(user_id, None)
    ctx.bot.send_message(chat_id, answer, reply_markup=ctx.main_menu())
