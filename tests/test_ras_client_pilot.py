import json
from unittest.mock import patch
import pytest
from services import ras_client_pilot as pilot

class Cursor:
    def __init__(self):
        self.sql='';self.events={};self.row=None;self.identity='123';self.phone=pilot.PREFIX+pilot.ACTOR
    def execute(self,sql,args=()):
        self.sql=sql;self.row=None
        if 'SELECT content FROM aiagentmessages WHERE id=' in sql:self.row=self.events.get(args[0])
        if "'client_delivery'" in sql and 'INSERT' in sql:self.events[args[0]]={'content':args[2]}
        if 'UPDATE aiagentmessages SET content' in sql:self.events[args[1]]={'content':args[0]}
    def fetchone(self):
        if 'SELECT u.telegram_id' in self.sql:return {'telegram_id':self.identity}
        if 'SELECT client_phone' in self.sql:return {'client_phone':self.phone}
        return self.row
class DB:
    def __init__(self):self.conn=self;self.c=Cursor();self.commits=0
    def cursor(self):return self.c
    def commit(self):self.commits+=1
    def rollback(self):pass
    def close(self):pass

@pytest.fixture
def setup():
    db=DB()
    with patch.object(pilot,'DatabaseManager',return_value=db),patch.object(pilot,'operate',return_value={'state':'human_active'}) as operate,patch.object(pilot,'send_telegram_message_result',return_value={'publish_outcome':'confirmed','message_id':12}) as send,patch('services.business_permissions.require_permission'):
        yield db,operate,send

def test_exact_account_business_and_private_identity(setup):
    db,_,send=setup
    assert pilot.identity(db.c,'123')=='123'
    with pytest.raises(PermissionError):pilot.identity(db.c,'999')
    assert not pilot.is_pilot('foreign',db.c.phone)
    assert not pilot.is_pilot(pilot.BUSINESS,'tg-ras-pilot:someone')
    send.assert_not_called()

def test_real_reply_confirmed_and_duplicate_suppressed(setup):
    db,operate,send=setup;user={'user_id':pilot.ACTOR}
    result=pilot.reply(pilot.BUSINESS,'c',user,'Ответ')
    assert result['delivery']=='telegram' and db.commits==2
    assert send.call_args.args[0]=='123'
    assert 'Ответ' in send.call_args.args[1]
    assert pilot.reply(pilot.BUSINESS,'c',user,'Ответ')['duplicate_prevented']
    assert send.call_count==1 and operate.call_count==1

def test_uncertain_delivery_not_retried(setup):
    _,_,send=setup;send.return_value={'publish_outcome':'uncertain'}
    for _ in range(2):
        with pytest.raises(ValueError):pilot.reply(pilot.BUSINESS,'c',{'user_id':pilot.ACTOR},'Ответ')
    assert send.call_count==1

def test_foreign_channel_and_unaccepted_never_send(setup):
    db,operate,send=setup;db.c.phone='other'
    with pytest.raises(ValueError):pilot.reply(pilot.BUSINESS,'c',{'user_id':pilot.ACTOR},'Ответ')
    db.c.phone=pilot.PREFIX+pilot.ACTOR;operate.side_effect=ValueError('Сначала примите диалог')
    with pytest.raises(ValueError):pilot.reply(pilot.BUSINESS,'c',{'user_id':pilot.ACTOR},'Ответ')
    send.assert_not_called()

def test_incoming_queue_dedup_and_closed_stays_paused(setup):
    db,_,_=setup
    from unittest.mock import MagicMock
    c=MagicMock();db.c=c
    conversation={'id':'c','current_state':'greeting'}
    with patch.object(pilot,'identity'),patch.object(pilot,'load_actor',return_value={'user_id':pilot.ACTOR}),patch.object(pilot,'enqueue') as enqueue,patch('services.client_handoff_notifications.notify_self') as notify:
        c.fetchone.side_effect=[conversation,{'content':'active'},{'id':'m'}]
        assert pilot.receive('123',10,'Хочу записаться')['handled']
        enqueue.assert_called_once();notify.assert_called_once()
        c.fetchone.side_effect=[conversation,{'content':'active'},None]
        pilot.receive('123',10,'Хочу записаться')
        assert enqueue.call_count==1 and notify.call_count==1
        c.fetchone.side_effect=[{'id':'c','current_state':'closing'},{'content':'active'},{'id':'m2'}]
        assert pilot.receive('123',11,'Спасибо')['handled']
        assert enqueue.call_count==1 and notify.call_count==1

def test_inactive_mode_falls_back_to_operator(setup):
    db,_,_=setup
    from unittest.mock import MagicMock
    c=MagicMock();db.c=c;c.fetchone.side_effect=[{'id':'c','current_state':'closing'},{'content':'inactive'}]
    with patch.object(pilot,'identity'):
        assert not pilot.receive('123',12,'Статус бизнеса')['handled']

def test_registration_does_not_shadow_owner_start():
    import ast
    from pathlib import Path
    tree=ast.parse(Path('src/telegram_bot.py').read_text())
    boot=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_run_bot_once')
    assert not any(isinstance(n,ast.ImportFrom) and any(a.name=='start' for a in n.names) for n in ast.walk(boot))
