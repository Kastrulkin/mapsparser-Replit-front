from datetime import datetime, timedelta, timezone
from pathlib import Path

from api.outreach_campaign_api import _message_queue_status


ROOT = Path(__file__).resolve().parents[1]


def test_message_queue_status_uses_honest_provider_evidence() -> None:
    now = datetime(2026, 7, 28, 10, 0, tzinfo=timezone.utc)

    assert _message_queue_status(
        {"reply_is_human": True, "delivery_status": "sent"}, now=now
    ) == "replied"
    assert _message_queue_status(
        {"receipt_event_type": "read_receipt", "delivery_status": "sent"}, now=now
    ) == "read"
    assert _message_queue_status(
        {"delivery_status": "delivered"}, now=now
    ) == "delivered"
    assert _message_queue_status(
        {"delivery_status": "sent"}, now=now
    ) == "sent"


def test_message_queue_does_not_infer_read_or_delivery_from_send() -> None:
    now = datetime(2026, 7, 28, 10, 0, tzinfo=timezone.utc)

    assert _message_queue_status(
        {"delivery_status": "sent", "receipt_event_type": None}, now=now
    ) == "sent"
    assert _message_queue_status(
        {"campaign_status": "draft", "touch_status": "draft"}, now=now
    ) == "draft"
    assert _message_queue_status(
        {
            "campaign_status": "approved",
            "touch_status": "approved",
            "channel": "email",
            "scheduled_at": now + timedelta(days=1),
        },
        now=now,
    ) == "scheduled"
    assert _message_queue_status(
        {
            "campaign_status": "approved",
            "touch_status": "awaiting_manual_send",
            "channel": "max",
            "scheduled_at": now - timedelta(minutes=1),
        },
        now=now,
    ) == "awaiting_manual_send"


def test_messages_tab_uses_a_real_touch_queue_instead_of_the_lead_list() -> None:
    api_source = (ROOT / "src/api/outreach_campaign_api.py").read_text(encoding="utf-8")
    registry_source = (
        ROOT / "frontend/src/components/prospecting/AdminLeadRegistry.tsx"
    ).read_text(encoding="utf-8")
    queue_source = (
        ROOT / "frontend/src/components/prospecting/OutreachMessageQueue.tsx"
    ).read_text(encoding="utf-8")

    assert '@outreach_campaign_bp.get("/api/outreach/messages")' in api_source
    assert "ROW_NUMBER() OVER" in api_source
    assert "PARTITION BY campaign.workstream_id" in api_source
    assert "OutreachMessageQueue" in registry_source
    assert "view === 'messages'" in registry_source
    assert "Очередь сообщений" in queue_source
    assert "Прочитано" in queue_source
    assert "Получен ответ" in queue_source
    assert "Проверить в почте" in queue_source
