import sys


def test_parsing_admin_routes_stay_registered_after_blueprint_split():
    if "src" not in sys.path:
        sys.path.insert(0, "src")

    import main

    routes = {
        (str(rule), frozenset(rule.methods - {"HEAD", "OPTIONS"}), rule.endpoint)
        for rule in main.app.url_map.iter_rules()
    }

    expected = {
        ("/api/admin/parsing/tasks", frozenset({"GET"}), "parsing_admin_api.get_parsing_tasks"),
        (
            "/api/admin/parsing/tasks/<task_id>/restart",
            frozenset({"POST"}),
            "parsing_admin_api.restart_parsing_task",
        ),
        (
            "/api/admin/parsing/tasks/<task_id>",
            frozenset({"DELETE"}),
            "parsing_admin_api.delete_parsing_task",
        ),
        (
            "/api/admin/parsing/tasks/<task_id>/switch-to-sync",
            frozenset({"POST"}),
            "parsing_admin_api.switch_task_to_sync",
        ),
        ("/api/admin/parsing/stats", frozenset({"GET"}), "parsing_admin_api.get_parsing_stats"),
        (
            "/api/admin/parsing/runtime-settings",
            frozenset({"GET"}),
            "parsing_admin_api.get_parsing_runtime_settings",
        ),
        (
            "/api/admin/parsing/runtime-settings",
            frozenset({"POST"}),
            "parsing_admin_api.update_parsing_runtime_settings",
        ),
    }

    assert expected.issubset(routes)
    assert (
        "/api/business/<string:business_id>/parse-status",
        frozenset({"GET"}),
        "get_parse_status",
    ) in routes
