# Task Spec: approval-boundaries-audit-20260524

## Metadata
- Task ID: approval-boundaries-audit-20260524
- Created: 2026-05-24T08:54:50+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
P1/P2 approval boundaries audit for Agent Blueprint, Operator, supervised outreach, external dispatch, manual publication, billing/credits

## Acceptance criteria
- AC1: Supervised outreach send capability must require a drafts approval, not any earlier approval gate.
- AC2: Dangerous capabilities (`send`, `publish`, `payment`, `delete`, `destructive`, `mass`) must require human review through `ActionOrchestrator` policy by default.
- AC3: Outreach dispatcher must be explicit opt-in in worker runtime and compose, with default disabled.
- AC4: Agent Blueprint runtime may queue approved outreach batches but must not dispatch externally by itself.
- AC5: Backend lint guardrails and targeted tests must pass.
- AC6: Production deploy must be verified with app/worker health, dispatcher disabled in worker env, and no dispatch activity after restart.

## Constraints
- Do not change existing AIAgent persona/chat endpoints.
- Do not perform production data writes beyond deploy/restart verification.
- Do not enable external outreach dispatch in production during this task.
- Keep side effects routed through ActionOrchestrator and approval boundaries.

## Non-goals
- Full supervised outreach sourcing/drafting integration.
- Browser/UI changes.
- Enabling real external provider sends.
- Refactoring unrelated Operator Sprint 35 changes.

## Verification plan
- Build/import: local py_compile plus live import check in app container.
- Unit tests: targeted Agent Blueprint and Operator boundary tests.
- Integration tests: production docker compose health, worker env, policy check.
- Lint: `scripts/lint_backend_baseline.sh`.
- Manual checks: inspect worker logs for absence of `OUTREACH_DISPATCH` activity.
