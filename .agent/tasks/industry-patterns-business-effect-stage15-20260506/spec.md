# Task Spec: industry-patterns-business-effect-stage15-20260506

## Metadata
- Task ID: industry-patterns-business-effect-stage15-20260506
- Created: 2026-05-06T15:59:05+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Этап 15: аналитика качества паттернов по бизнес-эффекту

## Acceptance criteria
- AC1: Pattern result metrics include business-effect signals: SEO score delta, keyword delta, accepted count, manual edits, effect score/status.
- AC2: Monthly impact report aggregates business-effect totals, by type and by industry, and identifies effective/questionable patterns.
- AC3: Admin UI shows business-effect summary and top effective/questionable patterns.
- AC4: Regression tests cover business-effect metrics and report text.
- AC5: Type/build/backend checks pass and production deploy is verified.

## Constraints
- Do not introduce a new parallel prompt or pattern source.
- Do not mutate production data during verification.
- Keep existing guardrails/impact recommendations compatible.

## Non-goals
- Full business outcome attribution from external map rankings.
- New DB migrations; use existing impact event metrics JSON.

## Verification plan
- Build: frontend TypeScript noEmit and production build.
- Unit tests: focused industry pattern pytest suite.
- Integration tests: server deploy smoke and runtime compile.
- Lint: Python compile checks.
- Manual checks: production no-auth 403 and live bundle check.
