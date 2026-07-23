from scripts.repair_localos_sales_outreach import (
    REPAIR_VERSION,
    _bridge_for_fact,
    _messages,
    _proposal,
    _select_evidence,
    _usable_audit_evidence,
    _valid_uuid,
)


FOUNDER_STORY = (
    "Я развиваю LocalOS и сам разбираю публичные данные локальных компаний - "
    "карточки, услуги, отзывы и контент."
)


def _evidence(fact: str, observed_at: str = "2026-07-22T12:00:00+00:00"):
    return {
        "id": "evidence-1",
        "kind": "map_issue",
        "status": "observed",
        "fact": fact,
        "source_url": "https://localos.pro/audit",
        "observed_at": observed_at,
        "freshness": "fresh",
    }


def test_selects_latest_usable_audit_fact_and_rejects_zero_rating():
    older = _evidence("По данным аудита карточки: всего услуг - 60; с ценой - 15.", "2026-07-20T12:00:00+00:00")
    current = _evidence("По данным аудита карточки: всего услуг - 57; с ценой - 15.")
    zero_rating = _evidence("Рейтинг - 0,0; публичных отзывов - 9.", "2026-07-23T12:00:00+00:00")
    row = {"evidence_json": [older, current, zero_rating]}
    assert _select_evidence(row)["fact"] == current["fact"]
    assert not _usable_audit_evidence(zero_rating)


def test_neutral_rating_is_not_used_when_it_is_not_a_material_signal():
    weak_rating = _evidence("Рейтинг - 4,3; публичных отзывов - 28.")
    assert not _usable_audit_evidence(weak_rating)


def test_nearly_complete_service_prices_are_not_used_as_a_problem():
    almost_complete = _evidence("По данным аудита карточки: всего услуг - 30; с ценой - 28.")
    assert not _usable_audit_evidence(almost_complete)


def test_review_quote_is_not_used_as_outreach_fact():
    review = {
        "kind": "review",
        "status": "observed",
        "fact": "В отзыве клиент жалуется на сервис.",
        "source_url": "https://maps.example/review",
    }
    assert not _usable_audit_evidence(review)


def test_service_price_fact_gets_concrete_bridge():
    bridge = _bridge_for_fact("По данным аудита карточки: всего услуг - 57; с ценой - 15.")
    assert "для каких услуг клиент видит цену" in bridge


def test_room_proposal_uses_audit_fact_and_online_to_offline_bridge():
    evidence = _evidence("По данным аудита карточки: всего услуг - 57; с ценой - 15.")
    proposal = _proposal("047 Beauty Zone", evidence, "write_now")
    assert proposal["source"] == REPAIR_VERSION
    assert proposal["status"] == "draft"
    assert evidence["fact"] in proposal["body_text"]
    assert "найти бизнес в онлайн-поиске" in proposal["body_text"]
    assert "решение о визите" in proposal["body_text"]


def test_sequence_has_four_angles_and_does_not_repeat_fact_in_followups():
    evidence = _evidence("По данным аудита карточки: всего услуг - 57; с ценой - 15.")
    messages = _messages("047 Beauty Zone", evidence, FOUNDER_STORY)
    assert len(messages) == 4
    assert len({message["angle"] for message in messages}) == 4
    assert evidence["fact"] in messages[0]["text"]
    assert all(evidence["fact"] not in message["text"] for message in messages[1:])
    assert all(message["text"].count("?") == 1 for message in messages)
    assert all("—" not in message["text"] for message in messages)
    assert "Я Александр Демьянов" in messages[0]["text"]
    assert "больше писать не буду" in messages[3]["text"]


def test_sequence_does_not_require_recipient_name_declension():
    evidence = _evidence("По данным аудита карточки: всего услуг - 5; с ценой - 2.")
    name = "Пушкинский музыкально-драматический театр"
    messages = _messages(name, evidence, FOUNDER_STORY)
    assert f"По карточке {name}" in messages[1]["text"]
    assert f"Для карточки {name}" in messages[2]["text"]
    assert "отвлекать вашу команду" in messages[3]["text"]


def test_missing_evidence_never_creates_generic_offer():
    proposal = _proposal("Lead", None, "needs_evidence")
    assert proposal["status"] == "needs_evidence"
    assert "Предложение пока не готовим" in proposal["body_text"]


def test_legacy_business_slug_is_not_treated_as_uuid():
    assert _valid_uuid("6e5f16b4-489d-4659-815a-73d231b6797e")
    assert not _valid_uuid("grand-shaverma-165577542041")
    assert not _valid_uuid("")
