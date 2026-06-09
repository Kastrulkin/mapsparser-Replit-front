# Evidence Bundle: agents-migration-cleanup-20260609

## Summary
- Overall status: PASS
- Last updated: 2026-06-09T15:41:30+03:00

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
  - Production backend deployed by uploading changed `src` files to `/opt/seo-app/src` and restarting `app worker`.
  - Production `docker compose ps`: app, worker, postgres are up; postgres is healthy.
  - Production `curl -I http://localhost:8000`: HTTP 200.
  - Production route smoke: `LEGACY_MIGRATION_ROUTE ['GET']`.
  - Production service smoke: `LEGACY_WORKFLOW_STATUS deprecated_not_runtime_truth`.
- Gaps:
  - No production data was migrated or deleted in this stage by design.
  - Deprecated fields cannot be removed until a future Alembic migration and UI/API no-read proof are complete.

## Commands run
- `PYTHONPATH=src python3 -m py_compile src/api/agent_blueprints_api.py src/services/agent_legacy_migration.py`
- `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py`
- `ssh ... "cd /opt/seo-app && docker compose restart app worker"`
- `ssh ... "cd /opt/seo-app && docker compose ps"`
- `ssh ... "cd /opt/seo-app && docker compose logs --since 15m app | tail -n 120"`
- `ssh ... "cd /opt/seo-app && docker compose logs --since 15m worker | tail -n 80"`
- `ssh ... "cd /opt/seo-app && curl -I http://localhost:8000"`
- `ssh ... "cd /opt/seo-app && docker compose exec -T app python3 -c '...'"`

## Raw artifacts
- .agent/tasks/agents-migration-cleanup-20260609/raw/build.txt
- .agent/tasks/agents-migration-cleanup-20260609/raw/test-unit.txt
- .agent/tasks/agents-migration-cleanup-20260609/raw/test-integration.txt
- .agent/tasks/agents-migration-cleanup-20260609/raw/lint.txt
- .agent/tasks/agents-migration-cleanup-20260609/raw/screenshot-1.png

## Known gaps
- `docker compose cp` into `/app/src` is blocked by a read-only mount; runtime uses `/opt/seo-app/src` source with service restart.
- Deprecated legacy fields remain live compatibility reads until a later no-read proof and Alembic cleanup migration.
