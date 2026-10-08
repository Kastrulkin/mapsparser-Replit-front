from services import operator_content_publication as publication
from services.operator_editorial import editorial_input


def _post(**changes):
    return {
        "id": "post-1", "platform": "telegram", "status": "needs_review",
        "publish_mode": "api", "scheduled_for": "2026-10-06",
        "updated_at": "2026-10-06T09:00:00+00:00",
        "base_text": "Base copy", "platform_text": "Telegram copy",
        "media_json": [{"url": "image.jpg"}], **changes,
    }


def test_publication_commands_are_routed_to_editorial_tools():
    assert editorial_input("Опубликуй этот пост в Telegram")
    assert editorial_input("Опубликовать в Яндекс Картах")
    assert editorial_input("Проверь публикацию в VK")
    assert not editorial_input("Какие публикации запланированы на этой неделе?")


def test_channel_copy_edit_requires_fresh_version_and_exact_user_text(monkeypatch):
    post = _post()
    monkeypatch.setattr(publication, '_load_posts', lambda *args, **kwargs: [post])

    stale = publication.edit_channel_text(object(), business_id='business-1', user_id='user-1',
        message='Поменяй на Новый точный текст для канала.', arguments={'post_id':'post-1','text':'Новый точный текст для канала.','version':'old'})
    invented = publication.edit_channel_text(object(), business_id='business-1', user_id='user-1',
        message='Поменяй текст.', arguments={'post_id':'post-1','text':'Новый точный текст для канала.','version':publication._snapshot(post)['digest']})
    assert stale['status'] == 'blocked'
    assert invented['status'] == 'clarification_required'


def test_channel_snapshot_changes_when_text_media_or_post_version_changes():
    post = _post()
    initial = publication._snapshot(post)["digest"]
    assert publication._snapshot({**post, "platform_text": "Changed"})["digest"] != initial
    assert publication._snapshot({**post, "media_json": [{"url": "other.jpg"}]})["digest"] != initial
    assert publication._snapshot({**post, "updated_at": "2026-10-06T09:01:00+00:00"})["digest"] != initial


def test_chat_projects_handoff_receipt_without_changing_publication_status(monkeypatch):
    post = _post(metadata_json={
        "staff_handoff": {
            "telegram_deliveries": {
                "staff-1": {"parts": {"photo": {"status": "sent"}, "text:0": {"status": "sent"}}}
            }
        }
    })
    monkeypatch.setattr(publication, "_load_posts", lambda *args, **kwargs: [post])

    result = publication.list_channel_posts(object(), business_id="business-1", user_id="user-1")

    assert result["posts"][0]["handoff_status"] == "partially_delivered"
    assert result["posts"][0]["status"] == "needs_review"


def test_channel_copy_edit_updates_same_post_and_returns_it_to_review(monkeypatch):
    post = _post()
    monkeypatch.setattr(publication, '_load_posts', lambda *args, **kwargs: [post])

    class Cursor:
        rowcount = 1

        def __init__(self):
            self.calls = []

        def execute(self, query, params=()):
            self.calls.append((query, params))

        def fetchone(self):
            return {'id':'post-1'}

    cursor = Cursor()
    result = publication.edit_channel_text(cursor, business_id='business-1', user_id='user-1',
        message='Поменяй на Новый точный текст для канала.',
        arguments={'post_id':'post-1','text':'Новый точный текст для канала.','version':publication._snapshot(post)['digest']})

    assert result['status'] == 'completed'
    assert "status='needs_review'" in cursor.calls[0][0]
    assert "updated_at = %s::timestamptz" in cursor.calls[0][0]
    assert cursor.calls[0][1][0] == 'Новый точный текст для канала.'


def test_prepare_publish_binds_approval_to_exact_platform_copy(monkeypatch):
    monkeypatch.setattr(publication, "_load_posts", lambda *args, **kwargs: [_post()])
    monkeypatch.setattr("services.social_post_service.get_social_channel_readiness", lambda *args: {
        "channel_readiness": [{"platform": "telegram", "ready": True, "status": "ready"}]
    })

    result = publication.prepare_publish(
        object(), business_id="business-1", user_id="user-1", post_ids=["post-1"]
    )

    assert result["status"] == "approval_required"
    assert result["external_writes_performed"] is False
    assert "Telegram copy" in result["approval"]["summary"]
    assert result["approval"]["envelope"]["snapshots"] == [publication._snapshot(_post())]


def test_prepare_publish_refuses_posts_without_copy_or_already_in_flight(monkeypatch):
    monkeypatch.setattr("services.social_post_service.get_social_channel_readiness", lambda *args: {
        "channel_readiness": [{"platform": "telegram", "ready": True, "status": "ready"}]
    })
    monkeypatch.setattr(publication, "_load_posts", lambda *args, **kwargs: [_post(platform_text="", base_text="")])
    missing_text = publication.prepare_publish(
        object(), business_id="business-1", user_id="user-1", post_ids=["post-1"]
    )
    assert missing_text["status"] == "blocked"

    monkeypatch.setattr(publication, "_load_posts", lambda *args, **kwargs: [_post(status="publishing")])
    in_flight = publication.prepare_publish(
        object(), business_id="business-1", user_id="user-1", post_ids=["post-1"]
    )
    assert in_flight["status"] == "blocked"


def test_prepare_publish_blocks_unready_api_channel(monkeypatch):
    monkeypatch.setattr(publication, "_load_posts", lambda *args, **kwargs: [_post()])
    monkeypatch.setattr("services.social_post_service.get_social_channel_readiness", lambda *args: {
        "channel_readiness": [{"platform": "telegram", "ready": False, "status": "missing_keys"}]
    })

    result = publication.prepare_publish(
        object(), business_id="business-1", user_id="user-1", post_ids=["post-1"]
    )

    assert result["status"] == "blocked"
    assert "missing_keys" in result["chat_response"]


def test_publish_confirmation_rejects_changed_post_without_provider_write(monkeypatch):
    current = _post(platform_text="Edited after preview")
    monkeypatch.setattr(publication, "_load_posts", lambda *args, **kwargs: [current])
    writes = []
    monkeypatch.setattr("services.social_post_service.approve_social_post", lambda *args: writes.append("approve"))
    monkeypatch.setattr("services.social_post_service.publish_social_post", lambda *args: writes.append("publish"))
    envelope = {
        "business_id": "business-1", "post_ids": ["post-1"],
        "snapshots": [publication._snapshot(_post())],
    }

    result = publication.publish_confirmed(
        object(), business_id="business-1", user_id="user-1", envelope=envelope
    )

    assert result["status"] == "blocked"
    assert writes == []
    assert result["external_writes_performed"] is False


def test_publish_confirmation_reports_uncertain_provider_result_without_calling_it_success(monkeypatch):
    post = _post()
    monkeypatch.setattr(publication, "_load_posts", lambda *args, **kwargs: [post])
    monkeypatch.setattr("services.social_post_service.approve_social_post", lambda *args: post)
    monkeypatch.setattr("services.social_post_service.publish_social_post", lambda *args: {**post, "status": "publishing"})
    result = publication.publish_confirmed(
        object(), business_id="business-1", user_id="user-1",
        envelope={"business_id": "business-1", "post_ids": ["post-1"],
                  "snapshots": [publication._snapshot(post)]},
    )

    assert result["status"] == "blocked"
    assert "Повторно не отправляйте" in result["chat_response"]
    assert result["external_writes_performed"] is False


def test_manual_confirmation_requires_explicit_content_check(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "services.social_post_service.mark_manual_published",
        lambda user_id, post_id, **kwargs: calls.append(kwargs) or {
            "id": post_id, "platform": "vk", "status": "published", "provider_post_url": kwargs["provider_post_url"]
        },
    )

    publication.reconcile_manual(
        user_id="user-1", post_id="post-2", provider_post_url="https://vk.com/wall/1",
        content_confirmed=True,
    )

    assert calls == [{"provider_post_url": "https://vk.com/wall/1", "provider_post_id": "", "content_confirmed": True}]
