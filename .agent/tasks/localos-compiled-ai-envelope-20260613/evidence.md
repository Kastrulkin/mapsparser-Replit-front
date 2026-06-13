# Evidence Bundle: localos-compiled-ai-envelope-20260613

## Summary
- Overall status: PASS for current phase scope.
- Last updated: 2026-06-13T16:05:00+03:00
- Current phase: Phase 8, finance apply UI after approval.

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `finance.transaction.create` capability execution now creates the approved proposal/request without writing LocalOS Finance entries automatically.
  - `tests/test_agent_blueprint_layer.py::test_runner_passes_compiled_step_rows_to_next_capability_without_runtime_ai`

### AC2
- Status: PASS
- Proof:
  - Agent run observability exposes a finance transaction request after approval with `apply_state = apply_ready`, `can_apply = true`, and an apply endpoint.
  - `tests/test_agent_blueprint_layer.py::test_runner_applies_finance_requests_only_after_explicit_apply`

### AC3
- Status: PASS
- Proof:
  - `/dashboard/agents` advanced run detail renders “Применить в финансы” only for approved, apply-ready finance requests.
  - Frontend production build passed.

### AC4
- Status: PASS
- Proof:
  - Explicit apply writes LocalOS Finance entries, records `agent_action_ledger`, updates step output, and returns the refreshed run.
  - `tests/test_agent_blueprint_layer.py::test_runner_applies_finance_requests_only_after_explicit_apply`

### AC5
- Status: PASS
- Proof:
  - Full agent blueprint suite passed: 153 tests.
  - Frontend production build passed.

### AC6
- Status: PASS
- Proof:
  - No schema migration was added.
  - `git diff --check` passed.

## Commands run
- `venv/bin/python -m pytest tests/test_agent_blueprint_layer.py::test_agent_blueprint_routes_are_owned_by_blueprint tests/test_agent_blueprint_layer.py::test_runner_passes_compiled_step_rows_to_next_capability_without_runtime_ai tests/test_agent_blueprint_layer.py::test_runner_applies_finance_requests_only_after_explicit_apply tests/test_agent_blueprint_layer.py::test_approved_domain_executor_applies_finance_transactions_after_human_gate -q`
- `venv/bin/python -m pytest tests/test_agent_blueprint_layer.py -q`
- `npm run build` from `frontend/`
- `git diff --check`

## Raw artifacts
- `.agent/tasks/localos-compiled-ai-envelope-20260613/raw/phase8-finance-apply-focused-tests.txt`
- `.agent/tasks/localos-compiled-ai-envelope-20260613/raw/phase8-agent-blueprint-tests.txt`
- `.agent/tasks/localos-compiled-ai-envelope-20260613/raw/phase8-frontend-build.txt`
- `.agent/tasks/localos-compiled-ai-envelope-20260613/raw/phase8-diff-check.txt`

## Known gaps
- Full objective remains active: more production provider write handlers, live visual QA on production, and broader billing ledger coverage for compile/preview/run remain later phases.
