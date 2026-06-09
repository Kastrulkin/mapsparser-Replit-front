# Evidence Bundle: agents-ui-my-agents-20260609

## Summary
- Overall status: UNKNOWN
- Last updated: 2026-06-09T12:12:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `frontend/src/pages/dashboard/AgentBlueprintsPage.tsx` now labels the central section `Мои агенты`.
  - The route already points `/dashboard/agents` to `AgentBlueprintsPage`.
- Gaps:
  - None.

### AC2
- Status: PASS
- Proof:
  - `BlueprintAgentCard` renders `StatusBadge`, type/category, last run, pending approvals, sources, journal count and versions through `AgentSummaryPill`.
  - `getAgentListStatus()` maps pending approvals/failed last run into `needs_approval`/`error`.
- Gaps:
  - None.

### AC3
- Status: PASS
- Proof:
  - Detail tabs are `Логика`, `Запуск`, `Журнал`, `Голос и стиль`.
  - Existing `AgentWorkspacePanel`, run panel, `AgentRunReviewPanel`, pending approvals and `VersionSummary` remain in selected agent detail.
- Gaps:
  - None.

### AC4
- Status: PASS
- Proof:
  - `AgentVoiceStylePanel` embeds `AIAgentSettings` inside selected agent detail.
  - Main list no longer renders `PersonaAgentCard` alongside workflow agents.
  - Copy marks AIAgents as `AIAgents legacy wrapper` / voice persona, not workflow runtime.
- Gaps:
  - None.

### AC5
- Status: PASS
- Proof:
  - `/api/agent-blueprints` list query now returns `last_run_*`, `pending_approvals_count`, `sources_count`, `journal_entries_count`, and `versions_count`.
  - No Alembic migration or DB write added.
- Gaps:
  - `journal_entries_count` is metadata-backed until richer per-run journal aggregation is needed.

### AC6
- Status: UNKNOWN
- Proof:
  - Local tests and build passed.
  - Commit/push/deploy will be performed after proof validation.
- Gaps:
  - Commit/push/deploy not completed at this evidence timestamp.

## Commands run
- `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py` -> 40 passed.
- `cd frontend && npm run build` -> build succeeded.
- `python3 -m py_compile src/api/agent_blueprints_api.py` -> pass.
- `git diff --check -- ...` -> pass.
- `curl -I http://127.0.0.1:3000/dashboard/agents` -> 200 OK.

## Raw artifacts
- .agent/tasks/agents-ui-my-agents-20260609/raw/build.txt
- .agent/tasks/agents-ui-my-agents-20260609/raw/test-unit.txt
- .agent/tasks/agents-ui-my-agents-20260609/raw/test-integration.txt
- .agent/tasks/agents-ui-my-agents-20260609/raw/lint.txt
- .agent/tasks/agents-ui-my-agents-20260609/raw/screenshot-1.png

## Known gaps
- Browser MCP did not expose a `js` execution tool in this turn, so authenticated browser screenshot was not available. Build and HTTP smoke were used instead.
- Deployment still pending before final sign-off.
