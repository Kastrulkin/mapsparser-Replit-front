from types import SimpleNamespace
import asyncio
from unittest.mock import AsyncMock
import pytest
from services import operator_audio,max_inputs,operator_telegram_voice

@pytest.mark.parametrize('name,mime,expected',[('voice.wav','application/octet-stream',True),('voice.M4A',None,True),('voice','audio/ogg',True),('table.csv','text/csv',False),('photo.jpg','image/jpeg',False),('voice.wav.exe','application/octet-stream',False)])
def test_audio_file_classification(name,mime,expected):
    assert operator_audio.is_audio_document(name,mime)==expected
    assert max_inputs.is_audio_attachment({'type':'file','payload':{'filename':name,'mime_type':mime}})==expected


def test_max_audio_file_uses_existing_voice_queue(monkeypatch):
    calls=[]
    monkeypatch.setattr(max_inputs,'download_input',lambda url:(b'qa-audio','audio/wav'))
    monkeypatch.setattr(operator_audio,'create_transcription',lambda *a,**kw:calls.append(kw))
    out=max_inputs.receive_inputs(None,[{'type':'file','payload':{'filename':'voice.wav','url':'https://example.org/audio'}}],user_id='u',business_id='b',max_id='123',event_key='event')
    assert 'Голосовое получено' in out
    assert calls[0]['channel']=='max_bot' and calls[0]['request_id']=='max:event:0'
    assert calls[0]['metadata']=={'max_id':'123','business_id':'b'}


@pytest.mark.parametrize('audio_attribute',['voice','audio','document'])
def test_telegram_voice_and_audio_files_reuse_durable_download(monkeypatch,audio_attribute):
    from services import operator_async_jobs
    message=SimpleNamespace(voice=None,audio=None,document=None,message_id=42,reply_text=AsyncMock(return_value=SimpleNamespace(message_id=43)))
    setattr(message,audio_attribute,SimpleNamespace(file_id='qa-file',file_size=300,duration=10))
    update=SimpleNamespace(message=message,effective_chat=SimpleNamespace(id=1,type='private'),effective_user=SimpleNamespace(id=1,is_bot=False))
    host=SimpleNamespace(_control_scope_business_context=lambda _: {'user_id':'u','business_id':'b','business_name':'QA'},user_states={})
    calls=[]
    class Cursor:
        def execute(self,*args):pass
        def fetchone(self):return {}
    monkeypatch.setattr(operator_telegram_voice,'transaction',lambda fn:fn(Cursor()))
    monkeypatch.setattr(operator_telegram_voice,'authorize_actor',lambda *a:None)
    monkeypatch.setattr(operator_telegram_voice,'enabled',lambda *a:True)
    monkeypatch.setattr(operator_async_jobs,'create_operator_async_job',lambda c,**kw:calls.append(kw) or {'id':'job'})
    asyncio.run(operator_telegram_voice.receive_voice(update,None,host))
    assert calls[0]['kind']=='voice_receive' and calls[0]['payload']['file_id']=='qa-file'
    assert calls[0]['payload']['metadata']['durable_execution'] is True
    message.reply_text.assert_awaited_once()


def test_cancel_only_rejects_current_messenger_pending_actions(monkeypatch):
    from services import operator_conversations,operator_core
    calls=[]
    class Cursor:
        def execute(self,*a):pass
        def fetchone(self):return {'present':'operatorconversations'}
    monkeypatch.setattr(operator_conversations,'find_latest_operator_conversation',lambda c,**kw:calls.append(('conversation',kw)) or {'id':'own-max'})
    monkeypatch.setattr(operator_conversations,'list_pending_operator_actions',lambda c,**kw:calls.append(('pending',kw)) or [{'id':'pending-own'}])
    monkeypatch.setattr(operator_core,'reject_pending_operator_action',lambda c,**kw:calls.append(('reject',kw)) or ({'status':'rejected'},False))
    monkeypatch.setattr(operator_conversations,'set_operator_pending_context',lambda *a:calls.append(('clear',a[1:])))
    assert operator_conversations.cancel_owner_input(Cursor(),business_id='b',user_id='u',channel='max_bot')
    assert calls[0][1]=={'business_id':'b','user_id':'u','channel':'max_bot'}
    assert calls[1][1]['conversation_id']=='own-max'
    assert calls[2][1]=={'action_id':'pending-own','business_id':'b','user_id':'u'}
