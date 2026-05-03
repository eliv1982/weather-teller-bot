import math
import re

# ISO 3166-1 alpha-2 → русское название страны (для подписей локаций).
# Если кода нет в словаре, в подписи показывается сам код.
COUNTRY_NAMES_RU = {
    "RU": "Россия",
    "UA": "Украина",
    "BY": "Беларусь",
    "KZ": "Казахстан",
    "KG": "Киргизия",
    "TJ": "Таджикистан",
    "TM": "Туркменистан",
    "UZ": "Узбекистан",
    "AM": "Армения",
    "AZ": "Азербайджан",
    "GE": "Грузия",
    "MD": "Молдова",
    "US": "США",
    "GB": "Великобритания",
    "DE": "Германия",
    "FR": "Франция",
    "IT": "Италия",
    "ES": "Испания",
    "PT": "Португалия",
    "NL": "Нидерланды",
    "BE": "Бельгия",
    "CH": "Швейцария",
    "AT": "Австрия",
    "CZ": "Чехия",
    "SK": "Словакия",
    "HU": "Венгрия",
    "PL": "Польша",
    "RO": "Румыния",
    "BG": "Болгария",
    "GR": "Греция",
    "FI": "Финляндия",
    "SE": "Швеция",
    "NO": "Норвегия",
    "DK": "Дания",
    "EE": "Эстония",
    "LV": "Латвия",
    "LT": "Литва",
    "IE": "Ирландия",
    "CN": "Китай",
    "JP": "Япония",
    "KR": "Республика Корея",
    "IN": "Индия",
    "TR": "Турция",
    "MA": "Марокко",
    "EG": "Египет",
    "AE": "ОАЭ",
    "SA": "Саудовская Аравия",
    "IL": "Израиль",
    "AU": "Австралия",
    "NZ": "Новая Зеландия",
    "CA": "Канада",
    "BR": "Бразилия",
    "AR": "Аргентина",
    "MX": "Мексика",
    "ZA": "ЮАР",
    "ID": "Индонезия",
    "VN": "Вьетнам",
    "TH": "Таиланд",
    "MY": "Малайзия",
    "PH": "Филиппины",
}

CIS_AND_NEAR_COUNTRY_CODES = frozenset({"RU", "BY", "UA", "KZ", "KG", "TJ", "TM", "UZ", "AM", "AZ", "GE", "MD"})

REGION_NAMES_RU = {
    "Saint Petersburg": "Санкт-Петербург",
    "Moscow": "Москва",
    "Moscow Oblast": "Московская область",
    "Moscow oblast": "Московская область",
    "Leningrad Oblast": "Ленинградская область",
    "Leningrad oblast": "Ленинградская область",
    "Kaliningrad Oblast": "Калининградская область",
    "Kaliningrad oblast": "Калининградская область",
    "Kaliningrad": "Калининградская область",
    "Tyumen Oblast": "Тюменская область",
    "Tyumen oblast": "Тюменская область",
    "Vologda Oblast": "Вологодская область",
    "Vologda oblast": "Вологодская область",
    "Nizhny Novgorod Oblast": "Нижегородская область",
    "Nizhny Novgorod oblast": "Нижегородская область",
    "Kirov Oblast": "Кировская область",
    "Kirov oblast": "Кировская область",
    "Tver Oblast": "Тверская область",
    "Tver oblast": "Тверская область",
    "Novosibirsk Oblast": "Новосибирская область",
    "Novosibirsk oblast": "Новосибирская область",
    "Sverdlovsk Oblast": "Свердловская область",
    "Sverdlovsk oblast": "Свердловская область",
    "Chelyabinsk Oblast": "Челябинская область",
    "Chelyabinsk oblast": "Челябинская область",
    "Omsk Oblast": "Омская область",
    "Omsk oblast": "Омская область",
    "Samara Oblast": "Самарская область",
    "Samara oblast": "Самарская область",
    "Rostov Oblast": "Ростовская область",
    "Rostov oblast": "Ростовская область",
    "Krasnodar Krai": "Краснодарский край",
    "Krasnodar krai": "Краснодарский край",
    "Stavropol Krai": "Ставропольский край",
    "Stavropol krai": "Ставропольский край",
    "Krasnoyarsk Krai": "Красноярский край",
    "Krasnoyarsk krai": "Красноярский край",
    "Perm Krai": "Пермский край",
    "Perm krai": "Пермский край",
    "Altai Krai": "Алтайский край",
    "Altai krai": "Алтайский край",
    "Primorsky Krai": "Приморский край",
    "Primorsky krai": "Приморский край",
    "Khabarovsk Krai": "Хабаровский край",
    "Khabarovsk krai": "Хабаровский край",
    "Kamchatka Krai": "Камчатский край",
    "Kamchatka krai": "Камчатский край",
    "Zabaykalsky Krai": "Забайкальский край",
    "Zabaykalsky krai": "Забайкальский край",
    "Yaroslavl Oblast": "Ярославская область",
    "Yaroslavl oblast": "Ярославская область",
    "Vladimir Oblast": "Владимирская область",
    "Vladimir oblast": "Владимирская область",
    "Ivanovo Oblast": "Ивановская область",
    "Ivanovo oblast": "Ивановская область",
    "Kostroma Oblast": "Костромская область",
    "Kostroma oblast": "Костромская область",
    "Ryazan Oblast": "Рязанская область",
    "Ryazan oblast": "Рязанская область",
    "Voronezh Oblast": "Воронежская область",
    "Voronezh oblast": "Воронежская область",
    "Volgograd Oblast": "Волгоградская область",
    "Volgograd oblast": "Волгоградская область",
    "Saratov Oblast": "Саратовская область",
    "Saratov oblast": "Саратовская область",
    "Penza Oblast": "Пензенская область",
    "Penza oblast": "Пензенская область",
    "Tambov Oblast": "Тамбовская область",
    "Tambov oblast": "Тамбовская область",
    "Lipetsk Oblast": "Липецкая область",
    "Lipetsk oblast": "Липецкая область",
    "Kursk Oblast": "Курская область",
    "Kursk oblast": "Курская область",
    "Belgorod Oblast": "Белгородская область",
    "Belgorod oblast": "Белгородская область",
    "Bryansk Oblast": "Брянская область",
    "Bryansk oblast": "Брянская область",
    "Smolensk Oblast": "Смоленская область",
    "Smolensk oblast": "Смоленская область",
    "Kaluga Oblast": "Калужская область",
    "Kaluga oblast": "Калужская область",
    "Tula Oblast": "Тульская область",
    "Tula oblast": "Тульская область",
    "Oryol Oblast": "Орловская область",
    "Oryol oblast": "Орловская область",
    "Orel Oblast": "Орловская область",
    "Orel oblast": "Орловская область",
    "Novgorod Oblast": "Новгородская область",
    "Novgorod oblast": "Новгородская область",
    "Pskov Oblast": "Псковская область",
    "Pskov oblast": "Псковская область",
    "Murmansk Oblast": "Мурманская область",
    "Murmansk oblast": "Мурманская область",
    "Arkhangelsk Oblast": "Архангельская область",
    "Arkhangelsk oblast": "Архангельская область",
    "Karelia": "Республика Карелия",
    "Republic of Karelia": "Республика Карелия",
    "Komi Republic": "Республика Коми",
    "Udmurt Republic": "Удмуртская Республика",
    "Chuvash Republic": "Чувашская Республика",
    "Mari El Republic": "Республика Марий Эл",
    "Mordovia Republic": "Республика Мордовия",
    "Republic of Mordovia": "Республика Мордовия",
    "Chuvashia": "Чувашская Республика",
    "Bashkortostan Republic": "Республика Башкортостан",
    "Bashkortostan": "Республика Башкортостан",
    "Tatarstan": "Татарстан",
    "Republic of Tatarstan": "Татарстан",
    "Dagestan": "Республика Дагестан",
    "Republic of Dagestan": "Республика Дагестан",
    "Republic of Adygea": "Республика Адыгея",
    "Republic of Ingushetia": "Республика Ингушетия",
    "Republic of Khakassia": "Республика Хакасия",
    "Republic of Buryatia": "Республика Бурятия",
    "Republic of Altai": "Республика Алтай",
    "Chechen Republic": "Чеченская Республика",
    "Kabardino-Balkarian Republic": "Кабардино-Балкарская Республика",
    "North Ossetia-Alania": "Республика Северная Осетия — Алания",
    "Republic of North Ossetia-Alania": "Республика Северная Осетия — Алания",
    "Zaporizhzhia Oblast": "Запорожская область",
    "Zaporizhzhia oblast": "Запорожская область",
    "Irkutsk Oblast": "Иркутская область",
    "Irkutsk oblast": "Иркутская область",
    "Amur Oblast": "Амурская область",
    "Amur oblast": "Амурская область",
    "Sakhalin Oblast": "Сахалинская область",
    "Sakhalin oblast": "Сахалинская область",
    "Magadan Oblast": "Магаданская область",
    "Magadan oblast": "Магаданская область",
    "Sakha Republic": "Республика Саха (Якутия)",
    "Republic of Sakha": "Республика Саха (Якутия)",
    "Khanty-Mansi Autonomous Okrug": "Ханты-Мансийский автономный округ — Югра",
    "Yamalo-Nenets Autonomous Okrug": "Ямало-Ненецкий автономный округ",
    "Chukotka Autonomous Okrug": "Чукотский автономный округ",
    "Nenets Autonomous Okrug": "Ненецкий автономный округ",
}
_REGION_NAMES_RU_LOWER = {k.lower(): v for k, v in REGION_NAMES_RU.items()}


def _lookup_region_dict(state: str) -> str | None:
    """Возвращает перевод из REGION_NAMES_RU при точном совпадении или совпадении без учёта регистра."""
    if state in REGION_NAMES_RU:
        return REGION_NAMES_RU[state]
    return _REGION_NAMES_RU_LOWER.get(state.strip().lower())


def _pattern_republic_of_ru(state: str) -> str | None:
    """
    Осторожный шаблон: «Republic of …» → «Республика …», если в словаре нет ключа.
    """
    s = state.strip()
    match = re.match(r"(?i)^republic\s+of\s+(.+)$", s)
    if not match:
        return None
    rest = match.group(1).strip()
    return f"Республика {rest}" if rest else None


def contains_cyrillic(text: str) -> bool:
    """Проверяет наличие кириллицы в строке."""
    return bool(re.search(r"[а-яёА-ЯЁ]", text or ""))


def get_country_name_ru(country_code: str | None) -> str | None:
    """Возвращает русское название страны по ISO-коду."""
    if not country_code:
        return None
    code = country_code.strip().upper()
    if not code:
        return None
    return COUNTRY_NAMES_RU.get(code, code)


def get_city_name_ru(location: dict) -> str:
    """Возвращает отображаемое имя населённого пункта (предпочтительно на русском)."""
    local_names = location.get("local_names", {})
    raw_name = location.get("name", "")
    return (
        local_names.get("ru")
        or (raw_name if contains_cyrillic(raw_name) else None)
        or local_names.get("en")
        or raw_name
        or "неизвестная локация"
    )


def get_region_name_ru(state: str | None) -> str | None:
    """Возвращает человекочитаемое имя региона."""
    if not state:
        return None
    s = state.strip()
    if not s:
        return None
    mapped = _lookup_region_dict(s)
    if mapped is not None:
        return mapped
    if contains_cyrillic(s):
        return s
    return s


def build_location_label(location: dict, show_coords: bool = False) -> str:
    """Собирает строку подписи для локации (населённый пункт, страна, регион)."""
    city_name = get_city_name_ru(location)
    region_name = get_region_name_ru(location.get("state"))
    country_name = get_country_name_ru(location.get("country"))
    details = []
    if country_name:
        details.append(country_name)
    if region_name and region_name != city_name and region_name not in details:
        details.append(region_name)
    label = city_name
    if details:
        label += f" ({', '.join(details)})"
    if show_coords:
        lat = location.get("lat")
        lon = location.get("lon")
        if lat is not None and lon is not None:
            label += f" — {lat:.4f}, {lon:.4f}"
    return label


def location_label_plain(location: dict) -> str:
    """Короткая подпись локации без координат."""
    return build_location_label(location, show_coords=False)


def location_label_with_coords(location: dict) -> str:
    """Подпись локации с координатами."""
    return build_location_label(location, show_coords=True)


def build_disambiguated_location_labels(locations: list[dict]) -> list[str]:
    """Строит подписи кнопок и добавляет координаты только для дублей."""
    if not locations:
        return []
    bases = [location_label_plain(loc) for loc in locations]
    counts: dict[str, int] = {}
    for base in bases:
        counts[base] = counts.get(base, 0) + 1
    result: list[str] = []
    for loc, base in zip(locations, bases):
        result.append(location_label_with_coords(loc) if counts.get(base, 0) > 1 else base)
    return result


def build_geocode_item_with_disambiguated_label(locations: list[dict], index: int) -> dict:
    """Возвращает элемент геокодинга с label, совпадающим с кнопкой выбора."""
    labels = build_disambiguated_location_labels(locations)
    item = dict(locations[index])
    item["label"] = labels[index]
    return item


def _is_likely_administrative_unit(location: dict) -> bool:
    """Эвристика: область/край/округ и т.п. — менее приоритетно, чем населённый пункт."""
    raw_name = (location.get("name") or "").strip()
    local = location.get("local_names") or {}
    ru = (local.get("ru") or "").strip()
    try:
        label_preview = build_location_label(location, show_coords=False).lower()
    except (TypeError, ValueError):
        label_preview = ""
    blob = f"{raw_name} {ru} {label_preview}".lower()
    patterns = (
        " oblast",
        "область",
        " krai",
        " край",
        "krai",
        "oblast",
        "region",
        "district",
        "okrug",
        " округ",
        " район",
        " raion",
        " province",
        " провинция",
        " republic",
        " республик",
        "автоном",
        "autonomous",
        "municipality",
        "муниципал",
        " county",
        " prefecture",
        " префектур",
        "obasy",
        "сельсовет",
        "welayat",
        " welayaty",
    )
    return any(p in blob for p in patterns)


def _name_match_score(query: str, location: dict) -> float:
    """Насколько имя локации (ru/en/raw) совпадает с запросом пользователя."""
    q = query.strip().lower()
    if not q:
        return 0.0
    local_names = location.get("local_names") or {}
    candidates = [
        get_city_name_ru(location).strip().lower(),
        (location.get("name") or "").strip().lower(),
        (local_names.get("ru") or "").strip().lower(),
        (local_names.get("en") or "").strip().lower(),
    ]
    best = 0.0
    for s in candidates:
        if not s:
            continue
        if q == s:
            best = max(best, 1000.0)
        elif s.startswith(q) or q.startswith(s):
            best = max(best, 450.0)
        elif q in s or s in q:
            best = max(best, 150.0)
    return best


def _normalize_location_match_text(value: object) -> str:
    """Нормализует текст для эвристик сравнения кандидатов геокодинга."""
    text = str(value or "").strip().lower().replace("ё", "е")
    text = re.sub(r"[^\wа-яА-ЯёЁ]+", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


def _location_name_variants(location: dict) -> list[str]:
    local_names = location.get("local_names") or {}
    values = [
        location.get("local_name"),
        get_city_name_ru(location),
        location.get("name"),
        local_names.get("ru"),
        local_names.get("en"),
        location.get("label"),
    ]
    result: list[str] = []
    for value in values:
        normalized = _normalize_location_match_text(value)
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def _is_noisy_poi_like_location(location: dict) -> bool:
    """Консервативно определяет ЖК/POI-like кандидаты по имени и подписи."""
    local_names = location.get("local_names") or {}
    text = " ".join(
        str(value or "")
        for value in (
            location.get("name"),
            location.get("local_name"),
            location.get("label"),
            local_names.get("ru"),
            local_names.get("en"),
        )
    )
    normalized = _normalize_location_match_text(text)
    noisy_phrases = (
        "жилой комплекс",
        "residential complex",
    )
    if any(phrase in text.lower().replace("ё", "е") for phrase in noisy_phrases):
        return True
    tokens = set(normalized.split())
    return "жк" in tokens


def _is_exact_location_name_match(query: str, location: dict) -> bool:
    normalized_query = _normalize_location_match_text(query)
    if not normalized_query:
        return False
    return normalized_query in _location_name_variants(location)


def _same_or_similar_location_name(left: dict, right: dict) -> bool:
    left_names = _location_name_variants(left)
    right_names = _location_name_variants(right)
    for left_name in left_names:
        for right_name in right_names:
            if left_name == right_name:
                return True
            if min(len(left_name), len(right_name)) >= 5 and (
                left_name in right_name or right_name in left_name
            ):
                return True
    return False


def _edit_distance_limited(left: str, right: str, *, max_distance: int) -> int:
    if abs(len(left) - len(right)) > max_distance:
        return max_distance + 1
    previous = list(range(len(right) + 1))
    for left_index, left_char in enumerate(left, start=1):
        current = [left_index]
        row_min = current[0]
        for right_index, right_char in enumerate(right, start=1):
            cost = 0 if left_char == right_char else 1
            value = min(
                previous[right_index] + 1,
                current[right_index - 1] + 1,
                previous[right_index - 1] + cost,
            )
            current.append(value)
            row_min = min(row_min, value)
        if row_min > max_distance:
            return max_distance + 1
        previous = current
    return previous[-1]


def _is_strong_location_match(query: str, location: dict) -> bool:
    normalized_query = _normalize_location_match_text(query)
    if not normalized_query:
        return False
    query_tokens = normalized_query.split()
    if len(query_tokens) != 1:
        return _is_exact_location_name_match(query, location)
    for name in _location_name_variants(location):
        if name == normalized_query:
            return True
        if len(name.split()) == 1 and _edit_distance_limited(normalized_query, name, max_distance=1) <= 1:
            return True
        if (
            (name.startswith(normalized_query) or normalized_query.startswith(name))
            and _edit_distance_limited(normalized_query, name, max_distance=1) <= 1
        ):
            return True
    return False


def _is_weak_derivative_location_match(query: str, location: dict) -> bool:
    if _is_strong_location_match(query, location):
        return False
    semantic_noise_words = {
        "остров",
        "острова",
        "island",
        "islands",
        "архипелаг",
        "archipelago",
        "гора",
        "горы",
        "mount",
        "mountain",
        "mountains",
        "залив",
        "bay",
        "мыс",
        "cape",
    }
    for name in _location_name_variants(location):
        tokens = set(name.split())
        if tokens & semantic_noise_words:
            return True
    return False


def _coordinate_distance_km(left: dict, right: dict) -> float | None:
    try:
        left_lat = float(left.get("lat"))
        left_lon = float(left.get("lon"))
        right_lat = float(right.get("lat"))
        right_lon = float(right.get("lon"))
    except (TypeError, ValueError):
        return None
    radius_km = 6371.0
    d_lat = math.radians(right_lat - left_lat)
    d_lon = math.radians(right_lon - left_lon)
    lat_1 = math.radians(left_lat)
    lat_2 = math.radians(right_lat)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(lat_1) * math.cos(lat_2) * math.sin(d_lon / 2) ** 2
    )
    return radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _coordinates_are_city_level_close(left: dict, right: dict, *, threshold_km: float = 15.0) -> bool:
    distance = _coordinate_distance_km(left, right)
    return distance is not None and distance <= threshold_km


def _same_country_state(left: dict, right: dict) -> bool:
    left_country = str(left.get("country") or "").strip().upper()
    right_country = str(right.get("country") or "").strip().upper()
    if not left_country or not right_country or left_country != right_country:
        return False
    left_state = _normalize_location_match_text(left.get("state"))
    right_state = _normalize_location_match_text(right.get("state"))
    if left_state and right_state and left_state != right_state:
        return False
    return True


def _are_near_duplicate_locations(left: dict, right: dict) -> bool:
    return (
        _same_country_state(left, right)
        and _same_or_similar_location_name(left, right)
        and _coordinates_are_city_level_close(left, right)
    )


def _dedupe_near_identical_locations(query: str, locations: list[dict]) -> list[dict]:
    ranked = rank_locations(query, locations)
    result: list[dict] = []
    for location in ranked:
        if any(_are_near_duplicate_locations(location, existing) for existing in result):
            continue
        result.append(location)
    return result


def cleanup_location_candidates(query: str, locations: list[dict], *, limit: int = 3) -> list[dict]:
    """Финально чистит варианты геокодинга перед показом пользователю."""
    if not locations:
        return []
    cap = max(1, limit)
    ranked = rank_locations(query, locations)

    non_noisy = [loc for loc in ranked if not _is_noisy_poi_like_location(loc)]
    if non_noisy:
        ranked = non_noisy

    strong_matches = [loc for loc in ranked if _is_strong_location_match(query, loc)]
    if strong_matches:
        ranked = strong_matches

    deduped = _dedupe_near_identical_locations(query, ranked)
    if len(deduped) == 1 and _is_weak_derivative_location_match(query, deduped[0]):
        return []
    return deduped[:cap]


def _country_priority_score(query: str, location: dict) -> float:
    """Дополнительный вес по стране для кириллического запроса."""
    if not contains_cyrillic(query.strip()):
        return 0.0
    cc = (location.get("country") or "").upper()
    if not cc:
        return 0.0
    if cc == "RU":
        return 520.0
    if cc in CIS_AND_NEAR_COUNTRY_CODES:
        return 200.0
    return -80.0


def _location_relevance_score(location: dict, query: str) -> float:
    """Итоговая оценка полезности варианта для сортировки."""
    score = _name_match_score(query, location)
    score += _country_priority_score(query, location)
    if contains_cyrillic(query.strip()) and (location.get("local_names") or {}).get("ru"):
        score += 260.0
    is_admin = _is_likely_administrative_unit(location)
    if is_admin:
        score -= 450.0
    st = location.get("state")
    if st and not is_admin:
        score += 45.0
    return score


def _spb_alias_boost(query: str, location: dict) -> float:
    """Точечный boost для частого русского алиаса «питер»."""
    normalized_query = (query or "").strip().lower()
    if normalized_query not in {"питер"}:
        return 0.0

    city_name = get_city_name_ru(location).strip().lower()
    raw_name = str(location.get("name") or "").strip().lower()
    local_names = location.get("local_names") or {}
    local_ru = str(local_names.get("ru") or "").strip().lower()
    country_code = str(location.get("country") or "").strip().upper()

    matches_spb = any(
        candidate.startswith("санкт-петербург") or candidate.startswith("санкт петербург")
        for candidate in (city_name, raw_name, local_ru)
    )
    if matches_spb and country_code == "RU":
        return 3000.0
    return 0.0


def rank_locations(query: str, locations: list[dict]) -> list[dict]:
    """Сортирует список локаций по UX-эвристике для выбора пользователем."""
    if not locations:
        return []
    q = (query or "").strip()
    q_lower = q.lower()
    base_label_counts: dict[str, int] = {}
    for loc in locations:
        base_label = str(loc.get("label") or build_location_label(loc, show_coords=False)).strip().lower()
        base_label_counts[base_label] = base_label_counts.get(base_label, 0) + 1

    def score(loc: dict) -> tuple[float, int, str]:
        total = float(_location_relevance_score(loc, q))
        total += _spb_alias_boost(q, loc)
        local_name = str(loc.get("local_name") or get_city_name_ru(loc)).strip().lower()
        raw_name = str(loc.get("name") or "").strip().lower()
        if q_lower and (q_lower == local_name or q_lower == raw_name):
            total += 700.0
        if loc.get("state"):
            total += 120.0
        if loc.get("country"):
            total += 45.0
        population = loc.get("population")
        try:
            pop_value = int(population) if population is not None else 0
        except (TypeError, ValueError):
            pop_value = 0
        if pop_value > 0:
            total += min(pop_value / 20000.0, 260.0)
        label = str(loc.get("label") or "").lower()
        if "—" in label and re.search(r"-?\d{1,2}\.\d+", label):
            total -= 220.0
        base_label = str(loc.get("label") or build_location_label(loc, show_coords=False)).strip().lower()
        if base_label_counts.get(base_label, 0) > 1:
            total -= 90.0
        if _is_likely_administrative_unit(loc):
            total -= 180.0
        ru_priority = 0 if (loc.get("country") or "").upper() == "RU" and contains_cyrillic(q) else 1
        alpha = str(loc.get("label") or build_location_label(loc, show_coords=False))
        return (total, -ru_priority, alpha)

    return sorted(locations, key=lambda loc: score(loc), reverse=True)


def _dedupe_key(location: dict) -> tuple:
    """Ключ для схлопывания полных дублей."""
    name = get_city_name_ru(location).strip().lower()
    cc = (location.get("country") or "").upper()
    st = (location.get("state") or "").strip().lower()
    lat = location.get("lat")
    lon = location.get("lon")
    if lat is not None and lon is not None:
        try:
            lat_q = round(float(lat), 3)
            lon_q = round(float(lon), 3)
        except (TypeError, ValueError):
            lat_q = lon_q = None
    else:
        lat_q = lon_q = None
    return (name, cc, st, lat_q, lon_q)


def _dedupe_geocode_sorted(sorted_locations: list[dict]) -> list[dict]:
    """Убирает дубликаты после сортировки по релевантности."""
    seen: set[tuple] = set()
    out: list[dict] = []
    for loc in sorted_locations:
        key = _dedupe_key(loc)
        if key in seen:
            continue
        seen.add(key)
        out.append(loc)
    return out


def _enrich_location_item(raw: dict) -> dict:
    """Добавляет к элементу геокодинга поля local_name и label для бота."""
    local_name = get_city_name_ru(raw)
    label = build_location_label(raw, show_coords=False)
    enriched = dict(raw)
    enriched["local_name"] = local_name
    enriched["label"] = label
    return enriched
