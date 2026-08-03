import inspect
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


def test_public_room_read_and_message_write_do_not_run_schema_ddl():
    if "src" not in sys.path:
        sys.path.insert(0, "src")

    from src.api import sales_rooms_api

    request_handlers = (
        sales_rooms_api.public_sales_room,
        sales_rooms_api.public_sales_room_message,
    )

    for handler in request_handlers:
        source = inspect.getsource(handler)
        assert "_ensure_sales_room_tables(" not in source, (
            f"{handler.__name__} must not run schema DDL inside a public request; "
            "sales-room schema is owned by Alembic migrations"
        )


def test_sales_room_schema_guard_is_read_only():
    if "src" not in sys.path:
        sys.path.insert(0, "src")

    from src.api.prospecting.access_schema import _ensure_sales_room_tables

    class RecordingCursor:
        def __init__(self):
            self.queries = []

        def execute(self, query):
            self.queries.append(str(query))

        def fetchone(self):
            return (
                "sales_rooms",
                "sales_room_events",
                "sales_room_messages",
                "sales_room_participants",
            )

    class RecordingConnection:
        def __init__(self):
            self.cursor_instance = RecordingCursor()

        def cursor(self):
            return self.cursor_instance

    connection = RecordingConnection()
    _ensure_sales_room_tables(connection)

    statements = "\n".join(connection.cursor_instance.queries).upper()
    assert "CREATE TABLE" not in statements
    assert "CREATE INDEX" not in statements
    assert "ALTER TABLE" not in statements
