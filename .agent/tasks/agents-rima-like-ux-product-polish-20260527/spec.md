# Task Spec: agents-rima-like-ux-product-polish-20260527

## Metadata
- Task ID: agents-rima-like-ux-product-polish-20260527
- Created: 2026-05-27
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance Sources
- AGENTS.md
- README.md

## Original Task Statement
Rima-like agents UX/product polish:
- wizard creation should be understandable without explanation;
- run detail should show a product journal before technical details;
- Datahub-lite should distinguish connected agent sources from available LocalOS sources and show understandable file states/errors;
- version UX should show active version, changes, activate/rollback/run controls;
- email agent should be proven end-to-end without external sending.

## Acceptance Criteria
- AC1: `/dashboard/agents` creation flow has one primary `Создать агента` CTA, dialog preview before creation, clear connected-data summary, and a post-create selected-agent confirmation.
- AC2: Run detail prioritizes human-readable journal/result and keeps runtime internals under a collapsed technical journal.
- AC3: Datahub-lite UI separates sources connected to the agent from LocalOS sources available to connect, and displays readable source type/state/error/size.
- AC4: Version UX shows active version, readable changed fields, and controls to run, activate, or rollback versions.
- AC5: Email agent end-to-end smoke produces a draft result, requires approval, and does not send externally.
- AC6: Production deploy, authenticated UI smoke, cleanup, health, build, tests, and lint all pass.

## Constraints
- No DB schema migration in this cycle.
- Do not change backend contracts unless needed for UX proof.
- Production data mutations are limited to temporary smoke fixtures and must be cleaned.
- External sends/publishes/payments/destructive actions remain disallowed for generic agents unless routed through existing approval/action boundaries.

## Verification Plan
- Frontend build.
- Targeted pytest for agent UI guardrails, version diff, and review journal.
- Backend lint baseline.
- Deploy frontend dist to production.
- Production UI smoke with temporary authenticated fixture.
- Production email agent API smoke.
- Production fixture cleanup and health check.
