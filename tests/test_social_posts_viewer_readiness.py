"""Native PostgreSQL proof that social-post viewers keep read access but cannot mutate."""

import hashlib
import os
import re
import sys
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask
import psycopg2
from psycopg2 import sql
from psycopg2.extras import Json, RealDictCursor
import pytest

from api import social_posts_api
from services import social_post_service
from services.social_posts import readiness_foundation


TEST_DSN_ENV = "LOCALOS_SOCIAL_VIEWER_TEST_DATABASE_URL"
GUARD_ENV = "LOCALOS_SOCIAL_VIEWER_GUARD_SHA256"
TABLES = (
    "users",
    "businesses",
    "business_members",
    "network_members",
    "networks",
    "social_posts",
    "social_post_metrics",
    "social_post_attribution_events",
    "contentplans",
    "contentplanitems",
    "ailearningevents",
)


def isolated_test_dsn() -> str:
    database_url = os.getenv(TEST_DSN_ENV, "")
    if not database_url:
        pytest.skip(f"{TEST_DSN_ENV} is required for native social viewer proof")
    if any(os.getenv(key) for key in ("PGHOSTADDR", "PGSERVICE", "PGSERVICEFILE", "PGOPTIONS")):
        raise RuntimeError("native social viewer proof refuses inherited libpq overrides")
    parsed = urlsplit(database_url)
    if (
        parsed.scheme not in {"postgresql", "postgres"}
        or parsed.hostname not in {"127.0.0.1", "::1"}
        or parsed.port != 35418
        or not re.fullmatch(r"/readiness_full_test_[a-z0-9_]+", parsed.path)
        or parsed.query
        or parsed.fragment
    ):
        raise RuntimeError("native social viewer proof requires a migrated owned loopback readiness database")
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
        raise RuntimeError("native social viewer proof requires pinned guard-first sitecustomize")
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
def social_viewer_database():
    database_url = isolated_test_dsn()
    schema = "social_viewer_" + uuid.uuid4().hex
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
            "owner", "member", "manager", "viewer", "network_owner", "network_viewer",
            "superadmin", "foreign", "business", "foreign_business", "network", "plan", "item", "draft",
            "approved", "manual", "supervised", "published",
        )}
        for user_key in ("owner", "member", "manager", "viewer", "network_owner", "network_viewer", "superadmin", "foreign"):
            cursor.execute(
                "INSERT INTO users (id, email, is_active, is_verified, is_superadmin) VALUES (%s, %s, TRUE, TRUE, %s)",
                (ids[user_key], f"{user_key}@social-viewer.invalid", user_key == "superadmin"),
            )
        cursor.execute(
            "INSERT INTO networks (id, owner_id, name) VALUES (%s, %s, 'Social viewer network')",
            (ids["network"], ids["network_owner"]),
        )
        cursor.execute(
            "INSERT INTO businesses (id, owner_id, network_id, name, is_active) VALUES (%s, %s, %s, 'Social viewer proof', TRUE)",
            (ids["business"], ids["owner"], ids["network"]),
        )
        cursor.execute(
            "INSERT INTO businesses (id, owner_id, name, is_active) VALUES (%s, %s, 'Foreign social proof', TRUE)",
            (ids["foreign_business"], ids["foreign"]),
        )
        cursor.execute(
            """
            INSERT INTO contentplans (
                id, business_id, title, period_days, period_start, period_end, plan_status, generated_plan_json
            ) VALUES (%s, %s, 'Social viewer plan', 14, CURRENT_DATE, CURRENT_DATE + 13, 'generated', %s)
            """,
            (ids["plan"], ids["business"], Json({})),
        )
        cursor.execute(
            """
            INSERT INTO contentplanitems (
                id, plan_id, business_id, scheduled_for, content_type, theme, goal,
                source_kind, source_ref, draft_text, status, metadata_json
            ) VALUES (%s, %s, %s, CURRENT_DATE, 'news', 'Social viewer item', 'Role proof',
                      'synthetic', 'social-viewer', 'Проверенный исходный текст для подготовки публикации.',
                      'edited', %s)
            """,
            (ids["item"], ids["plan"], ids["business"], Json({})),
        )
        for actor, role in (("member", "member"), ("manager", "manager"), ("viewer", "viewer")):
            cursor.execute(
                "INSERT INTO business_members (id, business_id, user_id, role, status) VALUES (%s, %s, %s, %s, 'active')",
                (str(uuid.uuid4()), ids["business"], ids[actor], role),
            )
        cursor.execute(
            "INSERT INTO network_members (id, network_id, user_id, role, status) VALUES (%s, %s, %s, 'viewer', 'active')",
            (str(uuid.uuid4()), ids["network"], ids["network_viewer"]),
        )
        for post_key, status, platform in (
            ("draft", "needs_review", "telegram"),
            ("approved", "approved", "yandex_maps"),
            ("manual", "needs_manual_publish", "google_business"),
            ("supervised", "queued", "two_gis"),
            ("published", "published", "facebook"),
        ):
            approved_at = None
            approval_id = None
            published_at = None
            if status in {"approved", "queued", "published"}:
                approved_at = "2026-09-18T00:00:00+00:00"
                approval_id = str(uuid.uuid4())
            if status == "published":
                published_at = "2026-09-18T00:00:00+00:00"
            publish_mode = "manual" if post_key == "approved" else "api"
            media_json = Json([{"fixture": "social-viewer"}]) if post_key == "approved" else Json([])
            cursor.execute(
                """
                INSERT INTO social_posts (
                    id, business_id, content_plan_id, content_plan_item_id, platform, publish_mode, status, approved_at, approval_id,
                    published_at, base_text, platform_text, media_json, metadata_json, created_by
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    ids[post_key], ids["business"], ids["plan"], ids["item"], platform, publish_mode, status, approved_at, approval_id, published_at,
                    "Проверенный текст публикации для синтетического role regression.",
                    "Проверенный текст публикации для синтетического role regression.",
                    media_json, Json({}), ids["owner"],
                ),
            )
        connection.commit()
        yield {"database_url": database_url, "schema": schema, "ids": ids}
    finally:
        connection.rollback()
        cursor.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema)))
        connection.commit()
        cursor.close()
        connection.close()


def database_factory(social_viewer_database):
    return ScopedDatabaseManager(social_viewer_database["database_url"], social_viewer_database["schema"])


def post_snapshot(social_viewer_database, post_id: str) -> dict:
    connection = psycopg2.connect(social_viewer_database["database_url"], cursor_factory=RealDictCursor)
    cursor = connection.cursor()
    try:
        cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(social_viewer_database["schema"])))
        cursor.execute(
            "SELECT status, platform_text, base_text, approved_at, approval_id, provider_post_id, provider_post_url, metadata_json FROM social_posts WHERE id = %s",
            (post_id,),
        )
        row = cursor.fetchone()
        return dict(row)
    finally:
        cursor.close()
        connection.close()


def mutation_counts(social_viewer_database) -> dict:
    connection = psycopg2.connect(social_viewer_database["database_url"], cursor_factory=RealDictCursor)
    cursor = connection.cursor()
    try:
        cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(social_viewer_database["schema"])))
        result = {}
        for table_name in (
            "social_posts",
            "social_post_metrics",
            "social_post_attribution_events",
            "contentplans",
            "contentplanitems",
        ):
            cursor.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table_name)))
            result[table_name] = int(cursor.fetchone()["count"])
        return result
    finally:
        cursor.close()
        connection.close()


def plan_content_snapshot(social_viewer_database) -> dict:
    ids = social_viewer_database["ids"]
    connection = psycopg2.connect(social_viewer_database["database_url"], cursor_factory=RealDictCursor)
    cursor = connection.cursor()
    try:
        cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(social_viewer_database["schema"])))
        cursor.execute("SELECT edited_plan_json FROM contentplans WHERE id = %s", (ids["plan"],))
        plan = cursor.fetchone()
        cursor.execute(
            "SELECT goal, draft_text, status, metadata_json FROM contentplanitems WHERE id = %s",
            (ids["item"],),
        )
        item = cursor.fetchone()
        return {"plan": dict(plan), "item": dict(item)}
    finally:
        cursor.close()
        connection.close()


@pytest.fixture
def social_client(social_viewer_database, monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(social_posts_api.social_posts_bp)
    social_posts_api._WRITE_RATE_BUCKETS.clear()

    def manager():
        return database_factory(social_viewer_database)

    def verify(token):
        return {
            "user_id": token,
            "is_superadmin": token == social_viewer_database["ids"]["superadmin"],
        }

    monkeypatch.setattr(social_posts_api, "DatabaseManager", manager)
    monkeypatch.setattr(social_post_service, "DatabaseManager", manager)
    monkeypatch.setattr(social_posts_api, "verify_session", verify)
    monkeypatch.setattr(social_posts_api, "get_capability_access", lambda *_args: {"allowed": True})
    return app.test_client()


@pytest.mark.parametrize("actor_key", ("viewer", "network_viewer"))
def test_viewers_receive_403_and_leave_social_post_unchanged(social_viewer_database, social_client, monkeypatch, actor_key):
    ids = social_viewer_database["ids"]
    effects = {
        "provider": 0,
        "launch_preflight": 0,
        "dispatch": 0,
        "provider_metrics": 0,
        "variants": 0,
        "recommended_photo": 0,
    }

    def provider_should_not_run(*_args, **_kwargs):
        effects["provider"] += 1
        return {"publish_outcome": "uncertain", "metadata_json": {"synthetic": True}}

    def build_variants_should_not_run(*_args, **_kwargs):
        effects["variants"] += 1
        return {}

    def recommended_photo_should_not_run(*_args, **_kwargs):
        effects["recommended_photo"] += 1
        return {"selected": False, "photo_asset_id": "", "source": "test"}

    def provider_metrics_should_not_run(*_args, **_kwargs):
        effects["provider_metrics"] += 1
        return {"source": "test", "status": "not_attempted"}

    def launch_preflight_should_not_run(*_args, **_kwargs):
        effects["launch_preflight"] += 1
        return {"launch_gate": {"allowed": True}, "summary": {"api_due_posts": 0}}

    def dispatch_should_not_run(*_args, **_kwargs):
        effects["dispatch"] += 1
        return {
            "picked": 0,
            "published": 0,
            "supervised": 0,
            "manual": 0,
            "failed": 0,
            "details": [],
            "errors": [],
        }

    monkeypatch.setattr(social_post_service, "_publish_api_post", provider_should_not_run)
    monkeypatch.setattr(readiness_foundation, "build_platform_variants", build_variants_should_not_run)
    monkeypatch.setattr("services.media_intelligence.ensure_recommended_photo_usage", recommended_photo_should_not_run)
    monkeypatch.setattr(social_post_service, "_collect_provider_metrics_for_post", provider_metrics_should_not_run)
    monkeypatch.setattr(social_post_service, "get_social_launch_preflight", launch_preflight_should_not_run)
    monkeypatch.setattr(social_post_service, "dispatch_due_social_posts", dispatch_should_not_run)
    before = {
        key: post_snapshot(social_viewer_database, ids[key])
        for key in ("draft", "approved", "manual", "supervised", "published")
    }
    counts_before = mutation_counts(social_viewer_database)
    plan_before = plan_content_snapshot(social_viewer_database)
    headers = {"Authorization": f"Bearer {ids[actor_key]}"}
    responses = [
        social_client.post(
            f"/api/content-plans/items/{ids['item']}/social-posts/prepare",
            headers=headers,
            json={"platforms": ["telegram"]},
        ),
        social_client.patch(
            f"/api/social-posts/{ids['draft']}",
            headers=headers,
            json={"platform_text": "Попытка изменения viewer не должна попасть в БД."},
        ),
        social_client.post(f"/api/social-posts/{ids['approved']}/approve", headers=headers),
        social_client.post(f"/api/social-posts/{ids['approved']}/queue", headers=headers),
        social_client.post(f"/api/social-posts/{ids['approved']}/publish", headers=headers),
        social_client.post(
            f"/api/social-posts/{ids['manual']}/mark-manual-published",
            headers=headers,
            json={"content_confirmed": True, "provider_post_id": "synthetic-manual-receipt"},
        ),
        social_client.post(
            f"/api/social-posts/{ids['approved']}/use-manual-publish",
            headers=headers,
            json={"reason": "Viewer must not select manual publish."},
        ),
        social_client.post(
            f"/api/social-posts/{ids['supervised']}/mark-supervised-blocked",
            headers=headers,
            json={"reason": "Viewer must not change supervised status."},
        ),
        social_client.post(
            f"/api/social-posts/{ids['supervised']}/supervised-task",
            headers=headers,
            json={"approved": True},
        ),
        social_client.post(
            f"/api/social-posts/{ids['published']}/attribution-events",
            headers=headers,
            json={"event_type": "lead", "value": 1},
        ),
        social_client.post(
            "/api/social-posts/bulk-attribution-events",
            headers=headers,
            json={"post_ids": [ids["published"]], "event_type": "lead", "value": 1},
        ),
        social_client.post(
            "/api/social-posts/metrics/collect",
            headers=headers,
            json={"post_id": ids["published"]},
        ),
        social_client.post(
            "/api/social-posts/metrics/run-once",
            headers=headers,
            json={"business_id": ids["business"], "approved": True},
        ),
        social_client.post(
            f"/api/content-plans/{ids['plan']}/social-posts/apply-recommendation",
            headers=headers,
            json={"approved": True},
        ),
        social_client.post(
            "/api/social-posts/dispatch/run-once",
            headers=headers,
            json={"business_id": ids["business"], "approved": True, "approval_text": "ПУБЛИКУЮ"},
        ),
    ]

    assert [response.status_code for response in responses] == [403] * len(responses)
    assert effects == {key: 0 for key in effects}
    assert mutation_counts(social_viewer_database) == counts_before
    assert plan_content_snapshot(social_viewer_database) == plan_before
    for key, snapshot in before.items():
        assert post_snapshot(social_viewer_database, ids[key]) == snapshot


@pytest.mark.parametrize("actor_key", ("owner", "member", "manager", "network_owner", "superadmin"))
def test_write_roles_keep_social_post_text_mutation(social_viewer_database, social_client, actor_key):
    ids = social_viewer_database["ids"]
    response = social_client.patch(
        f"/api/social-posts/{ids['draft']}",
        headers={"Authorization": f"Bearer {ids[actor_key]}"},
        json={"platform_text": f"Обновление разрешённой роли {actor_key} для social-post regression."},
    )

    assert response.status_code == 200, response.get_json()
    assert post_snapshot(social_viewer_database, ids["draft"])["platform_text"].startswith("Обновление разрешённой роли")


def test_viewer_manual_reconciliation_is_denied_before_advisory_lock(social_viewer_database, social_client, monkeypatch):
    ids = social_viewer_database["ids"]
    advisory_queries = []

    class RecordingCursor:
        def __init__(self, cursor):
            self.cursor = cursor

        def execute(self, query, params=None):
            if "pg_try_advisory_xact_lock" in str(query):
                advisory_queries.append(str(query))
            if params is None:
                return self.cursor.execute(query)
            return self.cursor.execute(query, params)

        def __getattr__(self, name):
            return getattr(self.cursor, name)

    class RecordingConnection:
        def __init__(self, connection):
            self.connection = connection

        def cursor(self):
            return RecordingCursor(self.connection.cursor())

        def __getattr__(self, name):
            return getattr(self.connection, name)

    class RecordingDatabaseManager:
        def __init__(self):
            manager = database_factory(social_viewer_database)
            self._manager = manager
            self.conn = RecordingConnection(manager.conn)

        def close(self):
            self._manager.close()

    monkeypatch.setattr(social_post_service, "DatabaseManager", RecordingDatabaseManager)
    response = social_client.post(
        f"/api/social-posts/{ids['manual']}/mark-manual-published",
        headers={"Authorization": f"Bearer {ids['viewer']}"},
        json={"content_confirmed": True, "provider_post_id": "synthetic-manual-receipt"},
    )

    assert response.status_code == 403, response.get_json()
    assert advisory_queries == []


def test_viewer_keeps_read_and_rehearsal_access(social_viewer_database, social_client, monkeypatch):
    ids = social_viewer_database["ids"]
    headers = {"Authorization": f"Bearer {ids['viewer']}"}

    def channel_readiness(*_args, **_kwargs):
        return []

    def rehearsal(cursor, post):
        return {"post_id": str(post.get("id") or ""), "dry_run": True}

    monkeypatch.setattr(social_post_service, "_build_channel_readiness", channel_readiness)
    monkeypatch.setattr(social_post_service, "_build_social_post_publish_rehearsal", rehearsal)

    before = {
        "approved": post_snapshot(social_viewer_database, ids["approved"]),
        "counts": mutation_counts(social_viewer_database),
        "plan": plan_content_snapshot(social_viewer_database),
    }
    listed = social_client.get(f"/api/content-plans/{ids['plan']}/social-posts", headers=headers)
    rehearsal = social_client.post(f"/api/social-posts/{ids['approved']}/publish-rehearsal", headers=headers)

    assert listed.status_code == 200, listed.get_json()
    assert rehearsal.status_code == 200, rehearsal.get_json()
    assert any(str(post.get("id") or "") == ids["approved"] for post in listed.get_json()["posts"])
    assert rehearsal.get_json()["rehearsal"]["post_id"] == ids["approved"]
    assert post_snapshot(social_viewer_database, ids["approved"]) == before["approved"]
    assert mutation_counts(social_viewer_database) == before["counts"]
    assert plan_content_snapshot(social_viewer_database) == before["plan"]
