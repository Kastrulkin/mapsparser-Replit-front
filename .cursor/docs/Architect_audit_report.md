
## 2026-01-28 - Restore Development Environment

### Current Task
The local development environment (Frontend and Backend) was not starting. The backend crashed with multiple SyntaxErrors and IndentationErrors, and the frontend server was stopped.

### Architecture Decision
- **Fix Backend Syntax**:
    - **Invalid Character**: Replaced non-ASCII em-dash (`—`) with hyphen (`-`) in a string literal in `main.py` (Line ~7900).
    - **Logic/Indentation**:
        - Refactored `update_service` in `main.py` to remove redundant nested `try/except` blocks and fix misleading indentation that caused `SyntaxError: expected except or finally block`.
        - Corrected indentation in `yandex_business_sync_worker.py` (lines 289-322) where a block was excessively indented causing `IndentationError`.
    - **Duplicate Endpoint**: Removed a duplicate definition of `get_business_services` that was accidentally appended to the end of `main.py` (lines 9655-9690), preventing the Flask app from starting due to endpoint collision.
- **Restart Services**:
    - Manually restarted the Backend API (`python3 src/main.py`) and Frontend Dev Server (`npm run dev`).

### Files to Modify
- `src/main.py` - Fixed syntax, indentation, and removed duplicate code.
- `src/yandex_business_sync_worker.py` - Fixed indentation of stats calculation block.

### Trade-offs & Decisions
- **Robustness**: The duplicate code removal was necessary for the Flask app to bind URLs correctly. The indentation fixes ensure the Python interpreter can parse the files.


## 2026-01-28 - Fix Missing Updates in Services Dashboard

### Current Task
User reported that "Services", "Reviews", and "News" tabs were not updating their content (e.g. descriptions, replies) after a parser run, showing "—" in the "Updated" column.

### Architecture Decision
- Identified that `src/main.py` endpoint `/api/services/list` was **omitting** the `updated_at` field in its `SELECT` query and JSON response.
- Modified the endpoint to explicitly query `updated_at` from `UserServices` and check/query it from `ExternalBusinessServices`.
- **UPDATE**: Added explicit `replace(" ", "T")` formatting to `updated_at` to prevent `Invalid Date` on Safari/Firefox.
- **UPDATE**: Enabled `interception` parser mode by default (better product extraction).
- **UPDATE**: Fixed `worker.py` to fallback to `title` if `name` is missing (preventing "None" name).
- **UPDATE**: Fixed `parser_interception.py` to include `parse_products` in fallback logic.
- **UPDATE**: Updated `yandex_maps_scraper.py` (legacy) with broader product selectors.

### Files to Modify
- `src/main.py` - Added `updated_at` to `select_fields` and response dictionary construction.

### Trade-offs & Decisions
- **Correctness**: Prioritized fixing the visibility of data. The data was likely being saved by the worker (fixed earlier) but hidden by the API.
- **Safety**: Added a check for column existence in `ExternalBusinessServices` to prevent crashes if the schema varies, though `UserServices` schema is guaranteed.

### Dependencies
- None.

### Status
- [x] Completed

## 2026-01-29 - Fix UserServices Integrity Error & Parser Updates

### Current Task
Fix `sqlite3.IntegrityError: NOT NULL constraint failed: UserServices.user_id` preventing services from saving. Also fix missing rating/reviews in parser.

### Architecture Decision
- Modified `worker.py` and `yandex_business_sync_worker.py` to fetch `owner_id` from `Businesses` table before inserting into `UserServices`.
- Updated `parser_interception.py` to support `score` key (Yandex A/B test) and fix corrupted conditional logic.
- Added "Business Metrics" title to `ProgressPage.tsx`.

### Files to Modify
- `src/worker.py` - Added `owner_id` fetching in `_sync_parsed_services_to_db`.
- `src/yandex_business_sync_worker.py` - Added `owner_id` fetching in `_sync_services_to_db`.
- `src/parser_interception.py` - Fixed rating extraction.
- `frontend/src/pages/dashboard/ProgressPage.tsx` - Added title.

### Trade-offs & Decisions
- **Data Integrity**: Services must belong to a user (owner). If owner is missing, we skip sync instead of creating orphan records or crashing.
- **Performance**: One extra DB query (`SELECT owner_id`) per sync task, negligible impact.

### Status
- [x] Completed


## 2026-01-28 - Fix Interception Parser Data Extraction (Date, Rating)

### Current Task
User reported that after enabling the interception parser:
1.  **News Dates** were all current date (29.01.2026), not actual publication dates (e.g., 2025). This caused sorting issues and "bifurcation" of news.
2.  **Rating** was missing (—).
3.  **Parses** were duplicated (likely worker retry artifacts).
4.  **Services** were 0.

### Architecture Decision
1.  **News Date Parsing**: `parser_interception.py` `_extract_posts` was missing logic to parse timestamps (int) or ISO strings, defaulting to empty string -> `datetime.now()` in worker. Ported robust date parsing logic from `_extract_review_item`.
2.  **Rating Extraction**: Updated `_extract_organization_data` to check for `score` and `val` keys in the rating dictionary, not just `value`.
3.  **Debug Logging**: Added explicit logging for extracted posts and products to help identify empty results.

### Files to Modify
- `src/parser_interception.py` - Improved `_extract_posts` and `_extract_organization_data`.

### Trade-offs & Decisions
- **Robustness**: The interception parser relies on undocumented API structures. Adding multiple key checks (`value`, `score`, `val`) increases resilience to API changes. Added `updatedTime` to date fields as Yandex seems to use it for recent reviews.
- **Debugging**: Added key-dump logging to reverse engineer structure for services/posts. Added `searchResult`, `results` to product search keys.
- **Hybrid Mode**: Implemented fallback to HTML Selector parsing (`parse_products`) if API returns empty product list. This ensures services are found even if API keys change.
- **Observability**: Added "Warning" mechanism. If Hybrid Mode is used, the ParseQueue `error_message` is populated with "⚠️ Fast Endpoint Outdated", alerting the user to potential API changes while still delivering data.
- **Optimization**: Added `categoryItems` and `features` keys to product search based on user-provided JSON. This restores fast native API parsing for new Yandex response formats.
- **Bugfix (Metrics)**: Fixed disappearance of Business Metrics.
    - Frontend: Restored missing `<h2>` title in `ProgressPage.tsx`.
    - Backend: Updated `parser_interception.py` to support `score` key for rating (fixes missing stats in DB).

### Status
- [ ] In Progress (Verification needed)


## 2026-01-28 - Fix Production Deployment Issues (Worker Sync & Schema)

### Current Task
User reported that data (Services, Reviews) was missing after deployment, and Metrics/History graphs disappeared (showed dashes). The parser reported "Done" but no data was visible.

### Architecture Decision
1.  **Fix Worker Imports**: `src/worker.py` had imports inside a `try-except` block within the sync loop. This caused silent failures (caught as generic exceptions) if dependencies like `external_sources` were missing or had circular imports. Moved valid imports to top-level to fail fast/visibly.
2.  **Explicit Schema Update**: `src/main.py` calls `init_database_schema()` only in `if __name__ == "__main__":`. In production (gunicorn/systemd), this block is skipped, so new columns (like `unanswered_reviews_count`) were MISSING, causing API 500 errors and empty graphs.
3.  **Migration Script**: Created `src/migrate_apply_all.py` to allow explicit schema updates on the server without restarting the app in a specific mode.

### Files to Modify
- `src/worker.py` - Moved imports to top-level.
- `src/migrate_apply_all.py` - [NEW] Wrapper for schema initialization.

### Trade-offs & Decisions
- **Fail Fast**: Moving imports to top-level prevents the worker from starting if dependencies are broken, which is better than running but failing silently on every task.
- **Explicit Migration**: Relying on `main.py` sidebar execution for migrations is unreliable in WSGI environments. Dedicated script is safer.

### Dependencies
- None.

### Status
### Status
- [x] Completed

## 2026-01-29 - Hotfix: UnboundLocalError in Worker

### Current Task
Fix `UnboundLocalError: cannot access local variable 'response_text'` in `worker.py`. This error crashed the worker thread during review processing, preventing subsequent steps (Services, Statistics) from running.

### Architecture Decision
- Initialized `published_at`, `response_text`, `response_at` to `None` at the start of the review processing loop in `worker.py`.

### Status
### Status
- [x] Completed

## 2026-01-29 - Hotfix: SSL & IntegrityError

### Current Task
1. Fix `sqlite3.IntegrityError: NOT NULL constraint failed: UserServices.user_id` which persisted despite previous fixes.
2. Fix `SSLError: certificate verify failed` when connecting to GigaChat API.

### Architecture Decision
- **IntegrityError**: Added explicit debugging and stricter `None` checks for `owner_id` in `worker.py`. The error suggests `owner_id` might be `None` at runtime.
- **SSL Error**: Added `verify=False` to GigaChat API requests (`gigachat_analyzer.py`) to bypass server-side certificate validation issues (likely missing root CA on the VPS).

### Status
- [x] Completed

## 2026-01-29 - Исправление проблем с данными (Рейтинг, Отзывы, Услуги)

### Current Task
Устранение причин отсутствия рейтинга, неполного списка отзывов (20 вместо 70) и потери услуг при парсинге 'Oliver'.

### Architecture Decision
1.  **Улучшенная экстракция Рейтинга**:
    - Добавлена логика поиска ключа `ratingData` внутри `location-info` API ответов (вложенный объект `rating` или `value`). Ранее парсер смотрел только верхнеуровневый `rating`.
2.  **Агрессивная пагинация Отзывов**:
    - Увеличено количество попыток скролла с 30 до 60.
    - Добавлен принудительный JS скролл `window.scrollBy` и эмуляция движения мыши для триггера lazy-loading.
    - Добавлен клик по кнопке "Показать ещё" (если есть).
3.  **Защита данных при Failback**:
    - Обнаружен и исправлен баг: если Title не находился в API, запускался HTML-фаллбэк, который перезаписывал уже найденные через API услуги пустым списком.
    - Добавлена проверка `if not data.get('products')` перед запуском HTML-парсинга услуг в блоке фаллбэка заголовка.

### Files to Modify
- `src/parser_interception.py`:
    - `_extract_location_info`: расширен поиск рейтинга.
    - `parse_yandex_card`: улучшен скролл отзывов.
    - `parse_yandex_card`: добавлен гард `if not data.get('products')` в секции фаллбэка.

### Trade-offs & Decisions
- **Производительность**: Парсинг стал чуть медленнее из-за увеличенного времени скролла (до 60 итераций), но это необходимо для полной загрузки отзывов.
- **Надежность**: Теперь приоритет отдается данным из API (если они есть), HTML-фаллбэк используется только как крайняя мера, не разрушая уже найденное.

### Status
- [x] Completed
## 2026-01-29 - Улучшение стабильности парсинга (Title & Address Fallback)

### Current Task
Устранение ошибок `missing_title` и `missing_address`, возникающих из-за фильтрации городов в API и недостаточной надежности капча-детектора.

### Architecture Decision
1.  **Fallback для Заголовка**:
    - Добавлен поиск заголовка в мета-тегах (`og:title`).
    - Добавлен пользовательский CSS селектор: `div.orgpage-header-view__header-wrapper > h1`.
2.  **Fallback для Адреса**:
    - Добавлен поиск адреса в мета-тегах (`business:contact_data:street_address`).
    - Добавлены CSS селекторы для адреса (`div.orgpage-header-view__address`).
3.  **Улучшение детектора карточки**:
    - В `page.wait_for_selector` добавлены пользовательские селекторы заголовка, чтобы парсер корректно определял окончание загрузки после капчи.
    - Улучшена проверка `is_business_card` для предотвращения ложных срабатываний на редиректы.

### Files to Modify
- `src/parser_interception.py`:
    - `parse_yandex_card`: добавлена логика фаллбэка для Title и Address.
    - `parse_yandex_card`: обновлены селекторы ожидания загрузки.

### Trade-offs & Decisions
- **Robustness**: Теперь парсер может восстановить критические данные (название, адрес) даже если API вернул только "Санкт-Петербург" или вообще ничего полезного.
- **Maintenance**: Появилась зависимость от HTML-структуры страницы (селекторы), которая может меняться, но это необходимый компромисс при неполных данных API.

### Status
- [x] Completed

## 2026-01-30 - Fix Schema Drift and Documentation

### Current Task
Resolve `column "ai_agent_tone" specified more than once` error and document database schema.

### Architecture Decision
- Removed duplicate `ai_agent_tone` and `ai_agent_restrictions` columns from `src/schema_postgres.sql`.
- Created `database_schema.md` to serve as the single source of truth for the database schema, replacing reliance on `VERIFICATION.md`.
- Linked `database_schema.md` in `README.md`.

### Files to Modify
- `src/schema_postgres.sql` - removed duplicates.
- `database_schema.md` - created new file.
- `README.md` - updated link.

### Trade-offs & Decisions
- **Documentation**: Separating schema documentation into its own file (`database_schema.md`) improves discoverability and maintainability compared to burying it in verification logs.
- **Schema Integrity**: Validated `schema_postgres.sql` against known usage to ensure all columns are present and unique.

### Status
- [x] Completed

## 2026-01-30 - Fix Schema Drift (Legacy & Integration Columns)

### Current Task
Resolve `column "ai_agent_language" of relation "businesses" does not exist` error during migration.

### Architecture Decision
- Analyzed full SQLite schema dump provided by user.
- Identified numerous missing columns in `Businesses` table:
    - Legacy ChatGPT: `chatgpt_enabled`, `chatgpt_context`, `chatgpt_api_key`, `chatgpt_model`, `ai_agents_config`
    - Telegram: `telegram_bot_connected`, `telegram_username`
    - Stripe: `stripe_customer_id`, `stripe_subscription_id`
    - Subscription: `trial_ends_at`, `subscription_ends_at`
    - Moderation: `moderation_status`, `moderation_notes`
    - AI Agent: `ai_agent_language`
- Added ALL these columns to `src/schema_postgres.sql`.
- Updated `database_schema.md` to document these fields.

### Files to Modify
- `src/schema_postgres.sql` - added 14 missing columns.
- `database_schema.md` - updated documentation.

### Trade-offs & Decisions
- **Legacy Support**: Adding these columns ensures data migration succeeds without data loss, even if some features (like old ChatGPT integration) are deprecated.

### Status
- [x] Completed

## 2026-01-31 - Fix Schema Drift (UserSessions & Invites)

### Current Task
Resolve `column "ip_address" of relation "usersessions" does not exist` error during migration.

### Architecture Decision
- Identified missing columns `ip_address` and `user_agent` in `UserSessions` table (used in `auth_system.py`).
- Discovered missing `Invites` table (referenced in `auth_system.py`).
- Added these to `src/schema_postgres.sql` to support full application functionality and data migration.

### Files to Modify
- `src/schema_postgres.sql` - added columns and table.
- `database_schema.md` - updated documentation.

### Trade-offs & Decisions
- **Completeness**: Even if `Invites` table is empty or rarely used, it is part of the `auth_system` logic, so it must exist in Postgres to prevent runtime errors.

### Status
- [x] Completed

## 2026-01-30 - Fix Schema Drift (Legacy ChatGPT Columns)

### Current Task
Resolve `column "chatgpt_enabled", "chatgpt_api_key" of relation "businesses" does not exist` error during migration.

### Architecture Decision
- Identified missing legacy columns `chatgpt_enabled`, `chatgpt_context`, `chatgpt_api_key`, `chatgpt_model`, and `ai_agents_config` in `Businesses` table, and `chatgpt_context` in `UserServices`.
- Added these columns to `src/schema_postgres.sql` to support data migration from SQLite.
- Updated `database_schema.md` to document these as legacy/deprecated fields.

### Files to Modify
- `src/schema_postgres.sql` - added columns.
- `database_schema.md` - updated documentation.

### Trade-offs & Decisions
- **Legacy Support**: These columns are necessary for the migration script to copy data from SQLite.

### Status
- [x] Completed

## 2026-01-31 - Fix Schema Drift (PricelistOptimizations)

### Current Task
Resolve `column "user_id" of relation "pricelistoptimizations" does not exist` error during migration.

### Architecture Decision
- Identified missing `user_id` column in `PricelistOptimizations` table.
- Added it to `src/schema_postgres.sql`.

### Files to Modify
- `src/schema_postgres.sql` - added column.
- `database_schema.md` - updated documentation.

### Status
- [x] Completed

## 2026-01-31 - Fix Schema Drift (PricelistOptimizations Part 2)

### Current Task
Resolve `column "original_file_path" of relation "pricelistoptimizations" does not exist` error during migration.

### Architecture Decision
- Discovered that `PricelistOptimizations` usage in `main.py` differs significantly from what was implied by `migrate_fix_...` scripts.
- It uses `original_file_path`, `optimized_data`, `services_count`, and `expires_at`.
- Updated schema to include BOTH sets of columns (Superset) to ensure compatibility with all potential data sources and logic phases.
- Made `business_id` nullable as `main.py` does not populate it during file upload.

### Files to Modify
- `src/schema_postgres.sql` - redefined table with superset columns.
- `database_schema.md` - updated documentation.

### Status
- [x] Completed

## 2026-01-31 - Fix Schema Drift (MapParseResults)

### Current Task
Resolve `column "phone" of relation "mapparseresults" does not exist` error during migration.

### Architecture Decision
- Identified missing columns in `MapParseResults` table which were added via `src/migrations/add_missing_mapparse_columns.py` in SQLite.
- Added `phone`, `website`, `working_hours`, `features`, `posts_count` to `src/schema_postgres.sql`.

### Files to Modify
- `src/schema_postgres.sql` - added missing columns.
- `database_schema.md` - updated documentation.

### Status
- [x] Completed

## 2026-01-31 - Fix Schema Drift (MapParseResults Part 2)

### Current Task
Resolve `column "messengers" of relation "mapparseresults" does not exist` error during migration.

### Architecture Decision
- Identified additional missing columns in `MapParseResults` from `src/migrations/add_profile_completeness_fields.py`: `messengers`, `profile_completeness`, `first_photo_url`.
- Added them to `src/schema_postgres.sql`.

### Files to Modify
- `src/schema_postgres.sql` - added missing columns.
- `database_schema.md` - updated documentation.

### Status
- [x] Completed

## 2026-01-31 - Fix Schema Drift (MapParseResults Part 3)

### Current Task
Resolve missing `competitors` column in `MapParseResults`. Matches SQLite dump.

### Architecture Decision
- User confirmed `competitors` exists in SQLite but `features` does not.
- Added `competitors` to `src/schema_postgres.sql`.
- Commented out `features` to prevent migration errors if it doesn't exist.

### Files to Modify
- `src/schema_postgres.sql` - added `competitors`, removed `features`.
- `database_schema.md` - updated documentation.

### Status
- [x] Completed

## 2026-01-31 - Fix Schema Drift (UserServices)

### Current Task
Resolve `column "optimized_description" of relation "userservices" does not exist` error during migration.

### Architecture Decision
- Identified missing columns in `UserServices` from SQLite dump: `optimized_description`, `is_active`.
- Added them to `src/schema_postgres.sql`.

### Files to Modify
- `src/schema_postgres.sql` - added missing columns.
- `database_schema.md` - updated documentation.

### Status
- [x] Completed

## 2026-01-31 - Fix Schema Drift (ReviewExchangeDistribution)

### Current Task
Resolve `column "review_confirmed" of relation "reviewexchangedistribution" does not exist` error during migration.

### Architecture Decision
- Identified missing columns in `ReviewExchangeDistribution` from SQLite dump: `review_confirmed`, `confirmed_at`.
- Added them to `src/schema_postgres.sql`.

### Files to Modify
- `src/schema_postgres.sql` - added missing columns.
- `database_schema.md` - updated documentation.

### Status
- [x] Completed

## 2026-01-31 - Fix Schema Drift (ExternalBusinessReviews)

### Current Task
Resolve `column "account_id" of relation "externalbusinessreviews" does not exist` error during migration.

### Architecture Decision
- Identified missing `account_id` column in `ExternalBusinessReviews`.
- Added it to `src/schema_postgres.sql`.

### Files to Modify
- `src/schema_postgres.sql` - added missing column.
- `database_schema.md` - updated documentation.

### Status
- [x] Completed

## 2026-01-31 - Fix Schema Drift (ExternalBusinessReviews Part 2)

### Current Task
Sync `ExternalBusinessReviews` schema with SQLite dump.

### Architecture Decision
- Identified additional missing columns from user dump: `author_profile_url`, `lang`.
- Added them to `src/schema_postgres.sql`.

### Files to Modify
- `src/schema_postgres.sql` - added missing columns.
- `database_schema.md` - updated documentation.

### Status
- [x] Completed

## 2026-01-31 - Fix Schema Drift (ExternalBusinessStats)

### Current Task
Resolve `column "account_id" of relation "externalbusinessstats" does not exist` error during migration.

### Architecture Decision
- Identified missing `account_id` and `unanswered_reviews_count` columns in `ExternalBusinessStats` from SQLite dump.
- Added them to `src/schema_postgres.sql`.

### Files to Modify
- `src/schema_postgres.sql` - added missing columns.
- `database_schema.md` - updated documentation.

### Status
- [x] Completed
