import json
import pytest
from flask import Flask,Blueprint
from tests.test_operator_workday import workday
from tests.test_work_journal_pg import journal
from tests.test_finance_daily_pg import daily
from tests.test_operator_voice_pg import pg
from services import storage_oauth_settings,google_drive,yandex_disk
from api import operator_workday_api


@pytest.fixture
def settings(workday,monkeypatch):
    conn,c=workday
    c.execute('ALTER TABLE users ADD COLUMN IF NOT EXISTS is_superadmin BOOLEAN DEFAULT FALSE')
    c.execute("UPDATE users SET is_superadmin=TRUE WHERE id='u'")
    monkeypatch.setenv('EXTERNAL_AUTH_SECRET_KEY','unit-test-only')
    return conn,c


def test_encrypt_mask_reuse_conflict_rotation_and_runtime(settings):
    _,c=settings
    payload={'provider':'google','client_id':'test-client','client_secret':'private-test-secret','version':0}
    result=storage_oauth_settings.save(c,'u',payload)
    assert 'private-test-secret' not in json.dumps(result,default=str)
    assert result['items'][1]['secret_saved']
    assert google_drive.configuration(c)[:2]==('test-client','private-test-secret')
    c.execute('SELECT secret_encrypted FROM storage_oauth_apps');assert 'private-test-secret' not in c.fetchone()['secret_encrypted']
    with pytest.raises(ValueError,match='изменились'):storage_oauth_settings.save(c,'u',payload)
    payload.update(version=1,client_secret='');storage_oauth_settings.save(c,'u',payload)
    assert google_drive.configuration(c)[1]=='private-test-secret'
    payload.update(version=2,client_id='new-client')
    with pytest.raises(ValueError,match='нового Client ID'):storage_oauth_settings.save(c,'u',payload)
    payload.update(client_id='test-client',client_secret='rotated');storage_oauth_settings.save(c,'u',payload)
    assert google_drive.configuration(c)[1]=='rotated'
    storage_oauth_settings.save(c,'u',{'provider':'yandex','client_id':'yandex-client','client_secret':'yandex-secret','version':0})
    assert yandex_disk.configuration(c)[:2]==('yandex-client','yandex-secret')


def test_permissions_rechecked_and_change_client_with_connection_blocked(settings):
    _,c=settings
    payload={'provider':'google','client_id':'test-client','client_secret':'secret','version':0}
    with pytest.raises(PermissionError):storage_oauth_settings.save(c,'admin',payload)
    storage_oauth_settings.save(c,'u',payload)
    c.execute("INSERT INTO business_google_drive_connections(business_id,connected_by) VALUES ('b','u')")
    payload.update(version=1,client_id='new')
    with pytest.raises(ValueError,match='отключите'):storage_oauth_settings.save(c,'u',payload)
    c.execute("UPDATE users SET is_superadmin=FALSE WHERE id='u'")
    with pytest.raises(PermissionError):storage_oauth_settings.save(c,'u',payload)


def test_http_auth_no_secret_return_and_no_store(settings,monkeypatch):
    conn,c=settings
    class DB:
        def __init__(self):self.conn=conn
        def close(self):self.conn.rollback()
    monkeypatch.setattr(operator_workday_api,'DatabaseManager',DB)
    user={'id':'u'};monkeypatch.setattr(operator_workday_api,'require_auth_from_request',lambda:user)
    app=Flask(__name__);bp=Blueprint('storage_test',__name__);operator_workday_api.register_workday_routes(bp);app.register_blueprint(bp,url_prefix='/api/operator')
    client=app.test_client()
    response=client.post('/api/operator/storage-apps',json={'provider':'google','client_id':'test','client_secret':'private-value','version':0})
    assert response.status_code==200 and response.headers['Cache-Control']=='no-store'
    assert b'private-value' not in response.data
    response=client.get('/api/operator/storage-apps');assert response.status_code==200 and b'private-value' not in response.data
    user.update(session_kind='demo');assert client.get('/api/operator/storage-apps').status_code==403
    user.clear();user.update(id='admin');assert client.get('/api/operator/storage-apps').status_code==403
    user.clear();assert client.get('/api/operator/storage-apps').status_code==401
