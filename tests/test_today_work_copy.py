"""Additive display codes must never replace user content or provider state."""
from datetime import datetime, timezone

import pytest

from services.today_workspace import automation_work, content_work, influencer_work, work_item


NOW = datetime(2026, 9, 20, tzinfo=timezone.utc)
SCOPE = {"business_ids": ["business-1"]}


class Cursor:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, _query, params):
        assert params == (["business-1"],)

    def fetchall(self):
        return self.rows


def test_open_code_is_additive_and_user_copy_is_unchanged():
    item = work_item(entity_type="content_item", entity_id="item-1", flow="content",
        business_id="business-1", title="Открыть", description="Выполняется запись в таблицу.",
        status="edited", url="/dashboard/content?item_id=item-1", now=NOW)
    assert item["action"] == {"label": "Открыть", "label_code": "today.open", "url": "/dashboard/content?item_id=item-1"}
    assert item["title"] == "Открыть"
    assert item["description"] == "Выполняется запись в таблицу."
    assert item["message_code"] is None


@pytest.mark.parametrize("status,description", [
    ("waiting_provider", "Запись в таблицу подтверждена и ожидает выполнения."),
    ("provider_request_queued", "Запись в таблицу подтверждена и ожидает выполнения."),
    ("provider_executing", "Выполняется запись в таблицу."),
    ("provider_reconciliation_required", "Результат записи неизвестен. Сверьте таблицу перед следующими действиями."),
    ("provider_failed", "Запись требует внимания. Откройте результат, чтобы проверить причину."),
    ("provider_unavailable", "Для записи нужен доступ к таблице. Откройте результат, чтобы проверить подключение."),
    ("approval_invalid", "Подтверждение записи больше не действует. Откройте результат для проверки."),
])
def test_only_known_system_descriptions_get_codes(status, description):
    rows = [{"id": "run-1", "blueprint_id": "blueprint-1", "business_id": "business-1",
        "status": "waiting_provider", "provider_state": status, "name": "Проверка записей на завтра", "updated_at": NOW}]
    item = automation_work(Cursor(rows), SCOPE, NOW)[0]
    assert item["message_code"] == f"today.automation.{status}"
    assert item["description"] == description
    assert item["title"] == rows[0]["name"]
    assert item["status"] == item["reason_code"] == status
    assert item["action"]["url"] == "/dashboard/agents?blueprint_id=blueprint-1&run_id=run-1&business_id=business-1"


@pytest.mark.parametrize("run_status,provider_state", [("waiting_provider", "future_status"), ("succeeded", "provider_failed"), ("failed", None)])
def test_unknown_or_stale_provider_state_cannot_invent_system_copy(run_status, provider_state):
    item = automation_work(Cursor([{"id": "r", "blueprint_id": "b", "business_id": "business-1",
        "status": run_status, "provider_state": provider_state, "name": "Моя задача", "updated_at": NOW}]), SCOPE, NOW)[0]
    assert item["message_code"] is None
    assert item["description"] == ""
    assert item["status"] == (provider_state if run_status == "waiting_provider" else run_status)


def test_content_and_campaign_text_never_get_system_description_codes():
    content = content_work(Cursor([{"id": "i", "plan_id": "p", "business_id": "business-1",
        "theme": "Выполняется запись в таблицу.", "status": "edited", "preview": "Черновик"}]), SCOPE, NOW)[0]
    creator = influencer_work(Cursor([{"id": "c", "business_id": "business-1", "status": "replied",
        "display_name": "Открыть", "campaign_title": "Выполняется запись в таблицу.", "updated_at": NOW}]), SCOPE, NOW)[0]
    assert content["title"] == creator["description"] == "Выполняется запись в таблицу."
    assert content["message_code"] is creator["message_code"] is None
