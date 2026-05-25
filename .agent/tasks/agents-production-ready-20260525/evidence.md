# Evidence Bundle: agents-production-ready-20260525

## Summary
- Overall status: PASS
- Last updated: 2026-05-25T08:30:00+00:00

## Acceptance criteria evidence

### AC1: Backend ingestion
- Status: PASS
- Proof:
  - Added `src/services/agent_source_ingestion.py`.
  - Supports text-like files, PDF via `pypdf`, DOCX via stdlib zip/XML, XLSX via `openpyxl`.
  - Enforces size and extension/MIME checks.
  - `tests/test_agent_blueprint_layer.py` covers txt/docx/xlsx extraction and unsafe extension rejection.

### AC2: Useful document agent output and version loop
- Status: PASS
- Proof:
  - Document run now exposes extracted context plus `summary`, `facts`, `fields`, `risks`, `next_questions`.
  - Production smoke created a document agent, uploaded a text source, ran it, approved final output, and created a feedback version.
  - Smoke result: `initial_version=1`, `feedback_version=3`, `approval_type=final_output`.

### AC3: Safety boundaries
- Status: PASS
- Proof:
  - Generic output has `external_dispatch_performed=false`.
  - Production smoke asserted no external dispatch.
  - `scripts/lint_backend_baseline.sh` verifies Agent Blueprint dispatch boundaries and ActionOrchestrator guardrails.

### AC4: System agents config
- Status: PASS
- Proof:
  - Production smoke used paid test business (`starter/active`) and saved booking/marketing agent config through `/api/business/profile`.
  - Smoke result: `system_agents_config_persisted=true`.

### AC5: Authenticated production UI smoke
- Status: PASS
- Proof:
  - Browser smoke logged in as temporary paid test user.
  - `/dashboard/agents` loaded without error after fixing missing `Zap` import.
  - UI showed one main `Создать агента` CTA, `Системные агенты`, `Пользовательские агенты`, `Ждут решения`, `Последние запуски`.
  - Run details showed input/extracted/result/review content with `Технический журнал` collapsed markers and without `payload_json` / `blueprint_version_id` in the main surface.
  - Browser console error log was empty after the fix.
  - Temporary production fixture was cleaned.

## Commands run
- `python3 -m pytest -q tests/test_agent_blueprint_layer.py`
- `scripts/lint_backend_baseline.sh`
- `cd frontend && npm run build`
- `docker compose up -d --build app worker` on `/opt/seo-app`
- `docker compose exec -T app env SMOKE_BASE_URL=http://localhost:8000 python scripts/smoke_agent_blueprint_document_api.py`
- Authenticated browser smoke on `https://localos.pro/dashboard/agents`

## Raw artifacts
- `.agent/tasks/agents-production-ready-20260525/raw/build.txt`
- `.agent/tasks/agents-production-ready-20260525/raw/test-unit.txt`
- `.agent/tasks/agents-production-ready-20260525/raw/test-integration.txt`
- `.agent/tasks/agents-production-ready-20260525/raw/lint.txt`

## Known gaps
- Browser smoke covered existing created document agent and run review, not full manual wizard clicks end-to-end, because production fixture creation was intentionally controlled through the smoke script and then cleaned.
- Server disk remains tight; old backup folder `.agent_untracked_backup_20260525` is 7.4G and should be moved off-box or reviewed separately.
