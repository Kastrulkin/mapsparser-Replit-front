"""Shared Operator journal + real PG persistence, deterministic semantic planner."""
import json
import pytest
from tests.test_operator_voice_pg import pg
from services import operator_editorial, operator_core, operator_chat_service


@pytest.fixture
def editorial(pg,monkeypatch):
    conn,c=pg
    c.execute('''CREATE TABLE contentplans(id TEXT PRIMARY KEY,business_id TEXT,title TEXT,period_start DATE,period_end DATE,
        plan_status TEXT DEFAULT 'generated',generated_plan_json JSONB DEFAULT '{}',created_at TIMESTAMPTZ DEFAULT NOW(),updated_at TIMESTAMPTZ DEFAULT NOW())''')
    c.execute('''CREATE TABLE contentplanitems(id TEXT PRIMARY KEY,plan_id TEXT,business_id TEXT,theme TEXT,goal TEXT,scheduled_for DATE,status TEXT,
        draft_text TEXT,usernews_id TEXT,content_type TEXT,source_kind TEXT,source_ref TEXT,seo_keyword TEXT,service_id TEXT,transaction_id TEXT,metadata_json JSONB DEFAULT '{}',updated_at TIMESTAMPTZ DEFAULT NOW())''')
    c.execute('''CREATE TABLE content_voice_profiles(business_id TEXT PRIMARY KEY,preferences_json JSONB DEFAULT '{}',status TEXT,created_by TEXT,version INT DEFAULT 1,updated_at TIMESTAMPTZ DEFAULT NOW())''')
    c.execute("INSERT INTO contentplans(id,business_id,title,period_start,period_end) VALUES ('p','b','План','2099-09-01','2099-09-30'),('foreign','other','Чужой','2099-09-01','2099-09-30')")
    c.execute("INSERT INTO contentplanitems(id,plan_id,business_id,theme,goal,scheduled_for,status,draft_text) VALUES ('i','p','b','Тема А','Цель','2099-09-12','edited','Предыдущий текст'),('j','p','b','Тема Б','Цель','2099-09-15','planned',NULL),('pub','p','b','Опубликовано','Цель','2099-09-10','published','Уже опубликован')")
    def authorize(cursor,user_id,business_id):
        if user_id!='u' or business_id!='b': raise PermissionError('access denied')
        return {},{}
    monkeypatch.setattr(operator_editorial,'authorize_actor',authorize)
    conn.commit()
    return conn,c


def target(c,ident='i'):
    row=next(row for row in operator_editorial._items(c,'b') if row['id']==ident)
    return {**row,'version':operator_editorial._version(row)}


@pytest.mark.parametrize('channel',['telegram','web','telegram_mini_app'])
@pytest.mark.parametrize('voice',[False,True])
def test_edit_across_six_inputs_and_repeat_is_one_change(editorial,channel,voice):
    conn,c=editorial
    message='Измени тему поста на 12 сентября на Трансфер с детскими креслами'
    row=target(c)
    calls=[]
    def planner(state):
        calls.append(state)
        return {'action':'tool_call','tool':'content.edit_item','arguments':{'item_id':'i','plan_id':'p','version':row['version'],'theme':'Трансфер с детскими креслами'}}
    payload={'request_id':'request'}
    if voice:
        from services import operator_audio
        asset=operator_audio.create_transcription(c,content=b'fixture',user_id='u',business_id='b',channel=channel,conversation_id=None,request_id='recording')
        c.execute("UPDATE operator_audio_assets SET status='ready',transcript=%s WHERE id=%s",(message,asset['asset_id']))
        c.execute("UPDATE operator_async_jobs SET status='completed' WHERE id=%s",(asset['job_id'],))
        payload.update(transcription_id=asset['asset_id'],conversation_id=asset['conversation_id'])
    def router(cursor,**args): return operator_core.route_operator_message(cursor,tool_planner=planner,**args)
    kwargs=dict(business_id='b',user_id='u',channel=channel,message=message,payload=payload,router=router)
    result=operator_chat_service.process_chat(c,**kwargs);conn.commit()
    repeated=operator_chat_service.process_chat(c,**kwargs)
    assert result['status']=='completed'
    assert result['message_id']==repeated['message_id']
    assert len(calls)==1
    updated=target(c)
    assert updated['theme']=='Трансфер с детскими креслами'
    assert updated['draft_text'] is None
    assert updated['source_kind']=='owner' and updated['source_ref']=='Трансфер с детскими креслами'
    assert updated['metadata_json']['operator_edit_history'][0]['draft_text']=='Предыдущий текст'
    assert len(updated['metadata_json']['operator_edit_history'])==1


def focus_args(c):
    return {'plan_id':'p','focus':'акцент на семейных поездках','period_start':'2099-09-01','period_end':'2099-09-30',
        'changes':[{'item_id':row['id'],'version':row['version'],'theme':'Семейная поездка '+row['id']} for row in [target(c,'i'),target(c,'j')]]}


def test_focus_preview_no_write_then_atomic_apply_and_stale_denial(editorial):
    conn,c=editorial
    args=focus_args(c)
    preview=operator_editorial.prepare_focus(c,'b','u','В этом месяце акцент на семейных поездках',args)
    assert preview['status']=='approval_required'
    assert target(c)['theme']=='Тема А'
    c.execute("UPDATE contentplanitems SET theme='Изменено другим редактором' WHERE id='j'")
    denied=operator_editorial.apply_focus(c,'b','u',preview['approval']['envelope'])
    assert denied['status']=='blocked' and target(c)['theme']=='Тема А'
    preview=operator_editorial.prepare_focus(c,'b','u','В этом месяце акцент на семейных поездках',focus_args(c))
    result=operator_editorial.apply_focus(c,'b','u',preview['approval']['envelope'])
    assert result['changed_count']==2
    assert target(c)['metadata_json']['editorial_focus']=='акцент на семейных поездках'
    assert target(c,'pub')['theme']=='Опубликовано'


def test_memory_is_attributed_preserved_and_reaches_brief(editorial):
    from services.content_plan_service import _build_content_brief_v1
    conn,c=editorial
    fact='Мы работаем с проблемной кожей 25 лет'
    story='У меня самой были непроходящие угри, я изучала тему и создала компанию'
    for kind,text in [('company_fact',fact),('founder_story',story),('tone','Пиши от первого лица, спокойно и лично')]:
        result=operator_editorial.remember(c,'b','u',text,{'kind':kind,'quote':text})
        assert result['status']=='completed'
    prompt=operator_editorial.editorial_prompt(c,'b')
    assert fact in prompt and story in prompt and 'Пиши от первого лица' in prompt
    evidence=operator_editorial.editorial_evidence(c,'b')
    brief=_build_content_brief_v1({'theme':'История основателя','content_type':'brand_story'}, {}, evidence)
    assert brief['story_evidence_source_ids']
    assert any(source['fact']==story for source in brief['sources'])
    operator_editorial.remember(c,'b','u',fact,{'kind':'company_fact','quote':fact})
    assert len(operator_editorial.read_context(c,'b','u',{})['saved_notes'])==3


def test_foreign_published_hallucinated_and_hypothetical_input_denied(editorial):
    _,c=editorial
    with pytest.raises(PermissionError): operator_editorial.read_context(c,'other','u',{})
    row=target(c,'pub')
    result=operator_editorial.edit_item(c,'b','u','Измени тему на Новая тема',{'item_id':'pub','version':row['version'],'theme':'Новая тема'})
    assert result['status']=='blocked'
    with pytest.raises(ValueError): operator_editorial.remember(c,'b','u','Работаем 2 года',{'kind':'company_fact','quote':'Работаем 25 лет'})
    result=operator_editorial.remember(c,'b','u','Например, работаем 25 лет',{'kind':'company_fact','quote':'работаем 25 лет'})
    assert result['status']=='clarification_required'


def test_followup_retains_dictated_topic(editorial):
    _,c=editorial
    first,pending=operator_core.route_operator_message(c,business_id='b',user_id='u',message='Измени тему поста на Семейная поездка',channel='telegram',tool_planner=lambda _: {'action':'clarification','message':'На какую дату?'})
    assert pending['source_message']=='Измени тему поста на Семейная поездка'
    row=target(c)
    def planner(state):
        assert 'Семейная поездка' in state['message']
        return {'action':'tool_call','tool':'content.edit_item','arguments':{'item_id':'i','version':row['version'],'theme':'Семейная поездка'}}
    result,next_pending=operator_core.route_operator_message(c,business_id='b',user_id='u',message='12 сентября',channel='telegram',pending_context=pending,tool_planner=planner)
    assert result['status']=='completed' and not next_pending


def test_focus_confirmation_journal_replay_and_expiry(editorial):
    from services.operator_conversations import create_pending_operator_action, get_or_create_operator_conversation
    conn,c=editorial
    preview=operator_editorial.prepare_focus(c,'b','u','Нужен акцент на семейных поездках',focus_args(c))
    conversation=get_or_create_operator_conversation(c,business_id='b',user_id='u',channel='telegram')
    action=create_pending_operator_action(c,conversation_id=conversation['id'],business_id='b',user_id='u',capability='content.plan.refocus',envelope=preview['approval']['envelope'],request_key='focus-1')
    first,_=operator_core.confirm_pending_operator_action(c,action_id=action['id'],business_id='b',user_id='u')
    replay,duplicate=operator_core.confirm_pending_operator_action(c,action_id=action['id'],business_id='b',user_id='u')
    assert first['status']=='completed' and duplicate
    assert replay['changed_count']==2
    assert len(target(c)['metadata_json']['operator_edit_history'])==1
    preview=operator_editorial.prepare_focus(c,'b','u','Нужен акцент на семейных поездках',focus_args(c))
    action=create_pending_operator_action(c,conversation_id=conversation['id'],business_id='b',user_id='u',capability='content.plan.refocus',envelope=preview['approval']['envelope'],request_key='focus-2')
    c.execute("UPDATE operatoractions SET expires_at=NOW()-INTERVAL '1 second' WHERE id=%s",(action['id'],))
    expired,_=operator_core.confirm_pending_operator_action(c,action_id=action['id'],business_id='b',user_id='u')
    assert expired['blocked_reasons']==['approval_expired']


def test_focus_rejects_wrong_period_and_cancel_clears_pending(editorial):
    _,c=editorial
    args=focus_args(c);args['period_end']='2099-09-13'
    assert operator_editorial.prepare_focus(c,'b','u','акцент на семейных поездках',args)['status']=='blocked'
    result,pending=operator_core.route_operator_message(c,business_id='b',user_id='u',message='отмена',channel='telegram',pending_context={'capability':'content.editorial.clarification','source_message':'Измени тему'})
    assert result['status']=='cancelled' and not pending
    assert not operator_editorial.editorial_input('Покажи пост про бетон')


def test_planner_repairs_paraphrased_quote_without_saving_invented_fact(editorial):
    _,c=editorial
    steps=[]
    def planner(state):
        steps.append(state)
        quote='Работаем 250 лет' if len(steps)==1 else 'Работаем 25 лет'
        return {'action':'tool_call','tool':'content.remember','arguments':{'kind':'company_fact','quote':quote}}
    result,_=operator_core.route_operator_message(c,business_id='b',user_id='u',channel='telegram',message='Запомни факт о компании: Работаем 25 лет',tool_planner=planner)
    assert result['status']=='completed' and len(steps)==2
    notes=operator_editorial.read_context(c,'b','u',{})['saved_notes']
    assert len(notes)==1 and notes[0]['text']=='Работаем 25 лет'


@pytest.mark.parametrize('channel',['telegram','web','telegram_mini_app'])
@pytest.mark.parametrize('voice',[False,True])
@pytest.mark.parametrize('operation',['focus','memory'])
def test_focus_and_memory_six_inputs_share_journal(editorial,channel,voice,operation):
    conn,c=editorial
    if operation=='focus':
        message='В этом месяце акцент на семейных поездках'
        decision={'action':'tool_call','tool':'content.refocus_plan','arguments':focus_args(c)}
    else:
        message='Запомни факт о компании: Работаем 25 лет'
        decision={'action':'tool_call','tool':'content.remember','arguments':{'kind':'company_fact','quote':'Работаем 25 лет'}}
    payload={'request_id':'once'}
    if voice:
        from services import operator_audio
        asset=operator_audio.create_transcription(c,content=b'fixture',user_id='u',business_id='b',channel=channel,conversation_id=None,request_id='recording')
        c.execute("UPDATE operator_audio_assets SET status='ready',transcript=%s WHERE id=%s",(message,asset['asset_id']))
        c.execute("UPDATE operator_async_jobs SET status='completed' WHERE id=%s",(asset['job_id'],))
        payload.update(transcription_id=asset['asset_id'],conversation_id=asset['conversation_id'])
    def router(cursor,**args): return operator_core.route_operator_message(cursor,tool_planner=lambda _:decision,**args)
    args=dict(business_id='b',user_id='u',message=message,channel=channel,payload=payload,router=router)
    first=operator_chat_service.process_chat(c,**args);conn.commit()
    duplicate=operator_chat_service.process_chat(c,**args)
    assert first['message_id']==duplicate['message_id']
    if operation=='focus':
        assert first['status']=='approval_required' and target(c)['theme']=='Тема А'
        result,_=operator_core.confirm_pending_operator_action(c,action_id=first['approval']['action_id'],business_id='b',user_id='u')
        assert result['changed_count']==2
    else:
        assert first['status']=='completed'
        assert len(operator_editorial.read_context(c,'b','u',{})['saved_notes'])==1


def test_month_focus_never_silently_changes_only_subset(editorial):
    _,c=editorial
    args=focus_args(c);args['changes']=args['changes'][:1]
    result=operator_editorial.prepare_focus(c,'b','u','акцент на семейных поездках',args)
    assert result['status']=='clarification_required'
    assert target(c)['theme']=='Тема А'
