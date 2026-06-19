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
    }

    assert expected.issubset(routes)
