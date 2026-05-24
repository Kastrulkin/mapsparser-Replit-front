# Task Spec: operator-sprint34-apify-worker-settlement-20260524

## Metadata
- Task ID: operator-sprint34-apify-worker-settlement-20260524
- Created: 2026-05-24T08:35:05+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Sprint 34: connect Apify actual-cost settlement boundary to worker when parsequeue result has provider cost and matching Operator reservation metadata; no new paid map refresh enqueue

## Acceptance criteria
- AC1: Apify business parsing propagates provider run cost metadata to worker debug payload.
- AC2: Worker can find a reserved `map_reviews_refresh` Operator reservation by `metadata.parsequeue_id`.
- AC3: Worker calls existing actual-cost settlement only when source is Apify, cost is present, and reservation is found.
- AC4: Missing cost/reservation skips settlement and does not block parse completion.
- AC5: No paid map refresh enqueue, UI trigger, external write, or map publication is introduced.

## Constraints
- No schema migration.
- Settlement must use the existing `operatorcreditreservations.metadata` field.
- Settlement must be isolated from parser completion failures.

## Non-goals
- Creating paid refresh reservations.
- Starting Apify from Operator.
- Telegram refresh follow-up.
- Review reply generation after refresh completion.

## Verification plan
- Build: Python compile for worker, prospecting service, and settlement service.
- Unit tests: worker settlement helper, Apify metadata propagation, existing settlement service tests.
- Integration tests: none in this sprint; no live Apify or DB mutation.
- Lint: `git diff --check`.
- Manual checks: inspect worker completion path for savepoint isolation and skipped-settlement behavior.
