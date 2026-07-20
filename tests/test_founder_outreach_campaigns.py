import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask

from services.outreach_campaign_service import (
    _aggregate_quality_gate,
    _contact_outreach_rank,
    _message_for_angle,
    _review_record,
    _quality_gate,
    _recipient_contact_eligible,
    build_evidence_ledger,
    build_pilot_readiness,
    build_personalization_candidates,
    _localos_representative_profile,
    resolve_sender_mode,
)
from scripts.backfill_partnership_match_artifacts import _skip_reason


ROOT = Path(__file__).resolve().parents[1]


def test_contact_intelligence_job_serialization_is_independent_from_message_gating():
    source = (ROOT / "src/api/prospecting/contact_intelligence_routes.py").read_text()
    serialize_start = source.index("def _serialize_job")
    serialize_end = source.index("\n\ndef _load_workstream", serialize_start)
    load_start = source.index("def _load_intelligence")
    load_end = source.index("\n\ndef _save_sender_profile", load_start)

    assert "draft_row" not in source[serialize_start:serialize_end]
    assert "first_message = (" in source[load_start:load_end]
    assert source[load_start:load_end].index("profile_completeness =") < source[load_start:load_end].index("first_message = (")
    assert 'draft_payload["requires_regeneration"]' in source[load_start:load_end]


def test_outdated_generation_is_blocked_at_approval_and_dispatch():
    campaign_source = (ROOT / "src/services/outreach_campaign_service.py").read_text()
    approve_start = campaign_source.index("def approve_campaign")
    approve_end = campaign_source.index("\n\ndef change_campaign_status", approve_start)
    approve_block = campaign_source[approve_start:approve_end]
    safety_source = (ROOT / "src/services/outreach_safety_service.py").read_text()
    preflight_start = safety_source.index("def run_dispatch_preflight")
    preflight_end = safety_source.index("\n\ndef persist_preflight_result", preflight_start)
    preflight_block = safety_source[preflight_start:preflight_end]
    api_source = (ROOT / "src/api/outreach_campaign_api.py").read_text()

    assert "generation_contract_current(" in approve_block
    assert "Campaign generation is outdated; create a new preview" in approve_block
    assert "generation_contract_current(" in preflight_block
    assert '"generation_contract_outdated"' in preflight_block
    assert 'campaign["requires_regeneration"]' in api_source


def test_channel_setup_gap_can_be_saved_as_draft_but_not_approved():
    api_source = (ROOT / "src/api/outreach_campaign_api.py").read_text()
    frontend_source = (ROOT / "frontend/src/components/prospecting/AdminLeadRegistry.tsx").read_text()
    campaign_source = (ROOT / "src/services/outreach_campaign_service.py").read_text()
    approve_start = campaign_source.index("def approve_campaign")
    approve_end = campaign_source.index("\n\ndef change_campaign_status", approve_start)
    approve_block = campaign_source[approve_start:approve_end]

    assert 'preview.get("status") in {"ready", "needs_channel_setup"}' in api_source
    assert "['ready', 'needs_channel_setup'].includes" in frontend_source
    assert "Сохранить черновик версии" in frontend_source
    assert "senders_ready" in approve_block
    assert "channels_ready" in approve_block


def test_campaign_approval_uses_sender_mode_scope_preflight():
    campaign_source = (ROOT / "src/services/outreach_campaign_service.py").read_text()
    approve_start = campaign_source.index("def approve_campaign")
    approve_end = campaign_source.index("\n\ndef change_campaign_status", approve_start)
    approve_block = campaign_source[approve_start:approve_end]

    assert "sender_scope_preflight_reason({**campaign, **touch})" in approve_block
    assert "s.scope_type <> c.scope_type" not in approve_block
    assert "COALESCE(s.business_id, '') <> COALESCE(c.business_id, '')" not in approve_block


def test_personalization_requires_confirmed_founder_profile_and_sourced_evidence():
    context = {
        "lead_name": "Тестовая компания",
        "rating": 4.2,
        "reviews_count": 17,
        "source_url": "https://example.test/maps/card",
        "updated_at": "2026-07-16T10:00:00Z",
        "research": {},
        "sender_profile": {
            "display_name": "Алексей",
            "role_title": "Основатель",
            "company_name": "LocalOS",
            "competence_story": "Мы сами управляли локальным бизнесом и знаем работу с картами изнутри.",
            "confirmed_at": "2026-07-16T10:00:00Z",
            "proof_points_json": [{"fact": "Проводили публичные аудиты карточек", "status": "approved"}],
            "allowed_offers_json": [{
                "fact": "Могу прислать короткий аудит карточки.",
                "status": "approved",
            }],
            "forbidden_claims_json": ["Не обещать рост обращений"],
            "voice_examples_json": ["Здравствуйте! Могу прислать короткий разбор?"],
            "outreach_context_json": {
                "competence_story_status": "approved",
                "audience": "Владельцы локального бизнеса",
            },
        },
    }

    evidence = build_evidence_ledger(context)
    candidates = build_personalization_candidates(context, evidence)

    assert evidence[0]["fact"] == "Рейтинг - 4,2; публичных отзывов - 17."
    assert evidence[0]["source_url"] == "https://example.test/maps/card"
    assert candidates[0]["observed_fact"] == evidence[0]["fact"]
    assert candidates[0]["evidence_ids"] == [evidence[0]["id"]]
    assert candidates[0]["problem_hypothesis"] is None
    assert candidates[0]["problem_hypothesis_status"] == "missing"
    assert candidates[0]["relevance_to_offer"] == candidates[0]["bridge"]
    assert candidates[0]["founder_story"].startswith("Мы сами управляли")
    assert candidates[0]["next_step"] == "Могу прислать короткий аудит карточки."

    context["sender_profile"]["confirmed_at"] = None
    assert build_personalization_candidates(context, evidence) == []


def test_sender_modes_are_explicit_and_never_fall_back_across_motions():
    assert resolve_sender_mode("localos_sales") == "localos"
    assert resolve_sender_mode("client_partnership") == "partner_business"
    assert resolve_sender_mode("client_partnership", "localos_for_partner") == "localos_for_partner"

    for motion, mode in (
        ("localos_sales", "partner_business"),
        ("client_partnership", "localos"),
    ):
        try:
            resolve_sender_mode(motion, mode)
        except ValueError:
            pass
        else:
            raise AssertionError("Cross-motion sender fallback must be rejected")


def test_only_superadmin_can_choose_localos_for_partner():
    from api.outreach_campaign_api import _authorized_sender_mode

    workstream = {"workstream_type": "client_partnership"}
    assert _authorized_sender_mode(
        workstream,
        "localos_for_partner",
        {"is_superadmin": True},
    ) == "localos_for_partner"
    try:
        _authorized_sender_mode(
            workstream,
            "localos_for_partner",
            {"is_superadmin": False},
        )
    except PermissionError:
        pass
    else:
        raise AssertionError("Business user must not use the LocalOS platform identity")


def test_localos_representative_uses_localos_identity_and_partner_offer():
    combined = _localos_representative_profile({
        "business_service_count": 4,
        "platform_sender_profile": {
            "id": "localos-profile",
            "display_name": "Алексей",
            "company_name": "LocalOS",
            "competence_story": "Создаю LocalOS на основе практики локального маркетинга.",
            "proof_points_json": [{"fact": "Проверили 100 карточек", "status": "approved"}],
            "allowed_offers_json": ["Аудит карточки"],
            "forbidden_claims_json": ["Не обещать рост"],
            "voice_examples_json": ["Здравствуйте! Есть короткое предложение."],
            "outreach_context_json": {"competence_story_status": "approved"},
            "confirmed_at": "2026-07-20T12:00:00Z",
        },
        "business_sender_profile": {
            "id": "partner-profile",
            "allowed_offers_json": ["Совместный день открытых дверей"],
            "forbidden_claims_json": ["Не обещать поток клиентов"],
            "outreach_context_json": {
                "audience": "Семьи с детьми",
                "desired_partner_types": ["Детские центры"],
            },
            "confirmed_at": "2026-07-20T12:00:00Z",
        },
    })

    assert combined["id"] == "localos-profile"
    assert combined["company_name"] == "LocalOS"
    assert combined["allowed_offers_json"] == ["Совместный день открытых дверей"]
    assert combined["outreach_context_json"]["audience"] == "Семьи с детьми"
    assert combined["_represented_profile_id"] == "partner-profile"


def test_localos_for_partner_message_discloses_representation():
    message = _message_for_angle(
        "signal",
        {
            "recipient": "Потенциальный партнёр",
            "sender": "Алексей",
            "sender_role": "основатель",
            "sender_company": "LocalOS",
            "observed_fact": "В карточке указаны семейные занятия",
            "bridge": "У аудиторий есть реальное пересечение",
            "founder_story": "Мы проверяем совместимость локальных услуг",
            "next_step": "короткий вариант партнёрского теста",
            "representation_disclosure": (
                'Я пишу от LocalOS и представляю бизнес "Шансик" '
                "в этом партнёрском предложении."
            ),
        },
        {"story": "Мы проверяем совместимость локальных услуг"},
        [],
    )

    assert "пишу от LocalOS" in message
    assert 'представляю бизнес "Шансик"' in message


def test_partner_compatibility_is_valid_evidence_without_invented_problem():
    context = {
        "workstream_type": "client_partnership",
        "lead_name": "Партнёр",
        "source_url": "https://example.test/partner",
        "updated_at": "2026-07-16T10:00:00Z",
        "research": {},
        "partnership_match": {
            "match_score": 84,
            "recipient_observation": "В публичной карточке указаны услуги: фитнес, детские секции.",
            "compatibility_hypothesis": "Гипотеза для проверки: у компаний может совпадать семейная аудитория.",
            "relevance_bridge": "Есть основание проверить один безопасный партнёрский тест.",
        },
    }

    evidence = build_evidence_ledger(context)

    assert evidence == [
        {
            "id": "partnership-compatibility",
            "kind": "service_compatibility",
            "fact": "В публичной карточке указаны услуги: фитнес, детские секции.",
            "status": "observed",
            "source_url": "https://example.test/partner",
            "observed_at": "2026-07-16T10:00:00Z",
            "freshness": "current_snapshot",
            "confidence": 0.84,
            "hypothesis": "Гипотеза для проверки: у компаний может совпадать семейная аудитория.",
            "relevance": "Есть основание проверить один безопасный партнёрский тест.",
        }
    ]


def test_internal_partner_match_explanation_is_never_promoted_to_observed_evidence():
    context = {
        "workstream_type": "client_partnership",
        "lead_name": "Партнёр",
        "source_url": "https://example.test/partner",
        "updated_at": "2026-07-18T10:00:00Z",
        "research": {},
        "partnership_match": {
            "match_score": 62,
            "score_explanation": (
                "Сопоставлено услуг: ваши 12, партнёра 9. "
                "Прямые пересечения: массаж, восстановление."
            ),
        },
    }

    evidence = build_evidence_ledger(context)

    assert evidence == []

    context["partnership_match"]["recipient_observation"] = "В публичной карточке указана услуга: массаж."
    context["partnership_match"]["match_score"] = 39
    assert build_evidence_ledger(context) == []


def test_structured_audit_evidence_stays_primary_when_saved_research_has_review_first():
    context = {
        "research": {
            "evidence_json": [
                {
                    "id": "review-1",
                    "kind": "review",
                    "fact": "В публичном отзыве отмечено: «Долго ждал ответа».",
                    "status": "observed",
                    "source_url": "https://example.test/maps/review",
                    "observed_at": "2026-07-10T10:00:00Z",
                    "freshness": "fresh",
                    "confidence": 0.9,
                    "relevance": "Публичный клиентский сигнал",
                },
                {
                    "id": "audit-1",
                    "kind": "map_issue",
                    "fact": "В аудите публичной карточки найдено 20 услуг, цена указана у 5.",
                    "status": "observed",
                    "source_url": "https://localos.pro/company-audit",
                    "observed_at": "2026-07-16T10:00:00Z",
                    "freshness": "fresh",
                    "confidence": 0.95,
                    "relevance": "Есть конкретный элемент карточки для короткого разбора",
                },
            ],
        },
    }

    evidence = build_evidence_ledger(context)

    assert evidence[0]["id"] == "audit-1"
    assert evidence[0]["fact"] == (
        "По данным аудита карточки: всего услуг - 20; с ценой - 5."
    )
    assert evidence[-1]["kind"] == "review"


def test_saved_compact_rating_is_normalized_without_repeating_card_prefix():
    context = {
        "research": {
            "evidence_json": [
                {
                    "id": "rating-1",
                    "kind": "map_issue",
                    "fact": "В публичной карточке: рейтинг — 3,9, отзывов — 8.",
                    "status": "observed",
                    "source_url": "https://example.test/maps/clinic",
                    "observed_at": "2026-07-17T10:00:00Z",
                    "freshness": "fresh",
                    "confidence": 0.95,
                    "relevance": "Проверка рейтинга и отзывов",
                },
            ],
        },
    }

    evidence = build_evidence_ledger(context)

    assert evidence[0]["fact"] == "Рейтинг - 3,9; публичных отзывов - 8."


def test_saved_compact_service_fact_is_normalized_to_style_contract():
    context = {
        "research": {
            "evidence_json": [
                {
                    "id": "services-1",
                    "kind": "map_issue",
                    "fact": "По данным аудита, услуг в карточке — 60, с указанной ценой — 15.",
                    "status": "observed",
                    "source_url": "https://localos.pro/salon-audit",
                    "observed_at": "2026-07-17T10:00:00Z",
                    "freshness": "fresh",
                    "confidence": 0.95,
                    "relevance": "Проверка наполнения цен",
                },
            ],
        },
    }

    evidence = build_evidence_ledger(context)

    assert evidence[0]["fact"] == (
        "По данным аудита карточки: всего услуг - 60; с ценой - 15."
    )


def test_preview_content_can_pass_before_channel_permission_is_granted():
    observed_fact = "В аудите публичной карточки найдено 20 услуг, цена указана у 5."
    bridge = "Это можно проверить в коротком разборе карточки"
    text = f"Клиника, здравствуйте! {observed_fact} {bridge}. Прислать короткий разбор?"

    gate = _quality_gate(
        text,
        {
            "observed_fact": observed_fact,
            "recipient": "Клиника",
            "bridge": bridge,
            "source_url": "https://localos.pro/clinic-audit",
            "evidence_status": "observed",
            "freshness": "fresh",
            "confidence": 0.95,
            "next_step": "Короткий разбор",
        },
        {"forbidden_claims": []},
        channel="email",
        channel_status="permission_required",
        suppressed=False,
    )

    assert gate["checks"]["channel_fit"] is True
    assert gate["passed"] is True
    assert gate["criterion_scores"] == {
        "source_validity": 2,
        "observation_accuracy": 2,
        "freshness_and_why_now": 2,
        "offer_bridge": 2,
        "recipient_specificity": 2,
        "proof_integrity": 2,
        "channel_fit": 2,
        "single_cta_and_length": 2,
        "state_and_suppression_safety": 2,
    }
    assert gate["total_score"] == 18
    assert gate["reason_codes"] == []


def test_founder_message_does_not_repeat_company_in_role():
    message = _message_for_angle(
        "founder_story",
        {
            "recipient": "Клиника",
            "sender": "Александр",
            "sender_role": "руководитель LocalOS",
            "sender_company": "LocalOS",
            "observed_fact": "В аудите найдено 20 услуг, цена указана у 5",
            "bridge": "Есть конкретная тема для проверки",
            "founder_story": "Я развиваю LocalOS на основе работы с данными локальных бизнесов",
            "next_step": "Короткий разбор из трёх пунктов",
        },
        {"forbidden_claims": []},
        [],
    )

    assert "руководитель LocalOS в LocalOS" not in message
    assert 'Пишу по поводу карточки "Клиника"' in message
    assert not any(mark in message for mark in ("—", "«", "»"))
    assert "\n\n" in message
    assert message.count("?") == 1


def test_outreach_contact_selection_rejects_platform_and_hr_addresses():
    platform = {
        "contact_type": "email",
        "value": "info@dikidi.net",
        "verification_status": "confirmed_source",
        "confidence": 0.86,
        "source_type": "official_website",
        "source_url": "https://dikidi.net/profile/salon",
    }
    hr = {
        "contact_type": "email",
        "value": "hr_bd@burobeauty.ru",
        "verification_status": "confirmed_source",
        "confidence": 0.86,
        "source_type": "official_website",
        "source_url": "https://burobeauty.ru/contacts",
    }
    info = {
        "contact_type": "email",
        "value": "info@burobeauty.ru",
        "verification_status": "confirmed_source",
        "confidence": 0.62,
        "source_type": "map_card",
        "source_url": "https://yandex.ru/maps/org/burobeauty",
    }
    sales = {
        "contact_type": "email",
        "value": "sales_bd@burobeauty.ru",
        "verification_status": "confirmed_source",
        "confidence": 0.86,
        "source_type": "official_website",
        "source_url": "https://burobeauty.ru/contacts",
    }
    unverified = {
        "contact_type": "email",
        "value": "hello@burobeauty.ru",
        "verification_status": "valid_format",
        "confidence": 0.72,
        "source_type": "map_card",
        "source_url": "https://yandex.ru/maps/org/burobeauty",
    }

    assert _recipient_contact_eligible(platform) is False
    assert _recipient_contact_eligible(hr) is False
    assert _recipient_contact_eligible(unverified) is False
    assert _recipient_contact_eligible(info) is True
    assert sorted([sales, info], key=_contact_outreach_rank)[0]["value"] == "info@burobeauty.ru"


def test_quality_gate_blocks_machine_language_and_raw_negative_review_quote():
    candidate = {
        "observed_fact": "В публичном отзыве отмечено: «Долго ждал ответа». ",
        "recipient": "Клиника",
        "bridge": "Отзыв даёт проверяемую тему для полезного разбора",
        "evidence_kind": "review",
        "source_url": "https://example.test/maps/review",
        "evidence_status": "observed",
        "freshness": "fresh",
        "confidence": 0.9,
        "next_step": "Короткий разбор",
    }
    message = (
        "Клиника, здравствуйте! В публичном отзыве отмечено: «Долго ждал ответа». "
        "Отзыв даёт проверяемую тему для полезного разбора. Прислать короткий разбор?"
    )

    gate = _quality_gate(
        message,
        candidate,
        {"forbidden_claims": []},
        channel="telegram",
        channel_status="ready",
        suppressed=False,
    )

    assert gate["passed"] is False
    assert "machine_language_detected" in gate["blocking_reasons"]
    assert "sensitive_review_requires_manual_rewrite" in gate["blocking_reasons"]
    assert "style_contract_violation" in gate["blocking_reasons"]
    assert "STYLE_VIOLATION" in gate["canonical_reason_codes"]
    assert "SENSITIVE_TARGETING" in gate["canonical_reason_codes"]


def test_quality_gate_blocks_precise_but_weak_price_coverage_signal():
    candidate = {
        "observed_fact": "По данным аудита, услуг в карточке - 145, с указанной ценой - 130.",
        "recipient": "Салон",
        "bridge": "Можно проверить полноту цен",
        "evidence_kind": "map_issue",
        "source_url": "https://localos.pro/salon-audit",
        "evidence_status": "observed",
        "freshness": "fresh",
        "confidence": 0.95,
        "next_step": "Короткий разбор",
    }
    text = (
        "Салон, здравствуйте! По данным аудита, услуг в карточке - 145, "
        "с указанной ценой - 130. Можно проверить полноту цен. Прислать короткий разбор?"
    )

    gate = _quality_gate(
        text,
        candidate,
        {"forbidden_claims": []},
        channel="email",
        channel_status="ready",
        suppressed=False,
    )

    assert gate["passed"] is False
    assert "signal_too_weak_for_cold_outreach" in gate["blocking_reasons"]
    assert "DECORATIVE_PERSONALIZATION" in gate["reason_codes"]


def test_campaign_quality_gate_is_conservative_and_exposes_every_criterion():
    touches = [
        {
            "sequence_index": 0,
            "channel": "telegram",
            "quality_gate": {
                "criterion_scores": {
                    "source_validity": 2,
                    "observation_accuracy": 2,
                    "freshness_and_why_now": 2,
                    "offer_bridge": 2,
                    "recipient_specificity": 2,
                    "proof_integrity": 2,
                    "channel_fit": 2,
                    "single_cta_and_length": 2,
                    "state_and_suppression_safety": 2,
                },
                "total_score": 18,
                "max_score": 18,
                "verdict": "approve",
                "passed": True,
                "reason_codes": [],
            },
        },
        {
            "sequence_index": 1,
            "channel": "email",
            "quality_gate": {
                "criterion_scores": {
                    "source_validity": 2,
                    "observation_accuracy": 2,
                    "freshness_and_why_now": 2,
                    "offer_bridge": 1,
                    "recipient_specificity": 2,
                    "proof_integrity": 2,
                    "channel_fit": 2,
                    "single_cta_and_length": 2,
                    "state_and_suppression_safety": 2,
                },
                "total_score": 17,
                "max_score": 18,
                "verdict": "revise",
                "passed": False,
                "reason_codes": ["WEAK_OFFER_BRIDGE"],
            },
        },
    ]

    gate = _aggregate_quality_gate(touches)

    assert list(gate["criterion_scores"]) == [
        "source_validity",
        "observation_accuracy",
        "freshness_and_why_now",
        "offer_bridge",
        "recipient_specificity",
        "proof_integrity",
        "channel_fit",
        "single_cta_and_length",
        "state_and_suppression_safety",
    ]
    assert gate["criterion_scores"]["offer_bridge"] == 1
    assert gate["total_score"] == 17
    assert gate["verdict"] == "revise"
    assert gate["reason_codes"] == ["WEAK_OFFER_BRIDGE"]


def test_review_record_matches_canonical_outreach_contract_without_new_storage():
    generated_at = datetime(2026, 7, 19, 10, 0, tzinfo=timezone.utc)
    candidate = {
        "id": "personalization-1",
        "observed_fact": "В карточке указаны 12 услуг.",
        "source_url": "https://example.test/maps/company",
        "evidence_id": "evidence-1",
        "evidence_ids": ["evidence-1"],
        "relevance_to_offer": "Есть конкретная тема для короткой проверки карточки.",
        "confidence": 0.9,
    }
    touch = {
        "sequence_index": 0,
        "channel": "telegram",
        "day_offset": 0,
        "angle": "signal",
        "text": "В карточке указаны 12 услуг. Прислать короткий разбор?",
        "evidence_id": "evidence-1",
        "channel_status": "ready",
        "quality_gate": {"passed": True},
    }
    quality_gate = {
        "criterion_scores": {criterion: 2 for criterion in (
            "source_validity",
            "observation_accuracy",
            "freshness_and_why_now",
            "offer_bridge",
            "recipient_specificity",
            "proof_integrity",
            "channel_fit",
            "single_cta_and_length",
            "state_and_suppression_safety",
        )},
        "total_score": 18,
        "max_score": 18,
        "verdict": "approve",
        "passed": True,
        "reason_codes": [],
    }
    record = _review_record(
        {
            "lead_id": "lead-1",
            "lead_name": "Компания",
            "workstream_type": "localos_sales",
            "category": "Салон красоты",
            "source_url": "https://example.test/maps/company",
            "website": "https://example.test",
            "contacts": [{
                "contact_type": "email",
                "value": "hello@example.test",
                "source_url": "https://example.test/contacts",
                "verification_status": "confirmed_source",
                "confidence": 0.9,
                "observed_at": generated_at,
            }],
            "research": {
                "score": 82,
                "message_brief_json": {"segment": "локальный бизнес"},
                "limitations_json": [],
            },
        },
        ledger=[{
            "id": "evidence-1",
            "kind": "map_issue",
            "fact": "В карточке указаны 12 услуг.",
            "source_url": candidate["source_url"],
            "source_type": "map_card",
            "observed_at": generated_at,
            "confidence": 0.9,
            "status": "observed",
        }],
        candidates=[candidate],
        selected_candidate_id="personalization-1",
        touches=[touch],
        quality_gate=quality_gate,
        risks=[],
        generated_at=generated_at,
    )

    assert set(record) == {
        "schema_version",
        "lead_id",
        "motion",
        "identity",
        "contacts",
        "qualification",
        "evidence",
        "personalization_candidates",
        "selected_personalization_id",
        "touches",
        "quality_gate",
        "approval",
        "campaign",
        "outcome",
        "risks",
        "generated_at",
    }
    assert record["contacts"][0]["email_status"] == "verified"
    assert record["evidence"][0]["evidence_id"] == "evidence-1"
    assert record["evidence"][0]["observation"] == "В карточке указаны 12 услуг."
    assert record["personalization_candidates"][0]["personalization_id"] == "personalization-1"
    assert record["personalization_candidates"][0]["removal_test_passed"] is True
    assert record["touches"][0]["touch_no"] == 1
    assert record["touches"][0]["cta"] == "Прислать короткий разбор?"
    assert record["quality_gate"]["total_score"] == 18
    assert record["approval"]["status"] == "needs_review"
    assert record["campaign"]["status"] == "draft"
    assert json.loads(json.dumps(record, ensure_ascii=False))["schema_version"] == "1.0"


def test_campaign_builder_explains_facts_hypotheses_and_quality_scores():
    ui = (ROOT / "frontend/src/components/prospecting/OutreachCampaignBuilder.tsx").read_text()
    admin_ui = (ROOT / "frontend/src/components/prospecting/AdminLeadRegistry.tsx").read_text()

    for source in (ui, admin_ui):
        assert "Проверка всей цепочки" in source
        assert "Почему такая оценка" in source
        assert "Факт:" in source
        assert "Гипотеза:" in source
        assert "Почему это связано:" in source
    assert "QUALITY_CRITERION_LABELS" in ui
    assert "QUALITY_REASON_LABELS" in ui
    assert "outreachQualityCriterionLabels" in admin_ui
    assert "outreachQualityReasonLabels" in admin_ui


def test_frontend_chunking_does_not_split_radix_from_its_vendor_dependents():
    vite_config = (ROOT / "frontend/vite.config.ts").read_text()

    assert 'return "radix"' not in vite_config


def test_founder_story_type_is_not_replaced_by_a_more_lexically_relevant_proof():
    context = {
        "lead_name": "Клиника",
        "rating": 3.9,
        "reviews_count": 8,
        "source_url": "https://example.test/maps/clinic",
        "updated_at": "2026-07-17T10:00:00Z",
        "research": {},
        "sender_profile": {
            "display_name": "Александр",
            "role_title": "руководитель LocalOS",
            "company_name": "LocalOS",
            "competence_story": "Я развиваю LocalOS и сам разбираю публичные данные локальных компаний.",
            "proof_points_json": [
                {
                    "status": "observed",
                    "fact": "LocalOS собирает отзывы и рейтинг карточки в проверяемый аудит.",
                },
            ],
            "confirmed_at": "2026-07-17T10:00:00Z",
            "allowed_offers_json": ["Короткий разбор карточки."],
            "forbidden_claims_json": ["Не обещать гарантированный результат"],
            "voice_examples_json": ["Здравствуйте! Могу прислать короткий разбор?"],
            "outreach_context_json": {
                "competence_story_status": "approved",
                "audience": "Владельцы локального бизнеса",
            },
        },
    }

    evidence = build_evidence_ledger(context)
    candidate = build_personalization_candidates(context, evidence)[0]

    assert candidate["founder_story"].startswith("Я развиваю LocalOS")
    assert candidate["founder_proof"].startswith("LocalOS собирает отзывы")


def test_migration_keeps_existing_radar_access_but_never_backfills_send_permission():
    migration = (ROOT / "alembic_migrations/versions/20260716_add_founder_outreach_campaigns.py").read_text()

    assert "SELECT id, TRUE, FALSE" in migration
    assert "radar_enabled BOOLEAN NOT NULL DEFAULT TRUE" in migration
    assert "outreach_enabled BOOLEAN NOT NULL DEFAULT FALSE" in migration
    assert "sender_account_id UUID" in migration
    assert "outreach_campaign_events" in migration


def test_existing_radar_accounts_get_disabled_business_scoped_sender_bindings():
    migration = (
        ROOT
        / "alembic_migrations/versions/20260718_backfill_telegram_sender_bindings.py"
    ).read_text()

    assert "'business'" in migration
    assert "account.business_id IS NOT NULL" in migration
    assert "COALESCE(permission.outreach_enabled, FALSE)" in migration
    assert "'backfilled_from_radar', TRUE" in migration
    assert "scope_type = 'business'" in migration


def test_partner_match_backfill_rejects_manual_import_and_missing_service_evidence():
    assert _skip_reason({
        "source_url": "localos-doc://partnership/source/row",
        "search_payload_json": {"source": "manual_google_doc_import"},
        "services_json": [{"name": "Ошибочный fallback"}] * 3,
    }) == "manual_import_without_public_service_evidence"
    assert _skip_reason({
        "source_url": "https://maps.example/partner",
        "search_payload_json": {"source": "maps"},
        "services_json": [{"name": "Только одна услуга"}],
    }) == "partner_services_missing"
    assert _skip_reason({
        "source_url": "https://maps.example/partner",
        "search_payload_json": {"source": "maps"},
        "services_json": [{"name": "A"}, {"name": "B"}, {"name": "C"}],
    }) is None


def test_telegram_runtime_has_no_global_account_fallback_and_requires_sender_id():
    monitor = (ROOT / "src/services/telegram_opportunity_monitor.py").read_text()
    dispatcher = (ROOT / "src/api/prospecting/audit_generation.py").read_text()

    assert "TELEGRAM_OPPORTUNITY_MONITOR_ALLOW_GLOBAL_ACCOUNT" not in monitor
    assert "sender_account_required" in dispatcher
    assert "_resolve_telegram_sender(sender_account_id)" in dispatcher


def test_manual_first_touch_blocks_automatic_continuation_until_user_action():
    safety = (ROOT / "src/services/outreach_safety_service.py").read_text()
    campaigns = (ROOT / "src/services/outreach_campaign_service.py").read_text()

    assert "prior_manual_touch_pending" in safety
    assert "sequence_index < %s" in safety
    assert "status NOT IN ('manual_sent', 'manual_skipped')" in safety
    assert "preflight_reason = 'prior_manual_touch_pending'" in campaigns
    assert "delivery_status = 'queued'" in campaigns
    assert "status IN ('draft', 'approved', 'scheduled', 'queued'" in campaigns


def test_worker_syncs_replies_before_dispatch_and_fails_closed():
    worker = (ROOT / "src/worker.py").read_text()
    function_start = worker.index("def _dispatch_outreach_queue_if_due()")
    function_end = worker.index("\ndef _run_card_automation_if_due()", function_start)
    dispatch_block = worker[function_start:function_end]

    assert dispatch_block.index("_sync_telegram_app_replies") < dispatch_block.index("dispatch_due_outreach_queue")
    assert "OUTREACH_REPLY_SYNC_FAIL_CLOSED" in dispatch_block
    assert "skipped: reply_sync_failed" in dispatch_block


def test_pilot_dispatch_is_bounded_to_one_confirmed_campaign_queue_item():
    api = (ROOT / "src/api/outreach_campaign_api.py").read_text()
    dispatch = (ROOT / "src/services/outreach_dispatch_service.py").read_text()
    telegram_sync = (ROOT / "src/api/prospecting/audit_generation.py").read_text()
    ui = (ROOT / "frontend/src/components/prospecting/OutreachCampaignBuilder.tsx").read_text()
    admin_ui = (ROOT / "frontend/src/components/prospecting/AdminLeadRegistry.tsx").read_text()

    route_start = api.index("def pilot_dispatch_first_touch")
    route_end = api.index("\n\n@outreach_campaign_bp", route_start)
    route = api[route_start:route_end]

    assert "pilot-dispatch-first-touch" in api
    assert "Superadmin access required" not in route
    assert "_authorized_campaign" in route
    assert "confirm_campaign_id" in route
    assert "pilot_requires_global_dispatcher_disabled" in route
    assert route.index("_sync_telegram_app_replies") < route.index("dispatch_due_outreach_queue")
    assert "sender_account_id=sender_account_id" in route
    assert "sender_limit=1" in route
    assert "batch_size=1" in route
    assert "queue_id=queue_id" in route
    assert '"future_touches_dispatched": 0' in route
    assert "if queue_id:" in dispatch
    assert 'query += " AND q.id = %s"' in dispatch
    assert "SELECT COUNT(*) AS count" in dispatch
    assert "sent_row.get(\"count\")" in dispatch
    assert "Отправить только первое касание" in ui
    assert "confirm_campaign_id: selectedCampaign.id" in ui
    can_dispatch_start = ui.index("const canPilotDispatch")
    can_dispatch_end = ui.index("const pilotReplyReceived", can_dispatch_start)
    assert "is_superadmin" not in ui[can_dispatch_start:can_dispatch_end]
    assert "sender_account_id: str | None = None" in telegram_sync
    assert 'query += " AND q.sender_account_id = %s"' in telegram_sync
    assert "Следующий шаг: первое пилотное касание" in admin_ui
    assert "dispatchPilotFirstTouch" in admin_ui


def test_pilot_preflight_explains_exact_next_action_without_sending():
    state = {
        "campaign_status": "approved",
        "generation_current": True,
        "quality_passed": True,
        "touch_id": "touch-1",
        "touch_status": "scheduled",
        "channel": "telegram",
        "sender_account_id": "sender-1",
        "queue_id": "queue-1",
        "delivery_status": "queued",
    }
    ready = build_pilot_readiness(
        state,
        dispatch_preflight={"allowed": True, "reason_code": "preflight_passed"},
        global_dispatcher_enabled=False,
    )
    missing_permission = build_pilot_readiness(
        state,
        dispatch_preflight={"allowed": False, "reason_code": "sender_permission_revoked"},
        global_dispatcher_enabled=False,
    )

    assert ready["status"] == "ready"
    assert ready["can_dispatch_first_touch"] is True
    assert ready["messages_sent"] == 0
    assert missing_permission["reason_code"] == "sender_permission_revoked"
    assert missing_permission["can_dispatch_first_touch"] is False
    assert "Разрешите отправку" in missing_permission["next_action"]


def test_pilot_preflight_requires_explicit_check_before_ui_enables_dispatch():
    api = (ROOT / "src/api/outreach_campaign_api.py").read_text()
    service = (ROOT / "src/services/outreach_campaign_service.py").read_text()
    ui = (ROOT / "frontend/src/components/prospecting/OutreachCampaignBuilder.tsx").read_text()
    admin_ui = (ROOT / "frontend/src/components/prospecting/AdminLeadRegistry.tsx").read_text()

    assert "pilot-preflight" in api
    assert "build_pilot_readiness" in api
    assert "run_dispatch_preflight" in api
    assert '"messages_sent": 0' in service
    assert "Проверить готовность" in ui
    assert "pilotReadiness?.can_dispatch_first_touch" in ui
    assert ui.index("Проверить готовность") < ui.rindex("Отправить только первое касание")
    assert "Проверить готовность" in admin_ui
    assert "pilotReadiness?.can_dispatch_first_touch" in admin_ui
    assert "/pilot-preflight" in admin_ui
    assert admin_ui.index("Проверить готовность") < admin_ui.rindex("Отправить только первое касание")


def test_business_user_reaches_tenant_campaign_authorization_for_pilot(monkeypatch):
    module_path = ROOT / "src/api/outreach_campaign_api.py"
    spec = importlib.util.spec_from_file_location("outreach_campaign_api_pilot_test", module_path)
    assert spec and spec.loader
    outreach_campaign_api = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(outreach_campaign_api)

    class FakeConnection:
        def cursor(self, *args, **kwargs):
            return object()

        def rollback(self):
            return None

        def close(self):
            return None

    monkeypatch.delenv("OUTREACH_DISPATCH_ENABLED", raising=False)
    monkeypatch.setattr(
        outreach_campaign_api,
        "_require_auth",
        lambda: ({"user_id": "business-user", "is_superadmin": False}, None),
    )
    monkeypatch.setattr(outreach_campaign_api, "get_db_connection", lambda: FakeConnection())
    monkeypatch.setattr(outreach_campaign_api, "_authorized_campaign", lambda *args: None)

    app = Flask(__name__)
    app.register_blueprint(outreach_campaign_api.outreach_campaign_bp)
    response = app.test_client().post(
        "/api/outreach/campaigns/campaign-1/pilot-dispatch-first-touch",
        json={"confirm_campaign_id": "campaign-1"},
    )

    assert response.status_code == 404
    assert response.get_json()["error"] == "Campaign not found or access denied"


def test_pilot_reply_sync_is_bounded_to_campaign_and_sender():
    api = (ROOT / "src/api/outreach_campaign_api.py").read_text()
    email_sync = (ROOT / "src/services/outreach_email_reply_service.py").read_text()
    ui = (ROOT / "frontend/src/components/prospecting/OutreachCampaignBuilder.tsx").read_text()

    route_start = api.index("def pilot_reply_sync")
    route_end = api.index("\n\n@outreach_campaign_bp", route_start)
    route = api[route_start:route_end]

    assert "pilot-reply-sync" in api
    assert "_authorized_campaign" in route
    assert "batch_id=batch_id" in route
    assert "sender_account_id=sender_account_id" in route
    assert "campaign_id=campaign_id" in route
    assert '"future_touches_stopped"' in route
    assert "sender_account_id: str | None = None" in email_sync
    assert "campaign_id: str | None = None" in email_sync
    assert 'query += " AND id = %s"' in email_sync
    assert 'query += " AND touch.campaign_id = %s"' in email_sync
    assert "Проверить ответ сейчас" in ui
    assert "Ответ получен — цепочка остановлена" in ui


def test_telegram_ui_exposes_two_independent_permissions():
    component = (ROOT / "frontend/src/components/TelegramResearchSetup.tsx").read_text()

    assert "Telegram-радар" in component
    assert "Сообщения от вашего имени" in component
    assert "radar_enabled" in component
    assert "outreach_enabled" in component
    assert "stop-on-reply" in component
