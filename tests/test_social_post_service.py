import json
import sys
from datetime import date, timedelta

import services.social_post_service as social_post_service
from services.social_post_service import (
    _build_openclaw_supervised_task_payload,
    _channel_readiness_message,
    _dispatch_action_for_status,
    _dispatch_preview_readiness,
    _merge_metric_totals_into_posts,
    _meta_channel_readiness,
    _meta_publish_status,
    openclaw_browser_capability_status,
    _publish_external_account_post,
    _build_social_learning_insights,
    _preview_dispatch_decision,
    _queue_preflight_block,
    _record_social_supervised_handoff_ledger,
    _status_after_social_text_edit,
    _supervised_publish_state,
    _vk_publish_binding,
    apply_social_post_recommendation,
    _build_next_plan_changes,
    build_social_queue_groups,
    default_publish_mode,
    ensure_social_post_tables,
    next_action_for_social_post,
    openclaw_browser_available,
    queue_social_post,
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


def test_dispatch_action_for_status_matches_worker_log_buckets():
    assert _dispatch_action_for_status("published") == "published"
    assert _dispatch_action_for_status("needs_supervised_publish") == "supervised"
    assert _dispatch_action_for_status("needs_manual_publish") == "manual"
    assert _dispatch_action_for_status("failed") == "failed"
    assert _dispatch_action_for_status("queued") == "other"


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
        },
    )

    assert preview["dry_run"] is True
    assert preview["dispatch_action"] == "publish_api"
    assert preview["would_status"] == "published_or_failed"
    assert preview["external_publish"] is True
    assert preview["approval_required"] is True


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
        },
    )

    assert preview["dispatch_action"] == "manual_handoff"
    assert preview["would_status"] == "needs_manual_publish"
    assert preview["external_publish"] is False
    assert preview["metadata_json"]["queue_preflight_status"] == "missing_keys"


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
        },
    )

    assert preview["dispatch_action"] == "create_supervised_task"
    assert preview["would_status"] == "needs_supervised_publish"
    assert preview["external_publish"] is False
    assert preview["stop_before_final_publish"] is True


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
    assert payload["target"]["url"] == "https://yandex.ru/maps/org/123"
    assert payload["content"]["text"] == "Текст для карт"
    assert payload["approval_evidence"]["approval_id"] == "approval-1"
    assert "changed_ui" in payload["fallback"]["reasons"]


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


def test_dispatch_preview_readiness_marks_no_due_posts_as_safe_noop():
    readiness = _dispatch_preview_readiness([], {}, skipped_no_access=0)

    assert readiness["status"] == "no_due_posts"
    assert readiness["due_count"] == 0
    assert readiness["external_publish_count"] == 0
    assert readiness["message_ru"]


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
