"""Real local journals; deterministic planner, no provider sends."""
import uuid
import pytest
from tests.test_operator_voice_pg import pg
from tests.test_operator_editorial_pg import editorial
from services import operator_audio, operator_chat_service, operator_core, operator_editorial, operator_work_handoff


@pytest.mark.parametrize('channel', ['web', 'telegram_mini_app', 'telegram', 'max_mini_app', 'max_bot'])
@pytest.mark.parametrize('voice', [False, True])
def test_selected_post_edit_is_once_and_returns_from_bot(editorial, monkeypatch, channel, voice):
    conn, c = editorial
    item_id = str(uuid.uuid4())
    c.execute('UPDATE contentplanitems SET id=%s WHERE id=%s', (item_id, 'i'))
    c.execute('ALTER TABLE users ADD COLUMN telegram_id TEXT, ADD COLUMN is_active BOOLEAN DEFAULT TRUE')
    c.execute("ALTER TABLE operatorconversations ADD COLUMN input_context_json JSONB DEFAULT '{}'")
    c.execute("UPDATE users SET telegram_id='123'")
    c.execute('CREATE TABLE max_identities(user_id TEXT,max_id TEXT,revoked_at TIMESTAMPTZ)')
    c.execute("INSERT INTO max_identities VALUES('u','123',NULL)")
    monkeypatch.setenv('MAX_BOT_USERNAME', 'fixture_bot')
    def authorize(cursor, user_id, business_id, **kwargs):
        if user_id != 'u' or business_id != 'b': raise PermissionError('Foreign business')
        return {'role': 'business_owner'}, {'capabilities': ['operator', 'social_content']}
    monkeypatch.setattr(operator_audio, 'authorize_actor', authorize)
    row = next(row for row in operator_editorial._items(c, 'b') if row['id'] == item_id)
    version = operator_editorial._version(row)
    command = 'Измени тему поста на Пошив для команды'
    payload = {'request_id': 'one-edit', 'selected_object': {'type': 'content_item', 'id': item_id, 'version': version}}
    audio = None
    if voice:
        audio = operator_audio.create_transcription(c, content=b'provider fixture', user_id='u', business_id='b', channel=channel, conversation_id=None, request_id='one-recording')
        c.execute("UPDATE operator_audio_assets SET status='ready',transcript=%s WHERE id=%s", (command, audio['asset_id']))
        c.execute("UPDATE operator_async_jobs SET status='completed' WHERE id=%s", (audio['job_id'],))
        payload.update(transcription_id=audio['asset_id'], conversation_id=audio['conversation_id'])
    calls = []
    def planner(state):
        calls.append(state)
        return {'action': 'tool_call', 'tool': 'content.edit_item', 'arguments': {'item_id': item_id, 'plan_id': 'p', 'version': version, 'theme': 'Пошив для команды'}}
    def router(cursor, **kwargs): return operator_core.route_operator_message(cursor, tool_planner=planner, **kwargs)
    kwargs = dict(business_id='b', user_id='u', channel=channel, message=command, payload=payload, router=router)
    result = operator_chat_service.process_chat(c, **kwargs); conn.commit()
    repeated = operator_chat_service.process_chat(c, **kwargs)
    assert result['status'] == 'completed' and result['message_id'] == repeated['message_id']
    assert len(calls) == 1
    platform = 'max' if channel.startswith('max') else 'telegram'
    assert f'/{platform}/control?' in result['work_return_url'] and item_id in result['work_return_url']
    c.execute('SELECT theme,draft_text,metadata_json FROM contentplanitems WHERE id=%s', (item_id,))
    changed = c.fetchone()
    assert changed['theme'] == 'Пошив для команды' and changed['draft_text'] is None
    assert len(changed['metadata_json']['operator_edit_history']) == 1
    link = operator_work_handoff.prepare_handoff(c, user_id='u', business_id='b', platform=platform, item_id=item_id, request_id=str(uuid.uuid4())); conn.commit()
    resumed = operator_work_handoff.resume_handoff(c, user_id='u', platform=platform, token=link['url'].split('start=')[1])
    assert item_id in resumed['return_url'] and len(calls) == 1
    c.execute('SELECT pending_context FROM operatorconversations WHERE id=%s', (resumed['conversation_id'],))
    assert c.fetchone()['pending_context']['selected_item']['item_id'] == item_id
    if audio:
        c.execute('SELECT status,corrected_text FROM operator_audio_assets WHERE id=%s', (audio['asset_id'],))
        assert c.fetchone() == {'status': 'submitted', 'corrected_text': command}
