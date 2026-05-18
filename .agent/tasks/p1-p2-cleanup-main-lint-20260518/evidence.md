# Evidence Bundle: p1-p2-cleanup-main-lint-20260518

## Summary
- Overall status: PASS
- Last updated: 2026-05-18T19:41:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `.agent/tasks/p1-p2-cleanup-main-lint-20260518/raw/artifacts-before-cleanup.txt`
  - `.agent/tasks/p1-p2-cleanup-main-lint-20260518/raw/artifacts-after-cleanup.txt`
- Gaps:
  - None.

### AC2
- Status: PASS
- Proof:
  - `.gitignore` includes `tmp_docx_work/`.
- Gaps:
  - `.agent/tasks` remains visible by design because selected proof bundles are committed.

### AC3
- Status: PASS
- Proof:
  - `src/api/reports_api.py`
  - `src/main.py` imports and registers `reports_bp`.
  - `.agent/tasks/p1-p2-cleanup-main-lint-20260518/raw/test-integration.txt`
  - `.agent/tasks/p1-p2-cleanup-main-lint-20260518/raw/live-route-smoke.txt`
- Gaps:
  - None.

### AC4
- Status: PASS
- Proof:
  - `scripts/lint_backend_baseline.sh`
  - `.agent/tasks/p1-p2-cleanup-main-lint-20260518/raw/lint.txt`
- Gaps:
  - Focused baseline only; no full-repo style enforcement.

### AC5
- Status: PASS
- Proof:
  - `.agent/tasks/p1-p2-cleanup-main-lint-20260518/raw/build.txt`
  - `.agent/tasks/p1-p2-cleanup-main-lint-20260518/raw/test-unit.txt`
  - `.agent/tasks/p1-p2-cleanup-main-lint-20260518/raw/live-runtime-smoke.txt`
  - `.agent/tasks/p1-p2-cleanup-main-lint-20260518/raw/live-py-compile.txt`
- Gaps:
  - Live syntax verification uses `ast.parse` because `py_compile` tries to write `__pycache__` under read-only `/app/src`.

## Commands run
- `git status --short .agent/tasks tmp_docx_work`
- `rm -rf` for stale untracked proof/work directories only
- `scripts/lint_backend_baseline.sh`
- `python3 -m py_compile src/main.py src/api/reports_api.py tests/test_reports_api_routes.py tests/test_security_runtime_config.py`
- `PYTHONPATH=src python3 -m pytest -q tests/test_reports_api_routes.py tests/test_security_runtime_config.py tests/test_query_adapter.py`
- server backup and `scp` of `src/main.py`, `src/api/reports_api.py`, `scripts/lint_backend_baseline.sh`
- `cd /opt/seo-app && docker compose restart app worker && docker compose ps`
- `scripts/smoke_runtime.sh server`

## Raw artifacts
- .agent/tasks/p1-p2-cleanup-main-lint-20260518/raw/build.txt
- .agent/tasks/p1-p2-cleanup-main-lint-20260518/raw/test-unit.txt
- .agent/tasks/p1-p2-cleanup-main-lint-20260518/raw/test-integration.txt
- .agent/tasks/p1-p2-cleanup-main-lint-20260518/raw/lint.txt
- .agent/tasks/p1-p2-cleanup-main-lint-20260518/raw/screenshot-1.png

## Known gaps
- Full `main.py` decomposition remains future work.
- `EXTERNAL_AUTH_SECRET_KEY` remains a separate blocker in `p1-security-smoke-20260518`.
