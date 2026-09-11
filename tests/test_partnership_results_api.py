from flask import Flask
from api import partnership_leads_api


class Cursor:
    def execute(self, *args):
        pass
    def fetchall(self):
        return [{'id': 'b1', 'name': 'Точка'}]


class DB:
    def __init__(self):
        self.conn = self
    def cursor(self):
        return Cursor()
    def rollback(self):
        pass
    def commit(self):
        pass
    def close(self):
        pass


def setup(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(partnership_leads_api.partnership_leads_bp)
    monkeypatch.setattr(partnership_leads_api, '_require_auth', lambda: ({'user_id': 'owner'}, None))
    monkeypatch.setattr(partnership_leads_api, 'DatabaseManager', DB)
    monkeypatch.setattr(partnership_leads_api, 'resolve_control_scope', lambda *args, **kwargs: {'kind': 'network', 'business_ids': ['b1', 'b2']})
    monkeypatch.setattr(partnership_leads_api, 'verify_business_access', lambda *args: (True, 'owner'))
    monkeypatch.setattr(partnership_leads_api.service, '_partnership_write_access', lambda *args: None)
    return app.test_client()


def test_network_counts_companies_not_candidates_or_duplicate_locations(monkeypatch):
    browser = setup(monkeypatch)
    def results(cursor, ids):
        assert ids == ['b1', 'b2']  # supplied business_ids must never determine the scope
        return [{'id': 'w1', 'company_id': 'c1', 'agreement_json': {'status': 'confirmed', 'terms_version': 1}, 'partnership_launched_at': '2026-09-01'},
                {'id': 'w2', 'company_id': 'c1', 'agreement_json': {'status': 'confirmed', 'terms_version': 1}},
                {'id': 'candidate', 'company_id': 'c2', 'agreement_json': {}}]
    monkeypatch.setattr(partnership_leads_api, 'read_results', results)
    response = browser.get('/api/partnership/results?scope_type=network&scope_id=n1&business_ids=foreign')
    assert response.status_code == 200
    assert response.json['counts']['partners'] == 1
    assert response.json['counts']['launched'] == 1
    assert response.json['counts']['preparing'] == 1


def test_scope_and_object_tampering_are_denied(monkeypatch):
    browser = setup(monkeypatch)
    assert browser.get('/api/partnership/results?scope_type=platform&scope_id=p').status_code == 403
    assert browser.get('/api/partnership/results').status_code == 400
    monkeypatch.setattr(partnership_leads_api, 'resolve_control_scope', lambda *args, **kwargs: None)
    assert browser.get('/api/partnership/results?scope_type=business&scope_id=foreign').status_code == 403


def test_foreign_workstream_cannot_be_updated(monkeypatch):
    browser = setup(monkeypatch)
    def denied(*args):
        raise PermissionError()
    monkeypatch.setattr(partnership_leads_api, 'save_agreement', denied)
    assert browser.post('/api/partnership/results/foreign', json={'scope_id': 'b1', 'command': 'confirm', 'revision': 0}).status_code == 403
