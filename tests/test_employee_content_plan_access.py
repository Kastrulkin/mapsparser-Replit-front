import json

import pytest

from services import content_plan_service


class ContentPlanAccessCursor:
    def __init__(self):
        self.one = None
        self.many = []
        self.executed = []

    def execute(self, query, params=None):
        normalized = " ".join(str(query).split()).lower()
        self.executed.append((normalized, params))
        self.one = None
        self.many = []

        if "from contentplans" in normalized and "where id = %s" in normalized and "join" not in normalized:
            self.one = {
                "id": "plan-1",
                "business_id": "network-1",
                "network_id": "network-1",
                "scope_type": "network_parent",
                "scope_target_id": "network-1",
                "title": "Общий план сети",
                "period_days": 30,
                "period_start": "2026-08-07",
                "period_end": "2026-09-05",
                "plan_status": "generated",
                "generation_mode": "manual",
                "input_snapshot_json": {},
                "generated_plan_json": {},
                "edited_plan_json": {},
                "published_plan_json": {},
                "created_by": "owner-1",
                "created_at": "2026-08-07T08:59:46",
                "updated_at": "2026-08-07T08:59:46",
            }
        elif "from contentplanitems i" in normalized and "join contentplans p" in normalized:
            self.one = {
                "id": "item-1",
                "plan_id": "plan-1",
                "business_id": "location-1",
                "status": "edited",
                "source_kind": "industry_template",
                "content_type": "news",
                "theme": "Первая стрижка без слёз",
                "draft_text": "Исходный текст",
                "metadata_json": {},
                "location_scope": "location-1",
                "root_business_id": "network-1",
            }
        elif "from contentplanitems" in normalized and "where plan_id = %s" in normalized:
            self.many = [
                {
                    "id": "item-1",
                    "business_id": "location-1",
                    "scheduled_for": "2026-08-07",
                    "content_type": "news",
                    "theme": "Первая стрижка без слёз",
                    "goal": "Помочь родителям подготовиться",
                    "source_kind": "industry_template",
                    "source_ref": "kids_hair_salon",
                    "seo_keyword": "",
                    "service_id": "",
                    "transaction_id": "",
                    "seo_views": 0,
                    "location_scope": "location-1",
                    "draft_text": "Готовый текст",
                    "status": "edited",
                    "usernews_id": "",
                    "metadata_json": {},
                    "created_at": "2026-08-07T08:59:46",
                    "updated_at": "2026-08-07T08:59:46",
                }
            ]
        elif "select coalesce(is_superadmin, false)" in normalized:
            self.one = {"coalesce": False}
        elif "select to_regclass('public.social_posts')" in normalized:
            self.one = {"to_regclass": "social_posts"}

    def fetchone(self):
        return self.one

    def fetchall(self):
        return list(self.many)


class ContentPlanAccessDatabase:
    def __init__(self):
        self.cursor_value = ContentPlanAccessCursor()
        self.conn = self
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return self.cursor_value

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        return None


def install_access_fixture(monkeypatch, *, allow_member: bool):
    database = ContentPlanAccessDatabase()
    monkeypatch.setattr(content_plan_service, "DatabaseManager", lambda: database)
    monkeypatch.setattr(content_plan_service, "ensure_content_plan_tables", lambda _cursor: None)
    monkeypatch.setattr(content_plan_service, "get_business_owner_id", lambda _cursor, _business_id: "owner-1")
    monkeypatch.setattr(content_plan_service, "_resolve_scope_target_meta", lambda *_args: {})
    monkeypatch.setattr(content_plan_service, "_record_content_plan_event", lambda **_kwargs: None)
    monkeypatch.setattr(
        content_plan_service,
        "verify_business_access",
        lambda _cursor, _business_id, user_data: (
            allow_member and user_data.get("user_id") == "member-1",
            "owner-1",
        ),
    )
    return database


def test_active_network_member_can_open_shared_content_plan(monkeypatch):
    install_access_fixture(monkeypatch, allow_member=True)

    plan = content_plan_service.get_content_plan("member-1", "plan-1")

    assert plan["id"] == "plan-1"
    assert plan["items"][0]["draft_text"] == "Готовый текст"


def test_active_network_member_can_edit_shared_content_plan_item(monkeypatch):
    database = install_access_fixture(monkeypatch, allow_member=True)
    monkeypatch.setattr(
        content_plan_service,
        "get_content_plan",
        lambda _user_id, _plan_id: {"id": "plan-1", "items": [{"id": "item-1", "draft_text": "Обновлённый текст"}]},
    )

    plan = content_plan_service.update_content_plan_item(
        "member-1",
        "item-1",
        {"draft_text": "Обновлённый текст"},
    )

    assert plan["items"][0]["draft_text"] == "Обновлённый текст"
    assert database.committed is True
    assert any(query.startswith("update contentplanitems") for query, _params in database.cursor_value.executed)


def test_content_plan_item_saves_selected_channels_in_metadata(monkeypatch):
    database = install_access_fixture(monkeypatch, allow_member=True)
    monkeypatch.setattr(
        content_plan_service,
        "get_content_plan",
        lambda _user_id, _plan_id: {"id": "plan-1", "items": [{"id": "item-1"}]},
    )

    content_plan_service.update_content_plan_item(
        "member-1",
        "item-1",
        {"selected_channels": ["telegram", "yandex_maps", "telegram", "unknown"]},
    )

    update_params = next(
        params
        for query, params in database.cursor_value.executed
        if query.startswith("update contentplanitems")
    )
    metadata_payloads = [
        json.loads(value)
        for value in update_params
        if isinstance(value, str) and value.startswith("{")
    ]
    assert {"selected_channels": ["telegram", "yandex_maps"]} in metadata_payloads


def test_content_plan_item_date_updates_prepared_social_posts(monkeypatch):
    database = install_access_fixture(monkeypatch, allow_member=True)
    monkeypatch.setattr(
        content_plan_service,
        "get_content_plan",
        lambda _user_id, _plan_id: {"id": "plan-1", "items": [{"id": "item-1", "scheduled_for": "2026-08-10"}]},
    )

    content_plan_service.update_content_plan_item(
        "member-1",
        "item-1",
        {"scheduled_for": "2026-08-10"},
    )

    social_update = next(
        (query, params)
        for query, params in database.cursor_value.executed
        if query.startswith("update social_posts")
    )
    assert social_update[1] == ("2026-08-10", "item-1")


def test_unrelated_user_cannot_open_shared_content_plan(monkeypatch):
    install_access_fixture(monkeypatch, allow_member=False)

    with pytest.raises(PermissionError, match="Нет доступа к плану"):
        content_plan_service.get_content_plan("outsider-1", "plan-1")
