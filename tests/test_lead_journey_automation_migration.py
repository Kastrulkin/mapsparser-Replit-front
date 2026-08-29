import importlib


def test_automation_journey_migration_updates_both_flow_constraints(monkeypatch):
    migration = importlib.import_module(
        "alembic_migrations.versions.20260829_add_automation_journey_flow"
    )
    statements = []
    monkeypatch.setattr(migration.op, "execute", lambda statement: statements.append(str(statement)))

    migration.upgrade()

    combined = "\n".join(statements)
    assert migration.down_revision == "20260828_001"
    assert "'content', 'automation'" in combined
    assert "'content', 'automation', 'upgrade'" in combined

    statements.clear()
    migration.downgrade()
    rollback = "\n".join(statements)
    assert "Cannot remove automation journey flow" in rollback
    assert "'content', 'upgrade'" in rollback
