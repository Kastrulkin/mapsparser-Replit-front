import pytest
from services.operator_fresh_reviews import classify_fresh_reviews_intent


@pytest.mark.parametrize('message', [
    'Перепроверь сохранённые посты, читай сохранённые данные. Только чтение, ничего не меняй.',
    'Проверь данные карточки. Только чтение.',
    'Проверь свежие данные. Read-only.',
])
def test_read_only_cannot_trigger_paid_map_refresh(message):
    assert not classify_fresh_reviews_intent(message)


def test_explicit_refresh_is_still_supported():
    assert classify_fresh_reviews_intent('Обнови данные карточки')
