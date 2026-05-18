def test_report_routes_are_owned_by_reports_blueprint():
    import main

    expected = {
        "/api/download-report/<card_id>": "reports_api.download_report",
        "/api/view-report/<card_id>": "reports_api.view_report",
        "/api/reports/<card_id>/status": "reports_api.report_status",
    }

    actual = {rule.rule: rule.endpoint for rule in main.app.url_map.iter_rules()}

    for route, endpoint in expected.items():
        assert actual.get(route) == endpoint
