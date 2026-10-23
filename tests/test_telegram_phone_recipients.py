import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from core import telegram_userbot as bot

PHONE='+79990001122'

@pytest.fixture(autouse=True)
def phone_request_type(monkeypatch):
    monkeypatch.setattr(bot, 'ResolvePhoneRequest', lambda phone: SimpleNamespace(phone=phone))

@pytest.mark.parametrize('reference',[PHONE,'https://t.me/'+PHONE,'https://telegram.me/'+PHONE+'?text=hello'])
def test_phone_link_preserves_e164(reference):
    assert bot._normalize_entity_reference(reference)==PHONE

@pytest.mark.parametrize('reference',['https://t.me/+AbC123Invite','https://t.me/example','-1001234567','123456789'])
def test_nonphone_references_do_not_resolve_phone(monkeypatch,reference):
    client=SimpleNamespace(__call__=AsyncMock())
    async def forbidden(*args):raise AssertionError('Phone lookup not expected')
    monkeypatch.setattr(bot,'_wait_phone_resolution_slot',forbidden)
    result=asyncio.run(bot._telegram_request_target(client,{},reference))
    assert result is not None

class User:
    id=123
    username=None
    first_name='Business'
    bot=False

class Client:
    def __init__(self):
        self.user=User();self.requests=[];self.targets=[];self.disconnected=False
    async def is_user_authorized(self):return True
    async def __call__(self,request):
        self.requests.append(request)
        return SimpleNamespace(peer=SimpleNamespace(user_id=123),users=[self.user])
    async def get_entity(self,target):
        self.targets.append(target)
        assert target is self.user
        return target
    async def get_messages(self,target,**kwargs):
        self.targets.append(target)
        assert target is self.user
        return []
    async def send_message(self,target,text):
        self.targets.append(target)
        assert target is self.user
        return SimpleNamespace(id=41)
    async def disconnect(self):self.disconnected=True

@pytest.mark.parametrize('operation',['inspect','page','recent','replies','send'])
def test_same_resolved_user_used_for_all_operations(monkeypatch,operation):
    client=Client()
    monkeypatch.setattr(bot,'_connect_client',AsyncMock(return_value=client))
    wait=AsyncMock();monkeypatch.setattr(bot,'_wait_phone_resolution_slot',wait)
    ref='https://t.me/'+PHONE
    operations={'inspect':lambda:bot._inspect_telegram_entity_async({},ref),'page':lambda:bot._fetch_message_page_async({},ref),'recent':lambda:bot._fetch_recent_messages_async({},ref),'replies':lambda:bot._fetch_recent_replies_async({},ref),'send':lambda:bot._send_message_async({},ref,'approved text')}
    result=asyncio.run(operations[operation]())
    assert result['status'] in {'ok','sent'}
    assert len(client.requests)==1 and client.requests[0].phone==PHONE
    assert client.targets and client.disconnected
    wait.assert_awaited_once()


def test_unavailable_phone_never_falls_back_to_contacts_or_send(monkeypatch):
    client=Client()
    async def unavailable(self,request):return SimpleNamespace(peer=SimpleNamespace(user_id=999),users=[])
    monkeypatch.setattr(Client,'__call__',unavailable)
    monkeypatch.setattr(bot,'_connect_client',AsyncMock(return_value=client))
    monkeypatch.setattr(bot,'_wait_phone_resolution_slot',AsyncMock())
    with pytest.raises(ValueError,match='Telegram'):
        asyncio.run(bot._send_message_async({},'https://t.me/'+PHONE,'approved text'))
    assert client.targets==[] and client.disconnected


def test_phone_lookup_requires_shared_limiter_configuration(monkeypatch):
    monkeypatch.delenv('RATE_LIMIT_STORAGE_URI',raising=False)
    with pytest.raises(ValueError,match='ограничителя'):
        asyncio.run(bot._wait_phone_resolution_slot({'session_string':'test-only'}))


def test_phone_lookup_limiter_is_sender_bound_and_bounded(monkeypatch):
    import sys
    calls=[]
    class Backend:
        def set(self,*args,**kwargs):calls.append((args,kwargs));return False
        def close(self):pass
    monkeypatch.setitem(sys.modules,'redis',SimpleNamespace(Redis=SimpleNamespace(from_url=lambda *a,**k:Backend())))
    monkeypatch.setenv('RATE_LIMIT_STORAGE_URI','redis://test-only')
    sleep=AsyncMock();monkeypatch.setattr(bot.asyncio,'sleep',sleep)
    with pytest.raises(ValueError,match='Повторите позже'):
        asyncio.run(bot._wait_phone_resolution_slot({'session_string':'test-only'}))
    assert len(calls)==4 and sleep.await_count==3
    assert all(kw=={'nx':True,'px':3100} and 'test-only' not in args[0] for args,kw in calls)
