# Evidence Bundle: agents-builder-third-10-browser-20260617

## Summary
- Overall status: PASS
- Last updated: 2026-06-17T18:12:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - Added deterministic intent/source/output handling for photo quality, competitor prices, cancellation risk, new services, customer questions, team tasks, no-discount promos, repeated complaints, manager report, and holiday readiness.
  - Browser-use live retest found no `lead_cross_domain`, `finance_cross_domain`, `generic_services_output`, or unnecessary clarification issues across all 10 scenarios.
- Gaps:
  - Some source lists still show benign duplicates like `отзывы компании, отзывы`.

### AC2
- Status: PASS
- Proof:
  - Added user-facing labels for `business_cards`, `photos`, `competitors`, `customer_questions`, `customer_messages`, `localos_tasks`, `team`, `whatsapp`, `seasonality`, `posts`, and `schedule`.
  - Browser-use confirmed visible labels such as `карточки`, `фотографии`, `конкуренты`, `WhatsApp`, `задачи LocalOS`, `сезонность`, `посты`, and `расписание`.
- Gaps:
  - None blocking.

### AC3
- Status: PASS
- Proof:
  - `venv/bin/python -m pytest tests/test_agent_blueprint_layer.py -q -k "agent_builder"` passed: 34 passed.
  - `venv/bin/python -m pytest tests/test_agent_blueprint_layer.py -q` passed: 163 passed.
  - `npm --prefix frontend run build` passed.
- Gaps:
  - Build emitted existing Browserslist/PURE annotation warnings from dependencies.

### AC4
- Status: PASS
- Proof:
  - Deployed backend service files and `frontend/dist` to server.
  - Restarted `app` and `worker`; `docker compose ps` showed both up.
  - `curl -I http://localhost:8000` returned `HTTP/1.1 200 OK`.
  - Browser-use retested all 10 prompts on `https://localos.pro/dashboard/agents`.
- Gaps:
  - Browser test intentionally stopped before creating real agents.

## Commands run
- `venv/bin/python -m pytest tests/test_agent_blueprint_layer.py -q -k "agent_builder"`
- `venv/bin/python -m pytest tests/test_agent_blueprint_layer.py -q`
- `npm --prefix frontend run build`
- `scp ... src/services/agent_builder_session.py src/services/agent_blueprint_draft_builder.py`
- `tar -C frontend/dist -czf /tmp/localos-frontend-dist-agents-third.tgz .`
- `ssh root@80.78.242.105 'cd /opt/seo-app && ... docker compose restart app worker ... curl -I --max-time 15 http://localhost:8000'`
- Browser-use live scenario retest for all 10 supplied prompts.

## Raw artifacts
- .agent/tasks/agents-builder-third-10-browser-20260617/raw/build.txt
- .agent/tasks/agents-builder-third-10-browser-20260617/raw/test-unit.txt
- .agent/tasks/agents-builder-third-10-browser-20260617/raw/test-integration.txt
- .agent/tasks/agents-builder-third-10-browser-20260617/raw/lint.txt
- .agent/tasks/agents-builder-third-10-browser-20260617/raw/screenshot-1.png

## Known gaps
- Benign duplicate source wording remains for review-derived scenarios: `отзывы компании, отзывы`.
