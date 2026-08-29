import importlib


def test_ori_migration_creates_file_table_before_altering_it(monkeypatch):
    migration = importlib.import_module(
        "alembic_migrations.versions.20260824_add_ori_communication_compliance"
    )
    statements = []
    monkeypatch.setattr(migration.op, "execute", lambda statement: statements.append(str(statement)))

    migration.upgrade()

    combined = "\n".join(statements)
    create_position = combined.index("CREATE TABLE IF NOT EXISTS sales_room_files")
    alter_position = combined.index("ALTER TABLE sales_room_files")
    assert create_position < alter_position
    assert "REFERENCES sales_room_messages(id)" in combined
