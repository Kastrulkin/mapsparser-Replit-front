# Task Spec: finance-thresholds-stage4-20260512

## Metadata
- Task ID: finance-thresholds-stage4-20260512
- Created: 2026-05-12T12:09:56+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Этап 4 финансов: настройки KPI-порогов по бизнесу, API, UI, рекомендации с нормами

## Acceptance criteria
- AC1: Finance KPI thresholds are persisted per business through Alembic schema.
- AC2: Finance dashboard, recalculation, import, CRM sync, data-quality and recommendations use the same business-specific thresholds.
- AC3: Finance UI exposes a practical thresholds panel with save/reset.
- AC4: Recommendations and statuses change when custom thresholds are supplied.
- AC5: Relevant unit/build/syntax checks pass, with known unrelated lint debt documented.

## Constraints
- Do not apply production migrations or mutate production data in this stage.
- Keep existing finance import and CRM adapter flow intact.
- Follow current Flask/Vite patterns and avoid broad redesign.

## Non-goals
- Production CRM providers.
- Full historical BI or forecasting.
- Fixing unrelated frontend lint debt.

## Verification plan
- Build: `npm run build` in `frontend`.
- Unit tests: `python3 -m pytest -q tests/test_finance_kpis.py tests/test_finance_imports.py tests/test_finance_crm.py`.
- Integration tests: targeted API syntax via `python3 -m py_compile src/main.py`.
- Lint: targeted ESLint on new/touched finance UI files.
- Manual checks: open local `/dashboard/finance` route and confirm no browser console runtime errors in unauthenticated smoke.
