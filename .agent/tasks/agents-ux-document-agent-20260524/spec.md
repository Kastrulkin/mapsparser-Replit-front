# Task Spec: agents-ux-document-agent-20260524

## Metadata
- Task ID: agents-ux-document-agent-20260524
- Created: 2026-05-24T19:26:19+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Довести /dashboard/agents до понятного UX без технического шума и сделать первый полезный document agent end-to-end: wizard, данные агента, run review, feedback/version draft, safety boundaries.

## Acceptance criteria
- AC1: `/dashboard/agents` has a product-level agent builder with explicit scenarios, wizard fields, data source inputs, and no primary-screen JSON/ID workflow noise.
- AC2: Document agent creation can explicitly select `documents`, saves setup/sources during creation, runs through extraction/processing/output artifacts, and stops for `final_output` approval before final result.
- AC3: Run review shows human-readable setup, sources, extracted context, result, and keeps raw payload only inside `Технический журнал`.
- AC4: Safety boundaries remain unchanged: generic agents have empty capability allowlist, do not dispatch externally, and risky delivery stays approval/manual-only.

## Constraints
- Do not change existing booking/marketing/persona endpoints.
- Do not introduce a new runtime DB table or production data migration.
- Do not enable external send/publish/payment/destructive actions for generic agents.
- Do not mix unrelated Operator/Telegram changes into this task.

## Non-goals
- Full Rima clone or full Datahub product.
- Real binary PDF/DOCX/XLSX parsing beyond the existing text/file metadata path.
- Production data smoke that creates records on the live server without explicit approval.

## Verification plan
- Build: `npm --prefix frontend run build`
- Unit tests: `PYTHONPATH=src:. python3 -m pytest -q tests/test_agent_blueprint_layer.py`
- Integration tests: targeted Agent Blueprint + Operator boundary regression tests.
- Lint: `scripts/lint_backend_baseline.sh`
- Manual checks: Browser opened `/dashboard/agents`; session was not authenticated, so visual UI smoke is recorded as a remaining gap rather than faked.
