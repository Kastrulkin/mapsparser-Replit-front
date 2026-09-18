#!/usr/bin/env python3
"""Run bounded, local-only API journey measurements against a disposable DB.

This is intentionally a *measurement harness*, rather than a performance claim.
It creates one database whose name it owns, applies the real Alembic history,
uses Flask's real request dispatch and records every status/error.  A failed
journey remains a failed sample in the JSON output; it is never converted into
a successful timing value.

External text generation is not enabled by this program.  The Operator
refocus proposal receives a deterministic planner response at the provider
boundary; its route, approval journal, confirmation and SQL mutation remain
real.  Missing fixtures, schema gaps and authorization failures are recorded
truthfully.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qsl, urlsplit, urlunsplit

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import parse_dsn


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DSN_ENV = "LOCALOS_READINESS_JOURNEY_DATABASE_URL"
OWNED_DATABASE_PREFIX = "localos_readiness_benchmark_"


@dataclass
class StepSample:
    journey: str
    step: str
    kind: str
    status_code: int | None
    duration_ms: float | None
    success: bool
    error: str | None = None


REQUIRED_STEPS = {
    "auth_tenant": {"login", "me", "business"},
    "service_compression": {"draft", "review", "apply", "apply_replay", "apply_invariants"},
    "finance_import": {"preview", "apply"},
    "content": {"plan", "draft", "internal_news"},
    "operator": {"propose_refocus", "confirm", "confirm_replay", "confirm_invariants", "foreign_plan_untouched"},
}


def guarded_dsn(database_url: str) -> str:
    """Reject any DSN that is not an explicit disposable loopback test DB."""
    if os.getenv("PGHOSTADDR") or os.getenv("PGSERVICE") or os.getenv("PGSERVICEFILE") or os.getenv("PGOPTIONS"):
        raise ValueError("refusing inherited libpq service or host override")
    parsed_url = urlsplit(database_url)
    unsafe_query_keys = {"host", "hostaddr", "service", "servicefile", "port", "dbname"}
    if any(key.lower() in unsafe_query_keys for key, _value in parse_qsl(parsed_url.query, keep_blank_values=True)):
        raise ValueError("refusing DSN query overrides for database identity")
    params = parse_dsn(database_url)
    database_name = str(params.get("dbname") or "").lower()
    host = str(params.get("host") or "")
    port = str(params.get("port") or "")
    if (
        host not in {"127.0.0.1", "::1"}
        or not port.isdigit()
        or int(port) < 32768
        or "readiness" not in database_name
        or params.get("hostaddr")
        or params.get("service")
    ):
        raise ValueError("requires an explicit loopback readiness database on a high port")
    return database_url


def database_url_for(database_url: str, name: str) -> str:
    parts = urlsplit(database_url.replace("postgresql+psycopg2://", "postgresql://", 1))
    return urlunsplit((parts.scheme, parts.netloc, f"/{name}", parts.query, parts.fragment))


def migrate(database_url: str) -> None:
    environment = {"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", "")}
    inherited_pythonpath = os.environ.get("PYTHONPATH", "")
    python_paths = [path for path in inherited_pythonpath.split(os.pathsep) if path]
    python_paths.extend((str(ROOT / "src"), str(ROOT)))
    environment.update(
        {
            "DATABASE_URL": database_url,
            "FLASK_APP": "src.main:app",
            # Keep the caller's guard-first sitecustomize path intact.  It is
            # the network boundary for this local test process.
            "PYTHONPATH": os.pathsep.join(dict.fromkeys(python_paths)),
            "PYTHON_DOTENV_DISABLED": "1",
            "NO_PROXY": "*",
        }
    )
    completed = subprocess.run(
        [sys.executable, "-m", "flask", "db", "upgrade"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    if completed.returncode:
        detail = (completed.stderr or completed.stdout).strip()[-2000:]
        raise RuntimeError(f"migration failed: {detail}")


def create_owned_database(base_dsn: str) -> tuple[str, str]:
    name = OWNED_DATABASE_PREFIX + uuid.uuid4().hex
    admin_dsn = database_url_for(base_dsn, "postgres")
    connection = psycopg2.connect(admin_dsn)
    cursor = connection.cursor()
    try:
        connection.autocommit = True
        cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    finally:
        cursor.close()
        connection.close()
    return name, database_url_for(base_dsn, name)


def drop_owned_database(base_dsn: str, name: str) -> None:
    if not name.startswith(OWNED_DATABASE_PREFIX):
        raise ValueError("refusing to drop a database not owned by this harness")
    connection = psycopg2.connect(database_url_for(base_dsn, "postgres"))
    cursor = connection.cursor()
    try:
        connection.autocommit = True
        cursor.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))
    finally:
        cursor.close()
        connection.close()


def seed_user_and_business(database_url: str) -> tuple[str, str, str]:
    """Seed only the owner and one business required by the public API routes."""
    from auth_system import hash_password

    user_id, business_id, service_id = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    connection = psycopg2.connect(database_url)
    cursor = connection.cursor()
    try:
        cursor.execute(
                """
                INSERT INTO users (id, email, password_hash, is_active, is_verified, is_superadmin)
                VALUES (%s, %s, %s, TRUE, TRUE, FALSE)
                """,
                (user_id, f"{user_id}@benchmark.invalid", hash_password("benchmark-password")),
        )
        cursor.execute(
                """
                INSERT INTO businesses (
                    id, owner_id, name, entity_group, subscription_tier, subscription_status
                )
                VALUES (%s, %s, 'Readiness benchmark', 'client', 'concierge', 'active')
                """,
                (business_id, user_id),
        )
        cursor.execute(
                """
                INSERT INTO userservices (id, user_id, business_id, category, name, description, keywords, price, is_active)
                VALUES (%s, %s, %s, 'hair', 'Стрижка', 'Тестовая услуга', '[]'::jsonb, '1000', TRUE)
                """,
                (service_id, user_id, business_id),
        )
        connection.commit()
    finally:
        cursor.close()
        connection.close()
    return user_id, business_id, service_id


def seed_foreign_content_item(database_url: str, period_start: str, period_end: str) -> tuple[str, str]:
    """Create a foreign plan/item so a scoped refocus can prove non-mutation."""
    foreign_user, foreign_business = str(uuid.uuid4()), str(uuid.uuid4())
    foreign_plan, foreign_item = str(uuid.uuid4()), str(uuid.uuid4())
    connection = psycopg2.connect(database_url)
    cursor = connection.cursor()
    try:
        cursor.execute(
                "INSERT INTO users (id, email, is_active, is_verified) VALUES (%s, %s, TRUE, TRUE)",
                (foreign_user, f"{foreign_user}@benchmark.invalid"),
        )
        cursor.execute(
                "INSERT INTO businesses (id, owner_id, name, entity_group) VALUES (%s, %s, 'Foreign benchmark', 'client')",
                (foreign_business, foreign_user),
        )
        cursor.execute(
                """
                INSERT INTO contentplans (
                    id, business_id, title, period_days, period_start, period_end, plan_status, generated_plan_json
                )
                VALUES (%s, %s, 'Foreign plan', 30, %s, %s, 'generated', '{}'::jsonb)
                """,
                (foreign_plan, foreign_business, period_start, period_end),
        )
        cursor.execute(
                """
                INSERT INTO contentplanitems (id, plan_id, business_id, theme, goal, scheduled_for, status, metadata_json)
                VALUES (%s, %s, %s, 'Чужая тема', 'Не менять', %s, 'planned', '{}'::jsonb)
                """,
                (foreign_item, foreign_plan, foreign_business, period_start),
        )
        connection.commit()
    finally:
        cursor.close()
        connection.close()
    return foreign_business, foreign_item


def remove_external_provider_environment() -> None:
    """Replace inherited configuration with the local harness allowlist."""
    allowed = {"PATH", "HOME", "PYTHONPATH", "TMPDIR", "LANG", "LC_ALL", "LC_CTYPE"}
    safe_environment = {key: value for key, value in os.environ.items() if key in allowed}
    os.environ.clear()
    os.environ.update(safe_environment)
    os.environ["PYTHON_DOTENV_DISABLED"] = "1"
    os.environ["BROWSER_COOKIE_AUTH_ENABLED"] = "false"


def sitecustomize_provenance(pythonpath: str) -> dict[str, str] | None:
    for entry in pythonpath.split(os.pathsep):
        candidate = Path(entry) / "sitecustomize.py"
        if candidate.is_file():
            return {
                "path": str(candidate),
                "sha256": hashlib.sha256(candidate.read_bytes()).hexdigest(),
            }
    return None


def record(
    samples: list[StepSample],
    journey: str,
    step: str,
    request: Callable[[], Any],
    expected: set[int],
    response_validator: Callable[[Any], bool] | None = None,
) -> Any:
    started = time.perf_counter()
    try:
        response = request()
        duration_ms = (time.perf_counter() - started) * 1000
        status_code = int(response.status_code)
        success = status_code in expected and (response_validator(response) if response_validator else True)
        samples.append(StepSample(journey, step, "request", status_code, duration_ms, success))
        return response
    except Exception:  # A benchmark must retain, rather than hide, a route failure.
        samples.append(StepSample(journey, step, "request", None, (time.perf_counter() - started) * 1000, False, type(sys.exception()).__name__))
        return None


def verify_required_coverage(samples: list[StepSample]) -> None:
    recorded = {(sample.journey, sample.step) for sample in samples}
    for journey, required_steps in REQUIRED_STEPS.items():
        for step in sorted(required_steps):
            if (journey, step) not in recorded:
                samples.append(
                    StepSample(journey, step, "coverage", None, None, False, "required_step_not_executed")
                )


def run_samples(database_url: str) -> list[StepSample]:
    """Execute one real Flask-dispatch sample per bounded journey.

    The request sequence intentionally stops after a failed prerequisite.  This
    prevents a broken draft from being mistaken for a completed apply/publish.
    """
    os.environ["DATABASE_URL"] = database_url
    os.environ["PYTHON_DOTENV_DISABLED"] = "1"
    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))
    from main import app

    user_id, business_id, service_id = seed_user_and_business(database_url)
    email = f"{user_id}@benchmark.invalid"
    client = app.test_client()
    samples: list[StepSample] = []
    login_response = record(
        samples, "auth_tenant", "login", lambda: client.post(
            "/api/auth/login", json={"email": email, "password": "benchmark-password"}
        ), {200}
    )
    token = (login_response.get_json() or {}).get("token") if login_response else None
    if not token:
        raise RuntimeError("real benchmark login did not return a bearer token")
    headers = {"Authorization": f"Bearer {token}"}

    record(samples, "auth_tenant", "me", lambda: client.get("/api/auth/me", headers=headers), {200})
    record(samples, "auth_tenant", "business", lambda: client.get(f"/api/business/{business_id}/data", headers=headers), {200})

    draft = record(samples, "service_compression", "draft", lambda: client.post("/api/services/compression/draft", headers=headers, json={"business_id": business_id}), {200})
    draft_id = (draft.get_json() or {}).get("draft", {}).get("id") if draft and draft.status_code == 200 else None
    if draft_id:
        groups = [
            {
                "id": "benchmark-group",
                "action": "apply",
                "source_service_ids": [service_id],
                "target": {
                    "category": "hair",
                    "name": "Стрижка: benchmark group",
                    "description": "Тестовый результат сжатия",
                    "keywords": [],
                    "price": "1000",
                },
            }
        ]
        record(
            samples,
            "service_compression",
            "review",
            lambda: client.put(
                f"/api/services/compression/draft/{draft_id}", headers=headers, json={"groups": groups}
            ),
            {200},
        )
        applied = record(samples, "service_compression", "apply", lambda: client.post(f"/api/services/compression/draft/{draft_id}/apply", headers=headers), {200})
        replay = record(samples, "service_compression", "apply_replay", lambda: client.post(f"/api/services/compression/draft/{draft_id}/apply", headers=headers), {200})
        replay_payload = replay.get_json() or {} if replay else {}
        samples.append(
            StepSample(
                "service_compression",
                "apply_invariants",
                "invariant",
                200 if applied and replay_payload.get("already_applied") is True else None,
                None,
                bool(applied and replay_payload.get("already_applied") is True),
                None if applied and replay_payload.get("already_applied") is True else "replayed apply was not idempotent",
            )
        )

    csv_bytes = b"date,type,category,amount\n2026-09-18,revenue,sales,1000\nbad,revenue,sales,nope\n"
    multipart = {"business_id": business_id, "file": (io.BytesIO(csv_bytes), "benchmark.csv")}
    record(samples, "finance_import", "preview", lambda: client.post("/api/finance/import-preview", headers=headers, data=multipart, content_type="multipart/form-data"), {200})
    multipart = {"business_id": business_id, "file": (io.BytesIO(csv_bytes), "benchmark.csv")}
    record(samples, "finance_import", "apply", lambda: client.post("/api/finance/import-file", headers=headers, data=multipart, content_type="multipart/form-data"), {200})

    plan = record(samples, "content", "plan", lambda: client.post("/api/content-plans/generate", headers=headers, json={"business_id": business_id, "period_days": 30, "density": "light", "content_mix": {"services": True}}), {200})
    items = ((plan.get_json() or {}).get("plan") or {}).get("items") if plan and plan.status_code == 200 else []
    plan_id = str(((plan.get_json() or {}).get("plan") or {}).get("id") or "") if plan else ""

    # This is a deterministic stand-in for an external planner only.  It does
    # not replace the Operator's approval, persistence or execution code.
    if plan_id:
        from unittest.mock import patch
        from database_manager import DatabaseManager
        from services import operator_core, operator_editorial
        from api import operator_api

        database = DatabaseManager()
        try:
            cursor = database.conn.cursor()
            current_items = operator_editorial._items(cursor, business_id, plan_id)
            cursor.execute("SELECT period_start, period_end FROM contentplans WHERE id = %s", (plan_id,))
            period = cursor.fetchone() or {}
            period_start = str(period.get("period_start") if hasattr(period, "get") else period[0])
            period_end = str(period.get("period_end") if hasattr(period, "get") else period[1])
        finally:
            database.close()
        if current_items and len(current_items) <= 20:
            _foreign_business, foreign_item = seed_foreign_content_item(database_url, period_start, period_end)
            changes = [
                {
                    "item_id": item["id"],
                    "version": operator_editorial._version(item),
                    "theme": f"Семейная поездка {index + 1}",
                }
                for index, item in enumerate(current_items)
            ]

            def planner(_state: dict[str, Any]) -> dict[str, Any]:
                return {
                    "action": "tool_call",
                    "tool": "content.refocus_plan",
                    "arguments": {
                        "plan_id": plan_id,
                        "focus": "акцент на семейных поездках",
                        "period_start": period_start,
                        "period_end": period_end,
                        "changes": changes,
                    },
                }

            def deterministic_router(cursor: Any, **kwargs: Any) -> tuple[dict[str, Any], dict[str, Any]]:
                return operator_core.route_operator_message(cursor, tool_planner=planner, **kwargs)

            with patch.object(operator_api, "route_operator_message", deterministic_router):
                proposal = record(
                    samples,
                    "operator",
                    "propose_refocus",
                    lambda: client.post(
                        "/api/operator/chat",
                        headers=headers,
                        json={
                            "business_id": business_id,
                            "message": "В этом месяце акцент на семейных поездках",
                            "request_id": "readiness-refocus-1",
                        },
                    ),
                    {200},
                )
            proposal_result = ((proposal.get_json() or {}).get("operator_result") or {}) if proposal else {}
            action_id = str(((proposal_result.get("approval") or {}).get("action_id") or ""))
            if action_id:
                confirmed = record(samples, "operator", "confirm", lambda: client.post(f"/api/operator/actions/{action_id}/confirm", headers=headers, json={"business_id": business_id}), {200})
                replay = record(samples, "operator", "confirm_replay", lambda: client.post(f"/api/operator/actions/{action_id}/confirm", headers=headers, json={"business_id": business_id}), {200})
                confirmed_result = ((confirmed.get_json() or {}).get("operator_result") or {}) if confirmed else {}
                replay_payload = replay.get_json() or {} if replay else {}
                expected_changes = len(changes)
                success = (
                    confirmed_result.get("changed_count") == expected_changes
                    and replay_payload.get("idempotent") is True
                )
                samples.append(
                    StepSample(
                        "operator",
                        "confirm_invariants",
                        "invariant",
                        200 if success else None,
                        None,
                        success,
                        None if success else "confirmation was not an idempotent full refocus",
                    )
                )
                connection = psycopg2.connect(database_url)
                cursor = connection.cursor()
                try:
                    cursor.execute("SELECT theme FROM contentplanitems WHERE id = %s", (foreign_item,))
                    foreign_row = cursor.fetchone()
                finally:
                    cursor.close()
                    connection.close()
                foreign_untouched = bool(foreign_row and foreign_row[0] == "Чужая тема")
                samples.append(
                    StepSample(
                        "operator",
                        "foreign_plan_untouched",
                        "invariant",
                        200 if foreign_untouched else None,
                        None,
                        foreign_untouched,
                        None if foreign_untouched else "refocus changed foreign content",
                    )
                )
            else:
                samples.append(StepSample("operator", "confirm", "coverage", None, None, False, "approval_action_not_returned"))
        else:
            samples.append(StepSample("operator", "propose_refocus", "coverage", None, None, False, "plan_fixture_not_eligible"))
    if items:
        item_id = str(items[0].get("id") or "")
        if item_id:
            from services import content_plan_service
            from unittest.mock import patch

            def deterministic_content_provider(*_arguments: Any, **_keywords: Any) -> str:
                return "Стрижка помогает сохранить аккуратную форму. Запишитесь через карточку бизнеса."

            def draft_generated(response: Any) -> bool:
                payload = response.get_json() or {}
                generation = payload.get("generation") or {}
                return bool(payload.get("success") and generation.get("success") is True)

            with patch.object(content_plan_service, "analyze_text_with_gigachat", deterministic_content_provider):
                record(
                    samples,
                    "content",
                    "draft",
                    lambda: client.post(
                        f"/api/content-plans/items/{item_id}/generate-draft", headers=headers, json={}
                    ),
                    {200},
                    draft_generated,
                )
            record(
                samples,
                "content",
                "internal_news",
                lambda: client.post(f"/api/content-plans/items/{item_id}/create-news", headers=headers, json={}),
                {200},
                lambda response: bool((response.get_json() or {}).get("success")),
            )
    else:
        samples.append(StepSample("content", "draft", "coverage", None, None, False, "plan_item_not_returned"))

    verify_required_coverage(samples)

    return samples


def write_result(
    destination: Path,
    database_name: str,
    samples: list[StepSample],
    guard: dict[str, str] | None = None,
) -> None:
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    dirty = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    payload = {
        "sample_type": "mixed_request_and_invariant_samples",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "database_name": database_name,
        "provider_seams": ["content_text_generation", "operator_planner"],
        "invocation": list(sys.argv),
        "environment": {"PYTHON_DOTENV_DISABLED": "1", "BROWSER_COOKIE_AUTH_ENABLED": "false"},
        "guard": guard,
        "commit": revision.stdout.strip() if revision.returncode == 0 else None,
        "worktree_dirty": bool(dirty.stdout.strip()) if dirty.returncode == 0 else None,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "samples": [asdict(sample) for sample in samples],
        "successful_steps": sum(sample.success for sample in samples),
        "failed_steps": sum(not sample.success for sample in samples),
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.getenv(DEFAULT_DSN_ENV, ""))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--keep-database", action="store_true")
    args = parser.parse_args()
    base_dsn = guarded_dsn(args.database_url)
    guard = sitecustomize_provenance(os.environ.get("PYTHONPATH", ""))
    if guard is None:
        raise ValueError("readiness journey benchmark requires a guard-first sitecustomize.py path")
    remove_external_provider_environment()
    database_name, database_url = create_owned_database(base_dsn)
    samples: list[StepSample] = []
    try:
        migrate(database_url)
        samples = run_samples(database_url)
        write_result(args.output, database_name, samples, guard)
        return 0 if samples and all(sample.success for sample in samples) else 1
    finally:
        if not args.keep_database:
            drop_owned_database(base_dsn, database_name)


if __name__ == "__main__":
    raise SystemExit(main())
