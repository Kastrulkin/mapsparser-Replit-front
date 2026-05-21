# Task Spec: operator-sprint10-credit-reservation-finalization-20260521

## Metadata
- Task ID: operator-sprint10-credit-reservation-finalization-20260521
- Created: 2026-05-21T07:13:10+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Sprint 10: add Operator credit reservation finalization contract for charge/release without enabling paid runtime

## Acceptance criteria
- AC1: Add a reservation finalization dry-plan for charge and release paths.
- AC2: Add a narrow mutation boundary that can charge actual credits, write `credit_ledger`, and release unused reserve.
- AC3: Add safety blockers for missing reservations, already-final reservations, actual usage over reserve, invalid mode, missing actual usage, unavailable balance, and insufficient balance at finalization.
- AC4: Keep disabled Operator runtime unchanged: no Apify, no generation, no provider writes, no user-facing execution charges.
- AC5: Document Sprint 10 contract and verify targeted tests.

## Constraints
- No production data changes.
- No new migration unless required.
- Do not connect finalization to `/api/operator/paid-actions/<action_key>/execute` yet.
- Do not call Apify or other external providers.
- Do not generate paid AI content.
- Do not publish or write to maps.

## Non-goals
- No production deploy in this task unless the user explicitly asks.
- No autonomous charge from user-facing runtime.
- No provider integration.

## Verification plan
- Build: Python compile for Operator paid-action services.
- Unit tests: Operator reservation, adapter, executor, preflight, consent, actions, attention, audit, Telegram copy tests.
- Integration tests: not required; Sprint 10 changes backend service contract and docs only.
- Lint: `git diff --check`.
- Manual checks: inspect disabled execution path still reports `credit_charged=False`.
