# Evidence Bundle: agents-implementation-roadmap-20260626

## Summary
- Overall status: PASS
- Last updated: 2026-06-26T08:24:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - Added read-only `GET /api/agents/capabilities?business_id=...` with tenant access guard, provider/connector availability, approval/risk metadata, and redacted provider status.
  - Updated `docs/DOCUMENTATION_GAPS.md`: capability registry moved from `gap` to `available`.
  - Updated `docs/PARTNERSHIP_ROADMAP_BACKLOG.md`: P4/P5 now reflect implemented `/dashboard/partnerships` UI/orchestration and existing smoke coverage; P6 still marks OpenClaw capability wiring pending.
  - Updated agent UI contract tests from old "Preview run" copy to current product copy.
  - Backend deployed to production and `/api/agents/capabilities?business_id=test` returns `401 AUTH_REQUIRED` without token; route exists in `/app/src/api/capabilities_api.py`.
- Gaps:
  - Live Google Sheets smoke still requires the user to connect Google/OAuth and provide an authenticated business context.
  - Full partnership e2e smoke requires `AUTH_TOKEN`, `BUSINESS_ID`, `MAP_URL`; local CI gate skips it without these values.
  - Push remains blocked by local Git credentials (`git-credential-osxkeychain` missing; SSH keys not authorized).
  - Agent tokens, MCP surface, unified approval API, OpenAPI generation, prompt canonicalization, legacy cleanup, and deeper provider/domain integrations remain future phases.

## Commands run
- `python3 -m py_compile src/api/capabilities_api.py scripts/smoke_partnership_flow.py`
- `scripts/ci_gate_partnership.sh`
- `venv/bin/python -m pytest -q tests/test_capabilities_api_phase1.py -rs` -> 2 passed, 57 skipped because Docker daemon unavailable.
- `venv/bin/python -m pytest -q tests/test_agent_blueprint_layer.py` -> 171 passed.
- `npm --prefix frontend run build` -> passed with existing Browserslist/Yandex Maps Rollup warnings.
- `scripts/deploy_backend_src.sh` -> app/worker recreated; migrations passed.
- Server checks: `docker compose ps`, `curl -I http://localhost:8000`, app/worker logs, unauthenticated capability registry route check.

## Raw artifacts
- .agent/tasks/agents-implementation-roadmap-20260626/raw/build.txt
- .agent/tasks/agents-implementation-roadmap-20260626/raw/test-unit.txt
- .agent/tasks/agents-implementation-roadmap-20260626/raw/test-integration.txt
- .agent/tasks/agents-implementation-roadmap-20260626/raw/lint.txt
- .agent/tasks/agents-implementation-roadmap-20260626/raw/screenshot-1.png

## Known gaps
- Docker daemon unavailable locally, so Docker-backed capabilities integration tests were skipped.
- Production endpoint route was verified unauthenticated; authenticated business-scoped payload verification requires a real user token.
