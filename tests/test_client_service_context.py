from services.client_service_context import service_context,SERVICE_CONTEXT_BYTES

def test_large_catalog_is_ranked_and_bounded():
    services=[{'name':f'Пилинг вариант {i}','description':'текст '*500,'price':100+i} for i in range(683)]
    services.append({'name':'Лазерная эпиляция ног','price':2400,'description':'Удаление волос'})
    text=service_context(services,'Сколько стоит лазерная эпиляция?',[])
    assert 'Лазерная эпиляция ног' in text
    assert 'Пилинг' not in text
    assert len(text.encode()) <= SERVICE_CONTEXT_BYTES

def test_generic_question_asks_for_clarification_without_full_catalog():
    text=service_context([{'name':'Маникюр','price':1000}],'Здравствуйте! Какие услуги у вас есть?',[])
    assert 'Уточни' in text
    assert '1000' not in text

def test_follow_up_uses_recent_client_subject():
    text=service_context([{'name':'Маникюр','price':1000}], 'А сколько стоит?', [{'role':'client','content':'Хочу маникюр'}])
    assert 'Маникюр' in text and '1000' in text

def test_many_matches_respect_byte_bound():
    text=service_context([{'name':'Массаж '+('я'*240),'description':'я'*1000} for _ in range(683)],'Массаж',[])
    assert len(text.encode())<=SERVICE_CONTEXT_BYTES
