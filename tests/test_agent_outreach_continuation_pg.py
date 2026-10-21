from copy import deepcopy
from psycopg2.extras import Json
import pytest
from tests.test_outreach_continuation_pg import db
from services import agent_outreach_continuation as bridge, outreach_continuation as continuation


@pytest.fixture
def workflow(db,monkeypatch):
    conn,cur=db
    cur.execute('CREATE TABLE agent_blueprints(id TEXT,business_id TEXT,status TEXT,metadata_json JSONB)')
    cur.execute('CREATE TABLE agent_runs(id TEXT,blueprint_id TEXT,blueprint_version_id TEXT,business_id TEXT,status TEXT,updated_at TIMESTAMPTZ,lease_token TEXT,heartbeat_at TIMESTAMPTZ,next_attempt_at TIMESTAMPTZ,completed_at TIMESTAMPTZ,error_text TEXT,output_json JSONB)')
    cur.execute('CREATE TABLE agent_run_steps(id TEXT,run_id TEXT,status TEXT,output_json JSONB,completed_at TIMESTAMPTZ)')
    cur.execute("INSERT INTO agent_blueprints VALUES('bp','b','active','{\"active_version_id\":\"v1\"}')")
    cur.execute("INSERT INTO agent_runs VALUES('run','bp','v1','b','running',NOW(),NULL,NULL,NULL,NULL,NULL,'{}')")
    cur.execute("INSERT INTO agent_run_steps VALUES('step','run','running','{}',NULL)")
    config=continuation.normalize_config({'audience':'Agencies','mode':'find_only','target_count':100,'queries':[{'query':'travel agency','city':'Delhi'}]})
    version={'id':'v1','runtime_config_json':{'outreach_config':config}}
    run={'id':'run','blueprint_id':'bp','blueprint_version_id':'v1','business_id':'b','created_by_user_id':'u'}
    monkeypatch.setattr(continuation,'_require_current_actor',lambda *args:None)
    return conn,cur,run,version


def test_workflow_uses_existing_job_and_resumes_same_run(workflow):
    conn,cur,run,version=workflow
    job_id=bridge.bind(cur,run=run,version=version,step_id='step')
    conn.commit()
    cur.execute('SELECT * FROM operator_async_jobs WHERE id=%s',(job_id,))
    row=dict(cur.fetchone())
    assert row['kind']=='outreach_continue' and row['result_json']['started']
    assert row['payload_json']['target_count']==100
    assert bridge.parent_current(cur,row)
    cur.execute("UPDATE agent_blueprints SET status='paused'")
    assert not bridge.parent_current(cur,row)
    cur.execute("UPDATE agent_blueprints SET status='active'")
    cur.execute("UPDATE operator_async_jobs SET status='running',lease_token='lease' WHERE id=%s",(job_id,))
    row.update(status='running',lease_token='lease')
    assert continuation._save(cur,row,row['result_json'],status='completed',stage='Done')
    cur.execute("SELECT status,output_json FROM agent_run_steps WHERE id='step'")
    step=cur.fetchone()
    assert step['status']=='completed' and step['output_json']['job_id']==job_id
    cur.execute("SELECT status FROM agent_runs WHERE id='run'")
    assert cur.fetchone()['status']=='queued'
    # Replayed completion never advances the workflow twice.
    assert not continuation._save(cur,row,row['result_json'],status='completed',stage='Done')
    cur.execute('SELECT COUNT(*) n FROM operator_async_jobs')
    assert cur.fetchone()['n']==1


@pytest.mark.parametrize('change',['pause','version','unreviewed_config','step'])
def test_binding_requires_exact_active_workflow(workflow,change):
    _,cur,run,version=workflow
    if change=='pause':cur.execute("UPDATE agent_blueprints SET status='paused'")
    elif change=='version':run['blueprint_version_id']='v2'
    elif change=='unreviewed_config':version['runtime_config_json']['outreach_config'].pop('batch_size')
    else:cur.execute("UPDATE agent_run_steps SET status='completed'")
    with pytest.raises(ValueError):bridge.bind(cur,run=run,version=version,step_id='step')
    cur.execute('SELECT COUNT(*) n FROM operator_async_jobs')
    assert cur.fetchone()['n']==0


def test_stop_releases_parent_instead_of_orphan_wait(workflow):
    _,cur,run,version=workflow
    job=bridge.bind(cur,run=run,version=version,step_id='step')
    continuation.control_task(cur,task_id=job,business_id='b',user_id='u',action='stop',revision=continuation.config_hash(version['runtime_config_json']['outreach_config']))
    cur.execute("SELECT status,output_json FROM agent_runs WHERE id='run'")
    parent=cur.fetchone()
    assert parent['status']=='rejected' and parent['output_json']['run_billing']['status']=='not_required'
    cur.execute("SELECT COUNT(*) n FROM agent_runs WHERE status='waiting_provider'")
    assert cur.fetchone()['n']==0


def test_version_replacement_terminates_old_run_once(workflow):
    _,cur,run,version=workflow
    job=bridge.bind(cur,run=run,version=version,step_id='step')
    cur.execute('SELECT * FROM operator_async_jobs WHERE id=%s',(job,))
    row=dict(cur.fetchone())
    cur.execute("UPDATE agent_blueprints SET metadata_json='{\"active_version_id\":\"v2\"}'")
    assert bridge.parent_state(cur,row)=='changed'
    cur.execute("UPDATE operator_async_jobs SET status='running',lease_token='lease' WHERE id=%s",(job,))
    row.update(status='running',lease_token='lease')
    assert continuation._save(cur,row,{**row['result_json'],'blocker':'parent_version_changed'},status='cancelled',stage='superseded')
    cur.execute("SELECT status FROM agent_runs WHERE id='run'")
    assert cur.fetchone()['status']=='superseded'
    assert not continuation._save(cur,row,row['result_json'],status='completed',stage='old result')


def test_version_change_reconciles_nonclaimable_child(workflow):
    _,cur,run,version=workflow
    job=bridge.bind(cur,run=run,version=version,step_id='step')
    cur.execute("UPDATE operator_async_jobs SET status='waiting_for_review' WHERE id=%s",(job,))
    cur.execute("UPDATE agent_blueprints SET metadata_json='{\"active_version_id\":\"v2\"}'")
    assert bridge.supersede_previous_version(cur,'bp','v2')==1
    assert bridge.supersede_previous_version(cur,'bp','v2')==0
    cur.execute("SELECT status FROM agent_runs WHERE id='run'")
    assert cur.fetchone()['status']=='superseded'
    cur.execute('SELECT status FROM operator_async_jobs WHERE id=%s',(job,))
    assert cur.fetchone()['status']=='cancelled'


def test_common_api_activation_reconciles_previous_child(workflow,monkeypatch):
    from api import agent_blueprints_api as api
    _,cur,run,version=workflow
    job=bridge.bind(cur,run=run,version=version,step_id='step')
    cur.execute("UPDATE operator_async_jobs SET status='waiting_for_review' WHERE id=%s",(job,))
    cur.execute('ALTER TABLE agent_blueprints ADD COLUMN updated_at TIMESTAMPTZ')
    def load(cursor,key):
        cursor.execute('SELECT * FROM agent_blueprints WHERE id=%s',(key,))
        return dict(cursor.fetchone())
    def save(cursor,key,metadata):
        cursor.execute('UPDATE agent_blueprints SET metadata_json=%s WHERE id=%s',(Json(metadata),key))
    monkeypatch.setattr(api,'_load_blueprint',load)
    monkeypatch.setattr(api,'_save_blueprint_metadata',save)
    event=api._remember_active_version(cur,load(cur,'bp'),{'id':'v2','version_number':2},{'user_id':'u'},'activated')
    assert event['previous_active_version_id']=='v1'
    cur.execute('SELECT status FROM operator_async_jobs WHERE id=%s',(job,))
    assert cur.fetchone()['status']=='cancelled'
    cur.execute("SELECT status FROM agent_runs WHERE id='run'")
    assert cur.fetchone()['status']=='superseded'


def test_stop_automation_cancels_native_child_and_preserves_result(workflow, monkeypatch):
    from services import operator_agent_management as manage
    conn,cur,run,version=workflow
    job_id=bridge.bind(cur,run=run,version=version,step_id='step')
    cur.execute('CREATE TABLE agent_approvals(id TEXT,run_id TEXT,status TEXT,decided_by_user_id TEXT,decision_reason TEXT,decided_at TIMESTAMPTZ)')
    result=manage._stop_runs(cur,blueprint_id='bp',business_id='b',user_id='u')
    assert result=={'status':'completed','cancelled_runs':1}
    cur.execute('SELECT status,result_json FROM operator_async_jobs WHERE id=%s',(job_id,))
    job=cur.fetchone()
    assert job['status']=='cancelled' and job['result_json']['agent_run_id']=='run'
    cur.execute("SELECT status FROM agent_runs WHERE id='run'")
    assert cur.fetchone()['status']=='rejected'
    # Repeated stop cannot restart or erase completed work.
    assert manage._stop_runs(cur,blueprint_id='bp',business_id='b',user_id='u')['cancelled_runs']==0


def test_stop_requires_reconciliation_for_unfinished_generic_provider(workflow):
    from services import operator_agent_management as manage
    _,cur,_,_=workflow
    result=manage._stop_runs(cur,blueprint_id='bp',business_id='b',user_id='u')
    assert result['blocked_reasons']==['running_operation_needs_reconciliation']
    cur.execute("SELECT status FROM agent_runs WHERE id='run'")
    assert cur.fetchone()['status']=='running'


def test_operator_stop_pins_version_and_records_cutoff_with_pause(workflow,monkeypatch):
    from services import operator_agent_management as manage
    _,cur,run,version=workflow
    bridge.bind(cur,run=run,version=version,step_id='step')
    cur.execute('ALTER TABLE agent_blueprints ADD COLUMN updated_at TIMESTAMPTZ')
    cur.execute('CREATE TABLE agent_approvals(id TEXT,run_id TEXT,status TEXT,decided_by_user_id TEXT,decision_reason TEXT,decided_at TIMESTAMPTZ)')
    monkeypatch.setattr(manage,'_authorized_actor',lambda *args,**kw:{'user_id':'u'})
    envelope={'business_id':'b','blueprint_id':'bp','operation':'stop','expected_status':'active','version_id':'old'}
    assert manage.execute_lifecycle(cur,business_id='b',user_id='u',envelope=envelope)['blocked_reasons']==['active_version_changed']
    envelope['version_id']='v1'
    from datetime import datetime, timezone
    class SkewedApplicationClock:
        @staticmethod
        def now(*args):
            return datetime(2000,1,1,tzinfo=timezone.utc)
    monkeypatch.setattr(manage,'datetime',SkewedApplicationClock,raising=False)
    cur.execute('SELECT clock_timestamp() AS t')
    before=cur.fetchone()['t']
    result=manage.execute_lifecycle(cur,business_id='b',user_id='u',envelope=envelope)
    assert result['status']=='completed' and result['cancelled_runs']==1
    cur.execute("SELECT status,metadata_json FROM agent_blueprints WHERE id='bp'")
    stopped=cur.fetchone()
    assert stopped['status']=='paused'
    assert datetime.fromisoformat(stopped['metadata_json']['outreach_stopped_at']) >= before
    assert stopped['metadata_json']['active_version_id']=='v1'
    assert stopped['metadata_json']['version_events'][-1]['action']=='stopped'


@pytest.mark.parametrize('link_change',['historical','wrong_step','wrong_job','terminal_child'])
def test_stop_does_not_confuse_historical_or_mislinked_child_with_current_provider(workflow,link_change):
    from services import operator_agent_management as manage
    _,cur,run,version=workflow
    job=bridge.bind(cur,run=run,version=version,step_id='step')
    if link_change=='historical':
        cur.execute("UPDATE operator_async_jobs SET status='completed' WHERE id=%s",(job,))
        cur.execute("UPDATE agent_run_steps SET status='completed' WHERE id='step'")
        cur.execute("INSERT INTO agent_run_steps VALUES('other','run','waiting_provider','{}',NULL)")
    elif link_change=='wrong_step':
        cur.execute("UPDATE operator_async_jobs SET result_json=result_json || '{\"agent_step_id\":\"other\"}'::jsonb WHERE id=%s",(job,))
    elif link_change=='wrong_job':
        cur.execute("UPDATE agent_run_steps SET output_json='{\"job_id\":\"other\"}'")
    else:
        cur.execute("UPDATE operator_async_jobs SET status='failed' WHERE id=%s",(job,))
    result=manage._stop_runs(cur,blueprint_id='bp',business_id='b',user_id='u')
    assert result['blocked_reasons']==['running_operation_needs_reconciliation']
    cur.execute("SELECT status FROM agent_runs WHERE id='run'")
    assert cur.fetchone()['status']=='waiting_provider'
