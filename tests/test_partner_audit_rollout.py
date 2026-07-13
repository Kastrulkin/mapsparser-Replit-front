from src.api.admin_prospecting import (
    _build_organika_partner_offer_text,
    _candidate_is_closed,
    _is_synthetic_partnership_lead,
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
from scripts.prepare_partner_audit_rooms import _is_transient_parse_error


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
    }
    assert _lead_snapshot_business_id(lead) == "partner-map-card"
    assert _lead_snapshot_business_id({"business_id": "regular-business"}) == "regular-business"


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
