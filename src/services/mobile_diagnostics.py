"""Messenger-independent diagnostics; recovery is an explicit reviewed operation."""
import json


def build_snapshot(orchestrator, actor, business_id):
    metrics = orchestrator.get_callback_metrics(actor, tenant_id=business_id, window_minutes=60)
    if not metrics.get('success'):
        raise PermissionError('Диагностика недоступна')
    queues = {}
    for status in ('retry', 'dlq'):
        result = orchestrator.list_callback_outbox(actor, tenant_id=business_id, status=status, limit=200, offset=0)
        if not result.get('success'):
            raise PermissionError('Очередь недоступна')
        queues[status] = [{key: row.get(key) for key in ('id', 'action_id', 'event_type', 'attempts', 'status')} for row in result.get('items') or []]
    return {'business_id': business_id, 'metrics': metrics.get('metrics') or {}, 'queues': queues}


def render_snapshot(snapshot):
    return 'Состояние автоматизации\n' + json.dumps(snapshot, ensure_ascii=False, default=str, indent=2)


def recover(orchestrator, actor, business_id):
    before = build_snapshot(orchestrator, actor, business_id)
    replay = orchestrator.replay_callback_outbox(actor, tenant_id=business_id, include_retry=True, limit=200)
    if not replay.get('success'):
        raise PermissionError('Восстановление очереди не подтверждено. Проверьте журнал перед повтором.')
    dispatch = orchestrator.dispatch_callback_outbox_for_tenant(actor, tenant_id=business_id, batch_size=200)
    if not dispatch.get('success'):
        raise PermissionError('Отправка очереди не подтверждена. Проверьте журнал перед повтором.')
    return {'before': before, 'replay': replay, 'dispatch': dispatch,
            'after': build_snapshot(orchestrator, actor, business_id)}


def run_reviewed_operation_once(key, operation):
    """Commit an execution intent before recovery. A crash requires reconciliation."""
    from database_manager import DatabaseManager
    from psycopg2.extras import Json
    from services.operator_conversations import _row
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        cursor.execute("""INSERT INTO max_webhook_events(event_key,payload_json,status,started_at)
            VALUES (%s,'{}','processing',NOW()) ON CONFLICT(event_key) DO NOTHING RETURNING event_key""", (key,))
        if not cursor.fetchone():
            cursor.execute('SELECT status,result_json FROM max_webhook_events WHERE event_key=%s', (key,))
            receipt = _row(cursor, cursor.fetchone())
            return (receipt.get('result_json') or {}).get('text') or 'Операция уже принята. Проверьте её результат в журнале перед повтором.'
        db.conn.commit()
        try:
            result = operation()
            text = 'Операция выполнена.\n' + json.dumps(result, ensure_ascii=False, default=str)
            status = 'completed'
        except Exception:
            text = 'Результат восстановления не подтверждён. Проверьте очередь и журнал перед повтором.'
            status = 'needs_attention'
        cursor.execute('UPDATE max_webhook_events SET status=%s,result_json=%s,completed_at=NOW() WHERE event_key=%s',
                       (status, Json({'text': text}), key))
        db.conn.commit()
        return text
    finally:
        db.conn.rollback()
        db.close()
