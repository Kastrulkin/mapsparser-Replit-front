import sys

from services.social_post_service import (
    build_social_queue_groups,
    default_publish_mode,
    ensure_social_post_tables,
    next_action_for_social_post,
    openclaw_browser_available,
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
        ]
    )
    by_key = {group["key"]: group for group in groups}

    assert by_key["needs_review"]["count"] == 1
    assert by_key["api_ready"]["post_ids"] == ["p2"]
    assert by_key["needs_supervised_publish"]["post_ids"] == ["p3"]
    assert by_key["published"]["count"] == 1
    assert by_key["failed"]["count"] == 1
