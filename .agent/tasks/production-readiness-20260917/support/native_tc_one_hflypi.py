#!/usr/bin/env python3
"""Run an allowlisted, single-container integration slice after review."""

from __future__ import annotations

import argparse
import hashlib
import importlib
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
VENV = NATIVE / "venv/bin/python"
PROFILES = {
    "card-growth-v1": {
        "target": "tests/test_card_growth_migration_pg.py::test_card_growth_schema_is_available_after_migrations",
        "count": 1,
        "prefix": "native-tc-one",
    },
    "client-info-v1": {"target": "tests/test_client_info_gate.py", "count": 8, "prefix": "native-tc-client-info"},
}
OLD_GUARD_SHA256 = "07d3e2dc19cbb0f9e542a6d0835ea17b5efcc5713391c152a833e6efefd61150"
MIN_START = 5 * 1024**3
MIN_LIVE = 2 * 1024**3
MAX_RUNTIME = 300
NEGATIVE_CASES = {
    "external_tcp", "foreign_local", "udp", "dns", "postgres_foreign_host",
    "postgres_foreign_database", "postgres_explicit_options", "postgres_pghostaddr",
    "postgres_pgoptions", "postgres_pgservice",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def attempt(value: str) -> str:
    if not re.fullmatch(r"v[1-9][0-9]*", value):
        raise argparse.ArgumentTypeError("attempt must be v followed by a positive integer")
    return value


def write_exclusive(path: Path, value: object) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        raw = json.dumps(value, indent=2, sort_keys=True).encode()
        written = 0
        while written < len(raw):
            count = os.write(descriptor, raw[written:])
            if count <= 0:
                raise RuntimeError("exclusive evidence write failed")
            written += count
    finally:
        os.close(descriptor)


def copy_exclusive(source: Path, destination: Path) -> str:
    if not source.is_file() or source.is_symlink() or destination.exists() or destination.is_symlink():
        raise RuntimeError(f"refusing noncanonical or existing runtime path: {destination}")
    source_bytes = source.read_bytes()
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        written = 0
        while written < len(source_bytes):
            count = os.write(descriptor, source_bytes[written:])
            if count <= 0:
                raise RuntimeError("runtime extra copy failed")
            written += count
    finally:
        os.close(descriptor)
    if digest(destination) != hashlib.sha256(source_bytes).hexdigest():
        raise RuntimeError("runtime extra hash mismatch")
    return hashlib.sha256(source_bytes).hexdigest()


def replace_guard(source: Path, destination: Path, backup: Path) -> str:
    if not destination.is_file() or destination.is_symlink() or digest(destination) != OLD_GUARD_SHA256:
        raise RuntimeError("frozen sitecustomize is not the reviewed v2 guard")
    if backup.exists() or backup.is_symlink():
        raise RuntimeError("guard backup already exists")
    old_bytes = destination.read_bytes()
    copy_exclusive(destination, backup)
    staged = destination.with_name(f".{destination.name}.{os.getpid()}.tc-stage")
    if staged.exists() or staged.is_symlink():
        raise RuntimeError("guard staging path already exists")
    try:
        copy_exclusive(source, staged)
        os.replace(staged, destination)
    finally:
        if staged.exists() and not staged.is_symlink():
            staged.unlink()
    if digest(destination) != digest(source) or digest(backup) != hashlib.sha256(old_bytes).hexdigest():
        raise RuntimeError("guard replacement or backup hash mismatch")
    return digest(destination)


def restore_guard(destination: Path, backup: Path) -> None:
    if not backup.is_file() or backup.is_symlink() or digest(backup) != OLD_GUARD_SHA256:
        raise RuntimeError("guard backup cannot restore reviewed v2 bytes")
    staged = destination.with_name(f".{destination.name}.{os.getpid()}.tc-restore")
    if staged.exists() or staged.is_symlink():
        raise RuntimeError("guard restore staging path already exists")
    try:
        copy_exclusive(backup, staged)
        os.replace(staged, destination)
    finally:
        if staged.exists() and not staged.is_symlink():
            staged.unlink()
    if digest(destination) != OLD_GUARD_SHA256:
        raise RuntimeError("guard restore hash mismatch")


def stop_process(process: subprocess.Popen[str]) -> tuple[str, str, str | None]:
    problem = None
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    except BaseException:
        error = sys.exception()
        problem = f"term:{type(error).__name__}"
    try:
        return (*process.communicate(timeout=5), problem)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except BaseException:
            error = sys.exception()
            problem = f"{problem or 'kill'};kill:{type(error).__name__}"
        try:
            return (*process.communicate(timeout=5), problem)
        except BaseException:
            error = sys.exception()
            return "", f"cleanup capture: {type(error).__name__}: {error}", f"{problem or 'capture'};capture:{type(error).__name__}"


def result(command: list[str], environment: dict[str, str], timeout: int, deadline: float) -> dict[str, object]:
    started = time.monotonic()
    process = None
    stdout = ""
    stderr = ""
    stopped = None
    try:
        if started >= deadline or shutil.disk_usage(BASE).free < MIN_LIVE:
            stopped = "deadline_or_disk_floor_before_spawn"
            return {"command": command, "exit_code": None, "stdout": stdout, "stderr": stderr, "duration_seconds": round(time.monotonic() - started, 3), "timed_out": True, "stopped_reason": stopped}
        process = subprocess.Popen(command, cwd=SOURCE, env=environment, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        while True:
            try:
                stdout, stderr = process.communicate(timeout=5)
                break
            except subprocess.TimeoutExpired:
                if time.monotonic() - started >= timeout or time.monotonic() >= deadline or shutil.disk_usage(BASE).free < MIN_LIVE:
                    stopped = "timeout_or_disk_floor"
                    stdout, stderr, cleanup = stop_process(process)
                    if cleanup is not None:
                        stopped = f"{stopped};{cleanup}"
                    break
    except BaseException:
        error = sys.exception()
        stopped = f"runner_error:{type(error).__name__}"
        stderr = str(error)
    finally:
        if process is not None and process.poll() is None:
            stdout, stderr, cleanup = stop_process(process)
            stopped = stopped or "runner_cleanup"
            if cleanup is not None:
                stopped = f"{stopped};{cleanup}"
    return {"command": command, "exit_code": process.returncode if process is not None else None, "stdout": stdout, "stderr": stderr, "duration_seconds": round(time.monotonic() - started, 3), "timed_out": stopped is not None, "stopped_reason": stopped}


def require_probe(payload: dict[str, object], mode: str, guard_hash: str) -> None:
    if payload.get("exit_code") != 0 or payload.get("timed_out") is True:
        raise RuntimeError(f"{mode} probe did not succeed")
    output = payload.get("stdout")
    if not isinstance(output, str):
        raise RuntimeError(f"{mode} probe output missing")
    proof = json.loads(output)
    if not isinstance(proof, dict) or proof.get("guard_sha256") != guard_hash:
        raise RuntimeError(f"{mode} probe guard identity differs")
    if mode == "negative":
        checks = proof.get("checks")
        observed = {(item.get("case"), item.get("denied")) for item in checks if isinstance(item, dict)} if isinstance(checks, list) else set()
        if observed != {(case, True) for case in NEGATIVE_CASES}:
            raise RuntimeError("negative probe did not deny the exact ten cases")
    else:
        child = proof.get("child")
        parent = proof.get("provenance")
        if proof.get("child_guard_propagated") is not True or not isinstance(child, dict) or not isinstance(parent, dict):
            raise RuntimeError("child propagation result missing")
        if child.get("sha256") != guard_hash or child.get("denied") is not True or child.get("bytecode_disabled") is not True or child.get("user_site_disabled") is not True or child.get("pid") == parent.get("pid"):
            raise RuntimeError("child proof does not establish guarded distinct process")


def plugin_source(target: str | list[str]) -> str:
    targets = [target] if isinstance(target, str) else target
    if not targets or not all(isinstance(item, str) for item in targets):
        raise ValueError("literal pytest targets are required")
    return """
import json
import pytest
from _pytest.subtests import SubtestReport
state = {'collected': None, 'nodeids': [], 'passed': 0, 'failed': 0, 'skipped': 0, 'xfailed': 0, 'setup_failed': 0, 'call_failed': 0, 'child_calls': [], 'subtests_passed': 0, 'subtests_failed': 0, 'subtests_skipped': 0, 'subtests_xfailed': 0}
class Results:
    def pytest_collection_finish(self, session):
        state['collected'] = len(session.items)
        state['nodeids'] = [item.nodeid for item in session.items]
    def pytest_runtest_logreport(self, report):
        if isinstance(report, SubtestReport):
            if report.passed: state['subtests_passed'] += 1
            if report.failed: state['subtests_failed'] += 1
            if report.skipped: state['subtests_skipped'] += 1
            if getattr(report, 'wasxfail', None): state['subtests_xfailed'] += 1
            return
        if report.when == 'call':
            if report.passed: state['passed'] += 1
            if report.failed: state['failed'] += 1; state['call_failed'] += 1
            if report.skipped: state['skipped'] += 1
            if getattr(report, 'wasxfail', None): state['xfailed'] += 1
        elif report.when == 'setup':
            if report.failed: state['failed'] += 1; state['setup_failed'] += 1
            if report.skipped: state['skipped'] += 1
    def pytest_sessionfinish(self, session, exitstatus):
        state['pytest_exitstatus'] = int(exitstatus)
result = pytest.main(%r + ['-q', '-p', 'no:cacheprovider'], plugins=[Results()])
state['pytest_return'] = int(result)
print('HFLYPI_TC_ONE_RESULT=' + json.dumps(state, sort_keys=True))
raise SystemExit(result)
""" % targets


def parse_test(payload: dict[str, object], profile: dict[str, object]) -> dict[str, object]:
    stdout = payload.get("stdout")
    if not isinstance(stdout, str):
        raise RuntimeError("test stdout missing")
    rows = [line for line in stdout.splitlines() if line.startswith("HFLYPI_TC_ONE_RESULT=")]
    if len(rows) != 1:
        raise RuntimeError("test result callback payload is missing")
    parsed = json.loads(rows[0].split("=", 1)[1])
    if not isinstance(parsed, dict):
        raise RuntimeError("test callback payload invalid")
    expected = {"collected": profile["count"], "passed": profile["count"], "failed": 0, "skipped": 0, "xfailed": 0, "setup_failed": 0, "call_failed": 0, "pytest_exitstatus": 0, "pytest_return": 0, "subtests_failed": 0, "subtests_skipped": 0, "subtests_xfailed": 0}
    if any(parsed.get(key) != value for key, value in expected.items()) or payload.get("exit_code") != 0 or payload.get("timed_out") is True:
        raise RuntimeError("unchanged native slice did not pass every expected node without skip")
    if not isinstance(parsed.get("subtests_passed"), int) or parsed["subtests_passed"] < 0:
        raise RuntimeError("native slice subtest accounting missing or invalid")
    nodeids = parsed.get("nodeids")
    targets = profile.get("targets", [profile.get("target")])
    if not isinstance(targets, list) or not targets or not all(isinstance(target, str) for target in targets):
        raise RuntimeError("native slice has no literal target allowlist")
    if not isinstance(nodeids, list) or len(nodeids) != profile["count"] or len(set(nodeids)) != len(nodeids):
        raise RuntimeError("native slice did not report unique expected nodes")
    if not all(isinstance(node, str) and any(node == target or node.startswith(target + "::") for target in targets) for node in nodeids):
        raise RuntimeError("native slice collected a node outside its literal target")
    return parsed


def cleanup_owned(events: Path, relay_module: object, containers_before: list[dict[str, object]]) -> dict[str, object]:
    if not events.is_file() or events.is_symlink():
        return {"attempted": False, "reason": "no-owned-event-journal"}
    rows = [json.loads(row) for row in events.read_text().splitlines() if row]
    created = [row for row in rows if isinstance(row, dict) and row.get("event") == "container_created"]
    starts = [row for row in rows if isinstance(row, dict) and row.get("event") == "start_requested"]
    container_id = created[0].get("container_id") if len(created) == 1 else None
    session = created[0].get("session_id") if len(created) == 1 else None
    recovered = False
    if container_id is None and len(starts) == 1:
        session = starts[0].get("session_id")
        before_ids = {row.get("id") for row in containers_before}
        candidates = [row for row in docker_snapshot() if row.get("id") not in before_ids]
        if len(candidates) == 1:
            container_id = candidates[0].get("id")
            recovered = True
        elif not candidates:
            return {"attempted": True, "already_removed": True, "recovered_from_start": True}
        else:
            raise RuntimeError("refusing cleanup because more than one new container exists")
    if len(created) > 1:
        raise RuntimeError("refusing cleanup because multiple owned-container events exist")
    if not isinstance(container_id, str) or not isinstance(session, str):
        return {"attempted": False, "reason": "invalid-owned-event"}
    verifier = getattr(relay_module, "verify_container", None)
    if not callable(verifier):
        raise RuntimeError("relay has no owned-container verifier")
    import docker
    client = docker.DockerClient(base_url="unix:///Users/alexdemyanov/.docker/run/docker.sock")
    try:
        try:
            container = client.containers.get(container_id)
        except docker.errors.NotFound:
            return {"attempted": True, "container_id": container_id, "already_removed": True, "recovered_from_start": recovered}
        verifier(container_id, session, require_running=False)
        container.remove(force=True, v=False)
        try:
            client.containers.get(container_id)
        except docker.errors.NotFound:
            return {"attempted": True, "container_id": container_id, "removed": True, "recovered_from_start": recovered}
        raise RuntimeError("owned Testcontainers container remains after forced removal")
    finally:
        client.close()


def remove_owned_capability(events: Path) -> dict[str, object]:
    if not events.is_file() or events.is_symlink():
        return {"removed": False, "reason": "no-event-journal"}
    rows = [json.loads(row) for row in events.read_text().splitlines() if row]
    created = [row for row in rows if isinstance(row, dict) and row.get("event") == "container_created"]
    relays = [row for row in rows if isinstance(row, dict) and row.get("event") == "relay_started"]
    if len(created) != 1 or len(relays) != 1:
        return {"removed": False, "reason": "no-single-owned-relay"}
    container_id = created[0].get("container_id")
    session = created[0].get("session_id")
    owner_pid = created[0].get("pid")
    path_raw = relays[0].get("capability_path")
    if not isinstance(container_id, str) or not isinstance(session, str) or not isinstance(owner_pid, int) or not isinstance(path_raw, str):
        raise RuntimeError("relay ownership event is malformed")
    path = Path(path_raw)
    directory = NATIVE / "capabilities"
    if path.parent != directory or path.is_symlink() or not path.exists():
        return {"removed": False, "reason": "capability-absent"}
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict) or payload.get("nonce") != "hfLYPi" or payload.get("parent_pid") != owner_pid or payload.get("container_id") != container_id or payload.get("session_id") != session:
        raise RuntimeError("capability is not bound to the recorded owned relay")
    path.unlink()
    return {"removed": True, "path": path.name}


def audit_journals(events: Path, relay_artifact: Path, profile: str) -> dict[str, object]:
    if not events.is_file() or events.is_symlink() or not relay_artifact.is_file() or relay_artifact.is_symlink():
        raise RuntimeError("Testcontainers event or relay journal is missing")
    event_rows = [json.loads(row) for row in events.read_text().splitlines() if row]
    relay_rows = [json.loads(row) for row in relay_artifact.read_text().splitlines() if row]
    if not all(isinstance(row, dict) for row in event_rows + relay_rows):
        raise RuntimeError("Testcontainers journal row is invalid")
    start = [row for row in event_rows if row.get("event") == "start_requested"]
    created = [row for row in event_rows if row.get("event") == "container_created"]
    relay_started = [row for row in event_rows if row.get("event") == "relay_started"]
    denials = [row for row in event_rows if row.get("event") == "capability_denials"]
    admitted = [row for row in event_rows if row.get("event") == "dsn_admitted"]
    removed = [row for row in event_rows if row.get("event") == "container_removed"]
    cleanup = [row for row in event_rows if row.get("event") == "cleanup"]
    if len(start) != 1 or len(created) != 1 or len(relay_started) != 1 or len(denials) != 1 or len(removed) != 1 or len(cleanup) != 1:
        raise RuntimeError("Testcontainers lifecycle journal is incomplete")
    parent_pid = start[0].get("pid")
    container_id = created[0].get("container_id")
    session = created[0].get("session_id")
    port = relay_started[0].get("port")
    if not isinstance(parent_pid, int) or not isinstance(container_id, str) or not isinstance(session, str) or not isinstance(port, int):
        raise RuntimeError("Testcontainers lifecycle identity is invalid")
    if start[0].get("session_id") != session or relay_started[0].get("container_id") != container_id:
        raise RuntimeError("Testcontainers start, container and relay identities differ")
    if not any(row.get("pid") == parent_pid and row.get("container_id") == container_id and row.get("port") == port for row in admitted):
        raise RuntimeError("parent process did not admit its relay DSN")
    if not any(row.get("pid") != parent_pid and row.get("container_id") == container_id and row.get("port") == port for row in admitted):
        raise RuntimeError("Flask migration child did not admit its inherited relay DSN")
    expected_denials = {"stale_expiry", "nonce", "session", "container", "wrong_port", "world_readable", "foreign_path", "symlink"}
    checks = denials[0].get("checks")
    observed_denials = {(row.get("case"), row.get("denied")) for row in checks if isinstance(row, dict)} if isinstance(checks, list) else set()
    if observed_denials != {(case, True) for case in expected_denials}:
        raise RuntimeError("capability denial evidence is incomplete")
    if cleanup[0].get("errors") != []:
        raise RuntimeError("Testcontainers adapter reported cleanup errors")
    bindings = [row for row in event_rows if row.get("event") == "parent_database_bound"]
    unbindings = [row for row in event_rows if row.get("event") == "parent_database_unbound"]
    if profile == "client-info-v1":
        if len(bindings) != 1 or len(unbindings) != 1 or bindings[0].get("pid") != parent_pid or bindings[0].get("port") != port or bindings[0].get("database") != "test" or unbindings[0].get("pid") != parent_pid:
            raise RuntimeError("parent Flask database configuration lifecycle is incomplete")
    elif bindings or unbindings:
        raise RuntimeError("unexpected parent Flask database configuration")
    final = relay_rows[-1] if relay_rows else {}
    connections = final.get("connections") if isinstance(final, dict) else None
    executions = final.get("exec_results") if isinstance(final, dict) else None
    if not isinstance(final, dict) or not isinstance(connections, int) or connections < 2 or final.get("active") != 0 or final.get("rejections") != 0 or final.get("failures") != [] or not isinstance(executions, list) or len(executions) != connections:
        raise RuntimeError("relay did not close without active connections and failures")
    if not all(isinstance(row, dict) and row.get("returncode") == 0 and row.get("exit_mode") == "graceful" and row.get("stderr_bytes") == 0 for row in executions):
        raise RuntimeError("relay Docker exec evidence is incomplete")
    return {"event_rows": len(event_rows), "relay_rows": len(relay_rows), "connections": connections, "flask_child_dsn_admitted": True}


def require_empty_network(relay_module: object) -> dict[str, object]:
    network_id = getattr(relay_module, "NETWORK_ID", "")
    network_name = getattr(relay_module, "NETWORK_NAME", "")
    if not isinstance(network_id, str) or not isinstance(network_name, str):
        raise RuntimeError("relay network identity is unavailable")
    import docker
    client = docker.DockerClient(base_url="unix:///Users/alexdemyanov/.docker/run/docker.sock")
    try:
        attrs = client.api.inspect_network(network_id)
    finally:
        client.close()
    if not isinstance(attrs, dict) or attrs.get("Id") != network_id or attrs.get("Name") != network_name or attrs.get("Containers") != {}:
        raise RuntimeError("owned internal network is not empty after the node")
    return {"network_id": network_id, "empty": True}


def docker_snapshot() -> list[dict[str, object]]:
    import docker
    client = docker.DockerClient(base_url="unix:///Users/alexdemyanov/.docker/run/docker.sock")
    try:
        rows = []
        for container in client.containers.list(all=True):
            rows.append({"id": container.id, "name": container.name, "running": container.status == "running"})
        return sorted(rows, key=lambda row: str(row["id"]))
    finally:
        client.close()


def capabilities_snapshot() -> list[str]:
    directory = NATIVE / "capabilities"
    if not directory.exists():
        return []
    if not directory.is_dir() or directory.is_symlink():
        raise RuntimeError("capability directory is not canonical")
    return sorted(path.name for path in directory.iterdir())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", required=True, type=attempt)
    parser.add_argument("--profile", choices=tuple(PROFILES), default="card-growth-v1")
    values = parser.parse_args()
    name = values.attempt
    profile = PROFILES[values.profile]
    prefix = profile["prefix"]
    launcher = runpy.run_path(str(SUPPORT / "native_guard_checks_hflypi.py"))
    destination = EVIDENCE / f"{prefix}-{name}.json"
    journal = EVIDENCE / f"{prefix}-{name}-events.jsonl"
    relay_artifact = EVIDENCE / f"{prefix}-{name}-relay.json"
    probe_artifacts = {mode: EVIDENCE / f"{prefix}-{name}-{mode}.json" for mode in ("negative", "child")}
    backup = NATIVE / f"sitecustomize-before-{prefix}-{name}.py"
    source_guard = SUPPORT / "native_hflypi_sitecustomize.py"
    source_adapter = SUPPORT / "native_tc_adapter_hflypi.py"
    source_relay = SUPPORT / "native_tc_relay_hflypi.py"
    targets = {source_adapter: SOURCE / "src/native_tc_adapter_hflypi.py", source_relay: SOURCE / "src/native_tc_relay_hflypi.py"}
    started = time.monotonic()
    output: dict[str, object] = {"attempt": name, "profile": values.profile, "node": profile["target"], "expected_count": profile["count"], "phase": "preflight"}
    installed: list[Path] = []
    guard_installed = False
    relay_module = None
    containers_before: list[dict[str, object]] = []
    capabilities_before: list[str] = []
    try:
        if platform.machine() != "arm64":
            raise RuntimeError("native Testcontainers node requires arm64 parent")
        if destination.exists() or destination.is_symlink() or journal.exists() or journal.is_symlink() or relay_artifact.exists() or relay_artifact.is_symlink() or any(path.exists() or path.is_symlink() for path in probe_artifacts.values()):
            raise RuntimeError("attempt evidence path already exists")
        if shutil.disk_usage(BASE).free < MIN_START:
            raise RuntimeError("native Testcontainers node requires 5 GiB free")
        launcher["verify_endpoints"]()
        output["frozen_blobs_before"] = launcher["verify_frozen_source"]()
        if output["frozen_blobs_before"] != 5720:
            raise RuntimeError("unexpected frozen blob count")
        containers_before = docker_snapshot()
        capabilities_before = capabilities_snapshot()
        output["unrelated_containers_before"] = containers_before
        output["capabilities_before"] = capabilities_before
        for source in (source_guard, source_adapter, source_relay):
            if not source.is_file() or source.is_symlink():
                raise RuntimeError("required reviewed support source is absent")
        guard_hash = replace_guard(source_guard, SOURCE / "src/sitecustomize.py", backup)
        guard_installed = True
        hashes = {"guard": guard_hash, "support_guard": digest(source_guard), "launcher": digest(Path(__file__))}
        for source, target in targets.items():
            hashes[target.stem] = copy_exclusive(source, target)
            installed.append(target)
        output["hashes"] = hashes
        descriptor = os.open(journal, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(descriptor)
        environment = launcher["environment"](guard_hash)
        environment.pop("LOCALOS_HFLYPI_PROBE_DSN", None)
        environment.update({
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "LOCALOS_HFLYPI_TC_MODE": values.profile,
            "LOCALOS_HFLYPI_TC_ADAPTER_SHA256": hashes["native_tc_adapter_hflypi"],
            "LOCALOS_HFLYPI_TC_RELAY_SHA256": hashes["native_tc_relay_hflypi"],
            "LOCALOS_HFLYPI_TC_JOURNAL": str(journal),
        })
        probe = NATIVE / "native_hflypi_probe_v1.py"
        support_probe = SUPPORT / "native_hflypi_probe.py"
        if not probe.is_file() or probe.is_symlink() or not support_probe.is_file() or support_probe.is_symlink() or digest(probe) != digest(support_probe):
            raise RuntimeError("pinned native probe is absent")
        output["hashes"]["probe"] = digest(probe)
        for mode in ("negative", "child"):
            capture = result(["/usr/bin/arch", "-arm64", str(VENV), "-B", str(probe), mode], environment, 40, started + MAX_RUNTIME)
            output[f"{mode}_probe"] = capture
            write_exclusive(probe_artifacts[mode], capture)
            require_probe(capture, mode, guard_hash)
        if shutil.disk_usage(BASE).free < MIN_LIVE:
            raise RuntimeError("disk floor reached before native node")
        output["phase"] = "test"
        capture = result(["/usr/bin/arch", "-arm64", str(VENV), "-B", "-c", plugin_source(profile["target"])], environment, MAX_RUNTIME, started + MAX_RUNTIME)
        output["test"] = capture
        output["test_callbacks"] = parse_test(capture, profile)
        output["journals"] = audit_journals(journal, relay_artifact, values.profile)
        if str(SOURCE / "src") not in sys.path:
            sys.path.insert(0, str(SOURCE / "src"))
        relay_module = importlib.import_module("native_tc_relay_hflypi")
        output["network_after_test"] = require_empty_network(relay_module)
        output["phase"] = "passed"
    except BaseException:
        error = sys.exception()
        output["phase"] = "failed"
        output["error"] = f"{type(error).__name__}: {error}"
    finally:
        try:
            if str(SOURCE / "src") not in sys.path:
                sys.path.insert(0, str(SOURCE / "src"))
            relay_module = importlib.import_module("native_tc_relay_hflypi")
            output["owned_cleanup"] = cleanup_owned(journal, relay_module, containers_before)
            output["capability_cleanup"] = remove_owned_capability(journal)
            output["network_after_cleanup"] = require_empty_network(relay_module)
            if capabilities_snapshot() != capabilities_before:
                raise RuntimeError("Testcontainers capability files remain after cleanup")
            containers_after = docker_snapshot()
            output["unrelated_containers_after"] = containers_after
            if containers_after != containers_before:
                raise RuntimeError("unrelated Docker container identity changed")
        except BaseException:
            error = sys.exception()
            output["owned_cleanup_error"] = f"{type(error).__name__}: {error}"
            output["phase"] = "failed"
        try:
            if guard_installed:
                if digest(SOURCE / "src/sitecustomize.py") != output.get("hashes", {}).get("guard"):
                    raise RuntimeError("refusing to restore over an unknown guard replacement")
                restore_guard(SOURCE / "src/sitecustomize.py", backup)
            for target in installed:
                expected = output.get("hashes", {}).get(target.stem)
                if not isinstance(expected, str) or not target.is_file() or target.is_symlink() or digest(target) != expected:
                    raise RuntimeError("refusing to delete an unknown runtime extra")
                target.unlink()
            output["frozen_blobs_after"] = launcher["verify_frozen_source"]()
            if output["frozen_blobs_after"] != 5720:
                raise RuntimeError("frozen blob count changed after cleanup")
        except BaseException:
            error = sys.exception()
            output["restore_error"] = f"{type(error).__name__}: {error}"
            output["phase"] = "failed"
        output["duration_seconds"] = round(time.monotonic() - started, 3)
        output["free_bytes_after"] = shutil.disk_usage(BASE).free
        write_exclusive(destination, output)
    return 0 if output.get("phase") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
