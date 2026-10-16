import ast
import os
from pathlib import Path


def load_sender_lookup():
    source = Path('src/services/outreach_batch_preparation_service.py').read_text()
    function = next(node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name == '_load_platform_email_sender')
    namespace = {'Any': object, 'os': os, '_text': lambda value: str(value or '').strip()}
    exec(compile(ast.Module(body=[function], type_ignores=[]), '<sender_lookup>', 'exec'), namespace)
    return namespace['_load_platform_email_sender']


def test_missing_sender_config_does_not_select_another_account(monkeypatch):
    monkeypatch.delenv('OUTREACH_PLATFORM_EMAIL_SENDER', raising=False)
    assert load_sender_lookup()(None) is None


def test_sender_identity_is_configured_and_parameterized(monkeypatch):
    monkeypatch.setenv('OUTREACH_PLATFORM_EMAIL_SENDER', 'sender@example.com')
    class Cursor:
        def execute(self, sql, params):
            assert 'sender_identity = %s' in sql
            assert params == ('sender@example.com',)
            assert 'sender@example.com' not in sql
        def fetchone(self):
            return {'id': 'sender-id'}
    assert load_sender_lookup()(Cursor()) == 'sender-id'
