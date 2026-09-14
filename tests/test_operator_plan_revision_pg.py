import pytest
from tests.test_operator_voice_pg import pg
from tests.test_operator_editorial_pg import editorial, target
from services import operator_plan_revision, business_input_settings, content_plan_direction, operator_editorial


@pytest.fixture
def revision(editorial,monkeypatch):
    conn,c=editorial
    monkeypatch.setenv('OPERATOR_PLAN_REVISION_ASYNC_BUSINESS_IDS','b')
    c.execute('ALTER TABLE businesses ADD COLUMN description TEXT, ADD COLUMN name TEXT')
    c.execute('CREATE TABLE userservices(id TEXT,name TEXT,business_id TEXT,is_active BOOLEAN)')
    monkeypatch.setattr(business_input_settings,'resolve',lambda *args:{'timezone':'Europe/Tallinn'})
    def generate(skeleton,*args,**kwargs):
        for i,item in enumerate(skeleton['items']):item.update(theme=['Таиланд 1','Таиланд 2','Китай','Танзания'][i],goal='Советы путешественнику')
        skeleton['meta']['editorial_summary']='Таиланд: 2; Китай: 1; Танзания: 1'
        return skeleton
    monkeypatch.setattr(content_plan_direction,'apply_direction',generate)
    return conn,c


def test_four_weekly_preview_apply_and_repeat(revision):
    _,c=revision
    preview=operator_plan_revision.prepare(c,'b','u','Переработай план',{'plan_id':'p','post_count':4,'interval_days':7})
    assert target(c)['theme']=='Тема А'
    env=preview['approval']['envelope']
    assert [item['scheduled_for'] for item in env['changes']]==['2099-09-01','2099-09-08','2099-09-15','2099-09-22']
    assert operator_plan_revision.apply(c,'b','u',env)['status']=='completed'
    assert operator_plan_revision.apply(c,'b','u',env)['status']=='blocked'
    assert target(c,'pub')['status']=='published'
    assert target(c)['metadata_json']['operator_edit_history'][0]['scheduled_for']=='2099-09-12'
    c.execute("SELECT generated_plan_json FROM contentplans WHERE id='p'")
    assert len(c.fetchone()['generated_plan_json']['items'])==5


def test_stale_plan_and_period_extension(revision):
    _,c=revision
    with pytest.raises(ValueError,match='Продлить'):operator_plan_revision.prepare(c,'b','u','План',{'plan_id':'p','post_count':4,'interval_days':14})
    preview=operator_plan_revision.prepare(c,'b','u','Продли период',{'plan_id':'p','post_count':4,'interval_days':14,'extend_period':True})
    assert preview['approval']['envelope']['period_end']=='2099-10-13'
    c.execute("UPDATE contentplanitems SET status='published' WHERE id='i'")
    assert operator_plan_revision.apply(c,'b','u',preview['approval']['envelope'])['status']=='blocked'


@pytest.mark.parametrize('channel',['web','telegram_mini_app','telegram'])
def test_background_preview_survives_replay_without_changing_plan(revision,monkeypatch,channel):
    from services.operator_conversations import get_or_create_operator_conversation
    from services.operator_conversations import _row
    import database_manager
    conn,c=revision
    get_or_create_operator_conversation(c,business_id='b',user_id='u',channel=channel)
    monkeypatch.setenv('OPERATOR_PLAN_REVISION_ASYNC_BUSINESS_IDS','b')
    queued=operator_plan_revision.prepare(c,'b','u','Переработай план',{'plan_id':'p','post_count':4,'interval_days':7,'_channel':channel},queue=True)
    conn.commit()
    c.execute('SELECT * FROM operator_async_jobs WHERE id=%s',(queued['async_job_id'],));claimed=_row(c,c.fetchone())
    class Database:
        def __init__(self):self.conn=conn
        def close(self):pass
    monkeypatch.setattr(database_manager,'DatabaseManager',Database)
    result=operator_plan_revision.process_job(claimed)
    repeated=operator_plan_revision.process_job(claimed)
    assert result['approval']['action_id']==repeated['approval']['action_id']
    assert target(c)['theme']=='Тема А'
    c.execute("SELECT COUNT(*) n FROM operatormessages WHERE role='operator'");assert c.fetchone()['n']==1


def test_explicit_weekly_counts_do_not_ask_for_existing_information():
    assert operator_plan_revision.explicit_schedule('Измени план: один пост в неделю, два про Таиланд, один про Китай, один про Танзанию')=={'post_count':4,'interval_days':7,'extend_period':False}
    assert operator_plan_revision.explicit_schedule('Измени план: 1 пост в неделю, 2 про Таиланд, остальные произвольные') is None


def test_control_command_uses_code_for_schedule_selection(revision,monkeypatch):
    from services import operator_core
    from services.operator_tool_loop import run_operator_tool_loop
    _,c=revision
    seen=[]
    monkeypatch.setenv('OPERATOR_PLAN_REVISION_ASYNC_BUSINESS_IDS','b')
    def paid(cursor,**kwargs):
        seen.append(kwargs['planner']({}))
        return run_operator_tool_loop(**kwargs)
    original_prepare=operator_plan_revision.prepare
    monkeypatch.setattr(operator_plan_revision,'prepare',lambda cursor,business,user,message,args,**kwargs:original_prepare(cursor,business,user,message,args))
    monkeypatch.setattr(operator_core,'run_paid_operator_tool_loop',paid)
    result,_=operator_core.route_operator_message(c,business_id='b',user_id='u',channel='web',message='Измени последний контент план: один пост в неделю, два про Таиланд, один про Китай, один про Танзанию')
    assert result['status']=='approval_required'
    assert seen[0]['tool']=='content.rebuild_plan'
    assert len(result['approval']['envelope']['changes'])==4
