import pytest
from flask import Flask
from api import content_voice_api
api = content_voice_api
from services import content_references, content_voice_service
import database_manager


@pytest.fixture
def client(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(api.content_voice_bp)
    monkeypatch.setattr(api, 'verify_session', lambda _: {'user_id': 'owner'})
    class Database:
        conn = None
        def __init__(self):
            self.conn = self
        def cursor(self): return self
        def commit(self): pass
        def rollback(self): pass
        def close(self): pass
    monkeypatch.setattr(database_manager, 'DatabaseManager', Database)
    return app.test_client()


def test_requires_auth(client):
    assert client.get('/api/content-voice/references?business_id=a').status_code == 401


def test_cross_business_denial_precedes_repository(client, monkeypatch):
    def deny(*args, **kwargs): raise PermissionError('Нет доступа')
    monkeypatch.setattr(content_voice_service, '_verify_access', deny)
    monkeypatch.setattr(content_references, 'list_references', lambda *_: pytest.fail('unauthorized read'))
    assert client.get('/api/content-voice/references?business_id=other', headers={'Authorization': 'Bearer test'}).status_code == 403


def test_post_requires_write_and_conflicts_are_409(client, monkeypatch):
    called = []
    monkeypatch.setattr(content_voice_service, '_verify_access', lambda *args, **kwargs: called.append(kwargs['require_write']))
    def conflict(*_): raise content_references.ReferenceConflict('Настройки изменились')
    monkeypatch.setattr(content_references, 'change_reference', conflict)
    result = client.post('/api/content-voice/references', headers={'Authorization': 'Bearer test'}, json={'business_id': 'a', 'action': 'disable'})
    assert result.status_code == 409
    assert called == [True]


def test_bad_json_payload_rejected(client):
    assert client.post('/api/content-voice/references', headers={'Authorization': 'Bearer test'}, json=['invalid']).status_code == 400
