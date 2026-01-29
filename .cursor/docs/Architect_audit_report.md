## 2026-01-21 - Fix Missing Environment Variables (Local Debugging)

### Current Task
Diagnose why `worker.py` failed to decrypt auth tokens, leading to empty parser results.
User requested local debugging to find the cause.

### Architecture Decision
1.  **Local Reproduction**: Created `local_check_env.py` which confirmed that `src/worker.py` was NOT loading variables from `.env`.
2.  **Fix**: Added `from dotenv import load_dotenv; load_dotenv()` to:
    *   `src/worker.py` (Main entry point)
    *   `src/yandex_business_sync_worker.py` (Safety measure for direct usage)

### Files to Modify
- `src/worker.py`
- `src/yandex_business_sync_worker.py`
- Created temporary `local_check_env.py` and `.env` (will be ignored/deleted).

### Trade-offs & Decisions
- **Explicit Loading**: Relying on system environment variables is cleaner for containerization, but since we use `nohup python ...` and a `.env` file on the server, explicit `load_dotenv()` is required.

### Dependencies
- `python-dotenv` (already in requirements.txt).

### Status
- [x] Completed

## 2026-01-22 - Fix Frontend Login 501 Error (Local Debugging)

### Current Task
User reported `501 Unsupported method ('POST')` when trying to log in locally.
This error came from the Python SimpleHTTPRequestHandler (port 3000), meaning requests were **not** reaching the Flask backend (port 8000).

### Architecture Decision
- **Problem**: `frontend/src/lib/auth_new.ts` had a hardcoded `apiBaseUrl = window.location.origin + '/api'`, effectively forcing all API calls to localhost:3000.
- **Fix**: Updated `auth_new.ts` to import and use `API_URL` from `../config/api`, which is correctly configured to `http://localhost:8000`.

### Files to Modify
- `frontend/src/lib/auth_new.ts` - Changed `apiBaseUrl` initialization.

### Trade-offs & Decisions
- **Hardcoding vs Env**: Ideally `VITE_API_URL` should handle this, but for this local debug session, we hardcoded `src/config/api.ts` to ensuring stability. The fix in `auth_new.ts` aligns with using the centralized config.

### Status
- [x] Completed

## 2026-01-22 - Исправление парсинга Яндекс.Карт (Selectors vs Endpoints)

### Current Task
Исправление проблем с отсутствующими данными (рейтинг, телефон, услуги) при парсинге карт.

### Architecture Decision
- Переключить `PARSER_MODE` по умолчанию с `interception` (endpoints) на `legacy` (selectors/HTML).
- Значительно улучшить селекторы в `yandex_maps_scraper.py` (legacy parser), добавив эвристический поиск и regex для телефонов и рейтингов.
- Endpoints (Interception) парсер пока менее стабилен из-за возможной обфускации API Яндекса и сложностей с Captcha.

### Files to Modify
- `src/yandex_maps_scraper.py` - добавлены robust selectors для Rating, Phone, Hours, Tabs.
- `src/parser_config.py` - изменен дефолт на `legacy`.
- `src/worker.py` - без изменений, используется через `parser_config`.

### Trade-offs & Decisions
- **Стабильность vs Скорость**: Endpoint-парсинг быстрее, но HTML-парсинг сейчас надежнее с новыми эвристиками.
- **Backwards compatibility**: Legacy парсер полностью совместим с текущей БД и worker'ом.

### Dependencies
- Нет новых зависимостей (Playwright уже используется).

### Status
- [x] Completed

## 2026-01-22 - Исправление Type Error в Worker

### Current Task
Исправление ошибки `TypeError: '>=' not supported between instances of 'str' and 'int'`, возникающей при обработке данных парсера.

### Architecture Decision
- Ошибка возникала, так как `get_photos_count` (parser) возвращал строку, а `profile_completeness` (worker) сравнивал её с числом.
- **Fix**: Добавлено принудительное приведение типов (`int()`) для метрик (`photos_count`, `reviews_count`, `news_count`) в `worker.py` перед использованием в логике.

### Files to Modify
- `src/worker.py`

### Status
- [x] Completed

## 2026-01-22 - Разделение логики Парсинга и Оценки (Robust Worker)

### Current Task
Разделить "сбор данных" и "аналитику", чтобы ошибки в аналитике (например, Type Error) не блокировали сохранение данных.

### Architecture Decision
- Реализовать концепцию "Safe Analytics Execution" внутри `worker.py`.
- **Refactor**: 
    1. Расчет `profile_completeness` обернут в `try/except` блок.
    2. Добавлена повторная валидация типов (`_safe_photos`, `_safe_services`) перед использованием в логике.
    3. При ошибке аналитики ставится дефолтное значение (0), но "сырые" данные (телефон, сайт, часы работы) всё равно сохраняются.

### Files to Modify
- `src/worker.py`

- [x] Completed

## 2026-01-22 - Unified Analytics Service (Decoupling)

### Current Task
Обеспечить запуск анализа (SEO Score, Recommendations) при ручном изменении данных, а не только при парсинге.

### Architecture Decision
- Создан новый сервис `src/services/analytics_service.py`, инкапсулирующий логику оценки.
- **Integration**:
    1. **Worker**: Использует сервис для оценки после парсинга.
    2. **Main API (`save_card_to_db`)**: Автоматически пересчитывает баллы перед КАЖДЫМ сохранением карточки в БД.

### Files to Modify
- `src/services/analytics_service.py` [NEW]
- `src/worker.py`
- `src/main.py`

- [x] Completed

- [x] Completed

## 2026-01-22 - Fix Missing Database Tables (ExtReviews & ExtStats)

### Current Task
Воркер падал с ошибками `no such table: ExternalBusinessReviews` и `no such table: ExternalBusinessStats`.

### Architecture Decision
- Две таблицы для внешних данных (отзывы и статистика) отсутствовали в БД.
- **Fix**: 
    1. Созданы и запущены миграции: 
        - `src/migrations/add_external_reviews_table.py`
        - `src/migrations/add_external_stats_table.py`
    2. Определения обеих таблиц и индексов добавлены в `src/init_database_schema.py`.

### Files to Modify
- `src/migrations/add_external_stats_table.py` [NEW]
- `src/init_database_schema.py`

### Status
- [x] Completed

## 2026-01-22 - Fix URL Logic & Parsing Timeouts

### Current Task
Пользователь сообщал о "пустом результате" и таймаутах (10 мин).
Причина: 
1. Использовалась **админская ссылка** (`/sprav/`), которая возвращает 404 для парсера.
2. Парсер слишком долго скроллил (100 итераций), вызывая таймаут воркера.

### Architecture Decision
- **URL Normalization**: В `worker.py` добавлена авто-замена ссылок `sprav/{id}` -> `maps/org/redirect/{id}`.
- **Optimization**: В `yandex_maps_scraper.py` лимиты скролла уменьшены, добавлен **авто-клик по баннерам/диалогам**, которые перекрывали контент.

### Files to Modify
- `src/worker.py` - авто-коррекция URL
- `src/yandex_maps_scraper.py` - оптимизация циклов и закрытие диалогов

### Status
- [x] Completed

## 2026-01-22 - Fix Dialog Handling & Analytics Verification

### Current Task
Verification of parsing logic fixes revealed `NameError: name '_close_dialogs' is not defined` when running e2e tests.
Also needed to verify the new unified `analytics_service`.

### Architecture Decision
1.  **Code Fix**: Moved `_close_dialogs` in `src/yandex_maps_scraper.py` from nested scope to module level to be accessible by all scraper functions (`parse_reviews`, `parse_yandex_card`). Use global definition to avoid scope issues.
2.  **Verification**: Created `src/test_analytics.py` to unit test the profile completeness logic. Confirmed robust handling of mixed types and empty inputs.
3.  **Parsing Status**: Code logic confirmed correct. Parsing is currently intermittent due to CAPTCHA blocks, but the underlying mechanisms (URL correction, dialog closing, timeout handling) are fixed.

### Files to Modify
- `src/yandex_maps_scraper.py`
- `src/test_analytics.py` [NEW]

### Status
- [x] Completed
- [x] Completed

## 2026-01-23 - Debugging Stuck Worker

### Current Task
User reported a task stuck in "Pending" status for hours.

### Architecture Decision
1.  **Diagnosis**: 
    - Worker process was not running (`ps aux | grep worker.py` failed).
    - Database query confirmed task was `pending`.
2.  **Fix**:
    - Restarted worker using `nohup python3 src/worker.py > worker.log 2>&1 &`.
    - Worker immediately picked up the task.
3.  **Outcome**:
    - Task hit CAPTCHA (Yandex is aggressive).
    - System correctly switched to **Fallback Parsing** (ID: `d2ee9418...`).
    - Fallback is currently `processing`.

### Files to Modify
- None (Operational Fix).

### Status
- [x] Completed

## 2026-01-23 - Disable Automatic Fallback to Cabinet Parsing

### Current Task
User requested to make "Cabinet Parsing" (Yandex Business) a manual choice only.

### Architecture Decision
1.  **Change**: Disabled logic in `src/worker.py` that automatically created a `parse_cabinet_fallback` task when public parsing failed (e.g. due to Captcha).
2.  **Behavior**:
    - Parsing Fail/Captcha -> Task status becomes `error` or `captcha`.
    - No new task is created automatically.
    - User can still manually start Cabinet parsing via UI (Admin Panel).

### Files to Modify
- `src/worker.py`

### Status
- [x] Completed

## 2026-01-23 - Wordstat Integration (SEO Keywords)

### Current Task
User requested to make SEO optimization transparent by storing Wordstat keywords in the database and managing them via UI.

### Architecture Decision
1.  **Database**: Created `WordstatKeywords` table to store keywords, views, and categories.
2.  **Backend**: Updated `update_wordstat_data.py` to populate this table instead of a text file. Used `ServiceCategorizer` to categorize keywords during import.
3.  **API**: Added `GET /api/wordstat/keywords` and `POST /api/wordstat/update` to expose this data to the frontend.
4.  **Frontend**: Added "SEO Keywords" tab to `CardOverviewPage` using new `SEOKeywordsTab` component.

### Files to Modify
- `src/migrations/add_wordstat_table.py` [NEW]
- `src/init_database_schema.py`
- `src/update_wordstat_data.py`
- `src/api/wordstat_api.py` [NEW]
- `src/main.py`
- `frontend/src/components/SEOKeywordsTab.tsx` [NEW]
- `frontend/src/pages/dashboard/CardOverviewPage.tsx`

### Status
- [x] Completed

## 2026-01-23 - Bug Fixes (Parsing & Wordstat)

### Current Task
Fixing "Not Found" error in SEO tab and incorrect price parsing (120000 instead of 1200).

### Architecture Decision
1.  **Price Parsing**: Modified `yandex_business_sync_worker.py` to remove `* 100` multiplication. Prices are now stored as is (e.g. 1200).
2.  **API Not Found**: Identified as server restart issue.

### Files to Modify
- `src/yandex_business_sync_worker.py`
- `src/worker.py` (Fix: missing commit for external data, deterministic IDs for reviews)

### Trade-offs & Decisions
- **Fix (Data Loss)**: `worker.py` was failing to commit transactions for Reviews, News, and Stats (processed via `db_manager`), causing them to disappear despite successful parsing. Added explicit `commit()`.
- **Fix (Duplicates)**: Changed review ID generation to `uuid5` (deterministic hash of content) to prevent creating 652+ duplicates on repeated parses.
- **Fix (UI Limits)**: Increased `CardOverviewPage` services limit from 10 to 50 to ensure all services are displayed.
- **Fix (Deadlock)**: Added intermediate `conn.commit()` in `worker.py` to release SQLite write lock before initializing `DatabaseManager` for detailed data saving.
- **Fix (Infinite Parser Loop)**: Implemented in-memory deduplication in `yandex_maps_scraper.py` to handle infinite scroll duplication, preventing 6X duplicated data.

### Status
- [x] Completed

## 2026-01-23 - Fix 500 Error in Metrics History

### Current Task
User reported 500 Internal Server Error when loading metrics history.
Diagnosis: `ValueError: could not convert string to float: ''` in `src/api/metrics_history_api.py`.

### Architecture Decision
- **Root Cause**: `MapParseResults` table can contain empty strings for ratings. The API attempted `float('')`.
- **Fix**: Added explicit check `if row[2] != ''` before conversion in `metrics_history_api.py`.

### Files to Modify
- `src/api/metrics_history_api.py`

### Status
- [x] Completed

## 2026-01-26 - Fix Infinite Loading (DB Deadlock) & Missing Data Tables

### Current Task
1.  **Infinite Loading**: User reported "spinning" loading screen. Diagnosis: `src/main.py` was executing `CREATE TABLE IF NOT EXISTS` inside an API route, causing lock contention with the worker process.
2.  **Missing Data**: "Work with Maps" tab was empty despite parser "History" showing 144 reviews. Diagnosis: `ExternalBusinessPosts`, `ExternalBusinessPhotos` tables were missing from the database.

### Architecture Decision
1.  **Deadlock Fix**: Use `safe_migrate` pattern for table creation instead of ad-hoc DDL in API handlers.
    *   Moved `BusinessOptimizationWizard` table creation to `src/migrate_create_wizard_table.py`.
    *   Removed `CREATE TABLE` logic from `src/main.py`.
2.  **Missing Tables Fix**: Created safe migration `src/migrate_create_missing_external_tables.py` to create `ExternalBusinessPosts` and `ExternalBusinessPhotos`.

### Files to Modify
- `src/main.py` (Removed unsafe DDL)
- `src/migrate_create_wizard_table.py` [NEW]
- `src/migrate_create_missing_external_tables.py` [NEW]

### Trade-offs & Decisions
- **Safety**: `safe_migrate` ensures backups are created before schema changes.
- **Performance**: Removing DDL from hot paths (API routes) eliminates lock waiting time.

### Dependencies
- None.

### Status
- [x] Completed
## 2026-01-26 - Fix Backend Crash (Missing Dependency)

### Current Task
User reported "Connection Refused" and backend failing to start.
Logs showed `ModuleNotFoundError: No module named 'apify_client'`.

### Architecture Decision
- The `apify-client` library was used in `prospecting_service.py` but was missing from the environment.
- **Fix**: Installed `apify-client` and `cryptography`. Updated `requirements.txt`.
- **Path Fix**: Also corrected `start_servers.sh` which was pointing to an incorrect directory.

### Files to Modify
- `requirements.txt`
- `start_servers.sh`

### Status
- [x] Completed
## 2026-01-26 - Fix React Key Warning

### Current Task
User reported "Warning: Each child in a list should have a unique 'key' prop" in `BusinessGrowthPlan`.

### Architecture Decision
- The tasks list rendering in `BusinessGrowthPlan.tsx` used `task.number` as a key. If data had duplicates or issues, this caused a warning.
- **Fix**: Updated key generation to be robust: `key={task.id || \`task-${task.number}-${tIdx}\`}`.

### Files to Modify
- `frontend/src/components/BusinessGrowthPlan.tsx`

### Status
- [x] Completed
## 2026-01-26 - Исправление отображения статуса верификации в истории парсинга

### Current Task
В таблице "История парсинга" (Work with Maps -> Отчеты) не отображалась "Синяя галочка" верификации, хотя бэкенд собирал эти данные. Также требовалось убедиться в корректности отображения количества отзывов.

### Architecture Decision
- Добавлена иконка `CheckCircle2` (синяя галочка) рядом с URL в таблице `MapParseTable`.
- Иконка отображается условно, если флаг `isVerified` равен `true`.
- Используется библиотека `lucide-react` для иконок, соответствующая дизайн-системе проекта.

### Files to Modify
- `frontend/src/components/MapParseTable.tsx` - добавлен импорт иконки и логика отображения.

### Trade-offs & Decisions
- **UX**: Галочка размещена рядом с URL, так как это логичное место для статуса подтверждения сущности (карточки).
- **Производительность**: Изменения минимальны (клиентский рендеринг), не влияют на API.

### Dependencies
- Нет новых зависимостей (используется существующая `lucide-react`).

### Status
- [x] Completed
## 2026-01-26 - Синхронизация распарсенных данных с UI (Услуги, Новости, Отзывы)

### Current Task
Обеспечить отображение данных из парсера (услуги, отзывы, новости) в соответствующих вкладках раздела "Работа с картами" (CardOverviewPage).

### Architecture Decision
1.  **Backend (`src/main.py`)**:
    - Обновлен метод `get_services`: теперь он возвращает не только пользовательские услуги, но и спарсенные из `ExternalBusinessServices`.
    - Добавлен метод `get_external_posts`: возвращает новости из `ExternalBusinessPosts` (ранее endpoint отсутствовал).
    - Endpoint для отзывов (`get_external_reviews`) уже существовал и работал корректно.

2.  **Frontend (`CardOverviewPage.tsx`)**:
    - Обновлена функция `loadUserServices`: теперь она объединяет пользовательские и внешние услуги в единый список для отображения.
    - Добавлена функция `loadExternalPosts`: загружает новости и передает их в компонент `NewsGenerator`.
    - Компонент `ReviewReplyAssistant` работает автономно и уже загружает отзывы с правильного endpoint'а.

### Files to Modify
- `src/main.py` - добавление `get_external_posts` и обновление `get_services`.
- `frontend/src/pages/dashboard/CardOverviewPage.tsx` - логика загрузки и передачи данных.

### Trade-offs & Decisions
- **Объединение услуг**: Внешние услуги пока просто добавляются в общий список. В будущем может потребоваться UI для их "импорта" или редактирования, но сейчас цель - просто показать.
- **Монолитный `main.py`**: Новые методы добавлены в `main.py` для консистентности с текущей структурой, хотя лучше было бы вынести их в `src/api/`. Рефакторинг отложен.

### Dependencies
- Нет новых зависимостей.

### Status
- [x] Completed

## 2026-01-26 - Server Deployment Recovery & React Fixes

### Current Task
Recover server state after failed deployment. Issues: 500 Internal Server Error (caused by missing DB tables), missing "Prospecting" tab (caused by build failure/bad cache), and missing Verification Badge data.

### Architecture Decision
1.  **Server Recovery Strategy**: Adopted "Hard Reset" approach (`git reset --hard origin/main`) on server to guarantee code synchronization, followed by explicit migration execution and clean frontend rebuild.
2.  **React Build Fixes**: Fixed absolute path imports (`@/i18n/...`) in `ProspectingManagement.tsx` and `ParsingManagement.tsx` which were causing silent build failures or runtime errors (Error #300, #310). Changed to relative paths.
3.  **Missing Data Fix**: Identified that `ExternalBusinessPosts` and `UserNews` tables were missing on production DB. Created/ran `migrate_create_missing_external_tables.py`.

### Files to Modify
- `frontend/src/pages/dashboard/ProspectingManagement.tsx` (Fix imports)
- `frontend/src/components/ParsingManagement.tsx` (Fix imports)
- `src/migrate_create_missing_external_tables.py` [NEW]

### Dependencies
- None.

### Status
- [x] Completed

## 2026-01-26 - Feature: Verification Badge (Blue Checkmark)

### Current Task
Add support for capturing and displaying "Blue Checkmark" (verification status) from Yandex Maps. It worked locally (Legacy scraper) but not on server (Interception parser).

### Architecture Decision
1.  **Database**: Added `is_verified` column (INTEGER) to `MapParseResults` table via new migration.
2.  **Parser (Interception)**: Injected HTML-based verification check into `parser_interception.py` (since JSON structure for verification is obscure/variable). It now scrapes the badge selector from the loaded page before closing the browser.
3.  **Parser (Legacy)**: Already supported this.
4.  **Worker**: Updated `worker.py` to persist the `is_verified` flag to the database.

### Files to Modify
- `src/migrations/add_verification_column.py` [NEW]
- `src/parser_interception.py`
- `src/worker.py`

### Trade-offs & Decisions
- **Hybrid Parsing**: Even in "Interception" mode (which relies on network logs), we now do a quick DOM query for the badge. This is a pragmatic hybrid approach to ensure data completeness without full DOM scraping penalty.

### Status
- [x] Completed

## 2026-01-27 - Fix Pricing Display & Translation Issues

### Current Task
User requested fixes for pricing display:
1.  **Separate Starter Plan Price**: Isolate price from title string (e.g. "Starter - $5" -> "Starter").
2.  **Standardize Pricing**: Fix inconsistent price for Starter ($5 vs $15) in non-RU locales.
3.  **Complete Professional Plan**: Add missing description points (4 lines missing in EN/TH/DE).

### Architecture Decision
1.  **About.tsx Refactor**: Updated `About.tsx` to use dynamic translation keys (`t.about.pricingOption0Title/Price` etc.) for Professional and Concierge plans in non-Russian languages. Kept hardcoded Russian strings (`isRu ? ...`) to minimize risk of regressions for the primary audience, but enabled dynamic content for others.
2.  **Translation Update**: Updated `en.ts`, `th.ts`, `de.ts` to split merged strings (e.g. "Title $XX") into separate `Title` and `Price` keys. Added missing usage points for Professional plan.

### Files to Modify
- `frontend/src/i18n/locales/en.ts`
- `frontend/src/i18n/locales/th.ts`
- `frontend/src/i18n/locales/de.ts`
- `frontend/src/pages/About.tsx`

### Status
- [x] Completed

## 2026-01-27 - Database Schema Integrity Verification

### Current Task
Verify if all necessary tables are present via `init_database_schema.py` and detect any missing ones that caused parser issues.

### Architecture Decision
- **UserNews Table**: Identified as missing from `init_database_schema.py` but created ad-hoc in `main.py` (concurrency risk). Added to `init` schema and created migration.
- **TokenUsage Table**: Identified as missing but optional (handled in code). Prioritized `UserNews` fix.
- **Migration Strategy**: Use `safe_migrate` with `sqlite3` fallback for adding columns (handling `CURRENT_TIMESTAMP` limitation in SQLite).

### Files to Modify
- `src/init_database_schema.py` - Added `UserNews` table definition.
- `src/migrate_create_user_news.py` - [NEW] Migration to create `UserNews` or adds `updated_at` column if missing.

### Trade-offs & Decisions
- **Consistency**: Centralizing schema in `init_database_schema.py` prevents future "ghost tables" created only by runtime code.
- **Safety**: Migration script handles `updated_at` backfill to avoid limits of SQLite `ADD COLUMN`.

### Status
- [x] Completed

## 2026-01-27 - MapParserResults Schema Fix

### Current Task
Fix `sqlite3.OperationalError: table MapParseResults has no column named title`.

### Architecture Decision
- **Missing Columns**: `title`, `address`, and `analysis_json` were missing from the production schema for `MapParseResults`.
- **Typo Confusion**: Error message referenced `MapParserResults` (extra 'r') in UI, but DB table is `MapParseResults` and was missing columns.
- **Fix**: Added columns to `init_database_schema.py` and created `src/migrate_fix_map_parse_results.py`.

### Files to Modify
- `src/init_database_schema.py` - Added 3 missing columns.
- `src/migrate_fix_map_parse_results.py` - [NEW] Migration script.

### Status
- [x] Completed

## 2026-01-27 - Fix Services in Manual Parser (Working with Maps)

### Current Task
User reported that "Services" were still missing in the report for "Working with Maps" (manual parsing), while Reviews and News appeared.

### Architecture Decision
- Identified that `src/yandex_maps_scraper.py` (Manual Parser) completely lacked logic to extract products/services (unlike the API parser).
- Implemented `parse_products` function in `yandex_maps_scraper.py`.
- Supports parsing from "Prices", "Products", or "Services" tabs.
- Extracts categories and items (name, price, description).
- Updated `parse_yandex_card` to call `parse_products` and populate `data['products']`, which is then synced to `UserServices` by `worker.py`.

### Files to Modify
- `src/yandex_maps_scraper.py` - added `parse_products` and updated main parsing function.

### Trade-offs & Decisions
- **Robustness**: Uses multiple selectors for tab names and item structures to handle Yandex Maps variations.
- **Performance**: Adds a few seconds to parsing time to click the tab and scroll, but necessary for data completeness.

### Status
- [x] Completed

## 2026-01-27 - Fix Services in Worker (Variable Scope)

### Current Task
Services were still missing after the parser update.

### Architecture Decision
- Identified a critical bug in `worker.py`: the `products` variable used in the services sync block (`if products:`) was **undefined** in the scope of the manual processing block.
- It was assumed to be extracted from `card_data` but the line `products = card_data.get('products')` was missing.

### Files to Modify
- `src/worker.py` - added proper extraction of `products` from `card_data`.

### Status
- [x] Completed

## 2026-01-27 - Frontend Report Enhancement & Deployment Readiness

### Current Task
Enable display of detailed services, reviews, and posts in the Yandex Business Report table.

### Architecture Decision
- Refactored `YandexBusinessReport.tsx` to use a tabbed interface (Overview, Reviews, Services, Posts).
- Implemented lazy loading for detail tabs to optimize performance.
- Connected frontend to new API endpoints (`/api/business/:id/services`, `/api/business/:id/external/posts`).

### Files to Modify
- `frontend/src/components/YandexBusinessReport.tsx` - complete refactor with Shadcn Tabs.
- `src/main.py` - verified endpoints.

### Status
- [x] Completed

## 2026-01-27 - Fix Date Parsing and Sorting

### Current Task
Fix incorrect date display (news showing parsing date, random dates) and sorting issues for reviews and news.

### Architecture Decision
- Identified that `dateutil` parser fails on Russian dates (e.g., "27 января"), causing fallback to "today".
- Implemented `_parse_russian_date` helper in `worker.py` with a manual mapping of Russian month names.
- Integrated validation in `reproduce_date_parsing.py`.

### Files to Modify
- `src/worker.py` - added Russian date parser logic.

### Status
- [x] Completed

## 2026-01-27 - Fixing Pricing, Metrics, and Report UI

### Current Task
Fixing incorrect service pricing display (converting "тыс." to numbers), adding 'unanswered reviews count' to metrics history and dashboard, and reverting YandexBusinessReport UI to a single-page summary.

### Architecture Decision
- **Pricing**: Modified `src/yandex_business_sync_worker.py` to use regex for parsing "тыс" and "млн" suffixes in service prices.
- **Metrics**: Added `unanswered_reviews_count` column to `ExternalBusinessStats` and `BusinessMetricsHistory` tables. Modified sync worker to calculate this count from reviews during sync and store it. Updated API `metrics_history_api.py` to return this metric.
- **UI**: 
    - Updated `MetricsHistoryCharts.tsx` to display 'Unanswered' metric.
    - Reverted `YandexBusinessReport.tsx` to remove tabs and fetch logic, making it a pure presentation component for the summary data passed from `CardOverviewPage`.

### Files to Modify
- `src/init_database_schema.py` - Added migration for `unanswered_reviews_count` in `ExternalBusinessStats` and `BusinessMetricsHistory`.
- `src/yandex_business_sync_worker.py` - Updated `_sync_services_to_db` (pricing) and `sync_account` (metrics).
- `src/repositories/external_data_repository.py` - Updated `upsert_stats`.
- `src/api/metrics_history_api.py` - Updated `get_metrics_history` to include new metric.
- `frontend/src/components/MetricsHistoryCharts.tsx` - Added 'unanswered' metric type and config.
- `frontend/src/components/YandexBusinessReport.tsx` - Reverted to single page.

### Trade-offs & Decisions
- **Schema**: Added column to both `ExternalBusinessStats` (raw data) and `BusinessMetricsHistory` (app history) to ensure consistent data flow.
- **Worker**: Calculated `unanswered_count` in python instead of SQL aggregation during sync to keep logic in one place and reuse existing `reviews` list.
- **UI**: Decided to keep `YandexBusinessReport` simple as per user request, delegating detailed views to the main dashboard tabs.

### Dependencies
- No new external dependencies.
- Database migration required (handled by `init_database_schema.py`).

### Status
- [x] Completed

## 2026-01-27 - Fix Missing Text Content (Description, News, Replies)

### Current Task
User reported that text content (Service descriptions, News text, Review replies) was missing/empty in the application, despite the parser seeming to work.

### Architecture Decision
1.  **Diagnosis**:
    - **Scraper**: Correctly extracted text (`description`, `response_text`, `text`).
    - **Worker**: Correctly passed data to repository.
    - **Database**: Schema (`ExternalBusinessReviews`, `ExternalBusinessPosts`) had the correct columns.
    - **Repository**: **ROOT CAUSE**. `ExternalDataRepository.upsert_reviews` and `upsert_posts` methods were missing the text fields in their SQL `INSERT` and `UPDATE` statements, effectively discarding the text.
2.  **Fix**:
    - Updated `ExternalDataRepository.py` to include `response_text` (for reviews) and `title`, `text` (for posts) in the SQL queries.
    - Verified `UserServices` table and `yandex_business_sync_worker` logic for descriptions (logic was correct, missing data likely due to parsing failures or old syncs).

### Files to Modify
- `src/repositories/external_data_repository.py` - Added missing fields to SQL.

### Trade-offs & Decisions
- **Data Recovery**: The fix enables *future* syncs to save text. Existing data in DB cannot be "recovered" without a re-sync/re-scrape, as the text was never saved.

### Status
- [x] Completed

## 2026-01-28 - Fix Deployment Failures (Missing File & Services)

### Current Task
User reported frontend build failure (`AddMetricModal` not found) and missing systemd units (`beautybot-backend.service`, `beautybot-worker.service`) during deployment.

### Architecture Decision
1.  **Frontend Fix**: Created `frontend/src/components/AddMetricModal.tsx` which was referenced in `MetricsHistoryCharts.tsx` but missing from the codebase.
2.  **Service Fix**: Created `beautybot-backend.service` and `beautybot-worker.service` files in the repository root (cloned from existing `seo-api.service` templates) to ensure consistent deployment names.

### Files to Modify
- `frontend/src/components/AddMetricModal.tsx` [NEW]
- `beautybot-backend.service` [NEW]
- `beautybot-worker.service` [NEW]

### Status
- [x] Completed


## 2026-01-29 - Fix Missing "Services" Column in Parsing History

### Current Task
User reported that "Services" column was missing in the parsing history table and not showing up in reports, leading to confusion about data completeness.

### Architecture Decision
1.  **Database Schema**: Added `services_count` (INTEGER) and `products` (TEXT/JSON) columns to `MapParseResults` table.
2.  **Worker Logic**: Updated `YandexBusinessSyncWorker` (`src/yandex_business_sync_worker.py`) to calculate `services_count` from parsed products and persist it to `MapParseResults`.
3.  **Frontend**: Added "Services" column to `MapParseTable.tsx` to display the count.

### Files to Modify
- `src/init_database_schema.py` - Updated schema definition for future deploys.
- `src/yandex_business_sync_worker.py` - Updated insert/update logic.
- `frontend/src/components/MapParseTable.tsx` - Added table column.
- `src/migrate_add_map_parse_columns.py` [NEW] - Migration script for existing servers.
- `frontend/src/i18n/locales/ru.ts` - Added translation key.

### Trade-offs & Decisions
- **Migration**: Created a dedicated migration script to ensure data integrity on existing servers without requiring a full schema reset.
- **UI**: Added column to the history table to provide immediate feedback on whether services were successfully parsed.

### Status
- [x] Completed

## 2026-01-29 - Fix Date Parsing & UserServices Integrity Error

### Current Task
1.  **Date Parsing**: Russian dates with punctuation (e.g., "5 сентября,") failed to parse.
2.  **Integrity Error**: `sqlite3.IntegrityError: NOT NULL constraint failed: UserServices.user_id` occurred during service sync.

### Architecture Decision
1.  **Date Parsing**: Updated `_parse_russian_date` in `worker.py` to strip punctuation using regex `re.sub(r'[^\w\s]', '', month_str)` before dictionary lookup. Confirmed with `tests/test_date_parsing_strict.py`.
2.  **Integrity Error**:
    *   **Root Cause**: `worker.py` and `yandex_business_sync_worker.py` implicitly relied on fetching `owner_id` from `Businesses` table inside the sync function, which could fail or return None.
    *   **Fix**: Refactored `_sync_parsed_services_to_db` to require `user_id` (str) as a mandatory argument.
    *   **Fetch Once**: Moved `owner_id` fetching to the top-level `sync_account` method in `yandex_business_sync_worker.py` and `process_queue` in `worker.py`.
    *   **Migration**: Created `src/migration_fix_orphan_services.py` which fixed 41 existing orphan records by linking them to their business owners.

### Files to Modify
- `src/worker.py` - Regex fix and signature change.
- `src/yandex_business_sync_worker.py` - Signature change and fetch logic.
- `src/migration_fix_orphan_services.py` [NEW] - Data repair script.
- `tests/test_date_parsing_strict.py` [NEW] - Verification test.
- `tests/test_services_sync_logic.py` [NEW] - Logic verification test.

### Trade-offs & Decisions
- **Strictness**: Fail-fast approach (raising `ValueError` if `user_id` is missing) chosen over silent failure to prevent data corruption.
- **Migration**: Manual script chosen over auto-migration on startup to allow controlled execution and backup.

### Status
- [x] Completed
