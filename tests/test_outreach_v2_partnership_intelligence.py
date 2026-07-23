from services.outreach_campaign_service import (
    _message_for_angle,
    build_personalization_candidates,
)
from services.outreach_decision_service import (
    build_outreach_decision,
    offer_candidates,
    score_evidence,
    trust_candidates,
)
from services.outreach_relationship_service import _json_safe, build_relationship_delta, build_room_preview


def _compatibility_evidence():
    return [{
        "id": "partnership-compatibility",
        "kind": "service_compatibility",
        "fact": "В публичной карточке указаны семейные тренировки и детские секции.",
        "status": "observed",
        "source_url": "https://example.test/maps/partner",
        "observed_at": "2026-07-22T10:00:00+00:00",
        "freshness": "current_snapshot",
        "confidence": 0.9,
        "relevance": "У компаний пересекается семейная аудитория в одном районе.",
    }]


def _availability():
    return {
        "telegram": {"status": "ready"},
        "email": {"status": "manual"},
    }


def test_signal_score_redistributes_missing_engagement_weight():
    result = score_evidence({
        "id": "signal-1",
        "fact": "Компания открыла новую точку 20 июля 2026 года рядом с метро.",
        "relevance": "Новая точка делает предложение по локальному запуску своевременным.",
        "confidence": 1,
        "freshness": "fresh",
    })

    assert result["engagement_omitted"] is True
    assert sum(item["weight"] for item in result["components"].values()) == 90
    assert result["score"] >= 90


def test_suppression_is_stronger_than_high_scores():
    decision = build_outreach_decision(
        {
            "workstream_type": "client_partnership",
            "lifecycle_status": "active",
            "contacts": [{"verification_status": "verified"}],
            "partnership_match": {"match_score": 96},
        },
        _compatibility_evidence(),
        _availability(),
        {"suppressed": True},
        sender_mode="localos_for_partner",
        profile_ready=True,
    )

    assert decision["action"] == "excluded"
    assert "suppressed_contact" in decision["reason_codes"]


def test_strong_partnership_matching_can_write_without_social_post():
    decision = build_outreach_decision(
        {
            "workstream_type": "client_partnership",
            "lifecycle_status": "active",
            "contacts": [{"verification_status": "verified"}],
            "partnership_match": {"match_score": 82},
        },
        _compatibility_evidence(),
        _availability(),
        {"suppressed": False},
        sender_mode="localos_for_partner",
        profile_ready=True,
    )

    assert decision["action"] == "write_now"
    assert "partnership_compatibility_confirmed" in decision["reason_codes"]


def test_residential_offer_starts_with_invitation_and_keeps_terms_uncommitted():
    offers = offer_candidates(
        {
            "lead_name": "ЖК Новые кварталы",
            "category": "Жилой комплекс",
            "client_business_name": "Новамед",
            "represented_business_name": "Новамед",
            "business_sender_profile": {
                "confirmed_at": None,
                "allowed_offers_json": ["Скидка 20% всем жильцам"],
            },
            "partnership_match": {
                "offer_angles": ["Один безопасный совместный тест"],
            },
        },
        "localos_for_partner",
    )

    assert offers[0]["source"] == "residential_recipient_policy"
    assert offers[0]["text"] == "Пригласить жителей ЖК Новые кварталы в Новамед"
    assert "условия согласовать отдельно" in offers[0]["cta"].lower()
    assert all("20%" not in item["text"] for item in offers)


def test_veselaya_residential_offer_uses_approved_special_conditions_policy():
    offers = offer_candidates(
        {
            "lead_name": "ЖК Северная Долина",
            "category": "Жилой комплекс",
            "client_business_name": "Весёлая расчёска",
            "represented_business_name": "Весёлая расчёска",
            "partnership_match": {},
        },
        "localos_for_partner",
    )

    assert offers[0]["source"] == "approved_business_outreach_policy"
    assert offers[0]["text"] == (
        "Предложить особые условия на детские стрижки для жителей ЖК Северная Долина"
    )
    assert "с кем можно обсудить детали" in offers[0]["cta"].lower()


def test_veselaya_yes_apart_offer_mentions_guests_and_residents():
    offers = offer_candidates(
        {
            "lead_name": "Yes apart",
            "category": "Апарт-отель / жилой комплекс",
            "represented_business_name": "Весёлая расчёска",
            "partnership_match": {},
        },
        "localos_for_partner",
    )

    assert "семей гостей и жителей Yes apart" in offers[0]["text"]


def test_localos_for_partner_uses_matching_authority_without_localos_founder_story():
    context = {
        "lead_name": "Семейный клуб",
        "workstream_type": "client_partnership",
        "sender_mode": "localos_for_partner",
        "represented_business_name": "Органика",
        "client_business_type": "магазин",
        "client_business_categories": ["магазин"],
        "sender_profile": {
            "display_name": "Алексей",
            "role_title": "представитель",
            "company_name": "LocalOS",
            "confirmed_at": "2026-07-22T10:00:00+00:00",
        },
        "platform_sender_profile": {
            "competence_story": "История основателя LocalOS не должна попасть в это сообщение.",
            "allowed_offers_json": ["Купить LocalOS"],
            "confirmed_at": "2026-07-22T10:00:00+00:00",
        },
        "business_sender_profile": {},
        "partnership_match": {
            "match_score": 82,
            "relevance_bridge": "У компаний пересекается семейная аудитория района.",
            "offer_angles": ["Обсудить один небольшой совместный тест для семей района"],
        },
    }
    offers = offer_candidates(context, "localos_for_partner")
    trusts = trust_candidates(context, "localos_for_partner")
    candidates = build_personalization_candidates(
        context,
        _compatibility_evidence(),
        selected_offer=offers[0],
        selected_trust=trusts[0],
    )
    message = _message_for_angle("founder_story", candidates[0], None, [])

    assert candidates[0]["founder_story"] == ""
    assert candidates[0]["trust_strategy"] == "matching_authority"
    assert "Мы ваши соседи - Органика." in message
    assert "LocalOS" not in message
    assert "Алексей" not in message
    assert "История основателя LocalOS" not in message
    assert "Купить LocalOS" not in message


def test_partner_business_message_uses_business_reputation_and_never_names_localos():
    context = {
        "lead_name": "Семейный клуб",
        "workstream_type": "client_partnership",
        "sender_mode": "partner_business",
        "sender_profile": {
            "id": "profile-organika",
            "display_name": "Анна",
            "role_title": "основатель",
            "company_name": "Органика",
            "competence_story": "Органика много лет работает с семьями этого района.",
            "proof_points_json": [{"status": "approved", "fact": "Проводили семейные мероприятия с соседними проектами."}],
            "allowed_offers_json": [{"status": "approved", "fact": "Обсудить совместный семейный день"}],
            "forbidden_claims_json": [{"status": "approved", "fact": "Не обещать гарантированный поток клиентов"}],
            "confirmed_at": "2026-07-22T10:00:00+00:00",
            "voice_examples_json": ["Здравствуйте! Есть идея для соседского проекта."],
            "outreach_context_json": {
                "competence_story_status": "approved",
                "audience": "Семьи района",
                "desired_partner_types": ["Семейные клубы"],
            },
        },
        "business_service_count": 4,
        "business_sender_profile": {
            "display_name": "Анна",
            "role_title": "основатель",
            "company_name": "Органика",
            "competence_story": "Органика много лет работает с семьями этого района.",
            "proof_points_json": [{"status": "approved", "fact": "Проводили семейные мероприятия с соседними проектами."}],
            "allowed_offers_json": [{"status": "approved", "fact": "Обсудить совместный семейный день"}],
            "forbidden_claims_json": [{"status": "approved", "fact": "Не обещать гарантированный поток клиентов"}],
            "voice_examples_json": [{"status": "approved", "fact": "Здравствуйте! Есть идея для соседского проекта."}],
            "confirmed_at": "2026-07-22T10:00:00+00:00",
            "outreach_context_json": {
                "competence_story_status": "approved",
                "audience": "Семьи района",
                "desired_partner_types": ["Семейные клубы"],
            },
        },
        "partnership_match": {"match_score": 82},
    }
    offers = offer_candidates(context, "partner_business")
    trusts = trust_candidates(context, "partner_business")
    candidates = build_personalization_candidates(
        context,
        _compatibility_evidence(),
        selected_offer=offers[0],
        selected_trust=trusts[0],
    )
    message = _message_for_angle("business_reputation", candidates[0], {}, [])

    assert "Органика" in message
    assert "Проводили семейные мероприятия" in message
    assert "LocalOS" not in message


def test_relationship_reply_and_room_preview_are_pure_projections():
    relationship = build_relationship_delta(
        "Да, интересно. Лучше пишите в Telegram.",
        "interested",
    )
    room = build_room_preview(
        {
            "lead_id": "lead-1",
            "sender_mode": "partner_business",
            "decision": {"action": "write_now"},
            "selected_offer": {"text": "Совместный тест"},
            "selected_trust": {"strategy": "business_reputation"},
        },
        {"lead_name": "Партнёр", "city": "Санкт-Петербург"},
    )

    assert relationship["preferred_channel"] == "telegram"
    assert relationship["negotiation_stage"] == "engaged"
    assert room["visibility"] == "private"
    assert room["status"] == "prepared"
    assert room["proposal"]["title"] == "Идея сотрудничества"
    assert room["proposal"]["body_text"] == "Совместный тест"
    assert "20-минут" not in room["proposal"]["body_text"]


def test_partner_room_falls_back_to_safe_copy_without_selected_offer():
    room = build_room_preview(
        {
            "lead_id": "lead-2",
            "sender_mode": "localos_for_partner",
            "decision": {"action": "write_now"},
            "selected_offer": {},
            "selected_trust": {"strategy": "matching_authority"},
        },
        {
            "lead_name": "Партнёр",
            "client_business_name": "Бизнес",
            "city": "Санкт-Петербург",
        },
    )

    assert "общая локальная аудитория" in room["proposal"]["body_text"]


def test_room_json_projection_serializes_database_dates():
    from datetime import datetime, timezone

    value = _json_safe({"observed_at": datetime(2026, 7, 22, tzinfo=timezone.utc)})
    assert value == {"observed_at": "2026-07-22T00:00:00+00:00"}
