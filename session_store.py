class SessionStore:
    """Хранит runtime-состояние пользователей в памяти процесса."""

    def __init__(self) -> None:
        self.user_states: dict[int, str] = {}
        self.compare_drafts: dict[int, dict] = {}
        self.details_saved_drafts: dict[int, dict] = {}
        self.forecast_saved_drafts: dict[int, dict] = {}
        self.forecast_cache: dict[int, dict] = {}
        self.current_location_choices: dict[int, list] = {}
        self.alerts_location_choices: dict[int, list] = {}
        self.details_location_choices: dict[int, list] = {}
        self.forecast_location_choices: dict[int, list] = {}
        self.compare_location_choices: dict[int, dict] = {}
        self.saved_location_drafts: dict[int, dict] = {}
        self.rename_location_drafts: dict[int, dict] = {}

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

    def clear_saved_location_flows(self, user_id: int) -> None:
        """Очищает черновики сценариев раздела «Мои локации»."""
        self.saved_location_drafts.pop(user_id, None)
        self.rename_location_drafts.pop(user_id, None)

    def clear_all_user_runtime(self, user_id: int) -> None:
        """Очищает всё runtime-состояние пользователя."""
        self.clear_state(user_id)
        self.compare_drafts.pop(user_id, None)
        self.details_saved_drafts.pop(user_id, None)
        self.forecast_saved_drafts.pop(user_id, None)
        self.forecast_cache.pop(user_id, None)
        self.clear_location_choices(user_id)
        self.clear_saved_location_flows(user_id)
