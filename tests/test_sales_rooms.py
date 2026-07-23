from flask import Flask

from src.api.admin_prospecting import (
    SALES_ROOM_DATA_AUDITED,
    SALES_ROOM_DATA_TEMPLATE,
    SALES_ROOM_MODE_CLIENT,
    SALES_ROOM_MODE_PARTNER,
    _check_public_sales_room_rate_limit,
    _build_sales_room_invitation_text,
    _build_sales_room_payload,
    _build_sales_room_proposal,
    _normalize_sales_room_audit_offer_payload,
    _normalize_public_sales_room_proposal,
    _public_sales_room_rate_buckets,
    _public_audit_offer_visible_for_user,
    _serialize_public_audit_offer,
)


def test_public_room_preserves_human_approved_proposal_heading() -> None:
    room_json = {
        "proposal": {
            "title": "Идея сотрудничества",
            "summary": "Небольшой совместный пилот.",
            "body_text": "Кажется, у нас есть общая аудитория.",
            "bullets": ["Формат уже собран"],
            "next_step": "Выбрать формат.",
        }
    }

    normalized = _normalize_public_sales_room_proposal(
        None,
        {"mode": SALES_ROOM_MODE_PARTNER, "lead_id": "lead-1"},
        room_json,
    )

    assert normalized["proposal"]["title"] == "Идея сотрудничества"
    assert normalized["proposal"]["summary"] == "Небольшой совместный пилот."
    assert normalized["proposal"]["bullets"] == ["Формат уже собран"]


def test_partner_sales_room_invitation_points_to_room() -> None:
    text = _build_sales_room_invitation_text(
        mode=SALES_ROOM_MODE_PARTNER,
        data_mode=SALES_ROOM_DATA_AUDITED,
        business_name="Органика",
        lead_name="Весёлая расчёска",
        room_url="https://localos.pro/room/demo",
    )

    assert "предложение по возможному партнёрству" in text
    assert "https://localos.pro/room/demo" in text


def test_template_room_does_not_claim_audit() -> None:
    proposal = _build_sales_room_proposal(
        mode=SALES_ROOM_MODE_CLIENT,
        data_mode=SALES_ROOM_DATA_TEMPLATE,
        lead={"name": "Новамед"},
        business_name="LocalOS",
        audit_json={},
        match_json={},
    )

    assert proposal["data_mode"] == SALES_ROOM_DATA_TEMPLATE
    assert "аудит" not in proposal["summary"].lower()


def test_audited_localos_offer_uses_audit_facts_and_online_to_offline_value() -> None:
    proposal = _build_sales_room_proposal(
        mode=SALES_ROOM_MODE_CLIENT,
        data_mode=SALES_ROOM_DATA_AUDITED,
        lead={
            "name": "047 Beauty Zone",
            "category": "салон красоты",
            "source_url": "https://yandex.ru/maps/org/047-beauty-zone",
        },
        business_name="LocalOS",
        audit_json={
            "summary_text": "Карточку можно усилить.",
            "findings": [{
                "title": "Не заполнены цены",
                "description": "В карточке 12 услуг, цены указаны только у 2.",
            }],
        },
        match_json={},
    )

    body = proposal["body_text"].lower()
    assert "12 услуг" in body
    assert "цены указаны только у 2" in body
    assert "онлайн" in body
    assert "офлайн" in body
    assert "клиент" in body


def test_beauty_to_residential_room_uses_flyers_and_masterclasses_only() -> None:
    proposal = _build_sales_room_proposal(
        mode=SALES_ROOM_MODE_PARTNER,
        data_mode=SALES_ROOM_DATA_TEMPLATE,
        lead={
            "name": "Legenda на Яхтенной, 24",
            "category": "Жилой комплекс",
        },
        business_name="Оливер",
        business_profile={
            "name": "Оливер",
            "business_type": "beauty_salon",
            "industry": "Салон красоты",
        },
        audit_json={},
        match_json={},
    )

    body = proposal["body_text"].lower()
    assert proposal["title"] == "Идея сотрудничества"
    assert "мы ваши соседи - оливер" in body
    assert "разместить наши листовки" in body
    assert "приглашать жителей на открытые мастер-классы" in body
    assert "управляющей компанией" in body
    assert "кросс-рекомендац" not in body
    assert "интеграц" not in body
    assert "скид" not in body


def test_veselaya_to_residential_room_leads_with_special_conditions() -> None:
    proposal = _build_sales_room_proposal(
        mode=SALES_ROOM_MODE_PARTNER,
        data_mode=SALES_ROOM_DATA_TEMPLATE,
        lead={"name": "ЖК Северная Долина", "category": "Жилой комплекс"},
        business_name="Весёлая расчёска",
        business_profile={},
        audit_json={},
        match_json={},
    )

    body = proposal["body_text"].lower()
    assert "мы ваши соседи - весёлая расчёска" in body
    assert "особые условия на детские стрижки для жителей жк северная долина" in body
    assert "каналы жк" in body
    assert "листовки" in body
    assert "мастер-класс" in body
    assert "конкретные условия" in body


def test_unconfirmed_beauty_business_does_not_inherit_oliver_formats() -> None:
    proposal = _build_sales_room_proposal(
        mode=SALES_ROOM_MODE_PARTNER,
        data_mode=SALES_ROOM_DATA_TEMPLATE,
        lead={"name": "ЖК Соседи", "category": "Жилой комплекс"},
        business_name="Другой салон",
        business_profile={
            "name": "Другой салон",
            "business_type": "beauty_salon",
            "industry": "Салон красоты",
        },
        audit_json={},
        match_json={},
    )

    body = proposal["body_text"].lower()
    assert "пригласить ваших жителей к нам" in body
    assert "мастер-класс" not in body
    assert "листов" not in body
    assert "скид" not in body


def test_non_beauty_to_residential_room_invites_residents_without_invented_terms() -> None:
    proposal = _build_sales_room_proposal(
        mode=SALES_ROOM_MODE_PARTNER,
        data_mode=SALES_ROOM_DATA_TEMPLATE,
        lead={
            "name": "ЖК Новые кварталы",
            "category": "Жилой комплекс",
        },
        business_name="Новамед",
        business_profile={
            "name": "Новамед",
            "business_type": "cosmetology",
            "industry": "Косметология",
        },
        audit_json={},
        match_json={},
    )

    body = proposal["body_text"].lower()
    assert proposal["title"] == "Идея сотрудничества"
    assert "мы ваши соседи - новамед" in body
    assert "пригласить ваших жителей к нам" in body
    assert "конкретный формат и условия" in body
    assert "управляющей компанией" in body
    assert "мастер-класс" not in body
    assert "скид" not in body
    assert "особые условия" not in body


def test_residential_room_ignores_unreviewed_generic_ai_offer() -> None:
    proposal = _build_sales_room_proposal(
        mode=SALES_ROOM_MODE_PARTNER,
        data_mode=SALES_ROOM_DATA_TEMPLATE,
        lead={"name": "ЖК Новые кварталы", "category": "Жилой комплекс"},
        business_name="Новамед",
        business_profile={"name": "Новамед", "business_type": "medical_center"},
        audit_json={},
        match_json={},
        offer_draft_json={
            "generated_text": "Предлагаем один безопасный совместный тест без интеграции."
        },
    )

    assert "пригласить ваших жителей к нам" in proposal["body_text"]
    assert "безопасный совместный тест" not in proposal["body_text"]


def test_residential_room_preserves_explicitly_edited_offer() -> None:
    proposal = _build_sales_room_proposal(
        mode=SALES_ROOM_MODE_PARTNER,
        data_mode=SALES_ROOM_DATA_TEMPLATE,
        lead={"name": "ЖК Новые кварталы", "category": "Жилой комплекс"},
        business_name="Новамед",
        business_profile={"name": "Новамед", "business_type": "medical_center"},
        audit_json={},
        match_json={},
        offer_draft_json={
            "edited_text": "Хотим пригласить жителей на подтверждённый день открытых дверей."
        },
    )

    assert proposal["body_text"] == (
        "Хотим пригласить жителей на подтверждённый день открытых дверей."
    )


def test_sales_room_payload_hides_audit_for_template_mode() -> None:
    payload = _build_sales_room_payload(
        mode=SALES_ROOM_MODE_CLIENT,
        data_mode=SALES_ROOM_DATA_TEMPLATE,
        lead={"name": "Новамед", "category": "медицина", "source_url": "https://yandex.ru/maps/org/demo"},
        business_profile={"name": "LocalOS"},
        audit_public_url="https://localos.pro/audit",
        audit_json={"summary_text": "private audit", "findings": [{"title": "private finding"}]},
        match_json={"match_score": 99, "offer_angles": ["private match"]},
        proposal_json={"title": "Знания уровня сетей", "summary": "Шаблон", "bullets": ["Идея"]},
        slug="room-demo",
    )

    assert payload["audit"]["available"] is False
    assert payload["audit"]["summary_text"] is None
    assert payload["match"]["available"] is False
    assert payload["cta"]["secondary_label"] == "Проверить свою компанию в LocalOS"


def test_audited_partner_room_includes_match() -> None:
    payload = _build_sales_room_payload(
        mode=SALES_ROOM_MODE_PARTNER,
        data_mode=SALES_ROOM_DATA_AUDITED,
        lead={"name": "Весёлая расчёска", "category": "салон красоты"},
        business_profile={"name": "Органика"},
        audit_public_url="",
        audit_json={"summary_text": "Есть точки роста", "findings": [{"title": "Нет услуг"}]},
        match_json={"match_score": 82, "offer_angles": ["Общий клиентский сегмент"]},
        proposal_json={"title": "Партнёрство", "summary": "Сопоставили услуги", "bullets": ["Тест"]},
        slug="room-partner",
    )

    assert payload["match"]["available"] is True
    assert payload["match"]["match_score"] == 82
    assert payload["business"]["name"] == "Органика"


def test_public_sales_room_rate_limit_returns_retry_after() -> None:
    app = Flask(__name__)
    _public_sales_room_rate_buckets.clear()

    with app.test_request_context(
        "/api/sales-rooms/public/demo/messages",
        method="POST",
        environ_base={"REMOTE_ADDR": "203.0.113.10"},
    ):
        assert _check_public_sales_room_rate_limit("message", "demo", 1, 60) is None
        limited = _check_public_sales_room_rate_limit("message", "demo", 1, 60)

    assert limited is not None
    response, status_code = limited
    assert status_code == 429
    assert response.headers["Retry-After"]
    assert response.get_json()["reason"] == "public_sales_room_write_limit"

    _public_sales_room_rate_buckets.clear()


def test_audit_offer_payload_defaults_to_prepared_when_audit_url_exists() -> None:
    payload = _normalize_sales_room_audit_offer_payload(
        {
            "enabled": True,
            "company_name": "Новамед",
            "company_map_url": "https://yandex.ru/maps/org/demo",
            "prepared_audit_slug": "novamed",
        }
    )

    assert payload["status"] == "prepared"
    assert payload["platform"] == "yandex"
    assert payload["button_text"] == "Создать аудит карточки"
    assert payload["prepared_audit_url"].endswith("/novamed")


def test_audit_offer_teaser_visible_for_unverified_participant_without_url() -> None:
    offer = {
        "id": "offer-1",
        "enabled": True,
        "status": "offered",
        "prepared_audit_slug": "shansik-set-detskikh-tantsevalnykh-studiy",
        "lead_email": "lead@example.com",
        "prepared_audit_url": "https://localos.pro/audit",
    }
    participant = {"email": "lead@example.com", "is_verified": False}

    serialized = _serialize_public_audit_offer(offer, participant, expose_teaser=True)

    assert serialized is not None
    assert serialized["audit_url"] is None
    assert serialized["prepared_audit_slug"] == "shansik-set-detskikh-tantsevalnykh-studiy"
    assert serialized["requires_registration"] is True


def test_audit_offer_does_not_expose_audit_url_before_ready() -> None:
    offer = {
        "id": "offer-1",
        "enabled": True,
        "status": "offered",
        "lead_email": "lead@example.com",
        "prepared_audit_url": "https://localos.pro/audit",
    }
    participant = {"email": "lead@example.com", "is_verified": True}

    serialized = _serialize_public_audit_offer(offer, participant)

    assert serialized is not None
    assert serialized["status"] == "offered"
    assert serialized["audit_url"] is None


def test_audit_offer_exposes_audit_url_when_ready() -> None:
    offer = {
        "id": "offer-1",
        "enabled": True,
        "status": "ready",
        "lead_email": "lead@example.com",
        "prepared_audit_url": "https://localos.pro/audit",
    }
    participant = {"email": "lead@example.com", "is_verified": True}

    serialized = _serialize_public_audit_offer(offer, participant)

    assert serialized is not None
    assert serialized["audit_url"] == "https://localos.pro/audit"


def test_audit_offer_hidden_for_logged_in_foreign_business() -> None:
    class Cursor:
        def __init__(self) -> None:
            self.executed = False

        def execute(self, *_args, **_kwargs) -> None:
            self.executed = True

        def fetchall(self):
            return [{"name": "Весёлая расчёска"}]

    cursor = Cursor()
    visible = _public_audit_offer_visible_for_user(
        cursor,
        {"business_id": "11111111-1111-1111-1111-111111111111"},
        {"enabled": True, "status": "prepared", "company_name": "Шансик — сеть детских танцевальных студий"},
        {"user_id": "22222222-2222-2222-2222-222222222222"},
    )

    assert visible is False
    assert cursor.executed is True


def test_audit_offer_visible_for_logged_in_matching_business() -> None:
    class Cursor:
        def execute(self, *_args, **_kwargs) -> None:
            pass

        def fetchall(self):
            return [{"name": "Шансик — сеть детских танцевальных студий"}]

    visible = _public_audit_offer_visible_for_user(
        Cursor(),
        {"business_id": "11111111-1111-1111-1111-111111111111"},
        {"enabled": True, "status": "prepared", "company_name": "Шансик — сеть детских танцевальных студий"},
        {"user_id": "22222222-2222-2222-2222-222222222222"},
    )

    assert visible is True


def test_audit_offer_hidden_when_current_business_is_foreign_even_for_superadmin() -> None:
    class Cursor:
        def execute(self, *_args, **_kwargs) -> None:
            pass

        def fetchone(self):
            return {"name": "Весёлая расчёска", "owner_id": "22222222-2222-2222-2222-222222222222"}

    visible = _public_audit_offer_visible_for_user(
        Cursor(),
        {"business_id": "11111111-1111-1111-1111-111111111111"},
        {"enabled": True, "status": "prepared", "company_name": "Шансик — сеть детских танцевальных студий"},
        {"user_id": "22222222-2222-2222-2222-222222222222", "is_superadmin": True},
        current_business_id="33333333-3333-3333-3333-333333333333",
    )

    assert visible is False
