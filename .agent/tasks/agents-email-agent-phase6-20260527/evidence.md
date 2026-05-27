# Evidence Bundle: agents-email-agent-phase6-20260527

## Summary
- Overall status: PASS
- Last updated: 2026-05-27T08:15:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - Added `src/services/agent_email_llm.py`.
  - `src/services/agent_blueprint_workspace.py` routes email output generation through `draft_email_with_llm`.
  - `test_generic_email_runner_prepares_draft_and_never_dispatches` verifies a real email draft artifact.
- Gaps:
  - None.

### AC2
- Status: PASS
- Proof:
  - `draft_email_with_llm` normalizes `subject`, `body`, `checklist`, `assumptions`, `missing_info`, `rules_applied`, `provenance`, `analysis_source`, and `llm_analysis_used`.
  - Unit tests cover both LLM generator path and deterministic fallback.
  - Production smoke returned `analysis_source: gigachat`, `llm_analysis_used: true`, and a non-empty subject.
- Gaps:
  - None.

### AC3
- Status: PASS
- Proof:
  - Email version uses empty `capability_allowlist`.
  - Unit test verifies no capability steps are executed.
  - Production smoke returned `external_dispatch_performed: false` and run stopped on `final_output` approval.
- Gaps:
  - None.

### AC4
- Status: PASS
- Proof:
  - `_output_details` now includes `Тема письма`, `Чеклист`, and `Внешняя отправка` when present.
  - Production smoke validated journal detail labels include `Тема письма` and `Внешняя отправка`.
- Gaps:
  - None.

### AC5
- Status: PASS
- Proof:
  - Unit tests: `25 passed`.
  - Backend lint baseline passed.
  - Frontend build passed.
  - Backend deploy completed with `EXIT=0`.
  - Production email smoke passed and cleaned its fixture.
  - Server health returned `HTTP/1.1 200 OK`.
- Gaps:
  - Server logs include the existing Sber/GigaChat SSL workaround warning; this is pre-existing explicit production config, not a new Phase 6 regression.

## Commands run
- `python3 -m pytest -q tests/test_agent_blueprint_layer.py`
- `scripts/lint_backend_baseline.sh`
- `npm --prefix frontend run build`
- `scripts/deploy_backend_src.sh`
- `SMOKE_BASE_URL=http://localhost:8000 python /app/scripts/smoke_agent_blueprint_email_api.py`
- `docker compose ps` on server from `/opt/seo-app`
- `docker compose logs --since 10m app` on server from `/opt/seo-app`
- `curl -I http://localhost:8000` on server from `/opt/seo-app`

## Raw artifacts
- .agent/tasks/agents-email-agent-phase6-20260527/raw/build.txt
- .agent/tasks/agents-email-agent-phase6-20260527/raw/test-unit.txt
- .agent/tasks/agents-email-agent-phase6-20260527/raw/test-integration.txt
- .agent/tasks/agents-email-agent-phase6-20260527/raw/lint.txt
- .agent/tasks/agents-email-agent-phase6-20260527/raw/screenshot-1.png

## Known gaps
- Email sending/provider connection is intentionally not implemented.
- No authenticated browser UI click-through for the email agent was performed in this phase; API/runtime smoke passed.
