import importlib.util
from pathlib import Path


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic_migrations"
    / "versions"
    / "20260908_allow_creator_learning_events.py"
)


def load_migration():
    spec = importlib.util.spec_from_file_location("creator_learning_migration", MIGRATION_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upgrade_expands_and_validates_workstream_constraint(monkeypatch):
    migration = load_migration()
    statements = []
    monkeypatch.setattr(migration.op, "execute", statements.append)

    migration.upgrade()

    normalized = [" ".join(statement.split()) for statement in statements]
    assert len(normalized) == 3
    assert "DROP CONSTRAINT IF EXISTS ck_outreach_learning_workstream" in normalized[0]
    assert "'localos_sales', 'client_partnership', 'creator_collaboration'" in normalized[1]
    assert normalized[1].endswith("NOT VALID")
    assert "VALIDATE CONSTRAINT ck_outreach_learning_workstream" in normalized[2]


def test_downgrade_preserves_existing_creator_audit_rows(monkeypatch):
    migration = load_migration()
    statements = []
    monkeypatch.setattr(migration.op, "execute", statements.append)

    migration.downgrade()

    normalized = [" ".join(statement.split()) for statement in statements]
    assert len(normalized) == 2
    assert "DROP CONSTRAINT IF EXISTS ck_outreach_learning_workstream" in normalized[0]
    assert "'localos_sales', 'client_partnership'" in normalized[1]
    assert "creator_collaboration" not in normalized[1]
    assert normalized[1].endswith("NOT VALID")
