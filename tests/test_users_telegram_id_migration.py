import importlib


def test_users_telegram_id_migration_is_chained_and_idempotent(monkeypatch):
    migration = importlib.import_module(
        "alembic_migrations.versions.20260830_add_users_telegram_id"
    )
    statements = []
    monkeypatch.setattr(migration.op, "execute", lambda statement: statements.append(str(statement)))

    migration.upgrade()

    combined = "\n".join(statements)
    assert migration.down_revision == "20260830_001"
    assert "ALTER TABLE users" in combined
    assert "ADD COLUMN IF NOT EXISTS telegram_id TEXT" in combined

    statements.clear()
    migration.downgrade()
    assert statements == []
