from typing import Any
import ast
import os
import uuid
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor
import pytest
from flask import Flask, request, jsonify
from tests.test_operator_voice_pg import pg
from tests.test_finance_daily_pg import daily
from services import business_input_settings, finance_daily
from database_manager import DatabaseManager


@pytest.fixture
def profile(daily, monkeypatch):
    conn, cursor = daily
    cursor.execute('ALTER TABLE businesses ADD COLUMN city TEXT, ADD COLUMN owner_id TEXT, ADD COLUMN business_type TEXT, ADD COLUMN address TEXT, ADD COLUMN working_hours TEXT, ADD COLUMN is_active BOOLEAN DEFAULT TRUE, ADD COLUMN geo_lat NUMERIC, ADD COLUMN geo_lon NUMERIC, ADD COLUMN site TEXT, ADD COLUMN website TEXT, ADD COLUMN updated_at TIMESTAMPTZ')
    cursor.execute("UPDATE businesses SET city='Таллин',owner_id='u'")
    cursor.execute('ALTER TABLE business_finance_settings ADD COLUMN city TEXT')
    cursor.execute('ALTER TABLE userservices ADD COLUMN description TEXT, ADD COLUMN category TEXT, ADD COLUMN price TEXT, ADD COLUMN created_at TIMESTAMPTZ')
    cursor.execute('CREATE TABLE businessmaplinks(id TEXT,user_id TEXT,business_id TEXT,url TEXT,map_type TEXT,created_at TIMESTAMPTZ)')
    cursor.execute('CREATE TABLE businessprofiles(business_id TEXT,contact_name TEXT,contact_phone TEXT,contact_email TEXT)')
    cursor.execute("INSERT INTO businessprofiles VALUES ('b','Owner','','')")
    cursor.execute('SELECT current_schema() schema');schema=cursor.fetchone()['schema'];conn.commit()
    def database():
        db=DatabaseManager.__new__(DatabaseManager)
        db.conn=psycopg2.connect(os.environ['OPERATOR_VOICE_TEST_DSN'],cursor_factory=RealDictCursor)
        db.conn.cursor().execute('SET search_path TO '+schema)
        db._closed=False
        return db
    app=Flask(__name__)
    namespace={'Any':Any,'app':app,'request':request,'jsonify':jsonify,'uuid':uuid,'DatabaseManager':database,
        'verify_session':lambda token:{'user_id':'u'},'verify_business_access':lambda c,b,u:(b=='b','u'),
        'get_business_owner_id':lambda c,b:'u','normalize_map_url':lambda url:url,'is_google_map_url':lambda url:False,
        'parse_ll_from_maps_url':lambda url:(None,None),'suggest_city_from_address':lambda address:None,
        '_looks_like_url':lambda value:'://' in value,'_row_to_dict':lambda c,r:dict(r) if r else {},
        '_business_display_fields':lambda row:(row.get('name'),row.get('business_type'),row.get('address'),row.get('working_hours'))}
    source=ast.parse(Path('src/legacy_routes/parsing_networks.py').read_text())
    function=next(node for node in source.body if isinstance(node,ast.FunctionDef) and node.name=='client_info')
    exec(compile(ast.Module(body=[function],type_ignores=[]),'client_info','exec'),namespace)
    return cursor,app.test_client(),namespace


def test_saved_profile_city_supplies_timezone_without_duplicate_city(profile):
    cursor,client,_=profile
    cursor.execute('DELETE FROM business_finance_settings')
    result=business_input_settings.resolve(cursor,'b')
    assert result['city']=='Таллин' and result['timezone']=='Europe/Tallinn'
    assert result['currency'] is None


def test_profile_currency_save_and_voice_share_city(profile):
    cursor,client,_=profile
    response=client.post('/api/client-info',headers={'Authorization':'Bearer test'},json={'businessId':'b','city':'Таллин','currency':'THB','mapLinks':[{'url':'https://maps.example/test'}]})
    assert response.status_code==200,response.json
    assert response.json['currency']=='THB'
    result=client.get('/api/client-info?business_id=b',headers={'Authorization':'Bearer test'})
    assert result.status_code==200,result.json
    assert result.json['city']=='Таллин' and result.json['currency']=='THB'
    prepared=finance_daily.prepare(cursor,'b','u',{'kind':'settings','city':'Пхукет','timezone':'Asia/Bangkok'},'telegram','m')
    finance_daily.apply(cursor,'b','u',prepared,'voice-city');cursor.connection.commit()
    result=client.get('/api/client-info?business_id=b',headers={'Authorization':'Bearer test'})
    assert result.json['city']=='Пхукет' and result.json['timezone']=='Asia/Bangkok'


def test_failed_profile_rolls_back_currency_and_links(profile):
    cursor,client,namespace=profile
    def fail(url):raise RuntimeError('map failure')
    namespace['normalize_map_url']=fail
    response=client.post('/api/client-info',headers={'Authorization':'Bearer test'},json={'businessId':'b','currency':'THB','mapLinks':[{'url':'https://maps.example/test'}]})
    assert response.status_code==500
    assert business_input_settings.resolve(cursor,'b')['currency']=='EUR'
    cursor.execute('SELECT count(*) n FROM finance_daily_events');assert cursor.fetchone()['n']==0


def test_foreign_profile_cannot_change_currency_or_links(profile):
    cursor,client,_=profile
    response=client.post('/api/client-info',headers={'Authorization':'Bearer test'},json={'businessId':'other','currency':'THB','mapLinks':[]})
    assert response.status_code==403


def test_profile_city_change_invalidates_old_timezone_binding(profile):
    cursor,_,_=profile
    cursor.execute("UPDATE business_finance_settings SET city='Таллин',timezone='Europe/Tallinn'")
    cursor.execute("UPDATE businesses SET city='Пхукет'")
    assert business_input_settings.resolve(cursor,'b')['timezone']=='Asia/Bangkok'
    cursor.execute("UPDATE businesses SET city='Неизвестный город'")
    assert business_input_settings.resolve(cursor,'b')['timezone'] is None
