from datetime import datetime, timezone

from services import content_publish_notifications


def item():
    return {"id": "post", "user_id": "irina", "telegram_id": "123", "platform": "vk",
            "business_timezone": "Asia/Yekaterinburg", "lead_days": "1",
            "scheduled_for": datetime(2026, 10, 2, 0, tzinfo=timezone.utc),
            "selected_photo": {"id": "photo"}, "platform_text": "Текст"}


def test_calendar_day_not_24_hours_or_utc_day():
    post = item()
    assert content_publish_notifications.handoff_due(post, datetime(2026, 9, 30, 20, tzinfo=timezone.utc))
    assert not content_publish_notifications.handoff_due(post, datetime(2026, 10, 2, 0, tzinfo=timezone.utc))
    assert not content_publish_notifications.handoff_due({**post, "business_timezone": ""}, datetime.now(timezone.utc))
    assert not content_publish_notifications.handoff_due({**post, "scheduled_for": None}, datetime.now(timezone.utc))


def test_revision_changes_for_content_date_and_photo():
    original = item()
    revision = content_publish_notifications.handoff_revision(original)
    for key, value in [("platform_text", "Новая версия"), ("selected_photo", {"id": "new"}), ("scheduled_for", datetime.now(timezone.utc))]:
        assert content_publish_notifications.handoff_revision({**original, key: value}) != revision


class Connection:
    def rollback(self):
        pass


def test_partial_delivery_retries_only_known_unsent_part(monkeypatch):
    parts = {"photo": {"status": "sent", "message_id": 1}}
    monkeypatch.setattr(content_publish_notifications, "claim_handoff_part", lambda conn, post, key: parts.get(key, {"status": "claimed"}))
    monkeypatch.setattr(content_publish_notifications, "finish_handoff_part", lambda conn, post, key, result, **kw: parts.update({key: {"status": "sent"}}))
    sent = []
    result = content_publish_notifications.deliver_content_publish_handoff(Connection(), item(),
        send_photo=lambda post: (_ for _ in ()).throw(AssertionError("duplicate photo")),
        send_text=lambda chat, text, **kw: sent.append(text) or {"success": True, "message_id": 2})
    assert result == "sent" and len(sent) == 1


def test_uncertain_delivery_never_retries(monkeypatch):
    monkeypatch.setattr(content_publish_notifications, "claim_handoff_part", lambda *args: {"status": "uncertain"})
    def send(*args, **kwargs):
        raise AssertionError("provider called despite unknown receipt")
    assert content_publish_notifications.deliver_content_publish_handoff(Connection(), item(), send_photo=send, send_text=send) == "uncertain"


def test_long_text_delivered_without_truncation(monkeypatch):
    monkeypatch.setattr(content_publish_notifications, "claim_handoff_part", lambda *args: {"status": "claimed"})
    monkeypatch.setattr(content_publish_notifications, "finish_handoff_part", lambda *args, **kw: None)
    post = {**item(), "platform_text": "🌍" * 7000}
    expected, _ = content_publish_notifications.format_content_publish_handoff(post)
    chunks = []
    result = content_publish_notifications.deliver_content_publish_handoff(Connection(), post,
        send_photo=lambda post: {"success": True, "message_id": 1},
        send_text=lambda chat, text, **kw: chunks.append(text) or {"success": True, "message_id": 2})
    assert result == "sent" and "".join(chunks) == expected
    assert all(len(chunk.encode("utf-16-le")) // 2 <= 4096 for chunk in chunks)


def test_missing_photo_does_not_send_text():
    def send(*args, **kwargs):
        raise AssertionError("incomplete kit sent")
    assert content_publish_notifications.deliver_content_publish_handoff(Connection(), {**item(), "selected_photo": None}, send_photo=send, send_text=send) == "incomplete"


def test_all_selected_photos_have_separate_receipts(monkeypatch):
    monkeypatch.setattr(content_publish_notifications, 'claim_handoff_part', lambda *args: {'status': 'claimed'})
    receipts = []
    monkeypatch.setattr(content_publish_notifications, 'finish_handoff_part', lambda conn, post, key, result, **kw: receipts.append(key))
    photos = []
    post = {**item(), 'selected_photos': [{'id': 'one'}, {'id': 'two'}]}
    content_publish_notifications.deliver_content_publish_handoff(Connection(), post,
        send_photo=lambda post: photos.append(post['selected_photo']['id']) or {'success': True, 'message_id': 1},
        send_text=lambda *args, **kw: {'success': True, 'message_id': 2})
    assert photos == ['one', 'two'] and receipts == ['photo', 'photo:1', 'text:0']


def test_changed_delivered_material_can_update_on_publication_day_before_deadline():
    post = {**item(), 'is_update': True, 'scheduled_for': datetime(2026,10,2,12,tzinfo=timezone.utc)}
    assert content_publish_notifications.handoff_due(post, datetime(2026,10,2,7,tzinfo=timezone.utc))
    assert not content_publish_notifications.handoff_due({**post, 'is_update': False}, datetime(2026,10,2,7,tzinfo=timezone.utc))
    assert not content_publish_notifications.handoff_due(post, datetime(2026,10,2,13,tzinfo=timezone.utc))
