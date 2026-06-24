import json
import sys
from datetime import date, timedelta

import pytest

import services.social_post_service as social_post_service
from services.social_post_service import (
    _build_openclaw_supervised_task_payload,
    _build_plan_recommendation,
    _add_channel_breakdown_to_changes,
    _build_social_launch_preflight_payload,
    _channel_readiness_message,
    _dispatch_action_for_status,
    _social_dispatch_execution_report,
    _social_dispatch_followup_actions,
    _social_dispatch_result_summaries,
    _social_metrics_result_summaries,
    _dispatch_preview_readiness,
    _merge_metric_totals_into_posts,
    _meta_channel_readiness,
    _meta_publish_status,
    openclaw_browser_capability_status,
    _publish_external_account_post,
    _build_social_learning_insights,
    _collect_telegram_post_metrics,
    _collect_vk_post_metrics,
    _provider_metrics_placeholder,
    _preview_dispatch_decision,
    _dispatch_preview_first_cycle_steps,
    _telegram_publish_error_state,
    _queue_preflight_block,
    _record_social_supervised_handoff_ledger,
    _social_supervised_blocked_metadata,
    _social_publish_evidence,
    _social_learning_readiness,
    _social_recommendation_application_preview,
    _social_goal_progress,
    _social_first_api_proof_dossier,
    _social_first_api_publish_readiness,
    _social_openclaw_browser_readiness,
    _api_preflight_blocked_due_posts,
    _status_after_social_text_edit,
    _channel_readiness,
    _channel_readiness_next_action,
    _channel_readiness_setup_steps,
    _maps_connection_checks,
    _meta_connection_checks,
    _telegram_connection_checks,
    _supervised_publish_metadata,
    _supervised_publish_state,
    _vk_connection_checks,
    _vk_publish_binding,
    apply_social_post_recommendation,
    approve_social_post,
    _build_next_plan_changes,
    _attribution_metrics_for_post,
    build_social_queue_groups,
    check_social_openclaw_browser_readiness,
    collect_due_social_post_metrics,
    create_supervised_publish_task,
    default_publish_mode,
    dispatch_due_social_posts,
    ensure_social_post_tables,
    next_action_for_social_post,
    openclaw_browser_available,
    preview_due_social_post_dispatch,
    preview_social_posts_for_item,
    publish_social_post,
    queue_social_post,
    rehearse_social_post_publish,
    rehearse_social_posts_publish,
    mark_manual_published,
    record_social_post_attribution_event,
    record_social_post_attribution_events,
    run_scoped_social_dispatch_once,
    run_scoped_social_metrics_once,
    _vk_post_url,
)


class FakeTableCursor:
    def __init__(self, existing_tables):
        self.existing_tables = set(existing_tables)
        self.current_table = ""

    def execute(self, query, params=None):
        if "CREATE " in query.upper() or "ALTER " in query.upper() or "DROP " in query.upper():
            raise AssertionError("social post service must not create schema at runtime")
        self.current_table = str((params or [""])[0]).removeprefix("public.")

    def fetchone(self):
        if self.current_table in self.existing_tables:
            return (self.current_table,)
        return (None,)


class FakeRecommendationConn:
    def __init__(self):
        today = date.today()
        self.items = {
            "future-draft": {
                "id": "future-draft",
                "plan_id": "plan-1",
                "theme": "Будущая тема",
                "goal": "Старый goal",
                "scheduled_for": today + timedelta(days=2),
                "status": "draft",
                "usernews_id": "",
            },
            "past-draft": {
                "id": "past-draft",
                "plan_id": "plan-1",
                "theme": "Прошлая тема",
                "goal": "Старый goal",
                "scheduled_for": today - timedelta(days=2),
                "status": "draft",
                "usernews_id": "",
            },
            "future-published": {
                "id": "future-published",
                "plan_id": "plan-1",
                "theme": "Опубликованная тема",
                "goal": "Старый goal",
                "scheduled_for": today + timedelta(days=3),
                "status": "published",
                "usernews_id": "",
            },
            "future-news": {
                "id": "future-news",
                "plan_id": "plan-1",
                "theme": "Тема с новостью",
                "goal": "Старый goal",
                "scheduled_for": today + timedelta(days=4),
                "status": "draft",
                "usernews_id": "news-1",
            },
        }
        self.committed = False
        self.rolled_back = False
        self.edited_plan_json = ""

    def cursor(self):
        return FakeRecommendationCursor(self)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class FakeRecommendationCursor:
    def __init__(self, conn):
        self.conn = conn
        self.next_row = None
        self.next_rows = []
        self.description = []

    def execute(self, query, params=None):
        normalized = " ".join(str(query).split()).lower()
        if "select id, theme, scheduled_for, status, usernews_id from contentplanitems" in normalized:
            plan_id, item_ids = params
            self.description = [("id",), ("theme",), ("scheduled_for",), ("status",), ("usernews_id",)]
            self.next_rows = [
                (
                    item["id"],
                    item["theme"],
                    item["scheduled_for"],
                    item["status"],
                    item["usernews_id"],
                )
                for item_id in item_ids
                for item in [self.conn.items.get(str(item_id))]
                if item and item["plan_id"] == plan_id
            ]
            return
        if "update contentplanitems" in normalized:
            assert "scheduled_for >= current_date" in normalized
            proposed_goal, item_id, plan_id = params
            item = self.conn.items.get(str(item_id))
            today = date.today()
            eligible = (
                item
                and item["plan_id"] == plan_id
                and not str(item.get("usernews_id") or "")
                and str(item.get("status") or "") not in ("skipped", "published")
                and item.get("scheduled_for") >= today
            )
            if eligible:
                item["goal"] = proposed_goal
                self.description = [("id",), ("theme",), ("goal",)]
                self.next_row = (item["id"], item["theme"], item["goal"])
            else:
                self.next_row = None
            return
        if "update contentplans" in normalized:
            self.conn.edited_plan_json = str(params[0])
            self.next_row = None
            return
        raise AssertionError(f"unexpected SQL in recommendation fake: {query}")

    def fetchone(self):
        return self.next_row

    def fetchall(self):
        return self.next_rows


class FakeRecommendationDB:
    last_conn = None

    def __init__(self):
        self.conn = FakeRecommendationConn()
        FakeRecommendationDB.last_conn = self.conn

    def close(self):
        pass


class FakeMetricTotalsCursor:
    def __init__(self):
        self.params = None

    def execute(self, query, params=None):
        normalized = " ".join(str(query).split()).lower()
        assert "from social_post_metrics" in normalized
        self.params = params

    def fetchall(self):
        return [
            {
                "social_post_id": "post-lead",
                "views": 12,
                "impressions": 12,
                "reach": 10,
                "likes": 1,
                "comments": 2,
                "shares": 1,
                "clicks": 3,
                "inquiries": 1,
                "leads": 2,
            }
        ]


class FakeAttributionMetricsCursor:
    def execute(self, query, params=None):
        self.query = query
        self.params = params

    def fetchall(self):
        return [
            {"event_type": "view", "total": 25},
            {"event_type": "like", "total": 4},
            {"event_type": "comment", "total": 2},
            {"event_type": "share", "total": 1},
            {"event_type": "click", "total": 3},
            {"event_type": "inquiry", "total": 1},
            {"event_type": "lead", "total": 1},
        ]


class FakeAttributionEventConn:
    def __init__(self):
        self.committed = False
        self.rolled_back = False
        self.inserted_event = None
        self.inserted_events = []
        self.metric_upserted = False

    def cursor(self):
        return FakeAttributionEventCursor(self)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class FakeAttributionEventCursor:
    def __init__(self, conn):
        self.conn = conn
        self.next_row = None
        self.metric_query_count = 0

    def execute(self, query, params=None):
        normalized = " ".join(str(query).split()).lower()
        if "insert into social_post_attribution_events" in normalized:
            self.conn.inserted_event = params
            self.conn.inserted_events.append(params)
            self.next_row = {
                "id": params[0],
                "social_post_id": params[1],
                "business_id": params[2],
                "event_type": params[3],
                "event_source": params[4],
                "value": params[5],
                "metadata_json": params[6],
                "event_at": "2026-06-21T10:00:00+00:00",
            }
            return
        if "insert into social_post_metrics" in normalized:
            self.conn.metric_upserted = True
            self.next_row = None
            return
        if "from social_post_attribution_events" in normalized:
            self.metric_query_count += 1
            self.next_row = None
            return
        raise AssertionError(f"unexpected SQL: {query}")

    def fetchone(self):
        return self.next_row

    def fetchall(self):
        return [
            {"event_type": "lead", "total": 2},
            {"event_type": "inquiry", "total": 1},
            {"event_type": "comment", "total": 3},
        ]


class FakeAttributionEventDB:
    last_conn = None

    def __init__(self):
        self.conn = FakeAttributionEventConn()
        FakeAttributionEventDB.last_conn = self.conn

    def close(self):
        pass


class FakeManualPublishedConn:
    def __init__(self):
        self.committed = False
        self.rolled_back = False
        self.updated_row = {}

    def cursor(self):
        return FakeManualPublishedCursor(self)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class FakeManualPublishedCursor:
    def __init__(self, conn):
        self.conn = conn
        self.next_row = None
        self.description = []

    def execute(self, query, params=None):
        normalized = " ".join(str(query).split()).lower()
        if "update social_posts" in normalized and "set status = 'published'" in normalized:
            self.conn.updated_row = {
                "id": params[4],
                "business_id": "biz-1",
                "platform": "yandex_maps",
                "status": "published",
                "metadata_json": params[3],
                "provider_post_url": params[1],
                "provider_post_id": params[2],
            }
            self.next_row = self.conn.updated_row
            return
        raise AssertionError(f"unexpected SQL: {query}")

    def fetchone(self):
        return self.next_row


class FakeManualPublishedDB:
    last_conn = None

    def __init__(self):
        self.conn = FakeManualPublishedConn()
        FakeManualPublishedDB.last_conn = self.conn

    def close(self):
        pass


class FakeSocialLedgerCursor:
    def __init__(self, table_exists=True):
        self.table_exists = table_exists
        self.inserted = []
        self.last_query = ""

    def execute(self, query, params=None):
        self.last_query = " ".join(str(query).split()).lower()
        if "to_regclass" in self.last_query:
            self.next_row = ("agent_action_ledger",) if self.table_exists else (None,)
            return
        if "insert into agent_action_ledger" in self.last_query:
            self.inserted.append(params)
            self.next_row = None
            return
        raise AssertionError(f"unexpected SQL: {query}")

    def fetchone(self):
        return getattr(self, "next_row", None)


class FakeSocialOutboxCursor:
    def __init__(self, table_exists=True):
        self.table_exists = table_exists
        self.inserted = []
        self.last_query = ""

    def execute(self, query, params=None):
        self.last_query = " ".join(str(query).split()).lower()
        if "to_regclass" in self.last_query:
            self.next_row = ("action_callback_outbox",) if self.table_exists else (None,)
            return
        if "insert into action_callback_outbox" in self.last_query:
            self.inserted.append(params)
            self.next_row = {"id": "outbox-1"}
            return
        raise AssertionError(f"unexpected SQL: {query}")

    def fetchone(self):
        return getattr(self, "next_row", None)


class FakeQueueFallbackConn:
    def __init__(self):
        self.committed = False
        self.rolled_back = False
        self.updated_row = {}

    def cursor(self):
        return FakeQueueFallbackCursor(self)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class FakeQueueFallbackCursor:
    def __init__(self, conn):
        self.conn = conn
        self.next_row = None

    def execute(self, query, params=None):
        normalized = " ".join(str(query).split()).lower()
        if "update social_posts" in normalized and "needs_manual_publish" in normalized:
            self.conn.updated_row = {
                "id": "post-api",
                "business_id": "biz-1",
                "platform": "telegram",
                "publish_mode": "api",
                "status": "needs_manual_publish",
                "metadata_json": params[0],
                "last_error": params[1],
            }
            self.next_row = self.conn.updated_row
            return
        raise AssertionError(f"unexpected SQL: {query}")

    def fetchone(self):
        return self.next_row


class FakeQueueFallbackDB:
    last_conn = None

    def __init__(self):
        self.conn = FakeQueueFallbackConn()
        FakeQueueFallbackDB.last_conn = self.conn

    def close(self):
        pass


class FakePreparePreviewConn:
    def __init__(self):
        self.committed = False
        self.rolled_back = False
        self.cursor_obj = FakePreparePreviewCursor()

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class FakePreparePreviewCursor:
    description = (
        ("id",),
        ("platform",),
        ("status",),
        ("base_text",),
        ("platform_text",),
        ("media_json",),
    )

    def execute(self, query, params=None):
        self.last_query = str(query)
        self.last_params = tuple(params or ())

    def fetchall(self):
        return []

    def fetchone(self):
        return None


class FakePreparePreviewDB:
    last_conn = None

    def __init__(self):
        self.conn = FakePreparePreviewConn()
        FakePreparePreviewDB.last_conn = self.conn

    def close(self):
        pass


class FakeApproveGuardConn:
    def __init__(self):
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return object()

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class FakeApproveGuardDB:
    last_conn = None

    def __init__(self):
        self.conn = FakeApproveGuardConn()
        FakeApproveGuardDB.last_conn = self.conn

    def close(self):
        pass


class FakePublishEmptyCopyConn:
    def __init__(self):
        self.committed = False
        self.rolled_back = False
        self.updated_row = {}

    def cursor(self):
        return FakePublishEmptyCopyCursor(self)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class FakePublishEmptyCopyCursor:
    def __init__(self, conn):
        self.conn = conn
        self.next_row = None

    def execute(self, query, params=None):
        normalized = " ".join(str(query).split()).lower()
        if "update social_posts" in normalized and "status = 'needs_review'" in normalized:
            self.conn.updated_row = {
                "id": "post-empty",
                "business_id": "biz-1",
                "platform": "telegram",
                "publish_mode": "api",
                "status": "needs_review",
                "platform_text": "",
                "base_text": "",
                "last_error": params[0],
            }
            self.next_row = self.conn.updated_row
            return
        raise AssertionError(f"unexpected SQL: {query}")

    def fetchone(self):
        return self.next_row


class FakePublishEmptyCopyDB:
    last_conn = None

    def __init__(self):
        self.conn = FakePublishEmptyCopyConn()
        FakePublishEmptyCopyDB.last_conn = self.conn

    def close(self):
        pass


class FakeDispatchScopeConn:
    def __init__(self):
        self.cursor_obj = FakeDispatchScopeCursor()

    def cursor(self):
        return self.cursor_obj


class FakeDispatchScopeCursor:
    last_query = ""
    last_params = ()

    def execute(self, query, params=None):
        FakeDispatchScopeCursor.last_query = str(query)
        FakeDispatchScopeCursor.last_params = tuple(params or ())

    def fetchall(self):
        return []


class FakeDispatchScopeDB:
    last_conn = None

    def __init__(self):
        self.conn = FakeDispatchScopeConn()
        FakeDispatchScopeDB.last_conn = self.conn

    def close(self):
        pass


def test_default_publish_mode_uses_api_for_connected_social_channels(monkeypatch):
    monkeypatch.delenv("OPENCLAW_BROWSER_USE_ENABLED", raising=False)
    monkeypatch.delenv("OPENCLAW_BROWSER_USE_AVAILABLE", raising=False)

    assert default_publish_mode("telegram") == "api"
    assert default_publish_mode("vk") == "api"
    assert default_publish_mode("google_business") == "api"


def test_default_publish_mode_keeps_yandex_manual_when_browser_capability_is_absent(monkeypatch):
    monkeypatch.delenv("OPENCLAW_BROWSER_USE_ENABLED", raising=False)
    monkeypatch.delenv("OPENCLAW_BROWSER_USE_AVAILABLE", raising=False)
    monkeypatch.delenv("OPENCLAW_CAPABILITY_CATALOG_URL", raising=False)
    monkeypatch.delenv("OPENCLAW_BASE_URL", raising=False)
    monkeypatch.delenv("OPENCLAW_SANDBOX_BRIDGE_URL", raising=False)

    assert default_publish_mode("yandex_maps") == "manual"
    assert default_publish_mode("two_gis") == "manual"


def test_openclaw_browser_available_detects_live_catalog_action(monkeypatch):
    monkeypatch.delenv("OPENCLAW_BROWSER_USE_ENABLED", raising=False)
    monkeypatch.delenv("OPENCLAW_BROWSER_USE_AVAILABLE", raising=False)

    def fetcher():
        return {
            "actions": [
                {
                    "openclaw_action_ref": "openclaw.browser.fill_form",
                    "title": "Browser supervised publish",
                    "service": "browser",
                    "localos_capability": "social.post.publish_supervised_browser",
                    "status": "available",
                }
            ]
        }

    assert openclaw_browser_available(fetcher=fetcher) is True
    status = openclaw_browser_capability_status(fetcher=fetcher)
    assert status["ready"] is True
    assert status["source"] == "openclaw"
    assert status["action_ref"] == "openclaw.browser.fill_form"


def test_openclaw_browser_capability_status_explains_missing_catalog(monkeypatch):
    monkeypatch.delenv("OPENCLAW_BROWSER_USE_ENABLED", raising=False)
    monkeypatch.delenv("OPENCLAW_BROWSER_USE_AVAILABLE", raising=False)
    monkeypatch.delenv("OPENCLAW_CAPABILITY_CATALOG_URL", raising=False)
    monkeypatch.delenv("OPENCLAW_BASE_URL", raising=False)
    monkeypatch.delenv("OPENCLAW_SANDBOX_BRIDGE_URL", raising=False)

    status = openclaw_browser_capability_status()

    assert status["ready"] is False
    assert status["source"] == "not_configured"
    assert status["reason"] == "openclaw_catalog_not_configured"


def test_openclaw_browser_available_uses_sandbox_bridge_catalog(monkeypatch):
    from services import openclaw_capability_catalog

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "actions": [
                    {
                        "openclaw_action_ref": "openclaw.browser.supervised_publish",
                        "localos_capability": "social.post.publish_supervised_browser",
                        "status": "available",
                    }
                ]
            }

    monkeypatch.delenv("OPENCLAW_BROWSER_USE_ENABLED", raising=False)
    monkeypatch.delenv("OPENCLAW_BROWSER_USE_AVAILABLE", raising=False)
    monkeypatch.delenv("OPENCLAW_CAPABILITY_CATALOG_URL", raising=False)
    monkeypatch.delenv("OPENCLAW_BASE_URL", raising=False)
    monkeypatch.setenv("OPENCLAW_SANDBOX_BRIDGE_URL", "http://openclaw.local/capabilities")
    monkeypatch.setattr(openclaw_capability_catalog.requests, "get", lambda *args, **kwargs: FakeResponse())

    status = openclaw_browser_capability_status()

    assert openclaw_browser_available() is True
    assert status["ready"] is True
    assert status["source"] == "openclaw"
    assert status["action_ref"] == "openclaw.browser.supervised_publish"


def test_openclaw_browser_capability_status_blocks_private_sandbox_bridge(monkeypatch):
    monkeypatch.delenv("OPENCLAW_BROWSER_USE_ENABLED", raising=False)
    monkeypatch.delenv("OPENCLAW_BROWSER_USE_AVAILABLE", raising=False)
    monkeypatch.delenv("OPENCLAW_CAPABILITY_CATALOG_URL", raising=False)
    monkeypatch.delenv("OPENCLAW_BASE_URL", raising=False)
    monkeypatch.delenv("OPENCLAW_SOCIAL_SUPERVISED_ALLOW_SANDBOX_CALLBACK", raising=False)
    monkeypatch.setenv("OPENCLAW_SANDBOX_BRIDGE_URL", "http://192.168.0.177:8091/capabilities")

    status = openclaw_browser_capability_status()

    assert status["ready"] is False
    assert status["source"] == "sandbox_bridge_private_host"
    assert status["status"] == "unreachable_from_production"
    assert status["reason"] == "sandbox_bridge_private_host"
    assert "private/local host" in status["error"]


def test_openclaw_browser_capability_status_accepts_enabled_env_values(monkeypatch):
    monkeypatch.setenv("OPENCLAW_BROWSER_USE_ENABLED", "enabled")
    monkeypatch.delenv("OPENCLAW_BROWSER_USE_AVAILABLE", raising=False)
    monkeypatch.delenv("OPENCLAW_CAPABILITY_CATALOG_URL", raising=False)
    monkeypatch.delenv("OPENCLAW_BASE_URL", raising=False)
    monkeypatch.setenv("OPENCLAW_SANDBOX_BRIDGE_URL", "http://192.168.0.177:8091/capabilities")

    status = openclaw_browser_capability_status()

    assert status["ready"] is True
    assert status["source"] == "env_override"
    assert status["reason"] == "browser_use_enabled_by_env"


def test_openclaw_browser_capability_status_preserves_catalog_request_error(monkeypatch):
    monkeypatch.delenv("OPENCLAW_BROWSER_USE_ENABLED", raising=False)
    monkeypatch.delenv("OPENCLAW_BROWSER_USE_AVAILABLE", raising=False)

    status = openclaw_browser_capability_status(
        fetcher=lambda: (_ for _ in ()).throw(RuntimeError("bridge timeout"))
    )

    assert status["ready"] is False
    assert status["source"] == "catalog_error"
    assert status["status"] == "error"
    assert status["reason"] == "openclaw_catalog_error"
    assert "OpenClaw catalog request failed" in status["error"]


def test_social_openclaw_browser_readiness_explains_ready_and_manual_fallback(monkeypatch):
    monkeypatch.setenv("OPENCLAW_SOCIAL_SUPERVISED_CALLBACK_URL", "https://openclaw.example/localos/social")
    ready = _social_openclaw_browser_readiness(
        {
            "ready": True,
            "source": "openclaw",
            "status": "available",
            "reason": "openclaw_supervised_browser_available",
            "action_ref": "openclaw.browser.fill_form",
            "capability": "social.post.publish_supervised_browser",
        }
    )
    fallback = _social_openclaw_browser_readiness(
        {
            "ready": False,
            "source": "not_configured",
            "status": "missing_catalog",
            "reason": "openclaw_catalog_not_configured",
            "action_ref": "",
        }
    )

    assert ready["ready"] is True
    assert ready["handoff_ready"] is True
    assert ready["status"] == "ready"
    assert ready["delivery_readiness"]["ready"] is True
    assert ready["action_ref"] == "openclaw.browser.fill_form"
    assert ready["browser_final_click_allowed"] is False
    assert ready["read_only"] is True
    assert ready["external_publish_performed"] is False
    assert ready["stop_before_final_publish"] is True
    assert ready["requires_final_human_confirmation"] is True
    assert ready["final_publish_policy"] == "human_final_click_required"
    assert "show_preview" in ready["allowed_actions"]
    assert "click_final_publish" in ready["forbidden_actions"]
    assert "changed_ui" in ready["manual_fallback_triggers"]
    assert any("read-only" in item.lower() or "read-only" in item for item in ready["diagnostics_en"])
    assert "контролируемое размещение" in ready["message_ru"]
    assert fallback["ready"] is False
    assert fallback["status"] == "manual_fallback"
    assert "ручном fallback" in fallback["message_ru"]
    assert "capability catalog" in fallback["next_action_ru"]
    assert any("openclaw_catalog_not_configured" in item for item in fallback["diagnostics_ru"])


def test_social_openclaw_browser_readiness_blocks_handoff_without_callback(monkeypatch):
    monkeypatch.delenv("OPENCLAW_SOCIAL_SUPERVISED_CALLBACK_URL", raising=False)
    monkeypatch.delenv("OPENCLAW_SUPERVISED_CALLBACK_URL", raising=False)
    monkeypatch.delenv("OPENCLAW_BASE_URL", raising=False)
    monkeypatch.delenv("OPENCLAW_CAPABILITY_CATALOG_URL", raising=False)
    monkeypatch.delenv("OPENCLAW_SOCIAL_SUPERVISED_ALLOW_SANDBOX_CALLBACK", raising=False)
    monkeypatch.setenv("OPENCLAW_SANDBOX_BRIDGE_URL", "http://192.168.0.177:8091/capabilities")

    readiness = _social_openclaw_browser_readiness(
        {
            "ready": True,
            "source": "openclaw",
            "status": "available",
            "reason": "openclaw_supervised_browser_available",
            "action_ref": "openclaw.browser.fill_form",
            "capability": "social.post.publish_supervised_browser",
        }
    )

    assert readiness["ready"] is True
    assert readiness["handoff_ready"] is False
    assert readiness["status"] == "manual_fallback"
    assert readiness["delivery_readiness"]["status"] == "callback_missing"
    assert readiness["delivery_readiness"]["callback_env_var"] == "OPENCLAW_SOCIAL_SUPERVISED_CALLBACK_URL"
    assert readiness["delivery_readiness"]["suggested_callback_url"] == ""
    assert readiness["delivery_readiness"]["suggested_callback_blocked_reason"] == "sandbox_bridge_private_host"
    assert "Callback" in readiness["delivery_readiness"]["message_ru"]
    assert "публичный/доступный OPENCLAW_SOCIAL_SUPERVISED_CALLBACK_URL" in readiness["delivery_readiness"]["next_action_ru"]
    assert "ручной режим" in readiness["message_ru"]


def test_social_openclaw_browser_readiness_explains_private_sandbox_bridge(monkeypatch):
    monkeypatch.delenv("OPENCLAW_SOCIAL_SUPERVISED_CALLBACK_URL", raising=False)
    monkeypatch.delenv("OPENCLAW_SUPERVISED_CALLBACK_URL", raising=False)
    monkeypatch.delenv("OPENCLAW_BASE_URL", raising=False)
    monkeypatch.delenv("OPENCLAW_CAPABILITY_CATALOG_URL", raising=False)
    monkeypatch.delenv("OPENCLAW_SOCIAL_SUPERVISED_ALLOW_SANDBOX_CALLBACK", raising=False)
    monkeypatch.setenv("OPENCLAW_SANDBOX_BRIDGE_URL", "http://192.168.0.177:8091/capabilities")

    status = openclaw_browser_capability_status()
    readiness = _social_openclaw_browser_readiness(status)

    assert readiness["ready"] is False
    assert readiness["status"] == "manual_fallback"
    assert readiness["source"] == "sandbox_bridge_private_host"
    assert "приватный sandbox bridge" in readiness["message_ru"]
    assert "OPENCLAW_BASE_URL" in readiness["next_action_ru"]
    assert any("Sandbox bridge" in item for item in readiness["diagnostics_ru"])
    assert not any("Ошибка каталога OpenClaw" in item for item in readiness["diagnostics_ru"])


def test_social_openclaw_suggested_callback_prefers_base_url(monkeypatch):
    monkeypatch.delenv("OPENCLAW_SOCIAL_SUPERVISED_CALLBACK_URL", raising=False)
    monkeypatch.delenv("OPENCLAW_SUPERVISED_CALLBACK_URL", raising=False)
    monkeypatch.setenv("OPENCLAW_BASE_URL", "https://openclaw.example/base")
    monkeypatch.setenv("OPENCLAW_SANDBOX_BRIDGE_URL", "http://openclaw.local:8091/capabilities")

    assert (
        social_post_service._social_supervised_openclaw_suggested_callback_url()
        == "https://openclaw.example/m2m/localos/callbacks"
    )


def test_social_openclaw_suggested_callback_allows_private_sandbox_only_with_flag(monkeypatch):
    monkeypatch.delenv("OPENCLAW_SOCIAL_SUPERVISED_CALLBACK_URL", raising=False)
    monkeypatch.delenv("OPENCLAW_SUPERVISED_CALLBACK_URL", raising=False)
    monkeypatch.delenv("OPENCLAW_BASE_URL", raising=False)
    monkeypatch.delenv("OPENCLAW_CAPABILITY_CATALOG_URL", raising=False)
    monkeypatch.setenv("OPENCLAW_SANDBOX_BRIDGE_URL", "http://192.168.0.177:8091/capabilities")

    assert social_post_service._social_supervised_openclaw_suggested_callback_url() == ""
    assert (
        social_post_service._social_supervised_openclaw_suggested_callback_blocked_reason()
        == "sandbox_bridge_private_host"
    )

    monkeypatch.setenv("OPENCLAW_SOCIAL_SUPERVISED_ALLOW_SANDBOX_CALLBACK", "true")

    assert (
        social_post_service._social_supervised_openclaw_suggested_callback_url()
        == "http://192.168.0.177:8091/m2m/localos/callbacks"
    )
    assert social_post_service._social_supervised_openclaw_suggested_callback_blocked_reason() == ""


def test_social_openclaw_browser_readiness_explains_catalog_route_error():
    readiness = _social_openclaw_browser_readiness(
        {
            "ready": False,
            "source": "catalog_error",
            "status": "error",
            "reason": "openclaw_catalog_error",
            "error": "OpenClaw catalog request failed",
            "action_ref": "",
        }
    )

    assert readiness["ready"] is False
    assert readiness["status"] == "manual_fallback"
    assert "не смог прочитать capability catalog" in readiness["message_ru"]
    assert "production VPS" in readiness["next_action_ru"]
    assert any("Ошибка каталога OpenClaw" in item for item in readiness["diagnostics_ru"])
    assert any("OpenClaw catalog error" in item for item in readiness["diagnostics_en"])


def test_check_social_openclaw_browser_readiness_is_read_only_and_scoped(monkeypatch):
    captured = {}
    monkeypatch.setattr(social_post_service, "DatabaseManager", FakeQueueFallbackDB)
    monkeypatch.setattr(
        social_post_service,
        "_require_business_access",
        lambda cursor, user_id, business_id: captured.setdefault(
            "access",
            {"user_id": user_id, "business_id": business_id},
        ),
    )
    monkeypatch.setattr(
        social_post_service,
        "_social_openclaw_browser_readiness",
        lambda **kwargs: {
            "ready": True,
            "status": "ready",
            "browser_final_click_allowed": False,
        },
    )

    result = check_social_openclaw_browser_readiness("user-1", "biz-1")

    assert result["business_id"] == "biz-1"
    assert result["read_only"] is True
    assert result["external_publish_performed"] is False
    assert result["browser_final_click_allowed"] is False
    assert result["capability_checked"] == "social.post.publish_supervised_browser"
    assert result["safety_contract"]["final_publish_policy"] == "human_final_click_required"
    assert "click_final_publish" in result["safety_contract"]["forbidden_actions"]
    assert "ручное размещение" in result["owner_next_action_ru"]
    assert result["openclaw_browser_readiness"]["status"] == "ready"
    assert captured["access"] == {"user_id": "user-1", "business_id": "biz-1"}


def test_approve_social_post_rejects_empty_copy(monkeypatch):
    monkeypatch.setattr(social_post_service, "DatabaseManager", FakeApproveGuardDB)
    monkeypatch.setattr(social_post_service, "ensure_social_post_tables", lambda cursor: None)
    monkeypatch.setattr(
        social_post_service,
        "_load_post_for_user",
        lambda cursor, user_id, post_id: {
            "id": post_id,
            "business_id": "biz-1",
            "platform": "telegram",
            "status": "needs_review",
            "platform_text": "   ",
            "base_text": "",
        },
    )

    with pytest.raises(ValueError, match="текст публикации"):
        approve_social_post("user-1", "post-empty")

    assert FakeApproveGuardDB.last_conn.committed is False
    assert FakeApproveGuardDB.last_conn.rolled_back is True


def test_preview_social_posts_for_item_is_read_only(monkeypatch):
    monkeypatch.setattr(social_post_service, "DatabaseManager", FakePreparePreviewDB)
    monkeypatch.setattr(social_post_service, "ensure_social_post_tables", lambda cursor: None)
    monkeypatch.setattr(
        social_post_service,
        "_load_plan_item_for_user",
        lambda cursor, user_id, item_id: {
            "id": item_id,
            "plan_id": "plan-1",
            "business_id": "biz-1",
            "scheduled_for": date.today(),
            "theme": "Тема",
            "goal": "Цель",
            "draft_text": "Готовый текст",
        },
    )

    payload = preview_social_posts_for_item("user-1", "item-1", ["telegram", "yandex_maps"])

    assert payload["read_only"] is True
    assert payload["database_write_performed"] is False
    assert payload["external_publish_performed"] is False
    assert payload["summary"]["total"] == 2
    assert payload["summary"]["would_create"] == 2
    assert payload["summary"]["needs_review"] == 2
    assert [post["platform"] for post in payload["posts"]] == ["telegram", "yandex_maps"]
    assert payload["posts"][0]["platform_text"] == "Готовый текст"
    assert payload["posts"][1]["publish_mode"] in {"openclaw_browser", "local_supervised_browser", "manual"}
    assert FakePreparePreviewDB.last_conn.committed is False
    assert FakePreparePreviewDB.last_conn.rolled_back is False


def test_next_action_separates_review_api_and_supervised_states():
    assert next_action_for_social_post({"status": "needs_review", "platform": "telegram"}) == "review_required"
    assert next_action_for_social_post({"status": "approved", "platform": "telegram"}) == "wait_for_api_publish"
    assert next_action_for_social_post({"status": "approved", "platform": "yandex_maps"}) == "start_supervised_publish"
    assert next_action_for_social_post({"status": "queued", "platform": "telegram"}) == "wait_for_scheduled_publish"
    assert next_action_for_social_post({"status": "queued", "platform": "two_gis"}) == "wait_for_scheduled_supervised_publish"
    assert next_action_for_social_post({"status": "needs_supervised_publish", "platform": "two_gis"}) == "open_supervised_publish"


def test_social_text_edit_resets_approval_boundary():
    assert _status_after_social_text_edit("approved", "Новый текст") == "needs_review"
    assert _status_after_social_text_edit("needs_review", "") == "draft"
    assert _status_after_social_text_edit("draft", "Готовый текст") == "needs_review"


def test_ensure_social_post_tables_is_alembic_only_guard():
    cursor = FakeTableCursor(
        {
            "social_posts",
            "social_post_metrics",
            "social_post_attribution_events",
        }
    )

    ensure_social_post_tables(cursor)


def test_ensure_social_post_tables_fails_when_migration_is_missing():
    cursor = FakeTableCursor({"social_posts"})
    error = None

    try:
        ensure_social_post_tables(cursor)
    except RuntimeError:
        error = sys.exc_info()[1]
    assert error is not None
    assert "Run Alembic migration 20260619_001" in str(error)
    assert "social_post_metrics" in str(error)


def test_build_social_queue_groups_matches_daily_workflow():
    groups = build_social_queue_groups(
        [
            {"id": "p1", "content_plan_item_id": "i1", "platform": "telegram", "status": "needs_review"},
            {"id": "p2", "content_plan_item_id": "i1", "platform": "vk", "status": "approved"},
            {"id": "p3", "content_plan_item_id": "i2", "platform": "yandex_maps", "status": "approved"},
            {"id": "p4", "content_plan_item_id": "i3", "platform": "telegram", "status": "published"},
            {"id": "p5", "content_plan_item_id": "i4", "platform": "facebook", "status": "failed"},
            {"id": "p6", "content_plan_item_id": "i5", "platform": "telegram", "status": "queued"},
            {"id": "p7", "content_plan_item_id": "i6", "platform": "telegram", "status": "needs_manual_publish"},
        ]
    )
    by_key = {group["key"]: group for group in groups}

    assert by_key["needs_review"]["count"] == 1
    assert by_key["api_ready"]["post_ids"] == ["p2"]
    assert by_key["scheduled"]["post_ids"] == ["p6"]
    assert by_key["needs_supervised_publish"]["post_ids"] == ["p3"]
    assert by_key["needs_manual_publish"]["post_ids"] == ["p7"]
    assert by_key["published"]["count"] == 1
    assert by_key["failed"]["count"] == 1


def test_plan_recommendation_explains_signal_priority():
    recommendation = _build_plan_recommendation(
        [
            {"id": "p1", "leads": 2, "inquiries": 1, "comments": 5, "reach": 100},
            {"id": "p2", "views": 40, "likes": 9},
        ]
    )

    assert recommendation["primary_metric"] == "leads_and_inquiries"
    assert recommendation["leads"] == 2
    assert recommendation["inquiries"] == 1
    assert [item["key"] for item in recommendation["signal_priority"]] == ["leads", "inquiries", "comments", "reach"]
    assert recommendation["signal_priority"][0]["rank"] == 1
    assert recommendation["signal_priority"][0]["role_ru"] == "главный KPI"
    assert recommendation["signal_priority"][3]["value"] == 140


def test_social_learning_readiness_prefers_primary_business_results():
    readiness = _social_learning_readiness(
        [
            {"status": "published", "platform": "telegram", "leads": 1, "reach": 5},
            {"status": "published", "platform": "vk", "reach": 900},
        ]
    )

    assert readiness["schema"] == "localos_social_learning_readiness_v1"
    assert readiness["status"] == "ready_from_leads"
    assert readiness["confidence"] == "high"
    assert readiness["posts_with_primary_result"] == 1
    assert readiness["primary_signal_total"] == 1
    assert readiness["secondary_signal_total"] == 0
    assert readiness["early_signal_total"] == 905
    assert readiness["leads"] == 1
    assert readiness["inquiries"] == 0
    assert readiness["reach"] == 905
    assert readiness["safe_to_apply_recommendation"] is True
    assert readiness["apply_blocked_reason_ru"] == ""
    assert readiness["apply_blocked_reason_en"] == ""
    assert "Заявки" in readiness["primary_metric_ru"]
    checklist = {item["key"]: item for item in readiness["checklist"]}
    assert checklist["publish_first"]["status"] == "done"
    assert checklist["finish_manual_or_failed"]["status"] == "done"
    assert checklist["record_results"]["status"] == "done"
    assert checklist["apply_with_confirmation"]["status"] == "current"
    assert "Можно применять" in checklist["apply_with_confirmation"]["label_ru"]


def test_social_learning_readiness_warns_when_publish_work_is_pending():
    readiness = _social_learning_readiness(
        [
            {"status": "needs_supervised_publish", "platform": "yandex_maps"},
            {"status": "failed", "platform": "telegram"},
        ]
    )

    assert readiness["status"] == "finish_pending_publish"
    assert readiness["confidence"] == "low"
    assert readiness["pending_manual_or_supervised_posts"] == 1
    assert readiness["failed_posts"] == 1
    assert readiness["safe_to_apply_recommendation"] is False
    assert "manual/supervised" in readiness["next_action_en"]
    assert "Apply is blocked" in readiness["apply_blocked_reason_en"]
    assert "supervised/manual" in readiness["apply_blocked_reason_en"]
    checklist = {item["key"]: item for item in readiness["checklist"]}
    assert checklist["finish_manual_or_failed"]["status"] == "attention"
    assert checklist["record_results"]["status"] == "pending"


def test_social_learning_readiness_requires_signals_before_apply():
    readiness = _social_learning_readiness(
        [
            {"status": "published", "platform": "telegram"},
        ]
    )

    assert readiness["status"] == "published_without_signals"
    assert readiness["confidence"] == "low"
    assert readiness["published_posts"] == 1
    assert readiness["posts_with_primary_result"] == 0
    assert readiness["posts_with_early_signal"] == 0
    assert readiness["safe_to_apply_recommendation"] is False
    assert "Collect reactions" in readiness["next_action_en"]
    assert "collect reactions" in readiness["apply_blocked_reason_en"].lower()


def test_manual_attribution_metrics_include_views_and_likes():
    metrics = _attribution_metrics_for_post(FakeAttributionMetricsCursor(), "post-1")

    assert metrics["views"] == 25
    assert metrics["likes"] == 4
    assert metrics["comments"] == 2
    assert metrics["shares"] == 1
    assert metrics["clicks"] == 3
    assert metrics["inquiries"] == 1
    assert metrics["leads"] == 1


def test_record_social_post_attribution_event_returns_updated_metrics(monkeypatch):
    monkeypatch.setattr(social_post_service, "DatabaseManager", FakeAttributionEventDB)
    monkeypatch.setattr(social_post_service, "ensure_social_post_tables", lambda cursor: None)
    monkeypatch.setattr(
        social_post_service,
        "_load_post_for_user",
        lambda cursor, user_id, post_id: {
            "id": post_id,
            "business_id": "biz-1",
            "platform": "telegram",
            "status": "published",
            "leads": 0,
            "inquiries": 0,
        },
    )

    payload = record_social_post_attribution_event(
        "user-1",
        "post-1",
        "lead",
        value=2,
        event_source="manual_content_plan",
        metadata={"source": "button"},
    )

    assert payload["event"]["event_type"] == "lead"
    assert payload["event"]["value"] == 2
    assert payload["metrics"]["leads"] == 2
    assert payload["metrics"]["inquiries"] == 1
    assert payload["post"]["leads"] == 2
    assert payload["post"]["comments"] == 3
    assert FakeAttributionEventDB.last_conn.metric_upserted is True
    assert FakeAttributionEventDB.last_conn.committed is True


def test_record_social_post_attribution_event_rejects_unpublished_post(monkeypatch):
    monkeypatch.setattr(social_post_service, "DatabaseManager", FakeAttributionEventDB)
    monkeypatch.setattr(social_post_service, "ensure_social_post_tables", lambda cursor: None)
    monkeypatch.setattr(
        social_post_service,
        "_load_post_for_user",
        lambda cursor, user_id, post_id: {
            "id": post_id,
            "business_id": "biz-1",
            "platform": "telegram",
            "status": "queued",
        },
    )

    with pytest.raises(ValueError, match="после публикации"):
        record_social_post_attribution_event("user-1", "post-queued", "lead")

    assert FakeAttributionEventDB.last_conn.inserted_events == []
    assert FakeAttributionEventDB.last_conn.committed is False
    assert FakeAttributionEventDB.last_conn.rolled_back is True


def test_record_social_post_attribution_events_records_bulk_without_external_publish(monkeypatch):
    monkeypatch.setattr(social_post_service, "DatabaseManager", FakeAttributionEventDB)
    monkeypatch.setattr(social_post_service, "ensure_social_post_tables", lambda cursor: None)
    monkeypatch.setattr(
        social_post_service,
        "_load_post_for_user",
        lambda cursor, user_id, post_id: {
            "id": post_id,
            "business_id": "biz-1",
            "platform": "telegram" if post_id == "post-1" else "vk",
            "status": "published",
            "content_plan_item_id": f"item-{post_id}",
            "leads": 0,
            "inquiries": 0,
        },
    )

    payload = record_social_post_attribution_events(
        "user-1",
        ["post-1", "post-2"],
        "inquiry",
        value=1,
        event_source="manual_content_plan_bulk",
        metadata={"selected_bulk": True},
    )

    assert payload["summary"]["requested"] == 2
    assert payload["summary"]["recorded"] == 2
    assert payload["summary"]["event_type"] == "inquiry"
    assert payload["summary"]["external_publish_performed"] is False
    assert payload["summary"]["provider_write_performed"] is False
    assert len(payload["events"]) == 2
    assert [item["event_type"] for item in payload["events"]] == ["inquiry", "inquiry"]
    assert len(payload["posts"]) == 2
    assert payload["posts"][0]["inquiries"] == 1
    assert payload["metrics_by_post"]["post-1"]["inquiries"] == 1
    assert len(FakeAttributionEventDB.last_conn.inserted_events) == 2
    assert FakeAttributionEventDB.last_conn.metric_upserted is True
    assert FakeAttributionEventDB.last_conn.committed is True


def test_record_social_post_attribution_events_rejects_unpublished_bulk_post(monkeypatch):
    monkeypatch.setattr(social_post_service, "DatabaseManager", FakeAttributionEventDB)
    monkeypatch.setattr(social_post_service, "ensure_social_post_tables", lambda cursor: None)
    monkeypatch.setattr(
        social_post_service,
        "_load_post_for_user",
        lambda cursor, user_id, post_id: {
            "id": post_id,
            "business_id": "biz-1",
            "platform": "telegram",
            "status": "published" if post_id == "post-published" else "approved",
        },
    )

    with pytest.raises(ValueError, match="после публикации"):
        record_social_post_attribution_events(
            "user-1",
            ["post-published", "post-approved"],
            "inquiry",
            event_source="manual_content_plan_bulk",
        )

    assert FakeAttributionEventDB.last_conn.rolled_back is True
    assert FakeAttributionEventDB.last_conn.committed is False


def test_mark_manual_published_allows_manual_or_supervised_only(monkeypatch):
    monkeypatch.setattr(social_post_service, "DatabaseManager", FakeManualPublishedDB)
    monkeypatch.setattr(social_post_service, "ensure_social_post_tables", lambda cursor: None)
    monkeypatch.setattr(
        social_post_service,
        "_load_post_for_user",
        lambda cursor, user_id, post_id: {
            "id": post_id,
            "business_id": "biz-1",
            "platform": "yandex_maps",
            "status": "needs_supervised_publish",
            "metadata_json": {},
        },
    )

    post = mark_manual_published("user-1", "post-1", provider_post_url="https://maps.example/post-1")

    assert post["status"] == "published"
    assert post["provider_post_url"] == "https://maps.example/post-1"
    assert post["metadata_json"]["published_source"] == "manual_confirmation"
    assert FakeManualPublishedDB.last_conn.committed is True


def test_mark_manual_published_rejects_approved_api_post(monkeypatch):
    monkeypatch.setattr(social_post_service, "DatabaseManager", FakeManualPublishedDB)
    monkeypatch.setattr(social_post_service, "ensure_social_post_tables", lambda cursor: None)
    monkeypatch.setattr(
        social_post_service,
        "_load_post_for_user",
        lambda cursor, user_id, post_id: {
            "id": post_id,
            "business_id": "biz-1",
            "platform": "telegram",
            "status": "approved",
            "metadata_json": {},
        },
    )

    with pytest.raises(ValueError, match="ручного или контролируемого"):
        mark_manual_published("user-1", "post-api")

    assert FakeManualPublishedDB.last_conn.updated_row == {}
    assert FakeManualPublishedDB.last_conn.committed is False
    assert FakeManualPublishedDB.last_conn.rolled_back is True


def test_social_metrics_result_summaries_explain_api_manual_and_failed_results():
    summaries = _social_metrics_result_summaries(
        [
            {
                "platform": "vk",
                "source": "vk_api",
                "status": "vk_metrics_collected",
                "views": 120,
                "comments": 3,
                "leads": 1,
            },
            {
                "platform": "telegram",
                "source": "telegram_bot_api",
                "status": "telegram_bot_api_metrics_unavailable",
                "inquiries": 2,
            },
            {
                "platform": "google_business",
                "source": "google_business_api",
                "status": "google_business_metrics_not_enabled",
                "leads": 1,
            },
            {
                "platform": "instagram",
                "source": "meta_graph_api",
                "status": "meta_graph_metrics_permissions_required",
            },
            {
                "platform": "yandex_maps",
                "source": "manual_or_supervised_map",
                "status": "map_metrics_manual_input_required",
            },
            {
                "platform": "google_business",
                "source": "collector_error",
                "status": "failed",
                "error": "temporary",
            },
        ],
        True,
    )

    assert "VK: API-снимок обновлён" in summaries[0]
    assert "заявки 1" in summaries[0]
    assert "Telegram: Bot API опубликовал пост, но не отдаёт просмотры/реакции" in summaries[1]
    assert "Google Business: публикация учтена, но сбор реакций через Google Business пока не включён" in summaries[2]
    assert "Instagram: Meta Graph метрики требуют готовых прав" in summaries[3]
    assert "Яндекс Карты: реакции с карт собираются вручную" in summaries[4]
    assert "Ещё 1 результатов смотрите" in summaries[5]


def test_provider_metrics_placeholders_explain_non_vk_collector_boundaries():
    google = _provider_metrics_placeholder(
        "google_business",
        "google_business_api",
        "google_business_metrics_not_enabled",
    )
    assert google["source"] == "google_business_api"
    assert google["status"] == "google_business_metrics_not_enabled"
    assert google["views"] == 0

    meta = _provider_metrics_placeholder(
        "instagram",
        "meta_graph_api",
        "meta_graph_metrics_permissions_required",
    )
    assert meta["source"] == "meta_graph_api"
    assert meta["provider"] == "instagram"


def test_collect_telegram_post_metrics_is_explicit_about_bot_api_limits():
    missing = _collect_telegram_post_metrics({"platform": "telegram"})
    assert missing["source"] == "telegram_bot_api"
    assert missing["status"] == "missing_provider_post_binding"

    collected = _collect_telegram_post_metrics({"platform": "telegram", "provider_post_id": "42"})
    assert collected["source"] == "telegram_bot_api"
    assert collected["provider"] == "telegram"
    assert collected["status"] == "telegram_bot_api_metrics_unavailable"
    assert collected["provider_post_id"] == "42"
    assert collected["views"] == 0


def test_dispatch_action_for_status_matches_worker_log_buckets():
    assert _dispatch_action_for_status("published") == "published"
    assert _dispatch_action_for_status("needs_supervised_publish") == "supervised"
    assert _dispatch_action_for_status("needs_manual_publish") == "manual"
    assert _dispatch_action_for_status("failed") == "failed"
    assert _dispatch_action_for_status("queued") == "other"


def test_social_dispatch_followup_actions_explain_no_due_posts():
    actions = _social_dispatch_followup_actions(
        picked=0,
        published=0,
        supervised=0,
        manual=0,
        failed=0,
        errors=[],
        is_ru=True,
    )

    assert len(actions) == 1
    assert "Постов на текущую дату нет" in actions[0]
    assert "подтвердите" in actions[0]


def test_social_dispatch_followup_actions_prioritize_real_outcomes():
    actions = _social_dispatch_followup_actions(
        picked=4,
        published=1,
        supervised=1,
        manual=1,
        failed=1,
        errors=[{"id": "post-4", "error": "VK token expired"}],
        is_ru=False,
    )

    assert any("URL or provider ID" in item for item in actions)
    assert any("Yandex/2GIS" in item and "final click" in item for item in actions)
    assert any("connect keys/permissions" in item for item in actions)
    assert any("VK token expired" in item for item in actions)
    assert "leads/inquiries" in actions[-1]


def test_social_dispatch_result_summaries_explain_each_channel_outcome():
    summaries = _social_dispatch_result_summaries(
        [
            {
                "platform": "telegram",
                "status": "published",
                "provider_post_url": "https://t.me/channel/10",
            },
            {
                "platform": "yandex_maps",
                "status": "needs_supervised_publish",
                "automation_task_id": "task-1",
            },
            {
                "platform": "vk",
                "status": "needs_manual_publish",
                "last_error": "missing wall.post",
            },
            {
                "platform": "facebook",
                "status": "failed",
                "last_error": "temporary",
            },
        ],
        True,
    )

    assert "Telegram: опубликовано" in summaries[0]
    assert "https://t.me/channel/10" in summaries[0]
    assert summaries[1] == "Яндекс Карты: контролируемое размещение готово (task-1)."
    assert "missing wall.post" in summaries[2]
    assert summaries[3] == "Facebook: ошибка публикации: temporary."


def test_social_dispatch_execution_report_keeps_owner_proof_and_safety():
    report = _social_dispatch_execution_report(
        {
            "picked": 3,
            "published": 1,
            "supervised": 1,
            "manual": 1,
            "failed": 0,
            "business_scope": "biz-1",
            "by_status": {"published": 1, "needs_supervised_publish": 1, "needs_manual_publish": 1},
            "by_action": {"published": 1, "supervised": 1, "manual": 1},
            "details": [
                {
                    "id": "post-api",
                    "platform": "telegram",
                    "status": "published",
                    "provider_post_url": "https://t.me/channel/10",
                },
                {
                    "id": "post-map",
                    "platform": "yandex_maps",
                    "status": "needs_supervised_publish",
                    "automation_task_id": "task-1",
                },
                {
                    "id": "post-manual",
                    "platform": "vk",
                    "status": "needs_manual_publish",
                    "last_error": "missing wall.post",
                },
            ],
            "errors": [],
        }
    )

    assert report["schema"] == "localos_social_dispatch_execution_report_v1"
    assert report["status"] == "manual_action_needed"
    assert report["published"] == 1
    assert report["supervised"] == 1
    assert report["manual"] == 1
    assert report["external_publish_only_after_approval"] is True
    assert report["maps_are_supervised_or_manual"] is True
    assert report["browser_final_click_allowed"] is False
    assert report["provider_write_summary"]["published_with_provider_proof"] == 1
    assert report["provider_write_summary"]["supervised_tasks_created"] == 1
    assert report["first_api_proof_summary"]["schema"] == "localos_social_first_api_proof_summary_v1"
    assert report["first_api_proof_summary"]["ready"] is True
    assert report["first_api_proof_summary"]["published_with_provider_proof"] == 1
    assert report["first_api_proof_summary"]["provider_post_url"] == "https://t.me/channel/10"
    assert "заявки" in report["first_api_proof_summary"]["next_action_ru"]
    assert report["after_run_proof_packet"]["schema"] == "localos_social_after_run_proof_packet_v1"
    assert report["after_run_proof_packet"]["status"] == "loop_proven_collect_results"
    assert report["after_run_proof_packet"]["api_proof_ready"] is True
    assert report["after_run_proof_packet"]["can_collect_results"] is True
    assert report["after_run_proof_packet"]["maps_handoff_created"] is True
    assert report["after_run_proof_packet"]["browser_final_click_allowed"] is False
    assert "provider_post_id/provider_post_url" in report["after_run_proof_packet"]["checks_ru"][0]
    assert report["post_publish_learning_gate"]["schema"] == "localos_social_post_publish_learning_gate_v1"
    assert report["post_publish_learning_gate"]["status"] == "ready_for_metrics_and_attribution"
    assert report["post_publish_learning_gate"]["allowed"] is True
    assert report["post_publish_learning_gate"]["can_collect_metrics"] is True
    assert report["post_publish_learning_gate"]["api_proof_ready"] is True
    assert report["post_publish_learning_gate"]["primary_metric_ru"] == "Заявки и обращения"
    assert "Собрать реакции" in report["post_publish_learning_gate"]["next_action_ru"]
    assert "ручные/контролируемые" in report["next_action_ru"]


def test_dispatch_due_social_posts_blocks_unscoped_by_default(monkeypatch):
    def fail_if_db_opens():
        raise AssertionError("unscoped dispatch must not open DB")

    monkeypatch.delenv("SOCIAL_POST_DISPATCH_BUSINESS_ID", raising=False)
    monkeypatch.delenv("SOCIAL_POST_DISPATCH_ALLOW_UNSCOPED", raising=False)
    monkeypatch.setattr(social_post_service, "DatabaseManager", fail_if_db_opens)

    result = dispatch_due_social_posts(batch_size=20)

    assert result["picked"] == 0
    assert result["blocked"] is True
    assert result["blocked_reason"] == "business_scope_required"
    assert result["by_action"]["blocked_without_scope"] == 1


def test_dispatch_due_social_posts_can_scope_to_one_business(monkeypatch):
    monkeypatch.setattr(social_post_service, "DatabaseManager", FakeDispatchScopeDB)
    monkeypatch.setattr(social_post_service, "ensure_social_post_tables", lambda cursor: None)
    monkeypatch.setenv("SOCIAL_POST_DISPATCH_BUSINESS_ID", "biz-test")
    monkeypatch.delenv("SOCIAL_POST_DISPATCH_ALLOW_UNSCOPED", raising=False)

    result = dispatch_due_social_posts(batch_size=500)

    assert result["picked"] == 0
    assert result["business_scope"] == "biz-test"
    assert "sp.business_id = %s" in FakeDispatchScopeCursor.last_query
    assert FakeDispatchScopeCursor.last_params == ("biz-test", 200)


def test_dispatch_due_social_posts_uses_live_api_preflight_before_provider_publish(monkeypatch):
    class FakePickedCursor:
        def execute(self, query, params=None):
            self.query = str(query)
            self.params = tuple(params or ())

        def fetchall(self):
            return [
                {
                    "id": "post-live-block",
                    "business_id": "biz-1",
                    "platform": "telegram",
                    "status": "queued",
                }
            ]

    class FakePickedConn:
        def __init__(self):
            self.cursor_obj = FakePickedCursor()

        def cursor(self):
            return self.cursor_obj

    class FakePickedDB:
        def __init__(self):
            self.conn = FakePickedConn()

        def close(self):
            pass

    monkeypatch.setattr(social_post_service, "DatabaseManager", FakePickedDB)
    monkeypatch.setattr(social_post_service, "ensure_social_post_tables", lambda cursor: None)
    monkeypatch.setattr(social_post_service, "_owner_id_for_business", lambda business_id: "owner-1")
    monkeypatch.setattr(
        social_post_service,
        "_dispatch_live_api_preflight_block",
        lambda user_id, post_id: {
            "id": post_id,
            "business_id": "biz-1",
            "platform": "telegram",
            "status": "needs_manual_publish",
            "last_error": "Telegram: live API-preflight не готов.",
        },
    )
    monkeypatch.setattr(
        social_post_service,
        "publish_social_post",
        lambda user_id, post_id: (_ for _ in ()).throw(AssertionError("provider publish must not run")),
    )

    result = dispatch_due_social_posts(batch_size=10, business_id="biz-1")

    assert result["picked"] == 1
    assert result["manual"] == 1
    assert result["failed"] == 0
    assert result["errors"] == []
    assert result["by_action"]["manual"] == 1
    assert result["details"][0]["status"] == "needs_manual_publish"
    assert result["details"][0]["last_error"] == "Telegram: live API-preflight не готов."


def test_preview_due_social_post_dispatch_can_scope_to_one_business(monkeypatch):
    monkeypatch.setattr(social_post_service, "DatabaseManager", FakeDispatchScopeDB)
    monkeypatch.setattr(social_post_service, "ensure_social_post_tables", lambda cursor: None)
    monkeypatch.delenv("SOCIAL_POST_DISPATCH_BUSINESS_ID", raising=False)

    result = preview_due_social_post_dispatch("user-1", batch_size=2, business_id="biz-preview")

    assert result["picked"] == 0
    assert result["business_scope"] == "biz-preview"
    assert "sp.business_id = %s" in FakeDispatchScopeCursor.last_query
    assert FakeDispatchScopeCursor.last_params == ("biz-preview", 2)


def test_run_scoped_social_dispatch_once_requires_approval_before_preflight(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("preflight must not run without approval")

    monkeypatch.setattr(social_post_service, "get_social_launch_preflight", fail_if_called)

    error = None
    try:
        run_scoped_social_dispatch_once("user-1", "biz-1", approved=False)
    except PermissionError:
        error = sys.exc_info()[1]

    assert error is not None
    assert "явное подтверждение" in str(error)


def test_run_scoped_social_dispatch_once_runs_only_requested_business(monkeypatch):
    captured = {}

    def fake_preflight(user_id, business_id, batch_size=10):
        captured["preflight"] = {"user_id": user_id, "business_id": business_id, "batch_size": batch_size}
        return {
            "business_id": business_id,
            "summary": {"due_posts": 2, "skipped_no_access": 0},
            "safety": {"browser_final_click_allowed": False},
        }

    def fake_dispatch(batch_size=20, business_id=""):
        captured["dispatch"] = {"business_id": business_id, "batch_size": batch_size}
        return {
            "picked": 2,
            "published": 1,
            "supervised": 1,
            "manual": 0,
            "failed": 0,
            "business_scope": business_id,
        }

    monkeypatch.setattr(social_post_service, "get_social_launch_preflight", fake_preflight)
    monkeypatch.setattr(social_post_service, "dispatch_due_social_posts", fake_dispatch)

    result = run_scoped_social_dispatch_once("user-1", "biz-1", batch_size=500, approved=True)

    assert result["business_id"] == "biz-1"
    assert result["batch_size"] == 50
    assert result["dispatch_result"]["published"] == 1
    assert result["execution_report"]["schema"] == "localos_social_dispatch_execution_report_v1"
    assert result["execution_report"]["published"] == 1
    assert result["execution_report"]["browser_final_click_allowed"] is False
    assert result["browser_final_click_allowed"] is False
    assert result["external_publish_only_after_approval"] is True
    assert captured["preflight"] == {"user_id": "user-1", "business_id": "biz-1", "batch_size": 50}
    assert captured["dispatch"] == {"business_id": "biz-1", "batch_size": 50}


def test_run_scoped_social_dispatch_once_requires_phrase_for_api_publish(monkeypatch):
    def fake_preflight(user_id, business_id, batch_size=10):
        return {
            "business_id": business_id,
            "launch_gate": {"allowed": True, "api_posts": 1},
            "summary": {
                "due_posts": 1,
                "api_due_posts": 1,
                "skipped_no_access": 0,
                "api_preflight_blocked_due_posts": 0,
            },
        }

    def fail_dispatch(*args, **kwargs):
        raise AssertionError("dispatch must not run without typed external publish confirmation")

    monkeypatch.setattr(social_post_service, "get_social_launch_preflight", fake_preflight)
    monkeypatch.setattr(social_post_service, "dispatch_due_social_posts", fail_dispatch)

    error = None
    try:
        run_scoped_social_dispatch_once("user-1", "biz-1", approved=True, approval_text="")
    except PermissionError:
        error = sys.exc_info()[1]

    assert error is not None
    assert "ПУБЛИКУЮ" in str(error)


def test_run_scoped_social_dispatch_once_accepts_phrase_for_api_publish(monkeypatch):
    captured = {}

    def fake_preflight(user_id, business_id, batch_size=10):
        return {
            "business_id": business_id,
            "launch_gate": {"allowed": True, "api_posts": 1},
            "summary": {
                "due_posts": 1,
                "api_due_posts": 1,
                "skipped_no_access": 0,
                "api_preflight_blocked_due_posts": 0,
            },
        }

    def fake_dispatch(batch_size=20, business_id=""):
        captured["dispatch"] = {"business_id": business_id, "batch_size": batch_size}
        return {
            "picked": 1,
            "published": 1,
            "supervised": 0,
            "manual": 0,
            "failed": 0,
            "business_scope": business_id,
        }

    monkeypatch.setattr(social_post_service, "get_social_launch_preflight", fake_preflight)
    monkeypatch.setattr(social_post_service, "dispatch_due_social_posts", fake_dispatch)

    result = run_scoped_social_dispatch_once("user-1", "biz-1", approved=True, approval_text="публикую")

    assert result["dispatch_result"]["published"] == 1
    assert result["external_publish_confirmation_phrase"] == "ПУБЛИКУЮ"
    assert captured["dispatch"] == {"business_id": "biz-1", "batch_size": 10}


def test_run_scoped_social_dispatch_once_rejects_live_api_preflight_block(monkeypatch):
    def fake_preflight(user_id, business_id, batch_size=10):
        return {
            "business_id": business_id,
            "summary": {"due_posts": 1, "skipped_no_access": 0, "api_preflight_blocked_due_posts": 1},
        }

    def fail_dispatch(*args, **kwargs):
        raise AssertionError("dispatch must not run when live API preflight blocks due posts")

    monkeypatch.setattr(social_post_service, "get_social_launch_preflight", fake_preflight)
    monkeypatch.setattr(social_post_service, "dispatch_due_social_posts", fail_dispatch)

    error = None
    try:
        run_scoped_social_dispatch_once("user-1", "biz-1", approved=True)
    except PermissionError:
        error = sys.exc_info()[1]

    assert error is not None
    assert "Live API-проверка" in str(error)


def test_api_preflight_blocked_due_posts_include_recovery_actions():
    blocked = _api_preflight_blocked_due_posts(
        [
            {
                "id": "post-1",
                "content_plan_item_id": "item-1",
                "platform": "telegram",
                "platform_label": "Telegram",
                "dispatch_action": "publish_api",
            },
            {
                "id": "post-2",
                "platform": "vk",
                "dispatch_action": "manual_handoff",
            },
        ],
        [
            {
                "platform": "telegram",
                "ready": False,
                "status": "missing_keys",
                "message_ru": "Для Telegram нужны ключи.",
                "message_en": "Telegram needs keys.",
            },
            {
                "platform": "vk",
                "ready": False,
                "status": "missing_permissions",
            },
        ],
    )

    assert len(blocked) == 1
    assert blocked[0]["id"] == "post-1"
    assert blocked[0]["content_plan_item_id"] == "item-1"
    assert blocked[0]["settings_path"] == "/dashboard/settings?focus=channels"
    assert blocked[0]["recoverable"] is True
    assert "telegram_bot_token" in blocked[0]["next_action_ru"]
    assert "Worker не будет публиковать" in blocked[0]["safety_summary_ru"]


def test_run_scoped_social_dispatch_once_respects_launch_gate(monkeypatch):
    def fake_preflight(user_id, business_id, batch_size=10):
        return {
            "business_id": business_id,
            "launch_gate": {
                "allowed": False,
                "next_action_ru": "Подготовьте, подтвердите и поставьте хотя бы один пост в расписание.",
            },
            "summary": {"due_posts": 0, "skipped_no_access": 0, "api_preflight_blocked_due_posts": 0},
        }

    def fail_dispatch(*args, **kwargs):
        raise AssertionError("dispatch must not run when launch gate is closed")

    monkeypatch.setattr(social_post_service, "get_social_launch_preflight", fake_preflight)
    monkeypatch.setattr(social_post_service, "dispatch_due_social_posts", fail_dispatch)

    error = None
    try:
        run_scoped_social_dispatch_once("user-1", "biz-1", approved=True)
    except PermissionError:
        error = sys.exc_info()[1]

    assert error is not None
    assert "поставьте хотя бы один пост" in str(error)


def test_create_supervised_publish_task_requires_explicit_approval_before_db(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("supervised task must not touch DB without approval")

    monkeypatch.setattr(social_post_service, "DatabaseManager", fail_if_called)

    error = None
    try:
        create_supervised_publish_task("user-1", "post-map", approved=False)
    except PermissionError:
        error = sys.exc_info()[1]

    assert error is not None
    assert "явное подтверждение" in str(error)


def test_create_supervised_publish_task_reuses_controlled_handoff_helper(monkeypatch):
    captured = {}
    post = {
        "id": "post-map",
        "business_id": "biz-1",
        "platform": "yandex_maps",
        "status": "approved",
        "approved_at": "2026-06-19T10:00:00+00:00",
        "platform_text": "Текст для карт",
    }

    monkeypatch.setattr(social_post_service, "DatabaseManager", FakeQueueFallbackDB)
    monkeypatch.setattr(social_post_service, "ensure_social_post_tables", lambda cursor: None)
    monkeypatch.setattr(
        social_post_service,
        "_load_post_for_user",
        lambda cursor, user_id, post_id: captured.setdefault(
            "load",
            {"user_id": user_id, "post_id": post_id},
        ) and post,
    )

    def fake_create(cursor, loaded_post):
        captured["create"] = loaded_post
        return {
            **loaded_post,
            "status": "needs_supervised_publish",
            "automation_task_id": "task-1",
        }

    monkeypatch.setattr(social_post_service, "_create_supervised_publish_task", fake_create)

    result = create_supervised_publish_task("user-1", "post-map", approved=True)

    assert result["status"] == "needs_supervised_publish"
    assert result["automation_task_id"] == "task-1"
    assert captured["load"] == {"user_id": "user-1", "post_id": "post-map"}
    assert captured["create"]["id"] == "post-map"
    assert FakeQueueFallbackDB.last_conn.committed is True


def test_collect_due_social_post_metrics_can_scope_to_one_business(monkeypatch):
    monkeypatch.setattr(social_post_service, "DatabaseManager", FakeDispatchScopeDB)
    monkeypatch.setattr(social_post_service, "ensure_social_post_tables", lambda cursor: None)
    monkeypatch.setenv("SOCIAL_POST_METRICS_BUSINESS_ID", "biz-metrics")
    monkeypatch.delenv("SOCIAL_POST_METRICS_ALLOW_UNSCOPED", raising=False)

    result = collect_due_social_post_metrics(batch_size=999)

    assert result["picked"] == 0
    assert result["business_scope"] == "biz-metrics"
    assert "sp.business_id = %s" in FakeDispatchScopeCursor.last_query
    assert FakeDispatchScopeCursor.last_params == ("biz-metrics", 500)


def test_collect_due_social_post_metrics_blocks_unscoped_by_default(monkeypatch):
    def fail_if_db_opens():
        raise AssertionError("unscoped metrics must not open DB")

    monkeypatch.delenv("SOCIAL_POST_METRICS_BUSINESS_ID", raising=False)
    monkeypatch.delenv("SOCIAL_POST_METRICS_ALLOW_UNSCOPED", raising=False)
    monkeypatch.setattr(social_post_service, "DatabaseManager", fail_if_db_opens)

    result = collect_due_social_post_metrics(batch_size=50)

    assert result["picked"] == 0
    assert result["blocked"] is True
    assert result["blocked_reason"] == "business_scope_required"


def test_run_scoped_social_metrics_once_requires_approval_before_access_check(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("metrics collection must not check access without approval")

    monkeypatch.setattr(social_post_service, "DatabaseManager", fail_if_called)

    error = None
    try:
        run_scoped_social_metrics_once("user-1", "biz-1", approved=False)
    except PermissionError:
        error = sys.exc_info()[1]

    assert error is not None
    assert "явное подтверждение" in str(error)


def test_run_scoped_social_metrics_once_collects_only_requested_business(monkeypatch):
    captured = {}
    monkeypatch.setattr(social_post_service, "DatabaseManager", FakeDispatchScopeDB)
    monkeypatch.setattr(social_post_service, "ensure_social_post_tables", lambda cursor: None)
    monkeypatch.setattr(
        social_post_service,
        "_require_business_access",
        lambda cursor, user_id, business_id: captured.setdefault(
            "access",
            {"user_id": user_id, "business_id": business_id},
        ),
    )

    def fake_collect_due(batch_size=50, business_id=""):
        captured["collect_due"] = {"batch_size": batch_size, "business_id": business_id}
        return {
            "picked": 3,
            "collected": 2,
            "failed": 1,
            "errors": [{"id": "post-3", "error": "temporary"}],
            "business_scope": business_id,
            "metric_details": [
                {
                    "post_id": "post-1",
                    "platform": "telegram",
                    "leads": 1,
                    "inquiries": 2,
                    "comments": 3,
                    "shares": 1,
                    "clicks": 4,
                    "likes": 5,
                    "views": 100,
                },
                {
                    "post_id": "post-2",
                    "platform": "vk",
                    "leads": 0,
                    "inquiries": 1,
                    "comments": 1,
                    "shares": 0,
                    "clicks": 2,
                    "likes": 7,
                    "views": 80,
                },
            ],
        }

    monkeypatch.setattr(social_post_service, "collect_due_social_post_metrics", fake_collect_due)

    result = run_scoped_social_metrics_once("user-1", "biz-1", batch_size=500, approved=True)

    assert result["business_id"] == "biz-1"
    assert result["batch_size"] == 100
    assert result["external_publish_performed"] is False
    assert result["metrics_result"]["collected"] == 2
    assert result["metrics_learning_packet"]["schema"] == "localos_social_metrics_learning_packet_v1"
    assert result["metrics_learning_packet"]["status"] == "ready_from_leads"
    assert result["metrics_learning_packet"]["primary_result_total"] == 4
    assert result["metrics_learning_packet"]["early_signal_total"] == 203
    assert result["metrics_learning_packet"]["safe_to_recommend_next_plan"] is True
    assert result["metrics_learning_packet"]["safe_to_apply_without_approval"] is False
    assert result["metrics_learning_packet"]["external_publish_performed"] is False
    assert "ошибок 1" in result["message_ru"]
    assert captured["access"] == {"user_id": "user-1", "business_id": "biz-1"}
    assert captured["collect_due"] == {"batch_size": 100, "business_id": "biz-1"}


def test_collect_vk_post_metrics_reads_wall_counters(monkeypatch):
    class FakeResponse:
        def read(self):
            return json.dumps(
                {
                    "response": [
                        {
                            "views": {"count": 120},
                            "likes": {"count": 7},
                            "comments": {"count": 3},
                            "reposts": {"count": 2},
                        }
                    ]
                }
            ).encode("utf-8")

        def close(self):
            pass

    requested_urls = []
    monkeypatch.setattr(
        social_post_service,
        "_find_active_external_account",
        lambda cursor, business_id, sources: {"id": "vk-1", "external_id": "12345", "auth_data_encrypted": "x"},
    )
    monkeypatch.setattr(social_post_service, "_external_account_auth_data", lambda account: {"access_token": "token", "scope": "wall"})
    monkeypatch.setattr(
        social_post_service.urllib.request,
        "urlopen",
        lambda req, timeout=15: (requested_urls.append(req.full_url) or FakeResponse()),
    )

    metrics = _collect_vk_post_metrics(
        object(),
        {
            "id": "post-1",
            "business_id": "biz-1",
            "platform": "vk",
            "provider_post_id": "678",
            "provider_post_url": "https://vk.com/wall-12345_678",
        },
    )

    assert metrics["status"] == "vk_metrics_collected"
    assert metrics["views"] == 120
    assert metrics["reach"] == 120
    assert metrics["likes"] == 7
    assert metrics["comments"] == 3
    assert metrics["shares"] == 2
    assert "wall.getById" in requested_urls[0]
    assert "posts=-12345_678" in requested_urls[0]


def test_telegram_api_channel_preflight_checks_bot_and_chat_without_publish(monkeypatch):
    class FakeResponse:
        status = 200

        def __init__(self, payload):
            self.payload = payload

        def read(self):
            return json.dumps(self.payload).encode("utf-8")

        def close(self):
            pass

    requested_urls = []
    monkeypatch.setattr(
        social_post_service,
        "_load_business_publish_context",
        lambda cursor, business_id: {"telegram_bot_token": "encrypted", "telegram_chat_id": "@localos_test"},
    )
    monkeypatch.setattr(social_post_service, "decode_telegram_bot_token", lambda value: "telegram-token")

    def fake_urlopen(req, timeout=10):
        requested_urls.append(req.full_url)
        if "getChat" in req.full_url and "getChatMember" not in req.full_url:
            return FakeResponse({"ok": True, "result": {"id": "@localos_test", "type": "channel"}})
        if "getChatMember" in req.full_url:
            return FakeResponse({"ok": True, "result": {"status": "administrator", "can_post_messages": True}})
        return FakeResponse({"ok": True, "result": {"id": 100}})

    monkeypatch.setattr(
        social_post_service,
        "telegram_urlopen",
        fake_urlopen,
    )

    result = social_post_service._telegram_api_channel_preflight(object(), "biz-1")

    assert result["ready"] is True
    assert result["read_only"] is True
    assert result["external_publish_performed"] is False
    assert any("getMe" in url for url in requested_urls)
    assert any("getChat" in url for url in requested_urls)
    assert any("getChatMember" in url for url in requested_urls)
    assert all("sendMessage" not in url for url in requested_urls)
    assert [item["key"] for item in result["connection_checks"]][-3:] == [
        "telegram_get_me",
        "telegram_get_chat",
        "telegram_publish_permission_live",
    ]


def test_telegram_api_channel_preflight_blocks_channel_without_post_permission(monkeypatch):
    class FakeResponse:
        status = 200

        def __init__(self, payload):
            self.payload = payload

        def read(self):
            return json.dumps(self.payload).encode("utf-8")

        def close(self):
            pass

    monkeypatch.setattr(
        social_post_service,
        "_load_business_publish_context",
        lambda cursor, business_id: {"telegram_bot_token": "encrypted", "telegram_chat_id": "@localos_test"},
    )
    monkeypatch.setattr(social_post_service, "decode_telegram_bot_token", lambda value: "telegram-token")

    def fake_urlopen(req, timeout=10):
        if "getChat" in req.full_url and "getChatMember" not in req.full_url:
            return FakeResponse({"ok": True, "result": {"id": "@localos_test", "type": "channel"}})
        if "getChatMember" in req.full_url:
            return FakeResponse({"ok": True, "result": {"status": "member", "can_post_messages": False}})
        return FakeResponse({"ok": True, "result": {"id": 100}})

    monkeypatch.setattr(social_post_service, "telegram_urlopen", fake_urlopen)

    result = social_post_service._telegram_api_channel_preflight(object(), "biz-1")

    assert result["ready"] is False
    assert result["status"] == "missing_permissions"
    assert result["external_publish_performed"] is False
    assert result["connection_checks"][-1]["key"] == "telegram_publish_permission_live"
    assert result["connection_checks"][-1]["ok"] is False
    assert "can_post_messages=False" in result["connection_checks"][-1]["detail_ru"]
    assert "не имеет права" in result["message_ru"]


def test_vk_api_channel_preflight_uses_read_only_wall_get(monkeypatch):
    class FakeResponse:
        status = 200

        def read(self):
            return json.dumps({"response": {"count": 0, "items": []}}).encode("utf-8")

        def close(self):
            pass

    requested_urls = []
    monkeypatch.setattr(
        social_post_service,
        "_find_active_external_account",
        lambda cursor, business_id, sources: {"id": "vk-1", "external_id": "12345", "auth_data_encrypted": "x"},
    )
    monkeypatch.setattr(
        social_post_service,
        "_external_account_auth_data",
        lambda account: {"access_token": "vk-token", "owner_id": "-12345", "scope": "wall", "api_version": "5.199"},
    )
    monkeypatch.setattr(
        social_post_service.urllib.request,
        "urlopen",
        lambda req, timeout=10: (requested_urls.append(req.full_url) or FakeResponse()),
    )

    result = social_post_service._vk_api_channel_preflight(object(), "biz-1")

    assert result["ready"] is True
    assert result["read_only"] is True
    assert result["external_publish_performed"] is False
    assert requested_urls
    assert "wall.get" in requested_urls[0]
    assert "wall.post" not in requested_urls[0]
    assert result["connection_checks"][-1]["key"] == "vk_wall_read_probe"


def test_api_channel_preflight_covers_all_api_channels_without_publish(monkeypatch):
    class FakeConn:
        def cursor(self):
            return object()

    class FakeDB:
        conn = FakeConn()

        def close(self):
            pass

    monkeypatch.setattr(social_post_service, "DatabaseManager", FakeDB)
    monkeypatch.setattr(social_post_service, "_require_business_access", lambda cursor, user_id, business_id: None)
    monkeypatch.setattr(
        social_post_service,
        "_telegram_api_channel_preflight",
        lambda cursor, business_id: {"platform": "telegram", "ready": True},
    )
    monkeypatch.setattr(
        social_post_service,
        "_vk_api_channel_preflight",
        lambda cursor, business_id: {"platform": "vk", "ready": True},
    )
    monkeypatch.setattr(
        social_post_service,
        "_google_business_api_channel_preflight",
        lambda cursor, business_id: {"platform": "google_business", "ready": False, "status": "missing_binding"},
    )
    monkeypatch.setattr(
        social_post_service,
        "_meta_api_channel_preflight",
        lambda cursor, business_id, platform: {"platform": platform, "ready": False, "status": "adapter_pending"},
    )

    result = social_post_service.check_social_api_channel_preflight("user-1", "biz-1")

    assert [item["platform"] for item in result["api_preflight"]] == [
        "telegram",
        "vk",
        "google_business",
        "instagram",
        "facebook",
    ]
    assert result["summary"] == {"checked": 5, "ready": 2, "needs_attention": 3}
    assert result["read_only"] is True
    assert result["external_publish_performed"] is False


def test_api_channel_preflight_result_exposes_setup_path_and_missing_fields():
    telegram = social_post_service._api_channel_preflight_result(
        "telegram",
        False,
        "missing_keys",
        [],
        "missing",
        "missing",
    )
    vk = social_post_service._api_channel_preflight_result(
        "vk",
        False,
        "missing_permissions",
        [],
        "missing",
        "missing",
    )
    google = social_post_service._api_channel_preflight_result(
        "google_business",
        False,
        "missing_binding",
        [],
        "missing",
        "missing",
    )
    instagram = social_post_service._api_channel_preflight_result(
        "instagram",
        False,
        "missing_connection",
        [],
        "missing",
        "missing",
    )
    facebook = social_post_service._api_channel_preflight_result(
        "facebook",
        False,
        "missing_permissions",
        [],
        "missing",
        "missing",
    )

    assert telegram["settings_path"] == "/dashboard/settings?focus=telegram"
    assert telegram["missing_fields"] == ["telegram_bot_token", "telegram_chat_id"]
    assert vk["settings_path"] == "/dashboard/settings?focus=vk"
    assert vk["missing_fields"] == ["vk_access_token.wall_post_scope"]
    assert google["settings_path"] == "/dashboard/settings?focus=google_business"
    assert google["missing_fields"] == ["google_business_account", "google_business_location"]
    assert instagram["settings_path"] == "/dashboard/settings?focus=instagram"
    assert "instagram_business_account" in instagram["missing_fields"]
    assert facebook["settings_path"] == "/dashboard/settings?focus=facebook"
    assert facebook["missing_fields"] == ["meta_permissions.pages_manage_posts"]


def test_google_business_api_channel_preflight_requires_location(monkeypatch):
    monkeypatch.setattr(
        social_post_service,
        "_find_active_external_account",
        lambda cursor, business_id, sources: {"id": "google-1", "external_id": ""},
    )

    missing_location = social_post_service._google_business_api_channel_preflight(
        object(),
        "biz-1",
    )

    assert missing_location["ready"] is False
    assert missing_location["platform"] == "google_business"
    assert missing_location["status"] == "missing_binding"


def test_meta_api_channel_preflight_is_blocked_until_native_publish(monkeypatch):
    monkeypatch.setattr(
        social_post_service,
        "_find_active_external_account",
        lambda cursor, business_id, sources: {"id": "meta-1", "external_id": "page-1", "auth_data_encrypted": "x"},
    )
    monkeypatch.setattr(
        social_post_service,
        "_external_account_auth_data",
        lambda account: {"access_token": "token", "scope": "pages_manage_posts"},
    )

    result = social_post_service._meta_api_channel_preflight(object(), "biz-1", "facebook")

    assert result["platform"] == "facebook"
    assert result["ready"] is False
    assert result["status"] == "adapter_pending"
    assert result["read_only"] is True
    assert result["external_publish_performed"] is False
    assert "manual fallback" in result["message_en"]


def test_preview_dispatch_decision_publish_api_when_channel_ready(monkeypatch):
    monkeypatch.setattr(social_post_service, "_queue_preflight_block", lambda cursor, post: {})

    preview = _preview_dispatch_decision(
        None,
        {
            "id": "p-api",
            "business_id": "b1",
            "content_plan_id": "plan1",
            "content_plan_item_id": "item1",
            "platform": "telegram",
            "publish_mode": "api",
            "status": "queued",
            "approved_at": "2026-06-19T10:00:00+00:00",
            "platform_text": "Готовый текст",
        },
    )

    assert preview["dry_run"] is True
    assert preview["dispatch_action"] == "publish_api"
    assert preview["would_status"] == "published_or_failed"
    assert preview["external_publish"] is True
    assert preview["approval_required"] is True
    assert preview["action_label_ru"] == "API-публикация"
    assert "published или failed" in preview["safety_summary_ru"]
    assert "Channel is ready" in preview["reason_label_en"]


def test_preview_dispatch_decision_blocks_api_when_preflight_missing(monkeypatch):
    monkeypatch.setattr(
        social_post_service,
        "_queue_preflight_block",
        lambda cursor, post: {
            "status": "needs_manual_publish",
            "last_error": "Для Telegram нужны telegram_bot_token и telegram_chat_id бизнеса.",
            "metadata_json": {"queue_preflight_status": "missing_keys"},
        },
    )

    preview = _preview_dispatch_decision(
        None,
        {
            "id": "p-blocked",
            "business_id": "b1",
            "platform": "telegram",
            "publish_mode": "api",
            "status": "queued",
            "approved_at": "2026-06-19T10:00:00+00:00",
            "platform_text": "Готовый текст",
        },
    )

    assert preview["dispatch_action"] == "manual_handoff"
    assert preview["would_status"] == "needs_manual_publish"
    assert preview["external_publish"] is False
    assert preview["metadata_json"]["queue_preflight_status"] == "missing_keys"
    assert preview["action_label_en"] == "Manual fallback"
    assert "Worker не будет публиковать наружу" in preview["safety_summary_ru"]


def test_preview_dispatch_decision_maps_never_autopublishes(monkeypatch):
    monkeypatch.setattr(social_post_service, "openclaw_browser_available", lambda: True)
    monkeypatch.setenv("OPENCLAW_SOCIAL_SUPERVISED_CALLBACK_URL", "https://openclaw.example/localos/social")
    preview = _preview_dispatch_decision(
        None,
        {
            "id": "p-map",
            "business_id": "b1",
            "platform": "yandex_maps",
            "publish_mode": "openclaw_browser",
            "status": "queued",
            "approved_at": "2026-06-19T10:00:00+00:00",
            "platform_text": "Готовый текст",
        },
    )

    assert preview["dispatch_action"] == "create_supervised_task"
    assert preview["would_status"] == "needs_supervised_publish"
    assert preview["external_publish"] is False
    assert preview["stop_before_final_publish"] is True
    assert preview["action_label_ru"] == "Контролируемое размещение"
    assert "не нажмёт финальную кнопку" in preview["safety_summary_ru"]


def test_preview_dispatch_decision_blocks_empty_copy_before_worker_publish(monkeypatch):
    monkeypatch.setattr(social_post_service, "_queue_preflight_block", lambda cursor, post: {})

    preview = _preview_dispatch_decision(
        None,
        {
            "id": "p-empty",
            "business_id": "b1",
            "platform": "telegram",
            "publish_mode": "api",
            "status": "queued",
            "approved_at": "2026-06-19T10:00:00+00:00",
            "platform_text": "   ",
            "base_text": "",
        },
    )

    assert preview["dispatch_action"] == "manual_handoff"
    assert preview["would_status"] == "needs_review"
    assert preview["reason"] == "empty_post_copy"
    assert preview["external_publish"] is False
    assert "сначала нужен текст" in preview["safety_summary_ru"]


def test_rehearse_social_post_publish_reports_api_ready_without_provider_write(monkeypatch):
    monkeypatch.setattr(social_post_service, "DatabaseManager", FakeDispatchScopeDB)
    monkeypatch.setattr(social_post_service, "ensure_social_post_tables", lambda cursor: None)
    monkeypatch.setattr(
        social_post_service,
        "_load_post_for_user",
        lambda cursor, user_id, post_id: {
            "id": post_id,
            "business_id": "biz-1",
            "platform": "telegram",
            "publish_mode": "api",
            "status": "queued",
            "approved_at": "2026-06-19T10:00:00+00:00",
            "platform_text": "Пост готов к публикации",
            "base_text": "Пост готов к публикации",
        },
    )
    monkeypatch.setattr(social_post_service, "_queue_preflight_block", lambda cursor, post: {})
    monkeypatch.setattr(
        social_post_service,
        "_publish_api_post",
        lambda cursor, post: (_ for _ in ()).throw(AssertionError("rehearsal must not call provider publish")),
    )

    rehearsal = rehearse_social_post_publish("user-1", "post-ready")

    assert rehearsal["schema"] == "localos_social_publish_rehearsal_v1"
    assert rehearsal["dry_run"] is True
    assert rehearsal["ready_for_execution"] is True
    assert rehearsal["external_publish_performed"] is False
    assert rehearsal["provider_write_performed"] is False
    assert rehearsal["would_external_publish"] is True
    assert rehearsal["dispatch_decision"]["dispatch_action"] == "publish_api"
    assert rehearsal["blockers"] == []
    assert "канал готов" in rehearsal["summary_ru"]


def test_rehearse_social_post_publish_blocks_missing_approval(monkeypatch):
    monkeypatch.setattr(social_post_service, "DatabaseManager", FakeDispatchScopeDB)
    monkeypatch.setattr(social_post_service, "ensure_social_post_tables", lambda cursor: None)
    monkeypatch.setattr(
        social_post_service,
        "_load_post_for_user",
        lambda cursor, user_id, post_id: {
            "id": post_id,
            "business_id": "biz-1",
            "platform": "vk",
            "publish_mode": "api",
            "status": "needs_review",
            "approved_at": None,
            "platform_text": "Текст есть, но approval нет",
            "base_text": "Текст есть, но approval нет",
        },
    )
    monkeypatch.setattr(social_post_service, "_queue_preflight_block", lambda cursor, post: {})

    rehearsal = rehearse_social_post_publish("user-1", "post-needs-review")

    assert rehearsal["ready_for_execution"] is False
    assert rehearsal["external_publish_performed"] is False
    assert rehearsal["provider_write_performed"] is False
    assert rehearsal["blockers"][0]["code"] == "missing_approval"
    assert "подтвердить" in rehearsal["summary_ru"]


def test_rehearse_social_posts_publish_summarizes_ready_and_blocked(monkeypatch):
    posts = {
        "post-ready": {
            "id": "post-ready",
            "business_id": "biz-1",
            "platform": "telegram",
            "publish_mode": "api",
            "status": "queued",
            "approved_at": "2026-06-19T10:00:00+00:00",
            "platform_text": "Готовый пост",
            "base_text": "Готовый пост",
        },
        "post-blocked": {
            "id": "post-blocked",
            "business_id": "biz-1",
            "platform": "vk",
            "publish_mode": "api",
            "status": "needs_review",
            "approved_at": None,
            "platform_text": "Текст без approval",
            "base_text": "Текст без approval",
        },
    }
    monkeypatch.setattr(social_post_service, "DatabaseManager", FakeDispatchScopeDB)
    monkeypatch.setattr(social_post_service, "ensure_social_post_tables", lambda cursor: None)
    monkeypatch.setattr(
        social_post_service,
        "_load_post_for_user",
        lambda cursor, user_id, post_id: posts[post_id],
    )
    monkeypatch.setattr(social_post_service, "_queue_preflight_block", lambda cursor, post: {})
    monkeypatch.setattr(
        social_post_service,
        "_publish_api_post",
        lambda cursor, post: (_ for _ in ()).throw(AssertionError("bulk rehearsal must not call provider publish")),
    )

    payload = rehearse_social_posts_publish("user-1", ["post-ready", "post-blocked"])

    assert payload["schema"] == "localos_social_publish_rehearsal_bulk_v1"
    assert payload["dry_run"] is True
    assert payload["external_publish_performed"] is False
    assert payload["provider_write_performed"] is False
    assert payload["summary"]["status"] == "partial"
    assert payload["summary"]["ready"] == 1
    assert payload["summary"]["api_ready"] == 1
    assert payload["summary"]["manual_or_blocked"] == 1
    assert payload["rehearsals"][1]["blockers"][0]["code"] == "missing_approval"


def test_publish_social_post_moves_empty_copy_back_to_review(monkeypatch):
    monkeypatch.setattr(social_post_service, "DatabaseManager", FakePublishEmptyCopyDB)
    monkeypatch.setattr(social_post_service, "ensure_social_post_tables", lambda cursor: None)
    monkeypatch.setattr(
        social_post_service,
        "_load_post_for_user",
        lambda cursor, user_id, post_id: {
            "id": post_id,
            "business_id": "biz-1",
            "platform": "telegram",
            "publish_mode": "api",
            "status": "queued",
            "approved_at": "2026-06-19T10:00:00+00:00",
            "platform_text": " ",
            "base_text": "",
        },
    )
    monkeypatch.setattr(
        social_post_service,
        "_publish_api_post",
        lambda cursor, post: (_ for _ in ()).throw(AssertionError("empty post must not call provider")),
    )

    post = publish_social_post("user-1", "post-empty")

    assert post["status"] == "needs_review"
    assert "заново подтвердить" in post["last_error"]
    assert FakePublishEmptyCopyDB.last_conn.committed is True
    assert FakePublishEmptyCopyDB.last_conn.rolled_back is False


def test_queue_preflight_blocks_api_channel_when_readiness_is_missing(monkeypatch):
    monkeypatch.setattr(
        social_post_service,
        "_build_channel_readiness",
        lambda cursor, business_id: [
            {
                "platform": "telegram",
                "ready": False,
                "status": "missing_keys",
            }
        ],
    )

    block = _queue_preflight_block(object(), {"business_id": "biz-1", "platform": "telegram"})

    assert block["status"] == "needs_manual_publish"
    assert block["metadata_json"]["queue_preflight_status"] == "missing_keys"
    assert "Telegram" in block["last_error"]


def test_queue_preflight_allows_ready_api_channel(monkeypatch):
    monkeypatch.setattr(
        social_post_service,
        "_build_channel_readiness",
        lambda cursor, business_id: [
            {
                "platform": "telegram",
                "ready": True,
                "status": "ready",
            }
        ],
    )

    assert _queue_preflight_block(object(), {"business_id": "biz-1", "platform": "telegram"}) == {}


def test_queue_social_post_api_preflight_fallback_does_not_create_supervised_ledger(monkeypatch):
    monkeypatch.setattr(social_post_service, "DatabaseManager", FakeQueueFallbackDB)
    monkeypatch.setattr(social_post_service, "ensure_social_post_tables", lambda cursor: None)
    monkeypatch.setattr(
        social_post_service,
        "_load_post_for_user",
        lambda cursor, user_id, post_id: {
            "id": post_id,
            "business_id": "biz-1",
            "platform": "telegram",
            "publish_mode": "api",
            "status": "approved",
            "approved_at": "2026-06-19T10:00:00+00:00",
        },
    )
    monkeypatch.setattr(
        social_post_service,
        "_queue_preflight_block",
        lambda cursor, post: {
            "status": "needs_manual_publish",
            "last_error": "Для Telegram нужны telegram_bot_token и telegram_chat_id бизнеса.",
            "metadata_json": {"queue_preflight_status": "missing_keys"},
        },
    )
    monkeypatch.setattr(
        social_post_service,
        "_record_social_supervised_handoff_ledger",
        lambda cursor, original, updated, automation_task_id: (_ for _ in ()).throw(AssertionError("map ledger only")),
    )

    post = queue_social_post("user-1", "post-api")

    assert post["status"] == "needs_manual_publish"
    assert post["last_error"] == "Для Telegram нужны telegram_bot_token и telegram_chat_id бизнеса."
    assert post["metadata_json"]["queue_preflight_status"] == "missing_keys"
    assert FakeQueueFallbackDB.last_conn.committed is True


def test_queue_preflight_does_not_block_supervised_maps():
    assert _queue_preflight_block(object(), {"business_id": "biz-1", "platform": "yandex_maps"}) == {}
    assert _queue_preflight_block(object(), {"business_id": "biz-1", "platform": "two_gis"}) == {}


def test_supervised_publish_state_uses_manual_fallback_without_browser(monkeypatch):
    monkeypatch.setattr(social_post_service, "openclaw_browser_available", lambda: False)

    state = _supervised_publish_state({"publish_mode": "openclaw_browser"})

    assert state["status"] == "needs_manual_publish"
    assert "OpenClaw browser-use" in str(state["last_error"])


def test_supervised_publish_state_uses_openclaw_when_available(monkeypatch):
    monkeypatch.setattr(social_post_service, "openclaw_browser_available", lambda: True)
    monkeypatch.setenv("OPENCLAW_SOCIAL_SUPERVISED_CALLBACK_URL", "https://openclaw.example/localos/social")

    state = _supervised_publish_state({"publish_mode": "openclaw_browser"})

    assert state["status"] == "needs_supervised_publish"
    assert state["last_error"] is None


def test_supervised_publish_state_uses_manual_fallback_without_delivery(monkeypatch):
    monkeypatch.setattr(social_post_service, "openclaw_browser_available", lambda: True)
    monkeypatch.delenv("OPENCLAW_SOCIAL_SUPERVISED_CALLBACK_URL", raising=False)
    monkeypatch.delenv("OPENCLAW_SUPERVISED_CALLBACK_URL", raising=False)

    state = _supervised_publish_state({"publish_mode": "openclaw_browser"})

    assert state["status"] == "needs_manual_publish"
    assert "OpenClaw browser-use" in str(state["last_error"])


def test_vk_post_url_uses_owner_and_post_id():
    assert _vk_post_url("-12345", "678") == "https://vk.com/wall-12345_678"
    assert _vk_post_url("", "678") == ""
    assert _vk_post_url("-12345", "") == ""


def test_vk_publish_binding_requires_wall_permission_when_scope_is_explicit():
    account = {"id": "a1", "external_id": "12345"}

    blocked = _vk_publish_binding(account, {"access_token": "token", "scope": "groups photos"})
    allowed = _vk_publish_binding(account, {"access_token": "token", "scope": "groups wall"})

    assert blocked["ready"] is False
    assert blocked["status"] == "missing_permissions"
    assert allowed["ready"] is True
    assert allowed["owner_id"] == "-12345"


def test_vk_publish_binding_accepts_owner_id_without_explicit_scope():
    binding = _vk_publish_binding(
        {"id": "a1", "external_id": ""},
        {"access_token": "token", "owner_id": "-777"},
    )

    assert binding["ready"] is True
    assert binding["status"] == "ready"


def test_meta_publish_status_separates_connection_binding_and_permissions():
    assert _meta_publish_status({}, {}, "facebook") == "missing_connection"
    assert _meta_publish_status({"id": "m1", "external_id": "page-1"}, {}, "facebook") == "missing_keys"
    assert _meta_publish_status({"id": "m1", "external_id": "page-1"}, {"access_token": "token", "scope": "email"}, "facebook") == "missing_permissions"
    assert _meta_publish_status({"id": "m1", "external_id": "page-1"}, {"access_token": "token", "scope": "pages_manage_posts"}, "facebook") == "ready"
    assert _meta_publish_status({"id": "m1", "external_id": "page-1"}, {"access_token": "token", "scope": "instagram_content_publish"}, "instagram") == "missing_binding"


def test_meta_channel_readiness_blocks_ready_until_native_publish_exists():
    readiness = _meta_channel_readiness(
        {"id": "m1", "external_id": "page-1"},
        {"access_token": "token", "scope": "pages_manage_posts"},
        "facebook",
    )

    assert readiness == {"ready": False, "status": "adapter_pending"}
    assert "API-публикация ещё не включена" in _channel_readiness_message("facebook", "adapter_pending", True)


def test_channel_readiness_exposes_owner_next_action():
    telegram = _channel_readiness("telegram", "api", False, "missing_keys")
    vk = _channel_readiness("vk", "api", False, "missing_permissions")
    google = _channel_readiness("google_business", "api", False, "missing_connection")
    meta = _channel_readiness("instagram", "api", False, "missing_binding")
    facebook = _channel_readiness("facebook", "api", False, "missing_connection")
    maps = _channel_readiness("yandex_maps", "manual", False, "manual_fallback")

    assert "telegram_bot_token" in telegram["next_action_en"]
    assert "цели публикации" in telegram["message_ru"]
    assert "Owner-bot/миниапп" in telegram["message_ru"]
    assert "channel/group telegram_chat_id" in telegram["next_action_en"]
    assert "wall.post" in vk["next_action_en"]
    assert "Instagram business account" in meta["next_action_en"]
    assert "ручного действия" in maps["next_action_ru"]
    assert "bot token" in telegram["setup_summary_en"]
    assert "wall.post" in vk["setup_summary_en"]
    assert "Instagram business account" in meta["setup_summary_en"]
    assert "Автопубликации нет" in maps["setup_summary_ru"]
    assert telegram["missing_fields"] == ["telegram_bot_token", "telegram_chat_id"]
    assert "Telegram-бота" in telegram["setup_steps_ru"][0]
    assert vk["missing_fields"] == ["vk_access_token.wall_post_scope"]
    assert "wall.post" in vk["setup_steps_en"][1]
    assert maps["missing_fields"] == []
    assert "Скопируйте" in maps["setup_steps_ru"][0]
    assert telegram["settings_path"] == "/dashboard/settings?focus=telegram"
    assert vk["settings_path"] == "/dashboard/settings?focus=vk"
    assert google["settings_path"] == "/dashboard/settings?focus=google_business"
    assert meta["settings_path"] == "/dashboard/settings?focus=instagram"
    assert facebook["settings_path"] == "/dashboard/settings?focus=facebook"


def test_channel_readiness_can_expose_safe_connection_checks():
    checks = _telegram_connection_checks(token_present=True, chat_present=False)
    readiness = _channel_readiness("telegram", "api", False, "missing_keys", checks)

    assert readiness["connection_checks"][0]["key"] == "telegram_bot_token"
    assert readiness["connection_checks"][0]["ok"] is True
    assert readiness["connection_checks"][1]["key"] == "telegram_chat_id"
    assert readiness["connection_checks"][1]["ok"] is False
    assert "token" not in readiness["connection_checks"][0]["detail_ru"].lower()


def test_provider_connection_checks_explain_vk_meta_and_maps_states():
    vk_checks = _vk_connection_checks(
        {"id": "vk-1", "external_id": "123"},
        {"access_token": "secret", "scope": "groups"},
        {"ready": False, "status": "missing_permissions", "token": "secret", "owner_id": "-123"},
    )
    meta_checks = _meta_connection_checks(
        {"id": "m1", "external_id": "page-1"},
        {"access_token": "secret", "scope": "pages_manage_posts"},
        "facebook",
        "adapter_pending",
    )
    maps_checks = _maps_connection_checks(False, {"target_url": ""})

    assert [item["key"] for item in vk_checks][:4] == [
        "vk_account",
        "vk_access_token",
        "vk_owner_id",
        "vk_wall_permission",
    ]
    assert vk_checks[3]["ok"] is False
    assert "wall.post" in vk_checks[3]["detail_en"]
    assert meta_checks[-1]["key"] == "meta_native_publish"
    assert meta_checks[-1]["ok"] is False
    assert meta_checks[-1]["state"] == "blocked"
    assert maps_checks[0]["key"] == "openclaw_browser_use"
    assert maps_checks[0]["state"] == "manual"
    assert maps_checks[2]["state"] == "human_approval"


def test_channel_readiness_next_action_distinguishes_ready_and_supervised():
    assert "расписание" in _channel_readiness_next_action("telegram", "ready", True)
    supervised_next = _channel_readiness_next_action("two_gis", "supervised_ready", True)

    assert "контролируемое размещение" in supervised_next
    assert "финальная кнопка" in supervised_next


def test_channel_readiness_setup_steps_are_actionable_for_ready_and_meta():
    ready_steps = _channel_readiness_setup_steps("telegram", "ready", True)
    ready_channel = _channel_readiness("telegram", "api", True, "ready")
    meta_steps = _channel_readiness("facebook", "api", False, "missing_permissions")

    assert ready_steps == [
        "Запустите live API-проверку без публикации.",
        "Проверьте preview поста.",
        "Утвердите текст и поставьте в расписание.",
    ]
    assert "live API-проверку без публикации" in ready_channel["setup_summary_ru"]
    assert "Проверить API-каналы" in ready_channel["next_action_ru"]
    assert "live API-проверку" in ready_channel["message_ru"]
    assert meta_steps["missing_fields"] == ["meta_permissions.pages_manage_posts"]
    assert "permissions" in meta_steps["setup_steps_en"][2]
    assert "permissions" in meta_steps["setup_summary_en"]


def test_vk_ready_readiness_requires_live_api_check_before_first_post():
    ready_channel = _channel_readiness("vk", "api", True, "ready")

    assert "live API-проверку без публикации" in ready_channel["setup_summary_ru"]
    assert "Проверить API-каналы" in ready_channel["next_action_ru"]
    assert "first API post" in ready_channel["message_en"]
    assert ready_channel["setup_steps_en"][0] == "Run the live API check without publishing."


def test_external_account_preflight_does_not_requeue_without_native_publish(monkeypatch):
    monkeypatch.setattr(
        social_post_service,
        "_find_active_external_account",
        lambda cursor, business_id, sources: {"id": "m1", "source": "meta", "external_id": "page-1"},
    )
    monkeypatch.setattr(
        social_post_service,
        "_external_account_auth_data",
        lambda account: {"access_token": "token", "scope": "pages_manage_posts"},
    )

    result = _publish_external_account_post(
        object(),
        {"business_id": "biz-1", "platform": "facebook"},
        ("meta", "facebook", "instagram"),
        "Meta Graph permissions или бизнес-аккаунт ещё не подтверждены.",
        "meta_graph_permissions_required",
    )

    assert result["status"] == "needs_manual_publish"
    assert result["metadata_json"]["provider_status"] == "meta_graph_permissions_required"
    assert "manual handoff" in result["metadata_json"]["provider_note"]


def test_telegram_publish_error_state_marks_connection_errors_recoverable():
    assert _telegram_publish_error_state(401, "Unauthorized") == (
        "needs_manual_publish",
        "telegram_connection_invalid",
    )
    assert _telegram_publish_error_state(400, "Bad Request: chat not found") == (
        "needs_manual_publish",
        "telegram_connection_invalid",
    )
    assert _telegram_publish_error_state(403, "Forbidden: bot was blocked by the user") == (
        "needs_manual_publish",
        "telegram_connection_invalid",
    )
    assert _telegram_publish_error_state(429, "Too Many Requests") == ("failed", "telegram_api_error")


def test_publish_telegram_post_sends_message_and_records_provider_evidence(monkeypatch):
    class FakeTelegramResponse:
        status = 200

        def read(self):
            return json.dumps(
                {
                    "ok": True,
                    "result": {
                        "message_id": 42,
                    },
                }
            ).encode("utf-8")

        def close(self):
            pass

    requests = []
    monkeypatch.setattr(
        social_post_service,
        "_load_business_publish_context",
        lambda cursor, business_id: {
            "telegram_bot_token": "encrypted-token",
            "telegram_chat_id": "@localos_channel",
        },
    )
    monkeypatch.setattr(social_post_service, "decode_telegram_bot_token", lambda value: "telegram-token")
    monkeypatch.setattr(
        social_post_service,
        "telegram_urlopen",
        lambda req, timeout=15: (requests.append(req) or FakeTelegramResponse()),
    )

    result = social_post_service._publish_telegram_post(
        object(),
        {
            "id": "post-telegram",
            "business_id": "biz-1",
            "platform": "telegram",
            "platform_text": "Пост для Telegram",
        },
    )

    assert result["status"] == "published"
    assert result["provider_post_id"] == "42"
    assert result["provider_post_url"] == "https://t.me/localos_channel/42"
    assert result["metadata_json"]["provider_status"] == "telegram_published"
    assert result["metadata_json"]["provider_write_performed"] is True
    assert result["metadata_json"]["external_publish_performed"] is True
    assert len(requests) == 1
    assert requests[0].full_url == "https://api.telegram.org/bottelegram-token/sendMessage"
    payload = json.loads(requests[0].data.decode("utf-8"))
    assert payload["chat_id"] == "@localos_channel"
    assert payload["text"] == "Пост для Telegram"


def test_publish_vk_post_calls_wall_post_and_records_provider_evidence(monkeypatch):
    class FakeVkResponse:
        def read(self):
            return json.dumps(
                {
                    "response": {
                        "post_id": 678,
                    },
                }
            ).encode("utf-8")

        def close(self):
            pass

    requests = []
    monkeypatch.setattr(
        social_post_service,
        "_find_active_external_account",
        lambda cursor, business_id, sources: {
            "id": "vk-1",
            "external_id": "12345",
            "auth_data_encrypted": "encrypted",
        },
    )
    monkeypatch.setattr(
        social_post_service,
        "_external_account_auth_data",
        lambda account: {
            "access_token": "vk-token",
            "owner_id": "-12345",
            "scope": "wall",
            "api_version": "5.199",
        },
    )
    monkeypatch.setattr(
        social_post_service.urllib.request,
        "urlopen",
        lambda req, timeout=15: (requests.append(req) or FakeVkResponse()),
    )

    result = social_post_service._publish_vk_post(
        object(),
        {
            "id": "post-vk",
            "business_id": "biz-1",
            "platform": "vk",
            "platform_text": "Пост для VK",
        },
    )

    assert result["status"] == "published"
    assert result["provider_post_id"] == "678"
    assert result["provider_post_url"] == "https://vk.com/wall-12345_678"
    assert result["metadata_json"]["provider_status"] == "vk_published"
    assert result["metadata_json"]["provider_write_performed"] is True
    assert result["metadata_json"]["external_publish_performed"] is True
    assert result["metadata_json"]["external_account_id"] == "vk-1"
    assert len(requests) == 1
    assert requests[0].full_url == "https://api.vk.com/method/wall.post"
    payload = social_post_service.urllib.parse.parse_qs(requests[0].data.decode("utf-8"))
    assert payload["access_token"] == ["vk-token"]
    assert payload["owner_id"] == ["-12345"]
    assert payload["message"] == ["Пост для VK"]


def test_openclaw_supervised_task_payload_stops_before_final_publish():
    payload = _build_openclaw_supervised_task_payload(
        {
            "id": "post-1",
            "business_id": "biz-1",
            "content_plan_id": "plan-1",
            "content_plan_item_id": "item-1",
            "platform": "yandex_maps",
            "platform_text": "Текст для карт",
            "approved_at": "2026-06-19T10:00:00+00:00",
            "approval_id": "approval-1",
            "media_json": [],
        },
        "task-1",
        {
            "business_name": "Studio",
            "location_label": "Москва, Тверская",
            "target_url": "https://yandex.ru/maps/org/123",
            "target_url_source": "businessmaplinks.yandex",
        },
    )

    assert payload["schema"] == "localos_social_supervised_publish_task_v1"
    assert payload["capability"] == "social.post.publish_supervised_browser"
    assert payload["risk_class"] == "external_publish"
    assert payload["approval_class"] == "external_publish"
    assert payload["stop_before_final_publish"] is True
    assert payload["auto_final_click_allowed"] is False
    assert payload["safety_contract"]["side_effect_policy"] == "fill_preview_only"
    assert payload["completion_contract"]["success_state"] == "preview_ready"
    assert payload["completion_contract"]["preview_required"] is True
    assert payload["completion_contract"]["browser_final_click_allowed"] is False
    assert "filled_text" in payload["completion_contract"]["required_result_fields"]
    assert "Остановиться перед финальной кнопкой публикации" in payload["handoff_checklist_ru"][3]
    assert "Stop before the final publish button" in payload["handoff_checklist_en"][3]
    assert "Финальную публикацию нажал человек" in payload["done_criteria_ru"][1]
    assert "final publish click" in payload["completion_contract"]["done_criteria_en"][1]
    assert "click_final_publish" in payload["safety_contract"]["forbidden_actions"]
    assert "show_preview" in payload["safety_contract"]["allowed_actions"]
    assert "предпросмотр" in payload["operator_next_action_ru"]
    assert payload["target"]["url"] == "https://yandex.ru/maps/org/123"
    assert payload["content"]["text"] == "Текст для карт"
    assert payload["approval_evidence"]["approval_id"] == "approval-1"
    assert "changed_ui" in payload["fallback"]["reasons"]


def test_supervised_publish_metadata_exposes_user_visible_contract(monkeypatch):
    monkeypatch.setattr(
        social_post_service,
        "_map_publish_target",
        lambda cursor, business_id, platform: {
            "business_name": "Salon",
            "location_label": "Moscow",
            "target_url": "https://2gis.ru/firm/1",
            "target_url_source": "businessmaplinks.two_gis",
            "profile_hint": "2ГИС профиль бизнеса",
        },
    )
    monkeypatch.setattr(
        social_post_service,
        "openclaw_browser_capability_status",
        lambda: {
            "ready": True,
            "status": "available",
            "source": "openclaw",
            "reason": "openclaw_supervised_browser_available",
        },
    )

    metadata = _supervised_publish_metadata(
        object(),
        {
            "id": "post-1",
            "business_id": "biz-1",
            "platform": "two_gis",
            "publish_mode": "openclaw_browser",
            "platform_text": "Текст поста",
            "approved_at": "2026-06-19T10:00:00+00:00",
        },
        "task-1",
    )

    supervised = metadata["supervised_publish"]
    assert supervised["capability"] == "social.post.publish_supervised_browser"
    assert supervised["openclaw_action_ref"] == "openclaw.browser.supervised_publish"
    assert supervised["task_status"] == "ready_for_supervised_or_manual_handoff"
    assert supervised["target_url"] == "https://2gis.ru/firm/1"
    assert supervised["copy_ready_text"] == "Текст поста"
    assert supervised["profile_hint"] == "2ГИС профиль бизнеса"
    assert supervised["final_publish_policy"] == "human_final_click_required"
    assert supervised["stop_before_final_publish"] is True
    assert supervised["completion_contract"]["success_state"] == "preview_ready"
    assert supervised["completion_contract"]["final_publish_click_owner"] == "human"
    assert "Остановиться перед финальной кнопкой публикации" in supervised["handoff_checklist_ru"][3]
    assert "Stop before the final publish button" in supervised["handoff_checklist_en"][3]
    assert "blocked_by_captcha" in supervised["completion_contract"]["allowed_result_statuses"]
    assert "Пост отмечен размещённым" in supervised["completion_contract"]["done_criteria_ru"][-1]
    assert "preview" in supervised["operator_next_action_en"]
    assert supervised["safety_contract"]["requires_final_human_confirmation"] is True
    assert "publish_without_human_confirmation" in supervised["safety_contract"]["forbidden_actions"]
    assert supervised["manual_handoff"]["schema"] == "localos_social_manual_publish_handoff_v1"
    assert supervised["manual_handoff"]["copy_ready_text"] == "Текст поста"
    assert supervised["manual_handoff"]["target_url"] == "https://2gis.ru/firm/1"
    assert supervised["manual_handoff"]["browser_final_click_allowed"] is False
    assert "Скопировать готовый текст" in supervised["manual_checklist_ru"][0]
    assert "Mark published" in supervised["manual_checklist_en"][-1]
    assert "captcha" in supervised["fallback_reasons"]
    assert supervised["openclaw_capability_status"]["ready"] is True
    assert supervised["handoff_state"]["schema"] == "localos_social_supervised_handoff_state_v1"
    assert supervised["handoff_state"]["state"] == "ready_for_openclaw_handoff"
    assert supervised["handoff_state"]["task_payload_ready"] is True
    assert supervised["handoff_state"]["openclaw_task_requested"] is False
    assert supervised["handoff_state"]["ledger_recorded"] is False
    assert supervised["handoff_state"]["browser_final_click_allowed"] is False
    assert "предпросмотр" in supervised["handoff_state"]["owner_next_action_ru"]


def test_supervised_handoff_state_explains_manual_fallback():
    state = social_post_service._social_supervised_handoff_state(
        {"publish_mode": "manual"},
        {"task_id": "task-1"},
        {"ready": False, "reason": "openclaw_catalog_not_configured"},
    )

    assert state["state"] == "manual_fallback_required"
    assert state["openclaw_ready"] is False
    assert state["task_payload_ready"] is True
    assert state["openclaw_task_requested"] is False
    assert state["ledger_recorded"] is False
    assert state["browser_final_click_allowed"] is False
    assert "ручной режим" in state["owner_status_ru"]
    assert "Отметьте" in state["owner_next_action_ru"] or "отметьте" in state["owner_next_action_ru"]


def test_next_plan_changes_prioritize_leads_before_reach():
    changes = _build_next_plan_changes(
        [
            {
                "item_id": "reach-item",
                "theme": "Большой охват",
                "goal": "Рассказать о салоне",
                "reach": 9000,
                "comments": 0,
                "inquiries": 0,
                "leads": 0,
            },
            {
                "item_id": "lead-item",
                "theme": "Запись на услугу",
                "goal": "Получить заявки",
                "reach": 10,
                "comments": 0,
                "inquiries": 0,
                "leads": 1,
            },
        ]
    )

    assert changes[0]["item_id"] == "lead-item"
    assert changes[0]["action"] == "repeat_winning_topic"


def test_next_plan_change_channel_breakdown_explains_where_to_repeat_or_fix():
    changes = _add_channel_breakdown_to_changes(
        [
            {
                "item_id": "item-1",
                "theme": "Запись на услугу",
                "action": "repeat_winning_topic",
                "proposed_goal": "Повторить",
            }
        ],
        [
            {
                "id": "post-telegram",
                "content_plan_item_id": "item-1",
                "platform": "telegram",
                "status": "published",
                "leads": 1,
                "inquiries": 0,
                "comments": 1,
                "reach": 30,
            },
            {
                "id": "post-vk",
                "content_plan_item_id": "item-1",
                "platform": "vk",
                "status": "published",
                "leads": 0,
                "inquiries": 0,
                "comments": 2,
                "reach": 500,
            },
            {
                "id": "post-yandex",
                "content_plan_item_id": "item-1",
                "platform": "yandex_maps",
                "status": "needs_manual_publish",
                "leads": 0,
                "inquiries": 0,
            },
        ],
    )

    breakdown = changes[0]["channel_breakdown"]
    assert breakdown["best_channels"][0]["platform"] == "telegram"
    assert breakdown["best_channels"][0]["reason_ru"]
    assert breakdown["weak_channels"][0]["platform"] == "yandex_maps"
    assert "Telegram" in breakdown["summary_ru"]


def test_social_learning_insights_explain_winners_weak_channels_and_no_result_topics():
    insights = _build_social_learning_insights(
        [
            {
                "item_id": "reach-item",
                "theme": "Охват без заявок",
                "reach": 9000,
                "comments": 0,
                "inquiries": 0,
                "leads": 0,
            },
            {
                "item_id": "lead-item",
                "theme": "Запись на услугу",
                "reach": 10,
                "comments": 0,
                "inquiries": 0,
                "leads": 1,
            },
            {
                "item_id": "empty-item",
                "theme": "Без результата",
                "reach": 0,
                "comments": 0,
                "inquiries": 0,
                "leads": 0,
            },
        ],
        [
            {
                "platform": "vk",
                "status": "published",
                "reach": 1000,
                "comments": 2,
                "inquiries": 0,
                "leads": 0,
            },
            {
                "platform": "telegram",
                "status": "published",
                "reach": 20,
                "comments": 0,
                "inquiries": 1,
                "leads": 0,
            },
        ],
    )

    assert insights["winning_topics"][0]["item_id"] == "lead-item"
    assert insights["no_result_topics"][0]["item_id"] == "empty-item"
    assert insights["weak_channels"][0]["platform"] == "vk"
    assert insights["owner_next_steps"][0]["key"] == "repeat_winner"
    assert insights["owner_next_steps"][1]["key"] == "fix_weak_channel"
    assert insights["cta_suggestions"][0]["ru"]
    assert insights["frequency_suggestions"][0]["ru"]


def test_social_learning_insights_give_simple_first_step_without_results():
    insights = _build_social_learning_insights([], [])

    assert insights["owner_next_steps"][0]["key"] == "publish_and_measure"
    assert "заявки" in insights["owner_next_steps"][0]["ru"]


def test_metric_totals_are_merged_back_into_collected_posts():
    cursor = FakeMetricTotalsCursor()
    posts = [
        {"id": "post-lead", "platform": "telegram", "status": "published", "leads": 0, "inquiries": 0},
        {"id": "post-empty", "platform": "vk", "status": "published"},
    ]

    enriched = _merge_metric_totals_into_posts(cursor, posts)

    assert cursor.params == (["post-lead", "post-empty"],)
    assert enriched[0]["leads"] == 2
    assert enriched[0]["inquiries"] == 1
    assert enriched[0]["comments"] == 2
    assert enriched[0]["reach"] == 10
    assert enriched[1]["id"] == "post-empty"
    assert "leads" not in enriched[1]


def test_dispatch_preview_readiness_explains_external_controlled_and_manual_work():
    readiness = _dispatch_preview_readiness(
        [
            {"id": "api-post", "dispatch_action": "publish_api"},
            {"id": "map-post", "dispatch_action": "create_supervised_task"},
            {"id": "manual-post", "dispatch_action": "manual_handoff"},
        ],
        {
            "publish_api": 1,
            "create_supervised_task": 1,
            "manual_handoff": 1,
        },
        skipped_no_access=2,
        business_scope="biz-1",
    )

    assert readiness["status"] == "external_publish_ready"
    assert readiness["due_count"] == 3
    assert readiness["external_publish_count"] == 1
    assert readiness["controlled_count"] == 1
    assert readiness["manual_count"] == 1
    assert readiness["skipped_no_access"] == 2
    assert readiness["safe_dry_run"] is True
    assert readiness["external_publish_requires_approval"] is True
    assert readiness["browser_final_click_allowed"] is False
    assert "approved" in readiness["message_en"]
    assert "biz-1" in readiness["next_action_en"]
    assert readiness["recommended_dispatch_env"]["SOCIAL_POST_DISPATCH_BUSINESS_ID"] == "biz-1"
    assert readiness["recommended_dispatch_env"]["SOCIAL_POST_DISPATCH_ENABLED"] == "true"
    assert readiness["first_cycle_steps"][0]["key"] == "api_publish_after_approval"
    assert readiness["first_cycle_steps"][0]["external_publish"] is True
    assert readiness["first_cycle_steps"][1]["key"] == "maps_controlled_without_final_click"
    assert readiness["first_cycle_steps"][1]["label_en"] == "Maps: supervised/manual without final click"
    assert readiness["first_cycle_steps"][1]["stop_before_final_publish"] is True
    assert readiness["first_cycle_steps"][2]["key"] == "manual_handoff_or_connection"
    assert readiness["first_cycle_steps"][3]["key"] == "skipped_no_access"
    assert readiness["first_api_proof_candidate"]["schema"] == "localos_social_first_api_proof_candidate_v1"
    assert readiness["first_api_proof_candidate"]["ready"] is True
    assert readiness["first_api_proof_candidate"]["id"] == "api-post"
    assert "provider_post_id/provider_post_url" in readiness["first_api_proof_candidate"]["proof_check_ru"]
    assert "реакции/заявки" in readiness["first_api_proof_candidate"]["metrics_followup_ru"]
    verification = readiness["first_cycle_verification"]
    assert verification["log_filter"] == "[SOCIAL_POST_DISPATCH]"
    assert verification["business_scope"] == "biz-1"
    assert verification["expected_statuses"][0]["key"] == "api_channels"
    assert verification["expected_statuses"][1]["key"] == "maps_controlled"
    assert "picked/published" in verification["checks_en"][1]
    assert "Проверка" in readiness["safety_notes_ru"][2]
    readiness_json = json.dumps(readiness, ensure_ascii=False)
    assert "controlled/manual" not in readiness_json
    assert "controlled task" not in readiness_json
    assert "supervised/manual" in readiness_json


def test_dispatch_preview_first_cycle_steps_keep_owner_safe_before_worker_launch():
    steps = _dispatch_preview_first_cycle_steps(2, 1, 3)

    assert steps[0]["label_ru"] == "API: публикация после подтверждения"
    assert steps[0]["count"] == 2
    assert steps[0]["external_publish"] is True
    assert steps[0]["requires_approval"] is True
    assert steps[1]["label_ru"] == "Карты: контроль/вручную без финального клика"
    assert steps[1]["label_en"] == "Maps: supervised/manual without final click"
    assert steps[1]["external_publish"] is False
    assert steps[1]["stop_before_final_publish"] is True
    assert steps[2]["label_ru"] == "Ручной режим или подключение канала"
    assert steps[2]["count"] == 3


def test_dispatch_preview_readiness_marks_no_due_posts_as_safe_noop():
    readiness = _dispatch_preview_readiness([], {}, skipped_no_access=0)

    assert readiness["status"] == "no_due_posts"
    assert readiness["due_count"] == 0
    assert readiness["external_publish_count"] == 0
    assert readiness["message_ru"]
    assert readiness["next_action_ru"]


def test_social_launch_preflight_payload_recommends_scoped_env_and_keeps_safety_invariants(monkeypatch):
    monkeypatch.delenv("SOCIAL_POST_DISPATCH_ENABLED", raising=False)
    monkeypatch.delenv("SOCIAL_POST_DISPATCH_BUSINESS_ID", raising=False)
    monkeypatch.delenv("SOCIAL_POST_DISPATCH_ALLOW_UNSCOPED", raising=False)
    payload = _build_social_launch_preflight_payload(
        "biz-1",
        [
            _channel_readiness("telegram", "api", True, "ready"),
            _channel_readiness("vk", "api", False, "missing_permissions"),
            _channel_readiness("yandex_maps", "manual", False, "manual_fallback"),
        ],
        {"api_ready": 1, "api_needs_attention": 1, "controlled_or_manual": 1},
        {
            "dry_run": True,
            "picked": 2,
            "skipped_no_access": 0,
            "readiness": {
                "status": "external_publish_ready",
                "due_count": 2,
                "external_publish_count": 1,
                "controlled_count": 1,
                "manual_count": 0,
                "skipped_no_access": 0,
                "first_api_proof_candidate": {
                    "schema": "localos_social_first_api_proof_candidate_v1",
                    "ready": True,
                    "id": "post-telegram",
                    "platform": "telegram",
                    "platform_label": "Telegram",
                    "proof_check_ru": "После worker должен появиться provider_post_id/provider_post_url.",
                    "metrics_followup_ru": "Если proof есть, сразу соберите реакции/заявки.",
                },
            },
        },
        launch_rehearsal={
            "schema": "localos_social_publish_rehearsal_bulk_v1",
            "dry_run": True,
            "external_publish_performed": False,
            "provider_write_performed": False,
            "rehearsals": [],
            "failed": [],
            "summary": {
                "status": "partial",
                "total": 2,
                "ready": 1,
                "blocked": 1,
                "failed": 0,
                "api_ready": 1,
                "supervised_ready": 0,
                "manual_or_blocked": 1,
                "browser_final_click_allowed": False,
                "message_ru": "Часть постов готова.",
                "message_en": "Some posts are ready.",
                "next_action_ru": "Исправьте первый блокер.",
                "next_action_en": "Fix the first blocker.",
            },
        },
    )

    assert payload["status"] == "ready_for_api_dispatch"
    assert payload["safe_to_enable_scoped_dispatch"] is True
    assert payload["summary"]["api_due_posts"] == 1
    assert payload["summary"]["controlled_due_posts"] == 1
    assert payload["summary"]["api_ready_channels"] == 1
    assert payload["summary"]["api_blocked_channels"] == 1
    assert payload["summary"]["blocked_api_channels"] == 1
    assert payload["summary"]["launch_rehearsal_ready_posts"] == 1
    assert payload["summary"]["launch_rehearsal_blocked_posts"] == 1
    assert payload["launch_rehearsal"]["schema"] == "localos_social_publish_rehearsal_bulk_v1"
    assert payload["launch_rehearsal"]["dry_run"] is True
    assert payload["launch_rehearsal"]["external_publish_performed"] is False
    assert payload["launch_rehearsal"]["provider_write_performed"] is False
    assert payload["launch_rehearsal"]["summary"]["api_ready"] == 1
    assert payload["launch_rehearsal"]["summary"]["browser_final_click_allowed"] is False
    assert payload["blocked_api_channels"][0]["platform"] == "vk"
    assert payload["controlled_channels"][0]["platform"] == "yandex_maps"
    assert payload["first_api_publish_readiness"]["schema"] == "localos_social_first_api_publish_readiness_v1"
    assert payload["first_api_publish_readiness"]["status"] == "partial_api_ready"
    assert payload["first_api_publish_readiness"]["ready"] is True
    assert payload["first_api_publish_readiness"]["recommended_start_platform"]["platform"] == "telegram"
    assert payload["first_api_publish_readiness"]["ready_platforms"][0]["platform"] == "telegram"
    assert payload["first_api_publish_readiness"]["blocked_platforms"][0]["platform"] == "vk"
    assert "approval" in payload["first_api_publish_readiness"]["publish_path_en"]
    assert "Telegram" in payload["first_api_publish_readiness"]["first_post_checklist_ru"][0]
    assert "approval" in payload["first_api_publish_readiness"]["first_post_checklist_en"][2]
    assert "Telegram" in payload["first_api_publish_readiness"]["first_api_launch_plan_ru"][0]
    assert "provider_post_id/provider_post_url" in payload["first_api_publish_readiness"]["proof_check_ru"]
    assert "заявки" in payload["first_api_publish_readiness"]["metrics_followup_ru"]
    assert "shortest path" in payload["first_api_publish_readiness"]["recommended_start_reason_en"]
    assert payload["recommended_env"]["dispatch"]["SOCIAL_POST_DISPATCH_BUSINESS_ID"] == "biz-1"
    assert payload["recommended_env"]["metrics"]["SOCIAL_POST_METRICS_BUSINESS_ID"] == "biz-1"
    assert payload["safety"]["approval_required"] is True
    assert payload["safety"]["browser_final_click_allowed"] is False
    assert payload["safety"]["maps_are_supervised_or_manual"] is True
    assert "SOCIAL_POST_DISPATCH_BUSINESS_ID=biz-1" in payload["next_action_ru"]
    assert payload["first_cycle_verification"]["log_filter"] == "[SOCIAL_POST_DISPATCH]"
    assert payload["first_cycle_verification"]["expected_statuses"][0]["key"] == "api_channels"
    assert payload["launch_runbook"]["ready"] is True
    assert payload["launch_runbook"]["scope"] == "biz-1"
    assert payload["launch_runbook"]["blocked_reason_ru"] == ""
    assert "SOCIAL_POST_DISPATCH_BUSINESS_ID=biz-1" in payload["launch_runbook"]["steps_ru"][0]
    assert "provider_post_id" in payload["launch_runbook"]["steps_ru"][3]
    assert "needs_supervised_publish" in payload["launch_runbook"]["success_criteria_ru"][1]
    assert payload["runtime_alignment"]["dispatch"]["status"]
    assert payload["runtime_alignment"]["dispatch"]["can_process_this_business"] is False
    assert payload["production_readiness"]["schema"] == "localos_social_production_readiness_v1"
    assert payload["production_readiness"]["status"] == "ready_after_worker_scope"
    assert payload["production_readiness"]["safe_to_enable_scoped_dispatch"] is True
    assert payload["production_readiness"]["ready_for_first_scoped_cycle"] is False
    assert payload["production_readiness"]["due_posts"] == 2
    assert payload["production_readiness"]["api_due_posts"] == 1
    assert payload["production_readiness"]["controlled_due_posts"] == 1
    assert payload["production_readiness"]["maps_are_supervised_or_manual"] is True
    assert payload["production_readiness"]["browser_final_click_allowed"] is False
    assert payload["launch_gate"]["schema"] == "localos_social_first_cycle_launch_gate_v1"
    assert payload["launch_gate"]["status"] == "ready_with_api_publish"
    assert payload["launch_gate"]["allowed"] is True
    assert payload["launch_gate"]["api_posts"] == 1
    assert payload["launch_gate"]["supervised_posts"] == 1
    assert payload["launch_gate"]["manual_posts"] == 0
    assert payload["launch_gate"]["requires_human_confirmation"] is True
    assert payload["launch_gate"]["browser_final_click_allowed"] is False
    assert "API-посты" in payload["launch_gate"]["summary_ru"]
    assert payload["first_api_proof_gate"]["schema"] == "localos_social_first_api_proof_gate_v1"
    assert payload["first_api_proof_gate"]["status"] == "ready_for_ui_run_once"
    assert payload["first_api_proof_gate"]["allowed"] is True
    assert payload["first_api_proof_gate"]["ui_run_once_allowed"] is True
    assert payload["first_api_proof_gate"]["background_worker_aligned"] is False
    assert payload["first_api_proof_gate"]["candidate"]["id"] == "post-telegram"
    assert "provider_post_id/provider_post_url" in payload["first_api_proof_gate"]["summary_ru"]
    assert payload["first_cycle_proof_packet"]["schema"] == "localos_social_first_cycle_proof_packet_v1"
    assert payload["first_cycle_proof_packet"]["status"] == "ready_for_one_cycle"
    assert payload["first_cycle_proof_packet"]["ready_to_run_once"] is True
    assert payload["first_cycle_proof_packet"]["api_proof_ready"] is True
    assert payload["first_cycle_proof_packet"]["dispatch_business_id"] == "biz-1"
    assert payload["first_cycle_proof_packet"]["candidate_platform_label"] == "Telegram"
    assert payload["first_cycle_proof_packet"]["browser_final_click_allowed"] is False
    assert "provider_post_id/provider_post_url" in payload["first_cycle_proof_packet"]["after_run_checks_ru"][1]
    assert payload["proof_requirements"]["schema"] == "localos_social_proof_requirements_v1"
    assert payload["proof_requirements"]["ready_groups"] == 2
    assert payload["proof_requirements"]["total_groups"] == 3
    assert payload["proof_requirements"]["external_publish_requires_approval"] is True
    assert payload["proof_requirements"]["browser_final_click_allowed"] is False
    proof_groups = {item["key"]: item for item in payload["proof_requirements"]["groups"]}
    assert proof_groups["telegram_vk_api_proof"]["state"] == "ready"
    assert "provider_post_id/provider_post_url" in proof_groups["telegram_vk_api_proof"]["summary_ru"]
    assert proof_groups["maps_supervised_handoff"]["state"] == "ready"
    assert "финальной кнопкой" in proof_groups["maps_supervised_handoff"]["checklist_ru"][2]
    assert proof_groups["metrics_and_recommendation"]["state"] == "waiting_for_publish"
    assert "Заявки и обращения" in payload["proof_requirements"]["primary_metric_ru"]
    live_checklist = {item["key"]: item for item in payload["live_validation_checklist"]}
    assert live_checklist["open_real_plan"]["status"] == "done"
    assert live_checklist["ready_to_run_one_cycle"]["status"] == "current"
    assert live_checklist["api_proof_after_run"]["status"] == "current"
    assert live_checklist["maps_supervised_not_autopublish"]["status"] == "current"
    assert live_checklist["collect_results_next"]["status"] == "pending"
    assert "Финальный клик" in live_checklist["maps_supervised_not_autopublish"]["detail_ru"]
    warning_keys = [item["key"] for item in payload["production_readiness"]["warnings"]]
    assert "dispatch_runtime_not_aligned" in warning_keys
    assert "maps_supervised_required" in warning_keys
    assert "scoped worker" in payload["production_readiness"]["summary_en"]
    payload_json = json.dumps(payload, ensure_ascii=False)
    assert "controlled/manual" not in payload_json
    assert "controlled task" not in payload_json
    assert "supervised/manual" in payload_json


def test_social_goal_progress_maps_owner_loop_from_plan_to_learning():
    progress = _social_goal_progress(
        [
            {
                "id": "post-review",
                "platform": "telegram",
                "status": "needs_review",
            },
            {
                "id": "post-approved",
                "platform": "vk",
                "status": "approved",
            },
            {
                "id": "post-queued",
                "platform": "google_business",
                "status": "queued",
            },
            {
                "id": "post-map",
                "platform": "yandex_maps",
                "status": "needs_supervised_publish",
            },
            {
                "id": "post-result",
                "platform": "telegram",
                "status": "published",
                "leads": 1,
                "inquiries": 2,
            },
        ],
        plan_item_count=3,
    )

    assert progress["schema"] == "localos_social_goal_progress_v1"
    assert progress["approval_required"] is True
    assert progress["maps_are_supervised_or_manual"] is True
    assert progress["summary"]["total"] == 6
    assert progress["summary"]["current_key"] == "review_approval"
    stages = {stage["key"]: stage for stage in progress["stages"]}
    assert stages["content_plan"]["status"] == "done"
    assert stages["channel_posts"]["count"] == 5
    assert stages["review_approval"]["status"] == "current"
    assert stages["schedule"]["status"] == "current"
    assert stages["execution"]["status"] == "current"
    assert stages["learning"]["status"] == "done"
    assert "Заявки и обращения" in progress["primary_metric_ru"]


def test_social_first_api_proof_dossier_guides_owner_from_setup_to_proof():
    no_channel = _social_first_api_proof_dossier(
        [],
        [_channel_readiness("telegram", "api", False, "missing_keys")],
        plan_item_count=2,
    )
    review = _social_first_api_proof_dossier(
        [{"id": "post-review", "platform": "telegram", "status": "needs_review"}],
        [_channel_readiness("telegram", "api", True, "ready")],
        plan_item_count=2,
    )
    queued = _social_first_api_proof_dossier(
        [{"id": "post-queued", "platform": "vk", "status": "queued"}],
        [_channel_readiness("vk", "api", True, "ready")],
        plan_item_count=2,
    )
    proven = _social_first_api_proof_dossier(
        [
            {
                "id": "post-proven",
                "platform": "telegram",
                "status": "published",
                "provider_post_url": "https://t.me/channel/10",
            }
        ],
        [_channel_readiness("telegram", "api", True, "ready")],
        plan_item_count=2,
    )

    assert no_channel["schema"] == "localos_social_first_api_proof_dossier_v1"
    assert no_channel["status"] == "connect_first_api_channel"
    assert no_channel["external_publish_requires_approval"] is True
    assert no_channel["browser_final_click_allowed"] is False
    assert "Telegram" in no_channel["summary_ru"]
    assert review["status"] == "review_and_approve"
    assert review["candidate_post_id"] == "post-review"
    assert "Подтвердите" in review["steps_ru"][2]
    assert queued["status"] == "wait_for_worker_or_run_once"
    assert queued["candidate_post_id"] == "post-queued"
    assert "provider_post_id/provider_post_url" in queued["steps_ru"][2]
    assert proven["status"] == "proof_complete"
    assert proven["ready"] is True
    assert proven["provider_post_url"] == "https://t.me/channel/10"
    assert "реакции/заявки" in proven["next_action_ru"]
    assert proven["primary_metric_ru"] == "Заявки и обращения"


def test_social_first_api_proof_dossier_does_not_pick_blocked_meta_draft():
    dossier = _social_first_api_proof_dossier(
        [
            {
                "id": "post-facebook",
                "platform": "facebook",
                "status": "needs_review",
            }
        ],
        [
            _channel_readiness("facebook", "api", False, "adapter_pending"),
            _channel_readiness("telegram", "api", False, "missing_keys"),
            _channel_readiness("vk", "api", False, "missing_permissions"),
        ],
        plan_item_count=2,
    )

    assert dossier["status"] == "connect_first_api_channel"
    assert dossier["candidate_post_id"] == ""
    assert dossier["recommended_platform"] == "telegram"
    assert dossier["blocked_api_channels"][0]["platform"] == "telegram"
    assert "Telegram или VK" in dossier["summary_ru"]
    assert "Подключите Telegram или VK" in dossier["steps_ru"][0]


def test_social_first_api_proof_dossier_prefers_telegram_ready_post_over_meta():
    dossier = _social_first_api_proof_dossier(
        [
            {
                "id": "post-facebook",
                "platform": "facebook",
                "status": "needs_review",
            },
            {
                "id": "post-telegram",
                "platform": "telegram",
                "status": "needs_review",
            },
        ],
        [
            _channel_readiness("facebook", "api", True, "ready"),
            _channel_readiness("telegram", "api", True, "ready"),
        ],
        plan_item_count=2,
    )

    assert dossier["status"] == "review_and_approve"
    assert dossier["candidate_post_id"] == "post-telegram"
    assert dossier["recommended_platform"] == "telegram"
    assert dossier["ready_api_channels"][0]["platform"] == "telegram"


def test_social_first_api_publish_readiness_exposes_fast_start_and_safe_path():
    readiness = _social_first_api_publish_readiness(
        [
            _channel_readiness("facebook", "api", True, "ready"),
            _channel_readiness("telegram", "api", True, "ready"),
            _channel_readiness("vk", "api", False, "missing_permissions"),
        ]
    )

    assert readiness["schema"] == "localos_social_first_api_publish_readiness_v1"
    assert readiness["recommended_start_platform"]["platform"] == "telegram"
    assert readiness["fast_start_platforms"] == ["telegram", "vk"]
    assert readiness["fast_start_ready_platforms"][0]["platform"] == "telegram"
    assert readiness["fast_start_blocked_platforms"][0]["platform"] == "vk"
    assert "Telegram" in readiness["fast_start_message_ru"]
    assert "VK" in readiness["fast_start_message_ru"]
    assert readiness["safe_path_ru"][0] == "Проверить API-каналы без публикации."
    assert "provider_post_id/provider_post_url" in readiness["safe_path_ru"][-1]
    assert readiness["external_publish_requires_approval"] is True


def test_social_first_api_publish_readiness_keeps_non_fast_channel_when_it_is_the_only_live_candidate():
    readiness = _social_first_api_publish_readiness(
        [],
        [
            {
                "platform": "google_business",
                "platform_label": "Google Business",
                "ready": False,
                "status": "missing_binding",
                "next_action_ru": "Выберите location.",
                "next_action_en": "Select location.",
            }
        ],
    )

    assert readiness["source"] == "live_api_preflight"
    assert readiness["recommended_start_platform"]["platform"] == "google_business"
    assert readiness["fast_start_ready_platforms"] == []
    assert readiness["fast_start_blocked_platforms"] == []
    assert "Telegram/VK" in readiness["fast_start_message_ru"]
    assert "provider_post_id/provider_post_url" in readiness["safe_path_en"][-1]


def test_social_launch_preflight_blocks_due_api_posts_when_live_preflight_fails(monkeypatch):
    monkeypatch.delenv("SOCIAL_POST_DISPATCH_ENABLED", raising=False)
    payload = _build_social_launch_preflight_payload(
        "biz-1",
        [_channel_readiness("google_business", "api", True, "ready")],
        {"api_ready": 1, "api_needs_attention": 0},
        {
            "dry_run": True,
            "picked": 1,
            "skipped_no_access": 0,
            "readiness": {
                "status": "external_publish_ready",
                "due_count": 1,
                "external_publish_count": 1,
                "controlled_count": 0,
                "manual_count": 0,
                "skipped_no_access": 0,
            },
            "items": [
                {
                    "id": "post-google",
                    "platform": "google_business",
                    "platform_label": "Google Business",
                    "dispatch_action": "publish_api",
                }
            ],
        },
        [
            {
                "platform": "google_business",
                "platform_label": "Google Business",
                "ready": False,
                "status": "missing_binding",
                "message_ru": "Google Business Profile подключен, но location для публикации не выбран.",
                "message_en": "Google Business Profile is connected, but publishing location is missing.",
            }
        ],
        {"checked": 1, "ready": 0, "needs_attention": 1},
    )

    assert payload["status"] == "api_preflight_blocked"
    assert payload["safe_to_enable_scoped_dispatch"] is False
    assert payload["summary"]["api_preflight_blocked_due_posts"] == 1
    assert payload["summary"]["api_ready_channels"] == 0
    assert payload["summary"]["api_blocked_channels"] == 1
    assert payload["first_api_publish_readiness"]["status"] == "no_api_ready"
    assert payload["first_api_publish_readiness"]["ready"] is False
    assert payload["first_api_publish_readiness"]["recommended_start_platform"]["platform"] == "google_business"
    assert payload["first_api_publish_readiness"]["blocked_platforms"][0]["platform"] == "google_business"
    assert "live API-проверку" in payload["first_api_publish_readiness"]["first_post_checklist_ru"][1]
    assert "Повторите live API-проверку" in payload["first_api_publish_readiness"]["first_api_launch_plan_ru"][1]
    assert "provider_post_id/provider_post_url" in payload["first_api_publish_readiness"]["proof_check_ru"]
    assert "не имитировать success" in payload["first_api_publish_readiness"]["metrics_followup_ru"]
    assert payload["production_readiness"]["status"] == "blocked"
    assert payload["production_readiness"]["ready_for_first_scoped_cycle"] is False
    assert payload["production_readiness"]["blockers"][0]["key"] == "api_preflight_blocked"
    assert "ключи" in payload["production_readiness"]["next_action_ru"]
    assert payload["api_preflight_blocked_due_posts"][0]["id"] == "post-google"
    assert payload["api_preflight_blocked_due_posts"][0]["status"] == "missing_binding"
    assert payload["launch_runbook"]["ready"] is False
    assert "Live API-preflight" in payload["launch_runbook"]["blocked_reason_ru"]
    assert "повторите проверку" in payload["launch_runbook"]["steps_ru"][1]
    assert "исправьте" in payload["next_action_ru"].lower()


def test_social_launch_preflight_payload_handles_no_due_posts_as_next_ui_work():
    payload = _build_social_launch_preflight_payload(
        "biz-1",
        [_channel_readiness("telegram", "api", True, "ready")],
        {"api_ready": 1},
        {
            "dry_run": True,
            "picked": 0,
            "skipped_no_access": 0,
            "readiness": {
                "status": "no_due_posts",
                "due_count": 0,
                "external_publish_count": 0,
                "controlled_count": 0,
                "manual_count": 0,
                "skipped_no_access": 0,
            },
        },
    )

    assert payload["status"] == "no_due_posts"
    assert payload["safe_to_enable_scoped_dispatch"] is False
    assert payload["summary"]["due_posts"] == 0
    assert payload["launch_rehearsal"]["schema"] == "localos_social_publish_rehearsal_bulk_v1"
    assert payload["launch_rehearsal"]["summary"]["status"] == "empty"
    assert payload["launch_rehearsal"]["provider_write_performed"] is False
    assert "подготовьте" in payload["message_ru"]
    assert payload["launch_runbook"]["ready"] is False
    assert "Нет due-постов" in payload["launch_runbook"]["blocked_reason_ru"]
    assert "Подготовьте" in payload["launch_runbook"]["steps_ru"][0]


def test_social_launch_preflight_explains_worker_idle_on_review_posts():
    payload = _build_social_launch_preflight_payload(
        "biz-1",
        [_channel_readiness("telegram", "api", False, "missing_keys")],
        {"api_ready": 0},
        {
            "dry_run": True,
            "picked": 0,
            "skipped_no_access": 0,
            "readiness": {
                "status": "no_due_posts",
                "due_count": 0,
                "external_publish_count": 0,
                "controlled_count": 0,
                "manual_count": 0,
                "skipped_no_access": 0,
            },
        },
        workflow_stage_counts={
            "schema": "localos_social_post_workflow_stage_counts_v1",
            "business_id": "biz-1",
            "total": 7,
            "draft": 0,
            "needs_review": 7,
            "approved_not_queued": 0,
            "queued_total": 0,
            "queued_due": 0,
            "queued_future": 0,
            "publishing": 0,
            "published": 0,
            "needs_supervised_publish": 0,
            "needs_manual_publish": 0,
            "failed": 0,
        },
    )

    assert payload["status"] == "no_due_posts"
    assert payload["summary"]["workflow_needs_review"] == 7
    assert payload["worker_idle_reason"]["status"] == "waiting_for_review"
    assert payload["worker_idle_reason"]["count"] == 7
    assert payload["production_readiness"]["blockers"][0]["key"] == "posts_need_review"
    assert payload["production_readiness"]["blockers"][0]["count"] == 7
    assert "предпросмотр" in payload["production_readiness"]["next_action_ru"]


def test_social_launch_runtime_alignment_explains_disabled_and_matching_scope(monkeypatch):
    monkeypatch.delenv("SOCIAL_POST_DISPATCH_ENABLED", raising=False)
    monkeypatch.delenv("SOCIAL_POST_DISPATCH_BUSINESS_ID", raising=False)
    monkeypatch.delenv("SOCIAL_POST_DISPATCH_ALLOW_UNSCOPED", raising=False)
    monkeypatch.setenv("SOCIAL_POST_METRICS_ENABLED", "true")
    monkeypatch.setenv("SOCIAL_POST_METRICS_BUSINESS_ID", "biz-1")

    disabled = social_post_service._social_launch_runtime_alignment("biz-1")

    assert disabled["dispatch"]["status"] == "dispatch_disabled"
    assert disabled["dispatch"]["can_process_this_business"] is False
    assert disabled["metrics"]["status"] == "ready"
    assert "SOCIAL_POST_DISPATCH_ENABLED=true" in disabled["next_action_ru"]

    monkeypatch.setenv("SOCIAL_POST_DISPATCH_ENABLED", "true")
    monkeypatch.setenv("SOCIAL_POST_DISPATCH_BUSINESS_ID", "biz-1")

    ready = social_post_service._social_launch_runtime_alignment("biz-1")

    assert ready["dispatch"]["status"] == "ready"
    assert ready["dispatch"]["can_process_this_business"] is True
    assert ready["metrics"]["can_collect_this_business"] is True
    assert "первый цикл" in ready["next_action_ru"]


def test_social_launch_runtime_alignment_explains_scope_mismatch_and_guard(monkeypatch):
    monkeypatch.setenv("SOCIAL_POST_DISPATCH_ENABLED", "true")
    monkeypatch.setenv("SOCIAL_POST_DISPATCH_BUSINESS_ID", "biz-other")
    monkeypatch.delenv("SOCIAL_POST_DISPATCH_ALLOW_UNSCOPED", raising=False)
    monkeypatch.setenv("SOCIAL_POST_METRICS_ENABLED", "true")
    monkeypatch.delenv("SOCIAL_POST_METRICS_BUSINESS_ID", raising=False)
    monkeypatch.delenv("SOCIAL_POST_METRICS_ALLOW_UNSCOPED", raising=False)

    mismatch = social_post_service._social_launch_runtime_alignment("biz-1")

    assert mismatch["dispatch"]["status"] == "scope_mismatch"
    assert mismatch["dispatch"]["can_process_this_business"] is False
    assert mismatch["metrics"]["status"] == "blocked_without_scope"
    assert "biz-1" in mismatch["next_action_ru"]

    monkeypatch.delenv("SOCIAL_POST_DISPATCH_BUSINESS_ID", raising=False)

    guarded = social_post_service._social_launch_runtime_alignment("biz-1")

    assert guarded["dispatch"]["status"] == "blocked_without_scope"
    assert guarded["dispatch"]["can_process_this_business"] is False
    assert "business scope" in guarded["dispatch"]["message_en"]


def test_supervised_handoff_writes_agent_action_ledger_when_available():
    cursor = FakeSocialLedgerCursor(table_exists=True)
    original = {
        "id": "post-1",
        "business_id": "biz-1",
        "content_plan_id": "plan-1",
        "content_plan_item_id": "item-1",
        "platform": "yandex_maps",
        "publish_mode": "openclaw_browser",
        "approval_id": "approval-1",
    }
    updated = {
        **original,
        "status": "needs_supervised_publish",
        "metadata_json": {
            "openclaw_task": {"task_id": "task-1", "target": {"url": "https://yandex.ru/maps/org/1"}},
            "supervised_publish": {"target_url": "https://yandex.ru/maps/org/1", "stop_before_final_publish": True},
        },
    }

    ledger_id = _record_social_supervised_handoff_ledger(cursor, original, updated, "task-1")

    assert ledger_id
    assert len(cursor.inserted) == 1
    params = cursor.inserted[0]
    assert params[1] == "biz-1"
    assert params[2] == "social_post_supervised_handoff"
    assert params[3] == "social.post.publish_supervised_browser"
    assert params[5] == "high"
    assert params[8] == "approval-1"
    assert params[9] == "queued_for_supervised_handoff"
    metadata = json.loads(params[11])
    assert metadata["execution_contract"]["capability"] == "social.post.publish_supervised_browser"
    assert metadata["execution_contract"]["openclaw_action_ref"] == "openclaw.browser.supervised_publish"
    assert metadata["execution_contract"]["delivery_status"] == "pending_openclaw_supervised_task"
    assert metadata["execution_contract"]["side_effect_policy"] == "fill_preview_only"
    assert metadata["execution_contract"]["final_publish_policy"] == "human_final_click_required"
    assert "click_final_publish" in metadata["execution_contract"]["forbidden_actions"]
    assert "show_preview" in metadata["execution_contract"]["allowed_actions"]
    assert metadata["provider_write_performed"] is False
    assert metadata["human_final_approval_required"] is True
    assert metadata["browser_final_click_allowed"] is False


def test_supervised_handoff_ledger_is_optional_when_table_missing():
    cursor = FakeSocialLedgerCursor(table_exists=False)

    ledger_id = _record_social_supervised_handoff_ledger(
        cursor,
        {"id": "post-1", "business_id": "biz-1"},
        {"id": "post-1", "business_id": "biz-1", "status": "needs_manual_publish"},
        "task-1",
    )

    assert ledger_id == ""
    assert cursor.inserted == []


def test_supervised_openclaw_outbox_enqueues_when_callback_is_configured(monkeypatch):
    monkeypatch.setenv("OPENCLAW_SOCIAL_SUPERVISED_CALLBACK_URL", "https://openclaw.example/localos/social")
    cursor = FakeSocialOutboxCursor(table_exists=True)
    updated = {
        "id": "post-1",
        "business_id": "biz-1",
        "content_plan_id": "plan-1",
        "content_plan_item_id": "item-1",
        "platform": "yandex_maps",
        "status": "needs_supervised_publish",
        "metadata_json": {
            "openclaw_task": {
                "task_id": "task-1",
                "capability": "social.post.publish_supervised_browser",
                "target": {"url": "https://yandex.ru/maps/org/1"},
            },
            "supervised_publish": {
                "target_url": "https://yandex.ru/maps/org/1",
                "handoff_state": {"state": "ready_for_openclaw_handoff"},
                "handoff_checklist_ru": ["Открыть профиль", "Остановиться перед финальной кнопкой публикации"],
                "handoff_checklist_en": ["Open profile", "Stop before the final publish button"],
                "safety_contract": {
                    "side_effect_policy": "fill_preview_only",
                    "final_publish_policy": "human_final_click_required",
                },
            },
        },
    }

    outbox_id = social_post_service._enqueue_social_supervised_openclaw_outbox(
        cursor,
        updated,
        "task-1",
        "ledger-1",
    )

    assert outbox_id == "outbox-1"
    assert len(cursor.inserted) == 1
    params = cursor.inserted[0]
    assert params[1] == "task-1"
    assert params[2] == "biz-1"
    assert params[3] == "https://openclaw.example/localos/social"
    assert params[4] == "social.post.publish_supervised_browser.requested"
    payload = json.loads(params[5])
    assert payload["schema"] == "localos_social_supervised_openclaw_request_v1"
    assert payload["social_post_id"] == "post-1"
    assert payload["agent_action_ledger_id"] == "ledger-1"
    assert payload["openclaw_task"]["capability"] == "social.post.publish_supervised_browser"
    assert payload["external_publish_performed"] is False
    assert payload["provider_write_performed"] is False
    assert payload["browser_final_click_allowed"] is False
    assert payload["final_publish_policy"] == "human_final_click_required"
    assert payload["completion_contract"]["success_state"] == "preview_ready"
    assert payload["completion_contract"]["browser_final_click_allowed"] is False
    assert "status" in payload["completion_contract"]["required_result_fields"]
    assert "post is marked as published" in payload["completion_contract"]["done_criteria_en"][-1]
    assert payload["handoff_checklist_ru"][-1] == "Остановиться перед финальной кнопкой публикации"
    assert payload["handoff_checklist_en"][-1] == "Stop before the final publish button"
    assert "preview" in payload["operator_next_action_en"]
    assert params[7] == "social-supervised:post-1:task-1"


def test_supervised_openclaw_outbox_is_optional_without_callback(monkeypatch):
    monkeypatch.delenv("OPENCLAW_SOCIAL_SUPERVISED_CALLBACK_URL", raising=False)
    monkeypatch.delenv("OPENCLAW_SUPERVISED_CALLBACK_URL", raising=False)
    cursor = FakeSocialOutboxCursor(table_exists=True)

    outbox_id = social_post_service._enqueue_social_supervised_openclaw_outbox(
        cursor,
        {"id": "post-1", "business_id": "biz-1", "metadata_json": {}},
        "task-1",
        "",
    )

    assert outbox_id == ""
    assert cursor.inserted == []


def test_social_publish_evidence_explains_published_api_result():
    evidence = _social_publish_evidence(
        {
            "platform": "vk",
            "status": "published",
            "provider_post_id": "678",
            "provider_post_url": "https://vk.com/wall-12345_678",
            "leads": 1,
            "inquiries": 2,
            "likes": 9,
            "views": 120,
            "metadata_json": {"provider_status": "vk_published"},
        }
    )

    assert evidence["schema"] == "localos_social_publish_evidence_v1"
    assert evidence["tone"] == "success"
    assert evidence["proof_url"] == "https://vk.com/wall-12345_678"
    assert evidence["proof_id"] == "678"
    assert evidence["provider_status"] == "vk_published"
    assert evidence["proof_source"] == "vk_api"
    assert evidence["proof_quality"] == "url"
    assert evidence["external_publish_proven"] is True
    assert evidence["ready_for_metrics"] is True
    assert evidence["ready_for_attribution"] is True
    assert "заявки" in evidence["next_action_ru"]
    packet = evidence["result_packet"]
    assert packet["schema"] == "localos_social_result_collection_packet_v1"
    assert packet["status"] == "primary_result_recorded"
    assert packet["primary_result_total"] == 3
    assert packet["early_signal_total"] == 129
    assert packet["ready_for_recommendation"] is True
    assert packet["recommendation_priority"][:2] == ["leads", "inquiries"]


def test_social_publish_evidence_explains_recoverable_failure():
    evidence = _social_publish_evidence(
        {
            "platform": "telegram",
            "status": "needs_manual_publish",
            "last_error": "Для Telegram нужны telegram_bot_token и telegram_chat_id бизнеса.",
            "metadata_json": {"queue_preflight_status": "missing_keys"},
        }
    )

    assert evidence["tone"] == "warning"
    assert evidence["recoverable"] is True
    assert evidence["provider_status"] == "missing_keys"
    assert evidence["proof_quality"] == "error"
    assert evidence["ready_for_metrics"] is False
    assert evidence["external_publish_proven"] is False
    assert "telegram_bot_token" in evidence["summary_ru"]
    assert "ссылку/ID" in evidence["next_action_ru"]


def test_social_publish_evidence_keeps_supervised_maps_human_controlled():
    evidence = _social_publish_evidence(
        {
            "platform": "yandex_maps",
            "status": "needs_supervised_publish",
            "automation_task_id": "task-1",
            "metadata_json": {
                "supervised_publish": {
                    "target_url": "https://yandex.ru/maps/org/1",
                    "profile_hint": "Riderra Tallinn",
                    "copy_ready_text": "Текст для карты",
                    "manual_checklist_ru": ["Скопируйте текст", "Отметьте размещённым"],
                    "manual_checklist_en": ["Copy the text", "Mark as published"],
                    "handoff_checklist_ru": ["Открыть профиль", "Остановиться перед финальной кнопкой публикации"],
                    "handoff_checklist_en": ["Open profile", "Stop before the final publish button"],
                    "stop_before_final_publish": True,
                    "manual_handoff": {
                        "target_url": "https://yandex.ru/maps/org/1",
                        "copy_ready_text": "fallback text",
                    },
                }
            },
        }
    )

    assert evidence["tone"] == "warning"
    assert evidence["automation_task_id"] == "task-1"
    assert evidence["proof_quality"] == "supervised_task"
    assert evidence["external_publish_proven"] is False
    assert "финальный клик" in evidence["summary_ru"]
    assert "контролируемое или ручное размещение" in evidence["summary_ru"]
    assert evidence["target_url"] == "https://yandex.ru/maps/org/1"
    assert evidence["profile_hint"] == "Riderra Tallinn"
    assert evidence["copy_ready_text"] == "Текст для карты"
    assert evidence["manual_checklist_ru"] == ["Скопируйте текст", "Отметьте размещённым"]
    assert evidence["browser_final_click_allowed"] is False
    assert evidence["stop_before_final_publish"] is True
    packet = evidence["placement_packet"]
    assert packet["schema"] == "localos_social_supervised_placement_packet_v1"
    assert packet["target_url"] == "https://yandex.ru/maps/org/1"
    assert packet["target_ready"] is True
    assert packet["copy_ready"] is True
    assert packet["checklist_count"] == 2
    assert packet["handoff_checklist_ru"][-1] == "Остановиться перед финальной кнопкой публикации"
    assert packet["handoff_checklist_en"][-1] == "Stop before the final publish button"
    assert packet["automation_task_id"] == "task-1"
    assert packet["final_publish_policy"] == "human_final_click_required"
    assert packet["browser_final_click_allowed"] is False
    assert "Финальную публикацию нажал человек" in packet["done_criteria_ru"][1]
    assert "post is marked as published" in packet["done_criteria_en"][-1]


def test_social_publish_evidence_explains_queued_waiting_state():
    evidence = _social_publish_evidence(
        {
            "platform": "telegram",
            "status": "queued",
            "metadata_json": {},
        }
    )

    assert evidence["tone"] == "info"
    assert evidence["title_ru"] == "Telegram: в расписании"
    assert "ждёт даты публикации" in evidence["summary_ru"]
    assert "scoped dispatch" in evidence["next_action_ru"]


def test_social_supervised_blocked_metadata_preserves_manual_fallback_contract():
    metadata = _social_supervised_blocked_metadata(
        {
            "supervised_publish": {
                "task_status": "ready_for_supervised_or_manual_handoff",
                "target_url": "https://2gis.ru/firm/1",
            },
            "openclaw_task": {"task_id": "task-1"},
        },
        "captcha",
        "openclaw",
    )

    supervised = metadata["supervised_publish"]
    assert supervised["task_status"] == "blocked_needs_manual_publish"
    assert supervised["target_url"] == "https://2gis.ru/firm/1"
    assert supervised["blocked_reason"] == "captcha"
    assert supervised["blocked_source"] == "openclaw"
    assert supervised["manual_fallback_required"] is True
    assert supervised["stop_before_final_publish"] is True
    assert supervised["manual_handoff"]["schema"] == "localos_social_manual_publish_handoff_v1"
    assert supervised["manual_handoff"]["target_url"] == "https://2gis.ru/firm/1"
    assert supervised["manual_handoff"]["reason"] == "captcha"
    assert supervised["manual_handoff"]["browser_final_click_allowed"] is False
    assert "Отметить размещённым" in supervised["manual_checklist_ru"][-1]
    assert metadata["manual_fallback"]["required"] is True
    assert metadata["manual_fallback"]["reason"] == "captcha"
    assert metadata["manual_fallback"]["handoff"]["target_url"] == "https://2gis.ru/firm/1"
    assert metadata["browser_final_click_allowed"] is False
    assert metadata["human_final_approval_required"] is True


def test_apply_social_post_recommendation_requires_explicit_approval(monkeypatch):
    def fail_if_db_opens():
        raise AssertionError("database must not open before approval")

    monkeypatch.setattr(social_post_service, "DatabaseManager", fail_if_db_opens)

    error = None
    try:
        apply_social_post_recommendation("user-1", "plan-1", approved=False)
    except PermissionError:
        error = sys.exc_info()[1]

    assert error is not None
    assert "явное подтверждение" in str(error)


def test_social_recommendation_application_preview_explains_future_only_scope():
    conn = FakeRecommendationConn()
    cursor = conn.cursor()

    preview = _social_recommendation_application_preview(
        cursor,
        "plan-1",
        [
            {"item_id": "future-draft", "theme": "Будущая тема", "proposed_goal": "Новый goal"},
            {"item_id": "past-draft", "theme": "Прошлая тема", "proposed_goal": "Нельзя"},
            {"item_id": "future-published", "theme": "Опубликованная тема", "proposed_goal": "Нельзя"},
            {"item_id": "future-news", "theme": "Тема с новостью", "proposed_goal": "Нельзя"},
        ],
    )

    by_id = {item["item_id"]: item for item in preview["items"]}
    assert preview["schema"] == "localos_social_recommendation_application_preview_v1"
    assert preview["scope"] == "future_unpublished_content_plan_items"
    assert preview["applicable_count"] == 1
    assert preview["skipped_count"] == 3
    assert by_id["future-draft"]["applicable"] is True
    assert by_id["past-draft"]["skip_reason"] == "past_item"
    assert by_id["future-published"]["skip_reason"] == "status_published"
    assert by_id["future-news"]["skip_reason"] == "already_has_news"
    assert "будущие неопубликованные" in preview["summary_ru"]


def test_apply_social_post_recommendation_changes_only_future_unpublished_items(monkeypatch):
    monkeypatch.setattr(social_post_service, "DatabaseManager", FakeRecommendationDB)
    monkeypatch.setattr(social_post_service, "ensure_social_post_tables", lambda cursor: None)
    monkeypatch.setattr(
        social_post_service,
        "recommend_next_plan_from_social_posts",
        lambda user_id, plan_id: {
            "recommendation": {"primary_metric": "leads"},
            "proposed_changes": [
                {"item_id": "future-draft", "proposed_goal": "Новый goal для будущего"},
                {"item_id": "past-draft", "proposed_goal": "Нельзя менять прошлое"},
                {"item_id": "future-published", "proposed_goal": "Нельзя менять опубликованное"},
                {"item_id": "future-news", "proposed_goal": "Нельзя менять созданную новость"},
            ],
        },
    )
    monkeypatch.setattr(
        social_post_service,
        "_load_plan_for_user",
        lambda cursor, user_id, plan_id: {
            "id": plan_id,
            "edited_plan_json": {"existing_note": "keep me", "social_recommendation_history": [{"applied_count": 0}]},
        },
    )

    result = apply_social_post_recommendation("user-1", "plan-1", approved=True)
    conn = FakeRecommendationDB.last_conn
    edited_plan = json.loads(conn.edited_plan_json)

    assert result["applied_count"] == 1
    assert result["applied_items"][0]["id"] == "future-draft"
    assert conn.items["future-draft"]["goal"] == "Новый goal для будущего"
    assert conn.items["past-draft"]["goal"] == "Старый goal"
    assert conn.items["future-published"]["goal"] == "Старый goal"
    assert conn.items["future-news"]["goal"] == "Старый goal"
    assert conn.committed is True
    assert edited_plan["existing_note"] == "keep me"
    assert edited_plan["last_social_recommendation_apply"]["approved_by"] == "user-1"
    assert edited_plan["last_social_recommendation_apply"]["human_approved"] is True
    assert edited_plan["last_social_recommendation_apply"]["scope"] == "future_unpublished_content_plan_items"
    assert edited_plan["last_social_recommendation_apply"]["proposed_count"] == 4
    assert edited_plan["last_social_recommendation_apply"]["applied_count"] == 1
    assert len(edited_plan["social_recommendation_history"]) == 2
    assert result["approval_record"]["approved_by"] == "user-1"
    assert result["approval_record"]["human_approved"] is True
    assert result["approval_record"]["scope"] == "future_unpublished_content_plan_items"
    assert result["applies_automatically"] is False
