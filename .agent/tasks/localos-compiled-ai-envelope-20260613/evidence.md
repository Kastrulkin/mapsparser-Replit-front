# Evidence Bundle: localos-compiled-ai-envelope-20260613

## Summary
- Overall status: PASS for current phase scope.
- Last updated: 2026-06-13T15:11:21+03:00
- Current phase: Phase 7, real connector UX, preflight clarity, and billing breakdown.

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - Activation/preflight connection plans now include existing/attached integrations, `why_blocked`, and `setup_cta`.
  - `tests/test_agent_blueprint_layer.py::test_activation_connection_blocker_keeps_binding_route_context`

### AC2
- Status: PASS
- Proof:
  - `tests/test_agent_blueprint_layer.py::test_agent_connection_plan_turns_bindings_into_user_next_actions` asserts an existing Google Sheets connection becomes `choose_existing`.

### AC3
- Status: PASS
- Proof:
  - `/dashboard/agents` renders missing preflight reason text from `why_blocked` and CTA labels from `setup_cta`.
  - Frontend production build passed.

### AC4
- Status: PASS
- Proof:
  - Agent metrics now expose `billing_breakdown` and `cost_tokens.breakdown` with categories for creation, preview, production run, external actions, and operator chat.
  - `tests/test_agent_blueprint_layer.py::test_agent_metrics_summary_reports_compiled_runtime_health`

### AC5
- Status: PASS
- Proof:
  - Full agent blueprint suite passed: 152 tests.
  - Frontend production build passed.

### AC6
- Status: PASS
- Proof:
  - No schema migration was added.
  - `git diff --check` passed.

## Commands run
- `venv/bin/python -m pytest tests/test_agent_blueprint_layer.py::test_agent_preview_run_and_activation_endpoints_enforce_safe_gate tests/test_agent_blueprint_layer.py::test_activation_connection_blocker_keeps_binding_route_context tests/test_agent_blueprint_layer.py::test_agent_metrics_summary_reports_compiled_runtime_health tests/test_agent_blueprint_layer.py::test_agent_connection_plan_turns_bindings_into_user_next_actions -q`
- `venv/bin/python -m pytest tests/test_agent_blueprint_layer.py -q`
- `npm run build` from `frontend/`
- `git diff --check`

## Raw artifacts
- `.agent/tasks/localos-compiled-ai-envelope-20260613/raw/phase7-focused-tests.txt`
- `.agent/tasks/localos-compiled-ai-envelope-20260613/raw/phase7-agent-blueprint-tests.txt`
- `.agent/tasks/localos-compiled-ai-envelope-20260613/raw/phase7-frontend-build.txt`
- `.agent/tasks/localos-compiled-ai-envelope-20260613/raw/phase7-diff-check.txt`

## Known gaps
- Full objective remains active: deeper finance apply approval UI, more production provider write handlers, and live visual QA on production remain later phases.
