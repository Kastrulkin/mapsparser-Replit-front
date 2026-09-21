#!/usr/bin/env python3
"""Guarded, read-mostly hfLYPi probe launcher.  Do not run before review."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import time


COMMIT = "99849935de26e2932613f2a73cf515dff49104a1"
WORKSPACE = Path("/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре")
BASE = Path("/private/tmp/localos-readiness-20260921.hfLYPi")
SOURCE = BASE / "source"
NATIVE = BASE / "native"
EVIDENCE = NATIVE / "evidence"
VENV_PYTHON = NATIVE / "venv/bin/python"
VENV_PYTHON_TARGET = Path("/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11")
SUPPORT_GUARD = WORKSPACE / ".agent/tasks/production-readiness-20260917/support/native_hflypi_sitecustomize.py"
SUPPORT_PROBE = WORKSPACE / ".agent/tasks/production-readiness-20260917/support/native_hflypi_probe.py"
INSTALLED_GUARD = SOURCE / "src/sitecustomize.py"
COPIED_PROBE = NATIVE / "native_hflypi_probe_v1.py"
DOCKER_SOCKET = "/Users/alexdemyanov/.docker/run/docker.sock"
DOCKER_HOST = "unix:///Users/alexdemyanov/.docker/run/docker.sock"
DOCKER = "/Applications/Docker.app/Contents/Resources/bin/docker"
CONTAINER = "localos-readiness-hflypi-postgres-1"
CONTAINER_ID = "a099d92bbf720eaa20a9899ef9dc02cde6f8e2f012c00883191e517b53c74226"
POSTGRES_IMAGE_ID = "sha256:4f26f01433671ee540195bff27f4890acca58cb49cf6d61ea12008d842ec0699"
VOLUME = "localos-readiness-hflypi-pgdata"
NETWORKS = ("localos-readiness-hflypi_internal", "localos-readiness-hflypi_pg_ingress")
NETWORK_IDS = {
    "localos-readiness-hflypi_internal": "879fb9c7d6e60f983f8eba0872ad3677197e3f87ebab8fd3bca75c3e514ce19a",
    "localos-readiness-hflypi_pg_ingress": "c68f2b706e85fb9cb4a385b8f95a8e7141777c607663b5ace86a67ed4dc7150e",
}
NETWORK_INTERNAL = {
    "localos-readiness-hflypi_internal": True,
    "localos-readiness-hflypi_pg_ingress": False,
}
OWNER = "production-readiness-20260917-hfLYPi"
DSN = "postgresql://audit_owner:hflypi-local-only@127.0.0.1:35418/readiness_full_test_hflypi"
MIN_START_BYTES = 5 * 1024**3
MIN_LIVE_BYTES = 2 * 1024**3


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def free_bytes() -> int:
    return shutil.disk_usage(BASE).free


def git_blob_sha1(payload: bytes) -> str:
    return hashlib.sha1(f"blob {len(payload)}\0".encode() + payload).hexdigest()


def source_payload(path: Path, mode: str) -> bytes:
    if mode == "120000":
        if not path.is_symlink():
            raise RuntimeError("expected source symlink")
        return os.fsencode(os.readlink(path))
    if not path.is_file() or path.is_symlink():
        raise RuntimeError("expected source regular file")
    return path.read_bytes()


def verify_frozen_source() -> int:
    revision = subprocess.run(["git", "-C", str(WORKSPACE), "rev-parse", COMMIT], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    if revision.stdout.strip() != COMMIT:
        raise RuntimeError("frozen commit resolution mismatch")
    tree = subprocess.run(["git", "-C", str(WORKSPACE), "ls-tree", "-rz", "-r", COMMIT], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    checked = 0
    for record in tree.stdout.split(b"\0"):
        if not record:
            continue
        header, raw_path = record.split(b"\t", 1)
        mode_raw, object_type_raw, expected_raw = header.split(b" ", 2)
        mode = mode_raw.decode()
        if object_type_raw != b"blob":
            raise RuntimeError("non-blob tracked object")
        target = SOURCE / Path(os.fsdecode(raw_path))
        observed_hash = git_blob_sha1(source_payload(target, mode))
        observed_mode = "120000" if mode == "120000" and target.is_symlink() else format(stat.S_IMODE(target.lstat().st_mode), "06o")
        expected_mode = "000755" if mode == "100755" else "000644" if mode == "100644" else mode.zfill(6)
        if observed_hash != expected_raw.decode() or observed_mode != expected_mode:
            raise RuntimeError(f"frozen source mismatch: {target.relative_to(SOURCE)}")
        checked += 1
    return checked


def command_json(command: list[str]) -> object:
    docker_command = [DOCKER, "--context", "desktop-linux", *command[1:]]
    client_environment = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "DOCKER_CONFIG": "/Users/alexdemyanov/.docker",
    }
    completed = subprocess.run(docker_command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, check=True, env=client_environment)
    return json.loads(completed.stdout)


def verify_docker_owner() -> dict[str, object]:
    context = command_json(["docker", "context", "inspect", "desktop-linux"])[0]
    endpoint = context.get("Endpoints", {}).get("docker", {}).get("Host")
    if endpoint != DOCKER_HOST:
        raise RuntimeError("Docker context endpoint differs from approved socket")
    container = command_json(["docker", "inspect", CONTAINER])[0]
    labels = container.get("Config", {}).get("Labels", {})
    ports = container.get("NetworkSettings", {}).get("Ports", {}).get("5432/tcp")
    mounts = container.get("Mounts", [])
    container_networks = container.get("NetworkSettings", {}).get("Networks", {})
    if not container.get("State", {}).get("Running") or container.get("State", {}).get("Health", {}).get("Status") != "healthy":
        raise RuntimeError("synthetic PostgreSQL is not healthy")
    if container.get("Id") != CONTAINER_ID or container.get("Image") != POSTGRES_IMAGE_ID or container.get("Name") != f"/{CONTAINER}":
        raise RuntimeError("synthetic PostgreSQL pinned identity mismatch")
    if labels.get("localos.audit.owner") != OWNER or labels.get("com.docker.compose.project") != "localos-readiness-hflypi":
        raise RuntimeError("synthetic PostgreSQL owner identity mismatch")
    if ports != [{"HostIp": "127.0.0.1", "HostPort": "35418"}]:
        raise RuntimeError("synthetic PostgreSQL port mapping mismatch")
    if len(mounts) != 1 or mounts[0].get("Type") != "volume" or mounts[0].get("Name") != VOLUME or mounts[0].get("Destination") != "/var/lib/postgresql/data" or mounts[0].get("RW") is not True:
        raise RuntimeError("synthetic PostgreSQL volume mismatch")
    if set(container_networks) != set(NETWORKS):
        raise RuntimeError("synthetic PostgreSQL network membership mismatch")
    for network in NETWORKS:
        inspected = command_json(["docker", "network", "inspect", network])[0]
        if inspected.get("Id") != NETWORK_IDS[network] or inspected.get("Name") != network or inspected.get("Internal") is not NETWORK_INTERNAL[network]:
            raise RuntimeError("synthetic network pinned identity mismatch")
        if inspected.get("Labels", {}).get("localos.audit.owner") != OWNER:
            raise RuntimeError("synthetic network owner identity mismatch")
    volume = command_json(["docker", "volume", "inspect", VOLUME])[0]
    if volume.get("Labels", {}).get("localos.audit.owner") != OWNER:
        raise RuntimeError("synthetic volume owner identity mismatch")
    return {
        "docker_context_endpoint": endpoint,
        "container_id": container.get("Id"),
        "image_id": container.get("Image"),
        "name": container.get("Name"),
        "networks": {network: NETWORK_IDS[network] for network in NETWORKS},
    }


def verify_endpoints() -> None:
    for path in (BASE, SOURCE, NATIVE, EVIDENCE, INSTALLED_GUARD.parent, SUPPORT_GUARD.parent):
        if not path.is_dir() or path.is_symlink() or path.resolve(strict=True) != path:
            raise RuntimeError(f"non-canonical directory endpoint: {path}")
    for path in (SUPPORT_GUARD, SUPPORT_PROBE):
        if not path.is_file() or path.is_symlink() or path.resolve(strict=True) != path:
            raise RuntimeError(f"non-canonical file endpoint: {path}")
    if not VENV_PYTHON.is_symlink() or VENV_PYTHON.resolve(strict=True) != VENV_PYTHON_TARGET:
        raise RuntimeError("native Python endpoint differs from approved interpreter")


def write_all(descriptor: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(descriptor, view)
        if written <= 0:
            raise RuntimeError("exclusive artifact write failed")
        view = view[written:]


def write_exclusive(path: Path, payload: str) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        write_all(descriptor, payload.encode())
    finally:
        os.close(descriptor)


def install_exclusive(source: Path, destination: Path) -> str:
    source_bytes = source.read_bytes()
    expected_hash = hashlib.sha256(source_bytes).hexdigest()
    staging = destination.with_name(f".{destination.name}.{os.getpid()}.staging")
    descriptor = os.open(staging, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        write_all(descriptor, source_bytes)
    finally:
        os.close(descriptor)
    try:
        os.link(staging, destination)
    finally:
        staging.unlink(missing_ok=True)
    if sha256(destination) != expected_hash:
        raise RuntimeError("installed private guard or probe hash mismatch")
    return expected_hash


def environment(guard_sha256: str) -> dict[str, str]:
    return {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "PYTHONPATH": os.pathsep.join((str(SOURCE / "src"), str(SOURCE))),
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHON_DOTENV_DISABLED": "1",
        "DOCKER_HOST": DOCKER_HOST,
        "LOCALOS_HFLYPI_DOCKER_SOCKET": DOCKER_SOCKET,
        "LOCALOS_HFLYPI_SOURCE_ROOT": str(SOURCE),
        "TESTCONTAINERS_RYUK_DISABLED": "true",
        "TESTCONTAINERS_HOST_OVERRIDE": "127.0.0.1",
        "LOCALOS_HFLYPI_TESTCONTAINERS_NETWORK": NETWORKS[0],
        "LOCALOS_HFLYPI_PROBE_DSN": DSN,
        "LOCALOS_HFLYPI_EXPECTED_GUARD_SHA256": guard_sha256,
    }


def timeout_text(value: str | bytes | None) -> str:
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value or ""


def capture(label: str, arguments: list[str], env: dict[str, str], docker_preflight: dict[str, object] | None = None, attempt: str = "v1") -> None:
    destination = EVIDENCE / f"native-guard-{label}-{attempt}.json"
    if destination.exists():
        raise RuntimeError("probe evidence already exists")
    if free_bytes() < MIN_LIVE_BYTES:
        raise RuntimeError("insufficient free disk before guarded probe")
    started = time.monotonic()
    try:
        completed = subprocess.run(arguments, cwd=NATIVE, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, check=False)
    except subprocess.TimeoutExpired:
        error = sys.exception()
        if not isinstance(error, subprocess.TimeoutExpired):
            raise RuntimeError("unexpected guarded probe timeout state")
        payload = {
            "label": label,
            "command": arguments,
            "exit_code": None,
            "timed_out": True,
            "duration_ms": round((time.monotonic() - started) * 1000, 3),
            "stdout": timeout_text(error.stdout),
            "stderr": timeout_text(error.stderr),
            "free_bytes_after": free_bytes(),
            "environment_keys": sorted(env),
        }
        if docker_preflight is not None:
            payload["docker_preflight"] = docker_preflight
        write_exclusive(destination, json.dumps(payload, indent=2, sort_keys=True))
        raise RuntimeError("guarded probe timed out; preserve evidence and stop") from error
    payload = {
        "label": label,
        "command": arguments,
        "exit_code": completed.returncode,
        "duration_ms": round((time.monotonic() - started) * 1000, 3),
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "free_bytes_after": free_bytes(),
        "environment_keys": sorted(env),
    }
    if docker_preflight is not None:
        payload["docker_preflight"] = docker_preflight
    write_exclusive(destination, json.dumps(payload, indent=2, sort_keys=True))
    if completed.returncode:
        if completed.returncode == 78:
            raise RuntimeError("guard denied probe; preserve evidence and stop")
        raise RuntimeError("guarded probe failed")


def main() -> int:
    if free_bytes() < MIN_START_BYTES:
        raise RuntimeError("insufficient free disk for guarded probes")
    verify_endpoints()
    metadata_path = EVIDENCE / "native-guard-metadata-v1.json"
    output_paths = [metadata_path, *(EVIDENCE / f"native-guard-{label}-v1.json" for label in ("negative", "child", "own-postgres"))]
    if any(path.exists() for path in output_paths):
        raise RuntimeError("guarded probe output already exists")
    if subprocess.run(["git", "-C", str(WORKSPACE), "ls-tree", "-r", "--name-only", COMMIT, "--", "src/sitecustomize.py"], text=True, stdout=subprocess.PIPE, check=True).stdout.strip():
        raise RuntimeError("guard target is unexpectedly tracked")
    checked = verify_frozen_source()
    if INSTALLED_GUARD.exists() or COPIED_PROBE.exists():
        raise RuntimeError("guard or probe copy already exists")
    docker_details = verify_docker_owner()
    guard_hash = install_exclusive(SUPPORT_GUARD, INSTALLED_GUARD)
    probe_hash = install_exclusive(SUPPORT_PROBE, COPIED_PROBE)
    env = environment(guard_hash)
    metadata = {
        "tracked_blob_count_before_guard_extra": checked,
        "guard_sha256": guard_hash,
        "probe_sha256": probe_hash,
        "guard_extra_path": str(INSTALLED_GUARD),
        "docker": docker_details,
    }
    write_exclusive(metadata_path, json.dumps(metadata, indent=2, sort_keys=True))
    for label, mode in (("negative", "negative"), ("child", "child"), ("own-postgres", "own-postgres")):
        current_docker = verify_docker_owner() if label == "own-postgres" else None
        capture(label, [str(VENV_PYTHON), "-B", str(COPIED_PROBE), mode], env, current_docker)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
