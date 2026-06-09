# Evidence Bundle: custom-agent-telegram-sheets-20260609

## Summary
- Overall status: PASS for this iteration slice.
- Product interpretation: Compile AI custom workflow foundation; Telegram + Sheets is a showcase.

## Acceptance Criteria Evidence

### AC1
- Status: PASS
- Proof: `compile_agent_blueprint("Когда пользователь пишет в Telegram бота, добавь строку в Google таблицу")` returns `category=custom`.

### AC2
- Status: PASS
- Proof: compiled payload includes `trigger=telegram.message.received`, steps `capture_telegram_trigger -> prepare_sheet_row -> approve_sheet_update -> request_sheet_append -> record_sheet_request`, allowlist `sheets.append_row_request`, approval policy for `sheet_update`, and `autonomous_external_write_allowed=false`.

### AC3
- Status: PASS
- Proof: `build_agent_blueprint_orchestrator()` exposes `sheets.append_row_request`; catalog aliases `google_sheets.append_row` to it.

### AC4
- Status: PASS
- Proof: handler creates `agent_sheet_operation_requests`, returns `sheet_append_request_created`, `approval_state=pending_human`, `apply_state=not_applied`, `provider_write_performed=false`.

### AC5
- Status: PASS
- Proof: `evaluate_risk_policy("sheets.append_row_request", ...)` returns `requires_human=true`.

### AC6
- Status: PASS
- Proof: `src/ai_agent_webhooks.py` calls `dispatch_telegram_message_to_agent_blueprints`; `src/services/agent_trigger_runtime.py` records `agent_trigger_events` and starts matching active blueprints.

### AC7
- Status: PASS
- Proof: `alembic_migrations/versions/20260609_add_custom_agent_integration_tables.py` creates `agent_integrations`, `agent_trigger_events`, `agent_sheet_operation_requests`.

### AC8
- Status: PASS
- Proof: `docs/LOCALOS_AGENT_ARCHITECTURE_V1.md` now describes Compile AI custom workflows and Telegram/Sheets as blueprint endpoints.

### AC9
- Status: PASS
- Proof: targeted tests and syntax checks passed.

### AC10
- Status: PASS
- Proof: `AgentBlueprintRunner.load_run()` now includes `observability.domain_requests` for capability-created domain requests; `AgentRunObservabilityPanel` renders “Ожидают approval” with `why_waiting`, approval/apply status, limits and payload details.

### AC11
- Status: PASS
- Proof: `src/services/agent_domain_request_executors.py` is the approved executor boundary; `AgentBlueprintRunner` records `approved_executor` after capability success; `tests/test_agent_blueprint_layer.py::test_approved_domain_executor_moves_sheet_request_after_human_gate` verifies state transition, ledger record, and `provider_write_performed=false`.

### AC12
- Status: PASS
- Proof: `services.optimize` stores `diff_json`; `AgentBlueprintRunner` exposes `visual_diff`; `execute_approved_domain_requests()` applies approved suggestions to `userservices.optimized_name/optimized_description`; tests verify diff generation and approved internal apply.

### AC13
- Status: PASS
- Proof: `agent_communication_delivery_journal` migration exists; approved communication executor writes queued/blocked journal rows with limits/consent/router handoff metadata; `AgentRunObservabilityPanel` can display `delivery_journal`; tests verify one queued and one consent-blocked item with `provider_write_performed=false`.

## Commands Run
- `PYTHONPATH=src python3 -m py_compile src/services/agent_capability_handlers.py src/services/agent_blueprint_draft_builder.py src/services/agent_trigger_runtime.py src/ai_agent_webhooks.py src/core/action_policy.py alembic_migrations/versions/20260609_add_custom_agent_integration_tables.py`
- `PYTHONPATH=src python3 -m py_compile src/services/agent_blueprint_runner.py`
- `PYTHONPATH=src python3 -m py_compile src/services/agent_domain_request_executors.py src/services/agent_blueprint_runner.py`
- `PYTHONPATH=src python3 -m py_compile src/services/agent_capability_handlers.py src/services/agent_domain_request_executors.py src/services/agent_blueprint_runner.py alembic_migrations/versions/20260609_add_agent_service_optimization_diff.py`
- `PYTHONPATH=src python3 -m py_compile src/services/agent_domain_request_executors.py src/services/agent_blueprint_runner.py alembic_migrations/versions/20260609_add_agent_communication_delivery_journal.py`
- `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py`
- `PYTHONPATH=src python3 -m pytest -q tests/test_capabilities_api_phase1.py`
- `npm --prefix frontend run build`

## Known Gaps
- No Google provider write executor yet. This is intentional; external writes remain future approved executor work.
- No frontend connector setup UI in this iteration.
