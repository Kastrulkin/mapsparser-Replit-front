# Task Spec: operator-sprint4-consent-policy-20260520

## Metadata
- Task ID: operator-sprint4-consent-policy-20260520
- Created: 2026-05-20T13:24:23+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Sprint 4: add persisted Operator paid-action consent policy API and web controls without executing paid actions, charging credits, or calling external providers

## Acceptance criteria
- AC1: Add a persisted business-scoped Operator consent policy table for paid action keys without touching credit ledger or execution paths.
- AC2: Add a backend service that validates consent modes, action keys, and credit limits. `auto_with_limits` must require explicit positive limits.
- AC3: Add authenticated Operator API endpoints to read and update consent policies after verifying business access.
- AC4: Include the current consent policy in paid action offers returned by the attention brief.
- AC5: Add web Operator controls to choose `ask_each_time`, `auto_with_limits`, or `disabled` and save limits for a paid action offer.
- AC6: Tests and proof evidence must show no paid provider calls, credit charges, AI generation, or external publication were added.

## Constraints
- Runtime remains Docker + PostgreSQL.
- Schema changes must be Alembic-only and idempotent where possible.
- Do not execute Apify, model generation, credit ledger writes, provider writes, or publication.
- Preserve Sprint 1-3 cached attention brief behavior.
- Human/manual publication boundary remains unchanged.

## Non-goals
- Actual paid refresh execution.
- Actual Apify cost ingestion.
- Actual token/credit charging.
- Telegram inline consent buttons.
- Autonomous external publishing.

## Verification plan
- Build: backend `py_compile`, frontend production build.
- Unit tests: consent policy service, attention brief, paid action offers, Telegram copy.
- Integration tests: API route tests if lightweight fixtures exist; otherwise focused service tests.
- Lint: `git diff --check`.
- Manual checks: inspect proof bundle and affected source.
