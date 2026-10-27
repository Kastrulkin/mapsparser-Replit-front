import importlib.util
import sys
from pathlib import Path


def load_configuration_script():
    path=Path(__file__).parents[1]/'scripts/configure_max_bot.py'
    spec=importlib.util.spec_from_file_location('configure_max_bot_under_test',path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_apply_uses_current_max_command_endpoint_and_protected_webhook(monkeypatch,capsys):
    script=load_configuration_script();calls=[]
    class Transport:
        def call(self,method,path,**kwargs):
            calls.append((method,path,kwargs))
            if path=='/me':return {'is_bot':True}
            if method=='GET':return {'subscriptions':[]}
            return {'success':True}
    monkeypatch.setattr(script,'MaxTransport',Transport)
    monkeypatch.setenv('MAX_BOT_TOKEN','synthetic-token-never-log')
    monkeypatch.setenv('MAX_WEBHOOK_SECRET','synthetic-secret-'+'x'*32)
    monkeypatch.setattr(sys,'argv',['configure_max_bot.py','--apply'])
    script.main()
    assert [(method,path) for method,path,_ in calls]==[
        ('GET','/me'),('GET','/subscriptions'),('PATCH','/me/commands'),('POST','/subscriptions')]
    subscription=calls[-1][2]['body']
    assert subscription['url']=='https://localos.pro/api/max/webhook'
    assert subscription['secret']=='synthetic-secret-'+'x'*32
    assert 'message_created' in subscription['update_types']
    output=capsys.readouterr()
    assert 'synthetic-token-never-log' not in output.out+output.err
    assert subscription['secret'] not in output.out+output.err


def test_default_configuration_check_does_not_register_or_send(monkeypatch):
    script=load_configuration_script();calls=[]
    class Transport:
        def call(self,method,path,**kwargs):
            calls.append((method,path))
            return {'is_bot':True} if path=='/me' else {'subscriptions':[]}
    monkeypatch.setattr(script,'MaxTransport',Transport)
    monkeypatch.setenv('MAX_BOT_TOKEN','synthetic-token')
    monkeypatch.delenv('MAX_WEBHOOK_SECRET',raising=False)
    monkeypatch.setattr(sys,'argv',['configure_max_bot.py'])
    script.main()
    assert calls==[('GET','/me'),('GET','/subscriptions')]
