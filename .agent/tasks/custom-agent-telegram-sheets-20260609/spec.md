# Task Spec: custom-agent-telegram-sheets-20260609

## Metadata
- Task ID: custom-agent-telegram-sheets-20260609
- Created: 2026-06-09T14:07:13+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Clarified Goal
The real product goal is Compile AI / user-created agents as a unified process
builder. Telegram + Google Sheets is a showcase workflow, not a separate product
track.

## Scope For This Iteration
- Compile a natural-language integration workflow into an `AgentBlueprint.category=custom`.
- Represent Telegram as a trigger endpoint and Google Sheets as a capability target inside the blueprint.
- Record incoming Telegram trigger events.
- Create local Google Sheets operation requests without provider writes.
- Keep external writes behind approval, audit, limits and future approved executors.

## Acceptance Criteria
- AC1: Compiler recognizes Telegram-to-table wording as a custom integration workflow, not a communication agent.
- AC2: Compiled workflow has trigger, steps, allowlist, approval policy and safety limits for `sheets.append_row_request`.
- AC3: Capability map exposes `sheets.append_row_request` and legacy aliases.
- AC4: Sheets capability creates `agent_sheet_operation_requests` with `apply_state=not_applied` and no provider write.
- AC5: Direct orchestrator risk policy requires human approval for `sheets.append_row_request`.
- AC6: Telegram webhook dispatches matching active custom blueprints through a trigger runtime instead of legacy chat-only routing.
- AC7: New schema is represented by Alembic migrations.
- AC8: Architecture docs describe Compile AI custom workflows as blueprint/capability/runtime, not a parallel integration entity.
- AC9: Targeted tests and syntax checks pass.
- AC10: Agent run observability surfaces domain requests, approval state, apply state and plain-language waiting reasons for compiled workflows.
- AC11: Approved executor boundary moves domain requests forward only after a human gate, records audit ledger evidence, and still performs no provider writes.
- AC12: Services optimization requests include a visual before/after diff and can apply approved drafts to LocalOS service optimization fields after human approval.

## Constraints
- No direct Google Sheets API write in this iteration.
- No autonomous external write expansion.
- No new standalone `telegram sheets agent` entity.
- Existing dirty content-plan files are unrelated and must not be staged.

## Non-goals
- Full Google OAuth flow.
- Final approved executor that writes to Google Sheets.
- Frontend cockpit polish for connection setup.
- Production data mutation during local verification.

## Verification Plan
- Build: `PYTHONPATH=src python3 -m py_compile ...`
- Unit/regression: `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py`
- OpenClaw/capabilities smoke: `PYTHONPATH=src python3 -m pytest -q tests/test_capabilities_api_phase1.py`
- Frontend build: `npm --prefix frontend run build`
- Proof validation: `scripts/proof_loop.sh validate custom-agent-telegram-sheets-20260609`
