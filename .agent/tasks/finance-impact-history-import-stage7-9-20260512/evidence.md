# Evidence Bundle: finance-impact-history-import-stage7-9-20260512

## Summary
- Overall status: PASS
- Last updated: 2026-05-12T16:35:00+03:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `src/main.py` adds `_build_finance_impact` and `GET /api/finance/impact`.
  - Dashboard payload includes `action_impact`.
- Gaps:
  - Impact is directional comparison, not causal attribution.

### AC2
- Status: PASS
- Proof:
  - `src/main.py` adds `_build_finance_history` and `GET /api/finance/history`.
  - History supports bounded month windows up to 12 months.
- Gaps:
  - Live DB smoke was not run locally.

### AC3
- Status: PASS
- Proof:
  - `frontend/src/components/FinanceFirstStep.tsx` renders `ImpactPanel` and `HistoryPanel`.
  - UI supports 3, 6 and 12 month history switches.
- Gaps:
  - Authenticated browser visual QA was not run in this session.

### AC4
- Status: PASS
- Proof:
  - `src/core/finance_imports.py` adds import template profiles.
  - `src/main.py` adds `GET /api/finance/import-templates` and profile-aware template download.
  - `frontend/src/components/FinanceImportPanel.tsx` adds template selector and manual mapping editor.
  - `tests/test_finance_imports.py` covers template profiles.
- Gaps:
  - Real CRM export files were not tested.

### AC5
- Status: PASS
- Proof:
  - `python3 -m pytest -q tests/test_finance_kpis.py tests/test_finance_imports.py tests/test_finance_crm.py` passed with 17 tests.
  - `python3 -m py_compile src/main.py src/core/finance_kpis.py src/core/finance_imports.py src/core/finance_crm.py` passed.
  - `cd frontend && npx eslint src/components/FinanceFirstStep.tsx src/components/FinanceImportPanel.tsx src/components/FinanceThresholdsPanel.tsx src/pages/dashboard/FinancePage.tsx` passed.
  - `cd frontend && npm run build` passed.
- Gaps:
  - Full project lint still has unrelated legacy failures.

## Commands run
- `python3 -m pytest -q tests/test_finance_kpis.py tests/test_finance_imports.py tests/test_finance_crm.py`
- `python3 -m py_compile src/main.py src/core/finance_kpis.py src/core/finance_imports.py src/core/finance_crm.py`
- `cd frontend && npx eslint src/components/FinanceFirstStep.tsx src/components/FinanceImportPanel.tsx src/components/FinanceThresholdsPanel.tsx src/pages/dashboard/FinancePage.tsx`
- `cd frontend && npm run build`

## Raw artifacts
- .agent/tasks/finance-impact-history-import-stage7-9-20260512/raw/build.txt
- .agent/tasks/finance-impact-history-import-stage7-9-20260512/raw/test-unit.txt
- .agent/tasks/finance-impact-history-import-stage7-9-20260512/raw/test-integration.txt
- .agent/tasks/finance-impact-history-import-stage7-9-20260512/raw/lint.txt
- .agent/tasks/finance-impact-history-import-stage7-9-20260512/raw/screenshot-1.png

## Known gaps
- Full project lint remains blocked by unrelated existing lint debt.
- Production still needs DB backup and Alembic migration from earlier finance stages.
- Impact is a directional comparison, not proof that a specific action caused the KPI change.
