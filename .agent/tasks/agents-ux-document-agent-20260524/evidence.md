# Evidence Bundle: agents-ux-document-agent-20260524

## Summary
- Overall status: PASS
- Last updated: 2026-05-24T19:45:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `frontend/src/pages/dashboard/AgentBlueprintsPage.tsx` now has `AgentBuilderPanel`, explicit scenarios for documents/email/tables/outreach/reviews/partnerships/services/booking, wizard fields, and `Данные агента при создании`.
  - Primary UI keeps JSON behind `Технический журнал`.
- Gaps:
  - Authenticated visual smoke was blocked by missing browser session login.

### AC2
- Status: PASS
- Proof:
  - `src/services/agent_blueprint_draft_builder.py` accepts `preferred_category` and preserves safe empty capability allowlist for generic agents.
  - `src/api/agent_blueprints_api.py` passes explicit `category` from draft API.
  - Frontend saves setup and text/file/internal sources immediately after creating a blueprint.
  - `tests/test_agent_blueprint_layer.py::test_generic_document_runner_uses_sources_and_stops_for_final_approval` covers document run artifacts and final approval stop.
- Gaps:
  - Binary PDF/DOCX/XLSX extraction remains text-export/light metadata only in v1.

### AC3
- Status: PASS
- Proof:
  - `AgentRunReviewPanel` now shows `Как настроен агент`, `Источники`, and `HumanPayloadView` for extracted/result data before raw JSON.
  - Technical payload remains in collapsed `Технический журнал`.
- Gaps:
  - Needs authenticated browser pass to inspect real populated run visually.

### AC4
- Status: PASS
- Proof:
  - `scripts/lint_backend_baseline.sh` checks generic builder markers, safe blueprint runtime, no direct dispatcher call, and UI markers.
  - `scripts/lint_backend_baseline.sh` passed.
- Gaps:
  - No production data smoke was run in this cycle.

## Commands run
- `python3 -m py_compile src/api/agent_blueprints_api.py src/services/agent_blueprint_draft_builder.py src/services/agent_blueprint_workspace.py src/services/agent_blueprint_runner.py`
- `PYTHONPATH=src:. python3 -m pytest -q tests/test_agent_blueprint_layer.py` -> 13 passed
- `npm --prefix frontend run build` -> passed
- `scripts/lint_backend_baseline.sh` -> passed
- `PYTHONPATH=src:. python3 -m pytest -q tests/test_agent_blueprint_layer.py tests/test_operator_chat_fallback_api.py tests/test_operator_intent_ai_router.py` -> 25 passed
- Browser opened `http://127.0.0.1:5174/dashboard/agents`; app redirected to login due missing authenticated session.

## Raw artifacts
- .agent/tasks/agents-ux-document-agent-20260524/raw/build.txt
- .agent/tasks/agents-ux-document-agent-20260524/raw/test-unit.txt
- .agent/tasks/agents-ux-document-agent-20260524/raw/test-integration.txt
- .agent/tasks/agents-ux-document-agent-20260524/raw/lint.txt
- .agent/tasks/agents-ux-document-agent-20260524/raw/screenshot-1.png

## Known gaps
- Authenticated UI smoke still needs a real logged-in browser session or explicit test credentials.
- Generic document v1 handles pasted text and text-readable files; deeper PDF/DOCX/XLSX parsing is still a separate implementation task.
