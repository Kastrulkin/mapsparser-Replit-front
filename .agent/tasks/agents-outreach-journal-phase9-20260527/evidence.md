# Evidence Bundle: agents-outreach-journal-phase9-20260527

## Summary
- Overall status: PASS
- Last updated: 2026-05-27T09:09:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `src/services/agent_blueprint_workspace.py` now maps `lead_source_plan`, `lead_shortlist`, `message_drafts`, and `outreach_outcomes` to journal kinds `sourcing`, `shortlist`, `drafts`, and `queue`.
  - `tests/test_agent_blueprint_layer.py::test_outreach_run_review_journal_explains_pipeline_and_queue_boundary` verifies these stages.
  - Production smoke returned journal kinds: `sourcing`, `shortlist`, `drafts`, `queue`.

### AC2
- Status: PASS
- Proof:
  - Journal details include `Источник данных`, `Найдено лидов`, `Лидов в shortlist`, `Черновиков`, `В очереди`, `Dispatch`, and `Внешняя отправка`.
  - Production smoke verified those labels from `/api/agent-blueprints/<id>/review`.

### AC3
- Status: PASS
- Proof:
  - Existing outreach smoke created a blueprint, sourced from `prospectingleads`, approved shortlist and drafts, queued a batch, and verified `queued_not_dispatched`.
  - Smoke asserted queue row stayed `queued`, with no `sent_at` or provider message id.
  - Fixture was cleaned after smoke.

### AC4
- Status: PASS
- Proof:
  - Unit: 32 passed.
  - Lint baseline passed.
  - Frontend build passed.
  - Partial production deploy copied only the changed runtime workspace file and smoke script.
  - Server health returned `200 OK`.
  - Production outreach smoke passed.

## Commands run
- `python3 -m pytest -q tests/test_agent_blueprint_layer.py`
- `scripts/lint_backend_baseline.sh`
- `npm --prefix frontend run build`
- partial deploy: `scp src/services/agent_blueprint_workspace.py ... && docker compose restart app worker`
- `docker compose exec -T app env SMOKE_BASE_URL=http://localhost:8000 python /app/scripts/smoke_agent_blueprint_outreach_api.py`
- `docker compose ps && docker compose logs --since 10m app | tail -n 160 && curl -I http://localhost:8000`

## Raw artifacts
- .agent/tasks/agents-outreach-journal-phase9-20260527/raw/build.txt
- .agent/tasks/agents-outreach-journal-phase9-20260527/raw/test-unit.txt
- .agent/tasks/agents-outreach-journal-phase9-20260527/raw/test-integration.txt
- .agent/tasks/agents-outreach-journal-phase9-20260527/raw/lint.txt
- .agent/tasks/agents-outreach-journal-phase9-20260527/raw/screenshot-1.png

## Known gaps
- This phase does not redesign the UI; it improves the backend review payload that UI consumes.
- Dispatcher/provider sending remains intentionally out of scope.
- A separate pre-existing local `src/main.py` diff remains uncommitted and was not deployed by the normal whole-src deploy path.
