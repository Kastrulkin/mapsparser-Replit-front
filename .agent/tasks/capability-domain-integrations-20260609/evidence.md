# Evidence Bundle: capability-domain-integrations-20260609

## Summary
- Overall status: PASS
- Last updated: 2026-06-09
- Scope: domain-backed capability handlers with the same approval/audit/limits boundary.

## Acceptance Criteria Evidence

### AC1
- Status: PASS
- Proof: `_handle_appointments_read()` uses `_load_appointments()` against `Bookings` with `business_id`, optional status/phone/date filters and bounded limit.

### AC2
- Status: PASS
- Proof: communication handlers use `_create_communication_request()`, derive recipients from explicit payload or `Bookings`, cap batches to max 50, and store `agent_communication_requests` with `delivery_state=not_dispatched` and `provider_write_performed=False`.

### AC3
- Status: PASS
- Proof: `reviews.reply.publish_request` creates/updates `reviewreplydrafts` with `status=publish_requested`, returns `manual_publish_required=True`, and does not call a provider API.

### AC4
- Status: PASS
- Proof: `services.optimize` reads `userservices`, stores `agent_service_optimization_requests`, returns suggestions with `apply_state=not_applied` and `manual_apply_required=True`.

### AC5
- Status: PASS
- Proof: `billing.reserve` calls `reserve_paid_action_credits`; `billing.settle` calls `finalize_reserved_action_credits`; no external payment action is added outside the existing reservation/finalization policy.

### AC6
- Status: PASS
- Proof: `docs/LOCALOS_AGENT_ARCHITECTURE_V1.md` now has `Domain Integrations Behind Capability Map`.

### AC7
- Status: PASS
- Proof: `alembic_migrations/versions/20260609_add_agent_domain_request_tables.py` creates `agent_communication_requests` and `agent_service_optimization_requests`.

### AC8
- Status: PASS
- Proof: tests cover appointments read, communication internal request creation, review publish request, service optimization request, billing delegation, migration source, and source guards.

## Commands Run
- `PYTHONPATH=src python3 -m py_compile src/services/agent_capability_handlers.py`
- `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py`
- `PYTHONPATH=src python3 -m pytest -q tests/test_operator_credit_reservation.py`

## Raw Artifacts
- `.agent/tasks/capability-domain-integrations-20260609/raw/build.txt`
- `.agent/tasks/capability-domain-integrations-20260609/raw/test-unit.txt`
- `.agent/tasks/capability-domain-integrations-20260609/raw/test-integration.txt`

## Known Gaps
- No production handler execution was run because that could create production domain records.
- External provider send/publish/apply flows remain intentionally outside this iteration.
