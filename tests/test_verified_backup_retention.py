import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

spec = importlib.util.spec_from_file_location('verified_retention', Path(__file__).parents[1] / 'scripts/verified_backup_retention.py')
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)
NOW = datetime(2026, 10, 19, 12, tzinfo=timezone.utc)


def snapshot(folder, days, size=10, pinned=False):
    created = NOW - timedelta(days=days)
    name = 'db-' + created.strftime('%Y%m%dT%H%M%SZ') + '.dump'
    path = folder / name
    path.write_bytes(b'x' * size)
    for suffix in ('.toc', '.globals.sql'):
        (folder / (name + suffix)).write_text('fixture')
    backup.commit_record(folder, path, created)
    if pinned:
        (folder / (name + '.keep')).touch()
    return path


def test_preview_does_not_create_store(tmp_path):
    assert backup.run(tmp_path, now=NOW)['verified'] == 0
    assert not (tmp_path / 'data').exists()


def test_minimum_two_weekly_and_pin_survive(tmp_path):
    folder = backup.pool(tmp_path, True)
    paths = [snapshot(folder, d, pinned=d == 40) for d in (0, 1, 2, 8, 9, 40)]
    items, warnings = backup.records(folder, NOW)
    assert warnings == []
    assert {r['name'] for r in backup.removal_plan(items, NOW)} == {paths[2].name, paths[4].name}
    assert {r['name'] for r in backup.removal_plan(items, NOW, cap=20)} == {paths[2].name, paths[3].name, paths[4].name}


def test_corruption_unverified_and_symlink_never_deleted(tmp_path):
    folder = backup.pool(tmp_path, True)
    paths = [snapshot(folder, d) for d in (0, 1, 2, 3)]
    paths[2].write_bytes(b'corrupted!')
    paths[3].unlink()
    paths[3].symlink_to(paths[0])
    unknown = folder / 'unknown.dump'
    unknown.write_bytes(b'preserve')
    items, warnings = backup.records(folder, NOW)
    assert len(warnings) == 2
    assert len(items) == 2
    assert backup.rotate(folder, items, NOW) == []
    assert unknown.exists() and paths[2].exists() and paths[3].is_symlink()


def test_failed_backup_never_prunes_old_snapshots(tmp_path):
    folder = backup.pool(tmp_path, True)
    paths = [snapshot(folder, d) for d in (1, 2, 3)]
    with patch.object(backup, 'create_backup', side_effect=RuntimeError('provider failure')), patch.object(backup, 'rotate') as rotate:
        with pytest.raises(RuntimeError):
            backup.run(tmp_path, apply=True, now=NOW)
    rotate.assert_not_called()
    assert all(p.exists() for p in paths)


def test_repeat_today_skips_dump_and_rotates(tmp_path):
    folder = backup.pool(tmp_path, True)
    paths = [snapshot(folder, d) for d in (0, 1, 2)]
    with patch.object(backup, 'create_backup') as create:
        result = backup.run(tmp_path, apply=True, now=NOW)
        repeat = backup.run(tmp_path, apply=True, now=NOW)
    create.assert_not_called()
    assert result['removed'] == [paths[2].name]
    assert repeat['removed'] == []
    assert (folder / 'latest.dump').resolve() == paths[0]


def test_keep_added_after_scan_prevents_deletion(tmp_path):
    folder = backup.pool(tmp_path, True)
    paths = [snapshot(folder, d) for d in (0, 1, 2)]
    items, _ = backup.records(folder, NOW)
    (folder / '.keep').touch()
    assert backup.rotate(folder, items, NOW) == []
    assert all(p.exists() for p in paths)


def test_path_traversal_and_store_symlink_rejected(tmp_path):
    folder = backup.pool(tmp_path, True)
    path = snapshot(folder, 0)
    manifest = folder / (path.name + '.verified.json')
    value = json.loads(manifest.read_text())
    value['name'] = '../../../outside.dump'
    manifest.write_text(json.dumps(value))
    assert backup.records(folder, NOW)[0] == []
    root = tmp_path / 'other'
    root.mkdir()
    (root / 'data').symlink_to(tmp_path / 'data')
    with pytest.raises(ValueError):
        backup.pool(root, True)


def test_concurrent_writer_is_skipped(tmp_path):
    folder = backup.pool(tmp_path, True)
    with (folder / '.lock').open('a') as lock:
        backup.fcntl.flock(lock, backup.fcntl.LOCK_EX | backup.fcntl.LOCK_NB)
        assert backup.run(tmp_path, apply=True, now=NOW)['status'] == 'already_running'
