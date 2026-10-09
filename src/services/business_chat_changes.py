"""Versioned profile previews and atomic approved multi-business updates."""
import hashlib
import json
import sys
from services.business_settings_registry import FIELDS, normalize_patch
from services.business_permissions import load_actor, require_permission


def row(cursor, raw):
    if raw is None:
        return {}
    if hasattr(raw, 'keys'):
        return dict(raw)
    return dict(zip((column[0] for column in cursor.description), raw))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()


def lock_receipt(cursor, action_id, user_id, anchor_id, payload):
    if not action_id:
        raise ValueError('Отсутствует подтверждённое действие.')
    cursor.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', ('business-change:' + action_id,))
    cursor.execute('SELECT * FROM business_change_receipts WHERE action_id=%s', (action_id,))
    saved = row(cursor, cursor.fetchone())
    if saved:
        if saved['actor_user_id'] != user_id or saved['anchor_business_id'] != anchor_id or saved['payload_hash'] != digest(payload):
            raise ValueError('Подтверждение относится к другому изменению.')
        return saved['result_json']
    return None


def save_receipt(cursor, action_id, user_id, anchor_id, payload, result):
    cursor.execute('INSERT INTO business_change_receipts(action_id,actor_user_id,anchor_business_id,payload_hash,result_json) VALUES (%s,%s,%s,%s,%s::jsonb)',
                   (action_id, user_id, anchor_id, digest(payload), json.dumps(result, ensure_ascii=False)))


def owned_businesses(cursor, user):
    cursor.execute("""SELECT b.id, b.name, b.network_id FROM businesses b
        LEFT JOIN networks n ON n.id=b.network_id
        WHERE (b.is_active=TRUE OR b.is_active IS NULL)
          AND (b.owner_id=%s OR n.owner_id=%s OR %s)
        ORDER BY b.name, b.id LIMIT 1000""", (user['user_id'], user['user_id'], bool(user.get('is_superadmin'))))
    return [row(cursor, raw) for raw in cursor.fetchall()]


def search_businesses(cursor, user, reference=None, *, exact=False, id_only=False, limit=51):
    """Search authorized rows before limiting; never resolve from a catalogue page."""
    condition = ''
    params = [user['user_id'], user['user_id'], bool(user.get('is_superadmin')),
              user['user_id'], user['user_id'], user.get('session_kind') == 'demo', user.get('scope_business_id')]
    if reference:
        if id_only:
            condition = ' AND b.id=%s'
            params.append(reference)
        elif exact:
            condition = ' AND (b.id=%s OR LOWER(b.name)=LOWER(%s) OR LOWER(n.name)=LOWER(%s))'
            params.extend([reference, reference, reference])
        else:
            condition = ' AND (b.id=%s OR POSITION(LOWER(%s) IN LOWER(b.name))>0 OR POSITION(LOWER(%s) IN LOWER(n.name))>0)'
            params.extend([reference, reference, reference])
    params.append(limit)
    cursor.execute("""SELECT b.id,b.name,b.network_id,n.name network_name FROM businesses b
        LEFT JOIN networks n ON n.id=b.network_id
        WHERE b.is_active IS DISTINCT FROM FALSE
          AND (b.owner_id=%s OR n.owner_id=%s OR %s
               OR EXISTS(SELECT 1 FROM business_members m WHERE m.business_id=b.id AND m.user_id=%s AND m.status='active')
               OR EXISTS(SELECT 1 FROM network_members m WHERE m.network_id=b.network_id AND m.user_id=%s AND m.status='active'))
          AND (NOT %s OR b.id=%s)""" + condition + ' ORDER BY b.name,b.id LIMIT %s', tuple(params))
    return [row(cursor, raw) for raw in cursor.fetchall()]


def selected_business(cursor, user, anchor_id):
    return next((business for business in search_businesses(cursor,user,anchor_id,id_only=True)
                 if business['id'] == anchor_id), None)


def resolve_target(cursor, user, reference, anchor_id):
    if not reference:
        return anchor_id
    if not isinstance(reference, str):
        raise ValueError('Укажите название или идентификатор бизнеса.')
    reference = reference.strip()
    selected = selected_business(cursor,user,anchor_id)
    if selected and reference.casefold() in {selected['id'].casefold(), (selected.get('network_name') or '').casefold()}:
        return anchor_id
    businesses = search_businesses(cursor,user,reference,exact=True)
    by_id = [business for business in businesses if business['id'] == reference]
    if by_id:
        return by_id[0]['id']
    matches = [business for business in businesses if (business.get('name') or '').casefold() == reference.casefold()]
    if not matches:
        matches = businesses
    if not matches:
        matches = search_businesses(cursor,user,reference)
    if len(matches) != 1:
        raise ValueError('Уточните бизнес «' + reference + '».' + (' Варианты: ' + ', '.join(business['name'] for business in matches[:10]) if matches else ''))
    return matches[0]['id']


def read_profile(cursor, business_id):
    from services.business_input_settings import resolve
    cursor.execute('SELECT to_jsonb(b) data FROM businesses b WHERE id=%s', (business_id,))
    business = row(cursor, cursor.fetchone()).get('data') or {}
    if not business:
        raise ValueError('Бизнес не найден.')
    cursor.execute('SELECT * FROM businessprofiles WHERE business_id=%s', (business_id,))
    contacts = row(cursor, cursor.fetchone())
    defaults = resolve(cursor, business_id)
    values = {key: business.get(key) or '' for key in FIELDS}
    values['website'] = business.get('site') or business.get('website') or ''
    for key in ('contact_name', 'contact_phone', 'contact_email'):
        values[key] = contacts.get(key) or ''
    for key in ('currency', 'timezone'):
        values[key] = defaults.get(key) or ''
    temporary=None
    if defaults.get('timezone'):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        from services.operator_owner_actions import effective_hours
        temporary=effective_hours(cursor,business_id,datetime.now(ZoneInfo(defaults['timezone'])).date().isoformat())
    return {'business_id': business_id, 'name': business.get('name') or business_id,
            'temporary_working_hours': temporary,
            'values': values, 'coordinates': {'geo_lat': business.get('geo_lat'), 'geo_lon': business.get('geo_lon')},
            'profile_revision': business.get('updated_at'), 'contacts_revision': contacts.get('updated_at'),
            'defaults_version': defaults.get('version', 0), 'default_conflicts': defaults.get('conflicts', [])}


def prepare(cursor, anchor_id, user_id, arguments, session=None):
    user = load_actor(cursor, user_id)
    if session:
        user.update({key: session[key] for key in ('session_kind', 'scope_business_id') if key in session})
    require_permission(cursor, anchor_id, user, 'business.settings.write')
    requests = arguments.get('changes')
    if not isinstance(requests, list) or not 1 <= len(requests) <= 20:
        raise ValueError('Укажите от одного до двадцати бизнесов и новые настройки.')
    changes = []
    seen = set()
    from services.business_input_settings import city_timezone
    for request in requests:
        if not isinstance(request, dict):
            raise ValueError('Проверьте список изменений.')
        target = resolve_target(cursor, user, request.get('business'), anchor_id)
        require_permission(cursor, target, user, 'business.settings.write')
        if target in seen:
            raise ValueError('Объедините настройки одного бизнеса в одну строку.')
        seen.add(target)
        before = read_profile(cursor, target)
        patch = normalize_patch(request.get('patch'))
        notices = []
        if 'city' in patch and patch['city'] != before['values']['city']:
            if 'timezone' not in patch:
                zone = city_timezone(patch['city'])
                if not zone:
                    raise ValueError('Для города «' + patch['city'] + '» укажите часовой пояс IANA.')
                patch['timezone'] = zone
            notices.append('Проверьте часовой пояс после смены города.')
        clear_coordinates = any(key in patch and patch[key] != before['values'][key] for key in ('address', 'city'))
        if clear_coordinates and any(value is not None for value in before['coordinates'].values()):
            notices.append('Прежние координаты будут очищены; новую точку нужно проверить на карте.')
        changed = {key: value for key, value in patch.items() if before['values'][key] != value}
        # A conflicting default must be explicitly saved even if the displayed value is empty.
        if not changed:
            continue
        changes.append({'business_id': target, 'name': before['name'], 'patch': changed,
                        'before_hash': digest(before), 'before': before['values'],
                        'clear_coordinates': clear_coordinates, 'notices': notices})
    if not changes:
        raise ValueError('Эти значения уже сохранены. Изменений нет.')
    return {'anchor_business_id': anchor_id, 'actor_user_id': user_id, 'changes': changes}


def preview_text(payload):
    lines = ['Изменения только в профиле LocalOS:']
    for change in payload['changes']:
        lines.append('\n' + change['name'])
        for key, value in change['patch'].items():
            lines.append(FIELDS[key]['label'] + ': ' + (change['before'][key] or 'не задано') + ' → ' + (value or 'очистить'))
        lines.extend(change['notices'])
    lines.append('\nПодтвердить изменения?')
    return '\n'.join(lines)


def save_values(cursor, business_id, user_id, patch, action_id, settings_version=None):
    """Shared persistence for an approved chat preview or an explicit form save."""
    from services import finance_daily
    from services.business_input_settings import authorize_write
    authorize_write(cursor,business_id,user_id)
    cursor.execute('SELECT id FROM businesses WHERE id=%s FOR UPDATE', (business_id,))
    cursor.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', ('finance-daily:' + business_id,))
    patch = normalize_patch(patch)
    current = read_profile(cursor,business_id)
    from services.business_input_settings import city_timezone
    if patch.get('city') and patch['city'] != current['values']['city'] and not patch.get('timezone'):
        zone = city_timezone(patch['city'])
        if not zone:
            raise ValueError('Укажите часовой пояс для нового города.')
        patch['timezone'] = zone
    defaults = {key:value for key,value in patch.items() if key in {'currency','timezone','city'} and current['values'][key] != value}
    if defaults:
        if settings_version is not None and settings_version != current['defaults_version']:
            raise ValueError('Настройки изменились. Обновите профиль перед сохранением.')
        prepared = finance_daily.prepare(cursor,business_id,user_id,{'kind':'settings',**defaults},'profile',action_id)
        finance_daily.apply(cursor,business_id,user_id,prepared,action_id + ':' + business_id)
    assignments = []
    params = []
    for key,value in patch.items():
        for column in FIELDS[key].get('columns',[]):
            assignments.append(column + '=%s'); params.append(value or None)
    if any(key in patch and patch[key] != current['values'][key] for key in ('address','city')):
        assignments.extend(['geo_lat=NULL','geo_lon=NULL'])
    if assignments:
        cursor.execute('UPDATE businesses SET ' + ','.join(assignments) + ',updated_at=NOW() WHERE id=%s',(*params,business_id))
    contacts = {key:value for key,value in patch.items() if FIELDS[key].get('table') == 'businessprofiles'}
    if contacts:
        columns=list(contacts)
        cursor.execute('INSERT INTO businessprofiles(business_id,' + ','.join(columns) + ') VALUES (%s,' + ','.join(['%s']*len(columns)) + ') ON CONFLICT(business_id) DO UPDATE SET ' + ','.join(key+'=EXCLUDED.'+key for key in columns) + ',updated_at=NOW()', (business_id,*contacts.values()))


def apply(cursor, anchor_id, user_id, payload, action_id):
    if payload.get('anchor_business_id') != anchor_id or payload.get('actor_user_id') != user_id:
        raise PermissionError('Подтверждение относится к другому бизнесу или пользователю.')
    user = load_actor(cursor, user_id)
    require_permission(cursor, anchor_id, user, 'business.settings.write')
    replay = lock_receipt(cursor, action_id, user_id, anchor_id, payload)
    if replay is not None:
        return replay
    changes = payload.get('changes')
    if not isinstance(changes, list) or not 1 <= len(changes) <= 20:
        raise ValueError('Неверное подтверждение.')
    targets = sorted({change['business_id'] for change in changes})
    if len(targets) != len(changes):
        raise ValueError('Повторный бизнес в подтверждении.')
    for target in targets:
        require_permission(cursor, target, user, 'business.settings.write')
        cursor.execute('SELECT id FROM businesses WHERE id=%s FOR UPDATE', (target,))
        cursor.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', ('finance-daily:' + target,))
    for change in changes:
        current = read_profile(cursor, change['business_id'])
        if digest(current) != change['before_hash']:
            raise ValueError('Настройки «' + change['name'] + '» изменились. Подготовьте новое подтверждение.')
        normalize_patch(change['patch'])
    for change in changes:
        save_values(cursor,change['business_id'],user_id,change['patch'],action_id)
    result = {'status': 'completed', 'chat_response': 'Настройки сохранены в LocalOS: ' + ', '.join(change['name'] for change in changes) + '.',
              'business_ids': targets, 'localos_write_performed': True, 'provider_write_performed': False}
    save_receipt(cursor, action_id, user_id, anchor_id, payload, result)
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
        return result
    except (ValueError, PermissionError):
        error = sys.exception()
        db.conn.rollback()
        return {'status': 'blocked', 'chat_response': str(error), 'localos_write_performed': False}
    finally:
        db.close()
