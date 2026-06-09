# Evidence Bundle: agents-migration-cleanup-20260609

## Summary
- Overall status: PASS
- Last updated: 2026-06-09T12:58:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - Added read-only migration plan service in `src/services/agent_legacy_migration.py`.
  - Added authenticated endpoint `GET /api/agent-blueprints/legacy-migration-plan?business_id=...`.
  - Legacy `AIAgents.workflow` is marked `deprecated_not_runtime_truth`.
  - Legacy business AI settings are mapped to persona/blueprint targets and marked `deprecated_migration_source`.
  - Legacy sandbox preview is bridged to shared run preview contract without side effects.
  - OpenClaw and LocalOS agent architecture docs were updated.
  - `PYTHONPATH=src python3 -m py_compile src/api/agent_blueprints_api.py src/services/agent_legacy_migration.py` passed.
  - `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py` passed: 41 tests.
- Gaps:
  - No production data was migrated or deleted in this stage by design.
  - Deprecated fields cannot be removed until a future Alembic migration and UI/API no-read proof are complete.

## Commands run
- `PYTHONPATH=src python3 -m py_compile src/api/agent_blueprints_api.py src/services/agent_legacy_migration.py`
- `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py`

## Raw artifacts
- .agent/tasks/agents-migration-cleanup-20260609/raw/build.txt
- .agent/tasks/agents-migration-cleanup-20260609/raw/test-unit.txt
- .agent/tasks/agents-migration-cleanup-20260609/raw/test-integration.txt
- .agent/tasks/agents-migration-cleanup-20260609/raw/lint.txt
- .agent/tasks/agents-migration-cleanup-20260609/raw/screenshot-1.png

## Known gaps
- Production deploy verification is recorded after deployment.
