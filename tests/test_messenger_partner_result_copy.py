from services.telegram_dashboard import format_operator_chat_result_for_telegram


def test_partner_letter_is_not_formatted_like_map_review_replies():
    text = 'Партнёр: QA.\n\nПисьмо · Эл. почта · Черновик\nПроверенный текст.\n\nПросмотр не отправляет письма.'
    result = {'capability': 'partnerships.read', 'status': 'completed', 'chat_response': text,
              'drafts': [{'generated_text': 'Старый необработанный текст.'}]}
    shown = format_operator_chat_result_for_telegram(result)
    assert shown.startswith(text)
    assert 'Ответ 1' not in shown
    assert 'Публикация в карты' not in shown
    assert 'Старый необработанный' not in shown


def test_real_bulk_review_result_still_shows_review_drafts_and_manual_boundary():
    shown = format_operator_chat_result_for_telegram({'intent': 'bulk_review_replies_generate',
        'chat_response': 'Подготовлены ответы.', 'drafts': [{'generated_text': 'Спасибо за отзыв.'}]})
    assert 'Ответ 1' in shown
    assert 'Спасибо за отзыв.' in shown
    assert 'Публикация в карты остаётся ручной' in shown
