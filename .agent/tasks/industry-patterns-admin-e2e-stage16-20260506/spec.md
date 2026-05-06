# Task Spec: industry-patterns-admin-e2e-stage16-20260506

## Metadata
- Task ID: industry-patterns-admin-e2e-stage16-20260506
- Created: 2026-05-06T16:11:32+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Этап 16: E2E browser smoke для web/admin UI паттернов

## Acceptance criteria
- AC1: Web/admin industry patterns UI has a browser smoke path that can run without production auth or DB state.
- AC2: Smoke covers the important admin flows: summary, safety, business effect, pending proposals, calibration confirmation, active versions, detail card, and rollback preview.
- AC3: Production frontend build and TypeScript check remain green.
- AC4: Existing industry pattern API/UI Telegram regressions remain green.

## Constraints
- Do not depend on production credentials or mutate production data.
- Keep the E2E harness dev-only.
- Do not weaken current web/admin safety rules.
- Do not touch unrelated dirty files.

## Non-goals
- No new browser test framework dependency in this stage.
- No production deployment required for the dev-only smoke route.

## Verification plan
- Build: `npm run build`
- Unit tests: focused industry-pattern regression pytest files
- Integration tests: Vite dev route `curl -I`
- Lint: `npx tsc --noEmit --pretty false`
- Manual checks: Browser Use smoke on `/__e2e__/industry-patterns`
