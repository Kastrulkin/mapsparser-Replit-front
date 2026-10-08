"""Receipt durability on disposable PostgreSQL; never a proof of provider delivery."""
from datetime import datetime, timedelta, timezone
import pytest
from psycopg2.extras import Json
from tests.test_outreach_continuation_pg import db
from services import content_publish_notifications, operator_audio, business_input_settings


@pytest.fixture
def handoff(db, monkeypatch):
    conn, cursor = db
    cursor.execute('CREATE TABLE social_posts(id TEXT PRIMARY KEY, business_id TEXT, status TEXT, publish_mode TEXT, scheduled_for TIMESTAMPTZ, platform TEXT, platform_text TEXT, metadata_json JSONB, media_json JSONB)')
    cursor.execute('CREATE TABLE telegramcontrolpreferences(user_id TEXT PRIMARY KEY, telegram_id TEXT, notification_preferences_json JSONB)')
    cursor.execute('CREATE TABLE agent_blueprints(id TEXT PRIMARY KEY,business_id TEXT,status TEXT,metadata_json JSONB)')
    cursor.execute('CREATE TABLE agent_blueprint_versions(id TEXT PRIMARY KEY,blueprint_id TEXT,execution_mode TEXT,trigger TEXT,steps_json JSONB)')
    date = datetime.now(timezone.utc) + timedelta(days=1)
    photo = {'id': 'asset', 'storage_path': 's3://bucket/photo.jpg'}
    cursor.execute('INSERT INTO social_posts VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)', ('post', 'b', 'approved', 'manual', date, 'vk', 'Text', Json({}), Json([photo])))
    cursor.execute('INSERT INTO telegramcontrolpreferences VALUES(%s,%s,%s)', ('u', '123', Json({'business:b': {'content_publications': True, 'content_publications_lead_days': 1}})))
    monkeypatch.setattr(operator_audio, 'authorize_actor', lambda *args, **kwargs: ({}, {}))
    monkeypatch.setattr(business_input_settings, 'resolve', lambda *args: {'timezone': 'UTC'})
    conn.commit()
    cursor.execute("SELECT * FROM social_posts WHERE id='post'")
    item = dict(cursor.fetchone())
    item.update(user_id='u', telegram_id='123', scope_type='business', scope_id='b', lead_days='1', selected_photo={'id': 'asset', 'storage_path': 's3://bucket/photo.jpg', 'public_url': '', 'mime_type': 'image/jpeg', 'original_name': ''})
    item['revision'] = content_publish_notifications.handoff_revision(item)
    return conn, cursor, item


def test_committed_intent_survives_rollback_and_blocks_repeat(handoff):
    conn, cursor, item = handoff
    assert content_publish_notifications.claim_handoff_part(conn, item, 'photo')['status'] == 'claimed'
    conn.rollback()
    assert content_publish_notifications.claim_handoff_part(conn, item, 'photo')['status'] == 'uncertain'


def test_receipts_resume_only_unsent_text_and_finalize(handoff):
    conn, cursor, item = handoff
    assert content_publish_notifications.claim_handoff_part(conn, item, 'photo')['status'] == 'claimed'
    content_publish_notifications.finish_handoff_part(conn, item, 'photo', {'success': True, 'message_id': 10})
    assert content_publish_notifications.claim_handoff_part(conn, item, 'photo')['message_id'] == 10
    assert content_publish_notifications.claim_handoff_part(conn, item, 'text:0')['status'] == 'claimed'
    content_publish_notifications.finish_handoff_part(conn, item, 'text:0', {'success': True, 'message_id': 11}, final=True)
    cursor.execute("SELECT metadata_json FROM social_posts WHERE id='post'")
    receipt = cursor.fetchone()['metadata_json']['staff_handoff']['telegram_deliveries']['u']
    assert receipt['sent_at'] and len(receipt['parts']) == 2


def test_edit_cancel_and_pause_fence_unstarted_send(handoff):
    conn, cursor, item = handoff
    cursor.execute("UPDATE social_posts SET platform_text='new' WHERE id='post'")
    assert content_publish_notifications.claim_handoff_part(conn, item, 'photo')['status'] == 'stale'
    conn.rollback()
    cursor.execute("UPDATE social_posts SET status='cancelled' WHERE id='post'")
    assert content_publish_notifications.claim_handoff_part(conn, item, 'photo')['status'] == 'cancelled'
    conn.rollback()
    cursor.execute("UPDATE telegramcontrolpreferences SET notification_preferences_json='{}'")
    assert content_publish_notifications.claim_handoff_part(conn, item, 'photo')['status'] == 'paused'


def test_deterministic_rejection_has_backoff(handoff):
    conn, cursor, item = handoff
    assert content_publish_notifications.claim_handoff_part(conn, item, 'photo')['status'] == 'claimed'
    content_publish_notifications.finish_handoff_part(conn, item, 'photo', {'success': False, 'publish_outcome': 'rejected'})
    assert content_publish_notifications.claim_handoff_part(conn, item, 'photo')['status'] == 'retry_wait'


def alert_schema(cursor):
    cursor.execute('ALTER TABLE users ADD COLUMN telegram_id TEXT')
    cursor.execute("UPDATE users SET is_superadmin=TRUE,telegram_id='999' WHERE id='u2'")
    cursor.execute('ALTER TABLE businesses ADD COLUMN name TEXT, ADD COLUMN timezone TEXT')
    cursor.execute("UPDATE businesses SET name='Salon',timezone='UTC'")
    cursor.execute('CREATE TABLE business_finance_settings(business_id TEXT,timezone TEXT)')
    cursor.execute('CREATE TABLE contentplans(id TEXT,business_id TEXT,period_end DATE,plan_status TEXT,created_at TIMESTAMPTZ)')
    cursor.execute("CREATE TABLE journey_actions(id UUID PRIMARY KEY,business_id TEXT,user_id TEXT,flow_type TEXT,entity_type TEXT,entity_id TEXT,action_type TEXT,title TEXT,description TEXT,cta_label TEXT,cta_target_json JSONB,payload_json JSONB,dedupe_key TEXT,due_at TIMESTAMPTZ,status TEXT DEFAULT 'ready',updated_at TIMESTAMPTZ)")
    cursor.execute("CREATE UNIQUE INDEX uq_journey_actions_active_dedupe ON journey_actions(dedupe_key) WHERE status IN ('ready','in_progress','waiting','blocked')")
    cursor.execute('CREATE TABLE journey_action_notification_deliveries(dedupe_key TEXT PRIMARY KEY,action_id UUID,action_version INT,user_id TEXT,telegram_id TEXT,message_text TEXT,reply_markup_json JSONB,dispatch_state TEXT,attempted_at TIMESTAMPTZ,sent_at TIMESTAMPTZ,provider_message_id TEXT,created_at TIMESTAMPTZ DEFAULT NOW())')


def test_plan_end_is_not_missing_tomorrow_and_alert_is_deduplicated(handoff):
    conn, cursor, item = handoff
    alert_schema(cursor)
    cursor.execute("INSERT INTO contentplans VALUES('plan','b','2026-10-14','generated','2026-09-15')")
    content_publish_notifications.collect_exhausted_content_plan_alerts(conn, now=datetime(2026,10,1,tzinfo=timezone.utc))
    cursor.execute('SELECT COUNT(*) n FROM journey_actions')
    assert cursor.fetchone()['n'] == 0
    for _ in range(2):
        content_publish_notifications.collect_exhausted_content_plan_alerts(conn, now=datetime(2026,10,15,tzinfo=timezone.utc))
    cursor.execute('SELECT COUNT(*) n FROM journey_actions')
    assert cursor.fetchone()['n'] == 1
    cursor.execute("INSERT INTO contentplans VALUES('new-plan','b','2026-11-14','generated','2026-10-15')")
    content_publish_notifications.collect_exhausted_content_plan_alerts(conn, now=datetime(2026,10,16,tzinfo=timezone.utc))
    cursor.execute('SELECT COUNT(*) n FROM journey_actions')
    assert cursor.fetchone()['n'] == 1


def test_admin_alert_unknown_delivery_not_replayed(handoff):
    conn, cursor, item = handoff
    alert_schema(cursor)
    content_publish_notifications.queue_handoff_alert(conn, business_id='b', event_key='missing-photo', message='Check photo')
    conn.commit()
    sends = []
    def send(chat, message):
        sends.append(chat)
        return {'success': False}
    content_publish_notifications.dispatch_handoff_alerts(conn, send_text=send)
    content_publish_notifications.dispatch_handoff_alerts(conn, send_text=send)
    assert sends == ['999']
    cursor.execute('SELECT status FROM journey_actions')
    assert cursor.fetchone()['status'] == 'blocked'


def test_completed_plan_alert_is_not_created_or_sent_again(handoff):
    conn, cursor, item = handoff
    alert_schema(cursor)
    sends = []
    for _ in range(2):
        content_publish_notifications.queue_handoff_alert(conn, business_id='b', event_key='plan-ended:one', message='Plan ended')
        conn.commit()
        content_publish_notifications.dispatch_handoff_alerts(conn, send_text=lambda chat, text: sends.append(chat) or {'success': True, 'message_id': 10})
    assert sends == ['999']
    cursor.execute('SELECT COUNT(*) n FROM journey_actions')
    assert cursor.fetchone()['n'] == 1
    cursor.execute('SELECT COUNT(*) n FROM journey_action_notification_deliveries')
    assert cursor.fetchone()['n'] == 1


def test_future_plan_does_not_cancel_current_plan(handoff):
    conn, cursor, item = handoff
    cursor.execute('CREATE TABLE contentplans(id TEXT,business_id TEXT,period_start DATE,period_end DATE,plan_status TEXT,created_at TIMESTAMPTZ)')
    cursor.execute("INSERT INTO contentplans VALUES('current','b','2026-09-15','2026-10-14','generated','2026-09-15'),('next','b','2026-10-15','2026-11-14','generated','2026-09-30')")
    post = {**item, 'content_plan_id': 'current', 'scheduled_for': datetime(2026,10,2,tzinfo=timezone.utc)}
    assert content_publish_notifications.handoff_plan_current(cursor, post)
    assert not content_publish_notifications.handoff_plan_current(cursor, {**post, 'scheduled_for': datetime(2026,10,15,tzinfo=timezone.utc)})
    cursor.execute("UPDATE contentplans SET plan_status='archived' WHERE id='current'")
    assert not content_publish_notifications.handoff_plan_current(cursor, post)


def test_extra_platform_does_not_invalidate_required_kit(handoff):
    conn, cursor, item = handoff
    cursor.execute('ALTER TABLE social_posts ADD COLUMN content_plan_item_id TEXT')
    cursor.execute("UPDATE social_posts SET content_plan_item_id='entry'")
    for platform in ('telegram','max','instagram'):
        cursor.execute("INSERT INTO social_posts SELECT %s,business_id,status,publish_mode,scheduled_for,%s,platform_text,metadata_json,media_json,content_plan_item_id FROM social_posts WHERE id='post'", (platform,platform))
    post = {**item, 'content_plan_item_id': 'entry', 'required_platforms': ['vk','telegram','max']}
    assert content_publish_notifications.handoff_kit_complete(cursor, post, lambda photo: True)
    cursor.execute("UPDATE social_posts SET status='needs_review' WHERE platform='max'")
    assert not content_publish_notifications.handoff_kit_complete(cursor, post, lambda photo: True)


def test_platform_selection_is_rechecked_before_each_part(handoff):
    conn,cur,item=handoff
    cur.execute('ALTER TABLE businesses ADD COLUMN name TEXT,ADD COLUMN address TEXT,ADD COLUMN timezone TEXT')
    cur.execute("UPDATE businesses SET name='Salon',timezone='UTC'")
    cur.execute('CREATE TABLE business_finance_settings(business_id TEXT,timezone TEXT)')
    cur.execute('ALTER TABLE social_posts ADD COLUMN content_plan_item_id TEXT,ADD COLUMN created_at TIMESTAMPTZ DEFAULT NOW()')
    cur.execute("UPDATE social_posts SET content_plan_item_id='entry'")
    cur.execute("INSERT INTO social_posts SELECT 'tg',business_id,status,publish_mode,scheduled_for,'telegram',platform_text,metadata_json,media_json,content_plan_item_id,created_at FROM social_posts WHERE id='post'")
    def platforms(values):
        cur.execute("UPDATE telegramcontrolpreferences SET notification_preferences_json=%s",(Json({'business:b':{'content_publications':True,'content_publications_lead_days':1,'content_publications_platforms':values}}),))
        conn.commit()
    platforms(['vk'])
    collected=content_publish_notifications.collect_due_content_publish_handoffs(conn)
    assert [post['platform'] for post in collected]==['vk']
    platforms(['vk','telegram'])
    collected=content_publish_notifications.collect_due_content_publish_handoffs(conn)
    telegram=next(post for post in collected if post['platform']=='telegram')
    platforms(['vk'])
    assert content_publish_notifications.claim_handoff_part(conn,telegram,'photo')['status']=='paused'
