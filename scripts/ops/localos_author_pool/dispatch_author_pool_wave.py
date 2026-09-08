"""Dispatch only a server-local approved wave, using normal gates and delay.
No emails, CRM IDs or provider IDs are exported; detailed proof stays on server.
"""
import json
import argparse
import hashlib
import time
from datetime import datetime, timezone
from pg_db_utils import get_db_connection
from psycopg2.extras import RealDictCursor
from services.outreach_email_reply_service import sync_email_replies
from services.outreach_dispatch_service import dispatch_due_outreach_queue
from api import admin_prospecting as settings

SENDER='912646e4-1c3f-45d8-91da-e6080eef23db'
parser=argparse.ArgumentParser()
parser.add_argument('--wave',default='/tmp/localos-author-pool-wave-result.json')
parser.add_argument('--output',default='/tmp/localos-author-pool-dispatch-result.json')
args=parser.parse_args()
PATH=args.wave
with open(PATH,encoding='utf-8') as handle:
    wave=json.load(handle)
if wave.get('mode')!='commit':
    raise RuntimeError('wave_not_committed')
results=[]
synced_at=None
for index,row in enumerate(wave['records']):
    conn=get_db_connection()
    try:
        cur=conn.cursor(cursor_factory=RealDictCursor)
        cur.execute('SELECT delivery_status,sender_account_id,channel FROM outreachsendqueue WHERE id=%s',(row['queue_id'],))
        item=dict(cur.fetchone() or {})
        conn.rollback()
    finally:
        conn.close()
    if str(item.get('sender_account_id'))!=SENDER or item.get('channel')!='email':
        raise RuntimeError('wave_sender_changed')
    if item.get('delivery_status') in {'sent','delivered'}:
        results.append({'queue_id':row['queue_id'],'already_sent':True})
        continue
    if item.get('delivery_status')!='queued':
        results.append({'queue_id':row['queue_id'],'status':item.get('delivery_status'),'skipped':True})
        continue
    if synced_at is None or (datetime.now(timezone.utc)-synced_at).total_seconds()>85:
        sync_started=datetime.now(timezone.utc)
        sync=sync_email_replies(sender_limit=1,sender_account_id=SENDER,complete_window_limit=20000)
        if not sync.get('success') or int(sync.get('failed') or 0):
            print(json.dumps({'stage':'reply_sync_failed','sent_in_run':sum(int(r.get('sent') or 0) for r in results)}),flush=True)
            break
        synced_at=sync_started
        print(json.dumps({'stage':'reply_sync_complete','imported':sync.get('imported'),'failed':sync.get('failed')}),flush=True)
    conn=get_db_connection()
    try:
        cur=conn.cursor()
        cur.execute("UPDATE outreachsendqueue SET scheduled_at=NOW(),updated_at=NOW() WHERE id=%s AND sender_account_id=%s AND delivery_status='queued'",(row['queue_id'],SENDER))
        conn.commit()
    finally:
        conn.close()
    dispatched=dispatch_due_outreach_queue(batch_size=1,batch_id=row['batch_id'],queue_id=row['queue_id'],force_ready=False,author_reply_sync_started_at=synced_at)
    results.append({'queue_id':row['queue_id'],**dispatched})
    print(json.dumps({'stage':'dispatch','index':index+1,'sent':dispatched.get('sent'),'blocked':dispatched.get('blocked'),'failed':dispatched.get('failed'),'retry':dispatched.get('retry')}),flush=True)
    if int(dispatched.get('failed') or 0) or int(dispatched.get('retry') or 0):
        break
    if index+1<len(wave['records']):
        # Preserve configured provider pacing even though queue IDs are isolated.
        time.sleep(settings.OUTREACH_SEND_DELAY_MAX_SEC)
encoded=json.dumps({'results':results,'completed_at':datetime.now(timezone.utc).isoformat()},ensure_ascii=False,default=str)
with open(args.output,'w',encoding='utf-8') as handle:
    handle.write(encoded)
print(json.dumps({'stage':'completed','processed':len(results),'sent_in_run':sum(int(r.get('sent') or 0) for r in results),'result_sha256':hashlib.sha256(encoded.encode()).hexdigest()}),flush=True)
