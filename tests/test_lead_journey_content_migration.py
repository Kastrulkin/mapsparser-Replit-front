import importlib


def test_content_journey_migration_is_chained_and_rollback_safe(monkeypatch):
    migration = importlib.import_module("alembic_migrations.versions.20260827_add_content_journey_flow")
    statements = []
    monkeypatch.setattr(migration.op, "execute", lambda statement: statements.append(str(statement)))

    migration.upgrade()

    combined = "\n".join(statements)
    assert migration.down_revision == "20260827_001"
    assert "'influencer', 'partnership', 'maps', 'content'" in combined
    assert "'influencer', 'partnership', 'maps', 'content', 'upgrade'" in combined
    assert "CREATE INDEX IF NOT EXISTS idx_lead_journeys_flow_status" in combined

    statements.clear()
    migration.downgrade()
    assert "NOT VALID" in "\n".join(statements)
