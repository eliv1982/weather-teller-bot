from types import SimpleNamespace

import pytest

from handlers.locations import handle_locations_text
from handlers.states import (
    LOCATIONS_MENU,
    WAITING_LOCATION_TITLE,
    WAITING_NEW_SAVED_LOCATION_COORDS,
    WAITING_NEW_SAVED_LOCATION_COORDS_UNRESOLVED,
    WAITING_NEW_SAVED_LOCATION_MENU,
    WAITING_NEW_SAVED_LOCATION_TITLE,
    WAITING_RENAME_LOCATION_TITLE,
)


class _Bot:
    def __init__(self):
        self.calls = []

    def send_message(self, *args, **kwargs):
        self.calls.append(("send_message", args, kwargs))


def _message(*, text: str, chat_id: int = 100):
    return SimpleNamespace(text=text, chat=SimpleNamespace(id=chat_id))


def _session_store(**overrides):
    base = {
        "user_states": {},
        "saved_location_drafts": {},
        "rename_location_drafts": {},
        "ai_compare_drafts": {},
        "ai_compare_location_choices": {},
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _ctx(bot=None, **overrides):
    bot = bot or _Bot()
    base = {
        "bot": bot,
        "logger": SimpleNamespace(info=lambda *args, **kwargs: None),
        "load_user": lambda user_id: {},
        "save_user": lambda user_id, user_data: None,
        "save_saved_location_item": lambda **kwargs: {"status": "added"},
        "locations_menu": lambda: "locations-menu",
        "saved_locations_management_menu": lambda: "saved-locations-menu",
        "add_saved_location_menu": lambda: "add-saved-menu",
        "format_saved_locations": lambda user_data: "formatted-saved-locations",
        "geo_request_menu": lambda: "geo-request-menu",
        "get_location_by_coordinates": lambda lat, lon: None,
        "build_location_label": lambda item, show_coords=False: item.get("label"),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_waiting_location_title_success_saves_current_location():
    bot = _Bot()
    save_calls = []
    user_data = {"city": "Москва", "lat": 55.75, "lon": 37.61}
    ctx = _ctx(
        bot,
        load_user=lambda user_id: user_data,
        save_saved_location_item=lambda **kwargs: save_calls.append(kwargs) or {"status": "added"},
    )
    session_store = _session_store(user_states={7: WAITING_LOCATION_TITLE})

    handled = handle_locations_text(
        _message(text="Дом"),
        7,
        WAITING_LOCATION_TITLE,
        ctx=ctx,
        session_store=session_store,
    )

    assert handled is True
    assert save_calls == [
        {
            "user_id": 7,
            "title": "Дом",
            "label": "Москва",
            "lat": 55.75,
            "lon": 37.61,
        }
    ]
    assert session_store.user_states[7] == LOCATIONS_MENU
    assert bot.calls[0] == (
        "send_message",
        (100, "✅ Локация сохранена."),
        {"reply_markup": "saved-locations-menu"},
    )
    assert bot.calls[1] == (
        "send_message",
        (100, "formatted-saved-locations"),
        {"reply_markup": "saved-locations-menu"},
    )


def test_waiting_location_title_duplicate_title_keeps_prompt_state():
    bot = _Bot()
    ctx = _ctx(
        bot,
        load_user=lambda user_id: {"city": "Москва", "lat": 55.75, "lon": 37.61},
        save_saved_location_item=lambda **kwargs: {"status": "duplicate_title"},
    )
    session_store = _session_store(user_states={7: WAITING_LOCATION_TITLE})

    handled = handle_locations_text(
        _message(text="Дом"),
        7,
        WAITING_LOCATION_TITLE,
        ctx=ctx,
        session_store=session_store,
    )

    assert handled is True
    assert session_store.user_states[7] == WAITING_LOCATION_TITLE
    assert bot.calls[-1][1][1] == "Локация с названием «Дом» уже есть. Введи другое название."


def test_waiting_location_title_duplicate_location_returns_to_locations_menu():
    bot = _Bot()
    ctx = _ctx(
        bot,
        load_user=lambda user_id: {"city": "Москва", "lat": 55.75, "lon": 37.61},
        save_saved_location_item=lambda **kwargs: {
            "status": "duplicate_location",
            "item": {"title": "Дом", "label": "Москва", "lat": 55.75, "lon": 37.61},
        },
    )
    session_store = _session_store(user_states={7: WAITING_LOCATION_TITLE})

    handled = handle_locations_text(
        _message(text="Дом"),
        7,
        WAITING_LOCATION_TITLE,
        ctx=ctx,
        session_store=session_store,
    )

    assert handled is True
    assert session_store.user_states[7] == LOCATIONS_MENU
    assert "Эта локация уже есть в сохранённых:" in bot.calls[-1][1][1]
    assert "Дубль не добавляю." in bot.calls[-1][1][1]


def test_waiting_location_title_missing_current_location_returns_to_locations_menu():
    bot = _Bot()
    ctx = _ctx(bot, load_user=lambda user_id: {"city": None, "lat": None, "lon": None})
    session_store = _session_store(user_states={7: WAITING_LOCATION_TITLE})

    handled = handle_locations_text(
        _message(text="Дом"),
        7,
        WAITING_LOCATION_TITLE,
        ctx=ctx,
        session_store=session_store,
    )

    assert handled is True
    assert session_store.user_states[7] == LOCATIONS_MENU
    assert bot.calls[-1] == (
        "send_message",
        (100, "Сначала нужно получить погоду или выбрать локацию."),
        {"reply_markup": "locations-menu"},
    )


def test_waiting_new_saved_location_title_stale_draft_returns_to_locations_menu():
    bot = _Bot()
    ctx = _ctx(bot)
    session_store = _session_store(user_states={3: WAITING_NEW_SAVED_LOCATION_TITLE})

    handled = handle_locations_text(
        _message(text="Дом"),
        3,
        WAITING_NEW_SAVED_LOCATION_TITLE,
        ctx=ctx,
        session_store=session_store,
    )

    assert handled is True
    assert session_store.user_states[3] == LOCATIONS_MENU
    assert bot.calls[-1] == (
        "send_message",
        (100, "⚠️ Данные локации устарели. Начни добавление заново."),
        {"reply_markup": "locations-menu"},
    )


def test_waiting_new_saved_location_title_success_clears_draft_and_saves():
    bot = _Bot()
    save_calls = []
    ctx = _ctx(
        bot,
        load_user=lambda user_id: {"saved_locations": [{"id": "loc-1"}]},
        save_saved_location_item=lambda **kwargs: save_calls.append(kwargs) or {"status": "added"},
    )
    session_store = _session_store(
        user_states={3: WAITING_NEW_SAVED_LOCATION_TITLE},
        saved_location_drafts={3: {"lat": 55.75, "lon": 37.61, "label": "Москва"}},
    )

    handled = handle_locations_text(
        _message(text="Дом"),
        3,
        WAITING_NEW_SAVED_LOCATION_TITLE,
        ctx=ctx,
        session_store=session_store,
    )

    assert handled is True
    assert save_calls == [
        {
            "user_id": 3,
            "title": "Дом",
            "label": "Москва",
            "lat": 55.75,
            "lon": 37.61,
        }
    ]
    assert 3 not in session_store.saved_location_drafts
    assert session_store.user_states[3] == LOCATIONS_MENU
    assert bot.calls[0] == (
        "send_message",
        (100, "✅ Локация сохранена."),
        {"reply_markup": "saved-locations-menu"},
    )
    assert bot.calls[1] == (
        "send_message",
        (100, "formatted-saved-locations"),
        {"reply_markup": "saved-locations-menu"},
    )


def test_waiting_new_saved_location_title_duplicate_title_keeps_draft():
    bot = _Bot()
    ctx = _ctx(
        bot,
        save_saved_location_item=lambda **kwargs: {"status": "duplicate_title"},
    )
    session_store = _session_store(
        user_states={3: WAITING_NEW_SAVED_LOCATION_TITLE},
        saved_location_drafts={3: {"lat": 55.75, "lon": 37.61, "label": "Москва"}},
    )

    handled = handle_locations_text(
        _message(text="Дом"),
        3,
        WAITING_NEW_SAVED_LOCATION_TITLE,
        ctx=ctx,
        session_store=session_store,
    )

    assert handled is True
    assert session_store.user_states[3] == WAITING_NEW_SAVED_LOCATION_TITLE
    assert session_store.saved_location_drafts[3]["label"] == "Москва"
    assert bot.calls[-1][1][1] == "Локация с названием «Дом» уже есть. Введи другое название."


def test_waiting_new_saved_location_title_duplicate_location_clears_draft():
    bot = _Bot()
    ctx = _ctx(
        bot,
        save_saved_location_item=lambda **kwargs: {
            "status": "duplicate_location",
            "item": {"title": "Дом", "label": "Москва", "lat": 55.75, "lon": 37.61},
        },
    )
    session_store = _session_store(
        user_states={3: WAITING_NEW_SAVED_LOCATION_TITLE},
        saved_location_drafts={3: {"lat": 55.75, "lon": 37.61, "label": "Москва"}},
    )

    handled = handle_locations_text(
        _message(text="Дом"),
        3,
        WAITING_NEW_SAVED_LOCATION_TITLE,
        ctx=ctx,
        session_store=session_store,
    )

    assert handled is True
    assert 3 not in session_store.saved_location_drafts
    assert session_store.user_states[3] == LOCATIONS_MENU
    assert "Эта локация уже есть в сохранённых:" in bot.calls[-1][1][1]
    assert "Дубль не добавляю." in bot.calls[-1][1][1]


def test_waiting_rename_location_title_stale_draft_returns_to_locations_menu():
    bot = _Bot()
    ctx = _ctx(bot)
    session_store = _session_store(user_states={9: WAITING_RENAME_LOCATION_TITLE})

    handled = handle_locations_text(
        _message(text="Офис"),
        9,
        WAITING_RENAME_LOCATION_TITLE,
        ctx=ctx,
        session_store=session_store,
    )

    assert handled is True
    assert session_store.user_states[9] == LOCATIONS_MENU
    assert bot.calls[-1] == (
        "send_message",
        (100, "⚠️ Данные для переименования устарели. Попробуй снова."),
        {"reply_markup": "locations-menu"},
    )


def test_waiting_rename_location_title_missing_target_returns_to_locations_menu():
    bot = _Bot()
    ctx = _ctx(bot, load_user=lambda user_id: {"saved_locations": [{"id": "other", "title": "Дом"}]})
    session_store = _session_store(
        user_states={9: WAITING_RENAME_LOCATION_TITLE},
        rename_location_drafts={9: {"location_id": "missing"}},
    )

    handled = handle_locations_text(
        _message(text="Офис"),
        9,
        WAITING_RENAME_LOCATION_TITLE,
        ctx=ctx,
        session_store=session_store,
    )

    assert handled is True
    assert 9 not in session_store.rename_location_drafts
    assert session_store.user_states[9] == LOCATIONS_MENU
    assert bot.calls[-1] == (
        "send_message",
        (100, "⚠️ Выбранная локация не найдена."),
        {"reply_markup": "locations-menu"},
    )


def test_waiting_rename_location_title_success_updates_title_and_clears_draft():
    bot = _Bot()
    saved_users = []
    user_data = {"saved_locations": [{"id": "home", "title": "Дом", "label": "Москва"}]}
    ctx = _ctx(
        bot,
        load_user=lambda user_id: user_data,
        save_user=lambda user_id, data: saved_users.append((user_id, data["saved_locations"][0]["title"])),
    )
    session_store = _session_store(
        user_states={9: WAITING_RENAME_LOCATION_TITLE},
        rename_location_drafts={9: {"location_id": "home"}},
    )

    handled = handle_locations_text(
        _message(text="Офис"),
        9,
        WAITING_RENAME_LOCATION_TITLE,
        ctx=ctx,
        session_store=session_store,
    )

    assert handled is True
    assert saved_users == [(9, "Офис")]
    assert 9 not in session_store.rename_location_drafts
    assert session_store.user_states[9] == LOCATIONS_MENU
    assert bot.calls[0] == (
        "send_message",
        (100, "✅ Локация переименована."),
        {"reply_markup": "saved-locations-menu"},
    )
    assert bot.calls[1] == (
        "send_message",
        (100, "formatted-saved-locations"),
        {"reply_markup": "saved-locations-menu"},
    )


def test_waiting_new_saved_location_coords_unresolved_save_as_point_uses_candidate_helper(monkeypatch):
    bot = _Bot()
    captured = []

    monkeypatch.setitem(
        handle_locations_text.__globals__,
        "_set_new_saved_location_candidate",
        lambda message, user_id, *, lat, lon, label, ctx, session_store: captured.append(
            (message.text, user_id, lat, lon, label, ctx.add_saved_location_menu(), session_store.user_states[5])
        )
        or True,
    )
    ctx = _ctx(bot)
    session_store = _session_store(
        user_states={5: WAITING_NEW_SAVED_LOCATION_COORDS_UNRESOLVED},
        saved_location_drafts={5: {"lat": 12.34, "lon": 56.78, "label": "Координаты: 12.3400, 56.7800"}},
    )

    handled = handle_locations_text(
        _message(text="💾 Сохранить как точку"),
        5,
        WAITING_NEW_SAVED_LOCATION_COORDS_UNRESOLVED,
        ctx=ctx,
        session_store=session_store,
    )

    assert handled is True
    assert captured == [
        (
            "💾 Сохранить как точку",
            5,
            12.34,
            56.78,
            "Координаты: 12.3400, 56.7800",
            "add-saved-menu",
            WAITING_NEW_SAVED_LOCATION_COORDS_UNRESOLVED,
        )
    ]


@pytest.mark.parametrize(
    ("choice", "expected_state", "expected_text"),
    [
        ("🧭 Ввести координаты заново", WAITING_NEW_SAVED_LOCATION_COORDS, "Введи координаты в формате: 55.5789, 37.9051"),
        (
            "🏙 Ввести населённый пункт",
            WAITING_NEW_SAVED_LOCATION_MENU,
            "Введи название населённого пункта или выбери другой способ ниже:",
        ),
    ],
)
def test_waiting_new_saved_location_coords_unresolved_supported_menu_choices(choice, expected_state, expected_text):
    bot = _Bot()
    ctx = _ctx(bot)
    session_store = _session_store(
        user_states={5: WAITING_NEW_SAVED_LOCATION_COORDS_UNRESOLVED},
        saved_location_drafts={5: {"lat": 12.34, "lon": 56.78, "label": "Координаты: 12.3400, 56.7800"}},
    )

    handled = handle_locations_text(
        _message(text=choice),
        5,
        WAITING_NEW_SAVED_LOCATION_COORDS_UNRESOLVED,
        ctx=ctx,
        session_store=session_store,
    )

    assert handled is True
    assert session_store.user_states[5] == expected_state
    assert bot.calls[-1][1][1] == expected_text


def test_waiting_new_saved_location_coords_unresolved_invalid_choice_repeats_menu():
    bot = _Bot()
    ctx = _ctx(bot)
    session_store = _session_store(
        user_states={5: WAITING_NEW_SAVED_LOCATION_COORDS_UNRESOLVED},
        saved_location_drafts={5: {"lat": 12.34, "lon": 56.78, "label": "Координаты: 12.3400, 56.7800"}},
    )

    handled = handle_locations_text(
        _message(text="что-то другое"),
        5,
        WAITING_NEW_SAVED_LOCATION_COORDS_UNRESOLVED,
        ctx=ctx,
        session_store=session_store,
    )

    assert handled is True
    assert session_store.user_states[5] == WAITING_NEW_SAVED_LOCATION_COORDS_UNRESOLVED
    assert bot.calls[-1][1][1] == "Выбери действие кнопкой ниже."
