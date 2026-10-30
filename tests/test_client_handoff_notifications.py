import json
from unittest.mock import patch
import pytest
from services import client_handoff_notifications as notifications


class Cursor:
    def __init__(self):
        self.state='waiting_for_staff';self.phone='test-handoff:c';self.events=[];self.sql='';self.linked=True
    def execute(self,sql,args=()):
        self.sql=sql
        if 'INSERT INTO aiagentmessages' in sql:self.events.append(json.loads(args[2]))
        if 'UPDATE aiagentmessages' in sql:self.events[-1]=json.loads(args[0])
    def fetchone(self):
        if 'FROM aiagentconversations' in self.sql:return {'client_phone':self.phone,'current_state':self.state}
        if 'FROM telegramcontrolpreferences' in self.sql:return {'telegram_id':12345,'is_active':True} if self.linked else None
        if 'FROM businesses' in self.sql:return {'name':'Расчёска'}
    def fetchall(self):return [{'content':json.dumps(event)} for event in self.events]


class DB:
    def __init__(self):self.conn=self;self.c=Cursor();self.committed=0
    def cursor(self):return self.c
    def commit(self):self.committed+=1
    def rollback(self):pass
    def close(self):pass


@pytest.fixture
def setup():
    db=DB()
    with patch.object(notifications,'DatabaseManager',return_value=db),patch.object(notifications,'require_permission'),patch.object(notifications,'send_telegram_message_result',return_value={'publish_outcome':'confirmed','message_id':77}) as send:
        yield db,send


def test_self_only_sent_receipt_and_deduplication(setup):
    db,send=setup;user={'user_id':'me'}
    result=notifications.notify_self('business','c',user)
    assert result['status']=='sent' and result['message_id']==77
    assert result['recipient_user_id']=='me'
    assert send.call_args.args[0]=='12345'
    assert send.call_args.kwargs['include_outcome'] is True
    url=send.call_args.args[2]['inline_keyboard'][0][0]['url']
    assert 'business_id=business' in url and 'conversation_id=c' in url and 'view=handoffs' in url
    assert 'test' not in url
    assert notifications.notify_self('business','c',user)['duplicate_prevented'] is True
    assert send.call_count==1


@pytest.mark.parametrize('outcome,expected',[('uncertain','unknown'),('rejected','failed'),('not_attempted','failed')])
def test_provider_outcomes_are_honest_and_uncertain_is_not_retried(setup,outcome,expected):
    db,send=setup;send.return_value={'publish_outcome':outcome,'message_id':0}
    assert notifications.notify_self('b','c',{'user_id':'me'})['status']==expected
    if expected=='unknown':
        notifications.notify_self('b','c',{'user_id':'me'});assert send.call_count==1


@pytest.mark.parametrize('condition',['real_customer','closed','unlinked','permission'])
def test_unsafe_context_never_sends(setup,condition):
    db,send=setup
    if condition=='real_customer':db.c.phone='+7000000'
    if condition=='closed':db.c.state='closing'
    if condition=='unlinked':db.c.linked=False
    if condition=='permission':
        with patch.object(notifications,'require_permission',side_effect=PermissionError):
            with pytest.raises(PermissionError):notifications.notify_self('foreign','c',{'user_id':'me'})
    else:
        with pytest.raises(ValueError):notifications.notify_self('b','c',{'user_id':'me'})
    send.assert_not_called();assert not db.c.events


def test_crash_after_claim_prevents_repeat_send(setup):
    db,send=setup;send.side_effect=TimeoutError
    with pytest.raises(TimeoutError):notifications.notify_self('b','c',{'user_id':'me'})
    assert db.c.events[-1]['status']=='sending' and db.committed==1
    result=notifications.notify_self('b','c',{'user_id':'me'})
    assert result['duplicate_prevented'];assert send.call_count==1
