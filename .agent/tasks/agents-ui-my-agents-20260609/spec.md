# Task Spec: agents-ui-my-agents-20260609

## Metadata
- Task ID: agents-ui-my-agents-20260609
- Created: 2026-06-09T12:05:22+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Original task statement
Stage 6 UI My Agents: `/dashboard/agents` is main agents screen with list, status draft/active/paused/needs approval/error, type, last run, pending approvals, data sources, journal, change logic, versions; legacy AIAgentSettings/AIAgentsManagement integrated as Voice and Style tab or marked legacy; commit, push, deploy.

## Acceptance criteria
- AC1: `/dashboard/agents` is the main "Мои агенты" screen for AgentBlueprint product objects.
- AC2: Agent list shows status, type/category, last run, pending approvals, data source count, journal count, and versions.
- AC3: Agent detail exposes logic editing, run entrypoint, journal/results, approvals, sources, and version controls.
- AC4: Legacy `AIAgentSettings` / `AIAgentsManagement` is integrated as "Голос и стиль" inside agent detail or explicitly marked legacy, not presented as a separate workflow world.
- AC5: Backend list API provides summary fields needed by the UI without new tables or production data changes.
- AC6: Changes are tested, committed, pushed, and deployed.

## Constraints
- Reuse AgentBlueprint, versions, runs, approvals, metadata sources and existing AIAgents persona layer.
- No schema migration.
- No production data mutation.
- No destructive cleanup of dirty server worktree.

## Non-goals
- Full migration/removal of legacy AIAgents tables.
- New `/dashboard/ai-agents` route.
- Browser-authenticated E2E flow with real user session.

## Verification plan
- Build: `cd frontend && npm run build`
- Unit tests: `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py`
- Integration tests: `python3 -m py_compile src/api/agent_blueprints_api.py`; dev server HTTP smoke for `/dashboard/agents`
- Lint: `git diff --check`; `rg -n "\bas\b" ...`
- Manual checks: inspect diff for no standalone communication/AI agent route and no schema change.
