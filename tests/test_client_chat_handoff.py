import json
import pytest
from services import client_chat_handoff as handoff

class Cursor:
    def __init__(self,state='greeting'): self.state=state;self.actor=None;self.events=[];self.paused=0
    def execute(self,sql,args=None):
        self.sql=sql;self.args=args
        if 'UPDATE aiagentconversations' in sql:
            self.state='waiting_for_staff' if "current_state='waiting_for_staff'" in sql else args[0]
            self.paused=1
        if 'INSERT INTO aiagentmessages' in sql:
            self.events.append(args[2]);payload=json.loads(args[3])
            if args[2]=='handoff_accept':self.actor=payload['actor']
    def fetchone(self):
        if 'SELECT content' in self.sql:return {'content':json.dumps({'actor':self.actor})}
        return {'current_state':self.state}

def test_queue_is_deduplicated_and_pauses_ai():
    cursor=Cursor()
    assert handoff.enqueue(cursor,'b','c','Позовите человека')=='waiting_for_staff'
    assert cursor.paused==1
    handoff.enqueue(cursor,'b','c','Повтор')
    assert cursor.events==['handoff_requested']

def test_staff_accept_close_and_conflicting_accept(monkeypatch):
    monkeypatch.setattr(handoff,'require_permission',lambda *args:None)
    cursor=Cursor('waiting_for_staff');user={'user_id':'staff'}
    assert handoff.operate(cursor,'b','c',user,'accept')['state']=='human_active'
    assert handoff.operate(cursor,'b','c',user,'accept')['state']=='human_active'
    assert cursor.events==['handoff_accept']
    with pytest.raises(ValueError):handoff.operate(cursor,'b','c',{'user_id':'other'},'accept')
    with pytest.raises(PermissionError):handoff.operate(cursor,'b','c',{'user_id':'other'},'close')
    assert handoff.operate(cursor,'b','c',user,'close')['state']=='closing'
    assert cursor.paused==1

def test_access_denial_does_not_mutate_queue(monkeypatch):
    def deny(*args):raise PermissionError('Нет доступа')
    monkeypatch.setattr(handoff,'require_permission',deny)
    cursor=Cursor('waiting_for_staff')
    with pytest.raises(PermissionError):handoff.operate(cursor,'foreign','c',{'user_id':'staff'},'accept')
    assert not cursor.events
