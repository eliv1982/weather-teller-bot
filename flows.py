import time
from datetime import date
from telebot import types
from forecast_service import is_remaining_day_forecast
from formatters import format_history_monthly_climate_response
from flows_compare import (
    complete_compare_two_locations as run_complete_compare_two_locations,
    start_compare_flow as run_start_compare_flow,
)
from flows_forecast import (
    send_forecast_by_coordinates as run_send_forecast_by_coordinates,
    send_today_forecast_by_coordinates as run_send_today_forecast_by_coordinates,
    send_tomorrow_forecast_by_coordinates as run_send_tomorrow_forecast_by_coordinates,
    show_forecast_days_message as run_show_forecast_days_message,
    start_forecast_flow as run_start_forecast_flow,
    start_today_forecast_flow as run_start_today_forecast_flow,
    start_tomorrow_forecast_flow as run_start_tomorrow_forecast_flow,
)
from flows_history import (
    prepare_weather_history_by_coordinates as run_prepare_weather_history_by_coordinates,
    send_history_monthly_report as run_send_history_monthly_report,
    send_weather_history_by_date as run_send_weather_history_by_date,
    start_weather_history_flow as run_start_weather_history_flow,
)
from flows_source_compare import (
    send_source_compare_by_coordinates as run_send_source_compare_by_coordinates,
    send_source_compare_by_selected_date as run_send_source_compare_by_selected_date,
    start_source_compare_flow as run_start_source_compare_flow,
    start_source_compare_mode_flow as run_start_source_compare_mode_flow,
)

from handlers.callbacks_common import try_delete_message
from handlers.states import (
    ALERTS_MENU,
    LOCATIONS_MENU,
    WEATHER_MENU,
    WAITING_ALERTS_SUBSCRIPTION_MENU,
    WAITING_CURRENT_WEATHER_CITY,
    WAITING_DETAILS_CITY,
    WAITING_GEO_LOCATION,
    WAITING_HISTORY_CITY,
)
from source_compare_service import (
    compare_current_sources,
    compare_sources_by_date,
    compare_today_sources,
    compare_tomorrow_sources,
    get_source_compare_available_dates,
)
from weather_history_service import get_weather_history_by_date
from weather_monthly_service import get_monthly_climate_normals, get_monthly_history_for_month
from workers.alerts_worker import alerts_worker as run_alerts_worker


def _get_favorite_location(user_data: dict) -> dict | None:
    """Возвращает основную локацию пользователя из saved_locations, если она валидна."""
    favorite_id = user_data.get("favorite_location_id")
    saved_locations = user_data.get("saved_locations", [])
    if not isinstance(favorite_id, str) or not favorite_id:
        return None
    if not isinstance(saved_locations, list):
        return None

    favorite_item = next(
        (
            item
            for item in saved_locations
            if isinstance(item, dict) and item.get("id") == favorite_id
        ),
        None,
    )
    if not isinstance(favorite_item, dict):
        return None
    if favorite_item.get("lat") is None or favorite_item.get("lon") is None:
        return None
    return favorite_item


def start_alerts_flow(message: types.Message, *, ctx, session_store) -> None:
    """Запускает раздел уведомлений."""
    user_id = message.from_user.id
    ctx.logger.info("Пользователь %s вошёл в раздел уведомлений.", user_id)
    ctx.alerts_subscription_service.ensure_defaults(ctx.ensure_notifications_defaults(ctx.load_user(user_id)))
    session_store.set_state(user_id, WAITING_ALERTS_SUBSCRIPTION_MENU)
    ctx.bot.send_message(
        message.chat.id,
        "Раздел уведомлений по нескольким локациям.\nВыбери действие:",
        reply_markup=ctx.alerts_menu(),
    )


def start_locations_flow(message: types.Message, *, ctx, session_store) -> None:
    """Открывает раздел управления сохранёнными локациями."""
    user_id = message.from_user.id
    ctx.logger.info("Пользователь %s вошёл в раздел сохранённых локаций.", user_id)
    session_store.clear_saved_location_flows(user_id)
    session_store.set_state(user_id, LOCATIONS_MENU)
    ctx.bot.send_message(
        message.chat.id,
        "Раздел сохранённых локаций.\nВыбери действие:",
        reply_markup=ctx.locations_menu(),
    )


def start_current_weather_flow(message: types.Message, *, ctx, session_store) -> None:
    """Запускает сценарий ввода населённого пункта для текущей погоды."""
    user_id = message.from_user.id
    session_store.current_location_choices.pop(user_id, None)
    session_store.current_favorite_drafts.pop(user_id, None)
    user_data = ctx.load_user(user_id)
    has_saved = isinstance(user_data.get("saved_locations"), list) and bool(user_data.get("saved_locations"))
    session_store.set_state(user_id, WAITING_CURRENT_WEATHER_CITY)
    ctx.bot.send_message(
        message.chat.id,
        "Введи название населённого пункта или выбери другой способ ниже:",
        reply_markup=ctx.location_input_menu(has_saved_locations=has_saved),
    )


def start_geo_weather_flow(message: types.Message, *, ctx, session_store) -> None:
    """Запускает сценарий получения погоды по геолокации."""
    ctx.logger.info("Запущен сценарий геолокации для пользователя %s.", message.from_user.id)
    session_store.set_state(message.from_user.id, WAITING_GEO_LOCATION)
    ctx.bot.send_message(
        message.chat.id,
        "Отправь геолокацию через кнопку ниже.\n"
        "Если ты в Telegram Desktop и отправка недоступна, открой бота на телефоне или вернись в меню.",
        reply_markup=ctx.geo_request_menu(),
    )


def start_details_flow(message: types.Message, *, ctx, session_store) -> None:
    """Запускает сценарий получения расширенных данных по населённому пункту."""
    user_id = message.from_user.id
    ctx.logger.info("Запущен сценарий расширенных данных для пользователя %s.", user_id)
    session_store.details_location_choices.pop(user_id, None)
    session_store.details_favorite_drafts.pop(user_id, None)
    user_data = ctx.load_user(user_id)
    has_saved = isinstance(user_data.get("saved_locations"), list) and bool(user_data.get("saved_locations"))

    session_store.user_states[user_id] = WAITING_DETAILS_CITY
    ctx.bot.send_message(
        message.chat.id,
        "Введи название населённого пункта или выбери другой способ ниже:",
        reply_markup=ctx.location_input_menu(has_saved_locations=has_saved),
    )


def start_compare_flow(message: types.Message, *, ctx, session_store) -> None:
    """Запускает сценарий сравнения двух населённых пунктов."""
    run_start_compare_flow(message, ctx=ctx, session_store=session_store)


def start_forecast_flow(message: types.Message, *, ctx, session_store) -> None:
    """Запускает сценарий прогноза на 5 дней."""
    run_start_forecast_flow(message, ctx=ctx, session_store=session_store)


def start_tomorrow_forecast_flow(message: types.Message, *, ctx, session_store) -> None:
    """Запускает сценарий прогноза на завтра."""
    run_start_tomorrow_forecast_flow(message, ctx=ctx, session_store=session_store)


def start_today_forecast_flow(message: types.Message, *, ctx, session_store) -> None:
    """Запускает сценарий прогноза на сегодня."""
    run_start_today_forecast_flow(message, ctx=ctx, session_store=session_store)


def start_source_compare_flow(message: types.Message, *, ctx, session_store) -> None:
    """Открывает подменю выбора режима сравнения источников."""
    run_start_source_compare_flow(message, ctx=ctx, session_store=session_store)


def start_source_compare_mode_flow(message: types.Message, mode: str, *, ctx, session_store) -> None:
    """Запускает конкретный режим source compare и переводит к выбору локации."""
    run_start_source_compare_mode_flow(message, mode, ctx=ctx, session_store=session_store)


def start_weather_history_flow(message: types.Message, *, ctx, session_store) -> None:
    """Запускает сценарий архивной погоды и показывает первое подменю раздела."""
    run_start_weather_history_flow(message, ctx=ctx, session_store=session_store)


def start_weather_menu_flow(message: types.Message, *, ctx, session_store) -> None:
    """Открывает экран выбора погодного раздела и сохраняет menu-state."""
    session_store.set_state(message.from_user.id, WEATHER_MENU)
    ctx.bot.send_message(
        message.chat.id,
        "Выбери раздел в меню ниже.",
        reply_markup=ctx.weather_menu(),
    )


def show_forecast_days_message(message: types.Message, user_id: int, *, ctx, session_store) -> None:
    """Показывает сообщение со списком дней прогноза."""
    run_show_forecast_days_message(message, user_id, ctx=ctx, session_store=session_store)


def send_details_by_coordinates(
    message: types.Message,
    user_id: int,
    lat: float,
    lon: float,
    city_fallback: str,
    *,
    preferred_city_label: str | None = None,
    ctx,
    session_store,
) -> bool:
    """Получает и отправляет расширенные данные по известным координатам."""
    weather = ctx.get_current_weather(lat, lon)
    air_components = ctx.get_air_pollution(lat, lon)

    if not weather:
        ctx.logger.warning(
            "Не удалось получить расширенные данные для пользователя %s (населённый пункт: %s, lat: %s, lon: %s).",
            user_id,
            city_fallback,
            lat,
            lon,
        )
        session_store.user_states.pop(user_id, None)
        session_store.details_saved_drafts.pop(user_id, None)
        session_store.details_location_choices.pop(user_id, None)
        ctx.bot.send_message(
            message.chat.id,
            "Не удалось получить расширенные данные. Попробуй позже.",
            reply_markup=ctx.main_menu(),
        )
        return False

    # Приоритет у подписи, которую пользователь уже выбрал/сохранил вручную.
    if preferred_city_label:
        city_label = preferred_city_label
    elif city_fallback:
        city_label = city_fallback
    else:
        location = ctx.get_location_by_coordinates(lat, lon)
        city_label = ctx.build_location_label(location, show_coords=False) if location else "Выбранная локация"

    user_data = ctx.load_user(user_id)
    user_data["city"] = city_label
    user_data["lat"] = lat
    user_data["lon"] = lon
    ctx.save_user(user_id, user_data)

    answer = ctx.format_details_response(city_label, weather, air_components)
    session_store.user_states.pop(user_id, None)
    session_store.details_saved_drafts.pop(user_id, None)
    session_store.details_location_choices.pop(user_id, None)
    snapshot_id = session_store.generate_ai_snapshot_id(user_id)
    session_store.ai_details_snapshots[snapshot_id] = {
        "user_id": user_id,
        "city_label": city_label,
        "weather": weather,
        "air_components": air_components,
        "created_at": time.time(),
    }
    session_store.cleanup_ai_snapshots()
    ctx.bot.send_message(message.chat.id, answer, reply_markup=ctx.main_menu())
    ctx.bot.send_message(
        message.chat.id,
        "💡 Хочешь простое пояснение данных?",
        reply_markup=ctx.build_ai_action_keyboard(
            "💡 Пояснить данные",
            f"ai_details_explain:{snapshot_id}",
        ),
    )
    return True


def send_forecast_by_coordinates(
    message: types.Message,
    user_id: int,
    lat: float,
    lon: float,
    city_fallback: str,
    *,
    save_location: bool,
    preferred_city_label: str | None = None,
    ctx,
    session_store,
) -> bool:
    """Получает прогноз, сохраняет данные в кэш и показывает дни."""
    return run_send_forecast_by_coordinates(
        message,
        user_id,
        lat,
        lon,
        city_fallback,
        save_location=save_location,
        preferred_city_label=preferred_city_label,
        ctx=ctx,
        session_store=session_store,
        show_days_message=show_forecast_days_message,
    )


def send_tomorrow_forecast_by_coordinates(
    message: types.Message,
    user_id: int,
    lat: float,
    lon: float,
    city_fallback: str,
    *,
    save_location: bool,
    preferred_city_label: str | None = None,
    ctx,
    session_store,
) -> bool:
    """Получает 5-дневный прогноз и сразу показывает день завтрашнего прогноза."""
    return run_send_tomorrow_forecast_by_coordinates(
        message,
        user_id,
        lat,
        lon,
        city_fallback,
        save_location=save_location,
        preferred_city_label=preferred_city_label,
        ctx=ctx,
        session_store=session_store,
    )


def send_today_forecast_by_coordinates(
    message: types.Message,
    user_id: int,
    lat: float,
    lon: float,
    city_fallback: str,
    *,
    save_location: bool,
    preferred_city_label: str | None = None,
    ctx,
    session_store,
) -> bool:
    """Получает 5-дневный прогноз и сразу показывает сегодняшний локальный день."""
    return run_send_today_forecast_by_coordinates(
        message,
        user_id,
        lat,
        lon,
        city_fallback,
        save_location=save_location,
        preferred_city_label=preferred_city_label,
        ctx=ctx,
        session_store=session_store,
        remaining_day_detector=is_remaining_day_forecast,
    )


def send_source_compare_by_coordinates(
    message: types.Message,
    user_id: int,
    lat: float,
    lon: float,
    city_fallback: str,
    *,
    preferred_city_label: str | None = None,
    ctx,
    session_store,
) -> bool:
    """Сравнивает OpenWeather и Open-Meteo для выбранного режима source compare."""
    return run_send_source_compare_by_coordinates(
        message,
        user_id,
        lat,
        lon,
        city_fallback,
        preferred_city_label=preferred_city_label,
        ctx=ctx,
        session_store=session_store,
        current_sources_comparer=compare_current_sources,
        today_sources_comparer=compare_today_sources,
        tomorrow_sources_comparer=compare_tomorrow_sources,
        available_dates_getter=get_source_compare_available_dates,
    )


def send_source_compare_by_selected_date(
    message: types.Message,
    user_id: int,
    selected_day: str,
    *,
    ctx,
    session_store,
) -> bool:
    """Сравнивает источники на выбранную дату после шага выбора даты."""
    return run_send_source_compare_by_selected_date(
        message,
        user_id,
        selected_day,
        ctx=ctx,
        session_store=session_store,
        sources_by_date_comparer=compare_sources_by_date,
    )


def prepare_weather_history_by_coordinates(
    message: types.Message,
    user_id: int,
    lat: float,
    lon: float,
    city_fallback: str,
    *,
    preferred_city_label: str | None = None,
    ctx,
    session_store,
) -> bool:
    """Сохраняет выбранную локацию и переводит пользователя к нужной ветке истории."""
    return run_prepare_weather_history_by_coordinates(
        message,
        user_id,
        lat,
        lon,
        city_fallback,
        preferred_city_label=preferred_city_label,
        ctx=ctx,
        session_store=session_store,
    )


def send_weather_history_by_date(
    message: types.Message,
    user_id: int,
    target_date: date,
    *,
    send_confirmation: bool = True,
    ctx,
    session_store,
) -> bool:
    """Получает архивную погоду за выбранную дату и отправляет итоговую сводку."""
    return run_send_weather_history_by_date(
        message,
        user_id,
        target_date,
        send_confirmation=send_confirmation,
        ctx=ctx,
        session_store=session_store,
        history_getter=get_weather_history_by_date,
        delete_message=try_delete_message,
    )


def send_history_monthly_report(
    message: types.Message,
    user_id: int,
    *,
    send_year_confirmation: bool = True,
    ctx,
    session_store,
) -> bool:
    """Получает месячную архивную или климатическую справку и отправляет итоговую сводку."""
    return run_send_history_monthly_report(
        message,
        user_id,
        send_year_confirmation=send_year_confirmation,
        ctx=ctx,
        session_store=session_store,
        monthly_history_getter=get_monthly_history_for_month,
        monthly_normals_getter=get_monthly_climate_normals,
        delete_message=try_delete_message,
        monthly_formatter_default=format_history_monthly_climate_response,
    )


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
    run_complete_compare_two_locations(
        chat_id,
        user_id,
        lat_1,
        lon_1,
        city_label_1,
        lat_2,
        lon_2,
        city_label_2,
        ctx=ctx,
        session_store=session_store,
    )


def alerts_worker(*, ctx) -> None:
    """Фоновая проверка прогноза для уведомлений."""
    run_alerts_worker(ctx=ctx)
