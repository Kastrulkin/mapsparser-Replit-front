import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from flask import Flask

from services.outreach_campaign_service import (
    DEFAULT_SEQUENCE,
    _aggregate_quality_gate,
    _contact_outreach_rank,
    _email_subject,
    _message_for_angle,
    _review_record,
    _quality_gate,
    _recipient_contact_eligible,
    _represented_business_opening,
    build_evidence_ledger,
    build_pilot_readiness,
    build_personalization_candidates,
    channel_availability,
    _localos_representative_profile,
    _normalize_touch_overrides,
    _publication_capability_snapshot,
    _resolve_next_sequence_channel,
    _strategy_dimensions,
    resolve_sender_mode,
)
from services.outreach_decision_service import (
    build_outreach_decision,
    offer_candidates,
    trust_candidates,
)
from services.outreach_founder_led_copy import (
    localos_beauty_segment,
    natural_observation,
    observation_is_grounded,
    select_approved_localos_case,
)
from services.outreach_signal_hypothesis_service import derive_pain_signal_hypotheses
from services.outreach_playbook import (
    APPROVED_LOCALOS_MESSAGE_EXAMPLES,
    B2B_METHOD_RULES,
)
from scripts.backfill_partnership_match_artifacts import _skip_reason


ROOT = Path(__file__).resolve().parents[1]


def test_estem_content_example_requires_configured_deidentified_yclients_transfer():
    example = next(
        item
        for item in APPROVED_LOCALOS_MESSAGE_EXAMPLES
        if item["key"] == "estem_yclients_content_time_v1"
    )

    assert example["status"] == "approved"
    assert "Посты для нескольких площадок" in example["text"]
    assert "а это отнимает время" in example["text"]
    assert "Если из YCLIENTS можно передавать" in example["text"]
    assert "без данных пациента" in example["text"]
    assert "публикация в Картах останется ручной" in example["text"]
    assert not any(
        phrase in example["text"].lower()
        for phrase in (
            "автоматически публикует",
            "после каждой услуги",
        )
    )
    assert any("знакомой работы и цены времени" in rule for rule in B2B_METHOD_RULES)
    assert any("выполненная услуга → пост" in rule for rule in B2B_METHOD_RULES)


def test_next_sequence_channel_reuses_ready_channel_after_unique_channels_end():
    assert _resolve_next_sequence_channel(
        ["telegram", "sms"],
        [{"channel": "telegram"}, {"channel": "email"}, {"channel": "sms"}],
    ) == "telegram"


def test_localos_default_sequence_uses_reviewed_six_touch_order():
    assert DEFAULT_SEQUENCE == (
        ("email", 0, "signal"),
        ("telegram", 3, "founder_story"),
        ("max", 7, "proof"),
        ("vk_manual", 12, "audit_step"),
        ("phone", 18, "phone_handoff"),
        ("email", 25, "integrated_system"),
    )


def test_every_outreach_email_subject_uses_approved_client_template():
    candidate = _private_beauty_founder_candidate()
    candidate["recipient"] = "FGF medical"

    assert _email_subject("signal", candidate) == "FGF medical | ЛокалОС | Сотрудничество"
    assert _email_subject("matching_authority", candidate) == "FGF medical | ЛокалОС | Сотрудничество"


def _private_beauty_founder_candidate():
    return {
        "recipient": "Доктор-косметолог Татьяна Прокура",
        "recipient_category": "Косметология / услуги частных специалистов",
        "recipient_segment": "private_beauty_specialist",
        "sender": "Александр Демьянов",
        "sender_role": "основатель LocalOS",
        "sender_company": "LocalOS",
        "sender_mode": "localos",
        "observed_fact": "Рейтинг - 4,2; публичных отзывов - 3.",
        "bridge": "Можно проверить, как карточка формирует доверие",
        "founder_story": (
            "За десять лет предпринимательства я видел малый бизнес как основатель "
            "и как разработчик систем автоматизации. Поэтому я создал LocalOS - "
            "чтобы превращать повторяющиеся задачи в понятные рабочие сценарии."
        ),
        "founder_proof": "LocalOS уже применяется более чем в 240 точках малого бизнеса.",
        "trust_statement": "Подтверждённый опыт основателя LocalOS",
        "next_step": "Короткий разбор",
        "evidence_kind": "map_issue",
        "evidence_status": "observed",
        "source_url": "https://example.test/maps/tatyana",
        "freshness": "current_snapshot",
    }


def _publication_capabilities(*channels):
    return {
        "schema": "localos_outreach_publication_capabilities_v1",
        "approval_required": True,
        "channels": list(channels),
        "supported_after_connection": ["telegram", "vk"],
        "manual_or_supervised_channels": ["yandex_maps", "two_gis"],
    }


def _publication_channel(
    platform,
    *,
    connected=False,
    provider_ready=False,
    publish_mode="api",
    status="missing_connection",
):
    return {
        "platform": platform,
        "connected": connected,
        "provider_ready": provider_ready,
        "publish_mode": publish_mode,
        "status": status,
    }


def test_event_distribution_without_connected_channels_uses_conditional_autopublish_and_omits_maps_without_evidence():
    candidate = _private_beauty_founder_candidate()
    candidate.update({
        "signal_combo": "recent_event_announcement",
        "observed_fact": 'В Telegram опубликовано: "21 августа - клиентский день".',
        "map_observation": "",
        "supporting_evidence": [],
        "evidence_kind": "telegram_post",
        "source_url": "https://t.me/example/1",
        "publication_capabilities": _publication_capabilities(),
    })

    message = _message_for_angle("signal", candidate, None, [])

    assert (
        "После подключения каналов и вашего подтверждения LocalOS автоматически "
        "публикует материалы в поддерживаемые каналы."
    ) in message
    assert "карт" not in message.lower()
    assert "\n\n\n" not in message


def test_content_reuse_names_only_connected_provider_ready_channels():
    candidate = _private_beauty_founder_candidate()
    candidate["publication_capabilities"] = _publication_capabilities(
        _publication_channel(
            "telegram",
            connected=True,
            provider_ready=True,
            status="ready",
        ),
        _publication_channel(
            "vk",
            connected=False,
            provider_ready=False,
        ),
        _publication_channel(
            "google_business",
            connected=True,
            provider_ready=False,
            status="provider_not_ready",
        ),
    )

    message = _message_for_angle("content_operations", candidate, None, [])

    assert "После вашего подтверждения LocalOS автоматически публикует материалы в Telegram." in message
    assert "VK и Telegram" not in message
    assert "Google" not in message
    assert "\n\n" in message
    assert "\n\n\n" not in message


def test_google_autopublish_requires_beta_connection_provider_ready_and_approval():
    candidate = _private_beauty_founder_candidate()
    candidate["publication_capabilities"] = _publication_capabilities(
        _publication_channel(
            "google_business",
            connected=True,
            provider_ready=True,
            status="ready",
        ),
    )

    message = _message_for_angle("content_operations", candidate, None, [])

    assert "Google Business Profile в beta-режиме" in message
    assert "После вашего подтверждения" in message


def test_maps_are_mentioned_only_with_recipient_map_evidence_and_never_as_autopublish():
    candidate = _private_beauty_founder_candidate()
    candidate.update({
        "signal_combo": "recent_event_announcement",
        "observed_fact": 'В Telegram опубликовано: "21 августа - клиентский день".',
        "map_observation": "Рейтинг - 4,1; публичных отзывов - 5.",
        "publication_capabilities": _publication_capabilities(),
    })

    message = _message_for_angle("signal", candidate, None, [])

    assert "картах" in message.lower()
    assert "автоматически публикует" in message
    assert "автоматически публикует на картах" not in message.lower()


def test_publication_snapshot_is_kept_in_strategy_dimensions():
    candidate = _private_beauty_founder_candidate()
    candidate["publication_capabilities"] = _publication_capabilities(
        _publication_channel(
            "telegram",
            connected=True,
            provider_ready=True,
            status="ready",
        ),
    )

    strategy = _strategy_dimensions(
        {"workstream_type": "localos_sales", "category": "Салон красоты"},
        {},
        candidate,
        {},
        channel="email",
        sequence_index=0,
        day_offset=0,
        angle="signal",
    )

    assert strategy["publication_capabilities"] == candidate["publication_capabilities"]


def test_publication_snapshot_fail_closes_google_and_never_marks_maps_api_ready(monkeypatch):
    monkeypatch.delenv("GOOGLE_BUSINESS_PUBLICATION_BETA_PROVIDER_READY", raising=False)
    monkeypatch.setattr(
        "services.outreach_campaign_service.social_post_service._build_channel_readiness",
        lambda _cursor, _business_id: [
            {"platform": "telegram", "publish_mode": "api", "ready": True, "status": "ready"},
            {"platform": "google_business", "publish_mode": "api", "ready": True, "status": "ready"},
            {
                "platform": "yandex_maps",
                "publish_mode": "openclaw_browser",
                "ready": True,
                "status": "supervised_ready",
            },
        ],
    )

    snapshot = _publication_capability_snapshot(object(), "business-1")
    by_platform = {item["platform"]: item for item in snapshot["channels"]}

    assert by_platform["telegram"]["provider_ready"] is True
    assert by_platform["google_business"]["provider_ready"] is False
    assert by_platform["google_business"]["status"] == "provider_not_ready"
    assert by_platform["yandex_maps"]["provider_ready"] is False
    assert snapshot["approval_required"] is True


def test_publication_snapshot_uses_bound_social_post_service_readiness(monkeypatch):
    import services.social_post_service as social_post_service

    calls = []

    def _production_readiness(_cursor, business_id):
        calls.append(business_id)
        return [
            {
                "platform": "telegram",
                "publish_mode": "api",
                "ready": True,
                "status": "ready",
                "missing_fields": [],
            },
            {
                "platform": "yandex_maps",
                "publish_mode": "openclaw_browser",
                "ready": True,
                "status": "supervised_ready",
                "missing_fields": [],
            },
        ]

    monkeypatch.setattr(
        social_post_service,
        "_build_channel_readiness",
        _production_readiness,
    )

    snapshot = _publication_capability_snapshot(object(), "business-1")
    by_platform = {item["platform"]: item for item in snapshot["channels"]}

    assert calls == ["business-1"]
    assert snapshot["source"] == "social_channel_readiness"
    assert by_platform["telegram"]["connected"] is True
    assert by_platform["telegram"]["provider_ready"] is True
    assert by_platform["yandex_maps"]["provider_ready"] is False


def test_touch_override_normalizes_paragraph_spacing_without_flattening():
    normalized = _normalize_touch_overrides([{
        "sequence_index": 0,
        "text": "Первый абзац.\n\n\n\nВторой абзац.",
    }])

    assert normalized[0]["text"] == "Первый абзац.\n\nВторой абзац."


def test_founder_led_beauty_recipe_uses_signal_only_as_conversation_entry():
    candidate = _private_beauty_founder_candidate()
    story = {
        "story": candidate["founder_story"],
        "proof": candidate["founder_proof"],
        "forbidden_claims": [],
    }
    messages = {
        angle: _message_for_angle(angle, candidate, story, [])
        for angle in ("signal", "founder_story", "proof", "integrated_system")
    }

    assert "3 отзыва и рейтинг 4,2" in messages["signal"]
    assert "проверяемые наблюдения и конкретные шаги" in messages["signal"]
    assert "сначала нужно работать с клиентами" not in messages["signal"]
    assert "3 отзыва" not in messages["founder_story"]
    assert "3 отзыва" not in messages["proof"]
    assert "3 отзыва" not in messages["integrated_system"]
    assert "клиенты и ежедневная операционка всегда срочнее" in messages["founder_story"]
    assert "не просто выдаёт список рекомендаций" not in messages["founder_story"]
    assert "с 0 до 10 клиентов в день" in messages["proof"]
    assert "больше напоминать не буду" not in messages["integrated_system"]
    assert "LocalOS помогает не только с картами" in messages["integrated_system"]
    assert all(message.count("?") == 1 for message in messages.values())
    assert all(
        phrase not in " ".join(messages.values()).lower()
        for phrase in (
            "публичный снимок карточки",
            "элемент присутствия компании",
            "проверить соответствие",
            "вы теряете клиентов",
        )
    )


def test_founder_led_beauty_extended_sequence_has_distinct_audit_and_phone_touches():
    candidate = _private_beauty_founder_candidate()
    candidate["public_audit_url"] = "https://localos.pro/example-audit"

    audit_text = _message_for_angle("audit_step", candidate, None, [])
    phone_text = _message_for_angle("phone_handoff", candidate, None, [])

    assert "автопостингом" in audit_text
    assert "ищем локальных партнёров" in audit_text
    assert "накапливает опыт" in audit_text
    assert "Это Александр Демьянов, LocalOS" in phone_text
    assert "самая болезненная?" in phone_text


def test_fgf_average_ticket_editorial_contract_preserves_owner_phrases_and_one_final_cta():
    candidate = _private_beauty_founder_candidate()
    candidate.update({
        "recipient": "FGF medical",
        "approved_copy_contract": "fgf_average_ticket_owner_v1",
        "observed_fact": "В Яндексе указаны два комплекса лазерной эпиляции с финальными ценами.",
        "evidence_kind": "map_services",
        "source_url": "https://yandex.example/fgf",
        "evidence_status": "observed",
        "next_step": "Увеличить средний чек",
    })

    message = _message_for_angle("average_ticket", candidate, None, [])
    gate = _quality_gate(
        message,
        candidate,
        None,
        channel="telegram",
        channel_status="ready",
        suppressed=False,
        angle="average_ticket",
    )

    assert "Подскажите, прорабатывали ли другие способы увеличения среднего чека?" in message
    assert message.endswith("Вам было бы интересно увеличить средний чек?")
    assert "по подтверждённому прайсу соберёт матрицу услуг и допов" in message
    assert "Медицинскую совместимость" not in message
    assert "провер" not in message.lower()
    assert message.count("?") == 2
    assert gate["checks"]["single_cta"] is True


def test_two_questions_remain_rejected_without_the_selected_editorial_contract():
    candidate = _private_beauty_founder_candidate()
    candidate.update({
        "observed_fact": "В карточке указаны услуги с ценами.",
        "evidence_kind": "map_services",
        "source_url": "https://yandex.example/services",
        "evidence_status": "observed",
        "next_step": "Короткий разбор",
    })

    gate = _quality_gate(
        "Вам знакома проблема допродаж?\n\nВам было бы интересно увеличить средний чек?",
        candidate,
        None,
        channel="telegram",
        channel_status="ready",
        suppressed=False,
        angle="average_ticket",
    )

    assert gate["checks"]["single_cta"] is False
    assert "MULTIPLE_CTA" in gate["reason_codes"]


def test_fgf_contract_rejects_altered_two_question_copy_even_when_selected():
    candidate = _private_beauty_founder_candidate()
    candidate.update({
        "approved_copy_contract": "fgf_average_ticket_owner_v1",
        "observed_fact": "В карточке указаны услуги с ценами.",
        "evidence_kind": "map_services",
        "source_url": "https://yandex.example/services",
        "evidence_status": "observed",
        "next_step": "Увеличить средний чек",
    })

    gate = _quality_gate(
        "Подскажите, прорабатывали ли другие способы роста среднего чека?\n\n"
        "Вам было бы интересно увеличить средний чек?\n\n"
        "Показать матрицу?",
        candidate,
        None,
        channel="telegram",
        channel_status="ready",
        suppressed=False,
        angle="average_ticket",
    )

    assert gate["checks"]["single_cta"] is False
    assert "MULTIPLE_CTA" in gate["reason_codes"]


def test_proof_case_follows_services_and_price_signal():
    candidate = _private_beauty_founder_candidate()
    candidate["observed_fact"] = "В карточке всего услуг - 60; с ценой - 15."

    approved_case = select_approved_localos_case(candidate)
    message = _message_for_angle("proof", candidate, None, [])

    assert approved_case["key"] == "beauty_service_catalog_orders_plus_ten"
    assert "Заказы выросли на 10%" in message
    assert message.count("?") == 1


def test_proof_case_uses_map_result_for_social_and_map_gap():
    candidate = _private_beauty_founder_candidate()
    candidate["signal_combo"] = "active_social_with_map_gap"

    approved_case = select_approved_localos_case(candidate)

    assert approved_case["key"] == "beauty_maps_zero_to_ten"


def test_quality_gate_accepts_selected_approved_case_as_specific_proof():
    candidate = _private_beauty_founder_candidate()
    candidate["signal_combo"] = "active_social_with_map_gap"
    story = {
        "story": candidate["founder_story"],
        "proof": candidate["founder_proof"],
        "forbidden_claims": [],
    }

    message = _message_for_angle("proof", candidate, story, [])
    gate = _quality_gate(
        message,
        candidate,
        story,
        channel="vk_manual",
        channel_status="manual",
        suppressed=False,
        angle="proof",
    )

    assert "с 0 до 10 клиентов в день" in message
    assert gate["criterion_scores"]["observation_accuracy"] == 2
    assert gate["criterion_scores"]["offer_bridge"] == 2
    assert gate["criterion_scores"]["recipient_specificity"] == 2
    assert gate["score"] == 18
    assert gate["passed"] is True


def test_quality_gate_rejects_generic_founder_audit_touch_without_selected_signal_or_bridge():
    candidate = _private_beauty_founder_candidate()
    candidate.update({
        "recipient": "Хочу Красиво",
        "recipient_segment": "beauty_team",
        "signal_combo": "active_social_with_unanswered_negative_review",
        "observed_fact": (
            "Официальный канал обновляется регулярно. "
            "В публичной карточке найден 1 свежий отзыв с оценкой до 3 "
            "без ответа компании."
        ),
        "bridge": (
            "Свежий отзыв без ответа можно проверить и подготовить "
            "корректный ответ"
        ),
        "evidence_kind": "composite_signal",
        "evidence_status": "observed",
        "source_url": "https://example.test/maps/hochukrasivo",
        "freshness": "fresh",
        "next_step": "Короткий разбор",
    })
    story = {"forbidden_claims": []}

    message = _message_for_angle("audit_step", candidate, story, [])
    gate = _quality_gate(
        message,
        candidate,
        story,
        channel="vk_manual",
        channel_status="manual",
        suppressed=False,
        angle="audit_step",
    )

    assert "свежий отзыв" not in message.lower()
    assert "без ответа" not in message.lower()
    assert candidate["bridge"].lower() not in message.lower()
    assert {
        "passed": gate["passed"],
        "removal": gate["checks"]["removal"],
        "bridge": gate["checks"]["bridge"],
        "specificity": gate["checks"]["specificity"],
        "observation_accuracy": gate["criterion_scores"]["observation_accuracy"],
        "offer_bridge": gate["criterion_scores"]["offer_bridge"],
        "recipient_specificity": gate["criterion_scores"]["recipient_specificity"],
        "reason_codes": set(gate["reason_codes"]),
    } == {
        "passed": False,
        "removal": False,
        "bridge": False,
        "specificity": False,
        "observation_accuracy": 0,
        "offer_bridge": 0,
        "recipient_specificity": 0,
        "reason_codes": {"DECORATIVE_PERSONALIZATION", "WEAK_OFFER_BRIDGE"},
    }


def test_multisource_composite_claim_requires_source_for_each_material_clause():
    now = datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc)
    hypotheses = derive_pain_signal_hypotheses(
        {
            "source_url": "https://yandex.ru/maps/org/clinic",
            "website": "https://clinic.test",
            "is_verified_owner": False,
            "map_posts_count": 0,
            "map_services_count": 0,
            "official_social_activity": {
                "official": True,
                "source_url": "https://t.me/clinic",
                "last_post_at": "2026-08-06T10:00:00Z",
            },
        },
        [],
        now=now,
    )
    hypothesis = next(
        item
        for item in hypotheses
        if item["signal_combo"] == "active_external_channels_with_incomplete_map_profile"
    )
    candidate = _private_beauty_founder_candidate()
    candidate.update({
        "signal_combo": hypothesis["signal_combo"],
        "observed_fact": hypothesis["observed_fact"],
        "evidence_kind": hypothesis["kind"],
        "evidence_status": hypothesis["status"],
        "evidence_ids": hypothesis["evidence_ids"],
        "source_url": hypothesis["source_url"],
        "freshness": hypothesis["freshness"],
    })

    message = _message_for_angle("signal", candidate, None, [])
    gate = _quality_gate(
        message,
        candidate,
        None,
        channel="email",
        channel_status="ready",
        suppressed=False,
        angle="signal",
    )

    assert len(hypothesis["evidence_ids"]) == 3
    assert hypothesis["source_url"] == "https://t.me/clinic"
    assert gate["passed"] is False
    assert "SOURCE_MISMATCH" in gate["reason_codes"]


def test_quality_gate_accepts_singular_unanswered_review_without_printing_number_one():
    candidate = _private_beauty_founder_candidate()
    candidate.update({
        "signal_combo": "active_social_with_unanswered_negative_review",
        "observed_fact": (
            "Официальный канал обновляется регулярно. "
            "В публичной карточке найдено 1 свежих отзывов с оценкой до 3 без ответа компании."
        ),
    })
    story = {
        "story": candidate["founder_story"],
        "proof": candidate["founder_proof"],
        "forbidden_claims": [],
    }

    message = _message_for_angle("signal", candidate, story, [])
    gate = _quality_gate(
        message,
        candidate,
        story,
        channel="email",
        channel_status="ready",
        suppressed=False,
        angle="signal",
    )

    assert "есть свежий отзыв" in message
    assert gate["score"] == 18
    assert gate["passed"] is True


def test_quality_gate_accepts_exact_new_service_and_event_timing_observations():
    story = {
        "story": "Подтверждённый опыт основателя LocalOS",
        "proof": "LocalOS применяется более чем в 240 точках малого бизнеса.",
        "forbidden_claims": [],
    }
    cases = (
        (
            "recent_new_service_announcement",
            'В Telegram опубликовано: "Новая услуга - электроэпиляция".',
        ),
        (
            "recent_event_announcement",
            'В Telegram опубликовано: "21 августа - клиентский день".',
        ),
    )
    for signal_combo, observed_fact in cases:
        candidate = _private_beauty_founder_candidate()
        candidate.update({
            "signal_combo": signal_combo,
            "observed_fact": observed_fact,
            "public_audit_url": "https://localos.pro/example-audit",
        })
        message = _message_for_angle("signal", candidate, story, [])
        gate = _quality_gate(
            message,
            candidate,
            story,
            channel="email",
            channel_status="ready",
            suppressed=False,
            angle="signal",
        )
        assert gate["score"] == 18
        assert gate["passed"] is True


def test_founder_led_beauty_segmentation_is_deterministic_and_conservative():
    assert localos_beauty_segment(
        "Косметология / услуги частных специалистов",
        "Доктор-косметолог Татьяна Прокура",
    ) == "private_beauty_specialist"
    assert localos_beauty_segment("Салон красоты", "Бьюти&Ревайвл") == "beauty_team"
    assert localos_beauty_segment("Салон красоты", "Сеть салонов Лето") == "beauty_network"
    assert localos_beauty_segment(
        "Салон красоты",
        "Beauty Today",
        'В Telegram-источнике "Beauty Today | сеть студий в СПб"',
    ) == "beauty_network"
    assert localos_beauty_segment(
        "Косметология",
        "Студия Дарьи Кушнир",
        (
            'В Telegram-источнике "Дарья Кушнир" опубликовано: '
            '"для всей сети задача важна"'
        ),
    ) == "beauty_team"
    assert localos_beauty_segment("Стоматология", "Клиника") is None


def test_telegram_observation_does_not_turn_promotion_into_procedure_explanation():
    candidate = _private_beauty_founder_candidate()
    candidate.update({
        "recipient": "The Garden",
        "recipient_category": "Салон красоты",
        "recipient_segment": "beauty_team",
        "evidence_kind": "telegram_post",
        "observed_fact": (
            'В публичном Telegram-источнике "The Garden" '
            'опубликовано: "До конца лотереи осталось пару дней"'
        ),
    })
    message = _message_for_angle("signal", candidate, None, [])

    assert "напоминаете клиентам о лотерее" in message
    assert "объясняете клиентам процедуры" not in message


def test_telegram_signal_uses_conditional_autopublish_without_unsupported_maps():
    candidate = _private_beauty_founder_candidate()
    candidate.update({
        "evidence_kind": "telegram_post",
        "observed_fact": (
            'В публичном Telegram-источнике "Салон" '
            'опубликовано: "Свободные окна на завтра".'
        ),
        "map_observation": "",
        "public_audit_url": "https://localos.pro/example-audit",
        "next_step": "Работа LocalOS от 1200 рублей в месяц",
    })

    message = _message_for_angle("signal", candidate, None, [])

    assert "карт" not in message.lower()
    assert "Яндекс" not in message
    assert "После подключения каналов и вашего подтверждения" in message
    assert "автоматически публикует материалы" in message
    assert "\n\n\n\n" not in message


def test_zero_map_rating_is_described_as_missing_not_numeric_zero():
    candidate = _private_beauty_founder_candidate()
    candidate.update({
        "evidence_kind": "telegram_post",
        "observed_fact": (
            'В публичном Telegram-источнике "Салон" '
            'опубликовано: "Свободные окна на завтра".'
        ),
        "map_observation": "Рейтинг - 0,0; публичных отзывов - 0.",
        "public_audit_url": "https://localos.pro/example-audit",
        "next_step": "Работа LocalOS от 1200 рублей в месяц",
    })

    message = _message_for_angle("signal", candidate, None, [])

    assert "в карточке пока нет рейтинга и отзывов" in message.lower()
    assert "рейтинг 0,0" not in message


def test_collagen_telegram_observation_preserves_the_sourced_topic():
    source = (
        'В публичном Telegram-источнике "BeautyPLAN" опубликовано: '
        '"Зачем коже коллаген?".'
    )

    assert observation_is_grounded(
        "В Telegram вы разбираете, зачем коже коллаген.",
        source,
    )
    assert not observation_is_grounded(
        "Увидел вашу публикацию в Telegram.",
        source,
    )


def test_hot_slots_can_be_safely_normalized_as_available_slots():
    source = (
        'В публичном Telegram-источнике "Freedom" опубликовано: '
        '"Горящие окошки на завтра".'
    )

    assert observation_is_grounded(
        "В Telegram вы публикуете свободные окна для записи.",
        source,
    )


@pytest.mark.parametrize(
    ("post", "expected"),
    (
        ("СЕГОДНЯ СВОБОДНЫЕ ОКНА: 16:00, 17:00", "свободные окна для записи"),
        ("На завтра есть несколько свободных окошек", "свободные окна для записи"),
        ("ГОРЯЩИЕ ОКОШКИ - ЗАВТРА", "свободные окна для записи"),
        ("про фотостарение и хорошие солнцезащитные средства", "фотостарении и солнцезащитных"),
        ("Мама не разрешает краситься тушью, а хочется яркий взгляд", "подростку хочется яркий взгляд"),
        ("Клиентский день в салоне только 12 июля", "клиентский день в салоне"),
        ("Как прошла акция от АПЕЛЬСИН на Кушелевской дороге", "акция на Кушелевской дороге"),
    ),
)
def test_telegram_observations_keep_a_concrete_recipient_detail(post, expected):
    candidate = {
        "evidence_kind": "telegram_post",
        "observed_fact": (
            'В публичном Telegram-источнике "Салон" '
            f'опубликовано: "{post}".'
        ),
    }

    assert expected.lower() in natural_observation(candidate).lower()


def test_founder_led_beauty_quality_gate_blocks_abstract_solution_despite_sourced_observation():
    candidate = _private_beauty_founder_candidate()
    story = {
        "story": candidate["founder_story"],
        "proof": candidate["founder_proof"],
        "forbidden_claims": [],
    }
    message = _message_for_angle("signal", candidate, story, [])
    gate = _quality_gate(
        message,
        candidate,
        story,
        channel="email",
        channel_status="ready",
        suppressed=False,
        angle="signal",
    )

    assert gate["checks"]["removal"] is True
    assert gate["checks"]["bridge"] is True
    assert gate["checks"]["specificity"] is True
    assert gate["passed"] is False
    assert "ABSTRACT_SOLUTION" in gate["reason_codes"]


def test_composite_social_map_signal_still_requires_a_concrete_localos_action():
    candidate = _private_beauty_founder_candidate()
    candidate.update({
        "signal_combo": "active_social_with_map_gap",
        "observed_fact": (
            "В карточке на картах рейтинг 4.2 и 3 отзывов. "
            "Официальная соцсеть обновлялась 2 дней назад; "
            "опубликовано 8 сообщений за 30 дней."
        ),
        "public_audit_url": "https://localos.pro/example-audit",
        "next_step": "Работа LocalOS от 1200 рублей в месяц",
    })
    story = {
        "story": candidate["founder_story"],
        "proof": candidate["founder_proof"],
        "forbidden_claims": [],
    }
    message = _message_for_angle("signal", candidate, story, [])
    gate = _quality_gate(
        message,
        candidate,
        story,
        channel="email",
        channel_status="ready",
        suppressed=False,
        angle="signal",
    )

    assert "рейтинг 4.2 и только 3 отзыва" in message
    assert "активно ведёте соцсети" in message
    assert "8 сообщений за 30 дней" not in message
    assert gate["checks"]["removal"] is True
    assert gate["total_score"] == 16
    assert "ABSTRACT_SOLUTION" in gate["reason_codes"]
    assert gate["passed"] is False


@pytest.mark.parametrize(
    ("segment", "recipient", "category"),
    (
        ("beauty_team", "The Garden", "Салон красоты"),
        ("beauty_network", "Beauty Today", "Салон красоты"),
    ),
)
def test_founder_led_signal_bridge_alone_does_not_replace_a_concrete_localos_action(
    segment,
    recipient,
    category,
):
    candidate = _private_beauty_founder_candidate()
    candidate.update({
        "recipient": recipient,
        "recipient_category": category,
        "recipient_segment": segment,
    })
    message = _message_for_angle("signal", candidate, None, [])
    gate = _quality_gate(
        message,
        candidate,
        None,
        channel="email",
        channel_status="ready",
        suppressed=False,
        angle="signal",
    )

    assert gate["checks"]["bridge"] is True
    assert gate["passed"] is False
    assert "ABSTRACT_SOLUTION" in gate["reason_codes"]


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


def test_changed_research_fact_fingerprint_invalidates_saved_campaign():
    from api.outreach_campaign_api import _campaign_payload

    class Cursor:
        def __init__(self):
            self.query = ""
            self.queries = []

        def execute(self, query, _params=None):
            self.query = query
            self.queries.append(query)

        def fetchone(self):
            if "FROM outreach_campaigns WHERE id" in self.query:
                return {
                    "id": "campaign-1",
                    "workstream_id": "workstream-1",
                    "room_id": None,
                    "status": "draft",
                }
            if "FROM lead_workstream_research" in self.query:
                return {"report_hash": "fresh-facts-3-of-3"}
            return None

        def fetchall(self):
            if "FROM outreach_campaign_touches touch" in self.query:
                return [{
                    "id": "touch-1",
                    "campaign_id": "campaign-1",
                    "channel": "whatsapp",
                    "status": "draft",
                    "message_brief_json": {"source_fact_fingerprint": "stale-facts-27-of-3"},
                    "quality_gate_json": {"passed": True},
                }]
            return []

    cursor = Cursor()
    payload = _campaign_payload(cursor, "campaign-1")

    assert any("FROM lead_workstream_research" in query for query in cursor.queries)
    assert payload["requires_regeneration"] is True


def test_channel_setup_gap_can_be_saved_as_draft_but_not_approved():
    api_source = (ROOT / "src/api/outreach_campaign_api.py").read_text()
    frontend_source = (ROOT / "frontend/src/components/prospecting/AdminLeadRegistry.tsx").read_text()
    campaign_source = (ROOT / "src/services/outreach_campaign_service.py").read_text()
    approve_start = campaign_source.index("def approve_campaign")
    approve_end = campaign_source.index("\n\ndef change_campaign_status", approve_start)
    approve_block = campaign_source[approve_start:approve_end]

    assert 'preview.get("status") in {"ready", "needs_channel_setup", "needs_evidence", "needs_revision"}' in api_source
    assert "['ready', 'needs_channel_setup', 'needs_evidence', 'needs_revision'].includes" in frontend_source
    assert "Сохранить цепочку" in frontend_source
    assert "Ничего не будет отправлено" in frontend_source
    assert "savedCampaignNeedsChannelSetup" in frontend_source
    assert "Сначала настройте каналы и отправителя" in frontend_source
    assert "senders_ready" in approve_block
    assert "channels_ready" in approve_block


def test_vk_permission_change_refreshes_saved_campaign_channel_status():
    from services import outreach_campaign_service as campaign_service

    touch = {
        "channel": "vk",
        "contact_point_id": "contact-1",
        "sender_account_id": "sender-1",
        "message_brief_json": {"channel_status": "permission_required"},
        "sender_status": "connected",
        "sender_outreach_enabled": True,
        "sender_health_status": "healthy",
        "sender_capabilities_json": {"direct_send": True, "reply_sync": True},
    }

    assert campaign_service.runtime_touch_channel_status(touch) == "ready"

    touch["sender_outreach_enabled"] = False
    assert campaign_service.runtime_touch_channel_status(touch) == "permission_required"


def test_saved_campaign_and_approval_use_live_channel_readiness():
    api_source = (ROOT / "src/api/outreach_campaign_api.py").read_text()
    payload_start = api_source.index("def _campaign_payload")
    payload_end = api_source.index("\n\n@outreach_campaign_bp.get", payload_start)
    payload_block = api_source[payload_start:payload_end]
    campaign_source = (ROOT / "src/services/outreach_campaign_service.py").read_text()
    approve_start = campaign_source.index("def approve_campaign")
    approve_end = campaign_source.index("\n\ndef change_campaign_status", approve_start)
    approve_block = campaign_source[approve_start:approve_end]
    frontend_source = (ROOT / "frontend/src/components/prospecting/AdminLeadRegistry.tsx").read_text()

    assert "runtime_touch_channel_status" in payload_block
    assert 'touch["channel_status"]' in payload_block
    assert "touch.channel_status || touch.message_brief_json?.channel_status" in frontend_source
    assert "runtime_touch_channel_status" in approve_block
    assert "t.message_brief_json->>'channel_status' = 'ready'" not in approve_block


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


def test_personalization_uses_operator_confirmed_recipient_identity_without_claiming_personal_email():
    context = {
        "lead_name": "Клиника скульптуры лица",
        "rating": 4.2,
        "reviews_count": 12,
        "source_url": "https://example.test/maps/card",
        "updated_at": "2026-08-07T10:00:00Z",
        "research": {},
        "contacts": [{
            "contact_type": "email",
            "value": "hello@example.test",
            "owner_type": "company",
            "person_name": "Сусанна",
            "role_title": "Основатель",
            "verification_status": "confirmed_source",
            "metadata_json": {
                "recipient_identity_status": "operator_confirmed",
            },
        }],
        "sender_profile": {
            "display_name": "Александр",
            "role_title": "Основатель",
            "company_name": "LocalOS",
            "competence_story": "Мы сами управляли локальным бизнесом и знаем работу с картами изнутри.",
            "confirmed_at": "2026-08-07T10:00:00Z",
            "proof_points_json": [{"fact": "Проводили публичные аудиты карточек", "status": "approved"}],
            "allowed_offers_json": [{"fact": "Могу прислать короткий аудит карточки.", "status": "approved"}],
            "forbidden_claims_json": ["Не обещать рост обращений"],
            "voice_examples_json": ["Здравствуйте! Могу прислать короткий разбор?"],
            "outreach_context_json": {
                "competence_story_status": "approved",
                "audience": "Владельцы локального бизнеса",
            },
        },
    }

    evidence = build_evidence_ledger(context)
    candidate = build_personalization_candidates(context, evidence)[0]

    assert candidate["contact_name"] == "Сусанна"
    assert candidate["contact_role"] == "Основатель"
    assert context["contacts"][0]["owner_type"] == "company"


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


def test_localos_representative_uses_business_identity_and_partner_offer():
    combined = _localos_representative_profile({
        "business_service_count": 4,
        "represented_business_name": "Весёлая расчёска",
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
    assert combined["company_name"] == "Весёлая расчёска"
    assert combined["display_name"] == ""
    assert combined["allowed_offers_json"] == ["Совместный день открытых дверей"]
    assert combined["outreach_context_json"]["audience"] == "Семьи с детьми"
    assert combined["_represented_profile_id"] == "partner-profile"


def test_represented_business_opening_describes_the_neighbour_company():
    opening = _represented_business_opening({
        "represented_business_name": "Весёлая расчёска",
        "client_business_categories": ["Детский салон-парикмахерская"],
        "client_business_network_id": "network-1",
        "business_sender_profile": {},
    })

    assert opening == "Мы ваши соседи - сеть детских парикмахерских Весёлая расчёска."


def test_localos_representative_does_not_require_a_partner_founder_profile():
    combined = _localos_representative_profile({
        "business_service_count": 6,
        "category": "Спортивный клуб, секция / школа танцев",
        "platform_sender_profile": {
            "id": "localos-profile",
            "display_name": "Алексей",
            "role_title": "основатель",
            "company_name": "LocalOS",
            "competence_story": "Создаю LocalOS на основе практики локального маркетинга.",
            "proof_points_json": [{"fact": "Проверили 100 карточек", "status": "approved"}],
            "allowed_offers_json": ["Короткий безопасный тест"],
            "forbidden_claims_json": ["Не обещать рост"],
            "voice_examples_json": ["Здравствуйте! Есть короткая идея."],
            "outreach_context_json": {
                "competence_story_status": "approved",
                "audience": "Владельцы локального бизнеса",
            },
            "confirmed_at": "2026-07-20T12:00:00Z",
        },
        "business_sender_profile": {},
    })

    assert combined["confirmed_at"] == "2026-07-20T12:00:00Z"
    assert combined["allowed_offers_json"] == []
    assert "audience" not in combined["outreach_context_json"]
    assert combined["outreach_context_json"]["desired_partner_types"] == [
        "Спортивный клуб, секция",
        "школа танцев",
    ]
    assert combined["_represented_profile_id"] is None


def test_localos_representative_never_uses_unconfirmed_partner_claims():
    combined = _localos_representative_profile({
        "business_service_count": 3,
        "category": "Кафе",
        "platform_sender_profile": {
            "allowed_offers_json": ["Безопасный тест LocalOS"],
            "forbidden_claims_json": ["Не обещать рост"],
            "outreach_context_json": {"audience": "Локальный бизнес"},
            "confirmed_at": "2026-07-20T12:00:00Z",
        },
        "business_sender_profile": {
            "id": "draft-partner-profile",
            "allowed_offers_json": ["Неподтверждённая скидка"],
            "forbidden_claims_json": ["Черновой запрет"],
            "outreach_context_json": {
                "audience": "Неподтверждённая аудитория",
                "desired_partner_types": ["Любые"],
            },
            "confirmed_at": None,
        },
    })

    assert combined["allowed_offers_json"] == []
    assert combined["forbidden_claims_json"] == ["Не обещать рост"]
    assert "audience" not in combined["outreach_context_json"]
    assert combined["outreach_context_json"]["desired_partner_types"] == ["Кафе"]


def test_localos_for_partner_message_uses_represented_business_voice():
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
            "sender_mode": "localos_for_partner",
            "represented_business": "Шансик",
            "represented_business_opening": "Мы ваши соседи - Шансик.",
            "representation_disclosure": "",
        },
        {"story": "Мы проверяем совместимость локальных услуг"},
        [],
    )

    assert message.startswith("Здравствуйте!\n\nМы ваши соседи - Шансик.")
    assert "LocalOS" not in message
    assert "Алексей" not in message
    assert message.endswith("Мы собрали несколько простых идей для небольшого совместного пилота. Прислать?")


def test_residential_message_invites_residents_instead_of_selling_generic_pilot():
    message = _message_for_angle(
        "signal",
        {
            "recipient": "ЖК Новые кварталы",
            "recipient_type": "residential_complex",
            "sender": "",
            "sender_role": "",
            "sender_company": "",
            "observed_fact": "ЖК находится в том же районе, что и Новамед",
            "bridge": "Жителям может быть полезна медицинская клиника рядом с домом",
            "founder_story": "",
            "next_step": "Пригласить жителей ЖК Новые кварталы в Новамед",
            "sender_mode": "localos_for_partner",
            "represented_business": "Новамед",
            "represented_business_opening": "Мы ваши соседи - Новамед.",
            "representation_disclosure": "",
        },
        None,
        [],
    )

    assert message.startswith("Здравствуйте!\n\nМы ваши соседи - Новамед.")
    assert "Хотели бы пригласить ваших жителей к нам." in message
    assert "Конкретный формат и условия предложим отдельно" in message
    assert "скид" not in message.lower()
    assert "мастер-класс" not in message.lower()
    assert message.count("?") == 1


def test_sequence_quality_rejects_closing_language():
    candidate = {
        "recipient": "ЖК Новые кварталы",
        "observed_fact": 'В публичной карточке указана категория "Жилой комплекс".',
        "bridge": "Можно обсудить предложение непосредственно для жителей комплекса",
        "founder_story": "",
        "founder_proof": "",
        "trust_statement": "Совпадает локальная география",
        "source_url": "https://example.test/maps/residential",
        "evidence_status": "observed",
        "freshness": "current_snapshot",
        "next_step": "Вернуться к предложению позже",
        "evidence_kind": "residential_context",
    }
    text = (
        "Здравствуйте! Коротко закроем тему по ЖК Новые кварталы. "
        "Можно обсудить предложение непосредственно для жителей комплекса. "
        "Если сейчас неактуально, больше писать не будем. Вернуться к этому позже?"
    )

    gate = _quality_gate(
        text,
        candidate,
        None,
        channel="vk",
        channel_status="manual",
        suppressed=False,
        angle="respectful_close",
    )

    assert gate["passed"] is False
    assert "sequence_closing_language" in gate["blocking_reasons"]
    assert "STYLE_VIOLATION" in gate["reason_codes"]


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


def test_operator_approved_partnership_reason_can_prepare_personalized_chain_without_fake_matching():
    manual_reason = (
        "Предложить родителям после детского центра удобную детскую стрижку "
        "в соседней Весёлой расчёске."
    )
    context = {
        "workstream_type": "client_partnership",
        "lifecycle_status": "active",
        "lead_name": "Бэби-клуб на Комендантском",
        "category": "Детский развивающий центр",
        "city": "Санкт-Петербург",
        "source_url": "https://example.test/maps/baby-club",
        "updated_at": "2026-07-30T10:00:00Z",
        "contacts": [{"verification_status": "verified"}],
        "represented_business_name": "Весёлая расчёска",
        "client_business_name": "Весёлая расчёска",
        "sender_mode": "localos_for_partner",
        "sender_profile": {},
        "business_sender_profile": {},
        "partnership_match": {},
        "research": {
            "message_brief_json": {
                "operator_approved_reason": manual_reason,
                "operator_approved_at": "2026-07-30T10:00:00Z",
                "operator_approved_by": "superadmin-1",
            },
        },
    }

    evidence = build_evidence_ledger(context)

    assert evidence == [{
        "id": "operator-approved-partnership-reason",
        "kind": "operator_approved_partnership_reason",
        "fact": manual_reason,
        "status": "approved",
        "source_url": "https://example.test/maps/baby-club",
        "observed_at": "2026-07-30T10:00:00Z",
        "freshness": "current_snapshot",
        "confidence": 1.0,
        "hypothesis": None,
        "relevance": "У каждого участника есть понятная роль в одном совместном формате.",
        "source_type": "operator_input",
    }]
    assert context["partnership_match"] == {}

    decision = build_outreach_decision(
        context,
        evidence,
        {"vk": {"status": "ready"}},
        {"suppressed": False},
        sender_mode="localos_for_partner",
        profile_ready=True,
    )
    assert decision["action"] == "write_now"
    assert "operator_approved_partnership_reason" in decision["reason_codes"]

    offers = offer_candidates(context, "localos_for_partner")
    trusts = trust_candidates(context, "localos_for_partner")
    assert offers[0]["text"] == manual_reason
    assert offers[0]["source"] == "operator_input"
    assert trusts[0]["source"] == "operator_input"

    candidates = build_personalization_candidates(
        context,
        evidence,
        selected_offer=offers[0],
        selected_trust=trusts[0],
    )
    assert candidates
    assert candidates[0]["observed_fact"] == manual_reason
    assert candidates[0]["next_step"] != manual_reason

    first_touch = _message_for_angle(
        "signal",
        candidates[0],
        None,
        [],
    )
    assert first_touch.startswith("Здравствуйте!\n\nМы ваши соседи - Весёлая расчёска.")
    assert "Предлагаем команде Бэби-клуб на Комендантском такой формат" in first_touch
    assert "LocalOS" not in first_touch
    assert first_touch.count("?") == 1
    gate = _quality_gate(
        first_touch,
        candidates[0],
        None,
        channel="vk",
        channel_status="ready",
        suppressed=False,
        angle="signal",
    )
    assert gate["passed"] is True
    assert gate["total_score"] == 18


def test_operator_approved_partnership_reason_creates_distinct_human_sequence():
    manual_reason = (
        "Предложить совместный показ в ТРК Гранд Каньон: мы сделаем причёски, "
        "они предоставят одежду, а наш третий партнёр организует участие детей."
    )
    context = {
        "workstream_type": "client_partnership",
        "lead_name": "B&C for baby",
        "category": "Детские товары / одежда",
        "city": "Санкт-Петербург",
        "source_url": "https://vk.ru/bnckidsru",
        "updated_at": "2026-07-30T10:00:00Z",
        "represented_business_name": "Весёлая расчёска",
        "client_business_name": "Весёлая расчёска",
        "client_business_categories": ["детская парикмахерская"],
        "client_business_network_id": "network-1",
        "sender_mode": "localos_for_partner",
        "sender_profile": {},
        "business_sender_profile": {},
        "partnership_match": {},
        "research": {
            "message_brief_json": {
                "operator_approved_reason": manual_reason,
                "operator_approved_at": "2026-07-30T10:00:00Z",
                "operator_approved_by": "superadmin-1",
            },
        },
    }

    evidence = build_evidence_ledger(context)
    offers = offer_candidates(context, "localos_for_partner")
    trusts = trust_candidates(context, "localos_for_partner")
    candidates = build_personalization_candidates(
        context,
        evidence,
        selected_offer=offers[0],
        selected_trust=trusts[0],
    )
    candidate = candidates[0]
    angles = ["signal", "matching_authority", "proof", "respectful_close"]
    messages = [
        _message_for_angle(angle, candidate, None, angles[:index])
        for index, angle in enumerate(angles)
    ]
    combined = "\n".join(messages).lower()

    assert combined.count(manual_reason.lower()) <= 1
    assert "у нас есть конкретная идея сотрудничества" not in combined
    assert len(set(messages)) == 4
    assert all(message.count("?") == 1 for message in messages)
    assert all("LocalOS" not in message for message in messages)
    assert messages[0].startswith(
        "Здравствуйте!\n\nМы ваши соседи - сеть детских парикмахерских Весёлая расчёска."
    )
    assert "Предлагаем команде B&C for baby такой формат: совместный показ в ТРК Гранд Каньон." in messages[0]
    assert evidence[0]["relevance"] != manual_reason
    assert offers[0]["cta"] != manual_reason
    assert candidate["bridge"] != manual_reason
    assert candidate["next_step"] != manual_reason
    assert _email_subject("matching_authority", candidate) == "B&C for baby | ЛокалОС | Сотрудничество"


def test_residential_evidence_uses_recipient_type_instead_of_placeholder_services():
    evidence = build_evidence_ledger({
        "workstream_type": "client_partnership",
        "lead_name": "ЖК Новые кварталы",
        "category": "Жилой комплекс",
        "city": "Москва",
        "source_url": "https://example.test/maps/residential",
        "updated_at": "2026-07-22T10:00:00Z",
        "research": {},
        "partnership_match": {
            "match_score": 80,
            "recipient_observation": (
                "В публичной карточке указана категория Жилой комплекс; "
                "указаны услуги: Общее описание без структуры, Нет цены или формата."
            ),
            "relevance_bridge": "Есть основание обсудить предложение для жителей.",
        },
    })

    assert evidence[0]["kind"] == "residential_context"
    assert evidence[0]["fact"] == (
        'В публичной карточке ЖК Новые кварталы указана категория "Жилой комплекс".'
    )
    assert "Общее описание без структуры" not in evidence[0]["fact"]


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

    assert "—" not in evidence[0]["fact"]
    assert evidence[0]["fact"] == (
        "По данным аудита карточки: всего услуг - 60; с ценой - 15."
    )


def test_public_category_fact_is_normalized_to_style_contract():
    context = {
        "research": {
            "evidence_json": [
                {
                    "id": "category-1",
                    "kind": "service_compatibility",
                    "fact": "В публичной карточке указана категория «Фитнес-клуб».",
                    "status": "observed",
                    "source_url": "https://example.test/maps/fitness",
                    "observed_at": "2026-07-21T10:00:00Z",
                    "freshness": "current_snapshot",
                    "confidence": 0.55,
                },
            ],
        },
    }

    evidence = build_evidence_ledger(context)

    assert evidence[0]["fact"] == 'В публичной карточке указана категория "Фитнес-клуб".'


def test_partnership_match_fact_is_normalized_to_style_contract():
    context = {
        "workstream_type": "client_partnership",
        "source_url": "https://example.test/maps/fitness",
        "partnership_match": {
            "match_score": 65,
            "recipient_observation": (
                "В публичной карточке указана категория «Фитнес-клуб»."
            ),
            "compatibility_hypothesis": "У компаний может пересекаться аудитория.",
            "relevance_bridge": "Основание для безопасного теста.",
        },
        "research": {},
    }

    evidence = build_evidence_ledger(context)

    assert evidence[0]["fact"] == 'В публичной карточке указана категория "Фитнес-клуб".'


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


def test_estem_generic_email_with_no_localos_action_cannot_approve_raw_abstract_solution():
    candidate = {
        "recipient": "Эстем",
        "recipient_segment": "beauty_team",
        "sender_mode": "localos",
        "signal_combo": "active_social_content",
        "observed_fact": (
            "2 августа в канале Эстем вышел разбор ботулинотерапии "
            "с тремя преимуществами и указанием врача Дарьи Резник."
        ),
        "bridge": "Эту тему можно использовать для работы с контентом.",
        "localos_action": None,
        "evidence_kind": "telegram_post",
        "evidence_status": "observed",
        "source_url": "https://t.me/estemclinic/2084",
        "freshness": "fresh",
        "confidence": 0.95,
        "next_step": "Показать пример",
    }
    text = (
        "Эстем, здравствуйте!\n\n"
        "2 августа в канале Эстем вышел разбор ботулинотерапии с тремя "
        "преимуществами и указанием врача Дарьи Резник.\n\n"
        "Эту тему можно использовать для работы с контентом.\n\n"
        "LocalOS может помочь с ведением площадок.\n\n"
        "Показать пример?"
    )

    gate = _quality_gate(
        text,
        candidate,
        {"forbidden_claims": []},
        channel="email",
        channel_status="ready",
        suppressed=False,
        angle="signal",
    )

    assert "ABSTRACT_SOLUTION" in gate["human_language_review"]["reason_codes"]
    assert gate["human_language_review"]["detected_passed"] is False
    assert gate["passed"] is False
    assert gate["verdict"] != "approve"
    assert gate["total_score"] < 18


def test_public_audit_current_state_adds_distinct_description_and_news_signals():
    ledger = build_evidence_ledger(
        {
            "lead_name": "Padrina_studio",
            "source_url": "https://yandex.ru/maps/org/padrina_studio/68716502058/",
            "public_audit_updated_at": "2026-08-11T12:00:00+00:00",
            "public_audit_page_json": {
                "audit": {
                    "current_state": {
                        "description_present": False,
                        "news_count": 0,
                    }
                }
            },
            "research": {},
            "workstream_type": "localos_sales",
            "category": "Салон красоты",
        }
    )

    by_id = {item["id"]: item for item in ledger}
    assert by_id["map-description-gap"]["kind"] == "map_description_gap"
    assert by_id["map-content-gap"]["kind"] == "map_gap"
    assert by_id["map-description-gap"]["fact"] != by_id["map-content-gap"]["fact"]


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
        assert "Гипотеза боли:" in source
        assert "Почему это связано:" in source
    assert "QUALITY_CRITERION_LABELS" in ui
    assert "QUALITY_REASON_LABELS" in ui
    assert "outreachQualityCriterionLabels" in admin_ui
    assert "outreachQualityReasonLabels" in admin_ui


def test_outreach_preview_accepts_only_future_timezone_aware_start_dates():
    from api.outreach_campaign_api import _parse_campaign_start_at

    parsed = _parse_campaign_start_at("2099-07-24T10:30:00+03:00")

    assert parsed == datetime(2099, 7, 24, 7, 30, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="timezone"):
        _parse_campaign_start_at("2099-07-24T10:30:00")
    with pytest.raises(ValueError, match="past"):
        _parse_campaign_start_at("2020-01-01T10:30:00+03:00")


def test_manual_touch_overrides_preserve_original_copy_and_reject_invalid_payloads():
    normalized = _normalize_touch_overrides([
        {
            "sequence_index": 1,
            "subject": "Короткий вопрос",
            "text": "Здравствуйте! Подскажете, с кем обсудить партнёрство?",
            "original_subject": "Старое предложение",
            "original_text": "Старый текст",
            "human_edited": True,
        },
    ])

    assert normalized[1]["text"] == "Здравствуйте! Подскажете, с кем обсудить партнёрство?"
    assert normalized[1]["original_text"] == "Старый текст"
    assert normalized[1]["human_edited"] is True
    with pytest.raises(ValueError, match="required"):
        _normalize_touch_overrides([{"sequence_index": 0, "text": ""}])
    with pytest.raises(ValueError, match="duplicated"):
        _normalize_touch_overrides([
            {"sequence_index": 0, "text": "Первое"},
            {"sequence_index": 0, "text": "Второе"},
        ])


def test_manual_touch_overrides_preserve_paragraph_breaks():
    message = (
        'Здравствуйте! Мы ваши соседи - сеть детских парикмахерских "Весёлая расчёска".\n\n'
        "Хотели предложить Yes Apart небольшой проект для семей.\n\n"
        "Подскажите, пожалуйста, с кем можно обсудить такую идею?"
    )

    normalized = _normalize_touch_overrides([
        {
            "sequence_index": 0,
            "subject": "Yes Apart | Весёлая расчёска",
            "text": message,
            "original_text": message,
            "human_edited": True,
        },
    ])

    assert normalized[0]["text"] == message
    assert normalized[0]["original_text"] == message


def test_outreach_ui_shows_compact_calendar_and_edits_messages_outside_it():
    calendar_ui = (ROOT / "frontend/src/components/prospecting/OutreachScheduleCalendar.tsx").read_text()
    partner_ui = (ROOT / "frontend/src/components/prospecting/OutreachCampaignBuilder.tsx").read_text()
    admin_ui = (ROOT / "frontend/src/components/prospecting/AdminLeadRegistry.tsx").read_text()
    api_source = (ROOT / "src/api/outreach_campaign_api.py").read_text()
    editor_ui = (ROOT / "frontend/src/components/prospecting/OutreachTouchMessageEditor.tsx").read_text()

    assert "Календарь касаний" in calendar_ui
    assert "Когда и через какой канал пройдёт каждый шаг цепочки" in calendar_ui
    assert "Дата уже прошла" in calendar_ui
    assert "Шаг {Number(item.touch.sequence_index || 0) + 1}" in calendar_ui
    assert "touchText(item.touch)" not in calendar_ui
    assert "item.touch.subject" not in calendar_ui
    assert "Редактировать" in editor_ui
    assert "Принять изменения" in editor_ui
    assert "Изменения сохранены" in editor_ui
    assert "Правки не сохранены" in editor_ui
    assert "Вернуть исходный текст" in editor_ui
    assert "touch_overrides" in partner_ui
    assert "touch_overrides" in admin_ui
    history_start = admin_ui.index('История сообщений')
    history_end = admin_ui.index('Контакты и получатель', history_start)
    history_block = admin_ui[history_start:history_end]
    assert "OutreachTouchMessageEditor" in history_block
    assert "В цепочке есть несохранённые ручные правки" in history_block
    assert "Проверить сохранённые сообщения" in history_block
    assert "Результат проверки" in history_block
    assert "Сохранить новую версию" not in history_block
    campaign_source = (ROOT / "src/services/outreach_campaign_service.py").read_text()
    assert ") and not override_by_index" in campaign_source
    assert 'touch["generation_source"] = "manual_product_correction"' in campaign_source
    assert 'touch["original_generated_text"] = override["original_text"] or None' in campaign_source
    assert "Дата и время первого касания" in partner_ui
    assert "Дата и время первого касания" in admin_ui
    assert "OutreachScheduleCalendar" in partner_ui
    assert "OutreachScheduleCalendar" in admin_ui
    assert 'const scheduleStart = outreachStartIso(startAt)' in partner_ui
    assert 'const scheduleStart = outreachStartIso(sequenceStartAt)' in admin_ui
    assert 'start_at: scheduleStart' in partner_ui
    assert 'start_at: scheduleStart' in admin_ui
    assert 'start_at=_parse_campaign_start_at(payload.get("start_at"))' in api_source


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
    sync_start = worker.index("def _sync_outreach_replies_if_due()")
    function_start = worker.index("def _dispatch_outreach_queue_if_due()")
    function_end = worker.index("\ndef _run_card_automation_if_due()", function_start)
    sync_block = worker[sync_start:function_start]
    dispatch_block = worker[function_start:function_end]

    assert "_sync_telegram_app_replies" in sync_block
    assert "OUTREACH_REPLY_SYNC_FAIL_CLOSED" in sync_block
    assert dispatch_block.index("_sync_outreach_replies_if_due") < dispatch_block.index("dispatch_due_outreach_queue")
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
    assert "Проверить статус кампании" in admin_ui
    assert "dispatchPilotFirstTouch" not in admin_ui


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
    assert "Проверить перед отправкой" in ui
    assert "pilotReadiness?.can_dispatch_first_touch" in ui
    assert ui.index("Проверить перед отправкой") < ui.rindex("Отправить только первое касание")
    assert "Проверить статус кампании" in admin_ui
    assert "pilotReadiness?.can_dispatch_first_touch" not in admin_ui
    assert "/pilot-preflight" not in admin_ui


def test_draft_campaign_ui_explains_how_human_approval_changes_campaign_status():
    builder_ui = (
        ROOT / "frontend/src/components/prospecting/OutreachCampaignBuilder.tsx"
    ).read_text()
    admin_ui = (
        ROOT / "frontend/src/components/prospecting/AdminLeadRegistry.tsx"
    ).read_text()

    assert "Утвердить цепочку и перейти к отправке" in builder_ui
    assert "статус изменится с «Черновик» на «Утверждена»" in builder_ui
    assert "Сообщение ещё не отправится" in builder_ui
    assert "Утвердить цепочку и перейти к отправке" in admin_ui
    assert "статус изменится с «Черновик» на «Подтверждена»" in admin_ui
    assert "Автоматические касания будут поставлены в очередь" in admin_ui


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


def test_recipient_selection_updates_drawer_without_grey_stale_state():
    source = (ROOT / "frontend/src/components/prospecting/AdminLeadRegistry.tsx").read_text()

    select_start = source.index("const selectRecipient")
    select_end = source.index("\n\n  const saveSenderProfile", select_start)
    select_block = source[select_start:select_end]
    contacts_start = source.index("{drawerContacts.map")
    contacts_end = source.index("{!contactIntelligenceLoading", contacts_start)
    contacts_block = source[contacts_start:contacts_end]

    assert "if (drawerRecipient?.id === contact.id)" in select_block
    assert "selected_recipient: contact" in select_block
    assert "aria-pressed={selected}" in contacts_block
    assert "disabled:opacity-50" not in contacts_block


def test_contacts_used_by_campaign_touches_are_visually_distinct_from_the_current_recipient():
    source = (ROOT / "frontend/src/components/prospecting/AdminLeadRegistry.tsx").read_text()

    contacts_start = source.index("{drawerContacts.map")
    contacts_end = source.index("{!contactIntelligenceLoading", contacts_start)
    contacts_block = source[contacts_start:contacts_end]

    assert "chainTouchesByContactId" in source
    assert "touch.contact_point_id" in source
    assert "selectedForSending" in contacts_block
    assert "Выбран для отправки" in contacts_block
    assert "Выбран как получатель" in contacts_block
    assert "Шаг ${Number(touch.sequence_index || 0) + 1}" in contacts_block


def test_saved_campaign_remains_visible_while_editing_new_version():
    source = (ROOT / "frontend/src/components/prospecting/AdminLeadRegistry.tsx").read_text()

    channel_start = source.index("const updateSequenceChannel")
    channel_end = source.index("\n\n  const updateSequenceDay", channel_start)
    channel_block = source[channel_start:channel_end]

    day_start = channel_end
    day_end = source.index("\n\n  const updateSenderMode", day_start)
    day_block = source[day_start:day_end]

    mode_start = day_end
    mode_end = source.index("\n\n  const campaignSequence", mode_start)
    mode_block = source[mode_start:mode_end]

    schedule_start = source.index('ariaLabel="Дата и время первого касания"')
    schedule_end = source.index("/>\n", schedule_start)
    schedule_block = source[schedule_start:schedule_end]

    assert "setSavedOutreachCampaign(null)" not in channel_block
    assert "setSavedOutreachCampaign(null)" not in day_block
    assert "setSavedOutreachCampaign(null)" not in mode_block
    assert "setSavedOutreachCampaign(null)" not in schedule_block
    assert "setCampaignSetupDirty(true)" in channel_block
    assert "setCampaignSetupDirty(true)" in day_block
    assert "setCampaignSetupDirty(true)" in mode_block
    assert "setCampaignSetupDirty(true)" in schedule_block
    assert "campaignSetupDirty" in source[source.index("const outreachCalendarTouches"):source.index("const savedConversationTouches")]
    assert "busyAction === 'approve-campaign' || campaignSetupDirty" in source
    assert "Настройки новой версии ещё не сохранены" in source


def test_outreach_uses_the_product_date_time_picker_in_both_campaign_surfaces():
    admin_source = (ROOT / "frontend/src/components/prospecting/AdminLeadRegistry.tsx").read_text()
    builder_source = (ROOT / "frontend/src/components/prospecting/OutreachCampaignBuilder.tsx").read_text()
    picker_source = (ROOT / "frontend/src/components/prospecting/OutreachDateTimePicker.tsx").read_text()

    assert "<OutreachDateTimePicker" in admin_source
    assert "<OutreachDateTimePicker" in builder_source
    assert 'type="datetime-local"' not in admin_source
    assert 'type="datetime-local"' not in builder_source
    assert "Когда отправить первый шаг" in picker_source
    assert "Сегодня" in picker_source
    assert "Завтра" in picker_source
    assert 'type="time"' in picker_source


def test_manual_touch_edits_survive_reload_until_new_campaign_version_is_saved():
    source = (ROOT / "frontend/src/components/prospecting/AdminLeadRegistry.tsx").read_text()

    assert "outreachTouchEditsStorageKey" in source
    assert "localStorage.getItem(outreachTouchEditsStorageKey" in source
    assert "localStorage.setItem(outreachTouchEditsStorageKey" in source
    assert "beforeunload" in source

    prepare_campaign_start = source.index("const prepareOutreachCampaign")
    saved_campaign_start = source.index("if (payload?.campaign)", prepare_campaign_start)
    saved_campaign_end = source.index("\n      }", saved_campaign_start)
    saved_campaign_block = source[saved_campaign_start:saved_campaign_end]
    assert "localStorage.removeItem(outreachTouchEditsStorageKey" in saved_campaign_block


def test_accept_touch_edits_persists_current_draft_without_campaign_version():
    admin_source = (ROOT / "frontend/src/components/prospecting/AdminLeadRegistry.tsx").read_text()
    editor_source = (ROOT / "frontend/src/components/prospecting/OutreachTouchMessageEditor.tsx").read_text()
    api_source = (ROOT / "src/api/outreach_campaign_api.py").read_text()

    assert "Принять изменения" in editor_source
    assert "onAccept" in editor_source
    assert "const acceptTouchEdit" in admin_source
    accept_start = admin_source.index("const acceptTouchEdit")
    accept_end = admin_source.index("\n\n  const", accept_start)
    accept_block = admin_source[accept_start:accept_end]
    assert "method: 'PATCH'" in accept_block
    assert "/outreach/campaigns/" in accept_block
    assert "/touches/" in accept_block
    assert "prepareOutreachCampaign(true)" not in accept_block
    assert "Изменения сохранены" in accept_block
    assert '@outreach_campaign_bp.patch("/api/outreach/campaigns/<campaign_id>/touches/<touch_id>")' in api_source


def test_queued_touch_edit_respects_paused_queue_contract():
    admin_source = (ROOT / "frontend/src/components/prospecting/AdminLeadRegistry.tsx").read_text()
    service_source = (ROOT / "src/services/outreach_campaign_service.py").read_text()

    edit_guard_start = admin_source.index("const canEditSavedTouch")
    edit_guard_end = admin_source.index(";", edit_guard_start)
    edit_guard = admin_source[edit_guard_start:edit_guard_end]
    assert "campaignStatus === 'draft' && touchStatus === 'draft'" in edit_guard
    assert "campaignStatus === 'paused' && touchStatus === 'paused'" in edit_guard

    editor_start = admin_source.index("<OutreachTouchMessageEditor", admin_source.index("savedConversationTouches.map"))
    editor_end = admin_source.index("/>", editor_start)
    editor_block = admin_source[editor_start:editor_end]

    assert "touchCanBeEdited" in admin_source[admin_source.index("savedConversationTouches.map"):editor_start]
    assert "editableTouch && touchCanBeEdited" in admin_source[admin_source.index("savedConversationTouches.map"):editor_start]
    assert 'paused_edit = existing.get("campaign_status") == "paused"' in service_source
    assert 'paused_queue.get("delivery_status") != "paused"' in service_source
    assert 'approved_snapshot_hash = NULL' in service_source
    assert 'Review edited campaign messages before resuming' in service_source


def test_review_saved_touch_edits_does_not_require_a_new_campaign_version():
    admin_source = (ROOT / "frontend/src/components/prospecting/AdminLeadRegistry.tsx").read_text()
    api_source = (ROOT / "src/api/outreach_campaign_api.py").read_text()

    assert "Проверить сохранённые сообщения" in admin_source
    assert "/review-edits" in admin_source
    assert '@outreach_campaign_bp.post("/api/outreach/campaigns/<campaign_id>/review-edits")' in api_source

    history_start = admin_source.index("История сообщений")
    history_end = admin_source.index("Контакты и получатель", history_start)
    history_block = admin_source[history_start:history_end]
    assert "Проверить сохранённые сообщения" in history_block
    assert "Результат проверки" in history_block

    save_version_index = admin_source.index("Проверить и сохранить изменения", history_end)
    setup_dirty_block = admin_source[save_version_index - 1_200:save_version_index + 100]
    assert "campaignSetupDirty ?" in setup_dirty_block


def test_persisted_server_touch_is_not_restored_as_an_unsaved_device_edit():
    admin_source = (ROOT / "frontend/src/components/prospecting/AdminLeadRegistry.tsx").read_text()

    restore_start = admin_source.index("const storedValue = localStorage.getItem(outreachTouchEditsStorageKey)")
    restore_end = admin_source.index("\n  }, [outreachTouchEditsStorageKey", restore_start)
    restore_block = admin_source[restore_start:restore_end]

    assert "savedOutreachCampaign?.touches" in restore_block
    assert "persistedTouch?.approved_text || persistedTouch?.generated_text" in restore_block
    assert "localStorage.removeItem(outreachTouchEditsStorageKey)" in restore_block
    assert "Восстановили несохранённые ручные правки" in restore_block


def test_accepting_touch_while_schedule_is_dirty_still_persists_exact_text():
    admin_source = (ROOT / "frontend/src/components/prospecting/AdminLeadRegistry.tsx").read_text()

    accept_start = admin_source.index("const acceptTouchEdit")
    accept_end = admin_source.index("\n\n  const reloadLatestOutreachCampaign", accept_start)
    accept_block = admin_source[accept_start:accept_end]
    patch_index = accept_block.index("method: 'PATCH'")
    setup_guard_index = accept_block.find("if (campaignSetupDirty)")

    assert setup_guard_index == -1 or patch_index < setup_guard_index
    assert "subject: draft.subject.trim()" in accept_block
    assert "text: draft.text.trim()" in accept_block
    assert "setOutreachPreview(null)" in accept_block


def test_low_quality_schedule_change_can_be_saved_as_draft_but_not_approved():
    admin_source = (ROOT / "frontend/src/components/prospecting/AdminLeadRegistry.tsx").read_text()
    api_source = (ROOT / "src/api/outreach_campaign_api.py").read_text()
    campaign_source = (ROOT / "src/services/outreach_campaign_service.py").read_text()

    preview_route_start = api_source.index("def preview_campaign")
    preview_route_end = api_source.index("\n\n@outreach_campaign_bp", preview_route_start)
    preview_route = api_source[preview_route_start:preview_route_end]
    persist_start = campaign_source.index("def persist_preview")
    persist_end = campaign_source.index("\n\ndef ", persist_start)
    persist_block = campaign_source[persist_start:persist_end]

    assert 'preview.get("status") in {"ready", "needs_channel_setup", "needs_evidence", "needs_revision"}' in preview_route
    assert 'preview.get("status") not in {"ready", "needs_channel_setup", "needs_evidence", "needs_revision"}' in persist_block
    assert "'ready', 'needs_channel_setup', 'needs_evidence', 'needs_revision'" in admin_source
    assert "!savedCampaignQualityPassed" in admin_source


def test_residential_partnership_copy_passes_without_copying_internal_evidence_phrases():
    candidate = {
        "observed_fact": 'В публичной карточке Yes Apart указана категория "Жилой комплекс".',
        "recipient": "Yes Apart",
        "recipient_type": "residential_complex",
        "sender_mode": "localos_for_partner",
        "represented_business": "Весёлая расчёска",
        "bridge": "Это позволяет обсудить предложение непосредственно для жителей комплекса",
        "trust_statement": "Весёлая расчёска предлагает услуги семьям с детьми рядом с комплексом",
        "evidence_kind": "residential_context",
        "source_url": "https://example.test/maps/yes-apart",
        "evidence_status": "observed",
        "freshness": "current_snapshot",
        "confidence": 0.95,
        "next_step": "Обсудить специальные условия для семей жителей и гостей",
    }
    message = (
        'Здравствуйте! Мы ваши соседи - сеть детских парикмахерских "Весёлая расчёска". '
        "Хотим предложить особые условия на детские стрижки для семей гостей и жителей Yes Apart. "
        "Подскажите, с кем можно обсудить детали?"
    )

    gate = _quality_gate(
        message,
        candidate,
        None,
        channel="email",
        channel_status="ready",
        suppressed=False,
    )
    suppressed_gate = _quality_gate(
        message,
        candidate,
        None,
        channel="email",
        channel_status="ready",
        suppressed=True,
    )

    assert gate["passed"] is True
    assert gate["total_score"] == 18
    assert gate["reason_codes"] == []
    assert suppressed_gate["passed"] is False
    assert "SUPPRESSED_CONTACT" in suppressed_gate["reason_codes"]


def test_residential_map_category_evidence_does_not_force_internal_phrases_into_human_copy():
    candidate = {
        "observed_fact": 'В публичной карточке Yes Apart указана категория "Апарт-отель / жилой комплекс".',
        "recipient": "Yes Apart",
        "recipient_type": "residential_complex",
        "sender_mode": "localos_for_partner",
        "represented_business": "Весёлая расчёска",
        "bridge": "Это позволяет обсудить предложение непосредственно для жителей комплекса",
        "trust_statement": "Весёлая расчёска предлагает услуги семьям с детьми рядом с комплексом",
        "evidence_kind": "map_card_category",
        "source_url": "https://example.test/maps/yes-apart",
        "evidence_status": "observed",
        "freshness": "current_snapshot",
        "confidence": 0.95,
        "next_step": "Обсудить небольшой локальный проект для семей",
    }
    message = (
        'Здравствуйте! Мы ваши соседи - сеть детских парикмахерских "Весёлая расчёска". '
        "Замечаем, что люди всё больше собираются в небольшие сообщества вокруг дома. "
        "Хотели предложить Yes Apart небольшой проект для семей, который поможет познакомить "
        "жителей с полезными местами рядом. Подскажите, с кем можно обсудить такую идею?"
    )

    gate = _quality_gate(
        message,
        candidate,
        None,
        channel="email",
        channel_status="ready",
        suppressed=False,
    )

    assert gate["checks"]["human_tone"] is True
    assert gate["checks"]["style_contract"] is True
    assert gate["checks"]["removal"] is True
    assert gate["checks"]["bridge"] is True
    assert gate["criterion_scores"]["observation_accuracy"] == 2
    assert gate["criterion_scores"]["recipient_specificity"] == 2
    assert gate["passed"] is True


def test_residential_followups_are_scored_by_recipient_offer_relevance_not_literal_evidence_copy():
    candidate = {
        "observed_fact": 'В публичной карточке Yes Apart указана категория "Апарт-отель / жилой комплекс".',
        "recipient": "Yes Apart",
        "recipient_type": "residential_complex",
        "sender_mode": "localos_for_partner",
        "represented_business": "Весёлая расчёска",
        "bridge": "Это позволяет обсудить предложение непосредственно для жителей комплекса",
        "trust_statement": "Весёлая расчёска предлагает услуги семьям с детьми рядом с комплексом",
        "evidence_kind": "map_card_category",
        "source_url": "https://example.test/maps/yes-apart",
        "evidence_status": "observed",
        "freshness": "current_snapshot",
        "confidence": 0.95,
        "next_step": "Обсудить небольшой локальный проект для семей",
    }
    messages = [
        (
            "matching_authority",
            "max",
            "Здравствуйте!\n\n"
            "У нас есть несколько идей, как мы могли бы быть полезны сообществу жильцов "
            "Yes Apart. Например, мастер-классы. Это простой способ познакомить жителей "
            "с чем-то новым и сделать жизнь локального сообщества немного интереснее.\n\n"
            "Подскажите, с кем я мог бы обсудить возможное сотрудничество?\n\n"
            "С кем я мог бы обговорить это?",
            16,
            ["MULTIPLE_CTA"],
            False,
        ),
        (
            "proof",
            "vk",
            "Здравствуйте!\n\n"
            "Мы подготовили два варианта сотрудничества для семей Yes Apart.\n\n"
            "Один - специальные условия для жителей комплекса. Второй - небольшие "
            "мероприятия и мастер-классы, которые помогают объединять соседей вокруг "
            "полезных мест рядом с домом.\n\n"
            "Кажется, это могло бы быть интересным. С кем я мог бы обсудить?",
            18,
            [],
            True,
        ),
            (
                "integrated_system",
                "telegram",
                "Здравствуйте!\n\n"
                "Для Yes Apart можно заранее подготовить один понятный сценарий для жителей: "
                "участники, роли, черновик материала и ручная проверка перед внешним шагом.\n\n"
                "Показать такой сценарий?",
                18,
                [],
                True,
            ),
    ]

    for angle, channel, message, expected_score, expected_reasons, expected_passed in messages:
        gate = _quality_gate(
            message,
            candidate,
            None,
            channel=channel,
            channel_status="manual" if channel == "max" else "ready",
            suppressed=False,
            angle=angle,
        )

        assert gate["total_score"] == expected_score
        assert gate["reason_codes"] == expected_reasons
        assert gate["passed"] is expected_passed


def test_new_campaign_version_preserves_saved_human_copy_for_unchanged_channels():
    admin_source = (ROOT / "frontend/src/components/prospecting/AdminLeadRegistry.tsx").read_text()
    campaign_source = (ROOT / "src/services/outreach_campaign_service.py").read_text()

    overrides_start = admin_source.index("const campaignTouchOverrides")
    overrides_end = admin_source.index("\n\n  const", overrides_start)
    overrides_block = admin_source[overrides_start:overrides_end]
    prepare_start = admin_source.index("const prepareOutreachCampaign")
    prepare_end = admin_source.index("\n\n  const approveOutreachCampaign", prepare_start)
    prepare_block = admin_source[prepare_start:prepare_end]

    assert "savedOutreachCampaign?.touches" in overrides_block
    assert "touch.channel === sequenceChannels" in overrides_block
    assert "savedTouch?.message_brief_json?.human_edited" in overrides_block
    assert "campaignSetupDirty" in prepare_block
    assert "preserveSavedCampaign" in prepare_block
    assert "set(override_by_index).issubset(expected_indexes)" in campaign_source
    assert "if index not in override_by_index:" in campaign_source


def test_selected_campaign_recipient_wins_over_generic_email_ranking():
    class SenderCursor:
        def execute(self, _query, _params):
            return None

        def fetchall(self):
            return []

    availability = channel_availability(
        SenderCursor(),
        {
            "sender_mode": "localos_for_partner",
            "client_business_id": "business-1",
            "selected_contact_point_id": "pr-contact",
            "contacts": [
                {
                    "id": "office-contact",
                    "contact_type": "email",
                    "value": "office@yesapart.com",
                    "verification_status": "confirmed_source",
                    "confidence": 0.99,
                },
                {
                    "id": "pr-contact",
                    "contact_type": "email",
                    "value": "pr@yesapart.com",
                    "verification_status": "confirmed_source",
                    "confidence": 0.8,
                },
            ],
        },
    )

    assert availability["email"]["contact_point_id"] == "pr-contact"
    assert availability["email"]["recipient"] == "pr@yesapart.com"


def test_single_ready_email_sender_is_selected_when_other_account_needs_permission():
    class SenderCursor:
        def execute(self, _query, _params):
            return None

        def fetchall(self):
            return [
                {
                    "id": "localosgo-account",
                    "channel": "email",
                    "status": "connected",
                    "sender_identity": "localosgo@gmail.com",
                    "display_name": "LocalOS",
                    "health_status": "healthy",
                    "capabilities_json": {"direct_send": True, "reply_sync": True},
                    "sender_outreach_enabled": True,
                    "telegram_outreach_enabled": None,
                },
                {
                    "id": "info-account",
                    "channel": "email",
                    "status": "connected",
                    "sender_identity": "info@localos.pro",
                    "display_name": "Александр, LocalOS",
                    "health_status": "healthy",
                    "capabilities_json": {"direct_send": True, "reply_sync": True},
                    "sender_outreach_enabled": False,
                    "telegram_outreach_enabled": None,
                },
            ]

    availability = channel_availability(
        SenderCursor(),
        {
            "sender_mode": "localos",
            "contacts": [
                {
                    "id": "recipient-email",
                    "contact_type": "email",
                    "value": "recipient@example.com",
                    "verification_status": "confirmed_source",
                    "confidence": 0.95,
                },
            ],
        },
    )

    assert availability["email"]["status"] == "ready"
    assert availability["email"]["sender_account_id"] == "localosgo-account"
    assert availability["email"]["sender_accounts"] == [
        {
            "id": "localosgo-account",
            "sender_identity": "localosgo@gmail.com",
            "display_name": "LocalOS",
            "health_status": "healthy",
            "status": "ready",
        },
        {
            "id": "info-account",
            "sender_identity": "info@localos.pro",
            "display_name": "Александр, LocalOS",
            "health_status": "healthy",
            "status": "permission_required",
        },
    ]


def test_localosgo_is_default_platform_email_when_multiple_senders_are_ready():
    class SenderCursor:
        def execute(self, _query, _params):
            return None

        def fetchall(self):
            return [
                {
                    "id": "info-account",
                    "channel": "email",
                    "status": "connected",
                    "sender_identity": "info@localos.pro",
                    "display_name": "Александр, LocalOS",
                    "health_status": "healthy",
                    "capabilities_json": {"direct_send": True, "reply_sync": True},
                    "sender_outreach_enabled": True,
                    "telegram_outreach_enabled": None,
                },
                {
                    "id": "localosgo-account",
                    "channel": "email",
                    "status": "connected",
                    "sender_identity": "localosgo@gmail.com",
                    "display_name": "LocalOS",
                    "health_status": "healthy",
                    "capabilities_json": {"direct_send": True, "reply_sync": True},
                    "sender_outreach_enabled": True,
                    "telegram_outreach_enabled": None,
                },
            ]

    availability = channel_availability(
        SenderCursor(),
        {
            "sender_mode": "localos",
            "contacts": [
                {
                    "id": "recipient-email",
                    "contact_type": "email",
                    "value": "recipient@example.com",
                    "verification_status": "confirmed_source",
                    "confidence": 0.95,
                },
            ],
        },
    )

    assert availability["email"]["status"] == "ready"
    assert availability["email"]["sender_account_id"] == "localosgo-account"


def test_manual_vk_uses_vk_recipient_without_requiring_sender_account():
    class SenderCursor:
        def execute(self, _query, _params):
            return None

        def fetchall(self):
            return []

    availability = channel_availability(
        SenderCursor(),
        {
            "sender_mode": "localos_for_partner",
            "client_business_id": "business-1",
            "selected_contact_point_id": "vk-contact",
            "contacts": [
                {
                    "id": "vk-contact",
                    "contact_type": "vk",
                    "value": "https://vk.ru/bnckidsru",
                    "verification_status": "confirmed_source",
                    "confidence": 0.95,
                },
            ],
        },
    )

    assert availability["vk"]["status"] == "connect_required"
    assert availability["vk_manual"]["status"] == "manual"
    assert availability["vk_manual"]["contact_point_id"] == "vk-contact"
    assert availability["vk_manual"]["recipient"] == "https://vk.ru/bnckidsru"
    assert availability["vk_manual"]["sender_account_id"] is None


def test_new_version_message_edit_is_persisted_even_before_schedule_version_is_saved():
    admin_source = (ROOT / "frontend/src/components/prospecting/AdminLeadRegistry.tsx").read_text()

    accept_start = admin_source.index("const acceptTouchEdit")
    accept_end = admin_source.index("\n\n  const reloadLatestOutreachCampaign", accept_start)
    accept_block = admin_source[accept_start:accept_end]

    patch_request = accept_block.index("method: 'PATCH'")
    setup_guard = accept_block.find("if (campaignSetupDirty)")
    assert setup_guard == -1 or patch_request < setup_guard
    assert "subject: draft.subject.trim()" in accept_block
    assert "text: draft.text.trim()" in accept_block


def test_lead_drawer_uses_progressive_disclosure_without_unmounting_form_state():
    source = (ROOT / "frontend/src/components/prospecting/AdminLeadRegistry.tsx").read_text()

    assert "const LeadDrawerSection" in source
    assert 'id="lead-conversation"' in source
    assert 'id="lead-contacts"' in source
    assert 'id="lead-research"' in source
    assert 'id="first-message"' not in source
    assert 'title="Первое сообщение"' not in source
    assert 'id="outreach-sequence"' in source
    assert 'id="sender-settings"' in source
    assert "hidden={!open}" in source
    assert "{open ? children" not in source


def test_lead_drawer_progress_tracks_the_saved_sequence_instead_of_legacy_first_message():
    source = (ROOT / "frontend/src/components/prospecting/AdminLeadRegistry.tsx").read_text()

    assert 'aria-label="Этапы подготовки цепочки обращений"' in source
    assert "['Контакты', 'Получатель', 'Основание', 'Цепочка', 'Проверка']" in source
    assert "Boolean(savedOutreachCampaign?.touches?.length)" in source
    assert "Boolean(savedCampaignQualityPassed && !savedCampaignHasPendingReview)" in source


def test_russian_outreach_ui_uses_human_suppression_labels():
    sources = [
        (ROOT / "frontend/src/components/prospecting/OutreachSuppressionManager.tsx").read_text(),
        (ROOT / "frontend/src/components/prospecting/PartnershipLeadDetailDrawer.tsx").read_text(),
        (ROOT / "frontend/src/components/prospecting/OutreachCampaignBuilder.tsx").read_text(),
        (ROOT / "frontend/src/components/prospecting/AdminLeadRegistry.tsx").read_text(),
    ]
    combined = "\n".join(sources)

    assert "Исключения из контактов" in combined
    assert "Исключить из контактов" in combined
    assert "Не контактировать" not in combined
    assert "Stop-list" not in combined
    assert "stop-list" not in combined


def test_lead_drawer_shows_the_real_connected_sender_and_refreshes_it_after_setup():
    source = (ROOT / "frontend/src/components/prospecting/AdminLeadRegistry.tsx").read_text()

    assert "const loadSenderAccounts" in source
    assert "connectedEmailSender?.sender_identity" in source
    assert "connectedEmailSender?.display_name" in source
    assert "Проверить или заменить email отправителя" in source
    setup_start = source.index("<OutreachEmailSetup")
    setup_end = source.index("/>", setup_start)
    assert "void loadSenderAccounts()" in source[setup_start:setup_end]


def test_lead_drawer_has_one_sticky_next_action_summary():
    source = (ROOT / "frontend/src/components/prospecting/AdminLeadRegistry.tsx").read_text()

    assert 'className="sticky top-0 z-20' in source
    assert "summaryNextAction" in source
    assert "void prepareOutreachCampaign(true)" in source
    assert "scrollToLeadSection(summaryNextAction.target, summaryNextAction.focusTarget)" in source
    assert "Получатель" in source
    assert "Отправитель" in source
    assert "Первый шаг" in source
    assert "Состояние" in source


def test_sticky_next_action_does_not_override_message_review_with_setup_save():
    source = (ROOT / "frontend/src/components/prospecting/AdminLeadRegistry.tsx").read_text()

    sticky_start = source.index('<section className="sticky top-0 z-20')
    sticky_end = source.index("</section>", sticky_start)
    sticky_block = source[sticky_start:sticky_end]

    assert "campaignSetupDirty && summaryNextAction.target === 'outreach-sequence'" in sticky_block
    assert "scrollToLeadSection(summaryNextAction.target, summaryNextAction.focusTarget)" in sticky_block


def test_admin_lead_registry_has_one_operational_surface_without_legacy_duplicate():
    source = (ROOT / "frontend/src/components/prospecting/AdminLeadRegistry.tsx").read_text()

    assert "LegacyProspectingManagement" not in source
    assert "Дополнительные инструменты и аналитика" not in source
    assert "Найти лидов" in source
    assert 'title="Получатель и найденные контакты"' in source
    assert 'title="Почему обращаемся"' in source
    assert 'title="Цепочка, расписание и запуск"' in source
    assert 'title="Отправитель и подключения"' in source


def test_sender_selection_is_always_visible_and_reused_for_same_channel_touches():
    source = (ROOT / "frontend/src/components/prospecting/AdminLeadRegistry.tsx").read_text()

    assert 'id={`touch-sender-${index}`}' in source
    assert "updateSequenceSender(index, event.target.value)" in source
    assert "item === channel ? itemIndex : -1" in source
    assert "Один выбор применяется к шагам" in source
    assert "outreachPreview.channel_availability?.[channel]?.sender_accounts" not in source
    assert "Проверить и сохранить изменения" in source


def test_sticky_next_action_names_regeneration_before_unsaved_schedule_review():
    source = (ROOT / "frontend/src/components/prospecting/AdminLeadRegistry.tsx").read_text()

    action_start = source.index("const summaryNextAction")
    action_end = source.index("\n  const scrollToLeadSection", action_start)
    action_block = source[action_start:action_end]

    regeneration_index = action_block.index("savedOutreachCampaign?.requires_regeneration")
    dirty_setup_index = action_block.index("campaignSetupDirty")
    assert regeneration_index < dirty_setup_index
    assert "Подготовить новую цепочку" in action_block


def test_stale_manually_edited_campaign_is_rechecked_without_replacing_saved_version():
    source = (ROOT / "frontend/src/components/prospecting/AdminLeadRegistry.tsx").read_text()

    action_start = source.index("const summaryNextAction")
    action_end = source.index("\n  const scrollToLeadSection", action_start)
    action_block = source[action_start:action_end]

    manual_review_index = action_block.index("savedOutreachCampaign?.requires_regeneration && savedCampaignHasHumanEdits")
    generic_regeneration_index = action_block.index("savedOutreachCampaign?.requires_regeneration", manual_review_index + 1)
    assert manual_review_index < generic_regeneration_index
    assert "Проверить сохранённые сообщения" in action_block
    assert "Тексты, каналы и расписание останутся в этой же версии" in source


def test_ready_draft_primary_action_is_approval_before_preflight():
    source = (ROOT / "frontend/src/components/prospecting/AdminLeadRegistry.tsx").read_text()

    action_start = source.index("const summaryNextAction")
    action_end = source.index("\n  const scrollToLeadSection", action_start)
    action_block = source[action_start:action_end]

    assert "savedOutreachCampaign?.status === 'draft'" in action_block
    assert "Утвердить цепочку" in action_block
    assert action_block.index("savedOutreachCampaign?.status === 'draft'") < action_block.rindex("Проверить статус кампании")


def test_sticky_campaign_action_distinguishes_approval_from_actual_launch():
    source = (ROOT / "frontend/src/components/prospecting/AdminLeadRegistry.tsx").read_text()

    action_start = source.index("const summaryNextAction")
    action_end = source.index("\n  const scrollToLeadSection", action_start)
    action_block = source[action_start:action_end]

    assert "подтверждена, отправка по графику" in source
    assert "кампания запущена" in source
    assert "Проверить перед отправкой" not in action_block
    assert "Проверить статус кампании" in action_block
    assert action_block.index("pilotAlreadySent") < action_block.index("savedCampaignNeedsChannelSetup")
    assert 'id="campaign-status"' in source
    assert "Автоматические касания выполняются по графику" in source


def test_preflight_is_only_shown_after_campaign_approval():
    admin_source = (ROOT / "frontend/src/components/prospecting/AdminLeadRegistry.tsx").read_text()
    builder_source = (ROOT / "frontend/src/components/prospecting/OutreachCampaignBuilder.tsx").read_text()

    assert "/pilot-preflight" not in admin_source
    assert 'id="campaign-status"' in admin_source
    assert "{selectedCampaign?.status === 'approved' && !pilotAlreadySent && !pilotReplyReceived ? (" in builder_source


def test_partner_builder_blocks_approval_until_current_quality_checked_draft_is_ready():
    source = (ROOT / "frontend/src/components/prospecting/OutreachCampaignBuilder.tsx").read_text()
    approval_start = source.index("{selectedCampaign?.status === 'draft'")
    approval_end = source.index("</Button>", approval_start)
    approval_block = source[approval_start:approval_end]

    assert "campaignReadyForApproval" in approval_block
    assert "disabled={Boolean(busy) || !campaignReadyForApproval}" in approval_block


def test_saved_campaign_hydrates_schedule_form_and_calendar_from_same_version():
    source = (ROOT / "frontend/src/components/prospecting/AdminLeadRegistry.tsx").read_text()

    load_start = source.index("const loadCampaign = async")
    load_end = source.index("void loadCampaign();", load_start)
    load_block = source[load_start:load_end]

    assert "latestCampaign?.touches" in load_block
    assert "setSequenceChannels" in load_block
    assert "setSequenceDays" in load_block
    assert "setSequenceStartAt" in load_block
    assert "setCampaignSetupDirty(false)" in load_block
    assert ".sort((left, right) => new Date(left).getTime() - new Date(right).getTime())[0]" in load_block


def test_channel_setup_blocker_names_vk_permission_and_links_to_exact_outreach_setting():
    admin_source = (ROOT / "frontend/src/components/prospecting/AdminLeadRegistry.tsx").read_text()
    builder_source = (ROOT / "frontend/src/components/prospecting/OutreachCampaignBuilder.tsx").read_text()
    settings_source = (ROOT / "frontend/src/pages/dashboard/settings/IntegrationsPageV3.tsx").read_text()

    assert "VK подключён, но отправка запрещена" in admin_source
    assert "Разрешить отправку в VK" in admin_source
    assert "focus=outreach_vk&sender_scope=${selectedSenderScope}" in admin_source
    assert "focus=vk&sender_scope=${selectedSenderScope}" not in admin_source
    assert "return_to=${encodeURIComponent" in admin_source

    assert "focus=outreach_vk&sender_scope=${businessId ? 'business' : 'platform'}" in builder_source
    assert "focus=vk&sender_scope=${businessId ? 'business' : 'platform'}" not in builder_source

    assert "VK для аутрича LocalOS" in settings_source
    assert "Контур: LocalOS" in settings_source


def test_single_available_sender_can_be_selected_for_every_automatic_touch():
    sources = [
        (ROOT / "frontend/src/components/prospecting/AdminLeadRegistry.tsx").read_text(),
        (ROOT / "frontend/src/components/prospecting/OutreachCampaignBuilder.tsx").read_text(),
    ]

    for source in sources:
        assert "accounts.length <= 1" not in source
        assert "accounts.length === 0" in source or "!accounts.length" in source


def test_sender_settings_no_longer_describe_vk_as_manual_only():
    source = (ROOT / "frontend/src/components/prospecting/AdminLeadRegistry.tsx").read_text()

    assert "MAX, VK и WhatsApp остаются ручными" not in source
    assert "Для VK можно выбрать автоматическую отправку от подключённого сообщества или ручную отправку по найденной ссылке" in source


def test_campaign_preview_always_surfaces_result_and_next_action():
    source = (ROOT / "frontend/src/components/prospecting/AdminLeadRegistry.tsx").read_text()
    prepare_start = source.index("const prepareOutreachCampaign")
    prepare_end = source.index("\n\n  const approveOutreachCampaign", prepare_start)
    prepare_block = source[prepare_start:prepare_end]

    assert "Цепочка подготовлена:" in prepare_block
    assert "outreach-preview-result" in prepare_block
    assert "outreachPreview?.status === 'observe'" in source
    assert "outreachPreview?.status === 'needs_contact'" in source
    assert "outreachPreview?.status === 'needs_sender_setup'" in source
    assert "Цепочка пока не создана" in source


def test_explicitly_selected_valid_format_email_is_available_for_campaign():
    class SenderCursor:
        def execute(self, _query, _params):
            return None

        def fetchall(self):
            return []

    availability = channel_availability(
        SenderCursor(),
        {
            "sender_mode": "localos",
            "selected_contact_point_id": "selected-email",
            "contacts": [
                {
                    "id": "selected-email",
                    "contact_type": "email",
                    "value": "sepasta4@mail.ru",
                    "verification_status": "valid_format",
                    "confidence": 0.8,
                    "source_type": "map_card",
                },
            ],
        },
    )

    assert availability["email"]["contact_point_id"] == "selected-email"
    assert availability["email"]["recipient"] == "sepasta4@mail.ru"
    assert availability["email"]["status"] == "connect_required"


def test_lead_drawer_renders_message_editor_only_in_messages_section():
    source = (ROOT / "frontend/src/components/prospecting/AdminLeadRegistry.tsx").read_text()

    conversation_start = source.index('title="Сообщения и каналы"')
    sequence_start = source.index('title="Цепочка, расписание и запуск"')
    sender_start = source.index('title="Отправитель и подключения"', sequence_start)
    conversation_block = source[conversation_start:sequence_start]
    sequence_block = source[sequence_start:sender_start]

    assert "<OutreachTouchMessageEditor" in conversation_block
    assert "<OutreachTouchMessageEditor" not in sequence_block
    assert "displayedOutreachTouches.map" not in sequence_block


def test_unsaved_campaign_setup_is_restored_for_same_workstream_after_reload():
    source = (ROOT / "frontend/src/components/prospecting/AdminLeadRegistry.tsx").read_text()

    assert "outreachCampaignSetupStorageKey" in source
    assert "localos:outreach-campaign-setup:" in source
    assert "sequenceChannels" in source
    assert "sequenceDays" in source
    assert "sequenceSenders" in source
    assert "localStorage.setItem(outreachCampaignSetupStorageKey" in source
    assert "localStorage.getItem(outreachCampaignSetupStorageKey" in source
