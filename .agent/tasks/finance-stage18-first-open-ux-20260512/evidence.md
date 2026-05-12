# Evidence Bundle: finance-stage18-first-open-ux-20260512

## Summary
- Overall status: PASS
- Last updated: 2026-05-12T17:15:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `FinanceFirstStep` now shows a first-launch block: "Заполните 5 чисел, чтобы увидеть первую картину".
  - The block explains the minimum useful inputs: revenue, rent, payroll, materials, workplaces.
- Gaps:
  - None.

### AC2
- Status: PASS
- Proof:
  - Added visible four-step mini-wizard: `Деньги`, `Услуги`, `Мастера`, `Кресла`.
  - Clicking a step switches the existing input tabs.
- Gaps:
  - None.

### AC3
- Status: PASS
- Proof:
  - Added `Показать пример салона` button.
  - It fills local form state only and shows a message; it does not call save/import endpoints.
- Gaps:
  - None.

### AC4
- Status: PASS
- Proof:
  - KPI cards now include `meaning` and `action` text for operating profit, break-even, revenue per workplace, and workplace occupancy.
- Gaps:
  - None.

### AC5
- Status: PASS
- Proof:
  - Added `Что исправить первым` panel.
  - With no data, it shows starter priorities; with data, it uses recommendations and missing data.
- Gaps:
  - None.

### AC6
- Status: PASS
- Proof:
  - `npm exec -- eslint src/components/FinanceFirstStep.tsx src/pages/dashboard/FinancePage.tsx`: passed.
  - `npm run build`: passed.
  - `python3 -m pytest tests/test_finance_kpis.py tests/test_finance_imports.py tests/test_finance_crm.py -q`: 28 passed.
- Gaps:
  - None.

## Commands run
- `scripts/proof_loop.sh init finance-stage18-first-open-ux-20260512 "..."`
- `python3 -m pytest tests/test_finance_kpis.py tests/test_finance_imports.py tests/test_finance_crm.py -q`
- `cd frontend && npm exec -- eslint src/components/FinanceFirstStep.tsx src/pages/dashboard/FinancePage.tsx`
- `cd frontend && npm run build`

## Raw artifacts
- .agent/tasks/finance-stage18-first-open-ux-20260512/raw/build.txt
- .agent/tasks/finance-stage18-first-open-ux-20260512/raw/test-unit.txt
- .agent/tasks/finance-stage18-first-open-ux-20260512/raw/test-integration.txt
- .agent/tasks/finance-stage18-first-open-ux-20260512/raw/lint.txt
- .agent/tasks/finance-stage18-first-open-ux-20260512/raw/screenshot-1.png

## Known gaps
- Browser visual smoke not run in this turn.
- Production still needs deploying the fresh frontend build.
