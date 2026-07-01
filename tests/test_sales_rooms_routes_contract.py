import sys

from flask import Flask


def test_public_sales_room_routes_stay_registered_after_blueprint_split():
    if "src" not in sys.path:
        sys.path.insert(0, "src")

    import main

    routes = {
        (str(rule), frozenset(rule.methods - {"HEAD", "OPTIONS"}), rule.endpoint)
        for rule in main.app.url_map.iter_rules()
    }

    expected = {
        ("/api/sales-rooms/public/<string:slug>", frozenset({"GET"}), "sales_rooms_api.public_sales_room"),
        (
            "/api/sales-rooms/public/<string:slug>/welcome",
            frozenset({"PATCH"}),
            "sales_rooms_api.public_sales_room_welcome",
        ),
        (
            "/api/sales-rooms/public/<string:slug>/proposal/suggestions",
            frozenset({"POST"}),
            "sales_rooms_api.public_sales_room_proposal_suggestion",
        ),
        (
            "/api/sales-rooms/public/<string:slug>/proposal/suggestions/<string:suggestion_id>/resolve",
            frozenset({"POST"}),
            "sales_rooms_api.public_sales_room_proposal_suggestion_resolve",
        ),
        (
            "/api/sales-rooms/public/<string:slug>/messages",
            frozenset({"POST"}),
            "sales_rooms_api.public_sales_room_message",
        ),
        (
            "/api/sales-rooms/public/<string:slug>/files",
            frozenset({"POST"}),
            "sales_rooms_api.public_sales_room_file_upload",
        ),
        (
            "/api/sales-rooms/public/<string:slug>/files/<string:file_id>",
            frozenset({"GET"}),
            "sales_rooms_api.public_sales_room_file",
        ),
        (
            "/api/sales-rooms/public/<string:slug>/events",
            frozenset({"POST"}),
            "sales_rooms_api.public_sales_room_event",
        ),
        (
            "/api/sales-rooms/public/<string:slug>/participants",
            frozenset({"POST"}),
            "sales_rooms_api.public_sales_room_participant_register",
        ),
        (
            "/api/sales-rooms/public/<string:slug>/participants/verify",
            frozenset({"POST"}),
            "sales_rooms_api.public_sales_room_participant_verify",
        ),
        (
            "/api/sales-rooms/public/<string:slug>/audit-offer/request",
            frozenset({"POST"}),
            "sales_rooms_api.public_sales_room_audit_offer_request",
        ),
        (
            "/api/sales-rooms/public/<string:slug>/audit-offer/status",
            frozenset({"GET"}),
            "sales_rooms_api.public_sales_room_audit_offer_status",
        ),
        (
            "/api/sales-rooms/public/<string:slug>/audit-offer/opened",
            frozenset({"POST"}),
            "sales_rooms_api.public_sales_room_audit_offer_opened",
        ),
    }

    assert expected.issubset(routes)


def test_public_sales_room_participant_registration_requires_personal_data_consent(monkeypatch):
    if "src" not in sys.path:
        sys.path.insert(0, "src")

    from src.api.sales_rooms_api import sales_rooms_bp

    app = Flask(__name__)
    app.register_blueprint(sales_rooms_bp)

    response = app.test_client().post(
        "/api/sales-rooms/public/demo/participants",
        json={"email": "lead@example.com"},
    )

    assert response.status_code == 400
    assert "согласие" in response.get_json()["error"].lower()
