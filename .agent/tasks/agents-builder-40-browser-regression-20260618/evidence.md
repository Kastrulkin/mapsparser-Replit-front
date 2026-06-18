# Evidence Bundle: agents-builder-40-browser-regression-20260618

## Summary
- Overall status: PASS
- Last updated: 2026-06-18T06:05:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - Extracted 40 scenarios from the four scenario-pack tests in `tests/test_agent_blueprint_layer.py`.
  - Browser-use live run on `/dashboard/agents` completed with `count: 40`.
  - Raw summary: `.agent/tasks/agents-builder-40-browser-regression-20260618/raw/browser-40-final-summary.json`.
- Gaps:
  - No real agents were created by design.

### AC2
- Status: PASS
- Proof:
  - Final browser summary has `issues: []` for all 40 scenarios.
  - Spot checks covered reviews, reminders, Google Sheets, finance import, partnerships, bookings, photo quality, competitor prices, service checks, inventory, schedules, chats, FAQ, revenue anomalies, map questions, and branch descriptions.
- Gaps:
  - None known.

### AC3
- Status: PASS
- Proof:
  - Added stale-preview guard in `AgentBlueprintsPage.tsx`.
  - Browser check after deploy showed: `Вы изменили запрос. Нажмите «Обновить понимание»...`.
  - Browser check confirmed only one visible `Обновить понимание` button in that state.
- Gaps:
  - The old preview cards remain visible below the guard for context, but the next-step block clearly marks them stale and disables creation.

### AC4
- Status: PASS
- Proof:
  - `venv/bin/python -m pytest tests/test_agent_blueprint_layer.py -q` -> 164 passed.
  - `npm --prefix frontend run build` -> success.
- Gaps:
  - Existing Browserslist/Yandex maps build warnings remain.

### AC5
- Status: PASS
- Proof:
  - Frontend dist copied to production app container.
  - `docker compose ps` showed app and worker up.
  - `curl -I http://localhost:8000` returned `HTTP/1.1 200 OK`.
- Gaps:
  - None known.

## Commands run
- `scripts/proof_loop.sh init agents-builder-40-browser-regression-20260618 "..."`
- Browser-use initial 40-scenario run.
- Browser-use stale-preview guard check.
- `venv/bin/python -m pytest tests/test_agent_blueprint_layer.py -q`
- `npm --prefix frontend run build`
- Frontend-only production deploy by copying `frontend/dist` into `seo-app-app-1:/app/frontend/dist/`.
- Browser-use final live 40-scenario run.

## Raw artifacts
- .agent/tasks/agents-builder-40-browser-regression-20260618/raw/build.txt
- .agent/tasks/agents-builder-40-browser-regression-20260618/raw/test-unit.txt
- .agent/tasks/agents-builder-40-browser-regression-20260618/raw/test-integration.txt
- .agent/tasks/agents-builder-40-browser-regression-20260618/raw/lint.txt
- .agent/tasks/agents-builder-40-browser-regression-20260618/raw/screenshot-1.png
- .agent/tasks/agents-builder-40-browser-regression-20260618/raw/browser-40-final-summary.json
- .agent/tasks/agents-builder-40-browser-regression-20260618/raw/deploy.txt

## Known gaps
- No known task-blocking gaps.
