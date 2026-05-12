# Task Spec: finance-action-plan-stage5-20260512

## Metadata
- Task ID: finance-action-plan-stage5-20260512
- Created: 2026-05-12T12:42:31+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Этап 5 финансов: операционные планы действий для KPI-рекомендаций, UI, тесты

## Acceptance criteria
- AC1: Finance recommendations include an operational action plan while keeping old fields compatible.
- AC2: UI renders today / 7 days / regular actions for each recommendation.
- AC3: Missing-data fallback recommendation also gives onboarding actions.
- AC4: Tests, targeted lint, backend syntax and frontend build pass.

## Constraints
- Do not add new DB schema for this stage.
- Do not break existing `code/title/text/severity` recommendation consumers.
- Keep the UI inside existing Finance page patterns.

## Non-goals
- Task management workflow.
- Automatic execution of recommendations.
- Industry-specific recommendation engines beyond current service-business finance logic.

## Verification plan
- Build: `npm run build` in `frontend`.
- Unit tests: `python3 -m pytest -q tests/test_finance_kpis.py tests/test_finance_imports.py tests/test_finance_crm.py`.
- Integration tests: `python3 -m py_compile src/core/finance_kpis.py src/main.py`.
- Lint: targeted ESLint for touched finance frontend files.
- Manual checks: inspect generated recommendation payload shape and UI render path.
