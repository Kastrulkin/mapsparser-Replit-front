import uuid
from unittest.mock import Mock

import pytest
from flask import Blueprint, Flask

from api import operator_platform_outreach_api
from services import operator_platform_context, operator_platform_outreach, outreach_continuation


class Cursor:
    def __init__(self, allowed=True, replies=None):
        self.allowed = allowed
        self.replies = replies or []
        self.queries = []
        self.rows = []

    def execute(self, query, params=()):
        self.queries.append((query, params))
        if 'JOIN users actor' in query:
            self.rows = [{'id': operator_platform_context.platform_business_id()}] if self.allowed else []
        elif 'FROM users WHERE' in query:
            self.rows = [{'id': 'admin', 'is_active': True, 'is_superadmin': self.allowed}]
        elif 'FROM outreach_inbound_events inbound' in query:
            assert 'LEFT JOIN lead_workstreams' in query
            assert 'inbound.is_human=TRUE' in query
            self.rows = self.replies
        else:
            self.rows = []

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


@pytest.fixture
def api(monkeypatch):
    cursor = Cursor()
    database = Mock()
    database.conn.cursor.return_value = cursor
    monkeypatch.setattr(operator_platform_outreach_api, 'DatabaseManager', lambda: database)
    actor = {'user_id': 'admin', 'is_superadmin': True, 'messenger_platform': 'max'}
    monkeypatch.setattr(operator_platform_outreach_api, 'require_auth_from_request', lambda: actor)
    monkeypatch.setattr(operator_platform_outreach_api, 'resolve_control_scope', lambda *args, **kwargs: {'kind': 'platform'})
    app = Flask(__name__)
    blueprint = Blueprint('platform_test', __name__)
    operator_platform_outreach_api.register_platform_outreach_routes(blueprint)
    app.register_blueprint(blueprint)
    return app.test_client(), cursor, database, actor


def test_platform_search_needs_global_switch_but_not_a_second_business_allowlist(monkeypatch):
    business = operator_platform_context.platform_business_id()
    monkeypatch.setenv('OUTREACH_CONTINUATION_ENABLED', 'true')
    monkeypatch.setenv('OUTREACH_CONTINUATION_BUSINESS_IDS', 'client-1')
    assert outreach_continuation.continuation_enabled(business)
    assert outreach_continuation.continuation_enabled('client-1')
    assert not outreach_continuation.continuation_enabled('foreign')
    monkeypatch.setenv('OUTREACH_CONTINUATION_ENABLED', 'false')
    assert not outreach_continuation.continuation_enabled(business)


def test_platform_search_requires_current_admin_even_with_business_write_membership(monkeypatch):
    monkeypatch.setattr('core.auth_helpers.verify_business_write_access', lambda *args: (True, 'owner'))
    assert not outreach_continuation.actor_can_write(Cursor(allowed=False),
        operator_platform_context.platform_business_id(), {'id': 'ordinary-member', 'is_active': True})


@pytest.mark.parametrize('method', ['get', 'post'])
def test_current_db_access_denies_a_stale_superadmin_session(api, method):
    client, cursor, database, _actor = api
    cursor.allowed = False
    response = getattr(client, method)('/mobile/platform/outreach', json={'action': 'sync'})
    assert response.status_code == 403
    assert len(cursor.queries) == 1
    database.close.assert_called_once()


@pytest.mark.parametrize('restriction', [{'session_kind': 'demo'}, {'impersonating': True}, {'impersonated_by': 'other'}])
def test_platform_work_rejects_demo_and_impersonation_before_reading_data(api, restriction):
    client, cursor, _database, actor = api
    actor.update(restriction)
    response = client.get('/mobile/platform/outreach')
    assert response.status_code == 403
    assert not cursor.queries


def test_workspace_paginates_saved_replies_across_businesses(api, monkeypatch):
    client, cursor, _database, _actor = api
    ids = [str(uuid.uuid4()) for _ in range(3)]
    cursor.replies = [{'id': value, 'business_id': f'business-{index}', 'reply_text': 'Ответ'} for index, value in enumerate(ids)]
    monkeypatch.setattr('services.outreach_web_search.configured', lambda *args: False)
    response = client.get('/mobile/platform/outreach?limit=2')
    assert response.status_code == 200
    assert len(response.json['items']) == 2
    assert response.json['cursor'] == ids[1]
    response = client.get('/mobile/platform/outreach?limit=2&cursor=' + ids[1])
    assert response.status_code == 200
    queries = [(query, params) for query, params in cursor.queries if 'FROM outreach_inbound_events inbound' in query]
    assert queries[-1][1] == (ids[1], 3)
    assert 'inbound.created_at,inbound.id' in queries[-1][0]


def test_invalid_cursor_does_not_reach_inbox_query(api):
    client, cursor, *_ = api
    response = client.get('/mobile/platform/outreach?cursor=invalid')
    assert response.status_code == 400
    assert not any('FROM outreach_inbound_events inbound' in query for query, _ in cursor.queries)


def test_max_search_preview_reuses_chat_approval_without_creating_or_sending(api, monkeypatch):
    from services import operator_chat_service, partnership_leads_service
    client, cursor, database, _actor = api
    monkeypatch.setenv('OUTREACH_CONTINUATION_ENABLED', 'true')
    monkeypatch.setenv('OUTREACH_CONTINUATION_BUSINESS_IDS', '')
    monkeypatch.setattr(outreach_continuation, 'actor_can_write', lambda *args: True)
    monkeypatch.setattr(partnership_leads_service, 'get_capability_access', lambda *args: {'allowed': True})
    monkeypatch.setattr('services.outreach_web_search.configured', lambda *args: True)
    calls = []
    def chat(transaction_cursor, **context):
        calls.append(context)
        return context['router'](transaction_cursor)[0]
    monkeypatch.setattr(operator_chat_service, 'process_chat', chat)
    response = client.post('/mobile/platform/outreach', json={'action': 'search_preview', 'audience': 'салоны красоты',
        'search_geography': ['Пафос'], 'target_count': 10, 'request_id': 'preview-1', 'mode': 'auto_send', 'business_id': 'foreign'})
    assert response.status_code == 200
    result = response.json['operator_result']
    assert result['status'] == 'approval_required'
    assert result['search_started'] is False
    assert result['approval']['envelope']['business_id'] == operator_platform_context.platform_business_id()
    assert result['config']['mode'] == 'find_only'
    assert calls[0]['channel'] == 'max_mini_app'
    assert 'Пафос' in calls[0]['message']
    assert not any('INSERT' in query or 'UPDATE' in query for query, _ in cursor.queries)
    database.conn.commit.assert_called_once()


def test_refresh_queues_a_single_existing_job_without_provider_calls(api, monkeypatch):
    from services import operator_async_jobs
    client, cursor, database, _actor = api
    monkeypatch.setenv('OUTREACH_REPLY_SYNC_ENABLED', 'true')
    created = Mock(return_value={'id': 'sync-job', 'kind': operator_platform_outreach.SYNC_KIND, 'status': 'queued'})
    monkeypatch.setattr(operator_async_jobs, 'create_operator_async_job', created)
    forbidden = Mock(side_effect=AssertionError('provider call inside HTTP request'))
    monkeypatch.setattr(operator_platform_outreach, 'sync_reply_channels', forbidden)
    response = client.post('/mobile/platform/outreach', json={'action': 'sync', 'request_id': 'sync-1'})
    assert response.status_code == 200
    assert response.json['job']['id'] == 'sync-job'
    assert created.call_args.kwargs['business_id'] == operator_platform_context.platform_business_id()
    forbidden.assert_not_called()
    database.conn.commit.assert_called_once()


def test_real_chat_transaction_persists_the_platform_search_approval(api, monkeypatch):
    from services import operator_chat_service, partnership_leads_service
    client, _cursor, _database, _actor = api
    monkeypatch.setenv('OUTREACH_CONTINUATION_ENABLED', 'true')
    monkeypatch.setattr(outreach_continuation, 'actor_can_write', lambda *args: True)
    monkeypatch.setattr(partnership_leads_service, 'get_capability_access', lambda *args: {'allowed': True})
    monkeypatch.setattr('services.outreach_web_search.configured', lambda *args: True)
    monkeypatch.setattr('services.operator_request_history.enabled', lambda *args: False)
    monkeypatch.setattr('services.operator_workday.enabled', lambda *args: False)
    monkeypatch.setattr('services.operator_followups.remember_selection', lambda *args, **kwargs: None)
    for name, value in {'find_latest_operator_conversation': {}, 'get_or_create_operator_conversation': {'id': 'conversation'},
                        'conversation_pending_context': {}, 'list_operator_messages': [], 'list_pending_operator_actions': []}.items():
        monkeypatch.setattr(operator_chat_service, name, Mock(return_value=value))
    monkeypatch.setattr(operator_chat_service, 'append_operator_message', Mock(return_value='message'))
    monkeypatch.setattr(operator_chat_service, 'set_operator_pending_context', Mock())
    approval = Mock(return_value={'id': 'saved-approval'})
    monkeypatch.setattr(operator_chat_service, 'create_pending_operator_action', approval)
    create_task = Mock(side_effect=AssertionError('search created before confirmation'))
    monkeypatch.setattr(outreach_continuation, 'create_task', create_task)
    response = client.post('/mobile/platform/outreach', json={'action': 'search_preview', 'audience': 'салоны красоты',
        'search_geography': ['Пафос'], 'target_count': 10, 'request_id': 'preview-real'})
    assert response.status_code == 200
    assert response.json['operator_result']['approval']['action_id'] == 'saved-approval'
    assert approval.call_args.kwargs['business_id'] == operator_platform_context.platform_business_id()
    assert approval.call_args.kwargs['capability'] == 'partnerships.continue_outreach'
    assert approval.call_args.kwargs['envelope']['config']['mode'] == 'find_only'
    create_task.assert_not_called()


def test_shared_bot_check_command_queues_a_real_refresh(monkeypatch):
    cursor = Cursor()
    queue = Mock(return_value={'id': 'sync-job'})
    monkeypatch.setattr(operator_platform_outreach, 'enqueue_reply_sync', queue)
    result = operator_platform_context.platform_read_request(cursor, business_id=operator_platform_context.platform_business_id(), user_id='admin', message='Проверь входящие по всем бизнесам', actor={'session_kind':'standard'}, request_id='stable-platform-request')
    assert result['status'] == 'processing'
    assert result['async_job_id'] == 'sync-job'
    assert result['mobile_route']['screen'] == 'partnerships'
    queue.assert_called_once_with(cursor, user_id='admin', actor={'session_kind':'standard'}, request_id='stable-platform-request')


def test_sync_does_not_read_any_channel_after_access_revocation(monkeypatch):
    monkeypatch.setenv('OUTREACH_REPLY_SYNC_ENABLED', 'true')
    monkeypatch.setattr(operator_platform_outreach, '_authorize_job', Mock(side_effect=PermissionError('revoked')))
    adapters = Mock()
    monkeypatch.setattr(operator_platform_outreach, 'sync_reply_channels', adapters)
    with pytest.raises(PermissionError):
        operator_platform_outreach.process_reply_sync({})
    adapters.assert_not_called()


@pytest.mark.parametrize('picked,failed,expected', [(1, False, 'checked'), (1, True, 'partial'), (0, False, 'no_sources')])
def test_sync_reports_partial_failures_and_empty_sources_truthfully(monkeypatch, picked, failed, expected):
    monkeypatch.setenv('OUTREACH_REPLY_SYNC_ENABLED', 'true')
    authorize = Mock()
    monkeypatch.setattr(operator_platform_outreach, '_authorize_job', authorize)
    collect = Mock(side_effect=RuntimeError('private credential')) if failed else Mock(return_value={'picked': picked, 'imported': 0, 'failed': 0})
    next_channel = Mock(return_value={'picked': picked, 'failed': 0})
    monkeypatch.setattr(operator_platform_outreach, 'sync_reply_channels', lambda: [('email', collect), ('vk', next_channel)])
    connection = Mock()
    monkeypatch.setattr('pg_db_utils.get_db_connection', lambda: connection)
    monkeypatch.setattr(operator_platform_context, '_incoming', lambda *args, **kwargs: {'chat_response': 'Последние ответы', 'status': 'completed'})
    job = {'id': 'sync-job', 'user_id': 'admin', 'business_id': operator_platform_context.platform_business_id(), 'lease_token': 'current-lease'}
    result = operator_platform_outreach.process_reply_sync(job)
    assert result['sync_status'] == expected
    assert 'private credential' not in str(result)
    next_channel.assert_called_once()
    assert authorize.call_count == 4
    query, params = connection.cursor.return_value.execute.call_args.args
    assert 'UPDATE operatormessages' in query
    assert "lease_token=%s AND status='running'" in query
    assert params[-1] == 'current-lease'
    connection.commit.assert_called_once()
    connection.close.assert_called_once()


def test_existing_worker_executes_the_sync_job_and_persists_partial_status(monkeypatch):
    from services import operator_async_jobs
    import database_manager
    database = Mock()
    monkeypatch.setattr(database_manager, 'DatabaseManager', lambda: database)
    monkeypatch.setattr('services.operator_audio.cleanup_audio', lambda *args: None)
    monkeypatch.setattr(operator_async_jobs, 'recover_stale_operator_async_jobs', lambda *args: None)
    job = {'id': 'sync-job', 'user_id': 'admin', 'business_id': operator_platform_context.platform_business_id(), 'kind': operator_platform_outreach.SYNC_KIND, 'lease_token': 'lease'}
    monkeypatch.setattr(operator_async_jobs, 'claim_next_operator_async_job', lambda *args, **kwargs: job)
    heartbeat = Mock()
    monkeypatch.setattr(operator_async_jobs, '_OperatorJobHeartbeat', lambda *args: heartbeat)
    monkeypatch.setattr(operator_platform_outreach, 'process_reply_sync', lambda *args: {'sync_status': 'partial', 'chat_response': 'Часть каналов требует внимания'})
    save = Mock(return_value=True)
    monkeypatch.setattr(operator_async_jobs, 'update_operator_async_job', save)
    result = operator_async_jobs.process_next_operator_async_job()
    assert result['status'] == 'completed'
    assert save.call_args.kwargs['stage'] == 'Часть каналов требует внимания'
    assert save.call_args.kwargs['result']['sync_status'] == 'partial'
    heartbeat.stop.assert_called_once()
