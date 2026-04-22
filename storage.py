import json
from pathlib import Path


# Файл с данными пользователей рядом с этим модулем
DATA_FILE = Path(__file__).resolve().parent / "User_Data.json"


def _default_user_data() -> dict:
    """Возвращает структуру пользователя по умолчанию."""
    return {
        "city": "",
        "lat": None,
        "lon": None,
        "saved_locations": [],
        "favorite_location_id": None,
        "notifications": {
            "enabled": False,
            "interval_h": 2,
            "last_check_ts": 0,
        },
    }


def load_all_users() -> dict:
    """
    Загружает всех пользователей из User_Data.json.
    Если файл отсутствует, пустой или повреждён, возвращает пустой словарь.
    """
    if not DATA_FILE.exists():
        return {}

    try:
        raw_text = DATA_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return {}

    if not raw_text:
        return {}

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        return {}

    if not isinstance(data, dict):
        return {}

    return data


def save_all_users(data: dict) -> None:
    """
    Сохраняет весь словарь пользователей в User_Data.json.
    Если приходит не словарь, сохраняется пустой словарь.
    """
    safe_data = data if isinstance(data, dict) else {}

    try:
        DATA_FILE.write_text(
            json.dumps(safe_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        # Ошибка записи не должна прерывать работу бота traceback-ом
        return


def load_user(user_id: int) -> dict:
    """
    Загружает данные одного пользователя.
    Если записи нет, возвращает структуру по умолчанию.
    """
    users = load_all_users()
    user_key = str(user_id)
    user_data = users.get(user_key)

    if not isinstance(user_data, dict):
        return _default_user_data()

    # Объединяем с дефолтом, чтобы гарантировать все нужные поля
    default_data = _default_user_data()
    saved_locations_raw = user_data.get("saved_locations")
    if isinstance(saved_locations_raw, list):
        saved_locations = [item for item in saved_locations_raw if isinstance(item, dict)]
    else:
        saved_locations = []

    favorite_location_id_raw = user_data.get("favorite_location_id")
    favorite_location_id = favorite_location_id_raw if isinstance(favorite_location_id_raw, str) else None

    result = {
        "city": user_data.get("city", default_data["city"]),
        "lat": user_data.get("lat", default_data["lat"]),
        "lon": user_data.get("lon", default_data["lon"]),
        "saved_locations": saved_locations,
        "favorite_location_id": favorite_location_id,
        "notifications": {
            "enabled": (
                user_data.get("notifications", {}).get(
                    "enabled", default_data["notifications"]["enabled"]
                )
                if isinstance(user_data.get("notifications"), dict)
                else default_data["notifications"]["enabled"]
            ),
            "interval_h": (
                user_data.get("notifications", {}).get(
                    "interval_h", default_data["notifications"]["interval_h"]
                )
                if isinstance(user_data.get("notifications"), dict)
                else default_data["notifications"]["interval_h"]
            ),
            "last_check_ts": (
                user_data.get("notifications", {}).get(
                    "last_check_ts", default_data["notifications"]["last_check_ts"]
                )
                if isinstance(user_data.get("notifications"), dict)
                else default_data["notifications"]["last_check_ts"]
            ),
        },
    }
    return result


def save_user(user_id: int, data: dict) -> None:
    """
    Сохраняет данные пользователя по строковому ключу user_id.
    """
    users = load_all_users()
    users[str(user_id)] = data if isinstance(data, dict) else _default_user_data()
    save_all_users(users)
