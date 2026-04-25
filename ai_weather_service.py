import logging
import os
from datetime import datetime
import hashlib
import json
import re

from postgres_storage import get_ai_cached_response, save_ai_cached_response

logger = logging.getLogger(__name__)


try:
    from openai import OpenAI  # type: ignore[reportMissingModuleSource]
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore[assignment]


class AiWeatherService:
    """Сервис ИИ-надстройки для человеко-понятных погодных объяснений."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = (api_key or os.getenv("OPENAI_API_KEY") or "").strip()
        self.model = (model or os.getenv("OPENAI_MODEL") or "gpt-5.4-mini").strip()
        self.client = OpenAI(api_key=self.api_key) if self.api_key and OpenAI is not None else None
        self.temperature = 0.2
        self.max_output_tokens_default = 340
        self.max_output_tokens_forecast_day = 300
        self.ttl_current_seconds = 20 * 60
        self.ttl_details_seconds = 20 * 60
        self.ttl_forecast_seconds = 6 * 60 * 60

    def explain_current_weather(self, city_label: str, weather_data: dict) -> str:
        """Коротко объясняет текущую погоду простым языком."""
        fallback = self._fallback_current(city_label, weather_data)
        signature = self._current_signature(city_label, weather_data)
        cache_key = self._build_cache_key("current", signature)
        cached = self._get_cached(cache_key)
        if cached:
            logger.info("AI cache hit: scenario=current")
            return cached
        logger.info("AI cache miss: scenario=current")
        prompt = (
            "Объясни текущую погоду простым и живым русским языком.\n"
            "Требования: 3-4 коротких предложения, дружелюбно и по делу, без канцелярита, "
            "без сарказма, без клоунады, без дисклеймеров и без воды.\n"
            "Используй только переданные данные, ничего не выдумывай.\n"
            "Обязательно скажи: как ощущается погода, нужен ли зонт, как лучше одеться, "
            "насколько комфортно сейчас на улице.\n"
            "Пиши как полезный совет живого помощника, без сухих шаблонов.\n\n"
            f"Локация: {city_label}\n"
            f"Данные: {weather_data}"
        )
        model_answer = self._call_model(prompt, max_output_tokens=self.max_output_tokens_default)
        if model_answer:
            self._save_cached(cache_key, "current", model_answer, ttl_seconds=self.ttl_current_seconds)
            return model_answer
        logger.info("AI fallback used: scenario=current")
        return fallback

    def summarize_day_forecast(self, city_label: str, day_forecast_data: list[dict]) -> str:
        """Делает краткую рекомендацию по прогнозу на день."""
        fallback = self._fallback_day_forecast(city_label, day_forecast_data)
        signature = self._forecast_signature(city_label, day_forecast_data)
        cache_key = self._build_cache_key("forecast_day", signature)
        cached = self._get_cached(cache_key)
        if cached:
            logger.info("AI cache hit: scenario=forecast_day")
            return cached
        logger.info("AI cache miss: scenario=forecast_day")
        prompt = (
            "Дай короткий и полезный совет по прогнозу на день.\n"
            "Требования: русский язык, 3-4 коротких предложения, естественный дружелюбный тон, "
            "без канцелярита, без сарказма, без клоунады, без дисклеймеров и без воды.\n"
            "Используй только переданные данные, ничего не выдумывай.\n"
            "Обязательно укажи: лучшее окно для прогулки, осадки и главное изменение погоды в течение дня.\n"
            "Финал сделай практичным: что лучше учесть перед выходом.\n\n"
            f"Локация: {city_label}\n"
            f"Слоты прогноза за день: {day_forecast_data}"
        )
        model_answer = self._call_model(prompt, max_output_tokens=self.max_output_tokens_forecast_day)
        if model_answer:
            self._save_cached(cache_key, "forecast_day", model_answer, ttl_seconds=self.ttl_forecast_seconds)
            return model_answer
        logger.info("AI fallback used: scenario=forecast_day")
        return fallback

    def explain_weather_details(self, city_label: str, weather_data: dict, air_quality_data: dict | None) -> str:
        """Поясняет расширенные погодные данные и качество воздуха."""
        fallback = self._fallback_details(city_label, weather_data, air_quality_data)
        signature = self._details_signature(city_label, weather_data, air_quality_data)
        cache_key = self._build_cache_key("details", signature)
        cached = self._get_cached(cache_key)
        if cached:
            logger.info("AI cache hit: scenario=details")
            return cached
        logger.info("AI cache miss: scenario=details")
        prompt = (
            "Поясни расширенные погодные данные простым и полезным русским языком.\n"
            "Требования: 4-5 коротких предложений, дружелюбно и по делу, без канцелярита, "
            "без сарказма, без клоунады, без дисклеймеров и без воды.\n"
            "Используй только переданные данные, ничего не выдумывай.\n"
            "Не перечисляй всё подряд: выдели 1-2 самых важных фактора сейчас и объясни, "
            "почему именно они важны прямо сейчас.\n\n"
            f"Локация: {city_label}\n"
            f"Погода: {weather_data}\n"
            f"Качество воздуха: {air_quality_data}"
        )
        model_answer = self._call_model(prompt, max_output_tokens=self.max_output_tokens_default)
        if model_answer:
            self._save_cached(cache_key, "details", model_answer, ttl_seconds=self.ttl_details_seconds)
            return model_answer
        logger.info("AI fallback used: scenario=details")
        return fallback

    def explain_weather_alert(self, location_label: str, alert_payload: dict) -> str:
        """Коротко объясняет уведомление о погоде с практичным советом."""
        fallback = self._fallback_weather_alert(location_label, alert_payload)
        signature = self._weather_alert_signature(location_label, alert_payload)
        cache_key = self._build_cache_key("ai_weather_alert", signature)
        cached = self._get_cached(cache_key)
        if cached:
            logger.info("AI cache hit: scenario=ai_weather_alert")
            return cached
        logger.info("AI cache miss: scenario=ai_weather_alert")
        prompt = (
            "Объясни погодное уведомление коротко и практично.\n"
            "Требования: русский язык, 1-2 коротких предложения, без воды, без дисклеймеров, "
            "без драматизации и без длинного прогноза.\n"
            "Используй только переданные данные, ничего не выдумывай.\n"
            "Дай конкретный совет для ближайшей активности (одежда, зонт, маршрут, время выхода).\n\n"
            f"Локация: {location_label}\n"
            f"Событие: {alert_payload}"
        )
        model_answer = self._call_model(prompt, max_output_tokens=120)
        if model_answer:
            self._save_cached(cache_key, "ai_weather_alert", model_answer, ttl_seconds=self.ttl_current_seconds)
            return model_answer
        logger.info("AI fallback used: scenario=ai_weather_alert")
        return fallback

    def compare_two_locations_current_with_ai(self, location_1_payload: dict, location_2_payload: dict) -> str:
        """Сравнивает текущую погоду двух локаций в deterministic-first режиме."""
        signature = self._compare_current_signature(location_1_payload, location_2_payload)
        cache_key = self._build_cache_key("ai_compare_current", signature)
        cached = self._get_cached(cache_key)
        if cached:
            logger.info("AI cache hit: scenario=ai_compare_current")
            return cached
        logger.info("AI cache miss: scenario=ai_compare_current")
        final_text = self._fallback_compare_current(location_1_payload, location_2_payload)
        self._save_cached(cache_key, "ai_compare_current", final_text, ttl_seconds=self.ttl_current_seconds)
        return final_text

    def compare_two_locations_forecast_day_with_ai(
        self,
        location_1_payload: dict,
        location_2_payload: dict,
        selected_day: str,
    ) -> str:
        """Сравнивает прогноз двух локаций на выбранный день детерминированно."""
        profile_1 = self._build_forecast_day_risk_profile(location_1_payload)
        profile_2 = self._build_forecast_day_risk_profile(location_2_payload)
        verdict = self._build_forecast_compare_verdict(profile_1, profile_2)
        signature = self._compare_forecast_day_signature(location_1_payload, location_2_payload, selected_day)
        cache_key = self._build_cache_key("ai_compare_forecast_day", signature)
        cached = self._get_cached(cache_key)
        if cached:
            logger.info("AI cache hit: scenario=ai_compare_forecast_day")
            return cached
        logger.info("AI cache miss: scenario=ai_compare_forecast_day")
        final_text = self._build_deterministic_compare_forecast_day_text(profile_1, profile_2, verdict)
        self._save_cached(cache_key, "ai_compare_forecast_day", final_text, ttl_seconds=self.ttl_forecast_seconds)
        return final_text

    def _call_model(self, prompt: str, *, max_output_tokens: int | None = None) -> str | None:
        """Вызывает OpenAI Responses API и возвращает текст ответа."""
        if self.client is None:
            return None
        try:
            response = self.client.responses.create(
                model=self.model,
                input=prompt,
                temperature=self.temperature,
                max_output_tokens=max_output_tokens or self.max_output_tokens_default,
            )
            text = (response.output_text or "").strip()
            return text or None
        except Exception as exc:
            logger.warning("Ошибка запроса к OpenAI Responses API: %s", exc)
            return None

    def _build_cache_key(self, scenario: str, signature: dict) -> str:
        """Собирает стабильный cache_key из сценария, модели и сигнатуры входа."""
        payload = {
            "scenario": scenario,
            "model": self.model,
            "signature": signature,
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return f"ai:{scenario}:{digest}"

    def _get_cached(self, cache_key: str) -> str | None:
        """Безопасно читает ответ из PostgreSQL-кэша."""
        try:
            return get_ai_cached_response(cache_key)
        except Exception as exc:
            logger.warning("Ошибка чтения AI-кэша PostgreSQL: %s", exc)
            return None

    def _save_cached(self, cache_key: str, scenario: str, text: str, *, ttl_seconds: int) -> None:
        """Безопасно сохраняет ответ в PostgreSQL-кэш."""
        try:
            save_ai_cached_response(
                cache_key,
                scenario,
                text,
                ttl_seconds=ttl_seconds,
            )
        except Exception as exc:
            logger.warning("Ошибка записи AI-кэша PostgreSQL: %s", exc)

    def _current_signature(self, city_label: str, weather_data: dict) -> dict:
        """Возвращает сигнатуру ключевых параметров текущей погоды."""
        main_data = weather_data.get("main", {}) if isinstance(weather_data, dict) else {}
        wind_data = weather_data.get("wind", {}) if isinstance(weather_data, dict) else {}
        weather_item = weather_data.get("weather", [{}])[0] if isinstance(weather_data, dict) else {}
        signature = {
            "location": self._normalize_location(city_label),
            "temp": self._round_step(main_data.get("temp"), step=0.5),
            "feels_like": self._round_step(main_data.get("feels_like"), step=0.5),
            "humidity": self._as_int(main_data.get("humidity")),
            "pressure": self._as_int(main_data.get("pressure")),
            "description": self._normalize_description(weather_item.get("description")),
            "wind_speed": self._round_step(wind_data.get("speed"), step=1.0),
        }
        logger.debug("AI current normalized signature: %s", signature)
        return signature

    def _forecast_signature(self, city_label: str, day_forecast_data: list[dict]) -> dict:
        """Возвращает сигнатуру дневного прогноза из ключевых полей каждого слота."""
        slots: list[dict] = []
        for item in day_forecast_data if isinstance(day_forecast_data, list) else []:
            if not isinstance(item, dict):
                continue
            main_data = item.get("main", {}) if isinstance(item.get("main"), dict) else {}
            weather_item = item.get("weather", [{}])[0] if isinstance(item.get("weather"), list) else {}
            slot = {
                "dt_txt": item.get("dt_txt"),
                "temp": main_data.get("temp"),
                "temp_min": main_data.get("temp_min"),
                "temp_max": main_data.get("temp_max"),
                "humidity": main_data.get("humidity"),
                "description": weather_item.get("description"),
                "pop": item.get("pop"),
            }
            slots.append(slot)
        return {
            "location": str(city_label).strip().lower(),
            "slots": slots,
        }

    def _details_signature(self, city_label: str, weather_data: dict, air_quality_data: dict | None) -> dict:
        """Возвращает сигнатуру расширенных данных погоды и воздуха."""
        main_data = weather_data.get("main", {}) if isinstance(weather_data, dict) else {}
        wind_data = weather_data.get("wind", {}) if isinstance(weather_data, dict) else {}
        weather_item = weather_data.get("weather", [{}])[0] if isinstance(weather_data, dict) else {}
        return {
            "location": str(city_label).strip().lower(),
            "temp": self._round_1(main_data.get("temp")),
            "feels_like": self._round_1(main_data.get("feels_like")),
            "humidity": self._as_int(main_data.get("humidity")),
            "pressure": self._as_int(main_data.get("pressure")),
            "visibility": weather_data.get("visibility") if isinstance(weather_data, dict) else None,
            "description": weather_item.get("description"),
            "wind_speed": self._round_1(wind_data.get("speed")),
            "wind_deg": wind_data.get("deg"),
            "air_quality": self._air_quality_signature(air_quality_data),
        }

    def _weather_alert_signature(self, location_label: str, alert_payload: dict) -> dict:
        """Сигнатура кэша для AI-объяснения погодного уведомления."""
        payload = alert_payload if isinstance(alert_payload, dict) else {}
        return {
            "mode": "alert",
            "format_version": "weather_alert_v1",
            "location": self._normalize_location(location_label),
            "event_type": self._normalize_location(payload.get("event_type")),
            "slot_ts_utc": self._as_int(payload.get("slot_ts_utc")),
            "slot_local": self._normalize_location(payload.get("slot_local")),
            "temperature": self._round_step(payload.get("temperature"), step=0.5),
            "feels_like": self._round_step(payload.get("feels_like"), step=0.5),
            "description": self._normalize_description(payload.get("description")),
            "wind_speed": self._round_step(payload.get("wind_speed"), step=1.0),
            "precip_probability": self._round_1(payload.get("precip_probability")),
        }

    def _compare_current_signature(self, payload_1: dict, payload_2: dict) -> dict:
        """Сигнатура кэша для AI-сравнения текущей погоды."""
        return {
            "mode": "current",
            "format_version": "deterministic_current_v1",
            "location_1": {
                "label": self._normalize_location(payload_1.get("city_label")),
                "fingerprint": self._build_location_fingerprint(payload_1),
            },
            "temp_1": self._round_step(payload_1.get("temperature"), step=0.5),
            "feels_1": self._round_step(payload_1.get("feels_like"), step=0.5),
            "desc_1": self._normalize_description(payload_1.get("description")),
            "humidity_1": self._as_int(payload_1.get("humidity")),
            "wind_1": self._round_step(payload_1.get("wind_speed"), step=1.0),
            "location_2": {
                "label": self._normalize_location(payload_2.get("city_label")),
                "fingerprint": self._build_location_fingerprint(payload_2),
            },
            "temp_2": self._round_step(payload_2.get("temperature"), step=0.5),
            "feels_2": self._round_step(payload_2.get("feels_like"), step=0.5),
            "desc_2": self._normalize_description(payload_2.get("description")),
            "humidity_2": self._as_int(payload_2.get("humidity")),
            "wind_2": self._round_step(payload_2.get("wind_speed"), step=1.0),
        }

    def _compare_forecast_day_signature(self, payload_1: dict, payload_2: dict, selected_day: str) -> dict:
        """Сигнатура кэша для AI-сравнения прогноза на выбранный день."""
        return {
            "mode": "date",
            "format_version": "deterministic_v3",
            "selected_day": self._normalize_location(selected_day),
            "location_1": {
                "label": self._normalize_location(payload_1.get("city_label")),
                "fingerprint": self._build_location_fingerprint(payload_1),
            },
            "min_temp_1": self._round_step(payload_1.get("min_temp"), step=0.5),
            "max_temp_1": self._round_step(payload_1.get("max_temp"), step=0.5),
            "dominant_desc_1": self._normalize_description(payload_1.get("dominant_description")),
            "rain_slots_1": self._as_int((payload_1.get("precipitation_signal") or {}).get("rain_slots")),
            "max_pop_1": self._round_1((payload_1.get("precipitation_signal") or {}).get("max_pop")),
            "location_2": {
                "label": self._normalize_location(payload_2.get("city_label")),
                "fingerprint": self._build_location_fingerprint(payload_2),
            },
            "min_temp_2": self._round_step(payload_2.get("min_temp"), step=0.5),
            "max_temp_2": self._round_step(payload_2.get("max_temp"), step=0.5),
            "dominant_desc_2": self._normalize_description(payload_2.get("dominant_description")),
            "rain_slots_2": self._as_int((payload_2.get("precipitation_signal") or {}).get("rain_slots")),
            "max_pop_2": self._round_1((payload_2.get("precipitation_signal") or {}).get("max_pop")),
        }

    def _build_location_fingerprint(self, payload: dict) -> str:
        """Собирает стабильный fingerprint локации для cache signature."""
        country = self._normalize_location(payload.get("country"))
        state = self._normalize_location(payload.get("state"))
        city = self._normalize_location(payload.get("city_label"))
        lat = self._round_coords(payload.get("lat"))
        lon = self._round_coords(payload.get("lon"))
        return f"{country}|{state}|{city}|{lat}|{lon}"

    def _round_1(self, value: object) -> float | None:
        """Округляет число до 1 знака после запятой."""
        if isinstance(value, (int, float)):
            return round(float(value), 1)
        return None

    def _round_step(self, value: object, *, step: float) -> float | None:
        """Округляет число до заданного шага."""
        if not isinstance(value, (int, float)):
            return None
        if step <= 0:
            return float(value)
        return round(round(float(value) / step) * step, 3)

    def _round_coords(self, value: object) -> str:
        """Округляет координату для fingerprint до 3 знаков."""
        if not isinstance(value, (int, float)):
            return ""
        return f"{round(float(value), 3):.3f}"

    def _postprocess_compare_forecast_day_text(
        self,
        text: str,
        payload_1: dict,
        payload_2: dict,
        *,
        verdict: dict | None = None,
    ) -> str:
        """Лёгкая нормализация тона и защита от одностороннего вывода в mixed-условиях."""
        cleaned = " ".join(str(text or "").split())
        if not cleaned:
            return cleaned

        # Убираем избыточно субъективные формулировки.
        replacements = {
            "приятнее": "практичнее",
            "спокойнее": "ровнее",
        }
        for src, dst in replacements.items():
            cleaned = re.sub(rf"\b{re.escape(src)}\b", dst, cleaned, flags=re.IGNORECASE)

        verdict_obj = verdict if isinstance(verdict, dict) else {}
        has_clear_winner = bool(verdict_obj.get("has_clear_winner"))
        city_1 = str(payload_1.get("city_label") or "локация 1")
        city_2 = str(payload_2.get("city_label") or "локация 2")
        if not has_clear_winner and "однозначного победителя нет" not in cleaned.lower():
            cleaned = (
                "Однозначного победителя нет. "
                f"{cleaned}"
            )

        # Если есть сильная рекомендация, но не упомянуты риски осадков/ветра, добавляем нейтральный safety-tail.
        strong_reco = any(x in cleaned.lower() for x in ("лучше", "выбирай", "удобнее"))
        risk_mentioned = any(x in cleaned.lower() for x in ("осад", "дожд", "снег", "ветер"))
        if strong_reco and not risk_mentioned:
            cleaned = f"{cleaned} Перед выбором проверь риск осадков и ветер ближе к дате."

        # Мягкая привязка к обеим локациям, если модель случайно потеряла одну из них.
        if city_1.lower() not in cleaned.lower() or city_2.lower() not in cleaned.lower():
            cleaned = f"{cleaned} Учитывай условия в {city_1} и {city_2} отдельно."

        return cleaned

    def _normalize_location(self, value: object) -> str:
        """Нормализует подпись локации для устойчивого cache key."""
        text = str(value or "").strip().lower()
        return " ".join(text.split())

    def _normalize_description(self, value: object) -> str:
        """Нормализует описание погоды."""
        text = str(value or "").strip().lower()
        return " ".join(text.split())

    def _as_int(self, value: object) -> int | None:
        """Приводит значение к целому числу, если это возможно."""
        if isinstance(value, (int, float)):
            return int(round(float(value)))
        return None

    def _air_quality_signature(self, air_quality_data: dict | None) -> dict | None:
        """Возвращает нормализованную сигнатуру ключевых компонентов воздуха."""
        if not isinstance(air_quality_data, dict):
            return None
        return {
            "pm2_5": self._round_1(air_quality_data.get("pm2_5")),
            "pm10": self._round_1(air_quality_data.get("pm10")),
            "no2": self._round_1(air_quality_data.get("no2")),
            "o3": self._round_1(air_quality_data.get("o3")),
            "so2": self._round_1(air_quality_data.get("so2")),
            "co": self._round_1(air_quality_data.get("co")),
        }

    def _fallback_current(self, city_label: str, weather_data: dict) -> str:
        """Детерминированный fallback для текущей погоды без OpenAI."""
        main_data = weather_data.get("main", {}) if isinstance(weather_data, dict) else {}
        weather_list = weather_data.get("weather", []) if isinstance(weather_data, dict) else []
        wind_data = weather_data.get("wind", {}) if isinstance(weather_data, dict) else {}
        temp = main_data.get("temp")
        feels_like = main_data.get("feels_like")
        description = (weather_list[0].get("description") if weather_list else "") or "без описания"
        wind_speed = wind_data.get("speed")
        desc_lower = str(description).lower()
        umbrella = (
            "Лучше взять зонт на всякий случай."
            if any(x in desc_lower for x in ("дожд", "лив", "гроза", "снег"))
            else "Скорее всего, можно обойтись без зонта."
        )
        if isinstance(feels_like, (int, float)):
            if feels_like <= 0:
                clothes = "Лучше одеться заметно теплее."
            elif feels_like <= 12:
                clothes = "Лучше накинуть что-то тёплое."
            else:
                clothes = "Можно выбрать более лёгкую одежду."
        else:
            clothes = "Одежду лучше выбрать по ощущениям на месте."
        comfort = (
            "На улице в целом довольно комфортно."
            if isinstance(temp, (int, float)) and -5 <= temp <= 25
            else "На улице может быть не слишком комфортно."
        )
        wind_note = f" Ветер около {wind_speed} м/с." if isinstance(wind_speed, (int, float)) else ""
        return (
            f"Сейчас в {city_label}: {description}, температура {temp if temp is not None else 'н/д'}°C, "
            f"ощущается как {feels_like if feels_like is not None else 'н/д'}°C.{wind_note} "
            f"{umbrella} {clothes} {comfort}"
        )

    def _fallback_day_forecast(self, city_label: str, day_items: list[dict]) -> str:
        """Детерминированный fallback для дневного прогноза без OpenAI."""
        if not isinstance(day_items, list) or not day_items:
            return f"По {city_label} пока недостаточно данных, чтобы дать понятную рекомендацию на день."

        rain_slots = 0
        best_slot = None
        best_temp = None
        for item in day_items:
            weather_desc = str(item.get("weather", [{}])[0].get("description", "")).lower()
            if any(x in weather_desc for x in ("дожд", "лив", "гроза", "снег")):
                rain_slots += 1
            temp = item.get("main", {}).get("temp")
            dt_txt = str(item.get("dt_txt") or "")
            if isinstance(temp, (int, float)) and (best_temp is None or temp > best_temp):
                best_temp = float(temp)
                best_slot = dt_txt

        rain_note = (
            "В течение дня возможны осадки, зонт лучше взять с собой."
            if rain_slots > 0
            else "Существенных осадков по прогнозу не видно."
        )
        slot_note = ""
        if best_slot and " " in best_slot:
            try:
                slot_dt = datetime.strptime(best_slot, "%Y-%m-%d %H:%M:%S")
                slot_note = f"Лучшее окно для выхода — около {slot_dt.strftime('%H:%M')}."
            except ValueError:
                slot_note = ""

        return (
            f"По {city_label}: {rain_note} "
            f"{slot_note} В течение дня температура может заметно меняться, "
            "поэтому перед выходом лучше быстро проверить прогноз ещё раз."
        ).strip()

    def _fallback_details(self, city_label: str, weather_data: dict, air_quality_data: dict | None) -> str:
        """Детерминированный fallback для расширенных данных без OpenAI."""
        main_data = weather_data.get("main", {}) if isinstance(weather_data, dict) else {}
        wind_data = weather_data.get("wind", {}) if isinstance(weather_data, dict) else {}
        humidity = main_data.get("humidity")
        visibility = weather_data.get("visibility") if isinstance(weather_data, dict) else None
        wind_speed = wind_data.get("speed")
        pm25 = air_quality_data.get("pm2_5") if isinstance(air_quality_data, dict) else None

        humidity_note = (
            "Влажность высокая, поэтому воздух может ощущаться тяжёлым."
            if isinstance(humidity, (int, float)) and humidity >= 75
            else "Влажность сейчас в комфортном диапазоне."
        )
        wind_note = (
            f"Ветер около {wind_speed} м/с."
            if isinstance(wind_speed, (int, float))
            else "Данные о ветре ограничены."
        )
        visibility_note = (
            f"Видимость примерно {int(visibility)} м."
            if isinstance(visibility, (int, float))
            else "Данные по видимости ограничены."
        )
        if isinstance(pm25, (int, float)):
            air_note = "Качество воздуха в целом нормальное." if pm25 <= 35 else "Качество воздуха сейчас ниже комфортного."
        else:
            air_note = "Данные о качестве воздуха сейчас неполные."

        return (
            f"По {city_label}: {humidity_note} {wind_note} {visibility_note} {air_note} "
            "Если планируешь долгую прогулку, ориентируйся в первую очередь на эти факторы."
        )

    def _fallback_compare_current(self, payload_1: dict, payload_2: dict) -> str:
        """Короткий практичный fallback сравнения текущей погоды без субъективных оценок."""
        city_1_label = str(payload_1.get("city_label") or "Локация 1")
        city_2_label = str(payload_2.get("city_label") or "Локация 2")
        name_1 = self._get_short_location_name(city_1_label)
        name_2 = self._get_short_location_name(city_2_label)

        temp_1 = payload_1.get("temperature")
        temp_2 = payload_2.get("temperature")
        wind_1 = payload_1.get("wind_speed")
        wind_2 = payload_2.get("wind_speed")
        hum_1 = payload_1.get("humidity")
        hum_2 = payload_2.get("humidity")
        desc_1 = str(payload_1.get("description") or "").lower()
        desc_2 = str(payload_2.get("description") or "").lower()

        rain_markers = ("дожд", "лив", "гроза", "снег")
        precip_1 = any(m in desc_1 for m in rain_markers)
        precip_2 = any(m in desc_2 for m in rain_markers)

        def _signed(a: object, b: object) -> float | None:
            if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                return float(a) - float(b)
            return None

        d_temp = _signed(temp_1, temp_2)
        d_wind = _signed(wind_1, wind_2)
        d_hum = _signed(hum_1, hum_2)

        warmer = None
        if d_temp is not None and abs(d_temp) >= 1.0:
            warmer = 1 if d_temp > 0 else 2
        calmer = None
        if d_wind is not None and abs(d_wind) >= 1.0:
            calmer = 1 if d_wind < 0 else 2
        drier = None
        if d_hum is not None and abs(d_hum) >= 8:
            drier = 1 if d_hum < 0 else 2
        no_rain = None
        if precip_1 and not precip_2:
            no_rain = 2
        elif precip_2 and not precip_1:
            no_rain = 1

        signals = [s for s in (warmer, calmer, drier, no_rain) if s is not None]
        adv_1 = sum(1 for s in signals if s == 1)
        adv_2 = sum(1 for s in signals if s == 2)

        near_identical = (
            no_rain is None
            and (d_temp is None or abs(d_temp) < 1.0)
            and (d_wind is None or abs(d_wind) < 1.5)
            and (d_hum is None or abs(d_hum) < 10)
        )

        clear_winner = None
        if not near_identical:
            if adv_1 >= 2 and adv_2 == 0:
                clear_winner = 1
            elif adv_2 >= 2 and adv_1 == 0:
                clear_winner = 2

        if clear_winner is not None:
            return self._render_compare_current_clear(
                clear_winner,
                city_1_label, city_2_label,
                name_1, name_2,
                warmer, calmer, drier, no_rain,
            )
        if near_identical:
            return self._render_compare_current_near_identical(
                name_1, name_2, d_wind, d_hum,
            )
        return self._render_compare_current_mixed(
            city_1_label, city_2_label,
            name_1, name_2,
            warmer, calmer, drier, no_rain,
        )

    def _render_compare_current_clear(
        self,
        winner_idx: int,
        city_1_label: str,
        city_2_label: str,
        name_1: str,
        name_2: str,
        warmer: int | None,
        calmer: int | None,
        drier: int | None,
        no_rain: int | None,
    ) -> str:
        """Рендер ветки compare current с явным лидером."""
        if winner_idx == 1:
            win_label, los_label = city_1_label, city_2_label
            win_name, los_name = name_1, name_2
        else:
            win_label, los_label = city_2_label, city_1_label
            win_name, los_name = name_2, name_1

        pluses: list[str] = []
        if warmer == winner_idx:
            pluses.append("чуть теплее")
        if calmer == winner_idx:
            pluses.append("ветер слабее")
        if drier == winner_idx:
            pluses.append("воздух суше")
        if no_rain == winner_idx:
            pluses.append("без осадков")
        if not pluses:
            pluses.append("условия ровнее")
        win_inner = self._join_enumeration(pluses[:2])

        minuses: list[str] = []
        if warmer == winner_idx:
            minuses.append("прохладнее")
        if calmer == winner_idx:
            minuses.append("ветер заметнее")
        if drier == winner_idx:
            minuses.append("воздух более влажный")
        if no_rain == winner_idx:
            minuses.append("возможны осадки")
        if not minuses:
            minuses.append("условия менее ровные")
        los_inner = self._join_enumeration(minuses[:2])

        if calmer == winner_idx:
            extra_inner = "лучше одеться теплее из-за ветра."
        elif no_rain == winner_idx:
            extra_inner = "стоит взять зонт."
        elif warmer == winner_idx:
            extra_inner = "лучше одеться теплее."
        else:
            extra_inner = "стоит подбирать одежду осторожнее."

        line_1 = self._speak_about(win_label, f"сейчас {win_inner}.")
        line_2 = self._speak_about(los_label, f"{los_inner}.")
        line_3 = f"Для короткой прогулки практичнее {win_name}."
        line_4 = self._speak_about(los_label, extra_inner)
        return "\n".join([line_1, line_2, line_3, line_4])

    def _render_compare_current_near_identical(
        self,
        name_1: str,
        name_2: str,
        d_wind: float | None,
        d_hum: float | None,
    ) -> str:
        """Рендер ветки compare current, когда погода почти одинаковая."""
        wind_diff_visible = isinstance(d_wind, (int, float)) and abs(float(d_wind)) >= 0.7
        hum_diff_visible = isinstance(d_hum, (int, float)) and abs(float(d_hum)) >= 5

        if wind_diff_visible:
            detail = "Температура и влажность близкие, заметнее всего отличается ветер."
            calmer_name = name_1 if float(d_wind) <= 0 else name_2
            prefer = f"Если важен меньший ветер, практичнее {calmer_name}."
        elif hum_diff_visible:
            detail = "Температура и ветер близкие, заметнее всего отличается влажность."
            drier_name = name_1 if float(d_hum) <= 0 else name_2
            prefer = f"Если важен сухой воздух, практичнее {drier_name}."
        else:
            detail = "Температура, влажность и ветер — всё очень близко."
            prefer = "Разница настолько небольшая, что ориентируйся на удобство маршрута."

        return "\n".join([
            "Погода почти одинаковая.",
            detail,
            "Для прогулки выбирай по маршруту.",
            prefer,
        ])

    def _render_compare_current_mixed(
        self,
        city_1_label: str,
        city_2_label: str,
        name_1: str,
        name_2: str,
        warmer: int | None,
        calmer: int | None,
        drier: int | None,
        no_rain: int | None,
    ) -> str:
        """Рендер ветки compare current, когда у каждой локации есть плюсы и минусы."""
        if warmer is not None:
            warmer_label = city_1_label if warmer == 1 else city_2_label
            warmer_name = name_1 if warmer == 1 else name_2
            cooler_label = city_2_label if warmer == 1 else city_1_label
            cooler_name = name_2 if warmer == 1 else name_1
            other_idx = 3 - warmer
        else:
            warmer_label = city_1_label
            warmer_name = name_1
            cooler_label = city_2_label
            cooler_name = name_2
            other_idx = 2

        warmer_minuses: list[str] = []
        if drier == other_idx:
            warmer_minuses.append("влажнее")
        if calmer == other_idx:
            warmer_minuses.append("ветер чуть сильнее")
        if no_rain == other_idx:
            warmer_minuses.append("возможны осадки")
        cooler_pluses: list[str] = []
        if drier == other_idx:
            cooler_pluses.append("воздух суше")
        if calmer == other_idx:
            cooler_pluses.append("ветер слабее")
        if no_rain == other_idx:
            cooler_pluses.append("без осадков")

        if warmer is not None:
            warmer_inner = (
                f"теплее, но {self._join_enumeration(warmer_minuses[:2])}."
                if warmer_minuses
                else "теплее, но ровных плюсов меньше."
            )
            cooler_inner = (
                f"прохладнее, зато {self._join_enumeration(cooler_pluses[:2])}."
                if cooler_pluses
                else "прохладнее, зато без сюрпризов."
            )
            line_warmer = self._speak_about(warmer_label, warmer_inner)
            line_cooler = self._speak_about(cooler_label, cooler_inner)
        else:
            line_warmer = self._speak_about(
                warmer_label,
                "плюсы и минусы примерно равны.",
            )
            line_cooler = self._speak_about(
                cooler_label,
                "плюсы и минусы примерно равны.",
            )

        drier_name = None
        if drier == 1:
            drier_name = name_1
        elif drier == 2:
            drier_name = name_2
        calmer_name = None
        if calmer == 1:
            calmer_name = name_1
        elif calmer == 2:
            calmer_name = name_2

        if warmer is not None and drier_name and drier_name != warmer_name:
            trip_text = (
                f"Для прогулки выбирай по приоритету: тепло — {warmer_name}, "
                f"суше и ровнее — {drier_name}."
            )
        elif warmer is not None and calmer_name and calmer_name != warmer_name:
            trip_text = (
                f"Для прогулки выбирай по приоритету: тепло — {warmer_name}, "
                f"меньше ветра — {calmer_name}."
            )
        else:
            trip_text = "Для прогулки ориентируйся на удобство маршрута."

        return "\n".join([
            "Однозначного лидера нет.",
            line_warmer,
            line_cooler,
            trip_text,
        ])

    def _fallback_weather_alert(self, location_label: str, alert_payload: dict) -> str:
        """Детерминированный fallback для погодного уведомления (1-2 коротких предложения)."""
        payload = alert_payload if isinstance(alert_payload, dict) else {}
        slot_local = str(payload.get("slot_local") or "").strip()
        description = str(payload.get("description") or "").strip().lower()
        event_type = str(payload.get("event_type") or "").strip().lower()
        temperature = payload.get("temperature")
        feels_like = payload.get("feels_like")
        wind_speed = payload.get("wind_speed")
        precip_probability = payload.get("precip_probability")

        if any(x in description for x in ("дожд", "лив", "гроза", "снег")) or event_type == "precipitation":
            when = f"К {slot_local} " if slot_local else "Скоро "
            tail = ""
            if isinstance(precip_probability, (int, float)) and float(precip_probability) >= 0.6:
                tail = " Осадки выглядят вероятными."
            return f"{when}ожидаются осадки, лучше взять зонт или дождевик.{tail}".strip()

        if event_type == "wind" or (isinstance(wind_speed, (int, float)) and float(wind_speed) >= 8):
            speed_hint = (
                f" до {round(float(wind_speed), 1)} м/с"
                if isinstance(wind_speed, (int, float))
                else ""
            )
            return (
                f"К {slot_local} ветер усилится{speed_hint}, на открытых участках будет менее комфортно."
                if slot_local
                else f"Ветер усилится{speed_hint}, на открытых участках будет менее комфортно."
            ) + " Для прогулки лучше выбрать более защищённый маршрут."

        if event_type == "temperature_drop":
            feels_note = ""
            if isinstance(feels_like, (int, float)):
                feels_note = f" По ощущениям около {round(float(feels_like), 1)}°C."
            return (
                "Температура снизится, лучше взять дополнительный верхний слой одежды."
                f"{feels_note}"
            ).strip()

        if isinstance(temperature, (int, float)) and isinstance(feels_like, (int, float)):
            if float(feels_like) <= float(temperature) - 2.0:
                return (
                    f"К {slot_local} может ощущаться прохладнее фактической температуры, лучше одеться теплее."
                    if slot_local
                    else "Может ощущаться прохладнее фактической температуры, лучше одеться теплее."
                )

        if slot_local and description:
            return f"К {slot_local} ожидается {description}, лучше скорректировать маршрут и одежду под условия."
        if description:
            return f"Ожидается {description}, лучше заранее учесть это в планах на выход."
        return ""

    def _fallback_compare_forecast_day(self, payload_1: dict, payload_2: dict, selected_day: str) -> str:
        """Fallback сравнения прогноза двух локаций на выбранную дату."""
        profile_1 = self._build_forecast_day_risk_profile(payload_1)
        profile_2 = self._build_forecast_day_risk_profile(payload_2)
        verdict = self._build_forecast_compare_verdict(profile_1, profile_2)
        return self._build_deterministic_compare_forecast_day_text(profile_1, profile_2, verdict)

    def _build_forecast_day_risk_profile(self, payload: dict) -> dict:
        """Строит детерминированный профиль погодных рисков для compare-by-date."""
        city_label = str(payload.get("city_label") or "Локация")
        temp_min = payload.get("min_temp")
        temp_max = payload.get("max_temp")
        temp_avg = None
        if isinstance(temp_min, (int, float)) and isinstance(temp_max, (int, float)):
            temp_avg = (float(temp_min) + float(temp_max)) / 2.0

        if isinstance(temp_avg, (int, float)):
            if temp_avg < 5:
                temperature_note = "холодно"
                temp_penalty = 2.2
            elif temp_avg < 15:
                temperature_note = "прохладно"
                temp_penalty = 1.0
            elif temp_avg <= 24:
                temperature_note = "умеренно тепло"
                temp_penalty = 0.2
            elif temp_avg > 28:
                temperature_note = "жарко"
                temp_penalty = 1.8
            else:
                temperature_note = "умеренно тепло"
                temp_penalty = 0.6
        else:
            temperature_note = "температура не уточнена"
            temp_penalty = 1.0

        dominant_desc = self._normalize_description(payload.get("dominant_description"))
        pop_raw = (payload.get("precipitation_signal") or {}).get("max_pop")
        max_pop = float(pop_raw) if isinstance(pop_raw, (int, float)) else None
        has_snow = "снег" in dominant_desc
        has_rain = any(x in dominant_desc for x in ("дожд", "лив", "гроза"))
        if has_snow and has_rain:
            precipitation_type = "mixed"
        elif has_snow:
            precipitation_type = "snow"
        elif has_rain:
            precipitation_type = "rain"
        elif dominant_desc:
            precipitation_type = "none"
        else:
            precipitation_type = "unknown"

        if isinstance(max_pop, (int, float)):
            if max_pop >= 0.7:
                precipitation_risk = "high"
                precip_penalty = 3.2
            elif max_pop >= 0.35:
                precipitation_risk = "medium"
                precip_penalty = 1.8
            else:
                precipitation_risk = "low"
                precip_penalty = 0.5
        else:
            precipitation_risk = "medium" if precipitation_type in {"rain", "snow", "mixed"} else "low"
            precip_penalty = 1.2 if precipitation_risk == "medium" else 0.4

        # Снег при около-нулевой/плюсовой температуре считаем дополнительным UX-риском.
        if precipitation_type == "snow" and isinstance(temp_avg, (int, float)) and temp_avg >= -1:
            precip_penalty += 0.8

        precip_note_map = {
            ("high", "snow"): "высокий шанс снега",
            ("high", "rain"): "высокий шанс дождя",
            ("high", "mixed"): "высокий шанс осадков",
            ("high", "none"): "высокий шанс осадков",
            ("medium", "snow"): "возможен снег",
            ("medium", "rain"): "возможен дождь",
            ("medium", "mixed"): "возможны осадки",
            ("medium", "none"): "возможны осадки",
            ("low", "snow"): "снег маловероятен",
            ("low", "rain"): "дождь маловероятен",
            ("low", "mixed"): "осадки маловероятны",
            ("low", "none"): "без существенных осадков",
        }
        precipitation_note = precip_note_map.get((precipitation_risk, precipitation_type), "без существенных осадков")

        wind_signal = payload.get("wind_signal") if isinstance(payload, dict) else {}
        wind_avg = wind_signal.get("avg_speed") if isinstance(wind_signal, dict) else None
        wind_gust = wind_signal.get("max_speed") if isinstance(wind_signal, dict) else None
        wind_avg_f = float(wind_avg) if isinstance(wind_avg, (int, float)) else None
        wind_gust_f = float(wind_gust) if isinstance(wind_gust, (int, float)) else None

        if (
            (isinstance(wind_avg_f, (int, float)) and wind_avg_f >= 8.0)
            or (isinstance(wind_gust_f, (int, float)) and wind_gust_f >= 12.0)
        ):
            wind_risk = "high"
            wind_penalty = 2.4
            wind_note = "ветер заметно сильный"
        elif (
            (isinstance(wind_avg_f, (int, float)) and wind_avg_f >= 5.0)
            or (isinstance(wind_gust_f, (int, float)) and wind_gust_f >= 8.0)
        ):
            wind_risk = "medium"
            wind_penalty = 1.3
            wind_note = "ветер ощутимый"
        elif isinstance(wind_avg_f, (int, float)) or isinstance(wind_gust_f, (int, float)):
            wind_risk = "low"
            wind_penalty = 0.4
            wind_note = "ветер умеренный"
        else:
            wind_risk = "medium"
            wind_penalty = 1.0
            wind_note = "ветер не уточнён"

        risk_score = temp_penalty + precip_penalty + wind_penalty
        comfort_score = max(0.0, 10.0 - risk_score)
        summary = f"{temperature_note}; {precipitation_note}; {wind_note}"

        return {
            "city_label": city_label,
            "temp_min": self._round_1(temp_min),
            "temp_max": self._round_1(temp_max),
            "avg_temp": self._round_1(temp_avg),
            "temperature_note": temperature_note,
            "precipitation_type": precipitation_type,
            "precipitation_risk": precipitation_risk,
            "precipitation_note": precipitation_note,
            "wind_risk": wind_risk,
            "wind_note": wind_note,
            "comfort_score": round(comfort_score, 2),
            "risk_score": round(risk_score, 2),
            "summary": summary,
        }

    def _build_forecast_compare_verdict(self, profile_1: dict, profile_2: dict) -> dict:
        """Строит детерминированный verdict сравнения двух risk-профилей."""
        city_1 = str(profile_1.get("city_label") or "Локация 1")
        city_2 = str(profile_2.get("city_label") or "Локация 2")

        risk_1 = float(profile_1.get("risk_score") or 0.0)
        risk_2 = float(profile_2.get("risk_score") or 0.0)
        avg_1 = profile_1.get("avg_temp")
        avg_2 = profile_2.get("avg_temp")

        warmer_city = None
        if isinstance(avg_1, (int, float)) and isinstance(avg_2, (int, float)):
            if abs(float(avg_1) - float(avg_2)) >= 0.7:
                warmer_city = city_1 if float(avg_1) > float(avg_2) else city_2

        pop_rank = {"low": 0, "medium": 1, "high": 2}
        precip_rank_1 = pop_rank.get(str(profile_1.get("precipitation_risk") or "medium"), 1)
        precip_rank_2 = pop_rank.get(str(profile_2.get("precipitation_risk") or "medium"), 1)
        drier_city = None
        if precip_rank_1 != precip_rank_2:
            drier_city = city_1 if precip_rank_1 < precip_rank_2 else city_2

        wind_rank = {"low": 0, "medium": 1, "high": 2}
        wind_risk_1 = wind_rank.get(str(profile_1.get("wind_risk") or "medium"), 1)
        wind_risk_2 = wind_rank.get(str(profile_2.get("wind_risk") or "medium"), 1)
        calmer_city = None
        if wind_risk_1 != wind_risk_2:
            calmer_city = city_1 if wind_risk_1 < wind_risk_2 else city_2

        advantages_1 = 0
        advantages_2 = 0
        if warmer_city == city_1:
            advantages_1 += 1
        elif warmer_city == city_2:
            advantages_2 += 1
        if drier_city == city_1:
            advantages_1 += 1
        elif drier_city == city_2:
            advantages_2 += 1
        if calmer_city == city_1:
            advantages_1 += 1
        elif calmer_city == city_2:
            advantages_2 += 1

        precip_high_1 = str(profile_1.get("precipitation_risk")) == "high"
        precip_high_2 = str(profile_2.get("precipitation_risk")) == "high"
        wind_high_1 = str(profile_1.get("wind_risk")) == "high"
        wind_high_2 = str(profile_2.get("wind_risk")) == "high"

        severe_minus_1 = precip_high_1 or wind_high_1
        severe_minus_2 = precip_high_2 or wind_high_2

        winner = None
        if advantages_1 >= 2 and advantages_1 > advantages_2 and not severe_minus_1:
            winner = city_1
        elif advantages_2 >= 2 and advantages_2 > advantages_1 and not severe_minus_2:
            winner = city_2

        # Mixed conditions: одна локация теплее, но другая суше/тише.
        mixed_conditions = bool(
            warmer_city
            and (drier_city or calmer_city)
            and warmer_city not in {drier_city, calmer_city}
        )
        if mixed_conditions:
            winner = None

        has_clear_winner = winner is not None

        tradeoffs: list[str] = []
        if warmer_city:
            tradeoffs.append(f"в {warmer_city} теплее")
        if drier_city:
            tradeoffs.append(f"в {drier_city} ниже риск осадков")
        if calmer_city:
            tradeoffs.append(f"в {calmer_city} слабее ветер")
        main_tradeoff = "; ".join(tradeoffs) if tradeoffs else "условия в целом близкие"

        if has_clear_winner and isinstance(winner, str):
            walk_recommendation = f"Для прогулки практичнее {winner}: меньше погодных рисков."
            trip_recommendation = f"Для поездки практичнее {winner}."
            ai_instruction = f"Есть явный лидер: {winner}. Укажи это, но кратко назови риски второй локации."
        else:
            walk_city = drier_city or calmer_city or winner
            trip_city = drier_city or winner
            walk_recommendation = (
                f"Для прогулки практичнее {walk_city}."
                if isinstance(walk_city, str) and walk_city
                else "Для прогулки ориентируйся на меньший риск осадков и ветра."
            )
            trip_recommendation = (
                f"Для поездки практичнее {trip_city}."
                if isinstance(trip_city, str) and trip_city
                else "Для поездки ориентируйся на риск осадков."
            )
            ai_instruction = (
                "Однозначного победителя нет. Сформулируй компромиссы и дай отдельные практичные советы "
                "для прогулки и поездки."
            )

        return {
            "has_clear_winner": has_clear_winner,
            "winner": winner,
            "warmer_city": warmer_city,
            "drier_city": drier_city,
            "calmer_city": calmer_city,
            "mixed_conditions": mixed_conditions,
            "main_tradeoff": main_tradeoff,
            "walk_recommendation": walk_recommendation,
            "trip_recommendation": trip_recommendation,
            "ai_instruction": ai_instruction,
        }

    def _get_short_location_name(self, city_label: str) -> str:
        """Возвращает короткое имя локации без страны/региона в скобках."""
        label = str(city_label or "").strip()
        if not label:
            return "Локация"
        if "(" in label:
            return label.split("(", 1)[0].strip()
        return label

    def _get_prepositional_location_name(self, city_label: str) -> str | None:
        """Возвращает безопасную форму предложного падежа.

        Возвращает None, если форма неизвестна — в этом случае caller должен
        использовать безопасный формат с двоеточием, чтобы не писать "В Москва".
        """
        short = self._get_short_location_name(city_label)
        key = short.strip().lower()
        if not key:
            return None
        mapping = {
            "москва": "Москве",
            "санкт-петербург": "Санкт-Петербурге",
            "петербург": "Петербурге",
            "питер": "Питере",
            "тольятти": "Тольятти",
            "сочи": "Сочи",
            "астана": "Астане",
        }
        return mapping.get(key)

    def _speak_about(self, city_label: str, inner: str) -> str:
        """Строит фразу "В <Prep> <inner>" при известной форме, иначе "<Имя>: <inner>"."""
        prep = self._get_prepositional_location_name(city_label)
        if prep:
            return f"В {prep} {inner}"
        name = self._get_short_location_name(city_label)
        return f"{name}: {inner}"

    def _join_enumeration(self, parts: list[str]) -> str:
        """Объединяет элементы через запятую и союз 'и' перед последним."""
        clean = [p for p in parts if p]
        if not clean:
            return ""
        if len(clean) == 1:
            return clean[0]
        return ", ".join(clean[:-1]) + " и " + clean[-1]

    def _build_city_tradeoff_line(self, base: dict, other: dict) -> str:
        """Формирует строку вида: '<Город>: плюс, но минус.'"""
        city = self._get_short_location_name(str(base.get("city_label") or "Локация"))
        avg_base = base.get("avg_temp")
        avg_other = other.get("avg_temp")
        precip_rank = {"low": 0, "medium": 1, "high": 2}
        wind_rank = {"low": 0, "medium": 1, "high": 2}
        p_base = precip_rank.get(str(base.get("precipitation_risk") or "medium"), 1)
        p_other = precip_rank.get(str(other.get("precipitation_risk") or "medium"), 1)
        w_base = wind_rank.get(str(base.get("wind_risk") or "medium"), 1)
        w_other = wind_rank.get(str(other.get("wind_risk") or "medium"), 1)

        plus = None
        minus = None
        if p_base < p_other:
            plus = "меньше риск осадков"
        elif p_base > p_other:
            minus = "выше шанс осадков"
        if plus is None and isinstance(avg_base, (int, float)) and isinstance(avg_other, (int, float)):
            if float(avg_base) - float(avg_other) >= 0.7:
                plus = "немного теплее"
            elif float(avg_other) - float(avg_base) >= 0.7:
                minus = "чуть прохладнее"
        if plus is None and w_base < w_other:
            plus = "ветер слабее"
        if minus is None and w_base > w_other:
            minus = "ветер заметнее"

        if plus and minus:
            return f"{city}: {plus}, но {minus}."
        if plus:
            return f"{city}: {plus}."
        if minus:
            return f"{city}: {minus}."
        return f"{city}: разница по ключевым факторам почти не ощущается."

    def _temperature_comparison_phrase(self, base: dict, other: dict) -> str:
        """Сравнение температуры для одной локации относительно другой."""
        avg_base = base.get("avg_temp")
        avg_other = other.get("avg_temp")
        if not isinstance(avg_base, (int, float)) or not isinstance(avg_other, (int, float)):
            return "разница по температуре почти не ощущается"
        delta = float(avg_base) - float(avg_other)
        if delta >= 2.0:
            return "заметно теплее"
        if delta >= 0.7:
            return "чуть теплее"
        if delta <= -2.0:
            return "заметно прохладнее"
        if delta <= -0.7:
            return "чуть прохладнее"
        return "разница по температуре почти не ощущается"

    def _precipitation_comparison_phrase(self, base: dict, other: dict) -> str:
        """Сравнение осадков для одной локации относительно другой."""
        rank = {"low": 0, "medium": 1, "high": 2}
        base_rank = rank.get(str(base.get("precipitation_risk") or "medium"), 1)
        other_rank = rank.get(str(other.get("precipitation_risk") or "medium"), 1)
        base_type = str(base.get("precipitation_type") or "unknown")
        if base_rank < other_rank:
            return "ниже риск осадков"
        if base_rank > other_rank:
            if base_type == "snow":
                return "ожидается снег"
            if base_type == "rain":
                return "выше шанс дождя"
            return "выше риск осадков"
        note = str(base.get("precipitation_note") or "")
        if "снег" in note:
            return "возможен снег"
        if "дожд" in note:
            return "возможен дождь"
        if "без существенных" in note:
            return "без существенных осадков"
        return "возможны осадки"

    def _wind_comparison_phrase(self, base: dict, other: dict) -> str:
        """Сравнение ветра для одной локации относительно другой."""
        rank = {"low": 0, "medium": 1, "high": 2}
        base_rank = rank.get(str(base.get("wind_risk") or "medium"), 1)
        other_rank = rank.get(str(other.get("wind_risk") or "medium"), 1)
        if base_rank < other_rank:
            return "ветер слабее"
        if base_rank > other_rank:
            return "ветер заметнее"
        note = str(base.get("wind_note") or "")
        if "сильный" in note or "ощутимый" in note:
            return "ветер ощутимый"
        return "ветер умеренный"

    def _build_deterministic_compare_forecast_day_text(self, profile_1: dict, profile_2: dict, verdict: dict) -> str:
        """Строит финальный compare-by-date текст человеческим языком, с 3 ветками."""
        city_1_full = str(profile_1.get("city_label") or "Локация 1")
        city_2_full = str(profile_2.get("city_label") or "Локация 2")
        name_1 = self._get_short_location_name(city_1_full)
        name_2 = self._get_short_location_name(city_2_full)

        risk_1 = float(profile_1.get("risk_score") or 0.0)
        risk_2 = float(profile_2.get("risk_score") or 0.0)
        risk_diff = abs(risk_1 - risk_2)

        same_temp_band = str(profile_1.get("temperature_note")) == str(profile_2.get("temperature_note"))
        same_precip_risk = str(profile_1.get("precipitation_risk")) == str(profile_2.get("precipitation_risk"))
        near_identical = risk_diff < 0.8 or (
            same_temp_band and same_precip_risk and risk_diff < 1.5
        )

        warmer_name = None
        warmer_full = verdict.get("warmer_city")
        if isinstance(warmer_full, str) and warmer_full:
            warmer_name = self._get_short_location_name(warmer_full)
        if not verdict.get("has_clear_winner") and warmer_name not in {name_1, name_2}:
            near_identical = True

        if verdict.get("has_clear_winner"):
            return self._render_compare_forecast_clear_winner(
                profile_1, profile_2, verdict,
                city_1_full, city_2_full,
                name_1, name_2,
            )
        if near_identical:
            return self._render_compare_forecast_near_identical(
                profile_1, profile_2,
                city_1_full, city_2_full,
                name_1, name_2,
            )
        return self._render_compare_forecast_mixed(
            profile_1, profile_2, verdict,
            city_1_full, city_2_full,
            name_1, name_2,
            risk_1, risk_2,
        )

    def _render_compare_forecast_clear_winner(
        self,
        profile_1: dict,
        profile_2: dict,
        verdict: dict,
        city_1_full: str,
        city_2_full: str,
        name_1: str,
        name_2: str,
    ) -> str:
        """Рендер compare-by-date: есть явный лидер."""
        winner_full = str(verdict.get("winner") or "")
        winner_name = self._get_short_location_name(winner_full)
        if winner_name == name_1:
            win_profile, los_profile = profile_1, profile_2
            win_label, los_label = city_1_full, city_2_full
            win_name, los_name = name_1, name_2
        else:
            win_profile, los_profile = profile_2, profile_1
            win_label, los_label = city_2_full, city_1_full
            win_name, los_name = name_2, name_1

        warmer_name = self._get_short_location_name(str(verdict.get("warmer_city") or ""))
        drier_name = self._get_short_location_name(str(verdict.get("drier_city") or ""))
        calmer_name = self._get_short_location_name(str(verdict.get("calmer_city") or ""))

        pluses: list[str] = []
        if warmer_name == win_name:
            pluses.append("теплее")
        if drier_name == win_name:
            pluses.append("суше")
        if calmer_name == win_name:
            pluses.append("с более слабым ветром")
        if not pluses:
            pluses.append("условия ровнее")

        los_temp = self._temperature_comparison_phrase(los_profile, win_profile)
        if los_temp in {"заметно прохладнее", "чуть прохладнее"}:
            temp_opener = los_temp
        elif "прохладнее" in los_temp:
            temp_opener = "прохладнее"
        else:
            temp_opener = "уступает по сумме условий"

        los_precip_type = str(los_profile.get("precipitation_type") or "")
        los_precip_risk = str(los_profile.get("precipitation_risk") or "")
        tail_parts: list[str] = []
        if los_precip_type == "snow" and los_precip_risk in {"medium", "high"}:
            tail_parts.append("там ожидается снег")
        elif los_precip_type == "rain" and los_precip_risk in {"medium", "high"}:
            tail_parts.append("там возможен дождь")
        elif los_precip_risk == "high":
            tail_parts.append("высокий шанс осадков")

        wind_phrase = self._wind_comparison_phrase(los_profile, win_profile)
        if wind_phrase in {"ветер заметнее", "ветер ощутимый"}:
            tail_parts.append("ветер ощутимее")

        if not tail_parts:
            tail_parts.append("условия менее ровные")

        los_line = f"{los_name} {temp_opener}: " + " и ".join(tail_parts[:2]) + "."

        win_line = f"{win_name} " + self._join_enumeration(pluses[:3]) + "."
        trip_line = f"Для прогулки и поездки практичнее {win_name}."

        extra_line = self._speak_about(
            los_label,
            "стоит закладывать тёплую одежду и риск осадков.",
        )

        return (
            f"Лучше выглядит {win_name}.\n\n"
            f"{win_line}\n"
            f"{los_line}\n\n"
            f"{trip_line}\n"
            f"{extra_line}"
        )

    def _render_compare_forecast_near_identical(
        self,
        profile_1: dict,
        profile_2: dict,
        city_1_full: str,
        city_2_full: str,
        name_1: str,
        name_2: str,
    ) -> str:
        """Рендер compare-by-date: погода почти одинаковая."""
        wind_rank = {"low": 0, "medium": 1, "high": 2}
        w1 = wind_rank.get(str(profile_1.get("wind_risk") or "medium"), 1)
        w2 = wind_rank.get(str(profile_2.get("wind_risk") or "medium"), 1)

        if w1 != w2:
            if w1 > w2:
                windier_label, calmer_label = city_1_full, city_2_full
                windier_name, calmer_name = name_1, name_2
            else:
                windier_label, calmer_label = city_2_full, city_1_full
                windier_name, calmer_name = name_2, name_1
            windier_phrase = self._speak_about(windier_label, "ветер чуть сильнее")
            calmer_phrase_inner = "разница по температуре почти не ощущается"
            prep_calmer = self._get_prepositional_location_name(calmer_label)
            if prep_calmer:
                calmer_phrase = f"в {prep_calmer} {calmer_phrase_inner}"
            else:
                calmer_phrase = f"{calmer_name}: {calmer_phrase_inner}"
            detail_line = f"{windier_phrase}, {calmer_phrase}."
            prefer_line = f"Если важен меньший ветер, {calmer_name} выглядит чуть практичнее."
        else:
            detail_line = f"Разница по ветру и температуре между {name_1} и {name_2} почти не ощущается."
            prefer_line = "Если важен меньший ветер, ориентируйся на прогноз ближе к дате."

        temp_note_1 = str(profile_1.get("temperature_note") or "умеренно тепло")
        temp_note_2 = str(profile_2.get("temperature_note") or "умеренно тепло")
        common_temp = temp_note_1 if temp_note_1 == temp_note_2 else "переменная температура"

        precip_any = (
            str(profile_1.get("precipitation_risk")) in {"medium", "high"}
            or str(profile_2.get("precipitation_risk")) in {"medium", "high"}
        )
        wind_any = (
            str(profile_1.get("wind_risk")) in {"medium", "high"}
            or str(profile_2.get("wind_risk")) in {"medium", "high"}
        )
        context_parts = [f"в обеих локациях {common_temp}"]
        if precip_any:
            context_parts.append("возможны осадки")
        if wind_any:
            context_parts.append("заметный ветер")
        context_raw = self._join_enumeration(context_parts)
        context_line = context_raw[:1].upper() + context_raw[1:] + "."

        return (
            "Погода почти одинаковая.\n\n"
            f"{context_line}\n"
            f"{detail_line}\n\n"
            "Для прогулки явного преимущества нет — выбирай по маршруту.\n"
            f"{prefer_line}"
        )

    def _render_compare_forecast_mixed(
        self,
        profile_1: dict,
        profile_2: dict,
        verdict: dict,
        city_1_full: str,
        city_2_full: str,
        name_1: str,
        name_2: str,
        risk_1: float,
        risk_2: float,
    ) -> str:
        """Рендер compare-by-date: у каждой локации свой плюс и свой минус."""
        warmer_full = verdict.get("warmer_city")
        drier_full = verdict.get("drier_city")
        calmer_full = verdict.get("calmer_city")
        warmer_name = self._get_short_location_name(str(warmer_full)) if warmer_full else None
        drier_name = self._get_short_location_name(str(drier_full)) if drier_full else None
        calmer_name = self._get_short_location_name(str(calmer_full)) if calmer_full else None

        if warmer_name in {name_1, name_2}:
            if warmer_name == name_1:
                warmer_label, warmer_profile = city_1_full, profile_1
                cooler_label, cooler_profile = city_2_full, profile_2
                cooler_name = name_2
            else:
                warmer_label, warmer_profile = city_2_full, profile_2
                cooler_label, cooler_profile = city_1_full, profile_1
                cooler_name = name_1
        else:
            warmer_label, warmer_profile = city_1_full, profile_1
            cooler_label, cooler_profile = city_2_full, profile_2
            warmer_name = name_1
            cooler_name = name_2

        warmer_minus = self._precipitation_comparison_phrase(warmer_profile, cooler_profile)
        if warmer_minus in {"ниже риск осадков", "без существенных осадков"}:
            wind_cmp = self._wind_comparison_phrase(warmer_profile, cooler_profile)
            if wind_cmp == "ветер заметнее":
                warmer_minus = "ветер ощутимее"
            else:
                warmer_minus = "иных плюсов меньше"

        cooler_plus = self._precipitation_comparison_phrase(cooler_profile, warmer_profile)
        if cooler_plus in {"выше риск осадков", "выше шанс дождя", "ожидается снег"}:
            wind_cmp = self._wind_comparison_phrase(cooler_profile, warmer_profile)
            if wind_cmp == "ветер слабее":
                cooler_plus = "ветер слабее"
            else:
                cooler_plus = "суше воздуха меньше, но условия ровнее"

        warmer_inner = f"немного теплее, но {warmer_minus}."
        cooler_inner = f"чуть прохладнее, зато {cooler_plus}."

        prep_warmer = self._get_prepositional_location_name(warmer_label)
        prep_cooler = self._get_prepositional_location_name(cooler_label)
        line_warmer = (
            f"В {prep_warmer} {warmer_inner}" if prep_warmer
            else f"{warmer_name} {warmer_inner}"
        )
        line_cooler = (
            f"В {prep_cooler} {cooler_inner}" if prep_cooler
            else f"{cooler_name} {cooler_inner}"
        )

        walk_city = drier_name or calmer_name or (name_1 if risk_1 < risk_2 else name_2)
        walk_text = f"Для прогулки лучше {walk_city}."

        if warmer_name and drier_name and warmer_name != drier_name:
            trip_text = (
                f"Если важнее температура — {warmer_name}, "
                f"если важнее меньше осадков — {drier_name}."
            )
        elif warmer_name and calmer_name and warmer_name != calmer_name:
            trip_text = (
                f"Если важнее температура — {warmer_name}, "
                f"если важнее меньший ветер — {calmer_name}."
            )
        else:
            trip_text = "Для поездки выбирай по приоритету: температура или меньший риск осадков."

        return (
            "Однозначного лидера нет.\n\n"
            f"{line_warmer}\n"
            f"{line_cooler}\n\n"
            f"{walk_text}\n"
            f"{trip_text}"
        )
