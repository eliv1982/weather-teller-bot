from datetime import datetime
import time

from alerts_subscription_service import AlertsSubscriptionService

_alerts_subscriptions = AlertsSubscriptionService()


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
    return _alerts_subscriptions.ensure_defaults(user_data)


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
    user_data = {"alert_subscriptions": subscriptions if isinstance(subscriptions, list) else []}
    return _alerts_subscriptions.find_duplicate(user_data, lat, lon) is not None


def _normalized_coords(lat: float, lon: float) -> tuple[float, float]:
    """Нормализует координаты для сравнения подписок без дублей."""
    return _alerts_subscriptions.normalize_coordinates(lat, lon)


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
    return _alerts_subscriptions.add_subscription(
        user_data,
        location_id=location_id,
        title=title,
        label=label,
        lat=lat,
        lon=lon,
        enabled=True,
        interval_h=2,
    )


def _extract_timezone_offset(forecast_items: list[dict], explicit_offset: int | None = None) -> int:
    """Возвращает timezone offset локации в секундах."""
    if isinstance(explicit_offset, int):
        return explicit_offset
    for item in forecast_items:
        if not isinstance(item, dict):
            continue
        raw = item.get("_timezone_offset")
        if isinstance(raw, int):
            return raw
        if isinstance(raw, float):
            return int(raw)
    return 0


def _extract_slot_ts(item: dict) -> int | None:
    """Пытается извлечь UTC timestamp прогноза из элемента."""
    raw_dt = item.get("dt")
    if isinstance(raw_dt, (int, float)):
        return int(raw_dt)

    dt_txt = item.get("dt_txt", "")
    if not isinstance(dt_txt, str) or not dt_txt.strip():
        return None
    try:
        # OpenWeather отдает dt_txt в UTC.
        return int(datetime.strptime(dt_txt, "%Y-%m-%d %H:%M:%S").timestamp())
    except ValueError:
        return None


def detect_weather_alerts(
    forecast_items: list[dict],
    *,
    now_ts: int | None = None,
    horizon_hours: int = 24,
    timezone_offset_seconds: int | None = None,
) -> list[dict]:
    """Ищет в прогнозе ближайшие заметные ухудшения погоды по будущим слотам."""
    keywords = ("дожд", "ливень", "гроза", "снег", "метель", "туман")
    alerts: list[dict] = []
    if not isinstance(forecast_items, list) or not forecast_items:
        return alerts

    now_utc_ts = int(time.time()) if now_ts is None else int(now_ts)
    horizon_sec = max(1, int(horizon_hours)) * 3600
    upper_bound_ts = now_utc_ts + horizon_sec
    offset_sec = _extract_timezone_offset(forecast_items, explicit_offset=timezone_offset_seconds)

    for item in forecast_items:
        if not isinstance(item, dict):
            continue
        slot_ts = _extract_slot_ts(item)
        if slot_ts is None:
            continue
        # В анализ попадают только будущие слоты в ограниченном окне.
        if slot_ts < now_utc_ts or slot_ts > upper_bound_ts:
            continue

        description = item.get("weather", [{}])[0].get("description", "")
        lowered = description.lower()
        if any(keyword in lowered for keyword in keywords):
            local_ts = slot_ts + offset_sec
            local_dt = datetime.utcfromtimestamp(local_ts)
            local_slot = local_dt.strftime("%d.%m %H:%M")
            text = f"{local_slot} — {description}"
            alerts.append(
                {
                    "slot_ts_utc": slot_ts,
                    "slot_ts_local": local_ts,
                    "text": text,
                    "description": description,
                }
            )

    return alerts
