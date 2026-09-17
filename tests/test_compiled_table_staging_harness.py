import importlib.util
import hashlib
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "test_compiled_table_staging.py"


@pytest.fixture
def staging_script():
    specification = importlib.util.spec_from_file_location("compiled_table_staging_harness", SCRIPT_PATH)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def arguments():
    return [
        "--base-url", "http://127.0.0.1:18017",
        "--container", "localos-readiness-20260917-app-1",
        "--ingress-container", "localos-readiness-20260917-audit-ingress-1",
        "--compose-project", "localos-readiness-20260917",
        "--app-environment", "staging",
        "--postgres-database", "localos_staging",
    ]


def valid_containers(target, source):
    app = {
        "Config": {"Labels": {"com.docker.compose.project": target.compose_project, "com.docker.compose.service": "app"}},
        "State": {"Running": True},
        "NetworkSettings": {"Networks": {"internal": {"Aliases": ["app"]}}},
    }
    ingress = {
        "Config": {
            "Labels": {"com.docker.compose.project": target.compose_project, "com.docker.compose.service": "audit-ingress"},
            "Entrypoint": ["python", "/tmp/audit_proxy.py"],
            "Cmd": [],
        },
        "State": {"Running": True},
        "NetworkSettings": {
            "Networks": {"internal": {"Aliases": ["audit-ingress"]}},
            "Ports": {"8000/tcp": [{"HostIp": "127.0.0.1", "HostPort": "18017"}]},
        },
        "Mounts": [{"Type": "bind", "Destination": "/tmp/audit_proxy.py", "RW": False, "Source": str(source)}],
    }
    return app, ingress


@pytest.mark.parametrize("override", [
    ["--base-url", "https://localos.pro"],
    ["--base-url", "http://localhost:18017"],
    ["--base-url", "http://127.0.0.1:18017/api"],
    ["--app-environment", "production"],
    ["--postgres-database", "localos"],
])
def test_target_parser_fails_closed_for_non_synthetic_or_non_loopback_targets(staging_script, override):
    supplied = arguments()
    position = supplied.index(override[0])
    supplied[position + 1] = override[1]

    with pytest.raises(ValueError):
        staging_script.parse_target(supplied)


def test_target_identity_requires_checked_ingress_before_container_environment(staging_script, monkeypatch):
    target = staging_script.parse_target(arguments())
    app = {"Config": {"Labels": {}}, "State": {}}
    ingress = {"Config": {"Labels": {}}, "State": {}}
    monkeypatch.setattr(staging_script, "inspect_container", lambda name: app if name == target.container else ingress)
    seen = []
    def verify(_target, actual_app, actual_ingress):
        seen.append((actual_app, actual_ingress))
    monkeypatch.setattr(staging_script, "verify_ingress", verify)
    monkeypatch.setattr(
        staging_script,
        "container_python",
        lambda _target, _source: "staging localos_staging",
    )

    staging_script.verify_target_identity(target)
    assert seen == [(app, ingress)]

    monkeypatch.setattr(staging_script, "container_python", lambda _target, _source: "production localos")
    with pytest.raises(RuntimeError, match="environment"):
        staging_script.verify_target_identity(target)


def test_ingress_rejects_mismatched_project_port_or_remote_docker_context(staging_script, monkeypatch, tmp_path):
    target = staging_script.parse_target(arguments())
    source = tmp_path / "audit_proxy.py"
    source.write_text("proxy")
    app, ingress = valid_containers(target, source)
    monkeypatch.setattr(staging_script, "docker_context_endpoint", lambda: "tcp://remote.example:2376")
    with pytest.raises(RuntimeError, match="Unix Docker context"):
        staging_script.verify_ingress(target, app, ingress)

    monkeypatch.setattr(staging_script, "docker_context_endpoint", lambda: "unix:///tmp/docker.sock")
    monkeypatch.setenv("DOCKER_HOST", "tcp://remote.example:2376")
    with pytest.raises(RuntimeError, match="Unix Docker host"):
        staging_script.verify_ingress(target, app, ingress)

    monkeypatch.setenv("DOCKER_HOST", "unix:///tmp/docker.sock")
    monkeypatch.setattr(staging_script, "inspect_network", lambda _network: {"Internal": True})
    ingress["Config"]["Labels"]["com.docker.compose.project"] = "other"
    with pytest.raises(RuntimeError, match="Compose project"):
        staging_script.verify_ingress(target, app, ingress)

    ingress["Config"]["Labels"]["com.docker.compose.project"] = target.compose_project
    ingress["NetworkSettings"]["Ports"]["8000/tcp"][0]["HostPort"] = "18018"
    with pytest.raises(RuntimeError, match="loopback port"):
        staging_script.verify_ingress(target, app, ingress)


def test_valid_ingress_profile_requires_internal_network_app_alias_proxy_hash_and_readonly_mount(staging_script, monkeypatch, tmp_path):
    target = staging_script.parse_target(arguments())
    source = tmp_path / "audit_proxy.py"
    source.write_text("proxy")
    app, ingress = valid_containers(target, source)
    monkeypatch.setenv("DOCKER_HOST", "unix:///tmp/docker.sock")
    monkeypatch.setattr(staging_script, "docker_context_endpoint", lambda: "unix:///tmp/docker.sock")
    monkeypatch.setattr(staging_script, "inspect_network", lambda _network: {"Internal": True})
    monkeypatch.setattr(staging_script, "AUDIT_PROXY_SHA256", hashlib.sha256(source.read_bytes()).hexdigest())

    staging_script.verify_ingress(target, app, ingress)

    monkeypatch.setattr(staging_script, "AUDIT_PROXY_SHA256", "0" * 64)
    with pytest.raises(RuntimeError, match="proxy source"):
        staging_script.verify_ingress(target, app, ingress)

    monkeypatch.setattr(staging_script, "AUDIT_PROXY_SHA256", hashlib.sha256(source.read_bytes()).hexdigest())
    ingress["Mounts"][0]["RW"] = True
    with pytest.raises(RuntimeError, match="read-only"):
        staging_script.verify_ingress(target, app, ingress)

    ingress["Mounts"][0]["RW"] = False
    app["State"]["Running"] = False
    with pytest.raises(RuntimeError, match="must be running"):
        staging_script.verify_ingress(target, app, ingress)

    app["State"]["Running"] = True
    monkeypatch.setattr(staging_script, "inspect_network", lambda _network: {"Internal": False})
    with pytest.raises(RuntimeError, match="internal Docker network"):
        staging_script.verify_ingress(target, app, ingress)

    monkeypatch.setattr(staging_script, "inspect_network", lambda _network: {"Internal": True})
    app["NetworkSettings"]["Networks"]["internal"]["Aliases"] = ["not-app"]
    with pytest.raises(RuntimeError, match="app DNS alias"):
        staging_script.verify_ingress(target, app, ingress)


def test_worker_claim_is_scoped_to_the_run_and_never_uses_global_queue_claim():
    source = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "claim_next_agent_run" not in source
    assert "WHERE id=%s AND blueprint_id=%s AND business_id=%s AND status='queued'" in source
    assert "execute_claimed_compiled_agent_run" in source
