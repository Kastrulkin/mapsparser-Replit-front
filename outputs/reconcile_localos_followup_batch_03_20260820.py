#!/usr/bin/env python3
"""Reconcile the 70-item artifact with canonical existing/new PostgreSQL drafts."""

import hashlib
import json
from pathlib import Path
from psycopg2.extras import RealDictCursor
from database_manager import get_db_connection

PATH=Path('/app/debug_data/localos-followup-batch-03-final-20260820.json')
p=json.loads(PATH.read_text(encoding='utf-8')); c=get_db_connection(); q=c.cursor(cursor_factory=RealDictCursor); reused=[]
for x in p['items']:
    q.execute("SELECT id,status,subject,generated_text,approved_text,scheduled_at,quality_gate_json FROM outreach_campaign_touches WHERE campaign_id=%s AND sequence_index=1",(x['campaign_id'],)); r=dict(q.fetchone() or {})
    if r.get('status')!='draft' or r.get('approved_text') is not None: raise RuntimeError(f"canonical_draft_invalid:{x['name']}")
    q.execute('SELECT COUNT(*) count FROM outreachsendqueue WHERE campaign_touch_id=%s',(r['id'],))
    if int((q.fetchone() or {}).get('count') or 0): raise RuntimeError(f"canonical_draft_queued:{x['name']}")
    old=x.get('proposed_touch_id'); actual=str(r['id']); is_reused=old!=actual
    if is_reused: reused.append(x['name'])
    x['proposed_touch_id']=actual; x['actual_touch_id']=actual; x['reused_existing_canonical_draft']=is_reused
    x['draft']['subject']=r.get('subject'); x['draft']['text']=r.get('generated_text')
    x['canonical_scheduled_at']=r['scheduled_at'].isoformat()
c.rollback(); c.close(); p['reused_existing_count']=len(reused); p['imported_new_count']=70-len(reused); p['reused_existing_names']=reused
p.pop('review_sha256',None); p['review_sha256']=hashlib.sha256(json.dumps(p,ensure_ascii=False,sort_keys=True).encode()).hexdigest(); PATH.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'total':70,'reused_existing':len(reused),'imported_new':70-len(reused),'review_sha256':p['review_sha256']},ensure_ascii=False))
