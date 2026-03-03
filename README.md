# Localos.pro — SEO-анализатор и платформа для продвижения локального бизнеса

## Описание

localos.pro — сервис для анализа и продвижения локального бизнеса на картах и в онлайн-каналах. Позволяет автоматически проанализировать SEO-оптимизацию публичной карточки компании на Яндекс.Картах, получить рекомендации по улучшению и автоматизировать процессы привлечения и удержания клиентов.

**Целевая аудитория**: салоны красоты, мастера, студии, локальные сервисы, которые зависят от потока клиентов с карт и отзывов.

## Возможности

### Основной функционал
- Парсинг публичных данных карточки (название, адрес, рейтинг, отзывы и др.)
- Оценка SEO-параметров и генерация рекомендаций
- Генерация HTML-отчётов с анализом
- Антибан: рандомизация User-Agent, поддержка прокси
- Веб-интерфейс для создания и просмотра отчётов
- Автоматическая обработка очереди запросов

### Дополнительные возможности
- 📊 Финансовый дашборд с аналитикой и круговыми диаграммами
- 💰 Управление транзакциями (загрузка фото/файлов, распознавание через GigaChat)
- 🤖 Telegram-боты:
  - Бот для управления аккаунтом (добавление транзакций, оптимизация услуг)
  - Бот для обмена отзывами между пользователями
- 🏢 Поддержка сетей бизнесов
- 👥 Управление мастерами и услугами
- 📈 ROI калькулятор
- 🌐 Мультиязычный интерфейс

### Текущий статус платформы (март 2026)
- ✅ Завершён integration roadmap LocalOS ↔ OpenClaw (Phase 1–9)
- ✅ Работают:
  - Action Orchestrator + billing ledger + human-in-the-loop
  - M2M callbacks / outbox / retry / DLQ
  - diagnostics, incident snapshot/report, recovery и support export
  - unified audit timeline
  - Telegram control surface с approve/reject в чате
  - unified multi-channel routing (Telegram / WhatsApp / Maton bridge)
- 🔄 Следующий продуктовый трек:
  - supervised outreach для поиска и аккуратного первого касания потенциальных клиентов
  - режим только с ручным подтверждением на каждом шаге

### Архитектура Telegram-ботов и уведомлений

- **Глобальный бот BeautyBot (`TELEGRAM_BOT_TOKEN`)**
  - Используется по умолчанию для всех уведомлений владельцам салонов (новые бронирования, запросы поддержки из ChatGPT и т.п.).
  - Владелец привязывает свой Telegram к аккаунту (поле `telegram_id` в таблице `Users`).
  - Все служебные уведомления приходят в личный Telegram владельца от одного общего бота.
- **Боты конкретных бизнесов (`telegram_bot_token` в таблице `Businesses`)**
  - Нужны только если салон хочет **свой брендированный бот** для клиентов и ИИ-агента.
  - Используются в webhooks ИИ-агента (`/api/webhooks/telegram`), когда бот общается напрямую с клиентами.
  - В уведомлениях владельцу (support-запросы, бронирования) поле `telegram_bot_token` опционально: если заполнено — уведомление может уйти через бот салона, если нет — через глобальный BeautyBot.
- **Простой сценарий**
  - Для большинства случаев достаточно одного глобального бота BeautyBot; `telegram_bot_token` заполняется только там, где действительно нужен свой брендированный вход для клиентов/ИИ-агента.

## Технический стек

- **Backend**: Python 3.11, Flask 2.3
- **Frontend**: TypeScript, React 18, Vite 7, TailwindCSS 3.4, Radix UI, shadcn/ui
- **Парсинг**: Selenium, Playwright, BeautifulSoup, pandas
- **AI**: GigaChat API, Transformers, Hugging Face API
- **Инфраструктура**: Docker, Docker Compose, Nginx, systemd, venv (для локальных тестов)
- **База данных (runtime)**: PostgreSQL 16 в Docker
  - **Legacy**: SQLite (`src/reports.db`) используется только для старых отчётов и вспомогательных скриптов
  - **Текущее состояние**: 51+ таблица (на сервере) / 48 таблиц (локально, после миграции ИИ агента)
  - **План оптимизации**: уменьшение до 40-41 таблицы (удаление дублирующих таблиц, объединение похожих)
  - **Основные таблицы (в PostgreSQL — имена в нижнем регистре)**: users, businesses, businessprofiles, userservices, parsequeue, cards, externalbusinessaccounts, businessmaplinks, businessmetricshistory, externalbusinessstats, externalbusinessreviews; AIAgents, AIAgentConversations, AIAgentMessages, Bookings
  - **Иерархия**: Users → Businesses → все остальные данные (все привязано к `business_id`)
  - **Новые таблицы (2025-01-06)**: 
    - `AIAgentConversations` - разговоры с ИИ-агентом (WhatsApp, Telegram)
    - `AIAgentMessages` - сообщения в разговорах с ИИ-агентом
  - **Новые поля в Businesses**: 
    - `waba_phone_id`, `waba_access_token` - для интеграции с WhatsApp Business API
    - `whatsapp_phone`, `whatsapp_verified` - для верификации и уведомлений в WhatsApp
    - `telegram_bot_token` - токен пользовательского Telegram бота
    - `ai_agent_enabled`, `ai_agent_tone`, `ai_agent_restrictions` - настройки ИИ-агента
  - **BusinessProfiles**:
    - ключ профиля: `business_id` (PRIMARY KEY), отдельного `id` у runtime-схемы нет
    - поля: `contact_name`, `contact_phone`, `contact_email`, `created_at`, `updated_at`
  - **Безопасность**: автоматические бэкапы перед миграциями, WAL режим для параллельной работы
  - **Последние исправления (2025-01-06)**:
    - Исправлены синтаксические ошибки в обработке результатов генерации (новости, ответы, оптимизация услуг)
    - Унифицирована обработка JSON-ответов от GigaChat API
    - Улучшена обработка ошибок парсинга дат и ответов организации
- **Внешние интеграции**: Яндекс.Бизнес, Google Business Profile, 2ГИС (с шифрованием auth_data)

### Авторизация и блокировка пользователей (PostgreSQL)

- В таблице **users** используются флаги:
  - **`is_active`** (BOOLEAN, по умолчанию TRUE) — блокировка аккаунта (например, при неоплате); при `FALSE` вход и доступ к API запрещены.
  - **`is_verified`** (BOOLEAN, по умолчанию TRUE) — верификация пользователя (email и т.п.); используется в логике авторизации и отображении.
  - **`is_superadmin`** (BOOLEAN, по умолчанию FALSE) — доступ ко всем бизнесам и админ-функциям.
- **Поведение API:**
  - **401 Unauthorized** — неверные логин/пароль, отсутствующий или недействительный токен.
  - **403 Forbidden** — пользователь заблокирован (`is_active = FALSE`); в теле ответа: `{"error": "account_blocked", "message": "user is blocked"}`.
- Миграции, добавляющие эти колонки, применяются при старте контейнеров (Flask-Migrate в entrypoint). После обновления кода с новыми миграциями выполните: `docker compose up -d --build`.

## Порты и сервисы

📖 **Подробная информация**: см. [PORTS_AND_SERVICES.md](./PORTS_AND_SERVICES.md)

| Сервис | Порт | Описание |
|--------|------|----------|
| Фронтенд (Dev) | `3000` | Vite dev server |
| Фронтенд (Prod) | `80/443` | Nginx (статический фронтенд) |
| Бэкенд API | `8000` | Flask API сервер |
| Бот управления | - | Systemd сервис (polling) |
| Бот обмена отзывами | - | Systemd сервис (polling) |

## Документация

- 📖 [Порты и сервисы](./PORTS_AND_SERVICES.md) — схема портов, проверка процессов
- 🔄 [Алгоритм обновления](./ALGORITHM_UPDATE.md) — порядок применения изменений
- 🤖 [Настройка Telegram-ботов](./TELEGRAM_BOTS_SETUP.md) — установка и запуск ботов
- 🔌 [Контракт LocalOS↔OpenClaw (Phase 1)](./docs/contracts/localos-openclaw/PHASE1.md) — capability API, статусы, примеры запросов/ответов
- 🧭 [OpenClaw Ops Runbook](./docs/OPENCLAW_PHASE1_OPS_RUNBOOK.md) — smoke/recovery/deploy/acceptance команды
- ✅ [OpenClaw Phase 2 Handoff Checklist](./docs/OPENCLAW_PHASE2_HANDOFF_CHECKLIST.md) — production-ready handoff и критерии приёмки
- ✅ [OpenClaw Phase 3 Handoff Checklist](./docs/OPENCLAW_PHASE3_HANDOFF_CHECKLIST.md) — diagnostics/support acceptance и handoff
- 🚦 [OpenClaw CI Gate](./scripts/ci_gate_openclaw_phase2.sh) — обязательные проверки Phase 2 перед деплоем
- 🏗️ [Архитектура БД](./database_schema_design.md) — структура базы данных
- 📊 [Полная структура БД](./database_schema.md) — детальная документация (PostgreSQL)
- 🔧 [План оптимизации БД](./DB_OPTIMIZATION_PLAN.md) — план уменьшения до 40-41 таблицы
- 🔗 [Настройка внешних интеграций](./INTEGRATIONS_SETUP.md) — Яндекс.Бизнес, Google Business, 2ГИС

## Roadmap Note: Outreach

- В админской панели уже есть ранний раздел `Поиск клиентов`.
- Текущая реализация использует Apify и умеет только:
  - искать
  - сохранять лиды
  - менять базовый статус
- Следующая итерация этого раздела переводится в полноценный supervised outreach pipeline:
  1. сбор кандидатов
  2. ручной shortlist
  3. ручной выбор адресатов
  4. AI-черновики первого сообщения
  5. ручное утверждение текста
  6. capped sending (старт с 10/день)
  7. learning loop по ответам и вашим правкам
- Для Yandex-first sourcing планируется actor:
  - `m_mamaev/yandex-maps-places-scraper`
- Sprint 0 для этого трека:
  - перевести поиск на async jobs
  - закрыть admin-only доступ
  - заменить текущий sync search на staged ingestion foundation
- Sprint 1 (текущий):
  - staged UI поверх существующих лидов
  - фильтры по кандидатам
  - первый ручной этап `В shortlist / Отклонить`
- Sprint 1.5 / Sprint 2A:
  - экран `Отбор для контакта` поверх `shortlist_approved`
  - ручной перевод лида в `selected_for_outreach`
  - ручной выбор канала (`Telegram / WhatsApp / Email / Manual`)
  - фиксация статуса `channel_selected`
- Sprint 2B:
  - экран `Черновики первого сообщения`
  - генерация первого черновика для лидов в `channel_selected`
  - ручное утверждение текста и сохранение правок как learning examples
- Sprint 2C:
  - дневная очередь отправки
  - capped batch (`10/день`)
  - ручное подтверждение batch перед реальной отправкой
- Runtime parsing hardening:
  - фильтрация редакционных подборок Яндекс.Карт из синка услуг
  - `POST /api/business/<business_id>/parse-resume` для human-in-the-loop после прохождения captcha

## Runtime Safety Notes

- При старте контейнеров `app` и `worker` миграции должны выполняться под PostgreSQL advisory lock.
- Это защищает от deadlock при одновременном `docker compose restart app worker`, когда оба entrypoint пытаются сделать `flask db upgrade`.
- При `captcha` в `parsequeue` пользователь должен получать `captcha_url`, проходить проверку и затем явно запускать `POST /api/business/<business_id>/parse-resume`.
- Ожидаемые routing-ошибки (`404/405`, включая внешние `CONNECT` probes) не должны логироваться как фатальные серверные аварии.

## Установка

### Через Docker (основной сценарий)

1. Установите Docker и Docker Compose.
2. Клонируйте репозиторий на машину (dev или сервер).
3. Создайте `.env` в корне проекта (переменные для PostgreSQL и секреты; пример — ниже в секции «Docker»).
4. Запустите сервисы:
   ```bash
   docker compose up -d --build
   ```
5. Backend будет доступен на `http://localhost:8000` (или на соответствующем хосте/порте сервера).

Детали конфигурации контейнеров и миграций — в разделе **Docker** ниже.

### Локальная разработка без Docker (опционально)

Этот режим нужен только для отладки отдельных модулей (например, unit‑тестов) без поднятия контейнеров.

1. Клонируйте репозиторий.
2. Создайте и активируйте виртуальное окружение:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   pip install -r requirements.test.txt
   ```
3. Для Playwright‑парсера (если запускаете его с хоста) выполните:
   ```bash
   python3 -m playwright install
   ```

Запуск всего приложения (API, воркер, БД) в этом режиме **не рекомендуется**; для runtime используйте Docker.

## Запуск

### Через Docker (рекомендуется)

```bash
docker compose up --build        # сборка и запуск в foreground
docker compose up -d             # запуск в фоне
```

- Backend API: `http://localhost:8000`
- Миграции применяются автоматически в entrypoint контейнеров `app` и `worker`.

### Локальные тесты без Docker

Для быстрого прогона unit‑тестов (в том числе проверки валидации результата парсинга):

```bash
source venv/bin/activate
pytest -q tests/test_parsed_payload_validation.py
```

Unit‑тесты парсера Яндекс.Карт (org-bound, extract object, scoring, wait logic):

```bash
python3 tests/test_parser_interception.py --unit-only
```

Для полного прогона тестов (A–I) и gate‑тестов `/api/client-info` см. раздел **Тестирование** ниже и секцию «Gate‑тесты и smoke в Docker».

## Docker

Окружение одинаково запускается локально и на сервере: приложение и PostgreSQL в разных контейнерах, данные БД хранятся в volume.

**Сервисы:**
- **postgres** — PostgreSQL 16, данные в volume `pgdata`
- **app** — backend (Flask, порт 8000); при старте ждёт Postgres и выполняет `flask db upgrade`
- **worker** — воркер очереди (тот же образ); при старте тоже выполняет миграции, затем запуск воркера

Миграции (Flask-Migrate) применяются автоматически в entrypoint контейнеров app и worker. Таблицы (в т.ч. `parsequeue`) создаются при первом запуске.

**Локальный запуск:**

```bash
# Сборка и запуск в foreground
docker compose up --build

# Или в фоне
docker compose up -d
```

Backend будет доступен на `http://localhost:8000`. Проверка: `curl -s http://localhost:8000/health`.

**Запуск на сервере (VPS):**

1. Установите Docker и Docker Compose на сервер.
2. Склонируйте репозиторий (или скопируйте проект) в каталог на сервере.
3. При необходимости создайте `.env` в корне проекта:
   ```bash
   POSTGRES_USER=local
   POSTGRES_PASSWORD=<надёжный_пароль>
   POSTGRES_DB=local
   ```
4. Запустите:
   ```bash
   docker compose up -d --build
   ```
5. Данные PostgreSQL сохраняются в volume `pgdata`; при пересоздании контейнеров данные не теряются.

**Gate-тесты и smoke в Docker:**

Тесты запускаются **из контейнера app** (не с хоста). Для gate-тестов с testcontainers нужны:
- доступ к Docker daemon (в `docker-compose.yml` пробрасывается `/var/run/docker.sock`, задаётся `DOCKER_HOST=unix:///var/run/docker.sock`);
- `extra_hosts: host.docker.internal:host-gateway` — чтобы контейнер app мог достучаться до Postgres testcontainers;
- переменная окружения `TESTCONTAINERS_HOST_OVERRIDE=host.docker.internal`.

Отдельная команда для gate-тестов client-info:

```bash
docker compose exec app python -m pytest -q tests/test_client_info_gate.py
```

Перед первым запуском установите тестовые зависимости в контейнере: `docker compose exec app pip install -r requirements.test.txt`.

```bash
# Smoke DatabaseManager
docker compose run --rm app python scripts/smoke_db_manager.py

# Smoke client-info
docker compose run --rm app python scripts/smoke_client_info_gate.py
```

Для smoke в `DATABASE_URL` подставляется подключение к контейнеру `postgres`; убедитесь, что контейнеры postgres и app подняты (`docker compose up -d`).

**Важно:** Бизнес-логика и runtime-код не зависят от Docker; меняется только способ запуска и переменные окружения. Подробнее: [docs/DOCKER_DEPLOY.md](./docs/DOCKER_DEPLOY.md).

### Миграции (Flask-Migrate)

Схема БД управляется через Flask-Migrate (Alembic). Миграции лежат в каталоге `alembic_migrations/` (кастомные скрипты — в `migrations/`).

**Локально** (при наличии Postgres и `DATABASE_URL` в `.env`):

```bash
export FLASK_APP=src.main:app
export PYTHONPATH="$(pwd)/src:$(pwd)"
flask db upgrade
```

Создать новую миграцию после изменения моделей/схемы:

```bash
flask db migrate -m "описание"
flask db upgrade
```

**В Docker** миграции выполняются в entrypoint перед запуском app и worker; вручную:

```bash
docker compose run --rm app flask db upgrade
```

**Одноразовый перенос данных SQLite → Postgres** (когда схема в Postgres уже создана Alembic):

```bash
# В Docker: указать путь к файлу SQLite (например, смонтированный или скопированный legacy.db)
docker compose exec -e SQLITE_PATH=/app/legacy.sqlite app python scripts/migrate_sqlite_to_postgres.py

# Локально
SQLITE_PATH=./src/reports.db DATABASE_URL=postgresql://user:pass@localhost/db python scripts/migrate_sqlite_to_postgres.py

# Только счётчики, без записи
python scripts/migrate_sqlite_to_postgres.py --dry-run

# Выборочно таблицы
python scripts/migrate_sqlite_to_postgres.py --tables users,businesses,userservices
```

Подробности: комментарий вверху `scripts/migrate_sqlite_to_postgres.py`. После переноса smoke `scripts/smoke_client_info_gate.py` должен находить бизнесы (не выводить «нет ни одного бизнеса»).

### Правила работы со схемой БД и миграциями

- **Runtime не использует SQLAlchemy** — доступ к БД идёт через psycopg2. SQLAlchemy и Flask-Migrate используются только для миграций.
- **Миграции** лежат в `alembic_migrations/` (не в стандартной `migrations/`). Initial-миграция `20250207_initial_parsequeue.py` уже применена и не должна изменяться.
- **Данные в БД терять нельзя.** Вносить только минимально необходимые изменения. Ничего не удалять из существующих таблиц (users, businesses, parsequeue).
- **Изменения схемы — только через новую Alembic-миграцию:** новая ревизия; в `upgrade()` — безопасный DDL (`CREATE TABLE IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`); в `downgrade()` — откат только изменений этой ревизии.
- **Runtime-код** (psycopg2, SQL-запросы) не переписывать без необходимости. Не менять `entrypoint.sh`, Docker-логику и порядок запуска контейнеров.
- **Новая таблица / колонка / индекс:** сначала миграция, затем минимальная адаптация runtime-кода.
- **Исправление ошибки:** определить, DDL это или логика; DDL → миграция; логика → аккуратный патч без изменения контракта БД.
- **Обратная совместимость** с уже развёрнутой БД. Код должен быть готов к повторному `flask db upgrade` (no-op при повторном запуске).

### Backend: парсинг и внешние аккаунты (PostgreSQL)

В runtime все запросы к БД используют **имена таблиц в нижнем регистре** и плейсхолдеры **`%s`** (psycopg2). Результаты парсинга карт и синхронизаций пишутся в **cards** (source of truth), а не в MapParseResults.

- **Очередь парсинга**: таблица **parsequeue**; задачи создаются через `POST /api/admin/yandex/sync/business/<id>` (при наличии ссылки на карты или аккаунта Яндекс.Бизнес). Воркер обрабатывает задачи и сохраняет результат в **cards** через `DatabaseManager.save_new_card_version`.
- **Внешние аккаунты**: таблица **externalbusinessaccounts**; API: `GET/POST /api/business/<id>/external-accounts`. Upsert по `(business_id, source)`; при создании обязателен `auth_data` (строка или JSON-объект); в ответе `auth_data` не возвращается. В dev в ответах может быть `_debug` (tableName, saved_fields, action и т.п.).
- **2ГИС**: `POST /api/admin/2gis/sync/business/<id>` возвращает **501** с JSON `{ "success": false, "message": "2ГИС синк пока не реализован", "where": "admin_sync_business_2gis" }` (без 404 и без падения).
- **Ошибки API**: при любом исключении ответ — JSON с полями `success: false`, `error`, `error_type`; в режиме `app.debug` добавляется `traceback`. Нет ответов с телом «Критическая ошибка: 0» или HTML.

## Тестирование (PostgreSQL + HITL worker)

**Основной путь (один раз установить зависимости, затем запускать тесты):**

```bash
pip install -r requirements.test.txt
pytest -q
```

При **доступном Docker** (daemon запущен, `docker.from_env().ping()` успешен) прогоняются все gate-тесты для `/api/client-info`: **A–B–C–D–E–F–H** (с Postgres в testcontainers и применением миграций `flask db upgrade`) и статический тест **G** (проверка отсутствия PRAGMA/ClientInfo в runtime). Skip только если Docker реально недоступен. Дополнительно есть unit‑тест **I** (валидация результата парсинга), который не требует Docker и БД.

Что проверяется:

- корректное сохранение состояний `captcha / waiting / resume / expired` в таблице **parsequeue**
  (`tests/test_worker_captcha_flow.py`, `tests/test_worker_resume_flow.py`, `tests/test_worker_expired_flow.py`);
- поведение оркестратора `parser_interception.parse_yandex_card` в HITL-режиме
  (парковка/закрытие сессий, обработка `captcha_session_lost`) в `tests/test_parser_orchestrator.py`;
- gate-тесты `/api/client-info`: GET/POST по business_id, идемпотентность, пустые ссылки, GET без business_id, 404, отсутствие PRAGMA/ClientInfo в `src/`, видимость данных в новой транзакции (`tests/test_client_info_gate.py`).

Особенности:

- тесты поднимают временный PostgreSQL через `testcontainers.postgres`; боевая БД не затрагивается;
- перед gate-тестами выполняется `flask db upgrade` (таблицы users, businesses, parsequeue, businessmaplinks и др. создаются миграциями);
- каждое тестовое окружение использует свою схему `test_<uuid>` и таблицу **parsequeue**;
- Playwright в тестах не запускается — все вызовы браузера и парсера замоканы.

### Smoke-тесты

Быстрые проверки без поднятия testcontainers.

**1. Smoke-тест DatabaseManager (PostgreSQL)**

Проверяет основные методы `DatabaseManager` после миграции на Postgres: подключение, чтение пользователей/бизнесов/отчётов/услуг, версионирование карточек.

```bash
# Требуется DATABASE_URL в .env
python scripts/smoke_db_manager.py
```

Проверяется: подключение к БД, `get_user_by_email`, `get_businesses_by_owner`, `get_business_by_id`, `get_reports_by_business`, `get_services_by_business`, версионирование карточек (`save_new_card_version`, `get_latest_card_by_business`, `get_card_history_by_business`). В конце выводится счётчик вида `X/7 тестов прошли`.

**2. Smoke-тест результатов парсинга (SQLite)**

Проверяет наличие данных парсинга для тестового бизнеса (например, «Oliver»): количество услуг и отзывов в `reports.db`. Использует SQLite, не Postgres.

```bash
# Запуск из корня проекта; нужен файл reports.db в текущей директории
python tests/smoke_test_parsing_results.py
```

### Gate-тесты для /api/client-info

Входят в общий прогон `pytest -q` (см. выше). Проверяют, что эндпоинт работает только через Postgres (businessmaplinks + businesses), без PRAGMA/ClientInfo.

**Запуск gate-тестов:** A–H (с testcontainers) выполняются **внутри контейнера app**. На хосте должен быть доступ к Docker daemon; в `docker-compose.yml` для сервиса `app` заданы проброс сокета, `DOCKER_HOST`, `extra_hosts: host.docker.internal:host-gateway` и `TESTCONTAINERS_HOST_OVERRIDE=host.docker.internal`. Команда:

```bash
docker compose exec app python -m pytest -q tests/test_client_info_gate.py
```

(Предварительно: `docker compose exec app pip install -r requirements.test.txt`.) Локально на хосте (без Docker) можно по-прежнему запускать:

```bash
pip install -r requirements.test.txt
pytest tests/test_client_info_gate.py -v
```

- **A** — GET с `business_id` → 200, ссылки из businessmaplinks.
- **B** — POST mapLinks → 200, затем GET возвращает те же ссылки.
- **C** — два одинаковых POST → в businessmaplinks ровно N строк (идемпотентность).
- **D** — POST с пустыми mapLinks → 0 строк, GET → пустой список.
- **E** — GET без business_id → данные первого бизнеса пользователя.
- **F** — GET с несуществующим business_id → 404.
- **G** — статический тест: в runtime (`src/`, без `scripts` и `migrate_*.py`) нет вхождений `PRAGMA table_info(ClientInfo)`, `FROM ClientInfo`, `INTO ClientInfo`.
- **H** — после POST данные читаются из нового соединения (проверка commit).
- **I** — unit‑тест для `parsed_payload_validation.validate_parsed_payload` и хелперов (`_has_content`, `_resolve_categories`, one‑of `title_or_name`, `quality_score`): `tests/test_parsed_payload_validation.py`. Запуск: `pytest -q tests/test_parsed_payload_validation.py` (локально в venv, без Docker и БД).
- **Parser interception** — unit‑тесты парсера Яндекс.Карт: org-bound валидация, извлечение объекта организации, scoring, ожидание fetchGoods. Запуск: `python3 tests/test_parser_interception.py --unit-only` (без браузера).

**Smoke (локальный DATABASE_URL, для dev/stage):**

```bash
# Требуется DATABASE_URL в .env
python scripts/smoke_client_info_gate.py
```

## Деплой на сервер

### 1. Настройка systemd сервисов

#### Worker (обработка очереди парсинга)
Создайте файл `/etc/systemd/system/seo-worker.service`:
```ini
[Unit]
Description=SEO Worker Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/mapsparser-Replit-front
Environment=PYTHONPATH=/root/mapsparser-Replit-front/src
ExecStart=/root/mapsparser-Replit-front/venv/bin/python /root/mapsparser-Replit-front/src/worker.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### Telegram-боты
- Бот для управления аккаунтом: см. [TELEGRAM_BOTS_SETUP.md](./TELEGRAM_BOTS_SETUP.md)
- Бот для обмена отзывами: см. [TELEGRAM_BOTS_SETUP.md](./TELEGRAM_BOTS_SETUP.md)

### 2. Переменные окружения

Создайте файл `.env` в корне проекта:
```bash
# Telegram боты
TELEGRAM_BOT_TOKEN=токен_для_Local_bot
TELEGRAM_REVIEWS_BOT_TOKEN=токен_для_beautyreviewexchange_bot

# API
API_BASE_URL=http://localhost:8000

# GigaChat (для AI функций)
GIGACHAT_CLIENT_ID=ваш_client_id
GIGACHAT_CLIENT_SECRET=ваш_client_secret

# Шифрование для внешних интеграций (Яндекс.Бизнес, Google Business, 2ГИС)
# ВАЖНО: Используйте случайную строку длиной 32+ символов для продакшена!
EXTERNAL_AUTH_SECRET_KEY=ваш_секретный_ключ_для_шифрования_32_символа_минимум

# Режим тестирования внешних интеграций (без реальных запросов к кабинетам)
# Установите в 1 для тестирования с демо-данными
YANDEX_BUSINESS_FAKE=0

# SMTP (для отправки email)
SMTP_SERVER=mail.hosting.reg.ru
SMTP_PORT=587
SMTP_USERNAME=info@local.pro
SMTP_PASSWORD=ваш_пароль
```

### 3. Запуск сервисов
```bash
systemctl daemon-reload
systemctl enable seo-worker
systemctl start seo-worker
systemctl enable telegram-bot
systemctl start telegram-bot
systemctl enable telegram-reviews-bot
systemctl start telegram-reviews-bot
```

### 4. Проверка работы
```bash
# Проверить все сервисы
systemctl status seo-worker
systemctl status telegram-bot
systemctl status telegram-reviews-bot
systemctl status nginx

# Проверить порты
lsof -i :8000  # Бэкенд API
lsof -i :80    # Nginx HTTP
lsof -i :443   # Nginx HTTPS
```

## Как коммитить изменения

1. **Проверьте статус**: `git status -sb`.
2. **Добавьте файлы**: `git add <путь>`. Для массового добавления используйте `git add .`.
3. **Создайте коммит**: `git commit -m "Краткое описание изменений"`.
4. **Подготовьте токен**:
   - Установите переменную окружения `export GITHUB_TOKEN=<ваш токен>`, либо
   - Однократно сохраните креды: `git config credential.helper store` и выполните `git credential fill`/`approve`.
5. **Отправьте изменения**:
   ```bash
   git push https://$GITHUB_TOKEN@github.com/Kastrulkin/mapsparser-Replit-front.git main
   ```
   или, если helper уже настроен: `git push origin main`.
6. **Безопасность**: не добавляйте токен в коммит и не храните его в репозитории. Для временных сессий можно экспортировать токен только на время пуша.

## Структура проекта

```
├── src/                    # Исходный код бэкенда
│   ├── main.py            # Flask API сервер
│   ├── worker.py          # Воркер для обработки очереди
│   ├── telegram_bot.py    # Бот для управления аккаунтом
│   ├── telegram_reviews_bot.py  # Бот для обмена отзывами
│   ├── templates/         # Шаблоны для HTML-отчётов
│   ├── services/          # Сервисы (GigaChat и др.)
│   ├── core/              # Core модули
│   │   ├── db_helpers.py  # Helper функции для БД
│   │   └── helpers.py     # Общие helper функции
│   ├── reports.db         # База данных SQLite (51 таблица на сервере, 46 локально)
│   └── migrate_*.py       # Миграции БД (оптимизация структуры)
├── frontend/              # Веб-интерфейс (React + Vite)
│   ├── src/              # Исходники React
│   └── dist/             # Собранный фронтенд
├── migrations/            # Миграции базы данных
├── db_backups/            # Резервные копии БД (автоматические бэкапы перед миграциями)
├── prompts/              # Промпты для AI
├── .cursor/              # Документация и правила проекта
│   └── docs/             # Архитектурные решения, верификация, упрощение
└── .env                  # Переменные окружения
```

### Структура базы данных

**Текущее состояние:**
- **51 таблица** на сервере / **46 таблиц** локально
- **Основные категории таблиц:**
  - **Пользователи и авторизация**: Users, UserSessions, UserLoginHistory
  - **Бизнесы**: Businesses, Networks, BusinessMapLinks
  - **Услуги и контент**: UserServices, UserNews, UserExamples (объединены из UserNewsExamples, UserReviewExamples, UserServiceExamples)
  - **Финансы**: FinancialTransactions, FinancialMetrics, ROIData
  - **Парсинг**: parsequeue (очередь задач), cards (результаты парсинга — source of truth в PG), externalbusinessaccounts, externalbusinessreviews, externalbusinessposts, externalbusinessphotos, externalbusinessstats
  - **AI и интеграции**: AIAgents, AIAgentConversations, ChatGPTUserSessions, TokenUsage
  - **Бронирования**: Bookings, StripePayments, CRMIntegrations
  - **Telegram**: TelegramBindTokens, ReviewExchangeParticipants
  - **Оптимизация**: BusinessOptimizationWizard, PricelistOptimizations, GrowthStages, GrowthTasks

**План оптимизации (3 этапа):**
1. ✅ **Добавление индексов** - ускорение запросов в 5-10 раз (`migrate_add_missing_indexes.py`)
2. ⏳ **Удаление дублирующих таблиц** - ClientInfo, GigaChatTokenUsage, Cards (`migrate_remove_duplicate_tables.py`)
3. ⏳ **Объединение похожих таблиц** - UserExamples уже объединены (`migrate_merge_examples_tables.py`)

**Ожидаемый результат:** 40-41 таблица (упрощение схемы, устранение дублирования)

**Принципы:**
- Все данные привязаны к `business_id` (не к `user_id`)
- `user_id` используется только для авторизации
- Суперадмин видит все бизнесы, обычные пользователи - только свои
- Автоматические бэкапы перед миграциями через `safe_migrate()`

## Ограничения и требования

- **Браузер**: Для парсинга требуется установленный Google Chrome или Chromium
- **Капча**: Если Яндекс.Карты требуют капчу — попробуйте сменить прокси или User-Agent
- **Воркер**: Обрабатывает задачи из таблицы **parsequeue** каждые 5 минут; результаты парсинга пишутся в **cards** (PostgreSQL)
- **База данных**: SQLite — для продакшена рекомендуется PostgreSQL
- **Память**: Playwright требует достаточно памяти для запуска браузера

## Обновление проекта

📖 **Подробная инструкция**: см. [ALGORITHM_UPDATE.md](./ALGORITHM_UPDATE.md)

### Через Docker (основной сценарий)

После изменений в коде (`git pull` или локальные правки):

```bash
./scripts/docker-compose-build.sh up -d --build
```

Скрипт пересобирает образы (включая фронтенд — multi-stage build в Dockerfile) и перезапускает контейнеры. Миграции БД применяются автоматически при старте.

При необходимости принудительно пересоздать контейнеры:

```bash
./scripts/docker-compose-build.sh up -d --build --force-recreate
```

Фронтенд для разработки с hot-reload: `cd frontend && npm run dev`.

### Без Docker (systemd, Nginx)

**Кратко (РЕКОМЕНДУЕТСЯ):**
```bash
cd /root/mapsparser-Replit-front
bash update_server.sh
```

**Вручную (если скрипт недоступен):**
1. После изменений в `frontend/src/*` → пересобрать: `cd frontend && npm run build && cp -r dist/* /var/www/html/`
2. После изменений в `src/*.py` → перезапустить: `systemctl restart seo-api seo-worker`
3. После изменений в БД → создать бэкап и применить миграцию

## Интеграция с внешними источниками (Яндекс.Бизнес, Google Business, 2ГИС)

### Настройка Яндекс.Бизнес

Для подключения личного кабинета Яндекс.Бизнес через админскую панель:

1. **Войдите в личный кабинет Яндекс.Бизнес** в браузере
2. **Скопируйте cookies** из браузера:
   - Откройте DevTools (F12) → вкладка "Application" (Chrome) или "Storage" (Firefox)
   - Найдите раздел "Cookies" → выберите домен `business.yandex.ru` или `yandex.ru`
   - Скопируйте все cookies в формате: `yandexuid=...; Session_id=...; yandex_login=...; и т.д.`
3. **В админской панели** (Пользователи и бизнесы → кнопка "Настройки"):
   - Вставьте cookies в поле "Cookies / Токен сессии"
   - Опционально: укажите `external_id` (ID организации в Яндекс.Бизнес) и `display_name`
   - Нажмите "Сохранить"

**Формат данных для Яндекс.Бизнес:**
- **Cookies**: строка вида `yandexuid=123456789; Session_id=abc123def456; yandex_login=user@example.com`
- **external_id** (опционально): ID организации в Яндекс.Бизнес (можно найти в URL кабинета)
- **display_name** (опционально): название организации для удобства

**Для тестирования без реальных запросов:**
- Установите в `.env`: `YANDEX_BUSINESS_FAKE=1`
- В этом режиме воркер будет использовать демо-данные вместо реальных запросов к кабинету
- Данные авторизации всё равно можно указать (они будут сохранены, но не использованы)

**Примечание:** 
- Данные авторизации (cookies) шифруются перед сохранением в БД с помощью `cryptography`
- Для продакшена обязательно установите `EXTERNAL_AUTH_SECRET_KEY` в `.env` (случайная строка 32+ символов)

### Настройка 2ГИС

Аналогично Яндекс.Бизнес:
1. Войдите в личный кабинет 2ГИС
2. Скопируйте cookies из браузера
3. Вставьте в админской панели в разделе "2ГИС"

## Последние изменения

### 2025-01-06 - Исправление ошибок после упрощения кода

**Исправленные проблемы:**
- ✅ Синтаксические ошибки в обработке результатов генерации (новости, ответы, оптимизация услуг)
- ✅ Унифицирована обработка JSON-ответов от GigaChat API
- ✅ Исправлены отступы в коде (строки 5691, 5799)
- ✅ Улучшена обработка ошибок парсинга дат и ответов организации

**Измененные файлы:**
- `src/main.py` - исправлена обработка результатов генерации новостей, ответов и оптимизации услуг
- `.cursor/docs/SIMPLIFICATION.md` - добавлена запись об исправлениях

**Статус:**
- ✅ Синтаксис Python проверен и корректен
- ✅ Код готов к тестированию

### 2026-01-09 - Архитектурный рефакторинг

**Изменения:**
- ✅ **Репозитории**: Создан `src/repositories/external_data_repository.py` для централизованной работы с БД (отзывы, статистика, посты).
- ✅ **Воркеры**: `GoogleBusinessSyncWorker` и `YandexBusinessSyncWorker` теперь наследуются от `BaseSyncWorker` и используют репозитории.
- ✅ **Декомпозиция worker.py**: Удален дублирующийся код синхронизации, логика делегирована воркерам. `process_sync_queue` удален.
- ✅ **Переименование**: `src/parser.py` -> `src/yandex_maps_scraper.py` для ясности.

## TODO
- Улучшить алгоритм анализа и рекомендации
- Добавить массовую обработку ссылок
- Реализовать сравнение с конкурентами
- Миграция на PostgreSQL для продакшена
- Реализовать реальные эндпоинты для парсинга Яндекс.Бизнес и 2ГИС 

## ❓ Troubleshooting (Решение проблем)

### Ошибка `TypeError: Failed to fetch` на фронтенде / Белый экран

**Симптомы:**
- В консоли браузера: `TypeError: Failed to fetch` при запросах к API.
- Белый экран или бесконечная загрузка дашборда.
- Backend запущен и доступен через `curl`, но фронтенд его не видит.

**Причина:**
Часто возникает на macOS, где `localhost` разрешается в IPv6 адрес `::1`, а Flask сервер слушает только IPv4 `127.0.0.1`. Vite Proxy пытается подключиться по IPv6 и получает `Connection Refused`.

**Решение:**
В файле `frontend/vite.config.ts` принудительно укажите IP `127.0.0.1` вместо `localhost`:

```typescript
// frontend/vite.config.ts
proxy: {
  '/api': {
    target: 'http://127.0.0.1:8000', // Используйте IP вместо localhost
    changeOrigin: true,
    secure: false,
  },
},
```

### Ошибка `missing_title` или зависание парсинга

**Причина:**
Яндекс часто выдает CAPTCHA, которую headless-браузер не может пройти, либо изменились селекторы на странице.

**Решение:**
1. Проверьте `worker.log`. Если видите `⚠️ Обнаружена captcha!`, откройте ссылку из лога в обычном браузере и пройдите капчу вручную.
2. Если капчи нет, но ошибка остается — возможно, Яндекс изменил верстку. Обновите селекторы в `src/yandex_maps_scraper.py`. 
