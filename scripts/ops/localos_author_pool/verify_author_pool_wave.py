"""Verify exact Sent copies, then reconcile canonical creator history once.
Contact details and provider identifiers stay in the authorized server CRM.
"""
import argparse
import json
import hashlib
import re
from datetime import datetime, timedelta, timezone
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses
from psycopg2.extras import RealDictCursor, Json
from pg_db_utils import get_db_connection
from services.outreach_email_adapter import _imap_connection, _close_imap, _sent_mailbox, _imap_mailbox_argument, _text, load_mailbox_config
from services.creator_portal_service import add_contact_event, ensure_relationship
from services.outreach_yougile_sync_service import enqueue_touch_sent_projection

SENDER='912646e4-1c3f-45d8-91da-e6080eef23db'
CAMPAIGN='d70b2a83-fb15-4caf-95c3-98b85197d191'
parser=argparse.ArgumentParser(); parser.add_argument('--commit',action='store_true')
parser.add_argument('--wave',default='/tmp/localos-author-pool-wave-result.json')
parser.add_argument('--output',default='/tmp/localos-author-pool-provider-proof.json')
args=parser.parse_args()
with open(args.wave,encoding='utf-8') as handle: wave=json.load(handle)
conn=get_db_connection(); client=None; proofs=[]; failures=0; projection_count=0
try:
    cur=conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('SELECT * FROM outreach_sender_accounts WHERE id=%s',(SENDER,)); sender=dict(cur.fetchone())
    cur.execute("""SELECT q.id,q.delivery_status,q.provider_message_id,q.sent_at,q.recipient_value,q.sender_account_id,
        q.workstream_id,t.id AS touch_id,t.subject,t.generated_text,cc.id AS candidate_id,cc.creator_profile_id,
        c.last_reply_at
        FROM outreachsendqueue q JOIN outreach_campaign_touches t ON t.id=q.campaign_touch_id
        JOIN outreach_campaigns c ON c.id=t.campaign_id JOIN creator_campaign_candidates cc ON cc.outreach_campaign_id=c.id
        WHERE q.id::text=ANY(%s::text[]) AND cc.campaign_id=%s""",([r['queue_id'] for r in wave['records']],CAMPAIGN))
    records=[dict(r) for r in cur.fetchall()]; conn.rollback()
    client=_imap_connection(load_mailbox_config(sender),timeout=30)
    status,_=client.select(_imap_mailbox_argument(_sent_mailbox(client)),readonly=True)
    if _text(status).upper()!='OK': raise RuntimeError('sent_folder_unavailable')
    for row in records:
        if row['delivery_status'] not in {'sent','delivered'}: continue
        mid=row['provider_message_id']
        if not mid or not re.fullmatch(r'<[^<>\s"\\]+@[^<>\s"\\]+>',mid):
            failures+=1; continue
        status,data=client.uid('search',None,'HEADER','Message-ID','"'+mid+'"')
        ids=data[0].split() if _text(status).upper()=='OK' and data and data[0] else []
        if len(ids)!=1: failures+=1; continue
        status,data=client.uid('fetch',ids[0],'(UID BODY.PEEK[])')
        pairs=[v for v in data or [] if isinstance(v,tuple) and len(v)==2]
        if _text(status).upper()!='OK' or len(pairs)!=1: failures+=1; continue
        message=BytesParser(policy=policy.default).parsebytes(pairs[0][1])
        addresses=lambda field:{a.lower() for _,a in getaddresses(message.get_all(field,[]))}
        texts=[p for p in message.walk() if p.get_content_type()=='text/plain' and p.get_content_disposition()!='attachment']
        body=texts[0].get_content().replace('\r\n','\n') if len(texts)==1 else ''
        if body.endswith('\n'): body=body[:-1]
        good=(addresses('From')=={'localosgo@gmail.com'} and addresses('To')=={row['recipient_value'].lower()}
              and not addresses('Cc') and not addresses('Bcc') and message.get('Message-ID')==mid
              and message.get('Subject')==row['subject'] and body==row['generated_text']
              and str(row['sender_account_id'])==SENDER)
        if not good: failures+=1; continue
        proof={'queue_id':str(row['id']),'provider_message_id':mid,'sent_at':row['sent_at'].isoformat(),
               'sent_uid':ids[0].decode(),'evidence_kind':'provider_observed','body_sha256':hashlib.sha256(body.encode()).hexdigest()}
        proofs.append(proof)
        if not args.commit: continue
        add_contact_event(cur,profile_id=str(row['creator_profile_id']),event_type='sent',channel='email',body=body,
            contact=row['recipient_value'],source='native_email_sent_verification',campaign_id=CAMPAIGN,
            provider_message_id=mid,occurred_at=row['sent_at'],metadata=proof)
        ensure_relationship(cur,str(row['creator_profile_id']))
        cur.execute("""UPDATE creator_relationships SET stage='contacted',primary_channel='email',contact_value=%s,
            last_contacted_at=GREATEST(last_contacted_at,%s),status_reason='Первое приглашение LocalOS отправлено; подтверждено в Gmail Sent',updated_at=NOW()
            WHERE creator_profile_id=%s AND last_replied_at IS NULL AND stage IN ('discovered','contact_ready','contacted')""",
            (row['recipient_value'],row['sent_at'],row['creator_profile_id']))
        cur.execute("UPDATE creator_campaign_candidates SET status='invited',updated_at=NOW() WHERE id=%s AND status='invitation_ready'",(row['candidate_id'],))
        if row['last_reply_at'] is None:
            cur.execute("""UPDATE lead_workstreams SET last_contact_at=%s,last_contact_channel='email',
                next_action_at=COALESCE(next_action_at,%s),next_step='Проверить ответ на приглашение автора LocalOS',updated_at=NOW()
                WHERE id=%s AND (last_contact_at IS NULL OR last_contact_at<=%s)""",
                (row['sent_at'],row['sent_at']+timedelta(days=4),row['workstream_id'],row['sent_at']))
        if enqueue_touch_sent_projection(cur,queue_id=str(row['id'])): projection_count+=1
    if args.commit: conn.commit()
    else: conn.rollback()
    encoded=json.dumps({'checked_at':datetime.now(timezone.utc).isoformat(),'proofs':proofs,'verification_failures':failures,'yougile_projections':projection_count,'crm_committed':args.commit},ensure_ascii=False)
    with open(args.output,'w',encoding='utf-8') as handle: handle.write(encoded)
    print(json.dumps({'verified_sent':len(proofs),'verification_failures':failures,'crm_committed':args.commit,
                      'yougile_projections':projection_count,'proof_sha256':hashlib.sha256(encoded.encode()).hexdigest()}),flush=True)
finally:
    _close_imap(client); conn.close()
