# Evidence Bundle: project-security-quality-cleanup-20260619

## Summary
- Overall status: PASS_WITH_NOTED_WARNINGS
- Last updated: 2026-06-19T11:42:00+03:00

## Acceptance criteria evidence

### AC1 Security block
- Status: PASS
- Proof:
  - Removed the hardcoded Yandex Wordstat client secret from `src/wordstat_client.py`; helper now requires `YANDEX_WORDSTAT_CLIENT_ID` and `YANDEX_WORDSTAT_CLIENT_SECRET`.
  - Removed `verify=False` from 2GIS HTTP fallback requests.
  - Added env-driven in-process write limits to public sales-room suggestion, resolve, message, file upload, and event endpoints.
  - Added focused unit coverage for public sales-room rate limiting in `tests/test_sales_rooms.py`.
- Gaps:
  - Rotate the previously committed Yandex Wordstat secret outside the repository.
  - Replace in-process sales-room limits with Redis-backed Flask-Limiter when shared storage is available.

### AC2 Quality gate
- Status: PASS
- Proof:
  - Removed the disabled `{false && ...}` JSX block from `frontend/src/components/content-plan/ContentPlanTab.tsx`.
  - Added `scripts/local_quality_gate.sh`.
  - `scripts/local_quality_gate.sh` completed with exit 0.
- Gaps:
  - Existing frontend lint warnings remain: 344 warnings, 0 errors.
  - `pip-audit` is not installed locally; the gate prints the install command and runs it when available.

### AC3 Frontend dependency vulnerabilities
- Status: PASS
- Proof:
  - Updated frontend dependencies/lockfile.
  - `npm --prefix frontend audit --omit=dev` found 0 vulnerabilities.
  - Full `npm --prefix frontend audit` found 0 vulnerabilities.
- Gaps:
  - The lockfile now uses an `overrides.esbuild=0.28.1` entry to avoid a Vite 8 major upgrade while closing the dev-server advisory.

### AC4 Runtime cleanup and hardening plan
- Status: PASS
- Proof:
  - Moved root-level legacy debug/repro/fix/reset/cleanup scripts, local dumps, and legacy systemd services into `archive/legacy-runbooks/`.
  - Added `archive/legacy-runbooks/README.md`.
  - Added `docs/PROJECT_HARDENING_PLAN.md` with monolith split order, type hardening order, and follow-up security work.
- Gaps:
  - The actual monolith split is planned, not fully executed in this pass, to avoid a high-risk broad route move without a dedicated regression cycle.

## Commands run
- `python3 -m compileall -q src/api/admin_prospecting.py src/wordstat_client.py src/two_gis_maps_scraper.py`
- `python3 -m compileall -q src tests`
- `python3 -m pytest -q tests/test_sales_rooms.py tests/test_sales_room_file_storage.py tests/test_security_runtime_config.py tests/test_content_plan_policy.py`
- `npm --prefix frontend audit --omit=dev`
- `npm --prefix frontend audit`
- `npm --prefix frontend run build`
- `npm --prefix frontend run lint`
- `cd frontend && npx tsc --noEmit`
- `scripts/local_quality_gate.sh`

## Raw artifacts
- .agent/tasks/project-security-quality-cleanup-20260619/raw/build.txt
- .agent/tasks/project-security-quality-cleanup-20260619/raw/test-unit.txt
- .agent/tasks/project-security-quality-cleanup-20260619/raw/test-integration.txt
- .agent/tasks/project-security-quality-cleanup-20260619/raw/lint.txt
- .agent/tasks/project-security-quality-cleanup-20260619/raw/screenshot-1.png

## Known gaps
- Production deploy was not performed.
- Secret rotation must happen in the external Yandex/Wordstat account, not only in repository code.
- Full backend test suite was not run; focused subset passed.
