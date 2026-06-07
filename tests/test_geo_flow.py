from types import SimpleNamespace

from callbacks.constants import AI_CURRENT_EXPLAIN_PREFIX
from handlers.geo_flow import handle_geo_current_weather


class _Bot:
    def __init__(self):
        self.messages = []

    def send_message(self, chat_id, text, reply_markup=None):
        self.messages.append(
            {
                "chat_id": chat_id,
                "text": text,
                "reply_markup": reply_markup,
            }
        )


def test_handle_geo_current_weather_sends_current_weather_and_ai_prompt():
    bot = _Bot()
    saved_user_data = {}
    cleared_user_ids = []
    cleanup_calls = []
    ctx = SimpleNamespace(
        bot=bot,
        logger=SimpleNamespace(info=lambda *args, **kwargs: None, warning=lambda *args, **kwargs: None),
        get_current_weather=lambda lat, lon: {"temp": 22},
        get_location_by_coordinates=lambda lat, lon: {"name": "Москва"},
        build_location_label=lambda location, show_coords=False: "Москва",
        load_user=lambda user_id: {},
        save_user=lambda user_id, user_data: saved_user_data.update({user_id: dict(user_data)}),
        format_weather_response=lambda city_label, weather: f"weather:{city_label}:{weather['temp']}",
        main_menu=lambda: "main-menu",
        build_ai_action_keyboard=lambda text, callback_data: {
            "text": text,
            "callback_data": callback_data,
        },
    )
    session_store = SimpleNamespace(
        clear_location_choices=lambda user_id: cleared_user_ids.append(user_id),
        user_states={7: "waiting_current_weather_geo"},
        ai_current_snapshots={},
        generate_ai_snapshot_id=lambda user_id: "snap-1",
        cleanup_ai_snapshots=lambda: cleanup_calls.append(True),
    )
    message = SimpleNamespace(
        chat=SimpleNamespace(id=123),
        location=SimpleNamespace(latitude=55.75, longitude=37.61),
    )

    handle_geo_current_weather(
        message,
        7,
        ctx=ctx,
        session_store=session_store,
        ai_current_explain_prefix=AI_CURRENT_EXPLAIN_PREFIX,
        received_log_message="Получена геолокация от пользователя %s: lat=%s, lon=%s.",
    )

    assert cleared_user_ids == [7]
    assert 7 not in session_store.user_states
    assert saved_user_data[7] == {
        "city": "Москва",
        "lat": 55.75,
        "lon": 37.61,
    }
    assert cleanup_calls == [True]
    assert session_store.ai_current_snapshots["snap-1"]["user_id"] == 7
    assert session_store.ai_current_snapshots["snap-1"]["city_label"] == "Москва"
    assert session_store.ai_current_snapshots["snap-1"]["weather"] == {"temp": 22}
    assert isinstance(session_store.ai_current_snapshots["snap-1"]["created_at"], float)
    assert bot.messages == [
        {
            "chat_id": 123,
            "text": "weather:Москва:22",
            "reply_markup": "main-menu",
        },
        {
            "chat_id": 123,
            "text": "✨ Хочешь короткое пояснение погоды?",
            "reply_markup": {
                "text": "✨ Короткое пояснение погоды",
                "callback_data": "ai_current_explain:snap-1",
            },
        },
    ]


def test_handle_geo_current_weather_handles_weather_fetch_failure():
    bot = _Bot()
    cleared_user_ids = []
    ctx = SimpleNamespace(
        bot=bot,
        logger=SimpleNamespace(info=lambda *args, **kwargs: None, warning=lambda *args, **kwargs: None),
        get_current_weather=lambda lat, lon: None,
        get_location_by_coordinates=lambda lat, lon: (_ for _ in ()).throw(AssertionError("must not be called")),
        build_location_label=lambda location, show_coords=False: "unused",
        load_user=lambda user_id: (_ for _ in ()).throw(AssertionError("must not be called")),
        save_user=lambda user_id, user_data: (_ for _ in ()).throw(AssertionError("must not be called")),
        format_weather_response=lambda city_label, weather: "unused",
        main_menu=lambda: "main-menu",
        build_ai_action_keyboard=lambda text, callback_data: "unused",
    )
    session_store = SimpleNamespace(
        clear_location_choices=lambda user_id: cleared_user_ids.append(user_id),
        user_states={7: "waiting_current_weather_geo"},
        ai_current_snapshots={},
        generate_ai_snapshot_id=lambda user_id: "snap-1",
        cleanup_ai_snapshots=lambda: (_ for _ in ()).throw(AssertionError("must not be called")),
    )
    message = SimpleNamespace(
        chat=SimpleNamespace(id=123),
        location=SimpleNamespace(latitude=55.75, longitude=37.61),
    )

    handle_geo_current_weather(
        message,
        7,
        ctx=ctx,
        session_store=session_store,
        ai_current_explain_prefix=AI_CURRENT_EXPLAIN_PREFIX,
        received_log_message="Получена геолокация от пользователя %s вне сценария: lat=%s, lon=%s.",
    )

    assert cleared_user_ids == [7]
    assert 7 not in session_store.user_states
    assert session_store.ai_current_snapshots == {}
    assert bot.messages == [
        {
            "chat_id": 123,
            "text": "Не удалось получить данные о погоде по геолокации. Попробуй позже.",
            "reply_markup": "main-menu",
        }
    ]
