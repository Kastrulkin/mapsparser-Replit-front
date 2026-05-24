# Evidence Bundle: agent-blueprint-outreach-live-smoke-20260524

## Summary
- Overall status: PASS
- Last updated: 2026-05-24T20:40:00+03:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - Ran controlled production-runtime smoke inside the `app` container with `SMOKE_BASE_URL=http://localhost:8000`.
  - Smoke created a test user, business, `new` / `unprocessed` `prospectingleads` row, blueprint, run, shortlist approval, draft approval, and queued batch.
  - Result reported `source_artifact_status=hydrated`, `source_artifact_count=1`, `approval_count=2`, `queue_status=queued`, `dispatch_state=queued_not_dispatched`, `dispatcher_started=false`, `fixture_cleaned=true`.
  - Post-smoke DB cleanup check returned zero rows for the test user, business, lead, blueprint, and run.
  - App logs show the authenticated route sequence returned 200/201 responses and no dispatcher/provider write route was called.
- Gaps:
  - The script had to be copied into container `/tmp` because the production image has a baked `/app/scripts` directory while the host has the updated script.

## Commands run
- `cd /opt/seo-app && docker compose ps`
- `cd /opt/seo-app && docker compose cp scripts/smoke_agent_blueprint_outreach_api.py app:/tmp/smoke_agent_blueprint_outreach_api.py`
- `cd /opt/seo-app && docker compose exec -T app sh -lc 'SMOKE_BASE_URL=http://localhost:8000 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app/src python3 -B /tmp/smoke_agent_blueprint_outreach_api.py'`
- `cd /opt/seo-app && docker compose exec -T app sh -lc '<cleanup verification query>'`
- `cd /opt/seo-app && docker compose logs --since 5m app | tail -120`
- `cd /opt/seo-app && curl -I http://localhost:8000`

## Raw artifacts
- .agent/tasks/agent-blueprint-outreach-live-smoke-20260524/raw/build.txt
- .agent/tasks/agent-blueprint-outreach-live-smoke-20260524/raw/test-unit.txt
- .agent/tasks/agent-blueprint-outreach-live-smoke-20260524/raw/test-integration.txt
- .agent/tasks/agent-blueprint-outreach-live-smoke-20260524/raw/lint.txt
- .agent/tasks/agent-blueprint-outreach-live-smoke-20260524/raw/screenshot-1.png

## Known gaps
- Container packaging does not expose the latest host `scripts/` tree at `/app/scripts`; live smoke used `/tmp` copy as a controlled workaround.
