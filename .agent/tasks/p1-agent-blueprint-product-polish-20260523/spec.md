# Task Spec: p1-agent-blueprint-product-polish-20260523

## Metadata
- Task ID: p1-agent-blueprint-product-polish-20260523
- Created: 2026-05-23T20:10:07+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
P1/P2 Agent Blueprint product polish: improve run details with full artifact payload, run status filtering, separate approval queue, and explicit queued-but-not-dispatched outreach send state; verify backend and frontend; commit push deploy

## Acceptance criteria
- AC1: Run history supports status filtering.
- AC2: Run details expose full artifact payloads.
- AC3: Pending approvals are visible in a separate queue.
- AC4: Outreach send step clearly shows queued-but-not-dispatched state.
- AC5: Backend and frontend checks pass.

## Constraints
- Do not change side-effect boundaries; blueprint runtime must not dispatch external sends.
- Keep UI changes scoped to the Agent Blueprint page.

## Non-goals
- Universal visual workflow builder.
- Dispatcher implementation.

## Verification plan
- Build: `python3 -m py_compile src/api/agent_blueprints_api.py`
- Unit tests: `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py`
- Integration tests: `npm run build`
- Lint: `scripts/lint_backend_baseline.sh`
- Manual checks: inspect changed Agent Blueprint UI and API response shape.
