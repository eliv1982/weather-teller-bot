import os
import re
import time
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()
OW_API_KEY = os.getenv("OW_API_KEY")

LAST_ERROR_TYPE = None  # None | "network" | "rate_limit"

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

# Страны СНГ и ближнего зарубежья (для приоритета при кириллическом запросе).
CIS_AND_NEAR_COUNTRY_CODES = frozenset(
    {
        "RU",
        "BY",
        "UA",
        "KZ",
        "KG",
        "TJ",
        "TM",
        "UZ",
        "AM",
        "AZ",
        "GE",
        "MD",
    }
)

# Англоязычные названия регионов из OpenWeather (поле state) → русская подпись.
# Ключи должны совпадать с ответом API; при вариациях добавлены несколько форм.
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

# Быстрый поиск по REGION_NAMES_RU без учёта регистра (API иногда отличается в регистре).
_REGION_NAMES_RU_LOWER = {k.lower(): v for k, v in REGION_NAMES_RU.items()}


def _lookup_region_dict(state: str) -> str | None:
    """Возвращает перевод из REGION_NAMES_RU при точном совпадении или совпадении без учёта регистра."""
    if state in REGION_NAMES_RU:
        return REGION_NAMES_RU[state]
    return _REGION_NAMES_RU_LOWER.get(state.strip().lower())


def _pattern_republic_of_ru(state: str) -> str | None:
    """
    Осторожный шаблон: «Republic of …» → «Республика …», если в словаре нет ключа.

    Не применяется к видам «X Oblast» / «X Krai» — без словарной статьи они остаются как в API.
    Хвост после «Republic of» не переводится автоматически (остаётся латиница), чтобы не
    искажать неизвестные названия.
    """
    s = state.strip()
    match = re.match(r"(?i)^republic\s+of\s+(.+)$", s)
    if not match:
        return None
    rest = match.group(1).strip()
    if not rest:
        return None
    return f"Республика {rest}"


def contains_cyrillic(text: str) -> bool:
    return any("а" <= ch.lower() <= "я" or ch.lower() == "ё" for ch in text)


def safe_request(
    url: str,
    params: dict,
    retries: int = 3,
    timeout: int = 10
) -> requests.Response | None:
    global LAST_ERROR_TYPE
    LAST_ERROR_TYPE = None
    delay = 1

    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, params=params, timeout=timeout)
        except requests.RequestException:
            if attempt < retries:
                time.sleep(delay)
                delay *= 2
                continue

            LAST_ERROR_TYPE = "network"
            return None

        if response.status_code == 429:
            if attempt < retries:
                time.sleep(delay)
                delay *= 2
                continue

            LAST_ERROR_TYPE = "rate_limit"
            return response

        return response

    return None


def get_country_name_ru(country_code: str | None) -> str | None:
    """
    Возвращает русское название страны по коду ISO 3166-1 alpha-2.
    Если кода нет в словаре COUNTRY_NAMES_RU, возвращает сам код (например «TM»).
    """
    if not country_code:
        return None
    return COUNTRY_NAMES_RU.get(country_code, country_code)


def get_city_name_ru(location: dict) -> str:
    """
    Возвращает отображаемое имя населённого пункта (предпочтительно на русском).
    """
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
    """
    Возвращает человекочитаемое имя региона (штат, область и т.п.) для подписи локации.

    Порядок обработки:
    1. Словарь REGION_NAMES_RU (точное совпадение или без учёта регистра).
    2. Если state уже на кириллице — возвращается как есть.
    3. Иначе возвращается исходная строка из API (латиница и т.д.), не None.

    Важно: неизвестные зарубежные регионы не переводятся автоматически, чтобы подпись
    оставалась стабильной и без «угадываний».
    """
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
    """
    Собирает строку подписи для локации (населённый пункт, страна, регион).

    show_coords=False — обычная подпись без координат.
    show_coords=True — в конец добавляются широта и долгота (см. также location_label_with_coords).
    """
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
    """Короткая подпись локации без координат (название, страна, регион при необходимости)."""
    return build_location_label(location, show_coords=False)


def location_label_with_coords(location: dict) -> str:
    """Подпись локации с координатами (для различения похожих вариантов в списке выбора)."""
    return build_location_label(location, show_coords=True)


def build_disambiguated_location_labels(locations: list[dict]) -> list[str]:
    """
    Готовые строки подписей для inline-кнопок выбора локации.

    Сначала для каждого варианта считается обычная подпись без координат.
    Если одна и та же подпись повторяется у нескольких пунктов, для всех таких
    вариантов добавляются координаты, чтобы подписи различались там, где без этого
    их нельзя отличить.
    """
    if not locations:
        return []

    bases = [location_label_plain(loc) for loc in locations]
    counts: dict[str, int] = {}
    for base in bases:
        counts[base] = counts.get(base, 0) + 1

    result: list[str] = []
    for loc, base in zip(locations, bases):
        if counts.get(base, 0) > 1:
            result.append(location_label_with_coords(loc))
        else:
            result.append(base)
    return result


def build_geocode_item_with_disambiguated_label(locations: list[dict], index: int) -> dict:
    """
    Возвращает копию элемента геокодинга с полем label, совпадающим с подписью
    в списке выбора (включая координаты при дублях), чтобы сохранить в профиль то же имя,
    что видел пользователь на кнопке.
    """
    labels = build_disambiguated_location_labels(locations)
    item = dict(locations[index])
    item["label"] = labels[index]
    return item


def _geocode_direct_raw(q: str, limit: int = 5) -> list[dict]:
    """
    Один запрос к geo/1.0/direct без обогащения полями бота.
    У API лимит не более 5 результатов за вызов.
    """
    if not OW_API_KEY:
        return []

    query = (q or "").strip()
    if not query:
        return []

    limit = min(max(1, limit), 5)
    url = "https://api.openweathermap.org/geo/1.0/direct"
    params = {"q": query, "limit": limit, "appid": OW_API_KEY}
    response = safe_request(url, params)

    if response is None or response.status_code != 200:
        return []

    try:
        data = response.json()
    except ValueError:
        return []

    if not isinstance(data, list) or not data:
        return []

    return data


def _geocode_query_variants(query: str) -> list[str]:
    """
    Варианты строки запроса для геокодинга.
    Для кириллицы без явной страны добавляется «запрос,RU», чтобы поднять релевантные
    российские совпадения (например «Москва» и «Москва,RU» дают разные наборы).
    """
    q = query.strip()
    if not q:
        return []

    variants = [q]
    if contains_cyrillic(q) and "," not in q:
        variants.append(f"{q},RU")
    return variants


def _is_likely_administrative_unit(location: dict) -> bool:
    """
    Эвристика: область, край, район, сельсовет, obasy и т.п. — не отдельный населённый пункт.

    Варианты из выдачи не удаляются: при сортировке таким строкам задаётся меньший приоритет,
    чтобы выше оказались обычные города и посёлки, если они есть среди результатов.
    """
    raw_name = (location.get("name") or "").strip()
    local = location.get("local_names") or {}
    ru = (local.get("ru") or "").strip()
    try:
        label_preview = build_location_label(location, show_coords=False).lower()
    except (TypeError, ValueError):
        label_preview = ""

    # Поле state не включаем: у обычного города регион может называться «… Oblast»,
    # иначе населённый пункт ошибочно считался бы «административной единицей».
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


def _country_priority_score(query: str, location: dict) -> float:
    """
    Дополнительный вес по стране: для кириллического запроса выше Россия и страны СНГ,
    остальные не удаляются, а получают меньший приоритет.
    """
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
    """
    Итоговая оценка полезности варианта для сортировки (чем больше — тем выше в списке).

    Административные единицы (области, края и т.д.) получают понижение балла, но остаются
    в выдаче, если других совпадений нет.
    """
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


def _dedupe_key(location: dict) -> tuple:
    """
    Ключ для схлопывания полных дублей: имя для отображения, страна, регион, координаты с шагом.
    """
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
    """Убирает дубликаты после сортировки по релевантности (оставляется лучший вариант)."""
    seen: set[tuple] = set()
    out: list[dict] = []
    for loc in sorted_locations:
        key = _dedupe_key(loc)
        if key in seen:
            continue
        seen.add(key)
        out.append(loc)
    return out


def _collect_geocode_candidates(query: str) -> list[dict]:
    """
    Собирает сырые ответы API по всем вариантам запроса (без повторной обработки).
    """
    merged: list[dict] = []
    for variant in _geocode_query_variants(query):
        merged.extend(_geocode_direct_raw(variant, 5))
    return merged


def _enrich_location_item(raw: dict) -> dict:
    """
    Добавляет к элементу ответа Geocoding API поля local_name и label для бота.
    """
    local_name = get_city_name_ru(raw)
    label = build_location_label(raw, show_coords=False)
    enriched = dict(raw)
    enriched["local_name"] = local_name
    enriched["label"] = label
    return enriched


def get_locations(query: str, limit: int = 5) -> list[dict] | None:
    """
    Ищет населённые пункты и локации по строке запроса (OpenWeather Geocoding API).

    Поддерживаются не только крупные города, но и малые населённые пункты,
    а также уточнение через запятую: «населённый пункт, регион, страна».

    Результаты дополнительно сортируются по полезности (релевантность имени, Россия/СНГ
    при кириллице, штраф за области/районы), схлопываются полные дубли, затем обрезаются
    до «limit» и обогащаются полями local_name и label.

    Возвращает список словарей: поля ответа API плюс local_name и label.
    Если ничего не найдено или запрос не удался — None.
    """
    if not OW_API_KEY:
        return None

    q = (query or "").strip()
    if not q:
        return None

    candidates = _collect_geocode_candidates(q)
    if not candidates:
        return None

    candidates.sort(
        key=lambda loc: (
            -_location_relevance_score(loc, q),
            0 if (loc.get("country") or "").upper() == "RU" else 1,
            (loc.get("name") or ""),
        )
    )
    deduped = _dedupe_geocode_sorted(candidates)
    cap = min(max(1, limit), 5)
    final = deduped[:cap]
    return [_enrich_location_item(item) for item in final]


def get_location_by_coordinates(lat: float, lon: float) -> dict | None:
    if not OW_API_KEY:
        return None

    url = "https://api.openweathermap.org/geo/1.0/reverse"
    params = {
        "lat": lat,
        "lon": lon,
        "limit": 1,
        "appid": OW_API_KEY
    }

    response = safe_request(url, params)

    if response is None or response.status_code != 200:
        return None

    try:
        data = response.json()
    except ValueError:
        return None

    if not data:
        return None

    return data[0]


def get_current_weather(lat: float, lon: float) -> dict | None:
    if not OW_API_KEY:
        return None

    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "lat": lat,
        "lon": lon,
        "appid": OW_API_KEY,
        "units": "metric",
        "lang": "ru"
    }

    response = safe_request(url, params)

    if response is None or response.status_code != 200:
        return None

    try:
        return response.json()
    except ValueError:
        return None


def get_coordinates(query: str, limit: int = 1) -> tuple[float, float] | None:
    """
    Возвращает координаты (широта, долгота) первой найденной локации по запросу.
    Внутри используется get_locations: берётся первый вариант из списка.
    """
    locations = get_locations(query=query, limit=limit)
    if not locations:
        return None

    first = locations[0]
    lat = first.get("lat")
    lon = first.get("lon")

    if lat is None or lon is None:
        return None

    return lat, lon


def format_weather(weather: dict) -> str:
    location_name = (
        weather.get("_display_location")
        or weather.get("name")
        or "неизвестный город"
    )

    temp = weather.get("main", {}).get("temp")
    description = weather.get("weather", [{}])[0].get("description", "без описания")

    if temp is None:
        return f"Погода в городе {location_name}: данные о температуре недоступны."

    return f"Погода в городе {location_name}: {temp:.1f}°C, {description}"


def get_forecast_5d3h(lat: float, lon: float) -> list[dict] | None:
    if not OW_API_KEY:
        return None

    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {
        "lat": lat,
        "lon": lon,
        "appid": OW_API_KEY,
        "units": "metric",
        "lang": "ru",
    }
    response = safe_request(url, params)

    if response is None or response.status_code != 200:
        return None

    try:
        data = response.json()
        items = data.get("list")
    except ValueError:
        return None

    if not isinstance(items, list):
        return None

    return items


def get_air_pollution(lat: float, lon: float) -> dict | None:
    if not OW_API_KEY:
        return None

    url = "https://api.openweathermap.org/data/2.5/air_pollution"
    params = {
        "lat": lat,
        "lon": lon,
        "appid": OW_API_KEY,
    }
    response = safe_request(url, params)

    if response is None or response.status_code != 200:
        return None

    try:
        data = response.json()
        items = data.get("list")
        if not items:
            return None
        components = items[0].get("components")
    except (ValueError, IndexError, AttributeError):
        return None

    if not isinstance(components, dict):
        return None

    return components


def analyze_air_pollution(components: dict, extended: bool = False) -> dict:
    """
    Анализирует загрязнение воздуха и возвращает итоговый статус и детали.
    Все статусы и описания возвращаются на русском языке.
    """
    if not isinstance(components, dict) or not components:
        return {
            "overall_status": "Нет данных",
            "details": "Данные о загрязнении воздуха недоступны.",
        }

    thresholds = {
        "pm2_5": {"good": 12, "moderate": 35, "bad": 55, "name": "PM2.5"},
        "pm10": {"good": 20, "moderate": 50, "bad": 100, "name": "PM10"},
        "no2": {"good": 40, "moderate": 100, "bad": 200, "name": "NO2"},
        "so2": {"good": 20, "moderate": 80, "bad": 250, "name": "SO2"},
        "o3": {"good": 60, "moderate": 120, "bad": 180, "name": "O3"},
        "co": {"good": 4400, "moderate": 9400, "bad": 12400, "name": "CO"},
    }

    severity_score = 0
    short_details = []
    detailed_details: dict[str, dict[str, Any]] = {}

    for key, rule in thresholds.items():
        value = components.get(key)
        if value is None:
            continue

        if value <= rule["good"]:
            status = "Хорошо"
            level = 0
        elif value <= rule["moderate"]:
            status = "Умеренно"
            level = 1
        elif value <= rule["bad"]:
            status = "Повышено"
            level = 2
        else:
            status = "Опасно"
            level = 3

        severity_score = max(severity_score, level)
        short_details.append(f'{rule["name"]}: {status.lower()}')
        detailed_details[key] = {
            "name": rule["name"],
            "value": value,
            "status": status,
        }

    overall_map = {
        0: "Хорошее",
        1: "Умеренное",
        2: "Повышенное",
        3: "Опасное",
    }
    overall_status = overall_map.get(severity_score, "Нет данных")

    if not extended:
        return {
            "overall_status": overall_status,
            "details": ", ".join(short_details) if short_details else "Недостаточно данных для анализа.",
        }

    return {
        "overall_status": overall_status,
        "details": detailed_details if detailed_details else "Недостаточно данных для анализа.",
    }