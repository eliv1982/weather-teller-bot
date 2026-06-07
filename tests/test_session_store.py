"""
Unit tests for SessionStore (session_store.py).

Coverage:
- get_state / set_state / clear_state basics
- clear_location_choices removes all per-user choice dicts
- clear_saved_location_flows removes all saved-location draft dicts
- clear_all_user_runtime wipes all runtime state for a user
- generate_ai_snapshot_id returns unique strings
- cleanup_ai_snapshots: TTL expiry respects max_age_seconds
- clear_user_ai_snapshots removes only the target user's snapshots

Not covered here (follow-up tasks):
- Draft TTL for history_drafts, compare_drafts, ai_compare_drafts, etc.
  → Only AI snapshots have TTL today. All other drafts accumulate indefinitely
    until an explicit clear_*() call. See TestDraftTtlNotImplemented below.
"""

import time

import pytest

from session_store import SessionStore


# ---------------------------------------------------------------------------
# State basics
# ---------------------------------------------------------------------------


class TestSessionStateBasics:
    def test_get_state_returns_none_for_unknown_user(self):
        store = SessionStore()
        assert store.get_state(999) is None

    def test_set_and_get_state_roundtrip(self):
        store = SessionStore()
        store.set_state(1, "CURRENT_CITY_INPUT")
        assert store.get_state(1) == "CURRENT_CITY_INPUT"

    def test_set_state_overwrites_previous(self):
        store = SessionStore()
        store.set_state(1, "FIRST")
        store.set_state(1, "SECOND")
        assert store.get_state(1) == "SECOND"

    def test_clear_state_removes_user(self):
        store = SessionStore()
        store.set_state(1, "SOME_STATE")
        store.clear_state(1)
        assert store.get_state(1) is None

    def test_clear_state_is_idempotent_for_unknown_user(self):
        store = SessionStore()
        store.clear_state(999)  # must not raise
        assert store.get_state(999) is None

    def test_multiple_users_are_isolated(self):
        store = SessionStore()
        store.set_state(1, "STATE_A")
        store.set_state(2, "STATE_B")
        assert store.get_state(1) == "STATE_A"
        assert store.get_state(2) == "STATE_B"

        store.clear_state(1)
        assert store.get_state(1) is None
        assert store.get_state(2) == "STATE_B"


# ---------------------------------------------------------------------------
# Location choices clear
# ---------------------------------------------------------------------------


class TestClearLocationChoices:
    def test_removes_all_choice_dicts_for_user(self):
        store = SessionStore()
        uid = 42
        store.current_location_choices[uid] = [{"lat": 1}]
        store.alerts_location_choices[uid] = [{"lat": 2}]
        store.details_location_choices[uid] = [{"lat": 3}]
        store.forecast_location_choices[uid] = [{"lat": 4}]
        store.source_compare_location_choices[uid] = [{"lat": 5}]
        store.source_compare_drafts[uid] = {"mode": "current"}
        store.history_location_choices[uid] = [{"lat": 6}]
        store.history_drafts[uid] = {"section": "daily"}
        store.compare_location_choices[uid] = {"step": 1}
        store.ai_compare_location_choices[uid] = [{"lat": 7}]

        store.clear_location_choices(uid)

        assert uid not in store.current_location_choices
        assert uid not in store.alerts_location_choices
        assert uid not in store.details_location_choices
        assert uid not in store.forecast_location_choices
        assert uid not in store.source_compare_location_choices
        assert uid not in store.source_compare_drafts
        assert uid not in store.history_location_choices
        assert uid not in store.history_drafts
        assert uid not in store.compare_location_choices
        assert uid not in store.ai_compare_location_choices

    def test_does_not_affect_other_users(self):
        store = SessionStore()
        store.current_location_choices[1] = [{"lat": 1}]
        store.current_location_choices[2] = [{"lat": 2}]

        store.clear_location_choices(1)

        assert 1 not in store.current_location_choices
        assert 2 in store.current_location_choices

    def test_is_idempotent_for_user_without_choices(self):
        store = SessionStore()
        store.clear_location_choices(999)  # must not raise


# ---------------------------------------------------------------------------
# Saved location flows clear
# ---------------------------------------------------------------------------


class TestClearSavedLocationFlows:
    def test_removes_all_draft_dicts(self):
        store = SessionStore()
        uid = 7
        store.saved_location_drafts[uid] = {"title": "Home"}
        store.rename_location_drafts[uid] = {"new_title": "Office"}
        store.alerts_subscription_drafts[uid] = {"location_id": "abc"}
        store.ai_compare_drafts[uid] = {"step": 1}

        store.clear_saved_location_flows(uid)

        assert uid not in store.saved_location_drafts
        assert uid not in store.rename_location_drafts
        assert uid not in store.alerts_subscription_drafts
        assert uid not in store.ai_compare_drafts

    def test_does_not_affect_other_users(self):
        store = SessionStore()
        store.saved_location_drafts[1] = {"title": "A"}
        store.saved_location_drafts[2] = {"title": "B"}

        store.clear_saved_location_flows(1)

        assert 1 not in store.saved_location_drafts
        assert 2 in store.saved_location_drafts


# ---------------------------------------------------------------------------
# Full runtime clear
# ---------------------------------------------------------------------------


class TestClearAllUserRuntime:
    def test_removes_state_and_all_known_draft_dicts(self):
        store = SessionStore()
        uid = 55
        store.set_state(uid, "SOME_STATE")
        store.compare_drafts[uid] = {"city1": "Paris"}
        store.current_favorite_drafts[uid] = {"fav": "loc1"}
        store.details_favorite_drafts[uid] = {"fav": "loc1"}
        store.forecast_favorite_drafts[uid] = {"fav": "loc1"}
        store.details_saved_drafts[uid] = {"loc": "Moscow"}
        store.forecast_saved_drafts[uid] = {"loc": "Moscow"}
        store.forecast_cache[uid] = {"data": "..."}
        store.current_location_choices[uid] = [{"lat": 1}]
        store.saved_location_drafts[uid] = {"title": "Home"}

        store.clear_all_user_runtime(uid)

        assert store.get_state(uid) is None
        assert uid not in store.compare_drafts
        assert uid not in store.current_favorite_drafts
        assert uid not in store.details_favorite_drafts
        assert uid not in store.forecast_favorite_drafts
        assert uid not in store.details_saved_drafts
        assert uid not in store.forecast_saved_drafts
        assert uid not in store.forecast_cache
        assert uid not in store.current_location_choices
        assert uid not in store.saved_location_drafts

    def test_does_not_affect_other_users(self):
        store = SessionStore()
        store.set_state(1, "STATE_1")
        store.set_state(2, "STATE_2")
        store.compare_drafts[1] = {"a": 1}
        store.compare_drafts[2] = {"b": 2}

        store.clear_all_user_runtime(1)

        assert store.get_state(2) == "STATE_2"
        assert 2 in store.compare_drafts


# ---------------------------------------------------------------------------
# AI snapshot ID generation
# ---------------------------------------------------------------------------


class TestGenerateAiSnapshotId:
    def test_returns_non_empty_string(self):
        store = SessionStore()
        snap_id = store.generate_ai_snapshot_id(user_id=123)
        assert isinstance(snap_id, str)
        assert len(snap_id) > 0

    def test_ids_are_unique_across_calls(self):
        store = SessionStore()
        ids = {store.generate_ai_snapshot_id(user_id=1) for _ in range(100)}
        assert len(ids) == 100

    def test_different_users_produce_different_ids(self):
        store = SessionStore()
        id_u1 = store.generate_ai_snapshot_id(user_id=1)
        id_u2 = store.generate_ai_snapshot_id(user_id=2)
        assert id_u1 != id_u2


# ---------------------------------------------------------------------------
# AI snapshot TTL cleanup
# ---------------------------------------------------------------------------


class TestCleanupAiSnapshots:
    def test_removes_stale_snapshots_beyond_default_6h_ttl(self):
        store = SessionStore()
        old_ts = time.time() - 7 * 3600   # 7 h ago — older than 6 h TTL
        recent_ts = time.time() - 1800    # 30 min ago — should be kept

        store.ai_current_snapshots["old"] = {"created_at": old_ts, "user_id": 1}
        store.ai_current_snapshots["recent"] = {"created_at": recent_ts, "user_id": 1}

        store.cleanup_ai_snapshots()

        assert "old" not in store.ai_current_snapshots
        assert "recent" in store.ai_current_snapshots

    def test_custom_max_age_is_respected(self):
        store = SessionStore()
        ts_2h_ago = time.time() - 2 * 3600

        store.ai_current_snapshots["snap"] = {"created_at": ts_2h_ago, "user_id": 1}

        # 1 h threshold → 2 h old snap should be removed
        store.cleanup_ai_snapshots(max_age_seconds=1 * 3600)
        assert "snap" not in store.ai_current_snapshots

        # 3 h threshold → same snap should be kept
        store.ai_current_snapshots["snap"] = {"created_at": ts_2h_ago, "user_id": 1}
        store.cleanup_ai_snapshots(max_age_seconds=3 * 3600)
        assert "snap" in store.ai_current_snapshots

    def test_cleans_both_current_and_details_snapshot_dicts(self):
        store = SessionStore()
        old_ts = time.time() - 7 * 3600

        store.ai_current_snapshots["cur_old"] = {"created_at": old_ts, "user_id": 1}
        store.ai_details_snapshots["det_old"] = {"created_at": old_ts, "user_id": 1}

        store.cleanup_ai_snapshots()

        assert "cur_old" not in store.ai_current_snapshots
        assert "det_old" not in store.ai_details_snapshots

    def test_skips_entries_without_created_at(self):
        store = SessionStore()
        store.ai_current_snapshots["no_ts"] = {"user_id": 1}  # no created_at key

        store.cleanup_ai_snapshots()

        assert "no_ts" in store.ai_current_snapshots  # must NOT be evicted

    def test_skips_entries_with_non_numeric_created_at(self):
        store = SessionStore()
        store.ai_current_snapshots["bad_ts"] = {"created_at": "yesterday", "user_id": 1}

        store.cleanup_ai_snapshots()

        assert "bad_ts" in store.ai_current_snapshots  # must NOT be evicted

    def test_clear_user_ai_snapshots_removes_only_target_user(self):
        store = SessionStore()
        store.ai_current_snapshots["snap_u1"] = {"created_at": time.time(), "user_id": 1}
        store.ai_current_snapshots["snap_u2"] = {"created_at": time.time(), "user_id": 2}
        store.ai_details_snapshots["dsnap_u1"] = {"created_at": time.time(), "user_id": 1}

        store.clear_user_ai_snapshots(user_id=1)

        assert "snap_u1" not in store.ai_current_snapshots
        assert "snap_u2" in store.ai_current_snapshots
        assert "dsnap_u1" not in store.ai_details_snapshots

    def test_clear_user_ai_snapshots_is_safe_for_user_with_no_snapshots(self):
        store = SessionStore()
        store.clear_user_ai_snapshots(user_id=999)  # must not raise


# ---------------------------------------------------------------------------
# Draft TTL — documented absence (xfail reminder)
# ---------------------------------------------------------------------------


class TestDraftTtlNotImplemented:
    """
    Documents that draft TTL for non-AI drafts is NOT yet implemented.

    SessionStore today only expires ai_current_snapshots and ai_details_snapshots
    via cleanup_ai_snapshots(). All other draft dicts (history_drafts,
    compare_drafts, ai_compare_drafts, forecast_saved_drafts, etc.) accumulate
    indefinitely until an explicit clear_*() call.

    Follow-up task: add cleanup_stale_drafts() with configurable TTL — low risk,
    isolated change, no impact on existing state routing.
    """

    @pytest.mark.xfail(
        reason="Draft TTL not yet implemented — follow-up task",
        strict=False,
    )
    def test_session_store_has_cleanup_stale_drafts_method(self):
        store = SessionStore()
        assert hasattr(store, "cleanup_stale_drafts"), (
            "SessionStore должен иметь метод cleanup_stale_drafts() "
            "для очистки устаревших черновиков по TTL"
        )
