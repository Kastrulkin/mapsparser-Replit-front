"""Queue review digests through the existing journey notification outbox."""
import json
import os
import uuid
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from services import work_review
from services.operator_conversations import _row


def digest_enabled(business, settings):
    legacy={value.strip() for value in os.getenv('OPERATOR_WORK_REVIEW_BUSINESS_IDS','').split(',') if value.strip()}
    return settings.get('enabled', business in legacy) is True


def recipient_allowed(cursor,business,user,entity_type="work_digest"):
    if not work_review.enabled(business):return False
    try:
        if entity_type=='work_observation':
            work_review.work_journal.scope(cursor,business,user,write=True)
            return True
        work_review.work_journal.scope(cursor,business,user,write=True)
        cursor.execute('SELECT enabled FROM business_work_digest_settings WHERE business_id=%s',(business,))
        if not digest_enabled(business,_row(cursor,cursor.fetchone())):return False
        return work_review.can_review(cursor,business,user)
    except PermissionError:return False


def collect(cursor,now=None):
    from services.business_input_settings import resolve
    from services.team_work_access import rolled_out
    legacy_businesses={value.strip() for value in os.getenv('OPERATOR_WORK_REVIEW_BUSINESS_IDS','').split(',') if value.strip()}
    if not legacy_businesses and not rolled_out():return
    moment=now or datetime.now(timezone.utc)
    if not work_review.available(cursor):return
    cursor.execute('SELECT DISTINCT business_id FROM business_work_journal WHERE NOT is_voided')
    businesses=[row['business_id'] for row in [_row(cursor,value) for value in cursor.fetchall()]]
    for business in businesses:
        if not work_review.enabled(business):continue
        cursor.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('work-digest:'+business,))
        zone=resolve(cursor,business).get('timezone')
        cursor.execute('SELECT * FROM business_work_digest_settings WHERE business_id=%s',(business,))
        settings=_row(cursor,cursor.fetchone())
        # Opening team work for everyone must not subscribe existing clients to sends.
        if not digest_enabled(business,settings):continue
        cursor.execute('SELECT owner_id user_id FROM businesses WHERE id=%s UNION SELECT user_id FROM business_work_reviewers WHERE business_id=%s AND enabled',(business,business))
        recipients=[row['user_id'] for row in [_row(cursor,value) for value in cursor.fetchall()]]
        for user in recipients:
            if not recipient_allowed(cursor,business,user):continue
            cursor.execute("SELECT id,created_at FROM business_work_journal WHERE business_id=%s AND urgent AND NOT is_voided AND review_status='new' AND created_at>=%s",(business,moment-timedelta(days=1)))
            urgent=[_row(cursor,value) for value in cursor.fetchall()]
            for row in urgent:
                queue(cursor,business,user,'urgent:'+row['id'],'Срочное наблюдение сотрудника','Сотрудник отметил запись как срочную. Откройте рабочий журнал для разбора.',moment,{'entry_id':row['id']})
            if not zone:continue
            local=moment.astimezone(ZoneInfo(zone));at=settings.get('local_time') or time(18)
            cutoff=datetime.combine(local.date(),at,ZoneInfo(zone))
            if local<cutoff:continue
            cursor.execute("SELECT MAX((payload_json->>'cutoff')::timestamptz) cutoff FROM journey_actions WHERE business_id=%s AND user_id=%s AND entity_type='work_digest' AND jsonb_exists(payload_json,'cutoff')",(business,user))
            previous=_row(cursor,cursor.fetchone()).get('cutoff') or cutoff-timedelta(days=1)
            cursor.execute('SELECT COUNT(*) n FROM business_work_journal WHERE business_id=%s AND NOT is_voided AND created_at<=%s AND (%s IS NULL OR created_at>%s)',(business,cutoff,previous,previous))
            count=_row(cursor,cursor.fetchone())['n']
            if count:queue(cursor,business,user,'daily:'+local.date().isoformat(),'Новые рабочие наблюдения: '+str(count),'Разберите новые записи сотрудников в рабочем журнале.',moment,{'cutoff':cutoff.isoformat()})


def queue(cursor,business,user,key,title,description,due,payload):
    dedupe='work-review:'+business+':'+user+':'+key
    cursor.execute('SELECT id FROM journey_actions WHERE dedupe_key=%s',(dedupe,))
    if cursor.fetchone():return
    cursor.execute('''INSERT INTO journey_actions(id,business_id,user_id,flow_type,entity_type,entity_id,action_type,title,description,cta_label,cta_target_json,payload_json,dedupe_key,due_at)
        VALUES (%s,%s,%s,'work_journal','work_digest',%s,'review_digest',%s,%s,'Разобрать наблюдения',%s::jsonb,%s::jsonb,%s,NOW())''',
        (str(uuid.uuid4()),business,user,business,title,description,json.dumps({'href':'/dashboard/work-journal'}),json.dumps(payload),dedupe))
