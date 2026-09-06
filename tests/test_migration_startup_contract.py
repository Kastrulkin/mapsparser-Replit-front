from pathlib import Path
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

from scripts import localos_migrator


@pytest.mark.parametrize("mode,expected,starts", [("schema-check-only", "check", True), ("startup", "upgrade", True), ("migrate-only", "upgrade", False)])
def test_entrypoint_selects_one_migration_mode_then_starts_command(tmp_path, mode, expected, starts):
    log = tmp_path / "calls"
    for name, body in {
        "pg_isready": "exit 0",
        "python3": 'echo "$@" >> "$TEST_STARTUP_LOG"',
        "fake-app": 'echo "app started" >> "$TEST_STARTUP_LOG"',
    }.items():
        path = tmp_path / name
        path.write_text("#!/bin/sh\n" + body + "\n")
        path.chmod(0o755)
    root = Path(__file__).parents[1]
    result = subprocess.run(["sh", "entrypoint.sh", "fake-app"], cwd=root,
        env={**os.environ, "PATH": str(tmp_path) + ":/usr/bin:/bin", "LOCALOS_MIGRATION_MODE": mode, "TEST_STARTUP_LOG": str(log)}, capture_output=True, text=True)
    assert result.returncode == 0
    lines = log.read_text().splitlines()
    assert lines[0] == "scripts/localos_migrator.py " + expected
    assert ("app started" in lines) == starts
    assert len(lines) == (2 if starts else 1)


class MigrationConnection:
    def __init__(self):
        self.calls = []
        self.autocommit = False
    def cursor(self):
        return self
    def execute(self, query, parameters=None):
        self.calls.append((query, parameters))
    def close(self):
        return None


def test_migration_lock_is_held_for_upgrade_and_released_on_failure():
    connection = MigrationConnection()
    attempts = []
    def command(arguments, **options):
        attempts.append(arguments)
        assert connection.calls[0] == ("SELECT pg_advisory_lock(%s)", (883741,))
        return SimpleNamespace(returncode=1, stdout="", stderr="migration failed")
    assert localos_migrator.upgrade(connection, command, lambda _seconds: None) == 1
    assert len(attempts) == 1
    assert attempts[0][:3] == [sys.executable, "-m", "flask"]
    assert connection.calls[-1] == ("SELECT pg_advisory_unlock(%s)", (883741,))


def test_successful_migrator_requires_expected_revision(monkeypatch):
    connection = MigrationConnection()
    monkeypatch.setattr(localos_migrator, "check_revision", lambda _connection: False)
    assert localos_migrator.upgrade(connection, lambda *_args, **_options: SimpleNamespace(returncode=0, stdout="", stderr="")) == 1
    assert connection.calls[-1][0] == "SELECT pg_advisory_unlock(%s)"
