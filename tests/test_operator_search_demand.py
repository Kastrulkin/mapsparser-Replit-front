import pytest
from services import operator_query, operator_search_demand, business_permissions
from services.operator_context import PlannerContext
from services.operator_editorial import editorial_input
from services.operator_services_optimization import _build_services_prompt
from services.operator_product_knowledge import classify_product_explanation_intent


class ScopeCursor:
    description = []
    def execute(self, query, params):
        self.query = query
        self.params = params
    def fetchone(self):
        return {'network_id': 'root'}
    def fetchall(self):
        return [{'id': 'root'}, {'id': 'allowed'}, {'id': 'denied'}]


def test_network_parent_expands_only_authorized_locations(monkeypatch):
    monkeypatch.setattr(business_permissions, 'load_actor', lambda *args: {'id': 'user'})
    monkeypatch.setattr(business_permissions, 'require_permission', lambda *args: None)
    monkeypatch.setattr('core.auth_helpers.verify_business_access', lambda cursor, target, user: (target != 'denied', 'owner'))
    assert operator_query.query_business_ids(ScopeCursor(), 'root', 'user') == ['root', 'allowed']
    assert operator_query.query_business_ids(ScopeCursor(), 'allowed', 'user') == ['allowed']


def test_network_parent_denied_does_not_expand(monkeypatch):
    monkeypatch.setattr(business_permissions, 'load_actor', lambda *args: {'id': 'user'})
    def deny(*args):
        raise PermissionError('denied')
    monkeypatch.setattr(business_permissions, 'require_permission', deny)
    with pytest.raises(PermissionError):
        operator_query.query_business_ids(ScopeCursor(), 'root', 'user')


def test_network_review_query_uses_scope_and_branch_labels(monkeypatch):
    monkeypatch.setattr(operator_query, 'query_business_ids', lambda *args: ['root', 'allowed'])
    class Cursor(ScopeCursor):
        def fetchall(self):
            assert self.params == (['root', 'allowed'],)
            assert 'ANY(%s)' in self.query
            return [{'id': 'review', 'business_name': 'Филиал', 'author_name': 'Анна', 'text': 'Хорошо', 'updated_at': '2026-06-24', 'published_at': '2026-06-20'}]
    result = operator_query.execute_operator_query(Cursor(), business_id='root', user_id='user', arguments={'resource': 'reviews', 'view': 'full'})
    assert 'Филиал' in result['chat_response']
    assert '2026-06-24' in result['chat_response']
    assert result['external_writes_performed'] is False


def test_wordstat_excludes_mask_show_from_grooming():
    services = [{'name': 'SPA-маска для шерсти', 'description': 'Груминг собак'}]
    candidates = [{'keyword': 'кто снял маску в шоу', 'views': 30000}, {'keyword': 'spa уход для собак', 'views': 1200}]
    result = operator_search_demand.relevant_candidates(candidates, services)
    assert [item['keyword'] for item in result] == ['spa уход для собак']
    prompt = _build_services_prompt(services, {'items': result})
    assert 'spa уход для собак' in prompt
    assert 'кто снял маску' not in prompt
    assert 'не текущие тренды' in prompt


def test_new_search_queries_have_seo_tools():
    context = PlannerContext('Проверь новые популярные поисковые запросы из вордстата')
    tools = [{'name': 'seo.search_demand'}, {'name': 'services.prepare_updates'}, {'name': 'content.list_items'}]
    names = {tool['name'] for tool in context.tools(tools)}
    assert 'seo.search_demand' in names
    assert 'services.prepare_updates' in names
    assert not editorial_input('Проверь новые популярные поисковые запросы из вордстата')


def test_stored_queries_never_claim_new_trends(monkeypatch):
    monkeypatch.setattr(operator_search_demand, 'stored_demand', lambda *args, **kwargs: {'items': [{'keyword': 'груминг собак', 'views': 18500, 'updated_at': '2026-06-24', 'business_name': 'Филиал', 'business_city': 'СПб'}], 'period_comparison_available': False})
    result = operator_search_demand.read_demand(None, 'root', 'user', {})
    assert 'Новизна и рост не подтверждены' in result['chat_response']
    assert 'Город бизнеса не подтверждает регион' in result['chat_response']


def test_preview_refresh_does_not_route_to_stored_reviews():
    assert operator_query.read_reviews_request(None, 'root', 'Покажи стоимость обновления отзывов до запуска') is None


def test_compound_service_read_does_not_return_profile_explanation():
    assert not classify_product_explanation_intent('Покажи текущие услуги выбранного бизнеса и объясни, доступен ли предварительный просмотр')


def test_review_refresh_preview_is_read_only(monkeypatch):
    monkeypatch.setattr(operator_search_demand, 'query_business_ids', lambda *args: ['branch'])
    monkeypatch.setattr('services.operator_map_refresh.build_operator_map_refresh_plan', lambda *args, **kwargs: {'business_id': 'branch', 'url': 'https://yandex.ru/maps/org/demo', 'blocked_reasons': []})
    result = operator_search_demand.review_refresh_preview(None, 'root', 'user')
    assert 'Обновление пока не запущено' in result['chat_response']
    assert result['paid_actions_performed'] is False
    assert result['external_calls_performed'] is False
