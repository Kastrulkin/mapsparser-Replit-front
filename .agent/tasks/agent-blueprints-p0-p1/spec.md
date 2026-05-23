# Task Spec: agent-blueprints-p0-p1

## Metadata
- Task ID: agent-blueprints-p0-p1
- Created: 2026-05-23T11:22:47+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
P0-P1 Agent Blueprint: real outreach.send_batch handler, authenticated API smoke, permissions hardening

## Acceptance criteria
- AC1: `outreach.send_batch` is registered as a real Agent Blueprint capability through `ActionOrchestrator`.
- AC2: The capability queues only approved drafts for the run business, respects the hard daily cap, and does not directly dispatch external messages.
- AC3: Starting a run cannot use a `blueprint_version_id` from a different blueprint.
- AC4: Backend guardrails cover imports, route ownership, PostgreSQL placeholder checks, and Agent Blueprint capability safety.

## Constraints
- No production data mutation during local proof.
- No direct external send/publish/destructive side effects from blueprint runtime.
- Existing `AIAgents`, booking, marketing, and admin prospecting endpoints remain compatible.

## Non-goals
- Full universal agent constructor UI.
- New outreach schema migration.
- Direct dispatcher invocation from Agent Blueprint runtime.

## Verification plan
- Build: focused `py_compile` for changed backend modules and tests.
- Unit tests: `python3 -m pytest tests/test_agent_blueprint_layer.py`.
- Integration tests: import smoke for orchestrator handler registration.
- Lint: `scripts/lint_backend_baseline.sh`.
- Manual checks: inspect git diff and verify the capability result explicitly records `external_dispatch_performed = False`.
