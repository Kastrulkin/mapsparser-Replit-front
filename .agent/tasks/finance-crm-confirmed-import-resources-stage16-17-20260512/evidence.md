# Evidence Bundle: finance-crm-confirmed-import-resources-stage16-17-20260512

## Summary
- Overall status: PASS
- Last updated: 2026-05-12T16:25:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `/api/finance/crm/sync` now requires `confirm_preview_token` / `preview_token`.
  - `_validate_finance_crm_preview_confirmation` checks provider, period, token, and expiry.
- Gaps:
  - None.

### AC2
- Status: PASS
- Proof:
  - Sync fetches CRM data again and compares the fresh preview token to the confirmed token before importing.
  - `test_crm_preview_token_changes_when_dataset_changes` covers dataset drift.
- Gaps:
  - None.

### AC3
- Status: PASS
- Proof:
  - `crm_appointments_to_workplace_metrics` converts appointment resources into workplace rows.
  - `test_crm_appointments_build_workplace_metrics_from_resources` covers booked minutes, revenue, type, and available hours.
  - `test_crm_dataset_adds_workplace_rows_from_appointments` proves rows enter the import normalization flow.
- Gaps:
  - Provider schedule availability is only used when present in the payload.

### AC4
- Status: PASS
- Proof:
  - `python3 -m pytest tests/test_finance_crm.py -q`: 15 passed.
  - `python3 -m pytest tests/test_finance_crm.py tests/test_finance_imports.py tests/test_finance_kpis.py -q`: 28 passed.
  - `python3 -m py_compile src/core/finance_crm.py src/main.py`: passed.
- Gaps:
  - None.

### AC5
- Status: PASS
- Proof:
  - `FinanceCrmPanel` disables import until preview returns `preview_token`.
  - Button text changed to `Подтвердить импорт`; helper text explains preview-first flow.
  - `npm exec -- eslint src/components/FinanceCrmPanel.tsx`: passed.
  - `npm run build`: passed.
- Gaps:
  - None.

## Commands run
- `python3 -m pytest tests/test_finance_crm.py -q`
- `python3 -m py_compile src/core/finance_crm.py src/main.py`
- `python3 -m pytest tests/test_finance_crm.py tests/test_finance_imports.py tests/test_finance_kpis.py -q`
- `npm exec -- eslint src/components/FinanceCrmPanel.tsx`
- `npm run build`

## Raw artifacts
- .agent/tasks/finance-crm-confirmed-import-resources-stage16-17-20260512/raw/build.txt
- .agent/tasks/finance-crm-confirmed-import-resources-stage16-17-20260512/raw/test-unit.txt
- .agent/tasks/finance-crm-confirmed-import-resources-stage16-17-20260512/raw/test-integration.txt
- .agent/tasks/finance-crm-confirmed-import-resources-stage16-17-20260512/raw/lint.txt
- .agent/tasks/finance-crm-confirmed-import-resources-stage16-17-20260512/raw/screenshot-1.png

## Known gaps
- Live YCLIENTS/Altegio sync still needs real credentials and provider agreement.
- Schedule availability is mapped only from fields present in appointment/resource payloads; separate provider schedule endpoint remains a later step.
