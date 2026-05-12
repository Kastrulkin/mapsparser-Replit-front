# Task Spec: finance-action-checklist-stage6-20260512

## Metadata
- Task ID: finance-action-checklist-stage6-20260512
- Created: 2026-05-12T12:52:26+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Этап 6 финансов: чеклист выполнения рекомендаций, action log, API, UI, тесты

## Acceptance criteria
- AC1: Finance action checklist state is persisted per business.
- AC2: Finance API can read and update action completion state.
- AC3: Finance dashboard returns action logs with recommendation payloads.
- AC4: UI renders checklist actions and completion progress.
- AC5: Relevant backend, frontend and proof checks pass.

## Constraints
- Keep recommendation payload backward compatible.
- Do not build a full task manager in this stage.
- Do not mutate production data or apply production migrations locally.

## Non-goals
- Assignees, due dates, notifications or recurring task automation.
- KPI impact attribution after completion.
- Telegram checklist flow.

## Verification plan
- Build: `npm run build` in `frontend`.
- Unit tests: `python3 -m pytest -q tests/test_finance_kpis.py tests/test_finance_imports.py tests/test_finance_crm.py`.
- Integration tests: `python3 -m py_compile src/main.py src/core/finance_kpis.py`.
- Lint: targeted ESLint for touched finance frontend files.
- Manual checks: inspect route/table wiring and dashboard payload shape.
