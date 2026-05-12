# Evidence Bundle: finance-crm-contract-clients-stage14-15-20260512

## Summary
- Overall status: PASS
- Last updated: 2026-05-12T19:15:00+03:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - Added `tests/fixtures/crm/yclients_contract_sample.json`.
  - Fixture contains synthetic clients and placeholder phones.
- Gaps:
  - Real sandbox payload still needed later.

### AC2
- Status: PASS
- Proof:
  - `load_crm_contract_fixture` loads fixture and builds preview.
  - `test_crm_contract_fixture_locks_preview_mapping` asserts dataset and normalized counts.
- Gaps:
  - None.

### AC3
- Status: PASS
- Proof:
  - `crm_appointments_to_staff_metrics` aggregates appointments into staff metrics.
  - Tests cover visits, no-show, rebooking, revenue and booked minutes.
- Gaps:
  - Available minutes still require CRM schedule/resources or manual data.

### AC4
- Status: PASS
- Proof:
  - `crm_appointments_to_service_metrics` aggregates completed appointment services.
  - Tests cover service visits, revenue and avg price.
- Gaps:
  - Material cost/staff payout still require CRM salary/material integrations or manual enrichment.

### AC5
- Status: PASS
- Proof:
  - Fixture uses synthetic names and placeholder phones.
  - Preview sample masking from prior stage still masks secrets.
- Gaps:
  - Need keep this rule for future real payload fixtures.

### AC6
- Status: PASS
- Proof:
  - `25 passed`.
  - Backend py_compile passed.
  - Targeted eslint passed.
  - Frontend production build passed.
- Gaps:
  - Full project lint not run due known unrelated legacy debt.

## Commands run
- `python3 -m pytest -q tests/test_finance_crm.py tests/test_finance_imports.py tests/test_finance_kpis.py`
- `python3 -m py_compile src/core/finance_crm.py src/core/finance_imports.py src/core/finance_kpis.py src/main.py`
- `cd frontend && npx eslint src/components/FinanceCrmPanel.tsx src/pages/dashboard/SettingsPage.tsx src/pages/dashboard/FinancePage.tsx`
- `cd frontend && npm run build`

## Raw artifacts
- .agent/tasks/finance-crm-contract-clients-stage14-15-20260512/raw/build.txt
- .agent/tasks/finance-crm-contract-clients-stage14-15-20260512/raw/test-unit.txt
- .agent/tasks/finance-crm-contract-clients-stage14-15-20260512/raw/test-integration.txt
- .agent/tasks/finance-crm-contract-clients-stage14-15-20260512/raw/lint.txt
- .agent/tasks/finance-crm-contract-clients-stage14-15-20260512/raw/screenshot-1.png

## Known gaps
- First real YCLIENTS/Altegio sandbox response may require field mapping refinements.
- Available minutes, materials and payouts still need CRM-specific data or manual enrichment.
