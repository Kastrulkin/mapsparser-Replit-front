# Evidence Bundle: agents-learning-loop-20260609

## Summary
- Overall status: PASS
- Last updated: 2026-06-09T16:16:00+03:00

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
  - Backend files were deployed to `/opt/seo-app/src/...` and `docker compose restart app worker` completed.
  - Frontend dist deploy completed with live asset `/assets/index-DrgkSUe8.js`.
  - Production checks passed: `docker compose ps`, app logs after restart, `curl -I http://localhost:8000`, live frontend asset checks.
  - Production route/source smoke passed: `/api/agent-runs/<run_id>/feedback` is registered as POST; container source contains `agent_learning_loop_v1` and `auto_activate`.
- Gaps:
  - None.

## Commands run
- `PYTHONPATH=src python3 -m py_compile src/api/agent_blueprints_api.py src/services/agent_blueprint_workspace.py`
- `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py`
- `npm run build`
- `ssh ... "cd /opt/seo-app && docker compose restart app worker"`
- `bash scripts/deploy_frontend_dist.sh --build`
- `ssh ... "cd /opt/seo-app && docker compose ps && curl -I http://localhost:8000 && docker compose exec -T app python3 - <<'PY' ..."`

## Raw artifacts
- .agent/tasks/agents-learning-loop-20260609/raw/build.txt
- .agent/tasks/agents-learning-loop-20260609/raw/test-unit.txt
- .agent/tasks/agents-learning-loop-20260609/raw/test-integration.txt
- .agent/tasks/agents-learning-loop-20260609/raw/lint.txt
- .agent/tasks/agents-learning-loop-20260609/raw/screenshot-1.png

## Known gaps
- None.

## Deployment notes
- Frontend deploy emitted transient `tar: file changed as we read it` warnings during archive streaming, but deployment continued and verification checks passed.
- The Vite public directory included `yandex_9f7f92ca02ef161c.html` in generated dist. That file remains untracked locally and was not committed as part of this task.
