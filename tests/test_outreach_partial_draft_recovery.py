import ast
from copy import deepcopy
from pathlib import Path
import pytest
from services.outreach_continuation import remaining_qualified_drafts,qualified_contact_ids
from services.agent_outreach_continuation import resume_completed_preparation


def state():
    return {'phase':'prepare','llm_calls':4,'draft_attempts':0,'qualifications':{'ready':{'status':'qualified'}},
            'verified_contact_workstream_ids':['ready'],'campaign_results':{},'agent_run_id':'run','agent_step_id':'step'}


def test_check_limit_does_not_prevent_drafting_already_qualified_contact():
    tree=ast.parse(Path('src/services/outreach_continuation.py').read_text())
    nodes=[n for n in ast.walk(tree) if isinstance(n,ast.If)]
    check=next(n.test for n in nodes if ast.unparse(n.test).startswith('pending and ') and 'goal_reached' in ast.unparse(n.test))
    draft=next(n.test for n in nodes if ast.unparse(n.test).startswith("config.get('mode') != 'find_only' and any("))
    cfg={'mode':'prepare_only','target_count':2,'max_qualification_calls':4,'max_draft_attempts':2}
    env={'pending':[{'id':'unexamined'}],'goal_reached':False,'config':cfg,'state':state(),
         'entries':[{'id':'ready'}],'qualified_contact_ids':qualified_contact_ids}
    evaluate=lambda expression:eval(compile(ast.Expression(expression),'<production-condition>','eval'),env)
    assert not evaluate(check)
    assert evaluate(draft)
    before=deepcopy(env['state'])
    assert remaining_qualified_drafts(cfg,env['state'])==['ready']
    assert env['state']==before
    env['state']['llm_calls']=3
    assert evaluate(check)


def test_no_recovery_for_unverified_contacts_sent_mode_or_exhausted_drafts():
    cfg={'mode':'prepare_only','max_draft_attempts':2,'target_count':2};s=state()
    assert remaining_qualified_drafts({**cfg,'mode':'auto_send'},s)==[]
    assert remaining_qualified_drafts(cfg,{**s,'draft_attempts':2})==[]
    assert remaining_qualified_drafts(cfg,{**s,'verified_contact_workstream_ids':[]})==[]
    assert remaining_qualified_drafts(cfg,{**s,'campaign_results':{'ready':{'status':'draft'}}})==[]


class Cursor:
    def __init__(self,parent):self.parent=parent;self.statements=[]
    def execute(self,sql,args):self.statements.append((sql,args))
    def fetchone(self):return self.parent


def row():return {'id':'job','user_id':'owner','business_id':'business','payload_json':{'mode':'prepare_only'},'result_json':state()}


def test_recovery_reopens_same_parent_and_step_only_after_version_and_owner_checks():
    cursor=Cursor({'id':'run'})
    resume_completed_preparation(cursor,row=row(),user_id='owner')
    guard=cursor.statements[0][0]
    assert "b.status='active'" in guard and "r.status='completed'" in guard
    assert 'active_version_id' in guard and "s.output_json->>'job_id'" in guard
    assert cursor.statements[1][1]==('step','run')
    assert cursor.statements[2][1]==('run',)
    assert not any('INSERT' in sql for sql,args in cursor.statements)


def test_changed_or_paused_parent_cannot_reopen():
    cursor=Cursor(None)
    with pytest.raises(ValueError,match='parent_changed_or_paused'):resume_completed_preparation(cursor,row=row(),user_id='owner')
    assert len(cursor.statements)==1
    cursor=Cursor({'id':'run'})
    with pytest.raises(ValueError,match='owner_required'):resume_completed_preparation(cursor,row=row(),user_id='other')
    assert cursor.statements==[]
