"""Execute a reviewed server-local creator selection using existing services.

No contact export. Sources are reused with their original dates. No fake human
message approvals. --commit queues exact v2 messages under the existing grant;
provider dispatch is separate and retains all normal runtime gates.
"""
import argparse
import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses
from psycopg2.extras import Json, RealDictCursor
from pg_db_utils import get_db_connection
from services.author_template_authorization_service import load_author_template_authorization, previously_contacted_author
from services.creator_promotion_service import prepare_candidate_outreach
from services.outreach_campaign_service import build_preview, persist_preview, approve_campaign_by_author_template
from services.outreach_email_adapter import _imap_connection, _close_imap, _sent_mailbox, _special_use_mailbox, _imap_mailbox_argument, _text, load_mailbox_config
from services.creator_catalog_service import _stable_evidence_key

CAMPAIGN = 'd70b2a83-fb15-4caf-95c3-98b85197d191'
SENDER = '912646e4-1c3f-45d8-91da-e6080eef23db'
ACTOR = 'a453a8b3-3b26-4c4e-81e3-1b973d4b8755'
os.environ['OUTREACH_ROOM_SYNC_ENABLED'] = 'false'

def log(kind, **fields):
    # Production selection and provider IDs stay server-local. Only counts and
    # hashes leave this process; no alternative export of a blocked data list.
    safe={k:v for k,v in fields.items() if k in {'complete','addresses','existing_history','folders','selected','skipped_count','commit','mode','prepared','sent','failed','reason_code','reason_codes','sha256','path'}}
    print(json.dumps({'kind':kind, **safe},ensure_ascii=False,default=str),flush=True)

def provider_history(sender, records):
    """Address search in batches, exact parsed headers, all-time; no mailbox dump."""
    emails = sorted({r['email'].strip().lower() for r in records})
    assert all(re.fullmatch(r'[A-Za-z0-9.!#$%&\x27*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+',e) for e in emails)
    client = None
    seen = set()
    folders = []
    try:
        client = _imap_connection(load_mailbox_config(sender), timeout=30)
        mailbox_specs = [(_sent_mailbox(client),'TO'),(_special_use_mailbox(client,b'\\All'),'FROM'),
                         (_special_use_mailbox(client,b'\\Junk'),'FROM'),(_special_use_mailbox(client,b'\\Trash'),'FROM')]
        for folder, header in mailbox_specs:
            status, _ = client.select(_imap_mailbox_argument(folder), readonly=True)
            if _text(status).upper() != 'OK':
                raise RuntimeError('provider_history_folder_unavailable')
            ids = set()
            for offset in range(0,len(emails),20):
                group = emails[offset:offset+20]
                criteria = ['OR']*(len(group)-1)
                for address in group:
                    criteria += [header,'"'+address+'"']
                status, data = client.uid('search',None,*criteria)
                if _text(status).upper() != 'OK':
                    raise RuntimeError('provider_history_search_incomplete')
                ids.update(uid for chunk in data or [] if isinstance(chunk,bytes) for uid in chunk.split())
            if len(ids)>2000:
                raise RuntimeError('provider_history_requires_separate_thread_review')
            ids = sorted(ids,key=int)
            checked=0
            for offset in range(0,len(ids),50):
                status,data = client.uid('fetch',b','.join(ids[offset:offset+50]),'(UID BODY.PEEK[HEADER.FIELDS (FROM TO MESSAGE-ID)])')
                if _text(status).upper()!='OK':
                    raise RuntimeError('provider_history_headers_incomplete')
                pairs=[v for v in data or [] if isinstance(v,tuple) and len(v)==2]
                if len(pairs)!=len(ids[offset:offset+50]):
                    raise RuntimeError('provider_history_header_count_mismatch')
                for metadata,raw in pairs:
                    message=BytesParser(policy=policy.default).parsebytes(raw)
                    addresses={a.lower() for _,a in getaddresses(message.get_all(header,[]))}
                    seen.update(addresses.intersection(emails))
                    checked+=1
            folders.append({'role':'sent' if header=='TO' else 'incoming','matched_messages':checked})
        log('provider_history',complete=True,addresses=len(emails),existing_history=len(seen),folders=folders)
        return seen
    finally:
        _close_imap(client)

def ensure_saved_channel_evidence(cur, pid, channel_id, source, proof):
    """Normalize an existing verified observation, never claim a new inspection."""
    identity=(source['channel_metadata'] or {}).get('observed_identity') or {}
    title=str(identity.get('title') or '').strip()
    observed=source.get('channel_observed_at'); verified=source.get('channel_verified_at')
    if not title or not observed or not verified:
        raise ValueError('saved_channel_snapshot_or_original_time_missing')
    if observed.tzinfo is None or verified.tzinfo is None:
        raise ValueError('saved_channel_timestamp_timezone_missing')
    times=[observed,verified]
    for key in ('observed_at','researched_at'):
        if not proof.get(key): continue
        try:
            value=datetime.fromisoformat(str(proof[key]).replace('Z','+00:00'))
        except ValueError:
            raise ValueError('saved_contact_timestamp_invalid')
        if value.tzinfo is None: raise ValueError('saved_contact_timestamp_timezone_missing')
        times.append(value)
    if max(times)>datetime.now(timezone.utc): raise ValueError('saved_observation_time_in_future')
    observed=min(times); stale_after=observed+timedelta(days=90)
    if stale_after<=datetime.now(timezone.utc): raise ValueError('saved_channel_observation_expired')
    confidence=float(proof.get('confidence') or 0)
    if not 0.7<=confidence<=1: raise ValueError('saved_contact_confidence_insufficient')
    summary=f'Ранее сохранённый подтверждённый профиль «{title}». Публичный email сохранён с привязкой к этому каналу. Новая проверка источника не проводилась.'
    key=_stable_evidence_key(pid,source['canonical_url'],summary)
    cur.execute("SELECT id,observed_at,stale_after,confidence FROM creator_evidence WHERE creator_profile_id=%s AND metadata_json->>'catalog_evidence_key'=%s",(pid,key))
    existing=cur.fetchone()
    if existing:
        existing=dict(existing)
        if existing['stale_after']<=datetime.now(timezone.utc): raise ValueError('stored_snapshot_evidence_expired')
        return str(existing['id']),existing['observed_at'],existing['stale_after'],existing['confidence']
    evidence_id=str(uuid.uuid4())
    metadata={'catalog_evidence_key':key,'import_source':'stored_verified_channel_snapshot',
        'source_channel_id':channel_id,'observed_identity':identity,'public_contact_proof':proof,
        'channel_observed_at':source['channel_observed_at'].isoformat(),
        'channel_verified_at':source['channel_verified_at'].isoformat(),
        'original_observed_at':observed.isoformat(),'network_research_performed':False}
    cur.execute("""INSERT INTO creator_evidence(id,creator_profile_id,evidence_type,source_url,summary_text,
        confidence,observed_at,stale_after,metadata_json)
        VALUES(%s,%s,'stored_public_profile_snapshot',%s,%s,%s,%s,%s,%s)""",
        (evidence_id,pid,source['canonical_url'],summary,confidence,observed,stale_after,Json(metadata)))
    log('saved_snapshot_reused',complete=True)
    return evidence_id,observed,stale_after,confidence

def prepare_one(conn,cur,row,grant,scheduled_at):
    pid=str(row['creator_profile_id'])
    email=row['email'].strip().lower()
    first=row['verified_first_name']
    name_policy=row.get('name_policy') or {}
    if name_policy.get('style')!='neutral_formal_first_contact' or name_policy.get('formal_first_name_verified') is not True or name_policy.get('informal_form_not_expanded_or_guessed') is not True:
        raise ValueError('neutral_formal_name_review_required')
    channel_id=str(row['channel']['id'])
    evidence_id=str(row['evidence']['id'])
    if not re.fullmatch(r'[А-ЯЁ][а-яё]+(?:-[А-ЯЁ][а-яё]+)?',first):
        raise ValueError('unverified_personal_first_name')
    cur.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',('localos-author:'+email,))
    if previously_contacted_author(cur,creator_profile_id=pid,recipient=email,queue_id='saved-pool-preparation'):
        raise ValueError('previously_contacted')
    cur.execute("""SELECT p.*, c.preferred_contact,c.metadata_json AS commercial_metadata,
            ch.canonical_url,ch.platform AS source_platform,ch.verification_status AS channel_verification,
            ch.last_observed_at AS channel_observed_at,ch.verified_at AS channel_verified_at,
            ch.metadata_json AS channel_metadata,e.observed_at,e.stale_after,e.confidence,e.source_url AS evidence_source
        FROM creator_profiles p JOIN creator_commercial_profiles c ON c.creator_profile_id=p.id
        JOIN creator_channels ch ON ch.creator_profile_id=p.id AND ch.id=%s
        JOIN creator_evidence e ON e.creator_profile_id=p.id AND e.id=%s
        WHERE p.id=%s FOR UPDATE OF p,c""",(channel_id,evidence_id,pid))
    source=dict(cur.fetchone() or {})
    if not source or source['preferred_contact'].strip().lower()!=email or source['channel_verification']!='verified':
        raise ValueError('saved_source_or_contact_changed')
    if source.get('brand_safety_status')=='blocked' or source['display_name']!=row['display_name']:
        raise ValueError('reviewed_identity_changed_or_blocked')
    if source['stale_after']<=datetime.now(timezone.utc) or source['confidence']<0.7:
        raise ValueError('saved_evidence_expired')
    if source['display_name'].split()[0].strip(' ,.!|').capitalize()!=first:
        raise ValueError('template_name_not_equal_verified_name')
    public_contacts=(source['commercial_metadata'] or {}).get('public_contacts') or []
    proofs=[v for v in public_contacts if str(v.get('value') or '').lower().strip()==email
            and str(v.get('source_channel_id'))==channel_id and v.get('status')=='public_explicit'
            and v.get('type')=='email' and str(v.get('source_url') or '').strip()]
    if not proofs:
        raise ValueError('public_contact_provenance_missing')
    cur.execute("""SELECT 1 FROM creator_campaign_candidates WHERE creator_profile_id=%s
        AND status IN ('invited','replied','declined','removed')
        UNION ALL SELECT 1 FROM creator_relationships WHERE creator_profile_id=%s
          AND (last_contacted_at IS NOT NULL OR last_replied_at IS NOT NULL OR stage IN ('declined','paused','invalid_contact','paid_only'))
        UNION ALL SELECT 1 FROM creator_collaborations WHERE creator_profile_id=%s
          AND NULLIF(agreed_terms_json->'outreach'->>'provider_message_id','') IS NOT NULL
        UNION ALL SELECT 1 FROM creator_contact_events WHERE creator_profile_id=%s
          AND (NULLIF(provider_message_id,'') IS NOT NULL OR event_type IN ('manual_sent','sent','outbound','replied','declined'))
        LIMIT 1""",(pid,pid,pid,pid))
    if cur.fetchone():
        raise ValueError('legacy_history_or_relationship_stop')
    cur.execute("""SELECT 1 FROM outreachsendqueue q LEFT JOIN prospectingleads l ON l.id=q.lead_id
        WHERE (l.source_external_id='creator:'||%s OR lower(btrim(COALESCE(q.recipient_value,'')))=%s)
          AND (q.delivery_status IN ('queued','retry','sending','sent','delivered') OR q.error_text ILIKE '%%send_uncertain%%') LIMIT 1""",(pid,email))
    if cur.fetchone():
        raise ValueError('recipient_already_queued_or_contacted')
    cur.execute('SELECT * FROM creator_campaign_candidates WHERE campaign_id=%s AND creator_profile_id=%s FOR UPDATE',(CAMPAIGN,pid))
    candidate=dict(cur.fetchone() or {})
    cid=str(candidate.get('id') or uuid.uuid4())
    if candidate.get('workstream_id') or candidate.get('outreach_campaign_id'):
        raise ValueError('existing_preparation_requires_reuse')
    evidence_id,source['observed_at'],source['stale_after'],source['confidence']=ensure_saved_channel_evidence(cur,pid,channel_id,source,proofs[0])
    snapshot=dict(candidate.get('score_snapshot_json') or {})
    snapshot['contact_confirmation']={'confirmed':True,'source_url':source['canonical_url'],
        'note':f"Повторное использование сохранённых публичных данных: канал {channel_id}, доказательство {evidence_id}. Новая проверка сайта не выполнялась.",
        'method':'stored_public_source_reuse','observed_at':source['observed_at'].isoformat(),
        'source_contact_proof':proofs[0],'reviewed_by':'codex_root_operator',
        'authorization_reference':grant['authorization_reference']}
    cur.execute("""INSERT INTO creator_campaign_candidates(id,campaign_id,creator_profile_id,status,score_snapshot_json,selection_reason)
        VALUES (%s,%s,%s,'shortlisted',%s,'Сохранённый автор: первая отправка по утверждённому шаблону LocalOS')
        ON CONFLICT(campaign_id,creator_profile_id) DO UPDATE SET score_snapshot_json=EXCLUDED.score_snapshot_json,updated_at=NOW()""",
        (cid,CAMPAIGN,pid,Json(snapshot)))
    prepared=prepare_candidate_outreach(cur,conn,business_id=str(row['business_id']),campaign_id=CAMPAIGN,candidate_id=cid,user_id=ACTOR)
    lead_id=prepared['lead_id']; ws=prepared['workstream']; wid=str(ws['id'])
    cur.execute('UPDATE prospectingleads SET source_url=%s,updated_at=NOW() WHERE id=%s',(source['canonical_url'],lead_id))
    point_id=str(uuid.uuid4())
    cur.execute("""INSERT INTO lead_contact_points(id,lead_id,contact_type,value,normalized_value,owner_type,person_name,
        source_url,source_type,provider,confidence,verification_status,observed_at,verified_at,stale_after,metadata_json)
        VALUES(%s,%s,'email',%s,%s,'person',%s,%s,'public','creator_catalog',%s,'confirmed_source',%s,%s,%s,%s)
        ON CONFLICT(lead_id,contact_type,normalized_value) DO NOTHING RETURNING id""",
        (point_id,lead_id,email,email,source['display_name'],source['canonical_url'],source['confidence'],source['observed_at'],source['observed_at'],source['stale_after'],Json({'creator_profile_id':pid,'source_channel_id':channel_id,'source_evidence_id':evidence_id,'reuse_method':'stored_public_source_reuse'})))
    inserted=cur.fetchone()
    if not inserted:
        cur.execute("SELECT id,source_url FROM lead_contact_points WHERE lead_id=%s AND contact_type='email' AND normalized_value=%s",(lead_id,email))
        point=dict(cur.fetchone())
        if point['source_url'].rstrip('/').lower()!=source['canonical_url'].rstrip('/').lower():
            raise ValueError('existing_contact_source_conflict')
        point_id=str(point['id'])
    cur.execute("UPDATE lead_workstreams SET selected_channel='email',selected_contact_point_id=%s,updated_at=NOW() WHERE id=%s",(point_id,wid))
    preview=build_preview(cur,wid,sequence=[{'channel':'email','day_offset':0,'angle':'signal','sender_account_id':SENDER}],
        start_at=scheduled_at,sender_mode='localos_for_partner',generate_ai=False)
    if preview.get('status')!='ready':
        codes=list((preview.get('decision') or {}).get('reason_codes') or [])+list(preview.get('missing') or [])
        for item in [preview]+list(preview.get('touches') or []):
            gate=item.get('quality_gate') or {}
            codes+=list(gate.get('blocking_reasons') or [])+list(gate.get('reason_codes') or [])
        codes=sorted({str(c) for c in codes if re.fullmatch(r'[a-z][a-z0-9_]{0,100}',str(c))})
        log('preview_not_ready',reason_codes=codes)
        raise ValueError('preview_not_ready:'+','.join(codes))
    touch=preview['touches'][0]
    if not touch['text'].startswith(first+', здравствуйте!'):
        raise ValueError('rendered_name_mismatch')
    saved=persist_preview(cur,preview,user_id=ACTOR)
    approved=approve_campaign_by_author_template(cur,str(saved['id']))
    cur.execute('UPDATE creator_campaign_candidates SET outreach_campaign_id=%s,updated_at=NOW() WHERE id=%s',(saved['id'],cid))
    if ws.get('enrichment_job_id') and not ws.get('reused'):
        cur.execute("""UPDATE lead_enrichment_jobs SET status='ready',current_phase='ready',completed_at=NOW(),
            result_json=%s,readiness_json=%s,updated_at=NOW() WHERE id=%s AND status='queued'""",
            (Json({'method':'stored_verified_catalog_reuse','source_channel_id':channel_id,'source_evidence_id':evidence_id,'outreach_campaign_id':str(saved['id']),'network_research_performed':False}),
             Json({'ready':True,'scope':'approved_author_template','missing':[]}),ws['enrichment_job_id']))
    cur.execute('SELECT id,batch_id,delivery_status,scheduled_at FROM outreachsendqueue WHERE campaign_touch_id IN (SELECT id FROM outreach_campaign_touches WHERE campaign_id=%s)',(saved['id'],))
    queue=dict(cur.fetchone() or {})
    if queue.get('delivery_status')!='queued':
        raise ValueError('queue_not_created')
    return {'profile_id':pid,'candidate_id':cid,'workstream_id':wid,'campaign_id':str(saved['id']),
        'queue_id':str(queue['id']),'batch_id':str(queue['batch_id']),'scheduled_at':queue['scheduled_at'],
        'body_sha256':hashlib.sha256(touch['text'].encode()).hexdigest(),'subject_sha256':hashlib.sha256(touch['subject'].encode()).hexdigest()}

parser=argparse.ArgumentParser()
parser.add_argument('--selection',required=True)
parser.add_argument('--commit',action='store_true')
parser.add_argument('--limit',type=int,default=20)
parser.add_argument('--output')
args=parser.parse_args()
with open(args.selection,encoding='utf-8') as handle:
    payload=json.load(handle)
records=payload['records'][:max(0,min(150,args.limit))]
conn=get_db_connection()
results=[]; skipped=[]
try:
    cur=conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('SELECT * FROM outreach_sender_accounts WHERE id=%s',(SENDER,))
    sender=dict(cur.fetchone())
    grant=load_author_template_authorization(cur,sender_account_id=SENDER)
    if not grant:
        raise RuntimeError('author_template_grant_missing')
    cur.execute('SELECT business_id,status,terms_version,approved_terms_version FROM creator_campaigns WHERE id=%s',(CAMPAIGN,))
    campaign=dict(cur.fetchone())
    assert campaign['status']=='approved' and campaign['terms_version']==campaign['approved_terms_version']
    conn.rollback()
    contacted=provider_history(sender,records)
    selected=[]; emails=set()
    for row in records:
        email=row['email'].strip().lower()
        if email in contacted or email in emails:
            skipped.append({'profile_id':row['creator_profile_id'],'reason':'provider_history_or_duplicate'})
            continue
        emails.add(email); row['business_id']=str(campaign['business_id']); selected.append(row)
    log('selection',selected=len(selected),skipped_count=len(skipped),commit=args.commit)
    scheduled_at=datetime.now(timezone.utc)+timedelta(minutes=20)
    for row in selected:
        cur.execute('SAVEPOINT author_item')
        try:
            result=prepare_one(conn,cur,row,grant,scheduled_at)
            cur.execute('RELEASE SAVEPOINT author_item')
            results.append(result)
            log('prepared',**result)
        except Exception as exc:
            cur.execute('ROLLBACK TO SAVEPOINT author_item')
            cur.execute('RELEASE SAVEPOINT author_item')
            reason=str(exc).split('\n')[0][:200]
            skipped.append({'profile_id':row['creator_profile_id'],'reason':reason})
            log('skipped',reason_code=reason if re.fullmatch(r'[a-z_]+',reason) else 'preparation_error')
    if args.commit:
        conn.commit()
    else:
        conn.rollback()
    output={'mode':'commit' if args.commit else 'rolled_back_preview','prepared':len(results),'skipped':skipped,'records':results,'sent':0}
    encoded=json.dumps(output,ensure_ascii=False,default=str)
    output_path=args.output or ('/tmp/localos-author-pool-wave-result.json' if args.commit else '/tmp/localos-author-pool-wave-preview.json')
    with open(output_path,'w',encoding='utf-8') as handle:
        handle.write(encoded)
    log('completed',mode=output['mode'],prepared=len(results),skipped_count=len(skipped),sent=0,path=output_path,sha256=hashlib.sha256(encoded.encode()).hexdigest())
finally:
    conn.close()
