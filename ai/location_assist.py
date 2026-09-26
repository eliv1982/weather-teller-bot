"""Location assist parsing and deterministic fallback helpers."""

import json


def parse_location_assist_payload(payload: str) -> dict | None:
    raw = str(payload or "").strip()
    if not raw:
        return None
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        parsed = json.loads(raw[start : end + 1])
    except Exception:
        return None
    if not isinstance(parsed, dict):
        return None

    normalized_query = str(parsed.get("normalized_query") or "").strip()
    alt_raw = parsed.get("alternative_queries")
    alternative_queries: list[str] = []
    if isinstance(alt_raw, list):
        for item in alt_raw:
            candidate = str(item or "").strip()
            if candidate and candidate not in alternative_queries:
                alternative_queries.append(candidate)

    needs_clarification = bool(parsed.get("needs_clarification", False))
    clarification_text = str(parsed.get("clarification_text") or "").strip()
    reason = str(parsed.get("reason") or "").strip()
    if needs_clarification and not clarification_text:
        clarification_text = "Уточни населённый пункт или отправь геолокацию."
    return {
        "normalized_query": normalized_query,
        "alternative_queries": alternative_queries[:5],
        "needs_clarification": needs_clarification,
        "clarification_text": clarification_text,
        "reason": reason,
    }


def fallback_location_assist(service, user_input: str, context: dict | None) -> dict:
    _ = context
    normalized = service._normalize_query_text(user_input)
    alias = service.apply_location_alias(user_input)
    center_case = build_center_location_assist(service, normalized)
    if center_case is not None:
        return center_case
    if normalized in {"рядом со мной", "рядом", "возле меня", "около меня"}:
        return {
            "normalized_query": "",
            "alternative_queries": [],
            "needs_clarification": True,
            "clarification_text": "Лучше отправь геолокацию — так я точнее пойму место.",
            "reason": "near_me_ambiguous",
        }
    if normalized in {"центр"}:
        return {
            "normalized_query": normalized,
            "alternative_queries": [],
            "needs_clarification": True,
            "clarification_text": "Уточни город: например, центр Москвы или центр Санкт-Петербурга.",
            "reason": "generic_center_ambiguous",
        }
    if normalized in {"аэропорт"}:
        return {
            "normalized_query": normalized,
            "alternative_queries": [],
            "needs_clarification": True,
            "clarification_text": "Уточни город или отправь геолокацию. Например: аэропорт Сочи или аэропорт Москвы.",
            "reason": "generic_airport_ambiguous",
        }
    if normalized in {"район", "область", "регион"}:
        return {
            "normalized_query": normalized,
            "alternative_queries": [],
            "needs_clarification": True,
            "clarification_text": "Уточни населённый пункт и регион. Например: Заречный, Свердловская область.",
            "reason": "generic_admin_area_ambiguous",
        }

    structured = build_structured_location_alternatives(normalized)
    if structured is not None:
        return structured

    if alias and alias != str(user_input or "").strip():
        alternatives = [alias]
        if alias == "Санкт-Петербург":
            alternatives.extend(["Saint Petersburg", "Петербург"])
        return {
            "normalized_query": alias,
            "alternative_queries": alternatives,
            "needs_clarification": False,
            "clarification_text": "",
            "reason": "alias_match",
        }
    return {
        "normalized_query": str(user_input or "").strip(),
        "alternative_queries": [],
        "needs_clarification": False,
        "clarification_text": "Уточни населённый пункт или отправь геолокацию.",
        "reason": "default_fallback",
    }


def build_center_location_assist(service, normalized_input: str) -> dict | None:
    text = str(normalized_input or "").strip()
    if "центр" not in text:
        return None
    if text == "центр":
        return {
            "normalized_query": "центр",
            "alternative_queries": [],
            "needs_clarification": True,
            "clarification_text": "Уточни город: например, «центр Москвы» или «центр Санкт-Петербурга». Можно также отправить геолокацию.",
            "reason": "center_without_city",
        }

    without_center = " ".join([t for t in text.replace(",", " ").split() if t != "центр"]).strip()
    if not without_center:
        return {
            "normalized_query": "центр",
            "alternative_queries": [],
            "needs_clarification": True,
            "clarification_text": "Уточни город: например, «центр Москвы» или «центр Санкт-Петербурга». Можно также отправить геолокацию.",
            "reason": "center_without_city",
        }

    city_alias = service.apply_location_alias(without_center)
    city_norm = service._normalize_query_text(city_alias or without_center)
    if city_norm in {"москвы", "москва"}:
        return {
            "normalized_query": "Москва",
            "alternative_queries": ["Москва", "Москва центр", "Moscow city center"],
            "needs_clarification": False,
            "clarification_text": "",
            "reason": "center_with_moscow",
        }
    if city_norm in {"санкт-петербурга", "санкт-петербург", "петербурга", "петербург", "питер", "спб"}:
        return {
            "normalized_query": "Санкт-Петербург",
            "alternative_queries": ["Санкт-Петербург", "Санкт-Петербург центр", "Saint Petersburg city center"],
            "needs_clarification": False,
            "clarification_text": "",
            "reason": "center_with_saint_petersburg",
        }
    city_cap = (city_alias or without_center).strip().title()
    if not city_cap:
        return None
    return {
        "normalized_query": city_cap,
        "alternative_queries": [city_cap, f"{city_cap} центр"],
        "needs_clarification": False,
        "clarification_text": "",
        "reason": "center_with_city",
    }


def build_structured_location_alternatives(normalized_input: str) -> dict | None:
    text = str(normalized_input or "").strip()
    if not text or len(text.split()) < 2:
        return None
    tokens = [t for t in text.replace(",", " ").split() if t]
    if not tokens:
        return None
    area_stopwords = {"рядом", "с", "центр", "район", "область", "край", "регион", "г", "город"}
    region_markers = {"область", "край", "регион"}

    settlement_tokens: list[str] = []
    for token in tokens:
        if token in area_stopwords:
            break
        settlement_tokens.append(token)
    if not settlement_tokens:
        settlement_tokens = [tokens[0]]
    settlement = " ".join(settlement_tokens).strip()
    if not settlement:
        return None

    region_value = ""
    if any(marker in tokens for marker in region_markers):
        idx = next((i for i, t in enumerate(tokens) if t in region_markers), -1)
        if idx > 0:
            region_value = " ".join(tokens[max(0, idx - 1) : idx + 1]).strip()

    district_value = ""
    if "район" in tokens:
        idx = tokens.index("район")
        if idx > 0:
            district_value = " ".join(tokens[max(0, idx - 1) : idx + 1]).strip()

    nearby_value = ""
    if "рядом" in tokens and "с" in tokens:
        s_idx = max(i for i, t in enumerate(tokens) if t == "с")
        if s_idx + 1 < len(tokens):
            nearby_value = " ".join(tokens[s_idx + 1 :]).strip()

    area_value = ""
    if "центр" in tokens:
        area_value = "центр"
    elif len(tokens) > len(settlement_tokens):
        tail = [t for t in tokens[len(settlement_tokens) :] if t not in {"рядом", "с"}]
        if tail and "район" not in tail and not any(t in region_markers for t in tail):
            area_value = " ".join(tail).strip()

    settlement_cap = settlement.title()
    region_cap = region_value.title() if region_value else ""
    district_cap = district_value.title() if district_value else ""
    nearby_cap = nearby_value.title() if nearby_value else ""
    area_cap = area_value.title() if area_value else ""

    alternatives: list[str] = []
    if district_cap and region_cap:
        alternatives.append(f"{settlement_cap}, {district_cap}, {region_cap}")
    if nearby_cap and region_cap:
        alternatives.append(f"{settlement_cap}, рядом с {nearby_cap}, {region_cap}")
    elif nearby_cap:
        alternatives.append(f"{settlement_cap}, рядом с {nearby_cap}")
    if area_cap and settlement_cap.lower() != area_cap.lower():
        alternatives.append(f"{settlement_cap}, {area_cap}")
    if region_cap:
        alternatives.append(f"{settlement_cap}, {region_cap}")
    if "Московская Область" in region_cap:
        alternatives.append(f"{settlement_cap}, Moscow Oblast")

    unique_alternatives: list[str] = []
    for candidate in alternatives:
        clean = candidate.strip()
        if clean and clean not in unique_alternatives:
            unique_alternatives.append(clean)
    if not unique_alternatives:
        return None
    return {
        "normalized_query": settlement_cap,
        "alternative_queries": unique_alternatives[:5],
        "needs_clarification": False,
        "clarification_text": "",
        "reason": "structured_settlement_area_query",
    }
