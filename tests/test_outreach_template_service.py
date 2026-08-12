from services.outreach_template_service import (
    OUTREACH_TEMPLATES,
    TEMPLATE_LIBRARY_VERSION,
    render_outreach_template,
    attach_public_audit_link,
    select_outreach_template,
    template_allows_two_questions,
    template_copy_matches,
    template_owner_pain_matches,
)
from services.outreach_campaign_service import (
    _format_channel_outreach_message,
    _message_for_angle,
    _quality_gate,
)
from services.outreach_playbook import beauty_outreach_guidance


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


def test_library_contains_nine_versioned_owner_templates():
    assert TEMPLATE_LIBRARY_VERSION == "localos_outreach_templates_v7"
    assert len(OUTREACH_TEMPLATES) == 9
    assert len({item["key"] for item in OUTREACH_TEMPLATES}) == 9
    assert all(item["version"] >= 1 for item in OUTREACH_TEMPLATES)
    assert all(item.get("owner_language") for item in OUTREACH_TEMPLATES)


def test_playbook_exposes_five_supported_owner_pains():
    guidance = beauty_outreach_guidance()
    assert guidance["localos_supported_pain_count"] == 5
    assert len(guidance["localos_supported_pain_keys"]) == 5
    assert set(guidance["localos_supported_pain_keys"]).issubset(
        {item["key"] for item in guidance["pain_library"]}
    )
    assert set(guidance["localos_supported_pain_keys"]) == {
        item["pain_key"] for item in OUTREACH_TEMPLATES
    }


def test_revenue_without_profit_template_uses_owner_language_as_hypothesis():
    candidate = _candidate(
        observed_fact="На сайте запись ведётся через DIKIDI.",
        evidence_kind="crm_presence",
        crm_provider_name="DIKIDI",
    )
    selection = select_outreach_template("integrated_system", candidate)
    selected = {
        **candidate,
        "outreach_template_key": selection["key"],
        "outreach_template_version": selection["version"],
        "trust_statement": "Подтверждённый опыт LocalOS",
    }
    text = render_outreach_template(selection, selected)

    assert selection["key"] == "revenue_without_profit_control_v1"
    assert "выручка есть, а прибыли нет" in text
    assert "Не знаю, актуально ли это для вас" in text
    assert "обезличенные данные" in text
    assert template_owner_pain_matches(text, "integrated_system", selected) is True


def test_playbook_keeps_owner_rule_for_weak_map_first_touch():
    rules = " ".join(beauty_outreach_guidance()["method_rules"])
    assert "карточка на Яндекс Картах" in rules
    assert "риск недополучать клиентов" in rules
    assert "ссылка на аудит" in rules


def test_low_rating_template_is_selected_and_uses_approved_owner_copy():
    candidate = _candidate()
    selection = select_outreach_template("signal", candidate)
    text = render_outreach_template(selection, candidate)

    assert selection["key"] == "weak_map_rating_beauty_v1"
    assert "сейчас 2,5" in text
    assert "Рейтинг карточки Padrina_studio на Яндекс Картах сейчас 2,5" in text
    assert "мы с нуля привлекли 10 клиентов с карт" in text
    assert "от 1200 рублей в месяц" in text
    assert text.count("?") == 1
    assert "—" not in text


def test_zero_rating_sentinel_cannot_select_low_rating_template():
    candidate = _candidate(observed_fact="Рейтинг - 0,0; публичных отзывов - 2.")
    candidate["rating"] = 0

    selection = select_outreach_template("signal", candidate)

    assert selection["status"] == "individual_copy_required"
    assert any(
        item["key"] == "weak_map_rating_beauty_v1"
        and "low_map_rating_required" in item["reasons"]
        for item in selection["rejected"]
    )


def test_active_social_template_uses_time_pain_and_concrete_multichannel_result():
    candidate = _candidate(
        observed_fact=(
            "Вижу, вы ведёте соцсети: за последние 30 дней в Telegram "
            "вышло 8 публикаций."
        ),
        evidence_kind="active_social_activity",
        signal_combo="active_social_multichannel_content",
    )

    selection = select_outreach_template("content_operations", candidate)
    text = render_outreach_template(selection, candidate)

    assert selection["key"] == "active_social_multichannel_content_v1"
    assert "приходится готовить несколько раз" in text
    assert "это отнимает время" in text
    assert "Telegram, VK и Яндекс Карт" in text
    assert text.endswith("Вам было бы интересно сэкономить время на ведении площадок?")
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


def test_social_content_touch_introduces_map_audit_as_an_additional_result():
    candidate = _candidate(
        observed_fact="В Telegram за 30 дней вышло 8 публикаций.",
        evidence_kind="active_social_activity",
        signal_combo="active_social_multichannel_content",
        public_audit_url="https://localos.pro/example",
        include_public_audit_link=True,
    )
    selection = select_outreach_template("content_operations", candidate)

    text = render_outreach_template(selection, candidate)

    assert (
        "Помимо этого, мы ещё собрали аудит по вашей карточке на картах. "
        "Сможете поправить сами: https://localos.pro/example"
    ) in text
    assert text.count("?") == 1


def test_crm_template_requires_a_confirmed_provider_and_current_source():
    candidate = _candidate(
        observed_fact="В карточке опубликована запись через DIKIDI.",
        evidence_kind="crm_presence",
        crm_provider_name="DIKIDI",
    )
    selection = select_outreach_template("crm_content", candidate)
    text = render_outreach_template(selection, candidate)

    assert selection["key"] == "crm_completed_service_content_v2"
    assert "На основе выгрузки из DIKIDI" in text
    assert "черновики" in text
    assert "не всегда понятно, что публиковать" in text
    assert "времени на контент не хватает" in text
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
    assert select_outreach_template("content_operations", candidate)["key"] == "map_service_price_coverage_v3"


def test_map_price_gap_names_yandex_maps_and_follows_sales_flow():
    candidate = _candidate(
        recipient="Кожно-венерологический диспансер № 7",
        observed_fact=(
            "По данным аудита карточки на Яндекс Картах: "
            "всего услуг - 27; с ценой - 3."
        ),
        evidence_kind="map_issue",
        public_audit_url=(
            "https://localos.pro/kozhno-venerologicheskiy-dispanser-7"
        ),
        include_public_audit_link=True,
    )

    selection = select_outreach_template("content_operations", candidate)
    text = render_outreach_template(selection, candidate)

    assert selection["key"] == "map_service_price_coverage_v3"
    assert (
        "Вижу, что в карточке компании Кожно-венерологический диспансер № 7 на Яндекс Картах "
        "есть 27 услуг, но цена указана только у 3."
    ) in text
    assert "может недополучать обращения с карт" in text
    assert "LocalOS поможет исправить карточку" in text
    assert "мы с нуля привлекли 10 клиентов с карт" in text
    assert "Стоимость - от 1200 рублей в месяц" in text
    assert "сможете поправить сами" in text
    assert text.endswith("Вам может быть это интересно?")
    assert text.count("?") == 1
    assert "—" not in text


def test_description_gap_is_not_an_outreach_signal_for_yandex_maps():
    candidate = _candidate(
        observed_fact="В карточке Padrina_studio нет описания бизнеса.",
        evidence_kind="map_description_gap",
        signal_combo="map_description_gap",
    )
    selection = select_outreach_template("content_operations", candidate)
    assert selection["status"] == "individual_copy_required"
    assert selection["key"] is None


def test_news_gap_template_offers_client_acquisition_instead_of_time_saving():
    candidate = _candidate(
        recipient="Анни",
        observed_fact="В карточке Анни нет новостей.",
        evidence_kind="map_gap",
        signal_combo="map_content_gap",
    )
    selection = select_outreach_template("content_operations", candidate)
    text = render_outreach_template(selection, candidate)

    assert selection["key"] == "map_content_gap_v4"
    assert "В карточке компании Анни на Яндекс Картах нет новостей." in text
    assert "возможно, вы просто не успеваете" in text.lower()
    assert "сэкономить время на публикациях" in text
    assert text.count("?") == 1


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


def test_templates_do_not_repeat_one_owner_pain_inside_sequence():
    rating = _candidate()
    services = _candidate(
        observed_fact="По данным аудита карточки: всего услуг - 30; с ценой - 2.",
        evidence_kind="map_issue",
    )
    first = select_outreach_template("signal", rating)
    second = select_outreach_template(
        "content_operations",
        services,
        used_template_keys=[first["key"]],
        used_pain_keys=[first["pain_key"]],
    )

    assert second["status"] == "individual_copy_required"
    assert any(
        item["key"] == "map_service_price_coverage_v3"
        and "pain_already_used_in_sequence" in item["reasons"]
        for item in second["rejected"]
    )


def test_selected_template_rejects_copy_without_owner_pain_language():
    candidate = _candidate(
        recipient="Анни",
        observed_fact="В карточке Анни нет новостей.",
        evidence_kind="map_gap",
        signal_combo="map_content_gap",
    )
    selection = select_outreach_template("content_operations", candidate)
    selected = {**candidate, "outreach_template_key": selection["key"]}
    generic = (
        "В карточке компании Анни на Яндекс Картах нет новостей. "
        "LocalOS подготовит черновики новостей. Показать пример?"
    )

    assert template_owner_pain_matches(generic, "content_operations", selected) is False


def test_missing_evidence_returns_explicit_individual_copy_fallback():
    selection = select_outreach_template(
        "integrated_system",
        _candidate(source_url="", freshness="", signal_combo=""),
    )

    assert selection["status"] == "individual_copy_required"
    assert selection["key"] is None
    assert selection["rejected"]


def test_all_templates_pass_current_quality_gate_on_supported_evidence():
    cases = (
        ("content_operations", _candidate(
            observed_fact="За последние 30 дней в Telegram вышло 8 публикаций.",
            evidence_kind="active_social_activity",
            signal_combo="active_social_multichannel_content",
        )),
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
        ("integrated_system", _candidate(
            observed_fact="На сайте запись ведётся через DIKIDI.",
            evidence_kind="crm_presence",
            crm_provider_name="DIKIDI",
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
        message = _format_channel_outreach_message(
            _message_for_angle(angle, reviewed_candidate, None, []),
            channel="email",
            sender_mode="localos",
        )
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
