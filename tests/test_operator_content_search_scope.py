from services.operator_tool_loop import run_operator_tool_loop


def test_search_reads_all_plans_before_using_previous_conversation():
    calls = []
    tool = {'name': 'content.editorial_context', 'risk_class': 'read_only',
            'input_schema': {'type': 'object', 'properties': {}},
            'execute': lambda args: calls.append(args) or {'status': 'completed',
                'items': [{'id': 'old-item', 'plan_id': 'old'}, {'id': 'new-item', 'plan_id': 'new'}]}}

    def planner(state):
        assert state['observations'][0]['tool'] == 'content.editorial_context'
        assert len(state['observations'][0]['items']) == 2
        return {'action': 'final', 'message': 'Нашёл две записи.'}

    run_operator_tool_loop(business_id='b', user_id='u',
        message='Найди будущие посты без версии Google. Только чтение.',
        conversation_history=[{'role': 'assistant', 'content': 'Выбран новый план.'}],
        tools=[tool], planner=planner)
    assert calls == [{}]


def test_edit_does_not_eagerly_search_or_change_selected_target():
    calls = []
    tool = {'name': 'content.editorial_context', 'risk_class': 'read_only',
            'execute': lambda args: calls.append(args)}
    run_operator_tool_loop(business_id='b', user_id='u', message='Сохрани текст поста',
        tools=[tool], max_steps=1,
        planner=lambda state: {'action': 'clarification', 'message': 'Какой пост?'})
    assert calls == []


def test_failed_context_cannot_be_reported_as_no_posts():
    def unavailable(args):
        raise PermissionError('not authorised')
    result = run_operator_tool_loop(business_id='b', user_id='u', message='Покажи посты',
        tools=[{'name':'content.editorial_context','risk_class':'read_only','execute':unavailable}],
        planner=lambda state: {'action':'final','message':'Постов нет.'})
    assert result['status'] == 'error'
    assert result['planner_steps'] == 0
    assert 'Полнота поиска не подтверждена' in result['chat_response']
