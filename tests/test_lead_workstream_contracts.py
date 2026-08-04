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


def test_action_filter_uses_the_same_workstream_scope_as_the_registry():
    runtime = read("src/api/prospecting/delivery_runtime.py")

    assert 'not workstream_type or str(item.get("workstream_type")' in runtime
    assert 'not client_business_id or str(item.get("client_business_id")' in runtime
    assert 'get("next_action")' in runtime


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
