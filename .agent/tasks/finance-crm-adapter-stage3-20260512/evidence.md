# Evidence Bundle: finance-crm-adapter-stage3-20260512

## Summary
- Overall status: PASS
- Last updated: 2026-05-12T15:20:00+03:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `src/core/finance_crm.py` defines `CRMConnector` with fetch methods for appointments, payments, clients, services, staff and workplaces.
- Gaps:
  - None for stage 3.

### AC2
- Status: PASS
- Proof:
  - `MockDemoCRMAdapter` returns payments, services, staff and workplaces without external calls.
- Gaps:
  - Real providers remain planned.

### AC3
- Status: PASS
- Proof:
  - `finance_crm_connections` added to `20260512_add_finance_first_step.py`.
- Gaps:
  - Migration must be applied before production use.

### AC4
- Status: PASS
- Proof:
  - `GET /api/finance/crm/providers`
  - `POST /api/finance/crm/connect`
  - `GET /api/finance/crm/status`
  - `POST /api/finance/crm/sync`
- Gaps:
  - No migrated-DB integration test in this pass.

### AC5
- Status: PASS
- Proof:
  - CRM dataset goes through `crm_dataset_to_finance_rows`, then `_insert_finance_import_item`.
  - `finance_import_batches` stores CRM sync as `source_type = crm`.
- Gaps:
  - None for stage 3.

### AC6
- Status: PASS
- Proof:
  - CRM rows include `external_id`; normalization creates `duplicate_key`.
  - Sync uses `_finance_import_duplicate_exists` before inserts.
- Gaps:
  - None.

### AC7
- Status: PASS
- Proof:
  - `frontend/src/components/FinanceCrmPanel.tsx` added.
  - `FinancePage.tsx` renders the CRM panel and refreshes finance data after sync.
- Gaps:
  - Authenticated browser smoke not run in this pass.

### AC8
- Status: PASS
- Proof:
  - `tests/test_finance_crm.py` added.
  - `python3 -m pytest -q tests/test_finance_kpis.py tests/test_finance_imports.py tests/test_finance_crm.py` passed.
- Gaps:
  - None.

### AC9
- Status: PASS
- Proof:
  - `npm run build` from `frontend` passed.
- Gaps:
  - Existing Browserslist/Rollup warnings remain unrelated.

## Commands run
- `python3 -m pytest -q tests/test_finance_kpis.py tests/test_finance_imports.py tests/test_finance_crm.py`
- `python3 -m py_compile src/main.py src/core/finance_kpis.py src/core/finance_imports.py src/core/finance_crm.py alembic_migrations/versions/20260512_add_finance_first_step.py`
- `npm run build` from `frontend`

## Raw artifacts
- .agent/tasks/finance-crm-adapter-stage3-20260512/raw/build.txt
- .agent/tasks/finance-crm-adapter-stage3-20260512/raw/test-unit.txt
- .agent/tasks/finance-crm-adapter-stage3-20260512/raw/test-integration.txt
- .agent/tasks/finance-crm-adapter-stage3-20260512/raw/lint.txt
- .agent/tasks/finance-crm-adapter-stage3-20260512/raw/screenshot-1.png

## Known gaps
- Production deploy still needs DB backup + Alembic migration.
- Authenticated browser smoke was not run in this pass.
- Real YCLIENTS/Altegio adapters remain later stages.
