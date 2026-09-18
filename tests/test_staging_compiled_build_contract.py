"""Compiled browser fixtures require an explicit build-time staging opt-in."""
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
FLAG = "VITE_COMPILED_SCRIPT_PREVIEW_ENABLED"
COMPILED_STAGING_FILES = (
    "docker-compose.yml",
    "docker-compose.workers.yml",
    "docker-compose.staging.yml",
    "docker/compiled-script-runner/compose.fragment.yml",
    "docker-compose.compiled-staging.yml",
)


def test_canonical_image_accepts_opt_in_without_enabling_it_by_default():
    frontend_stage = (ROOT / "Dockerfile").read_text().split("FROM python:", 1)[0]
    assert f"ARG {FLAG}=false" in frontend_stage
    assert f"ENV {FLAG}=${{{FLAG}}}" in frontend_stage
    assert frontend_stage.index(f"ENV {FLAG}=") < frontend_stage.index("RUN npm run build:all")


def test_staging_compose_passes_preview_opt_in_to_the_build():
    docker = shutil.which("docker")
    if not docker:
        pytest.skip("Docker Compose CLI required; no daemon needed")
    result = subprocess.run(
        [docker, "compose", "--env-file", "/dev/null", "-f", "docker-compose.yml",
         "-f", "docker-compose.staging.yml", "config", "--no-env-resolution", "--format", "json"],
        cwd=ROOT,
        env={"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", "")},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, "Compose rendering failed; do not expose rendered credentials"
    app = json.loads(result.stdout)["services"]["app"]
    assert app["build"]["args"].get(FLAG) == "true"


def test_compiled_staging_profile_is_loopback_only_with_a_tracked_readonly_ingress():
    docker = shutil.which("docker")
    if not docker:
        pytest.skip("Docker Compose CLI required; no daemon needed")
    digest = "sha256:" + "a" * 64
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "COMPILED_SCRIPT_RUNNER_IMAGE": f"example.invalid/runner@{digest}",
        "COMPILED_SCRIPT_RUNNER_IMAGE_DIGEST": digest,
        "COMPILED_SCRIPT_RUNNER_SHARED_SECRET": "synthetic-render-only",
        "COMPILED_STAGING_EXECUTE_ENABLED": "true",
        "COMPILED_STAGING_ADVANCED_ENABLED": "true",
        "COMPILED_STAGING_PILOT_BUSINESS_IDS": "00000000-0000-4000-8000-000000000001",
    }
    command = [docker, "compose", "--env-file", "/dev/null"]
    for compose_file in COMPILED_STAGING_FILES:
        command.extend(("-f", compose_file))
    command.extend(("config", "--no-env-resolution", "--format", "json"))
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, "Compiled staging Compose rendering failed"
    rendered = json.loads(result.stdout)
    app = rendered["services"]["app"]
    ingress = rendered["services"]["audit-ingress"]
    runner = rendered["services"]["compiled-script-runner"]
    assert app.get("ports", []) == []
    assert app["environment"]["COMPILED_SCRIPT_PREVIEW_ENABLED"] == "true"
    assert app["environment"]["COMPILED_SCRIPT_EXECUTE_ENABLED"] == "true"
    assert app["environment"]["COMPILED_SCRIPT_ADVANCED_ENABLED"] == "true"
    assert app["environment"]["COMPILED_SCRIPT_PILOT_BUSINESS_IDS"] == "00000000-0000-4000-8000-000000000001"
    assert "*" not in app["environment"]["COMPILED_SCRIPT_PILOT_BUSINESS_IDS"]
    assert ingress["ports"] == [{"mode": "ingress", "host_ip": "127.0.0.1", "published": "18017", "target": 8000, "protocol": "tcp"}]
    assert ingress["read_only"] is True
    assert ingress["environment"] == {"PYTHONDONTWRITEBYTECODE": "1"}
    assert ingress["entrypoint"] == ["python", "/opt/audit-proxy/proxy.py"]
    assert ingress["volumes"] == [{"type": "bind", "source": str(ROOT / "docker/audit-ingress/proxy.py"), "target": "/opt/audit-proxy/proxy.py", "read_only": True, "bind": {}}]
    assert rendered["networks"]["default"]["internal"] is True
    assert rendered["networks"]["ingress_access"].get("internal", False) is False
    assert runner["read_only"] is True
    assert runner["networks"] == {"compiled_script_internal": None}


def test_compiled_staging_default_services_exclude_all_worker_and_bot_variants():
    docker = shutil.which("docker")
    if not docker:
        pytest.skip("Docker Compose CLI required; no daemon needed")
    digest = "sha256:" + "b" * 64
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "COMPILED_SCRIPT_RUNNER_IMAGE": f"example.invalid/runner@{digest}",
        "COMPILED_SCRIPT_RUNNER_IMAGE_DIGEST": digest,
        "COMPILED_SCRIPT_RUNNER_SHARED_SECRET": "synthetic-render-only",
    }
    command = [docker, "compose", "--env-file", "/dev/null"]
    for compose_file in COMPILED_STAGING_FILES:
        command.extend(("-f", compose_file))
    command.extend(("config", "--services"))
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, "Compiled staging service rendering failed"
    assert set(result.stdout.split()) == {"app", "audit-ingress", "compiled-script-runner", "postgres", "redis"}


def test_compiled_staging_runbook_carries_a_verified_local_docker_socket_into_env_i():
    runbook = (ROOT / "docker/audit-ingress/README.md").read_text(encoding="utf-8")
    assert 'docker_host="${DOCKER_HOST:-}"' in runbook
    assert "docker context inspect --format '{{.Endpoints.docker.Host}}'" in runbook
    assert 'case "$docker_host" in' in runbook
    assert 'unix://*)' in runbook
    assert "A local Unix Docker context is required." in runbook
    assert 'env -i PATH="$PATH" HOME="$HOME" DOCKER_HOST="$docker_host"' in runbook
    assert "host-access network still permits network egress" in runbook
    assert "no credentials or arbitrary-upstream option" in runbook
