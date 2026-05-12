# Evidence Bundle: finance-thresholds-stage4-20260512

## Summary
- Overall status: PASS
- Last updated: 2026-05-12T15:10:00+03:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `alembic_migrations/versions/20260512_add_finance_first_step.py` creates `finance_kpi_thresholds`.
  - The table stores business, profile, metric key, green/yellow ranges, red rule, label, unit and active flag.
- Gaps:
  - Production migration was not applied in this local stage.

### AC2
- Status: PASS
- Proof:
  - `src/main.py` loads thresholds through `_load_finance_thresholds`.
  - Dashboard, manual entry response, recalculation, data quality, recommendations, file import and CRM sync use `_finance_snapshot_for_period`.
- Gaps:
  - Live API smoke against a migrated database was not run locally.

### AC3
- Status: PASS
- Proof:
  - `frontend/src/components/FinanceThresholdsPanel.tsx` adds editable KPI norms.
  - `frontend/src/pages/dashboard/FinancePage.tsx` renders the panel and refreshes finance data after save/reset.
- Gaps:
  - Authenticated browser check was not possible in this session.

### AC4
- Status: PASS
- Proof:
  - `tests/test_finance_kpis.py` verifies custom thresholds change KPI statuses.
  - Recommendation text includes custom metric label and custom norm.
- Gaps:
  - None.

### AC5
- Status: PASS
- Proof:
  - `python3 -m pytest -q tests/test_finance_kpis.py tests/test_finance_imports.py tests/test_finance_crm.py` passed.
  - `python3 -m py_compile src/main.py src/core/finance_kpis.py src/core/finance_imports.py src/core/finance_crm.py` passed.
  - `npx eslint src/components/FinanceThresholdsPanel.tsx src/pages/dashboard/FinancePage.tsx` passed.
  - `npm run build` passed.
- Gaps:
  - Full `npm run lint` still fails on pre-existing unrelated project-wide lint debt.

## Commands run
- `python3 -m pytest -q tests/test_finance_kpis.py tests/test_finance_imports.py tests/test_finance_crm.py`
- `python3 -m py_compile src/main.py src/core/finance_kpis.py src/core/finance_imports.py src/core/finance_crm.py`
- `npx eslint src/components/FinanceThresholdsPanel.tsx src/pages/dashboard/FinancePage.tsx`
- `npm run build`
- Browser smoke: opened `http://127.0.0.1:5176/dashboard/finance`, confirmed redirect to login and no console errors.

## Raw artifacts
- .agent/tasks/finance-thresholds-stage4-20260512/raw/build.txt
- .agent/tasks/finance-thresholds-stage4-20260512/raw/test-unit.txt
- .agent/tasks/finance-thresholds-stage4-20260512/raw/test-integration.txt
- .agent/tasks/finance-thresholds-stage4-20260512/raw/lint.txt
- .agent/tasks/finance-thresholds-stage4-20260512/raw/screenshot-1.png

## Known gaps
- Full project lint still fails on old unrelated files.
- Production requires DB backup and Alembic migration before deploy.
