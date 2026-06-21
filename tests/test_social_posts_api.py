from flask import Flask

from src.api import social_posts_api


def test_social_post_write_rate_limit_allows_first_request(monkeypatch):
    social_posts_api._WRITE_RATE_BUCKETS.clear()
    monkeypatch.setenv("SOCIAL_POST_WRITE_RATE_LIMIT", "1")
    monkeypatch.setenv("SOCIAL_POST_WRITE_RATE_WINDOW_SEC", "60")

    assert social_posts_api._check_write_rate_limit("user-1", "publish") is None


def test_social_post_write_rate_limit_blocks_repeated_action(monkeypatch):
    social_posts_api._WRITE_RATE_BUCKETS.clear()
    monkeypatch.setenv("SOCIAL_POST_WRITE_RATE_LIMIT", "1")
    monkeypatch.setenv("SOCIAL_POST_WRITE_RATE_WINDOW_SEC", "60")

    assert social_posts_api._check_write_rate_limit("user-1", "publish") is None
    app = Flask(__name__)
    with app.app_context():
        error_response = social_posts_api._check_write_rate_limit("user-1", "publish")

    assert error_response is not None
    assert error_response[1] == 429


def test_social_post_routes_include_bulk_and_attribution_endpoints():
    app = Flask(__name__)
    app.register_blueprint(social_posts_api.social_posts_bp)
    routes = {
        (str(rule), frozenset(rule.methods - {"HEAD", "OPTIONS"}))
        for rule in app.url_map.iter_rules()
    }

    assert ("/api/content-plans/social-posts/bulk-prepare", frozenset({"POST"})) in routes
    assert ("/api/social-posts/bulk-approve", frozenset({"POST"})) in routes
    assert ("/api/social-posts/bulk-queue", frozenset({"POST"})) in routes
    assert ("/api/social-posts/bulk-publish", frozenset({"POST"})) in routes
    assert ("/api/social-posts/<post_id>/queue", frozenset({"POST"})) in routes
    assert ("/api/social-posts/dispatch/preview", frozenset({"POST"})) in routes
    assert ("/api/social-posts/runtime-status", frozenset({"GET"})) in routes
    assert ("/api/business/<business_id>/social-posts/channel-readiness", frozenset({"GET"})) in routes
    assert ("/api/social-posts/<post_id>", frozenset({"PATCH"})) in routes
    assert ("/api/social-posts/bulk-mark-manual-published", frozenset({"POST"})) in routes
    assert ("/api/social-posts/<post_id>/attribution-events", frozenset({"POST"})) in routes
    assert ("/api/content-plans/<plan_id>/social-posts/recommend-next-plan", frozenset({"POST"})) in routes
    assert ("/api/content-plans/<plan_id>/social-posts/apply-recommendation", frozenset({"POST"})) in routes


def test_social_post_runtime_status_reflects_worker_flags(monkeypatch):
    monkeypatch.setenv("SOCIAL_POST_DISPATCH_ENABLED", "true")
    monkeypatch.setenv("SOCIAL_POST_DISPATCH_INTERVAL_SEC", "5")
    monkeypatch.setenv("SOCIAL_POST_DISPATCH_BATCH_SIZE", "250")
    monkeypatch.setenv("SOCIAL_POST_DISPATCH_BUSINESS_ID", "biz-test")
    monkeypatch.setenv("SOCIAL_POST_METRICS_ENABLED", "0")
    monkeypatch.setenv("SOCIAL_POST_METRICS_INTERVAL_SEC", "20")
    monkeypatch.setenv("SOCIAL_POST_METRICS_BATCH_SIZE", "999")
    monkeypatch.setenv("SOCIAL_POST_METRICS_BUSINESS_ID", "biz-metrics")

    payload = social_posts_api.social_post_runtime_status_payload()

    assert payload["dispatch"]["enabled"] is True
    assert payload["dispatch"]["interval_sec"] == 15
    assert payload["dispatch"]["batch_size"] == 200
    assert payload["dispatch"]["business_scope"] == "biz-test"
    assert payload["dispatch"]["scoped"] is True
    assert payload["metrics"]["enabled"] is False
    assert payload["metrics"]["interval_sec"] == 60
    assert payload["metrics"]["batch_size"] == 500
    assert payload["metrics"]["business_scope"] == "biz-metrics"
    assert payload["metrics"]["scoped"] is True
    assert payload["approval_required"] is True
    assert payload["browser_final_click_allowed"] is False


def test_social_post_channel_readiness_endpoint_is_read_only(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(social_posts_api.social_posts_bp)
    monkeypatch.setattr(social_posts_api, "_require_auth", lambda: ({"user_id": "user-1"}, None))
    monkeypatch.setattr(
        social_posts_api,
        "get_social_channel_readiness",
        lambda user_id, business_id: {
            "channel_readiness": [
                {
                    "platform": "telegram",
                    "publish_mode": "api",
                    "ready": False,
                    "status": "missing_keys",
                    "message_ru": "Telegram: нужны ключи.",
                    "message_en": "Telegram: keys required.",
                }
            ],
            "summary": {"api_ready": 0, "api_needs_attention": 1},
        },
    )

    response = app.test_client().get("/api/business/biz-1/social-posts/channel-readiness")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["channel_readiness"][0]["platform"] == "telegram"
    assert payload["summary"]["api_needs_attention"] == 1
