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
    _public_sales_room_rate_buckets,
    _public_audit_offer_visible_for_user,
    _serialize_public_audit_offer,
)


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
