# Evidence Bundle: agents-builder-second-10-browser-20260617

## Summary
- Overall status: PASS
- Last updated: 2026-06-17T19:25:00+03:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - Browser-use opened `https://localos.pro/dashboard/agents`.
  - Initial pass covered all 10 requested scenarios and identified failures in overdue invoices, empty customer cards, expense control, weak reviews by location, content from reviews, old client reactivation, partner replies, and daily problem digest.
  - Post-deploy browser retest covered all failed scenarios and showed no `issues` from the runner.
- Gaps:
  - The two scenarios that were already correct in the first pass, bookings without prepayment and duplicate services, were covered by regression tests and not repeated post-deploy.

### AC2
- Status: PASS
- Proof:
  - Fixed category/source detection in `src/services/agent_blueprint_draft_builder.py`.
  - Guarded AI intent acceptance so Telegram/Google Sheets/finance routes require explicit support in user text.
  - Narrowed post-format clarification in `src/services/agent_openclaw_planner_loop.py`.
  - Regression test `test_agent_builder_understands_second_browser_scenario_pack_without_wrong_domains` covers all 10 prompts.
- Gaps:
  - Natural-language heuristics still need future expansion as new real prompts appear.

### AC3
- Status: PASS
- Proof:
  - Added user-facing labels for `clients`, `locations`, `localos_digest`, and `outreach_drafts`.
  - Browser retest showed visible labels: `клиенты`, `точки сети`, `дайджест LocalOS`, `черновики сообщений партнёрам`.
- Gaps:
  - Some older source labels such as `отзывы компании, отзывы` are duplicative but not blocking.

### AC4
- Status: PASS
- Proof:
  - `venv/bin/python -m pytest tests/test_agent_blueprint_layer.py -q` passed: 162 tests.
  - `npm --prefix frontend run build` passed.
  - Backend partial deploy completed, `docker compose ps` showed app/worker up, `curl -I http://localhost:8000` returned 200.
  - Frontend dist copied into `seo-app-app-1:/app/frontend/dist/`.
  - App logs after browser pass showed `POST /api/agent-builder/sessions` returning 201 and no application exceptions.
- Gaps:
  - `EXTERNAL_AUTH_SECRET_KEY` and urllib3 certificate warnings are pre-existing server warnings, unrelated to this task.

## Commands run
- `scripts/proof_loop.sh init agents-builder-second-10-browser-20260617 "..."`
- `venv/bin/python -m pytest tests/test_agent_blueprint_layer.py -q -k "agent_builder"`
- `venv/bin/python -m pytest tests/test_agent_blueprint_layer.py -q`
- `npm --prefix frontend run build`
- backend partial deploy through `scp` + `docker compose restart app worker`
- frontend dist partial deploy through `docker cp`
- browser-use scenario runner on `https://localos.pro/dashboard/agents`

## Raw artifacts
- .agent/tasks/agents-builder-second-10-browser-20260617/raw/build.txt
- .agent/tasks/agents-builder-second-10-browser-20260617/raw/test-unit.txt
- .agent/tasks/agents-builder-second-10-browser-20260617/raw/test-integration.txt
- .agent/tasks/agents-builder-second-10-browser-20260617/raw/lint.txt
- .agent/tasks/agents-builder-second-10-browser-20260617/raw/screenshot-1.png

## Known gaps
- Browser tabs changed ids during repeated scenario navigation; retests rebound to the latest tab and continued.
- No production data mutation was performed.
