# Evidence Bundle: finance-crm-preview-stage12-13-20260512

## Summary
- Overall status: PASS
- Last updated: 2026-05-12T18:55:00+03:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `src/main.py` adds `POST /api/finance/crm/preview`.
  - The endpoint fetches CRM data and builds preview, but does not create `finance_import_batches`.
- Gaps:
  - No real vendor sandbox credentials in this session.

### AC2
- Status: PASS
- Proof:
  - `src/core/finance_crm.py` adds `build_crm_sync_preview`.
  - Preview returns `dataset_counts`, `normalized_counts`, `valid_rows`, `failed_rows`, `preview_rows`, `errors`, `raw_samples`.
- Gaps:
  - Live payload mapping may need adjustment after first real response.

### AC3
- Status: PASS
- Proof:
  - `_safe_preview_item` masks keys containing `token`, `password`, `secret`, `authorization`.
  - `tests/test_finance_crm.py` covers token masking.
- Gaps:
  - None.

### AC4
- Status: PASS
- Proof:
  - `frontend/src/components/FinanceCrmPanel.tsx` adds "Проверить данные".
  - UI renders `CrmPreviewSummary` with counts, rows and errors.
- Gaps:
  - Browser screenshot not captured.

### AC5
- Status: PASS
- Proof:
  - Existing sync endpoint remains separate and still creates import batch only on explicit "Синхронизировать".
- Gaps:
  - None.

### AC6
- Status: PASS
- Proof:
  - `22 passed`.
  - Backend py_compile passed.
  - Targeted eslint passed.
  - Frontend production build passed.
- Gaps:
  - Full project lint not run due known unrelated legacy debt.

## Commands run
- `python3 -m pytest -q tests/test_finance_crm.py tests/test_finance_imports.py tests/test_finance_kpis.py`
- `python3 -m py_compile src/main.py src/core/finance_crm.py src/core/finance_imports.py src/core/finance_kpis.py`
- `cd frontend && npx eslint src/components/FinanceCrmPanel.tsx src/pages/dashboard/SettingsPage.tsx src/pages/dashboard/FinancePage.tsx`
- `cd frontend && npm run build`

## Raw artifacts
- .agent/tasks/finance-crm-preview-stage12-13-20260512/raw/build.txt
- .agent/tasks/finance-crm-preview-stage12-13-20260512/raw/test-unit.txt
- .agent/tasks/finance-crm-preview-stage12-13-20260512/raw/test-integration.txt
- .agent/tasks/finance-crm-preview-stage12-13-20260512/raw/lint.txt
- .agent/tasks/finance-crm-preview-stage12-13-20260512/raw/screenshot-1.png

## Known gaps
- No real YCLIENTS/Altegio sandbox credentials yet.
- First live contract sample may require endpoint/mapping refinements.
