# Evidence Bundle: agents-table-agent-phase7-20260527

## Summary
- Overall status: PASS
- Last updated: 2026-05-27T08:42:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - Added `src/services/agent_table_analysis.py`.
  - `src/services/agent_blueprint_workspace.py` routes table output generation through `analyze_table_with_llm`.
  - `test_generic_table_runner_prepares_report_and_never_dispatches` verifies a table report artifact.
- Gaps:
  - None.

### AC2
- Status: PASS
- Proof:
  - `analyze_table_with_llm` normalizes `summary`, `exceptions`, `rows_to_review`, `recommendations`, `rules_applied`, `provenance`, `analysis_source`, and `llm_analysis_used`.
  - Unit tests cover both LLM generator path and deterministic fallback.
  - Production smoke returned `analysis_source: gigachat`, `llm_analysis_used: true`, `exceptions_count: 2`, `rows_to_review_count: 2`.
- Gaps:
  - None.

### AC3
- Status: PASS
- Proof:
  - Table version uses empty `capability_allowlist`.
  - Unit test verifies no capability steps are executed.
  - Production smoke returned `external_dispatch_performed: false` and run stopped on `final_output` approval.
- Gaps:
  - None.

### AC4
- Status: PASS
- Proof:
  - `_output_details` now includes `Исключений`, `Строк к проверке`, and `Внешняя отправка`.
  - Production smoke validated journal detail labels include `Исключений` and `Строк к проверке`.
- Gaps:
  - None.

### AC5
- Status: PASS
- Proof:
  - Unit tests: `28 passed`.
  - Backend lint baseline passed.
  - Frontend build passed.
  - Backend deploy completed with `EXIT=0`.
  - Production table smoke passed and cleaned its fixture.
  - Server health returned `HTTP/1.1 200 OK`.
- Gaps:
  - Server logs include the existing Sber/GigaChat SSL workaround warning; this is pre-existing explicit production config, not a new Phase 7 regression.

## Commands run
- `python3 -m pytest -q tests/test_agent_blueprint_layer.py`
- `scripts/lint_backend_baseline.sh`
- `npm --prefix frontend run build`
- `scripts/deploy_backend_src.sh`
- `SMOKE_BASE_URL=http://localhost:8000 python /app/scripts/smoke_agent_blueprint_table_api.py`
- `docker compose ps` on server from `/opt/seo-app`
- `docker compose logs --since 10m app` on server from `/opt/seo-app`
- `curl -I http://localhost:8000` on server from `/opt/seo-app`

## Raw artifacts
- .agent/tasks/agents-table-agent-phase7-20260527/raw/build.txt
- .agent/tasks/agents-table-agent-phase7-20260527/raw/test-unit.txt
- .agent/tasks/agents-table-agent-phase7-20260527/raw/test-integration.txt
- .agent/tasks/agents-table-agent-phase7-20260527/raw/lint.txt
- .agent/tasks/agents-table-agent-phase7-20260527/raw/screenshot-1.png

## Known gaps
- Table editing/export/import is intentionally not implemented.
- No authenticated browser UI click-through for the table agent was performed in this phase; API/runtime smoke passed.
