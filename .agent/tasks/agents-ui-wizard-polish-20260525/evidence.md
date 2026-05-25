# Evidence Bundle: agents-ui-wizard-polish-20260525

## Summary
- Overall status: PASS
- Last updated: 2026-05-25T09:45:00+00:00

## Acceptance criteria evidence

### AC1: Version UX
- Status: PASS
- Proof:
  - `frontend/src/pages/dashboard/AgentBlueprintsPage.tsx` now shows active version in blueprint cards and detail panel.
  - Settings panel includes `Версия агента`, newest versions, and old-run preservation wording.
  - Feedback notice says what changes for following runs.

### AC2: File upload errors
- Status: PASS
- Proof:
  - `src/services/agent_source_ingestion.py` returns Russian user-facing messages for required file, unsupported type/MIME, too large, empty file, empty extraction, and extraction failure.
  - `tests/test_agent_blueprint_layer.py` covers unsupported and empty file messages.
  - Frontend surfaces request error text instead of replacing it with a generic failure.

### AC3: Generic safety smoke
- Status: PASS
- Proof:
  - Added `scripts/smoke_agent_blueprint_generic_boundaries.py`.
  - Production run checked `documents`, `email`, `tables`, `reviews`.
  - Result: `external_dispatch_performed=false`, `dispatcher_started=false`, `approvals_required=true`, `fixture_cleaned=true`.

### AC4: Deploy after steps
- Status: PASS
- Proof:
  - Commit `b491764` pushed and deployed backend/frontend.
  - Commit `5ad21a7` pushed and smoke script copied into production app container for execution.
  - Production `curl -I http://localhost:8000` returned 200 after deploy.

### AC5: Authenticated UI smoke
- Status: PASS
- Proof:
  - Temporary paid test user logged in through browser.
  - Wizard created a document agent from `Тип агента -> Данные -> Правила и контроль -> Результат`.
  - Agent was launched from its card.
  - Review showed human-readable input/extraction/output, `Технический журнал`, active version, and no `payload_json` / `blueprint_version_id` on the main surface.
  - Feedback created a new active version notice.
  - Temporary fixture cleanup verified `users 0`, `businesses 0`, `agent_blueprints 0`.

## Commands run
- `python3 -m pytest -q tests/test_agent_blueprint_layer.py`
- `scripts/lint_backend_baseline.sh`
- `cd frontend && npm run build`
- `bash scripts/deploy_backend_src.sh`
- `bash scripts/deploy_frontend_dist.sh --build`
- `cd /opt/seo-app && docker compose exec -T app env SMOKE_BASE_URL=http://localhost:8000 python /app/scripts/smoke_agent_blueprint_generic_boundaries.py`
- Authenticated browser smoke on `https://localos.pro/dashboard/agents`

## Raw artifacts
- `.agent/tasks/agents-ui-wizard-polish-20260525/raw/build.txt`
- `.agent/tasks/agents-ui-wizard-polish-20260525/raw/test-unit.txt`
- `.agent/tasks/agents-ui-wizard-polish-20260525/raw/test-integration.txt`
- `.agent/tasks/agents-ui-wizard-polish-20260525/raw/lint.txt`

## Known gaps
- UI browser automation had to type ASCII text because the in-app browser virtual clipboard was unavailable for Cyrillic fill/type. The product UI itself handled the workflow correctly.
- Server git checkout remains dirty from runtime/deploy state, so production smoke script was copied into the app container rather than applied via `git pull`.
