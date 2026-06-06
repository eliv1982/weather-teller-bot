"""Prompt templates/builders extracted from AiWeatherService."""

from weather.descriptions import normalize_weather_description
from weather.pressure import format_pressure_mmhg


def _normalize_ai_weather_payload(value: object) -> object:
    """Return an AI-only copy with normalized weather descriptions."""
    if isinstance(value, list):
        return [_normalize_ai_weather_payload(item) for item in value]
    if not isinstance(value, dict):
        return value

    normalized: dict = {}
    for key, item in value.items():
        if key in {"description", "weather_description"}:
            normalized[key] = normalize_weather_description(item) if isinstance(item, str) else item
        elif key == "weather" and isinstance(item, list):
            normalized[key] = [
                _normalize_ai_weather_payload(weather_item)
                if isinstance(weather_item, dict)
                else weather_item
                for weather_item in item
            ]
        elif isinstance(item, (dict, list)):
            normalized[key] = _normalize_ai_weather_payload(item)
        else:
            normalized[key] = item
    return normalized


def _prepare_history_prompt_payload(history_data: dict) -> tuple[dict, str]:
    payload = _normalize_ai_weather_payload(history_data)
    if not isinstance(payload, dict):
        return {}, "н/д"

    prompt_payload = dict(payload)
    pressure_text = format_pressure_mmhg(prompt_payload.pop("pressure_mean", None))
    return prompt_payload, pressure_text


def _format_tomorrow_pressure_note(day_forecast_data: list[dict]) -> str:
    pressure_values: list[float] = []
    for item in day_forecast_data if isinstance(day_forecast_data, list) else []:
        if not isinstance(item, dict):
            continue
        main_data = item.get("main", {}) if isinstance(item.get("main"), dict) else {}
        pressure = main_data.get("pressure")
        if isinstance(pressure, (int, float)):
            pressure_values.append(float(pressure))
    if not pressure_values:
        return "Данные по давлению ограничены."

    min_pressure = min(pressure_values)
    max_pressure = max(pressure_values)
    avg_pressure = sum(pressure_values) / len(pressure_values)
    min_mmhg = round(min_pressure * 0.75006)
    max_mmhg = round(max_pressure * 0.75006)
    avg_mmhg = round(avg_pressure * 0.75006)
    if max_mmhg - min_mmhg <= 2:
        pressure_text = f"{avg_mmhg} мм рт. ст."
    else:
        pressure_text = f"{min_mmhg}-{max_mmhg} мм рт. ст."
    if avg_pressure <= 1000:
        return f"Давление: {pressure_text}, ниже обычного."
    if avg_pressure >= 1025:
        return f"Давление: {pressure_text}, выше обычного."
    return f"Давление: {pressure_text}, в пределах нормы."


def _tomorrow_ai_payload(day_forecast_data: list[dict]) -> dict:
    temps: list[float] = []
    feels_like_values: list[float] = []
    humidity_values: list[float] = []
    wind_speeds: list[float] = []
    descriptions: dict[str, int] = {}
    precipitation_slots = 0
    date_label = ""
    for item in day_forecast_data if isinstance(day_forecast_data, list) else []:
        if not isinstance(item, dict):
            continue
        if not date_label:
            dt_txt = str(item.get("dt_txt") or "")
            date_label = dt_txt.split(" ", 1)[0] if dt_txt else ""
        main_data = item.get("main", {}) if isinstance(item.get("main"), dict) else {}
        wind_data = item.get("wind", {}) if isinstance(item.get("wind"), dict) else {}
        weather_list = item.get("weather")
        weather_item = weather_list[0] if isinstance(weather_list, list) and weather_list and isinstance(weather_list[0], dict) else {}
        description = normalize_weather_description(weather_item.get("description") or "без описания")
        descriptions[description] = descriptions.get(description, 0) + 1
        if any(x in description.lower() for x in ("дожд", "лив", "гроза", "снег")):
            precipitation_slots += 1
        for target, key in (
            (temps, "temp"),
            (feels_like_values, "feels_like"),
            (humidity_values, "humidity"),
        ):
            value = main_data.get(key)
            if isinstance(value, (int, float)):
                target.append(float(value))
        wind_speed = wind_data.get("speed")
        if isinstance(wind_speed, (int, float)):
            wind_speeds.append(float(wind_speed))
    return {
        "date": date_label or "завтра",
        "temperature": _format_tomorrow_range(temps, "°C"),
        "feels_like": _format_tomorrow_range(feels_like_values, "°C"),
        "description": max(descriptions, key=descriptions.get) if descriptions else "без описания",
        "humidity": _format_tomorrow_range(humidity_values, "%", precision=0),
        "wind": _format_tomorrow_wind_text(wind_speeds),
        "precipitation": "Возможны осадки." if precipitation_slots else "Существенных осадков не ожидается.",
        "pressure": _format_tomorrow_pressure_note(day_forecast_data),
    }


def _format_tomorrow_range(values: list[float], suffix: str, *, precision: int = 1) -> str:
    if not values:
        return "нет данных"
    min_value = min(values)
    max_value = max(values)
    if round(min_value, precision) == round(max_value, precision):
        return f"{min_value:.{precision}f}{suffix}"
    return f"{min_value:.{precision}f}-{max_value:.{precision}f}{suffix}"


def _format_tomorrow_wind_text(wind_speeds: list[float]) -> str:
    if not wind_speeds:
        return "Данные по ветру ограничены."
    max_wind = max(wind_speeds)
    if max_wind < 3:
        return "Ветер слабый."
    if max_wind <= 5:
        return "Ветер умеренный."
    if max_wind < 8:
        return "Ветер заметный, но не сильный."
    return "Ветер сильный."


def build_location_assist_prompt(user_input: str, context: dict | None = None) -> str:
    return (
        "Ты помогаешь уточнить пользовательский запрос локации для геокодинга OpenWeather.\n"
        "КРИТИЧЕСКИ ВАЖНО:\n"
        "- не возвращай координаты;\n"
        "- не выдумывай населённые пункты;\n"
        "- только нормализуй текст и предложи безопасные альтернативные поисковые фразы.\n\n"
        "Поддержи составные русские запросы вида:\n"
        "- <населенный пункт> <район>\n"
        "- <населенный пункт> <область/край/регион>\n"
        "- <населенный пункт> рядом с <городом>\n"
        "- <город> <район/ориентир> (например: Сочи Адлер, Москва центр)\n"
        "Разбери ввод на settlement/city/village, district/rayon, region/oblast/krai, optional landmark/area,\n"
        "и собери alternative_queries, пригодные для OpenWeather geocoding.\n\n"
        "Верни ТОЛЬКО JSON-объект с полями:\n"
        "{\n"
        '  "normalized_query": string,\n'
        '  "alternative_queries": string[],\n'
        '  "needs_clarification": boolean,\n'
        '  "clarification_text": string,\n'
        '  "reason": string\n'
        "}\n\n"
        "Когда запрос слишком общий (например: центр, аэропорт, рядом со мной),"
        " выставляй needs_clarification=true и пиши короткий practical clarification_text.\n"
        "Язык ответа: русский.\n"
        "Контекст сценария: "
        f"{context if isinstance(context, dict) else {}}\n"
        f"Запрос пользователя: {str(user_input or '').strip()}"
    )


def build_current_prompt(city_label: str, weather_data: dict) -> str:
    ai_weather_data = _normalize_ai_weather_payload(weather_data)
    return (
        "Объясни текущую погоду простым и живым русским языком.\n"
        "Требования: 3-4 коротких предложения, дружелюбно и по делу, без канцелярита, "
        "без сарказма, без клоунады, без дисклеймеров и без воды.\n"
        "Используй только переданные данные, ничего не выдумывай.\n"
        "Обязательно скажи: как ощущается погода, есть ли сейчас осадки, как лучше одеться, "
        "насколько комфортно сейчас на улице.\n"
        "Осадки упоминай один раз. Если тип осадков понятен по данным, называй его конкретно: "
        "дождь, снег, гроза, морось. Избегай расплывчатых формулировок вроде "
        "«идут осадки» и не повторяй один и тот же факт про дождь или снег в нескольких предложениях.\n"
        "Давление упоминай только если оно явно низкое (около <=1000 в исходных данных) "
        "или явно высокое (около >=1025 в исходных данных); "
        "без медицинских утверждений, только как мягкий фактор, который можно учесть. "
        "Если пишешь давление, переводи его в мм рт. ст.; при нормальном давлении формулируй: "
        "«Давление в пределах нормы.»\n"
        "Правила формулировок по ветру:\n"
        "- <3 м/с: слабый ветер, почти не мешает;\n"
        "- 3-5 м/с: умеренный ветер;\n"
        "- 5-7 м/с: заметный ветер, может усилить ощущение прохлады при дожде/холоде;\n"
        "- >=8 м/с: сильный ветер, реально влияет на комфорт.\n"
        "Не используй при ветре <=5 м/с формулировки: "
        "«усиливает холод», «усиливает сырость», «делает погоду неприятной», "
        "«сильно влияет на комфорт», «главный фактор».\n"
        "Пиши как полезный совет живого помощника, без сухих шаблонов.\n\n"
        f"Локация: {city_label}\n"
        f"Данные: {ai_weather_data}"
    )


def build_history_prompt(city_label: str, history_data: dict) -> str:
    ai_history_data, pressure_text = _prepare_history_prompt_payload(history_data)
    pressure_line = f"Давление: {pressure_text}\n" if pressure_text != "н/д" else ""
    return (
        "Коротко поясни архивную погоду за прошедший день простым русским языком.\n"
        "Требования: 2-3 коротких предложения, спокойно и по делу, без канцелярита, "
        "без драматизации, без дисклеймеров и без воды.\n"
        "Используй только переданные данные, ничего не выдумывай.\n"
        "Это архивная справка: опирайся на формулировки вроде «по архивным данным» "
        "или «примерная картина дня».\n"
        "Не давай рекомендаций. Не сравнивай с другими днями. Не используй букву с двумя точками. "
        "Пиши через обычную е.\n"
        "Не давай медицинских рекомендаций и не советуй, как одеваться.\n"
        "Коротко опиши температуру, осадки, ветер и при уместности добавь один спокойный штрих "
        "про влажность, давление или общие условия дня.\n\n"
        "Если упоминаешь давление, используй только строку давления в мм рт. ст. "
        "Не пиши hPa, гПа и не выводи сырые числа без единицы. "
        "Если давления нет в данных, не упоминай его.\n\n"
        f"Локация: {city_label}\n"
        f"{pressure_line}"
        f"Архивные данные за день: {ai_history_data}"
    )


def build_forecast_day_prompt(city_label: str, day_forecast_data: list[dict]) -> str:
    ai_day_forecast_data = _normalize_ai_weather_payload(day_forecast_data)
    return (
        "Дай короткий и полезный совет по прогнозу на день.\n"
        "Требования: русский язык, 3-4 коротких предложения, естественный дружелюбный тон, "
        "без канцелярита, без сарказма, без клоунады, без дисклеймеров и без воды.\n"
        "Используй только переданные данные, ничего не выдумывай.\n"
        "Обязательно укажи: лучшее окно для прогулки, осадки и главное изменение погоды в течение дня.\n"
        "Финал сделай практичным и привязанным к погоде: зонт или непромокаемая одежда при дожде, "
        "одеться теплее при холоде, учитывать ветер только если он заметный.\n"
        "Избегай фраз про отсутствие суеты и расплывчатых формулировок про отсутствие акцентов. "
        "Если упоминаешь давление, переводи значение давления в мм рт. ст.; при нормальном давлении пиши: "
        "«Давление в пределах нормы.»\n\n"
        f"Локация: {city_label}\n"
        f"Слоты прогноза за день: {ai_day_forecast_data}"
    )


def build_tomorrow_forecast_prompt(city_label: str, day_forecast_data: list[dict]) -> str:
    ai_day_forecast_data = _tomorrow_ai_payload(day_forecast_data)
    return (
        "Поясни прогноз на завтра простым русским языком.\n"
        "Требования: 4-5 коротких предложений, дружелюбно и по делу, без канцелярита, "
        "без сарказма, без клоунады, без дисклеймеров и без воды.\n"
        "Это не рекомендация на день и не экран прогноза на 5 дней. Не пиши заголовок.\n"
        "Используй только переданные данные, ничего не выдумывай.\n"
        "Скажи: какая погода ожидается завтра, диапазон температуры, как будет ощущаться, "
        "осадки, ветер и давление.\n"
        "Осадки упоминай один раз. Если по описанию виден конкретный тип, называй его прямо: дождь, снег, гроза, морось. "
        "Избегай повторов одного и того же факта про дождь или снег.\n"
        "Не используй фразы про выбор лучшего времени для прогулки, главное изменение погоды, "
        "отсутствие суеты, отсутствие акцентов и драматизацию.\n"
        "Используй поле pressure как готовый текст о давлении и не меняй числа в нём. "
        "Не добавляй другие значения давления и не пиши конвертацию. "
        "Никаких медицинских утверждений.\n"
        "Ветер описывай одной ясной категорией: «Ветер слабый.», «Ветер умеренный.», "
        "«Ветер заметный, но не сильный.» или «Ветер сильный.» Не описывай ветер диапазоном.\n"
        "Если дождя по данным нет, пиши «Дождь не ожидается.» или "
        "«Существенных осадков не ожидается.»\n\n"
        f"Локация: {city_label}\n"
        f"Сводка прогноза на завтра: {ai_day_forecast_data}"
    )


def build_today_forecast_prompt(city_label: str, day_forecast_data: list[dict], *, is_remaining_day: bool = False) -> str:
    ai_day_forecast_data = _tomorrow_ai_payload(day_forecast_data)
    period_label = "на сегодня"
    timing_note = "Если слоты начинаются не с утра, говори просто о сегодняшней погоде по доступным данным." if is_remaining_day else ""
    return (
        f"Поясни прогноз {period_label} простым русским языком.\n"
        "Требования: 4-5 коротких предложений, дружелюбно и по делу, без канцелярита, "
        "без сарказма, без клоунады, без дисклеймеров и без воды.\n"
        "Это не рекомендация на день и не экран прогноза на 5 дней. Не пиши заголовок.\n"
        "Используй только переданные данные, ничего не выдумывай.\n"
        f"Скажи: какая погода ожидается {period_label}, диапазон температуры, как будет ощущаться, "
        "осадки, ветер и давление.\n"
        "Осадки упоминай один раз. Если по описанию виден конкретный тип, называй его прямо: дождь, снег, гроза, морось. "
        "Избегай расплывчатых фраз вроде «осадки идут» и не повторяй один и тот же факт про дождь или снег.\n"
        f"{timing_note}\n"
        "Не используй фразы про выбор лучшего времени для прогулки, главное изменение погоды, "
        "отсутствие суеты, отсутствие акцентов и драматизацию.\n"
        "Используй поле pressure как готовый текст о давлении и не меняй числа в нём. "
        "Не добавляй другие значения давления и не пиши конвертацию. "
        "Никаких медицинских утверждений.\n"
        "Ветер описывай одной ясной категорией: «Ветер слабый.», «Ветер умеренный.», "
        "«Ветер заметный, но не сильный.» или «Ветер сильный.» Не описывай ветер диапазоном.\n"
        "Если дождя по данным нет, пиши «Дождь не ожидается.» или "
        "«Существенных осадков не ожидается.»\n\n"
        f"Локация: {city_label}\n"
        f"Сводка прогноза {period_label}: {ai_day_forecast_data}"
    )


def build_details_prompt(city_label: str, weather_data: dict, air_quality_data: dict | None) -> str:
    ai_weather_data = _normalize_ai_weather_payload(weather_data)
    return (
        "Поясни расширенные погодные данные простым и полезным русским языком.\n"
        "Требования: 4-5 коротких предложений, дружелюбно и по делу, без канцелярита, "
        "без сарказма, без клоунады, без дисклеймеров и без воды.\n"
        "Используй только переданные данные, ничего не выдумывай.\n"
        "Не перечисляй всё подряд: выдели 1-2 самых важных фактора сейчас и объясни, "
        "почему именно они важны прямо сейчас.\n\n"
        "Давление упоминай только если оно явно низкое (около <=1000 в исходных данных) "
        "или явно высокое (около >=1025 в исходных данных); "
        "без медицинских утверждений, только как мягкий фактор, который можно учесть. "
        "Если пишешь давление, переводи его в мм рт. ст.; при нормальном давлении формулируй: "
        "«Давление в пределах нормы.»\n\n"
        "Правила формулировок по ветру:\n"
        "- <3 м/с: слабый ветер, почти не мешает;\n"
        "- 3-5 м/с: умеренный ветер;\n"
        "- 5-7 м/с: заметный ветер, может усилить ощущение прохлады при дожде/холоде;\n"
        "- >=8 м/с: сильный ветер, влияет на комфорт.\n"
        "При ветре <=5 м/с избегай фраз о сильном негативном влиянии ветра.\n"
        "Если качество воздуха хорошее, формулируй коротко: "
        "«Качество воздуха хорошее: пыль и основные загрязнители на низком уровне.»\n\n"
        f"Локация: {city_label}\n"
        f"Погода: {ai_weather_data}\n"
        f"Качество воздуха: {air_quality_data}"
    )


def build_weather_alert_prompt(location_label: str, alert_payload: dict) -> str:
    ai_alert_payload = _normalize_ai_weather_payload(alert_payload)
    return (
        "Объясни погодное уведомление коротко и практично.\n"
        "Требования: русский язык, 1-2 коротких предложения, без воды, без дисклеймеров, "
        "без преувеличений и без длинного прогноза.\n"
        "Используй только переданные данные, ничего не выдумывай.\n"
        "Дай конкретный и сдержанный практический совет: зонт и непромокаемая одежда при дожде, "
        "одеться теплее при холоде, отметить заметный ветер как фактор дискомфорта.\n\n"
        "Нельзя использовать неестественные конструкции: "
        "«маршрут под крышей», «короткий маршрут под крышей», «маршрут под укрытием», «идти под крышей».\n"
        "Используй естественные варианты: "
        "«избегать долгой прогулки под дождём», "
        "«взять зонт и непромокаемую верхнюю одежду», «одеться теплее», "
        "«ветер заметный», «может быть прохладнее из-за ветра».\n"
        "Ветер описывай по шкале:\n"
        "- <3 м/с: слабый;\n"
        "- 3-5 м/с: умеренный;\n"
        "- 5-7 м/с: заметный;\n"
        "- >=8 м/с: сильный.\n"
        "При ветре до 5 м/с не пиши фразы «ветер усиливает холод/сырость» и "
        "«сильно влияет на комфорт».\n\n"
        f"Локация: {location_label}\n"
        f"Событие: {ai_alert_payload}"
    )

