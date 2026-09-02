import hashlib
import hmac
import io
import json

from flask import Flask

from api import finance_api, media_intelligence_api, social_posts_api, telegram_opportunity_radar_api


FINANCE_INTERNAL_ERROR = "postgresql://private-user:private-password@database/internal"
MEDIA_INTERNAL_ERROR = "storage-key=private-media-secret"
RADAR_INTERNAL_ERROR = "postgresql://private-radar-password@database/internal"
SOCIAL_INTERNAL_ERROR = "postgresql://private-social-password@database/internal"


class _Connection:
    def __init__(self):
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return object()

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class _Database:
    def __init__(self):
        self.conn = _Connection()
        self.closed = False

    def close(self):
        self.closed = True


def _app(blueprint):
    app = Flask(__name__)
    app.register_blueprint(blueprint)
    return app


def _assert_redacted(response, request_id, message, internal_error):
    assert response.status_code == 500
    assert response.get_json() == {
        "code": "internal_error",
        "message": message,
        "request_id": request_id,
    }
    assert internal_error not in response.get_data(as_text=True)


def test_finance_import_preview_internal_error_is_redacted(monkeypatch):
    monkeypatch.setattr(
        finance_api,
        "_require_finance_user_and_business",
        lambda: ({"user_id": "owner-1"}, "business-1", None),
    )
    monkeypatch.setattr(
        finance_api,
        "_finance_import_payload_from_request",
        lambda: (_ for _ in ()).throw(RuntimeError(FINANCE_INTERNAL_ERROR)),
    )

    response = _app(finance_api.finance_bp).test_client().post(
        "/api/finance/import-preview",
        json={"business_id": "business-1"},
        headers={"X-Request-ID": "finance-import-preview-redaction"},
    )

    _assert_redacted(
        response,
        "finance-import-preview-redaction",
        "Не удалось подготовить импорт финансов",
        FINANCE_INTERNAL_ERROR,
    )


def test_media_photo_upload_internal_error_is_redacted(monkeypatch):
    database = _Database()
    monkeypatch.setattr(media_intelligence_api, "DatabaseManager", lambda: database)
    monkeypatch.setattr(
        media_intelligence_api,
        "require_auth_from_request",
        lambda: {"user_id": "owner-1"},
    )
    monkeypatch.setattr(media_intelligence_api, "_require_business", lambda *_args: (True, None))
    monkeypatch.setattr(media_intelligence_api, "is_capability_enabled", lambda *_args: True)
    monkeypatch.setattr(
        media_intelligence_api,
        "create_uploaded_photo_asset",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError(MEDIA_INTERNAL_ERROR)),
    )

    response = _app(media_intelligence_api.media_intelligence_bp).test_client().post(
        "/api/media-intelligence/photos/upload",
        data={
            "business_id": "business-1",
            "file": (io.BytesIO(b"synthetic-photo"), "photo.jpg", "image/jpeg"),
        },
        headers={"X-Request-ID": "media-photo-upload-redaction"},
    )

    _assert_redacted(
        response,
        "media-photo-upload-redaction",
        "Не удалось загрузить фотографию",
        MEDIA_INTERNAL_ERROR,
    )
    assert database.conn.rolled_back is True
    assert database.closed is True


def test_media_photo_file_internal_error_is_redacted(monkeypatch):
    class _Cursor:
        description = None

        def execute(self, *_args, **_kwargs):
            return None

        def fetchone(self):
            return {
                "business_id": "business-1",
                "storage_key": "business-1/private-photo.jpg",
                "versions_json": {},
            }

    database = _Database()
    database.conn.cursor = lambda: _Cursor()
    monkeypatch.setattr(media_intelligence_api, "DatabaseManager", lambda: database)
    monkeypatch.setattr(
        media_intelligence_api,
        "require_auth_from_request",
        lambda: {"user_id": "owner-1"},
    )
    monkeypatch.setattr(media_intelligence_api, "_require_business", lambda *_args: (True, None))
    monkeypatch.setattr(
        media_intelligence_api,
        "load_media_file",
        lambda *_args: (_ for _ in ()).throw(RuntimeError(MEDIA_INTERNAL_ERROR)),
    )

    response = _app(media_intelligence_api.media_intelligence_bp).test_client().get(
        "/api/media-intelligence/photos/asset-1/file",
        headers={"X-Request-ID": "media-photo-file-redaction"},
    )

    _assert_redacted(
        response,
        "media-photo-file-redaction",
        "Не удалось получить файл фотографии",
        MEDIA_INTERNAL_ERROR,
    )
    assert database.closed is True


def test_social_post_prepare_internal_error_is_redacted(monkeypatch):
    social_posts_api._WRITE_RATE_BUCKETS.clear()
    monkeypatch.setattr(social_posts_api, "_social_request_business_id", lambda: "business-1")
    monkeypatch.setattr(social_posts_api, "get_capability_access", lambda *_args, **_kwargs: {"allowed": True})
    monkeypatch.setattr(
        social_posts_api,
        "verify_session",
        lambda *_args: {"user_id": "owner-1"},
    )
    monkeypatch.setattr(
        social_posts_api,
        "prepare_social_posts_for_item",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError(SOCIAL_INTERNAL_ERROR)),
    )

    response = _app(social_posts_api.social_posts_bp).test_client().post(
        "/api/content-plans/items/item-1/social-posts/prepare",
        json={"platforms": ["telegram"]},
        headers={
            "Authorization": "Bearer synthetic-session",
            "X-Request-ID": "social-post-prepare-redaction",
        },
    )

    _assert_redacted(
        response,
        "social-post-prepare-redaction",
        "Не удалось подготовить публикацию",
        SOCIAL_INTERNAL_ERROR,
    )


def test_social_posts_bulk_prepare_internal_error_is_redacted(monkeypatch):
    social_posts_api._WRITE_RATE_BUCKETS.clear()
    monkeypatch.setattr(social_posts_api, "_social_request_business_id", lambda: "business-1")
    monkeypatch.setattr(social_posts_api, "get_capability_access", lambda *_args, **_kwargs: {"allowed": True})
    monkeypatch.setattr(
        social_posts_api,
        "verify_session",
        lambda *_args: {"user_id": "owner-1"},
    )
    monkeypatch.setattr(
        social_posts_api,
        "prepare_social_posts_for_items",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError(SOCIAL_INTERNAL_ERROR)),
    )

    response = _app(social_posts_api.social_posts_bp).test_client().post(
        "/api/content-plans/social-posts/bulk-prepare",
        json={"item_ids": ["item-1"], "platforms": ["telegram"]},
        headers={
            "Authorization": "Bearer synthetic-session",
            "X-Request-ID": "social-post-bulk-prepare-redaction",
        },
    )

    _assert_redacted(
        response,
        "social-post-bulk-prepare-redaction",
        "Не удалось подготовить публикации",
        SOCIAL_INTERNAL_ERROR,
    )


def test_media_settings_get_internal_error_is_redacted(monkeypatch):
    database = _Database()
    monkeypatch.setattr(media_intelligence_api, "DatabaseManager", lambda: database)
    monkeypatch.setattr(
        media_intelligence_api,
        "require_auth_from_request",
        lambda: {"user_id": "owner-1"},
    )
    monkeypatch.setattr(media_intelligence_api, "_require_business", lambda *_args: (True, None))
    monkeypatch.setattr(
        media_intelligence_api,
        "list_capability_settings",
        lambda *_args: (_ for _ in ()).throw(RuntimeError(MEDIA_INTERNAL_ERROR)),
    )

    response = _app(media_intelligence_api.media_intelligence_bp).test_client().get(
        "/api/media-intelligence/settings?business_id=business-1",
        headers={"X-Request-ID": "media-settings-get-redaction"},
    )

    _assert_redacted(
        response,
        "media-settings-get-redaction",
        "Не удалось получить настройки фотографий",
        MEDIA_INTERNAL_ERROR,
    )
    assert database.closed is True


def test_media_settings_post_internal_error_is_redacted(monkeypatch):
    database = _Database()
    monkeypatch.setattr(media_intelligence_api, "DatabaseManager", lambda: database)
    monkeypatch.setattr(
        media_intelligence_api,
        "require_auth_from_request",
        lambda: {"user_id": "owner-1"},
    )
    monkeypatch.setattr(media_intelligence_api, "_require_business", lambda *_args: (True, None))
    monkeypatch.setattr(
        media_intelligence_api,
        "set_capability_enabled",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError(MEDIA_INTERNAL_ERROR)),
    )

    response = _app(media_intelligence_api.media_intelligence_bp).test_client().post(
        "/api/media-intelligence/settings",
        json={"business_id": "business-1", "vision_enabled": True},
        headers={"X-Request-ID": "media-settings-post-redaction"},
    )

    _assert_redacted(
        response,
        "media-settings-post-redaction",
        "Не удалось сохранить настройки фотографий",
        MEDIA_INTERNAL_ERROR,
    )
    assert database.conn.rolled_back is True
    assert database.closed is True


def test_media_photos_list_internal_error_is_redacted(monkeypatch):
    database = _Database()
    monkeypatch.setattr(media_intelligence_api, "DatabaseManager", lambda: database)
    monkeypatch.setattr(
        media_intelligence_api,
        "require_auth_from_request",
        lambda: {"user_id": "owner-1"},
    )
    monkeypatch.setattr(media_intelligence_api, "_require_business", lambda *_args: (True, None))
    monkeypatch.setattr(
        media_intelligence_api,
        "list_photo_assets",
        lambda *_args: (_ for _ in ()).throw(RuntimeError(MEDIA_INTERNAL_ERROR)),
    )

    response = _app(media_intelligence_api.media_intelligence_bp).test_client().get(
        "/api/media-intelligence/photos?business_id=business-1",
        headers={"X-Request-ID": "media-photos-list-redaction"},
    )

    _assert_redacted(
        response,
        "media-photos-list-redaction",
        "Не удалось получить фотографии",
        MEDIA_INTERNAL_ERROR,
    )
    assert database.closed is True


def test_media_photo_create_internal_error_is_redacted(monkeypatch):
    database = _Database()
    monkeypatch.setattr(media_intelligence_api, "DatabaseManager", lambda: database)
    monkeypatch.setattr(
        media_intelligence_api,
        "require_auth_from_request",
        lambda: {"user_id": "owner-1"},
    )
    monkeypatch.setattr(media_intelligence_api, "_require_business", lambda *_args: (True, None))
    monkeypatch.setattr(media_intelligence_api, "is_capability_enabled", lambda *_args: True)
    monkeypatch.setattr(
        media_intelligence_api,
        "upsert_photo_asset",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError(MEDIA_INTERNAL_ERROR)),
    )

    response = _app(media_intelligence_api.media_intelligence_bp).test_client().post(
        "/api/media-intelligence/photos",
        json={"business_id": "business-1", "original_url": "https://example.test/photo.jpg"},
        headers={"X-Request-ID": "media-photo-create-redaction"},
    )

    _assert_redacted(
        response,
        "media-photo-create-redaction",
        "Не удалось добавить фотографию",
        MEDIA_INTERNAL_ERROR,
    )
    assert database.conn.rolled_back is True
    assert database.closed is True


def test_media_photo_analyze_internal_error_is_redacted(monkeypatch):
    database = _Database()
    monkeypatch.setattr(media_intelligence_api, "DatabaseManager", lambda: database)
    monkeypatch.setattr(
        media_intelligence_api,
        "require_auth_from_request",
        lambda: {"user_id": "owner-1"},
    )
    monkeypatch.setattr(media_intelligence_api, "_require_business", lambda *_args: (True, None))
    monkeypatch.setattr(
        media_intelligence_api,
        "load_business",
        lambda *_args: (_ for _ in ()).throw(RuntimeError(MEDIA_INTERNAL_ERROR)),
    )

    response = _app(media_intelligence_api.media_intelligence_bp).test_client().post(
        "/api/media-intelligence/photos/asset-1/analyze",
        json={"business_id": "business-1", "image_url": "https://example.test/photo.jpg"},
        headers={"X-Request-ID": "media-photo-analyze-redaction"},
    )

    _assert_redacted(
        response,
        "media-photo-analyze-redaction",
        "Не удалось проанализировать фотографию",
        MEDIA_INTERNAL_ERROR,
    )
    assert database.conn.rolled_back is True
    assert database.closed is True


def test_media_photo_version_internal_error_is_redacted(monkeypatch):
    database = _Database()
    monkeypatch.setattr(media_intelligence_api, "DatabaseManager", lambda: database)
    monkeypatch.setattr(
        media_intelligence_api,
        "require_auth_from_request",
        lambda: {"user_id": "owner-1"},
    )
    monkeypatch.setattr(media_intelligence_api, "_require_business", lambda *_args: (True, None))
    monkeypatch.setattr(
        media_intelligence_api,
        "create_photo_asset_version",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError(MEDIA_INTERNAL_ERROR)),
    )

    response = _app(media_intelligence_api.media_intelligence_bp).test_client().post(
        "/api/media-intelligence/photos/asset-1/version",
        json={"business_id": "business-1", "original_url": "https://example.test/version.jpg"},
        headers={"X-Request-ID": "media-photo-version-redaction"},
    )

    _assert_redacted(
        response,
        "media-photo-version-redaction",
        "Не удалось создать версию фотографии",
        MEDIA_INTERNAL_ERROR,
    )
    assert database.conn.rolled_back is True
    assert database.closed is True


def test_media_photo_usage_internal_error_is_redacted(monkeypatch):
    database = _Database()
    monkeypatch.setattr(media_intelligence_api, "DatabaseManager", lambda: database)
    monkeypatch.setattr(
        media_intelligence_api,
        "require_auth_from_request",
        lambda: {"user_id": "owner-1"},
    )
    monkeypatch.setattr(media_intelligence_api, "_require_business", lambda *_args: (True, None))
    monkeypatch.setattr(
        media_intelligence_api,
        "record_photo_usage",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError(MEDIA_INTERNAL_ERROR)),
    )

    response = _app(media_intelligence_api.media_intelligence_bp).test_client().post(
        "/api/media-intelligence/photos/asset-1/usage",
        json={"business_id": "business-1", "usage_type": "publication", "target_id": "item-1"},
        headers={"X-Request-ID": "media-photo-usage-redaction"},
    )

    _assert_redacted(
        response,
        "media-photo-usage-redaction",
        "Не удалось сохранить использование фотографии",
        MEDIA_INTERNAL_ERROR,
    )
    assert database.conn.rolled_back is True
    assert database.closed is True


def test_media_coverage_internal_error_is_redacted(monkeypatch):
    database = _Database()
    monkeypatch.setattr(media_intelligence_api, "DatabaseManager", lambda: database)
    monkeypatch.setattr(
        media_intelligence_api,
        "require_auth_from_request",
        lambda: {"user_id": "owner-1"},
    )
    monkeypatch.setattr(media_intelligence_api, "_require_business", lambda *_args: (True, None))
    monkeypatch.setattr(
        media_intelligence_api,
        "build_photo_coverage",
        lambda *_args: (_ for _ in ()).throw(RuntimeError(MEDIA_INTERNAL_ERROR)),
    )

    response = _app(media_intelligence_api.media_intelligence_bp).test_client().get(
        "/api/media-intelligence/coverage?business_id=business-1",
        headers={"X-Request-ID": "media-coverage-redaction"},
    )

    _assert_redacted(
        response,
        "media-coverage-redaction",
        "Не удалось получить покрытие фотографиями",
        MEDIA_INTERNAL_ERROR,
    )
    assert database.closed is True


def test_media_post_recommendation_internal_error_is_redacted(monkeypatch):
    database = _Database()
    monkeypatch.setattr(media_intelligence_api, "DatabaseManager", lambda: database)
    monkeypatch.setattr(
        media_intelligence_api,
        "require_auth_from_request",
        lambda: {"user_id": "owner-1"},
    )
    monkeypatch.setattr(media_intelligence_api, "_require_business", lambda *_args: (True, None))
    monkeypatch.setattr(
        media_intelligence_api,
        "recommend_media_for_post",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError(MEDIA_INTERNAL_ERROR)),
    )

    response = _app(media_intelligence_api.media_intelligence_bp).test_client().get(
        "/api/media-intelligence/posts/item-1/recommendation?business_id=business-1",
        headers={"X-Request-ID": "media-post-recommendation-redaction"},
    )

    _assert_redacted(
        response,
        "media-post-recommendation-redaction",
        "Не удалось подобрать фотографию для публикации",
        MEDIA_INTERNAL_ERROR,
    )
    assert database.closed is True


def test_telegram_radar_ingest_internal_error_is_redacted(monkeypatch):
    database = _Database()
    secret = "test-openclaw-secret"
    payload = {"business_id": "business-1", "text": "synthetic opportunity"}
    raw_body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

    monkeypatch.setenv("OPENCLAW_WEBHOOK_SECRET", secret)
    monkeypatch.setattr(telegram_opportunity_radar_api, "get_capability_access", lambda *_args, **_kwargs: {"allowed": True})
    monkeypatch.setattr(telegram_opportunity_radar_api, "DatabaseManager", lambda: database)
    monkeypatch.setattr(
        telegram_opportunity_radar_api,
        "ingest_opportunity",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError(RADAR_INTERNAL_ERROR)),
    )

    response = _app(telegram_opportunity_radar_api.telegram_opportunity_radar_bp).test_client().post(
        "/api/telegram-opportunity-radar/ingest",
        data=raw_body,
        content_type="application/json",
        headers={
            "X-OpenClaw-Signature": signature,
            "X-Request-ID": "telegram-radar-ingest-redaction",
        },
    )

    _assert_redacted(
        response,
        "telegram-radar-ingest-redaction",
        "Не удалось сохранить возможность",
        RADAR_INTERNAL_ERROR,
    )
    assert database.conn.rolled_back is True
    assert database.closed is True
