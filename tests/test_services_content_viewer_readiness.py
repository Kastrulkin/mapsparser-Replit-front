"""Native PostgreSQL proof that a viewer cannot change services or content plans."""

import hashlib
import json
import os
import re
import sys
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask
import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor
import pytest

from api import content_plans_api, services_api
from services import content_plan_service


TEST_DSN_ENV = "LOCALOS_VIEWER_MUTATION_TEST_DATABASE_URL"
GUARD_ENV = "LOCALOS_VIEWER_MUTATION_GUARD_SHA256"
TABLES = (
    "users",
    "businesses",
    "business_members",
    "network_members",
    "networks",
    "userservices",
    "service_catalog_compression_requests",
    "serviceregenerationjobs",
    "serviceregenerationjobitems",
    "contentplans",
    "contentplanitems",
    "ailearningevents",
)


def isolated_test_dsn() -> str:
    database_url = os.getenv(TEST_DSN_ENV, "")
    if not database_url:
        pytest.skip(f"{TEST_DSN_ENV} is required for native viewer mutation proof")
    if any(os.getenv(key) for key in ("PGHOSTADDR", "PGSERVICE", "PGSERVICEFILE", "PGOPTIONS")):
        raise RuntimeError("native viewer mutation proof refuses inherited libpq overrides")
    parsed = urlsplit(database_url)
    if (
        parsed.scheme not in {"postgresql", "postgres"}
        or parsed.hostname not in {"127.0.0.1", "::1"}
        or parsed.port != 35418
        or parsed.path != "/readiness_full_test_reviewed_20260918"
        or parsed.query
        or parsed.fragment
    ):
        raise RuntimeError("native viewer mutation proof requires the owned loopback readiness database")
    pythonpath = os.getenv("PYTHONPATH", "")
    guard_directory = pythonpath.split(os.pathsep)[0] if pythonpath else ""
    guard_path = Path(guard_directory) / "sitecustomize.py"
    loaded_guard = sys.modules.get("sitecustomize")
    expected_hash = os.getenv(GUARD_ENV, "")
    if (
        not guard_path.is_file()
        or loaded_guard is None
        or Path(str(getattr(loaded_guard, "__file__", ""))).resolve() != guard_path.resolve()
        or not re.fullmatch(r"[0-9a-f]{64}", expected_hash)
        or hashlib.sha256(guard_path.read_bytes()).hexdigest() != expected_hash
    ):
        raise RuntimeError("native viewer mutation proof requires the pinned guard-first sitecustomize")
    return database_url


class ScopedDatabaseManager:
    def __init__(self, database_url: str, schema: str):
        self.conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
        cursor = self.conn.cursor()
        try:
            cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
            self.conn.commit()
        finally:
            cursor.close()

    def close(self):
        self.conn.close()


@pytest.fixture
def viewer_mutation_database():
    database_url = isolated_test_dsn()
    schema = "viewer_mutation_" + uuid.uuid4().hex
    connection = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
    cursor = connection.cursor()
    try:
        cursor.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        for table_name in TABLES:
            cursor.execute(
                sql.SQL("CREATE TABLE {} (LIKE public.{} INCLUDING ALL)").format(
                    sql.Identifier(table_name),
                    sql.Identifier(table_name),
                )
            )
        ids = {key: str(uuid.uuid4()) for key in (
            "owner", "member", "viewer", "network_viewer", "revoked", "foreign", "business",
            "foreign_business", "network", "plan", "item", "source_service", "viewer_service", "compression_request",
        )}
        for user_key in ("owner", "member", "viewer", "network_viewer", "revoked", "foreign"):
            cursor.execute(
                "INSERT INTO users (id, email, is_superadmin) VALUES (%s, %s, FALSE)",
                (ids[user_key], f"{user_key}@viewer-rbac.invalid"),
            )
        cursor.execute(
            "INSERT INTO networks (id, owner_id, name) VALUES (%s, %s, 'Viewer proof network')",
            (ids["network"], ids["owner"]),
        )
        cursor.execute(
            "INSERT INTO businesses (id, owner_id, name, network_id, is_active) VALUES (%s, %s, 'Viewer proof', %s, TRUE)",
            (ids["business"], ids["owner"], ids["network"]),
        )
        cursor.execute(
            "INSERT INTO businesses (id, owner_id, name, is_active) VALUES (%s, %s, 'Foreign proof', TRUE)",
            (ids["foreign_business"], ids["foreign"]),
        )
        for actor, role, status in (("member", "member", "active"), ("viewer", "viewer", "active"), ("revoked", "viewer", "revoked")):
            cursor.execute(
                "INSERT INTO business_members (id, business_id, user_id, role, status) VALUES (%s, %s, %s, %s, %s)",
                (str(uuid.uuid4()), ids["business"], ids[actor], role, status),
            )
        cursor.execute(
            "INSERT INTO network_members (id, network_id, user_id, role, status) VALUES (%s, %s, %s, 'viewer', 'active')",
            (str(uuid.uuid4()), ids["network"], ids["network_viewer"]),
        )
        cursor.execute(
            """
            INSERT INTO userservices (id, user_id, business_id, category, name, description, keywords, price, is_active)
            VALUES (%s, %s, %s, 'Source', 'Source service', '', '[]'::jsonb, 100, TRUE)
            """,
            (ids["source_service"], ids["owner"], ids["business"]),
        )
        cursor.execute(
            """
            INSERT INTO userservices (id, user_id, business_id, category, name, description, keywords, price, is_active)
            VALUES (%s, %s, %s, 'Source', 'Viewer legacy service', '', '[]'::jsonb, 100, TRUE)
            """,
            (ids["viewer_service"], ids["viewer"], ids["business"]),
        )
        cursor.execute(
            """
            INSERT INTO contentplans (
                id, business_id, scope_type, title, period_days, period_start, period_end,
                plan_status, generation_mode, input_snapshot_json, created_by
            ) VALUES (%s, %s, 'single_business', 'Viewer mutation proof', 14, CURRENT_DATE,
                      CURRENT_DATE + 13, 'draft', 'journey', '{}'::jsonb, %s)
            """,
            (ids["plan"], ids["business"], ids["owner"]),
        )
        cursor.execute(
            """
            INSERT INTO contentplanitems (
                id, plan_id, business_id, scheduled_for, content_type, theme, goal,
                source_kind, source_ref, draft_text, status, metadata_json
            ) VALUES (%s, %s, %s, CURRENT_DATE, 'news', 'Viewer mutation proof', 'Proof role gate',
                      'e2e_fixture', 'viewer-mutation', 'Original draft', 'edited', '{}'::jsonb)
            """,
            (ids["item"], ids["plan"], ids["business"]),
        )
        connection.commit()
        yield {"database_url": database_url, "schema": schema, "ids": ids}
    finally:
        connection.rollback()
        cursor.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema)))
        connection.commit()
        cursor.close()
        connection.close()


def database_factory(viewer_mutation_database):
    return ScopedDatabaseManager(viewer_mutation_database["database_url"], viewer_mutation_database["schema"])


def response_status(result):
    if isinstance(result, tuple):
        return result[1]
    return result.status_code


def service_count(viewer_mutation_database, name: str) -> int:
    connection = psycopg2.connect(viewer_mutation_database["database_url"], cursor_factory=RealDictCursor)
    cursor = connection.cursor()
    try:
        cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(viewer_mutation_database["schema"])))
        cursor.execute("SELECT COUNT(*) FROM userservices WHERE name = %s", (name,))
        return int(cursor.fetchone()["count"])
    finally:
        cursor.close()
        connection.close()


def compression_request_count(viewer_mutation_database) -> int:
    connection = psycopg2.connect(viewer_mutation_database["database_url"], cursor_factory=RealDictCursor)
    cursor = connection.cursor()
    try:
        cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(viewer_mutation_database["schema"])))
        cursor.execute("SELECT COUNT(*) FROM service_catalog_compression_requests")
        return int(cursor.fetchone()["count"])
    finally:
        cursor.close()
        connection.close()


def compression_snapshot(viewer_mutation_database, request_id: str) -> dict:
    connection = psycopg2.connect(viewer_mutation_database["database_url"], cursor_factory=RealDictCursor)
    cursor = connection.cursor()
    try:
        cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(viewer_mutation_database["schema"])))
        cursor.execute(
            "SELECT status, groups_json FROM service_catalog_compression_requests WHERE id = %s",
            (request_id,),
        )
        request_row = cursor.fetchone()
        cursor.execute(
            "SELECT is_active FROM userservices WHERE id = %s",
            (viewer_mutation_database["ids"]["source_service"],),
        )
        source_row = cursor.fetchone()
        return {
            "status": request_row["status"],
            "groups": request_row["groups_json"],
            "source_active": source_row["is_active"],
        }
    finally:
        cursor.close()
        connection.close()


def content_text(viewer_mutation_database) -> str:
    connection = psycopg2.connect(viewer_mutation_database["database_url"], cursor_factory=RealDictCursor)
    cursor = connection.cursor()
    try:
        cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(viewer_mutation_database["schema"])))
        cursor.execute("SELECT draft_text FROM contentplanitems WHERE id = %s", (viewer_mutation_database["ids"]["item"],))
        return str(cursor.fetchone()["draft_text"])
    finally:
        cursor.close()
        connection.close()


def service_snapshot(viewer_mutation_database, service_id: str) -> dict:
    connection = psycopg2.connect(viewer_mutation_database["database_url"], cursor_factory=RealDictCursor)
    cursor = connection.cursor()
    try:
        cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(viewer_mutation_database["schema"])))
        cursor.execute(
            "SELECT name, keywords, is_active FROM userservices WHERE id = %s",
            (service_id,),
        )
        row = cursor.fetchone()
        return {"name": row["name"], "keywords": row["keywords"], "is_active": row["is_active"]}
    finally:
        cursor.close()
        connection.close()


def regeneration_job_count(viewer_mutation_database) -> int:
    connection = psycopg2.connect(viewer_mutation_database["database_url"], cursor_factory=RealDictCursor)
    cursor = connection.cursor()
    try:
        cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(viewer_mutation_database["schema"])))
        cursor.execute("SELECT COUNT(*) FROM serviceregenerationjobs")
        return int(cursor.fetchone()["count"])
    finally:
        cursor.close()
        connection.close()


@pytest.mark.parametrize(
    "actor_key, business_key, expected_status",
    (
        ("viewer", "business", 403),
        ("network_viewer", "business", 403),
        ("revoked", "business", 403),
        ("foreign", "business", 403),
        ("member", "business", 200),
        ("owner", "business", 200),
    ),
)
def test_service_add_uses_stored_write_role(viewer_mutation_database, monkeypatch, actor_key, business_key, expected_status):
    app = Flask(__name__)
    ids = viewer_mutation_database["ids"]
    monkeypatch.setattr(services_api, "DatabaseManager", lambda: database_factory(viewer_mutation_database))
    monkeypatch.setattr(services_api, "verify_session", lambda token: {"user_id": token, "is_superadmin": False})
    context = app.test_request_context(
        "/api/services/add",
        method="POST",
        headers={"Authorization": f"Bearer {ids[actor_key]}"},
        json={
            "business_id": ids[business_key],
            "category": "Test",
            "name": f"add-{actor_key}",
            "keywords": [],
            "price": 1,
        },
    )
    context.push()
    try:
        result = services_api.add_service()
    finally:
        context.pop()
    expected_count = 1 if expected_status == 200 else 0
    assert (
        response_status(result),
        service_count(viewer_mutation_database, f"add-{actor_key}"),
    ) == (expected_status, expected_count)


def test_service_compression_viewer_cannot_create_or_apply_a_draft(viewer_mutation_database, monkeypatch):
    app = Flask(__name__)
    ids = viewer_mutation_database["ids"]
    monkeypatch.setattr(services_api, "DatabaseManager", lambda: database_factory(viewer_mutation_database))
    monkeypatch.setattr(services_api, "verify_session", lambda token: {"user_id": token, "is_superadmin": False})
    context = app.test_request_context(
        "/api/services/compression/draft",
        method="POST",
        headers={"Authorization": f"Bearer {ids['viewer']}"},
        json={"business_id": ids["business"]},
    )
    context.push()
    try:
        draft_result = services_api.create_service_compression_draft()
    finally:
        context.pop()
    assert (response_status(draft_result), compression_request_count(viewer_mutation_database)) == (403, 0)

    connection = psycopg2.connect(viewer_mutation_database["database_url"], cursor_factory=RealDictCursor)
    cursor = connection.cursor()
    try:
        cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(viewer_mutation_database["schema"])))
        cursor.execute(
            """
            INSERT INTO service_catalog_compression_requests (
                id, business_id, user_id, status, before_count, after_count, groups_json, diff_json
            ) VALUES (%s, %s, %s, 'needs_review', 1, 1, %s::jsonb, '{}'::jsonb)
            """,
            (
                ids["compression_request"], ids["business"], ids["owner"],
                json.dumps([{
                    "id": "group-1",
                    "action": "apply",
                    "source_service_ids": [ids["source_service"]],
                    "target": {"category": "Replacement", "name": "Forbidden replacement", "description": "", "keywords": [], "price": 1},
                }]),
            ),
        )
        connection.commit()
    finally:
        cursor.close()
        connection.close()
    before_snapshot = compression_snapshot(viewer_mutation_database, ids["compression_request"])
    context = app.test_request_context(
        f"/api/services/compression/draft/{ids['compression_request']}/apply",
        method="POST",
        headers={"Authorization": f"Bearer {ids['viewer']}"},
    )
    context.push()
    try:
        apply_result = services_api.apply_service_compression_draft(ids["compression_request"])
    finally:
        context.pop()
    assert response_status(apply_result) == 403
    assert service_count(viewer_mutation_database, "Forbidden replacement") == 0
    assert compression_snapshot(viewer_mutation_database, ids["compression_request"]) == before_snapshot


@pytest.mark.parametrize(
    "operation, request_status",
    (
        ("update", "needs_review"),
        ("apply", "needs_review"),
        ("rollback", "applied"),
    ),
)
def test_service_compression_viewer_cannot_mutate_existing_draft(
    viewer_mutation_database,
    monkeypatch,
    operation,
    request_status,
):
    app = Flask(__name__)
    ids = viewer_mutation_database["ids"]
    monkeypatch.setattr(services_api, "DatabaseManager", lambda: database_factory(viewer_mutation_database))
    monkeypatch.setattr(services_api, "verify_session", lambda token: {"user_id": token, "is_superadmin": False})
    connection = psycopg2.connect(viewer_mutation_database["database_url"], cursor_factory=RealDictCursor)
    cursor = connection.cursor()
    try:
        cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(viewer_mutation_database["schema"])))
        cursor.execute(
            """
            INSERT INTO service_catalog_compression_requests (
                id, business_id, user_id, status, before_count, after_count, groups_json, diff_json,
                created_service_ids, archived_service_ids
            ) VALUES (%s, %s, %s, %s, 1, 1, %s::jsonb, '{}'::jsonb, '[]'::jsonb, %s::jsonb)
            """,
            (
                ids["compression_request"],
                ids["business"],
                ids["owner"],
                request_status,
                json.dumps([{
                    "id": "group-1",
                    "action": "apply",
                    "source_service_ids": [ids["source_service"]],
                    "target": {"category": "Replacement", "name": "Forbidden replacement", "description": "", "keywords": [], "price": 1},
                }]),
                json.dumps([ids["source_service"]]),
            ),
        )
        connection.commit()
    finally:
        cursor.close()
        connection.close()
    before_snapshot = compression_snapshot(viewer_mutation_database, ids["compression_request"])
    if operation == "update":
        method = "PUT"
        result_call = lambda: services_api.update_service_compression_draft(ids["compression_request"])
        payload = {"groups": []}
    elif operation == "apply":
        method = "POST"
        result_call = lambda: services_api.apply_service_compression_draft(ids["compression_request"])
        payload = None
    else:
        method = "POST"
        result_call = lambda: services_api.rollback_service_compression_draft(ids["compression_request"])
        payload = None
    context = app.test_request_context(
        f"/api/services/compression/draft/{ids['compression_request']}/{operation}",
        method=method,
        headers={"Authorization": f"Bearer {ids['viewer']}"},
        json=payload,
    )
    context.push()
    try:
        result = result_call()
    finally:
        context.pop()
    assert response_status(result) == 403
    assert compression_request_count(viewer_mutation_database) == 1
    assert compression_snapshot(viewer_mutation_database, ids["compression_request"]) == before_snapshot


@pytest.mark.parametrize("actor_key", ("viewer", "network_viewer"))
def test_viewer_cannot_start_service_write_workflows(viewer_mutation_database, monkeypatch, actor_key):
    app = Flask(__name__)
    ids = viewer_mutation_database["ids"]
    provider_calls = []
    monkeypatch.setattr(services_api, "DatabaseManager", lambda: database_factory(viewer_mutation_database))
    monkeypatch.setattr(services_api, "verify_session", lambda token: {"user_id": token, "is_superadmin": False})
    monkeypatch.setattr(
        services_api,
        "enrich_service_keywords_from_wordstat",
        lambda *_args, **_kwargs: provider_calls.append("wordstat") or {"status": "auto_found", "keywords": ["forbidden"]},
    )
    before_service = service_snapshot(viewer_mutation_database, ids["viewer_service"])
    before_jobs = regeneration_job_count(viewer_mutation_database)
    contexts = (
        (
            "/api/services/enrich-keywords",
            "POST",
            {"service_id": ids["viewer_service"]},
            services_api.enrich_service_keywords,
        ),
        (
            f"/api/services/update/{ids['viewer_service']}",
            "PUT",
            {"category": "Source", "name": "Forbidden edit", "keywords": [], "price": 1},
            lambda: services_api.update_service(ids["viewer_service"]),
        ),
        (
            f"/api/services/delete/{ids['viewer_service']}",
            "DELETE",
            None,
            lambda: services_api.delete_service(ids["viewer_service"]),
        ),
        (
            "/api/services/enrich-problematic-keywords",
            "POST",
            {"business_id": ids["business"]},
            services_api.enrich_problematic_service_keywords,
        ),
        (
            "/api/services/regenerate-problematic",
            "POST",
            {"business_id": ids["business"], "confirm": True},
            services_api.regenerate_problematic_services,
        ),
    )
    for path, method, payload, call_route in contexts:
        context = app.test_request_context(
            path,
            method=method,
            headers={"Authorization": f"Bearer {ids[actor_key]}"},
            json=payload,
        )
        context.push()
        try:
            result = call_route()
        finally:
            context.pop()
        assert response_status(result) == 403
    assert provider_calls == []
    assert service_snapshot(viewer_mutation_database, ids["viewer_service"]) == before_service
    assert regeneration_job_count(viewer_mutation_database) == before_jobs


@pytest.mark.parametrize("actor_key", ("member", "owner"))
def test_writer_can_enrich_and_update_service(viewer_mutation_database, monkeypatch, actor_key):
    app = Flask(__name__)
    ids = viewer_mutation_database["ids"]
    provider_calls = []
    monkeypatch.setattr(services_api, "DatabaseManager", lambda: database_factory(viewer_mutation_database))
    monkeypatch.setattr(services_api, "verify_session", lambda token: {"user_id": token, "is_superadmin": False})
    monkeypatch.setattr(
        services_api,
        "enrich_service_keywords_from_wordstat",
        lambda *_args, **_kwargs: provider_calls.append("wordstat") or {"status": "auto_found", "keywords": ["writer keyword"]},
    )
    context = app.test_request_context(
        "/api/services/enrich-keywords",
        method="POST",
        headers={"Authorization": f"Bearer {ids[actor_key]}"},
        json={"service_id": ids["source_service"]},
    )
    context.push()
    try:
        enrichment_result = services_api.enrich_service_keywords()
    finally:
        context.pop()
    assert response_status(enrichment_result) == 200
    assert provider_calls == ["wordstat"]
    assert service_snapshot(viewer_mutation_database, ids["source_service"])["keywords"] == ["writer keyword"]
    context = app.test_request_context(
        f"/api/services/update/{ids['source_service']}",
        method="PUT",
        headers={"Authorization": f"Bearer {ids[actor_key]}"},
        json={"category": "Source", "name": f"Updated by {actor_key}", "keywords": ["writer keyword"], "price": 1},
    )
    context.push()
    try:
        update_result = services_api.update_service(ids["source_service"])
    finally:
        context.pop()
    assert response_status(update_result) == 200
    assert service_snapshot(viewer_mutation_database, ids["source_service"])["name"] == f"Updated by {actor_key}"


@pytest.mark.parametrize(
    "actor_key, expected_status, expected_text",
    (
        ("viewer", 403, "Original draft"),
        ("network_viewer", 403, "Original draft"),
        ("revoked", 403, "Original draft"),
        ("foreign", 403, "Original draft"),
        ("member", 200, "Edited by member"),
        ("owner", 200, "Edited by owner"),
    ),
)
def test_content_item_update_uses_stored_write_role(viewer_mutation_database, monkeypatch, actor_key, expected_status, expected_text):
    app = Flask(__name__)
    ids = viewer_mutation_database["ids"]
    monkeypatch.setattr(content_plan_service, "DatabaseManager", lambda: database_factory(viewer_mutation_database))
    monkeypatch.setattr(content_plans_api, "verify_session", lambda token: {"user_id": token, "is_superadmin": False})
    context = app.test_request_context(
        f"/api/content-plans/items/{ids['item']}",
        method="PUT",
        headers={"Authorization": f"Bearer {ids[actor_key]}"},
        json={"draft_text": f"Edited by {actor_key}"},
    )
    context.push()
    try:
        result = content_plans_api.content_plan_item_update(ids["item"])
    finally:
        context.pop()
    assert response_status(result) == expected_status
    assert content_text(viewer_mutation_database) == expected_text
