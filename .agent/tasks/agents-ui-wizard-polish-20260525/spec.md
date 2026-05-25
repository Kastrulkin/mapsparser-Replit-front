# Task Spec: agents-ui-wizard-polish-20260525

## Metadata
- Task ID: agents-ui-wizard-polish-20260525
- Created: 2026-05-25T09:30:14+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Original task statement
P1 UI wizard smoke + version loop polish for `/dashboard/agents`; improve document agent errors and safety smoke guardrails; commit, push, deploy between steps.

## Acceptance criteria
- AC1: `/dashboard/agents` shows clearer version state: active version in cards/details, feedback impact, old run preservation note.
- AC2: Document/file upload failures return useful user-facing messages for unsupported, empty, too-large, and extraction-failed files.
- AC3: Generic agents have a self-contained safety smoke proving document/email/table/review agents do not dispatch externally and stop for approval.
- AC4: Production deploy is live after each committed step.
- AC5: Authenticated production UI smoke verifies wizard-created document agent: create through wizard, run from card, review/result without JSON/IDs, technical journal available, feedback creates new active version.

## Constraints
- Do not modify production data except explicit smoke fixtures; clean fixtures after verification.
- Keep external sends, publishing, payments and destructive actions behind ActionOrchestrator and approvals.
- Do not mix pre-existing untracked proof bundles into implementation commits.

## Non-goals
- Full Rima-style universal builder.
- External sending/publishing for generic agents.
- Database schema migration for version draft status.

## Verification plan
- Build: `npm run build`.
- Unit tests: `python3 -m pytest -q tests/test_agent_blueprint_layer.py`.
- Integration tests: production `scripts/smoke_agent_blueprint_generic_boundaries.py`.
- Lint: `scripts/lint_backend_baseline.sh`.
- Manual checks: authenticated browser smoke on `https://localos.pro/dashboard/agents`.
