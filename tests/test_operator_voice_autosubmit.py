import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from services import operator_core, operator_query, operator_telegram_voice


@pytest.mark.parametrize('message', [
    'Покажи мне следующий пост который будет опубликован на google бизнес от райдеры',
    'Это прошлые посты которые уже были опубликованы покажи мне следующий после 11 сентября который должен быть опубликован',
    'Ты видишь контент план',
])
def test_real_voice_requests_read_plan_without_publication(monkeypatch, message):
    monkeypatch.setattr(operator_query, '_load_module_items', lambda *args, **kwargs: ([
        {'title': 'Прошлый', 'scheduled_for': '2026-08-10', 'status': 'edited'},
        {'title': 'Следующий', 'scheduled_for': '2099-09-12', 'status': 'edited', 'draft_text': 'Проверенный текст'},
    ], {}))
    result, _ = operator_core.route_operator_message(None, business_id='b', user_id='u', message=message, channel='telegram')
    assert result['status'] == 'completed'
    assert result['capability'] == 'operator.query'
    assert result['items'][0]['title'] == 'Следующий'
    assert not result['external_writes_performed']


def test_publish_stays_guarded():
    result, _ = operator_core.route_operator_message(None, business_id='b', user_id='u', message='Опубликуй следующий пост', channel='telegram')
    assert result['capability'] == 'content.publish_external'
    assert result['status'] != 'completed'


@pytest.mark.parametrize('changed', [False, True])
def test_voice_delivers_transcript_then_result_without_click(monkeypatch, changed):
    app = SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock()))
    calls = []
    business = {'business_id': 'other' if changed else 'b', 'user_id': 'u', 'telegram_id': '1'}
    host = SimpleNamespace(_control_scope_business_context=lambda _: business,
        build_operator_chat_payload=lambda ctx, text: calls.append(ctx['operator_payload']) or {'text': 'Ответ', 'result': {}},
        _build_operator_result_markup=lambda _: None)
    monkeypatch.setattr(operator_telegram_voice, 'transaction', lambda _: None)
    monkeypatch.setattr(operator_telegram_voice, 'queue_reply_speech', AsyncMock())
    asset = {'id': 'a', 'business_id': 'b', 'user_id': 'u', 'conversation_id': 'c', 'transcript': 'Что ты умеешь?', 'metadata_json': {'chat_id': 1}}
    asyncio.run(operator_telegram_voice.submit_recognized_voice(app, host, asset))
    if changed:
        assert not calls
    else:
        assert calls == [{'conversation_id': 'c', 'transcription_id': 'a', 'request_id': 'voice:a'}]
        messages = app.bot.send_message.call_args_list
        assert 'Распознано' in messages[0].kwargs['text']
        assert messages[1].kwargs['text'] == 'Ответ'
        assert messages[0].kwargs.get('reply_markup') is None


def test_next_post_excludes_published_and_old_items(monkeypatch):
    observed = []
    def query(cursor, **kwargs):
        observed.append(kwargs)
        return {'status': 'completed', 'items': [{'status': 'published', 'title': 'Already published'}], 'query': {'resource': 'content'}}
    monkeypatch.setattr(operator_core, 'execute_operator_query', query)
    result = operator_core._read_requested_content(None, 'riderra', 'Покажи следующий пост после 11 сентября 2026')
    assert observed[0]['business_id'] == 'riderra'
    assert observed[0]['arguments']['filters'][0]['value'] == '2026-09-12'
    assert result['items'] == []
    assert 'не нашёл' in result['chat_response']


def test_historical_query_not_replaced_with_future_plan():
    assert not operator_core._content_read_request('Покажи посты опубликованные вчера')


def test_voice_retry_keeps_same_execution_key_and_skips_delivered_messages(monkeypatch):
    app = SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock()))
    calls = []
    host = SimpleNamespace(_control_scope_business_context=lambda _: {'business_id': 'b', 'user_id': 'u'},
        build_operator_chat_payload=lambda ctx, text: calls.append(ctx['operator_payload']['request_id']) or {'text': 'Saved', 'result': {'idempotent': True}},
        _build_operator_result_markup=lambda _: None)
    monkeypatch.setattr(operator_telegram_voice, 'queue_reply_speech', AsyncMock())
    asset = {'id': 'a', 'business_id': 'b', 'user_id': 'u', 'conversation_id': 'c', 'transcript': 'Command',
        'metadata_json': {'chat_id': 1, 'transcript_delivered': True, 'result_delivered': True}}
    asyncio.run(operator_telegram_voice.submit_recognized_voice(app, host, asset))
    assert calls == ['voice:a']
    app.bot.send_message.assert_not_called()
