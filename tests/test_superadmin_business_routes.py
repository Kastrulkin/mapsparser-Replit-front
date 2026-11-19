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
        "/api/superadmin/networks/<network_id>/members": {
            frozenset({"POST"}): "superadmin_business_api.add_network_member",
        },
        "/api/superadmin/businesses/<business_id>/members": {
            frozenset({"POST"}): "superadmin_business_api.add_business_member",
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


def test_create_business_validates_catalog_before_creating_owner(monkeypatch):
    from unittest.mock import Mock
    from flask import Flask
    from api import superadmin_business_api

    db = Mock()
    db.conn.cursor.return_value.fetchone.side_effect = [None, (1,)]
    db.get_user_by_email.return_value = {"id": "owner"}
    db.create_business.return_value = "new-business"
    monkeypatch.setattr(superadmin_business_api, "DatabaseManager", lambda: db)
    monkeypatch.setattr(superadmin_business_api, "_require_superadmin", lambda _: ({"user_id": "admin"}, None))
    app = Flask(__name__)
    app.register_blueprint(superadmin_business_api.superadmin_business_bp)
    client = app.test_client()
    payload = {"name": "Test cafe", "owner_email": "owner@example.test"}

    rejected = client.post("/api/superadmin/businesses", json={**payload, "business_type": "inactive"})
    assert rejected.status_code == 400
    db.get_user_by_email.assert_not_called()
    db.create_business.assert_not_called()

    created = client.post("/api/superadmin/businesses", json={**payload, "business_type": "cafe"})
    assert created.status_code == 200
    db.create_business.assert_called_once_with("Test cafe", "", "cafe", "owner", business_type="cafe")
