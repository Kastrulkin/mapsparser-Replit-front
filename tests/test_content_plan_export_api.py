from io import BytesIO
from flask import Flask
import pytest
from api import content_plans_api

api = content_plans_api


def test_export_signer_uses_deployment_secret_without_flask_secret(monkeypatch):
    monkeypatch.delenv('CONTENT_PLAN_EXPORT_TOKEN_SECRET', raising=False)
    monkeypatch.setenv('EXTERNAL_AUTH_SECRET_KEY', 'configured-deployment-secret')
    app = Flask(__name__)
    with app.app_context():
        signer = api._export_signer()
        assert signer.loads(signer.dumps({'plan': 'p1'})) == {'plan': 'p1'}


def test_export_signer_fails_closed_without_any_secret(monkeypatch):
    monkeypatch.delenv('CONTENT_PLAN_EXPORT_TOKEN_SECRET', raising=False)
    monkeypatch.delenv('EXTERNAL_AUTH_SECRET_KEY', raising=False)
    app = Flask(__name__)
    with app.app_context(), pytest.raises(RuntimeError):
        api._export_signer()


def client(monkeypatch):
    app = Flask(__name__)
    app.secret_key = 'test-export-secret'
    app.register_blueprint(api.content_plans_bp)
    monkeypatch.setattr(api, '_require_auth', lambda: ({'user_id': 'owner'}, None))
    monkeypatch.setattr(api, '_export_plan', lambda *args: {'id': 'plan', 'items': []})
    monkeypatch.setattr(api, 'render_export', lambda *args: BytesIO(b'pdf'))
    return app.test_client()


def test_download_requires_signed_unchanged_snapshot(monkeypatch):
    browser = client(monkeypatch)
    result = browser.post('/api/content-plans/plan/export', json={'format': 'pdf'})
    assert result.status_code == 200
    url = result.json['download_url']
    assert browser.get(url).status_code == 200
    assert browser.get(url).headers['Cache-Control'] == 'private, no-store'
    assert browser.get(url).headers['Access-Control-Allow-Origin'] == 'https://web.telegram.org'
    assert browser.get(url + 'tampered').status_code == 410
    monkeypatch.setattr(api, '_export_plan', lambda *args: {'id': 'plan', 'items': ['changed']})
    assert browser.get(url).status_code == 409


def test_download_rechecks_access(monkeypatch):
    browser = client(monkeypatch)
    url = browser.post('/api/content-plans/plan/export', json={'format': 'xlsx'}).json['download_url']
    def denied(*args):
        raise PermissionError()
    monkeypatch.setattr(api, '_export_plan', denied)
    assert browser.get(url).status_code == 403


def test_format_is_validated(monkeypatch):
    assert client(monkeypatch).post('/api/content-plans/plan/export', json={'format': '../csv'}).status_code == 400
