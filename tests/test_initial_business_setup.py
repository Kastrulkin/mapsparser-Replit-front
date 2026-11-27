"""Setup chat, queue and durable results on an explicitly disposable PostgreSQL."""
import importlib
import json
import os
from types import SimpleNamespace

import psycopg2
import pytest
from flask import Flask, request
from psycopg2.extras import RealDictCursor

import database_manager
from api import initial_business_setup_api
from services import initial_business_setup as setup
from services import initial_setup_sources
from services.prospecting_service import ProspectingService
from services.operator_async_jobs import claim_next_operator_async_job, process_next_operator_async_job

SETUP = '/api/operator/initial-setup/'
HAMIK = 'pilot-hamik'
JINLIAN = 'pilot-jinlian'


@pytest.fixture()
def pilot(monkeypatch):
    dsn = os.getenv('INITIAL_SETUP_TEST_DSN')
    if not dsn:
        pytest.skip('Set INITIAL_SETUP_TEST_DSN to the disposable pilot cluster')
    if dsn != 'postgresql://pilot@127.0.0.1:55674/initial_setup_pilot':
        raise RuntimeError('This test only permits the explicitly owned pilot database')

    def connect():
        return psycopg2.connect(dsn, cursor_factory=RealDictCursor)

    monkeypatch.setenv('LOCALOS_INITIAL_SETUP_ENABLED', '1')
    monkeypatch.setenv('APIFY_TOKEN', '')
    from services import initial_setup_opportunities
    monkeypatch.setattr(initial_setup_opportunities, 'queue', lambda *args, **kwargs: None)
    monkeypatch.delenv('LOCALOS_INITIAL_SETUP_BUSINESS_IDS', raising=False)
    monkeypatch.delenv('LOCALOS_INITIAL_SETUP_LEAD_IDS', raising=False)
    monkeypatch.setattr(database_manager, 'get_db_connection', lambda: database_manager.DBConnectionWrapper(connect()))
    monkeypatch.setattr(initial_business_setup_api, 'require_auth_from_request', lambda: {
        'user_id': request.headers.get('X-Pilot-Actor', 'owner'),
        'session_kind': request.headers.get('X-Pilot-Session', 'standard'),
        'is_superadmin': request.headers.get('X-Pilot-Actor') == 'staff',
    })
    conn = connect()
    cursor = conn.cursor()
    cursor.execute('''
        DROP SCHEMA public CASCADE;
        CREATE SCHEMA public;
        CREATE TABLE users(id text PRIMARY KEY, email text, is_active boolean, is_superadmin boolean, password_hash text, created_at timestamptz DEFAULT now());
        ALTER TABLE users ADD COLUMN name text, ADD COLUMN phone text, ADD COLUMN updated_at timestamptz,
            ADD COLUMN is_verified boolean, ADD COLUMN verification_token text, ADD COLUMN personal_data_consent_at timestamptz,
            ADD COLUMN personal_data_consent_version text, ADD COLUMN privacy_accepted_at timestamptz,
            ADD COLUMN terms_accepted_at timestamptz, ADD COLUMN consent_ip text, ADD COLUMN consent_user_agent text;
        CREATE TABLE usersessions(id text, user_id text, token text, expires_at timestamptz, ip_address text,
            user_agent text, created_at timestamptz, session_kind text, scope_business_id text);
        CREATE TABLE businesses(id text PRIMARY KEY, owner_id text, name text, address text, city text, country text,
            business_type text, website text, site text, phone text, email text, is_active boolean DEFAULT true, network_id text,
            geo_lat real, geo_lon real, subscription_tier text, subscription_status text, subscription_ends_at timestamptz,
            entity_group text DEFAULT 'client', moderation_status text, updated_at timestamptz DEFAULT now());
        CREATE TABLE business_members(business_id text, user_id text, role text, status text);
        CREATE TABLE network_members(network_id text, user_id text, role text, status text);
        CREATE TABLE networks(id text, owner_id text);
        CREATE TABLE businessprofiles(business_id text PRIMARY KEY, contact_phone text, contact_email text, updated_at timestamptz);
        CREATE TABLE businessmaplinks(id text PRIMARY KEY, user_id text, business_id text, url text, map_type text,
            created_at timestamptz DEFAULT now());
        CREATE TABLE userservices(id text PRIMARY KEY, user_id text, business_id text, name text, description text,
            category text, optimized_name text, optimized_description text, keywords text, source text, is_active boolean,
            created_at timestamptz DEFAULT now(), updated_at timestamptz DEFAULT now());
        CREATE TABLE cards(id text PRIMARY KEY, business_id text, url text, title text, products text, rating real,
            reviews_count int, is_latest boolean, created_at timestamptz DEFAULT now(), updated_at timestamptz DEFAULT now());
        CREATE TABLE businesstypes(id text, type_key text, label text, description text);
        CREATE TABLE wordstatkeywords(id text PRIMARY KEY, keyword text UNIQUE, views integer,
            category text, updated_at timestamptz DEFAULT now());
        CREATE TABLE wordstatkeywordsexcluded(id text PRIMARY KEY, business_id text, keyword text);
        CREATE TABLE wordstatkeywordscustom(id text PRIMARY KEY, business_id text, keyword text, views integer,
            category text, updated_at timestamptz DEFAULT now(), created_at timestamptz DEFAULT now(), UNIQUE (business_id, keyword));
        CREATE TABLE seonegativekeywords(id text PRIMARY KEY, business_id text, phrase text, scope text,
            category text, is_active boolean, created_at timestamptz DEFAULT now());
        CREATE TABLE photo_assets (id text PRIMARY KEY, business_id text, source text, original_url text, storage_key text,
            versions_json jsonb, metadata_json jsonb, content_hash text, analysis_status text,
            category text, quality_score int, created_by text, last_used_at timestamptz,
            created_at timestamptz DEFAULT now(), updated_at timestamptz DEFAULT now());
        CREATE TABLE operatoractions(id text PRIMARY KEY);
        CREATE TABLE prospectingleads(id text PRIMARY KEY, business_id text, name text, address text, city text,
            country_code text, category text, phone text, email text, source_url text);
        CREATE TABLE business_company_links(business_id text, company_id uuid, company_location_id uuid,
            relation_role text, is_primary boolean);
        INSERT INTO users(id,email,is_active,is_superadmin,password_hash) VALUES ('owner','pilot-owner@example.com',true,false,'existing'),('other','pilot-other@example.com',true,false,'existing'),
            ('staff','pilot-staff@example.com',true,true,'existing');
        INSERT INTO businesses(id, owner_id, name, address, city, country, is_active) VALUES
            ('pilot-hamik','owner','Хамик','1-я улица Джрашена, 38/1','Ереван','AM',true),
            ('pilot-jinlian','owner','Jinlian Vegan Ice Cream','Fixture address','Bangkok','TH',true);
        INSERT INTO business_members VALUES ('pilot-jinlian','other','viewer','active');
        INSERT INTO userservices(id,user_id,business_id,name,description,category,is_active) VALUES
            ('s','owner','pilot-jinlian','Vegan ice cream','Wholesale orders','Wholesale',true),
            ('hidden','owner','pilot-hamik','Old menu','Archived','Old',false);
        INSERT INTO businessmaplinks(id,business_id,url,map_type) VALUES
            ('maps','pilot-jinlian','https://yandex.com/maps/org/jinlian/123456/','yandex');
        INSERT INTO cards(id,business_id,url,title,products,rating,reviews_count,is_latest) VALUES
            ('card','pilot-jinlian','https://yandex.com/maps/org/jinlian/123456','Jinlian fixture',
             '[{"name":"Coconut scoop","description":"Coconut dessert"}]',4.6,30,true);
    ''')
    for name in ('20260727_add_operator_async_jobs', '20260905_add_runtime_job_leases',
                 '20261012_business_knowledge', '20261105_prepared_cabinet', '20261122_initial_business_setup'):
        migration = importlib.import_module('alembic_migrations.versions.' + name)
        if name == '20260905_add_runtime_job_leases':
            cursor.execute('ALTER TABLE operator_async_jobs ADD COLUMN lease_token text')
        else:
            monkeypatch.setattr(migration.op, 'execute', cursor.execute)
            migration.upgrade()
    conn.commit()
    app = Flask(__name__)
    app.register_blueprint(initial_business_setup_api.initial_setup_bp)
    try:
        yield app.test_client(), conn
    finally:
        conn.close()


def action(client, business_id, name, state=None, **kwargs):
    data = {'action': name, **kwargs}
    if state:
        data['revision'] = state['revision']
    response = client.post(SETUP + business_id, json=data)
    assert response.status_code == 200, response.get_json()
    return response.get_json()['setup']


def process_next(conn):
    claimed = claim_next_operator_async_job(conn.cursor())
    assert claimed is not None
    conn.commit()
    return setup.process_source(claimed)


def test_hamik_verified_registration_resumes_without_a_listing(pilot, monkeypatch):
    client, conn = pilot
    cursor = conn.cursor()
    setup.init(cursor, HAMIK, 'registration')
    assert setup.verified_registration_business(cursor, 'owner') == HAMIK
    conn.commit()
    first = client.get(SETUP + HAMIK).get_json()['setup']
    assert first['profile']['address'] == '1-я улица Джрашена, 38/1'
    assert not first['started']
    assert not first['sources']
    state = action(client, HAMIK, 'start')
    monkeypatch.setattr(initial_setup_sources.map_card_initial_audit, 'initial_native_readers',
                        lambda **_: pytest.fail('A residential address must not launch a business card parser'))
    state = action(client, HAMIK, 'message', state, message='https://yandex.com/maps/house/example/123456')
    assert state['activity'][-1]['reply'] == 'Ссылки появились в списке источников.'
    assert process_next(conn)['state'] == 'link_only'
    row = setup.load(cursor, HAMIK, lock=True)
    row['data']['activity'][-1]['reply'] += ' Ход чтения виден рядом с чатом.'
    setup.persist(cursor, row)
    conn.commit()
    state = client.get(SETUP + HAMIK).get_json()['setup']
    assert state['sources'][0]['status'] == 'link_only'
    assert state['activity'][-1]['reply'] == 'Ссылки появились в списке источников.'
    state = action(client, HAMIK, 'message', state, message='Вид деятельности: Посуточная аренда квартиры')
    monkeypatch.setattr(setup, '_wordstat', lambda *_args: [])
    state = action(client, HAMIK, 'prepare', state)
    assert state['services'] == []
    assert state['category_keywords'] == [
        {'text': 'Посуточная аренда квартиры', 'source': 'Вид деятельности', 'views': None, 'dated': ''},
        {'text': 'Посуточная аренда квартиры Ереван', 'source': 'Тема с городом', 'views': None, 'dated': ''},
    ]
    state = action(client, HAMIK, 'save', state)
    assert state['saved']
    assert client.get(SETUP + HAMIK).get_json()['setup']['saved']
    cursor.execute('SELECT count(*) AS total FROM businessmaplinks WHERE business_id=%s', (HAMIK,))
    assert cursor.fetchone()['total'] == 0
    assert client.get(SETUP + HAMIK, headers={'X-Pilot-Actor': 'other'}).status_code == 403
    assert client.get(SETUP + HAMIK, headers={'X-Pilot-Session': 'demo'}).status_code == 401


def test_jinlian_preserves_sources_original_and_owner_scope(pilot, monkeypatch):
    client, conn = pilot
    state = action(client, JINLIAN, 'start')
    assert state['sources'][0]['status'] == 'queued'
    assert process_next(conn)['state'] == 'ready'
    state = client.get(SETUP + JINLIAN).get_json()['setup']
    assert state['sources'][0]['service_count'] == 1
    state = action(client, JINLIAN, 'message', state, message='Конкурент: https://yandex.com/maps/org/fixture/789012')
    monkeypatch.setattr(initial_setup_sources.map_card_initial_audit, 'initial_native_readers', lambda **_: {'yandex': lambda url: {
        'title': 'Fixture competitor', 'rating': 4.4, 'reviews_count': 12, 'products': [{'name': 'Soy scoop'}],
        'website': 'https://competitor.example/', 'telegram_url': 'https://t.me/competitor_news',
    }})
    assert process_next(conn)['state'] == 'ready'
    state = client.get(SETUP + JINLIAN).get_json()['setup']
    assert len(state['sources']) == 2
    assert state['comparisons'][0]['ours']['rating'].startswith('4.6')
    assert state['comparisons'][0]['their_services'] == ['Soy scoop']
    monkeypatch.setattr(setup, '_wordstat', lambda cursor, business, service, city, search: (
        [{'text': 'Vegan ice cream Bangkok', 'views': 140, 'source': 'Wordstat', 'dated': '2026-11-01'}]
        if service['name'] == 'Vegan ice cream' else []
    ))
    state = action(client, JINLIAN, 'prepare', state)
    original = next(item for item in state['services'] if item['original'] == 'Vegan ice cream')
    assert original['proposed'] == 'Vegan ice cream — Bangkok'
    assert original['service_id'] == 's'
    assert original['has_original'] is True
    assert original['keywords'][0]['views'] == 140
    assert len(state['services']) == 2
    assert client.post(SETUP + JINLIAN, headers={'X-Pilot-Actor': 'other'}, json={'action': 'service', 'key': original['key']}).status_code == 403
    assert client.post(SETUP + JINLIAN, json={'action': 'service', 'revision': state['revision'] - 1, 'key': original['key']}).status_code == 409
    state = action(client, JINLIAN, 'service', state, key=original['key'])
    assert not state['saved']
    state = action(client, JINLIAN, 'save', state)
    assert state['saved']
    cursor = conn.cursor()
    cursor.execute('SELECT count(*) AS total FROM businessmaplinks WHERE business_id=%s', (JINLIAN,))
    assert cursor.fetchone()['total'] == 1
    conn.commit()
    assert client.post(SETUP + JINLIAN + '/owner', json={'email': 'pilot-other@example.com', 'revision': state['revision']},
                       headers={'X-Pilot-Actor': 'staff'}).status_code == 409
    assert client.post(SETUP + JINLIAN + '/owner', json={'email': 'pilot-owner@example.com', 'revision': state['revision']},
                       headers={'X-Pilot-Actor': 'staff'}).get_json()['existing_account']
    site = 'https://example.com/'
    state = client.get(SETUP + JINLIAN).get_json()['setup']
    state = action(client, JINLIAN, 'message', state, message=site)
    monkeypatch.setattr(setup, 'read_website', lambda url: {
        'status': 'ready', 'facts': [initial_setup_sources.dated('Vegan ice cream wholesale in Bangkok', url)],
        'website_audit': {'status': 'ready', 'engine': 'SEOmator', 'pages': [{'url': url, 'findings': []}]},
    })
    assert process_next(conn)['state'] == 'ready'
    state = client.get(SETUP + JINLIAN).get_json()['setup']
    assert next(source for source in state['sources'] if source['kind'] == 'website')['website_audit']['engine'] == 'SEOmator'
    fact = state['facts'][0]
    state = action(client, JINLIAN, 'fact', state, key=fact['key'])
    from services import business_knowledge
    context = business_knowledge.context(cursor, JINLIAN, 'owner')
    assert 'Vegan ice cream wholesale in Bangkok' in context['text']
    assert context['sources'][0]['source'] == site
    cursor.execute('SELECT name,optimized_name,description FROM userservices WHERE id=%s', ('s',))
    assert dict(cursor.fetchone()) == {
        'name': 'Vegan ice cream', 'optimized_name': 'Vegan ice cream — Bangkok', 'description': 'Wholesale orders',
    }


def test_one_save_completes_a_legacy_draft_and_does_not_duplicate_data(pilot, monkeypatch):
    client, conn = pilot
    city = 'Bangkok'
    url = 'https://yandex.com/maps/org/jinlian/123456'
    site = 'https://shop.example/'
    shared_fact = 'Orders accepted in Bangkok'
    phone = '+66 1234 5678'
    monkeypatch.setattr(setup, '_wordstat', lambda *_args: [])
    cursor = conn.cursor()
    row = setup.init(cursor, JINLIAN, 'staff')
    map_key = setup.register_source(row, url)
    site_key = setup.register_source(row, site)
    row['data']['sources'][map_key].update(status='ready', catalog=[{
        'name': 'Coconut scoop', 'description': 'Coconut dessert', 'url': url,
    }], profile=[
        {'field': 'contact_phone', **initial_setup_sources.dated(phone, url)},
        {'field': 'address', **initial_setup_sources.dated('A conflicting address', url)},
        {'field': 'contact_email', **initial_setup_sources.dated('maps@example.com', url)},
    ], facts=[initial_setup_sources.dated(shared_fact, url)])
    row['data']['sources'][site_key].update(status='ready', profile=[
        {'field': 'contact_phone', **initial_setup_sources.dated('+6612345678', site)},
        {'field': 'contact_email', **initial_setup_sources.dated('site@example.com', site)},
    ], facts=[initial_setup_sources.dated(shared_fact, site)])
    row['data'].update(started=True, saved=True)
    setup.prepare_seo(cursor, row, setup.read_business(cursor, JINLIAN), live_wordstat=False)
    setup.persist(cursor, row)
    conn.commit()

    state = client.get(SETUP + JINLIAN).get_json()['setup']
    assert state['draft_ready'] and not state['saved']
    state = action(client, JINLIAN, 'save', state)
    assert state['saved'] and not state['seo_dirty']
    assert state['profile']['website'] == site
    assert state['profile']['address'] == 'Fixture address'
    assert state['profile']['contact_phone'] == phone
    assert not state['profile']['contact_email']
    assert all(service['accepted'] for service in state['services'])
    assert all(fact['accepted'] for fact in state['facts'])
    action(client, JINLIAN, 'save', state)
    cursor.execute('SELECT name,description,optimized_description FROM userservices WHERE business_id=%s ORDER BY name', (JINLIAN,))
    services = cursor.fetchall()
    assert [(item['name'], item['description']) for item in services] == [
        ('Coconut scoop', 'Coconut dessert'), ('Vegan ice cream', 'Wholesale orders'),
    ]
    assert all(city in item['optimized_description'] for item in services)
    cursor.execute("SELECT count(*) AS count FROM business_knowledge_records WHERE scope_id=%s AND kind='rule'", (JINLIAN,))
    assert cursor.fetchone()['count'] == 1
    cursor.execute('SELECT count(*) AS count FROM businessmaplinks WHERE business_id=%s', (JINLIAN,))
    assert cursor.fetchone()['count'] == 1


def test_prepare_searches_wordstat_for_each_service_and_saves_after_review(pilot, monkeypatch):
    from wordstat_client import WordstatClient
    from wordstat_config import config

    client, conn = pilot
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE userservices SET keywords='["ручная фраза"]' WHERE id='s';
        INSERT INTO wordstatkeywordscustom (id,business_id,keyword,views,category)
          VALUES ('current','pilot-jinlian','vegan ice cream Bangkok',140,'other'),
                 ('foreign','pilot-hamik','vegan ice cream',999,'other');
        INSERT INTO wordstatkeywordsexcluded VALUES ('exclude','pilot-jinlian','пошив мерча срочно');
        INSERT INTO seonegativekeywords(id,business_id,phrase,scope,category,is_active)
          VALUES ('minus','pilot-jinlian','бесплатно','global','',true);
    """)
    conn.commit()
    calls = []

    def get_queries(self, seeds, region):
        calls.append(seeds)
        assert seeds == ['пошив брендированного мерча']
        return [{'topRequests': [
            {'phrase': 'мерч на заказ', 'count': '518'},
            {'phrase': 'пошив мерча', 'count': '181'},
            {'phrase': 'пошив одежды', 'count': '9000'},
            {'phrase': 'пошив мерча срочно', 'count': '1000'},
            {'phrase': 'пошив мерча бесплатно', 'count': '1000'},
            {'phrase': 'пошив брендированного мерча', 'count': '0'},
        ]}]

    monkeypatch.setattr(config, 'is_configured', lambda: True)
    monkeypatch.setattr(WordstatClient, 'get_popular_queries', get_queries)
    state = action(client, JINLIAN, 'start')
    assert process_next(conn)['state'] == 'ready'
    state = client.get(SETUP + JINLIAN).get_json()['setup']
    state = action(client, JINLIAN, 'remove', state, key=state['sources'][0]['key'])
    state = action(client, JINLIAN, 'message', state, message='Услуга: Пошив брендированного мерча')
    state = action(client, JINLIAN, 'prepare', state)
    original = next(item for item in state['services'] if item['original'] == 'Vegan ice cream')
    new_service = next(item for item in state['services'] if item['original'] == 'Пошив брендированного мерча')
    assert calls == [['пошив брендированного мерча']]
    assert [(item['text'], item['views']) for item in original['keywords']] == [('vegan ice cream Bangkok', 140)]
    assert [(item['text'], item['views']) for item in new_service['keywords']] == [('мерч на заказ', 518), ('пошив мерча', 181)]
    cursor.execute('SELECT name,keywords FROM userservices WHERE business_id=%s', (JINLIAN,))
    assert cursor.fetchall() == [{'name': 'Vegan ice cream', 'keywords': '["ручная фраза"]'}]
    conn.commit()

    state = action(client, JINLIAN, 'service', state, key=new_service['key'])
    state = action(client, JINLIAN, 'service', state, key=original['key'])
    action(client, JINLIAN, 'service', state, key=original['key'])
    cursor.execute('SELECT name,keywords FROM userservices WHERE business_id=%s', (JINLIAN,))
    assert {row['name']: json.loads(row['keywords']) for row in cursor.fetchall()} == {
        'Vegan ice cream': ['ручная фраза', 'vegan ice cream Bangkok'],
        'Пошив брендированного мерча': ['мерч на заказ', 'пошив мерча'],
    }


def test_prepare_finds_low_frequency_stored_queries_outside_the_global_top(pilot, monkeypatch):
    client, conn = pilot
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO wordstatkeywords(id,keyword,views,category)
        SELECT 'generic-' || n, 'популярный запрос ' || n, 10000, 'other'
        FROM generate_series(1,5001) n;
        INSERT INTO wordstatkeywords(id,keyword,views,category)
        VALUES ('relevant','пошив мерча',41,'other');
    """)
    conn.commit()
    monkeypatch.setattr(setup._SetupWordstatSearch, 'lookup', lambda *_: pytest.fail('Stored evidence should suffice'))

    state = action(client, HAMIK, 'start')
    state = action(client, HAMIK, 'message', state, message='Услуга: Пошив брендированного мерча')
    state = action(client, HAMIK, 'prepare', state)
    assert [(item['text'], item['views']) for item in state['services'][0]['keywords']] == [('пошив мерча', 41)]


def test_prepare_keeps_unmeasured_topics_when_wordstat_is_unavailable(pilot, monkeypatch):
    from wordstat_client import WordstatClient, WordstatTemporaryUnavailable
    from wordstat_config import config

    client, conn = pilot
    calls = []

    def unavailable(self, seeds, region):
        calls.append(seeds)
        raise WordstatTemporaryUnavailable('quota')

    monkeypatch.setattr(config, 'is_configured', lambda: True)
    monkeypatch.setattr(WordstatClient, 'get_popular_queries', unavailable)
    state = action(client, HAMIK, 'start')
    state = action(client, HAMIK, 'message', state, message='Услуга: Пошив мерча')
    state = action(client, HAMIK, 'message', state, message='Услуга: Ремонт обуви')
    state = action(client, HAMIK, 'prepare', state)
    assert calls == [['пошив мерча']]
    assert state['seo_prepared']
    assert len(state['services']) == 2
    assert all(item['views'] is None for service in state['services'] for item in service['keywords'])
    action(client, HAMIK, 'service', state, key=state['services'][0]['key'])
    cursor = conn.cursor()
    cursor.execute("SELECT keywords FROM userservices WHERE business_id=%s AND is_active", (HAMIK,))
    assert [json.loads(item['keywords']) for item in cursor.fetchall()] == [[]]


def test_seo_reviews_large_existing_catalog_without_changing_services(pilot, monkeypatch):
    client, conn = pilot
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO userservices (id,user_id,business_id,name,description,optimized_name,is_active)
        SELECT 'service-' || n,'owner',%s,'Service ' || n,'Original ' || n,'Existing SEO ' || n,true
        FROM generate_series(1,86) n
    """, (HAMIK,))
    conn.commit()
    state = action(client, HAMIK, 'start')
    monkeypatch.setattr(setup, '_wordstat', lambda *_args: [])
    state = action(client, HAMIK, 'prepare', state)
    assert len(state['services']) == 86
    assert all(item['proposed'].startswith('Existing SEO ') for item in state['services'])
    assert all(not item['accepted'] for item in state['services'])
    cursor.execute("SELECT count(*) AS total FROM userservices WHERE business_id=%s AND optimized_name LIKE 'Existing SEO %%'", (HAMIK,))
    assert cursor.fetchone()['total'] == 86


def test_source_validation_and_website_social_discovery(monkeypatch):
    from services import contact_intelligence_service
    from services import website_seo_audit

    with pytest.raises(ValueError):
        initial_setup_sources.source_url('http://127.0.0.1/private')
    with pytest.raises(ValueError):
        initial_setup_sources.source_url('https://t.me/+private')

    def read(url, observe_page):
        observe_page('https://another.example.com/', '<title>Another company</title>')
        observe_page(url, '''
            <meta name="description" content="Family-run vegan kitchen">
            <script type="application/ld+json">{"@type":"Product","name":"Mango scoop"}</script>
            <a href="https://t.me/fixture_channel">Official Telegram</a>
            <a href="https://www.instagram.com/fixture/">Official Instagram</a>
        ''')
        observe_page('https://example.com/contact', '<title>Contact the platform</title>')
        return [], {}, {}

    def audit(pages):
        return {'status': 'ready', 'pages': [{'url': page['url'], 'findings': []} for page in pages]}

    monkeypatch.setattr(contact_intelligence_service, 'collect_public_website_intelligence', read)
    monkeypatch.setattr(website_seo_audit, 'audit_pages', audit)
    result = initial_setup_sources.read_website('https://example.com/')
    assert {link['provider'] for link in result['links']} == {'telegram', 'instagram'}
    assert result['catalog'][0]['name'] == 'Mango scoop'
    assert result['facts'][0]['url'] == 'https://example.com/'
    assert [page['url'] for page in result['website_audit']['pages']] == [
        'https://example.com/', 'https://example.com/contact',
    ]
    listing = initial_setup_sources.read_website('https://example.com/business/123')
    assert [page['url'] for page in listing['website_audit']['pages']] == ['https://example.com/business/123']


def test_website_audit_refresh_is_separate_from_saved_catalog_and_uses_same_permissions(pilot, monkeypatch):
    client, conn = pilot
    site = 'https://example.com/'
    refreshed = {'status': 'ready', 'engine': 'SEOmator', 'pages': [{'url': site, 'findings': []}]}
    cursor = conn.cursor()
    cursor.execute('UPDATE businesses SET website=%s WHERE id=%s', (site, HAMIK))
    conn.commit()
    state = action(client, HAMIK, 'start')
    # Worker output from an earlier release before site auditing was available.
    monkeypatch.setattr(setup, 'read_website', lambda url: {'status': 'ready', 'facts': [
        initial_setup_sources.dated('A verified business fact', url),
    ]})
    assert process_next(conn)['state'] == 'ready'
    state = client.get(SETUP + HAMIK).get_json()['setup']
    key = state['sources'][0]['key']
    row = setup.load(cursor, HAMIK, lock=True)
    photo_report = {'status': 'ready', 'shortlist': [{'key': 'fixture-photo'}]}
    row['data'].update(photo_report=photo_report, photo_report_scope=setup._photo_scope(row))
    setup.persist(cursor, row)
    conn.commit()
    state = client.get(SETUP + HAMIK).get_json()['setup']
    assert state['photo_report'] == photo_report
    assert 'website_audit' not in state['sources'][0]
    state = action(client, HAMIK, 'prepare', state)
    state = action(client, HAMIK, 'save', state)
    assert state['saved'] and not state['seo_dirty']
    facts = state['facts']
    assert all(fact['accepted'] for fact in facts)
    refused = client.post(SETUP + HAMIK, json={'action': 'website_audit', 'key': key, 'revision': state['revision']},
                          headers={'X-Pilot-Actor': 'other'})
    assert refused.status_code == 403
    state = action(client, HAMIK, 'website_audit', state, key=key)
    assert state['sources'][0]['status'] == 'ready'
    assert state['sources'][0]['website_audit'] == {'status': 'queued'}
    state = action(client, HAMIK, 'website_audit', state, key=key)
    cursor.execute("SELECT count(*) AS total FROM operator_async_jobs WHERE status='queued'")
    assert cursor.fetchone()['total'] == 1
    conn.commit()
    monkeypatch.setattr(setup, 'read_website', lambda url: {'status': 'ready', 'website_audit': refreshed})
    assert process_next(conn)['state'] == 'ready'
    state = client.get(SETUP + HAMIK).get_json()['setup']
    assert state['sources'][0]['website_audit'] == refreshed
    assert 'website_audit_job' not in state['sources'][0]
    assert state['facts'] == facts
    assert state['photo_report'] == photo_report
    assert state['saved'] and not state['seo_dirty']
    state = action(client, HAMIK, 'website_audit', state, key=key)
    monkeypatch.setattr(setup, 'read_website', lambda url: {'status': 'unavailable', 'note': 'Сайт недоступен.'})
    assert process_next(conn)['state'] == 'unavailable'
    state = client.get(SETUP + HAMIK).get_json()['setup']
    assert state['sources'][0]['website_audit']['status'] == 'unavailable'
    assert state['sources'][0]['status'] == 'ready'
    assert state['facts'] == facts and state['saved'] and not state['seo_dirty']


@pytest.mark.parametrize('recipient_id', ['owner', 'staff'])
def test_staff_lead_draft_is_idempotent_and_handoff_requires_review(pilot, monkeypatch, recipient_id):
    client, conn = pilot
    from services import company_registry_service

    cursor = conn.cursor()
    cursor.execute("""INSERT INTO prospectingleads(id,name,address,city,country_code,category,phone,email)
        VALUES ('new-lead','Sample apartment','Street 8','Yerevan','AM','Apartment rental','+37491123456','business@example.com')""")
    conn.commit()
    identity = {'company_id': '918956c9-9f4f-4bfd-84eb-200ac553ed4d', 'company_location_id': '50bc7bd0-3585-4c05-94fb-57c96d970816'}
    monkeypatch.setattr(company_registry_service, 'ensure_company_for_lead', lambda *_args, **_kwargs: identity)
    staff = {'X-Pilot-Actor': 'staff'}
    response = client.post(SETUP + 'lead/new-lead', json={}, headers=staff)
    assert response.status_code == 201, response.get_json()
    business = response.get_json()['business_id']
    assert client.post(SETUP + 'lead/new-lead', json={}, headers=staff).get_json()['business_id'] == business
    assert client.get(SETUP + business).status_code == 403
    state = client.get(SETUP + business, headers=staff).get_json()['setup']
    assert state['provisional'] and state['viewer_is_owner']
    assert state['profile']['contact_email'] == ''
    assert any(choice['text'] == 'business@example.com' for choice in state['profile_choices'])
    owner_url = SETUP + business + '/owner'
    assert client.post(owner_url, json={'email': 'pilot-owner@example.com', 'revision': state['revision']}, headers=staff).status_code == 409
    state = client.post(SETUP + business, json={'action': 'start'}, headers=staff).get_json()['setup']
    monkeypatch.setattr(setup, '_wordstat', lambda *_args: [])
    for name in ('prepare', 'save'):
        change = client.post(SETUP + business, json={'action': name, 'revision': state['revision']}, headers=staff)
        assert change.status_code == 200, change.get_json()
        state = change.get_json()['setup']
    owner = client.post(owner_url, json={'email': f'pilot-{recipient_id}@example.com', 'revision': state['revision']}, headers=staff)
    assert owner.status_code == 200, owner.get_json()
    access = owner.get_json()
    assert access['existing_account']
    assert access['already_signed_in'] is (recipient_id == 'staff')
    assert access['login_path'] == f'/dashboard/operator?business_id={business}&setup=1'
    assert 'invite_url' not in access
    confirmed = client.get(SETUP + business, headers={'X-Pilot-Actor': recipient_id}).get_json()['setup']
    assert confirmed['viewer_is_owner'] and not confirmed['provisional']
    assert client.get(SETUP + business, headers=staff).get_json()['setup']['viewer_is_owner'] is (recipient_id == 'staff')
    cursor.execute('SELECT relation_role FROM business_company_links WHERE business_id=%s', (business,))
    assert cursor.fetchone()['relation_role'] == 'owner'


def test_signed_in_owner_without_password_does_not_get_an_invitation(pilot):
    client, conn = pilot
    cursor = conn.cursor()
    cursor.execute("UPDATE businesses SET owner_id='staff' WHERE id=%s", (HAMIK,))
    cursor.execute("UPDATE users SET password_hash=NULL WHERE id='staff'")
    row = setup.init(cursor, HAMIK, 'staff')
    row['data'].update(started=True, seo_prepared=True, saved=True)
    setup.persist(cursor, row)
    conn.commit()

    path = SETUP + HAMIK
    staff = {'X-Pilot-Actor': 'staff'}
    state = client.get(path, headers=staff).get_json()['setup']
    assert state['viewer_is_owner'] and state['saved']
    response = client.post(path + '/owner', headers=staff, json={
        'email': 'pilot-staff@example.com', 'revision': state['revision'],
    })
    assert response.status_code == 200, response.get_json()
    assert response.get_json()['already_signed_in']
    assert 'invite_url' not in response.get_json()
    assert client.get(path, headers=staff).get_json()['setup']['revision'] == state['revision']
    cursor.execute('SELECT 1 FROM prepared_cabinets WHERE business_id=%s', (HAMIK,))
    assert cursor.fetchone() is None


def test_saved_setup_progress_and_monthly_content_use_the_existing_queue(pilot, monkeypatch):
    from datetime import date, datetime, timedelta, timezone
    from services import business_knowledge, content_plan_service, setup_content_journey as journey
    from core.content_plan_generator import build_content_plan_skeleton

    client, conn = pilot
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE agent_blueprints(id text PRIMARY KEY, business_id text, name text, category text,
            description text, status text, created_by_user_id text, metadata_json jsonb, created_at timestamptz DEFAULT now(),
            updated_at timestamptz DEFAULT now());
        CREATE TABLE agent_blueprint_versions(id text PRIMARY KEY, blueprint_id text, version_number integer,
            goal text, inputs_schema_json jsonb, steps_json jsonb, persona_agent_id text, capability_allowlist_json jsonb,
            approval_policy_json jsonb, output_schema_json jsonb, execution_mode text, trigger text, schedule_json jsonb,
            runtime_config_json jsonb, limits_json jsonb, required_integration_bindings_json jsonb,
            compiled_artifact_json jsonb, compiled_artifact_hash text, compiled_state text, created_by_user_id text);
        CREATE TABLE contentplans(id text PRIMARY KEY, business_id text, title text, plan_status text,
            scope_type text, period_start date, period_end date, generated_plan_json jsonb, created_at timestamptz DEFAULT now());
        CREATE TABLE contentplanitems(id text PRIMARY KEY, business_id text, plan_id text, theme text, goal text,
            scheduled_for date, draft_text text, status text, updated_at timestamptz DEFAULT NOW());
        CREATE TABLE social_posts(business_id text, content_plan_item_id text, status text, base_text text, platform_text text);
        CREATE TABLE externalbusinessaccounts(business_id text, source text, external_id text, is_active boolean, last_error text);
    """)
    row = setup.init(cursor, HAMIK, 'registration')
    row['data'].update(started=True, seo_prepared=True, saved=True)
    setup.persist(cursor, row)
    business_knowledge.mutate(cursor, 'business', HAMIK, {'user_id': 'owner'}, {
        'operation': 'rule', 'request_id': 'initial-setup-fact:qa',
        'payload': {'label': 'Факт из первичной настройки', 'text': 'У апартаментов есть отдельный вход.',
                    'source': 'https://example.com/'},
    })
    business_knowledge.mutate(cursor, 'business', HAMIK, {'user_id': 'owner'}, {
        'operation': 'rule', 'request_id': 'publishing-rule:qa',
        'payload': {'label': 'Правило редакции', 'text': 'Не обещать раннее заселение.'},
    })
    business_knowledge.mutate(cursor, 'business', HAMIK, {'user_id': 'owner'}, {
        'operation': 'rule', 'request_id': 'private-fact:qa', 'audience': 'management',
        'payload': {'label': 'Факт для руководства', 'text': 'Сведения только для руководства.'},
    })
    conn.commit()
    monkeypatch.setattr(journey, 'resolve', lambda *_: {'timezone': 'Asia/Yerevan'})
    monkeypatch.setattr(journey, 'get_subscription_access', lambda _: {'capabilities': ['maps.news', 'automation']})

    def build(user_id, business_id, **values):
        assert business_id == HAMIK and user_id == 'owner'
        assert values['needs_setup_review'] and values['operator_request_id']
        facts = business_knowledge.planning_facts(cursor, business_id, user_id)
        assert len(facts) == 1
        start = values.get('period_start') or date.today() - timedelta(days=24)
        skeleton = build_content_plan_skeleton({'business_facts': facts}, period_days=30, density='standard',
                                               period_start=start)
        topic = next(item for item in skeleton['items'] if item['source_kind'] == 'business_fact')
        assert topic['theme'] == 'У апартаментов есть отдельный вход'
        plan_id = values['operator_request_id']
        cursor.execute("""INSERT INTO contentplans VALUES (%s,%s,'Темы на утверждение','generated',
            'single_business',%s,%s,'{}',NOW())""", (plan_id, business_id, start, start + timedelta(days=29)))
        cursor.execute("""INSERT INTO contentplanitems VALUES (%s,%s,%s,%s,'Показать вход гостям',%s,NULL,'planned')""",
                       (plan_id, business_id, plan_id, topic['theme'], start))
        conn.commit()
        return {'id': plan_id}

    monkeypatch.setattr(content_plan_service, 'create_generated_content_plan', build)
    endpoint = SETUP + HAMIK + '/next-steps'

    def read():
        response = client.get(endpoint)
        assert response.status_code == 200, response.get_json()
        return response.get_json()

    def post(action, **values):
        response = client.post(endpoint, json={'action': action, **values})
        assert response.status_code == 200, response.get_json()
        return response.get_json()

    assert read()['fact_count'] == 1 and read()['step'] == 'facts'
    assert client.post(endpoint, json={'action':'generate'}).status_code == 409
    assert post('confirm_facts', version=read()['facts_version'])['step'] == 'plan'
    assert post('generate')['step'] == 'generating'
    assert post('generate')['job']['id'] == read()['job']['id']
    assert process_next_operator_async_job()['status'] == 'waiting_for_review'
    prepared = read()
    assert prepared['step'] == 'photos'
    cursor.execute("INSERT INTO photo_assets(id,business_id,analysis_status) VALUES ('analyzed',%s,'analyzed')", (HAMIK,))
    conn.commit()
    ready = read()['plan']
    assert read()['step'] == 'review' and 'У апартаментов есть отдельный вход' in ready['topics']
    assert client.post(endpoint, json={'action': 'approve', 'plan_id': ready['id'], 'version': 'old'}).status_code == 409
    assert post('approve', plan_id=ready['id'], version=ready['version'])['step'] == 'texts'
    cursor.execute("UPDATE contentplanitems SET draft_text='Проверьте наш отдельный вход' WHERE plan_id=%s", (ready['id'],))
    cursor.execute("INSERT INTO social_posts VALUES (%s,%s,'approved','Готово',NULL)", (HAMIK, ready['id']))
    cursor.execute("INSERT INTO externalbusinessaccounts VALUES (%s,'vk_group','group-qa',TRUE,NULL)", (HAMIK,))
    conn.commit()
    assert read()['step'] == 'monthly'
    settings = post('enable_monthly')['monthly']
    assert settings['active']
    assert post('enable_monthly')['monthly']['id'] == settings['id']
    blueprint = {'id': settings['id'], 'business_id': HAMIK}
    from services.agent_trigger_runtime import dispatch_due_scheduled_agent_blueprints

    due = datetime.now(timezone.utc) + timedelta(days=30)
    assert journey.scheduled_dispatch(cursor, blueprint, due) is None
    cursor.execute("UPDATE social_posts SET status='published' WHERE content_plan_item_id=%s", (ready['id'],))
    conn.commit()
    dispatched = dispatch_due_scheduled_agent_blueprints(cursor, now=due)
    assert dispatched['dispatched_count'] == 1 and dispatched['dispatched'][0]['blueprint_id'] == settings['id']
    assert journey.scheduled_dispatch(cursor, blueprint, due + timedelta(days=1)) is None
    conn.commit()
    assert process_next_operator_async_job()['status'] == 'waiting_for_review'
    assert read()['step'] == 'review'
    assert read()['plan']['id'] != ready['id']
    assert not post('pause_monthly')['monthly']['active']
    assert journey.scheduled_dispatch(cursor, blueprint, due + timedelta(days=31)) is None


def test_blocked_map_leaves_draft_incomplete_and_retry_collects_catalog_and_gallery(pilot, monkeypatch):
    client, _conn = pilot
    url = 'https://yandex.com/maps/org/clinic/123456'
    photo = 'https://avatars.mds.yandex.net/get-altay/12345/a-b/XXXL'
    responses = iter([
        {'error': 'yandex_rate_limited'},
        {'name': 'Clinic', 'products': [{'name': 'Laser consultation'}], 'photos': [photo]},
    ])

    def readers(*, content_only):
        assert content_only
        return {'yandex': lambda value: next(responses)}

    monkeypatch.setattr(initial_setup_sources.map_card_initial_audit, 'initial_native_readers', readers)
    state = action(client, HAMIK, 'start', message=url, auto=True)
    assert state['sources'][0]['status'] == 'queued'
    assert process_next_operator_async_job()['status'] == 'failed'
    assert process_next_operator_async_job()['result']['state'] == 'needs_source'
    assert process_next_operator_async_job() is None
    state = client.get(SETUP + HAMIK).get_json()['setup']
    assert state['draft_status'] == 'needs_source'
    assert not state['draft_ready'] and not state['report_ready']
    assert 'временно ограничил' in state['sources'][0]['note']
    assert client.get(SETUP + HAMIK + '/report').status_code == 409

    state = action(client, HAMIK, 'retry', state, key=state['sources'][0]['key'])
    assert state['draft_status'] == 'queued'
    for _ in range(3):
        assert process_next_operator_async_job()['status'] == 'completed'
    state = client.get(SETUP + HAMIK).get_json()['setup']
    assert state['report_ready']
    assert state['sources'][0]['photo_candidate_count'] == 1
    assert state['services'][0]['original'] == 'Laser consultation'
    assert state['photo_report']['review'][0]['image_url'] == photo


def test_placeholder_map_title_does_not_confirm_a_card():
    source = {'provider': 'yandex', 'url': 'https://yandex.com/maps/org/clinic/123456'}
    result = initial_setup_sources.read_map(source, {'name': 'Untitled'})
    assert result['status'] == 'unavailable'


def test_first_map_link_checks_website_and_socials_before_marking_draft_ready(pilot, monkeypatch):
    from services import contact_intelligence_service

    client, _ = pilot
    site = 'https://clinic.example/'
    url = 'https://yandex.ru/maps/org/clinic/123456'
    telegram = 'https://t.me/clinic_news'
    vk = 'https://vk.com/clinic'
    checked_pages = []

    monkeypatch.setattr(initial_setup_sources.map_card_initial_audit, 'initial_native_readers', lambda **_: {
        'yandex': lambda _: {
            'name': 'Clinic', 'website': 'clinic.example/?utm_source=yandex',
            'products': [{'name': 'Consultation'}], 'messenger_links': [{'url': telegram}],
        },
    })
    def collect_website(observed_url, *, observe_page):
        assert observed_url == site
        observe_page(site, f'<a href="{telegram}">Telegram</a><a href="{vk}">VK</a>')
        return [], {}, {}

    def audit_pages(pages):
        checked_pages.extend(page['url'] for page in pages)
        return {'status': 'ready', 'pages': [{'url': site, 'findings': []}]}

    monkeypatch.setattr(contact_intelligence_service, 'collect_public_website_intelligence', collect_website)
    monkeypatch.setattr(initial_setup_sources.website_seo_audit, 'audit_pages', audit_pages)
    monkeypatch.setattr(setup, 'read_social', lambda provider, url: {
        'status': 'ready' if provider == 'telegram' else 'link_only',
    })
    action(client, HAMIK, 'start', message=url, auto=True)
    assert process_next_operator_async_job()['result']['state'] == 'ready'
    state = client.get(SETUP + HAMIK).get_json()['setup']
    assert {(item['kind'], item['status']) for item in state['sources']} == {
        ('map', 'ready'), ('website', 'queued'), ('social', 'queued'),
    }
    assert not state['report_ready']
    for _ in range(3):
        job = process_next_operator_async_job()
        assert job['kind'] == setup.JOB_KIND and job['status'] == 'completed'
        assert not client.get(SETUP + HAMIK).get_json()['setup']['report_ready']
    assert checked_pages == [site]
    for _ in range(2):
        assert process_next_operator_async_job()['status'] == 'completed'
    state = client.get(SETUP + HAMIK).get_json()['setup']
    sources = {item['url']: item for item in state['sources']}
    assert len(sources) == len(state['sources']) == 4
    assert sources[site]['found_on'] == url
    assert sources[site]['website_audit']['status'] == 'ready'
    assert sources[telegram]['status'] == 'ready'
    assert sources[vk]['found_on'] == site and sources[vk]['status'] == 'link_only'
    assert state['report_ready']


@pytest.mark.parametrize(('provider_returns_card', 'cached_snapshot'), [(True, True), (True, False), (False, False)])
def test_primary_setup_uses_one_capped_fallback_after_native_failure(pilot, monkeypatch, provider_returns_card, cached_snapshot):
    client, conn = pilot
    path = SETUP + HAMIK
    url = 'https://yandex.ru/maps/org/clinic/123456'
    calls = []

    def read_native(url):
        calls.append('native')
        return {'error': 'yandex_rate_limited'}

    monkeypatch.setattr(initial_setup_sources.map_card_initial_audit, 'initial_native_readers',
                        lambda **_: {'yandex': read_native})
    monkeypatch.setenv('APIFY_TOKEN', 'disposable-token')

    def transport(self, method, endpoint, **kwargs):
        calls.append(method)
        if method == 'GET':
            data = {'pricingInfo': {'pricingModel': 'PAY_PER_EVENT'}}
        else:
            assert method == 'POST'
            assert kwargs['params']['maxTotalChargeUsd'] == '0.02'
            assert kwargs['params']['restartOnError'] == 'false'
            assert kwargs['allow_redirects'] is False
            assert kwargs['json']['maxResults'] == 1
            assert kwargs['json']['query'] == []
            assert kwargs['json']['businessIds'] == ['123456']
            assert kwargs['json']['enrichBusinessData'] is True
            with conn.cursor() as cursor:
                cursor.execute("""SELECT payload_json FROM operator_async_jobs
                    WHERE business_id=%s AND status='running'""", (HAMIK,))
                assert cursor.fetchone()['payload_json']['apify_started'] is True
            if not provider_returns_card:
                raise TimeoutError('Provider did not confirm the request')
            data = {'id': 'fixture-apify', 'status': 'SUCCEEDED', 'defaultDatasetId': 'fixture', 'usageTotalUsd': 0.0155}
        return SimpleNamespace(status_code=200, raise_for_status=lambda: None, json=lambda: {'data': data})

    gallery = 'https://avatars.mds.yandex.net/get-altay/12345/a-b/XXXL'
    monkeypatch.setattr(ProspectingService, '_apify_request', transport)
    monkeypatch.setattr(ProspectingService, 'fetch_dataset_items', lambda _service, _dataset: [{
        'source': 'apify_yandex', 'source_external_id': '123456', 'source_url': url, 'name': 'Clinic',
        'services_json': [{'name': 'Laser consultation'}], 'raw_payload_json': {'photos': [gallery]},
    }])
    queued = action(client, HAMIK, 'start', message=url, auto=True)
    assert queued['sources'][0]['status'] == 'queued'
    assert calls == []
    paid_on_request = {'action': 'read_apify', 'revision': queued['revision'], 'key': queued['sources'][0]['key']}
    assert client.post(path, json=paid_on_request, headers={'X-Pilot-Actor': 'staff'}).status_code == 400
    result = process_next_operator_async_job()
    assert 'error' not in result, result
    assert result['result']['state'] == ('ready' if provider_returns_card else 'unavailable')
    assert process_next_operator_async_job()['result']['state'] == ('ready' if provider_returns_card else 'needs_source')
    if provider_returns_card:
        assert process_next_operator_async_job()['status'] == 'completed'
    assert calls == ['native', 'GET', 'POST']
    state = client.get(path).get_json()['setup']
    assert state['report_ready'] is provider_returns_card
    assert 'apify' not in json.dumps(state).lower()
    if provider_returns_card:
        assert state['services'][0]['original'] == 'Laser consultation'
        assert state['sources'][0]['photo_candidate_count'] == 1
        assert state['sources'][0]['note'] == 'Карточка прочитана.'

        def get_previous_run(_service, run_id):
            assert run_id == 'fixture-apify'
            calls.append('reuse')
            return {'id': run_id, 'status': 'SUCCEEDED', 'defaultDatasetId': 'fixture'}

        monkeypatch.setattr(ProspectingService, 'get_run', get_previous_run)
        # Reset the chat while preserving the previous job and its charge record.
        with conn.cursor() as cursor:
            cursor.execute("UPDATE operator_async_jobs SET idempotency_key='archived-initial-setup:'||id WHERE business_id=%s", (HAMIK,))
            if not cached_snapshot:
                cursor.execute("UPDATE operator_async_jobs SET payload_json=payload_json-'map_snapshot' WHERE business_id=%s", (HAMIK,))
            cursor.execute("UPDATE initial_business_setups SET data='{}'::jsonb,revision=revision+1 WHERE business_id=%s", (HAMIK,))
        conn.commit()
        action(client, HAMIK, 'start', message=url, auto=True)
        assert process_next_operator_async_job()['result']['state'] == 'ready'
        assert process_next_operator_async_job()['result']['state'] == 'ready'
        assert process_next_operator_async_job()['status'] == 'completed'
        state = client.get(path).get_json()['setup']
        assert state['report_ready']
        assert state['services'][0]['original'] == 'Laser consultation'
        assert state['sources'][0]['photo_candidate_count'] == 1
        assert state['sources'][0]['note'] == 'Использован сохранённый снимок этой карточки.'
        assert calls.count('reuse') == int(not cached_snapshot)
    else:
        state = action(client, HAMIK, 'retry', state, key=state['sources'][0]['key'])
        assert process_next_operator_async_job()['status'] == 'failed'
        assert process_next_operator_async_job()['result']['state'] == 'needs_source'
        state = client.get(path).get_json()['setup']
    state = action(client, HAMIK, 'message', state, message='https://yandex.com/maps/org/other/654321', auto=True)
    assert process_next_operator_async_job()['status'] == 'failed'
    assert calls.count('POST') == 1
    assert calls.count('GET') == 1
    assert calls.count('reuse') == int(provider_returns_card and not cached_snapshot)


def test_generated_topics_do_not_replace_an_unread_source():
    data = {'auto_draft': True, 'category_keywords': [{'text': 'Company category'}]}
    assert setup._draft_needs_source(data, [{'status': 'unavailable'}])


def test_website_audit_can_use_pinned_node_on_existing_images(monkeypatch, tmp_path):
    from types import SimpleNamespace

    from services import website_seo_audit

    runner = tmp_path / 'audit.mjs'
    node = tmp_path / 'node'
    monkeypatch.setattr(website_seo_audit, 'IMAGE_RUNNER', tmp_path / 'missing-image-runner.mjs')
    monkeypatch.setattr(website_seo_audit, 'LOCAL_RUNNER', runner)
    monkeypatch.setattr(website_seo_audit, 'BUNDLED_NODE', node)
    monkeypatch.setattr(website_seo_audit.shutil, 'which', lambda binary: str(node) if binary == str(node) else None)
    page = {'url': 'https://example.com/', 'html': '<title>Fixture</title>'}

    def run(args, **kwargs):
        assert args == [str(node), '--max-old-space-size=192', str(runner)]
        assert json.loads(kwargs['input']) == [page]
        return SimpleNamespace(stdout=json.dumps([{'url': page['url'], 'findings': []}]))

    monkeypatch.setattr(website_seo_audit.subprocess, 'run', run)
    report = website_seo_audit.audit_pages([page])
    assert report['status'] == 'ready'
    assert report['engine'] == 'SEOmator'


@pytest.mark.parametrize('business, name, link, service', [
    (HAMIK, 'Хамик', 'https://yandex.com/maps/house/example/4338', None),
    (JINLIAN, 'Jinlian Vegan Ice Cream', 'https://yandex.com/maps/org/jinlian/123456/', 'Coconut scoop'),
])
def test_link_to_private_report_and_owner_session(pilot, monkeypatch, tmp_path, business, name, link, service):
    import main
    import auth_system
    from urllib.parse import parse_qs, urlsplit
    from services import initial_setup_photos

    client, conn = pilot
    dsn = os.environ['INITIAL_SETUP_TEST_DSN']
    new_connection = lambda: psycopg2.connect(dsn, cursor_factory=RealDictCursor)
    monkeypatch.setattr(main, 'get_db_connection', new_connection)
    monkeypatch.setattr(auth_system, 'get_db_connection', new_connection)
    monkeypatch.setenv('BROWSER_COOKIE_AUTH_ENABLED', 'true')
    monkeypatch.setenv('BROWSER_COOKIE_AUTH_SECURE', 'false')
    monkeypatch.setenv('LOCALOS_INITIAL_SETUP_BUSINESS_IDS', 'different-pilot-company')
    monkeypatch.setattr(initial_setup_sources.map_card_initial_audit, 'initial_native_readers', lambda **_: {})
    monkeypatch.setattr(setup._SetupWordstatSearch, 'lookup', lambda _search, _name: [])
    cursor = conn.cursor()
    cursor.execute("UPDATE businesses SET owner_id='staff' WHERE id=%s", (business,))
    stored = setup.init(cursor, business, 'staff', provisional=True)
    stored['data']['activity_type'] = 'Посуточная аренда квартиры' if business == HAMIK else 'Wholesale vegan ice cream in Phuket'
    setup.persist(cursor, stored)
    email = business + '@example.com'
    if business == JINLIAN:
        cursor.execute("UPDATE businesses SET city='Phuket' WHERE id=%s", (business,))
        cursor.execute("INSERT INTO users(id,email,is_active) VALUES ('passwordless-recipient',%s,TRUE)", (email,))
    conn.commit()

    def read(actor='staff'):
        return client.get(SETUP + business, headers={'X-Pilot-Actor': actor}).get_json()['setup']

    def send(action_name, state=None, **values):
        response = client.post(SETUP + business, headers={'X-Pilot-Actor': 'staff'}, json={
            'action': action_name, 'revision': (state or {}).get('revision'), **values
        })
        assert response.status_code == 200, response.get_json()
        return response.get_json()['setup']

    state = send('start', message=link, auto=True)
    assert state['draft_status'] == 'queued'
    assert not state['report_ready']
    staff = {'X-Pilot-Actor': 'staff'}
    assert client.get(SETUP + business + '/report', headers=staff).status_code == 409
    jobs = []
    for _ in range(7):
        job = process_next_operator_async_job()
        if not job:
            break
        jobs.append(job['kind'])
        assert job['status'] == 'completed', job
    assert jobs == [setup.JOB_KIND, setup.DRAFT_JOB_KIND, initial_setup_photos.JOB_KIND]
    state = read()
    assert state['draft_ready'] and state['report_ready']
    assert not state['saved']
    assert state['profile']['name'] == name
    assert (state['sources'][0]['status'] == 'link_only') is (business == HAMIK)
    if service:
        assert any(item['original'] == service for item in state['services'])
    else:
        assert not state['services']

    pdf = client.get(SETUP + business + '/report', headers=staff)
    assert pdf.status_code == 200, pdf.get_data(as_text=True)[:120] if pdf.status_code != 200 else ''
    assert pdf.data.startswith(b'%PDF-')
    assert pdf.headers['Cache-Control'] == 'private, no-store'
    (tmp_path / (business + '.pdf')).write_bytes(pdf.data)
    cursor.execute('SELECT name, optimized_name FROM userservices WHERE business_id=%s AND is_active IS NOT FALSE', (business,))
    existing = cursor.fetchall()
    assert all(row['optimized_name'] is None for row in existing)
    assert len(existing) == (1 if service else 0)
    cursor.execute('SELECT owner_id FROM businesses WHERE id=%s', (business,))
    assert cursor.fetchone()['owner_id'] == 'staff'

    invite_route = SETUP + business + '/owner'
    assert client.post(invite_route, headers=staff, json={'email': email, 'revision': state['revision']}).status_code == 409
    state = send('save', state)
    invitation = client.post(invite_route, headers=staff, json={'email': email, 'revision': state['revision']})
    assert invitation.status_code == 200, invitation.get_json()
    invitation_parts = urlsplit(invitation.get_json()['invite_url'])
    assert invitation_parts.path == '/set-password'
    assert not invitation_parts.query
    details = parse_qs(invitation_parts.fragment)
    activation = {'email': email, 'token': details['token'][0], 'password': 'Test-only-activation-771', 'personal_data_consent': True}
    with main.app.test_client() as owner:
        activated = owner.post('/api/auth/set-password', json=activation)
        assert activated.status_code == 200, activated.get_json()
        assert activated.get_json()['initial_setup'] is True
        assert activated.get_json()['business_id'] == business
        assert 'token' not in activated.get_json()
        cookie = owner.get_cookie('localos_session')
        assert cookie and cookie.http_only and auth_system.verify_session(cookie.value)
        session_actor = auth_system.verify_session(cookie.value)
        assert not session_actor['is_superadmin']
        owner_id = session_actor['user_id']
        if business == JINLIAN:
            assert owner_id == 'passwordless-recipient'
        assert read(owner_id)['saved']
        assert read(owner_id)['viewer_is_owner']
        assert client.get(SETUP + business + '/report', headers={'X-Pilot-Actor': owner_id}).status_code == 200
        other = HAMIK if business == JINLIAN else JINLIAN
        assert client.get(SETUP + other + '/report', headers={'X-Pilot-Actor': owner_id}).status_code in (403, 404)
        assert owner.post('/api/auth/set-password', json=activation).status_code == 400
        owner_state = read(owner_id)
        update = client.post(SETUP + business, headers={'X-Pilot-Actor': owner_id}, json={
            'action': 'message', 'revision': owner_state['revision'], 'message': 'https://example.com/contact', 'auto': True,
        })
        assert update.status_code == 200 and not update.get_json()['setup']['saved']
        assert client.get(SETUP + business, headers={'X-Pilot-Actor': owner_id}).get_json()['available']


def test_report_keeps_multilingual_queries_and_avoids_repeated_evidence():
    from pypdf import PdfReader
    from services.initial_setup_report import render_report

    terms = [{'text': 'վարձով բնակարան', 'views': 18, 'source': 'Wordstat'},
             {'text': 'ไอศกรีมวีแกน ภูเก็ต', 'views': None, 'source': 'Тема'}]
    state = {
        'business_id': 'fixture', 'profile': {'name': 'Проверка PDF'}, 'sources': [], 'profile_choices': [],
        'facts': [], 'comparisons': [], 'category_keywords': terms,
        'services': [{'original': 'Мороженое', 'proposed': 'Мороженое', 'keywords': terms}],
        'report_follow_up': {
            'requests': {'photos': 'Дневной снимок входа', 'data': 'Адрес выдачи', 'access': 'Роль управляющего'},
            'listings': [{'label': 'Google Maps', 'text': 'Точка закрыта', 'url': 'https://www.google.com/maps?cid=123'}],
        },
    }
    document = PdfReader(render_report(state))
    content = '\n'.join(page.extract_text() for page in document.pages)
    assert all(content.count(item['text']) == 1 for item in terms)
    assert all(item in content for item in (
        'Что нужно от вас', 'Дневной снимок входа', 'Адрес выдачи', 'Роль управляющего', 'Точка закрыта',
    ))
    fonts = {str(ref.get_object().get('/BaseFont')) for page in document.pages
             for ref in page['/Resources']['/Font'].values()}
    assert any('NotoSansArmenian' in font for font in fonts)
    assert any('NotoSansThai' in font for font in fonts)
