import logging
import os
import json
import re

from formatters import build_history_brief_summary, build_monthly_climate_brief_summary
from ai import compare_render, fallbacks, location_assist, prompts, response_cache, signatures
from weather.pressure import format_pressure_mmhg

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
        self.ttl_history_seconds = 24 * 60 * 60
        self.ttl_location_assist_seconds = 24 * 60 * 60
        self.location_alias_map = {
            "питер": "Санкт-Петербург",
            "спб": "Санкт-Петербург",
            "санкт питер": "Санкт-Петербург",
            "петербург": "Санкт-Петербург",
            "ленинград": "Санкт-Петербург",
            "мск": "Москва",
            "москва": "Москва",
        }

    def apply_location_alias(self, user_input: str) -> str:
        """Нормализует частые алиасы локаций до geocoding-запроса."""
        key = self._normalize_query_text(user_input)
        if not key:
            return ""
        return self.location_alias_map.get(key, str(user_input or "").strip())

    def assist_location_query(self, user_input: str, context: dict | None = None) -> dict:
        """Помогает уточнить текст локации, не возвращая координаты."""
        fallback = self._fallback_location_assist(user_input, context)
        signature = self._location_assist_signature(user_input, context)
        cache_key = self._build_cache_key("ai_location_assist", signature)
        cached = self._get_cached(cache_key)
        if cached:
            parsed_cached = self._parse_location_assist_payload(cached)
            if parsed_cached is not None:
                logger.info("AI cache hit: scenario=ai_location_assist")
                return parsed_cached
        logger.info("AI cache miss: scenario=ai_location_assist")
        prompt = prompts.build_location_assist_prompt(user_input, context)
        model_answer = self._call_model(prompt, max_output_tokens=220)
        parsed_model = self._parse_location_assist_payload(model_answer or "")
        if parsed_model is not None:
            self._save_cached(
                cache_key,
                "ai_location_assist",
                json.dumps(parsed_model, ensure_ascii=False, separators=(",", ":")),
                ttl_seconds=self.ttl_location_assist_seconds,
            )
            return parsed_model
        logger.info("AI fallback used: scenario=ai_location_assist")
        return fallback

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
        prompt = prompts.build_current_prompt(city_label, weather_data)
        model_answer = self._call_model(prompt, max_output_tokens=self.max_output_tokens_default)
        if model_answer:
            self._save_cached(cache_key, "current", model_answer, ttl_seconds=self.ttl_current_seconds)
            return model_answer
        logger.info("AI fallback used: scenario=current")
        return fallback

    def explain_history_weather(self, city_label: str, history_data: dict) -> str:
        """Коротко поясняет архивную погоду за выбранный день."""
        fallback = self._fallback_history(city_label, history_data)
        signature = self._history_signature(city_label, history_data)
        cache_key = self._build_cache_key("history", signature)
        cached = self._get_cached(cache_key)
        if cached:
            logger.info("AI cache hit: scenario=history")
            return self._postprocess_history_text(cached, history_data)
        logger.info("AI cache miss: scenario=history")
        prompt = prompts.build_history_prompt(city_label, history_data)
        model_answer = self._call_model(prompt, max_output_tokens=200)
        if model_answer:
            final_text = self._postprocess_history_text(model_answer, history_data)
            self._save_cached(cache_key, "history", final_text, ttl_seconds=self.ttl_history_seconds)
            return final_text
        logger.info("AI fallback used: scenario=history")
        return fallback

    def explain_monthly_climate(self, city_label: str, report_data: dict) -> str:
        """Коротко поясняет месячную архивную или климатическую справку."""
        fallback = self._fallback_monthly_climate(city_label, report_data)
        signature = self._monthly_climate_signature(city_label, report_data)
        cache_key = self._build_cache_key("monthly_climate", signature)
        cached = self._get_cached(cache_key)
        if cached:
            logger.info("AI cache hit: scenario=monthly_climate")
            final_text = self._postprocess_monthly_climate_text(cached, report_data)
            if self._is_monthly_climate_text_valid(final_text, report_data):
                return final_text
            return fallback
        logger.info("AI cache miss: scenario=monthly_climate")
        prompt = prompts.build_monthly_climate_prompt(city_label, report_data)
        model_answer = self._call_model(prompt, max_output_tokens=200)
        if model_answer:
            final_text = self._postprocess_monthly_climate_text(model_answer, report_data)
            if self._is_monthly_climate_text_valid(final_text, report_data):
                self._save_cached(cache_key, "monthly_climate", final_text, ttl_seconds=self.ttl_history_seconds)
                return final_text
        logger.info("AI fallback used: scenario=monthly_climate")
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
        prompt = prompts.build_forecast_day_prompt(city_label, day_forecast_data)
        model_answer = self._call_model(prompt, max_output_tokens=self.max_output_tokens_forecast_day)
        if model_answer:
            self._save_cached(cache_key, "forecast_day", model_answer, ttl_seconds=self.ttl_forecast_seconds)
            return model_answer
        logger.info("AI fallback used: scenario=forecast_day")
        return fallback

    def explain_tomorrow_forecast(self, city_label: str, day_forecast_data: list[dict]) -> str:
        """Поясняет прогноз на завтра в стиле отдельного экрана."""
        fallback = self._fallback_tomorrow_forecast(city_label, day_forecast_data)
        signature = self._tomorrow_forecast_signature(city_label, day_forecast_data)
        cache_key = self._build_cache_key("tomorrow_forecast", signature)
        cached = self._get_cached(cache_key)
        if cached:
            logger.info("AI cache hit: scenario=tomorrow_forecast")
            return cached
        logger.info("AI cache miss: scenario=tomorrow_forecast")
        prompt = prompts.build_tomorrow_forecast_prompt(city_label, day_forecast_data)
        model_answer = self._call_model(prompt, max_output_tokens=self.max_output_tokens_forecast_day)
        if model_answer:
            self._save_cached(cache_key, "tomorrow_forecast", model_answer, ttl_seconds=self.ttl_forecast_seconds)
            return model_answer
        logger.info("AI fallback used: scenario=tomorrow_forecast")
        return fallback

    def explain_today_forecast(
        self,
        city_label: str,
        day_forecast_data: list[dict],
        *,
        is_remaining_day: bool = False,
    ) -> str:
        """Поясняет прогноз на сегодня по доступным слотам."""
        fallback = self._fallback_today_forecast(city_label, day_forecast_data, is_remaining_day=is_remaining_day)
        signature = self._today_forecast_signature(
            city_label,
            day_forecast_data,
            is_remaining_day=is_remaining_day,
        )
        cache_key = self._build_cache_key("today_forecast", signature)
        cached = self._get_cached(cache_key)
        if cached:
            logger.info("AI cache hit: scenario=today_forecast")
            return cached
        logger.info("AI cache miss: scenario=today_forecast")
        prompt = prompts.build_today_forecast_prompt(
            city_label,
            day_forecast_data,
            is_remaining_day=is_remaining_day,
        )
        model_answer = self._call_model(prompt, max_output_tokens=self.max_output_tokens_forecast_day)
        if model_answer:
            self._save_cached(cache_key, "today_forecast", model_answer, ttl_seconds=self.ttl_forecast_seconds)
            return model_answer
        logger.info("AI fallback used: scenario=today_forecast")
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
        prompt = prompts.build_details_prompt(city_label, weather_data, air_quality_data)
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
            return self._postprocess_weather_alert_text(cached)
        logger.info("AI cache miss: scenario=ai_weather_alert")
        prompt = prompts.build_weather_alert_prompt(location_label, alert_payload)
        model_answer = self._call_model(prompt, max_output_tokens=120)
        if model_answer:
            final_text = self._postprocess_weather_alert_text(model_answer)
            self._save_cached(cache_key, "ai_weather_alert", final_text, ttl_seconds=self.ttl_current_seconds)
            return final_text
        logger.info("AI fallback used: scenario=ai_weather_alert")
        return self._postprocess_weather_alert_text(fallback)

    def compare_two_locations_current_with_ai(self, location_1_payload: dict, location_2_payload: dict) -> str:
        """Сравнивает текущую погоду двух локаций в deterministic-first режиме."""
        signature = self._compare_current_signature(location_1_payload, location_2_payload)
        cache_key = self._build_cache_key("ai_compare_current", signature)
        cached = self._get_cached(cache_key)
        if cached and self._is_compare_text_factual(cached):
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
        signature = self._compare_forecast_day_signature(location_1_payload, location_2_payload, selected_day)
        cache_key = self._build_cache_key("ai_compare_forecast_day", signature)
        cached = self._get_cached(cache_key)
        if cached and self._is_compare_text_factual(cached):
            logger.info("AI cache hit: scenario=ai_compare_forecast_day")
            return cached
        logger.info("AI cache miss: scenario=ai_compare_forecast_day")
        final_text = self._render_compare_forecast_factual(location_1_payload, location_2_payload, selected_day)
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
        return signatures.build_cache_key(self.model, scenario, signature)

    def _get_cached(self, cache_key: str) -> str | None:
        """Безопасно читает ответ из PostgreSQL-кэша."""
        return response_cache.get_cached_response(cache_key, logger=logger)

    def _save_cached(self, cache_key: str, scenario: str, text: str, *, ttl_seconds: int) -> None:
        """Безопасно сохраняет ответ в PostgreSQL-кэш."""
        response_cache.save_cached_response(
            cache_key,
            scenario,
            text,
            ttl_seconds=ttl_seconds,
            logger=logger,
        )

    def _current_signature(self, city_label: str, weather_data: dict) -> dict:
        """Возвращает сигнатуру ключевых параметров текущей погоды."""
        signature = signatures.current_signature(city_label, weather_data)
        logger.debug("AI current normalized signature: %s", signature)
        return signature

    def _forecast_signature(self, city_label: str, day_forecast_data: list[dict]) -> dict:
        """Возвращает сигнатуру дневного прогноза из ключевых полей каждого слота."""
        return signatures.forecast_signature(city_label, day_forecast_data)

    def _tomorrow_forecast_signature(self, city_label: str, day_forecast_data: list[dict]) -> dict:
        """Возвращает сигнатуру прогноза на завтра."""
        return signatures.tomorrow_forecast_signature(city_label, day_forecast_data)

    def _today_forecast_signature(
        self,
        city_label: str,
        day_forecast_data: list[dict],
        *,
        is_remaining_day: bool = False,
    ) -> dict:
        """Возвращает сигнатуру прогноза на сегодня."""
        return signatures.today_forecast_signature(
            city_label,
            day_forecast_data,
            is_remaining_day=is_remaining_day,
        )

    def _details_signature(self, city_label: str, weather_data: dict, air_quality_data: dict | None) -> dict:
        """Возвращает сигнатуру расширенных данных погоды и воздуха."""
        return signatures.details_signature(city_label, weather_data, air_quality_data)

    def _history_signature(self, city_label: str, history_data: dict) -> dict:
        """Возвращает сигнатуру архивной погоды за день."""
        return signatures.history_signature(city_label, history_data)

    def _monthly_climate_signature(self, city_label: str, report_data: dict) -> dict:
        """Возвращает сигнатуру месячной климатической справки."""
        return signatures.monthly_climate_signature(city_label, report_data)

    def _weather_alert_signature(self, location_label: str, alert_payload: dict) -> dict:
        """Сигнатура кэша для AI-объяснения погодного уведомления."""
        return signatures.weather_alert_signature(location_label, alert_payload)

    def _location_assist_signature(self, user_input: str, context: dict | None) -> dict:
        """Сигнатура кэша для AI-assist текстового запроса локации."""
        return signatures.location_assist_signature(user_input, context)

    def _compare_current_signature(self, payload_1: dict, payload_2: dict) -> dict:
        """Сигнатура кэша для AI-сравнения текущей погоды."""
        return signatures.compare_current_signature(payload_1, payload_2)

    def _compare_forecast_day_signature(self, payload_1: dict, payload_2: dict, selected_day: str) -> dict:
        """Сигнатура кэша для AI-сравнения прогноза на выбранный день."""
        return signatures.compare_forecast_day_signature(payload_1, payload_2, selected_day)

    def _build_location_fingerprint(self, payload: dict) -> str:
        """Собирает стабильный fingerprint локации для cache signature."""
        return signatures.build_location_fingerprint(payload)

    def _round_1(self, value: object) -> float | None:
        """Округляет число до 1 знака после запятой."""
        return signatures.round_1(value)

    def _round_step(self, value: object, *, step: float) -> float | None:
        """Округляет число до заданного шага."""
        return signatures.round_step(value, step=step)

    def _round_coords(self, value: object) -> str:
        """Округляет координату для fingerprint до 3 знаков."""
        return signatures.round_coords(value)

    def _normalize_location(self, value: object) -> str:
        """Нормализует подпись локации для устойчивого cache key."""
        return signatures.normalize_location(value)

    def _normalize_description(self, value: object) -> str:
        """Нормализует описание погоды."""
        return signatures.normalize_description(value)

    def _normalize_query_text(self, value: object) -> str:
        """Нормализует произвольный пользовательский текстовый запрос."""
        return signatures.normalize_query_text(value)

    def _parse_location_assist_payload(self, payload: str) -> dict | None:
        """Парсит JSON-пейлоад AI-assist и валидирует ожидаемые поля."""
        return location_assist.parse_location_assist_payload(payload)

    def _fallback_location_assist(self, user_input: str, context: dict | None) -> dict:
        """Детерминированный fallback для неоднозначного ввода локации."""
        return location_assist.fallback_location_assist(self, user_input, context)

    def _build_center_location_assist(self, normalized_input: str) -> dict | None:
        """Обрабатывает запросы с «центр» отдельно от общего fallback."""
        return location_assist.build_center_location_assist(self, normalized_input)

    def _build_structured_location_alternatives(self, normalized_input: str) -> dict | None:
        """Собирает fallback-варианты geocoding для запросов с районом/областью/ориентиром."""
        return location_assist.build_structured_location_alternatives(normalized_input)

    def _as_int(self, value: object) -> int | None:
        """Приводит значение к целому числу, если это возможно."""
        return signatures.as_int(value)

    def _air_quality_signature(self, air_quality_data: dict | None) -> dict | None:
        """Возвращает нормализованную сигнатуру ключевых компонентов воздуха."""
        return signatures.air_quality_signature(air_quality_data)

    def _fallback_current(self, city_label: str, weather_data: dict) -> str:
        """Детерминированный fallback для текущей погоды без OpenAI."""
        return fallbacks.fallback_current(city_label, weather_data)

    def _fallback_history(self, city_label: str, history_data: dict) -> str:
        """Детерминированный fallback для архивной погоды без OpenAI."""
        _ = city_label
        return build_history_brief_summary(history_data)

    def _fallback_monthly_climate(self, city_label: str, report_data: dict) -> str:
        """Детерминированный fallback для месячной климатической справки без OpenAI."""
        _ = city_label
        return build_monthly_climate_brief_summary(report_data)

    def _fallback_day_forecast(self, city_label: str, day_items: list[dict]) -> str:
        """Детерминированный fallback для дневного прогноза без OpenAI."""
        return fallbacks.fallback_day_forecast(city_label, day_items)

    def _fallback_tomorrow_forecast(self, city_label: str, day_items: list[dict]) -> str:
        """Детерминированный fallback для прогноза на завтра без OpenAI."""
        return fallbacks.fallback_tomorrow_forecast(city_label, day_items)

    def _fallback_today_forecast(
        self,
        city_label: str,
        day_items: list[dict],
        *,
        is_remaining_day: bool = False,
    ) -> str:
        """Детерминированный fallback для прогноза на сегодня без OpenAI."""
        return fallbacks.fallback_today_forecast(city_label, day_items, is_remaining_day=is_remaining_day)

    def _fallback_details(self, city_label: str, weather_data: dict, air_quality_data: dict | None) -> str:
        """Детерминированный fallback для расширенных данных без OpenAI."""
        return fallbacks.fallback_details(city_label, weather_data, air_quality_data)

    def _fallback_compare_current(self, payload_1: dict, payload_2: dict) -> str:
        """Фактическая сводка по двум локациям без рекомендаций."""
        return self._render_compare_current_factual(payload_1, payload_2)

    def _format_number(self, value: object, suffix: str = "") -> str:
        if isinstance(value, (int, float)):
            return f"{float(value):.1f}{suffix}"
        return "н/д"

    def _postprocess_history_text(self, text: str, history_data: dict | None = None) -> str:
        """Слегка чистит AI-текст для архивной справки."""
        clean = re.sub(r"\s+", " ", str(text or "").strip())
        clean = clean.translate({1105: 1077, 1025: 1045})
        clean = re.sub(r"(?<!\d)-0(?:\.0+)?(?=\D|$)", "0.0", clean)
        pressure_text = format_pressure_mmhg((history_data or {}).get("pressure_mean"))
        pressure_pattern = r"(?i)(?:^|(?<=[.!?]))\s*[^.!?]*(?:давлен|hpa|гпа)[^.!?]*[.!?]?"
        if pressure_text == "н/д":
            clean = re.sub(pressure_pattern, " ", clean, count=1)
        elif re.search(pressure_pattern, clean) and "мм рт. ст." not in clean.lower():
            clean = re.sub(pressure_pattern, f" Давление было около {pressure_text}.", clean, count=1)
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean

    def _postprocess_monthly_climate_text(self, text: str, report_data: dict | None = None) -> str:
        """Чистит AI-текст для месячной климатической справки."""
        clean = self._postprocess_history_text(text, report_data)
        clean = re.sub(
            r"(?i)вероятност[ьи] осадков",
            "доля дней с осадками по архивным данным",
            clean,
        )
        mode = str((report_data or {}).get("mode") or "")
        if mode == "monthly_normals":
            clean = re.sub(
                r"(?i)это не прогноз на конкретный месяц,?\s*а архивная справка по (?:периоду|данным за) 1991-2020\.?",
                "Это архивная справка по данным за 1991-2020.",
                clean,
            )
            clean = re.sub(
                r"(?i)это не прогноз на конкретный месяц\.?",
                "Это архивная справка по данным за 1991-2020.",
                clean,
            )
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean

    def _is_monthly_climate_text_valid(self, text: str, report_data: dict | None = None) -> bool:
        lowered = str(text or "").lower()
        if "ё" in lowered or "вероятност" in lowered:
            return False
        if any(token in lowered for token in ("hpa", "гпа")):
            return False
        if "давлен" in lowered and "мм рт. ст." not in lowered:
            return False
        if any(
            phrase in lowered
            for phrase in (
                "надень",
                "наденьте",
                "возьми",
                "возьмите",
                "лучше",
                "рекоменд",
            )
        ):
            return False
        mode = str((report_data or {}).get("mode") or "")
        if mode == "monthly_normals":
            if "прогноз" in lowered:
                return False
        elif "прогноз" in lowered:
            return False
        if mode == "monthly_normals":
            if "1991-2020" not in text:
                return False
            if "архив" not in lowered:
                return False
        return True

    def _is_compare_text_factual(self, text: str) -> bool:
        lowered = str(text or "").lower()
        banned = (
            "теплее",
            "прохладнее",
            "холоднее",
            "жарче",
            "суше",
            "влажнее",
            "слабее",
            "сильнее",
            "лучше",
            "хуже",
            "практичнее",
            "удобнее",
            "спокойнее",
            "если важнее",
            "у вариантов разные плюсы",
            "условия близки",
            "ориентируйся",
            "выбирай",
            "маршрут",
            "прогулки",
            "поездки",
        )
        return not any(phrase in lowered for phrase in banned)

    def _temperature_absolute_note(self, value: object) -> str:
        if not isinstance(value, (int, float)):
            return "температура не указана"
        temp = float(value)
        if temp <= 0:
            return "холодно"
        if temp < 10:
            return "прохладно"
        if temp < 16:
            return "свежо"
        if temp < 26:
            return "тепло"
        return "жарко"

    def _humidity_absolute_note(self, value: object) -> str:
        if not isinstance(value, (int, float)):
            return "влажность не указана"
        humidity = float(value)
        if humidity < 40:
            return "воздух сухой"
        if humidity <= 70:
            return "влажность умеренная"
        return "влажно"

    def _wind_absolute_note(self, value: object) -> str:
        if not isinstance(value, (int, float)):
            return "ветер не указан"
        speed = float(value)
        if speed < 3:
            return "ветер слабый"
        if speed < 6:
            return "ветер умеренный"
        if speed < 9:
            return "ветер заметный"
        return "ветер сильный"

    def _capitalize_phrase(self, text: object) -> str:
        phrase = str(text or "").strip()
        if not phrase:
            return ""
        return phrase[:1].upper() + phrase[1:]

    def _render_compare_current_block(self, payload: dict, fallback_name: str) -> str:
        return compare_render._render_compare_current_block(self, payload, fallback_name)

    def _render_compare_current_factual(self, payload_1: dict, payload_2: dict) -> str:
        return compare_render._render_compare_current_factual(self, payload_1, payload_2)

    def _fallback_weather_alert(self, location_label: str, alert_payload: dict) -> str:
        """Детерминированный fallback для погодного уведомления (1-2 коротких предложения)."""
        return fallbacks.fallback_weather_alert(location_label, alert_payload)

    def _postprocess_weather_alert_text(self, text: str) -> str:
        """Мягко нормализует формулировки AI-совета по уведомлениям."""
        return fallbacks.postprocess_weather_alert_text(text)

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
            trip_recommendation = f"Если важнее меньше погодных помех в дороге — {winner}."
            ai_instruction = (
                f"Есть заметный перевес по отдельным погодным факторам: {winner}. "
                "Укажи это, но кратко назови риски второй локации."
            )
        else:
            walk_city = drier_city or calmer_city or winner
            trip_city = drier_city or winner
            walk_recommendation = (
                f"Для прогулки практичнее {walk_city}."
                if isinstance(walk_city, str) and walk_city
                else "Для прогулки ориентируйся на меньший риск осадков и ветра."
            )
            trip_recommendation = (
                f"Если важнее меньше погодных помех в дороге — {trip_city}."
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

    def _render_compare_forecast_block(self, payload: dict, selected_day: str, fallback_name: str) -> str:
        return compare_render._render_compare_forecast_block(self, payload, selected_day, fallback_name)

    def _render_compare_forecast_factual(self, payload_1: dict, payload_2: dict, selected_day: str) -> str:
        return compare_render._render_compare_forecast_factual(self, payload_1, payload_2, selected_day)

