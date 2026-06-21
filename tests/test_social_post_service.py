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
    _dispatch_preview_readiness,
    _merge_metric_totals_into_posts,
    _meta_channel_readiness,
    _meta_publish_status,
    openclaw_browser_capability_status,
    _publish_external_account_post,
    _build_social_learning_insights,
    _collect_vk_post_metrics,
    _preview_dispatch_decision,
    _dispatch_preview_first_cycle_steps,
    _telegram_publish_error_state,
    _queue_preflight_block,
    _record_social_supervised_handoff_ledger,
    _social_supervised_blocked_metadata,
    _social_publish_evidence,
    _social_learning_readiness,
    _social_openclaw_browser_readiness,
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
    publish_social_post,
    queue_social_post,
    record_social_post_attribution_event,
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
        self.description = []

    def execute(self, query, params=None):
        normalized = " ".join(str(query).split()).lower()
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

    status = openclaw_browser_capability_status()

    assert status["ready"] is False
    assert status["source"] == "not_configured"
    assert status["reason"] == "openclaw_catalog_not_configured"


def test_social_openclaw_browser_readiness_explains_ready_and_manual_fallback():
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
    assert ready["status"] == "ready"
    assert ready["action_ref"] == "openclaw.browser.fill_form"
    assert ready["browser_final_click_allowed"] is False
    assert "controlled-задачи" in ready["message_ru"]
    assert fallback["ready"] is False
    assert fallback["status"] == "manual_fallback"
    assert "ручном fallback" in fallback["message_ru"]
    assert "capability catalog" in fallback["next_action_ru"]


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
        lambda: {
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
    assert readiness["safe_to_apply_recommendation"] is True
    assert "Заявки" in readiness["primary_metric_ru"]


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


def test_dispatch_action_for_status_matches_worker_log_buckets():
    assert _dispatch_action_for_status("published") == "published"
    assert _dispatch_action_for_status("needs_supervised_publish") == "supervised"
    assert _dispatch_action_for_status("needs_manual_publish") == "manual"
    assert _dispatch_action_for_status("failed") == "failed"
    assert _dispatch_action_for_status("queued") == "other"


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
    assert result["browser_final_click_allowed"] is False
    assert result["external_publish_only_after_approval"] is True
    assert captured["preflight"] == {"user_id": "user-1", "business_id": "biz-1", "batch_size": 50}
    assert captured["dispatch"] == {"business_id": "biz-1", "batch_size": 50}


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
        }

    monkeypatch.setattr(social_post_service, "collect_due_social_post_metrics", fake_collect_due)

    result = run_scoped_social_metrics_once("user-1", "biz-1", batch_size=500, approved=True)

    assert result["business_id"] == "biz-1"
    assert result["batch_size"] == 100
    assert result["external_publish_performed"] is False
    assert result["metrics_result"]["collected"] == 2
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

        def read(self):
            return json.dumps({"ok": True, "result": {"id": 100}}).encode("utf-8")

        def close(self):
            pass

    requested_urls = []
    monkeypatch.setattr(
        social_post_service,
        "_load_business_publish_context",
        lambda cursor, business_id: {"telegram_bot_token": "encrypted", "telegram_chat_id": "@localos_test"},
    )
    monkeypatch.setattr(social_post_service, "decode_telegram_bot_token", lambda value: "telegram-token")
    monkeypatch.setattr(
        social_post_service,
        "telegram_urlopen",
        lambda req, timeout=10: (requested_urls.append(req.full_url) or FakeResponse()),
    )

    result = social_post_service._telegram_api_channel_preflight(object(), "biz-1")

    assert result["ready"] is True
    assert result["read_only"] is True
    assert result["external_publish_performed"] is False
    assert any("getMe" in url for url in requested_urls)
    assert any("getChat" in url for url in requested_urls)
    assert all("sendMessage" not in url for url in requested_urls)
    assert [item["key"] for item in result["connection_checks"]][-2:] == ["telegram_get_me", "telegram_get_chat"]


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
    assert preview["action_label_ru"] == "Controlled task"
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

    state = _supervised_publish_state({"publish_mode": "openclaw_browser"})

    assert state["status"] == "needs_supervised_publish"
    assert state["last_error"] is None


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
    meta = _channel_readiness("instagram", "api", False, "missing_binding")
    maps = _channel_readiness("yandex_maps", "manual", False, "manual_fallback")

    assert "telegram_bot_token" in telegram["next_action_en"]
    assert "wall.post" in vk["next_action_en"]
    assert "Instagram business account" in meta["next_action_en"]
    assert "ручного действия" in maps["next_action_ru"]
    assert telegram["missing_fields"] == ["telegram_bot_token", "telegram_chat_id"]
    assert "Telegram-бота" in telegram["setup_steps_ru"][0]
    assert vk["missing_fields"] == ["vk_access_token.wall_post_scope"]
    assert "wall.post" in vk["setup_steps_en"][1]
    assert maps["missing_fields"] == []
    assert "Скопируйте" in maps["setup_steps_ru"][0]
    assert telegram["settings_path"] == "/dashboard/settings?focus=channels"


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

    assert "controlled" in supervised_next
    assert "финальная кнопка" in supervised_next


def test_channel_readiness_setup_steps_are_actionable_for_ready_and_meta():
    ready_steps = _channel_readiness_setup_steps("telegram", "ready", True)
    meta_steps = _channel_readiness("facebook", "api", False, "missing_permissions")

    assert ready_steps == ["Проверьте preview поста.", "Утвердите текст.", "Поставьте в расписание."]
    assert meta_steps["missing_fields"] == ["meta_permissions.pages_manage_posts"]
    assert "permissions" in meta_steps["setup_steps_en"][2]


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
    assert "click_final_publish" in payload["safety_contract"]["forbidden_actions"]
    assert "show_preview" in payload["safety_contract"]["allowed_actions"]
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
    assert insights["cta_suggestions"][0]["ru"]
    assert insights["frequency_suggestions"][0]["ru"]


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
    assert readiness["first_cycle_steps"][1]["stop_before_final_publish"] is True
    assert readiness["first_cycle_steps"][2]["key"] == "manual_handoff_or_connection"
    assert readiness["first_cycle_steps"][3]["key"] == "skipped_no_access"
    verification = readiness["first_cycle_verification"]
    assert verification["log_filter"] == "[SOCIAL_POST_DISPATCH]"
    assert verification["business_scope"] == "biz-1"
    assert verification["expected_statuses"][0]["key"] == "api_channels"
    assert verification["expected_statuses"][1]["key"] == "maps_controlled"
    assert "picked/published" in verification["checks_en"][1]
    assert "Dry-run" in readiness["safety_notes_ru"][2]


def test_dispatch_preview_first_cycle_steps_keep_owner_safe_before_worker_launch():
    steps = _dispatch_preview_first_cycle_steps(2, 1, 3)

    assert steps[0]["label_ru"] == "API: публикация после approval"
    assert steps[0]["count"] == 2
    assert steps[0]["external_publish"] is True
    assert steps[0]["requires_approval"] is True
    assert steps[1]["label_ru"] == "Карты: controlled/manual без финального клика"
    assert steps[1]["external_publish"] is False
    assert steps[1]["stop_before_final_publish"] is True
    assert steps[2]["label_ru"] == "Ручной fallback или подключение канала"
    assert steps[2]["count"] == 3


def test_dispatch_preview_readiness_marks_no_due_posts_as_safe_noop():
    readiness = _dispatch_preview_readiness([], {}, skipped_no_access=0)

    assert readiness["status"] == "no_due_posts"
    assert readiness["due_count"] == 0
    assert readiness["external_publish_count"] == 0
    assert readiness["message_ru"]
    assert readiness["next_action_ru"]


def test_social_launch_preflight_payload_recommends_scoped_env_and_keeps_safety_invariants():
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
            },
        },
    )

    assert payload["status"] == "ready_for_api_dispatch"
    assert payload["safe_to_enable_scoped_dispatch"] is True
    assert payload["summary"]["api_due_posts"] == 1
    assert payload["summary"]["controlled_due_posts"] == 1
    assert payload["summary"]["blocked_api_channels"] == 1
    assert payload["blocked_api_channels"][0]["platform"] == "vk"
    assert payload["controlled_channels"][0]["platform"] == "yandex_maps"
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
    assert "подготовьте" in payload["message_ru"]
    assert payload["launch_runbook"]["ready"] is False
    assert "Нет due-постов" in payload["launch_runbook"]["blocked_reason_ru"]
    assert "Подготовьте" in payload["launch_runbook"]["steps_ru"][0]


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


def test_social_publish_evidence_explains_published_api_result():
    evidence = _social_publish_evidence(
        {
            "platform": "vk",
            "status": "published",
            "provider_post_id": "678",
            "provider_post_url": "https://vk.com/wall-12345_678",
            "metadata_json": {"provider_status": "vk_published"},
        }
    )

    assert evidence["schema"] == "localos_social_publish_evidence_v1"
    assert evidence["tone"] == "success"
    assert evidence["proof_url"] == "https://vk.com/wall-12345_678"
    assert evidence["proof_id"] == "678"
    assert evidence["provider_status"] == "vk_published"
    assert "заявки" in evidence["next_action_ru"]


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
    assert "telegram_bot_token" in evidence["summary_ru"]
    assert "ссылку/ID" in evidence["next_action_ru"]


def test_social_publish_evidence_keeps_supervised_maps_human_controlled():
    evidence = _social_publish_evidence(
        {
            "platform": "yandex_maps",
            "status": "needs_supervised_publish",
            "automation_task_id": "task-1",
        }
    )

    assert evidence["tone"] == "warning"
    assert evidence["automation_task_id"] == "task-1"
    assert "финальный клик" in evidence["summary_ru"]
    assert "controlled/manual" in evidence["summary_ru"]


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
    assert edited_plan["last_social_recommendation_apply"]["applied_count"] == 1
    assert len(edited_plan["social_recommendation_history"]) == 2
