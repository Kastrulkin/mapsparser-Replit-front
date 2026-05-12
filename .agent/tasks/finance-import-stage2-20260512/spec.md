# Task Spec: finance-import-stage2-20260512

## Metadata
- Task ID: finance-import-stage2-20260512
- Created: 2026-05-12T11:20:35+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Этап 2 финансов: импорт CSV/XLSX, антидубли, import batches, templates, data quality integration

## Acceptance criteria
- AC1: Есть таблица истории импортов и поля для антидублей.
- AC2: Есть backend preview для CSV/XLSX с mapping, валидными строками и ошибками.
- AC3: Есть backend import, который создает batch и пропускает дубли.
- AC4: Есть шаблон импорта CSV.
- AC5: В UI финансов есть блок импорта с preview, загрузкой и историей.
- AC6: Импорт интегрирован с пересчетом finance dashboard/data quality.
- AC7: Есть тесты parser/normalizer/duplicate key.
- AC8: Production frontend build проходит.
- AC9: Миграция содержит все новые таблицы/колонки для stage 1+2.

## Constraints
- Не деплоить и не менять production data без отдельного подтверждения.
- Перед продом применить Alembic migration.
- Не ломать legacy finance transactions upload.
- CSV/XLSX import делать минимальным, без полноценного CRM connector.

## Non-goals
- CRM connectors.
- Сложный визуальный column mapping editor.
- Автоматическая чистка старых финансовых данных.
- Полноценный BI/report builder.

## Verification plan
- Build: `cd frontend && npm run build`
- Unit tests: `python3 -m pytest -q tests/test_finance_kpis.py tests/test_finance_imports.py`
- Syntax: `python3 -m py_compile src/main.py src/core/finance_kpis.py src/core/finance_imports.py alembic_migrations/versions/20260512_add_finance_first_step.py`
- Manual checks: inspect endpoint and UI wiring.
