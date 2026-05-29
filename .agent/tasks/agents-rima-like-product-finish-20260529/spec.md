# Task Spec: agents-rima-like-product-finish-20260529

## Metadata
- Task ID: agents-rima-like-product-finish-20260529
- Created: 2026-05-29T07:52:50+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Rima-like agents product finish: dialog creation, run journal, Datahub source visibility, version UX, generic agent safety smokes

## Acceptance criteria
- AC1: Dialog creation lets a user describe an agent in natural language, asks clarifying questions, shows preview, and creates a blueprint.
- AC2: Run detail/journal stays human-readable and hides technical payload behind "Технический журнал".
- AC3: Datahub-lite distinguishes connected sources, available LocalOS sources, and sources used in the latest run.
- AC4: Version UX shows active version, diff/changed fields, activate/rollback, and run-specific version controls.
- AC5: Email, table, and reviews agents work end-to-end as draft/result generators without external sends or publishes.
- AC6: Safety smoke proves generic agents do not dispatch externally and require approvals.
- AC7: Production deploy and smoke checks pass, with temporary fixtures cleaned.

## Constraints
- Do not change database schema in this cycle.
- Do not change existing public API contracts except additive review fields.
- Do not modify production data except temporary smoke fixtures that are cleaned in the same run.
- External sends, publishes, payments, and destructive actions remain blocked unless they go through ActionOrchestrator and approval.

## Non-goals
- Full Rima clone.
- New full Datahub product.
- Fully autonomous external sending.
- Reworking system/persona agents.

## Verification plan
- Build: `npm --prefix frontend run build`.
- Unit tests: `python3 -m pytest -q tests/test_agent_blueprint_layer.py`.
- Integration tests: production smoke for dialog builder, email/table/reviews, generic boundaries.
- Lint: `scripts/lint_backend_baseline.sh`.
- Manual checks: authenticated browser smoke on `/dashboard/agents`.
