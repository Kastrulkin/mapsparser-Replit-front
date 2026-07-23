from scripts.repair_remaining_partner_outreach import (
    BUSINESSES,
    _messages,
    _offer,
    _proposal,
    _recipient_kind,
)


NOVAMED = BUSINESSES["38a11c0e-6eea-4fdc-90d6-66f21af9adce"]
OLIVER = BUSINESSES["533c1300-8a54-43a8-aa1f-69a8ed9c24ba"]
SHANSIK = BUSINESSES["46bb9a2f-bd03-5930-9644-76315016d471"]


def test_novamed_avoids_competitors_and_has_residential_offer():
    assert _recipient_kind("novamed", "Алекс-Стом", "Стоматологическая клиника") == "observe"
    kind = _recipient_kind("novamed", "ЖК Рассказово", "Жилой комплекс")
    assert kind == "residential"
    assert "жителям ЖК Рассказово" in _offer("novamed", kind, "ЖК Рассказово")["opening"]


def test_oliver_residential_copy_uses_business_voice_and_concrete_benefit():
    messages = _messages(OLIVER, "Legenda на Яхтенной, 24", "Жилой комплекс")
    assert len(messages) == 4
    assert "Мы ваши соседи - салон красоты Оливер" in messages[0]["text"]
    assert "особые условия" in messages[0]["text"]
    assert "LocalOS" not in messages[0]["text"]


def test_oliver_dental_offer_is_for_staff_not_patients():
    messages = _messages(OLIVER, "Dental Place", "Стоматологическая клиника")
    assert "сотрудникам Dental Place" in messages[0]["text"]
    assert "без рекомендаций пациентам" in messages[1]["text"]


def test_shansik_routes_useful_and_weak_partners_differently():
    assert _recipient_kind("shansik", "Sun School", "Детский сад, ясли / центр развития ребёнка") == "child_education"
    assert _recipient_kind("shansik", "Spbfoto", "Фотостудия / фотоуслуги") == "photo"
    assert _recipient_kind("shansik", "Plastica", "Спортивный клуб, секция / школа танцев") == "observe"
    assert _recipient_kind("shansik", "Илата", "Стоматологическая клиника") == "observe"


def test_shansik_message_is_specific_and_does_not_name_localos():
    messages = _messages(SHANSIK, "Sun School", "Детский сад, ясли / центр развития ребёнка")
    assert "пробное занятие по танцам и акробатике" in messages[0]["text"]
    assert "LocalOS" not in " ".join(item["text"] for item in messages)
    assert all(item["text"].count("?") == 1 for item in messages)
    assert "от Шансика" in messages[3]["text"]


def test_needs_evidence_room_does_not_create_generic_offer():
    proposal = _proposal(NOVAMED, "Алекс-Стом", "Стоматологическая клиника")
    assert proposal["status"] == "needs_evidence"
    assert "Конкретное предложение пока не готовим" in proposal["body_text"]


def test_all_ready_sequences_have_four_distinct_angles():
    scenarios = (
        (NOVAMED, "ЖК Рассказово", "Жилой комплекс"),
        (OLIVER, "Фотограф Коробейникова Евгения", "Фотоуслуги"),
        (SHANSIK, "Spbfoto", "Фотостудия / фотоуслуги"),
    )
    for config, name, category in scenarios:
        messages = _messages(config, name, category)
        assert len(messages) == 4
        assert len({item["angle"] for item in messages}) == 4
        assert len({item["text"] for item in messages}) == 4
        assert ": можно начать" not in messages[2]["text"]
