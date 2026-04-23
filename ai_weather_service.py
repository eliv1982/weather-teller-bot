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
        self.max_output_tokens = 220
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
            "Объясни текущую погоду по-человечески: коротко, дружелюбно и естественно.\n"
            "Требования: русский язык, 3-4 коротких предложения, тёплый живой тон, "
            "без сарказма, без клоунады, без дисклеймеров, без воды, "
            "используй только переданные данные, не выдумывай.\n"
            "Ответ не должен звучать как официальный отчёт: говори просто и по делу.\n"
            "Обязательно укажи: как ощущается погода, нужен ли зонт, как лучше одеться, комфортно ли на улице.\n"
            "Допустимы живые формулировки вроде «зонт можно оставить дома» или «на улице вполне комфортно», "
            "но без чрезмерной разговорности.\n\n"
            f"Локация: {city_label}\n"
            f"Данные: {weather_data}"
        )
        model_answer = self._call_model(prompt)
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
            "Дай краткий полезный совет по прогнозу на день.\n"
            "Требования: русский язык, 3-4 коротких предложения, дружелюбный и естественный тон, "
            "без сарказма, без клоунады, без дисклеймеров, без воды, "
            "используй только переданные данные, не выдумывай.\n"
            "Обязательно укажи: лучшее окно для прогулки/выхода, осадки, главное изменение погоды в течение дня.\n"
            "Пиши компактно, без лишних деталей.\n\n"
            f"Локация: {city_label}\n"
            f"Слоты прогноза за день: {day_forecast_data}"
        )
        model_answer = self._call_model(prompt)
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
            "Поясни расширенные погодные данные простым и живым языком.\n"
            "Требования: русский язык, 4-5 коротких предложений, дружелюбный естественный тон, "
            "без сарказма, без клоунады, без дисклеймеров, без воды, "
            "используй только переданные данные, не выдумывай.\n"
            "Не перечисляй показатели механически. Выдели 1-2 главных фактора, которые реально важны сейчас "
            "(например, качество воздуха, ветер, влажность или видимость), и объясни почему.\n"
            "Стиль должен быть человеческий, не канцелярский.\n\n"
            f"Локация: {city_label}\n"
            f"Погода: {weather_data}\n"
            f"Качество воздуха: {air_quality_data}"
        )
        model_answer = self._call_model(prompt)
        if model_answer:
            self._save_cached(cache_key, "details", model_answer, ttl_seconds=self.ttl_details_seconds)
            return model_answer
        logger.info("AI fallback used: scenario=details")
        return fallback

    def _call_model(self, prompt: str) -> str | None:
        """Вызывает OpenAI Responses API и возвращает текст ответа."""
        if self.client is None:
            return None
        try:
            response = self.client.responses.create(
                model=self.model,
                input=prompt,
                temperature=self.temperature,
                max_output_tokens=self.max_output_tokens,
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
            "В целом на улице должно быть комфортно."
            if isinstance(temp, (int, float)) and -5 <= temp <= 25
            else "По ощущениям на улице может быть не очень комфортно."
        )
        wind_note = f" Ветер около {wind_speed} м/с." if isinstance(wind_speed, (int, float)) else ""
        return (
            f"Сейчас в локации {city_label}: {description}, температура {temp if temp is not None else 'н/д'}°C, "
            f"ощущается как {feels_like if feels_like is not None else 'н/д'}°C.{wind_note} "
            f"{umbrella} {clothes} {comfort}"
        )

    def _fallback_day_forecast(self, city_label: str, day_items: list[dict]) -> str:
        """Детерминированный fallback для дневного прогноза без OpenAI."""
        if not isinstance(day_items, list) or not day_items:
            return f"По локации {city_label} недостаточно данных, чтобы дать рекомендацию на день."

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
            f"Кратко по {city_label}: {rain_note} "
            f"{slot_note} В течение дня возможны заметные колебания температуры, "
            "так что перед выходом лучше быстро свериться с прогнозом."
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
            "Влажность высокая, может ощущаться духота."
            if isinstance(humidity, (int, float)) and humidity >= 75
            else "Влажность в комфортном диапазоне."
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
            air_note = "Качество воздуха выглядит приемлемым." if pm25 <= 35 else "Качество воздуха сейчас может быть снижено."
        else:
            air_note = "Данные о качестве воздуха неполные."

        return (
            f"По локации {city_label}: {humidity_note} {wind_note} {visibility_note} {air_note} "
            "Если планируешь длительную прогулку, лучше ориентироваться на эти показатели перед выходом."
        )
