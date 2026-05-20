# Task Spec: operator-sprint5-paid-preflight-20260520

## Metadata
- Task ID: operator-sprint5-paid-preflight-20260520
- Created: 2026-05-20T19:10:27+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Sprint 5: add Operator paid action preflight for map refresh with consent, balance, estimate, and limit checks; no Apify execution, credit charges, or external writes

## Acceptance criteria
- AC1: Add paid action preflight for `map_reviews_refresh` and future paid action keys using the Sprint 4 consent policy.
- AC2: Preflight checks action key, estimated credits, user balance, consent mode, per-action/day/month limits, and disabled policy.
- AC3: Preflight must be read-only: no Apify calls, no parsequeue insertion, no AI generation, no credit ledger writes, no external writes.
- AC4: Add authenticated Operator API endpoint for preflight after business access verification.
- AC5: Add Operator web controls to enter estimated credits and inspect the preflight result before any future execution.
- AC6: Tests and proof evidence cover allowed, blocked, missing estimate, disabled policy, insufficient balance, and no-execution status.

## Constraints
- Do not add migrations in Sprint 5 unless strictly required.
- Do not execute paid actions.
- Do not write to `credit_ledger`, `billing_ledger`, `parsequeue`, provider APIs, or external maps.
- Keep Sprint 4 consent policies as source of truth.

## Non-goals
- Actual Apify run start or polling.
- Actual provider cost ingestion.
- Credit reservation or final charge.
- Telegram inline buttons for paid action execution.

## Verification plan
- Build: backend `py_compile`, frontend production build.
- Unit tests: paid action preflight plus existing Operator paid action/consent/attention tests.
- Integration tests: route behavior through service-level tests; no live provider calls.
- Lint: `git diff --check`.
- Manual checks: inspect changed source and proof bundle.
