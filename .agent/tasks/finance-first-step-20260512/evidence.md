# Evidence Bundle: finance-first-step-20260512

## Summary
- Overall status: PASS
- Last updated: 2026-05-12T14:20:00+03:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `frontend/src/components/FinanceFirstStep.tsx` adds onboarding tabs for P&L, services, staff and workplaces.
  - `frontend/src/pages/dashboard/FinancePage.tsx` renders the onboarding block above legacy metrics.
- Gaps:
  - Authenticated browser smoke not run in this pass.

### AC2
- Status: PASS
- Proof:
  - `POST /api/finance/manual-entry` accepts manual entries, service metrics, staff metrics, workplaces and workplace metrics.
- Gaps:
  - File import and CRM connector remain non-goals for stage 1.

### AC3
- Status: PASS
- Proof:
  - `src/core/finance_kpis.py` calculates revenue, expenses, operating profit, margin, gross profit, gross margin and service KPI.
  - `tests/test_finance_kpis.py` covers core formulas.
- Gaps:
  - None for stage 1.

### AC4
- Status: PASS
- Proof:
  - `finance_workplaces` and `finance_workplace_metrics` migration tables added.
  - `calculate_finance_snapshot` calculates workplace occupancy and idle hours.
- Gaps:
  - None for stage 1.

### AC5
- Status: PASS
- Proof:
  - `calculate_finance_snapshot` returns `revenue_per_workplace` and `revenue_per_workplace_hour`.
  - UI displays "Выручка на кресло" and "Кресло-час".
- Gaps:
  - None for stage 1.

### AC6
- Status: PASS
- Proof:
  - `break_even_revenue` and `daily_revenue_target` are calculated and shown in KPI cards.
- Gaps:
  - Uses 22 working days as stage-1 assumption.

### AC7
- Status: PASS
- Proof:
  - `calculate_data_quality` returns score, missing fields, approximate KPI and blocked KPI names.
  - UI shows "Качество данных" with missing and approximate lists.
- Gaps:
  - None for stage 1.

### AC8
- Status: PASS
- Proof:
  - `build_finance_recommendations` returns red-zone recommendations.
  - UI renders "Красные зоны и следующие действия".
- Gaps:
  - Thresholds are code-configured in stage 1; per-business threshold settings can be later.

### AC9
- Status: PASS
- Proof:
  - Division by zero returns `null` and explanations.
  - `test_finance_snapshot_handles_division_by_zero_with_explanations` passes.
- Gaps:
  - None.

### AC10
- Status: PASS
- Proof:
  - `tests/test_finance_kpis.py` added with 5 tests for formulas, workplace metrics, low-margin classification, division by zero and recommendations.
- Gaps:
  - API integration tests can be added after migration is applied in a test DB.

### AC11
- Status: PASS
- Proof:
  - `docs/FINANCE_MODULE.md` documents data model, formulas, workplaces, quality, API and non-goals.
- Gaps:
  - None.

## Commands run
- `python3 -m pytest -q tests/test_finance_kpis.py`
- `npm run build` from `frontend`
- `python3 -m py_compile src/main.py src/core/finance_kpis.py`
- Limited Playwright smoke against protected `/dashboard/finance`; no console/page errors before auth gate.

## Raw artifacts
- .agent/tasks/finance-first-step-20260512/raw/build.txt
- .agent/tasks/finance-first-step-20260512/raw/test-unit.txt
- .agent/tasks/finance-first-step-20260512/raw/test-integration.txt
- .agent/tasks/finance-first-step-20260512/raw/lint.txt
- .agent/tasks/finance-first-step-20260512/raw/screenshot-1.png

## Known gaps
- Migration must be applied before the new API is used in an environment.
- Authenticated browser smoke was not run in this pass.
- Stage 1 intentionally does not include CRM connectors or file import wizard.
