# Evidence Bundle: agent-blueprints-p0-p1

## Summary
- Overall status: PASS
- Last updated: 2026-05-23T12:06:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - Added `src/services/agent_blueprint_orchestrator.py`.
  - `build_agent_blueprint_orchestrator()` registers `outreach.send_batch` with `ActionOrchestrator`.
  - `src/api/agent_blueprints_api.py` now creates runners with the registered orchestrator.
- Gaps:
  - None.

### AC2
- Status: PASS
- Proof:
  - Added `src/services/outreach_send_capability.py`.
  - Handler filters drafts by `l.business_id = %s`, approved draft status, unqueued drafts, contact availability, and the `10/day` cap.
  - Handler creates approved queue batches but does not call the dispatcher; result includes `external_dispatch_performed: false`.
  - Unit test: `test_outreach_send_batch_handler_queues_approved_drafts_without_external_dispatch`.
- Gaps:
  - Live authenticated run smoke still requires a real user session/token and real approved drafts.

### AC3
- Status: PASS
- Proof:
  - `src/api/agent_blueprints_api.py` rejects mismatched run version IDs with `VERSION_BLUEPRINT_MISMATCH`.
  - Regression marker test: `test_agent_blueprint_api_guards_version_blueprint_mismatch`.
- Gaps:
  - None.

### AC4
- Status: PASS
- Proof:
  - `scripts/lint_backend_baseline.sh` compiles the new modules.
  - Added guardrail check for orchestrator registration, blocked capability handling, no direct dispatch marker, and business-scoped SQL.
  - Existing route ownership and PostgreSQL placeholder guardrails passed.
- Gaps:
  - None.

## Commands run
- `python3 -m py_compile src/api/agent_blueprints_api.py src/services/agent_blueprint_orchestrator.py src/services/agent_blueprint_runner.py src/services/outreach_send_capability.py tests/test_agent_blueprint_layer.py`
- `PYTHONPATH=src python3 - <<'PY' ... build_agent_blueprint_orchestrator smoke ... PY`
- `scripts/lint_backend_baseline.sh`
- `python3 -m pytest tests/test_agent_blueprint_layer.py`

## Raw artifacts
- .agent/tasks/agent-blueprints-p0-p1/raw/build.txt
- .agent/tasks/agent-blueprints-p0-p1/raw/test-unit.txt
- .agent/tasks/agent-blueprints-p0-p1/raw/test-integration.txt
- .agent/tasks/agent-blueprints-p0-p1/raw/lint.txt
- .agent/tasks/agent-blueprints-p0-p1/raw/screenshot-1.png

## Known gaps
- Live authenticated API smoke was not run because no browser/session token was available inside this autonomous cycle.
