from src.api.admin_prospecting import (
    SALES_ROOM_DATA_AUDITED,
    SALES_ROOM_DATA_TEMPLATE,
    SALES_ROOM_MODE_CLIENT,
    SALES_ROOM_MODE_PARTNER,
    _build_sales_room_invitation_text,
    _build_sales_room_payload,
    _build_sales_room_proposal,
)


def test_partner_sales_room_invitation_points_to_room() -> None:
    text = _build_sales_room_invitation_text(
        mode=SALES_ROOM_MODE_PARTNER,
        data_mode=SALES_ROOM_DATA_AUDITED,
        business_name="Органика",
        lead_name="Весёлая расчёска",
        room_url="https://localos.pro/room/demo",
    )

    assert "предложение по партнёрству" in text
    assert "https://localos.pro/room/demo" in text
    assert "аудит" in text


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
