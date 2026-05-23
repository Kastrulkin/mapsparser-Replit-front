def test_superadmin_business_routes_are_owned_by_superadmin_business_blueprint():
    import main

    expected = {
        "/api/superadmin/businesses": {
            frozenset({"GET"}): "superadmin_business_api.get_all_businesses",
            frozenset({"POST"}): "superadmin_business_api.create_business",
        },
        "/api/superadmin/businesses/<business_id>": {
            frozenset({"PUT"}): "superadmin_business_api.update_business",
            frozenset({"DELETE"}): "superadmin_business_api.delete_business",
        },
        "/api/superadmin/businesses/<business_id>/send-credentials": {
            frozenset({"POST"}): "superadmin_business_api.send_business_credentials",
        },
    }

    actual = {}
    for rule in main.app.url_map.iter_rules():
        methods = frozenset(rule.methods - {"HEAD", "OPTIONS"})
        actual.setdefault(rule.rule, {})[methods] = rule.endpoint

    for route, methods in expected.items():
        for method_set, endpoint in methods.items():
            assert actual.get(route, {}).get(method_set) == endpoint


def test_superadmin_business_routes_are_not_declared_in_main_py():
    from pathlib import Path

    main_text = Path("src/main.py").read_text(encoding="utf-8")
    forbidden_markers = (
        "@app.route('/api/superadmin/businesses'",
        '@app.route("/api/superadmin/businesses"',
        "@app.route('/api/superadmin/businesses/<business_id>'",
        '@app.route("/api/superadmin/businesses/<business_id>"',
        "@app.route('/api/superadmin/businesses/<business_id>/send-credentials'",
        '@app.route("/api/superadmin/businesses/<business_id>/send-credentials"',
    )
    for marker in forbidden_markers:
        assert marker not in main_text
