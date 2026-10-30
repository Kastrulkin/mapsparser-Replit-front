from unittest.mock import MagicMock, patch
from ai_agent import process_message


def test_paused_incoming_is_saved_without_ai_or_unconfirmed_response_time():
    db=MagicMock();db.conn.cursor.return_value.fetchone.return_value=('waiting_for_staff','[]',1)
    with patch('ai_agent.DatabaseManager',return_value=db),patch('ai_agent.get_or_create_conversation',return_value='test'),patch('ai_agent.get_business_info',return_value={}),patch('ai_agent.get_business_services',return_value=[]),patch('ai_agent.get_agent_config',return_value={}),patch('ai_agent.save_message') as save,patch('ai_agent.get_gigachat_client') as model:
        result=process_message('business','test-handoff:check','Internal test','Пожелание после передачи')
    assert result['agent_paused'] is True
    assert result['state']=='waiting_for_staff'
    assert 'Срок ответа пока не подтверждён' in result['response']
    save.assert_called_once_with('test','text','Пожелание после передачи','client')
    model.assert_not_called()
