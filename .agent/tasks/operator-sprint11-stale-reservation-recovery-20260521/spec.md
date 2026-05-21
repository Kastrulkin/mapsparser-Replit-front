# Task Spec: operator-sprint11-stale-reservation-recovery-20260521

## Metadata
- Task ID: operator-sprint11-stale-reservation-recovery-20260521
- Created: 2026-05-21T07:52:14+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Sprint 11: add Operator stale credit reservation recovery contract without enabling paid runtime

## Acceptance criteria
- AC1: Add a read-only stale reservation recovery plan for outstanding `reserved` rows.
- AC2: Add a narrow mutation boundary that releases stale outstanding reservations without charging credits or writing `credit_ledger`.
- AC3: Keep recovery scoped and bounded by stale window, limit, optional business, and optional user filters.
- AC4: Keep Operator runtime unchanged: no Apify, no paid generation, no provider writes, no user-facing charges, no cron/endpoint hook.
- AC5: Document Sprint 11 contract and verify targeted tests.

## Constraints
- No production data changes.
- No new migration unless required.
- Do not connect recovery to a cron job, endpoint, or `/execute`.
- Do not call Apify or external providers.
- Do not write `credit_ledger` during recovery.

## Non-goals
- No production deploy in this task unless the user explicitly asks.
- No autonomous stale-reservation job.
- No paid action execution.

## Verification plan
- Build: Python compile for Operator paid-action services.
- Unit tests: Operator reservation, adapter, executor, preflight, consent, actions, attention, audit, Telegram copy tests.
- Integration tests: not required; Sprint 11 changes backend service contract and docs only.
- Lint: `git diff --check`.
- Manual checks: inspect recovery side effects keep `credit_charged=False`.
