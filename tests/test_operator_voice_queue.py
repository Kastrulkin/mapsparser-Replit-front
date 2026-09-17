import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from services import operator_voice_queue, operator_telegram_voice


def test_transport_never_executes_durable_command(monkeypatch):
    host=SimpleNamespace(build_operator_chat_payload=lambda *a:pytest.fail('delivery executed command'),_build_operator_result_markup=lambda _:None)
    app=SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock()))
    asset={'user_id':'u','business_id':'b','id':'a','metadata_json':{'chat_id':1,'durable_execution':True,'operator_payload':{'text':'Сохранено','result':{'status':'completed'}}}}
    monkeypatch.setattr(operator_telegram_voice,'transaction',lambda fn:None)
    monkeypatch.setattr(operator_telegram_voice,'queue_reply_speech',AsyncMock())
    from services import operator_request_history
    monkeypatch.setattr(operator_request_history,'mark_delivery',lambda *a:None)
    asyncio.run(operator_telegram_voice.submit_recognized_voice(app,host,asset))
    assert app.bot.send_message.call_args.kwargs['text']=='Сохранено'


def test_pending_execution_never_marked_delivered():
    asset={'metadata_json':{'chat_id':1,'durable_execution':True}}
    app=SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock()))
    assert asyncio.run(operator_telegram_voice.submit_recognized_voice(app,None,asset)) is False
    app.bot.send_message.assert_not_called()


def test_download_error_never_exposes_token(monkeypatch):
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN','private-token')
    def fail(*args,**kwargs):raise RuntimeError('https://api.telegram.org/botprivate-token/getFile')
    monkeypatch.setattr(operator_voice_queue.requests,'post',fail)
    with pytest.raises(ValueError,match=r'^Не удалось получить запись из Telegram. Задание сохранено для повторной попытки\.$'):
        operator_voice_queue.download('file')


def test_execution_enqueued_with_stable_key(monkeypatch):
    calls=[]
    monkeypatch.setattr(operator_voice_queue,'create_operator_async_job',lambda cursor,**kwargs:calls.append(kwargs))
    asset={'id':'a','user_id':'u','business_id':'b','channel':'telegram','metadata_json':{'durable_execution':True}}
    operator_voice_queue.enqueue_execution(None,asset);operator_voice_queue.enqueue_execution(None,asset)
    assert calls[0]['idempotency_key']==calls[1]['idempotency_key']=='voice-execute:a'


def test_legacy_review_not_autoexecuted(monkeypatch):
    monkeypatch.setattr(operator_voice_queue,'create_operator_async_job',lambda *a,**k:pytest.fail('legacy submission'))
    operator_voice_queue.enqueue_execution(None,{'channel':'telegram','metadata_json':{}})


def test_repeated_delivery_does_not_run_completed_command(monkeypatch):
    app=SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock()))
    host=SimpleNamespace(_build_operator_result_markup=lambda _:None)
    asset={'id':'a','user_id':'u','business_id':'b','metadata_json':{'chat_id':1,'durable_execution':True,'result_delivered':True,
        'operator_payload':{'text':'Сохранено','result':{'status':'completed'}}}}
    monkeypatch.setattr(operator_telegram_voice,'queue_reply_speech',AsyncMock())
    asyncio.run(operator_telegram_voice.submit_recognized_voice(app,host,asset))
    app.bot.send_message.assert_not_called()
