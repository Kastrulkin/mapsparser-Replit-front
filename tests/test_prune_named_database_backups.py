from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.prune_named_database_backups import removal_plan, unique_candidates


def set_age(path: Path, *, days: int) -> None:
    timestamp = (datetime.now(timezone.utc) - timedelta(days=days)).timestamp()
    os.utime(path, (timestamp, timestamp))


def test_named_backup_plan_keeps_latest_and_protected_files(tmp_path: Path) -> None:
    backups = tmp_path / "backups"
    backups.mkdir()
    files: list[Path] = []
    for index, age in enumerate((12, 10, 8, 2, 1)):
        path = backups / f"before_change_{index}.dump"
        path.write_bytes(b"x" * 20)
        set_age(path, days=age)
        files.append(path)
    Path(f"{files[0]}.keep").touch()

    candidates = unique_candidates([backups])
    remove = removal_plan(
        candidates,
        keep_latest=2,
        retention_days=7,
        max_total_bytes=10_000,
        now=datetime.now(timezone.utc),
    )

    assert files[0] not in remove
    assert set(remove) == {files[1], files[2]}
    assert files[3] not in remove
    assert files[4] not in remove


def test_named_backup_plan_enforces_size_cap_without_deleting_latest(tmp_path: Path) -> None:
    backups = tmp_path / "backups"
    backups.mkdir()
    files: list[Path] = []
    for index, age in enumerate((4, 3, 2, 1, 0)):
        path = backups / f"snapshot_{index}.sql.gz"
        path.write_bytes(b"x" * 100)
        set_age(path, days=age)
        files.append(path)

    candidates = unique_candidates([backups])
    remove = removal_plan(
        candidates,
        keep_latest=2,
        retention_days=30,
        max_total_bytes=300,
        now=datetime.now(timezone.utc),
    )

    assert len(remove) == 2
    assert files[-1] not in remove
    assert files[-2] not in remove


def test_standard_and_latest_backups_are_not_named_candidates(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    directory = Path("data/backups/postgres")
    directory.mkdir(parents=True)
    (directory / "local_20260723_190133.sql.gz").write_bytes(b"standard")
    (directory / "latest.sql.gz").write_bytes(b"latest")
    named = directory / "local_before_migration.sql.gz"
    named.write_bytes(b"named")

    assert unique_candidates([directory]) == [named]
