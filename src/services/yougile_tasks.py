"""Business-scoped YouGile connection, previews and approved task operations."""
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone

import auth_encryption
from psycopg2.extras import Json
from pg_db_utils import get_db_connection
from services import yougile_client
from services.yougile_client import YouGileError
from services.business_permissions import load_actor, require_permission


def enabled():
    return os.getenv('YOUGILE_CLIENT_ENABLED', 'false').lower() == 'true'


def authorize(cursor, business_id, user_id, permission='business.read'):
    if not enabled():
        raise YouGileError('disabled', 'Клиентское подключение YouGile пока выключено.', 503)
    try:
        require_permission(cursor, business_id, load_actor(cursor, user_id), permission)
    except PermissionError:
        raise YouGileError('access_denied', 'Нет права на это действие в выбранном бизнесе.', 403) from None


def require_encryption():
    if not auth_encryption.CRYPTOGRAPHY_AVAILABLE or not os.getenv('EXTERNAL_AUTH_SECRET_KEY', '').strip():
        raise YouGileError('encryption_required', 'Защищённое хранение ключей ещё не настроено.', 503)


def connection(cursor, business_id):
    require_encryption()
    cursor.execute('''SELECT a.id,a.auth_data_encrypted,c.* FROM externalbusinessaccounts a
        JOIN yougile_connections c ON c.account_id=a.id
        WHERE a.business_id=%s AND a.source='yougile' AND a.is_active=TRUE''', (business_id,))
    row = cursor.fetchone()
    if not row:
        raise YouGileError('not_connected', 'Сначала подключите YouGile.', 409)
    value = dict(row)
    try:
        secret = json.loads(auth_encryption.decrypt_auth_data(value.pop('auth_data_encrypted')) or '{}')
    except (ValueError, TypeError):
        secret = {}
    if not secret.get('api_key'):
        raise YouGileError('not_connected', 'Подключите YouGile заново.', 409)
    return value, secret['api_key']


def status(cursor, business_id):
    cursor.execute('''SELECT a.id,a.is_active,a.last_error,c.project_id,c.board_id,c.column_id,c.selection_json,c.version
        FROM externalbusinessaccounts a LEFT JOIN yougile_connections c ON c.account_id=a.id
        WHERE a.business_id=%s AND a.source='yougile' ''', (business_id,))
    row = dict(cursor.fetchone() or {})
    return {'enabled': enabled(), 'connected': bool(row.get('is_active')),
            'configured': bool(row.get('is_active') and row.get('column_id')),
            'selection': row.get('selection_json') or {}, 'needs_reauthorization': bool(row.get('last_error'))}


def connect(cursor, business_id, user_id, token):
    authorize(cursor, business_id, user_id, 'business.settings.write')
    require_encryption()
    if not isinstance(token, str) or not 20 <= len(token.strip()) <= 2048 or any(c.isspace() for c in token.strip()):
        raise YouGileError('invalid_key', 'Укажите API-ключ YouGile.')
    token = token.strip()
    profile = yougile_client.request(token, 'GET', '/users/me')
    yougile_client.identifier(profile.get('id'))
    encrypted = auth_encryption.encrypt_auth_data(json.dumps({'api_key': token}))
    cursor.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', ('yougile:' + business_id,))
    cursor.execute('''INSERT INTO externalbusinessaccounts(id,business_id,source,auth_data_encrypted,is_active,created_at,updated_at)
        VALUES(%s,%s,'yougile',%s,TRUE,NOW(),NOW())
        ON CONFLICT(business_id) WHERE source='yougile' DO UPDATE SET
        auth_data_encrypted=EXCLUDED.auth_data_encrypted,is_active=TRUE,last_error=NULL,updated_at=NOW() RETURNING id''',
        (str(uuid.uuid4()), business_id, encrypted))
    account_id = cursor.fetchone()['id']
    cursor.execute('''INSERT INTO yougile_connections(account_id) VALUES(%s)
        ON CONFLICT(account_id) DO UPDATE SET project_id=NULL,board_id=NULL,column_id=NULL,selection_json='{}',
        version=yougile_connections.version+1,updated_at=NOW()''', (account_id,))
    return status(cursor, business_id)


def disconnect(cursor, business_id, user_id):
    authorize(cursor, business_id, user_id, 'business.settings.write')
    cursor.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', ('yougile:' + business_id,))
    cursor.execute("UPDATE externalbusinessaccounts SET is_active=FALSE,auth_data_encrypted=NULL,last_error=NULL,updated_at=NOW() WHERE business_id=%s AND source='yougile' RETURNING id", (business_id,))
    row = cursor.fetchone()
    if row:
        cursor.execute('UPDATE yougile_connections SET version=version+1,updated_at=NOW() WHERE account_id=%s', (row['id'],))
    return {'connected': False}


def resources(token, project_id, board_id=None, column_id=None):
    project = yougile_client.request(token, 'GET', '/projects/' + yougile_client.identifier(project_id))
    if project.get('id') != project_id or project.get('deleted'):
        raise YouGileError('invalid_selection', 'Проект YouGile недоступен.', 409)
    board = column = None
    if board_id:
        board = yougile_client.request(token, 'GET', '/boards/' + yougile_client.identifier(board_id))
        if board.get('id') != board_id or board.get('projectId') != project_id or board.get('deleted'):
            raise YouGileError('invalid_selection', 'Доска не относится к выбранному проекту.', 409)
    if column_id:
        column = yougile_client.request(token, 'GET', '/columns/' + yougile_client.identifier(column_id))
        if column.get('id') != column_id or column.get('boardId') != board_id or column.get('deleted'):
            raise YouGileError('invalid_selection', 'Колонка не относится к выбранной доске.', 409)
    return project, board, column


def catalog(cursor, business_id, user_id, project_id=None, board_id=None):
    authorize(cursor, business_id, user_id, 'business.settings.write')
    _, token = connection(cursor, business_id)
    if board_id and not project_id:
        raise YouGileError('invalid_selection', 'Сначала выберите проект.')
    if project_id:
        resources(token, project_id, board_id)
    resource, filters = ('columns', {'boardId': board_id}) if board_id else ('boards', {'projectId': project_id}) if project_id else ('projects', {})
    rows = yougile_client.collection(token, resource, filters)
    if any((board_id and row.get('boardId') != board_id) or (project_id and not board_id and row.get('projectId') != project_id) for row in rows):
        raise YouGileError('invalid_response', 'YouGile вернул данные другого проекта.', 502)
    return {'items': [{'id': row['id'], 'title': row.get('title', '')} for row in rows]}


def select(cursor, business_id, user_id, args):
    authorize(cursor, business_id, user_id, 'business.settings.write')
    cursor.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', ('yougile:' + business_id,))
    account, token = connection(cursor, business_id)
    ids = [yougile_client.identifier(args.get(k)) for k in ('project_id', 'board_id', 'column_id')]
    project, board, column = resources(token, *ids)
    selected = dict(zip(('project_id', 'board_id', 'column_id'), ids))
    selected.update(project_name=project.get('title', ''), board_name=board.get('title', ''), column_name=column.get('title', ''))
    cursor.execute('''UPDATE yougile_connections SET project_id=%s,board_id=%s,column_id=%s,selection_json=%s,
        version=version+1,updated_at=NOW() WHERE account_id=%s''', (*ids, Json(selected), account['id']))
    return {'selection': selected}


def selected_context(cursor, business_id):
    account, token = connection(cursor, business_id)
    if not account.get('column_id'):
        raise YouGileError('selection_required', 'Выберите проект, доску и колонку в подключении YouGile.', 409)
    project, board, column = resources(token, account['project_id'], account['board_id'], account['column_id'])
    return account, token, project, board, column


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def task_view(task):
    return {key: task.get(key) for key in ('id', 'title', 'description', 'columnId', 'completed', 'archived', 'assigned', 'deadline')}


def task_on_board(token, account, task_id):
    task = yougile_client.request(token, 'GET', '/tasks/' + yougile_client.identifier(task_id))
    if task.get('id') != task_id or task.get('deleted'):
        raise YouGileError('invalid_task', 'Задача недоступна.', 409)
    resources(token, account['project_id'], account['board_id'], task.get('columnId'))
    return task_view(task)


def read_tasks(cursor, business_id, user_id):
    authorize(cursor, business_id, user_id)
    account, token, project, _, _ = selected_context(cursor, business_id)
    columns = yougile_client.collection(token, 'columns', {'boardId': account['board_id']})
    if len(columns) > 30 or any(c.get('boardId') != account['board_id'] for c in columns):
        raise YouGileError('limit_exceeded', 'Выберите доску не более чем с 30 колонками.', 409)
    tasks = []
    for column in columns:
        rows = yougile_client.collection(token, 'tasks', {'columnId': column['id']})
        if any(t.get('columnId') != column['id'] for t in rows):
            raise YouGileError('invalid_response', 'YouGile вернул задачи другой доски.', 502)
        tasks.extend(task_view(t) for t in rows)
        if len(tasks) > 5000:
            raise YouGileError('limit_exceeded', 'Доска превышает лимит: 5000 задач.', 409)
    users = yougile_client.collection(token, 'users')
    direct = project.get('users') or {}
    return {'items': tasks, 'columns': [{'id': c['id'], 'title': c.get('title', '')} for c in columns],
            'users': [{'id': u['id'], 'name': u.get('realName') or u.get('email') or u['id']}
                      for u in users if u['id'] in direct and direct[u['id']] != '-'],
            'selection': account['selection_json']}


def prepare(cursor, business_id, user_id, args):
    authorize(cursor, business_id, user_id, 'operations.write')
    account, token, project, _, column = selected_context(cursor, business_id)
    operation = args.get('operation')
    if operation == 'create':
        title, description = str(args.get('title') or '').strip(), str(args.get('description') or '').strip()
        if not 1 <= len(title) <= 300 or len(description) > 5000:
            raise YouGileError('invalid_task', 'Укажите название до 300 символов и описание до 5000 символов.')
        assigned = args.get('assigned') or []
        if not isinstance(assigned, list) or len(assigned) > 10:
            raise YouGileError('invalid_assignees', 'Выберите не более 10 исполнителей.')
        assigned = list(dict.fromkeys(yougile_client.identifier(value) for value in assigned))
        project_users = project.get('users') or {}
        if any(value not in project_users or project_users[value] == '-' for value in assigned):
            raise YouGileError('invalid_assignees', 'Исполнитель должен иметь прямой доступ к выбранному проекту.')
        body = {'title': title, 'description': description, 'assigned': assigned, 'columnId': account['column_id']}
        if args.get('deadline'):
            try:
                due = datetime.fromisoformat(args['deadline'].replace('Z', '+00:00'))
                if due.tzinfo is None:
                    raise ValueError()
            except (ValueError, TypeError, AttributeError):
                raise YouGileError('invalid_deadline', 'Укажите точную дату и время с часовым поясом, например 2026-11-03T18:00:00+03:00.') from None
            body['deadline'] = {'deadline': int(due.timestamp() * 1000), 'withTime': True}
        expected = None
    elif operation == 'complete':
        current = task_on_board(token, account, args.get('task_id'))
        if current.get('completed') or current.get('archived'):
            raise YouGileError('invalid_task', 'Задача уже завершена или архивирована.', 409)
        expected = digest(current)
        body = {'completed': True}
        title = current.get('title') or ''
    else:
        raise YouGileError('invalid_operation', 'Доступны создание и завершение задачи.')
    users = yougile_client.collection(token, 'users') if operation == 'create' else []
    names = {u['id']: u.get('realName') or u.get('email') or u['id'] for u in users}
    if any(value not in names for value in body.get('assigned', [])):
        raise YouGileError('invalid_assignees', 'Исполнитель больше не доступен в YouGile.', 409)
    summary = ('Создать задачу: ' if operation == 'create' else 'Завершить задачу: ') + title
    summary += '\nДоска: ' + account['selection_json'].get('board_name', '')
    if operation == 'create':
        summary += '\nКолонка: ' + str(column.get('title', ''))
        summary += '\nИсполнители: ' + (', '.join(names[u] for u in body['assigned']) or 'не назначены')
        summary += '\nСрок: ' + (str(args.get('deadline')) if args.get('deadline') else 'не задан')
        if body.get('description'):
            summary += '\n\n' + body['description']
    return {'business_id': business_id, 'account_id': account['id'], 'version': account['version'],
            'operation': operation, 'task_id': args.get('task_id') if operation == 'complete' else None,
            'body': body, 'expected': expected, 'summary': summary, 'request_id': str(uuid.uuid4())}


def apply(envelope, actor):
    """Called only by the registered Action Orchestrator handler after approval."""
    business_id = envelope['tenant_id']
    user_id = actor.get('user_id') or actor.get('id')
    payload = envelope.get('payload') or {}
    conn = get_db_connection()
    cursor = conn.cursor()
    write_state = 'blocked'
    try:
        cursor.execute('SELECT pg_advisory_lock(hashtext(%s))', ('yougile:' + business_id,))
        authorize(cursor, business_id, user_id, 'operations.write')
        account, token, _, _, _ = selected_context(cursor, business_id)
        if payload.get('business_id') != business_id or payload.get('account_id') != account['id'] or payload.get('version') != account['version']:
            raise YouGileError('stale_preview', 'Подключение изменилось. Подготовьте задачу заново.', 409)
        request_id = yougile_client.identifier(payload.get('request_id'))
        fingerprint = digest(payload)
        cursor.execute('SELECT * FROM yougile_task_requests WHERE request_id=%s FOR UPDATE', (request_id,))
        existing = dict(cursor.fetchone() or {})
        if existing and (existing['account_id'] != account['id'] or existing['user_id'] != user_id or existing['payload_hash'] != fingerprint):
            raise YouGileError('request_conflict', 'Подтверждение относится к другому поручению.', 409)
        if existing.get('status') == 'completed':
            return existing['result_json']
        if existing and not existing.get('external_task_id'):
            raise YouGileError('unknown_result', 'Предыдущая попытка уже выполнялась. Проверьте YouGile; автоматического повтора нет.', 409)
        task_id = existing.get('external_task_id')
        if task_id:
            write_state = 'verification_pending'
        if not existing:
            # Revalidate the exact approved payload and the current assignees/task.
            arguments = {'operation': payload.get('operation'), **payload.get('body', {})}
            if payload.get('operation') == 'complete':
                current = task_on_board(token, account, payload.get('task_id'))
                if digest(current) != payload.get('expected'):
                    raise YouGileError('stale_task', 'Задача изменилась. Подготовьте подтверждение заново.', 409)
                arguments['task_id'] = payload['task_id']
            if arguments.get('deadline'):
                arguments['deadline'] = datetime.fromtimestamp(arguments['deadline']['deadline'] / 1000, timezone.utc).isoformat()
            validated = prepare(cursor, business_id, user_id, arguments)
            if validated['body'] != payload.get('body'):
                raise YouGileError('invalid_preview', 'Данные задачи изменились. Подготовьте её заново.', 409)
            cursor.execute('''INSERT INTO yougile_task_requests(request_id,account_id,user_id,payload_hash,status)
                VALUES(%s,%s,%s,%s,'dispatching')''', (request_id, account['id'], user_id, fingerprint))
            conn.commit()  # Durable attempt before external write; session lock survives commit.
            write_state = 'unknown'
            try:
                if payload['operation'] == 'create':
                    created = yougile_client.request(token, 'POST', '/tasks', payload['body'])
                    try:
                        task_id = yougile_client.identifier(created.get('id'))
                    except YouGileError:
                        raise YouGileError('unknown_result', 'YouGile не вернул ID созданной задачи. Проверьте результат вручную.', 502) from None
                else:
                    task_id = payload['task_id']
                    yougile_client.request(token, 'PUT', '/tasks/' + task_id, payload['body'])
            except YouGileError:
                cursor.execute("UPDATE yougile_task_requests SET status='unknown',updated_at=NOW() WHERE request_id=%s", (request_id,))
                conn.commit()
                raise
            cursor.execute("UPDATE yougile_task_requests SET external_task_id=%s,status='verification_pending',updated_at=NOW() WHERE request_id=%s", (task_id, request_id))
            conn.commit()
            write_state = 'verification_pending'
        verified = task_on_board(token, account, task_id)
        matches = all(verified.get(k) == v for k, v in payload['body'].items() if k not in {'assigned', 'deadline'})
        matches = matches and set(verified.get('assigned') or []) == set(payload['body'].get('assigned') or [])
        if payload['body'].get('deadline'):
            matches = matches and all((verified.get('deadline') or {}).get(k) == v for k, v in payload['body']['deadline'].items())
        if (payload['operation'] == 'complete' and not verified.get('completed')) or (payload['operation'] == 'create' and not matches):
            raise YouGileError('verification_pending', 'Запись отправлена, но результат не подтверждён. Проверьте задачу в YouGile.', 409)
        result = {'status': 'completed', 'chat_response': 'Задача создана в YouGile.' if payload['operation'] == 'create' else 'Задача завершена в YouGile.',
                  'provider_write_performed': True, 'external_task_id': task_id, 'task': verified}
        cursor.execute("UPDATE yougile_task_requests SET status='completed',result_json=%s,updated_at=NOW() WHERE request_id=%s", (Json(result), request_id))
        conn.commit()
        return result
    except (YouGileError, PermissionError):
        import sys
        error = sys.exception()
        conn.rollback()
        code = getattr(error, 'code', 'access_denied')
        return {'status': 'blocked', 'chat_response': str(error), 'blocked_reasons': [code],
                'external_write_state': write_state,
                'provider_write_performed': True if write_state == 'verification_pending' else None if write_state == 'unknown' or code == 'unknown_result' else False}
    finally:
        conn.rollback()
        cursor.execute('SELECT pg_advisory_unlock(hashtext(%s))', ('yougile:' + business_id,))
        conn.commit()
        conn.close()
