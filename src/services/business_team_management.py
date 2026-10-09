"""Owner-controlled membership proposals, apply receipts and invitation delivery."""
import re
import json
import secrets
import uuid
import sys
from services.business_chat_changes import row, digest, lock_receipt, save_receipt, resolve_target
from services.business_permissions import ROLE_PERMISSIONS, load_actor, require_permission

ASSIGNABLE_ROLES = ('admin', 'master', 'viewer', 'manager', 'member')
ROLE_LABELS = {'admin': 'Администратор', 'master': 'Мастер', 'viewer': 'Наблюдатель', 'manager': 'Управляющий', 'member': 'Сотрудник'}
PERMISSION_LABELS = {'business.read': 'просмотр бизнеса', 'operations.write': 'операционная работа', 'work.facts.write': 'свои рабочие сведения'}


def role_options():
    return [{'key': role, 'label': ROLE_LABELS[role],
             'permissions': [PERMISSION_LABELS[permission] for permission in sorted(ROLE_PERMISSIONS[role])]} for role in ASSIGNABLE_ROLES]


def scopes_for(cursor, anchor_id, user, arguments):
    kind = arguments.get('scope', 'business')
    if kind == 'business':
        references = arguments.get('businesses') if 'businesses' in arguments else [anchor_id]
        if not isinstance(references, list) or not 1 <= len(references) <= 20:
            raise ValueError('Укажите от одного до двадцати бизнесов.')
        scopes = []
        for reference in references:
            target = resolve_target(cursor, user, reference, anchor_id)
            require_permission(cursor, target, user, 'team.manage')
            cursor.execute('SELECT id,name,owner_id FROM businesses WHERE id=%s', (target,))
            business = row(cursor, cursor.fetchone())
            scopes.append({'kind': 'business', 'id': target, 'name': business['name'], 'owner_id': business['owner_id']})
        return list({scope['id']: scope for scope in scopes}.values())
    if kind != 'network':
        raise ValueError('Выберите доступ к бизнесу или ко всей сети.')
    cursor.execute('SELECT n.id,n.name,n.owner_id FROM networks n JOIN businesses b ON b.network_id=n.id WHERE b.id=%s', (anchor_id,))
    network = row(cursor, cursor.fetchone())
    if not network or (network['owner_id'] != user['user_id'] and not user.get('is_superadmin')):
        raise PermissionError('Доступ ко всей сети выдаёт её владелец.')
    if user.get('session_kind') == 'demo':
        raise PermissionError('В демонстрационном сеансе нельзя выдавать доступ к сети.')
    return [{'kind': 'network', **network}]


def snapshot(cursor, email, scopes, lock=False):
    cursor.execute('SELECT id,name,email,is_active,password_hash FROM users WHERE LOWER(email)=%s ORDER BY id LIMIT 2' + (' FOR UPDATE' if lock else ''), (email,))
    users = [row(cursor, raw) for raw in cursor.fetchall()]
    if len(users) > 1:
        raise ValueError('Найдено несколько аккаунтов с этим email. Требуется проверка.')
    user = users[0] if users else {}
    if user.get('is_active') is False:
        raise PermissionError('Аккаунт отключён. Владелец бизнеса не может активировать его повторно.')
    memberships = []
    inherited = []
    if user:
        for scope in scopes:
            if scope['owner_id'] == user['id']:
                raise ValueError('Нельзя менять роль владельца через добавление сотрудника.')
            table = 'business_members' if scope['kind'] == 'business' else 'network_members'
            column = 'business_id' if scope['kind'] == 'business' else 'network_id'
            cursor.execute('SELECT role,status FROM ' + table + ' WHERE ' + column + '=%s AND user_id=%s' + (' FOR UPDATE' if lock else ''), (scope['id'], user['id']))
            memberships.append({'scope': scope['id'], **row(cursor, cursor.fetchone())})
            if scope['kind'] == 'business':
                cursor.execute("""SELECT nm.role,b.network_id FROM network_members nm
                    JOIN businesses b ON b.network_id=nm.network_id
                    WHERE b.id=%s AND nm.user_id=%s AND nm.status='active'
                    UNION ALL SELECT 'owner',n.id FROM networks n JOIN businesses b ON b.network_id=n.id
                    WHERE b.id=%s AND n.owner_id=%s ORDER BY role""", (scope['id'],user['id'],scope['id'],user['id']))
                inherited.extend({'business_id':scope['id'],**row(cursor,raw)} for raw in cursor.fetchall())
    return {'user_id': user.get('id'), 'name': user.get('name') or '', 'is_active': user.get('is_active'),
            'has_password': bool(user.get('password_hash')), 'memberships': memberships,'inherited':inherited}


def prepare(cursor, anchor_id, user_id, arguments, session=None):
    user = load_actor(cursor, user_id)
    if session:
        user.update({key: session[key] for key in ('session_kind', 'scope_business_id') if key in session})
    require_permission(cursor, anchor_id, user, 'team.manage')
    email = arguments.get('email')
    if not isinstance(email, str) or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email.strip()) or len(email) > 254:
        raise ValueError('Укажите email сотрудника.')
    email = email.strip().lower()
    role = arguments.get('role')
    if role not in ASSIGNABLE_ROLES:
        raise ValueError('Выберите роль: администратор, мастер или наблюдатель.')
    name = arguments.get('name', '')
    if not isinstance(name, str) or len(name) > 200:
        raise ValueError('Проверьте имя сотрудника.')
    send_invitation = arguments.get('send_invitation', False)
    if not isinstance(send_invitation, bool):
        raise ValueError('Укажите, отправлять ли приглашение.')
    scopes = scopes_for(cursor, anchor_id, user, arguments)
    before = snapshot(cursor, email, scopes)
    return {'anchor_business_id': anchor_id, 'actor_user_id': user_id, 'email': email, 'name': before['name'] if before['user_id'] else name.strip(),
            'role': role, 'scopes': scopes, 'before_hash': digest(before),
            'before_memberships': before['memberships'], 'inherited': before['inherited'],
            'send_invitation': send_invitation, 'account_created': not bool(before['user_id'])}


def preview_text(payload):
    permission_text = ', '.join(PERMISSION_LABELS[key] for key in sorted(ROLE_PERMISSIONS[payload['role']]))
    lines = ['Добавить сотрудника в LocalOS:', payload['name'] + ' · ' + payload['email'],
             'Роль: ' + ROLE_LABELS[payload['role']],
             'Доступ: ' + ', '.join(scope['name'] + (' (вся сеть)' if scope['kind'] == 'network' else '') for scope in payload['scopes']),
             'Разрешено: ' + permission_text + '.', 'Настройки бизнеса и выдача доступа остаются у владельца.']
    if payload['account_created']:
        lines.append('Будет создан отдельный аккаунт сотрудника.')
    else:
        lines.append('Будет использован существующий аккаунт. Его личные данные не изменяются.')
    for membership in payload['before_memberships']:
        scope = next(item for item in payload['scopes'] if item['id'] == membership['scope'])
        old = ROLE_LABELS.get(membership.get('role'), 'нет прямого доступа') if membership.get('status') == 'active' else 'нет активного доступа'
        lines.append(scope['name'] + ': ' + old + ' → ' + ROLE_LABELS[payload['role']])
    if payload['inherited']:
        lines.append('Дополнительный доступ через сеть сохранится: ' + ', '.join(ROLE_LABELS.get(item['role'],'Владелец') for item in payload['inherited']) + '. Прямая роль не ограничивает более широкие сетевые права.')
    lines.append('Приглашение по email: ' + ('отправить после подтверждения' if payload['send_invitation'] else 'не отправлять'))
    lines.append('Подтвердить добавление' + (' и отправку приглашения?' if payload['send_invitation'] else '?'))
    return '\n'.join(lines)


def apply(cursor, anchor_id, user_id, payload, action_id):
    if payload.get('anchor_business_id') != anchor_id or payload.get('actor_user_id') != user_id:
        raise PermissionError('Подтверждение относится к другому пользователю или бизнесу.')
    user = load_actor(cursor, user_id)
    require_permission(cursor, anchor_id, user, 'team.manage')
    replay = lock_receipt(cursor, action_id, user_id, anchor_id, payload)
    if replay is not None:
        return replay
    if payload.get('role') not in ASSIGNABLE_ROLES:
        raise ValueError('Недопустимая роль.')
    cursor.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', ('team-email:' + payload['email'],))
    # Rebuild scope ownership and lock it before comparing the preview.
    for scope in sorted(payload['scopes'], key=lambda item: item['id']):
        if scope['kind'] == 'business':
            require_permission(cursor, scope['id'], user, 'team.manage')
            cursor.execute('SELECT owner_id FROM businesses WHERE id=%s FOR UPDATE', (scope['id'],))
        elif scope['kind'] == 'network':
            cursor.execute('SELECT owner_id FROM networks WHERE id=%s FOR UPDATE', (scope['id'],))
        else:
            raise ValueError('Недопустимая область доступа.')
        owner = row(cursor, cursor.fetchone()).get('owner_id')
        if owner != scope['owner_id'] or (scope['kind'] == 'network' and owner != user_id and not user.get('is_superadmin')):
            raise PermissionError('Владелец области доступа изменился.')
    if digest(snapshot(cursor, payload['email'], payload['scopes'],lock=True)) != payload['before_hash']:
        raise ValueError('Аккаунт или права сотрудника изменились. Подготовьте новое подтверждение.')
    cursor.execute('SELECT id,password_hash,verification_token,is_active FROM users WHERE LOWER(email)=%s FOR UPDATE', (payload['email'],))
    account = row(cursor, cursor.fetchone())
    if account.get('is_active') is False:
        raise PermissionError('Аккаунт отключён.')
    target_id = account.get('id') or str(uuid.uuid4())
    if not account:
        token = secrets.token_urlsafe(32)
        cursor.execute('INSERT INTO users(id,email,name,is_active,is_verified,verification_token,created_at,updated_at) VALUES (%s,%s,%s,TRUE,FALSE,%s,NOW(),NOW())',
                       (target_id, payload['email'], payload['name'] or None, token))
    elif payload['send_invitation'] and not account.get('password_hash') and not account.get('verification_token'):
        cursor.execute('UPDATE users SET verification_token=%s,updated_at=NOW() WHERE id=%s', (secrets.token_urlsafe(32), target_id))
    for scope in payload['scopes']:
        table = 'business_members' if scope['kind'] == 'business' else 'network_members'
        column = 'business_id' if scope['kind'] == 'business' else 'network_id'
        before = next((item for item in payload['before_memberships'] if item['scope'] == scope['id']),{})
        if before.get('role'):
            cursor.execute('UPDATE ' + table + " SET role=%s,status='active',updated_at=NOW() WHERE " + column + '=%s AND user_id=%s AND role=%s AND status=%s',
                           (payload['role'],scope['id'],target_id,before['role'],before['status']))
        else:
            cursor.execute('INSERT INTO ' + table + '(id,' + column + ",user_id,role,status,created_by_user_id) VALUES (%s,%s,%s,%s,'active',%s) ON CONFLICT(" + column + ',user_id) DO NOTHING',
                           (str(uuid.uuid4()),scope['id'],target_id,payload['role'],user_id))
        if cursor.rowcount != 1:
            raise ValueError('Права сотрудника изменились. Подготовьте новое подтверждение.')
    result = {'status': 'completed', 'chat_response': 'Доступ сотрудника сохранён. ' + ('Приглашение подготовлено к отправке.' if payload['send_invitation'] else 'Приглашение не отправлялось.'),
              'user_id': target_id, 'membership_saved': True, 'invitation_status': 'pending' if payload['send_invitation'] else 'not_requested',
              'localos_write_performed': True, 'provider_write_performed': False}
    save_receipt(cursor, action_id, user_id, anchor_id, payload, result)
    if payload['send_invitation']:
        cursor.execute('INSERT INTO business_team_invitations(action_id,recipient_user_id) VALUES (%s,%s)', (action_id, target_id))
    return result


def deliver_invitation(db, action_id, result):
    from core.email_delivery import send_email, build_password_setup_link
    cursor = db.conn.cursor()
    cursor.execute("UPDATE business_team_invitations SET status='sending',updated_at=NOW() WHERE action_id=%s AND status='pending' RETURNING recipient_user_id", (action_id,))
    claimed = row(cursor, cursor.fetchone())
    db.conn.commit()
    if claimed:
        cursor.execute('SELECT email,name,password_hash,verification_token,is_active FROM users WHERE id=%s', (claimed['recipient_user_id'],))
        account = row(cursor, cursor.fetchone())
        db.conn.commit()
        sent = False
        if account and account.get('is_active') is not False:
            link = 'https://localos.pro/login' if account.get('password_hash') else build_password_setup_link(account['email'], account['verification_token'])
            sent = bool(send_email(account['email'], 'Приглашение в LocalOS', 'Вам открыт доступ к бизнесу в LocalOS.\nДля входа: ' + link))
        cursor.execute('UPDATE business_team_invitations SET status=%s,updated_at=NOW() WHERE action_id=%s', ('sent' if sent else 'failed', action_id))
        db.conn.commit()
    cursor.execute('SELECT status FROM business_team_invitations WHERE action_id=%s', (action_id,))
    status = row(cursor, cursor.fetchone()).get('status') or 'not_requested'
    messages = {'sent': 'Приглашение принято почтовым сервером.', 'failed': 'Приглашение отправить не удалось.',
                'sending': 'Отправка приглашения началась; результат пока не подтверждён.', 'pending': 'Приглашение ожидает отправки.', 'not_requested': 'Приглашение не отправлялось.'}
    result = {**result, 'invitation_status': status, 'provider_write_performed': status == 'sent',
              'chat_response': 'Доступ сотрудника сохранён. ' + messages[status]}
    cursor.execute('UPDATE business_change_receipts SET result_json=%s::jsonb WHERE action_id=%s', (json.dumps(result, ensure_ascii=False), action_id))
    db.conn.commit()
    return result


def handle_apply(envelope, user_data):
    from database_manager import DatabaseManager
    user_id = (envelope.get('actor') or {}).get('id')
    if user_id != (user_data.get('user_id') or user_data.get('id')):
        raise PermissionError('Пользователь подтверждения изменился.')
    db = DatabaseManager()
    try:
        result = apply(db.conn.cursor(), envelope['tenant_id'], user_id, envelope.get('payload') or {}, envelope.get('action_id'))
        db.conn.commit()
        if result.get('invitation_status') != 'not_requested':
            try:
                result = deliver_invitation(db, envelope['action_id'], result)
            except Exception:
                db.conn.rollback()
                result = {**result,'invitation_status':'sending','chat_response':'Доступ сотрудника сохранён. Результат отправки приглашения пока не подтверждён.'}
        return result
    except (ValueError, PermissionError):
        error = sys.exception()
        db.conn.rollback()
        return {'status': 'blocked', 'chat_response': str(error), 'localos_write_performed': False}
    finally:
        db.close()
