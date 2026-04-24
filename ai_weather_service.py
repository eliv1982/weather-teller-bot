import logging
import os
from datetime import datetime
import hashlib
import json

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

    def compare_two_locations_current_with_ai(self, location_1_payload: dict, location_2_payload: dict) -> str:
        """Сравнивает текущую погоду двух локаций через AI (или fallback)."""
        fallback = self._fallback_compare_current(location_1_payload, location_2_payload)
        signature = self._compare_current_signature(location_1_payload, location_2_payload)
        cache_key = self._build_cache_key("ai_compare_current", signature)
        cached = self._get_cached(cache_key)
        if cached:
            logger.info("AI cache hit: scenario=ai_compare_current")
            return cached
        logger.info("AI cache miss: scenario=ai_compare_current")

        prompt = (
            "Сравни текущую погоду в двух локациях и дай короткий человеческий вывод.\n"
            "Требования: русский язык, 3-5 коротких предложений, дружелюбно, естественно и по делу, "
            "без канцелярита, без сарказма, без клоунады, без дисклеймеров и без воды.\n"
            "Мы уже показываем фактическую сводку отдельно, поэтому не повторяй цифры подробно.\n"
            "Сфокусируйся на практическом выводе: где холоднее/ветренее/влажнее, где погода ровнее, "
            "и для чего удобнее каждый вариант (прогулка, поездка).\n"
            "Избегай оценочных и резких формулировок. Финал — понятная рекомендация в одно короткое предложение.\n\n"
            f"Локация 1: {location_1_payload}\n"
            f"Локация 2: {location_2_payload}"
        )
        model_answer = self._call_model(prompt, max_output_tokens=self.max_output_tokens_default)
        if model_answer:
            self._save_cached(cache_key, "ai_compare_current", model_answer, ttl_seconds=self.ttl_current_seconds)
            return model_answer
        logger.info("AI fallback used: scenario=ai_compare_current")
        return fallback

    def compare_two_locations_forecast_day_with_ai(
        self,
        location_1_payload: dict,
        location_2_payload: dict,
        selected_day: str,
    ) -> str:
        """Сравнивает прогноз двух локаций на выбранный день через AI (или fallback)."""
        fallback = self._fallback_compare_forecast_day(location_1_payload, location_2_payload, selected_day)
        signature = self._compare_forecast_day_signature(location_1_payload, location_2_payload, selected_day)
        cache_key = self._build_cache_key("ai_compare_forecast_day", signature)
        cached = self._get_cached(cache_key)
        if cached:
            logger.info("AI cache hit: scenario=ai_compare_forecast_day")
            return cached
        logger.info("AI cache miss: scenario=ai_compare_forecast_day")

        prompt = (
            "Сравни прогноз на выбранную дату для двух локаций и дай короткий совет для выбора.\n"
            "Требования: русский язык, 3-5 коротких предложений, дружелюбно, естественно и по делу, "
            "без канцелярита, без сарказма, без клоунады, без дисклеймеров и без воды.\n"
            "Фактическая сводка уже показана отдельно, поэтому не повторяй длинные цифры.\n"
            "Дай практичный вывод: где холоднее или снежнее, где погода ровнее, и куда удобнее для прогулки или поездки.\n"
            "Избегай фраз вроде «день неприятный», «чуть приятнее», «если выбирать из этих двух», «без лишних раздумий».\n"
            "Если условия похожи, скажи это спокойно и предложи нейтральный выбор по задачам дня.\n\n"
            f"Выбранная дата: {selected_day}\n"
            f"Локация 1: {location_1_payload}\n"
            f"Локация 2: {location_2_payload}"
        )
        model_answer = self._call_model(prompt, max_output_tokens=self.max_output_tokens_default)
        if model_answer:
            self._save_cached(cache_key, "ai_compare_forecast_day", model_answer, ttl_seconds=self.ttl_forecast_seconds)
            return model_answer
        logger.info("AI fallback used: scenario=ai_compare_forecast_day")
        return fallback

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

    def _compare_current_signature(self, payload_1: dict, payload_2: dict) -> dict:
        """Сигнатура кэша для AI-сравнения текущей погоды."""
        return {
            "mode": "current",
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
        """Fallback сравнения текущей погоды между двумя локациями."""
        city_1 = str(payload_1.get("city_label") or "Локация 1")
        city_2 = str(payload_2.get("city_label") or "Локация 2")
        temp_1 = payload_1.get("temperature")
        temp_2 = payload_2.get("temperature")
        feels_1 = payload_1.get("feels_like")
        feels_2 = payload_2.get("feels_like")
        wind_1 = payload_1.get("wind_speed")
        wind_2 = payload_2.get("wind_speed")
        hum_1 = payload_1.get("humidity")
        hum_2 = payload_2.get("humidity")
        desc_1 = str(payload_1.get("description") or "").lower()
        desc_2 = str(payload_2.get("description") or "").lower()
        warm_text = "По температуре заметной разницы почти нет."
        if isinstance(temp_1, (int, float)) and isinstance(temp_2, (int, float)):
            delta_temp = abs(float(temp_1) - float(temp_2))
            if delta_temp >= 1.0:
                warmer = city_1 if float(temp_1) > float(temp_2) else city_2
                warm_text = f"Чуть теплее сейчас в {warmer}."

        wind_text = "По ветру условия близкие."
        if isinstance(wind_1, (int, float)) and isinstance(wind_2, (int, float)):
            delta_wind = abs(float(wind_1) - float(wind_2))
            if delta_wind >= 1.0:
                calmer = city_1 if float(wind_1) < float(wind_2) else city_2
                wind_text = f"По ветру мягче в {calmer}."

        humidity_text = ""
        if isinstance(hum_1, (int, float)) and isinstance(hum_2, (int, float)):
            delta_hum = abs(float(hum_1) - float(hum_2))
            if delta_hum >= 8:
                humid = city_1 if float(hum_1) > float(hum_2) else city_2
                humidity_text = f"В {humid} воздух более влажный."

        comfort_hint = "По ощущениям разница небольшая."
        if isinstance(feels_1, (int, float)) and isinstance(feels_2, (int, float)):
            comfort_1 = abs(float(feels_1) - 20)
            comfort_2 = abs(float(feels_2) - 20)
            if abs(comfort_1 - comfort_2) >= 0.7:
                better = city_1 if comfort_1 < comfort_2 else city_2
                comfort_hint = f"По ощущениям комфортнее в {better}."

        rain_risk = ""
        rain_markers = ("дожд", "лив", "гроза", "снег")
        has_precip_1 = any(marker in desc_1 for marker in rain_markers)
        has_precip_2 = any(marker in desc_2 for marker in rain_markers)
        if has_precip_1 and not has_precip_2:
            rain_risk = f"По осадкам сейчас менее удачный вариант — {city_1}."
        elif has_precip_2 and not has_precip_1:
            rain_risk = f"По осадкам сейчас менее удачный вариант — {city_2}."

        parts = [warm_text, comfort_hint]
        risk_parts = [p for p in [wind_text, humidity_text] if p]
        if risk_parts:
            parts.append(" ".join(risk_parts))
        if rain_risk:
            parts.append(rain_risk)
        if isinstance(feels_1, (int, float)) and isinstance(feels_2, (int, float)):
            comfort_1 = abs(float(feels_1) - 20)
            comfort_2 = abs(float(feels_2) - 20)
            if abs(comfort_1 - comfort_2) < 0.7:
                parts.append("Условия очень близкие — если есть возможность, лучше сравнить с другой локацией.")
            else:
                final_choice = city_1 if comfort_1 < comfort_2 else city_2
                parts.append(f"Если выбирать между этими двумя, сейчас приятнее {final_choice}.")
        else:
            parts.append("Ориентируйся на более спокойный ветер и меньшую влажность.")
        return " ".join(part for part in parts if part).strip()

    def _fallback_compare_forecast_day(self, payload_1: dict, payload_2: dict, selected_day: str) -> str:
        """Fallback сравнения прогноза двух локаций на выбранную дату."""
        city_1 = str(payload_1.get("city_label") or "Локация 1")
        city_2 = str(payload_2.get("city_label") or "Локация 2")
        min_1 = payload_1.get("min_temp")
        max_1 = payload_1.get("max_temp")
        min_2 = payload_2.get("min_temp")
        max_2 = payload_2.get("max_temp")
        rain_1 = (payload_1.get("precipitation_signal") or {}).get("rain_slots")
        rain_2 = (payload_2.get("precipitation_signal") or {}).get("rain_slots")
        pop_1 = (payload_1.get("precipitation_signal") or {}).get("max_pop")
        pop_2 = (payload_2.get("precipitation_signal") or {}).get("max_pop")

        temp_text = "По температуре условия близкие."
        if all(isinstance(v, (int, float)) for v in (max_1, max_2)):
            if abs(float(max_1) - float(max_2)) >= 1.0:
                warmer = city_1 if float(max_1) > float(max_2) else city_2
                temp_text = f"В {warmer} будет теплее."

        rain_text = "По осадкам заметной разницы почти нет."
        if isinstance(rain_1, (int, float)) and isinstance(rain_2, (int, float)):
            rainy = city_1 if float(rain_1) > float(rain_2) else city_2 if float(rain_2) > float(rain_1) else None
            if rainy:
                rain_text = f"Осадки вероятнее в {rainy}."
        if rain_text == "По осадкам заметной разницы почти нет." and isinstance(pop_1, (int, float)) and isinstance(pop_2, (int, float)):
            rainy = city_1 if float(pop_1) > float(pop_2) else city_2 if float(pop_2) > float(pop_1) else None
            if rainy:
                rain_text = f"Осадки вероятнее в {rainy}."

        walk_text = "Для прогулки оба варианта в целом сопоставимы."
        if all(isinstance(v, (int, float)) for v in (min_1, max_1, min_2, max_2)):
            spread_1 = float(max_1) - float(min_1)
            spread_2 = float(max_2) - float(min_2)
            steadier = city_1 if spread_1 < spread_2 else city_2 if spread_2 < spread_1 else None
            if steadier:
                walk_text = f"Для прогулки практичнее {steadier}: погода там ровнее."

        day_comfort_text = ""
        if all(isinstance(v, (int, float)) for v in (min_1, max_1, min_2, max_2)):
            avg_1 = (float(min_1) + float(max_1)) / 2
            avg_2 = (float(min_2) + float(max_2)) / 2
            comfort_1 = abs(avg_1 - 20)
            comfort_2 = abs(avg_2 - 20)
            if abs(comfort_1 - comfort_2) > 0.7:
                better_day = city_1 if comfort_1 < comfort_2 else city_2
                day_comfort_text = f"По ощущениям комфортнее будет в {better_day}."

        final_text = "Ориентируйся на маршрут и формат поездки: заметного перекоса по погоде нет."
        if isinstance(rain_1, (int, float)) and isinstance(rain_2, (int, float)) and rain_1 != rain_2:
            final_text = f"Для поездки удобнее {city_1 if rain_1 < rain_2 else city_2}."
        elif isinstance(pop_1, (int, float)) and isinstance(pop_2, (int, float)) and pop_1 != pop_2:
            final_text = f"Для поездки удобнее {city_1 if pop_1 < pop_2 else city_2}."
        return " ".join(
            part
            for part in [
                f"На {selected_day}: {temp_text}",
                rain_text,
                walk_text,
                day_comfort_text,
                final_text,
            ]
            if part
        ).strip()
