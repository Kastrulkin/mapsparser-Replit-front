# Evidence Bundle: finance-crm-real-connectors-stage10-20260512

## Summary
- Overall status: PASS
- Last updated: 2026-05-12T18:20:00+03:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - Checked public Altegio developer docs: Business Management API exists, business data uses partner + user authorization, documented limits are 200 requests/min or 5 requests/sec per IP.
  - Checked public YCLIENTS support/docs: API access requires application/user token flow and rights for the system user.
- Gaps:
  - No partner agreement or real sandbox credentials yet.

### AC2
- Status: PASS
- Proof:
  - `src/core/finance_crm.py` adds `YClientsCRMAdapter` and `AltegioCRMAdapter`.
  - Both providers are now `available` with docs URL, required fields and capabilities.
- Gaps:
  - Real endpoint shapes can still need adjustment after first live sandbox response.

### AC3
- Status: PASS
- Proof:
  - Connector validates `api_base_url`, `location_id`, `partner_token`, `user_token`.
  - `/api/finance/crm/connect` rejects missing required fields.
  - `/api/finance/crm/sync` stores failed sync status and returns a clear CRM error.
- Gaps:
  - No credential rotation UI in this stage.

### AC4
- Status: PASS
- Proof:
  - `frontend/src/components/FinanceCrmPanel.tsx` renders docs links, provider capabilities and credential fields for real CRM providers.
  - UI prevents connect until required fields are filled.
- Gaps:
  - No browser auth smoke in this session.

### AC5
- Status: PASS
- Proof:
  - `tests/test_finance_crm.py` covers provider registry, credential validation, auth header format, Altegio defaults and CRM normalization.
- Gaps:
  - No external HTTP contract test without vendor sandbox.

## Commands run
- `python3 -m pytest -q tests/test_finance_crm.py tests/test_finance_imports.py tests/test_finance_kpis.py`
- `python3 -m py_compile src/main.py src/core/finance_crm.py src/core/finance_imports.py src/core/finance_kpis.py`
- `cd frontend && npx eslint src/components/FinanceCrmPanel.tsx src/components/FinanceFirstStep.tsx src/components/FinanceImportPanel.tsx src/pages/dashboard/FinancePage.tsx`
- `cd frontend && npm run build`

## Raw artifacts
- .agent/tasks/finance-crm-real-connectors-stage10-20260512/raw/build.txt
- .agent/tasks/finance-crm-real-connectors-stage10-20260512/raw/test-unit.txt
- .agent/tasks/finance-crm-real-connectors-stage10-20260512/raw/test-integration.txt
- .agent/tasks/finance-crm-real-connectors-stage10-20260512/raw/lint.txt
- .agent/tasks/finance-crm-real-connectors-stage10-20260512/raw/screenshot-1.png

## Known gaps
- Реальное подключение требует ключей и прав на стороне YCLIENTS/Altegio.
- Текущая реализация готовит sync оплаты/услуги/мастера; клиенты и визиты нужно расширять после получения реальных ответов API.
