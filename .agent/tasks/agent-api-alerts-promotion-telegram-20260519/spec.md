# Task Spec: agent-api-alerts-promotion-telegram-20260519

## Metadata
- Task ID: agent-api-alerts-promotion-telegram-20260519
- Created: 2026-05-19T09:00:02+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Agent API: Telegram alerts, sandbox to live promotion flow, and Telegram bot-to-bot security routing plan

## Acceptance criteria
- AC1: Agent API sends Telegram alerts to superadmins for denied access, high-risk approval requests, key rotation/client changes, and promotion decisions.
- AC2: Sandbox-to-live promotion flow exists as explicit request and decision endpoints with ledger entries.
- AC3: Agent API admin UI supports promotion approve/reject with reviewer note.
- AC4: Telegram bot-to-bot feature has a security routing foundation and documented implementation plan.
- AC5: Machine-readable policy/docs mention promotion and Telegram transport boundaries.
- AC6: Regression tests and builds pass.

## Constraints
- Do not trust Telegram messages directly; route trust through agent_clients, scopes, ledger, and approval.
- Do not add a schema migration unless required.
- Keep dangerous actions behind human approval.
- Do not stage or alter unrelated pre-existing docs/articles changes.

## Non-goals
- Enabling live Telegram bot-to-bot automation in production.
- Full rate-limit middleware.
- Public MCP tool server.

## Verification plan
- Build: `cd frontend && npm run build`
- Unit tests: `./venv/bin/python -m pytest -q tests/test_agent_api_security.py`
- Syntax: `./venv/bin/python -m py_compile ...`
- Static: check new files for forbidden `as` usage.
- Manual: review docs, admin UI, and endpoint list.
