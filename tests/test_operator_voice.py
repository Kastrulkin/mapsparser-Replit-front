"""Voice boundary tests without external providers."""
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from services import operator_audio, operator_speechkit, operator_conversations


@pytest.fixture(autouse=True)
def voice_pilot(monkeypatch):
    monkeypatch.setenv('OPERATOR_VOICE_INPUT_ENABLED','true')
    monkeypatch.setenv('OPERATOR_VOICE_BUSINESS_IDS','b')


class Cursor:
    def __init__(self, rows=()):
        self.rows=list(rows); self.calls=[]
    def execute(self, sql, args=None): self.calls.append((sql,args))
    def fetchone(self): return self.rows.pop(0) if self.rows else None


def test_foreign_conversation_is_rejected_not_silently_replaced():
    cursor=Cursor()
    with pytest.raises(ValueError):
        operator_conversations.get_or_create_operator_conversation(cursor,business_id='b',user_id='u',channel='web',conversation_id='foreign')
    assert len(cursor.calls)==1
    assert 'channel = %s' in cursor.calls[0][0]


@pytest.mark.parametrize('kind', ['transcription','speech'])
def test_flags_fail_closed_and_require_pilot(monkeypatch,kind):
    monkeypatch.setenv('OPERATOR_VOICE_INPUT_ENABLED','true'); monkeypatch.setenv('OPERATOR_VOICE_OUTPUT_ENABLED','true')
    monkeypatch.setenv('OPERATOR_VOICE_BUSINESS_IDS','pilot')
    assert operator_audio.enabled(kind,'pilot')
    assert not operator_audio.enabled(kind,'other')


def test_unrelated_yandex_key_is_not_used(monkeypatch):
    monkeypatch.delenv('OPERATOR_SPEECHKIT_API_KEY',raising=False)
    monkeypatch.setenv('YANDEX_WORDSTAT_API_KEY','not-speechkit')
    with pytest.raises(ValueError): operator_speechkit.SpeechKit()


def test_empty_and_oversized_upload_never_reserves_or_calls_provider():
    for content in (b'',b'x'*(operator_audio.MAX_BYTES+1)):
        with pytest.raises(ValueError): operator_audio.create_transcription(Cursor(),content=content)


def test_private_path_rejects_escape(tmp_path,monkeypatch):
    monkeypatch.setenv('OPERATOR_AUDIO_DIR',str(tmp_path/'audio'))
    with pytest.raises(PermissionError): operator_audio.private_path(str(tmp_path/'secret'))


@pytest.mark.parametrize('state', ['submitted','cancelled','queued'])
def test_unreviewable_transcript_cannot_execute(monkeypatch,state):
    monkeypatch.setattr(operator_audio,'load_asset',lambda *args:{'kind':'transcription','conversation_id':'c','status':state})
    with pytest.raises(ValueError): operator_audio.consume_transcription(Cursor(),'a','u','b','c','Обнови карточку')


def test_cancelled_job_cannot_submit_ready_transcript(monkeypatch):
    monkeypatch.setattr(operator_audio,'load_asset',lambda *args:{'kind':'transcription','conversation_id':'c','status':'ready','job_id':'j'})
    with pytest.raises(ValueError): operator_audio.consume_transcription(Cursor([{'status':'cancelled'}]),'a','u','b','c','Обнови карточку')


def test_corrected_text_is_stored_separately(monkeypatch):
    monkeypatch.setattr(operator_audio,'load_asset',lambda *args:{'kind':'transcription','conversation_id':'c','status':'ready','job_id':'j'})
    cursor=Cursor([{'status':'completed'},{'id':'a'}])
    operator_audio.consume_transcription(cursor,'a','u','b','c','Цена 1500 рублей')
    assert cursor.calls[-1][1]==('Цена 1500 рублей','a')
    assert 'corrected_text' in cursor.calls[-1][0]
    assert 'transcript=' not in cursor.calls[-1][0]


def test_stt_multiple_final_segments(monkeypatch):
    monkeypatch.setenv('OPERATOR_SPEECHKIT_API_KEY','test')
    provider=operator_speechkit.SpeechKit()
    monkeypatch.setattr(provider,'_json',lambda *a,**k:{'done':True})
    response=SimpleNamespace(raise_for_status=lambda:None,text='\n'.join(json.dumps({'result':{'final':{'alternatives':[{'text':t}]}}}) for t in ['Цена','1500 рублей']))
    monkeypatch.setattr(operator_speechkit.requests,'get',lambda *a,**k:response)
    assert provider.result('operation')=='Цена 1500 рублей'


def test_stt_pending_is_not_empty_transcript(monkeypatch):
    monkeypatch.setenv('OPERATOR_SPEECHKIT_API_KEY','test')
    provider=operator_speechkit.SpeechKit(); monkeypatch.setattr(provider,'_json',lambda *a,**k:{'done':False})
    assert provider.result('operation') is None


def test_decoder_rejects_long_and_non_audio(monkeypatch,tmp_path):
    for info in ({'format':{'duration':'121'},'streams':[{'codec_type':'audio'}]}, {'format':{'duration':'1'},'streams':[{'codec_type':'video'}]}):
        monkeypatch.setattr(operator_audio.subprocess,'run',lambda *a,**k:SimpleNamespace(stdout=json.dumps(info)))
        with pytest.raises(ValueError): operator_audio.normalize_audio(tmp_path/'input',tmp_path/'output.ogg')


def test_tts_failure_does_not_leak_credentials(monkeypatch):
    monkeypatch.setenv('OPERATOR_SPEECHKIT_API_KEY','secret')
    def fail(*args,**kwargs): raise operator_speechkit.requests.ConnectionError('secret')
    monkeypatch.setattr(operator_speechkit.requests,'post',fail)
    with pytest.raises(ValueError,match='Текст ответа сохранён'):
        operator_speechkit.SpeechKit().synthesize('Готово')


@pytest.mark.parametrize('suffix,codec', [('.webm','libopus'),('.m4a','aac'),('.ogg','libopus')])
def test_real_decoder_formats(tmp_path,suffix,codec):
    import shutil
    import subprocess
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        pytest.skip('FFmpeg/ffprobe not installed')
    source=tmp_path/('recording'+suffix)
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=440:duration=1','-c:a',codec,str(source)],check=True,capture_output=True,timeout=45)
    output=tmp_path/'normalized.ogg'
    duration=operator_audio.normalize_audio(source,output)
    assert 0.9<duration<1.2
    assert output.read_bytes().startswith(b'OggS')


def test_stt_raw_rest_events_replace_with_normalized_numbers(monkeypatch):
    monkeypatch.setenv('OPERATOR_SPEECHKIT_API_KEY','test')
    provider=operator_speechkit.SpeechKit();monkeypatch.setattr(provider,'_json',lambda *a,**k:{'done':True})
    events=[{'audioCursors':{'finalIndex':'0'},'final':{'alternatives':[{'text':'тысяча пятьсот'}]}},
            {'finalRefinement':{'finalIndex':'0','normalizedText':{'alternatives':[{'text':'1500'}]}}}]
    response=SimpleNamespace(raise_for_status=lambda:None,text='\n'.join(json.dumps(event) for event in events))
    monkeypatch.setattr(operator_speechkit.requests,'get',lambda *a,**k:response)
    assert provider.result('operation')=='1500'
