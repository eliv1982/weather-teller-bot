from ai import location_assist


class _DummyService:
    location_alias_map = {
        "питер": "Санкт-Петербург",
        "спб": "Санкт-Петербург",
        "мск": "Москва",
        "москва": "Москва",
    }

    def _normalize_query_text(self, value: object) -> str:
        text = str(value or "").strip().lower().replace("ё", "е")
        return " ".join(text.split())

    def apply_location_alias(self, user_input: str) -> str:
        key = self._normalize_query_text(user_input)
        if not key:
            return ""
        return self.location_alias_map.get(key, str(user_input or "").strip())


def test_parse_location_assist_payload_parses_wrapped_json():
    payload = 'noise before {"normalized_query":"Москва","alternative_queries":["Moscow"],"needs_clarification":false,"clarification_text":"","reason":"ok"} noise after'
    result = location_assist.parse_location_assist_payload(payload)
    assert isinstance(result, dict)
    assert result["normalized_query"] == "Москва"


def test_parse_location_assist_payload_invalid_json_returns_none():
    assert location_assist.parse_location_assist_payload("not-json") is None


def test_fallback_alias_match_for_piter():
    service = _DummyService()
    result = location_assist.fallback_location_assist(service, "питер", None)
    assert result["normalized_query"] == "Санкт-Петербург"
    assert result["reason"] == "alias_match"


def test_fallback_center_requires_clarification():
    service = _DummyService()
    result = location_assist.fallback_location_assist(service, "центр", None)
    assert result["needs_clarification"] is True


def test_fallback_center_of_moscow_returns_alternatives():
    service = _DummyService()
    result = location_assist.fallback_location_assist(service, "центр Москвы", None)
    assert result["needs_clarification"] is False
    assert "Москва" in result["normalized_query"]
    assert any("Moscow" in x or "Москва" in x for x in result["alternative_queries"])


def test_fallback_near_me_requires_geolocation_clarification():
    service = _DummyService()
    result = location_assist.fallback_location_assist(service, "рядом со мной", None)
    assert result["needs_clarification"] is True
    assert "геолокац" in result["clarification_text"].lower()

