import telegram_bot
from services.telegram_static_answers import guest_welcome_text, tariff_detail_text
from services import telegram_dashboard
from services.telegram_response_router import classify_client_intent
from telegram_bot import (
    _build_guest_audit_result_menu,
    _build_guest_compare_result_menu,
    _build_guest_more_menu,
    _request_public_report_from_telegram,
    _build_subscription_menu,
    _suggested_upgrade_tier,
)


def test_subscription_upgrade_prompt_for_trial_mentions_starter() -> None:
    text = telegram_dashboard._subscription_upgrade_prompt(
        {"tier": "trial", "status": "inactive"},
        {"trial_expired": False, "automation_access": False},
    )
    assert "starter" in text.lower()


def test_subscription_upgrade_prompt_for_starter_mentions_professional() -> None:
    text = telegram_dashboard._subscription_upgrade_prompt(
        {"tier": "starter", "status": "active"},
        {"automation_access": True},
    )
    assert "professional" in text.lower()


def test_suggested_upgrade_tier_maps_promo_to_supported_tariff() -> None:
    result = _suggested_upgrade_tier({"business_id": "", "tier": "promo"})
    assert result == "starter"


def test_suggested_upgrade_tier_maps_existing_promo_subscription_to_concierge(monkeypatch) -> None:
    monkeypatch.setattr(
        telegram_bot,
        "get_subscription_info",
        lambda business_id: {"tier": "promo", "status": "active"},
    )

    result = _suggested_upgrade_tier({"business_id": "biz-1", "tier": "promo"})
    assert result == "concierge"


def test_subscription_menu_opens_full_tariff_list_from_pick_tariff() -> None:
    markup = _build_subscription_menu({"business_id": "", "tier": "trial"})
    rows = markup.inline_keyboard

    assert rows[2][0].callback_data == "tariff_info_starter"
    assert rows[3][0].callback_data == "client_tariffs"
    assert rows[4][0].callback_data == "client_tariffs"


def test_guest_welcome_sells_free_audit_and_price_anchor() -> None:
    text = guest_welcome_text()

    assert "Бесплатный аудит" in text
    assert "1200 ₽/мес" in text
    assert "10 и более раз дешевле агентства" in text
    assert "Пришлите ссылку" in text


def test_guest_more_menu_does_not_push_account_connection_too_early() -> None:
    markup = _build_guest_more_menu()
    labels = [button.text for row in markup.inline_keyboard for button in row]

    assert "🧩 Подключить аккаунт LocalOS" not in labels
    assert "✨ Что будет после аудита" in labels
    assert "💳 Тарифы и цена входа" in labels


def test_guest_audit_result_menu_has_post_audit_cta() -> None:
    markup = _build_guest_audit_result_menu("https://localos.pro/audit")
    labels = [button.text for row in markup.inline_keyboard for button in row]

    assert "📊 Открыть аудит" in labels
    assert "🛠 Исправить это в LocalOS" in labels
    assert "💳 Посмотреть Starter за 1200 ₽" in labels
    assert "🧩 Подключить LocalOS" in labels


def test_guest_audit_start_does_not_send_report_link_before_ready(monkeypatch) -> None:
    monkeypatch.setattr(
        telegram_bot,
        "_start_public_report_request",
        lambda telegram_id, normalized_url, source_name="": (
            True,
            {
                "public_url": "https://localos.pro/audit",
                "slug": "audit",
                "normalized_url": normalized_url,
                "source_name": source_name,
            },
        ),
    )

    ok, text = _request_public_report_from_telegram(
        "123",
        "https://yandex.com/maps/org/ryad/205932220769/reviews",
    )

    assert ok is True
    assert "Я напишу сюда, когда аудит будет готов" in text
    assert "https://localos.pro/audit" not in text
    assert "Страница аудита" not in text


def test_guest_compare_result_menu_sells_fixing_the_gap() -> None:
    markup = _build_guest_compare_result_menu("https://localos.pro/a", "https://localos.pro/b")
    labels = [button.text for row in markup.inline_keyboard for button in row]

    assert "🛠 Исправить разрыв в LocalOS" in labels
    assert "💳 Starter за 1200 ₽" in labels
    assert "🧩 Подключить LocalOS" in labels


def test_starter_copy_positions_tariff_as_path_from_audit_to_fix() -> None:
    text = tariff_detail_text("starter")

    assert "самый короткий путь от бесплатного аудита к исправлениям" in text
    assert "1200 ₽/мес" in text
    assert "10 и более раз дороже" in text


def test_operator_attention_text_keeps_paid_actions_manual_and_cached() -> None:
    text = telegram_dashboard._format_operator_attention_text(
        {
            "business": {"name": "Салон LocalOS"},
            "summary": {"text": "Нашёл 2 пункта по последним сохранённым данным."},
            "metrics": {
                "reviews_without_response": 2,
                "pending_approvals": 1,
                "pending_news": 0,
                "review_reply_drafts": 1,
                "partnership_leads_ready": 0,
            },
            "freshness": {
                "latest_card_at": "2026-05-20T10:00:00+00:00",
                "card_age_days": 0,
            },
            "items": [
                {
                    "title": "Отзывы без ответа",
                    "description": "Это последние сохранённые данные.",
                    "count": 2,
                    "action_class": "free_cached",
                },
                {
                    "title": "Данные карт стоит обновить",
                    "description": "Обновление карт относится к платным внешним действиям.",
                    "count": 0,
                    "action_class": "paid_external",
                },
            ],
            "paid_action_offers": [
                {
                    "copy": {
                        "primary": "Могу показать последние известные данные бесплатно. Или обновить карты сейчас — платно.",
                        "disclosure": "Точная стоимость появится после оценки. До согласия платные действия не выполняются.",
                    }
                }
            ],
        }
    )

    assert "LocalOS Operator" in text
    assert "последним сохранённым данным" in text
    assert "Могу показать последние известные данные бесплатно" in text
    assert "Платные действия не выполнялись" in text
    assert "Публикация ответов в карты сейчас ручная" in text
    assert "платное обновление данных" in text


def test_client_intent_recognizes_operator_attention_request() -> None:
    assert classify_client_intent("Что требует моего внимания сегодня?") == "today"


def test_client_intent_recognizes_refresh_jobs_followup() -> None:
    assert classify_client_intent("Покажи статус обновлений отзывов") == "refresh_jobs"
    assert classify_client_intent("Проверить результат обновления") == "refresh_jobs"


def test_operator_refresh_jobs_text_keeps_publication_manual() -> None:
    text = telegram_dashboard._format_operator_refresh_jobs_text(
        {
            "summary": {
                "text": "Последние read-only обновления карт.",
                "jobs_count": 2,
                "processing_count": 1,
                "completed_count": 1,
                "failed_count": 0,
                "new_reviews_count": 2,
                "new_unanswered_reviews_count": 1,
            },
            "jobs": [
                {
                    "status": "completed",
                    "queue_status": "completed",
                    "created_at": "2026-05-24T10:00:00+00:00",
                    "new_reviews_count": 2,
                    "new_unanswered_reviews_count": 1,
                    "reliability_state": {
                        "status": "failed",
                        "title": "Таймаут парсинга",
                        "reason_code": "timeout",
                        "next_step": "Проверьте ссылку и повторите обновление позже.",
                    },
                    "new_reviews": [
                        {
                            "author_name": "Анна",
                            "text": "Очень понравился сервис, обязательно вернусь.",
                            "has_response": False,
                        }
                    ],
                }
            ],
        }
    )

    assert "Обновления отзывов" in text
    assert "В работе: 1" in text
    assert "Новых отзывов: 2" in text
    assert "Анна" in text
    assert "Надёжность: Таймаут парсинга (timeout)" in text
    assert "подготовь ответы на отзывы" in text
    assert "публикация в карты остаётся ручной" in text.lower()
