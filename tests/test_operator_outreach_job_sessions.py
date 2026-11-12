"""Restricted sessions cannot recover real outreach data through job endpoints."""
from unittest.mock import Mock

import pytest
from flask import Flask

from api import operator_api
from services import business_permissions, operator_async_jobs

SCOPE={'kind':'business','id':'business-a','business_ids':['business-a']}
RESTRICTIONS=[{'session_kind':'demo'},{'impersonating':True},{'impersonated_by':'admin'}]


class Cursor:
    def __init__(self,kind='outreach_inbox_sync'):
        self.job={'id':'job','user_id':'owner','business_id':'business-a','kind':kind,
                  'status':'completed','result_json':{'private':'actual reply'},'stage':'ready'}
        self.rows=[]
    def execute(self,query,params=()):
        if 'FROM operator_async_jobs' in query:
            self.rows=[self.job]
        else:
            raise AssertionError('Unexpected query '+query)
    def fetchone(self):
        return self.rows[0] if self.rows else None
    def fetchall(self):
        return self.rows


@pytest.fixture
def current_permissions(monkeypatch):
    load=Mock(return_value={'id':'owner','user_id':'owner','is_active':True,'is_superadmin':False})
    monkeypatch.setattr(business_permissions,'load_actor',load)
    monkeypatch.setattr('core.auth_helpers.verify_business_access',lambda *args:(True,'owner'))
    monkeypatch.setattr('core.auth_helpers.verify_business_write_access',lambda *args:(True,'owner'))
    return load


@pytest.mark.parametrize('restriction',RESTRICTIONS)
@pytest.mark.parametrize('kind',['outreach_inbox_sync','outreach_continue'])
@pytest.mark.parametrize('scope',[SCOPE,{'kind':'platform','id':None,'business_ids':[]}])
def test_direct_job_load_and_list_reject_restricted_session(current_permissions,restriction,kind,scope):
    cursor=Cursor(kind)
    assert operator_async_jobs.load_operator_async_job(cursor,job_id='job',user_id='owner',scope=scope,actor_context=restriction) is None
    assert operator_async_jobs.list_operator_async_jobs(cursor,user_id='owner',scope=scope,actor_context=restriction)['items']==[]
    current_permissions.assert_not_called()


def test_standard_session_keeps_current_db_access_and_own_job(current_permissions):
    cursor=Cursor()
    result=operator_async_jobs.load_operator_async_job(cursor,job_id='job',user_id='owner',scope=SCOPE,actor_context={'user_id':'owner'})
    assert result['result']=={'private':'actual reply'}
    assert operator_async_jobs.list_operator_async_jobs(cursor,user_id='owner',scope=SCOPE,actor_context={'user_id':'owner'})['items'][0]['id']=='job'
    assert current_permissions.call_count==2


def test_unrelated_job_behavior_is_unchanged_for_restricted_session(current_permissions):
    cursor=Cursor('content_plan_generate')
    assert operator_async_jobs.load_operator_async_job(cursor,job_id='job',user_id='owner',scope=SCOPE,actor_context={'session_kind':'demo'})['id']=='job'
    current_permissions.assert_not_called()


@pytest.fixture
def api(monkeypatch,current_permissions):
    cursor=Cursor();database=Mock();database.conn.cursor.return_value=cursor
    actor={'user_id':'owner'}
    monkeypatch.setattr(operator_api,'require_auth_from_request',lambda:actor)
    monkeypatch.setattr(operator_api,'DatabaseManager',lambda:database)
    # Intentionally reproduce resolution dropping session flags. They must
    # separately reach the real job service through actor_context.
    monkeypatch.setattr(operator_api,'_resolve_mobile_scope',lambda *args:SCOPE)
    monkeypatch.setattr(operator_api,'load_mobile_job',lambda *args,**kwargs:None)
    app=Flask(__name__);app.register_blueprint(operator_api.operator_bp,url_prefix='/api/operator')
    return app.test_client(),actor,cursor


@pytest.mark.parametrize('restriction',RESTRICTIONS)
@pytest.mark.parametrize('path',['/mobile/jobs','/mobile/jobs/job','/mobile/jobs/job/retry','/mobile/jobs/job/cancel'])
def test_mobile_job_endpoints_preserve_session_restrictions(api,restriction,path):
    client,actor,cursor=api;actor.update(restriction)
    response=(client.post if path.endswith(('/retry','/cancel')) else client.get)('/api/operator'+path)
    assert response.status_code==(200 if path=='/mobile/jobs' else 404)
    if path=='/mobile/jobs':assert response.json['items']==[]
    assert 'actual reply' not in response.get_data(as_text=True)


def test_mobile_normal_actor_can_poll_and_list_own_outreach_job(api):
    client,*_=api
    response=client.get('/api/operator/mobile/jobs/job')
    assert response.status_code==200 and response.json['job']['result']['private']=='actual reply'
    response=client.get('/api/operator/mobile/jobs')
    assert response.status_code==200 and response.json['items'][0]['id']=='job'
