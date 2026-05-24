# Evidence Bundle: operator-sprint40-refresh-billing-polish-20260524

## Summary
- Overall status: PASS
- Last updated: 2026-05-24T15:23:09Z

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `build_refresh_result_status` includes `billing_state`.
  - `list_refresh_jobs` includes each job billing state and billing totals in summary.
- Gaps:
  - None.

### AC2
- Status: PASS
- Proof:
  - Billing state includes reservation, reserved/charged/released/outstanding/overage credits, provider actual cost, multiplier, and actual credits.
  - `tests/test_operator_refresh_result.py` covers charged billing state from reservation metadata.
- Gaps:
  - None.

### AC3
- Status: PASS
- Proof:
  - `settle_apify_actual_cost` writes provider actual cost, actual credits, overage, provider run id, and multiplier into reservation metadata.
  - `tests/test_operator_apify_settlement.py` checks settlement metadata update.
- Gaps:
  - Old settlements without metadata will show only reservation credit fields.

### AC4
- Status: PASS
- Proof:
  - `OperatorPage.tsx` renders refresh billing details in the single result card and recent refresh job cards.
  - Frontend build passed.
- Gaps:
  - No authenticated browser session was used to inspect a real paid refresh job.

## Commands run
- `python3 -m py_compile src/services/operator_content_history.py src/services/operator_refresh_result.py src/services/operator_apify_settlement.py src/services/operator_news_generation.py src/services/operator_social_post_generation.py src/api/operator_api.py`
- `PYTHONPATH=src:. python3 -m pytest -q tests/test_operator_refresh_result.py tests/test_operator_apify_settlement.py`
- `cd frontend && npm run build`
- `scripts/lint_backend_baseline.sh`
- `git diff --check`

## Raw artifacts
- .agent/tasks/operator-sprint40-refresh-billing-polish-20260524/raw/build.txt
- .agent/tasks/operator-sprint40-refresh-billing-polish-20260524/raw/test-unit.txt
- .agent/tasks/operator-sprint40-refresh-billing-polish-20260524/raw/test-integration.txt
- .agent/tasks/operator-sprint40-refresh-billing-polish-20260524/raw/lint.txt
- .agent/tasks/operator-sprint40-refresh-billing-polish-20260524/raw/screenshot-1.png

## Known gaps
- Old settlements without metadata will show only reservation credit fields.
- No authenticated browser inspection of a real paid refresh job was run.
