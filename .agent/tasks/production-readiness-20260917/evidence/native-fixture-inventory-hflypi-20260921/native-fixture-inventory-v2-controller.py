#!/usr/bin/env python3
"""Collect frozen pytest fixture metadata without executing test bodies.

This is an admission-inventory primitive, not a test runner or classifier.  It
records pytest's resolved fixture definitions for every collected frozen node so
that a later reviewed classifier can partition the complete collection without
using module-name guesses.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import runpy
import shutil
import stat
import subprocess
import sys
import time


SUPPORT = Path(__file__).resolve().parent
CONTROLS = SUPPORT / "native_fixture_inventory_hflypi_checks.py"
GUARD_HELPER = SUPPORT / "native_guard_checks_hflypi.py"
BASE = Path("/private/tmp/localos-readiness-20260921.hfLYPi")
SOURCE = BASE / "source"
NATIVE = BASE / "native"
EVIDENCE = NATIVE / "evidence"
VENV = NATIVE / "venv/bin/python"
INSTALLED_GUARD = SOURCE / "src/sitecustomize.py"
COLLECTION = EVIDENCE / "native-collection-hflypi-v3.json"
DESTINATION = EVIDENCE / "native-fixture-inventory-v2.json"
FAILURE = EVIDENCE / "native-fixture-inventory-v2-terminal-failure.json"
DEFAULT_GUARD_SHA256 = "07d3e2dc19cbb0f9e542a6d0835ea17b5efcc5713391c152a833e6efefd61150"
COLLECTION_SHA256 = "de5bdffd3c61191c9395032b9a927afe75a60d1713a995fcd8917e822a7753b4"
EXPECTED_BLOBS = 5720
EXPECTED_NODES = 5481
MIN_START = 5 * 1024**3
MAX_SECONDS = 180
METADATA_DATABASE_URL = "postgresql+psycopg2://metadata_only@127.0.0.1:1/localos_metadata_only"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def support_hashes() -> dict[str, str]:
    paths = {"controller_sha256": Path(__file__).resolve(), "controls_sha256": CONTROLS, "guard_helper_sha256": GUARD_HELPER}
    result = {}
    for name, path in paths.items():
        if not path.is_file() or path.is_symlink():
            raise RuntimeError("support provenance path is not a regular file")
        result[name] = sha256(path)
    return result


def source_inventory() -> dict[str, tuple[int, int, int]]:
    result = {}
    for directory, _, names in os.walk(SOURCE, followlinks=False):
        for name in names:
            path = Path(directory) / name
            status = path.lstat()
            result[str(path.relative_to(SOURCE))] = (status.st_mode, status.st_size, status.st_mtime_ns)
    return result


def nodeids_from_collection(path: Path) -> list[str]:
    if not path.is_file() or path.is_symlink():
        raise RuntimeError("frozen collection artifact is unavailable")
    payload = json.loads(path.read_text())
    stdout = payload.get("stdout")
    if not isinstance(stdout, str):
        raise RuntimeError("frozen collection stdout is unavailable")
    if sha256(path) != COLLECTION_SHA256:
        raise RuntimeError("frozen collection artifact identity differs")
    nodeids = [line.strip() for line in stdout.splitlines() if line.strip().startswith("tests/")]
    if len(nodeids) != EXPECTED_NODES or len(set(nodeids)) != len(nodeids):
        raise RuntimeError("frozen collection node inventory is not exact")
    return nodeids


def approved_runtime_source(value: str) -> bool:
    try:
        path = Path(value).resolve(strict=True)
    except FileNotFoundError:
        return False
    if not path.is_file() or path.is_symlink():
        return False
    for root in (NATIVE / "venv", Path(sys.base_prefix)):
        try:
            path.relative_to(root.resolve(strict=True))
            return True
        except ValueError:
            continue
    return False


def same_directory_identity(left: os.stat_result, right: os.stat_result) -> bool:
    return stat.S_ISDIR(right.st_mode) and left.st_dev == right.st_dev and left.st_ino == right.st_ino


def output_text(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    return str(value)


def profile_environment(inherited: dict[str, str], guarded: dict[str, str]) -> dict[str, str]:
    if "DATABASE_URL" in inherited or "DATABASE_URL" in guarded:
        raise RuntimeError("fixture inventory refuses an inherited database URL")
    result = dict(guarded)
    result["DATABASE_URL"] = METADATA_DATABASE_URL
    return result


def owned_result_is_unchanged(directory: Path, directory_status: os.stat_result, result: Path, result_status: os.stat_result, expected_hash: str) -> bool:
    try:
        if not same_directory_identity(directory_status, directory.lstat()):
            return False
        if set(path.name for path in directory.iterdir()) != {"records.json"}:
            return False
        raw = result.read_bytes()
        return result.lstat() == result_status and hashlib.sha256(raw).hexdigest() == expected_hash
    except OSError:
        return False


def validate_records(records: object, expected_nodeids: list[str]) -> dict[str, int]:
    if not isinstance(records, list) or len(records) != len(expected_nodeids):
        raise RuntimeError("fixture inventory record count differs from frozen collection")
    observed = []
    fixture_defs = 0
    frozen_sources = 0
    for record in records:
        if not isinstance(record, dict):
            raise RuntimeError("fixture inventory record is invalid")
        nodeid = record.get("nodeid")
        module_path = record.get("module_path")
        module_hash = record.get("module_sha256")
        class_name = record.get("class_name")
        function_name = record.get("function_name")
        fixture_names = record.get("fixture_names")
        fixtures = record.get("fixtures")
        marker_names = record.get("marker_names")
        usefixtures_args = record.get("usefixtures_args")
        if not isinstance(nodeid, str) or not isinstance(module_path, str) or not re.fullmatch(r"[0-9a-f]{64}", str(module_hash)):
            raise RuntimeError("fixture inventory node identity is invalid")
        if not module_path.startswith("tests/") or not isinstance(class_name, (str, type(None))) or not isinstance(function_name, str) or not function_name or not isinstance(fixtures, list):
            raise RuntimeError("fixture inventory module path or fixture list is invalid")
        for names in (fixture_names, marker_names, usefixtures_args):
            if not isinstance(names, list) or any(not isinstance(name, str) for name in names):
                raise RuntimeError("fixture inventory name list is invalid")
        observed.append(nodeid)
        for fixture in fixtures:
            if not isinstance(fixture, dict):
                raise RuntimeError("fixture definition is invalid")
            required = ("name", "baseid", "scope", "source_kind", "source_path", "source_sha256", "argnames")
            if any(key not in fixture for key in required):
                raise RuntimeError("fixture definition fields are incomplete")
            if fixture["source_kind"] not in {"frozen", "runtime"} or not re.fullmatch(r"[0-9a-f]{64}", str(fixture["source_sha256"])):
                raise RuntimeError("fixture definition provenance is invalid")
            if not all(isinstance(fixture[key], str) for key in ("name", "baseid", "scope", "source_path")) or not isinstance(fixture["argnames"], list) or any(not isinstance(name, str) for name in fixture["argnames"]):
                raise RuntimeError("fixture definition metadata is invalid")
            if fixture["source_kind"] == "frozen":
                frozen_sources += 1
                if not isinstance(fixture["source_path"], str) or fixture["source_path"].startswith("/"):
                    raise RuntimeError("frozen fixture source escaped the frozen tree")
            elif not approved_runtime_source(fixture["source_path"]):
                raise RuntimeError("runtime fixture source escaped approved runtime roots")
            fixture_defs += 1
    if observed != expected_nodeids or len(set(observed)) != len(observed):
        raise RuntimeError("fixture inventory node order or identity differs from frozen collection")
    return {"records": len(observed), "fixture_definitions": fixture_defs, "frozen_fixture_definitions": frozen_sources}


def child_source(result_path: Path) -> str:
    return """
import hashlib
import json
import os
from pathlib import Path
import sys

def deny(event, arguments):
    if event.startswith('socket.') or event in {'subprocess.Popen', 'os.system', 'os.posix_spawn', 'os.posix_spawnp', 'os.exec', 'os.execve', 'os.fork', 'os.forkpty', 'os.spawn'}:
        raise PermissionError('hfLYPi fixture collection denies sockets and process spawning')

sys.addaudithook(deny)
import psycopg2
def denied_connect(*arguments, **keywords):
    raise PermissionError('hfLYPi fixture collection denies libpq connection')
psycopg2._connect = denied_connect
import pytest

SOURCE = Path(%r).resolve()
RESULT = Path(%r)
COLLECTION = Path(%r)
COLLECTION_SHA256 = %r
VENV_ROOT = Path(%r).resolve()
STDLIB_ROOT = Path(%r).resolve()

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def provenance(filename):
    path = Path(filename).resolve(strict=True)
    try:
        relative = path.relative_to(SOURCE)
    except ValueError:
        if not path.is_file() or path.is_symlink():
            raise RuntimeError('runtime fixture source is not a regular file')
        try:
            path.relative_to(VENV_ROOT)
        except ValueError:
            try:
                path.relative_to(STDLIB_ROOT)
            except ValueError:
                raise RuntimeError('runtime fixture source is outside approved runtime roots')
        return 'runtime', str(path), digest(path)
    if not path.is_file() or path.is_symlink():
        raise RuntimeError('frozen fixture source is not a regular file')
    return 'frozen', str(relative), digest(path)

class Inventory:
    def __init__(self):
        self.records = []

    def pytest_collection_finish(self, session):
        for item in session.items:
            module_path = Path(str(item.path)).resolve(strict=True)
            try:
                module_relative = module_path.relative_to(SOURCE)
            except ValueError:
                raise RuntimeError('collected item is outside frozen source')
            if not module_path.is_file() or module_path.is_symlink():
                raise RuntimeError('collected module is not a regular frozen file')
            definitions = getattr(item._fixtureinfo, 'name2fixturedefs', {})
            fixtures = []
            for name in sorted(item.fixturenames):
                for definition in definitions.get(name) or ():
                    function = definition.func
                    source_kind, source_path, source_hash = provenance(function.__code__.co_filename)
                    fixtures.append({'name': name, 'baseid': str(definition.baseid or ''), 'scope': str(definition.scope), 'source_kind': source_kind, 'source_path': source_path, 'source_sha256': source_hash, 'argnames': list(definition.argnames or ())})
            usefixtures = []
            marker_names = []
            for marker in item.iter_markers():
                marker_names.append(marker.name)
                if marker.name == 'usefixtures':
                    usefixtures.extend(value for value in marker.args if isinstance(value, str))
            function = getattr(item, 'function', None)
            owner = getattr(item, 'cls', None)
            function_name = getattr(function, '__name__', None) or getattr(item, 'originalname', None) or item.name
            self.records.append({'nodeid': item.nodeid, 'module_path': str(module_relative), 'module_sha256': digest(module_path), 'class_name': getattr(owner, '__name__', None), 'function_name': function_name, 'fixture_names': sorted(item.fixturenames), 'fixtures': fixtures, 'marker_names': sorted(set(marker_names)), 'usefixtures_args': sorted(set(usefixtures))})

plugin = Inventory()
result = pytest.main(['--collect-only', '-q', '--maxfail=1', '-p', 'no:cacheprovider', 'tests'], plugins=[plugin])
nodeids = [record['nodeid'] for record in plugin.records]
collection_payload = json.loads(COLLECTION.read_text())
if hashlib.sha256(COLLECTION.read_bytes()).hexdigest() != COLLECTION_SHA256:
    raise RuntimeError('frozen collection artifact identity differs in child')
reference = [line.strip() for line in collection_payload.get('stdout', '').splitlines() if line.strip().startswith('tests/')]
if result != 0 or len(nodeids) != %d or len(nodeids) != len(set(nodeids)) or len(reference) != %d or len(reference) != len(set(reference)):
    raise RuntimeError('pytest collection did not reproduce the frozen node inventory')
payload = {'schema_version': 1, 'kind': 'frozen-pytest-fixture-metadata-only', 'collection_count': len(nodeids), 'records': plugin.records}
descriptor = os.open(RESULT, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
try:
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()
    offset = 0
    while offset < len(raw):
        written = os.write(descriptor, raw[offset:])
        if written <= 0:
            raise RuntimeError('temporary inventory write failed')
        offset += written
finally:
    os.close(descriptor)
print('HFLYPI_FIXTURE_INVENTORY=' + json.dumps({'collected': len(nodeids), 'records': len(plugin.records), 'result_path': str(RESULT), 'result_sha256': hashlib.sha256(raw).hexdigest()}))
raise SystemExit(0)
""" % (str(SOURCE), str(result_path), str(COLLECTION), COLLECTION_SHA256, str(NATIVE / "venv").rstrip("/"), str(Path(sys.base_prefix)), EXPECTED_NODES, EXPECTED_NODES)


def parse_callback(stdout: str, result_path: Path) -> dict[str, object]:
    rows = [row for row in stdout.splitlines() if row.startswith("HFLYPI_FIXTURE_INVENTORY=")]
    if len(rows) != 1:
        raise RuntimeError("fixture inventory callback is missing")
    payload = json.loads(rows[0].split("=", 1)[1])
    result_hash = payload.get("result_sha256") if isinstance(payload, dict) else None
    if not isinstance(payload, dict) or payload.get("collected") != EXPECTED_NODES or payload.get("records") != EXPECTED_NODES or payload.get("result_path") != str(result_path) or not isinstance(result_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", result_hash):
        raise RuntimeError("fixture inventory callback is invalid")
    return payload


def valid_attempt(value: str) -> str:
    if value != "v2":
        raise argparse.ArgumentTypeError("fixture inventory supports only immutable attempt v2")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", required=True, type=valid_attempt)
    values = parser.parse_args()
    temporary_dir = NATIVE / (".native-fixture-inventory-" + str(os.getpid()) + "-v2")
    temporary = temporary_dir / "records.json"
    if values.attempt != "v2" or DESTINATION.exists() or DESTINATION.is_symlink() or FAILURE.exists() or FAILURE.is_symlink() or temporary_dir.exists() or temporary_dir.is_symlink():
        raise RuntimeError("fixture inventory output path is not fresh")
    if platform.machine() != "arm64" or shutil.disk_usage(BASE).free < MIN_START:
        raise RuntimeError("fixture inventory requires arm64 and 5 GiB free")
    helpers = runpy.run_path(str(SUPPORT / "native_guard_checks_hflypi.py"))
    support_provenance = support_hashes()
    helpers["verify_endpoints"]()
    if not INSTALLED_GUARD.is_file() or INSTALLED_GUARD.is_symlink() or sha256(INSTALLED_GUARD) != DEFAULT_GUARD_SHA256:
        raise RuntimeError("installed default guard identity differs")
    frozen_before = helpers["verify_frozen_source"]()
    if frozen_before != EXPECTED_BLOBS:
        raise RuntimeError("unexpected frozen source blob count before collection")
    expected_nodeids = nodeids_from_collection(COLLECTION)
    before = source_inventory()
    environment = helpers["environment"](DEFAULT_GUARD_SHA256)
    environment.pop("LOCALOS_HFLYPI_PROBE_DSN", None)
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    environment = profile_environment(dict(os.environ), environment)
    temporary_dir.mkdir(mode=0o700)
    owner_status = temporary_dir.lstat()
    started = time.monotonic()
    completed = None
    issue = None
    failure_stdout = ""
    failure_stderr = ""
    timed_out = False
    callback = None
    summary = None
    records = None
    frozen_after = None
    guard_after = None
    source_inventory_unchanged = None
    postverification_error = None
    try:
        completed = subprocess.run(["/usr/bin/arch", "-arm64", str(VENV), "-B", "-c", child_source(temporary)], cwd=SOURCE, env=environment, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=MAX_SECONDS, check=False)
        if completed.returncode != 0 or completed.stderr:
            raise RuntimeError("fixture collection child failed: exit=" + str(completed.returncode))
        callback = parse_callback(completed.stdout, temporary)
        if not temporary.is_file() or temporary.is_symlink():
            raise RuntimeError("fixture collection child did not produce a regular temporary artifact")
        temporary_status = temporary.lstat()
        raw = temporary.read_bytes()
        if temporary.lstat() != temporary_status or hashlib.sha256(raw).hexdigest() != callback["result_sha256"]:
            raise RuntimeError("fixture collection temporary artifact changed while reading")
        child_payload = json.loads(raw)
        records = child_payload.get("records") if isinstance(child_payload, dict) else None
        summary = validate_records(records, expected_nodeids)
    except Exception:
        error = sys.exception()
        issue = str(error) or "unknown fixture inventory error"
        failure_stdout = output_text(getattr(error, "stdout", ""))
        failure_stderr = output_text(getattr(error, "stderr", ""))
        timed_out = isinstance(error, subprocess.TimeoutExpired)
    finally:
        try:
            frozen_after = helpers["verify_frozen_source"]()
            after = source_inventory()
            guard_after = sha256(INSTALLED_GUARD) if INSTALLED_GUARD.is_file() and not INSTALLED_GUARD.is_symlink() else None
            source_inventory_unchanged = before == after
            if frozen_after != EXPECTED_BLOBS or not source_inventory_unchanged or guard_after != DEFAULT_GUARD_SHA256:
                verification_issue = "frozen source or default guard changed during collection"
                postverification_error = verification_issue
                issue = verification_issue if issue is None else issue + "; " + verification_issue
        except Exception:
            verification_issue = "post-collection identity verification failed: " + (str(sys.exception()) or "unknown error")
            postverification_error = verification_issue
            issue = verification_issue if issue is None else issue + "; " + verification_issue
    duration = round(time.monotonic() - started, 3)
    if issue is not None:
        failure = {"schema_version": 1, "kind": "frozen-pytest-fixture-metadata-terminal-failure", "attempt": values.attempt, "error": issue, "duration_seconds": duration, "returncode": completed.returncode if completed is not None else None, "stdout": output_text(completed.stdout) if completed is not None else failure_stdout, "stderr": output_text(completed.stderr) if completed is not None else failure_stderr, "timed_out": timed_out, "temporary_directory": str(temporary_dir), "frozen_blobs_after": frozen_after, "installed_guard_sha256_after": guard_after, "source_inventory_unchanged": source_inventory_unchanged, "postverification_error": postverification_error, **support_provenance}
        helpers["write_exclusive"](FAILURE, json.dumps(failure, indent=2, sort_keys=True))
        raise RuntimeError("fixture inventory failed; immutable terminal capture written")
    payload = {"schema_version": 1, "kind": "frozen-pytest-fixture-metadata-only", "attempt": values.attempt, "collection_count": EXPECTED_NODES, "collection_sha256": sha256(COLLECTION), "installed_guard_sha256_before": DEFAULT_GUARD_SHA256, "installed_guard_sha256_after": guard_after, "frozen_blobs_before": frozen_before, "frozen_blobs_after": frozen_after, "source_inventory_unchanged": source_inventory_unchanged, "postverification_error": postverification_error, "callback": callback, "summary": summary, "records": records, "duration_seconds": duration, **support_provenance}
    try:
        if not owned_result_is_unchanged(temporary_dir, owner_status, temporary, temporary_status, callback["result_sha256"]):
            raise RuntimeError("owned temporary result changed before cleanup")
        temporary.unlink()
        temporary_dir.rmdir()
    except Exception:
        failure = {"schema_version": 1, "kind": "frozen-pytest-fixture-metadata-terminal-failure", "attempt": values.attempt, "error": "owned temporary directory cleanup failed: " + (str(sys.exception()) or "unknown error"), "duration_seconds": duration, "returncode": completed.returncode, "stdout": output_text(completed.stdout), "stderr": output_text(completed.stderr), "timed_out": False, "temporary_directory": str(temporary_dir), "frozen_blobs_after": frozen_after, "installed_guard_sha256_after": guard_after, "source_inventory_unchanged": source_inventory_unchanged, "postverification_error": postverification_error, **support_provenance}
        helpers["write_exclusive"](FAILURE, json.dumps(failure, indent=2, sort_keys=True))
        raise RuntimeError("fixture inventory cleanup failed; immutable terminal capture written")
    helpers["write_exclusive"](DESTINATION, json.dumps(payload, indent=2, sort_keys=True))
    print(json.dumps({"collection_count": EXPECTED_NODES, **summary, "duration_seconds": duration}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
