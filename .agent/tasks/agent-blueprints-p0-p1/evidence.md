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
  - None.

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
- `ssh ... 'cd /opt/seo-app && docker compose exec -T app sh -lc "APP_SRC_DIR=/app/src python3 -"' < scripts/smoke_agent_blueprint_outreach_api.py`
- server cleanup verification queries for smoke user/business/lead/draft rows

## Raw artifacts
- .agent/tasks/agent-blueprints-p0-p1/raw/build.txt
- .agent/tasks/agent-blueprints-p0-p1/raw/test-unit.txt
- .agent/tasks/agent-blueprints-p0-p1/raw/test-integration.txt
- .agent/tasks/agent-blueprints-p0-p1/raw/lint.txt
- .agent/tasks/agent-blueprints-p0-p1/raw/screenshot-1.png

## Known gaps
- No known P0/P1 gaps for the Agent Blueprint authenticated supervised outreach smoke.

## Live authenticated smoke
- Status: PASS
- Environment: production container, `http://localhost:8000` inside `/opt/seo-app`.
- Fixture: temporary smoke user, business, prospecting lead, approved message draft.
- Flow: login -> auth/me -> create supervised outreach blueprint -> start run -> approve shortlist -> approve drafts -> queue send batch.
- Result: run completed, `approval_count=2`, send queue stayed `queued`, `dispatcher_started=false`, fixture cleanup verified with zero remaining smoke rows.
