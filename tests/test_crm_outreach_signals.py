from services import contact_intelligence_service
from services.outreach_campaign_service import (
    DEFAULT_SEQUENCE,
    _evidence_aware_sequence_angle,
    _message_for_angle,
    _quality_gate,
)


def _localos_workstream():
    return {"id": "ws-crm", "workstream_type": "localos_sales"}


def _crm_signal(payload):
    return next(
        item for item in payload["signals_json"]
        if item.get("kind") == "crm_presence"
    )


def test_known_booking_crm_in_map_payload_is_source_bound_without_invented_pain():
    payload = contact_intelligence_service.build_native_research_payload(
        {
            "id": "lead-dikidi",
            "name": "Клиника М32",
            "category": "Медицинский центр / косметология",
            "website": "https://m32.example",
            "source_url": "https://yandex.ru/maps/org/klinika_m32/207917182858/",
            "raw_payload_json": {
                "onlineBookingUrl": "https://dikidi.net/123456",
            },
        },
        _localos_workstream(),
    )

    signal = _crm_signal(payload)

    assert signal["provider_key"] == "dikidi"
    assert signal["provider_name"] == "DIKIDI"
    assert signal["provider_domain"] == "dikidi.net"
    assert signal["source_url"].startswith("https://yandex.ru/maps/org/klinika_m32")
    assert signal["source_type"] == "map_payload"
    assert signal["researched_at"]
    assert signal["confidence"] >= 0.9
    assert signal["hypothesis"] is None
    assert payload["message_brief_json"]["pain"] == ""
    assert payload["message_brief_json"]["crm_context"]["not_a_pain"] is True
    assert payload["score_breakdown"]["problem_strength"] == 0
    assert len([
        item for item in payload["signals_json"]
        if item.get("kind") == "crm_presence"
    ]) == 1


def test_official_website_detects_known_provider_and_explicit_unknown_provider():
    known = contact_intelligence_service.extract_booking_crm_observations_from_html(
        '<a href="https://w123.yclients.com/company:42">Записаться</a>',
        "https://clinic.example/contacts",
    )
    unknown = contact_intelligence_service.extract_booking_crm_observations_from_html(
        '<a data-booking-provider="BookFlow Pro" href="https://bookflow.example/widget/42">Онлайн-запись</a>',
        "https://clinic.example/contacts",
    )

    assert known[0]["provider_key"] == "yclients"
    assert known[0]["provider_domain"] == "w123.yclients.com"
    assert unknown[0]["provider_key"] == "other_booking_crm"
    assert unknown[0]["provider_name"] == "BookFlow Pro"
    assert unknown[0]["provider_domain"] == "bookflow.example"
    assert unknown[0]["confidence"] < known[0]["confidence"]


def test_generic_booking_button_does_not_invent_a_crm():
    observations = contact_intelligence_service.extract_booking_crm_observations_from_html(
        '<a href="/booking">Записаться</a>',
        "https://clinic.example/contacts",
    )

    assert observations == []


def test_yandex_booking_partner_keeps_explicit_unknown_provider_as_other_crm():
    for provider_name in ("Sonline", "Universe Soft"):
        payload = contact_intelligence_service.build_native_research_payload(
            {
                "id": f"lead-{provider_name.lower().replace(' ', '-')}",
                "name": "Beauty Today",
                "category": "Салон красоты",
                "source_url": "https://yandex.ru/maps/org/beauty_today/1",
                "raw_payload_json": {
                    "bookingPartner": {"partner": provider_name},
                },
            },
            _localos_workstream(),
        )

        signal = _crm_signal(payload)

        assert signal["provider_key"] == "other_booking_crm"
        assert signal["provider_name"] == provider_name
        assert signal["provider_domain"] == ""
        assert signal["source_type"] == "map_payload"
        assert signal["hypothesis"] is None
        assert payload["message_brief_json"]["pain"] == ""


def test_yandex_booking_partner_normalizes_known_provider_without_booking_url():
    payload = contact_intelligence_service.build_native_research_payload(
        {
            "id": "lead-yandex-yclients",
            "name": "Клиника",
            "category": "Косметология",
            "source_url": "https://yandex.ru/maps/org/clinic/2",
            "raw_payload_json": {
                "bookingPartner": {"partner": "yclients"},
            },
        },
        _localos_workstream(),
    )

    signal = _crm_signal(payload)

    assert signal["provider_key"] == "yclients"
    assert signal["provider_name"] == "YCLIENTS"
    assert signal["provider_domain"] == ""


def test_website_crm_observation_from_another_official_host_is_rejected():
    payload = contact_intelligence_service.build_native_research_payload(
        {
            "id": "lead-source-mismatch",
            "name": "Салон",
            "category": "Салон красоты",
            "website": "https://salon.example",
            "source_url": "https://yandex.ru/maps/org/salon/1",
            "public_crm_observations": [{
                "provider_key": "yclients",
                "provider_name": "YCLIENTS",
                "provider_domain": "yclients.com",
                "source_url": "https://unrelated.example/contacts",
                "source_type": "official_website",
                "observed_at": "2026-08-10T10:00:00+03:00",
                "confidence": 0.95,
            }],
        },
        _localos_workstream(),
    )

    assert not any(item.get("kind") == "crm_presence" for item in payload["signals_json"])


def test_official_social_crm_link_is_kept_with_the_post_url():
    payload = contact_intelligence_service.build_native_research_payload(
        {
            "id": "lead-social-crm",
            "name": "Студия",
            "category": "Салон красоты",
            "source_url": "https://yandex.ru/maps/org/studio/2",
        },
        _localos_workstream(),
        {
            "radar_signals": [{
                "message_text": "Онлайн-запись: https://n123.yclients.com/company:5",
                "message_link": "https://t.me/studio_official/77",
                "message_date": "2026-08-09T10:00:00+03:00",
                "chat_title": "Студия",
                "relevance_score": 90,
                "auto_discovered": True,
            }],
        },
    )

    signal = _crm_signal(payload)
    assert signal["provider_key"] == "yclients"
    assert signal["source_type"] == "official_social"
    assert signal["source_url"] == "https://t.me/studio_official/77"


def test_non_beauty_or_medical_lead_does_not_get_crm_personalization_signal():
    payload = contact_intelligence_service.build_native_research_payload(
        {
            "id": "lead-restaurant",
            "name": "Кафе",
            "category": "Ресторан",
            "source_url": "https://yandex.ru/maps/org/cafe/3",
            "raw_payload_json": {"onlineBookingUrl": "https://dikidi.net/cafe"},
        },
        _localos_workstream(),
    )

    assert not any(item.get("kind") == "crm_presence" for item in payload["signals_json"])


def test_last_touch_is_a_standalone_new_angle_without_sequence_closing_language():
    assert DEFAULT_SEQUENCE[-1][2] == "integrated_system"
    candidate = {
        "recipient": "М32",
        "observed_fact": "На официальном сайте найдена запись через DIKIDI.",
        "bridge": "Это открывает сценарии на основе структурированного учёта приёмов",
        "founder_story": "LocalOS помогает готовить проверяемые рабочие сценарии.",
        "founder_proof": "LocalOS используется локальными компаниями.",
        "trust_statement": "Подтверждённый опыт LocalOS",
        "source_url": "https://clinic.example",
        "evidence_status": "observed",
        "freshness": "current_snapshot",
        "next_step": "Показать один сценарий",
        "evidence_kind": "crm_presence",
        "recipient_category": "Медицинский центр / косметология",
        "recipient_segment": "beauty_team",
        "sender_mode": "localos",
        "sender": "Александр Демьянов",
        "sender_role": "основатель LocalOS",
        "crm_type": "dikidi",
        "crm_provider_name": "DIKIDI",
        "crm_integration_mode": "manual_or_capability_check_required",
    }

    growth_message = _message_for_angle("crm_growth", candidate, None, [])
    message = _message_for_angle("crm_content", candidate, None, [])
    lowered = message.lower()

    assert "Актуальна ли для М32 задача увеличивать средний чек?" in growth_message
    assert "без увеличения количества записей" not in growth_message.lower()
    assert "Я Александр Демьянов, основатель LocalOS" in growth_message
    assert "Я Александр Демьянов, основатель LocalOS" in message
    assert "dikidi" in lowered
    assert "черновик" in lowered
    assert "вручную" in lowered or "если передать" in lowered
    assert all(
        phrase not in lowered
        for phrase in (
            "последнее письмо",
            "больше писать не буду",
            "больше писать не будем",
            "закрываю переписку",
            "закрою тему",
            "закроем тему",
        )
    )
    assert message.count("?") == 1


def test_crm_evidence_replaces_average_ticket_and_final_system_angles():
    crm_evidence = {"kind": "crm_presence", "provider_name": "Sonline"}

    assert _evidence_aware_sequence_angle("audit_step", crm_evidence) == "crm_growth"
    assert _evidence_aware_sequence_angle("average_ticket", crm_evidence) == "crm_growth"
    assert _evidence_aware_sequence_angle("integrated_system", crm_evidence) == "crm_content"
    assert _evidence_aware_sequence_angle("content_operations", crm_evidence) == "content_operations"
    assert _evidence_aware_sequence_angle("average_ticket", None) == "average_ticket"
    assert _evidence_aware_sequence_angle("respectful_close", None) == "integrated_system"


def test_quality_gate_rejects_sequence_closing_language_even_in_manual_copy():
    candidate = {
        "recipient": "Клиника",
        "observed_fact": "На официальном сайте найдена запись через DIKIDI.",
        "bridge": "Можно проверить один сценарий на основе структурированного учёта приёмов",
        "founder_story": "LocalOS помогает готовить проверяемые рабочие сценарии.",
        "founder_proof": "LocalOS помогает готовить проверяемые рабочие сценарии.",
        "trust_statement": "LocalOS помогает готовить проверяемые рабочие сценарии.",
        "source_url": "https://clinic.example",
        "evidence_status": "observed",
        "freshness": "current_snapshot",
        "next_step": "Показать один сценарий",
        "evidence_kind": "crm_presence",
        "sender_mode": "localos",
        "recipient_segment": "beauty_team",
    }
    text = (
        "Здравствуйте! Для Клиники можно проверить один сценарий на основе "
        "структурированного учёта приёмов. Если неактуально, больше писать не буду. "
        "Показать один сценарий?"
    )

    gate = _quality_gate(
        text,
        candidate,
        None,
        channel="email",
        channel_status="ready",
        suppressed=False,
        angle="integrated_system",
    )

    assert gate["passed"] is False
    assert "sequence_closing_language" in gate["blocking_reasons"]
    assert "STYLE_VIOLATION" in gate["reason_codes"]

    alternate = _quality_gate(
        text.replace("больше писать не буду", "больше вас отвлекать не будем"),
        candidate,
        None,
        channel="email",
        channel_status="ready",
        suppressed=False,
        angle="integrated_system",
    )
    assert "sequence_closing_language" in alternate["blocking_reasons"]
