# Evidence Bundle: agents-wizard-creation-ui-smoke-phase13-20260527

## Summary
- Overall status: PASS
- Last updated: 2026-05-27T16:58:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `raw/browser-wizard-creation-ui-smoke.txt`: browser flow created email, tables, and reviews agents from `/dashboard/agents` manual wizard.
  - Screenshots: `raw/browser-email-created-run.png`, `raw/browser-tables-created-run.png`, `raw/browser-reviews-created-run.png`.
- Gaps:
  - The smoke covers the manual wizard. Dialog-builder preview remains the next separate hardening target.

### AC2
- Status: PASS
- Proof:
  - `raw/browser-wizard-creation-ui-smoke.txt`: each created agent was launched and checked for `Путь письма-агента`, `Путь таблицы-агента`, or `Путь отзывы-агента`.
  - Each review included `Входные данные`, `Что понял`, and `Результат`.
- Gaps:
  - None.

### AC3
- Status: PASS
- Proof:
  - `raw/prod-created-agents-verify.txt`: `runs=3`, `capability_steps=0`, `external_dispatch_true_artifacts=0`, `pending_approvals=3`.
  - `raw/browser-wizard-creation-ui-smoke.txt`: `visible_open_pre_count=0` for all three scenarios.
- Gaps:
  - None.

### AC4
- Status: PASS
- Proof:
  - `raw/prod-fixture-cleanup.txt`: production fixture removed.
  - `raw/prod-fixture-cleanup-verify.txt`: `users=0`, `businesses=0`, `blueprints=0`, `runs=0`, `builder_sessions=0`.
  - `raw/prod-health-after-smoke.txt`: app/postgres/worker up and local HTTP returns 200.
- Gaps:
  - None.

## Commands run
- `scripts/proof_loop.sh init agents-wizard-creation-ui-smoke-phase13-20260527 ...`
- `ssh ... 'cd /opt/seo-app && docker compose exec -T app ...'` to create exact smoke fixture.
- `SMOKE_UI_PASSWORD=... python3 .agent/tasks/agents-wizard-creation-ui-smoke-phase13-20260527/raw/wizard_creation_ui_smoke.py`
- `ssh ... 'cd /opt/seo-app && docker compose exec -T app python -'` to verify safety boundaries and cleanup.
- `ssh ... 'cd /opt/seo-app && docker compose ps && curl -I http://localhost:8000'`

## Raw artifacts
- .agent/tasks/agents-wizard-creation-ui-smoke-phase13-20260527/raw/build.txt
- .agent/tasks/agents-wizard-creation-ui-smoke-phase13-20260527/raw/test-unit.txt
- .agent/tasks/agents-wizard-creation-ui-smoke-phase13-20260527/raw/test-integration.txt
- .agent/tasks/agents-wizard-creation-ui-smoke-phase13-20260527/raw/lint.txt
- .agent/tasks/agents-wizard-creation-ui-smoke-phase13-20260527/raw/screenshot-1.png
- .agent/tasks/agents-wizard-creation-ui-smoke-phase13-20260527/raw/wizard_creation_ui_smoke.py
- .agent/tasks/agents-wizard-creation-ui-smoke-phase13-20260527/raw/browser-wizard-creation-ui-smoke.txt
- .agent/tasks/agents-wizard-creation-ui-smoke-phase13-20260527/raw/browser-email-created-run.png
- .agent/tasks/agents-wizard-creation-ui-smoke-phase13-20260527/raw/browser-tables-created-run.png
- .agent/tasks/agents-wizard-creation-ui-smoke-phase13-20260527/raw/browser-reviews-created-run.png
- .agent/tasks/agents-wizard-creation-ui-smoke-phase13-20260527/raw/prod-created-agents-verify.txt
- .agent/tasks/agents-wizard-creation-ui-smoke-phase13-20260527/raw/prod-fixture-cleanup.txt
- .agent/tasks/agents-wizard-creation-ui-smoke-phase13-20260527/raw/prod-fixture-cleanup-verify.txt
- .agent/tasks/agents-wizard-creation-ui-smoke-phase13-20260527/raw/prod-health-after-smoke.txt

## Known gaps
- Dialog builder preview/create flow was not changed in this cycle. It should be the next focused proof-loop after manual wizard creation is now proven.
