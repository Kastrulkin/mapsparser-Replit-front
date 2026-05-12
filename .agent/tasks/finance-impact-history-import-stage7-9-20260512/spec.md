# Task Spec: finance-impact-history-import-stage7-9-20260512

## Metadata
- Task ID: finance-impact-history-import-stage7-9-20260512
- Created: 2026-05-12T14:13:10+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Этапы 7-9 финансов: влияние действий на KPI, история периодов, улучшенный import wizard

## Acceptance criteria
- AC1: Finance impact compares current KPI values with the previous equivalent period and includes completed action count.
- AC2: Finance history returns monthly points for 3, 6 or 12 months.
- AC3: Finance UI shows action impact and period history.
- AC4: Import wizard supports template profiles, preview mapping and manual mapping edits.
- AC5: Relevant tests, backend syntax, targeted frontend lint and production build pass.

## Constraints
- Do not add new schema unless required.
- Keep existing import endpoint compatibility.
- Treat impact as directional management signal, not strict attribution.

## Non-goals
- Causal analytics.
- Real YCLIENTS/Altegio API connectors.
- Heavy BI charts.

## Verification plan
- Build: `npm run build` in `frontend`.
- Unit tests: `python3 -m pytest -q tests/test_finance_kpis.py tests/test_finance_imports.py tests/test_finance_crm.py`.
- Integration tests: `python3 -m py_compile src/main.py src/core/finance_kpis.py src/core/finance_imports.py src/core/finance_crm.py`.
- Lint: targeted ESLint on finance frontend files.
- Manual checks: inspect endpoint/UI wiring.
