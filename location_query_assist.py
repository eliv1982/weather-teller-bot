from __future__ import annotations


GENERIC_CENTER_QUERIES = {
    "центр",
    "центр города",
    "город центр",
    "центр тут",
    "центр рядом",
    "центр поблизости",
    "центр населенного пункта",
    "центр населённого пункта",
}

CENTER_CLARIFICATION_TEXT = (
    "Уточни город: например, «центр Москвы» или «центр Санкт-Петербурга». "
    "Можно также отправить геолокацию."
)


def _normalize_text(value: str) -> str:
    return " ".join(str(value or "").strip().lower().replace("ё", "е").split())


def _extract_city_for_center_query(query: str, *, ctx) -> str | None:
    """Возвращает нормализованный город для запросов вида «центр + город»."""
    normalized = _normalize_text(query)
    if "центр" not in normalized:
        return None

    if normalized in GENERIC_CENTER_QUERIES:
        return None

    tokens = [t for t in normalized.replace(",", " ").split() if t != "центр"]
    if not tokens:
        return None
    city_raw = " ".join(tokens).strip()
    if not city_raw:
        return None

    # Нормализация частых форм/падежей до базового города.
    moscow_forms = {"москва", "москвы", "москве", "москву"}
    petersburg_forms = {
        "санкт-петербург",
        "санкт петербург",
        "санкт-петербурга",
        "санкт петербурга",
        "петербург",
        "петербурга",
        "питер",
        "питера",
        "спб",
    }
    if city_raw in moscow_forms:
        return "Москва"
    if city_raw in petersburg_forms:
        return "Санкт-Петербург"

    alias = ctx.ai_weather_service.apply_location_alias(city_raw)
    if alias:
        return str(alias).strip()
    return city_raw.title()


def find_locations_with_assist(
    query: str,
    *,
    scenario: str,
    ctx,
) -> dict:
    """Ищет локации через geocoding с alias- и AI-assist-подсказками."""
    clean_query = str(query or "").strip()
    if not clean_query:
        return {"locations": [], "clarification_text": None}

    def _search_once(search_query: str) -> list[dict]:
        found = ctx.get_locations(search_query, limit=5)
        return ctx.rank_locations(search_query, found)[:3]

    tried_queries: list[str] = []

    def _remember(value: str) -> None:
        v = str(value or "").strip()
        if v and v not in tried_queries:
            tried_queries.append(v)

    normalized_query = _normalize_text(clean_query)

    # 1-3) deterministic pre-check для generic center queries до geocoding и AI.
    if normalized_query in GENERIC_CENTER_QUERIES:
        return {"locations": [], "clarification_text": CENTER_CLARIFICATION_TEXT}

    # 4) center + city normalization до geocoding.
    center_city = _extract_city_for_center_query(clean_query, ctx=ctx)
    if center_city:
        _remember(center_city)
        locations = _search_once(center_city)
        if locations:
            return {"locations": locations, "clarification_text": None}

    # 5) обычный geocoding с alias map.
    alias_query = ctx.ai_weather_service.apply_location_alias(clean_query)
    primary_query = alias_query or clean_query
    _remember(primary_query)
    locations = _search_once(primary_query)
    if locations:
        return {"locations": locations, "clarification_text": None}

    # 6) AI-assist только после deterministic checks и geocoding miss.
    assist = ctx.ai_weather_service.assist_location_query(
        clean_query,
        context={"scenario": scenario, "language": "ru"},
    )
    if bool((assist or {}).get("needs_clarification")):
        clarification = str((assist or {}).get("clarification_text") or "").strip()
        return {
            "locations": [],
            "clarification_text": clarification or "Уточни населённый пункт или отправь геолокацию.",
        }

    candidates: list[str] = []
    normalized_query = str((assist or {}).get("normalized_query") or "").strip()
    if normalized_query:
        candidates.append(normalized_query)
    alternatives = (assist or {}).get("alternative_queries")
    if isinstance(alternatives, list):
        for item in alternatives:
            candidate = str(item or "").strip()
            if candidate:
                candidates.append(candidate)

    for candidate in candidates:
        if candidate in tried_queries:
            continue
        _remember(candidate)
        locations = _search_once(candidate)
        if locations:
            return {"locations": locations, "clarification_text": None}

    return {"locations": [], "clarification_text": None}
