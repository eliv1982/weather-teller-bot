"""Tests for sensitive/contested region display name suppression."""
from weather.locations import build_location_label, _is_sensitive_location


def _loc(name, *, ru=None, country="UA", state=None, lat=44.95, lon=34.10):
    loc = {"name": name, "country": country, "lat": lat, "lon": lon}
    if ru:
        loc["local_names"] = {"ru": ru}
    if state:
        loc["state"] = state
    return loc


# ---------------------------------------------------------------------------
# Sensitive region detection
# ---------------------------------------------------------------------------

class TestIsSensitiveLocation:
    def test_republic_of_crimea_is_sensitive(self):
        assert _is_sensitive_location({"name": "Yalta", "state": "Republic of Crimea"})

    def test_autonomous_republic_of_crimea_is_sensitive(self):
        assert _is_sensitive_location({"name": "Simferopol", "state": "Autonomous Republic of Crimea"})

    def test_donetsk_oblast_is_sensitive(self):
        assert _is_sensitive_location({"name": "Donetsk", "state": "Donetsk Oblast"})

    def test_donetsk_peoples_republic_is_sensitive(self):
        assert _is_sensitive_location({"name": "Donetsk", "state": "Donetsk People's Republic"})

    def test_luhansk_oblast_is_sensitive(self):
        assert _is_sensitive_location({"name": "Luhansk", "state": "Luhansk Oblast"})

    def test_luhansk_peoples_republic_is_sensitive(self):
        assert _is_sensitive_location({"name": "Luhansk", "state": "Luhansk People's Republic"})

    def test_zaporizhzhia_oblast_is_sensitive(self):
        assert _is_sensitive_location({"name": "Melitopol", "state": "Zaporizhzhia Oblast"})

    def test_kherson_oblast_is_sensitive(self):
        assert _is_sensitive_location({"name": "Kherson", "state": "Kherson Oblast"})

    def test_regular_region_is_not_sensitive(self):
        assert not _is_sensitive_location({"name": "Moscow", "state": "Moscow Oblast", "country": "RU"})

    def test_no_state_is_not_sensitive(self):
        assert not _is_sensitive_location({"name": "Amsterdam", "country": "NL"})

    def test_empty_state_is_not_sensitive(self):
        assert not _is_sensitive_location({"name": "Kyiv", "state": "", "country": "UA"})


# ---------------------------------------------------------------------------
# build_location_label for sensitive locations
# ---------------------------------------------------------------------------

class TestBuildLocationLabelSensitive:
    def test_yalta_crimea_shows_only_city_name(self):
        loc = _loc("Yalta", ru="Ялта", country="UA", state="Republic of Crimea", lat=44.5, lon=34.17)
        label = build_location_label(loc)
        assert label == "Ялта"
        assert "Украина" not in label
        assert "Россия" not in label
        assert "Crimea" not in label
        assert "Крым" not in label

    def test_simferopol_crimea_shows_only_city_name(self):
        loc = _loc("Simferopol", ru="Симферополь", country="RU", state="Republic of Crimea", lat=44.95, lon=34.10)
        label = build_location_label(loc)
        assert label == "Симферополь"
        assert "Россия" not in label
        assert "Crimea" not in label

    def test_donetsk_donetsk_oblast_shows_only_city_name(self):
        loc = _loc("Donetsk", ru="Донецк", country="UA", state="Donetsk Oblast", lat=48.0, lon=37.8)
        label = build_location_label(loc)
        assert label == "Донецк"
        assert "Украина" not in label
        assert "Donetsk" not in label.replace("Донецк", "")

    def test_luhansk_luhansk_oblast_shows_only_city_name(self):
        loc = _loc("Luhansk", ru="Луганск", country="UA", state="Luhansk Oblast", lat=48.57, lon=39.33)
        label = build_location_label(loc)
        assert label == "Луганск"
        assert "Украина" not in label
        assert "Luhansk" not in label.replace("Луганск", "")

    def test_sensitive_location_with_coords_shows_city_and_coords(self):
        loc = _loc("Yalta", ru="Ялта", country="UA", state="Republic of Crimea", lat=44.4958, lon=34.1667)
        label = build_location_label(loc, show_coords=True)
        assert label.startswith("Ялта")
        assert "44.4958" in label
        assert "34.1667" in label
        assert "Украина" not in label
        assert "Crimea" not in label

    def test_dnr_donetsk_peoples_republic_shows_only_city(self):
        loc = _loc("Donetsk", ru="Донецк", country="RU", state="Donetsk People's Republic", lat=48.0, lon=37.8)
        label = build_location_label(loc)
        assert label == "Донецк"
        assert "Россия" not in label

    def test_lnr_luhansk_peoples_republic_shows_only_city(self):
        loc = _loc("Luhansk", ru="Луганск", country="RU", state="Luhansk People's Republic", lat=48.57, lon=39.33)
        label = build_location_label(loc)
        assert label == "Луганск"
        assert "Россия" not in label


# ---------------------------------------------------------------------------
# Regular locations still use old format
# ---------------------------------------------------------------------------

class TestBuildLocationLabelRegular:
    def test_amsterdam_keeps_full_format(self):
        loc = {
            "name": "Amsterdam",
            "country": "NL",
            "state": "North Holland",
            "lat": 52.37,
            "lon": 4.89,
        }
        label = build_location_label(loc)
        assert "Amsterdam" in label
        assert "Нидерланды" in label
        assert "North Holland" in label

    def test_minsk_keeps_country(self):
        loc = {
            "name": "Minsk",
            "local_names": {"ru": "Минск"},
            "country": "BY",
            "lat": 53.9,
            "lon": 27.57,
        }
        label = build_location_label(loc)
        assert "Минск" in label
        assert "Беларусь" in label

    def test_moscow_keeps_full_format(self):
        loc = {
            "name": "Moscow",
            "local_names": {"ru": "Москва"},
            "country": "RU",
            "state": "Moscow",
            "lat": 55.75,
            "lon": 37.61,
        }
        label = build_location_label(loc)
        assert "Москва" in label
        assert "Россия" in label

    def test_kyiv_keeps_full_format(self):
        loc = {
            "name": "Kyiv",
            "local_names": {"ru": "Киев"},
            "country": "UA",
            "state": "Kyiv City",
            "lat": 50.45,
            "lon": 30.52,
        }
        label = build_location_label(loc)
        assert "Киев" in label
        assert "Украина" in label


# ---------------------------------------------------------------------------
# New sensitive patterns: Sevastopol + plain Crimea state
# ---------------------------------------------------------------------------

class TestSevastopolAndPlainCrimea:
    def test_sevastopol_state_is_sensitive(self):
        assert _is_sensitive_location({"name": "Sevastopol", "state": "Sevastopol"})

    def test_sevastopol_russian_state_is_sensitive(self):
        assert _is_sensitive_location({"name": "Sevastopol", "state": "Севастополь"})

    def test_plain_crimea_state_is_sensitive(self):
        assert _is_sensitive_location({"name": "Kerch", "state": "Crimea"})

    def test_plain_krym_state_is_sensitive(self):
        assert _is_sensitive_location({"name": "Yalta", "state": "Крым"})

    def test_sevastopol_label_shows_only_city_name(self):
        loc = _loc("Sevastopol", ru="Севастополь", country="RU", state="Sevastopol")
        label = build_location_label(loc)
        assert label == "Севастополь"
        assert "Россия" not in label
        assert "Украина" not in label
        assert "Sevastopol" not in label.replace("Севастополь", "")

    def test_sevastopol_ua_label_shows_only_city_name(self):
        loc = _loc("Sevastopol", ru="Севастополь", country="UA", state="Sevastopol")
        label = build_location_label(loc)
        assert label == "Севастополь"
        assert "Украина" not in label

    def test_kerch_plain_crimea_label_shows_only_city_name(self):
        loc = _loc("Kerch", ru="Керчь", country="UA", state="Crimea")
        label = build_location_label(loc)
        assert label == "Керчь"
        assert "Украина" not in label
        assert "Crimea" not in label
