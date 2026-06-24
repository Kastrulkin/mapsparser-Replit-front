# Evidence Bundle: agents-custom-ui-20260616

## Summary
- Overall status: PASS
- Last updated: 2026-06-16T12:52:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `/dashboard/agents` no longer crashes when the user opens `Подключения`; the missing `postCreateHandoff` prop path was fixed.
  - First-layer copy now uses product language: `Следующий шаг`, `Карта готовности`, `Доступы`, `Тест без отправки`, `Ручное подтверждение`, `Источники и каналы`.
  - Technical terms are moved out of the normal first layer or renamed in Russian: no `safe preview`, `preflight`, `compiled workflow`, `Policy`, `approval gate`, `provider route`, `billing ledger`, `production run`, `OpenClaw` in the visible product layer checked by the guard.
  - `scripts/ci_gate_product_ui.sh` passed and includes the mocked cockpit render plus the expanded copy guard.
  - `scripts/smoke_agents_product_ui_mock.py` passed and clicks the `Подключения` tab to catch runtime crashes.
  - Live `https://localos.pro/dashboard/agents` was reloaded in the in-app browser after deploy: `Мои агенты`, `Создать агента`, `Следующий шаг` are visible; `Подключения агента` opens; console error count is `0`.
- Gaps:
  - No backend behavior changed; this task was limited to the product UI layer and smoke coverage.

## Commands run
- `(cd frontend && npm run build:all) > .agent/tasks/agents-custom-ui-20260616/raw/build.txt 2>&1`
- `scripts/ci_gate_product_ui.sh > .agent/tasks/agents-custom-ui-20260616/raw/lint.txt 2>&1`
- `python3 scripts/smoke_agents_product_ui_mock.py --screenshot .agent/tasks/agents-custom-ui-20260616/raw/screenshot-1.png > .agent/tasks/agents-custom-ui-20260616/raw/test-integration.txt 2>&1`
- `scripts/verify_frontend_dist_integrity.sh frontend/dist > .agent/tasks/agents-custom-ui-20260616/raw/dist-integrity.txt 2>&1`
- `scripts/verify_frontend_dist_integrity.sh frontend/public-dist frontend/public-dist/public-audit/index.html > .agent/tasks/agents-custom-ui-20260616/raw/public-dist-integrity.txt 2>&1`
- `bash scripts/deploy_frontend_dist.sh > .agent/tasks/agents-custom-ui-20260616/raw/deploy.txt 2>&1`
- In-app browser verification on `https://localos.pro/dashboard/agents`: reload, inspect DOM, open `Подключения`, inspect console errors.

## Raw artifacts
- .agent/tasks/agents-custom-ui-20260616/raw/build.txt
- .agent/tasks/agents-custom-ui-20260616/raw/test-unit.txt
- .agent/tasks/agents-custom-ui-20260616/raw/test-integration.txt
- .agent/tasks/agents-custom-ui-20260616/raw/lint.txt
- .agent/tasks/agents-custom-ui-20260616/raw/dist-integrity.txt
- .agent/tasks/agents-custom-ui-20260616/raw/public-dist-integrity.txt
- .agent/tasks/agents-custom-ui-20260616/raw/deploy.txt
- .agent/tasks/agents-custom-ui-20260616/raw/screenshot-1.png

## Known gaps
- Existing unrelated production log line `GET /api/partnership/health ... 500` appeared before/around deployment checks and belongs to the partnership screen, not `/dashboard/agents`.
