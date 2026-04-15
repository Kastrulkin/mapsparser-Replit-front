from src.api import admin_prospecting
from src.api.admin_prospecting import (
    _build_admin_lead_offer_payload,
    _build_compact_outreach_payload,
    _generate_superadmin_deterministic_first_message,
    _generate_lead_audit_enrichment,
    _generate_audit_first_message_draft,
    _resolve_outreach_language,
)
from src.core.card_audit import _build_reasoning_fields


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
    assert "Нашёл вас на картах - вижу, что часть клиентов теряется." in text
    assert "Например, описание не всех услуг попадает в поиск." in text
    assert "https://localos.pro/apelsin-kremenchugskaya-ulitsa" in text
    assert "+30-80% к обращениям без рекламы." in text
    assert payload["prompt_source"] == "deterministic"


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
