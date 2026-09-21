#!/usr/bin/env python3
"""Pure structural controls for the frozen fixture metadata collector."""

from __future__ import annotations

import os
from pathlib import Path
import runpy
import shutil
import stat
import tempfile
from types import SimpleNamespace


SUPPORT = Path(__file__).resolve().parent


def record(nodeid: str, module: str, fixtures: list[dict[str, object]]) -> dict[str, object]:
    return {"nodeid": nodeid, "module_path": module, "module_sha256": "a" * 64, "class_name": None, "function_name": "test_example", "fixture_names": ["monkeypatch"], "fixtures": fixtures, "marker_names": [], "usefixtures_args": []}


def fixture(kind: str = "frozen", path: str = "tests/conftest.py") -> dict[str, object]:
    return {"name": "monkeypatch", "baseid": "", "scope": "function", "source_kind": kind, "source_path": path, "source_sha256": "b" * 64, "argnames": []}


def rejected(action) -> None:
    try:
        action()
    except RuntimeError:
        return
    raise AssertionError("invalid fixture inventory was accepted")


def main() -> int:
    collector = runpy.run_path(str(SUPPORT / "native_fixture_inventory_hflypi.py"))
    provenance = collector["support_hashes"]()
    assert set(provenance) == {"controller_sha256", "controls_sha256", "guard_helper_sha256"}
    assert all(len(value) == 64 for value in provenance.values())
    stable = SimpleNamespace(st_dev=1, st_ino=2, st_mode=stat.S_IFREG | 0o600, st_nlink=1, st_uid=3, st_gid=4, st_size=5, st_mtime_ns=6, st_ctime_ns=7, st_atime_ns=8)
    atime_only = SimpleNamespace(st_dev=1, st_ino=2, st_mode=stat.S_IFREG | 0o600, st_nlink=1, st_uid=3, st_gid=4, st_size=5, st_mtime_ns=6, st_ctime_ns=7, st_atime_ns=99)
    assert collector["same_result_identity"](stable, atime_only)
    for changed in ("st_dev", "st_ino", "st_mode", "st_nlink", "st_uid", "st_gid", "st_size", "st_mtime_ns", "st_ctime_ns"):
        altered = SimpleNamespace(st_dev=1, st_ino=2, st_mode=stat.S_IFREG | 0o600, st_nlink=1, st_uid=3, st_gid=4, st_size=5, st_mtime_ns=6, st_ctime_ns=7, st_atime_ns=8)
        setattr(altered, changed, getattr(altered, changed) + 1)
        assert not collector["same_result_identity"](stable, altered)
    symlink = SimpleNamespace(st_dev=1, st_ino=2, st_mode=stat.S_IFLNK | 0o600, st_nlink=1, st_uid=3, st_gid=4, st_size=5, st_mtime_ns=6, st_ctime_ns=7, st_atime_ns=8)
    assert not collector["same_result_identity"](stable, symlink)
    clean_environment = collector["profile_environment"]({}, {"PYTHONPATH": "/private/tmp/localos-readiness-20260921.hfLYPi/source"})
    assert clean_environment["DATABASE_URL"] == collector["METADATA_DATABASE_URL"]
    rejected(lambda: collector["profile_environment"]({"DATABASE_URL": "postgresql://inherited"}, {}))
    rejected(lambda: collector["profile_environment"]({}, {"DATABASE_URL": "postgresql://guarded"}))
    expected = ["tests/test_one.py::test_one", "tests/test_two.py::test_two"]
    good = [record(expected[0], "tests/test_one.py", [fixture()]), record(expected[1], "tests/test_two.py", [fixture("runtime", str(Path(runpy.__file__).resolve()))])]
    summary = collector["validate_records"](good, expected)
    assert summary == {"records": 2, "fixture_definitions": 2, "frozen_fixture_definitions": 1}
    rejected(lambda: collector["validate_records"](good[:-1], expected))
    duplicate = [record(expected[0], "tests/test_one.py", []), record(expected[0], "tests/test_two.py", [])]
    rejected(lambda: collector["validate_records"](duplicate, expected))
    outside = [record(expected[0], "/outside.py", []), record(expected[1], "tests/test_two.py", [])]
    rejected(lambda: collector["validate_records"](outside, expected))
    escaped_fixture = [record(expected[0], "tests/test_one.py", [fixture("frozen", "/outside.py")]), record(expected[1], "tests/test_two.py", [])]
    rejected(lambda: collector["validate_records"](escaped_fixture, expected))
    malformed_fixture = [record(expected[0], "tests/test_one.py", [{"name": "x"}]), record(expected[1], "tests/test_two.py", [])]
    rejected(lambda: collector["validate_records"](malformed_fixture, expected))
    assert collector["nodeids_from_collection"](collector["COLLECTION"])[0].startswith("tests/")
    assert collector["COLLECTION_SHA256"] == collector["sha256"](collector["COLLECTION"])
    compile(collector["child_source"](Path("/private/tmp/hflypi-fixture-controls.json")), "fixture-inventory-child", "exec")
    guard_source = collector["child_source"](Path("/private/tmp/hflypi-fixture-controls.json"))
    assert "event.startswith('socket.')" in guard_source
    assert "psycopg2._connect = denied_connect" in guard_source
    assert collector["output_text"](b"output\xff") == "output\ufffd"
    assert collector["output_text"]("output") == "output"
    assert collector["output_text"](None) == ""
    missing_runtime = [record(expected[0], "tests/test_one.py", [fixture("runtime", "/private/tmp/hflypi-missing-runtime-source.py")]), record(expected[1], "tests/test_two.py", [])]
    rejected(lambda: collector["validate_records"](missing_runtime, expected))
    directory = Path(tempfile.mkdtemp(prefix="hflypi-fixture-controls-", dir="/private/tmp"))
    try:
        before = directory.lstat()
        os.utime(directory, None)
        assert collector["same_directory_identity"](before, directory.lstat())
        result = directory / "records.json"
        result.write_text("result")
        result_status = result.lstat()
        result_hash = collector["hashlib"].sha256(result.read_bytes()).hexdigest()
        assert collector["owned_result_is_unchanged"](directory, before, result, result_status, result_hash)
        replacement = directory / "replacement"
        replacement.write_text("other!")
        os.replace(replacement, result)
        assert not collector["owned_result_is_unchanged"](directory, before, result, result_status, result_hash)
        (directory / "foreign.txt").write_text("foreign")
        assert not collector["owned_result_is_unchanged"](directory, before, result, result_status, result_hash)
    finally:
        shutil.rmtree(directory)
    print("fixture inventory controls: record shape, exact set, duplicates and source-boundary gates passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
