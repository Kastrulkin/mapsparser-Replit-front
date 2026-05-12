# Task Spec: finance-crm-adapter-stage3-20260512

## Metadata
- Task ID: finance-crm-adapter-stage3-20260512
- Created: 2026-05-12T11:53:39+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Этап 3 финансов: CRM adapter layer, connections, sync endpoints, mock adapter, UI status

## Acceptance criteria
- AC1: Есть CRMConnector interface / base adapter contract.
- AC2: Есть mock/demo CRM adapter для безопасной проверки sync.
- AC3: Есть таблица `finance_crm_connections`.
- AC4: Есть endpoints providers/connect/status/sync.
- AC5: CRM sync пишет данные в те же finance tables через import pipeline.
- AC6: CRM sync сохраняет external_id/duplicate_key и не плодит дубли.
- AC7: В UI финансов есть CRM-блок со статусом и запуском sync.
- AC8: Есть тесты CRM registry/adapter/normalization.
- AC9: Production frontend build проходит.

## Constraints
- Не подключать реальные CRM без явной настройки provider credentials.
- Не хранить auth_data открытым текстом.
- Не ломать ручной ввод и CSV/XLSX import.
- Перед продом нужен DB backup + Alembic migration.

## Non-goals
- Реальный YCLIENTS/Altegio API adapter.
- OAuth или полноценный credential wizard.
- Async job queue для sync.
- Автоматическая CRM-синхронизация по расписанию.

## Verification plan
- Build: `cd frontend && npm run build`
- Unit tests: `python3 -m pytest -q tests/test_finance_kpis.py tests/test_finance_imports.py tests/test_finance_crm.py`
- Syntax: `python3 -m py_compile src/main.py src/core/finance_kpis.py src/core/finance_imports.py src/core/finance_crm.py alembic_migrations/versions/20260512_add_finance_first_step.py`
- Manual checks: inspect route/UI wiring and migration shape.
