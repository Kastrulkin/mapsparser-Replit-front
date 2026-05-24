# Task Spec: supervised-outreach-queue-visibility-20260524

## Metadata
- Task ID: supervised-outreach-queue-visibility-20260524
- Created: 2026-05-24T10:33:08+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
P1 supervised outreach product polish: make Agent Blueprint queued-but-not-dispatched state explicit in capability output, outcomes artifact, and smoke checks

## Acceptance criteria
- AC1: `outreach.send_batch` capability result exposes explicit `dispatch_state=queued_not_dispatched` when it only queues LocalOS handoff rows.
- AC2: Agent Blueprint outreach outcomes artifact exposes `queued_count`, `dispatch_state`, and `external_dispatch_performed=false`.
- AC3: Dashboard Agent Blueprint UI recognizes the explicit dispatch state and shows queued-but-not-dispatched copy with operator note.
- AC4: Live supervised outreach smoke validates shortlist approval, draft approval, send batch queueing, dispatch state, and no dispatcher start.
- AC5: Backend tests, py_compile, lint baseline, frontend build, backend deploy, frontend deploy, and server health checks pass.

## Constraints
- Do not start or enable the external outreach dispatcher.
- Do not change existing AIAgents runtime semantics.
- Do not introduce a second lead table; use the transitional prospecting leads path.
- Do not touch unrelated Operator Sprint 37 working tree changes.

## Non-goals
- Universal agent builder.
- Real external message delivery.
- Production data mutation outside smoke-owned fixture rows.

## Verification plan
- Build: py_compile changed backend modules; `npm run build`.
- Unit tests: targeted Agent Blueprint and Operator boundary tests.
- Integration tests: live `scripts/smoke_agent_blueprint_outreach_api.py` against server app container.
- Lint: `scripts/lint_backend_baseline.sh`.
- Manual checks: server compose status, app/worker logs, root health, dispatcher env, frontend bundle reference.
