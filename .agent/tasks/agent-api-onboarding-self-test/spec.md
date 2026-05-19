# Task Spec: agent-api-onboarding-self-test

## Metadata
- Task ID: agent-api-onboarding-self-test
- Created: 2026-05-19T10:41:22+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Agent API onboarding + sandbox self-test

## Acceptance criteria
- AC1: `/api/agent-api/self-test` validates an agent key, returns status/scopes/available safe actions, and writes a safe `agent_api_self_test` ledger event.
- AC2: `/docs` and agent/API documentation explain the onboarding flow: sandbox client, `agent_key`, policy, self-test, test approval request, ledger.
- AC3: Admin Agent API UI has quickstart copy, key self-test, and recent self-test visibility.
- AC4: Superadmin morning digest includes self-test count, auth/scope errors, tested agents, and promotion requests.
- AC5: OpenAPI and machine-readable manifests include the self-test endpoint without implying autonomous publish/send/payment/destructive behavior.

## Constraints
- No DB schema change; reuse `agent_action_ledger` and existing `agent_clients`.
- No production data mutation.
- Keep external actions behind human approval.
- Do not include unrelated dirty content-plan/article changes.

## Non-goals
- No public MCP server.
- No product-wide Agent API contract beyond existing Agent API security endpoints.
- No live promotion automation.

## Verification plan
- Build: `cd frontend && npm run build`
- Unit tests: `venv/bin/python -m pytest -q tests/test_agent_api_security.py`
- Integration checks: Flask test-client coverage for self-test success and missing-key denial.
- Lint/static: JSON manifests, `py_compile`, `git diff --check`.
- Manual checks: review changed docs/UI/OpenAPI and ledger/digest query behavior.
