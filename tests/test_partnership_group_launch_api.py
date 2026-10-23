from flask import Flask
import pytest
from api import partnership_leads_api as api
from services import partnership_group_launch as launch


@pytest.fixture
def route(monkeypatch):
    events=[]
    class DB:
        def __init__(self):self.conn=self
        def cursor(self):return object()
        def close(self):events.append('close')
        def commit(self):events.append('commit')
        def rollback(self):events.append('rollback')
    monkeypatch.setattr(api,'_require_auth',lambda:({'user_id':'owner'},None))
    monkeypatch.setattr(api,'DatabaseManager',DB)
    app=Flask(__name__);app.register_blueprint(api.partnership_leads_bp)
    return app.test_client(),events


def test_preview_never_commits_or_calls_confirmation(monkeypatch,route):
    browser,events=route
    monkeypatch.setattr(launch,'build_preview',lambda *args,**kwargs:{'digest':'d','messages_sent':0})
    monkeypatch.setattr(launch,'confirm_launch',lambda *args,**kwargs:pytest.fail('Preview cannot approve'))
    response=browser.post('/api/partnership/collections/group/launch',json={'action':'preview','business_id':'business'})
    assert response.status_code==200;assert response.json['preview']['messages_sent']==0
    assert events==['rollback','close']


def test_confirm_failure_rolls_back_whole_group(monkeypatch,route):
    browser,events=route
    def fail(*args,**kwargs):raise ValueError('Изменился отправитель')
    monkeypatch.setattr(launch,'confirm_launch',fail)
    response=browser.post('/api/partnership/collections/group/launch',json={'action':'confirm','business_id':'business','reviewed':True,'confirmed':True})
    assert response.status_code==409;assert events==['rollback','close']


def test_confirm_commits_only_after_native_group_returns(monkeypatch,route):
    browser,events=route
    def complete(*args,**kwargs):events.append('native approvals');return {'batch_id':'batch','messages_sent':0}
    monkeypatch.setattr(launch,'confirm_launch',complete)
    response=browser.post('/api/partnership/collections/group/launch',json={'action':'confirm','business_id':'business','reviewed':True,'confirmed':True})
    assert response.status_code==200;assert events==['native approvals','commit','close']


def test_permission_denial_has_no_queue_commit(monkeypatch,route):
    browser,events=route
    def deny(*args,**kwargs):raise PermissionError()
    monkeypatch.setattr(launch,'build_preview',deny)
    assert browser.post('/api/partnership/collections/group/launch',json={'action':'preview','business_id':'foreign'}).status_code==403
    assert events==['rollback','close']


@pytest.mark.parametrize('payload',[{},[],{'action':'send','business_id':'business'},{'action':'preview','business_id':[]}])
def test_invalid_actions_do_not_open_database(route,payload):
    browser,events=route
    assert browser.post('/api/partnership/collections/group/launch',json=payload).status_code==400
    assert events==[]
