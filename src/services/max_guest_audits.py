"""Guest audits reuse the same public audit pipeline as Telegram."""
import os
import requests
from psycopg2.extras import Json
from services.operator_conversations import _row


def start_guest_audit(cursor, *, max_id, normalized_url, event_key, source_name=''):
    cursor.execute('SELECT slug,public_url FROM max_guest_audits WHERE event_key=%s', (event_key,))
    previous = _row(cursor, cursor.fetchone())
    if previous:
        return True, {**previous, 'normalized_url': normalized_url, 'source_name': source_name}
    cursor.execute("SELECT COUNT(*) AS n FROM max_guest_audits WHERE max_id=%s AND created_at>NOW()-INTERVAL '1 hour'", (max_id,))
    if _row(cursor, cursor.fetchone()).get('n', 0) >= 10:
        return False, {'error': 'Достигнут часовой лимит аудитов. Попробуйте позже.'}
    base = os.getenv('API_BASE_URL', 'http://127.0.0.1:8000').rstrip('/')
    try:
        response = requests.post(base + '/api/public/request-report', json={
            'email': 'max-' + max_id + '@localos.bot', 'url': normalized_url, 'source': 'max_bot'}, timeout=(5, 20))
        result = response.json()
        if response.status_code >= 400 or not result.get('success') or not result.get('slug'):
            return False, {'error': 'Не удалось запустить аудит. Попробуйте публичный аудит на https://localos.pro.'}
    except (requests.RequestException, ValueError):
        return False, {'error': 'Не удалось подтвердить запуск аудита. Проверьте результат в LocalOS перед повторной заявкой.'}
    public_url = str(result.get('public_url') or '/' + str(result['slug']))
    if public_url.startswith('/'): public_url = 'https://localos.pro' + public_url
    cursor.execute('INSERT INTO max_guest_audits(event_key,max_id,slug,public_url) VALUES (%s,%s,%s,%s) ON CONFLICT(event_key) DO NOTHING',
        (event_key, max_id, str(result['slug']), public_url))
    return True, {'public_url': public_url, 'slug': str(result['slug']), 'normalized_url': normalized_url, 'source_name': source_name}


def request_guest_audit(cursor, *, max_id, text, event_key):
    from services.telegram_lead_intake import parse_map_links_from_text
    parsed = parse_map_links_from_text(text)
    items = parsed.get('valid_items') or []
    if not parsed.get('ok') or len(items) != 1:
        return None
    ok, result = start_guest_audit(cursor, max_id=max_id, normalized_url=items[0]['normalized_url'], event_key=event_key)
    return ('Карточка принята в аудит. Результат придёт сюда, когда будет готов.\n' + result['public_url']) if ok else result['error']


def collect_guest_audit_results(cursor):
    cursor.execute("""SELECT a.event_key,a.max_id,a.public_url,r.status FROM max_guest_audits a
        JOIN publicreportrequests r ON r.slug=a.slug WHERE a.notifications_enabled AND r.status IN ('completed','error')
        AND NOT EXISTS(SELECT 1 FROM max_webhook_events e WHERE e.event_key='guest-audit:' || a.event_key)
        AND a.created_at>NOW()-INTERVAL '7 days' ORDER BY a.created_at LIMIT 100""")
    for row in cursor.fetchall():
        payload = {'update_type': 'localos_guest_audit_ready', 'audit_event_key': row['event_key'], 'max_id': row['max_id']}
        cursor.execute('INSERT INTO max_webhook_events(event_key,payload_json) VALUES (%s,%s) ON CONFLICT(event_key) DO NOTHING',
                       ('guest-audit:' + row['event_key'], Json(payload)))


def prepare_guest_audit_result(cursor, payload):
    cursor.execute('''SELECT a.max_id,a.public_url,r.status FROM max_guest_audits a
        JOIN publicreportrequests r ON r.slug=a.slug WHERE a.notifications_enabled AND a.event_key=%s AND a.max_id=%s''',
        (payload.get('audit_event_key'), payload.get('max_id')))
    audit = _row(cursor, cursor.fetchone())
    if not audit or audit['status'] not in {'completed', 'error'}:
        return None
    from services.max_bot import response
    return response(str(audit['max_id']), ('Аудит готов.\n' if audit['status'] == 'completed' else 'Аудит требует внимания. Проверьте состояние отчёта.\n') + audit['public_url'])
