import pytest
from tests.test_operator_voice_pg import pg
from tests.test_operator_editorial_pg import editorial, target
from services import operator_editorial, operator_chat_service, operator_core

@pytest.fixture
def generation(editorial,monkeypatch):
    from services import operator_social_post_generation, operator_news_generation
    calls=[]
    monkeypatch.setattr(operator_news_generation,'_load_business_context',lambda *a:{'name':'Riderra'})
    def generate(prompt,**kw):
        calls.append(prompt)
        return '{"post":"Пхукет — повод сменить привычный ритм. Спланируйте путешествие и забронируйте поездку: [ссылка для бронирования]"}'
    monkeypatch.setattr(operator_social_post_generation,'_default_social_post_generator',generate)
    return editorial,calls

@pytest.mark.parametrize('channel',['web','telegram_mini_app','telegram'])
@pytest.mark.parametrize('voice',[False,True])
def test_rewrite_six_inputs_and_idempotency(generation,channel,voice):
    (conn,c),calls=generation
    message='Замени пост на рекламный пост про Пхукет. Придумай сам'
    row=target(c)
    def planner(state):return {'action':'tool_call','tool':'content.rewrite_item','arguments':{'item_id':'i','plan_id':'p','version':row['version'],'theme':'Путешествие на Пхукет'}}
    payload={'request_id':'rewrite'}
    if voice:
        from services import operator_audio
        asset=operator_audio.create_transcription(c,content=b'fixture',user_id='u',business_id='b',channel=channel,conversation_id=None,request_id='voice')
        c.execute("UPDATE operator_audio_assets SET status='ready',transcript=%s WHERE id=%s",(message,asset['asset_id']))
        c.execute("UPDATE operator_async_jobs SET status='completed' WHERE id=%s",(asset['job_id'],))
        payload.update(transcription_id=asset['asset_id'],conversation_id=asset['conversation_id'])
    def router(cursor,**args):return operator_core.route_operator_message(cursor,tool_planner=planner,**args)
    args=dict(business_id='b',user_id='u',channel=channel,message=message,payload=payload,router=router)
    result=operator_chat_service.process_chat(c,**args);conn.commit()
    repeated=operator_chat_service.process_chat(c,**args)
    assert result['status']=='completed'
    assert repeated['message_id']==result['message_id']
    assert len(calls)==1
    updated=target(c)
    assert updated['scheduled_for']==row['scheduled_for']
    assert 'Пхукет' in updated['draft_text']
    assert updated['metadata_json']['operator_edit_history'][0]['draft_text']=='Предыдущий текст'
    assert result['selected_item']['item_id']=='i'


def test_failure_and_stale_version_leave_old_text(generation,monkeypatch):
    (conn,c),calls=generation
    from services import operator_social_post_generation
    def fail(*a,**kw):raise TimeoutError()
    monkeypatch.setattr(operator_social_post_generation,'_default_social_post_generator',fail)
    row=target(c);args={'item_id':'i','plan_id':'p','version':row['version'],'theme':'Пхукет'}
    assert operator_editorial.rewrite_item(c,'b','u','Придумай пост',args)['status']=='failed'
    assert target(c)['draft_text']=='Предыдущий текст'
    args['version']='stale'
    assert operator_editorial.rewrite_item(c,'b','u','Придумай пост',args)['status']=='blocked'


def test_restore_and_published_protection(generation):
    (conn,c),calls=generation
    row=target(c)
    result=operator_editorial.rewrite_item(c,'b','u','Придумай пост',{'item_id':'i','plan_id':'p','version':row['version'],'theme':'Пхукет'})
    assert operator_editorial.restore_item(c,'b','u','Верни старый текст',result['selected_item'])['status']=='completed'
    assert target(c)['draft_text']=='Предыдущий текст'
    row=target(c,'pub')
    assert operator_editorial.rewrite_item(c,'b','u','Перепиши',{'item_id':'pub','plan_id':'p','version':row['version']})['status']=='blocked'


def test_short_followup_uses_selected_post(generation):
    (conn,c),calls=generation
    row=target(c)
    first=operator_editorial.rewrite_item(c,'b','u','Придумай рекламный пост про Пхукет',{'item_id':'i','plan_id':'p','version':row['version'],'theme':'Пхукет'})
    pending={'capability':'content.editorial.selected','source_message':'Придумай рекламный пост про Пхукет','selected_item':first['selected_item']}
    def planner(state):
        assert 'Пхукет' in state['message'] and 'Короче' in state['message']
        return {'action':'tool_call','tool':'content.rewrite_item','arguments':{**first['selected_item'],'theme':'Пхукет'}}
    result,context=operator_core.route_operator_message(c,business_id='b',user_id='u',message='Короче',channel='telegram',pending_context=pending,tool_planner=planner)
    assert result['status']=='completed' and context['selected_item']['item_id']=='i'
    assert len(calls)==2


def test_original_edit_tool_also_handles_creative_request(generation):
    (conn,c),calls=generation
    row=target(c)
    result=operator_editorial.edit_item(c,'b','u','У меня нет точной формулировки придумай пост про Пхукет',{'item_id':'i','plan_id':'p','version':row['version'],'theme':'Отпуск на Пхукете'})
    assert result['status']=='completed' and len(calls)==1


def test_unverified_link_is_not_saved(generation,monkeypatch):
    (conn,c),calls=generation
    from services import operator_social_post_generation
    monkeypatch.setattr(operator_social_post_generation,'_default_social_post_generator',lambda *a,**kw:'{"post":"Забронируйте прекрасную поездку на Пхукет: https://invented.invalid/booking"}')
    row=target(c)
    assert operator_editorial.rewrite_item(c,'b','u','Придумай пост',{'item_id':'i','plan_id':'p','version':row['version']})['status']=='failed'
    assert target(c)['draft_text']=='Предыдущий текст'

@pytest.mark.parametrize('generated',['{"post":"оборванный текст без закрытия', '{"error":"Провайдер не смог подготовить текст поста"}'])
def test_invalid_generation_never_replaces_draft(generation,monkeypatch,generated):
    (conn,c),calls=generation
    from services import operator_social_post_generation
    monkeypatch.setattr(operator_social_post_generation,'_default_social_post_generator',lambda *a,**kw:generated)
    row=target(c)
    result=operator_editorial.rewrite_item(c,'b','u','Придумай пост',{'item_id':'i','plan_id':'p','version':row['version']})
    assert result['status']=='failed' and target(c)['draft_text']=='Предыдущий текст'
