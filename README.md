# Weather Teller Telegram Bot

## English Summary

Weather Teller is a deployed Telegram weather assistant built with Python, PostgreSQL, Docker Compose, OpenWeather API and OpenAI API.
It provides current weather, tomorrow forecast, 5-day forecast, saved locations, location comparison, subscriptions and short AI explanations.
The project is in active beta testing and is designed to run locally or as a Docker Compose deployment.

## Описание

Weather Teller — Telegram-бот для погоды и погодных сценариев на каждый день. Он помогает быстро посмотреть прогноз, сохранить важные локации, сравнить погоду в двух местах и настроить подписки на погодные обновления.

Текущий статус: **v1.2 beta-ready / active beta testing**.

## Возможности

### Меню

Главное меню сгруппировано по разделам:

- 🌦 Прогноз погоды
- 📍 Локации
- 🔔 Подписки
- ℹ️ Помощь

### Прогноз погоды

- текущая погода;
- прогноз на завтра;
- прогноз на 5 дней;
- расширенные погодные данные;
- AI-пояснение текущей погоды;
- AI-пояснение прогноза на завтра;
- AI-пояснение выбранного дня прогноза;
- ввод локации текстом, координатами, геолокацией или через сохранённые локации.

### Локации

- сохранение важных локаций;
- добавление через город, координаты или геолокацию;
- переименование и удаление;
- защита от дублей;
- использование сохранённых локаций в погоде, прогнозе, расширенных данных, подписках и сравнении.

### Сравнение

- сравнение локаций сейчас;
- сравнение прогноза по двум локациям на дату;
- выбор каждой локации любым доступным способом;
- фактический нейтральный вывод без навязчивых рекомендаций.

### Подписки

- подписки на погодные обновления по нескольким локациям;
- настройка интервала;
- включение и выключение подписки;
- удаление подписки;
- хранение подписок в PostgreSQL.

### AI и кэширование

- OpenAI API для коротких погодных пояснений;
- deterministic fallback, если OpenAI API недоступен;
- OpenWeather API cache для погодных запросов;
- PostgreSQL AI cache для AI-ответов.

## Команды

Видимые команды для BotFather:

```text
start - Главное меню
weather - Прогноз погоды
locations - Локации
subscriptions - Подписки
help - Помощь
```

Команды в боте:

- `/start` — главное меню
- `/weather` — прогноз погоды
- `/locations` — локации
- `/subscriptions` — подписки
- `/help` — помощь

Дополнительно могут работать старые быстрые команды:

- `/current`
- `/tomorrow`
- `/forecast`
- `/details`
- `/compare`
- `/alerts`
- `/geo`

## Стек

- Python
- pyTelegramBotAPI
- Docker Compose
- PostgreSQL
- OpenWeather API
- OpenAI API
- pytest

## Структура проекта

```text
bot.py
flows.py
handlers/
weather/
ai/
ai_weather_service.py
postgres_storage.py
alerts_subscription_service.py
app_context.py
session_store.py
formatters.py
keyboards.py
Dockerfile
docker-compose.yml
docker-compose.postgres.yml
tests/
```

Ключевые модули:

- `bot.py` — точка входа, регистрация обработчиков, polling и фоновые процессы.
- `flows.py` — сценарии погодных flow.
- `handlers/` — текстовые и callback-обработчики.
- `weather/` — OpenWeather API, геокодинг, air quality и погодные helpers.
- `ai/` и `ai_weather_service.py` — prompt builders, fallback-логика, signatures и AI-интеграция.
- `postgres_storage.py` — хранение данных в PostgreSQL.
- `alerts_subscription_service.py` — логика подписок.
- `formatters.py` — пользовательские тексты.
- `keyboards.py` — reply и inline клавиатуры.

## Переменные окружения

Пример `.env` без секретов:

```env
BOT_TOKEN=your_telegram_bot_token
OW_API_KEY=your_openweather_api_key
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=your_openai_model

PGHOST=localhost
PGPORT=5432
PGDATABASE=weather_teller
PGUSER=weather_user
PGPASSWORD=change_me
```

Важно:

- не коммить реальные токены, IP-адреса серверов и production credentials;
- для локального запуска обычно используется `PGHOST=localhost`;
- для Docker Compose внутри контейнерной сети обычно используется `PGHOST=postgres`;
- `OPENAI_API_KEY` опционален: при его отсутствии погодные сценарии продолжают работать через fallback.

## Локальный запуск

1. Создать виртуальное окружение:

```bash
python -m venv venv
```

2. Активировать окружение.

Windows PowerShell:

```powershell
venv\Scripts\Activate.ps1
```

Windows CMD:

```cmd
venv\Scripts\activate.bat
```

3. Установить зависимости:

```bash
pip install -r requirements.txt
```

4. Подготовить `.env`:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

5. Заполнить `BOT_TOKEN`, `OW_API_KEY`, параметры PostgreSQL и при необходимости `OPENAI_API_KEY`.

6. Запустить PostgreSQL локально или через Docker Compose.

7. Запустить бота:

```bash
python bot.py
```

## Docker Compose

Запуск PostgreSQL отдельно для локальной разработки:

```bash
docker compose -f docker-compose.postgres.yml up -d
```

Остановка:

```bash
docker compose -f docker-compose.postgres.yml down
```

Запуск полного стека:

```bash
docker compose up -d --build
```

Остановка полного стека:

```bash
docker compose down
```

Для Docker Compose проверь, что в `.env` указан контейнерный хост PostgreSQL, например `PGHOST=postgres`.

## PostgreSQL

В базе хранятся:

- `users` — пользовательские настройки и последняя рабочая локация;
- `saved_locations` — сохранённые локации;
- `alert_subscriptions` — подписки на погодные обновления;
- `ai_response_cache` — кэш AI-ответов.

Пример входа в `psql` внутри контейнера:

```bash
docker exec -it weather_postgres psql -U weather_user -d weather_teller -P pager=off
```

## Тесты

Запуск тестов:

```bash
pytest
```

Проверка компиляции Python-файлов:

```bash
python -m compileall .
```

## Roadmap

### Near-term

- location-not-found copy polish;
- more beta wording fixes.

### Experimental, not merged yet

- Open-Meteo fallback if OpenWeather fails;
- compare forecast across two sources.

### Later

- voice input;
- TTS for AI explanations;
- climate/historical context;
- separate air quality module.

## Автор

Автор: Елена Шленскова
Telegram: @elena_shlenskova
