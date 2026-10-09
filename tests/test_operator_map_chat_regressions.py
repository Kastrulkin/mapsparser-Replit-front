import pytest
from services import operator_query, operator_map_refresh


def test_source_exclusions_do_not_select_google(monkeypatch):
    monkeypatch.setattr(operator_query, 'execute_operator_query', lambda *args, **kwargs: kwargs['arguments'])
    query = operator_query.read_reviews_request(None, 'root', 'Покажи только отзывы из 2ГИС. Не включай отзывы Яндекс и Google.')
    filters = query['filters']
    assert {'field': 'source', 'operator': 'contains', 'value': '2gis'} in filters
    assert {'field': 'source', 'operator': 'not_contains', 'value': 'google'} in filters
    assert not operator_query._matches({'source': 'google_business'}, filters[0])
    assert operator_query._matches({'source': 'two_gis'}, filters[0])


def test_source_exclusion_in_same_sentence(monkeypatch):
    monkeypatch.setattr(operator_query, 'execute_operator_query', lambda *args, **kwargs: kwargs['arguments'])
    query = operator_query.read_reviews_request(None, 'root', 'Покажи отзывы 2ГИС, не включай Google')
    assert query['filters'][0]['operator'] == 'contains'
    assert query['filters'][1]['operator'] == 'not_contains'


class BranchCursor:
    def execute(self, query, params):
        assert params == (['root', 'branch'],)
    def fetchall(self):
        return [{'id': 'root', 'name': 'Рога и копыта'}, {'id': 'branch', 'name': 'Рога и копыта — Петроградская'}]


def test_named_branch_is_filtered_within_authorized_scope(monkeypatch):
    monkeypatch.setattr(operator_query, 'query_business_ids', lambda *args: ['root', 'branch'])
    monkeypatch.setattr(operator_query, 'execute_operator_query', lambda *args, **kwargs: kwargs['arguments'])
    query = operator_query.read_reviews_request(BranchCursor(), 'root', 'Покажи отзывы только филиала «Рога и копыта — Петроградская».', 'user')
    assert query['filters'] == [{'field': 'business_name', 'operator': 'eq', 'value': 'Рога и копыта — Петроградская'}]
    assert operator_query.compile_operator_query(query)['filters'] == query['filters']
    result = operator_query.read_reviews_request(BranchCursor(), 'root', 'Покажи отзывы филиала «Закрытый филиал».', 'user')
    assert result['status'] == 'needs_clarification'


def test_services_show_branch_without_dropping_price():
    text = operator_query._render_service({'title': 'SPA', 'business_name': 'Петроградская', 'price': 1200}, full=False)
    assert 'Петроградская' in text and '1200' in text


@pytest.mark.parametrize('url,reason', [
    ('https://maps.google.com/?cid=demo-roga', 'demo_map_link'),
    ('https://maps.google.com/?cid=12345', 'unsupported_map_provider'),
    ('https://yandex.ru/maps/', 'map_organization_id_required'),
    ('https://evil.test/org/123/', 'unsupported_map_provider'),
])
def test_invalid_map_plan_blocks_before_reserving(monkeypatch, url, reason):
    def forbidden(*args, **kwargs):
        raise AssertionError('Must not reserve credits or call paid preflight')
    monkeypatch.setattr(operator_map_refresh, 'build_paid_action_preflight', forbidden)
    monkeypatch.setattr(operator_map_refresh, 'reserve_paid_action_credits', forbidden)
    result = operator_map_refresh.enqueue_paid_operator_map_refresh(None, business_id='root', user_id='user', explicit_url=url)
    assert reason in result['blocked_reasons']
    assert result['queue_id'] is None


def test_real_yandex_link_is_supported():
    result = operator_map_refresh.build_operator_map_refresh_plan(None, business_id='root', user_id='user', explicit_url='https://yandex.ru/maps/org/salon/12345/', require_runtime_flag=False)
    assert result['status'] == 'ready'
