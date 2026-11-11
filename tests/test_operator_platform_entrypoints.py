"""Execute the actual entrypoint bodies without unrelated optional app imports."""
import ast
import json
import logging
import uuid
from pathlib import Path

import pytest
from flask import Flask, jsonify, request

from services import operator_chat_service, operator_platform_context


def load_function(path, name, namespace):
    tree = ast.parse(Path(path).read_text())
    definition = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)
    definition.decorator_list = []
    unit = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), definition], type_ignores=[])
    exec(compile(ast.fix_missing_locations(unit), path, 'exec'), namespace)
    return namespace[name]


class EntryDatabase:
    allowed = True

    def __init__(self):
        self.conn = self
        self.closed = False

    def cursor(self):
        return self

    def execute(self, query, params=()):
        if 'JOIN users actor' in query:
            assert params == ('admin', operator_platform_context.platform_business_id())

    def fetchone(self):
        return {'id': operator_platform_context.platform_business_id(), 'name': 'ЛокалОС'} if self.allowed else None

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        self.closed = True


@pytest.mark.parametrize('allowed', [True, False])
def test_chat_platform_payload_uses_existing_localos_business_after_access_check(monkeypatch, allowed):
    monkeypatch.setattr(EntryDatabase, 'allowed', allowed)
    chat_calls = []
    def process(cursor, **arguments):
        chat_calls.append(arguments)
        return {'conversation_id': 'conversation', 'message_id': 'message', 'status': 'completed', 'chat_response': 'Ответы по всем бизнесам'}
    monkeypatch.setattr(operator_chat_service, 'process_chat', process)
    resolved = []
    def resolve(cursor, **arguments):
        resolved.append(arguments)
        return {'kind': 'platform'}
    namespace = dict(json=json, uuid=uuid, request=request, jsonify=jsonify, logger=logging.getLogger(__name__),
        DatabaseManager=EntryDatabase, require_auth_from_request=lambda: {'user_id': 'admin', 'is_superadmin': allowed},
        resolve_control_scope=resolve, verify_business_access=lambda *args: (True, 'admin'), verify_business_write_access=lambda *args: (True, 'admin'),
        _scope_capability_access=lambda *args: {'allowed': True}, _scope_subscription_access=lambda *args: {},
        record_operator_event=lambda *args, **kwargs: None, _operator_mobile_route=lambda value: {'screen': 'partnerships'},
        route_operator_message=lambda *args, **kwargs: None, refresh_reviews_from_operator=None,
        classify_operator_intent_with_ai=None, process_operator_chat_message=None)
    for name in ('_scope_request_values', '_resolve_mobile_scope', 'operator_chat'):
        load_function('src/api/operator_api.py', name, namespace)
    app = Flask(__name__)
    app.add_url_rule('/chat', view_func=namespace['operator_chat'], methods=['POST'])
    response = app.test_client().post('/chat', json={'scope_type': 'platform', 'message': 'Проверь входящие', 'channel': 'max_mini_app'})
    assert response.status_code == (200 if allowed else 403)
    assert resolved[0]['requested_kind'] == 'platform'
    if allowed:
        assert chat_calls[0]['business_id'] == operator_platform_context.platform_business_id()
        assert chat_calls[0]['channel'] == 'max_mini_app'
        assert response.json['business_id'] == operator_platform_context.platform_business_id()
    else:
        assert not chat_calls


@pytest.mark.parametrize('allowed', [True, False])
def test_shared_owner_bot_uses_the_same_localos_context(monkeypatch, allowed):
    monkeypatch.setattr(EntryDatabase, 'allowed', allowed)
    database = EntryDatabase()
    namespace = dict(get_user_id_from_telegram=lambda external_id: 'admin', get_db_connection=lambda: database)
    function = load_function('src/telegram_bot.py', '_control_scope_business_context', namespace)
    result = function('verified-max-identity', {'kind': 'platform', 'name': 'LocalOS'})
    assert database.closed
    if allowed:
        assert result['business_id'] == operator_platform_context.platform_business_id()
        assert result['control_scope']['kind'] == 'platform'
    else:
        assert result is None
