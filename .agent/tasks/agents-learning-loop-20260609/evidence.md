# Evidence Bundle: agents-learning-loop-20260609

## Summary
- Overall status: PASS
- Last updated: 2026-06-09T16:12:00+03:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `POST /api/agent-runs/<run_id>/feedback` now stores typed learning feedback with `trigger_type`.
  - Feedback creates a candidate `agent_blueprint_versions` payload with feedback history and diff.
  - Product UI sends `auto_activate: false`, so candidate versions are not runtime truth until human activation.
  - UI Learning Loop block supports manual edit, rejected approval, bad outcome, runtime error, and manual feedback triggers.
  - UI shows candidate version, diff summary, changed fields, activation state, activate action, and rollback after activation.
  - `build_learning_loop_summary()` returns `agent_learning_loop_v1` / `versioned_review`.
  - `docs/LOCALOS_AGENT_ARCHITECTURE_V1.md` defines Learning Loop v1 as versioned and human-gated.
  - `PYTHONPATH=src python3 -m py_compile src/api/agent_blueprints_api.py src/services/agent_blueprint_workspace.py` passed.
  - `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py` passed: 43 tests.
  - `npm run build` passed.
- Gaps:
  - Production deploy verification is pending.

## Commands run
- `PYTHONPATH=src python3 -m py_compile src/api/agent_blueprints_api.py src/services/agent_blueprint_workspace.py`
- `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py`
- `npm run build`

## Raw artifacts
- .agent/tasks/agents-learning-loop-20260609/raw/build.txt
- .agent/tasks/agents-learning-loop-20260609/raw/test-unit.txt
- .agent/tasks/agents-learning-loop-20260609/raw/test-integration.txt
- .agent/tasks/agents-learning-loop-20260609/raw/lint.txt
- .agent/tasks/agents-learning-loop-20260609/raw/screenshot-1.png

## Known gaps
- Production deploy verification is pending.
