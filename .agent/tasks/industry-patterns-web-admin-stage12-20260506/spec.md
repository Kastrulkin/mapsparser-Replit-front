# Task Spec: industry-patterns-web-admin-stage12-20260506

## Metadata
- Task ID: industry-patterns-web-admin-stage12-20260506
- Created: 2026-05-06T15:12:36+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Этап 12: web/admin UI для управления паттернами

## Acceptance criteria
- AC1: Superadmin web API exists for industry pattern summary, pending/revision proposals, active versions, detail cards, impact health, and recalibration.
- AC2: Web admin can accept/reject/revise pending proposals.
- AC3: Web admin can regenerate proposals that are on revision.
- AC4: Web admin can view active patterns, health/impact counters, details, good/bad examples, decisions, and rollback candidates.
- AC5: Web admin can create a new pending version proposal, send active pattern to revision, and disable active pattern.
- AC6: Web admin rollback uses the same safety model as Telegram: preview first, reason, explicit confirm, backend re-validation.
- AC7: Bazich admin has a visible "Паттерны" tab and lazy-loads the management UI.
- AC8: No schema migration is added; all actions use existing HITL/version tables.
- AC9: Local build/tests and production smoke checks pass.

## Constraints
- Do not add a migration.
- Do not apply patterns automatically.
- Keep Telegram HITL behavior intact.
- Keep UI in the existing Bazich admin, not a separate landing page.
- Backend endpoints must be superadmin-only.

## Non-goals
- Full visual diff editor.
- Bulk web approval.
- A/B impact attribution.
- Replacing Telegram HITL.

## Verification plan
- Build: Python compile, frontend build:all, frontend dist integrity.
- Unit tests: industry pattern regression suite.
- Integration tests: production API smoke with and without superadmin auth, frontend bundle check, app/worker logs.
- Lint: targeted TypeScript error check for new files.
- Manual checks: inspect admin tab wiring and rollback confirm flow.
