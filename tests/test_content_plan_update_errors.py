import pytest
from flask import Flask
from api import content_plans_api


@pytest.fixture
def client(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(content_plans_api.content_plans_bp)
    monkeypatch.setattr(content_plans_api, '_require_auth', lambda: ({'user_id': 'qa-manager'}, None))
    return app.test_client()


def test_internal_update_failure_returns_a_traceable_safe_message(client, monkeypatch):
    def fail(*args, **kwargs):
        assert kwargs['auth_context'].user_id == 'qa-manager'
        assert not kwargs['auth_context'].is_superadmin
        raise RuntimeError('SQL private_table constraint details')
    monkeypatch.setattr(content_plans_api, 'update_content_plan_item', fail)
    response = client.put('/api/content-plans/items/qa-item', json={'draft_text': 'Синтетический текст'}, headers={'X-Request-ID': 'qa-trace'})
    assert response.status_code == 500
    body = response.get_json()
    assert body['code'] == 'internal_error'
    assert body['request_id'] == 'qa-trace'
    assert 'Не удалось подтвердить сохранение публикации' in body['message']
    assert 'private_table' not in response.get_data(as_text=True)


@pytest.mark.parametrize('failure,status', [(PermissionError('Нет доступа'),403), (content_plans_api.ContentPlanItemConflict('Пост изменился'),409), (ValueError('Материал не найден'),404)])
def test_domain_errors_keep_their_actionable_status(client, monkeypatch, failure, status):
    def fail(*args, **kwargs):
        raise failure
    monkeypatch.setattr(content_plans_api, 'update_content_plan_item', fail)
    response = client.put('/api/content-plans/items/qa-item', json={'draft_text': 'Тест'})
    assert response.status_code == status
    assert response.get_json()['error'] == str(failure)
