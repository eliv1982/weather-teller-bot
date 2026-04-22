from datetime import datetime
import time


def ensure_notifications_defaults(user_data: dict) -> dict:
    """Гарантирует корректную структуру notifications в данных пользователя."""
    notifications = user_data.get("notifications", {})
    if not isinstance(notifications, dict):
        notifications = {}

    interval_h = notifications.get("interval_h", 2)
    if not isinstance(interval_h, int) or interval_h <= 0:
        interval_h = 2

    last_check_ts = notifications.get("last_check_ts", 0)
    if not isinstance(last_check_ts, (int, float)):
        last_check_ts = 0

    notifications["enabled"] = bool(notifications.get("enabled", False))
    notifications["interval_h"] = interval_h
    notifications["last_check_ts"] = int(last_check_ts)
    user_data["notifications"] = notifications
    return user_data


def ensure_alert_subscriptions_defaults(user_data: dict) -> dict:
    """Гарантирует корректную структуру подписок уведомлений в данных пользователя."""
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
        coords_key = _normalized_coords(lat_f, lon_f)
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
            }
        )

    user_data["alert_subscriptions"] = normalized
    return user_data


def migrate_legacy_alert_to_subscriptions(user_data: dict) -> tuple[dict, bool]:
    """
    Мягко переносит старую одиночную локацию уведомлений в subscriptions.

    Миграция выполняется только если подписок пока нет и у пользователя есть lat/lon.
    """
    user_data = ensure_notifications_defaults(user_data)
    user_data = ensure_alert_subscriptions_defaults(user_data)
    if user_data["alert_subscriptions"]:
        return user_data, False

    lat = user_data.get("lat")
    lon = user_data.get("lon")
    if lat is None or lon is None:
        return user_data, False

    city = str(user_data.get("city") or "Текущая локация").strip()
    interval_h = user_data["notifications"].get("interval_h", 2)
    enabled = user_data["notifications"].get("enabled", False)

    user_data["alert_subscriptions"].append(
        {
            "location_id": f"legacy_{int(time.time() * 1000)}",
            "title": city,
            "label": city,
            "lat": float(lat),
            "lon": float(lon),
            "enabled": bool(enabled),
            "interval_h": interval_h if isinstance(interval_h, int) and interval_h > 0 else 2,
            "last_check_ts": 0,
        }
    )
    return user_data, True


def has_subscription_with_coordinates(subscriptions: list[dict], lat: float, lon: float) -> bool:
    """Проверяет, есть ли уже подписка с теми же координатами."""
    target_key = _normalized_coords(lat, lon)
    for item in subscriptions:
        if not isinstance(item, dict):
            continue
        item_lat = item.get("lat")
        item_lon = item.get("lon")
        if item_lat is None or item_lon is None:
            continue
        try:
            if _normalized_coords(float(item_lat), float(item_lon)) == target_key:
                return True
        except (TypeError, ValueError):
            continue
    return False


def _normalized_coords(lat: float, lon: float) -> tuple[float, float]:
    """Нормализует координаты для сравнения подписок без дублей."""
    return round(float(lat), 5), round(float(lon), 5)


def add_alert_subscription(
    user_data: dict,
    *,
    location_id: str,
    title: str,
    label: str,
    lat: float,
    lon: float,
) -> tuple[dict, bool]:
    """Добавляет новую подписку, если для этих координат ещё нет записи."""
    user_data = ensure_notifications_defaults(user_data)
    user_data = ensure_alert_subscriptions_defaults(user_data)
    subscriptions = user_data["alert_subscriptions"]

    if has_subscription_with_coordinates(subscriptions, lat, lon):
        return user_data, False

    subscriptions.append(
        {
            "location_id": location_id,
            "title": title.strip() or label.strip() or "Локация",
            "label": label.strip() or title.strip() or "Локация",
            "lat": float(lat),
            "lon": float(lon),
            "enabled": True,
            "interval_h": 2,
            "last_check_ts": 0,
        }
    )
    return user_data, True


def detect_weather_alerts(forecast_items: list[dict]) -> list[str]:
    """Ищет в прогнозе ближайшие заметные ухудшения погоды."""
    keywords = ("дожд", "ливень", "гроза", "снег", "метель", "туман")
    alerts: list[str] = []

    for item in forecast_items[:8]:
        description = item.get("weather", [{}])[0].get("description", "")
        lowered = description.lower()
        if any(keyword in lowered for keyword in keywords):
            dt_txt = item.get("dt_txt", "")
            if " " in dt_txt:
                date_part, time_part = dt_txt.split(" ", 1)
                try:
                    date_fmt = datetime.strptime(date_part, "%Y-%m-%d").strftime("%d.%m")
                except ValueError:
                    date_fmt = date_part
                short = f"{date_fmt} {time_part[:5]} — {description}"
            else:
                short = f"{dt_txt} — {description}"
            alerts.append(short)

    return alerts
