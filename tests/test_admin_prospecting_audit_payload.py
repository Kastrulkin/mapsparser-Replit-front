from src.api import admin_prospecting
from src.api.admin_prospecting import (
    _build_admin_lead_offer_payload,
    _build_deterministic_dense_audit_enrichment,
    _build_compact_outreach_payload,
    _generate_superadmin_deterministic_first_message,
    _generate_lead_audit_enrichment,
    _generate_audit_first_message_draft,
    _lead_has_channel_contact,
    _outreach_channel_contact_error,
    _resolve_outreach_language,
    _resolve_telegram_app_recipient,
    _classify_telegram_app_error,
    _classify_telegram_sync_error,
    _dispatch_outreach_queue_item,
    _sync_telegram_app_replies_for_queue_item,
)
from src.core.card_audit import (
    _build_card_baseline_action_plan,
    _build_card_baseline_issue_blocks,
    _build_beauty_issue_blocks,
    _build_default_local_business_action_plan,
    _build_default_local_business_issue_blocks,
    _build_fashion_issue_blocks,
    _build_fitness_issue_blocks,
    _build_food_issue_blocks,
    _build_medical_issue_blocks,
    _build_reasoning_fields,
    _build_wellness_issue_blocks,
    _extract_lead_import_payload,
    _format_ru_location_prepositional,
    _merge_action_plan,
    _merge_issue_blocks,
    _normalize_generated_location_phrases,
)


def test_build_admin_lead_offer_payload_exposes_current_state_top_level_facts() -> None:
    payload = _build_admin_lead_offer_payload(
        lead={
            "id": "lead-1",
            "name": "Girlie",
            "city": "Санкт-Петербург",
            "address": "Санкт-Петербург, Каменноостровский проспект, 34",
            "category": "Салон красоты",
            "source_url": "https://yandex.ru/maps/org/girlie/123",
        },
        preview={
            "current_state": {
                "rating": 5.0,
                "reviews_count": 656,
                "services_count": 30,
                "photos_state": "good",
                "has_website": True,
                "has_recent_activity": True,
            },
            "preview_meta": {"photo_urls": ["https://example.com/1.jpg"]},
        },
        preferred_language="en",
        enabled_languages=["en", "tr"],
    )

    assert payload["rating"] == 5.0
    assert payload["reviews_count"] == 656
    assert payload["services_count"] == 30
    assert payload["photos_state"] == "good"
    assert payload["has_website"] is True
    assert payload["has_recent_activity"] is True


def test_extract_lead_import_payload_prefers_full_services_count_over_preview_len() -> None:
    payload = _extract_lead_import_payload(
        {
            "search_payload_json": {
                "menu_preview": [
                    {"title": f"Услуга {index}", "price": "1000", "category": "preview"}
                    for index in range(1, 31)
                ],
                "menu_full": [
                    {"title": f"Услуга {index}", "price": "1000", "category": "full"}
                    for index in range(1, 164)
                ],
                "services_total_count": 163,
                "services_with_price_count": 163,
            }
        }
    )

    assert payload["services_total_count"] == 163
    assert payload["services_with_price_count"] == 163
    assert len(payload["services_preview"]) == 20
    assert "Услуга 80 full" in " | ".join(payload["services_profile_names"])


def test_extract_lead_import_payload_uses_full_services_for_profile_names() -> None:
    payload = _extract_lead_import_payload(
        {
            "search_payload_json": {
                "menu_preview": [
                    {"title": f"Консультация врача невролога {index}", "price": "1000", "category": "Услуга"}
                    for index in range(1, 31)
                ],
                "menu_full": [
                    {"title": "Консультация врача гинеколога", "price": "2500", "category": "Услуга"},
                    {"title": "Консультация врача гастроэнтеролога", "price": "2500", "category": "Услуга"},
                    {"title": "Консультация врача дерматолога-венеролога", "price": "2500", "category": "Услуга"},
                    {"title": "Консультация врача кардиолога", "price": "2500", "category": "Услуга"},
                    {"title": "Консультация врача отоларинголога", "price": "2000", "category": "Услуга"},
                    {"title": "Консультация врача офтальмолога", "price": "2000", "category": "Услуга"},
                ],
                "services_total_count": 6,
                "services_with_price_count": 6,
            }
        }
    )

    profile_names = " | ".join(payload["services_profile_names"])
    assert "Консультация врача гастроэнтеролога" in profile_names
    assert profile_names.count("Консультация врача невролога") == 0


def test_extract_lead_import_payload_marks_preview_limited_services() -> None:
    payload = _extract_lead_import_payload(
        {
            "search_payload_json": {
                "menu_preview": [
                    {"title": f"Услуга {index}", "price": "1000", "category": "preview"}
                    for index in range(1, 31)
                ],
                "services_total_count": 30,
                "services_with_price_count": 30,
            }
        }
    )

    assert payload["services_total_count"] == 30
    assert payload["services_preview_limited"] is True


def test_extract_lead_import_payload_normalizes_description_city_from_address() -> None:
    payload = _extract_lead_import_payload(
        {
            "address": "Санкт-Петербург, переулок Крылова, 2",
            "search_payload_json": {
                "menu_preview": [
                    {
                        "title": "БОТОКС от BLANZO",
                        "description": "Приходите к нам в Санкт-Петербург...",
                        "price": "1000",
                    }
                ],
                "services_total_count": 1,
                "services_with_price_count": 1,
            },
        }
    )

    description = str(payload["services_preview"][0]["description"] or "")
    assert "в Санкт-Петербурге..." in description
    assert "в Санкт-Петербург..." not in description


def test_extract_lead_import_payload_keeps_profile_names_beyond_ui_preview() -> None:
    payload = _extract_lead_import_payload(
        {
            "search_payload_json": {
                "menu_preview": [
                    {"title": f"Дерматология услуга {index}", "price": "1000", "category": "Дерматология"}
                    for index in range(1, 24)
                ] + [
                    {"title": "Контурная пластика", "price": "600", "category": "Косметология - Контурная пластика"}
                ],
            }
        }
    )

    assert len(payload["services_preview"]) == 20
    assert any("Косметология" in item for item in payload["services_profile_names"])


def test_beauty_reasoning_uses_service_specific_intents() -> None:
    reasoning = _build_reasoning_fields(
        audit_profile="beauty",
        business_name="Girlie",
        city="Санкт-Петербург",
        address="Санкт-Петербург, Каменноостровский проспект, 34",
        overview_text="Студия маникюра и лазерной эпиляции",
        services_count=12,
        has_description=True,
        photos_count=20,
        reviews_count=100,
        unanswered_reviews_count=0,
        service_names=["Маникюр с покрытием", "Лазерная эпиляция", "Оформление бровей"],
    )

    intents = reasoning.get("search_intents_to_target") or []
    joined = " | ".join(intents)
    assert "маникюр" in joined
    assert "лазерная эпиляция" in joined


def test_medical_reasoning_uses_service_specific_intents() -> None:
    reasoning = _build_reasoning_fields(
        audit_profile="medical",
        business_name="Альбатрос",
        city="Санкт-Петербург",
        address="Санкт-Петербург, улица Олеко Дундича, 8",
        overview_text="Медцентр, клиника",
        services_count=30,
        has_description=True,
        photos_count=1,
        reviews_count=34,
        unanswered_reviews_count=0,
        service_names=[
            "Химическая деструкция подошвенной бородавки Дерматология",
            "Лазерная деструкция папилломы Дерматология",
            "Бледная трепонема, определение ДНК в соскобе кожи Дерматология - Анализы",
        ],
    )

    intents = reasoning.get("search_intents_to_target") or []
    joined = " | ".join(intents)
    assert "дерматолог Санкт-Петербург" in joined
    assert "удаление бородавок и папиллом Санкт-Петербург" in joined
    assert "невролог" not in joined
    best_fit = " | ".join(reasoning.get("best_fit_customer_profile") or [])
    assert "в Санкт-Петербурге" in best_fit
    assert "в Санкт-Петербург |" not in best_fit
    weak_fit = " | ".join(reasoning.get("weak_fit_customer_profile") or [])
    assert "с какими запросами сюда обращаться" in weak_fit
    assert "дерматолог" in weak_fit
    assert "формат приёма" in weak_fit


def test_medical_issue_blocks_use_ru_location_case() -> None:
    issues = _build_medical_issue_blocks(
        business_name="Альбатрос",
        city="Санкт-Петербург",
        has_description=False,
        services_count=30,
        priced_services_count=24,
        photos_count=1,
        reviews_count=34,
        unanswered_reviews_count=0,
    )

    evidence = " | ".join(str(item.get("evidence") or "") for item in issues)
    assert "в Санкт-Петербурге" in evidence
    assert "в Санкт-Петербург." not in evidence
    assert "нет сильного описания" not in evidence


def test_medical_issue_blocks_are_specific_for_multispecialty_clinic() -> None:
    issues = _build_medical_issue_blocks(
        business_name="Евромедсервис",
        city="Пушкин",
        has_description=False,
        services_count=37,
        priced_services_count=37,
        photos_count=1,
        reviews_count=95,
        unanswered_reviews_count=0,
        focus_terms=["медицинский центр", "консультации врачей", "гинеколог", "гастроэнтеролог"],
    )

    first_issue = issues[0]
    assert first_issue["title"] == "Описание не собирает направления клиники в понятный выбор"
    assert "в Пушкине" in first_issue["evidence"]
    assert "в Пушкин." not in first_issue["evidence"]
    assert "В прайсе 37 услуг с ценами" in first_issue["evidence"]
    assert "гинеколог" in first_issue["evidence"]
    assert "нет сильного описания" not in first_issue["evidence"]


def test_non_medical_issue_blocks_do_not_use_strong_description_water() -> None:
    default_issues = _build_default_local_business_issue_blocks(
        business_name="Новая Эра",
        city="Санкт-Петербург",
        has_description=False,
        services_count=30,
        priced_services_count=30,
        photos_count=1,
        reviews_count=78,
        unanswered_reviews_count=0,
    )
    beauty_issues = _build_beauty_issue_blocks(
        business_name="Орхидея",
        city="Пушкин",
        has_description=False,
        services_count=30,
        priced_services_count=30,
        photos_count=1,
        reviews_count=159,
        unanswered_reviews_count=0,
        focus_terms=["маникюр", "педикюр", "косметология"],
    )
    wellness_issues = _build_wellness_issue_blocks(
        business_name="Body Lab",
        city="Колпино",
        has_description=False,
        services_count=12,
        photos_count=3,
        reviews_count=42,
        unanswered_reviews_count=0,
    )
    fashion_issues = _build_fashion_issue_blocks(
        business_name="Atelier",
        city="Санкт-Петербург",
        has_description=False,
        services_count=12,
        priced_services_count=12,
        photos_count=3,
        reviews_count=42,
        news_count=0,
        has_recent_activity=False,
        is_verified=False,
    )
    food_issues = _build_food_issue_blocks(
        business_name="Кафе",
        city="Санкт-Петербург",
        has_description=False,
        services_count=12,
        priced_services_count=12,
        photos_count=3,
        reviews_count=42,
        unanswered_reviews_count=0,
    )
    fitness_issues = _build_fitness_issue_blocks(
        business_name="Фитнес",
        city="Санкт-Петербург",
        has_description=False,
        services_count=12,
        priced_services_count=12,
        photos_count=3,
        reviews_count=42,
        unanswered_reviews_count=0,
    )

    joined = " | ".join(
        str(item.get("evidence") or "")
        for item in default_issues + beauty_issues + wellness_issues + fashion_issues + food_issues + fitness_issues
    )
    assert "нет сильного" not in joined
    assert "SEO-описания" not in joined
    assert "fashion-описания" not in joined
    assert "food-описания" not in joined
    assert "fitness-описания" not in joined
    assert "в Санкт-Петербурге" in joined
    assert "в Пушкине" in joined
    assert "в Колпине" in joined
    assert _format_ru_location_prepositional("Колпино") == "Колпине"


def test_generated_service_descriptions_use_locative_city_form() -> None:
    text = "Приходите к нам в Санкт-Петербург... Запишем вас сегодня."

    result = _normalize_generated_location_phrases(text, "Санкт-Петербург")

    assert "в Санкт-Петербурге..." in result
    assert "в Санкт-Петербург..." not in result


def test_medical_reasoning_fallback_does_not_invent_neurologist() -> None:
    reasoning = _build_reasoning_fields(
        audit_profile="medical",
        business_name="Медцентр",
        city="Санкт-Петербург",
        address="",
        overview_text="Медцентр, клиника",
        services_count=0,
        has_description=False,
        photos_count=0,
        reviews_count=0,
        unanswered_reviews_count=0,
        service_names=[],
    )

    intents = reasoning.get("search_intents_to_target") or []
    joined = " | ".join(intents)
    assert "медицинский центр Санкт-Петербург" in joined
    assert "невролог" not in joined


def test_medical_reasoning_for_multispecialty_clinic_stays_broad() -> None:
    reasoning = _build_reasoning_fields(
        audit_profile="medical",
        business_name="Евромедсервис",
        city="Пушкин",
        address="Пушкин, Красносельское шоссе, 49",
        overview_text="Медцентр, клиника / диагностический центр / медицинская комиссия",
        services_count=36,
        has_description=True,
        photos_count=1,
        reviews_count=95,
        unanswered_reviews_count=0,
        service_names=[
            "Консультация врача гинеколога",
            "Консультация врача гастроэнтеролога",
            "Консультация врача дерматолога-венеролога",
            "Консультация врача кардиолога",
            "Консультация врача невролога",
            "Консультация врача онколога",
            "Консультация врача отоларинголога",
            "Консультация врача офтальмолога",
            "Консультация врача терапевта",
        ],
    )

    intents = reasoning.get("search_intents_to_target") or []
    joined = " | ".join(intents)
    assert "медицинский центр Пушкин" in joined
    assert "консультации врачей Пушкин" in joined
    assert "гинеколог Пушкин" in joined
    assert "гастроэнтеролог Пушкин" in joined
    assert "невролог Пушкин" not in joined


class _FakeCursor:
    def __init__(self) -> None:
        self._rows = []
        self._last_query = ""

    def execute(self, query, params=None) -> None:
        self._last_query = str(query)
        if "information_schema.columns" in self._last_query:
            self._rows = [
                {"column_name": "id"},
                {"column_name": "name"},
                {"column_name": "city"},
                {"column_name": "address"},
                {"column_name": "yandex_url"},
            ]
            return
        if "FROM businesses WHERE id = %s" in self._last_query:
            self._rows = [
                {
                    "id": "business-1",
                    "name": "Мечта",
                    "city": "",
                    "address": "Санкт-Петербург",
                    "yandex_url": "https://yandex.com/maps/org/platonova_kolorist/87626261151/",
                }
            ]
            return
        self._rows = []

    def fetchall(self):
        return list(self._rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _FakeDB:
    def __init__(self) -> None:
        self.conn = self
        self.cursor_obj = _FakeCursor()

    def cursor(self):
        return self.cursor_obj

    def close(self) -> None:
        return


def test_find_existing_business_for_lead_ignores_mismatched_explicit_business(monkeypatch) -> None:
    monkeypatch.setattr(admin_prospecting, "DatabaseManager", _FakeDB)

    lead = {
        "name": "Платонова колорист",
        "city": "Санкт-Петербург",
        "source_url": "https://yandex.com/maps/org/platonova_kolorist/87626261151/",
        "source_external_id": "87626261151",
        "business_id": "business-1",
    }

    business = admin_prospecting._find_existing_business_for_lead(lead)

    assert business is None


def test_generate_audit_first_message_draft_uses_public_audit_link_for_email() -> None:
    payload = _generate_audit_first_message_draft(
        lead={
            "name": "Апельсин",
            "preferred_language": "ru",
            "public_audit_url": "https://localos.pro/apelsin-kremenchugskaya-ulitsa?lang=ru",
        },
        preview={
            "findings": [{"title": "Карточка выглядит незавершённой"}],
            "recommended_actions": [{"title": "Добавить услуги"}],
            "revenue_potential": {"total_min": 30000, "total_max": 70000},
        },
        channel="email",
    )

    text = payload["generated_text"]
    assert "https://localos.pro/apelsin-kremenchugskaya-ulitsa?lang=ru" in text
    assert "недополучаете клиентов с карт" in text
    assert "Можем внедрить это под ключ" in text
    assert "₽" not in text
    assert "По нашей модели" not in text


def test_generate_audit_first_message_draft_does_not_include_money_hint() -> None:
    payload = _generate_audit_first_message_draft(
        lead={
            "name": "Комфорт",
            "preferred_language": "ru",
            "public_audit_url": "https://localos.pro/komfort?lang=ru",
        },
        preview={
            "findings": [{"title": "Описание карточки не продаёт ключевые услуги"}],
            "recommended_actions": [{"title": "Переписать описание"}],
            "revenue_potential": {"total_min": 13200, "total_max": 33600},
        },
        channel="email",
    )

    text = payload["generated_text"]
    assert "13200" not in text
    assert "33 600" not in text
    assert "₽" not in text
    assert "По нашей модели" not in text


def test_generate_superadmin_deterministic_first_message_uses_requested_template_shape() -> None:
    payload = _generate_superadmin_deterministic_first_message(
        {
            "name": "Апельсин",
            "public_audit_url": "https://localos.pro/apelsin-kremenchugskaya-ulitsa",
        },
        {
            "findings": [{"title": "Описание не всех услуг попадает в поиск"}],
        },
    )

    text = payload["generated_text"]
    assert "Здравствуйте!" in text
    assert "Нашёл Апельсин на картах - вижу, что у вас часть клиентов теряется." in text
    assert "Например, описание не всех услуг попадает в поиск." in text
    assert "https://localos.pro/apelsin-kremenchugskaya-ulitsa" in text
    assert "+30-80% к обращениям без рекламы." in text
    assert "Или, хотите, настрою всё, до результата?" in text
    assert payload["prompt_source"] == "deterministic"


def test_build_deterministic_dense_audit_enrichment_makes_summary_specific() -> None:
    payload = _build_deterministic_dense_audit_enrichment(
        {
            "name": "Апельсин",
            "category": "Салон красоты",
            "city": "Санкт-Петербург",
        },
        {
            "audit_profile": "beauty",
            "findings": [
                {"title": "Описание карточки не продаёт салон под реальный спрос"},
                {"title": "Фото не продают качество услуг и результат"},
                {"title": "Отзывы есть, но они не работают как маркетинговый актив"},
            ],
            "current_state": {
                "rating": 4.7,
                "reviews_count": 119,
                "services_count": 29,
                "services_with_price_count": 8,
                "photos_count": 1,
                "photos_state": "weak",
                "description_present": False,
                "has_website": True,
            },
            "recommended_actions": [
                {"title": "Описание карточки не продаёт салон под реальный спрос", "description": "Переписать описание."},
                {"title": "Фото не продают качество услуг и результат", "description": "Добавить фото работ."},
                {"title": "Отзывы есть, но они не работают как маркетинговый актив", "description": "Наладить ответы на отзывы."},
                {"title": "Карточке не хватает сигналов активности", "description": "Публиковать обновления."},
            ],
        },
        "ru",
    )

    assert payload["meta"]["prompt_version"] == "deterministic_dense_v2"
    assert payload["summary_text"].startswith("Описание карточки не продаёт салон под реальный спрос")
    assert "В первую очередь стоит" in payload["summary_text"]
    assert payload["why_now"]
    assert len(payload["recommended_actions"]) == 3


def test_resolve_outreach_language_defaults_to_russian_for_cyrillic_lead() -> None:
    language = _resolve_outreach_language(
        {
            "name": "Апельсин",
            "city": "Санкт-Петербург",
            "preferred_language": None,
        }
    )

    assert language == "ru"


def test_generate_lead_audit_enrichment_uses_ai_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        admin_prospecting,
        "_get_prompt_from_db",
        lambda prompt_type, fallback="": "Factual JSON: {factual_json}",
    )
    monkeypatch.setattr(
        admin_prospecting,
        "analyze_text_with_gigachat",
        lambda prompt, task_type=None: (
            '{"summary_text":"AI summary","recommended_actions":[{"title":"Action 1","description":"Do it"}],"why_now":"Now matters"}'
        ),
    )

    enrichment = _generate_lead_audit_enrichment(
        {"name": "Апельсин", "category": "Салон красоты", "city": "Санкт-Петербург"},
        {
            "summary_text": "Basic summary",
            "recommended_actions": [{"title": "Base action", "description": "Base description"}],
            "current_state": {"rating": 4.5, "reviews_count": 14, "services_count": 3},
        },
        "ru",
    )

    assert enrichment["summary_text"] == "AI summary"
    assert enrichment["recommended_actions"][0]["title"] == "Action 1"
    assert enrichment["meta"]["source"] == "gigachat"


def test_resolve_telegram_app_recipient_prefers_username() -> None:
    recipient = _resolve_telegram_app_recipient(
        {
            "telegram_url": "https://t.me/localos_support",
            "phone": "+79998887766",
        }
    )

    assert recipient == {
        "recipient_kind": "username",
        "recipient_value": "@localos_support",
    }


def test_resolve_telegram_app_recipient_falls_back_to_phone() -> None:
    recipient = _resolve_telegram_app_recipient(
        {
            "telegram_url": "",
            "phone": "79998887766",
        }
    )

    assert recipient == {
        "recipient_kind": "phone",
        "recipient_value": "+79998887766",
    }


def test_classify_telegram_app_error_marks_privacy_as_terminal() -> None:
    class PrivacyRestrictedError(Exception):
        pass

    code, retryable, message = _classify_telegram_app_error(PrivacyRestrictedError("You can't write in this chat"))

    assert code == "telegram_privacy_restricted"
    assert retryable is False
    assert "chat" in message


def test_classify_telegram_sync_error_marks_missing_peer_as_terminal() -> None:
    class PeerLookupError(Exception):
        pass

    code, retryable, message = _classify_telegram_sync_error(PeerLookupError("Cannot find any entity corresponding to \"+7999\""))

    assert code == "telegram_peer_not_found"
    assert retryable is False
    assert "entity" in message


def test_dispatch_outreach_queue_item_uses_telegram_app(monkeypatch) -> None:
    monkeypatch.setattr(
        admin_prospecting,
        "_dispatch_via_telegram_app",
        lambda item, message: {
            "success": True,
            "provider_name": "telegram_app",
            "provider_account_id": "acc-1",
            "recipient_kind": "username",
            "recipient_value": "@ola",
            "provider_message_id": "777",
        },
    )

    result = _dispatch_outreach_queue_item(
        {
            "id": "queue-1",
            "channel": "telegram",
            "selected_channel": "telegram",
            "approved_text": "Привет",
            "telegram_url": "https://t.me/ola",
        }
    )

    assert result["delivery_status"] == "sent"
    assert result["provider_name"] == "telegram_app"
    assert result["provider_account_id"] == "acc-1"
    assert result["recipient_value"] == "@ola"


def test_dispatch_outreach_queue_item_marks_telegram_app_missing_as_terminal(monkeypatch) -> None:
    monkeypatch.setattr(
        admin_prospecting,
        "_dispatch_via_telegram_app",
        lambda item, message: {
            "success": False,
            "provider_name": "telegram_app",
            "error_code": "telegram_app_missing",
            "error_text": "Telegram app is not configured",
            "retryable": False,
        },
    )

    result = _dispatch_outreach_queue_item(
        {
            "id": "queue-1",
            "channel": "telegram",
            "approved_text": "Привет",
        }
    )

    assert result["delivery_status"] == "failed"
    assert result["provider_name"] == "telegram_app"
    assert result["retryable"] is False
    assert "telegram_app_missing" in result["error_text"]


def test_sync_telegram_app_replies_for_queue_item_records_inbound_reaction(monkeypatch) -> None:
    monkeypatch.setattr(
        admin_prospecting,
        "_resolve_telegram_app_account",
        lambda account_id=None: {
            "account_id": account_id or "acc-1",
            "session_string": "session",
        },
    )
    monkeypatch.setattr(
        admin_prospecting,
        "_fetch_telegram_replies_subprocess",
        lambda *args, **kwargs: {
            "status": "ok",
            "replies": [
                {
                    "message_id": 901,
                    "text": "Да, интересно",
                    "created_at": "2026-04-17T10:00:00+00:00",
                }
            ],
        },
    )
    captured = {}

    def _fake_record_reaction(queue_id, raw_reply, outcome, note, user_id, **kwargs):
        captured["queue_id"] = queue_id
        captured["raw_reply"] = raw_reply
        captured["kwargs"] = kwargs
        return {"id": "reaction-1"}, None

    monkeypatch.setattr(admin_prospecting, "_record_reaction", _fake_record_reaction)

    result = _sync_telegram_app_replies_for_queue_item(
        {
            "id": "queue-1",
            "provider_account_id": "acc-1",
            "provider_message_id": "777",
            "recipient_value": "@ola",
            "sent_at": "2026-04-17T09:30:00+00:00",
        }
    )

    assert result["status"] == "imported"
    assert result["imported"] == 1
    assert captured["queue_id"] == "queue-1"
    assert captured["raw_reply"] == "Да, интересно"
    assert captured["kwargs"]["provider_name"] == "telegram_app"
    assert captured["kwargs"]["provider_message_id"] == "901"
    assert captured["kwargs"]["prefer_ai"] is False


def test_sync_telegram_app_replies_for_queue_item_counts_duplicate_as_noop(monkeypatch) -> None:
    monkeypatch.setattr(
        admin_prospecting,
        "_resolve_telegram_app_account",
        lambda account_id=None: {
            "account_id": account_id or "acc-1",
            "session_string": "session",
        },
    )
    monkeypatch.setattr(
        admin_prospecting,
        "_fetch_telegram_replies_subprocess",
        lambda *args, **kwargs: {
            "status": "ok",
            "replies": [
                {
                    "message_id": 901,
                    "text": "Да, интересно",
                    "created_at": "2026-04-17T10:00:00+00:00",
                }
            ],
        },
    )
    monkeypatch.setattr(
        admin_prospecting,
        "_record_reaction",
        lambda *args, **kwargs: ({"id": "reaction-1"}, "Reaction already recorded"),
    )

    result = _sync_telegram_app_replies_for_queue_item(
        {
            "id": "queue-1",
            "provider_account_id": "acc-1",
            "provider_message_id": "777",
            "recipient_value": "@ola",
            "sent_at": "2026-04-17T09:30:00+00:00",
        }
    )

    assert result["status"] == "noop"
    assert result["duplicates"] == 1


def test_build_compact_outreach_payload_limits_findings_and_actions() -> None:
    payload = _build_compact_outreach_payload(
        {
            "name": "Апельсин",
            "category": "Салон красоты",
            "city": "Санкт-Петербург",
            "rating": 4.6,
            "reviews_count": 145,
            "services_count": 12,
        },
        {
            "summary_text": "Очень длинный summary " * 20,
            "findings": [
                {"title": "Нет цен на услуги", "severity": "high"},
                {"title": "Мало фото результата", "severity": "high"},
                {"title": "Слабая работа с отзывами", "severity": "medium"},
            ],
            "recommended_actions": [
                {"title": "Добавить цены", "description": "Описание " * 30},
                {"title": "Обновить фото", "description": "Описание " * 30},
                {"title": "Ответить на отзывы", "description": "Описание " * 30},
            ],
            "revenue_potential": {"total_min": 30000, "total_max": 70000},
            "current_state": {"rating": 4.6, "reviews_count": 145, "services_count": 12},
        },
    )

    assert len(payload["top_findings"]) == 2
    assert len(payload["top_actions"]) == 2
    assert payload["revenue_potential"]["total_min"] == 30000
    assert len(payload["summary_text"]) <= 240


def test_generate_audit_first_message_draft_uses_ai_when_available(monkeypatch) -> None:
    monkeypatch.setattr(
        admin_prospecting,
        "_get_prompt_from_db",
        lambda prompt_type, fallback="": "Factual JSON: {factual_json}\nDeterministic fallback: {fallback_message}",
    )
    captured = {}

    def _fake_gigachat(prompt, task_type=None):
        captured["prompt"] = prompt
        return '{"message":"AI outreach message","angle_type":"audit_preview","tone":"professional"}'

    monkeypatch.setattr(
        admin_prospecting,
        "analyze_text_with_gigachat",
        _fake_gigachat,
    )

    payload = _generate_audit_first_message_draft(
        lead={
            "name": "Апельсин",
            "preferred_language": "ru",
            "public_audit_url": "https://localos.pro/apelsin-kremenchugskaya-ulitsa?lang=ru",
        },
        preview={
            "findings": [{"title": "Карточка выглядит незавершённой"}],
            "recommended_actions": [{"title": "Добавить услуги"}],
            "revenue_potential": {"total_min": 30000, "total_max": 70000},
        },
        channel="email",
    )

    assert payload["generated_text"] == "AI outreach message"
    assert payload["prompt_source"] == "gigachat"
    assert "Карточка выглядит незавершённой" in captured["prompt"]
    assert "Добавить услуги" in captured["prompt"]
    assert '"summary_text": ""' in captured["prompt"]


def test_lead_has_channel_contact_checks_matching_field_only() -> None:
    lead = {
        "telegram_url": "https://t.me/example",
        "whatsapp_url": "",
        "email": "",
    }

    assert _lead_has_channel_contact(lead, "telegram") is True
    assert _lead_has_channel_contact(lead, "whatsapp") is False
    assert _lead_has_channel_contact(lead, "max") is False
    assert _lead_has_channel_contact(lead, "email") is False
    assert _lead_has_channel_contact(lead, "manual") is True


def test_lead_has_channel_contact_detects_max_from_messenger_links() -> None:
    lead = {
        "website": "",
        "messenger_links_json": [
            "https://max.ru/beautybot",
            "https://vk.com/example",
        ],
    }

    assert _lead_has_channel_contact(lead, "max") is True


def test_outreach_channel_contact_error_is_human_readable() -> None:
    assert _outreach_channel_contact_error("telegram") == "Telegram channel cannot be selected without telegram_url"
    assert _outreach_channel_contact_error("whatsapp") == "WhatsApp channel cannot be selected without whatsapp_url"
    assert _outreach_channel_contact_error("max") == "MAX channel cannot be selected without max.ru contact"
    assert _outreach_channel_contact_error("email") == "Email channel cannot be selected without email"


def test_default_local_business_merges_baseline_quality_rules() -> None:
    default_issues = _build_default_local_business_issue_blocks(
        business_name="Тест Бизнес",
        city="Москва",
        has_description=False,
        services_count=4,
        priced_services_count=0,
        photos_count=2,
        reviews_count=7,
        unanswered_reviews_count=3,
    )
    baseline_issues = _build_card_baseline_issue_blocks(
        business_name="Тест Бизнес",
        city="Москва",
        services_count=4,
        priced_services_count=0,
        photos_count=2,
        reviews_count=7,
        unanswered_reviews_count=3,
        news_count=0,
        has_recent_activity=False,
        is_verified=False,
        reviews_target_min=30,
        include_pricing=True,
        include_photos=True,
        include_activity_stale=True,
    )

    merged = _merge_issue_blocks(default_issues, baseline_issues)
    titles = [str(item.get("title") or "") for item in merged]

    assert "У карточки нет синей галочки" in titles
    assert "В карточке не используются новости" in titles
    assert "Карточка ведётся по остаточному принципу" in titles
    assert "Есть отзывы без ответа" in titles


def test_medical_profile_keeps_niche_copy_and_adds_universal_baseline_rules() -> None:
    medical_issues = _build_medical_issue_blocks(
        business_name="Клиника",
        city="Москва",
        has_description=False,
        services_count=4,
        priced_services_count=0,
        photos_count=2,
        reviews_count=7,
        unanswered_reviews_count=3,
        focus_terms=["дерматолог", "консультация врача"],
    )
    baseline_issues = _build_card_baseline_issue_blocks(
        business_name="Клиника",
        city="Москва",
        services_count=4,
        priced_services_count=0,
        photos_count=2,
        reviews_count=7,
        unanswered_reviews_count=3,
        news_count=0,
        has_recent_activity=False,
        is_verified=False,
        reviews_target_min=30,
        include_pricing=False,
        include_photos=False,
        include_activity_stale=False,
    )

    merged = _merge_issue_blocks(medical_issues, baseline_issues)
    titles = [str(item.get("title") or "") for item in merged]

    assert "Описание не собирает направления клиники в понятный выбор" in titles
    assert "У карточки нет синей галочки" in titles
    assert "В карточке не используются новости" in titles
    assert "Карточке не хватает отзывов для устойчивого доверия" in titles


def test_merge_action_plan_flattens_and_deduplicates_steps() -> None:
    merged = _merge_action_plan(
        _build_default_local_business_action_plan(
            has_description=False,
            services_count=4,
            priced_services_count=0,
            photos_count=2,
            reviews_count=7,
            news_count=0,
            has_recent_activity=False,
            is_verified=False,
            unanswered_reviews_count=3,
        ),
        _build_card_baseline_action_plan(
            services_count=4,
            priced_services_count=0,
            photos_count=2,
            reviews_count=7,
            news_count=0,
            has_recent_activity=False,
            is_verified=False,
            unanswered_reviews_count=3,
            include_pricing=True,
            include_photos=True,
            include_activity_stale=True,
        ),
    )

    assert all(isinstance(item, str) for item in merged["next_24h"])
    assert all(isinstance(item, str) for item in merged["next_7d"])
    assert len(merged["next_24h"]) <= 4
    assert len(merged["next_7d"]) <= 4


def test_vertical_activity_copy_uses_concrete_conversion_language() -> None:
    beauty_titles = [
        str(item.get("title") or "")
        for item in _build_beauty_issue_blocks(
            business_name="Beauty",
            city="Москва",
            has_description=True,
            services_count=8,
            priced_services_count=6,
            photos_count=12,
            reviews_count=20,
            unanswered_reviews_count=2,
            focus_terms=["маникюр", "окрашивание"],
        )
    ]
    food_titles = [
        str(item.get("title") or "")
        for item in _build_food_issue_blocks(
            business_name="Food",
            city="Москва",
            has_description=True,
            services_count=12,
            priced_services_count=10,
            photos_count=15,
            reviews_count=24,
            unanswered_reviews_count=1,
        )
    ]
    wellness_titles = [
        str(item.get("title") or "")
        for item in _build_wellness_issue_blocks(
            business_name="Wellness",
            city="Москва",
            has_description=True,
            services_count=10,
            photos_count=8,
            reviews_count=18,
            unanswered_reviews_count=1,
        )
    ]
    fitness_issues = _build_fitness_issue_blocks(
        business_name="Fitness",
        city="Москва",
        has_description=True,
        services_count=8,
        priced_services_count=6,
        photos_count=10,
        reviews_count=20,
        unanswered_reviews_count=1,
    )
    fitness_titles = [str(item.get("title") or "") for item in fitness_issues]
    fitness_activity = next(
        item for item in fitness_issues if str(item.get("id") or "") == "activity_signals_gap"
    )

    assert "Карточка не показывает свежие работы и поводы записаться" in beauty_titles
    assert "Карточка не продаёт новинки и сезонные поводы прийти" in food_titles
    assert "Карточка не показывает свежие процедуры и обновления центра" in wellness_titles
    assert "Карточка не даёт свежих поводов начать заниматься" in fitness_titles
    assert "первый шаг" in str(fitness_activity.get("problem") or "")


def test_baseline_issue_flags_allow_fashion_and_hospitality_specific_merge() -> None:
    fashion_baseline = _build_card_baseline_issue_blocks(
        business_name="Showroom",
        city="Москва",
        services_count=6,
        priced_services_count=0,
        photos_count=3,
        reviews_count=10,
        unanswered_reviews_count=2,
        news_count=0,
        has_recent_activity=False,
        is_verified=False,
        reviews_target_min=30,
        include_pricing=False,
        include_photos=False,
        include_activity_stale=False,
        include_review_count=False,
        include_review_responses=True,
        include_news=False,
        include_verification=False,
    )
    hospitality_baseline = _build_card_baseline_issue_blocks(
        business_name="Hotel",
        city="Москва",
        services_count=4,
        priced_services_count=0,
        photos_count=3,
        reviews_count=10,
        unanswered_reviews_count=2,
        news_count=0,
        has_recent_activity=False,
        is_verified=False,
        reviews_target_min=120,
        include_pricing=False,
        include_photos=False,
        include_activity_stale=False,
        include_review_count=False,
        include_review_responses=False,
        include_news=True,
        include_verification=True,
    )

    fashion_titles = [str(item.get("title") or "") for item in fashion_baseline]
    hospitality_titles = [str(item.get("title") or "") for item in hospitality_baseline]

    assert fashion_titles == ["Есть отзывы без ответа"]
    assert "В карточке не используются новости" in hospitality_titles
    assert "У карточки нет синей галочки" in hospitality_titles
    assert "Карточке не хватает отзывов для устойчивого доверия" not in hospitality_titles
