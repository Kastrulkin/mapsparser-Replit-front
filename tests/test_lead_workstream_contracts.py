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
    assert "duplicate_client_names" in runtime
    assert "source_provider" in database
    assert "intent" in database


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
