from services.operator_tool_loop import run_operator_tool_loop
import pytest


def test_read_only_request_cannot_call_write_even_if_planner_asks():
    writes = []
    tools = [
        {'name': 'content.update_item_fields', 'risk_class': 'write_internal_draft',
         'input_schema': {'type': 'object', 'properties': {}},
         'execute': lambda args: writes.append(args) or {'status': 'completed'}},
        {'name': 'content.channel_posts', 'risk_class': 'read_only',
         'input_schema': {'type': 'object', 'properties': {}},
         'execute': lambda args: {'status': 'completed', 'posts': []}},
    ]
    steps = iter([
        {'action': 'tool_call', 'tool': 'content.update_item_fields', 'arguments': {}},
        {'action': 'tool_call', 'tool': 'content.channel_posts', 'arguments': {}},
        {'action': 'final', 'message': 'Сохранил правки поста.'},
    ])
    result = run_operator_tool_loop(business_id='b', user_id='u',
        message='Проверь посты. Только чтение, ничего не меняй и не публикуй.',
        tools=tools, planner=lambda state: next(steps))
    assert writes == []
    assert not result['chat_response'].startswith('Сохранил')
    assert result['external_writes_performed'] is False


@pytest.mark.parametrize('message', [
    'Сохрани мой текст поста.',
    'Сохрани мой текст поста, но ничего не публикуй и не отправляй.',
])
def test_explicit_edit_remains_available_outside_read_only_mode(message):
    writes = []
    tool = {'name': 'content.update_item_fields', 'risk_class': 'write_internal_draft',
            'input_schema': {'type': 'object', 'properties': {}},
            'execute': lambda args: writes.append(args) or {'status': 'completed'}}
    steps = iter([
        {'action': 'tool_call', 'tool': tool['name'], 'arguments': {}},
        {'action': 'final', 'message': 'Правка сохранена.'},
    ])
    run_operator_tool_loop(business_id='b', user_id='u', message=message,
        tools=[tool], planner=lambda state: next(steps))
    assert writes == [{}]


@pytest.mark.parametrize('risk_class', ['write_internal_draft', 'write_external', None, 'unknown'])
def test_read_only_blocks_non_read_tools_and_approval(risk_class):
    calls = []
    tool = {'name': 'test.change', 'risk_class': risk_class,
            'input_schema': {'type': 'object', 'properties': {}},
            'approval_required': True,
            'prepare_approval': lambda args: calls.append('approval') or {},
            'execute': lambda args: calls.append('execute') or {}}
    steps = iter([
        {'action': 'tool_call', 'tool': tool['name'], 'arguments': {}},
        {'action': 'final', 'message': 'Проверка завершена.'},
    ])
    run_operator_tool_loop(business_id='b', user_id='u', message='Только чтение.',
        tools=[tool], planner=lambda state: next(steps))
    assert calls == []
