# Evidence Bundle: agents-datahub-rich-files-polish-20260528

## Summary
- Overall status: PASS
- Last updated: 2026-05-28T07:31:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - Unit test `test_agent_source_ingestion_extracts_text_pdf_docx_xlsx_and_rejects_unsafe_files` covers TXT, PDF, DOCX, XLSX extraction.
  - Production smoke uploaded PDF, DOCX, XLSX and received ready sources with methods `pypdf`, `docx_xml`, `openpyxl`.
- Gaps:
  - None for v1 smoke coverage.

### AC2
- Status: PASS
- Proof:
  - Unit test verifies unsupported `.exe` and empty `.txt` readable errors.
  - Production smoke verifies `UNSUPPORTED_FILE_TYPE` and `EMPTY_FILE` responses.
- Gaps:
  - None.

### AC3
- Status: PASS
- Proof:
  - Production smoke calls `/sources/catalog` and finds connected ready sources: `Smoke PDF contract`, `Smoke DOCX contract`, `Smoke XLSX risks`.
- Gaps:
  - None.

### AC4
- Status: PASS
- Proof:
  - Production smoke creates a document agent, attaches rich files, starts a run, and verifies journal kinds `input`, `extraction`, `output`, `approval`.
  - Output details include `Источник анализа` and `Внешняя отправка`.
- Gaps:
  - LLM provider returned deterministic fallback in smoke, which is acceptable for safe runtime proof.

### AC5
- Status: PASS
- Proof:
  - Production smoke checks no `capability` step ran.
  - Output and result both report `external_dispatch_performed=false` and `dispatch_state=not_dispatched`.
- Gaps:
  - None.

### AC6
- Status: PASS
- Proof:
  - Production smoke printed `fixture_cleaned=true`.
  - Follow-up DB check returned zero smoke users and zero smoke businesses.
- Gaps:
  - None.

## Commands run
- `python3 -m py_compile scripts/smoke_agent_blueprint_rich_files_api.py`
- `python3 -m pytest -q tests/test_agent_blueprint_layer.py -k 'agent_source_ingestion or agent_datahub_catalog or generic_document_runner'`
- `python3 -m pytest -q tests/test_agent_blueprint_layer.py`
- `scripts/lint_backend_baseline.sh`
- `ssh ... 'cd /opt/seo-app && docker compose exec -T app ... python -' < scripts/smoke_agent_blueprint_rich_files_api.py`
- `ssh ... 'cd /opt/seo-app && docker compose ps && curl -I -sS http://localhost:8000 | head -5'`
- `ssh ... 'cd /opt/seo-app && docker compose logs --since 10m app | tail -80'`
- `ssh ... 'cd /opt/seo-app && docker compose exec -T app ... cleanup count check'`

## Raw artifacts
- .agent/tasks/agents-datahub-rich-files-polish-20260528/raw/smoke-py-compile.txt
- .agent/tasks/agents-datahub-rich-files-polish-20260528/raw/test-unit.txt
- .agent/tasks/agents-datahub-rich-files-polish-20260528/raw/test-agent-blueprint-layer-full.txt
- .agent/tasks/agents-datahub-rich-files-polish-20260528/raw/lint.txt
- .agent/tasks/agents-datahub-rich-files-polish-20260528/raw/prod-rich-files-smoke.txt
- .agent/tasks/agents-datahub-rich-files-polish-20260528/raw/prod-health-after-rich-files.txt
- .agent/tasks/agents-datahub-rich-files-polish-20260528/raw/prod-app-logs-after-rich-files.txt
- .agent/tasks/agents-datahub-rich-files-polish-20260528/raw/prod-fixture-cleanup-check.txt

## Known gaps
- GigaChat SSL warning still appears in logs under the existing explicit workaround. It did not block the smoke and is outside this Datahub-lite cycle.
