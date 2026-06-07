from types import SimpleNamespace

from callbacks.constants import SAVEDLOC_CANCEL
from handlers.callbacks_locations import (
    handle_delete_location_pick_callback,
    handle_favorite_pick_callback,
    handle_rename_location_pick_callback,
    handle_saved_location_pick_callback,
)


class _Bot:
    def __init__(self):
        self.calls = []

    def send_message(self, *args, **kwargs):
        self.calls.append(("send_message", args, kwargs))

    def answer_callback_query(self, *args, **kwargs):
        self.calls.append(("answer_callback_query", args, kwargs))

    def edit_message_text(self, *args, **kwargs):
        self.calls.append(("edit_message_text", args, kwargs))


def _call(*, data: str, user_id: int = 1, chat_id: int = 100, message_id: int = 200):
    return SimpleNamespace(
        id="callback-id",
        data=data,
        from_user=SimpleNamespace(id=user_id),
        message=SimpleNamespace(chat=SimpleNamespace(id=chat_id), message_id=message_id),
    )


def _ctx(bot=None, **overrides):
    bot = bot or _Bot()
    base = {
        "bot": bot,
        "logger": SimpleNamespace(info=lambda *args, **kwargs: None),
        "load_user": lambda user_id: {"saved_locations": []},
        "save_user": lambda user_id, user_data: None,
        "locations_menu": lambda: "locations-menu",
        "saved_locations_management_menu": lambda: "saved-locations-menu",
        "format_saved_locations": lambda user_data: "formatted-saved-locations",
        "build_geocode_item_with_disambiguated_label": lambda locations, index: locations[index],
        "build_location_label": lambda item, show_coords=False: item.get("label"),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


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


def test_favorite_pick_success_updates_favorite_location_and_state():
    bot = _Bot()
    saved_users = []
    user_data = {"saved_locations": [{"id": "home", "title": "Дом"}]}
    ctx = _ctx(
        bot,
        load_user=lambda user_id: user_data,
        save_user=lambda user_id, data: saved_users.append((user_id, data["favorite_location_id"])),
    )
    session_store = _session_store(user_states={1: "old-state"})

    handle_favorite_pick_callback(
        _call(data="favorite_pick:home"),
        ctx=ctx,
        session_store=session_store,
        LOCATIONS_MENU="locations-menu-state",
    )

    assert saved_users == [(1, "home")]
    assert session_store.user_states[1] == "locations-menu-state"
    assert ("answer_callback_query", ("callback-id",), {}) in bot.calls
    assert bot.calls[-1] == (
        "send_message",
        (100, "✅ Основная локация обновлена.\n\nformatted-saved-locations"),
        {"reply_markup": "saved-locations-menu"},
    )


def test_favorite_pick_not_found_returns_friendly_message():
    bot = _Bot()
    ctx = _ctx(bot, load_user=lambda user_id: {"saved_locations": [{"id": "home", "title": "Дом"}]})
    session_store = _session_store()

    handle_favorite_pick_callback(
        _call(data="favorite_pick:missing"),
        ctx=ctx,
        session_store=session_store,
        LOCATIONS_MENU="locations-menu-state",
    )

    assert bot.calls[-1] == (
        "send_message",
        (100, "⚠️ Выбранная локация не найдена. Попробуй снова."),
        {"reply_markup": "locations-menu"},
    )


def test_delete_location_pick_success_removes_location():
    bot = _Bot()
    saved_users = []
    user_data = {
        "saved_locations": [
            {"id": "home", "title": "Дом"},
            {"id": "office", "title": "Офис"},
        ],
        "favorite_location_id": "office",
    }
    ctx = _ctx(
        bot,
        load_user=lambda user_id: user_data,
        save_user=lambda user_id, data: saved_users.append(data["saved_locations"]),
    )
    session_store = _session_store(user_states={1: "old-state"}, rename_location_drafts={1: {"location_id": "home"}})

    handle_delete_location_pick_callback(
        _call(data="delete_location_pick:home"),
        ctx=ctx,
        session_store=session_store,
        LOCATIONS_MENU="locations-menu-state",
    )

    assert saved_users == [[{"id": "office", "title": "Офис"}]]
    assert session_store.user_states[1] == "locations-menu-state"
    assert 1 not in session_store.rename_location_drafts
    assert bot.calls[-1] == (
        "send_message",
        (100, "✅ Локация удалена.\n\nformatted-saved-locations"),
        {"reply_markup": "saved-locations-menu"},
    )


def test_delete_location_pick_resets_favorite_when_favorite_is_deleted():
    bot = _Bot()
    saved_users = []
    user_data = {
        "saved_locations": [{"id": "home", "title": "Дом"}],
        "favorite_location_id": "home",
    }
    ctx = _ctx(
        bot,
        load_user=lambda user_id: user_data,
        save_user=lambda user_id, data: saved_users.append(data["favorite_location_id"]),
    )
    session_store = _session_store()

    handle_delete_location_pick_callback(
        _call(data="delete_location_pick:home"),
        ctx=ctx,
        session_store=session_store,
        LOCATIONS_MENU="locations-menu-state",
    )

    assert saved_users == [None]


def test_delete_location_pick_missing_target_returns_friendly_message():
    bot = _Bot()
    ctx = _ctx(bot, load_user=lambda user_id: {"saved_locations": [{"id": "home", "title": "Дом"}]})
    session_store = _session_store()

    handle_delete_location_pick_callback(
        _call(data="delete_location_pick:missing"),
        ctx=ctx,
        session_store=session_store,
        LOCATIONS_MENU="locations-menu-state",
    )

    assert bot.calls[-1] == (
        "send_message",
        (100, "⚠️ Выбранная локация не найдена."),
        {"reply_markup": "locations-menu"},
    )


def test_rename_location_pick_success_sets_waiting_state():
    bot = _Bot()
    ctx = _ctx(bot, load_user=lambda user_id: {"saved_locations": [{"id": "home", "title": "Дом"}]})
    session_store = _session_store(user_states={1: "old-state"})
    fake_types = SimpleNamespace(ReplyKeyboardRemove=lambda: "reply-remove")

    handle_rename_location_pick_callback(
        _call(data="rename_location_pick:home"),
        ctx=ctx,
        session_store=session_store,
        LOCATIONS_MENU="locations-menu-state",
        WAITING_RENAME_LOCATION_TITLE="waiting-rename-state",
        types=fake_types,
    )

    assert session_store.rename_location_drafts[1] == {"location_id": "home"}
    assert session_store.user_states[1] == "waiting-rename-state"
    assert bot.calls[-1] == (
        "send_message",
        (100, "Введи новое название для локации."),
        {"reply_markup": "reply-remove"},
    )


def test_rename_location_pick_stale_selection_returns_friendly_message():
    bot = _Bot()
    ctx = _ctx(bot, load_user=lambda user_id: {"saved_locations": [{"id": "home", "title": "Дом"}]})
    session_store = _session_store()
    fake_types = SimpleNamespace(ReplyKeyboardRemove=lambda: "reply-remove")

    handle_rename_location_pick_callback(
        _call(data="rename_location_pick:missing"),
        ctx=ctx,
        session_store=session_store,
        LOCATIONS_MENU="locations-menu-state",
        WAITING_RENAME_LOCATION_TITLE="waiting-rename-state",
        types=fake_types,
    )

    assert bot.calls[-1] == (
        "send_message",
        (100, "⚠️ Выбранная локация не найдена."),
        {"reply_markup": "locations-menu"},
    )


def test_saved_location_pick_cancel_clears_draft_and_returns_to_menu():
    bot = _Bot()
    ctx = _ctx(bot)
    session_store = _session_store(
        user_states={1: "old-state"},
        saved_location_drafts={1: {"locations": [{"label": "Москва"}]}},
    )
    fake_types = SimpleNamespace(ReplyKeyboardRemove=lambda: "reply-remove")

    handle_saved_location_pick_callback(
        _call(data=SAVEDLOC_CANCEL),
        ctx=ctx,
        session_store=session_store,
        LOCATIONS_MENU="locations-menu-state",
        types=fake_types,
    )

    assert 1 not in session_store.saved_location_drafts
    assert session_store.user_states[1] == "locations-menu-state"
    assert bot.calls[-1] == (
        "send_message",
        (100, "Выбор отменён."),
        {"reply_markup": "locations-menu"},
    )


def test_saved_location_pick_stale_list_returns_restart_message():
    bot = _Bot()
    ctx = _ctx(bot)
    session_store = _session_store(
        user_states={1: "old-state"},
        saved_location_drafts={1: {"locations": [{"label": "Москва", "lat": 55.75, "lon": 37.61}]}},
    )
    fake_types = SimpleNamespace(ReplyKeyboardRemove=lambda: "reply-remove")

    handle_saved_location_pick_callback(
        _call(data="savedloc_pick:5"),
        ctx=ctx,
        session_store=session_store,
        LOCATIONS_MENU="locations-menu-state",
        types=fake_types,
    )

    assert 1 not in session_store.saved_location_drafts
    assert session_store.user_states[1] == "locations-menu-state"
    assert bot.calls[-1] == (
        "send_message",
        (100, "⚠️ Список вариантов устарел. Начни добавление заново."),
        {"reply_markup": "locations-menu"},
    )
