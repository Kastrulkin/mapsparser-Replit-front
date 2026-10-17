import json
import uuid
from datetime import datetime, timezone

import pytest
from services import operator_work_handoff
from services import operator_audio, operator_editorial

USER = str(uuid.uuid4())
BUSINESS = str(uuid.uuid4())
ITEM = str(uuid.uuid4())
CONVERSATION = str(uuid.uuid4())


class Cursor:
    def __init__(self, conversation=None):
        self.conversation = conversation
        self.query = ''
        self.calls = []

    def execute(self, query, params=()):
        self.query = query
        self.calls.append((query, params))

    def fetchone(self):
        if 'FROM users' in self.query:
            return {'telegram_id': '123'}
        if 'FROM max_identities' in self.query:
            return {'max_id': '456'}
        if 'FROM operatorconversations' in self.query:
            return self.conversation
        return None


@pytest.fixture(autouse=True)
def content_access(monkeypatch):
    import subscription_manager
    monkeypatch.setattr(subscription_manager, 'capability_access_payload', lambda *a, **kw: {'allowed': True})


def selected():
    return {'item_id': ITEM, 'plan_id': 'plan', 'version': 'v1'}


@pytest.mark.parametrize('platform,host,channel', [('telegram', 't.me', 'telegram'), ('max', 'max.ru', 'max_bot')])
def test_handoff_uses_own_platform_and_existing_conversation_storage(monkeypatch, platform, host, channel):
    monkeypatch.setenv('MAX_BOT_USERNAME', 'localos_max_bot')
    monkeypatch.setattr(operator_work_handoff, 'content_selection', lambda *a, **kw: selected())
    seen = []
    monkeypatch.setattr(operator_work_handoff, 'get_or_create_operator_conversation', lambda *a, **kw: seen.append(kw) or {'id': CONVERSATION})
    monkeypatch.setattr(operator_work_handoff, 'set_operator_pending_context', lambda c, identifier, pending: seen.append(pending))
    result = operator_work_handoff.prepare_handoff(Cursor(), user_id=USER, business_id=BUSINESS, platform=platform,
        item_id=ITEM, request_id=str(uuid.uuid4()))
    assert result['url'].startswith('https://' + host + '/')
    assert result['url'].endswith('work_' + uuid.UUID(CONVERSATION).hex)
    assert seen[0]['channel'] == channel
    assert seen[1]['selected_item'] == selected()
    assert '/' + platform + '/control?' in result['return_url']


def test_content_selection_checks_access_and_business_before_returning_a_version(monkeypatch):
    access = []
    monkeypatch.setattr(operator_audio, 'authorize_actor', lambda *a, **kw: (access.append(kw), {}))
    monkeypatch.setattr(operator_editorial, '_items', lambda *a, **kw: [])
    with pytest.raises(PermissionError):
        operator_work_handoff.content_selection(Cursor(), user_id=USER, business_id=BUSINESS, item_id=ITEM)
    assert access == [{'require_write': True}]


def test_content_selection_rejects_changed_displayed_post(monkeypatch):
    monkeypatch.setattr(operator_audio, 'authorize_actor', lambda *a, **kw: ({}, {}))
    monkeypatch.setattr(operator_editorial, '_items', lambda *a, **kw: [{'id': ITEM, 'plan_id': 'p', 'updated_at': datetime(2026, 10, 16, tzinfo=timezone.utc)}])
    with pytest.raises(ValueError, match='Пост изменился'):
        operator_work_handoff.content_selection(Cursor(), user_id=USER, business_id=BUSINESS, item_id=ITEM, expected_updated_at='2026-10-15T00:00:00+00:00')


def test_other_user_or_platform_cannot_resume_handoff():
    cursor = Cursor()
    with pytest.raises(PermissionError):
        operator_work_handoff.resume_handoff(cursor, user_id=USER, platform='max', token='work_' + uuid.UUID(CONVERSATION).hex)
    assert cursor.calls[0][1] == (CONVERSATION, USER, 'max_bot')


def test_resume_rechecks_access_version_and_never_executes_a_command(monkeypatch):
    cursor = Cursor({'id': CONVERSATION, 'business_id': BUSINESS,
        'pending_context': {'selected_item': selected()}})
    monkeypatch.setattr(operator_work_handoff, 'content_selection', lambda *a, **kw: {**selected(), 'version': 'v2'})
    with pytest.raises(ValueError, match='Пост изменился'):
        operator_work_handoff.resume_handoff(cursor, user_id=USER, platform='telegram', token='work_' + uuid.UUID(CONVERSATION).hex)
    assert not any('UPDATE' in query for query, _ in cursor.calls)


def test_duplicate_request_cannot_replace_another_selection(monkeypatch):
    monkeypatch.setattr(operator_work_handoff, 'content_selection', lambda *a, **kw: selected())
    monkeypatch.setattr(operator_work_handoff, 'get_or_create_operator_conversation', lambda *a, **kw: {'id': CONVERSATION,
        'pending_context': {'selected_item': {**selected(), 'item_id': 'other'}}})
    with pytest.raises(ValueError, match='другого поста'):
        operator_work_handoff.prepare_handoff(Cursor(), user_id=USER, business_id=BUSINESS, platform='telegram', item_id=ITEM, request_id=str(uuid.uuid4()))


def test_handoff_does_not_bypass_the_content_subscription(monkeypatch):
    import subscription_manager
    monkeypatch.setattr(operator_audio, 'authorize_actor', lambda *a, **kw: ({}, {}))
    monkeypatch.setattr(subscription_manager, 'capability_access_payload', lambda *a, **kw: {'allowed': False})
    monkeypatch.setattr(operator_editorial, '_items', lambda *a, **kw: pytest.fail('Content must not be loaded before its tier gate'))
    with pytest.raises(PermissionError, match='тарифе'):
        operator_work_handoff.content_selection(Cursor(), user_id=USER, business_id=BUSINESS, item_id=ITEM)
