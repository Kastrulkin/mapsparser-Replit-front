from services import operator_core, operator_query


def setup_items(monkeypatch):
    items = [{'title': f'Пост {n}', 'scheduled_for': f'2026-09-{n:02}', 'status': 'edited', 'draft_text': 'Длинный текст ' * 100} for n in range(1,14)]
    monkeypatch.setattr(operator_query, '_load_module_items', lambda *args, **kwargs: (items, {}))


def test_last_means_latest_date_not_next_future(monkeypatch):
    setup_items(monkeypatch)
    result = operator_core._read_requested_content(None, 'b', 'Покажи последний пост в контент плане')
    assert len(result['items']) == 1
    assert result['items'][0]['title'] == 'Пост 13'
    assert 'Длинный текст' in result['chat_response']


def test_plan_is_compact_complete_schedule(monkeypatch):
    setup_items(monkeypatch)
    result = operator_core._read_requested_content(None, 'b', 'Пришли контент план')
    assert len(result['items']) == 13
    assert 'Пост 13' in result['chat_response'] and 'Пост 1' in result['chat_response']
    assert 'Длинный текст' not in result['chat_response']
    assert len(result['chat_response']) < 3500


def test_read_phrasings_and_publish_boundary():
    for message in ['Пришли контент-план', 'Контент план', 'Покажи последний пост', 'Какой последний пост в контент плане', 'Покажи крайний пост в плане']:
        assert operator_core._content_read_request(message), message
    for message in ['Опубликуй последний пост', 'Создай контент план', 'Отправь пост в канал', 'Покажи опубликованные вчера посты']:
        assert not operator_core._content_read_request(message), message
