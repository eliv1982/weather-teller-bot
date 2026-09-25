import time


def _short_location_name(label: object) -> str:
    """Возвращает короткую географическую подпись без служебных префиксов/скобок."""
    raw = str(label or "").strip()
    if not raw:
        return "неизвестная локация"
    if "—" in raw:
        raw = raw.split("—", 1)[1].strip()
    if "(" in raw:
        raw = raw.split("(", 1)[0].strip()
    return raw or "неизвестная локация"


def _resolve_alert_location_label(sub: dict) -> str:
    """Возвращает фактическую подпись локации для уведомления и AI-совета."""
    if not isinstance(sub, dict):
        return "неизвестная локация"
    raw_label = (
        sub.get("label")
        or sub.get("city")
        or sub.get("city_label")
        or sub.get("title")
        or "неизвестная локация"
    )
    return _short_location_name(raw_label)


def _finish_subscription_check(
    *,
    ctx,
    user_id_str: object,
    sub: dict,
    previous_check_ts: int,
    interval_h: int,
    now_ts: int,
    new_signature: str | None = None,
) -> None:
    """
    Фиксирует результат проверки одной подписки: last_check_ts (и last_alert_signature после отправки).

    В БД уходит только состояние этой подписки (точечный UPDATE по user_id + location_id), а не весь
    устаревший снимок пользователя: правки, сделанные пользователем в боте во время итерации
    (локации, настройки подписок), не затираются. previous_check_ts и interval_h - значения из снимка,
    по которым определялось, что подписка пора проверять: last_check_ts обновится, только если в БД оба
    всё ещё такие же (смена интервала в боте меняет interval_h и сбрасывает last_check_ts в 0).
    """
    sub["last_check_ts"] = now_ts
    if new_signature is not None:
        sub["last_alert_signature"] = new_signature
    location_id = sub.get("location_id")
    try:
        ctx.update_alert_subscription_state(
            int(user_id_str),
            str(location_id),
            last_check_ts=now_ts,
            expected_last_check_ts=previous_check_ts,
            expected_interval_h=interval_h,
            last_alert_signature=new_signature,
        )
    except Exception:
        ctx.logger.exception(
            "Не удалось сохранить состояние уведомления пользователя %s (подписка %s).",
            user_id_str,
            location_id,
        )


def run_alerts_worker_iteration(*, ctx) -> bool:
    """
    Выполняет одну итерацию фоновой проверки уведомлений.

    В БД записывается только состояние проверенных подписок (last_check_ts / last_alert_signature),
    по одной подписке за раз; загруженный в начале итерации снимок пользователей целиком не сохраняется.
    """
    all_users = ctx.load_all_users()
    changed = False
    now_ts = int(time.time())

    for user_id_str, user_data in all_users.items():
        if not isinstance(user_data, dict):
            continue

        user_data = ctx.alerts_subscription_service.ensure_defaults(ctx.ensure_notifications_defaults(user_data))
        subscriptions = ctx.alerts_subscription_service.list_subscriptions(user_data)
        if not isinstance(subscriptions, list) or not subscriptions:
            continue

        for sub in subscriptions:
            if not isinstance(sub, dict):
                continue
            if not bool(sub.get("enabled", True)):
                continue
            lat = sub.get("lat")
            lon = sub.get("lon")
            if lat is None or lon is None:
                continue
            interval_h = sub.get("interval_h", 2)
            if not isinstance(interval_h, int) or interval_h <= 0:
                interval_h = 2
            last_check_ts = sub.get("last_check_ts", 0)
            if not isinstance(last_check_ts, (int, float)):
                last_check_ts = 0
            previous_check_ts = int(last_check_ts)
            if now_ts - previous_check_ts < interval_h * 3600:
                continue

            forecast_items = ctx.get_forecast_5d3h(float(lat), float(lon))
            if not forecast_items:
                _finish_subscription_check(
                    ctx=ctx,
                    user_id_str=user_id_str,
                    sub=sub,
                    previous_check_ts=previous_check_ts,
                    interval_h=interval_h,
                    now_ts=now_ts,
                )
                changed = True
                continue

            alerts = ctx.detect_weather_alerts(
                forecast_items,
                now_ts=now_ts,
                horizon_hours=24,
            )
            if alerts:
                location_label = _resolve_alert_location_label(sub)
                first_alert = alerts[0]
                first_alert_text = str(first_alert.get("text") or "")
                first_alert_slot_utc = int(first_alert.get("slot_ts_utc") or 0)
                location_id = str(sub.get("location_id") or "no_id")
                alert_signature = f"{location_id}|{first_alert_slot_utc}|{first_alert_text}"
                previous_signature = str(sub.get("last_alert_signature") or "")

                if previous_signature == alert_signature:
                    _finish_subscription_check(
                        ctx=ctx,
                        user_id_str=user_id_str,
                        sub=sub,
                        previous_check_ts=previous_check_ts,
                        interval_h=interval_h,
                        now_ts=now_ts,
                    )
                    changed = True
                    continue

                slot_item = next(
                    (
                        item
                        for item in forecast_items
                        if isinstance(item, dict) and int(item.get("dt") or 0) == first_alert_slot_utc
                    ),
                    None,
                )
                slot_main = slot_item.get("main", {}) if isinstance(slot_item, dict) else {}
                slot_wind = slot_item.get("wind", {}) if isinstance(slot_item, dict) else {}
                slot_pop = slot_item.get("pop") if isinstance(slot_item, dict) else None

                desc_l = str(first_alert.get("description") or "").lower()
                if any(x in desc_l for x in ("дожд", "лив", "гроза", "снег")):
                    event_type = "precipitation"
                elif isinstance(slot_wind.get("speed"), (int, float)) and float(slot_wind.get("speed")) >= 8.0:
                    event_type = "wind"
                elif (
                    isinstance(slot_main.get("temp"), (int, float))
                    and isinstance(slot_main.get("feels_like"), (int, float))
                    and float(slot_main.get("feels_like")) <= float(slot_main.get("temp")) - 2.0
                ):
                    event_type = "temperature_drop"
                else:
                    event_type = "general"

                alert_payload = {
                    "event_type": event_type,
                    "slot_ts_utc": first_alert_slot_utc,
                    "slot_local": str(first_alert_text).split("—", 1)[0].strip(),
                    "temperature": slot_main.get("temp"),
                    "feels_like": slot_main.get("feels_like"),
                    "description": first_alert.get("description"),
                    "wind_speed": slot_wind.get("speed"),
                    "precip_probability": slot_pop,
                }
                ai_explanation = ""
                try:
                    ai_explanation = str(
                        ctx.ai_weather_service.explain_weather_alert(str(location_label), alert_payload)
                    ).strip()
                except Exception:
                    ctx.logger.warning(
                        "Не удалось получить AI-объяснение уведомления для пользователя %s.",
                        user_id_str,
                    )

                alert_text = (
                    "🌤 Weather Teller\n"
                    f"Для локации {location_label} найдено изменение погоды:\n"
                    f"• {first_alert_text}"
                )
                if ai_explanation:
                    alert_text = (
                        f"{alert_text}\n\n"
                        "🪄 Совет:\n"
                        f"{ai_explanation}"
                    )
                sent_signature = None
                try:
                    ctx.bot.send_message(int(user_id_str), alert_text)
                    sent_signature = alert_signature
                except Exception:
                    ctx.logger.warning("Не удалось отправить уведомление пользователю %s.", user_id_str)
                _finish_subscription_check(
                    ctx=ctx,
                    user_id_str=user_id_str,
                    sub=sub,
                    previous_check_ts=previous_check_ts,
                    interval_h=interval_h,
                    now_ts=now_ts,
                    new_signature=sent_signature,
                )
                changed = True
                continue

            _finish_subscription_check(
                ctx=ctx,
                user_id_str=user_id_str,
                sub=sub,
                previous_check_ts=previous_check_ts,
                interval_h=interval_h,
                now_ts=now_ts,
            )
            changed = True

    return changed


def alerts_worker(*, ctx) -> None:
    """Фоновая проверка прогноза для уведомлений."""
    ctx.logger.info("Фоновый поток уведомлений запущен.")

    while True:
        try:
            run_alerts_worker_iteration(ctx=ctx)
        except Exception:
            ctx.logger.exception("Ошибка в фоновом потоке уведомлений.")

        time.sleep(60)
