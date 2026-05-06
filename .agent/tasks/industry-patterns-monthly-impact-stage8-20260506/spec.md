# Task Spec: industry-patterns-monthly-impact-stage8-20260506

## Metadata
- Task ID: industry-patterns-monthly-impact-stage8-20260506
- Created: 2026-05-06T14:30:14+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Этап 8: monthly impact report суперадмину по active-паттернам

## Acceptance criteria
- AC1: Build a monthly active-pattern impact report from `industry_pattern_impact_events`.
- AC2: Report shows totals by type and key causes: fallback, guardrails, missing keywords, drift, facts risk, too long, no detail.
- AC3: Report identifies candidates to keep, watch, revise, or disable without automatic action.
- AC4: Superadmin can run the report manually from Telegram command and menu button.
- AC5: Monthly superadmin Telegram digest includes the impact report on the 1st day of the month.
- AC6: HITL buttons allow disabling or sending an active pattern to revision.
- AC7: Relevant tests and production smoke checks pass.

## Constraints
- Do not add a new migration; reuse existing impact events table.
- Do not auto-disable, auto-accept, or auto-revise patterns.
- Decisions must stay human-in-the-loop.

## Non-goals
- A/B attribution.
- Detailed per-pattern history screen; that is the next stage.
- Frontend dashboard.

## Verification plan
- Build: Python syntax checks for touched modules.
- Unit tests: industry patterns, content plan, worker quality, service/beauty regressions.
- Integration: production AST syntax check, restart app/worker/bot, HTTP smoke, logs.
