from services.outreach_template_service import (
    OUTREACH_TEMPLATES,
    TEMPLATE_LIBRARY_VERSION,
    render_outreach_template,
    attach_public_audit_link,
    select_outreach_template,
    template_allows_two_questions,
    template_copy_matches,
)
from services.outreach_campaign_service import _message_for_angle, _quality_gate


def _candidate(**overrides):
    candidate = {
        "recipient": "Padrina_studio",
        "recipient_category": "Салон красоты",
        "recipient_segment": "beauty_team",
        "sender": "Александр Демьянов",
        "sender_role": "основатель LocalOS",
        "observed_fact": "Рейтинг - 2,5; публичных отзывов - 3.",
        "evidence_kind": "map_rating",
        "evidence_status": "observed",
        "source_url": "https://yandex.ru/maps/org/padrina/1",
        "freshness": "current_snapshot",
        "next_step": "Показать пример",
        "sender_mode": "localos",
    }
    candidate.update(overrides)
    return candidate


def test_library_contains_eight_versioned_owner_templates():
    assert TEMPLATE_LIBRARY_VERSION == "localos_outreach_templates_v1"
    assert len(OUTREACH_TEMPLATES) == 8
    assert len({item["key"] for item in OUTREACH_TEMPLATES}) == 8
    assert all(item["version"] == 1 for item in OUTREACH_TEMPLATES)


def test_low_rating_template_is_selected_and_uses_approved_owner_copy():
    candidate = _candidate()
    selection = select_outreach_template("signal", candidate)
    text = render_outreach_template(selection, candidate)

    assert selection["key"] == "weak_map_rating_beauty_v1"
    assert "рейтинг 2,5" in text
    assert "В карточке Padrina_studio сейчас рейтинг 2,5" in text
    assert "мы с нуля привлекли 10 клиентов с карт" in text
    assert "от 1200 рублей в месяц" in text
    assert text.count("?") == 1
    assert "—" not in text


def test_public_audit_link_is_added_only_for_explicit_first_touch():
    candidate = _candidate(
        public_audit_url="https://localos.pro/padrina-studio",
        include_public_audit_link=True,
    )
    selection = select_outreach_template("signal", candidate)
    text = render_outreach_template(selection, candidate)

    assert (
        "Мы подготовили аудит карточки на картах, сможете поправить сами: "
        "https://localos.pro/padrina-studio"
    ) in text
    assert text.endswith("Вам может быть это интересно?")
    assert "Мы подготовили аудит" not in attach_public_audit_link(
        "Здравствуйте!\n\nПоказать?",
        {**candidate, "include_public_audit_link": False},
    )
    assert "Мы подготовили аудит" not in attach_public_audit_link(
        "Здравствуйте!\n\nПоказать?",
        {**candidate, "public_audit_url": "https://example.com/audit"},
    )


def test_crm_template_requires_a_confirmed_provider_and_current_source():
    candidate = _candidate(
        observed_fact="В карточке опубликована запись через DIKIDI.",
        evidence_kind="crm_presence",
        crm_provider_name="DIKIDI",
    )
    selection = select_outreach_template("crm_content", candidate)
    text = render_outreach_template(selection, candidate)

    assert selection["key"] == "crm_completed_service_content_v1"
    assert "На основе выгрузки из DIKIDI" in text
    assert "черновики" in text
    assert select_outreach_template("crm_content", {**candidate, "crm_provider_name": ""})["status"] == "individual_copy_required"
    assert select_outreach_template("crm_content", {**candidate, "freshness": "stale"})["status"] == "individual_copy_required"


def test_average_ticket_template_has_strict_two_question_contract():
    candidate = _candidate(
        observed_fact="На сайте запись ведётся через DIKIDI.",
        evidence_kind="crm_presence",
        crm_provider_name="DIKIDI",
    )
    selection = select_outreach_template("average_ticket", candidate)
    text = render_outreach_template(selection, candidate)

    assert selection["key"] == "average_ticket_service_matrix_v1"
    assert template_allows_two_questions(text, "average_ticket", candidate) is True
    assert template_copy_matches(text, "average_ticket", candidate) is True
    assert template_allows_two_questions(text.replace("увеличить", "поднять"), "average_ticket", candidate) is False
    assert template_copy_matches(text.replace("увеличить", "поднять"), "average_ticket", candidate) is False


def test_map_price_gap_cannot_be_reused_as_average_ticket_signal():
    candidate = _candidate(
        observed_fact="По данным аудита карточки: всего услуг - 30; с ценой - 4.",
        evidence_kind="map_issue",
    )

    assert select_outreach_template("average_ticket", candidate)["status"] == "individual_copy_required"
    assert select_outreach_template("content_operations", candidate)["key"] == "map_service_price_coverage_v1"


def test_description_gap_template_is_grounded_and_passes_strict_flow():
    candidate = _candidate(
        observed_fact="В карточке Padrina_studio нет описания бизнеса.",
        evidence_kind="map_description_gap",
        signal_combo="map_description_gap",
    )
    selection = select_outreach_template("content_operations", candidate)
    text = render_outreach_template(selection, candidate)

    assert selection["key"] == "map_description_gap_v1"
    assert "нет описания бизнеса" in text
    assert "LocalOS подготовит черновик описания" in text


def test_templates_do_not_repeat_inside_one_sequence():
    candidate = _candidate()
    first = select_outreach_template("signal", candidate)
    second = select_outreach_template("signal", candidate, used_template_keys=[first["key"]])

    assert first["status"] == "selected"
    assert second["status"] == "individual_copy_required"
    assert any(
        item["key"] == first["key"] and "already_used_in_sequence" in item["reasons"]
        for item in second["rejected"]
    )


def test_missing_evidence_returns_explicit_individual_copy_fallback():
    selection = select_outreach_template(
        "integrated_system",
        _candidate(source_url="", freshness="", signal_combo=""),
    )

    assert selection["status"] == "individual_copy_required"
    assert selection["key"] is None
    assert selection["rejected"]


def test_all_six_templates_pass_current_quality_gate_on_supported_evidence():
    cases = (
        ("signal", _candidate()),
        ("crm_content", _candidate(
            observed_fact="В карточке опубликована запись через DIKIDI.",
            evidence_kind="crm_presence",
            crm_provider_name="DIKIDI",
        )),
        ("average_ticket", _candidate(
            observed_fact="На сайте запись ведётся через DIKIDI.",
            evidence_kind="crm_presence",
            crm_provider_name="DIKIDI",
        )),
        ("integrated_system", _candidate(
            observed_fact="26 июля опубликована новая услуга диагностики кожи.",
            evidence_kind="new_service",
            signal_combo="recent_new_service_announcement",
        )),
        ("reviews_service", _candidate(
            observed_fact="В карточке есть свежий отзыв без ответа компании.",
            evidence_kind="review_signal",
        )),
        ("content_operations", _candidate(
            observed_fact="В карточке нет новостей.",
            evidence_kind="map_gap",
            signal_combo="map_content_gap",
        )),
        ("content_operations", _candidate(
            observed_fact="По данным аудита карточки: всего услуг - 30; с ценой - 2.",
            evidence_kind="map_issue",
        )),
        ("content_operations", _candidate(
            observed_fact="В карточке Padrina_studio нет описания бизнеса.",
            evidence_kind="map_description_gap",
            signal_combo="map_description_gap",
        )),
    )

    selected_keys = []
    for angle, candidate in cases:
        selection = select_outreach_template(angle, candidate)
        selected_keys.append(selection["key"])
        reviewed_candidate = {
            **candidate,
            "outreach_template_key": selection["key"],
            "outreach_template_version": selection["version"],
            "trust_statement": "Подтверждённый опыт LocalOS",
        }
        message = _message_for_angle(angle, reviewed_candidate, None, [])
        gate = _quality_gate(
            message,
            reviewed_candidate,
            None,
            channel="email",
            channel_status="ready",
            suppressed=False,
            angle=angle,
        )
        assert gate["passed"] is True, (selection["key"], gate)
        assert gate["total_score"] == 18

    assert set(selected_keys) == {item["key"] for item in OUTREACH_TEMPLATES}
