# Task Spec: operator-sprint7-disabled-executor-20260520

## Metadata
- Task ID: operator-sprint7-disabled-executor-20260520
- Created: 2026-05-20T20:01:49+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Sprint 7: add a disabled Operator paid-action execution endpoint and service that reuses preflight, records an audit event, and always blocks execution while runtime is disabled. Do not call Apify, create parsequeue jobs, reserve or charge credits, generate content, or publish externally.

## Acceptance criteria
- AC1: Backend has a shared disabled paid-action execution service that reuses preflight.
- AC2: API exposes authenticated, business-scoped `POST /api/operator/paid-actions/<action_key>/execute`.
- AC3: Execute endpoint records an Operator audit event when execution is blocked.
- AC4: Web Operator can call execute and display the structured blocked result.
- AC5: Sprint 7 does not call Apify, create parsequeue jobs, reserve or charge credits, generate AI content, write to providers, or publish externally.

## Constraints
- Keep runtime execution disabled by code.
- Reuse existing consent, preflight, auth, business scoping, and audit patterns.
- Do not introduce schema migrations.
- Do not imply that external map publication is supported.

## Non-goals
- Real Apify execution.
- Credit reservations or charges.
- AI generation.
- Parsequeue jobs.
- Provider writes or external publication.

## Verification plan
- Build: `npm run build`
- Unit tests: Operator executor, audit, preflight, consent, paid actions, attention, Telegram copy.
- Integration tests: Python compile for touched backend modules.
- Lint: `git diff --check`; scan touched implementation for forbidden `as` usage.
- Manual checks: proof-loop validation and code review of no paid/external execution paths.
