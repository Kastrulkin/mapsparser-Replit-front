# Evidence Bundle: localos-compiled-ai-envelope-20260613

## Summary
- Overall status: PASS for current phase scope.
- Last updated: 2026-06-13T17:32:41+03:00
- Current phase: Phase 11, billing ledger end-to-end + simplified Agents cockpit.

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - Agent creation cost preview now exposes `localos_agent_billing_estimate_v1`.
  - Estimate rows cover compile, preview run, production run, external action, and operator chat.
  - `tests/test_agent_blueprint_layer.py::test_agent_creation_cost_preview_exposes_unified_ledger_estimate_items`

### AC2
- Status: PASS
- Proof:
  - Agent metrics now expose `localos_agent_unified_billing_ledger_v1`.
  - The ledger combines estimate and fact rows for compile, preview, run, external action, and operator chat.
  - Agent creation fact reads both `credits_charged` and legacy/current `actual_credits`.
  - `tests/test_agent_blueprint_layer.py::test_agent_metrics_summary_reports_compiled_runtime_health`

### AC3
- Status: PASS
- Proof:
  - Run observability now exposes `localos_agent_run_unified_billing_ledger_v1`.
  - Action boundary billing remains separate and does not double-count run totals.
  - `tests/test_agent_blueprint_layer.py::test_runner_load_run_includes_observability_envelope_for_openclaw_actions`

### AC4
- Status: PASS
- Proof:
  - `/dashboard/agents` top cockpit now answers four product questions: what the agent does, whether it is ready, what is missing, and the last run.
  - Technical readiness rows were removed from the first screen.
  - `tests/test_agent_blueprint_layer.py::test_agent_blueprint_api_guards_version_blueprint_mismatch`

### AC5
- Status: PASS
- Proof:
  - Agents UI billing panel now displays `Единый billing ledger`, `Оценка до запуска`, and `Факт после запуска`.
  - Run detail billing also renders unified ledger items when present.
  - Frontend production build passed.

### AC6
- Status: PASS
- Proof:
  - Full agent blueprint suite passed: 156 tests.
  - Frontend production build passed.
  - `git diff --check` passed.
  - No schema migration was added.

## Commands run
- `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py`
- `cd frontend && npm run build`
- `git diff --check`

## Raw artifacts
- `.agent/tasks/localos-compiled-ai-envelope-20260613/raw/phase11-billing-cockpit-agent-blueprint-tests.txt`
- `.agent/tasks/localos-compiled-ai-envelope-20260613/raw/phase11-billing-cockpit-frontend-build.txt`
- `.agent/tasks/localos-compiled-ai-envelope-20260613/raw/phase11-billing-cockpit-diff-check.txt`

## Known gaps
- Full objective remains active: live OpenClaw/GigaChat planning should keep replacing deterministic compiler heuristics where it can do better.
- More provider-specific production handlers can still be deepened: real Telegram post handoff, review publish provider handoff, and richer external provider billing facts.
