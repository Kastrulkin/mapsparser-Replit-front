from services.operator_context import PlannerContext


def test_references_in_reply_are_restored_without_prefix_collision():
    context = PlannerContext('Покажи посты')
    identifiers = [f'00000000-0000-0000-0000-{index:012d}' for index in range(12)]
    encoded = context.encode(identifiers)
    reply = f'plan_id: {encoded[1]}; item_id: {encoded[10]}. Неизвестно: @ref199'
    assert context.decode({'message': reply}) == {'message':
        f'plan_id: {identifiers[1]}; item_id: {identifiers[10]}. Неизвестно: @ref199'}
    assert PlannerContext('Другой запрос').decode(reply) == reply


def test_references_restore_inside_scoped_content_link():
    context = PlannerContext('Покажи пост')
    identifier = '00000000-0000-0000-0000-000000000001'
    ref = context.encode(identifier)
    assert context.decode(f'/dashboard/content?plan_id={ref}') == f'/dashboard/content?plan_id={identifier}'
