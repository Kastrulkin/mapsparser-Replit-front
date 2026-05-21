# Task Spec: operator-sprint9-credit-reservation-ledger-20260521

## Metadata
- Task ID: operator-sprint9-credit-reservation-ledger-20260521
- Created: 2026-05-21T06:44:15+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Sprint 9: add Operator credit reservation ledger for paid actions without enabling external execution

## Acceptance criteria
- AC1: Add an idempotent Alembic migration for Operator credit reservations.
- AC2: Add a typed backend service that can calculate whether credits can be reserved after active reservations are considered.
- AC3: Connect the reservation plan to the disabled Operator paid-action execution response and adapter `reserve` stage without enabling paid runtime side effects.
- AC4: Surface reservation plan status in the Operator UI without claiming that credits were reserved or charged.
- AC5: Document the Sprint 9 boundary and verify unit/build checks.

## Constraints
- Do not call Apify or other external providers.
- Do not generate paid AI content.
- Do not publish or write to external maps.
- Do not reserve, charge, or release credits from the disabled execution runtime.
- Do not apply production schema changes without explicit approval and DB backup.

## Non-goals
- No production deploy in this task unless the user explicitly requests it.
- No direct provider write support.
- No autonomous publication.
- No real paid action execution.

## Verification plan
- Build: `npm run build` in `frontend`.
- Unit tests: Operator paid action, preflight, audit, attention, and reservation tests.
- Integration tests: not required for local schema-only Sprint 9; migration is not applied to production.
- Lint: `git diff --check` and Python compile checks.
- Manual checks: inspect API contract and UI rendering for `reservation_plan`.
