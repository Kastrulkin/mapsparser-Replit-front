"""Selected post photos reuse business library bounds; no provider or writes to production."""
import os,uuid,json
import pytest,psycopg2
from psycopg2.extras import RealDictCursor
from services import operator_mobile_modules

@pytest.fixture
def library(monkeypatch):
 dsn=os.getenv('OPERATOR_VOICE_TEST_DSN')
 if not dsn:pytest.skip('Disposable PostgreSQL DSN required')
 conn=psycopg2.connect(dsn,cursor_factory=RealDictCursor);c=conn.cursor();schema='saved_content_'+uuid.uuid4().hex;c.execute('CREATE SCHEMA '+schema);c.execute('SET search_path TO '+schema)
 c.execute('CREATE TABLE businesses(id TEXT PRIMARY KEY,name TEXT,network_id TEXT)')
 c.execute("INSERT INTO businesses VALUES ('b','Business','n'),('n','Network','n'),('sibling','Sibling','n'),('foreign','Foreign',NULL)")
 c.execute('CREATE TABLE contentplans(id TEXT PRIMARY KEY,business_id TEXT,title TEXT,period_days INTEGER,created_at TIMESTAMPTZ DEFAULT NOW(),plan_status TEXT)')
 c.execute("INSERT INTO contentplans VALUES ('p','b','Saved plan',30,NOW(),'generated'),('foreign-plan','foreign','Foreign',30,NOW(),'generated')")
 c.execute("CREATE TABLE contentplanitems(id UUID PRIMARY KEY,business_id TEXT,theme TEXT,goal TEXT,draft_text TEXT,status TEXT,updated_at TIMESTAMPTZ DEFAULT NOW(),plan_id TEXT,scheduled_for TIMESTAMPTZ,content_type TEXT,metadata_json JSONB DEFAULT '{}')")
 c.execute("CREATE TABLE photo_assets(id UUID PRIMARY KEY,business_id TEXT,metadata_json JSONB DEFAULT '{}',category TEXT DEFAULT 'product')")
 c.execute('CREATE TABLE photo_asset_usage_events(id UUID PRIMARY KEY,target_id TEXT,business_id TEXT,photo_asset_id UUID,usage_type TEXT,target_platform TEXT,created_at TIMESTAMPTZ DEFAULT NOW())')
 def exists(cursor,name):cursor.execute('SELECT to_regclass(%s) value',(name,));return bool(cursor.fetchone()['value'])
 monkeypatch.setattr(operator_mobile_modules,'_table_exists',exists)
 yield c
 conn.rollback();conn.close()

@pytest.mark.parametrize('owner,metadata,category,allowed',[('b',{},'product',True),('n',{},'product',True),('sibling',{},'product',False),('foreign',{},'product',False),('b',{'disk_import_available':False},'product',False),('b',{},'document',False)])
def test_saved_post_photo_is_scoped_to_own_or_parent_library(library,owner,metadata,category,allowed):
 c=library;photo=str(uuid.uuid4());item=str(uuid.uuid4());c.execute('INSERT INTO photo_assets VALUES(%s,%s,%s::jsonb,%s)',(photo,owner,json.dumps(metadata),category))
 c.execute("INSERT INTO contentplanitems(id,business_id,theme,draft_text,status,plan_id,content_type,metadata_json) VALUES(%s,'b','Existing post','Existing text','draft','p','news',%s::jsonb)",(item,json.dumps({'selected_photo_asset_id':photo})))
 c.execute("INSERT INTO contentplanitems(id,business_id,theme,plan_id) VALUES(%s,'foreign','Private post','foreign-plan')",(str(uuid.uuid4()),))
 rows=operator_mobile_modules._content(c,{'kind':'business','business_ids':['b']})
 assert len(rows)==1 and rows[0]['draft_text']=='Existing text'
 assert rows[0]['selected_photo_asset_id']==(photo if allowed else None)
 assert 'metadata_json' not in rows[0]

def test_manual_selection_journal_overrides_older_metadata_without_rewriting_plan(library):
 c=library;old=str(uuid.uuid4());new=str(uuid.uuid4());item=str(uuid.uuid4())
 for photo in [old,new]:c.execute("INSERT INTO photo_assets(id,business_id) VALUES(%s,'b')",(photo,))
 c.execute("INSERT INTO contentplanitems(id,business_id,theme,draft_text,plan_id,metadata_json) VALUES(%s,'b','Saved','Keep exact text','p',%s::jsonb)",(item,json.dumps({'selected_photo_asset_id':old})))
 c.execute("INSERT INTO photo_asset_usage_events VALUES(%s,%s,'b',%s,'publication',NULL,NOW())",(str(uuid.uuid4()),item,new))
 assert operator_mobile_modules._content(c,{'kind':'business','business_ids':['b']})[0]['selected_photo_asset_id']==new
 c.execute('SELECT draft_text,metadata_json FROM contentplanitems WHERE id=%s',(item,));row=c.fetchone();assert row['draft_text']=='Keep exact text' and row['metadata_json']['selected_photo_asset_id']==old
