# Evidence Bundle: agents-builder-fourth-10-browser-20260617

## Summary
- Overall status: PASS
- Last updated: 2026-06-17T19:35:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - Browser-use exercised all 10 prompts on production `/dashboard/agents` using the create-agent dialog path.
  - Raw summary: `.agent/tasks/agents-builder-fourth-10-browser-20260617/raw/browser-retest-summary.json`.
- Gaps:
  - No real agents were created; checks intentionally stopped at the understanding/preview flow.

### AC2
- Status: PASS
- Proof:
  - Inventory maps to остатки/товары/расходники and a purchase list, not finance expenses.
  - New employee maps to team/staff profile readiness, not photo quality.
  - Cancellation reasons maps to grouped cancellation causes, not cancellation-risk client lists.
  - No browser scenario reported the known generic-domain issue markers.
- Gaps:
  - None known.

### AC3
- Status: PASS
- Proof:
  - Frontend labels now translate internal source keys such as inventory, staff_schedule, customer_chats, map_questions, and location_descriptions into user-facing Russian labels.
  - Browser summary shows expected data/result lines for all 10 scenarios.
- Gaps:
  - None known.

### AC4
- Status: PASS
- Proof:
  - `venv/bin/python -m pytest tests/test_agent_blueprint_layer.py -q` -> 164 passed.
  - `npm --prefix frontend run build` -> built successfully.
- Gaps:
  - Build still prints existing Browserslist/Yandex maps warnings.

### AC5
- Status: PASS
- Proof:
  - Partial production deploy copied the two backend service files and `frontend/dist`.
  - `docker compose restart app worker` completed.
  - `curl -I http://localhost:8000` returned HTTP 200.
  - App logs after restart showed normal startup and no traceback.
- Gaps:
  - None known.

## Commands run
- `scripts/proof_loop.sh init agents-builder-fourth-10-browser-20260617 "..."`
- Browser-use production pass for all 10 scenarios before fixes.
- `venv/bin/python -m pytest tests/test_agent_blueprint_layer.py -q -k "agent_builder"`
- `venv/bin/python -m pytest tests/test_agent_blueprint_layer.py -q`
- `npm --prefix frontend run build`
- Browser-use production retest for all 10 scenarios after fixes.
- Partial production deploy via `ssh -i ~/.ssh/localos_prod root@80.78.242.105 'cd /opt/seo-app && ...'`.

## Raw artifacts
- .agent/tasks/agents-builder-fourth-10-browser-20260617/raw/build.txt
- .agent/tasks/agents-builder-fourth-10-browser-20260617/raw/test-unit.txt
- .agent/tasks/agents-builder-fourth-10-browser-20260617/raw/test-integration.txt
- .agent/tasks/agents-builder-fourth-10-browser-20260617/raw/lint.txt
- .agent/tasks/agents-builder-fourth-10-browser-20260617/raw/screenshot-1.png
- .agent/tasks/agents-builder-fourth-10-browser-20260617/raw/browser-retest-summary.json
- .agent/tasks/agents-builder-fourth-10-browser-20260617/raw/deploy.txt

## Known gaps
- No known task-blocking gaps.
