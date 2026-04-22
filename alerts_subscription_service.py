import time


class AlertsSubscriptionService:
    """Сервис доменной логики подписок на погодные уведомления."""

    def ensure_defaults(self, user_data: dict) -> dict:
        """Гарантирует корректную структуру подписок в user_data."""
        raw_subscriptions = user_data.get("alert_subscriptions", [])
        if not isinstance(raw_subscriptions, list):
            raw_subscriptions = []

        normalized: list[dict] = []
        seen_coords: set[tuple[float, float]] = set()
        for item in raw_subscriptions:
            if not isinstance(item, dict):
                continue

            lat = item.get("lat")
            lon = item.get("lon")
            if lat is None or lon is None:
                continue

            try:
                lat_f = float(lat)
                lon_f = float(lon)
            except (TypeError, ValueError):
                continue

            coords_key = self.normalize_coordinates_for_duplicate(lat_f, lon_f)
            if coords_key in seen_coords:
                continue
            seen_coords.add(coords_key)

            location_id = item.get("location_id")
            if not isinstance(location_id, str) or not location_id.strip():
                location_id = f"sub_{int(time.time() * 1000)}_{len(normalized) + 1}"

            title_raw = item.get("title")
            label_raw = item.get("label")
            title = str(title_raw).strip() if title_raw is not None else ""
            label = str(label_raw).strip() if label_raw is not None else ""
            if not label:
                label = "Выбранная локация"
            if not title:
                title = label

            interval_h = item.get("interval_h", 2)
            if not isinstance(interval_h, int) or interval_h <= 0:
                interval_h = 2

            last_check_ts = item.get("last_check_ts", 0)
            if not isinstance(last_check_ts, (int, float)):
                last_check_ts = 0
            last_alert_signature = item.get("last_alert_signature")
            if not isinstance(last_alert_signature, str):
                last_alert_signature = ""

            normalized.append(
                {
                    "location_id": location_id,
                    "title": title,
                    "label": label,
                    "lat": lat_f,
                    "lon": lon_f,
                    "enabled": bool(item.get("enabled", True)),
                    "interval_h": interval_h,
                    "last_check_ts": int(last_check_ts),
                    "last_alert_signature": last_alert_signature,
                }
            )

        user_data["alert_subscriptions"] = normalized
        return user_data

    def normalize_coordinates(self, lat: float, lon: float) -> tuple[float, float]:
        """Нормализует координаты для сравнения подписок без дублей."""
        return round(float(lat), 5), round(float(lon), 5)

    def normalize_coordinates_for_duplicate(self, lat: float, lon: float) -> tuple[float, float]:
        """
        Нормализует координаты для дедупликации при добавлении.

        Используется более грубое округление, чтобы одинаковая логическая локация,
        пришедшая из разных сценариев, считалась дублем даже при небольшом сдвиге.
        """
        return round(float(lat), 4), round(float(lon), 4)

    def normalize_label_for_duplicate(self, label: str) -> str:
        """Нормализует label для проверки дублей по имени локации."""
        text = (label or "").strip().lower()
        if not text:
            return ""
        compact = " ".join(text.split())
        return compact

    def build_subscription_id(self, lat: float, lon: float, fallback_prefix: str = "geo") -> str:
        """Формирует стабильный id подписки по нормализованным координатам."""
        lat_n, lon_n = self.normalize_coordinates(lat, lon)
        lat_part = f"{abs(lat_n):.5f}".replace(".", "")
        lon_part = f"{abs(lon_n):.5f}".replace(".", "")
        lat_prefix = "n" if lat_n >= 0 else "s"
        lon_prefix = "e" if lon_n >= 0 else "w"
        return f"{fallback_prefix}_{lat_prefix}{lat_part}_{lon_prefix}{lon_part}"

    def find_duplicate(
        self,
        user_data: dict,
        lat: float,
        lon: float,
        *,
        location_id: str | None = None,
        label: str | None = None,
    ) -> dict | None:
        """
        Ищет существующую подписку.

        Подписка считается дублем, если совпало хотя бы одно:
        - location_id;
        - координаты после грубой нормализации для дедупликации;
        - нормализованный label.
        """
        user_data = self.ensure_defaults(user_data)
        target_key = self.normalize_coordinates_for_duplicate(lat, lon)
        target_id = (location_id or "").strip()
        target_label = self.normalize_label_for_duplicate(label or "")

        for item in user_data.get("alert_subscriptions", []):
            if not isinstance(item, dict):
                continue

            item_id = str(item.get("location_id") or "").strip()
            if target_id and item_id and target_id == item_id:
                return item

            item_lat = item.get("lat")
            item_lon = item.get("lon")
            try:
                if item_lat is not None and item_lon is not None and self.normalize_coordinates_for_duplicate(
                    float(item_lat), float(item_lon)
                ) == target_key:
                    return item
            except (TypeError, ValueError):
                pass

            item_label = self.normalize_label_for_duplicate(str(item.get("label") or ""))
            if target_label and item_label and target_label == item_label:
                return item

        return None

    def add_subscription(
        self,
        user_data: dict,
        *,
        location_id: str,
        title: str,
        label: str,
        lat: float,
        lon: float,
        enabled: bool = True,
        interval_h: int = 2,
    ) -> tuple[dict, bool]:
        """Добавляет подписку, если для координат ещё нет записи."""
        user_data = self.ensure_defaults(user_data)
        if self.find_duplicate(
            user_data,
            lat,
            lon,
            location_id=location_id,
            label=label,
        ):
            return user_data, False

        safe_interval_h = interval_h if isinstance(interval_h, int) and interval_h > 0 else 2
        user_data["alert_subscriptions"].append(
            {
                "location_id": location_id,
                "title": title.strip() or label.strip() or "Локация",
                "label": label.strip() or title.strip() or "Локация",
                "lat": float(lat),
                "lon": float(lon),
                "enabled": bool(enabled),
                "interval_h": safe_interval_h,
                "last_check_ts": 0,
                "last_alert_signature": "",
            }
        )
        return user_data, True

    def toggle_subscription(self, user_data: dict, subscription_id: str) -> tuple[dict, bool]:
        """Переключает enabled у подписки по id."""
        user_data = self.ensure_defaults(user_data)
        target = self.get_subscription(user_data, subscription_id)
        if not isinstance(target, dict):
            return user_data, False
        target["enabled"] = not bool(target.get("enabled", True))
        return user_data, True

    def update_interval(self, user_data: dict, subscription_id: str, interval_h: int) -> tuple[dict, bool]:
        """Обновляет интервал подписки и сбрасывает last_check_ts."""
        user_data = self.ensure_defaults(user_data)
        target = self.get_subscription(user_data, subscription_id)
        if not isinstance(target, dict):
            return user_data, False
        safe_interval_h = interval_h if isinstance(interval_h, int) and interval_h > 0 else 2
        target["interval_h"] = safe_interval_h
        target["last_check_ts"] = 0
        return user_data, True

    def delete_subscription(self, user_data: dict, subscription_id: str) -> tuple[dict, bool]:
        """Удаляет подписку по id."""
        user_data = self.ensure_defaults(user_data)
        before = len(user_data["alert_subscriptions"])
        user_data["alert_subscriptions"] = [
            item
            for item in user_data["alert_subscriptions"]
            if isinstance(item, dict) and item.get("location_id") != subscription_id
        ]
        return user_data, len(user_data["alert_subscriptions"]) != before

    def get_subscription(self, user_data: dict, subscription_id: str) -> dict | None:
        """Возвращает подписку по id или None."""
        user_data = self.ensure_defaults(user_data)
        return next(
            (
                item
                for item in user_data["alert_subscriptions"]
                if isinstance(item, dict) and item.get("location_id") == subscription_id
            ),
            None,
        )

    def list_subscriptions(self, user_data: dict) -> list[dict]:
        """Возвращает список подписок пользователя."""
        user_data = self.ensure_defaults(user_data)
        return user_data.get("alert_subscriptions", [])
