# Evidence Bundle: agents-rima-like-hardening-phase14-20260527

## Summary
- Overall status: PASS
- Last updated: 2026-05-27T17:49:00+00:00
- Code change: Datahub catalog now includes connected agent text/file/internal sources before LocalOS internal catalog sources.
- Smoke change: generic boundary smoke now checks the current reviews payload key `reply_drafts`.

## Acceptance Criteria Evidence

### AC1: Dialog Builder
- Status: PASS
- Proof:
  - `raw/dialog-datahub-version-smoke-after-proof-fix.txt` shows blueprint creation from the UI dialog builder on `https://localos.pro`.
  - Result includes `builder=dialog_builder_v1`, `category=documents`, and `setup_completed=true`.
  - `raw/browser-dialog-builder-created.png` captures the browser flow after create-from-preview.
- Gaps:
  - None for this phase.

### AC2: Datahub-Lite Connected Sources
- Status: PASS
- Proof:
  - `raw/dialog-datahub-version-smoke-after-proof-fix.txt` includes connected text source `Smoke договор контекст` and uploaded file source `Smoke uploaded contract`.
  - Both sources have `extraction_state=ready`; uploaded file uses `extraction_method=plain_text`.
  - `raw/test-agent-builder-datahub.txt` / `raw/test-unit.txt` show targeted unit coverage passed.
- Gaps:
  - None for text/plain upload coverage. Rich PDF/DOCX/XLSX quality remains a later product polish track.

### AC3: Version Loop
- Status: PASS
- Proof:
  - `raw/dialog-datahub-version-smoke-after-proof-fix.txt` shows run review journal kinds `input`, `extraction`, `output`, `approval`.
  - Feedback created version 2 from version 1.
  - Diff includes changed fields `approval_policy` and `output_schema`.
  - Rollback to initial version and activation of feedback version both returned success during the smoke.
- Gaps:
  - None for API/runtime proof. More visual polish can still improve the UI around version history.

### AC4: Generic Safety Boundaries
- Status: PASS
- Proof:
  - `raw/prod-generic-boundaries-smoke-after-fix.txt` checks `documents`, `email`, `tables`, `reviews`.
  - Output shows `external_dispatch_performed=false`, `dispatcher_started=false`, and `approvals_required=true`.
  - Each generic run creates draft output and stops for final approval.
- Gaps:
  - None for the tested generic categories.

### AC5: Production Cleanup And Health
- Status: PASS
- Proof:
  - `raw/prod-fixture-cleanup-verify.txt` shows `users=0`, `businesses=0`, `blueprints=0`, `runs=0`, `builder_sessions=0`.
  - `raw/prod-health-after-phase14.txt` shows app/worker/postgres up and `HTTP/1.1 200 OK`.
- Gaps:
  - None.

## Commands Run
- `python3 -m pytest -q tests/test_agent_blueprint_layer.py -k 'agent_datahub_catalog or agent_builder_session'`
- `scripts/lint_backend_baseline.sh`
- `ssh ... 'cd /opt/seo-app && docker compose restart app worker && docker compose ps ...'`
- `SMOKE_UI_PASSWORD=... python3 .agent/tasks/agents-rima-like-hardening-phase14-20260527/raw/rima_like_dialog_datahub_version_smoke.py`
- `ssh ... 'cd /opt/seo-app && docker compose exec -T app ... python -' < scripts/smoke_agent_blueprint_generic_boundaries.py`
- `ssh ... 'cd /opt/seo-app && docker compose exec -T postgres psql ... cleanup/verify ...'`
- `ssh ... 'cd /opt/seo-app && docker compose ps && docker compose logs --since 2m app | tail -80 && curl -I -sS http://localhost:8000 | head -5'`

## Raw Artifacts
- `raw/test-unit.txt`
- `raw/test-agent-builder-datahub.txt`
- `raw/lint.txt`
- `raw/deploy-datahub-catalog.txt`
- `raw/deploy-datahub-catalog-restart.txt`
- `raw/prod-health-after-datahub-restart.txt`
- `raw/dialog-datahub-version-smoke-after-proof-fix.txt`
- `raw/prod-generic-boundaries-smoke-after-fix.txt`
- `raw/prod-fixture-cleanup.txt`
- `raw/prod-fixture-cleanup-verify.txt`
- `raw/prod-health-after-phase14.txt`
- `raw/browser-dialog-builder-created.png`

## Known Gaps
- Production logs still show the already-known GigaChat SSL verification warning when LLM analysis runs. This was previously accepted only as an explicit workaround and should stay visible in future hardening work.
