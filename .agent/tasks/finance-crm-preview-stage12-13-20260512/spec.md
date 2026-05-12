# Task Spec: finance-crm-preview-stage12-13-20260512

## Metadata
- Task ID: finance-crm-preview-stage12-13-20260512
- Created: 2026-05-12T15:17:34+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Этапы 12-13: sandbox/live проверка CRM-контракта и CRM sync preview без записи в финансы

## Acceptance criteria
- AC1: Добавить CRM preview endpoint, который проверяет sandbox/live контракт без записи в finance tables.
- AC2: Preview должен возвращать counts по CRM dataset, counts по нормализованным строкам, ошибки и примеры строк.
- AC3: Preview не должен раскрывать токены/секреты в raw samples.
- AC4: UI должен иметь действие "Проверить данные" перед реальной синхронизацией и показывать понятную сводку.
- AC5: Реальный sync остаётся отдельным действием и продолжает писать данные только после явного запуска.
- AC6: Добавить тесты и пройти build/lint/compile.

## Constraints
- Не выполнять реальные CRM запросы без сохранённого подключения и ключей.
- Не создавать `finance_import_batches` и не писать finance rows в preview.
- Не менять Alembic-схему на этом этапе.
- Не показывать auth secrets в preview payload.

## Non-goals
- Не подключать конкретный YCLIENTS/Altegio филиал без credentials.
- Не делать финальную field mapping к live API без sandbox payload.
- Не заменять существующий sync preview-режимом.

## Verification plan
- Build: `cd frontend && npm run build`
- Unit tests: `python3 -m pytest -q tests/test_finance_crm.py tests/test_finance_imports.py tests/test_finance_kpis.py`
- Integration tests: `python3 -m py_compile src/main.py src/core/finance_crm.py src/core/finance_imports.py src/core/finance_kpis.py`
- Lint: targeted eslint for Finance CRM UI
- Manual checks: code inspection confirms `/api/finance/crm/preview` does not insert import batches.
