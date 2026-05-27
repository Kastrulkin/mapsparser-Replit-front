# Evidence Bundle: agents-reviews-agent-phase8-20260527

## Summary
- Overall status: PASS
- Last updated: 2026-05-27T08:54:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - Added `src/services/agent_review_reply_analysis.py` with LLM-backed and deterministic fallback reply drafting.
  - `tests/test_agent_blueprint_layer.py::test_generic_reviews_runner_prepares_reply_drafts_and_never_publishes` proves a reviews blueprint produces `reply_drafts`.
  - Production smoke produced `reply_drafts_count: 2`.

### AC2
- Status: PASS
- Proof:
  - Unit tests assert `manual_review_reasons`, `checklist`, `provenance`, `analysis_source`, and LLM/fallback flags.
  - Production smoke returned `analysis_source: gigachat`, `llm_analysis_used: true`, and `manual_review_reasons_count: 3`.

### AC3
- Status: PASS
- Proof:
  - Runner test asserts no capability steps are executed.
  - Unit and production smoke assert `external_dispatch_performed: false`, `delivery_state: not_dispatched`, and `publish_state: not_published`.
  - Production smoke stopped at `approval_type: final_output`.

### AC4
- Status: PASS
- Proof:
  - `src/services/agent_blueprint_workspace.py` now exposes output details for `Черновиков ответов`, `Причин ручной проверки`, and `Публикация`.
  - Production smoke confirmed those journal labels.

### AC5
- Status: PASS
- Proof:
  - Unit: 31 passed.
  - Lint baseline: pass.
  - Frontend build: pass.
  - Backend deploy: exit 0.
  - Production targeted smoke: pass with fixture cleanup.

## Commands run
- `python3 -m pytest -q tests/test_agent_blueprint_layer.py`
- `scripts/lint_backend_baseline.sh`
- `npm --prefix frontend run build`
- `scripts/deploy_backend_src.sh`
- `docker compose exec -T app env SMOKE_BASE_URL=http://localhost:8000 python /app/scripts/smoke_agent_blueprint_reviews_api.py`
- `docker compose ps && docker compose logs --since 10m app | tail -n 140 && curl -I http://localhost:8000`

## Raw artifacts
- .agent/tasks/agents-reviews-agent-phase8-20260527/raw/build.txt
- .agent/tasks/agents-reviews-agent-phase8-20260527/raw/test-unit.txt
- .agent/tasks/agents-reviews-agent-phase8-20260527/raw/test-integration.txt
- .agent/tasks/agents-reviews-agent-phase8-20260527/raw/lint.txt
- .agent/tasks/agents-reviews-agent-phase8-20260527/raw/screenshot-1.png

## Known gaps
- Publishing provider integration is intentionally not implemented.
- UI click-through for a reviews agent was not part of this backend-focused phase.
- Server logs still show the previously known explicit GigaChat SSL verification workaround warning.
