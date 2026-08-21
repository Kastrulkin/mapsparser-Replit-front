#!/usr/bin/env python3
import json
from pathlib import Path
from psycopg2.extras import RealDictCursor
from database_manager import get_db_connection

p=json.loads(Path('/app/debug_data/localos-followup-batch-03-final-20260820.json').read_text(encoding='utf-8')); ids=tuple(x['actual_touch_id'] for x in p['items'])
c=get_db_connection(); q=c.cursor(cursor_factory=RealDictCursor)
q.execute("""SELECT COUNT(*) total,COUNT(*) FILTER(WHERE status='draft') drafts,COUNT(*) FILTER(WHERE approved_text IS NOT NULL) approved,COUNT(*) FILTER(WHERE scheduled_at='2026-08-21 07:00:00+00') aug21,COUNT(*) FILTER(WHERE scheduled_at='2026-08-24 07:00:00+00') aug24,COUNT(*) FILTER(WHERE COALESCE((delivery_json->>'queued')::boolean,FALSE)) delivery_queued,COUNT(*) FILTER(WHERE COALESCE((delivery_json->>'sent')::boolean,FALSE)) delivery_sent FROM outreach_campaign_touches WHERE id IN %s""",(ids,)); counts=dict(q.fetchone())
q.execute('SELECT COUNT(*) count FROM outreachsendqueue WHERE campaign_touch_id IN %s',(ids,)); queue=int(q.fetchone()['count'])
q.execute("SELECT COUNT(*) count FROM outreach_campaign_events WHERE touch_id IN %s AND event_type IN ('queued','send_started','sent','delivered','manual_sent')",(ids,)); events=int(q.fetchone()['count'])
c.rollback(); c.close()
if counts!={'total':70,'drafts':70,'approved':0,'aug21':44,'aug24':26,'delivery_queued':0,'delivery_sent':0} or queue or events: raise RuntimeError(f"safety_failed:{counts}:{queue}:{events}")
print(json.dumps({'counts':counts,'queue_rows':queue,'send_events':events,'delivery_authorized':False},ensure_ascii=False))
