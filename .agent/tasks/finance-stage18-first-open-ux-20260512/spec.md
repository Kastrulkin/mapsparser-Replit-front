# Task Spec: finance-stage18-first-open-ux-20260512

## Metadata
- Task ID: finance-stage18-first-open-ux-20260512
- Created: 2026-05-12T16:09:39+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Этап 18: сделать вкладку Финансы понятной при первом открытии: пустое состояние, мини-мастер ввода, демо-данные, пояснения KPI и приоритеты

## Acceptance criteria
- AC1: Finance tab has a clear first-open empty state that explains what to enter first.
- AC2: User can see a simple mini-wizard path: money, services, staff, workplaces.
- AC3: User can fill a demo salon example without writing data to DB automatically.
- AC4: KPI cards explain what the metric means and what to do when it is weak.
- AC5: Top of the finance block shows the first 2-3 priorities instead of only raw metrics.
- AC6: Frontend build, targeted lint, and finance tests pass.

## Constraints
- Keep existing finance API and data model.
- Do not remove legacy finance tools; keep them below as secondary tools.
- Do not save demo data automatically.

## Non-goals
- Full redesign of every finance table.
- New backend schema changes.
- Live CRM verification.

## Verification plan
- Build: `cd frontend && npm run build`.
- Unit tests: `python3 -m pytest tests/test_finance_kpis.py tests/test_finance_imports.py tests/test_finance_crm.py -q`.
- Lint: `cd frontend && npm exec -- eslint src/components/FinanceFirstStep.tsx src/pages/dashboard/FinancePage.tsx`.
- Manual checks: inspect FinanceFirstStep first-open copy, demo button, mini-wizard state, KPI explanations.
