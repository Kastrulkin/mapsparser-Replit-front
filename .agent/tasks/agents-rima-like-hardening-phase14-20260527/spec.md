# Task Spec: agents-rima-like-hardening-phase14-20260527

## Metadata
- Task ID: agents-rima-like-hardening-phase14-20260527
- Created: 2026-05-27T17:36:24+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance Sources
- AGENTS.md
- README.md

## Original Task Statement
Rima-like agents plan 1-4: dialog builder proof, Datahub-lite polish, version loop polish, and generic safety smoke

## Acceptance Criteria
- AC1: Dialog builder can create a document agent from natural language, asks clarifying questions when needed, shows preview, creates a blueprint, and persists builder/setup metadata.
- AC2: Datahub-lite exposes connected agent sources in the catalog, including text and uploaded file sources, with ready state and human-readable preview.
- AC3: Version loop works end to end: run review is human-readable, feedback creates a new version, version diff is available, rollback works, and the feedback version can be activated.
- AC4: Generic agents respect safety boundaries: documents/email/tables/reviews stop for final approval, do not execute capability steps, do not dispatch externally, and do not start dispatcher.
- AC5: Production fixture data is cleaned after smoke, production service remains healthy, and proof-loop evidence is complete.

## Constraints
- Runtime is Docker Compose + PostgreSQL.
- SQLite is legacy-only and not a runtime target.
- Production data changes are limited to temporary smoke fixtures and must be cleaned.
- External send/publish/payment/destructive actions must remain behind ActionOrchestrator and approval boundaries.
- Server commands must start from `/opt/seo-app`.

## Non-goals
- No new database migration for this phase.
- No fully autonomous external sending or publishing.
- No broad UI redesign beyond proofing the existing Rima-like flow.

## Verification Plan
- Unit tests: targeted agent builder/Datahub tests.
- Lint: backend baseline guardrails.
- Deploy: sync backend service change, restart app/worker, verify live source and health.
- Production smoke: authenticated dialog builder + Datahub + version loop.
- Production safety smoke: generic boundaries for documents/email/tables/reviews.
- Cleanup: delete production smoke user/business/agent data and verify zero remaining rows.
