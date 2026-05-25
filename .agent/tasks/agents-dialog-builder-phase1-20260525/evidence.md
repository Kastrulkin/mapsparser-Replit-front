# Evidence Bundle: agents-dialog-builder-phase1-20260525

## Summary
- Overall status: PASS
- Last updated: 2026-05-25T12:24:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - Added Alembic migration `20260525_add_agent_builder_sessions.py`.
  - Added backend API blueprint `src/api/agent_builder_api.py`.
  - Registered routes in `src/main.py`.
  - Added route ownership/lint guardrails.
- Gaps:
  - None.

### AC2
- Status: PASS
- Proof:
  - `scripts/smoke_agent_builder_dialog_api.py` created a `documents` blueprint from one free-text request.
  - Production smoke returned `category=documents`, `preview_available=true`, and a created `blueprint_id`.
- Gaps:
  - None.

### AC3
- Status: PASS
- Proof:
  - Unit tests assert missing questions are returned for document tasks without explicit data source/output.
  - Production smoke returned `questions_initial=2`, then `questions_after_reply=0` after clarification.
- Gaps:
  - None.

### AC4
- Status: PASS
- Proof:
  - Authenticated production browser smoke opened `/dashboard/agents`, clicked `Создать агента`, saw dialog prompt, saw `Нужно уточнить`, `Preview будущего агента`, and enabled `Создать из preview`.
  - Clicking `Создать из preview` closed the dialog and added the agent to the page.
- Gaps:
  - Browser input automation required keyboard-by-keyboard entry because virtual clipboard filling was unavailable, but the product flow itself passed.

### AC5
- Status: PASS
- Proof:
  - Manual wizard remains available behind `Открыть ручной мастер`.
  - Existing Agent Blueprint tests passed.
  - Backend lint baseline passed.
- Gaps:
  - None.

## Commands run
- `python3 -m pytest -q tests/test_agent_blueprint_layer.py`
- `scripts/lint_backend_baseline.sh`
- `cd frontend && npm run build`
- `bash scripts/deploy_backend_src.sh`
- `bash scripts/deploy_frontend_dist.sh --build`
- Server: `cd /opt/seo-app && docker compose ps && docker compose logs --since 15m app | tail -160 && curl -I http://localhost:8000`
- Server smoke: `cd /opt/seo-app && docker compose exec -T app env SMOKE_BASE_URL=http://localhost:8000 python /app/scripts/smoke_agent_builder_dialog_api.py`
- Authenticated production browser smoke on `https://localos.pro/dashboard/agents`

## Raw artifacts
- .agent/tasks/agents-dialog-builder-phase1-20260525/raw/build.txt
- .agent/tasks/agents-dialog-builder-phase1-20260525/raw/test-unit.txt
- .agent/tasks/agents-dialog-builder-phase1-20260525/raw/test-integration.txt
- .agent/tasks/agents-dialog-builder-phase1-20260525/raw/lint.txt
- .agent/tasks/agents-dialog-builder-phase1-20260525/raw/screenshot-1.png

## Known gaps
- No P0/P1 blocker remains for Phase 1.
- The next real gap is product depth: LLM-quality planning and Datahub-lite are later phases, not part of this Phase 1 DoD.
