# Технический контекст

- **Языки**: Python 3.11 (бекенд), TypeScript + React 18 (фронтенд), SQL (SQLite).
- **Фреймворки и библиотеки**:
  - Flask 2.3 для API, user_api и внутренних сервисов.
  - Selenium, Playwright, BeautifulSoup, pandas для парсинга и анализа данных карточек.
  - Transformers + Hugging Face API, torch 2.1 для AI-анализов.
  - React 18 + Vite 7 + TailwindCSS 3.4 + Radix UI + shadcn/ui на фронтенде.
  - @tanstack/react-query для работы с данными, react-router-dom для навигации.
- **База данных**: SQLite (`reports.db` в корне и `src/reports.db` для исторических модулей). Работа ведётся через `DatabaseManager` и `safe_db_utils`.
- **Сборка и деплой**:
  - Vite build → копирование dist в `/var/www/html`.
  - systemd сервисы `seo-worker`, `seo-api`, `seo-download`.
  - Скрипты `server_update_commands.sh`, `cleanup_server.sh` для автоматизации обновлений и очистки диска.
- **Инфраструктура**:
  - Nginx как фронтовой сервер.
  - Bash-скрипты для миграций, резервных копий и синхронизации баз (`db_backups/`).
  - Виртуальное окружение Python (`venv/`).
