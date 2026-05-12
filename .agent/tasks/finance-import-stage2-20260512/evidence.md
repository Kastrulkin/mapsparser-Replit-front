# Evidence Bundle: finance-import-stage2-20260512

## Summary
- Overall status: PASS
- Last updated: 2026-05-12T14:55:00+03:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `finance_import_batches` added to `20260512_add_finance_first_step.py`.
  - `import_batch_id`, `external_id`, `duplicate_key` columns added to finance metric tables.
- Gaps:
  - Migration must be applied before production use.

### AC2
- Status: PASS
- Proof:
  - `POST /api/finance/import-preview` parses CSV/XLSX, suggests mapping, returns preview and errors.
  - Parser lives in `src/core/finance_imports.py`.
- Gaps:
  - Visual column mapping editor is not part of this stage.

### AC3
- Status: PASS
- Proof:
  - `POST /api/finance/import-file` creates batch, inserts valid rows, skips duplicate keys and returns counts.
- Gaps:
  - API integration test against a migrated DB was not run locally.

### AC4
- Status: PASS
- Proof:
  - `GET /api/finance/import-template` returns CSV template.
  - `finance_import_template_csv` is covered by tests.
- Gaps:
  - None.

### AC5
- Status: PASS
- Proof:
  - `frontend/src/components/FinanceImportPanel.tsx` added.
  - `FinancePage.tsx` renders import panel under finance onboarding.
- Gaps:
  - Authenticated browser smoke not run in this pass.

### AC6
- Status: PASS
- Proof:
  - After import, endpoint returns recalculated `dashboard`.
  - UI calls `onImported` to refresh finance blocks.
- Gaps:
  - None for stage 2.

### AC7
- Status: PASS
- Proof:
  - `tests/test_finance_imports.py` added.
  - `python3 -m pytest -q tests/test_finance_kpis.py tests/test_finance_imports.py` passed.
- Gaps:
  - None.

### AC8
- Status: PASS
- Proof:
  - `npm run build` from `frontend` passed.
- Gaps:
  - Existing Browserslist/Rollup warnings remain unrelated.

### AC9
- Status: PASS
- Proof:
  - The single pending migration now includes stage 1 and stage 2 schema, so pre-prod Alembic upgrade covers both.
- Gaps:
  - Production DB backup still required before deploy/migration.

## Commands run
- `python3 -m pytest -q tests/test_finance_kpis.py tests/test_finance_imports.py`
- `python3 -m py_compile src/main.py src/core/finance_kpis.py src/core/finance_imports.py alembic_migrations/versions/20260512_add_finance_first_step.py`
- `npm run build` from `frontend`

## Raw artifacts
- .agent/tasks/finance-import-stage2-20260512/raw/build.txt
- .agent/tasks/finance-import-stage2-20260512/raw/test-unit.txt
- .agent/tasks/finance-import-stage2-20260512/raw/test-integration.txt
- .agent/tasks/finance-import-stage2-20260512/raw/lint.txt
- .agent/tasks/finance-import-stage2-20260512/raw/screenshot-1.png

## Known gaps
- Production deploy still needs DB backup + Alembic migration.
- Authenticated browser smoke was not run in this pass.
- CRM connectors and visual mapping editor remain later stages.
