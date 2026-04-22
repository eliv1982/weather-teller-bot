import os
from contextlib import contextmanager

from dotenv import load_dotenv

try:
    import psycopg  # type: ignore[reportMissingModuleSource]
    from psycopg.rows import dict_row  # type: ignore[reportMissingModuleSource]
except ImportError as exc:  # pragma: no cover
    raise RuntimeError(
        "Не найден драйвер PostgreSQL. Установи пакет psycopg[binary]: pip install \"psycopg[binary]\""
    ) from exc


load_dotenv()


def _default_user_data() -> dict:
    """Возвращает структуру пользователя по умолчанию (совместимую с текущим storage)."""
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
        "alert_subscriptions": [],
    }


def get_connection():
    """
    Создаёт подключение к PostgreSQL на основе переменных окружения.

    Требуемые переменные:
    - PGHOST
    - PGPORT
    - PGDATABASE
    - PGUSER
    - PGPASSWORD
    """
    host = os.getenv("PGHOST")
    port = os.getenv("PGPORT")
    dbname = os.getenv("PGDATABASE")
    user = os.getenv("PGUSER")
    password = os.getenv("PGPASSWORD")

    missing = [
        name
        for name, value in (
            ("PGHOST", host),
            ("PGPORT", port),
            ("PGDATABASE", dbname),
            ("PGUSER", user),
            ("PGPASSWORD", password),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            f"Не заданы параметры подключения к PostgreSQL: {', '.join(missing)}"
        )

    try:
        return psycopg.connect(
            host=host,
            port=int(port),
            dbname=dbname,
            user=user,
            password=password,
        )
    except Exception as exc:
        raise RuntimeError(f"Не удалось подключиться к PostgreSQL: {exc}") from exc


@contextmanager
def _cursor(commit: bool = False):
    """
    Контекстный менеджер для cursor с аккуратным rollback/commit.
    """
    conn = get_connection()
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            yield cur
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_postgres_db() -> None:
    """
    Создаёт таблицы users, saved_locations и alert_subscriptions, если их ещё нет.

    В новой схеме используются составные первичные ключи:
    - saved_locations: (user_id, id)
    - alert_subscriptions: (user_id, location_id)

    Если таблицы уже были созданы в старой схеме, CREATE TABLE IF NOT EXISTS их не изменит.
    Для таких случаев потребуется отдельная SQL-миграция ключей.
    """
    users_sql = """
    CREATE TABLE IF NOT EXISTS users (
        user_id BIGINT PRIMARY KEY,
        current_city TEXT NULL,
        current_lat DOUBLE PRECISION NULL,
        current_lon DOUBLE PRECISION NULL,
        favorite_location_id TEXT NULL,
        notifications_enabled BOOLEAN NOT NULL DEFAULT FALSE,
        notifications_interval_h INTEGER NOT NULL DEFAULT 2,
        notifications_last_check_ts BIGINT NOT NULL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    users_legacy_notifications_sql = """
    ALTER TABLE users
    ADD COLUMN IF NOT EXISTS notifications_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS notifications_interval_h INTEGER NOT NULL DEFAULT 2,
    ADD COLUMN IF NOT EXISTS notifications_last_check_ts BIGINT NOT NULL DEFAULT 0;
    """
    saved_locations_sql = """
    CREATE TABLE IF NOT EXISTS saved_locations (
        id TEXT NOT NULL,
        user_id BIGINT NOT NULL,
        title TEXT NOT NULL,
        label TEXT NOT NULL,
        lat DOUBLE PRECISION NOT NULL,
        lon DOUBLE PRECISION NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, id),
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
    );
    """
    alert_subscriptions_sql = """
    CREATE TABLE IF NOT EXISTS alert_subscriptions (
        location_id TEXT NOT NULL,
        user_id BIGINT NOT NULL,
        title TEXT NOT NULL,
        label TEXT NOT NULL,
        lat DOUBLE PRECISION NOT NULL,
        lon DOUBLE PRECISION NOT NULL,
        enabled BOOLEAN NOT NULL DEFAULT TRUE,
        interval_h INTEGER NOT NULL DEFAULT 2,
        last_check_ts BIGINT NOT NULL DEFAULT 0,
        last_alert_signature TEXT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, location_id),
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
    );
    """
    saved_locations_indexes_sql = """
    CREATE INDEX IF NOT EXISTS idx_saved_locations_user_id ON saved_locations(user_id);
    """
    alert_subscriptions_indexes_sql = """
    CREATE INDEX IF NOT EXISTS idx_alert_subscriptions_user_id ON alert_subscriptions(user_id);
    CREATE INDEX IF NOT EXISTS idx_alert_subscriptions_user_enabled ON alert_subscriptions(user_id, enabled);
    """

    with _cursor(commit=True) as cur:
        cur.execute(users_sql)
        cur.execute(users_legacy_notifications_sql)
        cur.execute(saved_locations_sql)
        cur.execute(alert_subscriptions_sql)
        cur.execute(saved_locations_indexes_sql)
        cur.execute(alert_subscriptions_indexes_sql)


def _load_saved_locations(cur, user_id: int) -> list[dict]:
    """Загружает сохранённые локации пользователя."""
    cur.execute(
        """
        SELECT id, title, label, lat, lon
        FROM saved_locations
        WHERE user_id = %s
        ORDER BY created_at ASC;
        """,
        (user_id,),
    )
    rows = cur.fetchall() or []
    return [
        {
            "id": str(row["id"]),
            "title": str(row["title"]),
            "label": str(row["label"]),
            "lat": float(row["lat"]),
            "lon": float(row["lon"]),
        }
        for row in rows
    ]


def _load_alert_subscriptions(cur, user_id: int) -> list[dict]:
    """Загружает подписки уведомлений пользователя."""
    cur.execute(
        """
        SELECT location_id, title, label, lat, lon, enabled, interval_h, last_check_ts, last_alert_signature
        FROM alert_subscriptions
        WHERE user_id = %s
        ORDER BY created_at ASC;
        """,
        (user_id,),
    )
    rows = cur.fetchall() or []
    return [
        {
            "location_id": str(row["location_id"]),
            "title": str(row["title"]),
            "label": str(row["label"]),
            "lat": float(row["lat"]),
            "lon": float(row["lon"]),
            "enabled": bool(row["enabled"]),
            "interval_h": int(row["interval_h"]),
            "last_check_ts": int(row["last_check_ts"]),
            "last_alert_signature": str(row["last_alert_signature"] or ""),
        }
        for row in rows
    ]


def load_user(user_id: int) -> dict:
    """
    Загружает данные пользователя из PostgreSQL в структуру, совместимую с текущим кодом.
    """
    default_data = _default_user_data()
    with _cursor(commit=False) as cur:
        cur.execute(
            """
            SELECT
                user_id, current_city, current_lat, current_lon, favorite_location_id,
                notifications_enabled, notifications_interval_h, notifications_last_check_ts
            FROM users
            WHERE user_id = %s;
            """,
            (user_id,),
        )
        user_row = cur.fetchone()
        if not user_row:
            return default_data

        saved_locations = _load_saved_locations(cur, user_id)
        alert_subscriptions = _load_alert_subscriptions(cur, user_id)

        return {
            "city": user_row["current_city"] or "",
            "lat": user_row["current_lat"],
            "lon": user_row["current_lon"],
            "saved_locations": saved_locations,
            "favorite_location_id": user_row["favorite_location_id"],
            # legacy-compatible поле notifications хранится в таблице users.
            "notifications": {
                "enabled": bool(user_row.get("notifications_enabled", False)),
                "interval_h": int(user_row.get("notifications_interval_h", 2)),
                "last_check_ts": int(user_row.get("notifications_last_check_ts", 0)),
            },
            "alert_subscriptions": alert_subscriptions,
        }


def save_user(user_id: int, user_data: dict) -> None:
    """
    Сохраняет пользователя в PostgreSQL.

    Стратегия простая и надёжная:
    - upsert users
    - delete + insert saved_locations
    - delete + insert alert_subscriptions
    """
    safe_data = user_data if isinstance(user_data, dict) else _default_user_data()
    saved_locations = safe_data.get("saved_locations", [])
    if not isinstance(saved_locations, list):
        saved_locations = []
    alert_subscriptions = safe_data.get("alert_subscriptions", [])
    if not isinstance(alert_subscriptions, list):
        alert_subscriptions = []
    notifications = safe_data.get("notifications", {})
    if not isinstance(notifications, dict):
        notifications = {}
    notifications_enabled = bool(notifications.get("enabled", False))
    notifications_interval_h = notifications.get("interval_h", 2)
    if not isinstance(notifications_interval_h, int) or notifications_interval_h <= 0:
        notifications_interval_h = 2
    notifications_last_check_ts = notifications.get("last_check_ts", 0)
    if not isinstance(notifications_last_check_ts, (int, float)):
        notifications_last_check_ts = 0

    with _cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO users (
                user_id, current_city, current_lat, current_lon, favorite_location_id,
                notifications_enabled, notifications_interval_h, notifications_last_check_ts
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
                current_city = EXCLUDED.current_city,
                current_lat = EXCLUDED.current_lat,
                current_lon = EXCLUDED.current_lon,
                favorite_location_id = EXCLUDED.favorite_location_id,
                notifications_enabled = EXCLUDED.notifications_enabled,
                notifications_interval_h = EXCLUDED.notifications_interval_h,
                notifications_last_check_ts = EXCLUDED.notifications_last_check_ts,
                updated_at = CURRENT_TIMESTAMP;
            """,
            (
                user_id,
                safe_data.get("city"),
                safe_data.get("lat"),
                safe_data.get("lon"),
                safe_data.get("favorite_location_id"),
                notifications_enabled,
                notifications_interval_h,
                int(notifications_last_check_ts),
            ),
        )

        cur.execute("DELETE FROM saved_locations WHERE user_id = %s;", (user_id,))
        for item in saved_locations:
            if not isinstance(item, dict):
                continue
            loc_id = item.get("id")
            title = item.get("title")
            label = item.get("label")
            lat = item.get("lat")
            lon = item.get("lon")
            if not loc_id or title is None or label is None or lat is None or lon is None:
                continue
            cur.execute(
                """
                INSERT INTO saved_locations (id, user_id, title, label, lat, lon)
                VALUES (%s, %s, %s, %s, %s, %s);
                """,
                (str(loc_id), user_id, str(title), str(label), float(lat), float(lon)),
            )

        cur.execute("DELETE FROM alert_subscriptions WHERE user_id = %s;", (user_id,))
        for item in alert_subscriptions:
            if not isinstance(item, dict):
                continue
            location_id = item.get("location_id")
            title = item.get("title")
            label = item.get("label")
            lat = item.get("lat")
            lon = item.get("lon")
            if not location_id or title is None or label is None or lat is None or lon is None:
                continue
            cur.execute(
                """
                INSERT INTO alert_subscriptions (
                    location_id, user_id, title, label, lat, lon,
                    enabled, interval_h, last_check_ts, last_alert_signature
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """,
                (
                    str(location_id),
                    user_id,
                    str(title),
                    str(label),
                    float(lat),
                    float(lon),
                    bool(item.get("enabled", True)),
                    int(item.get("interval_h", 2)),
                    int(item.get("last_check_ts", 0)),
                    str(item.get("last_alert_signature") or ""),
                ),
            )


def load_all_users() -> dict[int, dict]:
    """
    Загружает всех пользователей из PostgreSQL в совместимом формате.
    """
    result: dict[int, dict] = {}
    with _cursor(commit=False) as cur:
        cur.execute(
            """
            SELECT
                user_id, current_city, current_lat, current_lon, favorite_location_id,
                notifications_enabled, notifications_interval_h, notifications_last_check_ts
            FROM users
            ORDER BY user_id ASC;
            """
        )
        users_rows = cur.fetchall() or []

        cur.execute(
            """
            SELECT user_id, id, title, label, lat, lon
            FROM saved_locations
            ORDER BY user_id ASC, created_at ASC;
            """
        )
        saved_rows = cur.fetchall() or []

        cur.execute(
            """
            SELECT
                user_id, location_id, title, label, lat, lon,
                enabled, interval_h, last_check_ts, last_alert_signature
            FROM alert_subscriptions
            ORDER BY user_id ASC, created_at ASC;
            """
        )
        alerts_rows = cur.fetchall() or []

    saved_by_user: dict[int, list[dict]] = {}
    for row in saved_rows:
        uid = int(row["user_id"])
        saved_by_user.setdefault(uid, []).append(
            {
                "id": str(row["id"]),
                "title": str(row["title"]),
                "label": str(row["label"]),
                "lat": float(row["lat"]),
                "lon": float(row["lon"]),
            }
        )

    alerts_by_user: dict[int, list[dict]] = {}
    for row in alerts_rows:
        uid = int(row["user_id"])
        alerts_by_user.setdefault(uid, []).append(
            {
                "location_id": str(row["location_id"]),
                "title": str(row["title"]),
                "label": str(row["label"]),
                "lat": float(row["lat"]),
                "lon": float(row["lon"]),
                "enabled": bool(row["enabled"]),
                "interval_h": int(row["interval_h"]),
                "last_check_ts": int(row["last_check_ts"]),
                "last_alert_signature": str(row["last_alert_signature"] or ""),
            }
        )

    default_data = _default_user_data()
    for user_row in users_rows:
        uid = int(user_row["user_id"])
        result[uid] = {
            "city": user_row["current_city"] or "",
            "lat": user_row["current_lat"],
            "lon": user_row["current_lon"],
            "saved_locations": saved_by_user.get(uid, []),
            "favorite_location_id": user_row["favorite_location_id"],
            # legacy-compatible поле notifications хранится в users.
            "notifications": {
                "enabled": bool(user_row.get("notifications_enabled", False)),
                "interval_h": int(user_row.get("notifications_interval_h", 2)),
                "last_check_ts": int(user_row.get("notifications_last_check_ts", 0)),
            },
            "alert_subscriptions": alerts_by_user.get(uid, []),
        }

    # Если пользователей нет, возвращаем пустой словарь как и раньше.
    if not users_rows:
        return {}

    # На случай частичных данных в БД структура всегда соответствует default-схеме.
    for uid, user_data in result.items():
        if "notifications" not in user_data:
            user_data["notifications"] = default_data["notifications"]

    return result


def save_all_users(users_dict: dict) -> None:
    """
    Совместимая массовая запись пользователей для AppContext/worker.

    Реализация простая: вызывает save_user для каждого пользователя.
    """
    if not isinstance(users_dict, dict):
        return

    for user_id_raw, user_data in users_dict.items():
        try:
            user_id = int(user_id_raw)
        except (TypeError, ValueError):
            continue
        save_user(user_id, user_data if isinstance(user_data, dict) else _default_user_data())
