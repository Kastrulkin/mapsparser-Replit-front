"""A signed Telegram launch must execute the real tariff-filtered navigation."""
import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest
from flask import Flask
from api import operator_api
from subscription_manager import build_subscription_capabilities


@pytest.mark.parametrize('kind,tier', [('business','starter'), ('business','concierge'), ('network','professional'), ('platform','concierge')])
def test_signed_telegram_launch_uses_real_navigation(monkeypatch, kind, tier):
    token = 'synthetic-telegram-bootstrap-token'
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN', token)
    scope = {'kind':kind, 'id':'scope-1', 'business_ids':['business-1']}
    user = {'id':'owner-1','name':'Owner','is_superadmin':kind=='platform'}
    class Database:
        conn = None
        def __init__(self): self.conn = self
        def cursor(self): return object()
        def close(self): pass
    monkeypatch.setattr(operator_api,'DatabaseManager',Database)
    monkeypatch.setattr(operator_api,'load_localos_user_for_telegram',lambda *args:user)
    monkeypatch.setattr(operator_api,'list_control_scopes',lambda *args,**kwargs:{'businesses':[],'networks':[]})
    monkeypatch.setattr(operator_api,'resolve_control_scope',lambda *args,**kwargs:scope)
    monkeypatch.setattr(operator_api,'build_operator_scope_summary',lambda *args,**kwargs:{})
    monkeypatch.setattr(operator_api,'load_control_preferences',lambda *args,**kwargs:{})
    access = build_subscription_capabilities(tier=tier,status='active',is_superadmin=user['is_superadmin'])
    monkeypatch.setattr(operator_api,'_scope_subscription_access',lambda *args:access)
    monkeypatch.setattr(operator_api,'create_session',lambda *args,**kwargs:'synthetic-local-session')
    monkeypatch.setattr(operator_api,'resolve_mobile_deep_link',lambda *args,**kwargs:{})
    monkeypatch.setattr(operator_api,'_mobile_active_job',lambda *args,**kwargs:None)
    values={'auth_date':str(int(time.time())),'user':json.dumps({'id':123,'first_name':'Owner'})}
    secret=hmac.new(b'WebAppData',token.encode(),hashlib.sha256).digest()
    values['hash']=hmac.new(secret,'\n'.join(f'{key}={values[key]}' for key in sorted(values)).encode(),hashlib.sha256).hexdigest()
    app=Flask(__name__);app.register_blueprint(operator_api.operator_bp)
    client=app.test_client()
    response=client.post('/api/operator/telegram/bootstrap',json={'init_data':urlencode(values)})
    assert response.status_code==200,response.get_json()
    data=response.get_json();assert data['success'] and data['web_session_token']=='synthetic-local-session'
    navigation={item['key']:item for item in data['navigation']}
    assert navigation['today']['status']=='available'
    assert navigation['cards']['capability']=='maps'
    assert navigation['finance']['status']==('available' if tier=='concierge' else 'read_only')
    assert client.post('/api/operator/telegram/bootstrap',json={'init_data':'invalid'}).status_code==401


def test_mobile_write_capabilities_remain_defined():
    assert operator_api._mobile_capability_for_action('cards.refresh')=='maps'
    assert operator_api._mobile_capability_for_action('reviews.generate')=='maps.reviews'
    assert operator_api._mobile_capability_for_action('finance.sales.apply')=='finance'
