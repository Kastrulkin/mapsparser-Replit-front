# Task Spec: finance-first-step-20260512

## Metadata
- Task ID: finance-first-step-20260512
- Created: 2026-05-12T10:26:51+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Доработать вкладку Финансы: onboarding, KPI, рабочие места, data quality, рекомендации

## Acceptance criteria
- AC1: Во вкладке "Финансы" есть onboarding для первичного сбора данных.
- AC2: Можно внести базовые данные за последние 3 месяца.
- AC3: Система считает P&L и ключевые KPI.
- AC4: Система считает загрузку кресел / рабочих мест.
- AC5: Система считает выручку на кресло и кресло-час.
- AC6: Система показывает точку безубыточности и дневную цель.
- AC7: Система показывает data quality score и объясняет, чего не хватает.
- AC8: Система показывает рекомендации по красным зонам.
- AC9: При неполных данных нет ошибок, есть null + explanation.
- AC10: Есть тесты на формулы и рекомендации.
- AC11: Есть docs/FINANCE_MODULE.md.

## Constraints
- Не строить полноценную ERP/BI/CRM.
- Не ломать существующие financialtransactions, metrics и ROI.
- Schema changes только через Alembic.
- Beauty/service-business профиль не применять глобально.

## Non-goals
- CRM connectors.
- Сложный import wizard CSV/XLSX.
- Cohort analysis, CAC, retail attachment.
- Прогнозирование выручки.

## Verification plan
- Build: `cd frontend && npm run build`
- Unit tests: `python3 -m pytest -q tests/test_finance_kpis.py`
- Syntax: `python3 -m py_compile src/main.py src/core/finance_kpis.py`
- Manual checks: inspect Finance page integration and API route shape.
