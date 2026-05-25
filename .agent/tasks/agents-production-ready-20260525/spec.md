# Task Spec: agents-production-ready-20260525

## Metadata
- Task ID: agents-production-ready-20260525
- Created: 2026-05-25T07:59:13+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Agents production readiness: authenticated UI smoke, document agent E2E, backend file ingestion, review/version loop, generic agent safety boundary smoke

## Acceptance criteria
- AC1: Document agent supports backend ingestion for TXT/PDF/DOCX/CSV/XLSX with size/type validation and clear errors.
- AC2: Document agent run produces useful review output: extracted context, summary/facts/fields/risks/questions, final result, and feedback-created version draft.
- AC3: Generic document agents do not perform external dispatch and preserve approval/manual boundaries.
- AC4: System agent settings persist through normal production paid access checks.
- AC5: Production deployment is live and authenticated `/dashboard/agents` UI smoke passes without JSON/ID noise on the main review surface.

## Constraints
- Do not modify production data except explicit smoke fixtures; clean test fixture after verification.
- Keep external sends/publish/payment/destructive actions behind existing ActionOrchestrator and approval policies.
- Do not replace existing AIAgents or booking/marketing behavior.

## Non-goals
- Full Rima-style universal agent builder.
- External provider dispatch for generic agents.
- Full PDF/OCR quality guarantees beyond text extraction.

## Verification plan
- Build: `npm run build`.
- Unit tests: `python3 -m pytest -q tests/test_agent_blueprint_layer.py`.
- Integration tests: `scripts/smoke_agent_blueprint_document_api.py` locally through deployed app container.
- Lint: `scripts/lint_backend_baseline.sh`.
- Manual checks: authenticated browser smoke on `https://localos.pro/dashboard/agents`.
