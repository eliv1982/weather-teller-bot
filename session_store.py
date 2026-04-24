import time
import uuid


class SessionStore:
    """Хранит runtime-состояние пользователей в памяти процесса."""

    def __init__(self) -> None:
        self.user_states: dict[int, str] = {}
        self.compare_drafts: dict[int, dict] = {}
        self.current_favorite_drafts: dict[int, dict] = {}
        self.details_favorite_drafts: dict[int, dict] = {}
        self.forecast_favorite_drafts: dict[int, dict] = {}
        self.details_saved_drafts: dict[int, dict] = {}
        self.forecast_saved_drafts: dict[int, dict] = {}
        self.forecast_cache: dict[int, dict] = {}
        self.ai_current_snapshots: dict[str, dict] = {}
        self.ai_details_snapshots: dict[str, dict] = {}
        self.current_location_choices: dict[int, list] = {}
        self.alerts_location_choices: dict[int, list] = {}
        self.details_location_choices: dict[int, list] = {}
        self.forecast_location_choices: dict[int, list] = {}
        self.compare_location_choices: dict[int, dict] = {}
        self.ai_compare_location_choices: dict[int, list] = {}
        self.saved_location_drafts: dict[int, dict] = {}
        self.rename_location_drafts: dict[int, dict] = {}
        self.alerts_subscription_drafts: dict[int, dict] = {}
        self.ai_compare_drafts: dict[int, dict] = {}

    def get_state(self, user_id: int) -> str | None:
        """Возвращает текущее состояние пользователя."""
        return self.user_states.get(user_id)

    def set_state(self, user_id: int, state: str) -> None:
        """Устанавливает состояние пользователя."""
        self.user_states[user_id] = state

    def clear_state(self, user_id: int) -> None:
        """Очищает состояние пользователя."""
        self.user_states.pop(user_id, None)

    def clear_location_choices(self, user_id: int) -> None:
        """Очищает временные списки выбора локаций для пользователя."""
        self.current_location_choices.pop(user_id, None)
        self.alerts_location_choices.pop(user_id, None)
        self.details_location_choices.pop(user_id, None)
        self.forecast_location_choices.pop(user_id, None)
        self.compare_location_choices.pop(user_id, None)
        self.ai_compare_location_choices.pop(user_id, None)

    def clear_saved_location_flows(self, user_id: int) -> None:
        """Очищает черновики сценариев раздела «Мои локации»."""
        self.saved_location_drafts.pop(user_id, None)
        self.rename_location_drafts.pop(user_id, None)
        self.alerts_subscription_drafts.pop(user_id, None)
        self.ai_compare_drafts.pop(user_id, None)

    def generate_ai_snapshot_id(self, user_id: int) -> str:
        """Генерирует короткий уникальный snapshot_id для AI-кнопок."""
        return f"{user_id:x}{uuid.uuid4().hex[:10]}"

    def cleanup_ai_snapshots(self, *, max_age_seconds: int = 6 * 60 * 60) -> None:
        """Удаляет устаревшие AI-снапшоты из памяти процесса."""
        now = time.time()
        for storage in (self.ai_current_snapshots, self.ai_details_snapshots):
            stale_ids = [
                snapshot_id
                for snapshot_id, payload in storage.items()
                if isinstance(payload, dict)
                and isinstance(payload.get("created_at"), (int, float))
                and now - float(payload["created_at"]) > max_age_seconds
            ]
            for snapshot_id in stale_ids:
                storage.pop(snapshot_id, None)

    def clear_user_ai_snapshots(self, user_id: int) -> None:
        """Очищает все AI-снапшоты конкретного пользователя."""
        for storage in (self.ai_current_snapshots, self.ai_details_snapshots):
            snapshot_ids = [
                snapshot_id
                for snapshot_id, payload in storage.items()
                if isinstance(payload, dict) and payload.get("user_id") == user_id
            ]
            for snapshot_id in snapshot_ids:
                storage.pop(snapshot_id, None)

    def clear_all_user_runtime(self, user_id: int) -> None:
        """Очищает всё runtime-состояние пользователя."""
        self.clear_state(user_id)
        self.compare_drafts.pop(user_id, None)
        self.current_favorite_drafts.pop(user_id, None)
        self.details_favorite_drafts.pop(user_id, None)
        self.forecast_favorite_drafts.pop(user_id, None)
        self.details_saved_drafts.pop(user_id, None)
        self.forecast_saved_drafts.pop(user_id, None)
        self.forecast_cache.pop(user_id, None)
        self.clear_user_ai_snapshots(user_id)
        self.clear_location_choices(user_id)
        self.clear_saved_location_flows(user_id)
