from services.telegram_response_router import classify_client_intent, classify_guest_intent
from services.telegram_static_answers import (
    ask_localos_intro_text,
    guest_about_text,
    guest_compare_text,
    tariff_detail_text,
    guest_tariffs_text,
)


def test_guest_intent_tariffs():
    assert classify_guest_intent("Как оплатить подписку?") == "tariffs"


def test_guest_intent_about():
    assert classify_guest_intent("Что умеет LocalOS?") == "about"


def test_client_intent_today():
    assert classify_client_intent("Что делать сегодня?") == "today"


def test_client_intent_card():
    assert classify_client_intent("Где посмотреть аудит карточки?") == "card"


def test_client_intent_automation():
    assert classify_client_intent("Что можно автоматизировать?") == "automation"


def test_static_tariffs_mentions_cabinet_payment():
    text = guest_tariffs_text()
    assert "Оплата" in text
    assert "Telegram" in text


def test_static_about_mentions_growth_system():
    text = guest_about_text()
    assert "карточку" in text or "карточка" in text
    assert "автоматизацию" in text


def test_ask_localos_intro_has_examples():
    text = ask_localos_intro_text()
    assert "что делать сегодня" in text
    assert "как оплатить подписку" in text


def test_guest_compare_text_mentions_step_flow():
    text = guest_compare_text().lower()
    assert "сначала вашу карточку" in text
    assert "потом карточку конкурента" in text


def test_tariff_detail_text_mentions_monthly_price_and_cabinet():
    text = tariff_detail_text("starter").lower()
    assert "₽/мес" in text
    assert "кабинет" in text


def test_today_in_specific_tasks_does_not_open_home_summary():
    for message in (
        'Теперь покажи планёрку Органики на сегодня: фокус дня и задачи. Ничего сотрудникам не отправляй и не создавай новую планёрку.',
        'Создай пост на сегодня',
        'За сегодня выручка 50000 рублей, 20 чеков',
        'Покажи партнёров на сегодня',
    ):
        assert classify_client_intent(message) != 'today'


def test_standalone_today_still_opens_home_summary():
    for message in ('Сегодня', 'На сегодня?', 'Что делать сегодня?', 'Что требует моего внимания сегодня?'):
        assert classify_client_intent(message) == 'today'
