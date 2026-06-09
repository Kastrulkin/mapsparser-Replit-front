# Evidence Bundle: agents-runtime-observability-20260609

## Summary
- Overall status: PASS
- Last updated: 2026-06-09T16:05:00+03:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `AgentBlueprintRunner.load_run(..., user_data)` now returns `run.observability`.
  - `run.observability` includes run history, step history, artifacts, approvals, action ledger, delivery status, cost/tokens, errors, recovery actions, and support export metadata.
  - Added `GET /api/agent-runs/<run_id>/support-export` with JSON and markdown support.
  - Agent run detail UI embeds observability inside `Технический журнал` with action ledger, delivery, cost/tokens, errors, recovery and support export.
  - LocalOS architecture and OpenClaw contract docs now define agent run detail as the primary observability surface.
  - `PYTHONPATH=src python3 -m py_compile src/api/agent_blueprints_api.py src/services/agent_blueprint_runner.py` passed.
  - `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py` passed: 42 tests.
  - `npm run build` passed.
- Gaps:
  - Production deploy verification is recorded after deployment.

## Commands run
- `PYTHONPATH=src python3 -m py_compile src/api/agent_blueprints_api.py src/services/agent_blueprint_runner.py`
- `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py`
- `npm run build`

## Raw artifacts
- .agent/tasks/agents-runtime-observability-20260609/raw/build.txt
- .agent/tasks/agents-runtime-observability-20260609/raw/test-unit.txt
- .agent/tasks/agents-runtime-observability-20260609/raw/test-integration.txt
- .agent/tasks/agents-runtime-observability-20260609/raw/lint.txt
- .agent/tasks/agents-runtime-observability-20260609/raw/screenshot-1.png

## Known gaps
- None for local DoD before deployment.
