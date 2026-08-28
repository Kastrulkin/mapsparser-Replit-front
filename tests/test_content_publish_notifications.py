import json
from datetime import datetime, timezone

from services.content_publish_notifications import (
    collect_due_content_publish_handoffs,
    format_content_publish_handoff,
    mark_content_publish_handoff_sent,
)
from services import social_post_service


class Cursor:
    def __init__(self):
        self.description = []
        self.rows = []
        self.rowcount = 0
        self.metadata = {}

    def execute(self, sql, params=None):
        normalized = " ".join(sql.lower().split())
        if "from telegramcontrolpreferences" in normalized:
            self.description = [("user_id",), ("telegram_id",), ("notification_preferences_json",)]
            self.rows = [("user-1", "123", {"business:biz-1": {"content_publications": True}})]
        elif "from social_posts sp" in normalized:
            self.description = [
                ("id",), ("business_id",), ("content_plan_item_id",), ("platform",),
                ("publish_mode",), ("status",), ("scheduled_for",), ("platform_text",),
                ("metadata_json",), ("business_name",), ("business_address",),
            ]
            self.rows = [(
                "post-1", "biz-1", "item-1", "vk", "manual", "approved",
                datetime(2026, 8, 23, tzinfo=timezone.utc), "Готовый текст", {},
                "Весёлая расчёска", "проспект Энгельса, 154",
            )]
        elif "from photo_asset_usage_events usage" in normalized:
            self.description = [
                ("id",), ("original_url",), ("storage_key",), ("versions_json",),
                ("metadata_json",), ("target_platform",), ("created_at",),
            ]
            self.rows = [(
                "photo-1", "", "localos-media/businesses/biz-1/photo.jpg",
                {"original": {"storage_path": "s3://media/photo.jpg", "mime_type": "image/jpeg"}},
                {"upload": {"original_name": "visit.jpg"}}, "vk",
                datetime(2026, 8, 22, tzinfo=timezone.utc),
            )]
        elif "select metadata_json from social_posts" in normalized:
            self.description = [("metadata_json",)]
            self.rows = [(self.metadata,)]
        elif normalized.startswith("update social_posts set metadata_json"):
            self.metadata = params[0]
            self.rowcount = 1
            self.rows = []

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0] if self.rows else None


class Connection:
    def __init__(self):
        self.cursor_value = Cursor()

    def cursor(self):
        return self.cursor_value


def test_collects_only_enabled_manual_handoff():
    connection = Connection()
    handoffs = collect_due_content_publish_handoffs(
        connection,
        now=datetime(2026, 8, 23, 10, tzinfo=timezone.utc),
    )
    assert len(handoffs) == 1
    assert handoffs[0]["telegram_id"] == "123"
    assert handoffs[0]["platform"] == "vk"
    assert handoffs[0]["selected_photo"]["id"] == "photo-1"
    assert handoffs[0]["selected_photo"]["storage_path"] == "s3://media/photo.jpg"


def test_formats_copy_ready_message_and_link():
    message, reply_markup = format_content_publish_handoff(
        {
            "platform": "telegram",
            "business_name": "Весёлая расчёска",
            "business_address": "проспект Энгельса, 154",
            "platform_text": "Готовый текст",
            "business_id": "biz-1",
            "content_plan_item_id": "item-1",
            "scheduled_for": datetime(2026, 8, 24, tzinfo=timezone.utc),
        }
    )
    assert "Telegram · 24.08.2026" in message
    assert "Готовый текст" in message
    assert reply_markup["inline_keyboard"][0][0]["text"] == "Открыть публикацию"


def test_marks_delivery_in_post_metadata():
    connection = Connection()
    assert mark_content_publish_handoff_sent(
        connection,
        post_id="post-1",
        user_id="user-1",
        telegram_message_id=42,
        telegram_photo_message_id=41,
        sent_at=datetime(2026, 8, 23, 10, tzinfo=timezone.utc),
    )
    metadata = json.loads(connection.cursor_value.metadata)
    assert metadata["staff_handoff"]["telegram_deliveries"]["user-1"]["telegram_message_id"] == 42
    assert metadata["staff_handoff"]["telegram_deliveries"]["user-1"]["telegram_photo_message_id"] == 41


def test_sends_selected_photo_to_staff_telegram(monkeypatch):
    monkeypatch.setattr(
        social_post_service,
        "_media_asset_file",
        lambda media_asset: {
            "content": b"photo",
            "mime_type": "image/jpeg",
            "filename": "visit.jpg",
        },
    )
    monkeypatch.setattr(
        social_post_service,
        "_telegram_api_call",
        lambda token, method, payload, files: {
            "ok": method == "sendPhoto" and payload["chat_id"] == "123" and bool(files),
            "result": {"message_id": 41},
        },
    )

    result = social_post_service.send_telegram_photo_message(
        bot_token="token",
        chat_id="123",
        media_asset={"id": "photo-1"},
        caption="Фото для публикации",
    )

    assert result == {"success": True, "message_id": 41, "reason_code": ""}
