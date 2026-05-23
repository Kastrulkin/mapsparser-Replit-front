def test_auth_user_routes_are_owned_by_auth_user_blueprint():
    import main

    expected = {
        "/api/auth/me": "auth_user_api.get_user_info",
        "/api/auth/logout": "auth_user_api.logout",
        "/api/users/profile": "auth_user_api.update_user_profile",
    }

    actual = {rule.rule: rule.endpoint for rule in main.app.url_map.iter_rules()}
    for route, endpoint in expected.items():
        assert actual.get(route) == endpoint


def test_auth_user_routes_are_not_declared_in_main_py():
    from pathlib import Path

    main_text = Path("src/main.py").read_text(encoding="utf-8")
    forbidden_markers = (
        "@app.route('/api/auth/me'",
        '@app.route("/api/auth/me"',
        "@app.route('/api/auth/logout'",
        '@app.route("/api/auth/logout"',
        "@app.route('/api/users/profile'",
        '@app.route("/api/users/profile"',
    )
    for marker in forbidden_markers:
        assert marker not in main_text
