# Task Spec: agent-blueprint-auth-ui-smoke-20260524

## Metadata
- Task ID: agent-blueprint-auth-ui-smoke-20260524
- Created: 2026-05-24T08:25:01+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Original task statement
P1 authenticated browser smoke for Agent Blueprint UI: fix discovered endpoint bug, deploy frontend, create temporary controlled fixture, verify `/dashboard/agents` shows blueprint, run history filter, full artifact payload, approval queue, queued but not dispatched, then cleanup fixture.

## Acceptance criteria
- AC1: Authenticated `/dashboard/agents` loads workflow agents from production API without `/api/api` path duplication.
- AC2: Business owner can see blueprint card, run timeline, run history, and approval queue.
- AC3: Completed supervised outreach run exposes full artifact payload and explicitly shows "Queued but not dispatched".
- AC4: Starting a new run creates a pending approval visible in the approval queue.
- AC5: Run filters show `Approval` runs and `Completed` runs.
- AC6: Temporary live smoke fixture is removed after verification.
- AC7: Focused build, backend agent blueprint tests, and backend lint guardrails pass.

## Constraints
- Use temporary smoke data only.
- Do not start outbound dispatcher.
- Do not leave production smoke user/business/blueprint rows behind.
- Do not mix unrelated Operator/Apify worktree changes into this proof bundle.

## Verification plan
- Build: `cd frontend && npm run build`
- Unit tests: `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py`
- Lint: `scripts/lint_backend_baseline.sh`
- Integration: authenticated browser smoke on `https://localos.pro/dashboard/agents`
- Cleanup: call smoke fixture cleanup and verify DB counts are zero.
