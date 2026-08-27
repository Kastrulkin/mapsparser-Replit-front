from flask import Flask

from api import creator_promotion_api


def test_creator_automation_gate_requires_payment(monkeypatch):
    monkeypatch.setattr(creator_promotion_api, "creator_automation_allowed", lambda _cursor, _business_id: False)
    app = Flask(__name__)

    with app.test_request_context():
        response, status = creator_promotion_api._require_creator_automation(None, "business-1")

    assert status == 402
    assert response.get_json() == {
        "success": False,
        "error": "Подготовка персональных сообщений, подключение каналов и отправка доступны после оплаты.",
        "code": "payment_required",
        "access": {
            "status": "payment_required",
            "cta_label": "Выбрать тариф",
            "cta_target": {"screen": "settings", "focus": "subscription"},
        },
    }


def test_creator_automation_gate_allows_paid_business(monkeypatch):
    monkeypatch.setattr(creator_promotion_api, "creator_automation_allowed", lambda _cursor, _business_id: True)
    assert creator_promotion_api._require_creator_automation(None, "business-1") is None
