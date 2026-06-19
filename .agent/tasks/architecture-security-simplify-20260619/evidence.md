# Evidence Bundle: architecture-security-simplify-20260619

## Summary
- Overall status: PASS
- Last updated: 2026-06-19T12:45:00+03:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - Removed hardcoded Yandex Wordstat client credentials from runtime config and legacy docs.
  - Approval-boundary audit now checks the current capability-handler boundary.
  - Social-posts workflow keeps product API/service/UI path, but removed premature agent `social.post.*` capability/provider declarations.
  - Social-posts schema is Alembic-owned; runtime service now fails loudly if migration is missing.
  - Authenticated social-post write endpoints have an in-process per-user/action write limiter.
  - `local_quality_gate.sh` now uses the repo venv when present, requires `pip-audit`, includes approval/social-post tests, and checks changed frontend TS/TSX files with `--max-warnings=0`.
  - Legacy root fix/debug/repro/reset files moved to `archive/legacy-runbooks`; canonical Docker/Postgres runbook clarified in `docs/DOCKER_DEPLOY.md`.
  - `scripts/local_quality_gate.sh` completed with exit code 0.
  - Focused secret/security scan no longer finds the removed Wordstat credentials or `verify=False`.
- Gaps:
  - Production secret rotation must still be done outside the repo.
  - Broad frontend lint baseline still has existing warnings; changed-file lint is now enforced for new frontend TS/TSX changes.
  - No production deploy was performed in this proof bundle.

## Commands run
- `venv/bin/python -m compileall -q src tests`
- `venv/bin/python -m pytest -q tests/test_approval_boundaries_audit.py tests/test_security_runtime_config.py tests/test_sales_rooms.py tests/test_sales_room_file_storage.py tests/test_content_plan_policy.py tests/test_social_post_service.py tests/test_social_posts_api.py`
- `venv/bin/python -m pip install -r requirements.test.txt`
- `scripts/local_quality_gate.sh`
- `rg -n "623b9605|8ec666a|verify=False|social\\.post\\.draft|social\\.post\\.publish_api|social_channels|CREATE TABLE IF NOT EXISTS social_posts|ALTER TABLE social_posts" src tests scripts docs --glob '!frontend/dist/**'`

## Raw artifacts
- .agent/tasks/architecture-security-simplify-20260619/raw/build.txt
- .agent/tasks/architecture-security-simplify-20260619/raw/test-unit.txt
- .agent/tasks/architecture-security-simplify-20260619/raw/test-integration.txt
- .agent/tasks/architecture-security-simplify-20260619/raw/lint.txt
- .agent/tasks/architecture-security-simplify-20260619/raw/screenshot-1.png

## Known gaps
- Production deploy and DB backup are intentionally deferred until commit/push/deploy is requested for this batch.
- External Wordstat key rotation is required.
