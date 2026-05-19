def test_growth_workflow_routes_are_owned_by_growth_workflow_blueprint():
    import main

    expected = {
        "/api/progress": "growth_workflow_api.get_business_progress",
        "/api/business/<business_id>/optimization-wizard": "growth_workflow_api.business_optimization_wizard",
        "/api/business/<business_id>/sprint": "growth_workflow_api.business_sprint",
    }

    actual = {rule.rule: rule.endpoint for rule in main.app.url_map.iter_rules()}

    for route, endpoint in expected.items():
        assert actual.get(route) == endpoint


def test_growth_stage_routes_are_owned_by_existing_growth_blueprints():
    import main

    expected_first_match = {
        "/api/business/<string:business_id>/stages": "growth_api.get_business_stages",
        "/api/admin/growth-stages/<type_id>": "admin_growth_api.get_growth_stages",
        "/api/admin/growth-stages": "admin_growth_api.create_growth_stage",
    }

    route_methods = {}
    for rule in main.app.url_map.iter_rules():
        methods = frozenset(rule.methods - {"HEAD", "OPTIONS"})
        route_methods[(rule.rule, methods)] = rule.endpoint

    actual_first_match = {}
    for rule in main.app.url_map.iter_rules():
        actual_first_match.setdefault(rule.rule, rule.endpoint)

    for route, endpoint in expected_first_match.items():
        assert actual_first_match.get(route) == endpoint

    assert route_methods.get(("/api/admin/growth-stages/<stage_id>", frozenset({"PUT"}))) == "admin_growth_api.update_growth_stage"
    assert route_methods.get(("/api/admin/growth-stages/<stage_id>", frozenset({"DELETE"}))) == "admin_growth_api.delete_growth_stage"

    stale_main_endpoints = {
        "get_business_stages",
        "get_growth_stages",
        "create_growth_stage",
        "update_or_delete_growth_stage",
    }
    actual_endpoints = {rule.endpoint for rule in main.app.url_map.iter_rules()}

    assert not stale_main_endpoints.intersection(actual_endpoints)


def test_admin_business_type_routes_are_owned_by_admin_growth_blueprint():
    import main

    route_methods = {}
    for rule in main.app.url_map.iter_rules():
        methods = frozenset(rule.methods - {"HEAD", "OPTIONS"})
        route_methods[(rule.rule, methods)] = rule.endpoint

    expected_methods = {
        ("/api/admin/business-types", frozenset({"GET"})): "admin_growth_api.get_business_types",
        ("/api/admin/business-types", frozenset({"POST"})): "admin_growth_api.create_business_type",
        ("/api/admin/business-types/<type_id>", frozenset({"PUT"})): "admin_growth_api.update_business_type",
        ("/api/admin/business-types/<type_id>", frozenset({"DELETE"})): "admin_growth_api.delete_business_type",
    }

    for route_method, endpoint in expected_methods.items():
        assert route_methods.get(route_method) == endpoint

    stale_main_endpoints = {
        "get_business_types",
        "create_business_type",
        "update_or_delete_business_type",
    }
    actual_endpoints = {rule.endpoint for rule in main.app.url_map.iter_rules()}

    assert not stale_main_endpoints.intersection(actual_endpoints)


def test_public_business_type_route_is_owned_by_business_types_blueprint():
    import main

    actual = {rule.rule: rule.endpoint for rule in main.app.url_map.iter_rules()}

    assert actual.get("/api/business-types") == "business_types_api.get_business_types_public"
    assert "get_business_types_public" not in {rule.endpoint for rule in main.app.url_map.iter_rules()}
