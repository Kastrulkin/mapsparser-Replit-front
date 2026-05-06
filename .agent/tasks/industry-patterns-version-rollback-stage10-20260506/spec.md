# Task Spec: industry-patterns-version-rollback-stage10-20260506

## Metadata
- Task ID: industry-patterns-version-rollback-stage10-20260506
- Created: 2026-05-06T14:50:22+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Этап 10: версии и rollback active-паттернов без деплоя

## Acceptance criteria
- AC1: Active pattern card can create a new pending version proposal without deploy.
- AC2: Active pattern card shows rollback candidates/other versions.
- AC3: Rollback can activate a selected previous version and deactivate the current context version through Telegram HITL.
- AC4: Rollback and new-version actions are logged in `industry_pattern_decisions`.
- AC5: Optimizer continues to read active patterns from DB; no code deploy is needed for future version changes.
- AC6: Relevant tests and production smoke checks pass.

## Constraints
- Do not add a new migration.
- Do not auto-rollback or auto-disable patterns.
- Keep Telegram callback data under Telegram limits.
- Rollback must be initiated by superadmin.

## Non-goals
- Full web UI for version diff.
- Automated A/B impact comparison.

## Verification plan
- Build: Python syntax checks for touched modules.
- Unit tests: industry patterns and related regressions.
- Integration: production AST check, app/worker/bot restart, HTTP smoke, logs.
