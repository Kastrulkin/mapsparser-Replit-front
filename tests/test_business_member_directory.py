from flask import Blueprint, Flask
import pytest
from api import business_member_directory_api
from services.business_member_directory import list_business_members


def test_directory_combines_access_without_duplicate_people():
    class Cursor:
        def execute(self, query, params):
            assert params == ('b', 'b', 'b', 'b')
            assert "nm.status = 'active'" in query
            assert "business_id = %s AND status = 'active'" in query

        def fetchall(self):
            return [
                ('owner', 'Owner', 'owner@example.ru', True, 'owner', 'business'),
                ('owner', 'Owner', 'owner@example.ru', True, 'owner', 'network'),
                ('staff', 'Anna', 'anna@example.ru', False, 'member', 'business'),
                ('staff', 'Anna', 'anna@example.ru', False, 'viewer', 'network'),
            ]

    members = list_business_members(Cursor(), 'b')
    assert len(members) == 2
    assert members[0]['access'] == [{'role': 'owner', 'scope': 'business'}, {'role': 'owner', 'scope': 'network'}]
    assert members[1]['is_active'] is False
    assert set(members[1]) == {'id', 'name', 'email', 'is_active', 'access'}


@pytest.mark.parametrize('authenticated,business_id,allowed,status', [
    (False, 'b', True, 401), (True, '', True, 400),
    (True, 'other', False, 403), (True, 'b', True, 200),
])
def test_directory_authorizes_before_reading(monkeypatch, authenticated, business_id, allowed, status):
    reads = []
    closed = []

    class Database:
        conn = None

        def __init__(self):
            self.conn = self

        def cursor(self):
            return object()

        def rollback_and_close(self):
            closed.append(True)

    monkeypatch.setattr(business_member_directory_api, 'DatabaseManager', Database)
    monkeypatch.setattr(business_member_directory_api, 'require_auth_from_request', lambda: {'user_id': 'u'} if authenticated else None)
    monkeypatch.setattr(business_member_directory_api, 'verify_business_access', lambda *args: (allowed, 'owner'))
    monkeypatch.setattr(business_member_directory_api, 'list_business_members', lambda cursor, target: reads.append(target) or [])
    app = Flask(__name__)
    bp = Blueprint('directory', __name__)
    business_member_directory_api.register_member_directory_routes(bp)
    app.register_blueprint(bp)
    response = app.test_client().get('/business-members', query_string={'business_id': business_id})
    assert response.status_code == status
    assert reads == (['b'] if status == 200 else [])
    assert len(closed) == (1 if authenticated and business_id else 0)
