# Evidence Bundle: agents-version-diff-activate-rollback-phase4-20260526

## Summary
- Overall status: PASS
- Last updated: 2026-05-26T16:29:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `GET /api/agent-blueprints` returns `active_version_id`, `active_version_number`, `active_goal`.
  - `GET /api/agent-blueprints/<id>` returns `active_version`, `active_version_id`, `active_version_number`.
  - Active version is stored in `agent_blueprints.metadata_json`, so no schema migration was needed.

### AC2
- Status: PASS
- Proof:
  - `build_agent_version_diff` compares goal, inputs, steps, persona, capabilities, approval policy, and output schema.
  - Unit test `test_agent_version_diff_shows_readable_changes` verifies readable changed fields and summary.
  - Server smoke verified feedback diff includes `output_schema`.

### AC3
- Status: PASS
- Proof:
  - `POST /api/agent-runs/<run_id>/feedback` creates a new version, returns `diff`, and records `version_event`.
  - Server smoke verified feedback version became active.

### AC4
- Status: PASS
- Proof:
  - Added `POST /api/agent-blueprints/<blueprint_id>/versions/<version_id>/activate`.
  - Added `POST /api/agent-blueprints/<blueprint_id>/versions/<version_id>/rollback`.
  - Server smoke rolled back to v1 and reactivated v3.

### AC5
- Status: PASS
- Proof:
  - Default run now resolves active version instead of blindly using latest.
  - Server smoke started an explicit v1 run, then rollback made default run use v1.

### AC6
- Status: PASS
- Proof:
  - `/dashboard/agents` version panel now shows active state, diff summary, `Запустить эту версию`, `Сделать активной`, and `Откатиться`.
  - Frontend build passed.
  - Browser sanity opened `/dashboard/agents`, loaded production assets, and unauthenticated session redirected to login without frontend crash.

### AC7
- Status: PASS
- Proof:
  - Unit tests: `21 passed`.
  - Lint baseline: PASS.
  - Frontend build: PASS.
  - Backend deploy: PASS.
  - Frontend deploy: PASS.
  - Server smoke: PASS.

## Commands run
- `python3 -m pytest -q tests/test_agent_blueprint_layer.py`
- `scripts/lint_backend_baseline.sh`
- `npm --prefix frontend run build`
- `git commit -m "Add agent blueprint version controls"`
- `git push`
- `scripts/deploy_backend_src.sh`
- `scripts/deploy_frontend_dist.sh --build`
- `git commit -m "Fix agent version diff payload copies"`
- `git push`
- `scripts/deploy_backend_src.sh`
- `cd /opt/seo-app && docker compose exec -T app env SMOKE_BASE_URL=http://localhost:8000 python /app/scripts/smoke_agent_blueprint_document_api.py`
- Browser sanity: `https://localos.pro/dashboard/agents`

## Raw artifacts
- .agent/tasks/agents-version-diff-activate-rollback-phase4-20260526/raw/build.txt
- .agent/tasks/agents-version-diff-activate-rollback-phase4-20260526/raw/test-unit.txt
- .agent/tasks/agents-version-diff-activate-rollback-phase4-20260526/raw/test-integration.txt
- .agent/tasks/agents-version-diff-activate-rollback-phase4-20260526/raw/lint.txt
- .agent/tasks/agents-version-diff-activate-rollback-phase4-20260526/raw/deploy.txt

## Known gaps
- Diff is field-level readable summary, not a full visual JSON diff editor.
- Browser sanity was unauthenticated; authenticated UI flow is covered indirectly by API smoke and frontend build, not a full user click-through.
