"""Tests for Open-Meteo geocoding fallback in weather.api.get_locations (mocked)."""

from unittest.mock import patch

import pytest

import weather.api as api
from weather.locations import cleanup_location_candidates, rank_locations
from weather.open_meteo import map_open_meteo_geocode_to_ow_candidates


def _om_amsterdam_fixture() -> dict:
    return {
        "results": [
            {
                "id": 2759794,
                "name": "Амстердам",
                "latitude": 52.37403,
                "longitude": 4.88969,
                "country_code": "NL",
                "admin1": "Северная Голландия",
                "population": 921402,
            },
            {
                "id": 999999,
                "name": "Подольск",
                "latitude": 55.42418,
                "longitude": 37.55472,
                "country_code": "RU",
                "admin1": "Московская область",
                "population": 312000,
            },
        ],
    }


@pytest.fixture(autouse=True)
def _clear_api_cache():
    api.API_CACHE._store.clear()
    yield
    api.API_CACHE._store.clear()


def test_fallback_disabled_ow_empty_no_open_meteo(monkeypatch):
    monkeypatch.delenv("OPEN_METEO_FALLBACK", raising=False)
    monkeypatch.setattr(api, "OW_API_KEY", "k")
    with patch.object(api, "fetch_open_meteo_geocode") as om_geo:
        with patch.object(api, "_collect_geocode_candidates", return_value=[]):
            assert api.get_locations("Москва") is None
        om_geo.assert_not_called()


def test_fallback_on_ow_empty_uses_open_meteo(monkeypatch):
    monkeypatch.setenv("OPEN_METEO_FALLBACK", "1")
    monkeypatch.setattr(api, "OW_API_KEY", "k")
    with patch.object(api, "_collect_geocode_candidates", return_value=[]):
        with patch.object(api, "fetch_open_meteo_geocode", return_value=_om_amsterdam_fixture()):
            out = api.get_locations("Амстердам")
    assert out is not None
    assert len(out) >= 1
    first = out[0]
    assert first.get("local_name")
    assert first.get("label")
    assert first.get("country") == "NL"
    assert first.get("lat") == pytest.approx(52.37403)
    assert first["_provider"] == "open_meteo"


def test_fallback_on_missing_ow_key_open_meteo_resolves(monkeypatch):
    monkeypatch.setenv("OPEN_METEO_FALLBACK", "1")
    monkeypatch.setattr(api, "OW_API_KEY", "")
    with patch.object(api, "_collect_geocode_candidates", return_value=[]):
        with patch.object(api, "fetch_open_meteo_geocode", return_value=_om_amsterdam_fixture()):
            out = api.get_locations("Test")
    assert out is not None
    assert len(out) >= 1


def test_openweather_success_does_not_call_open_meteo(monkeypatch):
    monkeypatch.setenv("OPEN_METEO_FALLBACK", "1")
    monkeypatch.setattr(api, "OW_API_KEY", "k")
    ow_row = {"name": "Москва", "lat": 55.75, "lon": 37.62, "country": "RU", "state": "Москва", "local_names": {"ru": "Москва"}}
    with patch.object(api, "_collect_geocode_candidates", return_value=[ow_row]):
        with patch.object(api, "fetch_open_meteo_geocode") as om_geo:
            out = api.get_locations("Москва")
    om_geo.assert_not_called()
    assert out is not None
    assert out[0]["name"] == "Москва"


def test_open_meteo_non_200_returns_none(monkeypatch):
    monkeypatch.setenv("OPEN_METEO_FALLBACK", "1")
    monkeypatch.setattr(api, "OW_API_KEY", "k")
    with patch.object(api, "_collect_geocode_candidates", return_value=[]):
        with patch.object(api, "fetch_open_meteo_geocode", return_value=None):
            assert api.get_locations("Xyz") is None


def test_open_meteo_empty_results_returns_none(monkeypatch):
    monkeypatch.setenv("OPEN_METEO_FALLBACK", "1")
    monkeypatch.setattr(api, "OW_API_KEY", "k")
    with patch.object(api, "_collect_geocode_candidates", return_value=[]):
        with patch.object(api, "fetch_open_meteo_geocode", return_value={"results": []}):
            assert api.get_locations("Xyz") is None


def test_mapper_skips_invalid_rows():
    assert map_open_meteo_geocode_to_ow_candidates(None) == []
    assert map_open_meteo_geocode_to_ow_candidates({"results": []}) == []
    assert map_open_meteo_geocode_to_ow_candidates({"results": "bad"}) == []
    bad = {
        "results": [
            {"name": "X", "latitude": 1, "longitude": 2, "country_code": "BADLONG", "admin1": ""},
        ]
    }
    assert map_open_meteo_geocode_to_ow_candidates(bad) == []


def test_cyrillic_amsterdam_not_ru_only(monkeypatch):
    """OM called without countryCode filter — NL capital can rank first for Cyrillic query."""
    monkeypatch.setenv("OPEN_METEO_FALLBACK", "1")
    monkeypatch.setattr(api, "OW_API_KEY", "k")
    fixture = {
        "results": [
            {
                "name": "Амстердам",
                "latitude": 52.37403,
                "longitude": 4.88969,
                "country_code": "NL",
                "admin1": "Северная Голландия",
                "population": 900_000,
            },
        ]
    }
    with patch.object(api, "_collect_geocode_candidates", return_value=[]):

        def _capture_name(name, **kwargs):
            assert name == "Амстердам"
            assert "countryCode" not in kwargs
            return fixture

        with patch.object(api, "fetch_open_meteo_geocode", side_effect=_capture_name):
            out = api.get_locations("Амстердам")
    assert out is not None
    assert out[0]["country"] == "NL"


def test_cleanup_after_get_locations(monkeypatch):
    monkeypatch.setenv("OPEN_METEO_FALLBACK", "1")
    monkeypatch.setattr(api, "OW_API_KEY", "k")
    fixture = {
        "results": [
            {
                "name": "Амстердам",
                "latitude": 52.37403,
                "longitude": 4.88969,
                "country_code": "NL",
                "admin1": "Северная Голландия",
                "population": 900_000,
            },
            {
                "name": 'ЖК "Амстердам"',
                "latitude": 55.70,
                "longitude": 37.60,
                "country_code": "RU",
                "admin1": "Москва",
                "population": 500,
            },
        ],
    }
    with patch.object(api, "_collect_geocode_candidates", return_value=[]):
        with patch.object(api, "fetch_open_meteo_geocode", return_value=fixture):
            enriched = api.get_locations("Амстердам")
    assert enriched is not None
    ranked = rank_locations("Амстердам", enriched)
    cleaned = cleanup_location_candidates("Амстердам", ranked, limit=3)
    assert len(cleaned) >= 1
    assert any(c.get("country") == "NL" for c in cleaned)


def test_fetch_exception_does_not_raise(monkeypatch):
    monkeypatch.setenv("OPEN_METEO_FALLBACK", "1")
    monkeypatch.setattr(api, "OW_API_KEY", "k")

    def _boom(*_a, **_k):
        raise RuntimeError("network")

    with patch.object(api, "_collect_geocode_candidates", return_value=[]):
        with patch.object(api, "fetch_open_meteo_geocode", side_effect=_boom):
            assert api.get_locations("Q") is None
