from flask import Flask, jsonify

from api import partnership_leads_api


def test_blueprint_does_not_preempt_tenant_aware_superadmin_access(monkeypatch):
    monkeypatch.setattr(
        partnership_leads_api.service,
        "partnership_update_lead",
        lambda _lead_id: (jsonify({"success": True}), 200),
    )
    app = Flask(__name__)
    app.register_blueprint(partnership_leads_api.partnership_leads_bp)

    with app.test_client() as client:
        response = client.patch(
            "/api/partnership/leads/lead-1",
            json={"business_id": "business-1"},
        )

    assert response.status_code == 200
    assert response.get_json() == {"success": True}
