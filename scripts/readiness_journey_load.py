#!/usr/bin/env python3
"""Bounded prepared authenticated dashboard read-load.

This is Flask test-client dispatch, not HTTP/server-capacity measurement. It
creates and seeds isolated synthetic tenants before timing, then measures a
real login once and repeated authenticated dashboard reads in killable child
processes. It never imports the application in the parent or calls providers.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import signal
import subprocess
import sys
import threading
import time
import uuid
from typing import Any

import psycopg2
from psycopg2 import sql

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
import readiness_journey_benchmark
import readiness_journey_measure


ROOT = SCRIPTS.parent
DEFAULT_DSN_ENV = readiness_journey_benchmark.DEFAULT_DSN_ENV
OWNED_PREFIX = "localos_readiness_load_"
CONFIG_ENV = "LOCALOS_READINESS_LOAD_CONFIG"
MAX_TARGETS = 8
MAX_REPETITIONS = 5
MAX_TIMEOUT_SECONDS = 60


@dataclass
class RequestSample:
    target: int
    step: str
    status_code: int | None
    duration_ms: float
    success: bool
    error: str | None = None


def exact_owned_name(name: str) -> bool:
    return bool(re.fullmatch(OWNED_PREFIX + r"[0-9a-f]{32}", name))


def validate_limits(target_count: int, repetitions: int, timeout_seconds: int) -> None:
    if not 2 <= target_count <= MAX_TARGETS:
        raise ValueError(f"targets must be 2..{MAX_TARGETS}")
    if not 1 <= repetitions <= MAX_REPETITIONS:
        raise ValueError(f"repetitions must be 1..{MAX_REPETITIONS}")
    if not 1 <= timeout_seconds <= MAX_TIMEOUT_SECONDS:
        raise ValueError(f"timeout must be 1..{MAX_TIMEOUT_SECONDS} seconds")


def validate_targets(value: object, target_count: int) -> list[dict[str, str]]:
    if not isinstance(value, list) or len(value) != target_count:
        raise ValueError("target count does not match prepared targets")
    targets: list[dict[str, str]] = []
    seen_users: set[str] = set()
    seen_businesses: set[str] = set()
    seen_services: set[str] = set()
    seen_emails: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("target is not an object")
        required = ("user_id", "business_id", "service_id", "email")
        if any(not isinstance(item.get(key), str) or not item[key] for key in required):
            raise ValueError("target lacks a required identity")
        target = {key: str(item[key]) for key in required}
        if (
            target["user_id"] in seen_users
            or target["business_id"] in seen_businesses
            or target["service_id"] in seen_services
            or target["email"] in seen_emails
        ):
            raise ValueError("prepared target identities must be distinct")
        seen_users.add(target["user_id"])
        seen_businesses.add(target["business_id"])
        seen_services.add(target["service_id"])
        seen_emails.add(target["email"])
        targets.append(target)
    return targets


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def guard_provenance(expected_path: str, expected_sha256: str) -> dict[str, str]:
    """Prove the configured guard was actually imported and has pinned bytes."""
    expected = Path(expected_path).resolve()
    loaded = sys.modules.get("sitecustomize")
    loaded_name = str(getattr(loaded, "__file__", "")) if loaded else ""
    if not expected.is_file() or not loaded_name:
        raise ValueError("requires an imported canonical sitecustomize guard")
    if Path(loaded_name).resolve() != expected:
        raise ValueError("loaded sitecustomize origin is not canonical guard")
    observed_sha256 = sha256_file(expected)
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256) or observed_sha256 != expected_sha256:
        raise ValueError("canonical guard hash mismatch")
    return {"path": str(expected), "sha256": observed_sha256}


def database_url_for(base_dsn: str, database_name: str) -> str:
    return readiness_journey_benchmark.database_url_for(base_dsn, database_name)


def database_absent(base_dsn: str, name: str) -> bool:
    if not exact_owned_name(name):
        raise ValueError("refusing a database outside the UUID-owned namespace")
    connection = psycopg2.connect(database_url_for(base_dsn, "postgres"), connect_timeout=5)
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,))
        return cursor.fetchone() is None
    finally:
        cursor.close()
        connection.close()


def create_owned_database(base_dsn: str, name: str) -> str:
    """Return only after CREATE succeeded; caller may then set its created flag."""
    if not database_absent(base_dsn, name):
        raise ValueError("planned load database already exists")
    connection = psycopg2.connect(database_url_for(base_dsn, "postgres"), connect_timeout=5)
    cursor = connection.cursor()
    try:
        connection.autocommit = True
        cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    finally:
        cursor.close()
        connection.close()
    return database_url_for(base_dsn, name)


def cleanup_owned_database(base_dsn: str, name: str, created: bool) -> dict[str, Any]:
    if not created:
        return {"database_name": name, "skipped": "not_created_by_this_invocation"}
    if not exact_owned_name(name):
        raise ValueError("refusing cleanup outside the UUID-owned namespace")
    connection = psycopg2.connect(database_url_for(base_dsn, "postgres"), connect_timeout=5)
    cursor = connection.cursor()
    try:
        connection.autocommit = True
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,))
        existed = bool(cursor.fetchone())
        if existed:
            cursor.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
        return {"database_name": name, "removed": existed}
    finally:
        cursor.close()
        connection.close()


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


def prepare_targets(database_url: str, target_count: int) -> list[dict[str, str]]:
    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))
    targets: list[dict[str, str]] = []
    for _ in range(target_count):
        user_id, business_id, service_id = readiness_journey_benchmark.seed_user_and_business(database_url)
        targets.append({
            "user_id": user_id,
            "business_id": business_id,
            "service_id": service_id,
            "email": f"{user_id}@benchmark.invalid",
        })
    return targets


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def summarize(samples: list[RequestSample]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for step in sorted({sample.step for sample in samples}):
        rows = [sample for sample in samples if sample.step == step]
        durations = [sample.duration_ms for sample in rows if sample.success]
        result[step] = {
            "request_count": len(rows),
            "success_count": len(durations),
            "error_count": len(rows) - len(durations),
            "p50_ms": percentile(durations, 0.50),
            "p95_ms": percentile(durations, 0.95),
            "p99_ms": percentile(durations, 0.99),
            "p99_note": "exploratory: fewer than 100 successes",
        }
    return result


def resource_snapshot() -> dict[str, float | str]:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return {
        "cpu_user_seconds": usage.ru_utime,
        "cpu_system_seconds": usage.ru_stime,
        "peak_rss": float(usage.ru_maxrss),
        "peak_rss_unit": "bytes_on_macos" if sys.platform == "darwin" else "kibibytes_on_linux",
    }


def pair_waves(targets: list[dict[str, str]]) -> list[list[dict[str, str]]]:
    return [targets[index:index + 2] for index in range(0, len(targets), 2)]


def identity_from_payload(payload: object) -> str:
    if not isinstance(payload, dict):
        return ""
    nested = payload.get("user")
    if isinstance(nested, dict):
        nested_id = nested.get("id") or nested.get("user_id")
        if nested_id is not None:
            return str(nested_id)
    value = payload.get("id") or payload.get("user_id")
    return str(value) if value is not None else ""


def response_json(response: Any) -> object:
    try:
        return response.get_json()
    except Exception:
        return None


def valid_business_payload(value: object, target: dict[str, str]) -> bool:
    if not isinstance(value, dict):
        return False
    business = value.get("business")
    services = value.get("services")
    if not isinstance(business, dict) or str(business.get("id", "")) != target["business_id"]:
        return False
    if not isinstance(services, list):
        return False
    service_ids: set[str] = set()
    for service in services:
        if not isinstance(service, dict) or not isinstance(service.get("id"), str):
            return False
        service_ids.add(service["id"])
    return service_ids == {target["service_id"]}


def request_sample(target: int, step: str, request: Any, valid: Any) -> tuple[RequestSample, Any]:
    started = time.perf_counter()
    try:
        response = request()
        payload = response_json(response)
        success = response.status_code == 200 and bool(valid(payload))
        error = None if success else "semantic_response_mismatch"
        return RequestSample(target, step, response.status_code, (time.perf_counter() - started) * 1000, success, error), payload
    except Exception:
        return RequestSample(target, step, None, (time.perf_counter() - started) * 1000, False, type(sys.exception()).__name__), None


def coverage_failures(samples: list[RequestSample], target_count: int, repetitions: int) -> list[RequestSample]:
    failures: list[RequestSample] = []
    expected = {"login": 1, "me": repetitions, "business_data": repetitions}
    for target in range(target_count):
        for step, count in expected.items():
            observed = len([sample for sample in samples if sample.target == target and sample.step == step])
            if observed != count:
                failures.append(RequestSample(target, "coverage", None, 0.0, False, f"{step}:expected={count}:observed={observed}"))
    return failures


def run_target(app: Any, target_index: int, target: dict[str, str], repetitions: int, barrier: threading.Barrier, timeout_seconds: int) -> list[RequestSample]:
    try:
        barrier.wait(timeout=timeout_seconds)
    except threading.BrokenBarrierError:
        return [RequestSample(target_index, "barrier", None, 0.0, False, "barrier_broken")]
    client = app.test_client()
    rows: list[RequestSample] = []
    login, payload = request_sample(
        target_index,
        "login",
        lambda: client.post("/api/auth/login", json={"email": target["email"], "password": "benchmark-password"}),
        lambda value: isinstance(value, dict) and isinstance(value.get("token"), str) and bool(value["token"]),
    )
    rows.append(login)
    token = payload.get("token") if isinstance(payload, dict) else ""
    headers = {"Authorization": f"Bearer {token}"}
    for _ in range(repetitions):
        me, _ = request_sample(
            target_index,
            "me",
            lambda: client.get("/api/auth/me", headers=headers),
            lambda value: identity_from_payload(value) == target["user_id"],
        )
        rows.append(me)
        business, _ = request_sample(
            target_index,
            "business_data",
            lambda: client.get(f"/api/business/{target['business_id']}/data", headers=headers),
            lambda value: valid_business_payload(value, target),
        )
        rows.append(business)
    return rows


def child_run(config: dict[str, Any]) -> tuple[list[RequestSample], dict[str, Any]]:
    """Validate before importing the app, then run only pairwise read waves."""
    database_url = readiness_journey_measure.guarded_dsn(str(config.get("database_url", "")))
    target_count = int(config.get("target_count", 0))
    repetitions = int(config.get("repetitions", 0))
    timeout_seconds = int(config.get("timeout_seconds", 0))
    validate_limits(target_count, repetitions, timeout_seconds)
    targets = validate_targets(config.get("targets"), target_count)
    guard_provenance(str(config.get("guard_path", "")), str(config.get("guard_sha256", "")))
    data_directory_identity(database_url, str(config.get("data_directory", "")))
    safe_environment(database_url, str(config.get("pythonpath", "")))
    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))
    from main import app

    before = resource_snapshot()
    rows: list[RequestSample] = []
    for offset, wave in enumerate(pair_waves(targets)):
        barrier = threading.Barrier(len(wave))
        executor = ThreadPoolExecutor(max_workers=len(wave))
        futures = []
        for wave_index, target in enumerate(wave):
            futures.append(executor.submit(run_target, app, offset * 2 + wave_index, target, repetitions, barrier, timeout_seconds))
        for future in futures:
            rows.extend(future.result())
        executor.shutdown(wait=True)
    rows.extend(coverage_failures(rows, target_count, repetitions))
    after = resource_snapshot()
    return rows, {"before_timed_phase": before, "after_timed_phase": after}


def safe_environment(database_url: str, pythonpath: str) -> None:
    preserved_path = os.environ.get("PATH", "")
    preserved_lang = os.environ.get("LANG", "C")
    os.environ.clear()
    os.environ.update({
        "DATABASE_URL": database_url,
        "LANG": preserved_lang,
        "NO_PROXY": "*",
        "PATH": preserved_path,
        "PYTHON_DOTENV_DISABLED": "1",
        "PYTHONPATH": pythonpath,
    })


def child_payload(config: dict[str, Any]) -> dict[str, Any]:
    rows, resources = child_run(config)
    return {"samples": [asdict(row) for row in rows], "resources": resources}


def run_child_process(config: dict[str, Any], timeout_seconds: int) -> tuple[list[RequestSample], dict[str, Any], str]:
    output = Path(str(config["result_path"]))
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(config.get("pythonpath", "")),
        CONFIG_ENV: json.dumps(config, sort_keys=True),
    }
    command = [sys.executable, str(Path(__file__).resolve()), "--child"]
    child = subprocess.Popen(command, env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
    termination = "completed"
    try:
        child.communicate(timeout=timeout_seconds + 5)
    except subprocess.TimeoutExpired:
        termination = "sigterm"
        os.killpg(child.pid, signal.SIGTERM)
        try:
            child.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            termination = "sigkill"
            os.killpg(child.pid, signal.SIGKILL)
            child.communicate()
    if child.returncode != 0 or not output.is_file():
        error = f"child_exit:{child.returncode}" if child.returncode is not None else "child_result_missing"
        return [RequestSample(-1, "child", None, 0.0, False, error)], {}, termination
    try:
        payload = json.loads(output.read_text(encoding="utf-8"))
        rows = [RequestSample(**item) for item in payload["samples"]]
        resources = payload["resources"]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return [RequestSample(-1, "child", None, 0.0, False, type(sys.exception()).__name__)], {}, termination
    return rows, resources, termination


def validity(samples: list[RequestSample], resources: dict[str, Any], cleanup: dict[str, Any], termination: str) -> list[str]:
    reasons: list[str] = []
    if termination != "completed":
        reasons.append(f"child_termination:{termination}")
    if not resources.get("before_timed_phase") or not resources.get("after_timed_phase"):
        reasons.append("missing_child_timed_resources")
    for sample in samples:
        if not sample.success:
            reasons.append(f"failed:{sample.target}:{sample.step}:{sample.error or sample.status_code}")
    if cleanup.get("removed") is not True:
        reasons.append(f"cleanup_not_confirmed:{cleanup.get('skipped', cleanup.get('removed'))}")
    return reasons


def parent_failure(reason: str, cleanup: dict[str, Any], database_name: str = "") -> dict[str, Any]:
    return {
        "valid": False,
        "invalid_reasons": [reason],
        "scope": "prepared authenticated dashboard read-load; not five-flow mutation stress or HTTP capacity",
        "transport": "in-process Flask test client; no provider calls",
        "samples": [],
        "summary": {},
        "child_resources": {},
        "cleanup": cleanup,
        "database_name": database_name,
    }


def parent_run(args: argparse.Namespace) -> dict[str, Any]:
    base_dsn = ""
    database_name = ""
    created = False
    cleanup: dict[str, Any] = {"skipped": "not_started"}
    samples: list[RequestSample] = []
    resources: dict[str, Any] = {}
    termination = "not_started"
    try:
        base_dsn = readiness_journey_measure.guarded_dsn(os.environ.get(DEFAULT_DSN_ENV, ""))
        validate_limits(args.targets, args.repetitions, args.timeout)
        pythonpath = os.environ.get("PYTHONPATH", "")
        guard_path = Path(pythonpath.split(os.pathsep)[0]) / "sitecustomize.py" if pythonpath else Path()
        if not guard_path.is_file():
            raise ValueError("PYTHONPATH must begin with canonical guard directory")
        data_directory = data_directory_identity(base_dsn)
        database_name = OWNED_PREFIX + uuid.uuid4().hex
        cleanup = {"database_name": database_name, "skipped": "not_created_by_this_invocation"}
        database_url = create_owned_database(base_dsn, database_name)
        created = True
        readiness_journey_benchmark.remove_external_provider_environment()
        readiness_journey_benchmark.migrate(database_url)
        targets = prepare_targets(database_url, args.targets)
        result_path = Path(args.output).resolve().with_suffix(".child.json")
        config = {
            "database_url": database_url,
            "data_directory": data_directory,
            "guard_path": str(guard_path.resolve()),
            "guard_sha256": sha256_file(guard_path),
            "pythonpath": pythonpath,
            "repetitions": args.repetitions,
            "result_path": str(result_path),
            "target_count": args.targets,
            "targets": targets,
            "timeout_seconds": args.timeout,
        }
        samples, resources, termination = run_child_process(config, args.timeout)
        samples.extend(coverage_failures(samples, args.targets, args.repetitions))
    except Exception:
        reason = type(sys.exception()).__name__
        if created and base_dsn and database_name:
            try:
                cleanup = cleanup_owned_database(base_dsn, database_name, True)
            except Exception:
                cleanup = {"database_name": database_name, "cleanup_error": type(sys.exception()).__name__}
        return parent_failure(reason, cleanup, database_name)
    try:
        cleanup = cleanup_owned_database(base_dsn, database_name, created)
    except Exception:
        cleanup = {"database_name": database_name, "cleanup_error": type(sys.exception()).__name__}
    invalid_reasons = validity(samples, resources, cleanup, termination)
    return {
        "valid": not invalid_reasons,
        "invalid_reasons": invalid_reasons,
        "scope": "prepared authenticated dashboard read-load; not five-flow mutation stress or HTTP capacity",
        "transport": "in-process Flask test client; no provider calls",
        "target_count": args.targets,
        "repetitions": args.repetitions,
        "termination": termination,
        "summary": summarize(samples),
        "samples": [asdict(row) for row in samples],
        "child_resources": resources,
        "cleanup": cleanup,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--child", action="store_true")
    parser.add_argument("--execute", action="store_true", help="required for parent database creation")
    parser.add_argument("--output", help="parent JSON evidence path")
    parser.add_argument("--targets", type=int, default=2)
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=30)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.child:
        try:
            config = json.loads(os.environ.get(CONFIG_ENV, ""))
            if not isinstance(config, dict) or not config.get("result_path"):
                raise ValueError("child config/result path is required")
            payload = child_payload(config)
            Path(str(config["result_path"])).write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
            return 0
        except Exception:
            return 1
    if not args.execute or not args.output:
        raise SystemExit("parent mode requires --execute and --output")
    output = Path(args.output)
    payload = parent_run(args)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return 0 if payload["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
