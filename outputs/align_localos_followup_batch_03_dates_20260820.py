#!/usr/bin/env python3
import json
from datetime import datetime,timezone
from pathlib import Path
from psycopg2.extras import Json,RealDictCursor
from database_manager import get_db_connection

p=json.loads(Path('/app/debug_data/localos-followup-batch-03-final-20260820.json').read_text(encoding='utf-8')); dates={'2026-08-21':datetime(2026,8,21,7,0,tzinfo=timezone.utc),'2026-08-24':datetime(2026,8,24,7,0,tzinfo=timezone.utc)}
c=get_db_connection(); q=c.cursor(cursor_factory=RealDictCursor); updated=0
try:
 for x in p['items']:
  tid=x['actual_touch_id']; q.execute('SELECT status,approved_text,quality_gate_json,strategy_json FROM outreach_campaign_touches WHERE id=%s FOR UPDATE',(tid,)); r=dict(q.fetchone() or {})
  q.execute('SELECT COUNT(*) count FROM outreachsendqueue WHERE campaign_touch_id=%s',(tid,)); queued=int(q.fetchone()['count'])
  if r.get('status')!='draft' or r.get('approved_text') is not None or queued: raise RuntimeError(f"unsafe:{x['name']}")
  quality=dict(r.get('quality_gate_json') or {}); strategy=dict(r.get('strategy_json') or {}); approval='blocked_cooldown' if x['planned_send_date']=='2026-08-24' else 'pending_user_approval'
  quality.update({'approval_status':approval,'delivery_authorized':False}); strategy.update({'planned_send_date':x['planned_send_date'],'approval_status':approval})
  q.execute('UPDATE outreach_campaign_touches SET scheduled_at=%s,manual_due_at=%s,quality_gate_json=%s,strategy_json=%s,delivery_json=%s,updated_at=NOW() WHERE id=%s',(dates[x['planned_send_date']],dates[x['planned_send_date']],Json(quality),Json(strategy),Json({'queued':False,'sent':False,'delivery_authorized':False}),tid)); updated+=q.rowcount
 c.commit()
except Exception:
 c.rollback(); raise
finally: c.close()
print(json.dumps({'aligned':updated,'queued':0,'approved':0},ensure_ascii=False))
