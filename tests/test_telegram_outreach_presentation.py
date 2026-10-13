from services.telegram_outreach_presentation import is_outreach_result, summary, messages


def fixture():
    return {'chat_response': 'Long duplicated original', 'task': {'display_name': 'Search',
        'report': {'found': 3, 'eligible': 2, 'target': 3, 'prepared': 2, 'credits_charged': 7},
        'presentation': {'label': 'Требуется действие', 'next_action': {'label': 'Проверить письма'}},
        'state': {'campaign_results': {'ws': {'campaign_id': 'b', 'status': 'needs_revision'}}}},
        'drafts': [{'campaign_id': 'a', 'status': 'draft', 'generated_text': 'First canonical body'},
                   {'campaign_id': 'b', 'status': 'draft', 'generated_text': 'Second canonical body'}]}


def test_summary_does_not_duplicate_bodies_or_show_map_instructions():
    result = fixture()
    assert is_outreach_result(result)
    text = summary(result)
    assert 'Подходят: 2/3' in text and '7 кр.' in text
    assert 'canonical body' not in text and 'карт' not in text


def test_letters_are_separate_cards_with_canonical_body_once_and_readable_status():
    cards = messages(fixture())
    assert len(cards) == 3
    assert sum(card.count('First canonical body') for card in cards) == 1
    assert sum(card.count('Second canonical body') for card in cards) == 1
    assert 'Нужна правка' in cards[2]
    assert 'draft' not in '\n'.join(cards)


def test_review_drafts_are_not_outreach():
    assert not is_outreach_result({'drafts': [{'reply_text': 'Review answer'}]})
    assert 'пока неизвестно' in summary({'task': {}})


def formatter():
    import ast
    from pathlib import Path
    source = Path('src/services/telegram_dashboard.py').read_text()
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef)
                and n.name == '_format_operator_chat_result_for_telegram')
    namespace = {'Any': object, 'format_bulk_review_reply_result_for_telegram': lambda result: 'Review only'}
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<actual Telegram formatter>', 'exec'), namespace)
    return namespace[node.name]


def test_actual_formatter_does_not_dispatch_email_drafts_to_review_renderer():
    assert formatter()(fixture()) == summary(fixture())
    assert formatter()({'drafts': [{'reply_text': 'Review answer'}]}) == 'Review only'
