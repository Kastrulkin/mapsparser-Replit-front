from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "prune_postgres_backups.py"


def test_prune_keeps_milestones_and_links_latest_to_newest(tmp_path: Path) -> None:
    start = datetime(2026, 7, 1, 12, 0, 0)
    automated: list[Path] = []
    for offset in range(10):
        timestamp = start + timedelta(days=offset)
        path = tmp_path / f"local_{timestamp:%Y%m%d_%H%M%S}.sql.gz"
        path.write_bytes(f"backup-{offset}".encode())
        automated.append(path)

    milestone = tmp_path / "local_20260702_120000_before_migration.sql.gz"
    milestone.write_bytes(b"milestone")

    dry_run = subprocess.run(
        [sys.executable, str(SCRIPT), "--directory", str(tmp_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "KEEP_UNPARSED" in dry_run.stdout
    assert all(path.exists() for path in automated)
    assert milestone.exists()

    subprocess.run(
        [sys.executable, str(SCRIPT), "--directory", str(tmp_path), "--apply"],
        check=True,
        capture_output=True,
        text=True,
    )

    remaining = sorted(tmp_path.glob("local_????????_??????.sql.gz"))
    assert len(remaining) == 7
    assert milestone.exists()
    latest = tmp_path / "latest.sql.gz"
    newest = automated[-1]
    assert latest.exists()
    assert os.stat(latest).st_ino == os.stat(newest).st_ino
