"""Signed launch creates a real LocalOS session; revocation fails closed."""
import ast
import hashlib
import hmac
import json
import time
from pathlib import Path
from urllib.parse import urlencode, urlsplit

from flask import Flask

from tests.test_max_control_pg import max_pg


def test_signed_bootstrap_session_and_revocation(max_pg, monkeypatch):
    connection, connect = max_pg
    import auth_system
    from api import operator_api
    from services.max_identity import issue_link_code, consume_link_code
    monkeypatch.setenv('MAX_ENABLED', 'true')
    monkeypatch.setenv('MAX_BOT_TOKEN', 'synthetic-bootstrap-token')
    monkeypatch.setattr(auth_system, 'get_db_connection', connect)
    class Database:
        def __init__(self): self.conn = connect()
        def close(self): self.conn.close()
    monkeypatch.setattr(operator_api, 'DatabaseManager', Database)
    monkeypatch.setattr(operator_api, 'list_control_scopes', lambda *args, **kwargs: {'businesses': [], 'networks': []})
    monkeypatch.setattr(operator_api, 'resolve_control_scope', lambda *args, **kwargs: None)
    monkeypatch.setattr(operator_api, '_scope_subscription_access', lambda *args: {})
    monkeypatch.setattr(operator_api, '_mobile_navigation', lambda *args: [])
    monkeypatch.setattr(operator_api, 'resolve_mobile_deep_link', lambda *args, **kwargs: {})
    monkeypatch.setattr(operator_api, '_mobile_active_job', lambda *args, **kwargs: None)
    app = Flask(__name__)
    app.register_blueprint(operator_api.operator_bp)
    client = app.test_client()
    values = {'auth_date': str(int(time.time())), 'user': json.dumps({'id': 123, 'first_name': 'Owner'})}
    secret = hmac.new(b'WebAppData', b'synthetic-bootstrap-token', hashlib.sha256).digest()
    values['hash'] = hmac.new(secret, '\n'.join(f'{key}={values[key]}' for key in sorted(values)).encode(), hashlib.sha256).hexdigest()
    raw = urlencode(values)
    response = client.post('/api/operator/max/bootstrap', json={'init_data': raw})
    assert response.status_code == 401 and response.json['code'] == 'max_link_required'
    cursor = connection.cursor()
    consume_link_code(cursor, issue_link_code(cursor, 'u1'), '123')
    connection.commit()
    response = client.post('/api/operator/max/bootstrap', json={'init_data': raw})
    assert response.status_code == 200
    token = response.json['web_session_token']
    assert token and auth_system.verify_session(token)['messenger_platform'] == 'max'
    cursor.execute("UPDATE max_identities SET revoked_at=NOW() WHERE max_id='123'")
    connection.commit()
    assert auth_system.verify_session(token) is None
    assert client.post('/api/operator/max/bootstrap', json={'init_data': raw}).status_code == 401
    monkeypatch.setenv('MAX_ENABLED', 'false')
    assert client.post('/api/operator/max/bootstrap', json={'init_data': raw}).status_code == 503


def test_checkout_return_preserves_both_messengers_and_rejects_external_redirects():
    source = Path(__file__).parents[1] / 'src/yookassa_integration.py'
    tree = ast.parse(source.read_text())
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == '_safe_checkout_return_to')
    namespace = {'Any': object, 'urlsplit': urlsplit}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), namespace)
    validate = namespace['_safe_checkout_return_to']
    for path in ['/max/control?screen=settings', '/telegram/control?screen=content', '/dashboard/profile#subscription']:
        assert validate(path) == path
    for path in ['https://evil.test', '//evil.test', '/max/control/extra', '/dashboard/\\evil', '/max/control\nx']:
        assert validate(path) == ''
