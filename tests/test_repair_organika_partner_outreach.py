from scripts.repair_organika_partner_outreach import (
    _candidate,
    _manual_gate,
    _messages,
    _offer_data,
    _proposal,
    _recipient_kind,
)


def test_organika_partner_segments_are_explicit():
    assert _recipient_kind("DESALU", "Магазин детской одежды") == "child_retail"
    assert _recipient_kind("Fitness House", "Фитнес-клуб / бассейн") == "fitness"
    assert _recipient_kind("33-й Зуб", "Стоматологическая клиника") == "medical_team"
    assert _recipient_kind("Level UP", "Бизнес-центр") == "employee_benefit"
    assert _recipient_kind(
        "Watsons",
        "Магазин парфюмерии и косметики / магазин хозтоваров / фитнес-клуб",
    ) == "beauty_retail"
    assert _recipient_kind("Viva mare", "Туристическое агентство") == "travel"
    assert _recipient_kind("Oceankid", "Бассейн / центр развития ребёнка") == "child_education"
    assert _recipient_kind("Прибавление", "Товары для детей") == "child_retail"


def test_direct_competitors_and_non_addressable_entries_need_evidence():
    for name, category in (
        ("Borneo Beauty", "Ногтевая студия"),
        ("Лак", "Студия маникюра"),
        ("Детский развлекательный автомат", "Детские развлечения"),
        ("Мастерская по ремонту обуви", "Сервис у дома"),
    ):
        assert _recipient_kind(name, category) == "observe"
        assert _proposal(name, category)["status"] == "needs_evidence"
        assert _messages(name, category) == []


def test_child_retail_offer_uses_real_organika_services():
    offer = _offer_data("DESALU", "Магазин детской одежды")
    first_touch = _messages("DESALU", "Магазин детской одежды")[0]["text"]

    assert "детские стрижки, укладки" in first_touch
    assert "праздником или фотосессией" in first_touch
    assert "LocalOS" not in first_touch
    assert "Александр" not in first_touch
    assert "публичной карточке" not in first_touch
    assert "с кем можно обсудить детали?" in first_touch
    assert "покупают детские товары в DESALU" in offer["summary"]


def test_medical_offer_is_for_staff_not_patients():
    proposal = _proposal("33-й Зуб", "Стоматологическая клиника")
    body = proposal["body_text"]

    assert "сотрудникам компании 33-й Зуб" in body
    assert "без рекомендаций пациентам" in body
    assert "стрижки, маникюр или массаж" in body


def test_fitness_offer_uses_confirmed_massage_services():
    messages = _messages("Fitness House", "Фитнес-клуб / бассейн")

    assert "спортивный и расслабляющий массаж" in messages[0]["text"]
    assert "после тренировок" in messages[0]["text"]


def test_all_supported_sequences_pass_the_quality_gate():
    cases = (
        ("Oceankid", "Бассейн / центр развития ребёнка"),
        ("DESALU", "Магазин детской одежды"),
        ("Театр Кот Вильям", "Детский театр"),
        ("Fitness House", "Фитнес-клуб / бассейн"),
        ("33-й Зуб", "Стоматологическая клиника"),
        ("Level UP", "Бизнес-центр"),
        ("ТРК Атмосфера", "Торгово-развлекательный центр"),
        ("Watsons", "Магазин парфюмерии и косметики"),
        ("Viva mare", "Туристическое агентство"),
    )
    for index, (name, category) in enumerate(cases):
        candidate = _candidate(name, category, "https://example.test", f"ws-{index}")
        messages = _messages(name, category)
        assert len(messages) == 4
        for message in messages:
            gate = _manual_gate(message["text"], candidate, "email", message["angle"])
            assert gate["passed"] is True
            assert gate["total_score"] >= 15
            assert message["text"].count("?") == 1
