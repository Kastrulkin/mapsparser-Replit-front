# Evidence Bundle: agent-capability-map-openclaw-20260609

## Summary
- Overall status: PASS
- Last updated: 2026-06-09T11:08:00+00:00

## Acceptance Criteria Evidence

### AC1
- Status: PASS
- Proof:
  - `build_agent_blueprint_orchestrator()` now returns `ActionOrchestrator(build_capability_handlers())`.
  - Shared handler map lives in `src/services/agent_capability_handlers.py`.

### AC2
- Status: PASS
- Proof:
  - Handler map includes outreach, reviews, services, news, appointments, communications, support and billing capabilities.
  - Legacy aliases remain registered: `reviews.reply`, `appointments.create`, `appointments.update`, `appointments.cancel`, `reminders.send`, `communications.send`.

### AC3
- Status: PASS
- Proof:
  - `src/api/capabilities_api.py` registers user `/api/capabilities/*` and M2M `/api/openclaw/*` routes.
  - Route smoke found no missing required Stage 4 routes.

### AC4
- Status: PASS
- Proof:
  - OpenClaw catalog returns 401 without token and 200 with `X-OpenClaw-Token`.
  - Both user and M2M routes use `PHASE1_ACTION_ORCHESTRATOR`.

### AC5
- Status: PASS
- Proof:
  - Communications compiler allowlist now uses `communications.send_reminder` and `communications.send_offer`.
  - Updated compiler test passes.

### AC6
- Status: PASS
- Proof:
  - `docs/LOCALOS_AGENT_ARCHITECTURE_V1.md` documents capability map v1, registered route surface, aliases and follow-ups.

## Commands Run
- `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py`
- `PYTHONPATH=src OPENCLAW_LOCALOS_TOKEN=test-token python3 - <<'PY' ...`
- `git diff --check`

## Raw Artifacts
- `.agent/tasks/agent-capability-map-openclaw-20260609/raw/build.txt`
- `.agent/tasks/agent-capability-map-openclaw-20260609/raw/test-unit.txt`
- `.agent/tasks/agent-capability-map-openclaw-20260609/raw/test-integration.txt`
- `.agent/tasks/agent-capability-map-openclaw-20260609/raw/lint.txt`

## Known Gaps
- Some handlers are safe draft/request handlers, not full provider integrations.
- Full Telegram support-send delivery remains in the existing owner-bot/support surface.
