from pathlib import Path

from src.api import admin_prospecting
from src.api.admin_prospecting import (
    _build_organika_partner_offer_text,
    _candidate_is_closed,
    _extract_card_profile_fields,
    _is_direct_partnership_map_card_url,
    _is_synthetic_partnership_lead,
    _lead_identity_matches_candidate,
    _partnership_next_best_action,
    _partnership_parse_is_terminal_closed,
    _partnership_source_requires_map_match,
    _select_partnership_map_candidate,
)
from src.core.audit_quality import evaluate_audit_quality
from src.core.audit_editorial import apply_audit_editorial_pass
from src.core import card_audit
from src.core.card_audit import (
    _build_reasoning_fields,
    _detect_audit_profile_details,
    _lead_snapshot_business_id,
    build_lead_card_preview_snapshot,
)
from scripts.backfill_partnership_match_artifacts import (
    _build_prerequisite_assessment,
    _has_verified_category_evidence,
    _is_direct_map_card_url,
    _match_skip_reason,
    _recovery_action,
    _should_persist_match_assessment,
    _skip_reason,
)
from scripts.prepare_partner_audit_rooms import _is_transient_parse_error


class PartnershipMatchCursor:
    def __init__(self, services, sender_profile, lead=None):
        self.services = services
        self.sender_profile = sender_profile
        self.lead = lead or {}
        self.query = ""

    def execute(self, query, _params=None):
        self.query = str(query)

    def fetchall(self):
        if "FROM userservices" in self.query:
            return [{"name": name} for name in self.services]
        return []

    def fetchone(self):
        if "FROM outreach_sender_profiles" in self.query:
            return self.sender_profile
        if "FROM prospectingleads" in self.query:
            return self.lead
        return None


def _complete_partner_sender_profile():
    return {
        "display_name": "Анна",
        "role_title": "основатель",
        "company_name": "Студия восстановления",
        "competence_story": "Команда помогает людям безопасно возвращаться к активности.",
        "confirmed_at": "2026-07-18T10:00:00+03:00",
        "proof_points_json": [{"status": "approved", "fact": "Провели 120 программ восстановления."}],
        "verified_cases_json": [],
        "allowed_offers_json": [{"status": "approved", "text": "Совместный пробный день."}],
        "voice_examples_json": [{"status": "approved", "text": "Добрый день! Вижу возможную точку для полезного теста."}],
        "forbidden_claims_json": [{"status": "approved", "text": "Не обещать гарантированный результат."}],
        "outreach_context_json": {
            "competence_story_status": "approved",
            "audience": "Люди, которые занимаются спортом и следят за здоровьем",
            "segments": ["спорт", "здоровье"],
            "desired_partner_types": ["фитнес-клубы"],
            "geography": "Санкт-Петербург",
        },
    }


def test_new_partner_profiles_are_detected_from_real_business_categories() -> None:
    cases = (
        ("Робототехника для детей", "education_children"),
        ("Семейный развлекательный центр", "family_entertainment"),
        ("Туристическое агентство", "travel"),
        ("Страховая компания", "financial_services"),
        ("Ремонт обуви и изготовление ключей", "repair_service"),
        ("Многофункциональный бизнес-центр", "commercial_center"),
    )
    for category, expected_profile in cases:
        details = _detect_audit_profile_details(category, category, {"category": category})
        assert details["profile"] == expected_profile
        assert details["confidence"] >= 0.7


def test_partner_profile_detection_covers_real_parser_categories() -> None:
    education = _detect_audit_profile_details(
        "Курсы иностранных языков / обучение за рубежом",
        "MBC School",
        {"category": "Курсы иностранных языков / обучение за рубежом"},
    )
    retail = _detect_audit_profile_details(
        "Детский магазин / магазин игрушек",
        "Детский мир",
        {"category": "Детский магазин / магазин игрушек"},
    )
    assert education["profile"] == "education_children"
    assert retail["profile"] == "fashion"


def test_specialized_profile_reasoning_uses_its_own_visitor_language() -> None:
    reasoning = _build_reasoning_fields(
        audit_profile="education_children",
        business_name="Роботрек",
        city="Санкт-Петербург",
        address="проспект Испытателей, 35",
        overview_text="Робототехника для детей",
        services_count=0,
        has_description=False,
        photos_count=2,
        reviews_count=10,
        unanswered_reviews_count=1,
    )
    text = " ".join(
        reasoning["best_fit_customer_profile"]
        + reasoning["search_intents_to_target"]
        + reasoning["positioning_focus"]
    ).lower()
    assert "родител" in text
    assert "возраст" in text
    assert "пациент" not in text
    assert "косметолог" not in text


def test_specialized_audit_does_not_invent_demo_services_or_revenue(monkeypatch) -> None:
    monkeypatch.setattr(card_audit, "_resolve_lead_business_snapshot", lambda _lead: {})
    audit = build_lead_card_preview_snapshot(
        {
            "id": "lead-education",
            "name": "Роботрек",
            "city": "Санкт-Петербург",
            "address": "проспект Испытателей, 35",
            "category": "Робототехника для детей",
            "source_url": "https://yandex.ru/maps/org/robotrek/123",
            "rating": 4.8,
            "reviews_count": 12,
            "search_payload_json": {},
        }
    )
    assert audit["audit_profile"] == "education_children"
    assert audit["services_preview"] == []
    assert audit["revenue_potential"]["label"] == "Без денежной оценки"


def test_partner_audit_uses_the_parsed_company_snapshot() -> None:
    lead = {
        "business_id": "organika-tenant",
        "parse_business_id": "partner-map-card",
        "intent": "partnership_outreach",
    }
    assert _lead_snapshot_business_id(lead) == "partner-map-card"
    assert _lead_snapshot_business_id({
        "business_id": "organika-tenant",
        "intent": "partnership_outreach",
    }) == ""
    assert _lead_snapshot_business_id({"business_id": "regular-business"}) == "regular-business"


def test_partnership_match_requires_complete_confirmed_sender_profile(monkeypatch) -> None:
    monkeypatch.setattr(admin_prospecting, "_is_partnership_openclaw_enabled", lambda: False)
    cursor = PartnershipMatchCursor(
        ["Массаж"],
        {
            "display_name": "Анна",
            "role_title": "основатель",
            "company_name": "Студия",
            "confirmed_at": None,
        },
    )

    result = admin_prospecting._compute_partnership_match_result(
        cursor,
        business_id="business-1",
        lead_id="lead-1",
        audit_json={"services_preview": [{"current_name": "Фитнес"}]},
    )

    assert result["match_score"] == 0
    assert "SENDER_PROFILE_INCOMPLETE" in result["reason_codes"]
    assert result["profile_completeness"]["ready"] is False
    assert result["readiness_code"] == "needs_sender_profile"
    assert result["next_action"] == "Заполните и подтвердите профиль отправителя"


def test_profile_guided_partnership_match_separates_fact_from_hypothesis(monkeypatch) -> None:
    monkeypatch.setattr(admin_prospecting, "_is_partnership_openclaw_enabled", lambda: False)
    cursor = PartnershipMatchCursor(
        ["Массаж", "Восстановление после тренировок", "СПА-программы"],
        _complete_partner_sender_profile(),
        {
            "name": "Фитнес-клуб Движение",
            "category": "Фитнес-клуб",
            "city": "Санкт-Петербург",
            "address": "Невский проспект, 1",
            "source_url": "https://maps.example/fitness",
            "website": "https://fitness.example",
        },
    )

    result = admin_prospecting._compute_partnership_match_result(
        cursor,
        business_id="business-1",
        lead_id="lead-1",
        audit_json={
            "services_preview": [
                {"current_name": "Фитнес"},
                {"current_name": "Групповые тренировки"},
                {"current_name": "Детские секции"},
            ],
        },
    )

    assert result["match_score"] >= 40
    assert "DESIRED_PARTNER_TYPE_MATCH" in result["reason_codes"]
    assert result["recipient_observation"].startswith("В публичной карточке указана категория")
    assert "указаны услуги" in result["recipient_observation"]
    assert result["source_url"] == "https://maps.example/fitness"
    assert result["compatibility_hypothesis"].startswith("Гипотеза для проверки")
    assert "может пересекаться аудитория" in result["compatibility_hypothesis"]
    assert result["relevance_bridge"]
    assert result["profile_completeness"]["ready"] is True
    assert result["readiness_code"] == "ready"


def test_profile_guided_partnership_match_keeps_unrelated_lead_below_threshold(monkeypatch) -> None:
    monkeypatch.setattr(admin_prospecting, "_is_partnership_openclaw_enabled", lambda: False)
    cursor = PartnershipMatchCursor(
        ["Массаж", "Восстановление после тренировок", "СПА-программы"],
        _complete_partner_sender_profile(),
        {
            "name": "Бухгалтерский центр",
            "category": "Бухгалтерские услуги",
            "city": "Санкт-Петербург",
            "address": "Невский проспект, 2",
            "source_url": "https://maps.example/accounting",
            "website": "https://accounting.example",
        },
    )

    result = admin_prospecting._compute_partnership_match_result(
        cursor,
        business_id="business-1",
        lead_id="lead-2",
        audit_json={
            "services_preview": [
                {"current_name": "Бухгалтерское сопровождение"},
                {"current_name": "Налоговый аудит"},
                {"current_name": "Расчёт заработной платы"},
            ],
        },
    )

    assert result["match_score"] < 40
    assert "DESIRED_PARTNER_TYPE_MISSING" in result["reason_codes"]
    assert result["relevance_bridge"] is None
    assert result["readiness_code"] == "needs_evidence"


def test_match_backfill_never_saves_incomplete_or_weak_results() -> None:
    assert _match_skip_reason({
        "match_score": 80,
        "reason_codes": ["SENDER_PROFILE_INCOMPLETE"],
    }) == "sender_profile_incomplete"
    assert _match_skip_reason({"match_score": 39, "reason_codes": []}) == "compatibility_below_threshold"
    assert _match_skip_reason({"match_score": 40, "reason_codes": []}) == "compatibility_evidence_missing"
    assert _match_skip_reason({
        "match_score": 40,
        "reason_codes": [],
        "recipient_observation": "В публичной карточке указана категория «фитнес».",
        "source_url": "https://maps.example/fitness",
    }) is None


def test_match_backfill_persists_assessment_without_promoting_weak_match() -> None:
    assert _should_persist_match_assessment("sender_profile_incomplete") is True
    assert _should_persist_match_assessment("compatibility_below_threshold") is True
    assert _should_persist_match_assessment("compatibility_evidence_missing") is True
    assert _should_persist_match_assessment("partner_services_missing") is False


def test_match_backfill_records_explicit_prerequisite_without_claiming_compatibility() -> None:
    assessment = _build_prerequisite_assessment(
        {
            "source_url": "https://yandex.ru/maps/org/test/123/",
            "parse_status": "processing",
        },
        "partner_services_missing",
    )

    assert assessment["assessment_kind"] == "prerequisite"
    assert assessment["readiness_code"] == "needs_evidence"
    assert assessment["recovery_action"] == "wait_for_parse"
    assert assessment["match_score"] == 0
    assert assessment["recipient_observation"] is None
    assert assessment["compatibility_hypothesis"] is None
    assert assessment["relevance_bridge"] is None
    assert "совместим" not in str(assessment["next_action"]).lower()


def test_partner_evidence_recovery_actions_are_specific() -> None:
    assert _recovery_action({}, "manual_import_without_public_service_evidence") == "find_public_card"
    assert _recovery_action({}, "public_source_missing") == "find_public_source"
    assert _recovery_action({}, "partner_services_missing") == "resolve_public_map_card"
    assert _recovery_action({"source_url": "https://yandex.ru/maps/org/test/123/"}, "partner_services_missing") == "start_parse"
    assert _recovery_action({"parse_status": "processing"}, "partner_services_missing") == "wait_for_parse"
    assert _recovery_action({"parse_status": "captcha"}, "partner_services_missing") == "resolve_captcha"
    assert _recovery_action({"parse_status": "error"}, "partner_services_missing") == "retry_parse"
    assert _recovery_action({
        "parse_status": "error",
        "parse_error": "apify_empty_dataset: empty dataset for business card parsing",
    }, "partner_services_missing") == "find_alternate_public_source"
    assert _recovery_action({
        "parse_status": "error",
        "parse_error": "business_closed:permanent_closed",
    }, "partner_services_missing") == "mark_closed_not_relevant"
    assert _recovery_action({"parse_status": "completed"}, "partner_services_missing", {
        "parse_context": {"last_parse_status": "lead_preview"},
    }) == "repair_recipient_identity_mapping"
    assert _recovery_action({"parse_status": "completed"}, "partner_services_missing", {
        "parse_context": {"last_parse_status": "completed"},
    }) == "evaluate_category_only_match"
    assert _recovery_action({"parse_business_id": "business-1"}, "partner_services_missing") == "retry_parse"


def test_partner_parse_recovery_is_bounded_and_never_sends_outreach() -> None:
    source = Path("scripts/backfill_partnership_match_artifacts.py").read_text()

    assert 'default=20' in source
    assert '"parse_limit": max(0, args.parse_limit)' in source
    assert '"external_send": False' in source
    assert '"prerequisite_assessments_saved": 0' in source
    assert "assessment_kind" in source
    assert "_enqueue_parse_task_for_business" in source
    assert 'recovery_action in {"start_parse", "retry_parse"}' in source


def test_partnership_pipeline_passes_open_lead_action_through_list_component() -> None:
    component = Path(
        "frontend/src/components/prospecting/PartnershipPipelineSections.tsx"
    ).read_text(encoding="utf-8")
    page = Path("frontend/src/pages/dashboard/PartnershipSearchPage.tsx").read_text(encoding="utf-8")

    props_start = component.index("type PartnershipPipelineListProps")
    component_end = component.index("type PartnershipPipelineBulkBarProps", props_start)
    pipeline_block = component[props_start:component_end]
    assert "onOpenLead: (leadId: string) => void;" in pipeline_block
    assert "onOpenLead," in pipeline_block
    assert "onOpenLead={onOpenLead}" in pipeline_block
    assert "onOpenLead={setSelectedLeadId}" in page


def test_verified_parsed_category_can_qualify_without_a_published_price_list() -> None:
    row = {
        "category": "Курсы иностранных языков",
        "source_url": "https://yandex.ru/maps/org/mbc/123",
        "parse_business_id": "parsed-business",
        "services_json": [],
    }
    snapshot = {
        "parse_context": {"last_parse_status": "completed"},
        "services_preview": [],
    }

    assert _has_verified_category_evidence(row, snapshot) is True
    assert _skip_reason(row, snapshot) is None
    assert _has_verified_category_evidence(row, {
        "parse_context": {"last_parse_status": "lead_preview"},
    }) is False


def test_direct_map_card_detection_rejects_search_and_directory_urls() -> None:
    assert _is_direct_map_card_url("https://yandex.ru/maps/org/mango/1158370126/") is True
    assert _is_direct_map_card_url("https://yandex.ru/maps/search/Mango") is False
    assert _is_direct_map_card_url("https://zoon.ru/msk/fitness/test") is False


def test_backend_resolves_non_card_sources_before_starting_parse() -> None:
    direct_url = "https://yandex.ru/maps/org/mango/1158370126/"
    search_url = "https://yandex.ru/maps/search/Mango"
    directory_url = "https://zoon.ru/msk/fitness/test"

    assert _is_direct_partnership_map_card_url(direct_url) is True
    assert _partnership_source_requires_map_match(direct_url) is False
    assert _partnership_source_requires_map_match(search_url) is True
    assert _partnership_source_requires_map_match(directory_url) is True
    assert _partnership_source_requires_map_match("localos-doc://partnership/lead") is True


def test_next_partner_action_explains_map_resolution_before_parse() -> None:
    resolve_action = _partnership_next_best_action({
        "partnership_stage": "imported",
        "source_url": "https://zoon.ru/msk/fitness/test",
    })
    parse_action = _partnership_next_best_action({
        "partnership_stage": "imported",
        "source_url": "https://yandex.ru/maps/org/mango/1158370126/",
    })

    assert resolve_action["code"] == "resolve_and_parse"
    assert resolve_action["label"] == "Найти карточку и собрать данные"
    assert parse_action["code"] == "run_parse"


def test_parsed_card_identity_uses_top_level_title_and_address() -> None:
    parsed = _extract_card_profile_fields({
        "title": "Доктор Лапушкин",
        "address": "Санкт-Петербург, Невский проспект, 1",
        "overview": {"_meta": {"source": "apify"}},
    })

    assert parsed["name"] == "Доктор Лапушкин"
    assert parsed["address"] == "Санкт-Петербург, Невский проспект, 1"


def test_sender_profile_confirmation_refreshes_only_the_selected_lead() -> None:
    page = Path("frontend/src/pages/dashboard/PartnershipSearchPage.tsx").read_text(encoding="utf-8")
    drawer = Path("frontend/src/components/prospecting/PartnershipLeadDetailDrawer.tsx").read_text(encoding="utf-8")
    profile = Path("frontend/src/components/prospecting/OutreachSenderProfileSetup.tsx").read_text(encoding="utf-8")
    api = Path("frontend/src/components/prospecting/partnershipApi.ts").read_text(encoding="utf-8")

    assert "onChanged?.({" in profile
    assert "confirmed: profileConfirmed" in profile
    assert "ready: Boolean(savedCompleteness?.ready)" in profile
    assert "onSenderProfileChanged={handleSenderProfileChanged}" in page
    assert "setMatchData(null);" in page
    assert "startPartnershipContactIntelligence(currentBusinessId, leadId, workstreamId)" in page
    assert "onChanged={onSenderProfileChanged}" in drawer
    assert "/contact-intelligence" in api


def test_wrong_parsed_card_is_not_accepted_only_because_source_id_matches() -> None:
    assert _lead_identity_matches_candidate(
        {
            "name": "Ромашка",
            "city": "Санкт-Петербург",
            "source_url": "https://yandex.ru/maps/org/doctor_lapushkin/123456789/",
        },
        candidate_name="Доктор Лапушкин",
        candidate_city="Санкт-Петербург, Невский проспект, 1",
        candidate_source_url="https://yandex.ru/maps/org/doctor_lapushkin/123456789/",
        candidate_external_id="123456789",
    ) is False


def test_identity_mismatch_points_user_to_card_repair() -> None:
    action = _partnership_next_best_action({
        "partnership_stage": "imported",
        "parse_status": "completed",
        "parsed_identity_status": "mismatch",
        "parsed_candidate_name": "Доктор Лапушкин",
    })

    assert action["code"] == "repair_recipient_identity_mapping"
    assert action["label"] == "Найти правильную карточку компании"
    assert "Доктор Лапушкин" in action["hint"]


def test_closed_partner_is_not_sent_back_to_parser() -> None:
    assert _partnership_parse_is_terminal_closed({
        "status": "error",
        "error_message": "business_closed:permanent_closed",
    }) is True
    assert _partnership_parse_is_terminal_closed({
        "status": "error",
        "error_message": "provider timeout 503",
    }) is False
    assert _partnership_parse_is_terminal_closed({
        "status": "completed",
        "error_message": "business_closed:permanent_closed",
    }) is False

    next_action = _partnership_next_best_action({
        "partnership_stage": "imported",
        "parse_status": "error",
        "parse_error": "business_closed:permanent_closed",
    })
    assert next_action["code"] == "mark_closed_not_relevant"


def test_empty_apify_dataset_points_user_to_alternate_source() -> None:
    next_action = _partnership_next_best_action({
        "partnership_stage": "imported",
        "parse_status": "error",
        "parse_error": "apify_empty_dataset: empty dataset for business card parsing",
    })

    assert next_action["code"] == "find_alternate_public_source"
    assert next_action["label"] == "Найти другой публичный источник"
    assert "официальный сайт" in next_action["hint"]


def test_partner_map_match_requires_confidence_and_margin() -> None:
    ambiguous, status = _select_partnership_map_candidate(
        [
            {"confidence": 0.91, "raw": {}},
            {"confidence": 0.86, "raw": {}},
        ]
    )
    assert ambiguous is None
    assert status == "ambiguous"

    confirmed, status = _select_partnership_map_candidate(
        [
            {"confidence": 0.93, "raw": {}},
            {"confidence": 0.82, "raw": {}},
        ]
    )
    assert confirmed is not None
    assert status == "confirmed"


def test_partner_map_search_retries_one_transient_provider_error(monkeypatch) -> None:
    calls = []

    def fake_search(_card, limit=5):
        calls.append(limit)
        if len(calls) == 1:
            return [], "provider timeout 503"
        return [{"confidence": 0.91, "yandex_maps_url": "https://yandex.ru/maps/org/123"}], None

    monkeypatch.setattr(admin_prospecting, "_find_yandex_candidates_for_partner_card", fake_search)
    candidates, error = admin_prospecting._find_yandex_candidates_for_partnership_lead(
        {"name": "Naomi", "city": "Санкт-Петербург"}
    )
    assert error is None
    assert len(candidates) == 1
    assert len(calls) == 2


def test_closed_candidate_and_synthetic_group_are_not_processed() -> None:
    assert _candidate_is_closed({"raw": {"businessStatus": "permanently_closed"}}) is True
    assert _is_synthetic_partnership_lead({"name": "Медицинские арендаторы", "category": "группа"}) is True
    assert _is_transient_parse_error("error", "business_closed:permanent_closed") is False
    assert _is_transient_parse_error("error", "provider timeout 503") is True


def test_audit_quality_blocks_technical_and_foreign_industry_copy() -> None:
    quality = evaluate_audit_quality(
        {
            "audit_profile": "education_children",
            "business": {"name": "Роботрек"},
            "summary_text": "Fallback payload предлагает консультацию косметолога.",
            "issue_blocks": [{"title": "Нужно лечение"}],
        },
        expected_name="Роботрек",
    )
    assert quality["passed"] is False
    codes = {flag["code"] for flag in quality["flags"]}
    assert "technical_copy" in codes
    assert "industry_drift" in codes


def test_uncertain_photo_copy_uses_the_business_profile() -> None:
    audit = apply_audit_editorial_pass(
        {
            "audit_profile": "fashion",
            "summary_text": "Проверили карточку магазина.",
            "issue_blocks": [
                {
                    "id": "photo_story_gap",
                    "title": "Фото не работают как витрина магазина",
                    "problem": "Карточка не показывает ассортимент.",
                    "evidence": "Фото требуют проверки.",
                    "fix": "Добавить фото товаров.",
                }
            ],
        }
    )
    evidence = audit["issue_blocks"][0]["evidence"].lower()
    assert "витрина" in evidence
    assert "ассортимент" in evidence
    assert "кабинет" not in evidence
    assert "стойка администратора" not in evidence


def test_organika_offer_has_one_safe_test_and_no_automatic_action() -> None:
    text = _build_organika_partner_offer_text(
        business_name="Органика",
        lead_name="Роботрек",
        audit_json={"audit_profile": "education_children"},
    ).lower()
    assert "родител" in text
    assert "20-минутн" in text
    assert "автоматической рассылки" in text
    assert "заранее не обещаются" in text


def test_organika_fashion_offer_names_the_shared_family_audience() -> None:
    text = _build_organika_partner_offer_text(
        business_name="Органика",
        lead_name="Acoola",
        audit_json={"audit_profile": "fashion"},
    ).lower()
    assert "семьи района" in text
    assert "детской одежды" in text
    assert "наличия конкретных товаров" in text
