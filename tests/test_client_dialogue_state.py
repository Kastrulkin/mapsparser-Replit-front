from services.client_dialogue_state import next_state,preview_state

def test_stages_follow_customer_intent():
    state=next_state('greeting','Здравствуйте')
    assert state=='clarify_need'
    state=next_state(state,'Хочу массаж спины')
    assert state=='service_selection'
    state=next_state(state,'Сколько стоит?')
    assert state=='answer_question'
    assert next_state(state,'Спасибо')=='closing'

def test_booking_and_human_request_pause_for_staff():
    assert next_state('answer_question','Позовите сотрудника')=='waiting_for_staff'
    assert next_state('service_selection','Хочу записаться')=='booking_request'
    assert next_state('human_active','Сколько стоит?')=='human_active'
    assert next_state('waiting_for_staff','Здравствуйте')=='waiting_for_staff'

def test_preview_replays_without_state_writes():
    assert preview_state([{'role':'client','content':'Хочу массаж'}],'Сколько стоит?')=='answer_question'

def test_greeting_does_not_select_a_service():
    assert next_state('greeting','Добрый вечер!')=='clarify_need'
