import sys


def test_finance_routes_stay_registered_after_blueprint_split():
    if "src" not in sys.path:
        sys.path.insert(0, "src")

    import main

    routes = {
        (str(rule), frozenset(rule.methods - {"HEAD", "OPTIONS"}), rule.endpoint)
        for rule in main.app.url_map.iter_rules()
        if str(rule).startswith("/api/finance")
    }

    expected = {
        ("/api/finance/dashboard", frozenset({"GET"}), "finance_api.get_finance_dashboard"),
        ("/api/finance/manual-entry", frozenset({"POST"}), "finance_api.add_finance_manual_entry"),
        ("/api/finance/import-preview", frozenset({"POST"}), "finance_api.preview_finance_import"),
        ("/api/finance/import-file", frozenset({"POST"}), "finance_api.import_finance_file"),
        ("/api/finance/crm/sync", frozenset({"POST"}), "finance_api.sync_finance_crm"),
        ("/api/finance/transaction", frozenset({"POST"}), "finance_api.add_transaction"),
        ("/api/finance/transactions", frozenset({"GET"}), "finance_api.get_transactions"),
        ("/api/finance/metrics", frozenset({"GET"}), "finance_api.get_financial_metrics"),
        ("/api/finance/breakdown", frozenset({"GET"}), "finance_api.get_financial_breakdown"),
        ("/api/finance/roi", frozenset({"GET"}), "finance_api.get_roi_data"),
        ("/api/finance/roi", frozenset({"POST"}), "finance_api.calculate_roi"),
    }

    assert expected.issubset(routes)
