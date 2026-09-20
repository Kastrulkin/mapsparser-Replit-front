import io

from flask import Flask
import pytest

from api import media_intelligence_api
from api.media_intelligence_api import _invalidate_social_approvals_for_photo_usage


class FakeCursor:
    def __init__(self, rowcount=0):
        self.rowcount = rowcount
        self.query = ""
        self.params = ()

    def execute(self, query, params=None):
        self.query = " ".join(str(query).split())
        self.params = params or ()


def test_photo_selection_resets_approval_for_unpublished_platform_posts():
    cursor = FakeCursor(rowcount=3)

    changed = _invalidate_social_approvals_for_photo_usage(
        cursor,
        business_id="biz-1",
        content_plan_item_id="item-1",
        photo_asset_id="photo-1",
    )

    assert changed == 3
    assert "SET status = 'needs_review'" in cursor.query
    assert "approved_at = NULL" in cursor.query
    assert "status NOT IN ('published', 'publishing')" in cursor.query
    assert cursor.params == ("photo-1", "biz-1", "item-1")


def test_platform_photo_selection_only_resets_that_platform():
    cursor = FakeCursor(rowcount=1)

    changed = _invalidate_social_approvals_for_photo_usage(
        cursor,
        business_id="biz-1",
        content_plan_item_id="item-1",
        photo_asset_id="photo-1",
        target_platform="telegram",
    )

    assert changed == 1
    assert "AND platform = %s" in cursor.query
    assert cursor.params == ("photo-1", "biz-1", "item-1", "telegram")


def test_viewer_cannot_create_external_photo_asset(monkeypatch):
    class Connection:
        def cursor(self):
            return object()

        def rollback(self):
            return None

        def commit(self):
            return None

    class Database:
        conn = Connection()

        def close(self):
            return None

    app = Flask(__name__)
    app.register_blueprint(media_intelligence_api.media_intelligence_bp)
    created = []
    monkeypatch.setattr(media_intelligence_api, "DatabaseManager", Database)
    monkeypatch.setattr(media_intelligence_api, "require_auth_from_request", lambda: {"user_id": "viewer-1"})
    monkeypatch.setattr(media_intelligence_api, "verify_business_access", lambda *_args: (True, "owner-1"))
    monkeypatch.setattr(media_intelligence_api, "verify_business_write_access", lambda *_args: (False, "owner-1"), raising=False)
    monkeypatch.setattr(media_intelligence_api, "is_capability_enabled", lambda *_args: True)
    monkeypatch.setattr(
        media_intelligence_api,
        "upsert_photo_asset",
        lambda *_args, **_kwargs: created.append(True),
    )

    response = app.test_client().post(
        "/api/media-intelligence/photos",
        json={"business_id": "business-1", "original_url": "https://public.invalid/image.jpg"},
    )

    assert response.status_code == 403
    assert created == []


class _AccessCursor:
    def __init__(self, role):
        self.role = role
        self.role_queries = 0

    def execute(self, query, _params=None):
        if "SELECT bm.role" in str(query):
            self.role_queries += 1

    def fetchone(self):
        return ("owner-1", True, False, False)

    def fetchall(self):
        return [(self.role,)]


class _AccessConnection:
    def __init__(self, role):
        self.cursor_instance = _AccessCursor(role)
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class _AccessDatabase:
    def __init__(self, role):
        self.conn = _AccessConnection(role)
        self.closed = False

    def close(self):
        self.closed = True


def _media_app():
    app = Flask(__name__)
    app.register_blueprint(media_intelligence_api.media_intelligence_bp)
    return app


@pytest.mark.parametrize(
    ("path", "payload", "is_upload"),
    [
        ("/api/media-intelligence/settings", {"business_id": "business-1", "vision_enabled": True}, False),
        ("/api/media-intelligence/photos", {"business_id": "business-1", "original_url": "https://public.invalid/photo.jpg"}, False),
        ("/api/media-intelligence/photos/upload", {"business_id": "business-1"}, True),
        ("/api/media-intelligence/photos/photo-1/analyze", {"business_id": "business-1"}, False),
        ("/api/media-intelligence/photos/photo-1/version", {"business_id": "business-1", "original_url": "https://public.invalid/photo.jpg"}, False),
        ("/api/media-intelligence/photos/photo-1/usage", {"business_id": "business-1", "target_id": "item-1"}, False),
    ],
)
def test_viewer_cannot_reach_any_media_write_handler(monkeypatch, path, payload, is_upload):
    database = _AccessDatabase("viewer")
    downstream_calls = []

    def forbidden_downstream(*_args, **_kwargs):
        downstream_calls.append(True)
        raise AssertionError("viewer must be rejected before write-side effects")

    monkeypatch.setattr(media_intelligence_api, "DatabaseManager", lambda: database)
    monkeypatch.setattr(media_intelligence_api, "require_auth_from_request", lambda: {"user_id": "viewer-1"})
    for name in (
        "set_capability_enabled",
        "is_capability_enabled",
        "upsert_photo_asset",
        "create_uploaded_photo_asset",
        "load_business",
        "analyze_photo_runtime",
        "create_photo_asset_version",
        "record_photo_usage",
    ):
        monkeypatch.setattr(media_intelligence_api, name, forbidden_downstream)

    client = _media_app().test_client()
    if is_upload:
        response = client.post(path, data={**payload, "file": (io.BytesIO(b"image"), "photo.jpg")})
    else:
        response = client.post(path, json=payload)

    assert response.status_code == 403
    assert downstream_calls == []
    assert database.conn.cursor_instance.role_queries == 1
    assert database.conn.committed is False


def test_editor_can_create_media_asset_after_actual_write_gate(monkeypatch):
    database = _AccessDatabase("editor")
    created = []
    monkeypatch.setattr(media_intelligence_api, "DatabaseManager", lambda: database)
    monkeypatch.setattr(media_intelligence_api, "require_auth_from_request", lambda: {"user_id": "editor-1"})
    monkeypatch.setattr(media_intelligence_api, "is_capability_enabled", lambda *_args: True)
    monkeypatch.setattr(
        media_intelligence_api,
        "upsert_photo_asset",
        lambda *_args, **kwargs: created.append(kwargs) or {"id": "photo-1"},
    )

    response = _media_app().test_client().post(
        "/api/media-intelligence/photos",
        json={"business_id": "business-1", "original_url": "https://public.invalid/photo.jpg"},
    )

    assert response.status_code == 200
    assert created and created[0]["business_id"] == "business-1"
    assert database.conn.cursor_instance.role_queries == 1
    assert database.conn.committed is True


def test_viewer_keeps_media_read_and_head_access_without_write_role_query(monkeypatch):
    database = _AccessDatabase("viewer")
    monkeypatch.setattr(media_intelligence_api, "DatabaseManager", lambda: database)
    monkeypatch.setattr(media_intelligence_api, "require_auth_from_request", lambda: {"user_id": "viewer-1"})
    monkeypatch.setattr(media_intelligence_api, "list_photo_assets", lambda *_args: [])
    monkeypatch.setattr(media_intelligence_api, "build_photo_coverage", lambda *_args: {})
    monkeypatch.setattr(media_intelligence_api, "get_network_photo_analysis_quota", lambda *_args: {})

    client = _media_app().test_client()
    assert client.get("/api/media-intelligence/photos?business_id=business-1").status_code == 200
    assert client.head("/api/media-intelligence/photos?business_id=business-1").status_code == 200
    assert database.conn.cursor_instance.role_queries == 0
