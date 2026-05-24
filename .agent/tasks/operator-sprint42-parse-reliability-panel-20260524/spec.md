# Task Spec: operator-sprint42-parse-reliability-panel-20260524

## Metadata
- Task ID: operator-sprint42-parse-reliability-panel-20260524
- Created: 2026-05-24T16:23:11+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md
- agents/autonomous_development_brief.md

## Original task statement
Sprint 42: Apify/parse reliability panel for Operator refresh jobs. Show parse failures, retry/captcha/DLQ state, failed jobs, and user-facing explanations without provider writes or new parser execution.

## Acceptance criteria
- AC1: Refresh result and refresh-job history expose a typed `reliability_state` built from existing `parsequeue`/worker fields.
- AC2: Reliability state covers success, processing, retrying, captcha, failed, paused, completed-with-warnings, and known parser failure reasons.
- AC3: Web Operator shows retry/captcha/error/warning counters and a user-facing explanation per refresh job.
- AC4: Telegram refresh-job summaries include compact reliability information when a job needs attention.
- AC5: The feature stays read-only: no retry execution, no Apify start, no credit mutation, no external map writes.

## Constraints
- Use existing `parsequeue` fields and `parsing_failure_taxonomy`.
- Do not add a migration or new table.
- Do not enqueue, retry, charge, release, publish, or write to providers.
- Keep map publication/manual reply boundary intact.

## Non-goals
- Full admin parse operations console.
- Manual retry button.
- Provider incident dashboard.
- Customer-facing notifications.

## Verification plan
- Build: py_compile focused backend modules and Vite frontend build.
- Unit tests: refresh reliability, Telegram copy, refresh follow-up, worker settlement, map refresh.
- Integration checks: backend lint guardrails and `git diff --check`.
- Manual checks: inspect Operator UI section and docs for read-only boundary.
