import sys

from services.social_post_service import (
    _build_openclaw_supervised_task_payload,
    _meta_publish_status,
    _vk_publish_binding,
    _build_next_plan_changes,
    build_social_queue_groups,
    default_publish_mode,
    ensure_social_post_tables,
    next_action_for_social_post,
    openclaw_browser_available,
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


def test_next_action_separates_review_api_and_supervised_states():
    assert next_action_for_social_post({"status": "needs_review", "platform": "telegram"}) == "review_required"
    assert next_action_for_social_post({"status": "approved", "platform": "telegram"}) == "wait_for_api_publish"
    assert next_action_for_social_post({"status": "approved", "platform": "yandex_maps"}) == "start_supervised_publish"
    assert next_action_for_social_post({"status": "queued", "platform": "telegram"}) == "wait_for_scheduled_publish"
    assert next_action_for_social_post({"status": "queued", "platform": "two_gis"}) == "wait_for_scheduled_supervised_publish"
    assert next_action_for_social_post({"status": "needs_supervised_publish", "platform": "two_gis"}) == "open_supervised_publish"


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
        ]
    )
    by_key = {group["key"]: group for group in groups}

    assert by_key["needs_review"]["count"] == 1
    assert by_key["api_ready"]["post_ids"] == ["p2"]
    assert by_key["scheduled"]["post_ids"] == ["p6"]
    assert by_key["needs_supervised_publish"]["post_ids"] == ["p3"]
    assert by_key["published"]["count"] == 1
    assert by_key["failed"]["count"] == 1


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
