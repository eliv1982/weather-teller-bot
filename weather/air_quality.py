from typing import Any


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
