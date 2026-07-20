from pathlib import Path
import json

import requests
from urllib3.exceptions import ReadTimeoutError

from decimal import Decimal
from datetime import datetime, timezone

from services.contact_intelligence_service import (
    MessageQualityError,
    PersonalizationGenerationError,
    build_native_research_payload,
    contact_type_from_url,
    json_safe,
    build_first_message,
    build_message_brief,
    collect_public_website_contacts,
    enqueue_enrichment_job,
    evaluate_first_message,
    extract_contacts_from_html,
    legacy_contact_candidates,
    merge_research_briefs,
    normalize_contact_value,
    normalize_phone,
    prepare_first_message,
    public_audit_artifact_from_row,
    provider_error_is_retryable,
    recover_interrupted_enrichment_jobs,
    fail_enrichment_job,
    upsert_contact_points,
)
from services.outreach_sender_profile_service import evaluate_sender_profile_completeness
from services.outreach_personalization_ai import QUALITY_CRITERIA
from scripts.backfill_partnership_match_artifacts import _skip_reason


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


class RecoveryCursor:
    def __init__(self):
        self.query = ""
        self.params = ()

    def execute(self, query, params=None):
        self.query = query
        self.params = params or ()

    def fetchall(self):
        return [{"id": "job-1"}, {"id": "job-2"}]


class FailureCursor:
    def __init__(self):
        self.executions = []

    def execute(self, query, params=None):
        self.executions.append((query, params or ()))

    def fetchone(self):
        status = self.executions[0][1][0]
        return {"id": "job-1", "workstream_id": "ws-1", "status": status}


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


def test_interrupted_enrichment_recovery_only_requeues_inflight_jobs():
    cursor = RecoveryCursor()

    recovered = recover_interrupted_enrichment_jobs(cursor, minimum_age_seconds=45)

    assert recovered == ["job-1", "job-2"]
    assert "status IN ('collecting', 'verifying', 'researching', 'drafting')" in cursor.query
    assert "status = 'retry_wait'" in cursor.query
    assert "RETURNING id" in cursor.query
    assert cursor.params == (45,)


def test_sender_profile_completeness_requires_the_full_founder_led_context():
    incomplete = evaluate_sender_profile_completeness(
        {
            "display_name": "Юлия",
            "role_title": "основатель",
            "company_name": "Новамед",
            "competence_story": "Развиваем медицинский центр.",
            "proof_points_json": [],
            "allowed_offers_json": [],
            "forbidden_claims_json": [],
            "voice_examples_json": [],
            "outreach_context_json": {
                "competence_story_status": "approved",
                "audience": "",
                "desired_partner_types": [],
            },
        },
        workstream_type="client_partnership",
        business_service_count=5,
    )

    assert incomplete["ready"] is False
    assert incomplete["completed_count"] == 3
    assert incomplete["required_count"] == 9
    missing_codes = {item["code"] for item in incomplete["missing_items"]}
    assert missing_codes == {
        "sender_proof",
        "sender_audience",
        "sender_offer",
        "sender_voice",
        "sender_forbidden_claims",
        "desired_partner_types",
    }


def test_sender_profile_completeness_accepts_only_a_full_confirmable_profile():
    complete = evaluate_sender_profile_completeness(
        {
            "display_name": "Анна",
            "role_title": "основатель",
            "company_name": "Студия",
            "competence_story": "Пять лет развиваем программы для семей с детьми.",
            "proof_points_json": [{"fact": "Провели 20 совместных мероприятий", "status": "approved"}],
            "allowed_offers_json": ["Провести одно пробное совместное мероприятие"],
            "forbidden_claims_json": ["Не обещать рост выручки"],
            "voice_examples_json": ["Здравствуйте! Предлагаю спокойно проверить одну механику."],
            "outreach_context_json": {
                "competence_story_status": "approved",
                "audience": "Семьи с детьми",
                "desired_partner_types": ["детские центры"],
            },
        },
        workstream_type="client_partnership",
        business_service_count=12,
    )

    assert complete["ready"] is True
    assert complete["completed_count"] == complete["required_count"] == 9
    assert complete["missing_items"] == []


def test_match_backfill_accepts_parsed_snapshot_services_but_rejects_manual_imports():
    public_row = {
        "source_url": "https://maps.example/partner",
        "search_payload_json": {"source": "apify_yandex"},
        "services_json": [],
    }
    snapshot = {
        "services_preview": [
            {"current_name": "Детская стрижка"},
            {"current_name": "Укладка"},
            {"current_name": "Праздничная причёска"},
        ],
    }

    assert _skip_reason(public_row, snapshot) is None
    assert _skip_reason(
        {
            **public_row,
            "source_url": "localos-doc://partner",
            "search_payload_json": {"source": "manual_google_doc_import"},
        },
        snapshot,
    ) == "manual_import_without_public_service_evidence"


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


def test_malformed_bracketed_url_is_ignored_in_contact_payload():
    assert contact_type_from_url("https://[broken") is None
    assert normalize_contact_value("website", "https://[broken") == ""


def test_contact_evidence_dates_and_decimals_are_json_safe():
    observed_at = datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc)

    payload = json_safe({"observed_at": observed_at, "confidence": Decimal("0.875")})

    assert payload == {"observed_at": observed_at.isoformat(), "confidence": 0.875}


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


def test_legacy_candidates_recovers_all_supported_channels_from_nested_map_payload():
    contacts = legacy_contact_candidates({
        "source_url": "https://maps.example/company",
        "raw_payload_json": {
            "contacts": {
                "emails": ["partner@example.ru"],
                "phones": ["+7 921 555-12-34"],
                "socialLinks": [
                    "https://t.me/example",
                    "https://vk.com/example",
                    "https://instagram.com/example",
                    "https://max.ru/example",
                ],
            },
        },
    })

    assert {item["contact_type"] for item in contacts} == {
        "email", "phone", "telegram", "vk", "instagram", "max",
    }
    assert all(item["source_type"] == "map_payload" for item in contacts)


def test_localos_public_audit_becomes_sourced_research_without_promoting_hypothesis():
    artifact = public_audit_artifact_from_row({
        "slug": "clinic-audit",
        "is_active": True,
        "source_type": "admin_prospecting_public_audit",
        "edit_status": "published",
        "published_at": "2026-07-16T10:00:00+00:00",
        "published_json": {
            "audit": {
                "current_state": {
                    "services_count": 12,
                    "services_with_price_count": 3,
                },
                "top_3_issues": [{
                    "title": "Не хватает цен",
                    "evidence": "Цена отображается только у 3 из 12 услуг.",
                    "problem": "Клиенту может быть сложно оценить бюджет до звонка.",
                }],
            },
        },
    })

    payload = build_native_research_payload(
        {
            "id": "lead-1",
            "name": "Клиника",
            "category": "стоматология",
            "source_url": "https://maps.example/clinic",
        },
        {"id": "ws-1", "workstream_type": "localos_sales"},
        artifact,
    )

    public_audit_signals = [
        item for item in payload["signals_json"]
        if item.get("source_type") == "admin_prospecting_public_audit"
    ]
    assert artifact["audit_source_url"] == "https://localos.pro/clinic-audit"
    assert any("12 услуг" in item["observed_fact"] for item in public_audit_signals)
    issue_signal = next(item for item in public_audit_signals if item.get("hypothesis"))
    assert "может быть" in issue_signal["hypothesis"]
    assert issue_signal["usable_for_outreach"] is True
    assert payload["why_now"]


def test_public_audit_conclusion_without_observation_stays_unusable_hypothesis():
    payload = build_native_research_payload(
        {
            "id": "lead-2",
            "name": "Салон",
            "category": "beauty",
            "source_url": "https://maps.example/salon",
        },
        {"id": "ws-2", "workstream_type": "localos_sales"},
        {
            "audit_source_url": "https://localos.pro/salon-audit",
            "audit_source_date": datetime(2026, 7, 16, 10, 0, tzinfo=timezone.utc),
            "audit_json": {
                "top_3_issues": [{
                    "title": "Карточка не раскрывает ценность услуг",
                    "problem": "Клиенты могут уйти к конкуренту.",
                }],
            },
        },
    )

    hypothesis = next(item for item in payload["signals_json"] if item.get("hypothesis"))
    assert hypothesis["observed_fact"] == ""
    assert hypothesis["usable_for_outreach"] is False
    assert hypothesis["rejected_reason"] == "observation_missing_hypothesis_only"


def test_zero_rating_and_manual_check_language_do_not_become_outreach_facts():
    payload = build_native_research_payload(
        {
            "id": "lead-3",
            "name": "Студия",
            "category": "beauty",
            "rating": 0,
            "reviews_count": 0,
            "website": "https://studio.example",
            "source_url": "https://maps.example/studio",
        },
        {"id": "ws-3", "workstream_type": "localos_sales"},
        {
            "audit_source_url": "https://localos.pro/studio-audit",
            "audit_source_date": "2026-07-16T10:00:00+00:00",
            "audit_json": {
                "top_3_issues": [{
                    "observed_fact": "Визуальный блок требует ручной проверки: важно убедиться, что виден вход.",
                    "title": "Стоит проверить фотографии",
                }],
            },
        },
    )

    assert payload["why_now"] == ""
    assert payload["qualification_stage"] == "potential_fit"
    assert not any(item.get("usable_for_outreach") for item in payload["signals_json"])
    assert any(item.get("hypothesis") for item in payload["signals_json"])


def test_disqualified_native_research_keeps_readiness_out_of_qualification_stage():
    payload = build_native_research_payload(
        {
            "id": "lead-closed",
            "name": "Закрытая студия",
            "category": "beauty",
            "source_url": "https://maps.example/closed-studio",
            "raw_payload_json": {"permanently_closed": True},
        },
        {"id": "ws-closed", "workstream_type": "localos_sales"},
    )

    assert payload["score"] == 0
    assert payload["qualification_stage"] == "potential_fit"
    assert payload["score_breakdown"]["disqualifiers"] == ["business_closed"]


def test_normalized_partnership_match_becomes_sourced_compatibility_evidence():
    payload = build_native_research_payload(
        {
            "id": "partner-lead",
            "name": "Студия восстановления",
            "category": "здоровье",
            "source_url": "https://maps.example/partner",
        },
        {
            "id": "partner-ws",
            "workstream_type": "client_partnership",
            "client_business_name": "Фитнес-клуб",
        },
        {
            "match_json": {
                "match_score": 64,
                "recipient_observation": "В публичной карточке указаны услуги: восстановление, массаж.",
                "compatibility_hypothesis": "Гипотеза для проверки: у компаний может пересекаться аудитория.",
                "relevance_bridge": "Есть основание проверить один безопасный совместный тест.",
            }
        },
    )

    assert payload["why_now"].startswith("В публичной карточке")
    assert payload["evidence_json"][0]["kind"] == "service_compatibility"
    assert payload["evidence_json"][0]["hypothesis"].startswith("Гипотеза для проверки")
    assert payload["score_breakdown"]["service_compatibility"] == 16


def test_structured_card_fact_is_preferred_to_negative_review():
    payload = build_native_research_payload(
        {
            "id": "lead-4",
            "name": "Клиника",
            "category": "медцентр",
            "rating": 4.8,
            "reviews_count": 50,
            "reviews_json": [{
                "rating": 1,
                "text": "Долго ждал ответа администратора.",
                "source_url": "https://maps.example/clinic/review/1",
                "published_at": "2026-07-10T10:00:00+00:00",
            }],
            "source_url": "https://maps.example/clinic",
        },
        {"id": "ws-4", "workstream_type": "localos_sales"},
        {
            "audit_source_url": "https://localos.pro/clinic-audit",
            "audit_source_date": datetime(2026, 7, 16, 10, 0, tzinfo=timezone.utc),
            "audit_json": {
                "current_state": {"services_count": 20, "services_with_price_count": 5},
            },
        },
    )

    assert payload["why_now"] == "По данным аудита карточки: всего услуг - 20; с ценой - 5."
    json.dumps(payload["signals_json"])
    json.dumps(payload["evidence_json"])


def test_high_price_coverage_is_not_used_as_cold_outreach_signal():
    payload = build_native_research_payload(
        {
            "id": "lead-high-coverage",
            "name": "Салон",
            "category": "салон красоты",
            "rating": 4.9,
            "reviews_count": 50,
            "source_url": "https://maps.example/salon",
            "website": "https://salon.example",
        },
        {"id": "ws-high-coverage", "workstream_type": "localos_sales"},
        {
            "audit_source_url": "https://localos.pro/salon-audit",
            "audit_source_date": datetime(2026, 7, 16, 10, 0, tzinfo=timezone.utc),
            "audit_json": {
                "current_state": {"services_count": 145, "services_with_price_count": 130},
            },
        },
    )

    assert payload["why_now"] == ""
    assert not any(item.get("usable_for_outreach") for item in payload["signals_json"])
    assert any("выше 80%" in str(item.get("hypothesis") or "") for item in payload["signals_json"])


def test_stronger_native_research_replaces_stale_angle_but_keeps_approved_proof():
    merged, native_wins = merge_research_briefs(
        {
            "signal": "Общее совпадение по отрасли",
            "pain": "Общая гипотеза",
            "proof": "Подтверждённый кейс LocalOS",
        },
        {
            "signal": "В аудите найдено 12 услуг, цена указана у 3",
            "pain": "Цены указаны не для всех услуг",
            "result": "короткий разбор карточки",
        },
        existing_score=40,
        native_score=75,
    )

    assert native_wins is True
    assert merged["signal"].startswith("В аудите")
    assert merged["pain"].startswith("Цены указаны")
    assert merged["proof"] == "Подтверждённый кейс LocalOS"


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

    assert readiness["code"] == "needs_evidence"
    assert "Найдите роль получателя" in readiness["missing"]
    assert "Добавьте публичный сигнал «почему сейчас»" in readiness["missing"]
    assert "Добавьте подтверждённую проблему" in readiness["missing"]
    assert "Укажите один конкретный результат первого шага" in readiness["missing"]
    assert "Добавьте проверенное доказательство или кейс" in readiness["missing"]
    assert {item["code"] for item in readiness["missing_items"]} >= {
        "recipient_role",
        "timing_signal",
        "confirmed_problem",
        "first_step_result",
        "sender_proof",
    }
    assert brief["pain"] == ""


def test_partnership_readiness_names_sender_and_relationship_facts_separately():
    _brief, readiness = build_message_brief(
        {"name": "Plastica", "category": "школа танцев"},
        {
            "workstream_type": "client_partnership",
            "client_business_name": "Шансик",
            "service_compatibility_score": None,
        },
        None,
        {
            "contact_type": "phone",
            "value": "+79315765953",
            "owner_type": "company",
        },
        None,
    )

    assert readiness["code"] == "needs_evidence"
    assert readiness["label"] == "Нужны факты"
    assert readiness["missing_items"] == [
        {"code": "sender_profile", "label": "Добавьте факты об отправителе"},
        {
            "code": "partner_compatibility",
            "label": "Подтвердите, чем бизнес отправителя и потенциальный партнёр полезны друг другу",
        },
    ]


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
            "competence_story": "Мы сами управляли локальным бизнесом и знаем работу с картами изнутри",
            "proof_points_json": [{"fact": "Публичный аудит карточки", "status": "approved"}],
            "verified_cases_json": [],
            "allowed_offers_json": ["Разобрать три раздела карточки"],
            "forbidden_claims_json": ["Не обещать рост обращений"],
            "voice_examples_json": ["Здравствуйте! Могу показать короткий разбор?"],
            "outreach_context_json": {
                "competence_story_status": "approved",
                "audience": "Владельцы локального бизнеса",
            },
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
                "business_service_count": 8,
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
            "competence_story": "Мы ведём локальный бизнес и умеем запускать совместные механики без риска для клиентов",
            "proof_points_json": [{"fact": "Проводили совместные локальные мероприятия", "status": "approved"}],
            "verified_cases_json": [],
            "allowed_offers_json": ["Проверить одну совместную механику"],
            "forbidden_claims_json": ["Не обещать коммерческий результат"],
            "voice_examples_json": ["Здравствуйте! Предлагаю спокойно проверить одну механику."],
            "outreach_context_json": {
                "competence_story_status": "approved",
                "audience": "Жители района",
                "desired_partner_types": ["фитнес-клубы"],
            },
        },
    )

    assert readiness["code"] == "ready"
    assert brief["pain"] == ""
    assert brief["pain_strength"] == "not_required"
    assert "Органика" in brief["result"]


def test_first_message_is_short_human_and_has_one_question():
    brief = {
        "lead_name": "Клиника",
        "signal": "в карточке не указан актуальный раздел услуг",
        "result": "короткий список исправлений и первый приоритет",
        "proof": "публичный аудит карточки от 15 июля",
        "founder_story": "мы сами управляли локальным бизнесом и знаем работу с картами изнутри",
        "source_urls": ["https://maps.example/clinic"],
        "evidence_ids": ["evidence:clinic"],
        "evidence_fresh": True,
        "suppression_safe": True,
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


def test_first_message_deduplicates_signal_and_uses_natural_sender_identity():
    repeated_fact = "В аудите публичной карточки найдено 147 услуг, цена указана у 53"
    brief = {
        "lead_name": "Buro Beauty",
        "signal": repeated_fact,
        "pain": repeated_fact,
        "result": "короткий разбор карточки с одним приоритетным исправлением",
        "proof": "публичный аудит карточки",
        "founder_story": "Я развиваю LocalOS и сам разбираю публичные карточки локальных компаний",
        "source_urls": ["https://maps.example/buro-beauty"],
        "evidence_ids": ["evidence:buro-beauty"],
        "evidence_fresh": True,
        "suppression_safe": True,
        "cta": "Прислать короткий разбор?",
    }
    message = build_first_message(
        {"name": "Buro Beauty"},
        {"workstream_type": "localos_sales"},
        brief,
        {
            "display_name": "Александр Демьянов",
            "role_title": "руководитель LocalOS",
            "company_name": "LocalOS",
        },
        {},
    )

    assert message.lower().count(repeated_fact.lower()) == 1
    assert "руководитель LocalOS в LocalOS" not in message
    assert "Пишу не случайно:" not in message
    assert "Вижу задачу:" not in message
    assert evaluate_first_message(message, brief)["passed"] is True


def test_first_message_keeps_whole_words_when_approved_facts_are_long():
    long_story = " ".join(["подтверждённый опыт локального бизнеса"] * 20)
    brief = {
        "lead_name": "Клиника",
        "signal": "в карточке не указан актуальный раздел услуг",
        "pain": "",
        "result": "короткий разбор карточки и приоритет для продвижения",
        "proof": "",
        "founder_story": long_story,
        "source_urls": ["https://maps.example/clinic"],
        "evidence_ids": ["evidence:clinic"],
        "evidence_fresh": True,
        "suppression_safe": True,
        "cta": "Прислать короткий разбор?",
    }
    message = build_first_message(
        {"name": "Клиника"},
        {"workstream_type": "localos_sales"},
        brief,
        {"display_name": "Алексей", "role_title": "основатель", "company_name": "LocalOS"},
        {},
    )

    assert len(message.split()) <= 90
    assert "продвижени." not in message
    assert message.endswith("Прислать короткий разбор?")


def test_quality_gate_rejects_a_repeated_evidence_claim():
    signal = "В карточке найдено 147 услуг, цена указана у 53"
    brief = {
        "lead_name": "Buro Beauty",
        "signal": signal,
        "pain": signal,
        "result": "короткий разбор",
        "founder_story": "Я развиваю LocalOS и проверяю карточки локальных компаний",
        "source_urls": ["https://maps.example/buro-beauty"],
        "evidence_ids": ["evidence:buro-beauty"],
        "evidence_fresh": True,
        "suppression_safe": True,
    }
    quality = evaluate_first_message(
        (
            "Здравствуйте! Обратил внимание на Buro Beauty: "
            f"{signal}. Вижу задачу: {signal}. "
            "Я развиваю LocalOS и проверяю карточки локальных компаний. "
            "Могу прислать короткий разбор?"
        ),
        brief,
    )

    assert quality["passed"] is False
    assert "Один и тот же факт нельзя повторять как сигнал и проблему" in quality["failures"]


def test_prepare_first_message_uses_native_ai_contract_and_semantic_review():
    brief = {
        "lead_name": "Buro Beauty",
        "signal": "В карточке найдено 147 услуг, цена указана у 53",
        "pain": "",
        "result": "короткий разбор карточки с одним приоритетным исправлением",
        "proof": "Проводил аудиты карточек локальных компаний",
        "founder_story": "Я развиваю LocalOS и сам разбираю публичные карточки",
        "source_urls": ["https://maps.example/buro-beauty"],
        "evidence_ids": ["evidence:buro-beauty"],
        "evidence_fresh": True,
        "suppression_safe": True,
        "cta": "Прислать короткий разбор?",
    }
    candidate = {
        "id": "personalization-1",
        "evidence_id": "evidence:buro-beauty",
        "evidence_ids": ["evidence:buro-beauty"],
        "evidence_kind": "map_audit",
        "observed_fact": brief["signal"],
        "problem_hypothesis": None,
        "bridge": "Этот сигнал можно предметно проверить через короткий аудит карточки",
        "source_url": "https://maps.example/buro-beauty",
        "source_type": "public_audit",
        "freshness": "current_snapshot",
        "confidence": 0.95,
        "founder_story": brief["founder_story"],
        "founder_proof": brief["proof"],
        "next_step": brief["result"],
    }

    def generator(_prompt, **_kwargs):
        return json.dumps({
            "schema_version": "1.0",
            "touches": [{
                "sequence_index": 0,
                "channel": "telegram",
                "angle": "founder_story",
                "opening_style": "direct",
                "cta_intent": "send_short_review",
                "evidence_ids": ["evidence:buro-beauty"],
                "observation": brief["signal"],
                "problem_hypothesis": None,
                "relevance_bridge": candidate["bridge"],
            }],
        }, ensure_ascii=False)

    def reviewer(_prompt, **_kwargs):
        return json.dumps({
            "schema_version": "1.0",
            "reviews": [{
                "sequence_index": 0,
                "scores": {criterion: 2 for criterion in QUALITY_CRITERIA},
                "total_score": 18,
                "verdict": "approve",
                "reason_codes": [],
                "notes": [],
            }],
        }, ensure_ascii=False)

    message, quality, draft_brief = prepare_first_message(
        {"name": "Buro Beauty"},
        {"workstream_type": "localos_sales", "created_by": "user-1"},
        brief,
        {
            "display_name": "Александр Демьянов",
            "role_title": "руководитель",
            "company_name": "LocalOS",
            "created_by": "user-1",
            "forbidden_claims_json": [{"text": "Гарантированный рост", "status": "approved"}],
            "voice_examples_json": [{"text": "Пишу коротко и по делу", "status": "approved"}],
        },
        {"contact_type": "telegram"},
        candidate,
        use_ai=True,
        generator=generator,
        reviewer=reviewer,
    )

    assert brief["signal"] in message
    assert brief["founder_story"] in message
    assert quality["passed"] is True
    assert quality["generation"]["source"] == "gigachat"
    assert quality["semantic_review"]["passed"] is True
    assert draft_brief["selected_personalization_id"] == "personalization-1"


def test_prepare_first_message_compacts_long_approved_facts_before_ai_quality_gate():
    signal = " ".join(["В публичном аудите карточки найден подтверждённый сигнал"] * 8)
    story = (
        "Я развиваю LocalOS на основе практической работы с публичными данными локальных бизнесов. "
        + " ".join(["Команда проверяет карточки услуги отзывы и контент"] * 8)
    )
    bridge = " ".join(["Этот факт можно проверить через короткий аудит карточки"] * 6)
    brief = {
        "lead_name": "Клиника",
        "signal": signal,
        "pain": "",
        "result": "короткий разбор карточки с одним приоритетным исправлением",
        "proof": "Проводил аудиты карточек локальных компаний",
        "founder_story": story,
        "source_urls": ["https://maps.example/clinic"],
        "evidence_ids": ["evidence:clinic"],
        "evidence_fresh": True,
        "suppression_safe": True,
        "cta": "Прислать короткий разбор?",
    }
    candidate = {
        "id": "personalization-long",
        "evidence_id": "evidence:clinic",
        "evidence_ids": ["evidence:clinic"],
        "observed_fact": signal,
        "bridge": bridge,
        "source_url": "https://maps.example/clinic",
        "freshness": "current_snapshot",
        "founder_story": story,
        "founder_proof": brief["proof"],
        "next_step": brief["result"],
    }

    def generator(_prompt, **_kwargs):
        return json.dumps({
            "schema_version": "1.0",
            "touches": [{
                "sequence_index": 0,
                "channel": "telegram",
                "angle": "founder_story",
                "opening_style": "concise",
                "cta_intent": "send_short_review",
                "evidence_ids": ["evidence:clinic"],
                "observation": signal,
                "problem_hypothesis": None,
                "relevance_bridge": bridge,
            }],
        }, ensure_ascii=False)

    def reviewer(_prompt, **_kwargs):
        return json.dumps({
            "schema_version": "1.0",
            "reviews": [{
                "sequence_index": 0,
                "scores": {criterion: 2 for criterion in QUALITY_CRITERIA},
                "total_score": 18,
                "verdict": "approve",
                "reason_codes": [],
                "notes": [],
            }],
        }, ensure_ascii=False)

    message, quality, draft_brief = prepare_first_message(
        {"name": "Клиника"},
        {"workstream_type": "localos_sales", "created_by": "user-1"},
        brief,
        {
            "display_name": "Александр Демьянов",
            "role_title": "руководитель",
            "company_name": "LocalOS",
            "created_by": "user-1",
        },
        {"contact_type": "telegram"},
        candidate,
        use_ai=True,
        generator=generator,
        reviewer=reviewer,
    )

    assert quality["passed"] is True
    assert quality["word_count"] <= 90
    assert len(draft_brief["signal"].split()) <= 28
    assert draft_brief["evidence_ids"] == ["evidence:clinic"]
    assert message.count("?") == 1


def test_prepare_first_message_rejects_failed_semantic_review():
    brief = {
        "lead_name": "Клиника",
        "signal": "В карточке не указан актуальный раздел услуг",
        "pain": "",
        "result": "короткий разбор карточки",
        "founder_story": "Я управлял локальным бизнесом и знаю работу с картами изнутри",
        "source_urls": ["https://maps.example/clinic"],
        "evidence_ids": ["evidence:clinic"],
        "evidence_fresh": True,
        "suppression_safe": True,
        "cta": "Прислать короткий разбор?",
    }
    candidate = {
        "id": "personalization-1",
        "evidence_id": "evidence:clinic",
        "evidence_ids": ["evidence:clinic"],
        "observed_fact": brief["signal"],
        "bridge": "Можно проверить карточку без неподтверждённых обещаний",
        "source_url": "https://maps.example/clinic",
        "freshness": "current_snapshot",
        "founder_story": brief["founder_story"],
        "next_step": brief["result"],
    }

    def generator(_prompt, **_kwargs):
        return json.dumps({
            "schema_version": "1.0",
            "touches": [{
                "sequence_index": 0,
                "channel": "telegram",
                "angle": "founder_story",
                "opening_style": "direct",
                "cta_intent": "send_short_review",
                "evidence_ids": ["evidence:clinic"],
                "observation": brief["signal"],
                "problem_hypothesis": None,
                "relevance_bridge": candidate["bridge"],
            }],
        }, ensure_ascii=False)

    def reviewer(_prompt, **_kwargs):
        return json.dumps({
            "schema_version": "1.0",
            "reviews": [{
                "sequence_index": 0,
                "scores": {criterion: 2 for criterion in QUALITY_CRITERIA},
                "total_score": 18,
                "verdict": "revise",
                "reason_codes": ["STYLE_VIOLATION"],
                "notes": ["Слишком формально"],
            }],
        }, ensure_ascii=False)

    try:
        prepare_first_message(
            {"name": "Клиника"},
            {"workstream_type": "localos_sales"},
            brief,
            {"display_name": "Алексей", "role_title": "основатель", "company_name": "LocalOS"},
            {"contact_type": "telegram"},
            candidate,
            use_ai=True,
            generator=generator,
            reviewer=reviewer,
        )
    except PersonalizationGenerationError as error:
        assert error.code == "semantic_review_failed"
        assert provider_error_is_retryable(error) is True
    else:
        raise AssertionError("Semantic review failure must reject the first message")


def test_quality_gate_rejects_unproven_percentages_and_template_claims():
    quality = evaluate_first_message(
        "Здравствуйте! Вы недополучаете клиентов. Внедрим под ключ и дадим +30-80%. Интересно?",
        {"result": "рост обращений", "proof": ""},
    )

    assert quality["passed"] is False
    assert "Найдено неподтверждённое обещание" in quality["failures"]


def test_quality_gate_does_not_treat_percentage_in_recipient_name_as_a_claim():
    quality = evaluate_first_message(
        "Здравствуйте, Дыши на 100%! По данным аудита карточки: всего услуг - 30; "
        "с ценой - 14. Могу прислать короткий разбор?",
        {
            "lead_name": "Дыши на 100%",
            "signal": "По данным аудита карточки: всего услуг - 30; с ценой - 14.",
            "result": "короткий разбор",
        },
    )

    assert "Процент не подтверждён доказательством" not in quality["failures"]


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
    assert provider_error_is_retryable(
        PersonalizationGenerationError("ai_generation_failed", "retry")
    ) is True
    assert provider_error_is_retryable(
        MessageQualityError("message_quality_failed", "fix evidence")
    ) is False


def test_failed_enrichment_exposes_an_actionable_workstream_state():
    cursor = FailureCursor()

    result = fail_enrichment_job(
        cursor,
        {"id": "job-1", "attempt_count": 2, "max_attempts": 2},
        MessageQualityError("message_quality_failed", "Текст не прошёл quality gate"),
    )

    assert result["status"] == "failed"
    assert cursor.executions[0][1][4] == "message_quality_failed"
    workstream_query, workstream_params = cursor.executions[1]
    assert "lifecycle_status" in workstream_query
    assert "needs_attention" in workstream_query
    assert workstream_params == (
        "failed",
        "Текст не прошёл quality gate",
        "failed",
        "job-1",
    )


def test_contact_intelligence_migration_keeps_one_company_model():
    source = (ROOT / "alembic_migrations/versions/20260715_add_contact_intelligence.py").read_text()

    assert "CREATE TABLE IF NOT EXISTS lead_contact_points" in source
    assert "CREATE TABLE IF NOT EXISTS lead_enrichment_jobs" in source
    assert "CREATE TABLE IF NOT EXISTS outreach_sender_profiles" in source
    assert "CREATE TABLE IF NOT EXISTS prospectingleads" not in source
    assert "selected_contact_point_id" in source


def test_sender_profile_assigns_statuses_to_offers_voice_and_forbidden_claims():
    backend_source = (ROOT / "src/api/prospecting/contact_intelligence_routes.py").read_text()
    save_start = backend_source.index("def _save_sender_profile")
    save_end = backend_source.index("\n\n@admin_prospecting_bp.route", save_start)
    save_block = backend_source[save_start:save_end]
    frontend_source = (
        ROOT / "frontend/src/components/prospecting/OutreachSenderProfileSetup.tsx"
    ).read_text()

    assert 'allowed_offers = normalize_facts(data.get("allowed_offers"))' in save_block
    assert 'forbidden_claims = normalize_facts(data.get("forbidden_claims"))' in save_block
    assert 'voice_examples = normalize_facts(data.get("voice_examples"))' in save_block
    assert "allowedOffers: factsToText(profile.allowed_offers_json)" in frontend_source
    assert "forbiddenClaims: factsToText(profile.forbidden_claims_json)" in frontend_source
    assert "voiceExamples: factsToText(profile.voice_examples_json)" in frontend_source


def test_partnership_sender_profile_guides_user_with_completeness_and_business_services():
    backend_source = (ROOT / "src/api/prospecting/contact_intelligence_routes.py").read_text()
    route_start = backend_source.index("def partnership_sender_profile")
    route_block = backend_source[route_start:]
    frontend_source = (
        ROOT / "frontend/src/components/prospecting/OutreachSenderProfileSetup.tsx"
    ).read_text()

    assert '"profile_completeness": completeness' in route_block
    assert '"services_source": "business_services"' in route_block
    assert '"requires_confirmation": True' in route_block
    assert "payload?.profile?.confirmed_at" in frontend_source
    assert "Профиль сохранён, но пока не подтверждён" in frontend_source
    assert "Что нужно заполнить" in frontend_source
    assert "Сохранить и подтвердить" in frontend_source


def test_contact_intelligence_runtime_has_no_message_send_capability():
    source = (ROOT / "src/services/contact_intelligence_service.py").read_text()

    assert "send_message(" not in source
    assert "userbot_send" not in source
    assert "outreachsendqueue" not in source
    assert "CASE WHEN job.status = 'retry_wait' THEN 0 ELSE 1 END" in source


def test_worker_uses_database_wrapper_cursor_contract():
    source = (ROOT / "src" / "worker.py").read_text(encoding="utf-8")
    start = source.index("def _process_contact_intelligence_if_due()")
    end = source.index("\ndef _prepare_contact_intelligence_room", start)
    worker_block = source[start:end]

    assert "db.conn.cursor(cursor_factory=" not in worker_block
    assert "db.conn.cursor()" in worker_block
    assert 'PROSPECTING_CONTACT_INTELLIGENCE_BATCH_SIZE", "1"' in worker_block
    assert "min(20" in worker_block
    assert "if not _process_one_contact_intelligence_job():" in worker_block


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
