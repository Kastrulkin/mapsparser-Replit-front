# Task Spec: finance-crm-contract-clients-stage14-15-20260512

## Metadata
- Task ID: finance-crm-contract-clients-stage14-15-20260512
- Created: 2026-05-12T15:29:42+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Этапы 14-15: контрактные payload-примеры CRM и нормализация записей/клиентов

## Acceptance criteria
- AC1: Добавить обезличенный CRM contract fixture для YCLIENTS/Altegio-подобного payload.
- AC2: Fixture должен использоваться в тестах preview/mapping, чтобы закрепить контракт.
- AC3: Нормализовать CRM appointments в staff metrics: visits, no-show, rebooking, revenue, booked minutes.
- AC4: Нормализовать CRM appointments в service metrics: visits, revenue, avg price, duration.
- AC5: Не раскрывать реальные персональные данные или токены в fixtures.
- AC6: Обновить документацию и пройти тесты/build/lint.

## Constraints
- Не делать реальный запрос к YCLIENTS/Altegio без credentials.
- Не менять БД/миграции на этом этапе.
- Не писать новые CRM entities в finance tables напрямую; только через существующий import pipeline.
- Не использовать реальные телефоны/ФИО в fixtures.

## Non-goals
- Не делать финальный mapping всех полей YCLIENTS/Altegio без sandbox response.
- Не добавлять отдельные client tables.
- Не менять UI в этом этапе.

## Verification plan
- Build: `cd frontend && npm run build`
- Unit tests: `python3 -m pytest -q tests/test_finance_crm.py tests/test_finance_imports.py tests/test_finance_kpis.py`
- Integration tests: `python3 -m py_compile src/core/finance_crm.py src/core/finance_imports.py src/core/finance_kpis.py src/main.py`
- Lint: targeted eslint for existing finance CRM UI
- Manual checks: fixture contains synthetic data only.
