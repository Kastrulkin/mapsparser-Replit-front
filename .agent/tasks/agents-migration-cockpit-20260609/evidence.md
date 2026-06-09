# Evidence Bundle: agents-migration-cockpit-20260609

## Summary
- Overall status: PASS
- Last updated: 2026-06-09T13:31:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `src/services/agent_legacy_migration.py` implements `apply_legacy_ai_agent_migration()`.
  - `src/api/agent_blueprints_api.py` exposes `POST /api/agent-blueprints/legacy-migration/apply`.
  - Migration creates communications blueprint wrappers with `persona_agent_id` and `legacy_migration` metadata.
- Gaps:
  - Production data apply was not executed in this local proof bundle; it remains a guarded non-destructive endpoint/UI action.

### AC2
- Status: PASS
- Proof:
  - `business_has_product_agent_runtime()` and `business_agent_enabled_for_channel()` prefer active `agent_blueprints`.
  - `src/ai_agent_webhooks.py` no longer uses `WHERE ai_agent_enabled = 1` and routes through the product-agent gate with legacy fallback.
- Gaps:
  - Physical column removal is intentionally deferred until Alembic cleanup after production wrapper coverage.

### AC3
- Status: PASS
- Proof:
  - `src/ai_agent.py` returns `workflow: []` and records `legacy_workflow_context` with `deprecated_not_runtime_truth`.
  - `src/ai_agent.py` no longer puts legacy workflow into the runtime prompt and state transition function returns current state.
  - `src/chats_api.py` sandbox/test endpoints keep workflow only as `legacy_workflow_context`.
- Gaps:
  - None for runtime truth cleanup.

### AC4
- Status: PASS
- Proof:
  - `frontend/src/pages/dashboard/AdminPage.tsx` no longer imports `AIAgentsManagement`; admin agents tab redirects to `Мои агенты`.
  - `frontend/src/pages/dashboard/AgentBlueprintsPage.tsx` no longer imports/renders `AIAgentSettings`; voice/style is shown inside cockpit.
- Gaps:
  - Physical deletion of legacy component source files can happen after a broader route/import proof.

### AC5
- Status: PASS
- Proof:
  - `AgentCockpitPanel` adds product cockpit metrics, migration health, deprecated-field state, and migration apply action.
  - `LearningHistoryPanel` shows learning/version events and legacy migration context.
  - Version actions are labelled around runtime truth, activate, and rollback.
  - `explainApproval()` shows plain-language waiting reasons.
- Gaps:
  - No browser screenshot captured in this local proof bundle.

### AC6
- Status: PASS
- Proof:
  - `docs/LOCALOS_AGENT_ARCHITECTURE_V1.md` documents apply endpoint, legacy workflow cleanup, webhook fallback, and UI entrypoint removal.
  - `docs/contracts/localos-openclaw/PHASE1.md` documents migration apply and product-agent runtime gate.
- Gaps:
  - None.

### AC7
- Status: PASS
- Proof:
  - Python compile passed for touched backend modules.
  - `tests/test_agent_blueprint_layer.py`: 43 passed.
  - `cd frontend && npm run build`: passed.
  - Production deploy smoke passed: `docker compose ps`, app logs, `curl -I http://localhost:8000`, route registration, and live frontend chunk checks.
- Gaps:
  - Build includes existing Browserslist/Rollup warnings from dependencies.

## Commands run
- `PYTHONPATH=src python3 -m py_compile src/api/agent_blueprints_api.py src/services/agent_legacy_migration.py src/ai_agent_webhooks.py src/chats_api.py src/ai_agent.py`
- `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py`
- `cd frontend && npm run build`
- `rg -n "AIAgentSettings|AIAgentsManagement|WHERE ai_agent_enabled = 1|Ответь на сообщение клиента, учитывая workflow|state.get\\('init_state'\\)"`
- Backend deploy: selective archive to `/opt/seo-app`, `docker compose restart app worker`, route/source smoke in app container.
- Frontend deploy: `bash scripts/deploy_frontend_dist.sh --build`, followed by live chunk checks for `AgentBlueprintsPage-CgHSWjEZ.js`.

## Raw artifacts
- .agent/tasks/agents-migration-cockpit-20260609/raw/build.txt
- .agent/tasks/agents-migration-cockpit-20260609/raw/test-unit.txt
- .agent/tasks/agents-migration-cockpit-20260609/raw/test-integration.txt
- .agent/tasks/agents-migration-cockpit-20260609/raw/lint.txt
- .agent/tasks/agents-migration-cockpit-20260609/raw/screenshot-1.png

## Known gaps
- Production field deletion is not run inside this proof bundle because physical DB cleanup requires backup, Alembic migration, and a dedicated production removal step.
- The non-destructive migration apply endpoint is deployed and available, but no bulk production data mutation was run from the deploy shell.
