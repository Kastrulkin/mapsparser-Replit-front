#!/usr/bin/env python3
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
from psycopg2.extras import Json,RealDictCursor
from database_manager import get_db_connection

PATH=Path('/app/debug_data/localos-followup-batch-03-final-20260820.json'); NAMES={'Стоматология Комфорта','Зенит-Чемпионика','Территория Мистики','Я – Актер!','Шуваловская школа'}; REVIEW=datetime(2026,8,24,7,0,tzinfo=timezone.utc)
p=json.loads(PATH.read_text(encoding='utf-8')); c=get_db_connection(); q=c.cursor(cursor_factory=RealDictCursor)
try:
 for x in p['items']:
  if x['name'] not in NAMES: continue
  tid=x['actual_touch_id']; q.execute('SELECT status,approved_text,quality_gate_json,strategy_json FROM outreach_campaign_touches WHERE id=%s FOR UPDATE',(tid,)); r=dict(q.fetchone() or {})
  q.execute('SELECT COUNT(*) count FROM outreachsendqueue WHERE campaign_touch_id=%s',(tid,)); queue=int(q.fetchone()['count'])
  if r.get('status')!='draft' or r.get('approved_text') is not None or queue: raise RuntimeError(f"unsafe_collision:{x['name']}")
  quality=dict(r.get('quality_gate_json') or {}); quality.update({'approval_status':'blocked_channel_collision','verdict':'reject','reason_codes':['yougile_cross_channel_touch_id_collision'],'delivery_authorized':False})
  strategy=dict(r.get('strategy_json') or {}); strategy.update({'planned_send_date':None,'review_date':'2026-08-24','approval_status':'blocked_channel_collision'})
  q.execute('UPDATE outreach_campaign_touches SET scheduled_at=%s,manual_due_at=%s,quality_gate_json=%s,strategy_json=%s,delivery_json=%s,updated_at=NOW() WHERE id=%s',(REVIEW,REVIEW,Json(quality),Json(strategy),Json({'queued':False,'sent':False,'delivery_authorized':False}),tid))
  x['planned_send_date']=None; x['review_date']='2026-08-24'; x['status']='blocked_channel_collision'; x['reasons']=['yougile_cross_channel_touch_id_collision']; x['approval']={'content_status':'blocked_channel_collision','delivery_authorized':False}; x['quality'].update({'verdict':'reject','reason_codes':x['reasons']})
 c.commit()
except Exception:
 c.rollback(); raise
finally: c.close()
p['ready_aug21_count']=44; p['deferred_aug24_count']=21; p['blocked_channel_collision_count']=5; p.pop('review_sha256',None); p['review_sha256']=hashlib.sha256(json.dumps(p,ensure_ascii=False,sort_keys=True).encode()).hexdigest(); PATH.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'group_total':70,'ready_aug21':44,'cooldown_aug24':21,'blocked_channel_collision':5,'queued':0},ensure_ascii=False))
