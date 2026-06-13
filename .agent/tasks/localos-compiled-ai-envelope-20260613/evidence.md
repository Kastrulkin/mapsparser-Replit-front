# Evidence Bundle: localos-compiled-ai-envelope-20260613

## Summary
- Overall status: PASS for current phase scope.
- Last updated: 2026-06-13T14:55:00+03:00
- Current phase: Phase 5, Maton delivery draft/send route handler.

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `src/services/agent_blueprint_runner.py::_is_maton_delivery_step` recognizes communications send capabilities.
  - `_maton_delivery_contract` reads `maton_external_account_bridge` from blueprint metadata.

### AC2
- Status: PASS
- Proof:
  - `_execute_maton_delivery_step` treats safe preview as draft-only.
  - `tests/test_agent_blueprint_layer.py::test_runner_creates_maton_delivery_preview_draft_without_dispatch` fails if dispatch is called and asserts no external dispatch occurred.

### AC3
- Status: PASS
- Proof:
  - Existing runner approval gate blocks dangerous `send` capabilities without approved approval.
  - Maton dispatch additionally requires `dispatch_mode=send_after_approval`, `external_side_effects_allowed: true`, and non-preview input.

### AC4
- Status: PASS
- Proof:
  - Approved Maton dispatch calls `load_business_channel_context` and `dispatch_with_routing`.
  - Regression test asserts `preferred_provider == "maton"` and `force_channel_id == "maton_bridge"`.

### AC5
- Status: PASS
- Proof:
  - Artifact schema is `localos_maton_delivery_request_v1`.
  - Artifact records provider, handler, binding key, external account id, delivery state, router result, policy, and `external_dispatch_performed`.

### AC6
- Status: PASS
- Proof:
  - Focused Maton/OpenClaw runner tests passed: 4 tests.
  - Full agent blueprint suite passed: 151 tests.
  - Frontend production build passed.

## Commands run
- `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py -k 'maton_delivery or openclaw_preview_observations or creates_drafts_after_shortlist' -x`
- `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py -x`
- `npm --prefix frontend run build`

## Raw artifacts
- `.agent/tasks/localos-compiled-ai-envelope-20260613/raw/phase5-maton-delivery-tests.txt`
- `.agent/tasks/localos-compiled-ai-envelope-20260613/raw/phase5-agent-blueprint-tests.txt`
- `.agent/tasks/localos-compiled-ai-envelope-20260613/raw/phase5-frontend-build.txt`

## Known gaps
- Full objective remains active: Google Sheets read, LocalOS finance write, wider billing ledger expansion, and more real provider handlers still require later phases.
