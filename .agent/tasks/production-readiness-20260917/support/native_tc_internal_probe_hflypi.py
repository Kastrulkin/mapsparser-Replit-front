#!/usr/bin/env python3
"""DRAFT runtime proof for one isolated internal Testcontainers-style PostgreSQL.

This file is not launched automatically. The aggregate owner reviews it and
may invoke it from a named tmux session. It creates no fallback network and
never pulls or builds an image. Created probe resources are deliberately
retained for inspection on success and failure.
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import time


NONCE = "hfLYPi"
OWNER = "production-readiness-20260917-hfLYPi"
SCOPE = "native-tc-internal-probe"
IMAGE_TAG = "pgvector/pgvector:0.8.0-pg16-trixie"
IMAGE_ID = "sha256:4f26f01433671ee540195bff27f4890acca58cb49cf6d61ea12008d842ec0699"
DOCKER = "/Applications/Docker.app/Contents/Resources/bin/docker"
DOCKER_CONTEXT = "desktop-linux"
DOCKER_HOST = "unix:///Users/alexdemyanov/.docker/run/docker.sock"
DOCKER_CONFIG = "/Users/alexdemyanov/.docker"
NETWORK = "localos-readiness-hflypi-tc-internal"
CONTAINER = "localos-readiness-hflypi-tc-postgres-1"
DATABASE = "readiness_tc_hflypi"
USERNAME = "audit_tc"
PASSWORD = "hflypi-tc-local-only"
MIN_FREE_BYTES = 5 * 1024 * 1024 * 1024
MAX_RUNTIME_SECONDS = 120
READY_TIMEOUT_SECONDS = 60
LABELS = {
    "localos.audit.owner": OWNER,
    "localos.audit.nonce": NONCE,
    "localos.audit.scope": SCOPE,
}
PROVIDER_ENVIRONMENTS = (
    "ANTHROPIC_API_KEY",
    "APIFY_TOKEN",
    "OPENAI_API_KEY",
    "SMTP_PASSWORD",
    "STRIPE_SECRET_KEY",
    "TELEGRAM_BOT_TOKEN",
)
RESULT_PATH = Path(__file__).resolve().parents[1] / "evidence" / "native-tc-internal-probe-hflypi.json"


def _environment(extra: dict[str, str] | None = None) -> dict[str, str]:
    values = {
        "DOCKER_CONFIG": DOCKER_CONFIG,
        "DOCKER_HOST": DOCKER_HOST,
        "LANG": "C",
        "PATH": "/usr/bin:/bin",
    }
    for key in PROVIDER_ENVIRONMENTS:
        values[key] = ""
    if extra:
        values.update(extra)
    return values


def _redacted(command: list[str]) -> list[str]:
    result: list[str] = []
    for value in command:
        if value.startswith("POSTGRES_PASSWORD="):
            result.append("POSTGRES_PASSWORD=<synthetic>")
        elif value == "-c":
            result.append(value)
            result.append("<inline-python>")
            break
        else:
            result.append(value)
    return result


def _run(command: list[str], results: dict[str, object], started: float, timeout: int = 20, environment: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    remaining = MAX_RUNTIME_SECONDS - (time.monotonic() - started)
    if remaining <= 0:
        raise RuntimeError("probe runtime budget exhausted")
    bounded_timeout = min(timeout, max(1, int(remaining)))
    command_started = time.monotonic()
    completed = subprocess.run(
        command,
        capture_output=True,
        check=False,
        env=_environment() if environment is None else environment,
        text=True,
        timeout=bounded_timeout,
    )
    commands = results["commands"]
    if not isinstance(commands, list):
        raise RuntimeError("result command journal is invalid")
    commands.append(
        {
            "argv": _redacted(command),
            "returncode": completed.returncode,
            "seconds": round(time.monotonic() - command_started, 3),
        }
    )
    return completed


def _docker_command(*arguments: str) -> list[str]:
    return [DOCKER, "--context", DOCKER_CONTEXT, *arguments]


def _require_success(completed: subprocess.CompletedProcess[str], action: str) -> str:
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()[-600:]
        raise RuntimeError(f"{action} failed: {detail}")
    return completed.stdout.strip()


def _refuse_existing(docker: str, resource: str, name: str, results: dict[str, object], started: float) -> None:
    completed = _run(_docker_command(resource, "inspect", name), results, started)
    if completed.returncode == 0:
        raise RuntimeError(f"refusing pre-existing {resource}: {name}")


def _labels_arguments() -> list[str]:
    arguments: list[str] = []
    for key, value in LABELS.items():
        arguments.extend(("--label", f"{key}={value}"))
    return arguments


def _inspect_one(docker: str, resource: str, name: str, results: dict[str, object], started: float) -> dict[str, object]:
    output = _require_success(_run(_docker_command(resource, "inspect", name), results, started), f"inspect {resource}")
    parsed = json.loads(output)
    if not isinstance(parsed, list) or len(parsed) != 1 or not isinstance(parsed[0], dict):
        raise RuntimeError(f"unexpected {resource} inspect result")
    return parsed[0]


def _require_labels(labels: object) -> None:
    if not isinstance(labels, dict) or any(labels.get(key) != value for key, value in LABELS.items()):
        raise RuntimeError("probe resource labels do not prove exact ownership")


def _verify_network(docker: str, results: dict[str, object], started: float) -> None:
    inspected = _inspect_one(docker, "network", NETWORK, results, started)
    _require_labels(inspected.get("Labels"))
    if inspected.get("Name") != NETWORK or inspected.get("Driver") != "bridge" or inspected.get("Internal") is not True:
        raise RuntimeError("probe network is not the exact owned internal bridge")
    endpoints = inspected.get("Containers", {})
    if not isinstance(endpoints, dict):
        raise RuntimeError("probe network endpoint inventory is invalid")
    results["network"] = {
        "id": inspected.get("Id"),
        "name": inspected.get("Name"),
        "driver": inspected.get("Driver"),
        "internal": inspected.get("Internal"),
        "labels": inspected.get("Labels"),
        "endpoint_ids": sorted(endpoints),
    }


def _verify_container(docker: str, image_id: str, results: dict[str, object], started: float) -> int:
    inspected = _inspect_one(docker, "container", CONTAINER, results, started)
    _require_labels(inspected.get("Config", {}).get("Labels") if isinstance(inspected.get("Config"), dict) else None)
    if inspected.get("Image") != image_id:
        raise RuntimeError("probe container image is not the preflight-resolved immutable image")
    settings = inspected.get("NetworkSettings", {})
    networks = settings.get("Networks", {}) if isinstance(settings, dict) else {}
    if not isinstance(networks, dict) or set(networks) != {NETWORK}:
        raise RuntimeError("probe container is not attached only to its internal bridge")
    ports = settings.get("Ports", {}) if isinstance(settings, dict) else {}
    bindings = ports.get("5432/tcp") if isinstance(ports, dict) else None
    if not isinstance(bindings, list) or len(bindings) != 1 or not isinstance(bindings[0], dict):
        raise RuntimeError("probe PostgreSQL has an unexpected port binding")
    binding = bindings[0]
    host_ip = binding.get("HostIp")
    host_port = str(binding.get("HostPort", ""))
    if host_ip != "127.0.0.1" or not host_port.isdigit() or not 1 <= int(host_port) <= 65535:
        raise RuntimeError("probe PostgreSQL is not published on one literal loopback port")
    config = inspected.get("Config", {})
    exposed = config.get("ExposedPorts", {}) if isinstance(config, dict) else {}
    if not isinstance(exposed, dict) or set(exposed) != {"5432/tcp"}:
        raise RuntimeError("probe PostgreSQL exposes an unexpected port")
    host_config = inspected.get("HostConfig", {})
    if not isinstance(host_config, dict) or host_config.get("Privileged") is True or host_config.get("Binds"):
        raise RuntimeError("probe PostgreSQL has privileged mode or bind mounts")
    tmpfs = host_config.get("Tmpfs", {})
    if not isinstance(tmpfs, dict) or set(tmpfs) != {"/var/lib/postgresql/data"}:
        raise RuntimeError("probe PostgreSQL does not use exactly the expected PGDATA tmpfs")
    mounts = inspected.get("Mounts", [])
    if mounts not in (None, []):
        raise RuntimeError("probe PostgreSQL has unexpected Docker mounts or volumes")
    network = _inspect_one(docker, "network", NETWORK, results, started)
    endpoints = network.get("Containers", {})
    container_id = inspected.get("Id")
    if not isinstance(endpoints, dict) or set(endpoints) != {container_id}:
        raise RuntimeError("probe network has an unexpected endpoint")
    results["network"] = {
        "id": network.get("Id"),
        "name": network.get("Name"),
        "driver": network.get("Driver"),
        "internal": network.get("Internal"),
        "labels": network.get("Labels"),
        "endpoint_ids": sorted(endpoints),
    }
    results["container"] = {
        "id": container_id,
        "image": inspected.get("Image"),
        "networks": sorted(networks),
        "bindings": bindings,
        "mounts": mounts,
        "privileged": host_config.get("Privileged"),
        "binds": host_config.get("Binds"),
        "tmpfs": tmpfs,
    }
    return int(host_port)


def _wait_ready(docker: str, results: dict[str, object], started: float) -> None:
    deadline = min(started + MAX_RUNTIME_SECONDS, time.monotonic() + READY_TIMEOUT_SECONDS)
    while time.monotonic() < deadline:
        completed = _run(_docker_command("exec", CONTAINER, "pg_isready", "-U", USERNAME, "-d", DATABASE), results, started, timeout=5)
        if completed.returncode == 0:
            return
        time.sleep(1)
    raise RuntimeError("PostgreSQL did not become ready within 60 seconds")


def _native_select(port: int, results: dict[str, object], started: float) -> None:
    dsn = f"postgresql://{USERNAME}:{PASSWORD}@127.0.0.1:{port}/{DATABASE}"
    source = """
import os
import psycopg2
dsn = os.environ[\"LOCALOS_HFLYPI_PROBE_DSN\"]
expected = os.environ[\"LOCALOS_HFLYPI_PROBE_EXPECTED_DSN\"]
if dsn != expected:
    raise RuntimeError(\"unexpected probe DSN\")
connection = psycopg2.connect(dsn, connect_timeout=3)
try:
    connection.set_session(readonly=True, autocommit=True)
    cursor = connection.cursor()
    try:
        cursor.execute(\"SELECT 1\")
        if cursor.fetchone() != (1,):
            raise RuntimeError(\"unexpected SELECT result\")
    finally:
        cursor.close()
finally:
    connection.close()
"""
    environment = _environment(
        {
            "LOCALOS_HFLYPI_PROBE_DSN": dsn,
            "LOCALOS_HFLYPI_PROBE_EXPECTED_DSN": dsn,
        }
    )
    _require_success(_run([sys.executable, "-I", "-B", "-c", source], results, started, timeout=10, environment=environment), "native psycopg SELECT 1")


def main() -> int:
    started = time.monotonic()
    results: dict[str, object] = {
        "kind": "native_testcontainers_internal_postgres_probe",
        "nonce": NONCE,
        "status": "running",
        "commands": [],
        "resources_retained": {"container": CONTAINER, "network": NETWORK},
    }
    try:
        if RESULT_PATH.exists():
            raise RuntimeError(f"refusing to overwrite prior probe artifact: {RESULT_PATH}")
        free = shutil.disk_usage(Path.cwd()).free
        results["free_bytes"] = free
        if free < MIN_FREE_BYTES:
            raise RuntimeError("at least 5 GiB free disk is required before this probe")
        if not Path(DOCKER).is_file():
            raise RuntimeError("reviewed Docker CLI path is unavailable")
        context_text = _require_success(_run(_docker_command("context", "inspect", DOCKER_CONTEXT), results, started), "Docker context identity")
        context = json.loads(context_text)
        if not isinstance(context, list) or len(context) != 1 or context[0].get("Endpoints", {}).get("docker", {}).get("Host") != DOCKER_HOST:
            raise RuntimeError("Docker context does not target the reviewed local socket")
        results["docker_context_endpoint"] = DOCKER_HOST
        _refuse_existing(DOCKER, "network", NETWORK, results, started)
        _refuse_existing(DOCKER, "container", CONTAINER, results, started)
        image_id = _require_success(_run(_docker_command("image", "inspect", "--format", "{{.Id}}", IMAGE_TAG), results, started), "local image preflight")
        if image_id != IMAGE_ID:
            raise RuntimeError("local image tag does not resolve to the reviewed immutable image ID")
        results["image_id"] = image_id
        _require_success(_run(_docker_command("network", "create", "--driver", "bridge", "--internal", *_labels_arguments(), NETWORK), results, started), "create internal network")
        _verify_network(DOCKER, results, started)
        create = [
            *_docker_command("container", "create"),
            "--pull",
            "never",
            "--name",
            CONTAINER,
            *_labels_arguments(),
            "--network",
            NETWORK,
            "--tmpfs",
            "/var/lib/postgresql/data:rw,noexec,nosuid,size=512m",
            "--publish",
            "127.0.0.1::5432",
            "--env",
            f"POSTGRES_USER={USERNAME}",
            "--env",
            f"POSTGRES_PASSWORD={PASSWORD}",
            "--env",
            f"POSTGRES_DB={DATABASE}",
            "--env",
            "PGDATA=/var/lib/postgresql/data",
        ]
        for key in PROVIDER_ENVIRONMENTS:
            create.extend(("--env", f"{key}="))
        create.append(image_id)
        _require_success(_run(create, results, started), "create pinned PostgreSQL")
        _require_success(_run(_docker_command("container", "start", CONTAINER), results, started), "start pinned PostgreSQL")
        port = _verify_container(DOCKER, image_id, results, started)
        results["loopback_port"] = port
        _wait_ready(DOCKER, results, started)
        _native_select(port, results, started)
        results["status"] = "passed"
        return 0
    except BaseException:
        error = sys.exception()
        results["status"] = "failed"
        results["error"] = f"{type(error).__name__}: {error}"
        return 1
    finally:
        results["elapsed_seconds"] = round(time.monotonic() - started, 3)
        rendered = json.dumps(results, sort_keys=True)
        if not RESULT_PATH.exists():
            RESULT_PATH.write_text(rendered + "\n", encoding="utf-8")
        print(rendered)


if __name__ == "__main__":
    raise SystemExit(main())
