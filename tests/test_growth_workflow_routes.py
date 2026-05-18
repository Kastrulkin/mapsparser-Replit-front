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
