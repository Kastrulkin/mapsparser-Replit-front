"""Handoff references, stale previews and help requests against an owned PG schema."""
import os
import uuid

import psycopg2
import pytest
from psycopg2.extras import RealDictCursor, Json

from services import prepared_cabinet_sources, prepared_cabinet, connection_assistance


@pytest.fixture()
def db():
    dsn = os.getenv('PREPARED_CABINET_TEST_DSN')
    if not dsn:
        pytest.skip('PREPARED_CABINET_TEST_DSN is required for isolated PostgreSQL checks')
    if not dsn.startswith('postgresql://pilot@127.0.0.1:55674/'):
        raise RuntimeError('This test only permits its explicitly owned local cluster')
    conn = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
    schema = 'prepared_test_' + uuid.uuid4().hex
    cur = conn.cursor()
    cur.execute('CREATE SCHEMA ' + schema)
    cur.execute('SET search_path TO ' + schema)
    cur.execute('''
        CREATE TABLE users(id text PRIMARY KEY);
        CREATE TABLE businesses(id text PRIMARY KEY,name text,address text,owner_id text,is_active boolean,network_id text);
        CREATE TABLE business_members(business_id text,user_id text,status text,role text);
        CREATE TABLE networks(id text,owner_id text);
        CREATE TABLE network_members(network_id text,user_id text,status text);
        CREATE TABLE userservices(id text PRIMARY KEY,business_id text,name text,optimized_name text,optimized_description text,is_active boolean,updated_at timestamptz DEFAULT now());
        CREATE TABLE reviewreplydrafts(id text PRIMARY KEY,business_id text,author_name text,generated_text text,edited_text text,status text,updated_at timestamptz DEFAULT now());
        CREATE TABLE contentplans(id text PRIMARY KEY,business_id text,title text);
        CREATE TABLE contentplanitems(id text PRIMARY KEY,plan_id text,business_id text,theme text,goal text,draft_text text,status text,scheduled_for date);
        CREATE TABLE prospectingleads(id text PRIMARY KEY,name text,address text,source_url text,description text,disqualification_reason text);
        CREATE TABLE lead_workstreams(id text PRIMARY KEY,lead_id text,client_business_id text,workstream_type text,status text,partnership_outcome_json jsonb,updated_at timestamptz DEFAULT now());
        CREATE TABLE creator_profiles(id text PRIMARY KEY,display_name text,description text,verification_status text,metadata_json jsonb);
        CREATE TABLE creator_channels(id text PRIMARY KEY,creator_profile_id text,canonical_url text,verification_status text,created_at timestamptz DEFAULT now());
        CREATE TABLE creator_search_jobs(id text PRIMARY KEY,business_id text);
        CREATE TABLE creator_search_results(id text PRIMARY KEY,search_job_id text,creator_profile_id text,shortlist_status text,score numeric,reasons_json jsonb);
        CREATE TABLE prepared_cabinets(business_id text PRIMARY KEY,owner_id text,materials jsonb,seen jsonb DEFAULT '{}');
        CREATE TABLE botfeaturerequests(id text PRIMARY KEY,telegram_id text,user_id text,business_id text,source text,category text,request_text text,metadata_json jsonb,status text,created_at timestamptz,updated_at timestamptz);
        INSERT INTO businesses VALUES ('b','Test business','Test branch','owner',true,NULL);
        INSERT INTO userservices(id,business_id,name,optimized_name,optimized_description,is_active) VALUES ('s','b','Original','Improved','Description',true),('private','other','Private','Private','Private',true);
        INSERT INTO reviewreplydrafts VALUES ('r','b','Customer','Generated','Edited','draft',now());
        INSERT INTO contentplans VALUES ('p','b','Plan');
        INSERT INTO contentplanitems VALUES ('post','p','b','Theme','Goal','Post text','edited','2026-11-13');
        INSERT INTO prospectingleads VALUES ('lead','Partner','Address','https://example.com','Reason',NULL);
        INSERT INTO lead_workstreams VALUES ('partner','lead','b','client_partnership','active','{}',now());
        INSERT INTO creator_profiles VALUES ('author','Author','Local author','verified','{}');
        INSERT INTO creator_channels VALUES ('channel','author','https://example.com/author','verified',now());
        INSERT INTO creator_search_jobs VALUES ('job','b');
        INSERT INTO creator_search_results VALUES ('result','job','author','shortlisted',80,'["Fit"]');
    ''')
    conn.commit()
    try:
        yield conn
    finally:
        conn.rollback()
        conn.cursor().execute('DROP SCHEMA ' + schema + ' CASCADE')
        conn.commit()
        conn.close()


def choose_all(db):
    preview = prepared_cabinet_sources.preview(db.cursor(), 'b')
    selection = {section['key']: [item['source_id'] for item in section['items']] for section in preview['sections']}
    return prepared_cabinet_sources.choose(db.cursor(), 'b', selection, preview['version'])


def test_five_existing_sources_are_resolved_and_private_records_excluded(db):
    selection = choose_all(db)
    assert len(selection) == 5
    assert selection['services'] == [{'source_type':'services','source_id':'s'}]
    materials = prepared_cabinet_sources.resolve(db.cursor(),'b',selection)
    assert materials['reviews'][0]['text'] == 'Edited'
    assert materials['content'][0]['text'].endswith('Post text')


def test_stale_preview_is_rejected(db):
    preview = prepared_cabinet_sources.preview(db.cursor(),'b')
    selection = {section['key']: [item['source_id'] for item in section['items']] for section in preview['sections']}
    db.cursor().execute("UPDATE userservices SET optimized_name='Changed' WHERE id='s'")
    with pytest.raises(ValueError, match='изменились'):
        prepared_cabinet_sources.choose(db.cursor(),'b',selection,preview['version'])


def test_cross_business_source_cannot_be_selected(db):
    preview = prepared_cabinet_sources.preview(db.cursor(),'b')
    selection = {section['key']: [item['source_id'] for item in section['items']] for section in preview['sections']}
    selection['services'] = ['private']
    with pytest.raises(ValueError):
        prepared_cabinet_sources.choose(db.cursor(),'b',selection,preview['version'])


def test_selected_old_record_survives_newer_candidates(db):
    selected = choose_all(db)
    db.cursor().execute("INSERT INTO userservices SELECT 'new'||n,'b','New','New','New',true,now()+interval '1 day' FROM generate_series(1,40) n")
    assert prepared_cabinet_sources.resolve(db.cursor(),'b',selected)['services'][0]['source_id'] == 's'


def test_source_removal_does_not_expose_stale_content(db):
    selected = choose_all(db)
    db.cursor().execute("UPDATE userservices SET is_active=false WHERE id='s'")
    assert prepared_cabinet_sources.resolve(db.cursor(),'b',selected)['services'] == []


def test_legacy_packages_keep_their_content(db):
    legacy = {key:[{'title':'Title','text':'Text'}] for key in prepared_cabinet.SECTIONS}
    assert prepared_cabinet.save_materials(db.cursor(),'b',legacy)
    assert len(prepared_cabinet.owner_package(db.cursor(),'b','owner')) == 5
    assert prepared_cabinet.owner_package(db.cursor(),'b','other') == []


def test_native_package_changes_version_when_source_changes(db):
    assert prepared_cabinet.save_materials(db.cursor(),'b',choose_all(db),references=True)
    first = prepared_cabinet.owner_package(db.cursor(),'b','owner')[0]
    db.cursor().execute("UPDATE userservices SET optimized_description='Updated' WHERE id='s'")
    current = prepared_cabinet.owner_package(db.cursor(),'b','owner')[0]
    assert current['version'] != first['version']
    assert current['unread']


def test_help_is_persisted_once_and_scoped_to_business(db):
    data={'message':'Need help','service':'Telegram','request_id':str(uuid.uuid4())}
    user={'user_id':'owner','email':'owner@example.test'}
    first=connection_assistance.create(db,'b',user,data)
    assert connection_assistance.create(db,'b',user,data) == first
    assert len(connection_assistance.list_requests(db.cursor(),'b')) == 1
    assert not connection_assistance.list_requests(db.cursor(),'other')
    with pytest.raises(PermissionError):
        connection_assistance.create(db,'b',{'user_id':'stranger'},data)


def test_help_retry_with_changed_message_is_rejected(db):
    data={'message':'Need help','request_id':str(uuid.uuid4())}
    connection_assistance.create(db,'b',{'user_id':'owner'},data)
    with pytest.raises(ValueError,match='изменилось'):
        connection_assistance.create(db,'b',{'user_id':'owner'},{**data,'message':'Different'})


def test_help_lifecycle_rejects_stale_or_wrong_business_update(db):
    request_id=connection_assistance.create(db,'b',{'user_id':'owner'},{'message':'Need help','request_id':str(uuid.uuid4())})
    command={'id':request_id,'previous_status':'new','status':'in_progress'}
    with pytest.raises(ValueError): connection_assistance.update(db.cursor(),'other',command)
    connection_assistance.update(db.cursor(),'b',command)
    with pytest.raises(ValueError): connection_assistance.update(db.cursor(),'b',command)
    connection_assistance.update(db.cursor(),'b',{'id':request_id,'previous_status':'in_progress','status':'done'})
    assert connection_assistance.list_requests(db.cursor(),'b')[0]['status']=='done'


def test_plan_without_any_written_post_cannot_be_handed_to_owner(db):
    db.cursor().execute("UPDATE contentplanitems SET draft_text=NULL")
    with pytest.raises(ValueError,match='черновик поста'):
        choose_all(db)


def test_owner_help_history_does_not_include_another_users_question(db):
    connection_assistance.create(db,'b',{'user_id':'owner'},{'message':'Owner question','request_id':str(uuid.uuid4())})
    connection_assistance.create(db,'b',{'user_id':'admin','is_superadmin':True},{'message':'Admin question','request_id':str(uuid.uuid4())})
    own=connection_assistance.list_requests(db.cursor(),'b','owner')
    assert len(own)==1 and own[0]['request_text']=='Owner question'
    assert len(connection_assistance.list_requests(db.cursor(),'b'))==2
