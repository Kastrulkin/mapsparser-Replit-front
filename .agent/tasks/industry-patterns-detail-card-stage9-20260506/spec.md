# Task Spec: industry-patterns-detail-card-stage9-20260506

## Metadata
- Task ID: industry-patterns-detail-card-stage9-20260506
- Created: 2026-05-06T14:39:03+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Этап 9: детальная карточка active-паттерна с историей применений, примерами good/bad, причинами проблем и решениями суперадмина

## Acceptance criteria
- AC1: Active pattern detail card can be opened from Telegram active list, health, and impact report.
- AC2: Detail card shows active pattern metadata, impact summary, recent reasons, and recent event history.
- AC3: Detail card shows good and bad examples when event metrics include sample text.
- AC4: Detail card shows recent superadmin decisions linked to the source proposal/version/revision proposals.
- AC5: Detail card preserves HITL actions: send active pattern to revision or disable.
- AC6: Relevant tests and production smoke checks pass.

## Constraints
- Do not add a new migration.
- Do not auto-disable or auto-revise patterns.
- Keep Telegram callback data short enough for Telegram limits.

## Non-goals
- Full frontend UI.
- Long-term full-text storage beyond compact impact samples in metrics.

## Verification plan
- Build: Python syntax checks for touched modules.
- Unit tests: industry patterns and related regression tests.
- Integration: production AST syntax check, app/worker/bot restart, HTTP smoke, logs.
