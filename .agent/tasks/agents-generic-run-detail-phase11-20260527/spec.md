# Task Spec: agents-generic-run-detail-phase11-20260527

## Metadata
- Task ID: agents-generic-run-detail-phase11-20260527
- Created: 2026-05-27T12:36:13+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Rima-like generic agents run detail: document/email/table/reviews show human journal with input, understanding, result, manual control; technical runtime hidden by default

## Acceptance criteria
- AC1: Generic document/email/table/reviews runs show a human progress overview: input, understanding, result, manual control.
- AC2: Technical runtime columns and JSON are not the primary view; technical details stay behind disclosure blocks.
- AC3: Result payloads use readable labels for document/email/table/reviews outputs.
- AC4: Targeted tests, frontend build, and backend lint baseline pass.
- AC5: Frontend is deployed to production and authenticated production UI smoke verifies a document agent run detail.
- AC6: Production smoke fixture is cleaned up.

## Constraints
- Do not change backend contracts.
- Do not change action/approval boundaries.
- Do not start external dispatchers or provider writes.

## Non-goals
- No new database schema.
- No new runner behavior.
- No redesign of the whole Agents page.

## Verification plan
- Build: `npm --prefix frontend run build`
- Unit tests: `python3 -m pytest -q tests/test_agent_blueprint_layer.py`
- Integration tests: production document-agent fixture smoke via existing Agent Blueprint APIs
- Lint: `scripts/lint_backend_baseline.sh`
- Manual checks: authenticated browser smoke on `https://localos.pro/dashboard/agents`
