from services.operator_outreach_read_request import letter_request

ID = 'e361ce95-586a-441f-a167-455805fdb5ed'


def test_explicit_read_uses_exact_task_instead_of_conversation_copy():
    assert letter_request(f'Для Riderra покажи полные тексты писем задачи {ID}. Ничего не меняй и не отправляй.') == {'operation': 'letters', 'task_id': ID}
    assert letter_request('Покажи письма')['operation'] == 'letters'


def test_write_requests_and_multiple_task_ids_do_not_select_arbitrary_task():
    assert letter_request('Подготовь письма') is None
    assert letter_request('Отправь письма') is None
    assert letter_request(f'Покажи письма {ID} и 00000000-0000-0000-0000-000000000000')['ambiguous']
