"""Exercise the real maintenance entrypoint against isolated backup fixtures."""
import gzip
import importlib.util
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location('maintenance_retention', ROOT / 'scripts/verified_backup_retention.py')
retention = importlib.util.module_from_spec(spec)
spec.loader.exec_module(retention)


def fixture_store(tmp_path):
    scripts = tmp_path / 'scripts'
    scripts.mkdir()
    for name in ('verified_backup_retention.py', 'run_storage_maintenance.sh', 'postgres-backup.sh',
                 'compress_sql_backups.sh', 'prune_postgres_backups.py',
                 'prune_named_database_backups.py', 'prune_debug_data.sh'):
        shutil.copy2(ROOT / 'scripts' / name, scripts / name)
    (tmp_path / 'backups').mkdir()
    (tmp_path / 'debug_data').mkdir()
    folder = retention.pool(tmp_path, True)
    return folder


def snapshot(folder, now, days, compressed=False, pinned=False):
    created = now - timedelta(days=days)
    name = 'db-' + created.strftime('%Y%m%dT%H%M%SZ') + '.dump'
    dump = folder / name
    dump.write_bytes(b'isolated-dump-fixture')
    (folder / (name + '.toc')).write_text('fixture TOC')
    globals_file = folder / (name + '.globals.sql')
    globals_file.write_bytes(b'-- role definitions fixture\n')
    retention.commit_record(folder, dump, created)
    if compressed:
        globals_file.with_suffix('.sql.gz').write_bytes(gzip.compress(globals_file.read_bytes()))
        globals_file.unlink()
    if pinned:
        (folder / (name + '.keep')).touch()
    return dump


@pytest.mark.parametrize('compressed', [False, True])
def test_real_pipeline_repeats_without_losing_verified_snapshots(tmp_path, compressed):
    folder = fixture_store(tmp_path)
    now = datetime.now(timezone.utc)
    current = snapshot(folder, now, 0, compressed=compressed)
    previous = snapshot(folder, now, 1, compressed=compressed)
    obsolete = snapshot(folder, now, 2, compressed=compressed)
    pinned = snapshot(folder, now, 40, compressed=compressed, pinned=True)
    unknown = folder / 'unmanaged.dump'
    unknown.write_bytes(b'preserve')
    ordinary = tmp_path / 'backups' / 'ordinary.sql'
    ordinary.write_text('-- ordinary backup\n')
    seed = tmp_path / 'backups' / 'retention-20261019'
    seed.mkdir()
    (seed / '.keep').touch()
    (seed / 'globals.sql').write_text('-- seed roles\n')
    # A valid same-day snapshot must prevent any database operation.
    binaries = tmp_path / 'bin'
    binaries.mkdir()
    docker = binaries / 'docker'
    docker.write_text('#!/bin/sh\necho UNEXPECTED_DATABASE_OPERATION >&2\nexit 97\n')
    docker.chmod(0o755)
    env = dict(os.environ, PATH=str(binaries) + os.pathsep + os.environ['PATH'])
    for attempt in range(2):
        result = subprocess.run(['bash', 'scripts/run_storage_maintenance.sh'], cwd=tmp_path,
                                env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        valid, warnings = retention.records(folder, now)
        assert warnings == []
        assert {record['name'] for record in valid} == {current.name, previous.name, pinned.name}
        assert unknown.read_bytes() == b'preserve'
        assert (seed / 'globals.sql').is_file()
        assert not (seed / 'globals.sql.gz').exists()
        assert not obsolete.exists()
        assert not (folder / (obsolete.name + '.globals.sql.gz')).exists()
        assert (folder / 'latest.dump').resolve() == current
        summary = json.loads((folder / 'last-success.json').read_text())
        assert summary['created_new_dump'] is False
        assert summary['verified_retained'] == 3
        assert 'UNEXPECTED_DATABASE_OPERATION' not in result.stderr
    assert gzip.decompress((tmp_path / 'backups' / 'ordinary.sql.gz').read_bytes()) == b'-- ordinary backup\n'


@pytest.mark.parametrize('content', [b'not gzip', gzip.compress(b'roles')[:-5], gzip.compress(b'')])
def test_invalid_compressed_globals_are_preserved_but_not_verified(tmp_path, content):
    folder = retention.pool(tmp_path, True)
    now = datetime.now(timezone.utc)
    dump = snapshot(folder, now, 0, compressed=True)
    side = folder / (dump.name + '.globals.sql.gz')
    side.write_bytes(content)
    records, warnings = retention.records(folder, now)
    assert records == []
    assert warnings
    assert dump.exists() and side.read_bytes() == content


def test_compressed_globals_symlink_rejected(tmp_path):
    folder = retention.pool(tmp_path, True)
    now = datetime.now(timezone.utc)
    dump = snapshot(folder, now, 0, compressed=True)
    side = folder / (dump.name + '.globals.sql.gz')
    side.unlink()
    outside = tmp_path / 'outside.gz'
    outside.write_bytes(gzip.compress(b'roles'))
    side.symlink_to(outside)
    records, warnings = retention.records(folder, now)
    assert records == [] and warnings
    assert side.is_symlink() and outside.exists()


def test_adopt_existing_compressed_seed_preserves_original_files(tmp_path, monkeypatch):
    seed = tmp_path / 'backups' / 'retention-20261019'
    seed.mkdir(parents=True)
    dump = seed / 'local-20261019.dump'
    dump.write_bytes(b'seed-fixture')
    (seed / 'fresh.sha256').write_text(retention.sha(dump) + '  local-20261019.dump\n')
    roles = seed / 'globals.sql.gz'
    roles.write_bytes(gzip.compress(b'-- fixture seed roles\n'))
    folder = retention.pool(tmp_path, True)

    def validate(root, archive, toc):
        assert archive.read_bytes() == dump.read_bytes()
        toc.write_text('fixture TOC')

    monkeypatch.setattr(retention, 'validate_archive', validate)
    record = retention.adopt(tmp_path, folder)
    valid, warnings = retention.records(folder, datetime.now(timezone.utc))
    assert warnings == [] and len(valid) == 1
    side = folder / (record['name'] + '.globals.sql.gz')
    assert side.read_bytes() == roles.read_bytes()
    assert dump.is_file() and roles.is_file()
    assert (folder / record['name']).stat().st_ino == dump.stat().st_ino
