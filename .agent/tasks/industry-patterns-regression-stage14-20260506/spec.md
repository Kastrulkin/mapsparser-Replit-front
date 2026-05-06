# Task Spec: industry-patterns-regression-stage14-20260506

## Metadata
- Task ID: industry-patterns-regression-stage14-20260506
- Created: 2026-05-06T15:52:55+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Этап 14: автотесты и регрессии всей системы паттернов

## Acceptance criteria
- AC1: Backend admin pattern API regression tests cover auth gates, superadmin access, destructive confirmation gates, and rollback preview token.
- AC2: Frontend admin pattern UI regression test covers safety/status panel and confirmation flow wiring.
- AC3: Telegram HITL regression test verifies proposals 4 and 5 are actionable in pending proposal markup.
- AC4: Existing industry-pattern core regressions keep passing.
- AC5: Build/type/syntax checks pass.

## Constraints
- Do not mutate production data.
- Prefer fast unit/regression tests using fakes and monkeypatching over live external services.
- Keep implementation scoped to tests unless a direct bug is discovered.

## Non-goals
- Full authenticated Playwright browser automation.
- Real Telegram API calls.
- Real database writes.

## Verification plan
- Build: frontend TypeScript noEmit and production build.
- Unit tests: focused Python pytest files for industry patterns.
- Integration tests: Flask blueprint test client with fake auth/DB.
- Lint: Python compile checks for touched backend/test modules.
- Manual checks: not required; no runtime behavior changes in this stage.
