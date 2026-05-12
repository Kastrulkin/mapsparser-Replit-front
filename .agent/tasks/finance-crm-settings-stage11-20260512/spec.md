# Task Spec: finance-crm-settings-stage11-20260512

## Metadata
- Task ID: finance-crm-settings-stage11-20260512
- Created: 2026-05-12T15:08:19+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Этап 11: вынести CRM подключение в настройки/интеграции и сохранить sync во вкладке Финансы

## Acceptance criteria
- AC1: CRM-подключение доступно в `Настройки → Интеграции`.
- AC2: Блок CRM не дублирует вложенную dashboard-секцию внутри секции настроек.
- AC3: Вкладка `Финансы` продолжает показывать CRM-синхронизацию для запуска sync.
- AC4: Нет регресса в finance CRM API/tests/build.

## Constraints
- Не менять backend-схему и не трогать реальные credentials.
- Не удалять CRM-блок из Финансов, пока там нужен быстрый sync после импорта/расчёта.
- Не ломать существующие ExternalIntegrations.

## Non-goals
- Не делать отдельную страницу настроек CRM.
- Не запускать реальную синхронизацию с YCLIENTS/Altegio.

## Verification plan
- Build: `cd frontend && npm run build`
- Unit tests: `python3 -m pytest -q tests/test_finance_crm.py tests/test_finance_imports.py tests/test_finance_kpis.py`
- Integration tests: `python3 -m py_compile src/main.py src/core/finance_crm.py src/core/finance_imports.py src/core/finance_kpis.py`
- Lint: targeted eslint for Settings/Finance CRM files
- Manual checks: code inspection confirms SettingsPage embeds FinanceCrmPanel with `surface="embedded"`
