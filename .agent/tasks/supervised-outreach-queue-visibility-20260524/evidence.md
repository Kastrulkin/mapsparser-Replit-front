# Evidence Bundle: supervised-outreach-queue-visibility-20260524

## Summary
- Overall status: PASS
- Last updated: 2026-05-24T10:39:00+00:00

## Acceptance criteria evidence

### AC1: Capability exposes queued-not-dispatched state
- Status: PASS
- Proof:
  - `src/services/outreach_send_capability.py` returns `dispatch_state: queued_not_dispatched`, `dispatcher_required: true`, and an operator note when rows are queued.
  - `tests/test_agent_blueprint_layer.py` asserts the explicit dispatch state and note.

### AC2: Outcomes artifact exposes queue handoff state
- Status: PASS
- Proof:
  - `src/services/agent_blueprint_runner.py` writes `queued_count`, `dispatch_state`, `external_dispatch_performed: false`, and an operator note into outreach outcomes payloads.

### AC3: UI displays queued-not-dispatched clearly
- Status: PASS
- Proof:
  - `frontend/src/pages/dashboard/AgentBlueprintsPage.tsx` detects `dispatch_state === "queued_not_dispatched"` and renders explicit queued-but-not-dispatched state plus the backend operator note.
  - `npm run build` passed with `AgentBlueprintsPage-C34AIHvL.js`.

### AC4: Live smoke validates full supervised outreach queue path
- Status: PASS
- Proof:
  - Live smoke returned `approval_count=2`, `queue_status=queued`, `dispatch_state=queued_not_dispatched`, `dispatcher_started=false`, `fixture_cleaned=true`.

### AC5: Checks and deploy passed
- Status: PASS
- Proof:
  - Targeted pytest: 18 passed.
  - py_compile passed for changed backend modules and smoke script.
  - `scripts/lint_backend_baseline.sh` passed.
  - `npm run build` passed.
  - Backend deploy restarted `app` and `worker`; root health returned `HTTP/1.1 200 OK`.
  - Frontend deploy verified `/assets/index-B7kTYWvV.js`.

## Commands run
- `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py tests/test_operator_paid_action_adapter.py tests/test_operator_review_reply_bulk.py`
- `python3 -m py_compile src/services/agent_blueprint_runner.py src/services/outreach_send_capability.py scripts/smoke_agent_blueprint_outreach_api.py`
- `scripts/lint_backend_baseline.sh`
- `cd frontend && npm run build`
- `git archive --format=tar HEAD src scripts docker-compose.yml | ssh ... 'cd /opt/seo-app && tar -xf - && docker compose restart app worker ...'`
- `scripts/deploy_frontend_dist.sh --build`
- `cat scripts/smoke_agent_blueprint_outreach_api.py | ssh ... 'cd /opt/seo-app && docker compose exec -T app ...'`
- Server verification: `docker compose ps`, `docker compose logs --since 10m app`, `docker compose logs --since 10m worker`, `curl -I http://localhost:8000`, dispatcher env check, frontend index check.

## Raw artifacts
- .agent/tasks/supervised-outreach-queue-visibility-20260524/raw/build.txt
- .agent/tasks/supervised-outreach-queue-visibility-20260524/raw/test-unit.txt
- .agent/tasks/supervised-outreach-queue-visibility-20260524/raw/test-integration.txt
- .agent/tasks/supervised-outreach-queue-visibility-20260524/raw/lint.txt
- .agent/tasks/supervised-outreach-queue-visibility-20260524/raw/screenshot-1.png

## Known gaps
- None for this task.
- Frontend deploy produced non-fatal tar warnings because assets changed while packaging; deploy script exited 0 and verified live bundles.
