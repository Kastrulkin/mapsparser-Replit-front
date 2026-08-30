import importlib


def test_content_plan_item_metadata_migration_is_chained_and_idempotent(monkeypatch):
    migration = importlib.import_module(
        "alembic_migrations.versions.20260830_add_content_plan_item_metadata"
    )
    statements = []
    monkeypatch.setattr(migration.op, "execute", lambda statement: statements.append(str(statement)))

    migration.upgrade()

    combined = "\n".join(statements)
    assert migration.down_revision == "20260829_001"
    assert "ALTER TABLE contentplanitems" in combined
    assert "ADD COLUMN IF NOT EXISTS metadata_json JSONB NOT NULL" in combined

    statements.clear()
    migration.downgrade()
    assert statements == []
