from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_migration_adds_independent_context_to_messages_rooms_and_history():
    migration = read("alembic_migrations/versions/20260714_add_lead_workstreams.py")

    assert "CREATE TABLE IF NOT EXISTS lead_workstreams" in migration
    assert "uq_lead_workstreams_localos" in migration
    assert "uq_lead_workstreams_client" in migration
    for table in (
        "outreachmessagedrafts",
        "outreachsendqueue",
        "sales_rooms",
        "lead_timeline_events",
    ):
        assert f'"{table}"' in migration


def test_admin_compact_api_returns_workstream_registry_fields():
    runtime = read("src/api/prospecting/delivery_runtime.py")
    database = read("src/database_manager.py")

    assert "attach_workstreams(workstream_conn, normalized)" in runtime
    assert 'filters.get("workstream_type")' in runtime
    assert 'filters.get("client_business_id")' in runtime
    assert 'filters.get("action_state")' in runtime
    assert '"client_options": client_options' in runtime
    assert 'display_lead["partner_type"] = canonical_partner_type' in runtime
    assert 'display_lead["canonical_categories"] = canonical_categories' in runtime
    assert '"business_category_options": category_options' in runtime
    assert '"partner_type_options": category_options' in runtime
    assert "duplicate_client_names" in runtime
    assert "source_provider" in database
    assert "intent" in database


def test_registry_uses_server_pagination_in_api_and_ui():
    runtime = read("src/api/prospecting/delivery_runtime.py")
    frontend = read("frontend/src/components/prospecting/AdminLeadRegistry.tsx")

    assert 'request.args.get("page")' in runtime
    assert 'request.args.get("page_size")' in runtime
    assert '"total_pages": total_pages' in runtime
    assert "params.set('page', String(page))" in frontend
    assert "params.set('page_size', String(pageSize))" in frontend
    assert "Предыдущая" in frontend
    assert "Следующая" in frontend
    assert "leadLoadRequestId.current" in frontend
    assert "requestId !== leadLoadRequestId.current" in frontend
    assert "_normalize_lead_for_display_direct(lead)" in runtime
    assert "_lead_matches_filters_direct(lead, filters)" in runtime


def test_registry_migration_indexes_repeated_lateral_lookups():
    migration = read("alembic_migrations/versions/20260826_optimize_lead_registry.py")

    assert "idx_lead_enrichment_jobs_workstream_latest" in migration
    assert "idx_outreachsendqueue_sent_recipient" in migration
    assert "idx_outreach_inbound_workstream_human" in migration


def test_registry_exposes_latest_campaign_for_processing_filters():
    service = read("src/services/lead_workstream_service.py")
    frontend = read("frontend/src/components/prospecting/AdminLeadRegistry.tsx")

    assert "campaign.id AS campaign_id" in service
    assert "payload[\"campaign_state\"]" in service
    assert "Любая категория бизнеса" in frontend
    assert "Любое состояние цепочки" in frontend
    assert "Цепочка создана" in frontend
    assert "Цепочки нет" in frontend
    assert "Проверить черновик" in frontend
    assert '"code": "review_draft"' in service


def test_followup_migration_restores_partner_client_from_room_or_card():
    migration = read("alembic_migrations/versions/20260714_fix_lead_workstream_clients.py")

    assert "sr.mode = 'partner_search'" in migration
    assert "partnership_partner_cards" in migration
    assert "COALESCE(room_owner.client_business_id, card_owner.client_business_id)" in migration


def test_save_and_room_handlers_accept_workstream_id():
    runtime = read("src/api/prospecting/delivery_runtime.py")
    room_routes = read("src/api/prospecting/sales_room_routes.py")
    audit_routes = read("src/api/prospecting/audit_routes.py")

    assert 'data.get("workstream_type")' in runtime
    assert 'data.get("client_business_id")' in runtime
    assert 'data.get("workstream_id")' in room_routes
    assert "workstream_id=workstream_id" in audit_routes


def test_partner_deletion_removes_context_before_company():
    service = read("src/services/partnership_leads_service.py")

    assert "DELETE FROM lead_workstreams" in service
    assert "NOT EXISTS (" in service
    assert "SELECT 1 FROM lead_workstreams ws WHERE ws.lead_id = l.id" in service


def test_registry_exposes_touch_stage_readiness_and_duplicate_recipient_gate():
    service = read("src/services/lead_workstream_service.py")
    frontend = read("frontend/src/components/prospecting/AdminLeadRegistry.tsx")

    assert 'workstream["relationship_stage"] = build_relationship_stage(workstream)' in service
    assert 'workstream["readiness_gate"] = build_readiness_gate(lead, workstream)' in service
    assert "recipient_history.duplicate_recipient AS duplicate_recipient" in service
    assert "Ответили после" in service
    assert "Организация, контакт и рабочий контекст" in frontend
    assert "readiness_gate.checks.map" in frontend


def test_confirmed_sends_project_one_task_to_touch_number_column():
    delivery = read("src/api/prospecting/delivery_runtime.py")
    campaign = read("src/services/outreach_campaign_service.py")
    projection = read("src/services/outreach_yougile_sync_service.py")

    assert "enqueue_touch_sent_projection(cur, queue_id=queue_id)" in delivery
    assert "enqueue_touch_sent_projection(cursor, touch_id=touch_id)" in campaign
    assert "touch_column_ids" in projection
    assert "UNIQUE(workstream_id, provider)" in read(
        "alembic_migrations/versions/20260825_add_outreach_reply_tracking.py"
    )
