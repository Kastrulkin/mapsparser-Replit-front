# Evidence Bundle: agents-generic-run-detail-phase11-20260527

## Summary
- Overall status: PASS
- Last updated: 2026-05-27T16:20:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - Added `GenericRunProgress` for non-outreach blueprint categories.
  - Browser smoke verified `Путь документы-агента`, `Входные данные`, `Что понял`, `Результат`, and `Ручной контроль`.
- Gaps:
  - Browser smoke used document agent as representative generic flow; email/table/reviews share the same component and test guardrail.

### AC2
- Status: PASS
- Proof:
  - Runtime steps/artifacts/approvals are now behind `Техническая сводка запуска`.
  - Raw payload remains behind `Технический журнал`.
- Gaps:
  - In this document fixture `activeRun` was not selected in the frontend, so `Техническая сводка запуска` did not render; raw JSON remained hidden behind per-entry `Технический журнал`.

### AC3
- Status: PASS
- Proof:
  - Added `resultFieldLabels` and priority rendering for `summary`, `risks`, `facts`, `fields`, email subject/body, table exceptions, review reply drafts, etc.
  - Browser smoke verified readable document fields including `Название результата`, `Риски`, `Факты`, `Поля`.
- Gaps:
  - None.

### AC4
- Status: PASS
- Proof:
  - `python3 -m pytest -q tests/test_agent_blueprint_layer.py` -> 32 passed.
  - `npm --prefix frontend run build` -> passed.
  - `scripts/lint_backend_baseline.sh` -> passed.
- Gaps:
  - None.

### AC5
- Status: PASS
- Proof:
  - Frontend dist deployed with tar-over-ssh partial frontend deploy.
  - Live root returned 200 and referenced `/assets/index-DSQ2R5r3.js`.
  - Authenticated browser smoke verified production `/dashboard/agents` with a document agent run detail.
- Gaps:
  - Initial full `scp` deploy path was too slow and was replaced by tar-over-ssh.

### AC6
- Status: PASS
- Proof:
  - Production document fixture cleanup returned `cleanup_ok`.
  - Cleanup verification returned zero rows for test user, business, blueprint, and run.
- Gaps:
  - None.

## Commands run
- `python3 -m pytest -q tests/test_agent_blueprint_layer.py`
- `npm --prefix frontend run build`
- `scripts/lint_backend_baseline.sh`
- `scripts/deploy_frontend_dist.sh --build` attempted; upload was too slow.
- Frontend deploy via tar-over-ssh to `/opt/seo-app`, then sync into app container.
- Production document-agent fixture setup through Agent Blueprint APIs.
- Authenticated browser smoke on `/dashboard/agents`.
- Production fixture cleanup and zero-row verification.

## Raw artifacts
- .agent/tasks/agents-generic-run-detail-phase11-20260527/raw/build.txt
- .agent/tasks/agents-generic-run-detail-phase11-20260527/raw/test-unit.txt
- .agent/tasks/agents-generic-run-detail-phase11-20260527/raw/test-integration.txt
- .agent/tasks/agents-generic-run-detail-phase11-20260527/raw/lint.txt
- .agent/tasks/agents-generic-run-detail-phase11-20260527/raw/screenshot-1.png
- .agent/tasks/agents-generic-run-detail-phase11-20260527/raw/deploy.txt
- .agent/tasks/agents-generic-run-detail-phase11-20260527/raw/prod-document-ui-fixture.txt
- .agent/tasks/agents-generic-run-detail-phase11-20260527/raw/browser-smoke.txt
- .agent/tasks/agents-generic-run-detail-phase11-20260527/raw/prod-document-ui-cleanup.txt
- .agent/tasks/agents-generic-run-detail-phase11-20260527/raw/prod-document-ui-cleanup-verify.txt

## Known gaps
- Browser smoke verified the document generic flow. Email/table/reviews are covered by shared UI component and unit guardrails, but not separate authenticated UI fixtures in this phase.
