import gzip
import os
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("dump_status", [0, 42])
def test_automatic_backup_promotes_only_successful_dump(tmp_path, dump_status):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for name in ("docker-compose-build.sh", "prune_postgres_backups.py"):
        shutil.copy2(ROOT / "scripts" / name, scripts)
    backups = tmp_path / "data" / "backups" / "postgres"
    backups.mkdir(parents=True)
    previous = backups / "local_20201122_120000.sql.gz"
    previous.write_bytes(gzip.compress(b"previous snapshot"))
    latest = backups / "latest.sql.gz"
    os.link(previous, latest)

    binaries = tmp_path / "bin"
    binaries.mkdir()
    docker = binaries / "docker"
    docker.write_text(
        "#!/bin/sh\n"
        'case "$*" in\n'
        '  "compose ps -q postgres") printf "fixture-container\\n";;\n'
        '  "compose exec -T postgres pg_dump -U local local")\n'
        f'    printf "new snapshot"; exit {dump_status};;\n'
        '  "compose up -d app") exit 0;;\n'
        '  *) exit 96;;\n'
        'esac\n'
    )
    docker.chmod(0o755)
    result = subprocess.run(
        ["bash", "scripts/docker-compose-build.sh", "up", "-d", "app"],
        cwd=tmp_path,
        env={
            **os.environ,
            "PATH": str(binaries) + os.pathsep + os.environ["PATH"],
            "AUTO_DB_BACKUP": "1",
            "POSTGRES_USER": "local",
            "POSTGRES_DB": "local",
        },
        check=True,
        capture_output=True,
        text=True,
    )

    if dump_status == 0:
        assert gzip.decompress(latest.read_bytes()) == b"new snapshot"
        assert "Postgres backup complete:" in result.stdout
    else:
        assert sorted(backups.iterdir()) == [latest, previous]
        assert latest.samefile(previous)
        assert "WARNING: Postgres backup failed" in result.stdout
