# Task Spec: operator-sprint8-execution-adapter-stub-20260521

## Metadata
- Task ID: operator-sprint8-execution-adapter-stub-20260521
- Created: 2026-05-21T06:28:01+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Sprint 8: add real Operator paid-action execution adapter contract with an internal stub implementation for estimate -> reserve -> execute -> finalize, wired into the disabled executor. The adapter must remain dry-run only: no Apify, no parsequeue jobs, no credit reservations or charges, no AI generation, no provider writes, no deploy until verification, then commit/push/deploy at the end.

## Acceptance criteria
- AC1: Backend defines a shared paid-action execution adapter contract with stages `estimate`, `reserve`, `execute`, and `finalize`.
- AC2: Backend includes an internal stub adapter for `map_reviews_refresh` that returns deterministic dry-run stage results.
- AC3: The disabled Operator executor is wired through the adapter contract and exposes adapter plan/results in the existing execute response.
- AC4: Web Operator displays adapter stage status in the blocked execute result.
- AC5: Sprint 8 does not call Apify, create parsequeue jobs, reserve or charge credits, generate AI content, write to providers, or publish externally.

## Constraints
- Keep runtime execution disabled.
- Do not add schema migrations.
- Do not write credit ledger entries or mutate production data beyond existing audit events.
- Keep adapter implementation deterministic and testable without network.

## Non-goals
- Real Apify execution.
- Credit reservation or charging.
- Parsequeue job creation.
- AI generation or draft creation.
- Provider writes or external publication.

## Verification plan
- Build: `npm run build`
- Unit tests: Operator adapter, executor, audit, preflight, consent, paid actions, attention, Telegram copy.
- Integration tests: Python compile for touched backend modules.
- Lint: `git diff --check`; scan touched implementation for forbidden `as` usage and accidental external execution calls.
- Manual checks: proof-loop validation, live deployment health checks after commit/push.
