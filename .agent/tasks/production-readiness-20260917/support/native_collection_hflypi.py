#!/usr/bin/env python3
"""Collect a frozen attempt only after its guarded proof artifacts pass review."""

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
import signal
import subprocess
import sys
import time


SUPPORT = Path(__file__).resolve().parent
BASE = Path("/private/tmp/localos-readiness-20260921.hfLYPi")
SOURCE = BASE / "source"
NATIVE = BASE / "native"
EVIDENCE = NATIVE / "evidence"
SUPPORT_PROBE = SUPPORT / "native_hflypi_probe.py"
INSTALLED_GUARD = SOURCE / "src/sitecustomize.py"
NEGATIVE_CASES = (
    "external_tcp", "foreign_local", "udp", "dns", "postgres_foreign_host",
    "postgres_foreign_database", "postgres_explicit_options", "postgres_pghostaddr",
    "postgres_pgoptions", "postgres_pgservice",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(root: Path) -> dict[str, tuple[int, int, int]]:
    result = {}
    for directory, _, files in os.walk(root, followlinks=False):
        for name in files:
            path = Path(directory) / name
            status = path.lstat()
            result[str(path.relative_to(root))] = (status.st_mode, status.st_size, status.st_mtime_ns)
    return result


def runner(probe: Path) -> str:
    return f"""
import runpy
import sys
def deny_audit(event, arguments):
    if event.startswith('socket.'):
        raise PermissionError('hfLYPi collect-only: socket creation, connect, send, DNS and bind are disabled')
    if event in {{'subprocess.Popen', 'os.system', 'os.posix_spawn', 'os.posix_spawnp', 'os.exec', 'os.execve', 'os.fork', 'os.forkpty', 'os.spawn'}}:
        raise PermissionError('hfLYPi collect-only: process spawning is disabled')
sys.addaudithook(deny_audit)
import psycopg2
def deny_libpq(*arguments, **keywords):
    raise PermissionError('hfLYPi collect-only: database connections are disabled')
psycopg2._connect = deny_libpq
probe = runpy.run_path({str(probe)!r})
probe['_guard_details']()
import pytest
raise SystemExit(pytest.main(['--collect-only', '-q', '--maxfail=1', '-p', 'no:cacheprovider', 'tests']))
"""


def attempt_name(value: str) -> str:
    if not re.fullmatch(r"v[1-9][0-9]*", value):
        raise argparse.ArgumentTypeError("attempt must be v followed by a positive integer")
    return value


def read_json(path: Path) -> dict[str, object]:
    if not path.is_file() or path.is_symlink():
        raise RuntimeError(f"missing canonical evidence artifact: {path}")
    parsed = json.loads(path.read_text())
    if not isinstance(parsed, dict):
        raise RuntimeError(f"invalid evidence payload: {path}")
    return parsed


def require_guard_identity(proof: dict[str, object], guard_hash: str) -> None:
    provenance = proof.get("provenance")
    if proof.get("guard_path") != str(INSTALLED_GUARD) or proof.get("guard_sha256") != guard_hash:
        raise RuntimeError("probe did not load the pinned installed guard")
    if not isinstance(provenance, dict) or provenance.get("nonce") != "hfLYPi" or not isinstance(provenance.get("pid"), int) or provenance["pid"] <= 0:
        raise RuntimeError("probe provenance pid or nonce is invalid")
    if provenance.get("native_port") != 35418 or provenance.get("ryuk") != "disabled; wrapper cleans exact labels":
        raise RuntimeError("probe provenance flags do not match the guarded attempt")


def require_probe_artifact(label: str, mode: str, attempt: str, copied_probe: Path, metadata: dict[str, object], guard_hash: str, docker_current: dict[str, object] | None) -> None:
    artifact = read_json(EVIDENCE / f"native-guard-{label}-{attempt}.json")
    command = [str(NATIVE / "venv/bin/python"), "-B", str(copied_probe), mode]
    if artifact.get("label") != label or artifact.get("command") != command or artifact.get("exit_code") != 0 or artifact.get("timed_out") is True:
        raise RuntimeError(f"{label} proof artifact is not a successful exact command")
    proof_raw = artifact.get("stdout")
    if not isinstance(proof_raw, str):
        raise RuntimeError(f"{label} proof stdout is missing")
    proof = json.loads(proof_raw)
    if not isinstance(proof, dict):
        raise RuntimeError(f"{label} proof payload is invalid")
    require_guard_identity(proof, guard_hash)
    if metadata.get("guard_sha256") != guard_hash or metadata.get("probe_sha256") != sha256(copied_probe):
        raise RuntimeError("metadata does not pin this guard and copied probe")
    if label == "negative":
        checks = proof.get("checks")
        if not isinstance(checks, list) or len(checks) != len(NEGATIVE_CASES):
            raise RuntimeError("negative proof did not report all expected denials")
        observed = {(item.get("case"), item.get("denied")) for item in checks if isinstance(item, dict)}
        if observed != {(case, True) for case in NEGATIVE_CASES}:
            raise RuntimeError("negative proof cases were not all denied exactly once")
    elif label == "child":
        child = proof.get("child")
        if proof.get("child_guard_propagated") is not True or not isinstance(child, dict):
            raise RuntimeError("child propagation flag is absent")
        if child.get("origin") != str(INSTALLED_GUARD) or child.get("sha256") != guard_hash or child.get("denied") is not True or child.get("bytecode_disabled") is not True or child.get("user_site_disabled") is not True:
            raise RuntimeError("child guard path, hash or flags are invalid")
        provenance = proof.get("provenance")
        if not isinstance(provenance, dict) or not isinstance(child.get("pid"), int) or child.get("pid") <= 0 or child.get("actual_pid") != child.get("pid") or child.get("pid") == provenance.get("pid"):
            raise RuntimeError("child guard pid fields are invalid")
    elif proof.get("own_postgres_verified") is not True or artifact.get("docker_preflight") != docker_current:
        raise RuntimeError("positive proof lacks current exact Docker identity")


def postverify(launcher: dict[str, object], guard_hash: str, before: dict[str, tuple[int, int, int]]) -> dict[str, object]:
    details: dict[str, object] = {"frozen_blob_count": launcher["verify_frozen_source"]()}
    details["guard_sha256"] = sha256(INSTALLED_GUARD)
    details["guard_matches_preflight"] = details["guard_sha256"] == guard_hash
    after = inventory(SOURCE)
    details["inventory_files_after"] = len(after)
    details["inventory_changed_paths"] = sorted(path for path in before.keys() | after.keys() if before.get(path) != after.get(path))
    if details["guard_matches_preflight"] is not True:
        raise RuntimeError("installed guard hash changed during collection")
    return details


def terminate_runner(process: subprocess.Popen[str], stdout: str, stderr: str) -> tuple[str, str, str | None]:
    if process.poll() is not None:
        return stdout, stderr, None
    problem = None
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    except BaseException:
        error = sys.exception()
        problem = f"term:{type(error).__name__}"
    try:
        output, errors = process.communicate(timeout=5)
        return output or stdout, errors or stderr, problem
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except BaseException:
            error = sys.exception()
            problem = f"{problem or 'kill'};kill:{type(error).__name__}"
        try:
            output, errors = process.communicate(timeout=5)
            return output or stdout, errors or stderr, problem
        except BaseException:
            error = sys.exception()
            return stdout, f"{stderr}\nrunner cleanup capture: {type(error).__name__}: {error}", f"{problem or 'capture'};capture:{type(error).__name__}"
    except BaseException:
        error = sys.exception()
        return stdout, f"{stderr}\nrunner cleanup capture: {type(error).__name__}: {error}", f"{problem or 'capture'};capture:{type(error).__name__}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", required=True, type=attempt_name)
    arguments = parser.parse_args()
    attempt = arguments.attempt
    destination = EVIDENCE / f"native-collection-hflypi-{attempt}.json"
    metadata_path = EVIDENCE / f"native-guard-metadata-{attempt}.json"
    copied_probe = NATIVE / "native_hflypi_probe_v1.py"
    if destination.exists() or destination.is_symlink():
        raise RuntimeError("collection evidence already exists")
    machine = platform.machine()
    if machine != "arm64":
        raise RuntimeError("native collection requires an arm64 parent process")
    if shutil.disk_usage(BASE).free < 5 * 1024**3:
        raise RuntimeError("collection requires at least 5 GiB free")
    launcher = runpy.run_path(str(SUPPORT / "native_guard_checks_hflypi.py"))
    launcher["verify_endpoints"]()
    if not copied_probe.is_file() or copied_probe.is_symlink():
        raise RuntimeError("copied probe for the requested attempt is missing")
    support_probe_hash = sha256(SUPPORT_PROBE)
    copied_probe_hash = sha256(copied_probe)
    if copied_probe_hash != support_probe_hash:
        raise RuntimeError("copied probe differs from reviewed support probe")
    metadata = read_json(metadata_path)
    if metadata.get("parent_machine") != machine:
        raise RuntimeError("metadata was not captured by an arm64 guarded probe attempt")
    if metadata.get("probe_sha256") != copied_probe_hash:
        raise RuntimeError("metadata does not pin the copied probe before runner startup")
    support_guard = SUPPORT / "native_hflypi_sitecustomize.py"
    if not INSTALLED_GUARD.is_file() or INSTALLED_GUARD.is_symlink() or not support_guard.is_file() or support_guard.is_symlink():
        raise RuntimeError("installed or reviewed guard is not a regular file")
    guard_hash = sha256(INSTALLED_GUARD)
    if metadata.get("guard_sha256") != guard_hash or sha256(support_guard) != guard_hash:
        raise RuntimeError("metadata, installed guard and reviewed guard do not match before runner startup")
    docker = launcher["verify_docker_owner"]()
    require_probe_artifact("negative", "negative", attempt, copied_probe, metadata, guard_hash, None)
    require_probe_artifact("child", "child", attempt, copied_probe, metadata, guard_hash, None)
    require_probe_artifact("own-postgres", "own-postgres", attempt, copied_probe, metadata, guard_hash, docker)
    tracked_before = launcher["verify_frozen_source"]()
    before = inventory(SOURCE)
    environment = launcher["environment"](guard_hash)
    environment.pop("LOCALOS_HFLYPI_PROBE_DSN", None)
    environment.update({"DATABASE_URL": launcher["DSN"], "FLASK_ENV": "testing", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"})
    source = runner(copied_probe)
    command = ["/usr/bin/arch", "-arm64", str(NATIVE / "venv/bin/python"), "-B", "-c", source]
    started = time.monotonic()
    stdout = ""
    stderr = ""
    stopped_reason = None
    process: subprocess.Popen[str] | None = None
    post_error = None
    post_details: dict[str, object] = {}
    try:
        process = subprocess.Popen(command, cwd=SOURCE, env=environment, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        while True:
            try:
                stdout, stderr = process.communicate(timeout=5)
                break
            except subprocess.TimeoutExpired:
                if time.monotonic() - started > 180 or shutil.disk_usage(BASE).free < 2 * 1024**3:
                    stopped_reason = "timeout_or_disk_floor"
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        stdout, stderr = process.communicate(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        stdout, stderr = process.communicate(timeout=5)
                    break
    except BaseException:
        error = sys.exception()
        stopped_reason = f"runner_start_or_capture_error:{type(error).__name__}"
        stderr = str(error)
    finally:
        if process is not None and process.poll() is None:
            stdout, stderr, cleanup_error = terminate_runner(process, stdout, stderr)
            stopped_reason = stopped_reason or "runner_process_cleanup"
            if cleanup_error is not None:
                stopped_reason = f"{stopped_reason};{cleanup_error}"
        try:
            post_details = postverify(launcher, guard_hash, before)
        except BaseException:
            error = sys.exception()
            post_error = f"{type(error).__name__}: {error}"
            try:
                after = inventory(SOURCE)
                post_details = {"inventory_files_after": len(after), "inventory_changed_paths": sorted(path for path in before.keys() | after.keys() if before.get(path) != after.get(path))}
            except BaseException:
                post_details = {"inventory_capture": "failed"}
    exit_code = process.returncode if process is not None and process.returncode is not None else None
    payload = {
        "scope": "Collection only; libpq, all socket audit events and process spawning denied; no tests executed.",
        "attempt": attempt,
        "parent_machine": machine,
        "guard_sha256": guard_hash,
        "support_probe_sha256": support_probe_hash,
        "probe_sha256": copied_probe_hash,
        "runner_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "launcher_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "docker_preflight": docker,
        "tracked_files_before": tracked_before,
        "inventory_files_before": len(before),
        "environment_keys": sorted(environment),
        "exit_code": exit_code,
        "stopped_reason": stopped_reason,
        "postverification_error": post_error,
        "duration_seconds": round(time.monotonic() - started, 3),
        "stdout": stdout,
        "stderr": stderr,
        "free_bytes_after": shutil.disk_usage(BASE).free,
        **post_details,
    }
    launcher["write_exclusive"](destination, json.dumps(payload, indent=2, sort_keys=True))
    print(json.dumps({key: payload.get(key) for key in ("attempt", "exit_code", "duration_seconds", "inventory_changed_paths", "postverification_error", "free_bytes_after")}))
    return 1 if exit_code or stopped_reason or post_error or payload.get("inventory_changed_paths") else 0


if __name__ == "__main__":
    raise SystemExit(main())
