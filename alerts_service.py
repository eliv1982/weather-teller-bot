from datetime import datetime


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
