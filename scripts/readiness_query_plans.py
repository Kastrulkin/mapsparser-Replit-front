#!/usr/bin/env python3
"""Capture bounded query plans for the synthetic dashboard read journey.

This tool is intentionally limited to one UUID-owned, migrated synthetic DB.
It is not a production plan, load test, or generic SQL runner. Query counts
distinguish executed reads from DDL/writes so comparisons preserve both legacy
request-time schema maintenance and schema-free read behavior.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import uuid
from typing import Any

import psycopg2
from psycopg2 import sql

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
import readiness_journey_benchmark
import readiness_journey_load
import readiness_journey_measure


ROOT = SCRIPTS.parent
OWNED_PREFIX = "localos_readiness_queryproof_"
DEFAULT_DSN_ENV = readiness_journey_benchmark.DEFAULT_DSN_ENV
CONFIG_ENV = "LOCALOS_READINESS_QUERY_PROOF_CONFIG"

ACCESS_QUERY = """
SELECT b.*
FROM businesses b
LEFT JOIN networks n ON n.id = b.network_id
LEFT JOIN network_members nm ON nm.network_id = b.network_id AND nm.user_id = %s AND nm.status = 'active'
LEFT JOIN business_members bm ON bm.business_id = b.id AND bm.user_id = %s AND bm.status = 'active'
WHERE (b.owner_id = %s OR n.owner_id = %s OR nm.user_id IS NOT NULL OR bm.user_id IS NOT NULL)
  AND (b.is_active = TRUE OR b.is_active IS NULL)
  AND COALESCE(b.entity_group, 'lead') IN ('client', 'internal', 'demo')
  AND LOWER(COALESCE(b.description, '')) NOT LIKE 'lead shadow business for outreach lead%%'
ORDER BY b.created_at DESC
"""
SERVICES_QUERY = """
SELECT id, name, description, category, keywords, price, created_at, updated_at
FROM userservices
WHERE business_id = %s AND is_active = TRUE
ORDER BY created_at DESC
"""
CARDS_QUERY = """
SELECT * FROM cards WHERE business_id = %s ORDER BY version DESC
"""
QUERY_SPECS = (
    ("auth_me_business_access_representative", ACCESS_QUERY, lambda target: (target["user_id"],) * 4),
    ("business_data_services", SERVICES_QUERY, lambda target: (target["business_id"],)),
    ("business_data_cards", CARDS_QUERY, lambda target: (target["business_id"],)),
)


@dataclass
class QueryEvent:
    route: str
    category: str
    statement_sha256: str


def exact_owned_name(name: str) -> bool:
    return bool(re.fullmatch(OWNED_PREFIX + r"[0-9a-f]{32}", name))


def statement_category(statement: object) -> str:
    text = str(statement).lstrip().upper()
    if text.startswith(("CREATE ", "ALTER ", "UPDATE ", "INSERT ", "DELETE ", "DROP ")):
        return "ddl_or_write"
    if text.startswith(("SELECT ", "WITH ")):
        return "read"
    return "other"


def statement_hash(statement: object) -> str:
    return hashlib.sha256(str(statement).encode("utf-8")).hexdigest()


def loaded_guard(expected_path: str, expected_sha256: str) -> dict[str, str]:
    expected = Path(expected_path).resolve()
    loaded = sys.modules.get("sitecustomize")
    observed = Path(str(getattr(loaded, "__file__", ""))).resolve() if loaded else None
    if not expected.is_file() or observed != expected:
        raise ValueError("requires loaded canonical sitecustomize guard")
    observed_sha256 = hashlib.sha256(expected.read_bytes()).hexdigest()
    if observed_sha256 != expected_sha256:
        raise ValueError("canonical guard hash mismatch")
    return {"path": str(expected), "sha256": observed_sha256}


def data_directory_identity(database_url: str, expected: str = "") -> str:
    connection = psycopg2.connect(database_url, connect_timeout=5)
    cursor = connection.cursor()
    try:
        cursor.execute("SHOW data_directory")
        observed = str(cursor.fetchone()[0])
    finally:
        cursor.close()
        connection.close()
    if expected and Path(observed).resolve() != Path(expected).resolve():
        raise ValueError("PostgreSQL data directory identity mismatch")
    return observed


def database_url_for(base_dsn: str, database_name: str) -> str:
    return readiness_journey_benchmark.database_url_for(base_dsn, database_name)


def create_owned_database(base_dsn: str, name: str) -> str:
    if not exact_owned_name(name):
        raise ValueError("refusing database outside query-proof UUID namespace")
    connection = psycopg2.connect(database_url_for(base_dsn, "postgres"), connect_timeout=5)
    cursor = connection.cursor()
    try:
        connection.autocommit = True
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,))
        if cursor.fetchone():
            raise ValueError("refusing an existing query-proof database")
        cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    finally:
        cursor.close()
        connection.close()
    return database_url_for(base_dsn, name)


def cleanup_owned_database(base_dsn: str, name: str, created: bool) -> dict[str, Any]:
    if not created:
        return {"database_name": name, "skipped": "not_created_by_this_invocation"}
    if not exact_owned_name(name):
        raise ValueError("refusing cleanup outside query-proof UUID namespace")
    connection = psycopg2.connect(database_url_for(base_dsn, "postgres"), connect_timeout=5)
    cursor = connection.cursor()
    try:
        connection.autocommit = True
        cursor.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
    finally:
        cursor.close()
        connection.close()
    return {"database_name": name, "removed": True}


def attach_cursor_counter() -> tuple[list[QueryEvent], Any]:
    """Hook DatabaseManager's real cursor wrapper for only this child process."""
    import database_manager

    events: list[QueryEvent] = []
    original = database_manager.DBCursorWrapper.execute

    def counted(cursor_wrapper, query, params=None):
        events.append(QueryEvent("dashboard", statement_category(query), statement_hash(query)))
        return original(cursor_wrapper, query, params)

    database_manager.DBCursorWrapper.execute = counted
    return events, original


def detach_cursor_counter(original: Any) -> None:
    import database_manager

    database_manager.DBCursorWrapper.execute = original


def count_events(events: list[QueryEvent]) -> dict[str, int]:
    return {
        "all": len(events),
        "read": sum(event.category == "read" for event in events),
        "ddl_or_write": sum(event.category == "ddl_or_write" for event in events),
        "other": sum(event.category == "other" for event in events),
    }


def payload_user_id(value: object) -> str:
    if not isinstance(value, dict):
        return ""
    user = value.get("user")
    if not isinstance(user, dict):
        return ""
    return str(user.get("id", ""))


def valid_business_payload(value: object, target: dict[str, str]) -> bool:
    if not isinstance(value, dict) or not isinstance(value.get("business"), dict):
        return False
    if str(value["business"].get("id", "")) != target["business_id"]:
        return False
    services = value.get("services")
    if not isinstance(services, list):
        return False
    ids = {str(item.get("id", "")) for item in services if isinstance(item, dict)}
    return ids == {target["service_id"]}


def route_counts(database_url: str, target: dict[str, str]) -> dict[str, Any]:
    """Dispatch real endpoints and count actual DatabaseManager cursor calls."""
    os.environ["DATABASE_URL"] = database_url
    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))
    from main import app

    client = app.test_client()
    login = client.post("/api/auth/login", json={"email": target["email"], "password": "benchmark-password"})
    token = (login.get_json() or {}).get("token") if login.status_code == 200 else ""
    if not token:
        raise RuntimeError("synthetic login did not return a token")
    headers = {"Authorization": f"Bearer {token}"}
    events, original = attach_cursor_counter()
    try:
        me = client.get("/api/auth/me", headers=headers)
        me_events = events[:]
        business = client.get(f"/api/business/{target['business_id']}/data", headers=headers)
        business_events = events[len(me_events):]
        if me.status_code != 200 or payload_user_id(me.get_json()) != target["user_id"]:
            raise RuntimeError("auth me semantic response mismatch")
        if business.status_code != 200 or not valid_business_payload(business.get_json(), target):
            raise RuntimeError("business data semantic response mismatch")
    finally:
        detach_cursor_counter(original)
    return {
        "instrument": "DatabaseManager.DBCursorWrapper.execute",
        "auth_me": count_events(me_events),
        "business_data": count_events(business_events),
    }


def explain_plans(database_url: str, target: dict[str, str]) -> list[dict[str, Any]]:
    plans: list[dict[str, Any]] = []
    connection = psycopg2.connect(database_url, connect_timeout=5)
    cursor = connection.cursor()
    try:
        cursor.execute("SET LOCAL statement_timeout = '5000ms'")
        cursor.execute("SET LOCAL lock_timeout = '1000ms'")
        for name, query, parameters in QUERY_SPECS:
            cursor.execute("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + query, parameters(target))
            plans.append({"name": name, "source_sql_sha256": statement_hash(query), "plan": cursor.fetchone()[0]})
    finally:
        cursor.close()
        connection.close()
    return plans


def child_run(config: dict[str, Any]) -> dict[str, Any]:
    """Validate guard/identity before importing app and dispatching routes."""
    database_url = readiness_journey_measure.guarded_dsn(str(config.get("database_url", "")))
    target = config.get("target")
    if not isinstance(target, dict) or any(not target.get(key) for key in ("user_id", "business_id", "service_id", "email")):
        raise ValueError("invalid prepared target")
    guard = loaded_guard(str(config.get("guard_path", "")), str(config.get("guard_sha256", "")))
    data_directory_identity(database_url, str(config.get("data_directory", "")))
    readiness_journey_benchmark.remove_external_provider_environment()
    counts = route_counts(database_url, target)
    plans = explain_plans(database_url, target)
    return {"guard": guard, "query_counts": counts, "plans": plans}


def run_child_process(config: dict[str, Any], timeout_seconds: int) -> tuple[dict[str, Any], str]:
    result_path = Path(str(config["result_path"]))
    environment = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(config["pythonpath"]), CONFIG_ENV: json.dumps(config)}
    child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--child"], env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
    termination = "completed"
    try:
        child.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        termination = "sigterm"
        os.killpg(child.pid, signal.SIGTERM)
        try:
            child.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            termination = "sigkill"
            os.killpg(child.pid, signal.SIGKILL)
            child.communicate()
    if child.returncode != 0 or not result_path.is_file():
        raise RuntimeError(f"child failed:{child.returncode}:{termination}")
    return json.loads(result_path.read_text(encoding="utf-8")), termination


def invalid_payload(reason: str, cleanup: dict[str, Any] | None = None, database_name: str = "") -> dict[str, Any]:
    return {
        "valid": False,
        "invalid_reasons": [reason],
        "scope": "tiny synthetic fixture; plan evidence only, not production performance",
        "cleanup": cleanup or {"skipped": "not_started"},
        "database_name": database_name,
    }


def validity(counts: dict[str, Any], plans: list[dict[str, Any]], cleanup: dict[str, Any], termination: str) -> list[str]:
    reasons: list[str] = []
    names = [str(plan.get("name", "")) for plan in plans]
    expected = [item[0] for item in QUERY_SPECS]
    if names != expected or any(not isinstance(plan.get("plan"), list) or not plan["plan"] for plan in plans):
        reasons.append("missing_or_malformed_plan_set")
    for route in ("auth_me", "business_data"):
        value = counts.get(route)
        if not isinstance(value, dict) or value.get("all", 0) <= 0:
            reasons.append(f"missing_route_counts:{route}")
            continue
        if value.get("all") != sum(int(value.get(key, -1)) for key in ("read", "ddl_or_write", "other")):
            reasons.append(f"inconsistent_route_counts:{route}")
    if termination != "completed":
        reasons.append(f"child_termination:{termination}")
    if cleanup.get("removed") is not True:
        reasons.append("cleanup_not_confirmed")
    return reasons


def run(args: argparse.Namespace) -> dict[str, Any]:
    base_dsn = ""
    database_name = ""
    created = False
    cleanup: dict[str, Any] = {"database_name": database_name, "skipped": "not_started"}
    failure = ""
    counts: dict[str, Any] = {}
    plans: list[dict[str, Any]] = []
    termination = "not_started"
    try:
        base_dsn = readiness_journey_measure.guarded_dsn(os.environ.get(DEFAULT_DSN_ENV, ""))
        guard_first = os.environ.get("PYTHONPATH", "").split(os.pathsep)[0]
        guard_path = Path(guard_first) / "sitecustomize.py" if guard_first else Path()
        guard = loaded_guard(str(guard_path), hashlib.sha256(guard_path.read_bytes()).hexdigest())
        data_directory = data_directory_identity(base_dsn)
        database_name = OWNED_PREFIX + uuid.uuid4().hex
        cleanup = {"database_name": database_name, "skipped": "not_created_by_this_invocation"}
        database_url = create_owned_database(base_dsn, database_name)
        created = True
        readiness_journey_benchmark.migrate(database_url)
        target = readiness_journey_load.prepare_targets(database_url, 1)[0]
        result_path = Path(args.output).resolve().with_suffix(".child.json")
        child, termination = run_child_process({
            "database_url": database_url, "data_directory": data_directory, "guard_path": str(guard_path),
            "guard_sha256": guard["sha256"], "pythonpath": os.environ.get("PYTHONPATH", ""),
            "target": target, "result_path": str(result_path),
        }, 30)
        counts = child["query_counts"]
        plans = child["plans"]
    except Exception:
        failure = type(sys.exception()).__name__
    try:
        cleanup = cleanup_owned_database(base_dsn, database_name, created)
    except Exception:
        cleanup = {"database_name": database_name, "cleanup_error": type(sys.exception()).__name__}
    if failure:
        return invalid_payload(failure, cleanup, database_name)
    invalid_reasons = validity(counts, plans, cleanup, termination)
    return {
        "valid": not invalid_reasons,
        "invalid_reasons": invalid_reasons,
        "scope": "tiny synthetic fixture; plan evidence only, not production performance",
        "guard": guard,
        "query_counts": counts,
        "plans": plans,
        "cleanup": cleanup,
        "route_note": "observed counts distinguish reads from DDL/writes; the GET method alone does not establish read-only behavior",
        "representative_plan_note": "access SQL omits dynamic moderation/parser filters; source drift must be reviewed before interpretation",
        "child_termination": termination,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--child", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.child:
        try:
            config = json.loads(os.environ.get(CONFIG_ENV, ""))
            result_path = Path(str(config["result_path"]))
            result_path.write_text(json.dumps(child_run(config)), encoding="utf-8")
            return 0
        except Exception:
            return 1
    if not args.execute or args.output is None:
        raise SystemExit("requires --execute and --output")
    try:
        payload = run(args)
    except Exception:
        payload = invalid_payload(type(sys.exception()).__name__)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return 0 if payload["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
