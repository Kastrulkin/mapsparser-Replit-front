"""Real PostgreSQL regression tests; opt-in DSN must point to a disposable local DB."""
import importlib.util
import io
import os
import uuid
from pathlib import Path
import pytest
from services import business_knowledge as knowledge
from services.business_knowledge_validation import field_definition,typed_value,document_text
from services.business_knowledge_templates import fields


@pytest.mark.parametrize('kind,value',[('integer',0),('decimal',1.5),('boolean',False),('text','Шесть кресел'),('date','2026-10-12'),('url','https://localos.pro')])
def test_typed_values_keep_meaning(kind,value):
    definition=field_definition({'label':'Поле','type':kind})
    assert typed_value(definition,{'state':'set','value':value})['value']==value
    assert typed_value(definition,{'state':'unknown'})['value'] is None
    assert typed_value(definition,{'state':'not_applicable'})['state']=='not_applicable'


def test_types_and_archived_choices():
    definition=field_definition({'label':'Поле','type':'integer','min':0})
    for value in (True,1.5,'6',-1):
        with pytest.raises(ValueError):typed_value(definition,{'value':value})
    definition=field_definition({'label':'Поле','type':'multi_select','options':[{'id':'a','label':'A','archived':True},{'id':'b','label':'B'}]})
    assert typed_value(definition,{'value':['a']},{'value':['a']})['value']==['a']
    with pytest.raises(ValueError):typed_value(definition,{'value':['a']})
    with pytest.raises(ValueError):typed_value(definition,{'value':[{}]})
    with pytest.raises(ValueError):typed_value(definition,{'state':'unknown','valid_until':'не дата'})


def test_documents_limits_and_invalid_files():
    assert document_text('Условия обслуживания'.encode(),'rules.txt')[0]=='Условия обслуживания'
    with pytest.raises(ValueError):document_text(b'x'*30001,'large.txt')
    with pytest.raises(ValueError):document_text(b'x','rules.exe')
    with pytest.raises(ValueError):document_text(b'x','broken.docx')
    with pytest.raises(ValueError,match='10 МБ'):document_text(b'x'*(10*1024*1024+1),'huge.txt')
    from pypdf import PdfWriter
    writer=PdfWriter()
    for _ in range(51):writer.add_blank_page(width=100,height=100)
    output=io.BytesIO();writer.write(output)
    with pytest.raises(ValueError,match='50'):document_text(output.getvalue(),'large.pdf')
    writer=PdfWriter();writer.add_blank_page(width=100,height=100)
    output=io.BytesIO();writer.write(output)
    assert document_text(output.getvalue(),'scan.pdf')[1]=='text_unavailable'


@pytest.mark.parametrize('key', ['beauty_salon','school','auto_service','cafe','transport','hotel','guest_house','unknown'])
def test_industry_suggestions_are_definitions(key):
    assert all(field_definition(item)['location_only'] for item in fields(key))
    assert len({item['template_key'] for item in fields(key)})==len(fields(key))


@pytest.fixture
def db(monkeypatch,tmp_path):
    dsn=os.getenv('BUSINESS_KNOWLEDGE_TEST_DSN')
    if not dsn:pytest.skip('Set BUSINESS_KNOWLEDGE_TEST_DSN to a disposable localhost PostgreSQL')
    import psycopg2
    from psycopg2.extensions import parse_dsn
    assert parse_dsn(dsn).get('host') in ('localhost','127.0.0.1','/tmp')
    connection=psycopg2.connect(dsn)
    cursor=connection.cursor();schema='knowledge_test_'+uuid.uuid4().hex
    cursor.execute(f'CREATE SCHEMA {schema}');cursor.execute(f'SET search_path TO {schema}')
    cursor.execute('''CREATE TABLE users(id TEXT PRIMARY KEY,name TEXT,email TEXT,is_active BOOLEAN DEFAULT TRUE,is_superadmin BOOLEAN DEFAULT FALSE);
      CREATE TABLE networks(id TEXT PRIMARY KEY,name TEXT,owner_id TEXT);
      CREATE TABLE businesses(id TEXT PRIMARY KEY,name TEXT,business_type TEXT,network_id TEXT,owner_id TEXT,is_active BOOLEAN DEFAULT TRUE);
      CREATE TABLE business_members(business_id TEXT,user_id TEXT,role TEXT,status TEXT);
      CREATE TABLE network_members(network_id TEXT,user_id TEXT,role TEXT,status TEXT);
      CREATE TABLE businesstypes(type_key TEXT,label TEXT,is_active BOOLEAN);
      CREATE TABLE finance_workplaces(id TEXT,business_id TEXT,name TEXT,type TEXT,is_active BOOLEAN);
      INSERT INTO users(id,name) VALUES ('owner','Владелец'),('manager','Управляющий'),('staff','Сотрудник');
      INSERT INTO networks VALUES ('net','Сеть','owner');
      INSERT INTO businesses(id,name,business_type,network_id,owner_id) VALUES ('salon','Салон','beauty_salon','net','owner'),('school','Школа','school','net','owner');
      INSERT INTO business_members VALUES ('salon','manager','manager','active'),('salon','staff','member','active');
      INSERT INTO businesstypes VALUES ('beauty_salon','Салон',TRUE),('school','Школа',TRUE),('auto_service','СТО',TRUE),('other','Другое',TRUE);''')
    def verify(c,b,user):
        c.execute('SELECT owner_id FROM businesses WHERE id=%s',(b,));row=c.fetchone()
        if not row:return False,None
        owner=row[0]
        if owner==user['user_id']:return True,owner
        c.execute("SELECT 1 FROM business_members WHERE business_id=%s AND user_id=%s AND status='active'",(b,user['user_id']))
        return bool(c.fetchone()),owner
    monkeypatch.setattr('core.auth_helpers.verify_business_access',verify)
    monkeypatch.setattr('subscription_manager.get_capability_access',lambda *a,**kw:{'allowed':True})
    monkeypatch.setenv('BUSINESS_KNOWLEDGE_DIR',str(tmp_path/'private'))
    migration_path=Path(__file__).parents[1]/'alembic_migrations/versions/20261012_business_knowledge.py'
    spec=importlib.util.spec_from_file_location('knowledge_migration',migration_path);migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    monkeypatch.setattr(migration.op,'execute',cursor.execute)
    migration.upgrade();migration.upgrade()
    try:yield cursor
    finally:
        connection.rollback();cursor.execute(f'DROP SCHEMA IF EXISTS {schema} CASCADE');connection.commit();connection.close()


def user(name='owner'):return {'user_id':name,'is_superadmin':False}
def change(cursor,operation,payload=None,**kwargs):
    return knowledge.mutate(cursor,kwargs.pop('scope_type','business'),kwargs.pop('scope_id','salon'),user(kwargs.pop('actor','owner')),{'operation':operation,'request_id':str(uuid.uuid4()),'payload':payload or {},**kwargs})
def custom(cursor,**kwargs):return change(cursor,'field',{'label':'Кресла','type':'integer','min':0,**kwargs})['record']


def test_versions_rename_conflict_idempotence_and_archive(db):
    field=custom(db);value=change(db,'value',{'field_id':field['id'],'state':'set','value':0})['record']
    request={'operation':'field','id':field['id'],'version':field['version'],'payload':{**field['payload_json'],'label':'Рабочие кресла'},'request_id':'repeat'}
    result=knowledge.mutate(db,'business','salon',user(),request)
    assert knowledge.mutate(db,'business','salon',user(),request)==result
    assert result['record']['id']==field['id']
    with pytest.raises(knowledge.Conflict):change(db,'field',field['payload_json'],id=field['id'],version=1)
    with pytest.raises(ValueError):change(db,'field',{**field['payload_json'],'type':'boolean'},id=field['id'],version=2)
    assert knowledge.read(db,'business','salon',user())['fields'][0]['value_record']['payload_json']['value']==0
    assert len(knowledge.history(db,'business','salon',user(),field['id'])['items'])==2
    change(db,'archive',id=field['id'],version=2)
    assert not knowledge.read(db,'business','salon',user())['fields']
    with pytest.raises(PermissionError):knowledge.history(db,'business','salon',user('staff'),value['id'])


def test_editors_revocation_and_private_context(db):
    field=custom(db)
    with pytest.raises(PermissionError):change(db,'value',{'field_id':field['id'],'value':6},actor='manager')
    grant=change(db,'editor',{'user_id':'manager','enabled':True},version=0)['editor']
    change(db,'value',{'field_id':field['id'],'value':6},actor='manager')
    with pytest.raises(PermissionError):change(db,'field',{'label':'Нельзя','type':'text'},actor='manager')
    change(db,'rule',{'label':'Внутреннее','text':'Секрет руководства'},audience='management')
    assert 'Секрет' not in knowledge.context(db,'salon','staff')['text']
    assert 'Секрет' in knowledge.context(db,'salon','owner')['text']
    change(db,'editor',{'user_id':'manager','enabled':False},version=grant['version'])
    with pytest.raises(PermissionError):change(db,'rule',{'label':'Правило','text':'Нельзя'},actor='manager')
    with pytest.raises(PermissionError):knowledge.read(db,'business','school',user('staff'))


def test_network_rules_local_exception_and_capacity(db):
    rule=change(db,'rule',{'label':'Приём','text':'Только по записи'},scope_type='network',scope_id='net')['record']
    assert knowledge.read(db,'business','salon',user())['rules'][0]['id']==rule['id']
    change(db,'rule',{'label':'Приём','text':'С 12 часов','origin_id':rule['id']})
    assert [r['payload_json']['text'] for r in knowledge.read(db,'business','salon',user())['rules']]==['С 12 часов']
    assert knowledge.read(db,'business','school',user())['rules'][0]['payload_json']['text']=='Только по записи'
    template=change(db,'template',{'type_key':'beauty_salon','fields':['hair_chairs']},scope_type='network',scope_id='net')['records'][0]
    with pytest.raises(ValueError):change(db,'value',{'field_id':template['id'],'value':6},scope_type='network',scope_id='net')
    change(db,'value',{'field_id':template['id'],'value':6})
    data=knowledge.read(db,'network','net',user())
    assert data['locations']['summaries'][0]['value']==6
    assert data['locations']['summaries'][0]['coverage']==1
    assert data['locations']['total']==2
    assert change(db,'template',{'type_key':'beauty_salon','fields':['hair_chairs']},scope_type='network',scope_id='net')['already_present']==1
    maximum=change(db,'template',{'type_key':'school','fields':['group_max']},scope_type='network',scope_id='net')['records'][0]
    change(db,'value',{'field_id':maximum['id'],'value':15})
    assert len(knowledge.read(db,'network','net',user())['locations']['summaries'])==1


def test_financial_inventory_is_not_inferred_capacity(db):
    field=change(db,'template',{'type_key':'beauty_salon','fields':['hair_chairs']})['records'][0]
    change(db,'value',{'field_id':field['id'],'value':6})
    db.execute("INSERT INTO finance_workplaces VALUES ('chair','salon','Кресло 1','chair',TRUE)")
    assert not knowledge.read(db,'business','salon',user())['inventory']['mismatches']
    change(db,'inventory_complete',{'complete':True},version=0)
    assert knowledge.read(db,'business','salon',user())['inventory']['mismatches'][0]['declared']==6
    db.execute('SELECT COUNT(*) FROM finance_workplaces');assert db.fetchone()[0]==1
    change(db,'field',{**field['payload_json'],'unit':'руб.'},id=field['id'],version=1)
    assert not knowledge.read(db,'business','salon',user())['inventory']['mismatches']


def test_financial_access_does_not_block_knowledge_or_expose_resources(db,monkeypatch):
    custom(db)
    db.execute("INSERT INTO finance_workplaces VALUES ('private','salon','Закрытый ресурс','chair',TRUE)")
    monkeypatch.setattr('subscription_manager.get_capability_access',lambda *a,**kw:{'allowed':False})
    data=knowledge.read(db,'business','salon',user())
    assert data['can_edit'] and data['fields']
    assert not data['inventory']['items'] and not data['inventory']['available']


def test_private_documents_confirmation_replacement_history(db):
    request={'request_id':'upload-one','audience':'management'}
    document=knowledge.upload(db,'business','salon',user(),b'Policy A','rules.txt',request)['record']
    assert 'storage_key' not in document['payload_json']
    assert knowledge.upload(db,'business','salon',user(),b'Policy A','rules.txt',request)['record']==document
    assert not knowledge.context(db,'salon','owner')['text']
    change(db,'document',{'confirmed':True},id=document['id'],version=1)
    assert 'Policy A' in knowledge.context(db,'salon','owner')['text']
    assert not knowledge.read(db,'business','salon',user('staff'))['documents']
    with pytest.raises(PermissionError):knowledge.download(db,'business','salon',user('staff'),document['id'])
    replacement=knowledge.upload(db,'business','salon',user(),b'Policy B','rules.txt',{'request_id':'replacement','id':document['id'],'version':2})['record']
    assert replacement['id']==document['id'] and replacement['version']==3
    assert not knowledge.context(db,'salon','owner')['text']
    old,_=knowledge.download(db,'business','salon',user(),document['id'],1);assert old.read_bytes()==b'Policy A'
    change(db,'archive',id=document['id'],version=3)
    assert not knowledge.read(db,'business','salon',user())['documents']


def test_http_api_same_permissions_versions_and_downloads(db,monkeypatch):
    from flask import Flask,request
    from api import business_knowledge_api as api
    db.connection.commit()
    class Database:
        conn=db.connection
        def close(self):pass
    monkeypatch.setattr(api,'DatabaseManager',Database)
    monkeypatch.setattr(api,'require_auth_from_request',lambda:{'user_id':request.headers.get('X-Actor','owner')})
    app=Flask(__name__);app.register_blueprint(api.business_knowledge_bp);client=app.test_client()
    url='/api/business-knowledge?scope_type=business&scope_id=salon'
    definition=client.post(url,json={'operation':'field','payload':{'label':'Кресла','type':'integer'},'request_id':'http-create'})
    assert definition.status_code==200
    record=definition.json['record']
    assert client.get(url).headers['Cache-Control']=='private, no-store'
    assert client.post(url,headers={'X-Actor':'staff'},json={'operation':'value','payload':{'field_id':record['id'],'value':6},'request_id':'staff-write'}).status_code==403
    assert client.post(url,json={'operation':'field','id':record['id'],'version':0,'payload':record['payload_json'],'request_id':'conflict'}).status_code==409
    uploaded=client.post('/api/business-knowledge/documents?scope_type=business&scope_id=salon',data={'file':(io.BytesIO(b'Private facts'),'rules.txt'),'request_id':'http-upload','audience':'management'})
    assert uploaded.status_code==200
    doc=uploaded.json['record']
    download=f"/api/business-knowledge/{doc['id']}/download?scope_type=business&scope_id=salon"
    assert client.get(download).data==b'Private facts'
    assert client.get(download,headers={'X-Actor':'staff'}).status_code==403
    assert not client.get(url,headers={'X-Actor':'staff'}).json['documents']


def test_business_manager_cannot_download_private_network_document_history(db):
    original=knowledge.upload(db,'network','net',user(),b'Network leadership only','policy.txt',{'request_id':'network-private','audience':'management'})['record']
    replaced=knowledge.upload(db,'network','net',user(),b'Team instructions','policy.txt',{'request_id':'network-team','audience':'team','id':original['id'],'version':1})['record']
    db.execute("UPDATE businesses SET owner_id='manager' WHERE id='salon'")
    assert knowledge.read(db,'business','salon',user('manager'))['documents'][0]['id']==replaced['id']
    assert knowledge.download(db,'business','salon',user('manager'),replaced['id'])[0].read_bytes()==b'Team instructions'
    with pytest.raises(PermissionError):knowledge.download(db,'business','salon',user('manager'),replaced['id'],1)


def test_chat_and_telegram_tools_prepare_durable_approval_without_saving(db,monkeypatch):
    from services import operator_business_knowledge
    from services import operator_conversations
    from services.operator_tool_loop import run_operator_tool_loop
    db.execute('CREATE TABLE operatoractions(id TEXT PRIMARY KEY,expires_at TIMESTAMPTZ)')
    field=custom(db)
    actions=[]
    monkeypatch.setattr(operator_conversations,'get_or_create_operator_conversation',lambda *a,**kw:{'id':'conversation'})
    def create(cursor,**args):
        actions.append(args);cursor.execute("INSERT INTO operatoractions VALUES ('action',NULL)")
        return {'id':'action'}
    monkeypatch.setattr(operator_conversations,'create_pending_operator_action',create)
    tools=operator_business_knowledge.tools(db,'salon','owner','telegram')
    result=run_operator_tool_loop(business_id='salon',user_id='owner',message='Укажи шесть кресел',tools=tools,
        planner=lambda state:{'action':'tool_call','tool':'knowledge.prepare_change','arguments':{'operation':'value','payload':{'field_id':field['id'],'value':6}}})
    assert result['status']=='approval_required'
    assert result['approval']['action_id']=='action'
    assert not knowledge.read(db,'business','salon',user())['fields'][0]['value_record']
    from services import operator_core
    pending={'id':'action','status':'pending','capability':'business.knowledge','envelope_json':actions[0]['envelope']}
    monkeypatch.setattr(operator_core,'get_operator_action',lambda *a,**kw:pending)
    def finish(cursor,**args):pending.update(status='completed',result_json=args['result'])
    monkeypatch.setattr(operator_core,'finish_operator_action',finish)
    result,repeated=operator_core.confirm_pending_operator_action(db,action_id='action',business_id='salon',user_id='owner',subscription_access={'blocked':True})
    assert result['status']=='completed' and not repeated
    assert result['knowledge_change']['record']['payload_json']['value']==6
    repeated_result,repeated=operator_core.confirm_pending_operator_action(db,action_id='action',business_id='salon',user_id='owner')
    assert repeated and repeated_result==result
    assert len(knowledge.history(db,'business','salon',user(),result['knowledge_change']['record']['id'])['items'])==1


def test_staff_proposal_stays_in_journal_with_link_and_is_not_a_fact(db,monkeypatch):
    from services import operator_audio,work_journal
    db.execute('CREATE TABLE averageticketevents(id TEXT PRIMARY KEY)')
    spec=importlib.util.spec_from_file_location('journal_migration',Path(__file__).parents[1]/'alembic_migrations/versions/20260912_work_journal.py')
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    monkeypatch.setattr(migration.op,'execute',db.execute);migration.upgrade()
    monkeypatch.setattr(operator_audio,'authorize_actor',lambda cursor,actor,business,**kwargs:({'role':'business_owner' if actor=='owner' else 'business_user'},{}))
    monkeypatch.setenv('OPERATOR_WORK_JOURNAL_BUSINESS_IDS','')
    monkeypatch.setenv('OPERATOR_BUSINESS_INFORMATION_ENABLED','false')
    field=custom(db)
    entry=knowledge.propose(db,'salon',user('staff'),'В салоне шесть кресел',field['id'],'proposal')
    assert entry['facts_json']['knowledge_proposal']['record_id']==field['id']
    assert not knowledge.context(db,'salon','staff')['text']
    assert not knowledge.read(db,'business','salon',user())['fields'][0]['value_record']
    assert knowledge.propose(db,'salon',user('staff'),'В салоне шесть кресел',field['id'],'proposal')['id']==entry['id']
    with pytest.raises(PermissionError):work_journal.save_note(db,'salon','staff','web',None,'unrelated','Обычная запись',{'quote':'Обычная запись'})
    source={'source_entry_id':entry['id'],'source_entry_version':entry['version']}
    other=custom(db,label='Другое поле')
    with pytest.raises(ValueError,match='другой записи'):change(db,'value',{'field_id':other['id'],'value':6,**source})
    assert not knowledge.read(db,'business','salon',user())['proposals'][0]['applied']
    saved=change(db,'value',{'field_id':field['id'],'value':6,**source})['record']
    assert knowledge.read(db,'business','salon',user())['proposals'][0]['applied']
    db.execute('UPDATE business_work_journal SET version=version+1 WHERE id=%s',(entry['id'],))
    with pytest.raises(knowledge.Conflict,match='наблюдение изменилось'):change(db,'value',{'field_id':field['id'],'value':7,**source},id=saved['id'],version=saved['version'])


def test_current_sources_require_review_when_changed_and_never_include_expired_data(db):
    field=custom(db)
    value=change(db,'value',{'field_id':field['id'],'value':6})['record']
    rule=change(db,'rule',{'label':'Приём','text':'С 10 часов'})['record']
    source=knowledge.context(db,'salon','owner')['sources']
    assert all('business_id=salon' in row['href'] for row in source)
    assert not knowledge.changed_sources(db,'salon','owner',source)
    change(db,'field',{**field['payload_json'],'label':'Кресла в зале'},id=field['id'],version=1)
    assert value['id'] in knowledge.changed_sources(db,'salon','owner',source)
    with pytest.raises(knowledge.Conflict):knowledge.require_current_sources(db,'salon','owner',source)
    change(db,'rule',{'label':'Приём','text':'Устаревшее правило','valid_until':'2000-01-01'},id=rule['id'],version=1)
    assert 'Устаревшее' not in knowledge.context(db,'salon','owner')['text']
    assert rule['id'] in knowledge.changed_sources(db,'salon','owner',source)
    doc=knowledge.upload(db,'business','salon',user(),b'Expired document','policy.txt',{'request_id':'expired-doc'})['record']
    change(db,'document',{'confirmed':True,'valid_until':'2000-01-01'},id=doc['id'],version=1)
    assert 'Expired document' not in knowledge.context(db,'salon','owner')['text']


def test_real_concurrent_saves_only_one_version_wins(db):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    import psycopg2
    field=custom(db)
    value=change(db,'value',{'field_id':field['id'],'value':1})['record']
    db.execute('SELECT current_schema()');schema=db.fetchone()[0]
    db.connection.commit()
    barrier=Barrier(2)
    def save(number):
        connection=psycopg2.connect(os.environ['BUSINESS_KNOWLEDGE_TEST_DSN'])
        cursor=connection.cursor();cursor.execute(f'SET search_path TO {schema}')
        try:
            barrier.wait(timeout=10)
            change(cursor,'value',{'field_id':field['id'],'value':number},id=value['id'],version=value['version'])
            connection.commit();return 'saved'
        except knowledge.Conflict:
            connection.rollback();return 'conflict'
        finally:connection.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(save,[2,3]))
    assert sorted(results)==['conflict','saved']
    assert knowledge.read(db,'business','salon',user())['fields'][0]['value_record']['version']==2
    assert len(knowledge.history(db,'business','salon',user(),value['id'])['items'])==2


def test_mixed_templates_keep_existing_values_and_types(db):
    hair=change(db,'template',{'type_key':'beauty_salon','fields':['hair_chairs']})['records'][0]
    change(db,'value',{'field_id':hair['id'],'value':6})
    school=change(db,'template',{'type_key':'school','fields':[item['template_key'] for item in fields('school')]})
    assert school['records']
    db.execute("UPDATE businesses SET business_type='school' WHERE id='salon'")
    data=knowledge.read(db,'business','salon',user())
    assert next(row for row in data['fields'] if row['id']==hair['id'])['value_record']['payload_json']['value']==6
    assert change(db,'template',{'type_key':'beauty_salon','fields':['hair_chairs']})['already_present']==1
    with pytest.raises(ValueError):change(db,'template',{'type_key':'invented_type'})
