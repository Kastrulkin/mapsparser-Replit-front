# Database Schema

This document serves as the source of truth for the BeautyBot database schema. It is based on the PostgreSQL migration schema definitions (`src/schema_postgres.sql`) and Alembic migrations in `alembic_migrations/versions/`.

## PostgreSQL runtime: имена таблиц и source of truth

В коде (main.py, worker.py, database_manager) при работе с **PostgreSQL** используются только **имена таблиц в нижнем регистре** и плейсхолдеры **`%s`**:

- **parsequeue** — очередь задач парсинга и синхронизации (статусы: pending, processing, completed, error, captcha).
- **cards** — **источник правды по результатам парсинга карт**: рейтинг, отзывы, отчёт, версионирование. Все новые результаты (парсинг карты, синхронизация Яндекс.Бизнес, 2ГИС) пишутся в **cards**, а не в MapParseResults.
- **externalbusinessaccounts** — внешние аккаунты (Яндекс.Бизнес, Google Business, 2ГИС); поле `auth_data_encrypted` не отдаётся в API.
- **businessmaplinks** — ссылки бизнеса на карты (Яндекс, Google и т.д.).
- **businesses**, **users**, **userservices** — бизнесы, пользователи, услуги.
- **businessmetricshistory** — история метрик (рейтинг, отзывы по датам); **externalbusinessstats**, **externalbusinessreviews** — агрегаты и отзывы из внешних источников.

Таблицы **MapParseResults** и **ParseQueue** в CamelCase — legacy для SQLite; в PG не используются.

## Tables

### Users
Stores user authentication and profile information.
- `id` (TEXT, PK): Unique user identifier.
- `email` (TEXT, UNIQUE): User email address.
- `password_hash` (TEXT): Hashed password.
- `name` (TEXT): User's full name.
- `phone` (TEXT): Contact phone number.
- `telegram_id` (TEXT): Telegram user ID.
- `is_active` (BOOLEAN): Whether the account is active.
- `is_verified` (BOOLEAN): Email verification status.
- `is_superadmin` (BOOLEAN): Administrative privileges.
- `verification_token` (TEXT): Token for email verification.
- `reset_token` (TEXT): Token for password reset.
- `reset_token_expires` (TIMESTAMP): Expiry for reset token.
- `created_at`, `updated_at`: Timestamps.

### Networks
Groups multiple businesses under a single owner.
- `id` (TEXT, PK)
- `name` (TEXT)
- `owner_id` (TEXT, FK -> Users.id)
- `description` (TEXT)
- `created_at`, `updated_at`

### Businesses
Represents individual beauty salons or service providers.
*Primary entity for most operations.*
- `id` (TEXT, PK)
- `name` (TEXT)
- `owner_id` (TEXT, FK -> Users.id)
- `network_id` (TEXT, FK -> Networks.id, NULLABLE)
- `description`, `industry`, `business_type`, `address`, `working_hours`, `phone`, `email`, `website`
- `is_active` (BOOLEAN)
- `subscription_tier` (TEXT): 'trial', 'basic', 'pro', etc.
- `subscription_status` (TEXT): 'active', 'expired', etc.
- **Location**: `city`, `country`, `timezone`, `latitude`, `longitude`
- **Integrations**:
    - WhatsApp: `waba_phone_id`, `waba_access_token`, `whatsapp_phone`, `whatsapp_verified`
    - Telegram: `telegram_bot_token`
    - AI Agent: `ai_agent_enabled`, `ai_agent_type`, `ai_agent_id`, `ai_agent_tone`, `ai_agent_restrictions`, `ai_agent_language`
    - Yandex: `yandex_org_id`, `yandex_url`, `yandex_rating`, `yandex_reviews_total`, `yandex_reviews_30d`, `yandex_last_sync`
    - **Legacy/Deprecated**: `chatgpt_enabled`, `chatgpt_context`, `chatgpt_api_key`, `chatgpt_model`, `ai_agents_config`
    - **Integrations**: `telegram_bot_connected`, `telegram_username`, `stripe_customer_id`, `stripe_subscription_id`
    - **Subscription**: `trial_ends_at`, `subscription_ends_at`
    - **Moderation**: `moderation_status`, `moderation_notes`

### UserSessions
Active user sessions / JWT tokens.
- `id` (TEXT, PK)
- `user_id` (TEXT, FK -> Users.id)
- `token` (TEXT, UNIQUE)
- `token` (TEXT, UNIQUE)
- `expires_at` (TIMESTAMP)
- `ip_address` (TEXT)
- `user_agent` (TEXT)

### UserServices
Services offered by a business.
- `id` (TEXT, PK)
- `business_id` (TEXT, FK -> Businesses.id)
- `name` (TEXT)
- `category` (TEXT)
- `price` (TEXT)
- `description`, `keywords`
- `optimized_name` (TEXT): AI-optimized name for SEO.
- `optimized_description` (TEXT)
- `chatgpt_context` (TEXT): Context for AI generation.
- `is_active` (BOOLEAN)

### Masters
Employees or specialists working at a business.
- `id` (TEXT, PK)
- `business_id` (TEXT, FK -> Businesses.id)
- `name` (TEXT)
- `specialization` (TEXT)

### parsequeue (PostgreSQL)
Очередь задач парсинга и синхронизации. В коде — только имя в нижнем регистре.
- **Статусы (канонические)**: `pending`, `processing`, `completed`, `error`, `captcha`. Запись/обновление всегда использует `completed`; при чтении и фильтрации учитывается и старый `done` (константы и нормализация в `src/parsequeue_status.py`).
- `id` (TEXT, PK)
- `user_id` (TEXT), `business_id` (TEXT), `account_id` (TEXT)
- `url` (TEXT), `status` (TEXT)
- `task_type` (TEXT): 'parse_card', 'sync_yandex_business' и др.
- `source` (TEXT), `error_message` (TEXT), `retry_after` (TIMESTAMP)
- `created_at`, `updated_at`

### cards (PostgreSQL) — source of truth для результатов парсинга
Все результаты парсинга карт и синхронизаций (Яндекс.Карты, Яндекс.Бизнес, 2ГИС) сохраняются здесь. Версионирование: `version`, `is_latest`.
- `id` (TEXT, PK), `business_id` (TEXT), `user_id` (TEXT)
- `url`, `title`, `address`, `phone`, `site`
- `rating` (REAL), `reviews_count` (INTEGER)
- `categories`, `overview`, `products`, `news`, `photos`, `features_full`, `competitors`, `hours`, `hours_full`
- `report_path`, `seo_score`, `ai_analysis` (JSONB), `recommendations` (JSONB)
- `version`, `is_latest`, `created_at`, `updated_at`

### MapParseResults (legacy / SQLite)
В PostgreSQL не используется; эквивалент — таблица **cards**.

### PricelistOptimizations
- `id` (TEXT, PK)
- `user_id` (TEXT, FK -> Users.id)
- `original_file_path` (TEXT)
- `optimized_data` (TEXT, JSON)
- `receiver_participant_id` (TEXT)
- `sent_at` (TIMESTAMP)
- `review_confirmed` (BOOLEAN)
- `confirmed_at` (TIMESTAMP)
- `business_id` (TEXT, FK -> Businesses.id)
- `original_text`, `optimized_text`

### External Data Tables (PostgreSQL: имена в нижнем регистре)
- **externalbusinessaccounts**: Внешние аккаунты (Яндекс.Бизнес, Google, 2ГИС); `auth_data_encrypted` не отдаётся в API. Уникальность по паре (business_id, source) в runtime (без жёсткого UNIQUE в миграции).
- **externalbusinessreviews**: Отзывы из внешних источников; `account_id`, `response_text`, `published_at`.
- **externalbusinessstats**: Агрегированная статистика по дням (`rating`, `reviews_total`, `photos_count`, `news_count`, `unanswered_reviews_count`, `date`, `source`).
- **externalbusinessposts**, **externalbusinessphotos**: Публикации и фото из кабинетов.

### Financial Tables
- **FinancialTransactions**: Records of sales/services rendered.
- **FinancialMetrics**: Aggregated financial metrics.
- **ROIData**: Return on Investment calculations.

### Other Tables
- **ProxyServers**: Rotation pool for parsers.
- **BusinessMapLinks**: Links to business on different maps.
- **WordstatKeywords**: cached SEO keywords.
- **businessmetricshistory**: Снимки метрик по датам (`rating`, `reviews_count`, `photos_count`, `news_count`, `source` = 'parsing' и др.). В коде — имя в нижнем регистре.
- **TelegramBindTokens**: Tokens for linking Telegram accounts.
- **ReviewExchange* **: Tables for cross-promotion review system.
- **AIPrompts**: System prompts for AI generation features.
- **AIAgents**: Configuration for AI agents.
- **Invites**: User invitation system.

## Relationships
- **Users** 1:N **Businesses** (via `owner_id`)
- **Networks** 1:N **Businesses** (via `network_id`)
- **Businesses** 1:N **UserServices**
- **Businesses** 1:N **Masters**
- **Businesses** 1:N **ExternalBusinessReviews**

## Проверка полной схемы (PostgreSQL)

Актуальная схема в БД задаётся миграциями Alembic (`alembic_migrations/versions/`). Чтобы вывести **текущее состояние** схемы (все таблицы и колонки в `public`):

**Из контейнера app (рекомендуется):**
```bash
docker compose exec app python scripts/check_postgres_schema.py
```

**Локально** (если задан `DATABASE_URL` и установлены зависимости):
```bash
cd "/path/to/project"
export DATABASE_URL="postgresql://user:pass@localhost:5432/dbname"
python scripts/check_postgres_schema.py
```

Скрипт выводит список таблиц и для каждой — колонки, типы, NULL/NOT NULL, default. По нему можно сверить, что все нужные таблицы (в т.ч. `businessprofiles`, `businessmaplinks`, `externalbusinessaccounts`) есть в БД.
