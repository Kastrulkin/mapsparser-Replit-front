"""Both messenger entries share one durable approval and one changed result."""
import pytest
from tests import test_operator_voice_pg
from tests.test_operator_editorial_pg import editorial, focus_args, target


@pytest.fixture
def pg(postgres_container, monkeypatch, tmp_path):
    dsn = postgres_container.get_connection_url().replace('postgresql+psycopg2://', 'postgresql://')
    monkeypatch.setenv('OPERATOR_VOICE_TEST_DSN', dsn)
    yield from test_operator_voice_pg.pg.__wrapped__(monkeypatch, tmp_path)


@pytest.mark.parametrize('origin', ['telegram', 'max_bot', 'max_mini_app'])
def test_confirming_same_action_from_both_entries_changes_it_once(editorial, origin):
    from services import operator_core, operator_editorial
    from services.operator_conversations import create_pending_operator_action, get_or_create_operator_conversation
    connection, cursor = editorial
    preview = operator_editorial.prepare_focus(cursor, 'b', 'u', 'Нужен акцент на семейных поездках', focus_args(cursor))
    conversation = get_or_create_operator_conversation(cursor, business_id='b', user_id='u', channel=origin)
    action = create_pending_operator_action(cursor, conversation_id=conversation['id'], business_id='b', user_id='u',
        capability='content.plan.refocus', envelope=preview['approval']['envelope'], request_key='shared-review')
    first, duplicate = operator_core.confirm_pending_operator_action(cursor, action_id=action['id'], business_id='b', user_id='u')
    connection.commit()
    assert first['status'] == 'completed' and not duplicate
    second, duplicate = operator_core.confirm_pending_operator_action(cursor, action_id=action['id'], business_id='b', user_id='u')
    assert duplicate and second['changed_count'] == 2
    assert len(target(cursor)['metadata_json']['operator_edit_history']) == 1
