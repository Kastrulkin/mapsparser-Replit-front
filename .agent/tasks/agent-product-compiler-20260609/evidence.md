# Evidence Bundle: agent-product-compiler-20260609

## Summary
- Overall status: PASS
- Last updated: 2026-06-09T09:58:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - Added `src/services/agent_product_layer.py`.
  - `agent_blueprints_api` decorates blueprint list/detail responses with `product_agent`.
  - Product view exposes `components.blueprint`, `components.persona`, and `components.compiled_workflow`.
- Gaps:
  - Physical `agents` table intentionally not added in this stage.

### AC2
- Status: PASS
- Proof:
  - `persona_agent_id` is collected from latest/active versions and loaded from `AIAgents`.
  - Versions are decorated with `persona` and `voice`.
  - Test `test_agent_product_view_uses_aiagent_as_voice_persona` covers `AIAgents` as `agent_voice`.
- Gaps:
  - UI controls for selecting/changing persona are still a follow-up.

### AC3
- Status: PASS
- Proof:
  - Added `compile_agent_blueprint()`.
  - Added `communications` category inference and typed communications payload.
  - Test `test_agent_compiler_creates_communications_reminder_blueprint` covers trigger, audience, sources, steps, capabilities, approvals, limits, and output schema.
- Gaps:
  - `communications.send` execution capability is not wired yet.

### AC4
- Status: PASS
- Proof:
  - `build_agent_blueprint_draft()` remains as compatibility wrapper.
  - `agent_builder_session.py` uses compiler semantics and preview fields.
  - `agent_builder_api.py` uses `compile_agent_blueprint()` when creating a blueprint.
- Gaps:
  - None for current stage.

### AC5
- Status: PASS
- Proof:
  - `AgentBlueprintsPage.tsx` types include `persona`, `voice`, and `product_agent`.
  - Agent cards and details show the attached voice name when available.
- Gaps:
  - Persona management still lives in legacy `AIAgentSettings`.

### AC6
- Status: PASS
- Proof:
  - Updated `docs/LOCALOS_AGENT_ARCHITECTURE_V1.md` with Current Backend Contract and revised implementation checkpoints.
- Gaps:
  - Remaining follow-ups are explicitly documented.

## Commands run
- `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py`
- `cd frontend && npm run build`
- `git status --short --branch`

## Raw artifacts
- .agent/tasks/agent-product-compiler-20260609/raw/build.txt
- .agent/tasks/agent-product-compiler-20260609/raw/test-unit.txt
- .agent/tasks/agent-product-compiler-20260609/raw/test-integration.txt
- .agent/tasks/agent-product-compiler-20260609/raw/lint.txt
- .agent/tasks/agent-product-compiler-20260609/raw/screenshot-1.png

## Known gaps
- `communications.send` is currently a compiled capability contract, not an implemented ActionOrchestrator capability.
- Full production migration of old `AIAgents` into blueprint-backed agents is not done in this stage.
- Server deploy was not requested for this stage and was not performed.
