from pathlib import Path

import requests
from urllib3.exceptions import ReadTimeoutError

from services.contact_intelligence_service import (
    build_first_message,
    build_message_brief,
    collect_public_website_contacts,
    enqueue_enrichment_job,
    evaluate_first_message,
    extract_contacts_from_html,
    legacy_contact_candidates,
    normalize_contact_value,
    normalize_phone,
    provider_error_is_retryable,
    upsert_contact_points,
)


ROOT = Path(__file__).resolve().parents[1]


class EnrichmentJobCursor:
    def __init__(self, latest):
        self.latest = latest
        self.last_query = ""
        self.inserted = False

    def execute(self, query, params=None):
        self.last_query = query
        if "INSERT INTO lead_enrichment_jobs" in query:
            self.inserted = True

    def fetchone(self):
        if "SELECT * FROM lead_enrichment_jobs" in self.last_query:
            return self.latest
        if "INSERT INTO lead_enrichment_jobs" in self.last_query:
            return {"id": "new-job", "workstream_id": "ws-1", "status": "queued"}
        return None


def test_phone_normalization_produces_e164_and_rejects_short_values():
    assert normalize_phone("8 (921) 555-12-34") == "+79215551234"
    assert normalize_phone("921 555 12 34") == "+79215551234"
    assert normalize_phone("12345") == ""
    assert normalize_phone("780102095932") == ""
    assert normalize_phone("324784700384560") == ""


def test_enrichment_enqueue_reuses_terminal_job_until_explicit_retry():
    cursor = EnrichmentJobCursor({"id": "existing", "workstream_id": "ws-1", "status": "ready"})

    reused = enqueue_enrichment_job(cursor, "ws-1")

    assert reused["id"] == "existing"
    assert reused["reused"] is True
    assert cursor.inserted is False

    restarted = enqueue_enrichment_job(cursor, "ws-1", force=True)

    assert restarted["id"] == "new-job"
    assert restarted["reused"] is False
    assert cursor.inserted is True


def test_official_page_collects_multiple_channels_without_collapsing_them():
    contacts = extract_contacts_from_html(
        """
        <html><body>
          <a href="tel:+7 921 555-12-34">Основной телефон</a>
          <a href="tel:+7 921 555-56-78">Отдел партнёрств</a>
          <a href="mailto:hello@example.ru">Email</a>
          <a href="https://t.me/example_team">Telegram</a>
          <a href="https://wa.me/79215551234">WhatsApp</a>
          <form action="/request"><input name="email"></form>
        </body></html>
        """,
        "https://example.ru/contacts",
    )

    typed_values = {(item["contact_type"], item["normalized_value"]) for item in contacts}
    assert ("phone", "+79215551234") in typed_values
    assert ("phone", "+79215555678") in typed_values
    assert ("email", "hello@example.ru") in typed_values
    assert ("telegram", "https://t.me/example_team") in typed_values
    assert ("whatsapp", "https://wa.me/79215551234") in typed_values
    assert ("website_form", "https://example.ru/request") in typed_values


def test_messenger_contact_drops_prefilled_message_query():
    assert normalize_contact_value(
        "whatsapp",
        "https://wa.me/79215551234?text=Чужой%20текст",
    ) == "https://wa.me/79215551234"
    assert normalize_contact_value(
        "telegram",
        "https://t.me/example_team?start=tracking",
    ) == "https://t.me/example_team"


def test_messenger_contact_is_stored_with_canonical_display_value():
    class Cursor:
        params = None

        def execute(self, _query, params=None):
            self.params = params

    cursor = Cursor()
    upsert_contact_points(
        cursor,
        "lead-1",
        [{
            "contact_type": "whatsapp",
            "value": "https://wa.me/79215551234?text=Чужой%20текст",
            "source_type": "map_card",
        }],
    )

    assert cursor.params[3] == "https://wa.me/79215551234"
    assert cursor.params[4] == "https://wa.me/79215551234"


def test_website_stream_timeout_becomes_warning(monkeypatch):
    class TimedOutBody:
        def read(self, *_args, **_kwargs):
            raise ReadTimeoutError(None, "https://example.ru", "timed out")

    class Response:
        is_redirect = False
        headers = {"content-type": "text/html"}
        raw = TimedOutBody()
        encoding = "utf-8"
        url = "https://example.ru"

        def raise_for_status(self):
            return None

    monkeypatch.setattr(
        "services.contact_intelligence_service._public_http_url",
        lambda value: str(value),
    )
    monkeypatch.setattr(
        "services.contact_intelligence_service.requests.get",
        lambda *_args, **_kwargs: Response(),
    )

    contacts, warnings = collect_public_website_contacts("https://example.ru")

    assert contacts == []
    assert warnings == ["Не удалось проверить https://example.ru"]


def test_official_structured_data_keeps_person_name_and_role():
    contacts = extract_contacts_from_html(
        """
        <script type="application/ld+json">
          {
            "@type": "Person",
            "name": "Анна Петрова",
            "jobTitle": "Директор по партнёрствам",
            "email": "anna@example.ru",
            "sameAs": ["https://t.me/anna_example"]
          }
        </script>
        """,
        "https://example.ru/team",
    )

    email = next(item for item in contacts if item["contact_type"] == "email")
    telegram = next(item for item in contacts if item["contact_type"] == "telegram")
    assert email["owner_type"] == "person"
    assert email["person_name"] == "Анна Петрова"
    assert email["role_title"] == "Директор по партнёрствам"
    assert telegram["person_name"] == "Анна Петрова"


def test_legacy_candidates_keep_all_messenger_links():
    contacts = legacy_contact_candidates(
        {
            "phone": "+7 921 555-12-34",
            "source_url": "https://maps.example/company",
            "messenger_links_json": [
                "https://t.me/company",
                {"url": "https://vk.com/company"},
                "https://instagram.com/company",
            ],
        }
    )

    assert {item["contact_type"] for item in contacts} == {"phone", "telegram", "vk", "instagram"}


def test_localos_sales_stops_when_role_signal_and_proof_are_missing():
    brief, readiness = build_message_brief(
        {"name": "Example", "category": "стоматология"},
        {"workstream_type": "localos_sales"},
        None,
        {
            "contact_type": "email",
            "value": "info@example.ru",
            "owner_type": "company",
        },
        {
            "display_name": "Алексей",
            "role_title": "основатель",
            "company_name": "LocalOS",
            "confirmed_at": "2026-07-15T10:00:00Z",
            "proof_points_json": [],
            "verified_cases_json": [],
        },
    )

    assert readiness["code"] == "needs_facts"
    assert "Найдите роль получателя" in readiness["missing"]
    assert "Добавьте публичный сигнал «почему сейчас»" in readiness["missing"]
    assert "Добавьте подтверждённую проблему" in readiness["missing"]
    assert "Укажите один конкретный результ первого шага" in readiness["missing"]
    assert "Добавьте проверенное доказательство или кейс" in readiness["missing"]
    assert brief["pain"] == ""


def test_localos_sales_uses_researched_brief_instead_of_generic_offer():
    brief, readiness = build_message_brief(
        {"name": "Клиника", "category": "стоматология"},
        {"workstream_type": "localos_sales"},
        {
            "why_now": "в карточке нет актуального раздела услуг",
            "message_brief_json": {
                "buyer_persona": "управляющая",
                "pain": "пациенты не видят актуальные услуги до перехода на сайт",
                "result": "разбора трёх разделов карточки с приоритетом исправлений",
                "proof": "публичный аудит карточки",
                "cta": "Показать разбор?",
            },
            "sources_json": [{"title": "Карточка", "url": "https://maps.example/clinic"}],
        },
        {
            "contact_type": "email",
            "owner_type": "person",
            "person_name": "Анна",
            "role_title": "управляющая",
        },
        {
            "display_name": "Алексей",
            "role_title": "основатель",
            "company_name": "LocalOS",
            "confirmed_at": "2026-07-15T10:00:00Z",
            "proof_points_json": [],
            "verified_cases_json": [],
        },
    )

    assert readiness["code"] == "ready"
    assert brief["result"] == "разбора трёх разделов карточки с приоритетом исправлений"
    message = build_first_message(
        {"name": "Клиника"},
        {"workstream_type": "localos_sales"},
        brief,
        {"display_name": "Алексей", "role_title": "основатель", "company_name": "LocalOS"},
        {"person_name": "Анна"},
    )
    assert "трёх разделов карточки" in message
    assert "пациенты не видят" in message


def test_partner_brief_uses_compatibility_without_inventing_pain():
    brief, readiness = build_message_brief(
        {"name": "Фитнес рядом", "category": "фитнес"},
        {
            "workstream_type": "client_partnership",
            "client_business_name": "Органика",
            "service_compatibility_score": 82,
        },
        None,
        {
            "contact_type": "telegram",
            "value": "https://t.me/fitness",
            "owner_type": "company",
        },
        {
            "display_name": "Мария",
            "role_title": "управляющая",
            "company_name": "Органика",
            "confirmed_at": "2026-07-15T10:00:00Z",
            "proof_points_json": [],
            "verified_cases_json": [],
        },
    )

    assert readiness["code"] == "ready"
    assert brief["pain"] == ""
    assert brief["pain_strength"] == "not_required"
    assert "Органика" in brief["result"]


def test_first_message_is_short_human_and_has_one_question():
    brief = {
        "signal": "в карточке не указан актуальный раздел услуг",
        "result": "короткий список исправлений и первый приоритет",
        "proof": "публичный аудит карточки от 15 июля",
        "cta": "Прислать короткий разбор?",
    }
    sender = {"display_name": "Алексей", "role_title": "основатель", "company_name": "LocalOS"}
    contact = {"person_name": "Анна", "role_title": "управляющая"}
    message = build_first_message(
        {"name": "Клиника", "category": "стоматология"},
        {"workstream_type": "localos_sales"},
        brief,
        sender,
        contact,
    )
    quality = evaluate_first_message(message, brief)

    assert quality["passed"] is True
    assert quality["word_count"] <= 90
    assert message.count("?") == 1
    assert "недополучаете" not in message.lower()
    assert "под ключ" not in message.lower()


def test_quality_gate_rejects_unproven_percentages_and_template_claims():
    quality = evaluate_first_message(
        "Здравствуйте! Вы недополучаете клиентов. Внедрим под ключ и дадим +30-80%. Интересно?",
        {"result": "рост обращений", "proof": ""},
    )

    assert quality["passed"] is False
    assert "Найдено неподтверждённое обещание" in quality["failures"]


def test_hunter_timeout_and_rate_limit_are_retryable_but_bad_request_is_not():
    rate_limited_response = requests.Response()
    rate_limited_response.status_code = 429
    rate_limited = requests.HTTPError(response=rate_limited_response)
    bad_request_response = requests.Response()
    bad_request_response.status_code = 400
    bad_request = requests.HTTPError(response=bad_request_response)

    assert provider_error_is_retryable(requests.Timeout("timeout")) is True
    assert provider_error_is_retryable(rate_limited) is True
    assert provider_error_is_retryable(bad_request) is False


def test_contact_intelligence_migration_keeps_one_company_model():
    source = (ROOT / "alembic_migrations/versions/20260715_add_contact_intelligence.py").read_text()

    assert "CREATE TABLE IF NOT EXISTS lead_contact_points" in source
    assert "CREATE TABLE IF NOT EXISTS lead_enrichment_jobs" in source
    assert "CREATE TABLE IF NOT EXISTS outreach_sender_profiles" in source
    assert "CREATE TABLE IF NOT EXISTS prospectingleads" not in source
    assert "selected_contact_point_id" in source


def test_contact_intelligence_runtime_has_no_message_send_capability():
    source = (ROOT / "src/services/contact_intelligence_service.py").read_text()

    assert "send_message(" not in source
    assert "userbot_send" not in source
    assert "outreachsendqueue" not in source


def test_worker_uses_database_wrapper_cursor_contract():
    source = (ROOT / "src" / "worker.py").read_text(encoding="utf-8")
    start = source.index("def _process_contact_intelligence_if_due()")
    end = source.index("\ndef _prepare_contact_intelligence_room", start)
    worker_block = source[start:end]

    assert "db.conn.cursor(cursor_factory=" not in worker_block
    assert "db.conn.cursor()" in worker_block


def test_contact_routes_are_registered():
    import main

    routes = {(str(rule), frozenset(rule.methods - {"HEAD", "OPTIONS"})) for rule in main.app.url_map.iter_rules()}
    assert (
        "/api/admin/prospecting/leads/<string:lead_id>/contact-intelligence",
        frozenset({"POST"}),
    ) in routes
    assert (
        "/api/admin/prospecting/leads/<string:lead_id>/contact-intelligence",
        frozenset({"GET"}),
    ) in routes
    assert (
        "/api/partnership/leads/<string:lead_id>/contact-intelligence",
        frozenset({"GET", "POST"}),
    ) in routes


def test_contact_normalization_deduplicates_url_shape():
    assert normalize_contact_value("telegram", "t.me/example/") == "https://t.me/example"
