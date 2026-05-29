# Evidence Bundle: agents-rima-like-product-finish-20260529

## Summary
- Overall status: PASS
- Last updated: 2026-05-29T08:05:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - Production `smoke_agent_builder_dialog_api.py` created a document blueprint from a natural-language dialog; initial questions reduced from 2 to 0 after clarification.
  - Authenticated browser smoke verified dialog builder, preview, clarifying state, safety copy, and create-from-preview flow.
- Gaps:
  - None for current v1.

### AC2
- Status: PASS
- Proof:
  - Frontend build includes `GenericRunProgress`, `AgentRunReviewPanel`, `JournalEntryCard`, human result rendering, and technical payload only under `Технический журнал`.
  - Unit test verifies human-readable journal labels including `Источник анализа`, `Использованные источники`, and `Внешняя отправка`.
- Gaps:
  - None.

### AC3
- Status: PASS
- Proof:
  - Backend review now returns additive `used_sources`.
  - Frontend shows `Использовано в последнем запуске`, `Подключено к агенту`, and `Доступно в LocalOS`.
  - Unit test verifies only sources actually referenced by run artifacts are included in used sources.
- Gaps:
  - None.

### AC4
- Status: PASS
- Proof:
  - Existing `VersionSummary` shows active version, changed fields, run-this-version, activate, and rollback controls.
  - Full agent blueprint test suite passed after changes.
- Gaps:
  - No additional backend work needed in this cycle.

### AC5
- Status: PASS
- Proof:
  - Production email smoke produced subject/body and waited for final output approval with `external_dispatch_performed=false`.
  - Production table smoke produced exceptions/rows-to-review and waited for approval with no external dispatch.
  - Production reviews smoke produced reply drafts, `publish_state=not_published`, and no external dispatch.
- Gaps:
  - None.

### AC6
- Status: PASS
- Proof:
  - Production generic boundaries smoke checked documents/email/tables/reviews; `dispatcher_started=false`, `external_dispatch_performed=false`, `approvals_required=true`.
- Gaps:
  - None.

### AC7
- Status: PASS
- Proof:
  - Backend restarted on server after clean `git pull`.
  - Frontend dist deployed and verified by deploy script.
  - Production health returned `HTTP/1.1 200 OK`.
  - Production fixture cleanup checks returned zero smoke users/businesses.
- Gaps:
  - GigaChat SSL warning remains the known explicit workaround.

## Commands run
- `python3 -m py_compile src/services/agent_blueprint_workspace.py scripts/smoke_agent_builder_dialog_api.py scripts/smoke_agent_blueprint_email_api.py scripts/smoke_agent_blueprint_table_api.py scripts/smoke_agent_blueprint_reviews_api.py scripts/smoke_agent_blueprint_generic_boundaries.py`
- `python3 -m pytest -q tests/test_agent_blueprint_layer.py`
- `scripts/lint_backend_baseline.sh`
- `npm --prefix frontend run build`
- `ssh ... 'cd /opt/seo-app && git pull --ff-only origin main ... docker compose restart app worker ...'`
- `scripts/deploy_frontend_dist.sh`
- production API smokes: dialog builder, email, table, reviews, generic boundaries
- authenticated browser smoke on `/dashboard/agents`
- production fixture cleanup checks

## Raw artifacts
- .agent/tasks/agents-rima-like-product-finish-20260529/raw/build.txt
- .agent/tasks/agents-rima-like-product-finish-20260529/raw/test-unit.txt
- .agent/tasks/agents-rima-like-product-finish-20260529/raw/test-integration.txt
- .agent/tasks/agents-rima-like-product-finish-20260529/raw/lint.txt
- .agent/tasks/agents-rima-like-product-finish-20260529/raw/screenshot-1.png
- .agent/tasks/agents-rima-like-product-finish-20260529/raw/test-agent-blueprint-layer-full.txt
- .agent/tasks/agents-rima-like-product-finish-20260529/raw/py-compile.txt
- .agent/tasks/agents-rima-like-product-finish-20260529/raw/deploy-backend.txt
- .agent/tasks/agents-rima-like-product-finish-20260529/raw/deploy-backend-restart.txt
- .agent/tasks/agents-rima-like-product-finish-20260529/raw/frontend-dist-integrity.txt
- .agent/tasks/agents-rima-like-product-finish-20260529/raw/deploy-frontend.txt
- .agent/tasks/agents-rima-like-product-finish-20260529/raw/prod-builder-dialog-smoke.txt
- .agent/tasks/agents-rima-like-product-finish-20260529/raw/prod-generic-agent-smokes.txt
- .agent/tasks/agents-rima-like-product-finish-20260529/raw/prod-cleanup-health-logs.txt
- .agent/tasks/agents-rima-like-product-finish-20260529/raw/prod-ui-browser-smoke.txt
- .agent/tasks/agents-rima-like-product-finish-20260529/raw/prod-ui-cleanup.txt

## Known gaps
- GigaChat SSL warning still appears in logs under the existing explicit workaround; it did not block smokes.
