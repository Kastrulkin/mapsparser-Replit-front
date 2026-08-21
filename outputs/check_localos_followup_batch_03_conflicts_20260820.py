#!/usr/bin/env python3
import json
from pathlib import Path
from psycopg2.extras import RealDictCursor
from database_manager import get_db_connection

p = json.loads(Path('/app/debug_data/localos-followup-batch-03-final-20260820.json').read_text(encoding='utf-8'))
c = get_db_connection()
q = c.cursor(cursor_factory=RealDictCursor)
conflicts = []
for x in p['items']:
    q.execute("SELECT id,status FROM outreach_campaign_touches WHERE campaign_id=%s AND sequence_index=1 AND status<>'cancelled'", (x['campaign_id'],))
    r = q.fetchone()
    if r:
        conflicts.append({'name': x['name'], 'id': str(r['id']), 'status': r['status']})
c.rollback()
c.close()
print(json.dumps({'conflicts': conflicts, 'count': len(conflicts)}, ensure_ascii=False))
