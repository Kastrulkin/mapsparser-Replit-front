from flask import Flask
import pytest

from src.api import social_posts_api


@pytest.fixture(autouse=True)
def disable_runtime_telegram_transport_probe(monkeypatch):
    monkeypatch.setenv("SOCIAL_POST_TELEGRAM_TRANSPORT_PROBE_ENABLED", "0")


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
    assert ("/api/content-plans/items/<item_id>/social-posts/prepare-preview", frozenset({"POST"})) in routes
    assert ("/api/social-posts/bulk-approve", frozenset({"POST"})) in routes
    assert ("/api/social-posts/bulk-queue", frozenset({"POST"})) in routes
    assert ("/api/social-posts/bulk-publish", frozenset({"POST"})) in routes
    assert ("/api/social-posts/bulk-publish-rehearsal", frozenset({"POST"})) in routes
    assert ("/api/social-posts/<post_id>/queue", frozenset({"POST"})) in routes
    assert ("/api/social-posts/<post_id>/publish-rehearsal", frozenset({"POST"})) in routes
    assert ("/api/social-posts/dispatch/preview", frozenset({"POST"})) in routes
    assert ("/api/social-posts/dispatch/run-once", frozenset({"POST"})) in routes
    assert ("/api/social-posts/metrics/run-once", frozenset({"POST"})) in routes
    assert ("/api/social-posts/runtime-status", frozenset({"GET"})) in routes
    assert ("/api/business/<business_id>/social-posts/channel-readiness", frozenset({"GET"})) in routes
    assert ("/api/business/<business_id>/social-posts/api-channel-preflight", frozenset({"GET"})) in routes
    assert ("/api/business/<business_id>/social-posts/openclaw-browser-check", frozenset({"GET"})) in routes
    assert ("/api/business/<business_id>/social-posts/launch-preflight", frozenset({"GET"})) in routes
    assert ("/api/social-posts/<post_id>", frozenset({"PATCH"})) in routes
    assert ("/api/social-posts/bulk-mark-manual-published", frozenset({"POST"})) in routes
    assert ("/api/social-posts/<post_id>/mark-supervised-blocked", frozenset({"POST"})) in routes
    assert ("/api/social-posts/<post_id>/supervised-task", frozenset({"POST"})) in routes
    assert ("/api/social-posts/<post_id>/attribution-events", frozenset({"POST"})) in routes
    assert ("/api/social-posts/bulk-attribution-events", frozenset({"POST"})) in routes
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
    assert payload["dispatch"]["allow_unscoped"] is False
    assert payload["dispatch"]["requires_business_scope"] is True
    assert payload["dispatch"]["blocked_without_scope"] is False
    assert payload["metrics"]["enabled"] is False
    assert payload["metrics"]["interval_sec"] == 60
    assert payload["metrics"]["batch_size"] == 500
    assert payload["metrics"]["business_scope"] == "biz-metrics"
    assert payload["metrics"]["scoped"] is True
    assert payload["metrics"]["allow_unscoped"] is False
    assert payload["metrics"]["requires_business_scope"] is True
    assert payload["metrics"]["blocked_without_scope"] is False
    assert payload["approval_required"] is True
    assert payload["browser_final_click_allowed"] is False
    assert payload["owner_status"]["schema"] == "localos_social_runtime_owner_status_v1"
    assert payload["owner_status"]["status"] == "dispatch_scoped"
    assert payload["owner_status"]["metrics_status"] == "metrics_disabled"
    assert payload["owner_status"]["external_publish_requires_approval"] is True
    assert payload["owner_status"]["browser_final_click_allowed"] is False
    assert payload["telegram_transport"]["schema"] == "localos_telegram_transport_status_v1"


def test_social_post_runtime_status_blocks_enabled_unscoped_dispatch(monkeypatch):
    monkeypatch.setenv("SOCIAL_POST_DISPATCH_ENABLED", "true")
    monkeypatch.delenv("SOCIAL_POST_DISPATCH_BUSINESS_ID", raising=False)
    monkeypatch.delenv("SOCIAL_POST_DISPATCH_ALLOW_UNSCOPED", raising=False)

    payload = social_posts_api.social_post_runtime_status_payload()

    assert payload["dispatch"]["enabled"] is True
    assert payload["dispatch"]["scoped"] is False
    assert payload["dispatch"]["allow_unscoped"] is False
    assert payload["dispatch"]["requires_business_scope"] is True
    assert payload["dispatch"]["blocked_without_scope"] is True
    assert payload["owner_status"]["status"] == "dispatch_guarded_without_scope"
    assert "SOCIAL_POST_DISPATCH_BUSINESS_ID" in payload["owner_status"]["next_action_ru"]


def test_social_post_runtime_status_reports_ready_telegram_transport(monkeypatch):
    class Response:
        status = 302

        def close(self):
            return None

    monkeypatch.setenv("TELEGRAM_HTTP_PROXY", "http://host.docker.internal:2081")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("SOCIAL_POST_TELEGRAM_TRANSPORT_PROBE_ENABLED", "1")
    monkeypatch.setattr(social_posts_api, "telegram_urlopen", lambda req, timeout=3: Response())

    payload = social_posts_api.social_post_runtime_status_payload()

    transport = payload["telegram_transport"]
    assert transport["proxy_configured"] is True
    assert transport["bot_token_present"] is True
    assert transport["read_only_probe_performed"] is True
    assert transport["ready"] is True
    assert transport["status"] == "ready"
    assert transport["http_status"] == 302


def test_social_post_runtime_status_reports_broken_telegram_transport(monkeypatch):
    def fail_probe(req, timeout=3):
        raise ConnectionResetError("connection reset")

    monkeypatch.setenv("TELEGRAM_HTTP_PROXY", "http://host.docker.internal:2081")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("SOCIAL_POST_TELEGRAM_TRANSPORT_PROBE_ENABLED", "1")
    monkeypatch.setattr(social_posts_api, "telegram_urlopen", fail_probe)

    payload = social_posts_api.social_post_runtime_status_payload()

    transport = payload["telegram_transport"]
    assert transport["proxy_configured"] is True
    assert transport["bot_token_present"] is True
    assert transport["read_only_probe_performed"] is True
    assert transport["ready"] is False
    assert transport["status"] == "ConnectionResetError"
    assert "localos-telegram-proxy.service" in transport["next_action_ru"]


def test_social_post_runtime_status_allows_explicit_unscoped_dispatch(monkeypatch):
    monkeypatch.setenv("SOCIAL_POST_DISPATCH_ENABLED", "true")
    monkeypatch.setenv("SOCIAL_POST_DISPATCH_ALLOW_UNSCOPED", "true")
    monkeypatch.delenv("SOCIAL_POST_DISPATCH_BUSINESS_ID", raising=False)

    payload = social_posts_api.social_post_runtime_status_payload()

    assert payload["dispatch"]["enabled"] is True
    assert payload["dispatch"]["scoped"] is False
    assert payload["dispatch"]["allow_unscoped"] is True
    assert payload["dispatch"]["requires_business_scope"] is False
    assert payload["dispatch"]["blocked_without_scope"] is False
    assert payload["owner_status"]["status"] == "dispatch_unscoped_allowed"
    assert payload["owner_status"]["tone"] == "warning"


def test_social_post_runtime_status_blocks_enabled_unscoped_metrics(monkeypatch):
    monkeypatch.setenv("SOCIAL_POST_METRICS_ENABLED", "true")
    monkeypatch.delenv("SOCIAL_POST_METRICS_BUSINESS_ID", raising=False)
    monkeypatch.delenv("SOCIAL_POST_METRICS_ALLOW_UNSCOPED", raising=False)

    payload = social_posts_api.social_post_runtime_status_payload()

    assert payload["metrics"]["enabled"] is True
    assert payload["metrics"]["scoped"] is False
    assert payload["metrics"]["allow_unscoped"] is False
    assert payload["metrics"]["requires_business_scope"] is True
    assert payload["metrics"]["blocked_without_scope"] is True
    assert payload["owner_status"]["metrics_status"] == "metrics_guarded_without_scope"


def test_social_post_runtime_status_allows_explicit_unscoped_metrics(monkeypatch):
    monkeypatch.setenv("SOCIAL_POST_METRICS_ENABLED", "true")
    monkeypatch.setenv("SOCIAL_POST_METRICS_ALLOW_UNSCOPED", "true")
    monkeypatch.delenv("SOCIAL_POST_METRICS_BUSINESS_ID", raising=False)

    payload = social_posts_api.social_post_runtime_status_payload()

    assert payload["metrics"]["enabled"] is True
    assert payload["metrics"]["scoped"] is False
    assert payload["metrics"]["allow_unscoped"] is True
    assert payload["metrics"]["requires_business_scope"] is False
    assert payload["metrics"]["blocked_without_scope"] is False


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
            "openclaw_browser_readiness": {
                "ready": False,
                "status": "manual_fallback",
                "browser_final_click_allowed": False,
            },
            "summary": {"api_ready": 0, "api_needs_attention": 1},
        },
    )

    response = app.test_client().get("/api/business/biz-1/social-posts/channel-readiness")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["channel_readiness"][0]["platform"] == "telegram"
    assert payload["openclaw_browser_readiness"]["status"] == "manual_fallback"
    assert payload["openclaw_browser_readiness"]["browser_final_click_allowed"] is False
    assert payload["summary"]["api_needs_attention"] == 1


def test_social_post_openclaw_browser_check_endpoint_is_read_only(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(social_posts_api.social_posts_bp)
    monkeypatch.setattr(social_posts_api, "_require_auth", lambda: ({"user_id": "user-1"}, None))
    captured = {}

    def fake_check(user_id, business_id):
        captured["user_id"] = user_id
        captured["business_id"] = business_id
        return {
            "business_id": business_id,
            "read_only": True,
            "external_publish_performed": False,
            "browser_final_click_allowed": False,
            "openclaw_browser_readiness": {
                "ready": True,
                "status": "ready",
                "browser_final_click_allowed": False,
            },
        }

    monkeypatch.setattr(social_posts_api, "check_social_openclaw_browser_readiness", fake_check)

    response = app.test_client().get("/api/business/biz-1/social-posts/openclaw-browser-check")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["read_only"] is True
    assert payload["external_publish_performed"] is False
    assert payload["openclaw_browser_readiness"]["status"] == "ready"
    assert captured == {"user_id": "user-1", "business_id": "biz-1"}


def test_social_post_api_channel_preflight_endpoint_is_read_only(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(social_posts_api.social_posts_bp)
    monkeypatch.setattr(social_posts_api, "_require_auth", lambda: ({"user_id": "user-1"}, None))
    captured = {}

    def fake_preflight(user_id, business_id):
        captured["user_id"] = user_id
        captured["business_id"] = business_id
        return {
            "business_id": business_id,
            "read_only": True,
            "external_publish_performed": False,
            "human_approval_required_for_publish": True,
            "api_preflight": [
                {"platform": "telegram", "ready": True, "status": "ready"},
                {"platform": "vk", "ready": False, "status": "missing_permissions"},
            ],
            "summary": {"checked": 2, "ready": 1, "needs_attention": 1},
        }

    monkeypatch.setattr(social_posts_api, "check_social_api_channel_preflight", fake_preflight)

    response = app.test_client().get("/api/business/biz-1/social-posts/api-channel-preflight")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["read_only"] is True
    assert payload["external_publish_performed"] is False
    assert payload["api_preflight"][0]["platform"] == "telegram"
    assert payload["summary"]["needs_attention"] == 1
    assert captured == {"user_id": "user-1", "business_id": "biz-1"}


def test_social_post_launch_preflight_endpoint_is_read_only(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(social_posts_api.social_posts_bp)
    monkeypatch.setenv("SOCIAL_POST_PREFLIGHT_BATCH_SIZE", "25")
    monkeypatch.setattr(social_posts_api, "_require_auth", lambda: ({"user_id": "user-1"}, None))
    captured = {}

    def fake_preflight(user_id, business_id, batch_size=10):
        captured["user_id"] = user_id
        captured["business_id"] = business_id
        captured["batch_size"] = batch_size
        return {
            "business_id": business_id,
            "status": "ready_for_api_dispatch",
            "safe_to_enable_scoped_dispatch": True,
            "recommended_env": {
                "dispatch": {"SOCIAL_POST_DISPATCH_BUSINESS_ID": business_id},
                "metrics": {"SOCIAL_POST_METRICS_BUSINESS_ID": business_id},
            },
            "safety": {"browser_final_click_allowed": False},
            "summary": {"due_posts": 1},
        }

    monkeypatch.setattr(social_posts_api, "get_social_launch_preflight", fake_preflight)

    response = app.test_client().get("/api/business/biz-1/social-posts/launch-preflight")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["status"] == "ready_for_api_dispatch"
    assert payload["recommended_env"]["dispatch"]["SOCIAL_POST_DISPATCH_BUSINESS_ID"] == "biz-1"
    assert payload["safety"]["browser_final_click_allowed"] is False
    assert captured == {"user_id": "user-1", "business_id": "biz-1", "batch_size": 25}


def test_social_post_dispatch_run_once_requires_explicit_approval(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(social_posts_api.social_posts_bp)
    monkeypatch.setattr(social_posts_api, "_require_auth", lambda: ({"user_id": "user-1"}, None))

    def fail_if_called(*args, **kwargs):
        raise AssertionError("dispatch must not run without explicit approval")

    monkeypatch.setattr(social_posts_api, "run_scoped_social_dispatch_once", fail_if_called)

    response = app.test_client().post(
        "/api/social-posts/dispatch/run-once",
        json={"business_id": "biz-1", "approved": False},
    )

    assert response.status_code == 403
    assert "подтверждение" in response.get_json()["error"]


def test_social_post_dispatch_run_once_runs_scoped_first_cycle(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(social_posts_api.social_posts_bp)
    monkeypatch.setattr(social_posts_api, "_require_auth", lambda: ({"user_id": "user-1"}, None))
    captured = {}

    def fake_run_once(user_id, business_id, batch_size=10, approved=False, approval_text=""):
        captured["user_id"] = user_id
        captured["business_id"] = business_id
        captured["batch_size"] = batch_size
        captured["approved"] = approved
        captured["approval_text"] = approval_text
        return {
            "business_id": business_id,
            "approved": approved,
            "dispatch_result": {
                "picked": 2,
                "published": 1,
                "supervised": 1,
                "manual": 0,
                "failed": 0,
            },
            "browser_final_click_allowed": False,
            "message_ru": "Первый scoped цикл выполнен.",
        }

    monkeypatch.setattr(social_posts_api, "run_scoped_social_dispatch_once", fake_run_once)

    response = app.test_client().post(
        "/api/social-posts/dispatch/run-once",
        json={"business_id": "biz-1", "batch_size": 500, "approved": True, "approval_text": "ПУБЛИКУЮ"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["dispatch_result"]["published"] == 1
    assert payload["browser_final_click_allowed"] is False
    assert captured == {
        "user_id": "user-1",
        "business_id": "biz-1",
        "batch_size": 50,
        "approved": True,
        "approval_text": "ПУБЛИКУЮ",
    }


def test_social_post_metrics_run_once_requires_explicit_approval(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(social_posts_api.social_posts_bp)
    monkeypatch.setattr(social_posts_api, "_require_auth", lambda: ({"user_id": "user-1"}, None))

    def fail_if_called(*args, **kwargs):
        raise AssertionError("metrics collection must not run without explicit approval")

    monkeypatch.setattr(social_posts_api, "run_scoped_social_metrics_once", fail_if_called)

    response = app.test_client().post(
        "/api/social-posts/metrics/run-once",
        json={"business_id": "biz-1", "approved": False},
    )

    assert response.status_code == 403
    assert "подтверждение" in response.get_json()["error"]


def test_social_post_metrics_run_once_collects_scoped_business(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(social_posts_api.social_posts_bp)
    monkeypatch.setattr(social_posts_api, "_require_auth", lambda: ({"user_id": "user-1"}, None))
    captured = {}

    def fake_run_once(user_id, business_id, batch_size=25, approved=False):
        captured["user_id"] = user_id
        captured["business_id"] = business_id
        captured["batch_size"] = batch_size
        captured["approved"] = approved
        return {
            "business_id": business_id,
            "approved": approved,
            "external_publish_performed": False,
            "metrics_result": {
                "picked": 2,
                "collected": 2,
                "failed": 0,
                "result_summaries_ru": [
                    "VK: API-снимок обновлён; заявки 1, обращения 0, комментарии 3, охват 120.",
                ],
                "result_summaries_en": [
                    "VK: API snapshot updated; leads 1, inquiries 0, comments 3, reach 120.",
                ],
            },
            "message_ru": "Сбор реакций выполнен.",
        }

    monkeypatch.setattr(social_posts_api, "run_scoped_social_metrics_once", fake_run_once)

    response = app.test_client().post(
        "/api/social-posts/metrics/run-once",
        json={"business_id": "biz-1", "batch_size": 500, "approved": True},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["external_publish_performed"] is False
    assert payload["metrics_result"]["collected"] == 2
    assert payload["metrics_result"]["result_summaries_ru"][0].startswith("VK: API-снимок")
    assert captured == {"user_id": "user-1", "business_id": "biz-1", "batch_size": 100, "approved": True}


def test_social_post_mark_supervised_blocked_endpoint_records_manual_fallback(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(social_posts_api.social_posts_bp)
    monkeypatch.setattr(social_posts_api, "_require_auth", lambda: ({"user_id": "user-1"}, None))
    captured = {}

    def fake_mark_blocked(user_id, post_id, reason="", blocked_source="manual"):
        captured["user_id"] = user_id
        captured["post_id"] = post_id
        captured["reason"] = reason
        captured["blocked_source"] = blocked_source
        return {
            "id": post_id,
            "status": "needs_manual_publish",
            "last_error": reason,
            "metadata_json": {
                "manual_fallback": {"required": True, "reason": reason},
                "browser_final_click_allowed": False,
            },
        }

    monkeypatch.setattr(social_posts_api, "mark_supervised_publish_blocked", fake_mark_blocked)

    response = app.test_client().post(
        "/api/social-posts/post-1/mark-supervised-blocked",
        json={"reason": "captcha", "blocked_source": "openclaw"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["post"]["status"] == "needs_manual_publish"
    assert payload["post"]["metadata_json"]["browser_final_click_allowed"] is False
    assert captured == {
        "user_id": "user-1",
        "post_id": "post-1",
        "reason": "captcha",
        "blocked_source": "openclaw",
    }


def test_social_post_create_supervised_task_requires_explicit_approval(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(social_posts_api.social_posts_bp)
    monkeypatch.setattr(social_posts_api, "_require_auth", lambda: ({"user_id": "user-1"}, None))

    def fail_if_called(*args, **kwargs):
        raise AssertionError("supervised task must not run without explicit approval")

    monkeypatch.setattr(social_posts_api, "create_supervised_publish_task", fail_if_called)

    response = app.test_client().post(
        "/api/social-posts/post-1/supervised-task",
        json={"approved": False},
    )

    assert response.status_code == 403
    assert "подтверждение" in response.get_json()["error"]


def test_social_post_create_supervised_task_endpoint_returns_post(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(social_posts_api.social_posts_bp)
    monkeypatch.setattr(social_posts_api, "_require_auth", lambda: ({"user_id": "user-1"}, None))
    captured = {}

    def fake_create(user_id, post_id, approved=False):
        captured["user_id"] = user_id
        captured["post_id"] = post_id
        captured["approved"] = approved
        return {
            "id": post_id,
            "status": "needs_supervised_publish",
            "automation_task_id": "task-1",
            "metadata_json": {"browser_final_click_allowed": False},
        }

    monkeypatch.setattr(social_posts_api, "create_supervised_publish_task", fake_create)

    response = app.test_client().post(
        "/api/social-posts/post-1/supervised-task",
        json={"approved": True},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["post"]["automation_task_id"] == "task-1"
    assert payload["post"]["metadata_json"]["browser_final_click_allowed"] is False
    assert captured == {"user_id": "user-1", "post_id": "post-1", "approved": True}
