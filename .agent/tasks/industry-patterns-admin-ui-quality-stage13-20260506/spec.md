# Task Spec: industry-patterns-admin-ui-quality-stage13-20260506

## Metadata
- Task ID: industry-patterns-admin-ui-quality-stage13-20260506
- Created: 2026-05-06T15:37:56+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Этап 13: качество и безопасность web/admin UI для управления industry patterns

## Acceptance criteria
- AC1: Web/admin UI shows a compact safety/status panel for pattern management.
- AC2: Destructive admin actions require explicit confirmation in the UI and backend.
- AC3: Rollback apply requires a prior rollback preview confirmation token.
- AC4: Admin pattern actions are recorded and recent admin events are visible in the UI.
- AC5: Existing superadmin-only access remains enforced.

## Constraints
- Keep changes scoped to industry pattern admin UI/API.
- Do not apply or mutate production pattern data during verification.
- Do not make beauty-specific rules global.

## Non-goals
- Full Playwright/browser automation of authenticated admin flows.
- Replacing the existing Telegram HITL flow.

## Verification plan
- Build: frontend TypeScript check and production build.
- Unit tests: industry pattern regression tests.
- Integration tests: backend syntax checks locally and in container.
- Lint: not applicable; project uses TypeScript/build gates here.
- Manual checks: production deploy smoke, no-auth 403, live frontend bundle check.
