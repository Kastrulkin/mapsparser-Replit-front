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

from api import content_plans_api, operator_api, services_api
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


def is_owned_readiness_database(parsed):
    legacy = parsed.path == "/readiness_full_test_reviewed_20260918"
    fresh = re.fullmatch(r"/readiness_full_test_[0-9a-f]{8}_[0-9a-f]{12}", parsed.path)
    return (
        parsed.scheme in {"postgresql", "postgres"}
        and parsed.hostname in {"127.0.0.1", "::1"}
        and parsed.port == 35418
        and (legacy or fresh)
        and not parsed.query
        and not parsed.fragment
    )


def isolated_test_dsn() -> str:
    database_url = os.getenv(TEST_DSN_ENV, "")
    if not database_url:
        pytest.skip(f"{TEST_DSN_ENV} is required for native viewer mutation proof")
    if any(os.getenv(key) for key in ("PGHOSTADDR", "PGSERVICE", "PGSERVICEFILE", "PGOPTIONS")):
        raise RuntimeError("native viewer mutation proof refuses inherited libpq overrides")
    parsed = urlsplit(database_url)
    if not is_owned_readiness_database(parsed):
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
            "owner", "member", "member_all_locations", "member_viewer_location_b", "network_member",
            "root_viewer_location_b_member", "location_b_only_member", "viewer", "network_viewer", "revoked",
            "foreign", "superadmin", "business", "location_b",
            "foreign_business", "network", "plan", "item", "source_service", "viewer_service", "compression_request",
        )}
        for user_key in (
            "owner", "member", "member_all_locations", "member_viewer_location_b", "network_member",
            "root_viewer_location_b_member", "location_b_only_member", "viewer", "network_viewer", "revoked",
            "foreign", "superadmin",
        ):
            cursor.execute(
                "INSERT INTO users (id, email, is_superadmin) VALUES (%s, %s, %s)",
                (ids[user_key], f"{user_key}@viewer-rbac.invalid", user_key == "superadmin"),
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
            "INSERT INTO businesses (id, owner_id, name, network_id, is_active) VALUES (%s, %s, 'Viewer proof parent', %s, TRUE)",
            (ids["network"], ids["owner"], ids["network"]),
        )
        cursor.execute(
            "INSERT INTO businesses (id, owner_id, name, is_active) VALUES (%s, %s, 'Foreign proof', TRUE)",
            (ids["foreign_business"], ids["foreign"]),
        )
        cursor.execute(
            "INSERT INTO businesses (id, owner_id, name, network_id, is_active) VALUES (%s, %s, 'Viewer proof location B', %s, TRUE)",
            (ids["location_b"], ids["foreign"], ids["network"]),
        )
        for actor, role, status in (
            ("member", "member", "active"),
            ("member_all_locations", "member", "active"),
            ("member_viewer_location_b", "member", "active"),
            ("root_viewer_location_b_member", "viewer", "active"),
            ("viewer", "viewer", "active"),
            ("revoked", "viewer", "revoked"),
        ):
            cursor.execute(
                "INSERT INTO business_members (id, business_id, user_id, role, status) VALUES (%s, %s, %s, %s, %s)",
                (str(uuid.uuid4()), ids["business"], ids[actor], role, status),
            )
        for actor, target_id, role in (
            ("member_all_locations", ids["location_b"], "member"),
            ("member_all_locations", ids["network"], "member"),
            ("member_viewer_location_b", ids["location_b"], "viewer"),
            ("root_viewer_location_b_member", ids["location_b"], "member"),
            ("location_b_only_member", ids["location_b"], "member"),
        ):
            cursor.execute(
                "INSERT INTO business_members (id, business_id, user_id, role, status) VALUES (%s, %s, %s, %s, 'active')",
                (str(uuid.uuid4()), target_id, ids[actor], role),
            )
        cursor.execute(
            "INSERT INTO network_members (id, network_id, user_id, role, status) VALUES (%s, %s, %s, 'viewer', 'active')",
            (str(uuid.uuid4()), ids["network"], ids["network_viewer"]),
        )
        cursor.execute(
            "INSERT INTO network_members (id, network_id, user_id, role, status) VALUES (%s, %s, %s, 'member', 'active')",
            (str(uuid.uuid4()), ids["network"], ids["network_member"]),
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


def content_generation_snapshot(viewer_mutation_database) -> dict[str, list[dict]]:
    """Return every mutable row touched by content-plan generation.

    The proof deliberately compares complete rows, rather than just counts, so a
    denied generation cannot create an audit event or change an existing plan
    while still appearing harmless in the UI.
    """
    connection = psycopg2.connect(viewer_mutation_database["database_url"], cursor_factory=RealDictCursor)
    cursor = connection.cursor()
    try:
        cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(viewer_mutation_database["schema"])))
        snapshots = {}
        for table_name in ("contentplans", "contentplanitems", "ailearningevents"):
            cursor.execute(
                sql.SQL("SELECT to_jsonb(source) AS row FROM (SELECT * FROM {} ORDER BY id) AS source").format(
                    sql.Identifier(table_name)
                )
            )
            snapshots[table_name] = [row["row"] for row in cursor.fetchall()]
        return snapshots
    finally:
        cursor.close()
        connection.close()


def install_content_generation_dependencies(monkeypatch, viewer_mutation_database, *, use_real_scope_resolution=False):
    """Keep the real stored-role check while making generation deterministic.

    ``load_plan_context_for_business`` remains unmocked: it reads the cloned
    PostgreSQL memberships and calls the production read boundary.  Only
    unrelated context inputs and skeleton selection are fixed for this test.
    """
    ids = viewer_mutation_database["ids"]
    monkeypatch.setattr(content_plan_service, "DatabaseManager", lambda: database_factory(viewer_mutation_database))
    monkeypatch.setattr(content_plan_service, "ensure_content_plan_tables", lambda _cursor: None)
    monkeypatch.setattr(content_plan_service, "get_allowed_content_plan_horizons", lambda _business_id: [30])
    monkeypatch.setattr(
        content_plan_service,
        "get_subscription_access",
        lambda _business_id: {
            "tier": "maps",
            "status": "active",
            "capabilities": ["maps.news"],
            "automation_access": False,
            "reason": None,
        },
    )
    if not use_real_scope_resolution:
        monkeypatch.setattr(
            content_plan_service,
            "_fetch_network_scope_options",
            lambda _cursor, business_row: [
                {
                    "scope_type": "single_business",
                    "scope_target_id": str(business_row["id"]),
                    "label": str(business_row["name"]),
                    "city": "",
                    "address": "",
                    "is_current": True,
                }
            ],
        )
        monkeypatch.setattr(content_plan_service, "_build_scope_business_context", lambda _cursor, business_row, _scope_type, _target_id: business_row)
        monkeypatch.setattr(content_plan_service, "_scope_context_business_ids", lambda _cursor, business_row, _scope_type, _target_id: [str(business_row["id"])])
    monkeypatch.setattr(content_plan_service, "_fetch_map_link_count_for_businesses", lambda _cursor, _business_ids: 0)
    monkeypatch.setattr(content_plan_service, "_fetch_services_for_businesses", lambda _cursor, _business_ids: [])
    monkeypatch.setattr(content_plan_service, "_fetch_custom_seo_keywords_for_businesses", lambda _cursor, _business_ids: [])
    monkeypatch.setattr(content_plan_service, "_fetch_seo_keywords_isolated", lambda _user_id, _business_id: [])
    monkeypatch.setattr(content_plan_service, "_fetch_sales_signals_for_businesses", lambda _cursor, _user_id, _business_ids: [])
    monkeypatch.setattr(content_plan_service, "_fetch_recent_news_for_businesses", lambda _cursor, _user_id, _business_ids: [])
    monkeypatch.setattr(content_plan_service, "_fetch_audit_signals", lambda _business_id: [])
    monkeypatch.setattr(content_plan_service, "_load_content_plan_learning_feedback", lambda _cursor, _business_id: {})
    monkeypatch.setattr(
        content_plan_service,
        "build_content_plan_skeleton",
        lambda _context, **_kwargs: {
            "title": "RBAC deterministic plan",
            "period_start": "2026-09-10",
            "period_end": "2026-10-09",
            "meta": {},
            "items": [
                {
                    "scheduled_for": "2026-09-10",
                    "content_type": "news",
                    "theme": "RBAC deterministic item",
                    "goal": "Prove the stored write role",
                    "source_kind": "test_fixture",
                    "source_ref": "viewer-mutation-readiness",
                    "seo_views": 0,
                }
            ],
        },
    )
    return ids


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


@pytest.mark.parametrize(
    "actor_key, expected_status",
    (
        ("viewer", 403),
        ("network_viewer", 403),
        ("revoked", 403),
        ("foreign", 403),
        ("member", 200),
        ("owner", 200),
        ("superadmin", 200),
    ),
)
def test_content_plan_generation_uses_stored_write_role(
    viewer_mutation_database,
    monkeypatch,
    actor_key,
    expected_status,
):
    """The generate API must apply the write role before generation side effects."""
    app = Flask(__name__)
    ids = install_content_generation_dependencies(monkeypatch, viewer_mutation_database)
    monkeypatch.setattr(content_plans_api, "verify_session", lambda token: {"user_id": token, "is_superadmin": False})
    before = content_generation_snapshot(viewer_mutation_database)
    context = app.test_request_context(
        "/api/content-plans/generate",
        method="POST",
        headers={"Authorization": f"Bearer {ids[actor_key]}"},
        json={
            "business_id": ids["business"],
            "scope_type": "single_business",
            "scope_target_id": ids["business"],
            "period_days": 30,
            "density": "standard",
            "content_mix": {},
        },
    )
    context.push()
    try:
        result = content_plans_api.content_plan_generate()
    finally:
        context.pop()
    after = content_generation_snapshot(viewer_mutation_database)

    if expected_status == 403:
        counts = {
            table_name: (len(before[table_name]), len(after[table_name]))
            for table_name in before
        }
        assert (response_status(result), after == before) == (403, True), counts
        return

    assert response_status(result) == expected_status
    response = result.get_json()
    assert response["success"] is True
    assert response["plan"]["title"] == "RBAC deterministic plan"
    assert [item["theme"] for item in response["plan"]["items"]] == ["RBAC deterministic item"]
    assert len(after["contentplans"]) == len(before["contentplans"]) + 1
    assert len(after["contentplanitems"]) == len(before["contentplanitems"]) + 1
    assert len(after["ailearningevents"]) == len(before["ailearningevents"]) + 1
    before_ids = {table_name: {row["id"] for row in rows} for table_name, rows in before.items()}
    new_plan = next(row for row in after["contentplans"] if row["id"] not in before_ids["contentplans"])
    new_item = next(row for row in after["contentplanitems"] if row["id"] not in before_ids["contentplanitems"])
    new_event = next(row for row in after["ailearningevents"] if row["id"] not in before_ids["ailearningevents"])
    assert (new_plan["business_id"], new_plan["created_by"], new_plan["title"]) == (
        ids["business"],
        ids[actor_key],
        "RBAC deterministic plan",
    )
    assert (new_item["plan_id"], new_item["business_id"], new_item["theme"]) == (
        new_plan["id"],
        ids["business"],
        "RBAC deterministic item",
    )
    assert (new_event["business_id"], new_event["user_id"], new_event["capability"], new_event["event_type"]) == (
        ids["business"],
        ids[actor_key],
        "content_plan.generate",
        "generated",
    )


@pytest.mark.parametrize("actor_key", ("viewer", "network_viewer", "revoked", "foreign"))
def test_content_plan_generation_service_rejects_non_writers_before_generation_dependencies(
    viewer_mutation_database,
    monkeypatch,
    actor_key,
):
    """The service boundary must not rely on this particular HTTP route."""
    ids = install_content_generation_dependencies(monkeypatch, viewer_mutation_database)
    called_dependencies = []
    monkeypatch.setattr(
        content_plan_service,
        "get_allowed_content_plan_horizons",
        lambda _business_id: called_dependencies.append("horizons") or [30],
    )
    before = content_generation_snapshot(viewer_mutation_database)

    with pytest.raises(PermissionError, match="Нет доступа к бизнесу"):
        content_plan_service.create_generated_content_plan(
            ids[actor_key],
            ids["business"],
            scope_type="single_business",
            scope_target_id=ids["business"],
            period_days=30,
            density="standard",
            content_mix={},
        )

    assert called_dependencies == []
    assert content_generation_snapshot(viewer_mutation_database) == before


def invoke_mobile_content_plan_generation(app, viewer_mutation_database, monkeypatch, actor_key, payload):
    """Invoke the mobile route with real business membership verification."""
    ids = install_content_generation_dependencies(monkeypatch, viewer_mutation_database)
    monkeypatch.setattr(operator_api, "DatabaseManager", lambda: database_factory(viewer_mutation_database))
    monkeypatch.setattr(
        operator_api,
        "require_auth_from_request",
        lambda: {"user_id": ids[actor_key], "is_superadmin": False},
    )
    monkeypatch.setattr(
        operator_api,
        "resolve_control_scope",
        lambda _cursor, **_kwargs: {
            "kind": "business",
            "id": ids["business"],
            "business_ids": [ids["business"]],
        },
    )
    monkeypatch.setattr(operator_api, "_scope_capability_access", lambda *_args: {"allowed": True})
    context = app.test_request_context(
        "/api/operator/mobile/content/plans/generate",
        method="POST",
        json={"scope_type": "business", "scope_id": ids["business"], **payload},
    )
    context.push()
    try:
        return operator_api.operator_mobile_content_plan_generate(), ids
    finally:
        context.pop()


@pytest.mark.parametrize("actor_key", ("viewer", "network_viewer"))
def test_mobile_content_plan_generation_maps_service_write_denial_to_403(
    viewer_mutation_database,
    monkeypatch,
    actor_key,
):
    app = Flask(__name__)
    before = content_generation_snapshot(viewer_mutation_database)
    result, _ids = invoke_mobile_content_plan_generation(
        app,
        viewer_mutation_database,
        monkeypatch,
        actor_key,
        {"period_days": 30, "density": "standard", "content_mix": {}},
    )
    after = content_generation_snapshot(viewer_mutation_database)

    assert (response_status(result), after == before) == (403, True)


def test_mobile_content_plan_generation_keeps_invalid_period_as_400(
    viewer_mutation_database,
    monkeypatch,
):
    app = Flask(__name__)
    before = content_generation_snapshot(viewer_mutation_database)
    result, _ids = invoke_mobile_content_plan_generation(
        app,
        viewer_mutation_database,
        monkeypatch,
        "owner",
        {"period_days": "not-a-number", "density": "standard", "content_mix": {}},
    )
    after = content_generation_snapshot(viewer_mutation_database)

    assert (response_status(result), after == before) == (400, True)


@pytest.mark.parametrize(
    "actor_key, scope_type, target_key, expected_status, expected_error",
    (
        ("member", "network_location", "location_b", 403, "Нет доступа к бизнесу"),
        ("member_viewer_location_b", "network_location", "location_b", 403, "Нет доступа к бизнесу"),
        ("root_viewer_location_b_member", "network_location", "location_b", 403, "Нет доступа к бизнесу"),
        ("location_b_only_member", "network_location", "location_b", 403, "Нет доступа к бизнесу"),
        ("member", "network_location", "foreign_business", 403, "Недоступный контекст контент-плана"),
        ("member", "network_parent", "network", 403, "Нет доступа к бизнесу"),
        ("member_viewer_location_b", "network_parent", "network", 403, "Нет доступа к бизнесу"),
        ("member_all_locations", "network_location", "location_b", 200, ""),
        ("member_all_locations", "network_parent", "network", 200, ""),
        ("network_member", "network_parent", "network", 200, ""),
        ("owner", "network_parent", "network", 200, ""),
        ("superadmin", "network_parent", "network", 200, ""),
    ),
)
def test_content_plan_generation_authorizes_every_resolved_scope_target(
    viewer_mutation_database,
    monkeypatch,
    actor_key,
    scope_type,
    target_key,
    expected_status,
    expected_error,
):
    """Scope resolution is production code; each resolved target needs write access."""
    ids = install_content_generation_dependencies(
        monkeypatch,
        viewer_mutation_database,
        use_real_scope_resolution=True,
    )
    before = content_generation_snapshot(viewer_mutation_database)

    if expected_status == 403:
        with pytest.raises(PermissionError, match=expected_error):
            content_plan_service.create_generated_content_plan(
                ids[actor_key],
                ids["business"],
                scope_type=scope_type,
                scope_target_id=ids[target_key],
                period_days=30,
                density="standard",
                content_mix={},
            )
        assert content_generation_snapshot(viewer_mutation_database) == before
        return

    if scope_type == "network_parent":
        monkeypatch.setattr(
            content_plan_service,
            "build_content_plan_skeleton",
            lambda _context, **_kwargs: {
                "title": "RBAC deterministic network plan",
                "period_start": "2026-09-10",
                "period_end": "2026-10-09",
                "meta": {},
                "items": [
                    {"scheduled_for": "2026-09-10", "content_type": "news", "theme": "Network item A", "goal": "Proof", "source_kind": "test_fixture", "source_ref": "network-a", "seo_views": 0},
                    {"scheduled_for": "2026-09-17", "content_type": "news", "theme": "Network item B", "goal": "Proof", "source_kind": "test_fixture", "source_ref": "network-b", "seo_views": 0},
                ],
            },
        )

    plan = content_plan_service.create_generated_content_plan(
        ids[actor_key],
        ids["business"],
        scope_type=scope_type,
        scope_target_id=ids[target_key],
        period_days=30,
        density="standard",
        content_mix={},
    )
    after = content_generation_snapshot(viewer_mutation_database)
    assert (plan["scope_type"], plan["scope_target_id"]) == (scope_type, ids[target_key])
    assert len(after["contentplans"]) == len(before["contentplans"]) + 1
    expected_item_business_ids = {ids["location_b"]} if scope_type == "network_location" else {ids["business"], ids["location_b"]}
    assert len(after["contentplanitems"]) == len(before["contentplanitems"]) + len(expected_item_business_ids)
    assert len(after["ailearningevents"]) == len(before["ailearningevents"]) + 1
    before_ids = {table_name: {row["id"] for row in rows} for table_name, rows in before.items()}
    new_plan = next(row for row in after["contentplans"] if row["id"] not in before_ids["contentplans"])
    new_items = [row for row in after["contentplanitems"] if row["id"] not in before_ids["contentplanitems"]]
    new_event = next(row for row in after["ailearningevents"] if row["id"] not in before_ids["ailearningevents"])
    assert (new_plan["business_id"], new_plan["scope_type"], new_plan["scope_target_id"]) == (
        ids["business"], scope_type, ids[target_key]
    )
    assert {row["business_id"] for row in new_items} == expected_item_business_ids
    assert {row["location_scope"] for row in new_items} == expected_item_business_ids
    assert (new_event["business_id"], new_event["user_id"]) == (ids["business"], ids[actor_key])


@pytest.mark.parametrize("scope_type, target_key", (("single_business", "foreign_business"), ("", "foreign_business")))
def test_content_plan_single_business_scope_cannot_persist_foreign_target(
    viewer_mutation_database,
    monkeypatch,
    scope_type,
    target_key,
):
    ids = install_content_generation_dependencies(
        monkeypatch,
        viewer_mutation_database,
        use_real_scope_resolution=True,
    )

    plan = content_plan_service.create_generated_content_plan(
        ids["member"],
        ids["business"],
        scope_type=scope_type,
        scope_target_id=ids[target_key],
        period_days=30,
        density="standard",
        content_mix={},
    )

    assert (plan["scope_type"], plan["scope_target_id"]) == ("single_business", ids["business"])
    assert {item["business_id"] for item in plan["items"]} == {ids["business"]}


def test_content_plan_network_location_without_current_location_fails_closed(
    viewer_mutation_database,
    monkeypatch,
):
    ids = install_content_generation_dependencies(
        monkeypatch,
        viewer_mutation_database,
        use_real_scope_resolution=True,
    )
    before = content_generation_snapshot(viewer_mutation_database)

    with pytest.raises(PermissionError, match="Недоступный контекст контент-плана"):
        content_plan_service.create_generated_content_plan(
            ids["owner"],
            ids["network"],
            scope_type="network_location",
            scope_target_id=None,
            period_days=30,
            density="standard",
            content_mix={},
        )

    assert content_generation_snapshot(viewer_mutation_database) == before


@pytest.mark.parametrize(
    "actor_key, target_key, expected_status, expected_visible_keys",
    (
        ("member", "location_b", 403, ()),
        ("location_b_only_member", "location_b", 403, ()),
        ("member", "foreign_business", 403, ()),
        ("root_viewer_location_b_member", "location_b", 200, ("business", "location_b")),
        ("viewer", "business", 200, ("business",)),
    ),
)
def test_content_plan_context_scopes_are_read_authorized_per_target(
    viewer_mutation_database,
    monkeypatch,
    actor_key,
    target_key,
    expected_status,
    expected_visible_keys,
):
    """A viewer may open their own context, but not another location's context."""
    app = Flask(__name__)
    ids = install_content_generation_dependencies(
        monkeypatch,
        viewer_mutation_database,
        use_real_scope_resolution=True,
    )
    monkeypatch.setattr(content_plans_api, "verify_session", lambda token: {"user_id": token, "is_superadmin": False})
    before = content_generation_snapshot(viewer_mutation_database)
    context = app.test_request_context(
        "/api/content-plans/context",
        method="GET",
        headers={"Authorization": f"Bearer {ids[actor_key]}"},
        query_string={
            "business_id": ids["business"],
            "scope_type": "network_location",
            "scope_target_id": ids[target_key],
        },
    )
    context.push()
    try:
        result = content_plans_api.content_plan_context()
    finally:
        context.pop()

    assert response_status(result) == expected_status
    assert content_generation_snapshot(viewer_mutation_database) == before
    if expected_status == 200:
        scope = result.get_json()["context"]["scope"]
        assert scope["scope_target_id"] == ids[target_key]
        assert {item["scope_target_id"] for item in scope["scope_options"]} == {ids[key] for key in expected_visible_keys}


def test_content_plan_context_defaults_to_current_business_without_sibling_scope_leakage(
    viewer_mutation_database,
    monkeypatch,
):
    app = Flask(__name__)
    ids = install_content_generation_dependencies(
        monkeypatch,
        viewer_mutation_database,
        use_real_scope_resolution=True,
    )
    monkeypatch.setattr(content_plans_api, "verify_session", lambda token: {"user_id": token, "is_superadmin": False})
    context = app.test_request_context(
        "/api/content-plans/context",
        method="GET",
        headers={"Authorization": f"Bearer {ids['viewer']}"},
        query_string={"business_id": ids["business"]},
    )
    context.push()
    try:
        result = content_plans_api.content_plan_context()
    finally:
        context.pop()

    scope = result.get_json()["context"]["scope"]
    assert response_status(result) == 200
    assert (scope["scope_type"], scope["scope_target_id"]) == ("single_business", ids["business"])
    assert {item["scope_target_id"] for item in scope["scope_options"]} == {ids["business"]}
