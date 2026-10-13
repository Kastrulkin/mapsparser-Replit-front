"""Exercise the queue handler without importing unrelated API integrations."""
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock


def handler(args, business='business'):
    source = Path(__file__).parents[1] / 'src/api/outreach_campaign_api.py'
    tree = ast.parse(source.read_text())
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                    and node.name == 'get_outreach_message_queue')
    function.decorator_list = []
    cursor = Mock(); cursor.fetchall.return_value = []
    connection = Mock(); connection.cursor.return_value = cursor
    namespace = {
        'request': SimpleNamespace(args=args), 'jsonify': lambda payload: payload,
        '_require_auth': lambda: ({'is_superadmin': True}, None),
        '_resolve_business_for_user': lambda *arguments: business,
        'get_db_connection': lambda: connection, 'RealDictCursor': object,
    }
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), namespace)
    return namespace['get_outreach_message_queue'], cursor, connection


def test_selected_task_lists_its_campaign_even_if_another_task_has_newer_version(monkeypatch):
    import services.partnership_group_view as groups
    scope = Mock(return_value=['reviewed-campaign'])
    monkeypatch.setattr(groups, 'message_campaign_scope', scope)
    run, cursor, connection = handler({'business_id': 'business', 'search_task_id': 'task'})
    assert run()['items'] == []
    query, params = cursor.execute.call_args.args
    assert 'ranked.id::text = ANY(%s::text[])' in query
    assert 'ranked.campaign_rank = 1' not in query
    assert params == (['reviewed-campaign'], 'business')
    scope.assert_called_once_with(cursor, 'business', 'task')
    connection.close.assert_called_once()


def test_empty_task_list_never_reads_historical_company_campaigns(monkeypatch):
    import services.partnership_group_view as groups
    monkeypatch.setattr(groups, 'message_campaign_scope', lambda *args: [])
    run, cursor, _ = handler({'business_id': 'business', 'search_task_id': 'task'})
    assert run()['summary'] == {'all': 0}
    assert cursor.execute.call_args.args[1] == ([], 'business')


def test_business_access_is_checked_before_group_lookup(monkeypatch):
    import services.partnership_group_view as groups
    scope = Mock(); monkeypatch.setattr(groups, 'message_campaign_scope', scope)
    run, cursor, _ = handler({'business_id': 'foreign', 'search_task_id': 'task'}, business=None)
    assert run()[1] == 403
    scope.assert_not_called(); cursor.execute.assert_not_called()


def test_all_groups_view_preserves_latest_campaign_behavior():
    run, cursor, _ = handler({})
    assert run()['total'] == 0
    assert 'ranked.campaign_rank = 1' in cursor.execute.call_args.args[0]
