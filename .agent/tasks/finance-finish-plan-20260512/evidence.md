# Evidence Bundle: finance-finish-plan-20260512

## Summary
- Overall status: VALID
- Last updated: 2026-05-12T19:45:00+03:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `build_finance_recommendations` now returns `localos_actions`.
  - `FinanceFirstStep` renders "Что сделать в LocalOS" links inside recommendation cards.
- Gaps:
  - None.

### AC2
- Status: PASS
- Proof:
  - `CRMConnector.fetch_schedules` added to the adapter contract.
  - `crm_schedules_to_workplace_metrics` normalizes available workplace minutes from schedule rows and time ranges.
  - CRM preview dataset counts now include `schedules`.
- Gaps:
  - Real YCLIENTS/Altegio schedule payload still needs sandbox/live validation with issued credentials.

### AC3
- Status: PASS
- Proof:
  - Import wizard now shows file/preview/import steps.
  - Import is disabled until preview exists, has valid rows and mapping is not stale.
  - Mapping edits require another preview before import.
- Gaps:
  - None.

### AC4
- Status: PASS
- Proof:
  - `docs/FINANCE_MODULE.md` documents schedules/resources, LocalOS action links and the real-business CRM validation checklist.
- Gaps:
  - None.

### AC5
- Status: PASS
- Proof:
  - `python3 -m pytest tests/test_finance_kpis.py tests/test_finance_imports.py tests/test_finance_crm.py -q`: 29 passed.
  - `npm exec -- eslint src/components/FinanceFirstStep.tsx src/components/FinanceImportPanel.tsx src/components/FinanceCrmPanel.tsx src/pages/dashboard/FinancePage.tsx`: passed.
  - `npm run build`: passed.
  - `python3 -m compileall -q src/core/finance_crm.py src/core/finance_kpis.py`: passed.
- Gaps:
  - Browser opened `/dashboard/finance` locally and reached the expected login page because there is no local auth session.

## Commands run
- `python3 -m pytest tests/test_finance_kpis.py tests/test_finance_imports.py tests/test_finance_crm.py -q`
- `cd frontend && npm exec -- eslint src/components/FinanceFirstStep.tsx src/components/FinanceImportPanel.tsx src/components/FinanceCrmPanel.tsx src/pages/dashboard/FinancePage.tsx`
- `cd frontend && npm run build`
- `python3 -m compileall -q src/core/finance_crm.py src/core/finance_kpis.py`
- Browser smoke: `http://127.0.0.1:5175/dashboard/finance`

## Raw artifacts
- .agent/tasks/finance-finish-plan-20260512/raw/build.txt
- .agent/tasks/finance-finish-plan-20260512/raw/test-unit.txt
- .agent/tasks/finance-finish-plan-20260512/raw/test-integration.txt
- .agent/tasks/finance-finish-plan-20260512/raw/lint.txt
- .agent/tasks/finance-finish-plan-20260512/raw/screenshot-1.png

## Known gaps
- Live CRM sync still requires real credentials and sandbox/live payload approval.
- Local browser smoke could not enter the dashboard without an auth session.
