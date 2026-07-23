from scripts.repair_veselaya_partner_outreach import (
    _candidate,
    _manual_gate,
    _messages,
    _offer_summary,
    _proposal,
    _room_needs_repair,
    _choose_contacts,
    _usable_contact,
)


def test_kidburg_chain_uses_business_voice_and_concrete_profession_workshop():
    name = "Кидбург"
    category = "Детский город профессий"
    messages = _messages(name, category)

    assert len(messages) == 4
    assert "мастер-класс" in _offer_summary(name, category)
    assert all(name in item["text"] for item in messages)
    assert all(item["text"].count("?") == 1 for item in messages)
    assert all("LocalOS" not in item["text"] for item in messages)
    assert all("Александр" not in item["text"] for item in messages)


def test_residential_room_leads_with_special_conditions_for_residents():
    proposal = _proposal("ЖК Северная Долина", "Жилой комплекс")

    assert "особые условия на детские стрижки для жителей ЖК Северная Долина" in proposal["body_text"]
    assert "каналы ЖК" in proposal["body_text"]
    assert "листовки" in proposal["body_text"]
    assert "мастер-класс" in proposal["body_text"]
    assert "Конкретные условия" in proposal["body_text"]

    aparthotel = _proposal("Yes apart", "Апарт-отель / жилой комплекс")
    assert "семей гостей и жителей" in aparthotel["body_text"]
    assert "особые условия на детские стрижки" in aparthotel["body_text"]
    assert "ресепшене" in aparthotel["body_text"]


def test_yes_apart_first_touch_leads_with_guest_benefit_not_card_metadata():
    messages = _messages("Yes apart", "Апарт-отель / жилой комплекс")
    first_touch = messages[0]["text"]

    assert "В публичной карточке" not in first_touch
    assert "категория" not in first_touch
    assert "особые условия на детские стрижки" in first_touch
    assert "семей гостей и жителей Yes Apart" in first_touch
    assert "Не подскажете, с кем я мог бы обсудить детали?" in first_touch
    assert "Прислать короткое предложение?" not in first_touch
    assert first_touch.count("?") == 1
    assert len(first_touch.split()) <= 36


def test_other_residential_first_touch_uses_the_same_benefit_first_pattern():
    messages = _messages("ЖК Северная Долина", "Жилой комплекс")
    first_touch = messages[0]["text"]

    assert "В публичной карточке" not in first_touch
    assert "категория" not in first_touch
    assert "особые условия на детские стрижки для жителей ЖК Северная Долина" in first_touch
    assert "Не подскажете, с кем я мог бы обсудить детали?" in first_touch
    assert first_touch.count("?") == 1


def test_other_residential_chain_passes_current_deterministic_quality_gate():
    name = "ЖК Северная Долина"
    category = "Жилой комплекс"
    candidate = _candidate(name, category, "https://example.ru", "workstream-residential")

    for message in _messages(name, category):
        gate = _manual_gate(message["text"], candidate, "email", message["angle"])
        assert gate["passed"] is True
        assert gate["total_score"] >= 15


def test_yes_apart_chain_passes_current_deterministic_quality_gate():
    name = "Yes apart"
    category = "Апарт-отель / жилой комплекс"
    candidate = _candidate(name, category, "https://yesapart.com", "workstream-yes-apart")

    for message in _messages(name, category):
        gate = _manual_gate(message["text"], candidate, "email", message["angle"])
        assert gate["passed"] is True
        assert gate["total_score"] >= 15
        assert gate["manual_review"]["passed"] is True


def test_shared_venue_and_wrong_brand_contacts_are_not_recipients():
    assert _usable_contact(
        {
            "contact_type": "email",
            "value": "info@trk-canyon.ru",
            "source_url": "https://trk-canyon.ru/contacts",
            "verification_status": "confirmed_source",
        },
        "Eco beauty bar",
    ) is False
    assert _usable_contact(
        {
            "contact_type": "email",
            "value": "office@kabriol.ru",
            "source_url": "https://kabriol.ru/contacts",
            "verification_status": "confirmed_source",
        },
        "Спортивный клуб Gymfusion",
    ) is False
    assert _usable_contact(
        {
            "contact_type": "phone",
            "value": "+79675505252",
            "source_url": "https://yandex.ru/maps/org/eco",
            "verification_status": "confirmed_source",
        },
        "Eco beauty bar",
    ) is True


def test_public_telegram_channel_is_not_used_as_recipient():
    assert _usable_contact(
        {
            "contact_type": "telegram",
            "value": "https://t.me/example_channel",
            "source_url": "https://example.ru",
            "verification_status": "confirmed_source",
            "metadata_json": {"telegram_entity_kind": "channel"},
        },
        "Партнёр",
    ) is False
    assert _usable_contact(
        {
            "contact_type": "telegram",
            "value": "https://t.me/yesapartofficial",
            "verification_status": "confirmed_source",
            "metadata_json": {"recipient_eligible": False},
        },
        "Yes apart",
    ) is False


def test_unverified_found_contact_is_not_used_for_a_draft():
    assert _usable_contact(
        {
            "contact_type": "email",
            "value": "hello@example.ru",
            "source_url": "https://example.ru",
            "verification_status": "found",
        },
        "Партнёр",
    ) is False


def test_aparthotel_outreach_prefers_office_and_ignores_owner_or_rent_mailboxes():
    contacts = [
        {"id": "owner", "contact_type": "email", "value": "owner_hsm@yesapart.com", "verification_status": "confirmed_source"},
        {"id": "rent", "contact_type": "email", "value": "rent_hsm@yesapart.com", "verification_status": "confirmed_source"},
        {"id": "office", "contact_type": "email", "value": "office@yesapart.com", "verification_status": "confirmed_source"},
        {"id": "pr", "contact_type": "email", "value": "pr@yesapart.com", "verification_status": "confirmed_source"},
    ]

    selected = _choose_contacts(contacts, "Yes apart")

    assert selected[0][0] == "email"
    assert selected[0][1]["id"] == "office"


def test_manual_chain_passes_current_deterministic_quality_gate():
    name = "Кидбург"
    category = "Детский город профессий"
    candidate = _candidate(name, category, "https://kidburg.ru", "workstream-1")

    for message in _messages(name, category):
        gate = _manual_gate(message["text"], candidate, "email", message["angle"])
        assert gate["passed"] is True
        assert gate["total_score"] >= 15
        assert gate["manual_review"]["passed"] is True


def test_only_generic_or_mismatched_rooms_are_rewritten():
    assert _room_needs_repair(
        "CROCKID",
        "У Весёлая расчёска и CROCKID есть пересечение. Следующий шаг - 20-минутный разговор.",
    ) is True
    assert _room_needs_repair(
        "Спортивный клуб Gymfusion",
        "Подумали над форматом сотрудничества для воспитанниц Кабриоль.",
    ) is True
    assert _room_needs_repair(
        "Кидбург",
        "Мастера Весёлой расчёски могут проводить мастер-классы по профессии парикмахера.",
    ) is False
    assert _room_needs_repair(
        "ЖК Северная Долина",
        "Хотели бы пригласить жителей к нам и обсудить листовки.",
        "Жилой комплекс",
    ) is True
    assert _room_needs_repair(
        "ЖК Северная Долина",
        "Предлагаем особые условия на детские стрижки для жителей ЖК Северная Долина.",
        "Жилой комплекс",
    ) is False
