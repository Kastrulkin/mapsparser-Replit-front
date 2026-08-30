import importlib
import inspect

from src.api.prospecting import access_schema


def test_partnership_runtime_columns_are_owned_by_alembic(monkeypatch):
    migration = importlib.import_module(
        "alembic_migrations.versions.20260830_add_partnership_runtime_columns"
    )
    statements = []
    monkeypatch.setattr(migration.op, "execute", lambda statement: statements.append(str(statement)))

    migration.upgrade()

    combined = "\n".join(statements)
    assert migration.down_revision == "20260830_002"
    assert "ALTER TABLE prospectingleads" in combined
    assert "ADD COLUMN IF NOT EXISTS parse_business_id UUID" in combined
    assert "ADD COLUMN IF NOT EXISTS partnership_stage TEXT" in combined
    assert "CREATE INDEX IF NOT EXISTS idx_prospectingleads_intent_stage" in combined


def test_request_path_does_not_run_partnership_schema_ddl():
    source = inspect.getsource(access_schema._ensure_partnership_columns)

    assert "ALTER TABLE" not in source
    assert "CREATE INDEX" not in source
    assert "commit()" not in source
