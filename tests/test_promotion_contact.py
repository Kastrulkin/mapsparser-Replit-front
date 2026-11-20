"""Contact delivery contract, isolated from runtime DB and provider integrations."""
import ast
from pathlib import Path
import sys
from unittest.mock import Mock

from flask import Flask, jsonify, request
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from core.promotion_contact import promotion_contact_fields


@pytest.fixture
def contact():
    source = ROOT / 'src/legacy_routes/report_pipeline.py'
    tree = ast.parse(source.read_text())
    handler = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'public_contact')
    handler.decorator_list = []
    deliver = Mock(return_value=True)
    namespace = dict(request=request, jsonify=jsonify, send_contact_email=deliver)
    exec(compile(ast.Module(body=[handler], type_ignores=[]), str(source), 'exec'), namespace)
    app = Flask(__name__)
    app.add_url_rule('/api/public/contact', view_func=namespace['public_contact'], methods=['POST', 'OPTIONS'])
    return app.test_client(), deliver


def payload(**extra):
    return dict(request_kind='promotion', name='Тест', phone='+7 (999) 123-45-67', direction='maps', page='/prodvizhenie-na-yandex-kartah', personal_data_consent=True, attribution={'utm_source': 'search'}, **extra)


def test_phone_only_request_uses_existing_delivery(contact):
    client, deliver = contact
    response = client.post('/api/public/contact', json=payload())
    assert response.status_code == 200
    assert response.json['success'] is True
    name, email, phone, message = deliver.call_args.args
    assert email == ''
    assert name == 'Тест'
    assert 'Направление: maps' in message
    assert 'utm_source: search' in message
    assert 'Согласие на обработку данных: получено' in message


@pytest.mark.parametrize('change', [
    {'phone': 'abcd'}, {'phone': '123456'}, {'name': '\r\nBcc: someone'},
    {'name': None}, {'phone': ['bad']}, {'direction': 'unknown'},
    {'page': '/lokalnye-blogery'}, {'personal_data_consent': False},
    {'attribution': {'utm_source': 'x\nSpoof'}}, {'attribution': []},
])
def test_invalid_promotion_never_delivers(contact, change):
    client, deliver = contact
    data = payload()
    data.update(change)
    response = client.post('/api/public/contact', json=data)
    assert response.status_code == 400
    deliver.assert_not_called()


def test_failed_delivery_never_reports_success(contact):
    client, deliver = contact
    deliver.return_value = False
    response = client.post('/api/public/contact', json=payload())
    assert response.status_code == 503
    assert 'success' not in response.json


def test_exception_does_not_leak_provider_details(contact):
    client, deliver = contact
    deliver.side_effect = RuntimeError('smtp-secret-123')
    response = client.post('/api/public/contact', json=payload())
    assert response.status_code == 500
    assert 'smtp-secret' not in response.get_data(as_text=True)


def test_legacy_email_form_keeps_its_contract(contact):
    client, deliver = contact
    response = client.post('/api/public/contact', json={'name': 'Owner', 'email': 'owner@example.test', 'message': 'Hello'})
    assert response.status_code == 200
    assert deliver.call_args.args == ('Owner', 'owner@example.test', '', 'Hello')
    deliver.reset_mock()
    assert client.post('/api/public/contact', json={'name': 'Owner', 'phone': '+79991234567'}).status_code == 400
    deliver.assert_not_called()
