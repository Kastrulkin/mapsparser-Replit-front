# Evidence Bundle: agents-run-detail-human-journal-phase5-20260527

## Summary
- Overall status: PASS
- Last updated: 2026-05-27T08:00:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `src/services/agent_blueprint_workspace.py` now builds `review["journal"]` via `_review_journal`.
  - `tests/test_agent_blueprint_layer.py::test_agent_run_review_journal_is_human_readable` verifies the journal shape directly.
- Gaps:
  - None.

### AC2
- Status: PASS
- Proof:
  - Journal entries include `input`, `extraction`, `output`, and `approval` kinds.
  - Production document smoke returned `journal_kinds`: `approval`, `extraction`, `input`, `output`.
- Gaps:
  - None.

### AC3
- Status: PASS
- Proof:
  - `frontend/src/pages/dashboard/AgentBlueprintsPage.tsx` renders "Журнал запуска" and `JournalEntryCard`.
  - Full entry payload is behind the collapsed "Технический журнал" disclosure.
- Gaps:
  - Authenticated production browser click-through was not performed under a real user in this phase.

### AC4
- Status: PASS
- Proof:
  - `scripts/smoke_agent_blueprint_document_api.py` validates `journal` and `journal_kinds`.
  - Production smoke returned `external_dispatch_performed: false` and `fixture_cleaned: true`.
- Gaps:
  - None.

### AC5
- Status: PASS
- Proof:
  - Unit tests passed: `22 passed`.
  - Backend lint baseline passed.
  - Frontend build passed.
  - Deploy completed with `EXIT=0`.
  - Server health returned `HTTP/1.1 200 OK`.
  - Live browser sanity loaded `/dashboard/agents`, redirected to `/login`, used the deployed JS/CSS bundle, and had no console errors.
- Gaps:
  - Frontend deploy logged tar "file changed as we read it" warnings during static sync, but integrity checks and live asset references passed.

## Commands run
- `python3 -m pytest -q tests/test_agent_blueprint_layer.py`
- `scripts/lint_backend_baseline.sh`
- `npm --prefix frontend run build`
- `scripts/deploy_backend_src.sh`
- `scripts/deploy_frontend_dist.sh --build`
- `docker compose ps` on server from `/opt/seo-app`
- `docker compose logs --since 10m app` on server from `/opt/seo-app`
- `curl -I http://localhost:8000` on server from `/opt/seo-app`
- `SMOKE_BASE_URL=http://localhost:8000 python /app/scripts/smoke_agent_blueprint_document_api.py` inside the server app container

## Raw artifacts
- .agent/tasks/agents-run-detail-human-journal-phase5-20260527/raw/build.txt
- .agent/tasks/agents-run-detail-human-journal-phase5-20260527/raw/test-unit.txt
- .agent/tasks/agents-run-detail-human-journal-phase5-20260527/raw/test-integration.txt
- .agent/tasks/agents-run-detail-human-journal-phase5-20260527/raw/lint.txt
- .agent/tasks/agents-run-detail-human-journal-phase5-20260527/raw/screenshot-1.png

## Known gaps
- Authenticated production UI smoke under a real user was not performed in this phase; API/live bundle checks passed.
- Old unrelated untracked `.agent/tasks/agent-api-contract-onboarding-20260525/` remains untouched.
