# Evidence Bundle: agents-document-llm-analysis-phase3-20260525

## Summary
- Overall status: PASS
- Last updated: 2026-05-25T19:12:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `src/services/agent_blueprint_workspace.py` passes extracted uploaded/internal source items into `analyze_document_sources_with_llm`.
  - `src/services/agent_document_llm.py` builds prompt context from `raw.text` first, then source summaries.

### AC2
- Status: PASS
- Proof:
  - `src/services/agent_document_llm.py` calls `analyze_text_with_gigachat` with `task_type="agent_document_analysis"`.
  - Unit test `test_agent_document_llm_analysis_uses_generator_rules_and_provenance` verifies LLM-shaped summary/risks/facts/fields output.
  - Production smoke returned `"analysis_source": "gigachat"` and `"llm_analysis_used": true`.

### AC3
- Status: PASS
- Proof:
  - Prompt includes `workflow_description`, `extraction_rules`, `processing_rules`, `output_format`, `manual_control`, and recent feedback notes.
  - Unit test asserts processing rules and source name are present in the generated prompt.

### AC4
- Status: PASS
- Proof:
  - `analyze_document_sources_with_llm` catches provider failures and returns `analysis_source="deterministic_fallback"`.
  - Unit test `test_agent_document_llm_analysis_falls_back_without_external_dispatch` covers fallback.

### AC5
- Status: PASS
- Proof:
  - Output artifact payload now includes `analysis_source`, `llm_analysis_used`, `provenance`, `external_dispatch_performed=false`, and `dispatch_state="not_dispatched"`.
  - Server smoke checks these fields and reported provenance `["Smoke contract"]`.

### AC6
- Status: PASS
- Proof:
  - Existing final approval path completed in production smoke.
  - Feedback created a newer version: initial version `1`, feedback version `3`.

### AC7
- Status: PASS
- Proof:
  - Unit tests: `20 passed`.
  - Lint baseline: PASS.
  - Backend deploy: PASS.
  - Server document smoke: PASS.

## Commands run
- `python3 -m pytest -q tests/test_agent_blueprint_layer.py`
- `scripts/lint_backend_baseline.sh`
- `python3 scripts/smoke_agent_blueprint_document_api.py` locally, expected failure because local `DATABASE_URL` is unset.
- `git commit -m "Add document agent LLM analysis"`
- `git push`
- `scripts/deploy_backend_src.sh`
- `ssh root@80.78.242.105 'cd /opt/seo-app && docker compose cp scripts/smoke_agent_blueprint_document_api.py app:/app/scripts/smoke_agent_blueprint_document_api.py && docker compose exec -T app env SMOKE_BASE_URL=http://localhost:8000 python /app/scripts/smoke_agent_blueprint_document_api.py'`
- `ssh root@80.78.242.105 'cd /opt/seo-app && docker compose ps && docker compose logs --since 15m app | tail -n 160 && curl -I http://localhost:8000'`

## Raw artifacts
- .agent/tasks/agents-document-llm-analysis-phase3-20260525/raw/build.txt
- .agent/tasks/agents-document-llm-analysis-phase3-20260525/raw/test-unit.txt
- .agent/tasks/agents-document-llm-analysis-phase3-20260525/raw/test-integration.txt
- .agent/tasks/agents-document-llm-analysis-phase3-20260525/raw/lint.txt
- .agent/tasks/agents-document-llm-analysis-phase3-20260525/raw/deploy.txt

## Known gaps
- Local document smoke still requires a real PostgreSQL `DATABASE_URL`, so it is validated in the server Docker/Postgres runtime instead.
- LLM quality is provider-dependent; deterministic fallback keeps the run usable if GigaChat is unavailable.
