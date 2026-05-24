# Evidence Bundle: agent-blueprint-authenticated-ui-smoke-20260524

## Summary
- Overall status: PASS
- Last updated: 2026-05-24T21:00:00+03:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - Created a temporary production fixture with `SMOKE_KEEP_FIXTURE=1` and known smoke credentials.
  - Logged into `https://localos.pro/login` as `smoke-agent-2d6a720cb3@example.invalid`.
  - Opened `https://localos.pro/dashboard/agents` and selected run `61c2a5fe-2c15-4caa-8183-ca04e03e8a80`.
  - Browser-visible markers included `Workflow agents`, `Source`, `City`, `Category`, `Limit`, `Run timeline`, `Artifacts`, `Approvals`, `Approval queue`, `Queued but not dispatched`, `Leads source: prospectingleads`, `Derived from: lead_source_plan`, and `Full payload`.
  - Browser-visible queue handoff text confirmed LocalOS queue only: external dispatcher is a separate contour and queue had 1 item.
  - Cleaned the fixture and verified zero rows remain for smoke user, business, lead, blueprint, and run.
- Gaps:
  - Browser screenshot capture was not used because text-marker verification was sufficient and previous screenshot capture in the in-app browser was flaky.

## Commands run
- `cd /opt/seo-app && docker compose cp scripts/smoke_agent_blueprint_outreach_api.py app:/tmp/smoke_agent_blueprint_outreach_api.py`
- `cd /opt/seo-app && docker compose exec -T app sh -lc 'SMOKE_BASE_URL=http://localhost:8000 SMOKE_KEEP_FIXTURE=1 SMOKE_PASSWORD=... python3 -B /tmp/smoke_agent_blueprint_outreach_api.py'`
- Browser login and `/dashboard/agents` inspection via in-app browser.
- `cd /opt/seo-app && docker compose exec -T app sh -lc '<cleanup fixture and zero-count verification>'`
- `cd /opt/seo-app && curl -I http://localhost:8000`
- `cd /opt/seo-app && docker compose logs --since 8m app | tail -120`

## Raw artifacts
- .agent/tasks/agent-blueprint-authenticated-ui-smoke-20260524/raw/build.txt
- .agent/tasks/agent-blueprint-authenticated-ui-smoke-20260524/raw/test-unit.txt
- .agent/tasks/agent-blueprint-authenticated-ui-smoke-20260524/raw/test-integration.txt
- .agent/tasks/agent-blueprint-authenticated-ui-smoke-20260524/raw/lint.txt
- .agent/tasks/agent-blueprint-authenticated-ui-smoke-20260524/raw/screenshot-1.png

## Known gaps
- None.
