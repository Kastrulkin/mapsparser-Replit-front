#!/usr/bin/env python3
"""One migration lock path and a read-only release schema gate."""
import os
from pathlib import Path
import subprocess
import sys
import time

import psycopg2
from alembic.config import Config
from alembic.script import ScriptDirectory

LOCK_ID = 883741
ROOT = Path(__file__).resolve().parents[1]


def connect():
    dsn = os.environ.get("DATABASE_URL")
    if dsn:
        return psycopg2.connect(dsn)
    return psycopg2.connect(host=os.getenv("POSTGRES_HOST", "postgres"), port=os.getenv("POSTGRES_PORT", "5432"),
        user=os.getenv("POSTGRES_USER", "local"), password=os.getenv("POSTGRES_PASSWORD", "local"),
        dbname=os.getenv("POSTGRES_DB", "local"))


def expected_heads():
    configuration = Config(str(ROOT / "alembic.ini"))
    configuration.set_main_option("script_location", str(ROOT / "alembic_migrations"))
    return set(ScriptDirectory.from_config(configuration).get_heads())


def check_revision(connection, expected=None):
    expected = expected_heads() if expected is None else set(expected)
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT to_regclass('alembic_version')")
        if not cursor.fetchone()[0]:
            return False
        cursor.execute("SELECT version_num FROM alembic_version")
        actual = {row[0] for row in cursor.fetchall()}
        compatible = {value.strip() for value in os.getenv("LOCALOS_COMPATIBLE_SCHEMA_REVISIONS", "").split(",") if value.strip()}
        allowed = actual == expected or bool(compatible) and len(actual) == 1 and actual.issubset(compatible)
        if not allowed:
            print("Schema revision is incompatible: actual=" + ",".join(sorted(actual)) + " expected=" + ",".join(sorted(expected)), file=sys.stderr)
        return allowed
    finally:
        cursor.close()


def upgrade(connection, run_command=None, wait=None):
    run_command = subprocess.run if run_command is None else run_command
    wait = time.sleep if wait is None else wait
    connection.autocommit = True
    cursor = connection.cursor()
    locked = False
    try:
        cursor.execute("SELECT pg_advisory_lock(%s)", (LOCK_ID,))
        locked = True
        for attempt in range(3):
            result = run_command([sys.executable, "-m", "flask", "db", "upgrade"], cwd=str(ROOT), capture_output=True, text=True, check=False)
            if result.stdout:
                print(result.stdout, end="")
            if result.stderr:
                print(result.stderr, end="", file=sys.stderr)
            if result.returncode == 0:
                return 0 if check_revision(connection) else 1
            if "Can't locate revision identified by" not in (result.stderr or "") or attempt == 2:
                return result.returncode
            wait(3)
        return 1
    finally:
        if locked:
            cursor.execute("SELECT pg_advisory_unlock(%s)", (LOCK_ID,))
        cursor.close()


def main():
    mode = sys.argv[1] if len(sys.argv) == 2 else ""
    if mode not in {"upgrade", "check"}:
        print("usage: localos_migrator.py upgrade|check", file=sys.stderr)
        return 2
    connection = connect()
    try:
        if mode == "upgrade":
            return upgrade(connection)
        # No Flask app import and no schema mutation in ordinary DML-role startup.
        if not check_revision(connection):
            return 1
        return subprocess.run([sys.executable, str(ROOT / "scripts/check_content_learning_schema.py")], check=False).returncode
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
