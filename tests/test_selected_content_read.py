import uuid
import pytest
from services import operator_editorial, operator_core

ITEM=str(uuid.uuid4());PLAN=str(uuid.uuid4())
@pytest.mark.parametrize('message',['Покажи пост','Покажи полный текст этого поста','Прочитай публикацию','Открой выбранный пост'])
def test_literal_selected_read_intents(message):
    assert operator_editorial.selected_read_input(message)

@pytest.mark.parametrize('message',['Перепиши пост','Напиши пост','Покажи пост и опубликуй','Покажи письма'])
def test_read_does_not_swallow_writes_or_other_work(message):
    assert not operator_editorial.selected_read_input(message)

@pytest.fixture
def access(monkeypatch):
    import subscription_manager
    monkeypatch.setattr(operator_editorial,'authorize_actor',lambda *a,**k:({},{}))
    monkeypatch.setattr(subscription_manager,'capability_access_payload',lambda *a,**k:{'allowed':True})

def test_saved_text_is_returned_exactly_and_refreshes_selected_version(access,monkeypatch):
    seen=[]
    row={'id':ITEM,'plan_id':PLAN,'theme':'Тестовый пост','draft_text':'Первый абзац.\n\nВторой абзац.','scheduled_for':'2026-10-21'}
    def items(cursor,business,**kwargs):seen.append((business,kwargs));return [row]
    monkeypatch.setattr(operator_editorial,'_items',items)
    result=operator_editorial.read_selected_item(None,'qa-business','qa-user',{'item_id':ITEM,'version':'old'})
    assert row['draft_text'] in result['chat_response'];assert seen==[('qa-business',{'item_id':ITEM})]
    assert result['selected_item']['item_id']==ITEM
    assert not result['external_calls_performed'];assert not result['external_writes_performed'];assert not result['credit_charged']

@pytest.mark.parametrize('rows',[[],[{'id':str(uuid.uuid4())}], [{'id':ITEM,'plan_status':'archived'}]])
def test_missing_foreign_and_archived_posts_are_not_returned(access,monkeypatch,rows):
    monkeypatch.setattr(operator_editorial,'_items',lambda *a,**k:rows)
    with pytest.raises((PermissionError,ValueError)):
        operator_editorial.read_selected_item(None,'qa-business','qa-user',{'item_id':ITEM})

def test_denied_tier_never_reads_private_post(access,monkeypatch):
    import subscription_manager
    monkeypatch.setattr(subscription_manager,'capability_access_payload',lambda *a,**k:{'allowed':False})
    monkeypatch.setattr(operator_editorial,'_items',lambda *a,**k:pytest.fail('Must not read before permission'))
    with pytest.raises(PermissionError):operator_editorial.read_selected_item(None,'qa-business','qa-user',{'item_id':ITEM})


@pytest.mark.parametrize('channel',['telegram','max_bot','telegram_mini_app','max_mini_app'])
def test_selected_read_bypasses_ai_and_keeps_selection(monkeypatch,channel):
    class ReadCursor:
        description = []
        def execute(self, *args, **kwargs): pass
        def fetchone(self): return None
        def fetchall(self): return []
    monkeypatch.setattr(operator_core,'run_paid_operator_tool_loop',lambda *a,**k:pytest.fail('Saved text must not call AI'))
    monkeypatch.setattr(operator_editorial,'read_selected_item',lambda *a,**k:{'status':'completed','chat_response':'Точный сохранённый текст','selected_item':{'item_id':ITEM,'plan_id':PLAN,'version':'current'},'external_calls_performed':False,'external_writes_performed':False})
    result,pending=operator_core.route_operator_message(ReadCursor(),business_id='qa-business',user_id='qa-user',message='Покажи пост',channel=channel,
        pending_context={'capability':'content.editorial.selected','selected_item':{'item_id':ITEM,'plan_id':PLAN,'version':'old'}})
    assert result['chat_response']=='Точный сохранённый текст'
    assert pending['selected_item']['version']=='current'
    assert not result['external_calls_performed']
