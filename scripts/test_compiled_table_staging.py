#!/usr/bin/env python3
"""Real API/PostgreSQL/runner proof using internal manual-source staging only.

This is not evidence of a model-generation or a real-user pilot. Every account,
table and balance used here belongs to the synthetic isolated staging fixture.
"""
import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import subprocess
import uuid
from urllib.parse import urlparse

import requests


SOURCE = """def process(input_payload):
    accepted = []
    errors = []
    seen = []
    duplicates = 0
    invalid = 0
    for index, row in enumerate(input_payload.get('rows', [])):
        missing = [column for column in ['email'] if not row.get(column, '').strip()]
        if missing:
            invalid += 1
            errors.append({'row': index + 1, 'code': 'required', 'columns': missing})
            continue
        key = row.get('email', '').strip().lower()
        if key in seen:
            duplicates += 1
            errors.append({'row': index + 1, 'code': 'duplicate'})
            continue
        seen.append(key)
        accepted.append(row)
    return {'schema': 'localos_compiled_script_result_v1', 'rows': accepted,
        'report': {'received': len(input_payload.get('rows', [])), 'accepted': len(accepted),
            'duplicates': duplicates, 'invalid': invalid, 'errors': errors}}
"""
AUDIT_INGRESS_SERVICE = "audit-ingress"
APP_SERVICE = "app"
ROOT = Path(__file__).resolve().parents[1]
AUDIT_PROXY_RELATIVE_PATH = Path("docker/audit-ingress/proxy.py")
AUDIT_PROXY_SOURCE = ROOT / AUDIT_PROXY_RELATIVE_PATH
AUDIT_PROXY_PATH = "/opt/audit-proxy/proxy.py"
AUDIT_PROXY_SHA256 = "0fd0f918a5390fdf97d51019d5e9481227e9d1410838e23c1325718b27c22798"


@dataclass(frozen=True)
class StagingTarget:
    base_url: str
    container: str
    ingress_container: str
    compose_project: str
    app_environment: str
    postgres_database: str


def parse_target(arguments):
    parser = argparse.ArgumentParser(
        description="Run the compiled table proof against one explicitly identified synthetic staging app."
    )
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--container", required=True)
    parser.add_argument("--ingress-container", required=True)
    parser.add_argument("--compose-project", required=True)
    parser.add_argument("--app-environment", required=True)
    parser.add_argument("--postgres-database", required=True)
    values = parser.parse_args(arguments)
    target = StagingTarget(
        base_url=values.base_url.rstrip("/"),
        container=values.container,
        ingress_container=values.ingress_container,
        compose_project=values.compose_project,
        app_environment=values.app_environment,
        postgres_database=values.postgres_database,
    )
    validate_target_shape(target)
    return target


def validate_target_shape(target):
    parsed = urlparse(target.base_url)
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.port is None:
        raise ValueError("base URL must be an explicit http://127.0.0.1:<port> staging endpoint")
    if parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
        raise ValueError("base URL must not include a path, query, or fragment")
    if not target.container.strip() or any(character.isspace() for character in target.container):
        raise ValueError("container must be one Docker container name")
    if not target.ingress_container.strip() or any(character.isspace() for character in target.ingress_container):
        raise ValueError("ingress container must be one Docker container name")
    if target.ingress_container == target.container:
        raise ValueError("app and ingress containers must be distinct")
    if not target.compose_project.strip() or any(character.isspace() for character in target.compose_project):
        raise ValueError("compose project must be one explicit name")
    if target.app_environment != "staging" or target.postgres_database != "localos_staging":
        raise ValueError("only synthetic staging/localos_staging is supported")


def container_python(target, source):
    result = subprocess.run(["docker", "exec", target.container, "python", "-c", source],
                            capture_output=True, text=True, check=True, timeout=180)
    return result.stdout.strip()


def docker_context_endpoint():
    result = subprocess.run(
        ["docker", "context", "inspect", "--format", "{{ .Endpoints.docker.Host }}"],
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    )
    return result.stdout.strip()


def inspect_container(container):
    result = subprocess.run(
        ["docker", "inspect", container],
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    )
    inspected = json.loads(result.stdout)
    if not isinstance(inspected, list) or len(inspected) != 1 or not isinstance(inspected[0], dict):
        raise RuntimeError("Docker inspection did not return exactly one container")
    return inspected[0]


def inspect_network(network):
    result = subprocess.run(
        ["docker", "network", "inspect", network],
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    )
    inspected = json.loads(result.stdout)
    if not isinstance(inspected, list) or len(inspected) != 1 or not isinstance(inspected[0], dict):
        raise RuntimeError("Docker inspection did not return exactly one network")
    return inspected[0]


def compose_label(details, label):
    config = details.get("Config") if isinstance(details.get("Config"), dict) else {}
    labels = config.get("Labels") if isinstance(config.get("Labels"), dict) else {}
    return str(labels.get(label) or "")


def running(details):
    state = details.get("State") if isinstance(details.get("State"), dict) else {}
    return bool(state.get("Running"))


def network_names(details):
    settings = details.get("NetworkSettings") if isinstance(details.get("NetworkSettings"), dict) else {}
    networks = settings.get("Networks") if isinstance(settings.get("Networks"), dict) else {}
    return set(networks)


def app_has_alias(details, network, alias):
    settings = details.get("NetworkSettings") if isinstance(details.get("NetworkSettings"), dict) else {}
    networks = settings.get("Networks") if isinstance(settings.get("Networks"), dict) else {}
    endpoint = networks.get(network) if isinstance(networks.get(network), dict) else {}
    aliases = endpoint.get("Aliases") if isinstance(endpoint.get("Aliases"), list) else []
    return alias in aliases


def shared_internal_network_with_app_alias(app, ingress):
    for network in network_names(app).intersection(network_names(ingress)):
        details = inspect_network(network)
        if details.get("Internal") is True and app_has_alias(app, network, "app"):
            return True
    return False


def ingress_has_exact_port(details, port):
    settings = details.get("NetworkSettings") if isinstance(details.get("NetworkSettings"), dict) else {}
    ports = settings.get("Ports") if isinstance(settings.get("Ports"), dict) else {}
    bindings = ports.get("8000/tcp")
    return (
        isinstance(bindings, list)
        and len(bindings) == 1
        and isinstance(bindings[0], dict)
        and bindings[0].get("HostIp") == "127.0.0.1"
        and bindings[0].get("HostPort") == str(port)
    )


def proxy_mount_source(details):
    mounts = details.get("Mounts") if isinstance(details.get("Mounts"), list) else []
    for mount in mounts:
        if not isinstance(mount, dict):
            continue
        if mount.get("Type") == "bind" and mount.get("Destination") == AUDIT_PROXY_PATH and mount.get("RW") is False:
            source = mount.get("Source")
            return Path(source) if isinstance(source, str) else None
    return None


def verify_proxy_source(source):
    if source is None or not source.is_file():
        raise RuntimeError("audit proxy must have a read-only tracked source mount")
    if source.resolve() != AUDIT_PROXY_SOURCE.resolve():
        raise RuntimeError("audit proxy must mount the canonical tracked source")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if digest != AUDIT_PROXY_SHA256:
        raise RuntimeError("audit proxy source does not match the fixed app:8000 route")


def verify_ingress(target, app, ingress):
    parsed = urlparse(target.base_url)
    docker_host = os.getenv("DOCKER_HOST", "")
    if docker_host and not docker_host.startswith("unix://"):
        raise RuntimeError("compiled staging proof requires a local Unix Docker host")
    if docker_context_endpoint()[:7] != "unix://":
        raise RuntimeError("compiled staging proof requires a local Unix Docker context")
    if not running(app) or not running(ingress):
        raise RuntimeError("selected app and ingress containers must be running")
    if compose_label(app, "com.docker.compose.project") != target.compose_project:
        raise RuntimeError("app does not belong to the explicitly selected Compose project")
    if compose_label(ingress, "com.docker.compose.project") != target.compose_project:
        raise RuntimeError("ingress does not belong to the explicitly selected Compose project")
    if compose_label(app, "com.docker.compose.service") != APP_SERVICE:
        raise RuntimeError("selected app container does not have the app service identity")
    if compose_label(ingress, "com.docker.compose.service") != AUDIT_INGRESS_SERVICE:
        raise RuntimeError("selected ingress container does not have the audit-ingress service identity")
    if not shared_internal_network_with_app_alias(app, ingress):
        raise RuntimeError("app and ingress must share an internal Docker network with the app DNS alias")
    if not ingress_has_exact_port(ingress, parsed.port):
        raise RuntimeError("ingress does not own the explicitly selected loopback port")
    config = ingress.get("Config") if isinstance(ingress.get("Config"), dict) else {}
    if config.get("Entrypoint") != ["python", AUDIT_PROXY_PATH] or config.get("Cmd") not in ([], None):
        raise RuntimeError("ingress is not the fixed audit proxy")
    verify_proxy_source(proxy_mount_source(ingress))


def verify_target_identity(target):
    app = inspect_container(target.container)
    ingress = inspect_container(target.ingress_container)
    verify_ingress(target, app, ingress)
    guard = container_python(target, "import os; print(os.getenv('APP_ENV'),os.getenv('POSTGRES_DB'))")
    if guard != f"{target.app_environment} {target.postgres_database}":
        raise RuntimeError("container environment does not match the explicitly selected synthetic staging target")


def main(arguments=None):
    target = parse_target(arguments)
    verify_target_identity(target)
    session = requests.Session()
    response = session.post(target.base_url + "/api/auth/login", json={"email": "admin@localos-e2e.invalid", "password": "LocalOS-E2E-2026!"}, timeout=15)
    response.raise_for_status()
    session.headers["X-CSRF-Token"] = session.cookies.get("localos_csrf", "")
    session.headers["Origin"] = target.base_url
    business_id = container_python(target, "from scripts.staging_fixture_cli import owner_business_id; print(owner_business_id())")
    # Give the synthetic test account credits; no real balance is touched.
    container_python(target, "from database_manager import get_db_connection; c=get_db_connection(); q=c.cursor(); q.execute(\"UPDATE users SET credits_balance=100 WHERE email='admin@localos-e2e.invalid'\"); c.commit(); c.close()")
    def call(method, path, payload=None, expected=200):
        result = session.request(method, target.base_url + path, json=payload, timeout=60)
        if result.status_code != expected:
            raise AssertionError(f"{method} {path}: {result.status_code}: {result.text[:1200]}")
        return result.json()
    blueprint = call("POST", "/api/agent-blueprints", {"business_id": business_id, "name": "[E2E] Compiled table proof", "execution_mode": "one_off"}, 201)["blueprint"]
    prefix = "/api/agent-blueprints/" + blueprint["id"] + "/compiled-script"
    rows = [{"email": "a@example.test", "amount": "001"}, {"email": " A@example.test ", "amount": "0"}, {"email": "", "amount": "5"}]
    expected = {"schema": "localos_compiled_script_result_v1", "rows": [rows[0]], "report": {
        "received": 3, "accepted": 1, "duplicates": 1, "invalid": 1,
        "errors": [{"row": 2, "code": "duplicate"}, {"row": 3, "code": "required", "columns": ["email"]}],
    }}
    compile_payload = {"description": "Synthetic table proof", "source": SOURCE,
        "idempotency_key": str(uuid.uuid4()), "table_contract": {"version": 2, "columns": ["email", "amount"],
        "required_columns": ["email"], "dedupe_columns": ["email"], "version_name": "Проверка таблицы"},
        "fixtures": [{"input": {"rows": rows}, "expected": expected, "source": "user"}]}
    compiled = call("POST", prefix + "/compile", compile_payload, 201)
    replay = call("POST", prefix + "/compile", compile_payload)
    assert replay["artifact"] == compiled["artifact"]
    version_id = compiled["candidate_version"]["id"]
    assert replay["candidate_version"]["id"] == version_id
    for _attempt in range(10):
        preview = call("POST", prefix + "/preview", {"version_id": version_id, "input": {"rows": rows}})
        assert preview["preview"]["status"] == "passed"
    call("POST", prefix + "/approve", {"version_id": version_id,
        "approval_digest": preview["approval_digest"], "fixture_digest": preview["fixture_digest"]})
    details = call("GET", "/api/agent-blueprints/" + blueprint["id"])
    assert details["compiled_approved_version"]["id"] == version_id
    run_ids = []
    for number in range(5):
        table = {"rows": rows if number == 0 else [{"email": f"b{number}@example.test", "amount": "0"}]}
        snapshot = call("POST", prefix + "/snapshots", {"input": table}, 201)["snapshot"]
        payload = {"version_id": version_id, "snapshot_id": snapshot["id"], "idempotency_key": str(uuid.uuid4())}
        queued = call("POST", prefix + "/run", payload, 202)
        run_id = queued["run"]["id"]
        run_ids.append(run_id)
        assert call("POST", prefix + "/run", payload)["run"]["id"] == run_id
        worker_source = "\n".join([
            "import json", "import uuid", "from database_manager import DatabaseManager",
            "from services.agent_run_queue import execute_claimed_compiled_agent_run",
            "db=DatabaseManager(); cursor=db.conn.cursor()",
            "cursor.execute(\"\"\"UPDATE agent_runs SET status='running', started_at=COALESCE(started_at, NOW()), heartbeat_at=NOW(), next_attempt_at=NULL, attempt_count=attempt_count+1, lease_token=%s, updated_at=NOW() WHERE id=%s AND blueprint_id=%s AND business_id=%s AND status='queued' RETURNING *\"\"\", (str(uuid.uuid4()), " + repr(run_id) + ", " + repr(blueprint["id"]) + ", " + repr(business_id) + ",))",
            "run=cursor.fetchone()",
            "assert run and run['id']==" + repr(run_id) + ", 'target run was not queued'",
            "db.conn.commit(); db.rollback_and_close()",
            "result=execute_claimed_compiled_agent_run(run)",
            "assert result and result.get('success'), result",
            "print(json.dumps({'status':result['run']['status'],'run_id':result['run']['id']}))",
        ])
        worker_result = json.loads(container_python(target, worker_source).splitlines()[-1])
        assert worker_result["status"] == "completed"
        result = call("GET", "/api/agent-runs/" + run_id)["run"]["output_json"]
        assert result["runtime_ai_calls"] == 0 and result["external_effects"] == []
        assert result["rows"] == table["rows"][:1]
        assert result["report"] == (expected["report"] if number == 0 else {"received": 1, "accepted": 1, "duplicates": 0, "invalid": 0, "errors": []})
    assert len(set(run_ids)) == 5
    print(json.dumps({"status": "passed", "mode": "internal_manual_source_staging",
        "model_generation_tested": False, "real_user_pilot": False,
        "blueprint_id": blueprint["id"], "version_id": version_id, "run_ids": run_ids,
        "compile_replay": True, "run_replay": True, "runtime_ai_calls": 0,
        "table_contract_version": 2, "previews": 10, "runs": 5}, ensure_ascii=False))


if __name__ == "__main__":
    main()
