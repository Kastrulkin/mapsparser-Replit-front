# Evidence Bundle: agent-api-onboarding-self-test

## Summary
- Overall status: PASS
- Last updated: 2026-05-19T11:05:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - Added `POST /api/agent-api/self-test` in `src/api/agent_security_api.py`.
  - Added `build_agent_self_test_summary` in `src/core/agent_api_security.py`.
  - Success and missing-key denial covered in `tests/test_agent_api_security.py`.
- Gaps:
  - None known.

### AC2
- Status: PASS
- Proof:
  - Updated `docs/api/authentication.md`, `docs/api/examples.md`, `docs/api/endpoints.md`, `docs/agents/index.md`, `docs/agents/security-model.md`.
  - Updated public `llms.txt` and `localos-agents.txt`.
- Gaps:
  - None known.

### AC3
- Status: PASS
- Proof:
  - Added onboarding card, quickstart copy, self-test key input and result display to `frontend/src/components/AgentApiManagement.tsx`.
  - Added self-test count/promotion count to admin metrics.
- Gaps:
  - Browser visual smoke not run in this turn.

### AC4
- Status: PASS
- Proof:
  - Extended `build_agent_activity_digest` to include self-test, auth/scope errors, promotion requests and tested agents.
- Gaps:
  - Production digest delivery not run; code path is covered by compile and existing digest integration.

### AC5
- Status: PASS
- Proof:
  - Updated `frontend/public/localos-agent-openapi.json`, `localos-agent-policy.json`, `localos-agent-tools.json`.
  - JSON manifests validated with `python3 -m json.tool`.
- Gaps:
  - None known.

## Commands run
- `python3 -m json.tool frontend/public/localos-agent-openapi.json >/dev/null`
- `python3 -m json.tool frontend/public/localos-agent-policy.json >/dev/null`
- `python3 -m json.tool frontend/public/localos-agent-tools.json >/dev/null`
- `python3 -m py_compile src/core/agent_api_security.py src/api/agent_security_api.py src/core/card_automation.py`
- `venv/bin/python -m pytest -q tests/test_agent_api_security.py`
- `git diff --check`
- `cd frontend && npm run build`

## Raw artifacts
- .agent/tasks/agent-api-onboarding-self-test/raw/build.txt
- .agent/tasks/agent-api-onboarding-self-test/raw/test-unit.txt
- .agent/tasks/agent-api-onboarding-self-test/raw/test-integration.txt
- .agent/tasks/agent-api-onboarding-self-test/raw/lint.txt
- .agent/tasks/agent-api-onboarding-self-test/raw/screenshot-1.png

## Known gaps
- No deployment or commit was requested/performed for this turn.
- Existing unrelated dirty changes remain in content plan/article files.
