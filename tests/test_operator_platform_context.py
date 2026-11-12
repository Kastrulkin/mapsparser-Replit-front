import pytest

from services import operator_platform_context


class PlatformCursor:
    def __init__(self, allowed=True, replies=None):
        self.allowed = allowed
        self.replies = replies or []
        self.rows = []
        self.queries = []

    def execute(self, query, params=()):
        normalized = ' '.join(query.lower().split())
        self.queries.append((normalized, params))
        assert normalized.startswith('select'), 'Platform inbox must only read saved records'
        if 'join users actor' in normalized:
            assert 'actor.is_superadmin=true' in normalized
            assert 'actor.is_active' in normalized
            self.rows = [{'id': operator_platform_context.platform_business_id(), 'name': 'ЛокалОС'}] if self.allowed else []
        elif 'to_regclass' in normalized:
            self.rows = [{'table_ref': 'exists'}]
        elif 'from outreach_inbound_events' in normalized:
            assert 'left join lead_workstreams' in normalized
            assert 'inbound.is_human=true' in normalized
            self.rows = self.replies
        elif 'from outreach_sender_accounts' in normalized:
            self.rows = [{'channel': 'email', 'last_reply_sync_at': None, 'reply_sync_error': 'private-error'}]
        else:
            raise AssertionError(normalized)

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


def test_localos_inbox_reads_all_saved_replies_and_discloses_freshness():
    cursor = PlatformCursor(replies=[{'id': 'reply', 'lead_name': 'Партнёр', 'business_name': 'Клиент 2', 'reply_text': 'Давайте обсудим', 'channel': 'email'}])
    result = operator_platform_context.platform_read_request(cursor, business_id=operator_platform_context.platform_business_id(), user_id='admin', message='Покажи входящие по всем бизнесам')
    assert result['status'] == 'completed'
    assert 'Клиент 2' in result['chat_response']
    assert 'Давайте обсудим' in result['chat_response']
    assert 'ещё не подтверждена' in result['chat_response']
    assert 'не запускалась' in result['chat_response']
    assert 'private-error' not in result['chat_response']


def test_localos_name_never_grants_platform_access():
    cursor = PlatformCursor(allowed=False)
    with pytest.raises(PermissionError):
        operator_platform_context.platform_read_request(cursor, business_id=operator_platform_context.platform_business_id(), user_id='ordinary-owner', message='Проверь входящие')
    assert len(cursor.queries) == 1


@pytest.mark.parametrize('actor',[{'session_kind':'demo'},{'impersonating':True},{'impersonated_by':'admin'}])
def test_restricted_platform_chat_cannot_read_or_enqueue_live_inbox(actor,monkeypatch):
    from unittest.mock import Mock
    from services import operator_platform_outreach
    queue=Mock()
    monkeypatch.setattr(operator_platform_outreach,'enqueue_reply_sync',queue)
    cursor=PlatformCursor()
    with pytest.raises(PermissionError):
        operator_platform_context.platform_read_request(cursor,business_id=operator_platform_context.platform_business_id(),
            user_id='admin',message='Проверь входящие',actor=actor,request_id='restricted')
    assert not cursor.queries
    queue.assert_not_called()


def test_inbox_summary_fits_a_bot_message_without_hiding_the_freshness_limit():
    cursor = PlatformCursor(replies=[{'lead_name': 'Компания' * 100, 'business_name': 'Клиент' * 100,
                                     'reply_text': 'Ответ ' * 1000, 'channel': 'email'} for _ in range(21)])
    result = operator_platform_context.platform_read_request(cursor, business_id=operator_platform_context.platform_business_id(), user_id='admin', message='Покажи входящие')
    assert len(result['chat_response']) < 3500
    assert 'последние 5 ответов' in result['chat_response']
    assert 'не запускалась' in result['chat_response']


def test_localos_queries_expand_to_all_businesses_only_after_current_access_check(monkeypatch):
    from services import operator_query, business_permissions
    monkeypatch.setattr(business_permissions, 'load_actor', lambda *args: {'id': 'admin', 'is_superadmin': True})
    monkeypatch.setattr(business_permissions, 'require_permission', lambda *args: None)
    monkeypatch.setattr(operator_platform_context, 'platform_chat_business', lambda *args: {'id': operator_platform_context.platform_business_id()})
    class QueryCursor:
        def execute(self, query, params=()):
            assert 'FROM businesses WHERE COALESCE(is_active,TRUE)' in query
        def fetchall(self):
            return [{'id': 'localos'}, {'id': 'client-1'}, {'id': 'client-2'}]
    assert operator_query.query_business_ids(QueryCursor(), operator_platform_context.platform_business_id(), 'admin') == ['localos', 'client-1', 'client-2']


@pytest.mark.parametrize('business,message', [('ordinary', 'Проверь входящие'), ('system', 'Отправь всем ответы на входящие')])
def test_other_businesses_and_mutations_keep_the_existing_router(business, message):
    cursor = PlatformCursor()
    business_id = operator_platform_context.platform_business_id() if business == 'system' else business
    assert operator_platform_context.platform_read_request(cursor, business_id=business_id, user_id='admin', message=message) is None
    assert not cursor.queries
