from pathlib import Path


def _patterns() -> set[str]:
    path = Path(__file__).resolve().parents[1] / ".dockerignore"
    return {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def test_production_release_backups_are_excluded_from_build_context() -> None:
    required = {
        "backups", "db_backups", "data", "release-backups", ".release-backups",
        "deploy-backups", ".deploy-backups", ".deploy", ".deploy-staging", ".release",
    }
    assert required.issubset(_patterns()), required - _patterns()


def test_runtime_sources_and_migration_scripts_remain_build_inputs() -> None:
    required_inputs = {"src", "scripts", "alembic_migrations", "requirements.txt", "entrypoint.sh"}
    assert required_inputs.isdisjoint(_patterns())
