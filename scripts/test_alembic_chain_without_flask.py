#!/usr/bin/env python3
"""Apply the Alembic chain to an explicitly disposable database."""

from __future__ import annotations

import os

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine


def main() -> int:
    database_url = str(os.environ.get("MIGRATION_TEST_DATABASE_URL") or "").strip()
    if "creator_portal_test" not in database_url:
        raise RuntimeError("MIGRATION_TEST_DATABASE_URL must name a disposable creator_portal_test database")
    config = Config("alembic.ini")
    config.set_main_option("script_location", "alembic_migrations")
    script = ScriptDirectory.from_config(config)
    revisions = list(script.walk_revisions(base="base", head="heads"))
    revisions.reverse()
    engine = create_engine(database_url)
    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            for revision in revisions:
                print(f"apply {revision.revision}: {revision.doc}", flush=True)
                revision.module.upgrade()
    print(f"OK: {len(revisions)} migrations", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
