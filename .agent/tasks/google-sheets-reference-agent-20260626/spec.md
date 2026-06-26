# Task Spec: google-sheets-reference-agent-20260626

## Metadata
- Task ID: google-sheets-reference-agent-20260626
- Created: 2026-06-26T09:01:16+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md
- README.md
- agents/autonomous_development_brief.md

## Original task statement
Google OAuth binding, live Google Sheets custom-agent proof, runtime observability, and reference agent smoke.

## Acceptance criteria
- AC1: Google OAuth requests Google Sheets scope for the reference agent runtime.
- AC2: Saving a Google Sheets agent integration automatically binds an active Google account auth_ref when available.
- AC3: Agent integration preflight treats Google Sheets as ready only when sheet config and auth_ref are present.
- AC4: A reference smoke exists for live Google Sheets read proof without Telegram or WhatsApp.

## Constraints
- No production data mutation without explicit approval.
- No Telegram or WhatsApp delivery in the reference smoke.
- External writes and sends remain behind approval.
- No schema change for this phase.

## Non-goals
- Do not implement Telegram/WhatsApp delivery.
- Do not fake live Google provider reads.
- Do not build the full UI redesign in this phase.

## Verification plan
- Build: backend py_compile for changed modules and smoke script.
- Unit tests: focused Google Sheets agent tests and full tests/test_agent_blueprint_layer.py.
- Integration tests: production smoke script after deploy; expected BLOCKED until Google is reconnected with Sheets scope.
- Lint: git diff --check.
- Manual checks: production app health and deployed file grep.
