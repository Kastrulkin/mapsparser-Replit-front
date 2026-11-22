# Alembic env.py for Flask-Migrate (run via: flask db upgrade)
import logging
from logging.config import fileConfig

from flask import current_app
from alembic import context

config = context.config
if config.config_file_name is not None:
    try:
        fileConfig(config.config_file_name)
    except Exception:
        pass
logger = logging.getLogger("alembic.env")


def get_engine():
    try:
        return current_app.extensions["migrate"].db.get_engine()
    except (TypeError, AttributeError):
        return current_app.extensions["migrate"].db.engine


def get_engine_url():
    try:
        return get_engine().url.render_as_string(hide_password=False).replace("%", "%%")
    except AttributeError:
        return str(get_engine().url).replace("%", "%%")


config.set_main_option("sqlalchemy.url", get_engine_url())
target_db = current_app.extensions["migrate"].db


def get_metadata():
    if hasattr(target_db, "metadatas"):
        return target_db.metadatas[None]
    return target_db.metadata


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=get_metadata(), literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def prepare_version_table(connection):
    # Read-only commands such as "current" have no destination revision.
    try:
        context.get_revision_argument()
    except KeyError:
        return
    connection.exec_driver_sql("""
        DO $$
        BEGIN
            IF to_regclass('alembic_version') IS NULL THEN
                CREATE TABLE alembic_version (
                    version_num text NOT NULL CONSTRAINT alembic_version_pkc PRIMARY KEY
                );
            ELSIF EXISTS (
                SELECT 1 FROM pg_attribute
                WHERE attrelid = 'alembic_version'::regclass
                  AND attname = 'version_num' AND atttypmod > 0
            ) THEN
                -- Keep existing revision IDs that exceed Alembic's default VARCHAR(32).
                ALTER TABLE alembic_version ALTER COLUMN version_num TYPE text;
            END IF;
        END $$;
    """)


def run_migrations_online():
    connectable = get_engine()
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=get_metadata())
        with context.begin_transaction():
            if connection.dialect.name == "postgresql":
                prepare_version_table(connection)
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
