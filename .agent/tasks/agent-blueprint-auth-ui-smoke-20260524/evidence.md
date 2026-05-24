# Evidence Bundle: agent-blueprint-auth-ui-smoke-20260524

## Summary
- Overall status: PASS
- Last updated: 2026-05-24T08:40:00+00:00

## Acceptance criteria evidence

### AC1: Authenticated agents page loads production API
- Status: PASS
- Proof:
  - Found and fixed frontend endpoint path duplication in `AgentBlueprintsPage.tsx`: `/api/agent-blueprints` became `/agent-blueprints` for the shared API client.
  - Live browser load of `https://localos.pro/dashboard/agents` showed `Workflow agents 1` and the smoke blueprint.

### AC2: Blueprint card, timeline, run history, approval queue
- Status: PASS
- Proof:
  - Browser DOM contained `Smoke Supervised Outreach Agent`, `Run timeline`, `Run history`, and `Approval queue`.

### AC3: Full artifact payload and queued boundary
- Status: PASS
- Proof:
  - Browser DOM after opening completed run and expanding payloads contained `Full payload`, `Smoke generated text`, `Queued but not dispatched`, and `Внешняя отправка не запускалась`.
  - Fixed UI to read queued send boundary from `output_json.orchestrator.result`, matching production API shape.

### AC4: Pending approval visible
- Status: PASS
- Proof:
  - Browser started a new run and DOM contained `waiting_approval`, `pending`, `Отклонить`, and `Подтвердить`.

### AC5: Run filters
- Status: PASS
- Proof:
  - Browser clicked `Approval`; DOM showed `waiting_approval`.
  - Browser clicked `Completed`; DOM showed `completed`.

### AC6: Smoke fixture cleanup
- Status: PASS
- Proof:
  - Cleanup script reported `CLEANED`.
  - Production DB verification returned `users 0`, `businesses 0`, `blueprints 0`, `runs 0` for smoke IDs.

### AC7: Build/tests/lint
- Status: PASS
- Proof:
  - `npm run build` passed.
  - `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py` passed: `6 passed`.
  - `scripts/lint_backend_baseline.sh` passed.

## Commands run
- `cd frontend && npm run build`
- `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py`
- `scripts/lint_backend_baseline.sh`
- `scripts/deploy_frontend_dist.sh --build`
- `scripts/deploy_frontend_dist.sh`
- Authenticated browser smoke against `https://localos.pro/dashboard/agents`
- Production cleanup/verification via Docker app container.

## Raw artifacts
- `.agent/tasks/agent-blueprint-auth-ui-smoke-20260524/raw/build.txt`
- `.agent/tasks/agent-blueprint-auth-ui-smoke-20260524/raw/test-unit.txt`
- `.agent/tasks/agent-blueprint-auth-ui-smoke-20260524/raw/test-integration.txt`
- `.agent/tasks/agent-blueprint-auth-ui-smoke-20260524/raw/lint.txt`

## Known gaps
- Full-page screenshot capture timed out in the in-app browser, so proof relies on DOM assertions and command output.
