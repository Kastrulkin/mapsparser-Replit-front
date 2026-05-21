# Task Spec: operator-sprint12-runtime-flagged-reserve-20260521

## Metadata
- Task ID: operator-sprint12-runtime-flagged-reserve-20260521
- Created: 2026-05-21T08:13:45+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Sprint 12: connect real Operator credit reservation only behind disabled execution runtime flag

## Acceptance criteria
- AC1: Keep default runtime behavior disabled and side-effect free.
- AC2: When `EXECUTION_ENABLED=True`, call `reserve_paid_action_credits` after ready preflight.
- AC3: While adapter remains `internal_stub`, immediately rollback the reservation through release finalization.
- AC4: Preserve idempotency key flow from adapter/reservation plan into reservation creation.
- AC5: Keep Apify, parsequeue, AI generation, external writes, and credit charges disabled.
- AC6: Document Sprint 12 contract and verify targeted tests.

## Constraints
- No production data changes.
- No new migration.
- Do not enable `EXECUTION_ENABLED` by default.
- Do not call Apify or other external providers.
- Do not generate paid AI content.
- Do not charge credits.

## Non-goals
- No real paid external execution.
- No cron/job/endpoint rollout.
- No frontend changes unless required by the API contract.

## Verification plan
- Build: Python compile for Operator paid-action services and tests.
- Unit tests: Operator reservation, adapter, executor, preflight, consent, actions, attention, audit, Telegram copy tests.
- Integration tests: not required; Sprint 12 changes backend execution contract behind a disabled flag.
- Lint: `git diff --check`.
- Manual checks: inspect `EXECUTION_ENABLED=False` default and no external side effects.
