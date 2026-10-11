from copy import deepcopy
from datetime import date, datetime, timezone
from psycopg2.extras import Json
from tests.test_content_handoff_pg import handoff, alert_schema
from tests.test_outreach_continuation_pg import db
from services import content_network_renewal
from services.content_publish_notifications import _selected_photos, handoff_revision


def test_completion_is_per_branch_and_durable_once_after_both_recipients(handoff):
    conn, cursor, _ = handoff
    alert_schema(cursor)
    cursor.execute('ALTER TABLE businesses ADD COLUMN address TEXT')
    cursor.execute('ALTER TABLE agent_blueprints ADD COLUMN compiled_approved_version_id TEXT')
    cursor.execute("INSERT INTO agent_blueprints VALUES ('pilot','b','active','{}','v')")
    cursor.execute('ALTER TABLE social_posts ADD COLUMN content_plan_item_id TEXT, ADD COLUMN content_plan_id TEXT')
    cursor.execute('CREATE TABLE contentplanitems(id TEXT PRIMARY KEY,plan_id TEXT,business_id TEXT,scheduled_for DATE,status TEXT,theme TEXT)')
    for business in ['b','b2']:
        cursor.execute("INSERT INTO contentplanitems VALUES(%s,%s,%s,%s,'approved','Theme')", ('item-'+business,'plan-'+business,business,date(2026,11,1)))
        for platform in ['telegram','vk','max']:
            post_id = business+'-'+platform
            cursor.execute("INSERT INTO social_posts(id,business_id,status,publish_mode,scheduled_for,platform,platform_text,metadata_json,media_json,content_plan_item_id,content_plan_id) VALUES(%s,%s,'approved','api',%s,%s,'Text','{}',%s,%s,%s)",
                           (post_id,business,datetime(2026,11,1,tzinfo=timezone.utc),platform,Json([{'id':'photo','storage_path':'s3://bucket/file.jpg'}]),'item-'+business,'plan-'+business))
            cursor.execute('SELECT * FROM social_posts WHERE id=%s',(post_id,))
            post=cursor.fetchone()
            post['selected_photos']=_selected_photos(cursor,post)
            receipt={'sent_at':'2026-10-31','revision':handoff_revision(post),'parts':{'photo:0':{'status':'sent'},'text:0':{'status':'sent'}}}
            receipts={'u':deepcopy(receipt),'u2':deepcopy(receipt)}
            if business=='b2':
                receipts['u']['parts']['text:0']['status']='uncertain'
            cursor.execute('UPDATE social_posts SET metadata_json=%s WHERE id=%s',(Json({'staff_handoff':{'telegram_deliveries':receipts}}),post_id))
    scope={'business_ids':['b','b2'],'recipient_user_ids':['u','u2'],'platforms':['telegram','vk','max'],
           'plan_ids':{'b':['plan-b'],'b2':['plan-b2']},'timezone':'UTC','renewal':{'period_days':30,'reviewer_user_id':'u2'}}
    contract={'version':2,'scope':scope}
    for _ in range(2):
        jobs=content_network_renewal.enqueue_completed_plans(conn,contract,blueprint_id='pilot',version_id='v')
        conn.commit()
        assert len(jobs)==1
    cursor.execute('SELECT payload_json FROM operator_async_jobs')
    jobs=cursor.fetchall()
    assert len(jobs)==1 and jobs[0]['payload_json']['previous_plan_id']=='plan-b'
    cursor.execute('SELECT COUNT(*) count FROM journey_action_notification_deliveries')
    assert cursor.fetchone()['count']==2  # completion for b; reconciliation warning for b2
    cursor.execute("UPDATE social_posts SET metadata_json=jsonb_set(metadata_json,'{staff_handoff,telegram_deliveries,u,parts,text:0,status}','\"sent\"') WHERE business_id='b2'")
    for _ in range(2):
        assert len(content_network_renewal.enqueue_completed_plans(conn,contract,blueprint_id='pilot',version_id='v'))==2
        conn.commit()
    cursor.execute('SELECT COUNT(*) count FROM operator_async_jobs')
    assert cursor.fetchone()['count']==2
    cursor.execute('SELECT COUNT(*) count FROM journey_action_notification_deliveries')
    assert cursor.fetchone()['count']==3
    cursor.execute("UPDATE agent_blueprints SET status='draft' WHERE id='pilot'")
    assert not content_network_renewal.enqueue_completed_plans(conn,contract,blueprint_id='pilot',version_id='v')


def test_successor_context_has_exact_previous_plan_not_newest_other_plan(handoff):
    conn,cursor,_=handoff
    cursor.execute('CREATE TABLE contentplans(id TEXT,business_id TEXT,plan_status TEXT)')
    cursor.execute('CREATE TABLE contentplanitems(id TEXT,plan_id TEXT,business_id TEXT,scheduled_for DATE,status TEXT,theme TEXT)')
    cursor.execute("INSERT INTO contentplans VALUES ('previous','b','generated'),('other','b2','generated')")
    cursor.execute("INSERT INTO contentplanitems VALUES ('i','previous','b',CURRENT_DATE+10,'approved','Old theme'),('j','previous','b',CURRENT_DATE+13,'approved','Another theme')")
    context=content_network_renewal.resolve_successor_context(cursor,'b',{'previous_plan_id':'previous','timezone':'UTC','channels':['vk']})
    assert context['channels']==['vk'] and len(context['dates'])==10
    assert set(context['excluded_themes'])=={'Old theme','Another theme'}


def test_only_explicitly_reviewed_lineage_is_connected(handoff):
    conn,cursor,_=handoff
    cursor.execute('CREATE TABLE contentplans(id TEXT,business_id TEXT,plan_status TEXT,generated_plan_json JSONB)')
    approval={'blueprint_id':'pilot','version_id':'v','approved_by_user_id':'u2'}
    cursor.execute("INSERT INTO contentplans VALUES ('root','b','generated','{}'),('unreviewed','b','generated',%s),('reviewed','b','generated',%s),('foreign','b2','generated',%s)",
        (Json({'meta':{'previous_plan_id':'root'}}),Json({'meta':{'previous_plan_id':'root','handoff_approval':approval}}),Json({'meta':{'previous_plan_id':'root','handoff_approval':approval}})))
    scope={'plan_ids':{'b':['root']},'renewal':{'reviewer_user_id':'u2'}}
    assert content_network_renewal.approved_plan_ids(cursor,scope,'b','pilot','v')==['reviewed','root']
    assert content_network_renewal.approved_plan_ids(cursor,scope,'b','pilot','new-version')==['root']
