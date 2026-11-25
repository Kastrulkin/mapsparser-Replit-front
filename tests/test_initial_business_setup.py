"""Setup chat, queue and durable results on an explicitly disposable PostgreSQL."""
import importlib
import json
import os

import psycopg2
import pytest
from flask import Flask, request
from psycopg2.extras import RealDictCursor

import database_manager
from api import initial_business_setup_api
from services import initial_business_setup as setup
from services import initial_setup_sources
from services.operator_async_jobs import claim_next_operator_async_job

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
    monkeypatch.delenv('LOCALOS_INITIAL_SETUP_BUSINESS_IDS', raising=False)
    monkeypatch.delenv('LOCALOS_INITIAL_SETUP_LEAD_IDS', raising=False)
    monkeypatch.setattr(database_manager, 'get_db_connection', connect)
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
        CREATE TABLE businesses(id text PRIMARY KEY, owner_id text, name text, address text, city text, country text,
            business_type text, website text, phone text, email text, is_active boolean DEFAULT true, network_id text,
            entity_group text DEFAULT 'client', moderation_status text, updated_at timestamptz DEFAULT now());
        CREATE TABLE business_members(business_id text, user_id text, role text, status text);
        CREATE TABLE network_members(network_id text, user_id text, role text, status text);
        CREATE TABLE networks(id text, owner_id text);
        CREATE TABLE businessprofiles(business_id text PRIMARY KEY, contact_phone text, contact_email text);
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
                        lambda: pytest.fail('A residential address must not launch a business card parser'))
    state = action(client, HAMIK, 'message', state, message='https://yandex.com/maps/house/example/123456')
    assert process_next(conn)['state'] == 'link_only'
    state = client.get(SETUP + HAMIK).get_json()['setup']
    assert state['sources'][0]['status'] == 'link_only'
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
    monkeypatch.setattr(initial_setup_sources.map_card_initial_audit, 'initial_native_readers', lambda: {'yandex': lambda url: {
        'title': 'Fixture competitor', 'rating': 4.4, 'reviews_count': 12, 'products': [{'name': 'Soy scoop'}],
    }})
    assert process_next(conn)['state'] == 'ready'
    state = client.get(SETUP + JINLIAN).get_json()['setup']
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
    facts = state['facts']
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


def test_staff_lead_draft_is_idempotent_and_handoff_requires_review(pilot, monkeypatch):
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
    assert state['provisional']
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
    owner = client.post(owner_url, json={'email': 'pilot-owner@example.com', 'revision': state['revision']}, headers=staff)
    assert owner.status_code == 200, owner.get_json()
    assert owner.get_json()['existing_account']
    assert client.get(SETUP + business).get_json()['setup']['provisional'] is False
    cursor.execute('SELECT relation_role FROM business_company_links WHERE business_id=%s', (business,))
    assert cursor.fetchone()['relation_role'] == 'owner'

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
