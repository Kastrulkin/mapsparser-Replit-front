# Evidence Bundle: operator-sprint1-attention-brief-20260520

## Summary
- Overall status: PASS
- Last updated: 2026-05-20T10:46:09+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `src/api/operator_api.py` defines `GET /api/operator/attention-brief`.
  - The endpoint uses `require_auth_from_request` and `verify_business_access`.
  - `src/main.py` registers `operator_bp`.
- Gaps:
  - None.

### AC2
- Status: PASS
- Proof:
  - `src/services/operator_attention.py` builds structured cached JSON with summary, metrics, freshness, items, action classes, and explicit limits.
  - `tests/test_operator_attention.py` verifies `data_mode= cached`, `action_class=free_cached`, and no paid/external execution flags.
- Gaps:
  - None.

### AC3
- Status: PASS
- Proof:
  - The service performs read-only `SELECT` queries.
  - It does not call parser providers, GigaChat, ledger writes, provider publication, or schema mutation helpers.
  - No migrations were added.
- Gaps:
  - None.

### AC4
- Status: PASS
- Proof:
  - `frontend/src/pages/dashboard/OperatorPage.tsx` adds the first Operator screen.
  - `frontend/src/App.tsx` routes `/dashboard/operator`.
  - `frontend/src/components/DashboardSidebar.tsx` adds Operator navigation.
- Gaps:
  - None.

### AC5
- Status: PASS
- Proof:
  - `docs/agents/localos-operator.md` marks Operator as `beta` and documents the web/API Sprint 1 routes.
  - `docs/agents/index.md` states the Sprint 1 intent reads existing LocalOS data only and does not run paid refreshes, AI generation, external writes, or publication.
- Gaps:
  - None.

### AC6
- Status: PASS
- Proof:
  - This evidence bundle lists changed files and checks.
  - `verdict.json` records PASS.
- Gaps:
  - None.

## Commands run
- `sed -n '1,220p' README.md`
- `sed -n '1,260p' docs/agents/localos-operator.md`
- `scripts/proof_loop.sh init operator-sprint1-attention-brief-20260520 "..."`
- `python3 -m pytest -q tests/test_operator_attention.py`
- `python3 -m py_compile src/services/operator_attention.py src/api/operator_api.py src/main.py`
- `npm --prefix frontend run build`
- `npm --prefix frontend run dev -- --host 127.0.0.1`
- `curl -s -o /tmp/operator-route.html -w '%{http_code} %{content_type}\n' http://127.0.0.1:3001/dashboard/operator`
- `rg -n "operator|attention-brief|Что требует моего внимания|paid_actions_performed|external_writes_performed|paid refresh|provider write|MCP" src frontend/src docs/agents .agent/tasks/operator-sprint1-attention-brief-20260520/spec.md`
- `rg -n "опубликовал ответ|отправил ответ в карты|autonomously write|public MCP server is confirmed|direct map reply publishing" docs/agents src frontend/src`

## Raw artifacts
- .agent/tasks/operator-sprint1-attention-brief-20260520/raw/build.txt
- .agent/tasks/operator-sprint1-attention-brief-20260520/raw/test-unit.txt
- .agent/tasks/operator-sprint1-attention-brief-20260520/raw/test-integration.txt
- .agent/tasks/operator-sprint1-attention-brief-20260520/raw/lint.txt
- .agent/tasks/operator-sprint1-attention-brief-20260520/raw/screenshot-1.png

## Known gaps
- Freeform LLM chat is not implemented.
- Paid refresh execution and persisted consent settings are not implemented.
- Telegram command routing to the Operator core is not implemented.
- Provider write/publish actions are not implemented.
