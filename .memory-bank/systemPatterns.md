# Архитектурные паттерны и стандарты

- **Архитектура**: модульный монолит. Основные домены вынесены в отдельные модули (`parser`, `ai_analyzer`, `worker`, `auth_system`, `database_manager`). UI работает как SPA, а Flask отдаёт API и статический билд.
- **Слои**:
  - Парсинг → Аналитика → Генерация отчёта → API/Worker → Фронтенд.
  - Каждая миграция БД проходит через `safe_db_utils` с автоматическими бэкапами.
- **API-стандарты**:
  - REST JSON, префикс `/api/...`, единый обработчик ошибок (`jsonify({"error": ...})`).
  - Публичные эндпоинты (`/api/public/...`) отделены от авторизованных (`/api/...`).
  - Кросс-доменные запросы проходят через CORS в `user_api`.
- **Кодстайл**:
  - Python: `snake_case`, docstrings, обязательный импорт dotenv.
  - TypeScript/React: `camelCase`, функциональные компоненты + хуки, `LanguageContext` для i18n.
  - Переводы хранятся в `frontend/src/i18n/locales/*.ts`, ключи синхронизированы между языками.
- **i18n-паттерн**: `LanguageProvider` оборачивает приложение, `LanguageSwitcher` обновляет `localStorage`, `t.pageTitle` синхронизирует `<title>`.
- **Безопасность данных**: резервные копии в `db_backups`, скрипты очистки явно защищают `reports.db`, `.env`, `node_modules`, `venv`, таблицы Users/UserSessions.
