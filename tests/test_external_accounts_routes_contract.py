import sys


def test_external_accounts_routes_stay_registered_after_blueprint_split():
    if "src" not in sys.path:
        sys.path.insert(0, "src")

    import main

    routes = {
        (str(rule), frozenset(rule.methods - {"HEAD", "OPTIONS"}), rule.endpoint)
        for rule in main.app.url_map.iter_rules()
    }

    expected = {
        (
            "/api/business/<business_id>/external-accounts",
            frozenset({"GET"}),
            "external_accounts_api.get_external_accounts",
        ),
        (
            "/api/business/<business_id>/external-accounts",
            frozenset({"POST"}),
            "external_accounts_api.upsert_external_account",
        ),
        (
            "/api/business/<business_id>/external-accounts/test",
            frozenset({"POST"}),
            "external_accounts_api.test_external_account_cookies",
        ),
        (
            "/api/business/<business_id>/external/reviews",
            frozenset({"GET"}),
            "external_accounts_api.get_external_reviews",
        ),
        (
            "/api/business/<business_id>/external/summary",
            frozenset({"GET"}),
            "external_accounts_api.get_external_summary",
        ),
        (
            "/api/business/<business_id>/external/posts",
            frozenset({"GET"}),
            "external_accounts_api.get_external_posts",
        ),
        (
            "/api/external-accounts/<account_id>",
            frozenset({"DELETE"}),
            "external_accounts_api.delete_external_account",
        ),
        (
            "/api/yclients/marketplace/status",
            frozenset({"GET"}),
            "external_accounts_api.yclients_marketplace_status",
        ),
        (
            "/api/yclients/marketplace/connect",
            frozenset({"POST"}),
            "external_accounts_api.yclients_marketplace_connect",
        ),
        (
            "/api/yclients/marketplace/import-services",
            frozenset({"POST"}),
            "external_accounts_api.yclients_marketplace_import_services",
        ),
        (
            "/api/business/<business_id>/vk/oauth/start",
            frozenset({"POST"}),
            "external_accounts_api.start_vk_oauth",
        ),
        (
            "/api/vk/oauth/callback",
            frozenset({"GET"}),
            "external_accounts_api.vk_oauth_callback",
        ),
        (
            "/api/business/<business_id>/vk/oauth/complete",
            frozenset({"POST"}),
            "external_accounts_api.complete_vk_oauth",
        ),
    }

    assert expected.issubset(routes)


def test_external_accounts_get_uses_current_app_debug_without_name_error(monkeypatch):
    if "src" not in sys.path:
        sys.path.insert(0, "src")

    from flask import Flask
    from api import external_accounts_api

    class FakeCursor:
        description = [
            ("id",),
            ("source",),
            ("external_id",),
            ("display_name",),
            ("is_active",),
            ("last_sync_at",),
            ("last_error",),
            ("created_at",),
            ("updated_at",),
        ]

        def execute(self, query, params=None):
            return None

        def fetchall(self):
            return [
                (
                    "acc-1",
                    "vk",
                    "group-1",
                    "VK group",
                    1,
                    None,
                    None,
                    "2026-06-23T10:00:00",
                    "2026-06-23T10:00:00",
                )
            ]

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

    class FakeDatabase:
        conn = FakeConnection()

        def close(self):
            return None

        def is_superadmin(self, user_id):
            return False

    monkeypatch.setattr(
        external_accounts_api,
        "verify_session",
        lambda token: {"user_id": "owner-1"},
    )
    monkeypatch.setattr(
        external_accounts_api,
        "get_business_owner_id",
        lambda cursor, business_id: "owner-1",
    )
    monkeypatch.setattr(
        external_accounts_api,
        "DatabaseManager",
        lambda: FakeDatabase(),
    )

    app = Flask(__name__)
    app.debug = True
    app.register_blueprint(external_accounts_api.external_accounts_bp)

    response = app.test_client().get(
        "/api/business/business-1/external-accounts",
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["accounts"][0]["source"] == "vk"
    assert payload["_debug"]["tableName"] == "externalbusinessaccounts"
