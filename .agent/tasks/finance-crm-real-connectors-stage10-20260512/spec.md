# Task Spec: finance-crm-real-connectors-stage10-20260512

## Metadata
- Task ID: finance-crm-real-connectors-stage10-20260512
- Created: 2026-05-12T14:53:33+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Этап 10: подготовить реальные CRM-коннекторы YCLIENTS/Altegio без боевого подключения

## Acceptance criteria
- AC1: Проверить публичную доступность API YCLIENTS/Altegio и зафиксировать ограничения.
- AC2: Перевести YCLIENTS/Altegio из planned-заглушек в подготовленные CRM-коннекторы без боевого подключения.
- AC3: Не синхронизировать без partner token, user token и ID филиала; возвращать понятную ошибку.
- AC4: Дать UI возможность ввести реквизиты и увидеть документацию/возможности провайдера.
- AC5: Покрыть реестр, авторизацию и нормализацию тестами.

## Constraints
- Не выполнять реальные запросы к CRM без выданных ключей клиента.
- Не хранить auth data в публичном payload.
- Не менять KPI-слой и схему БД в этом этапе.
- Использовать существующую таблицу `finance_crm_connections`.

## Non-goals
- Не делать marketplace/OAuth activation flow.
- Не подключать конкретный филиал без договоренности с CRM и владельцем.
- Не делать полную нормализацию клиентов/визитов в финансовые KPI.

## Verification plan
- Build: `cd frontend && npm run build`
- Unit tests: `python3 -m pytest -q tests/test_finance_crm.py tests/test_finance_imports.py tests/test_finance_kpis.py`
- Integration tests: `python3 -m py_compile src/main.py src/core/finance_crm.py src/core/finance_imports.py src/core/finance_kpis.py`
- Lint: targeted eslint по finance frontend files
- Manual checks: провайдеры показывают поля `location_id`, `partner_token`, `user_token`
