# Task Spec: operator-sprint29-services-optimize-20260524

## Metadata
- Task ID: operator-sprint29-services-optimize-20260524
- Created: 2026-05-24T08:16:42+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
P1 Operator Sprint 29 services optimize: inspect existing uncommitted Operator changes, verify tests, finish missing pieces, keep external publication manual/no provider writes, add guardrails, commit push deploy if valid

## Acceptance criteria
- AC1: Operator Sprint 29 `services_optimize` is confirmed as valid current work, not discarded.
- AC2: Focused Operator tests pass for service optimization, bulk review replies, and paid action adapter.
- AC3: Operator bulk review smoke is self-contained and no longer imports test fixtures.
- AC4: Baseline guardrails pass and preserve manual/no-provider-write boundaries.

## Constraints
- Do not perform external provider writes.
- Do not mutate production data.
- Keep service application manual/confirmation-gated.

## Non-goals
- Full Operator decomposition.
- Autonomous service changes applied to third-party systems.
- Full browser QA for Operator Inbox.

## Verification plan
- Build: `python3 -m py_compile src/api/operator_api.py src/services/operator_services_optimization.py scripts/smoke_operator_bulk_review_replies.py`
- Unit tests: `PYTHONPATH=src python3 -m pytest -q tests/test_operator_services_optimization.py tests/test_operator_review_reply_bulk.py tests/test_operator_paid_action_adapter.py`
- Integration tests: `scripts/smoke_operator_bulk_review_replies.py`
- Lint: `scripts/lint_backend_baseline.sh`
- Manual checks: inspect git status and confirm no uncommitted Sprint 29 code remains.
