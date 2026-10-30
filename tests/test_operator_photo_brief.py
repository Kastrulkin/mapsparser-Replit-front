"""Photo + caption/text/voice uses real chat journals and draft persistence, no provider calls."""

import asyncio
import io
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from PIL import Image
from tests.test_operator_voice_pg import pg  # noqa: F401
from tests.test_finance_daily_pg import daily  # noqa: F401
from tests.test_work_journal_pg import journal  # noqa: F401
from tests.test_operator_workday import workday  # noqa: F401
from tests.test_operator_workday_integration import media  # noqa: F401
from services import operator_photo_brief, operator_attachments, operator_chat_service
from services import (
    operator_audio,
    operator_core,
    operator_editorial,
    operator_telegram_inputs,
    max_inputs,
)


@pytest.fixture
def photo_flow(media, monkeypatch):  # noqa: F811
    conn, cursor = media
    cursor.execute("""CREATE TABLE contentplans(id TEXT PRIMARY KEY,business_id TEXT,plan_status TEXT,
        period_start DATE,period_end DATE,generated_plan_json JSONB,updated_at TIMESTAMPTZ DEFAULT NOW())""")
    cursor.execute("""CREATE TABLE contentplanitems(id TEXT PRIMARY KEY,plan_id TEXT,business_id TEXT,theme TEXT,
        goal TEXT,scheduled_for DATE,status TEXT,content_type TEXT,source_kind TEXT,draft_text TEXT,
        metadata_json JSONB,updated_at TIMESTAMPTZ DEFAULT NOW())""")
    cursor.execute("""CREATE TABLE social_posts(id TEXT PRIMARY KEY,business_id TEXT,content_plan_item_id TEXT,
        status TEXT,approved_at TIMESTAMPTZ,approval_id TEXT,automation_task_id TEXT,base_text TEXT,
        platform_text TEXT,scheduled_for DATE,media_json JSONB,updated_at TIMESTAMPTZ DEFAULT NOW())""")
    cursor.execute(
        "INSERT INTO contentplans VALUES ('p','b','generated','2026-10-01','2026-10-31',%s::jsonb,NOW())",
        (json.dumps({"selected_channels": ["telegram", "vk", "yandex_maps"]}),),
    )
    monkeypatch.setattr(
        operator_audio,
        "authorize_actor",
        lambda *args, **kwargs: (
            {"role": "business_user"},
            {"capabilities": ["management", "operator", "social_content"]},
        ),
    )
    monkeypatch.setattr(
        operator_editorial,
        "read_context",
        lambda *args, **kwargs: {
            "status": "completed",
            "plans": [
                {"id": "p", "period_start": "2026-10-01", "period_end": "2026-10-31"}
            ],
        },
    )
    return conn, cursor


def upload(
    cursor, channel="telegram", key="photo-1", user="admin", caption="", group=None
):
    buffer = io.BytesIO()
    Image.new("RGB", (16, 16), "red").save(buffer, format="PNG")
    item = operator_attachments.receive(
        cursor,
        business_id="b",
        user_id=user,
        channel=channel,
        content=buffer.getvalue(),
        name="photo.png",
        mime_type="image/png",
        request_key=key,
    )
    operator_photo_brief.register(cursor, item, caption=caption, group_key=group)
    return item


def context(cursor, conversation):
    cursor.execute(
        "SELECT input_context_json FROM operatorconversations WHERE id=%s",
        (conversation,),
    )
    return cursor.fetchone()["input_context_json"]


def planner(state):
    assert {tool["name"] for tool in state["tools"]} == {
        "content.story_context",
        "content.save_story",
    }
    assert "Не спрашивай имена файлов" in state["message"]
    if not state["observations"]:
        return {
            "action": "tool_call",
            "tool": "content.story_context",
            "arguments": {},
            "remaining_actions": ["content.save_story"],
        }
    errors = [
        item
        for item in state["observations"]
        if item.get("status") not in {"completed"}
    ]
    assert not errors, errors
    return {
        "action": "tool_call",
        "tool": "content.save_story",
        "remaining_actions": [],
        "arguments": {
            "plan_id": "p",
            "theme": "Уход за волосами",
            "draft_text": "Мастер Анна рассказывает об уходе за волосами.",
            "scheduled_for": "2026-10-30",
        },
    }


def run(cursor, channel, message, payload=None, selected_planner=planner):
    def router(c, **kwargs):
        return operator_core.route_operator_message(
            c, tool_planner=selected_planner, **kwargs
        )

    return operator_chat_service.process_chat(
        cursor,
        business_id="b",
        user_id="admin",
        channel=channel,
        message=message,
        payload=payload or {"request_id": "post-1"},
        router=router,
    )


@pytest.mark.parametrize("channel", ["telegram", "max_bot"])
@pytest.mark.parametrize("voice", [False, True])
def test_photo_explanation_creates_one_draft_and_attaches_exact_photo(
    photo_flow, channel, voice
):
    conn, c = photo_flow
    item = upload(c, channel, caption="Уход за волосами, мастер Анна")
    message = "Расскажи про уход за волосами, мастер Анна. Без цены."
    payload = {"request_id": "post-1"}
    if voice:
        audio = operator_audio.create_transcription(
            c,
            content=b"fake audio",
            business_id="b",
            user_id="admin",
            channel=channel,
            conversation_id=item["conversation_id"],
            request_id="voice-1",
            metadata={
                "photo_brief_ids": operator_photo_brief.voice_snapshot(
                    c, "b", "admin", channel
                )
            },
        )
        c.execute(
            "UPDATE operator_audio_assets SET status='ready',transcript=%s WHERE id=%s",
            (message, audio["asset_id"]),
        )
        c.execute(
            "UPDATE operator_async_jobs SET status='completed' WHERE id=%s",
            (audio["job_id"],),
        )
        payload.update(
            transcription_id=audio["asset_id"], conversation_id=audio["conversation_id"]
        )
    first = run(c, channel, message, payload)
    assert first["status"] == "completed", first
    assert (
        "Мастер Анна" in first["chat_response"]
        and "Ничего не опубликовано" in first["chat_response"]
    )
    repeat = run(c, channel, message, payload)
    assert repeat["idempotent"] and repeat["item_id"] == first["item_id"]
    c.execute("SELECT * FROM contentplanitems")
    posts = c.fetchall()
    assert len(posts) == 1 and posts[0]["status"] == "draft_generated"
    assert posts[0]["metadata_json"]["story_source"]["attachment_ids"] == [item["id"]]
    assert len(posts[0]["metadata_json"]["operator_photo_asset_ids"]) == 1
    assert posts[0]["metadata_json"]["selected_channels"] == [
        "telegram",
        "vk",
        "yandex_maps",
    ]
    c.execute("SELECT COUNT(*) n FROM social_posts")
    assert c.fetchone()["n"] == 0
    c.execute("SELECT COUNT(*) n FROM operatoractions")
    assert c.fetchone()["n"] == 0
    assert "photo_brief" not in context(c, item["conversation_id"])
    conn.commit()


def test_new_photo_replaces_old_and_cannot_use_another_employees_input(photo_flow):
    _, c = photo_flow
    first = upload(c)
    second = upload(c, key="photo-2")
    other = upload(c, key="other-photo", user="master")
    result = run(c, "telegram", "Уход за волосами, мастер Анна")
    c.execute(
        "SELECT metadata_json FROM contentplanitems WHERE id=%s", (result["item_id"],)
    )
    assert c.fetchone()["metadata_json"]["story_source"]["attachment_ids"] == [
        second["id"]
    ]
    with pytest.raises(PermissionError):
        operator_attachments.load(
            c, "b", "admin", other["id"], first["conversation_id"]
        )


def test_voice_and_caption_race_do_not_attach_newer_photo(photo_flow):
    _, c = photo_flow
    first = upload(c)
    audio = operator_audio.create_transcription(
        c,
        content=b"fake",
        business_id="b",
        user_id="admin",
        channel="telegram",
        conversation_id=first["conversation_id"],
        request_id="old-voice",
        metadata={"photo_brief_ids": [first["id"]]},
    )
    message = "Уход за волосами, мастер Анна"
    c.execute(
        "UPDATE operator_audio_assets SET status='ready',transcript=%s WHERE id=%s",
        (message, audio["asset_id"]),
    )
    c.execute(
        "UPDATE operator_async_jobs SET status='completed' WHERE id=%s",
        (audio["job_id"],),
    )
    upload(c, key="new-photo")
    for payload in [
        {"request_id": "late-caption", "photo_brief_ids": [first["id"]]},
        {
            "request_id": "late-voice",
            "transcription_id": audio["asset_id"],
            "conversation_id": audio["conversation_id"],
        },
    ]:
        result = run(
            c,
            "telegram",
            message,
            payload,
            selected_planner=lambda _: pytest.fail("Wrong photo generation"),
        )
        assert result["status"] == "clarification_required"
    c.execute("SELECT COUNT(*) n FROM contentplanitems")
    assert c.fetchone()["n"] == 0


@pytest.mark.parametrize(
    "message", ["Отмена", "Покажи отзывы", "Сохрани расписание на завтра"]
)
def test_another_task_clears_pending_photo(photo_flow, message):
    _, c = photo_flow
    item = upload(c)
    state = context(c, item["conversation_id"])
    result = operator_photo_brief.route_context(
        c, "b", "admin", item["conversation_id"], state, message
    )
    assert not result.get("photo_post_request") and "photo_brief" not in result
    assert not context(c, item["conversation_id"]).get("attachment_ids")


def test_expired_photo_and_album_dedup(photo_flow):
    _, c = photo_flow
    first = upload(c, group="album")
    second = upload(c, key="second", group="album")
    operator_photo_brief.register(c, second, group_key="album")
    state = context(c, first["conversation_id"])
    assert state["attachment_ids"] == [first["id"], second["id"]]
    state["photo_brief"]["received_at"] -= 1801
    result = operator_photo_brief.route_context(
        c, "b", "admin", first["conversation_id"], state, "Описание"
    )
    assert "photo_brief" not in result


def test_revoked_employee_cannot_continue(photo_flow):
    _, c = photo_flow
    upload(c)
    c.execute("UPDATE business_members SET status='revoked' WHERE user_id='admin'")
    with pytest.raises(PermissionError):
        run(c, "telegram", "Уход за волосами, мастер Анна")


@pytest.mark.parametrize("caption", ["", "Уход за волосами, мастер Анна"])
@pytest.mark.parametrize("channel", ["telegram", "max_bot"])
def test_caption_dispatches_existing_chat_and_no_caption_waits(
    photo_flow, monkeypatch, caption, channel
):
    conn, c = photo_flow
    buffer = io.BytesIO()
    Image.new("RGB", (16, 16), "red").save(buffer, format="JPEG")
    photo_media = SimpleNamespace(file_id="file", file_size=100)
    message = SimpleNamespace(
        document=None,
        photo=[photo_media],
        caption=caption,
        message_id=17,
        reply_text=AsyncMock(),
    )
    update = SimpleNamespace(
        message=message,
        effective_chat=SimpleNamespace(id=123, type="private"),
        effective_user=SimpleNamespace(id=123, is_bot=False),
    )

    def build(business, text):
        result = run(c, channel, text, business["operator_payload"])
        return {"text": result["chat_response"], "result": result}

    host = SimpleNamespace(
        user_states={},
        _control_scope_business_context=lambda _: {
            "business_id": "b",
            "user_id": "admin",
        },
        build_operator_chat_payload=build,
        _build_operator_result_markup=lambda _: None,
    )
    bot = SimpleNamespace(
        get_file=AsyncMock(
            return_value=SimpleNamespace(
                download_as_bytearray=AsyncMock(return_value=buffer.getvalue())
            )
        )
    )
    monkeypatch.setattr(operator_telegram_inputs, "transaction", lambda fn: fn(c))
    from services import operator_request_history

    monkeypatch.setattr(operator_request_history, "mark_delivery", lambda *args: None)
    from services.owner_bot_context import OwnerBotContext, current_owner_bot

    runtime = None
    if channel == "max_bot":
        from services.max_owner_dialogues import Message, DialogueOutput, InputBot

        payload = {
            "message": {
                "body": {
                    "mid": "mid-17",
                    "text": caption,
                    "attachments": [
                        {
                            "type": "image",
                            "payload": {"url": "https://example.test/photo"},
                        }
                    ],
                }
            }
        }
        output = DialogueOutput(payload)
        update.message = Message(payload, output)
        bot = InputBot(update.message)
        buffer = io.BytesIO()
        Image.new("RGB", (16, 16), "red").save(buffer, format="PNG")
        monkeypatch.setattr(
            max_inputs, "download_input", lambda url: (buffer.getvalue(), "image/png")
        )
        runtime = current_owner_bot.set(
            OwnerBotContext("123", {"id": "admin"}, {}, "event-17", c)
        )
    try:
        assert asyncio.run(
            operator_telegram_inputs.receive(update, SimpleNamespace(bot=bot), host)
        )
        response = (
            output.messages[-1]["text"]
            if channel == "max_bot"
            else message.reply_text.call_args.args[0]
        )
    finally:
        if runtime is not None:
            current_owner_bot.reset(runtime)
    assert (
        ("Черновик поста" in response)
        if caption
        else ("Названия" not in response and "Название файла не нужно" in response)
    ), response
    c.execute("SELECT COUNT(*) n FROM contentplanitems")
    assert c.fetchone()["n"] == bool(caption)


def test_max_album_and_audio_capture_same_context(photo_flow, monkeypatch):
    _, c = photo_flow
    buffer = io.BytesIO()
    Image.new("RGB", (16, 16), "red").save(buffer, format="PNG")
    monkeypatch.setattr(
        max_inputs, "download_input", lambda url: (buffer.getvalue(), "image/png")
    )
    attachments = [
        {"type": "image", "payload": {"url": "https://example.test/photo"}}
    ] * 2
    max_inputs.receive_inputs(
        c,
        attachments,
        user_id="admin",
        business_id="b",
        max_id="123",
        event_key="album",
    )
    from services.operator_conversations import find_latest_operator_conversation

    conversation = find_latest_operator_conversation(
        c, business_id="b", user_id="admin", channel="max_bot"
    )
    assert len(context(c, conversation["id"])["attachment_ids"]) == 2
    metadata = []
    monkeypatch.setattr(
        operator_audio,
        "create_transcription",
        lambda cursor, **kwargs: metadata.append(kwargs["metadata"]),
    )
    max_inputs.receive_inputs(
        c,
        [{"type": "audio", "payload": {"url": "https://example.test/audio"}}],
        user_id="admin",
        business_id="b",
        max_id="123",
        event_key="audio",
    )
    assert (
        metadata[0]["photo_brief_ids"]
        == context(c, conversation["id"])["attachment_ids"]
    )


def test_telegram_voice_receipt_freezes_photo_before_worker(photo_flow, monkeypatch):
    from services import operator_telegram_voice

    _, c = photo_flow
    item = upload(c)
    host = SimpleNamespace(
        user_states={},
        _control_scope_business_context=lambda _: {
            "business_id": "b",
            "user_id": "admin",
            "business_name": "Test",
        },
    )
    message = SimpleNamespace(
        voice=SimpleNamespace(duration=5, file_size=100, file_id="audio"),
        message_id=25,
        reply_text=AsyncMock(return_value=SimpleNamespace(message_id=26)),
    )
    update = SimpleNamespace(
        message=message,
        effective_chat=SimpleNamespace(id=123, type="private"),
        effective_user=SimpleNamespace(id=123, is_bot=False),
    )
    monkeypatch.setattr(operator_telegram_voice, "transaction", lambda fn: fn(c))
    monkeypatch.setattr(operator_telegram_voice, 'authorize_actor', operator_audio.authorize_actor)
    asyncio.run(operator_telegram_voice.receive_voice(update, SimpleNamespace(), host))
    upload(c, key="later-photo")
    c.execute("SELECT payload_json FROM operator_async_jobs WHERE kind='voice_receive'")
    assert c.fetchone()["payload_json"]["metadata"]["photo_brief_ids"] == [item["id"]]


def test_redelivered_photo_does_not_reopen_completed_brief(photo_flow):
    _, c = photo_flow
    item = upload(c)
    run(c, "telegram", "Уход за волосами, мастер Анна")
    replayed = operator_attachments.public(
        operator_attachments.load(c, "b", "admin", item["id"])
    )
    assert operator_photo_brief.register(c, replayed)
    assert "photo_brief" not in context(c, item["conversation_id"])


def test_clarification_keeps_photo_until_employee_answers(photo_flow):
    _, c = photo_flow
    item = upload(c)
    first = run(
        c,
        "telegram",
        "Работа мастера",
        selected_planner=lambda _: {
            "action": "clarification",
            "message": "Как называется услуга?",
            "remaining_actions": [],
        },
    )
    assert first["status"] == "clarification_required"
    assert context(c, item["conversation_id"])["attachment_ids"] == [item["id"]]
    result = run(
        c, "telegram", "Уход за волосами, мастер Анна", {"request_id": "answer"}
    )
    assert result["status"] == "completed"
    c.execute("SELECT metadata_json FROM contentplanitems")
    assert c.fetchone()["metadata_json"]["story_source"]["attachment_ids"] == [
        item["id"]
    ]


def test_caption_cannot_replace_selected_photo_or_publish(photo_flow):
    _, c = photo_flow
    item = upload(c)

    def untrusted_selection(state):
        decision = planner(state)
        if decision.get("tool") == "content.save_story":
            decision["arguments"].update(
                attachment_ids=["foreign-photo"], copy_text_to_channels=True
            )
        return decision

    result = run(
        c,
        "telegram",
        "Уход за волосами. Сразу опубликуй везде.",
        selected_planner=untrusted_selection,
    )
    assert result["status"] == "completed"
    c.execute("SELECT metadata_json FROM contentplanitems")
    assert c.fetchone()["metadata_json"]["story_source"]["attachment_ids"] == [
        item["id"]
    ]
    c.execute("SELECT COUNT(*) n FROM social_posts")
    assert c.fetchone()["n"] == 0
