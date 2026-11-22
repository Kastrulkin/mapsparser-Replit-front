"""Run-bound Google card writes through the existing ActionOrchestrator.

Existing OAuth/GoogleServices transport is reused. Preparing only reads Google;
only the orchestrator's approved handler can PATCH. Public moderation is separate.
"""
import hashlib
import json
import re
import uuid
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit

from services.map_card_transfer import load_report, load_progress, record
from services.operator_google_services import same_service

CAPABILITY = 'maps.google.publish'
FIELDS = {'name': 'Название', 'phone': 'Телефон', 'website': 'Сайт', 'description': 'Описание', 'services': 'Услуги'}
MASKS = {'name': 'title', 'phone': 'phoneNumbers', 'website': 'websiteUri', 'description': 'profile.description', 'services': 'serviceItems'}
READ_MASK = 'name,title,phoneNumbers,websiteUri,profile,categories,serviceItems,metadata'


class GooglePublicationError(ValueError):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def package(cursor, run_id):
    report = load_report(cursor, run_id)
    _id, progress = load_progress(cursor, run_id)
    state = progress.get('platforms', {}).get('google')
    if not state:
        card = next((c for c in report.get('cards', []) if c.get('provider') == 'google'), {})
        state = {'fields': {f['field']: str(f.get('proposed') or '') for f in card.get('fields', [])},
                 'services': report.get('services', []), 'steps': {}}
    return report, progress, state


def package_digest(state):
    return digest({'fields': state.get('fields', {}), 'services': state.get('services', [])})


def binding(cursor, business_id, *, read_client=True):
    cursor.execute("SELECT id,external_id,is_active FROM externalbusinessaccounts WHERE business_id=%s AND source='google_business'", (business_id,))
    rows = cursor.fetchall()
    if not rows:
        raise GooglePublicationError('Подключите Google Business Profile и выберите карточку компании.')
    if len(rows) != 1 or not rows[0].get('is_active'):
        raise GooglePublicationError('Нужно одно действующее подключение Google Business Profile для этой компании.')
    account = rows[0]
    if not re.fullmatch(r'(?:accounts/[^/]+/)?locations/[^/]+', account.get('external_id') or ''):
        raise GooglePublicationError('В подключении Google не выбрана карточка компании.')
    client = None
    if read_client:
        from services.operator_google_services import load_google
        client, _ = load_google(cursor, business_id, str(account['id']))
    # OAuth refresh may have rotated credentials. Bind consent to the current grant.
    cursor.execute('SELECT id,external_id,auth_data_encrypted,is_active FROM externalbusinessaccounts WHERE id=%s AND business_id=%s', (account['id'], business_id))
    current = cursor.fetchone() or {}
    if not current.get('is_active') or current.get('external_id') != account['external_id']:
        raise GooglePublicationError('Подключение Google изменилось. Подготовьте правки заново.')
    fingerprint = digest([str(current.get('id')), current.get('external_id'), current.get('auth_data_encrypted')])
    return client, {'account_id': str(account['id']), 'external_id': account['external_id'], 'fingerprint': fingerprint}


def request_json(client, method, *, body=None, mask=None):
    kwargs = {'params': {'readMask': READ_MASK} if method == 'get' else {'updateMask': mask}, 'timeout': 25}
    if body is not None:
        kwargs['json'] = body
    try:
        response = getattr(client.session, method)(client.url, **kwargs)
        if response.status_code in (401, 403):
            raise GooglePublicationError('Google не разрешил доступ. Проверьте подключение и права управления карточкой.')
        if response.status_code == 429:
            raise GooglePublicationError('Google временно ограничил запросы. Повторите проверку позже.')
        if not 200 <= response.status_code < 300:
            raise GooglePublicationError('Google не принял запрос. Проверьте данные и повторите подготовку правок.')
        return response.json()
    except GooglePublicationError:
        raise
    except Exception:
        raise GooglePublicationError('Не удалось получить определённый ответ Google. Проверьте результат повторным чтением, не отправляйте правки повторно.') from None


def value(location, key):
    if key == 'name': return location.get('title', '')
    if key == 'phone': return (location.get('phoneNumbers') or {}).get('primaryPhone', '')
    if key == 'website': return location.get('websiteUri', '')
    if key == 'description': return (location.get('profile') or {}).get('description', '')
    return location.get('serviceItems') or []


def equal(key, left, right):
    if key == 'phone': return re.sub(r'\D', '', left or '') == re.sub(r'\D', '', right or '')
    if key == 'website': return str(left or '').rstrip('/') == str(right or '').rstrip('/')
    if key == 'services':
        remaining = list(right)
        for item in left:
            match = next((i for i, saved in enumerate(remaining) if same_service(item, saved) and same_service(saved, item)), None)
            if match is None: return False
            remaining.pop(match)
        return not remaining
    return left == right


def service_list(location, proposed, currency):
    items = deepcopy(location.get('serviceItems') or [])
    if not proposed: return items
    if not (location.get('metadata') or {}).get('canModifyServiceList'):
        raise GooglePublicationError('Google не разрешает изменять услуги этой карточки. Снимите выбор услуг или перенесите их вручную.')
    category = ((location.get('categories') or {}).get('primaryCategory') or {}).get('name', '').removeprefix('categories/')
    if not category or not re.fullmatch('[A-Z]{3}', currency or ''):
        raise GooglePublicationError('Для услуг нужны категория карточки Google и валюта в профиле компании.')
    seen = set()
    for source in proposed:
        name = str(source.get('name') or '').strip()
        description = str(source.get('description') or '').strip()
        if not name or len(name) > 250 or name.casefold() in seen or len(description) > 1000:
            raise GooglePublicationError('Проверьте названия, описания и повторы услуг в пакете.')
        seen.add(name.casefold())
        try:
            raw = str(source.get('price') or '').strip().replace(',', '.')
            if not re.fullmatch(r'\d{1,12}(?:\.\d{1,9})?', raw): raise InvalidOperation
            price = Decimal(raw)
            if price <= 0: raise InvalidOperation
        except InvalidOperation:
            raise GooglePublicationError('Для каждой услуги нужна точная положительная цена без дополнительных слов.') from None
        matches = [i for i, item in enumerate(items) if str(((item.get('freeFormServiceItem') or {}).get('label') or {}).get('displayName', '')).casefold() == name.casefold()]
        if len(matches) > 1:
            raise GooglePublicationError('В Google несколько услуг с одинаковым названием. Уточните их вручную.')
        item = deepcopy(items[matches[0]]) if matches else {'freeFormServiceItem': {'categoryId': category, 'label': {}}}
        item['freeFormServiceItem']['label']['displayName'] = name
        if description: item['freeFormServiceItem']['label']['description'] = description
        units = int(price)
        item['price'] = {'currencyCode': currency, 'units': str(units), 'nanos': int((price - units) * 1000000000)}
        if matches: items[matches[0]] = item
        else: items.append(item)
    return items


def make_preview(location, state, selected, currency):
    if not isinstance(selected, list) or not selected or not all(isinstance(key, str) for key in selected) or set(selected) - set(FIELDS) or len(selected) != len(set(selected)):
        raise GooglePublicationError('Выберите поддерживаемые поля для Google.')
    body, changes, before = {}, [], {}
    for key in selected:
        proposed = str((state.get('fields') or {}).get(key) or '').strip() if key != 'services' else service_list(location, state.get('services') or [], currency)
        if key != 'services' and not proposed: continue  # Missing facts never clear existing Google values.
        if key == 'name' and len(proposed) > 300 or key == 'description' and len(proposed) > 750:
            raise GooglePublicationError('Название должно быть до 300 символов, описание Google — до 750.')
        if key == 'phone' and (not re.fullmatch(r'[+\d ()\-]{5,30}', proposed)):
            raise GooglePublicationError('Проверьте формат телефона.')
        if key == 'website':
            url = urlsplit(proposed)
            if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password:
                raise GooglePublicationError('Укажите полный адрес сайта без логина и пароля.')
        old = value(location, key)
        if equal(key, old, proposed): continue
        before[key] = deepcopy(old)
        changes.append({'field': key, 'label': FIELDS[key], 'before': old, 'after': proposed})
        if key == 'name': body['title'] = proposed
        elif key == 'phone': body['phoneNumbers'] = {**(location.get('phoneNumbers') or {}), 'primaryPhone': proposed}
        elif key == 'website': body['websiteUri'] = proposed
        elif key == 'description': body['profile'] = {**(location.get('profile') or {}), 'description': proposed}
        else: body['serviceItems'] = proposed
    # The whole phone object/service list is bound, including values retained by PATCH.
    guards = {'phoneNumbers': location.get('phoneNumbers') or {}} if 'phone' in before else {}
    return {'body': body, 'changes': changes, 'before': before, 'guards': guards,
            'update_mask': ','.join(MASKS[c['field']] for c in changes), 'google_name': location.get('name'), 'google_title': location.get('title')}


def verification(location, preview):
    fields = [{'field': c['field'], 'label': c['label'], 'matches': equal(c['field'], value(location, c['field']), c['after']), 'actual': value(location, c['field'])} for c in preview['changes']]
    return {'verified': all(f['matches'] for f in fields), 'fields': fields, 'public_card_verified': False,
            'has_pending_edits': bool((location.get('metadata') or {}).get('hasPendingEdits'))}


def apply_preview(client, preview):
    current = request_json(client, 'get')
    checked = verification(current, preview)
    if checked['verified']: return {**checked, 'provider_write_performed': False, 'already_present': True}
    if any(not equal(key, value(current, key), old) for key, old in preview['before'].items()) or any(current.get(key, {}) != old for key, old in preview.get('guards', {}).items()):
        raise GooglePublicationError('Карточка Google изменилась после подготовки. Обновите сравнение и подтвердите правки заново.')
    if 'services' in preview['before'] and not (current.get('metadata') or {}).get('canModifyServiceList'):
        raise GooglePublicationError('Google больше не разрешает менять услуги.')
    # No write retry after an ambiguous transport result. A subsequent operation is read-only verification.
    try:
        request_json(client, 'patch', body=preview['body'], mask=preview['update_mask'])
    except GooglePublicationError:
        try: checked = verification(request_json(client, 'get'), preview)
        except GooglePublicationError: checked = {'verified': False, 'fields': [], 'public_card_verified': False}
        return {**checked, 'provider_write_performed': None, 'write_outcome': 'uncertain', 'message': 'Ответ Google неопределён. Повторите только проверку результата; повторная отправка не выполняется.'}
    try: checked = verification(request_json(client, 'get'), preview)
    except GooglePublicationError: checked = {'verified': False, 'fields': [], 'public_card_verified': False}
    return {**checked, 'provider_write_performed': True, 'write_outcome': 'accepted', 'message': 'Google принял запрос. Публичная карточка и модерация проверяются отдельно.'}


def authorize(cursor, business_id, user_data, *, write=False):
    from core.auth_helpers import verify_business_access, verify_business_write_access
    allowed, _owner = (verify_business_write_access if write else verify_business_access)(cursor, business_id, user_data)
    if not allowed:
        raise PermissionError('Недостаточно прав для работы с Google этой компании.')


def load_action(cursor, run_id, action_id):
    cursor.execute('SELECT tenant_id,capability,payload_json,status,result_json FROM action_requests WHERE action_id=%s', (action_id,))
    action = cursor.fetchone() or {}
    payload = record(action.get('payload_json'))
    if action.get('capability') != CAPABILITY or str(payload.get('run_id')) != str(run_id):
        raise GooglePublicationError('Подтверждение не относится к этому пакету оформления.')
    return action, payload


def connection_status(cursor, business_id):
    base = {'supported_fields': [{'field': key, 'label': label} for key, label in FIELDS.items()],
            'manual_fields': ['Адрес', 'Часы работы', 'Фотографии'], 'approval_required': True,
            'connect_url': '/dashboard/settings?focus=google', 'public_card_verified': False}
    try:
        client, info = binding(cursor, business_id)
        location = request_json(client, 'get')
        return {**base, 'connected': True, 'state': 'readable', 'account_id': info['account_id'],
                'location': client.location, 'title': location.get('title'),
                'can_modify_services': bool((location.get('metadata') or {}).get('canModifyServiceList')),
                'message': 'Google подключён. Перед отправкой будут показаны конкретные правки. Право записи зависит от доступа к карточке.'}
    except Exception as error:
        message = str(error) if isinstance(error, GooglePublicationError) else 'Не удалось проверить Google. Проверьте подключение и повторите.'
        return {**base, 'connected': False, 'state': 'connection_required', 'message': message}


def prepare(cursor, run, user_data, body):
    authorize(cursor, str(run['business_id']), user_data, write=True)
    report, progress, state = package(cursor, str(run['id']))
    if type(body.get('revision')) is not int or body['revision'] != progress['revision']:
        raise GooglePublicationError('Пакет изменился. Загрузите сохранённый прогресс и подготовьте сравнение заново.')
    if not all((state.get('steps') or {}).get(key) for key in ('data', 'services', 'photos')):
        raise GooglePublicationError('Сначала проверьте и сохраните шаги «Данные», «Услуги» и «Фотографии».')
    client, info = binding(cursor, str(run['business_id']))
    current = request_json(client, 'get')
    cursor.execute("SELECT to_jsonb(b)->>'currency' currency FROM businesses b WHERE id=%s", (run['business_id'],))
    currency = (cursor.fetchone() or {}).get('currency') or ''
    preview = make_preview(current, state, body.get('selected_fields'), currency)
    if not preview['changes']:
        return {'success': True, 'status': 'no_changes', 'message': 'Выбранные сведения уже совпадают с Google. Запись не нужна.'}, None
    request_id = str(body.get('request_id') or '')
    try: uuid.UUID(request_id)
    except (ValueError, AttributeError): raise GooglePublicationError('Обновите страницу и подготовьте сравнение заново.') from None
    frozen = {'run_id': str(run['id']), 'business_id': str(run['business_id']), 'binding': info,
              'package_digest': package_digest(state), 'preview': preview}
    frozen['digest'] = digest(frozen)
    user_id = str(user_data.get('user_id') or user_data.get('id') or '')
    return {'tenant_id': str(run['business_id']), 'actor': {'id': user_id}, 'trace_id': str(uuid.uuid4()),
            'idempotency_key': f"map-google:{run['id']}:{frozen['digest']}:{request_id}",
            'capability': CAPABILITY, 'approval': {'mode': 'required', 'ttl_sec': 1800},
            'billing': {'reserve_tokens': 1, 'tariff_id': 'maps.google.publish'}, 'payload': frozen}, preview


def handle_apply(envelope, user_data):
    from database_manager import DatabaseManager
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        payload = envelope.get('payload') or {}
        business_id = str(envelope.get('tenant_id') or '')
        authorize(cursor, business_id, user_data, write=True)
        action, saved = load_action(cursor, payload.get('run_id'), envelope.get('action_id'))
        cursor.execute("SELECT status,expires_at >= NOW() live FROM action_approvals WHERE action_id=%s", (envelope.get('action_id'),))
        approval = cursor.fetchone() or {}
        if action.get('status') != 'executing' or approval.get('status') != 'approved' or not approval.get('live') or str(action.get('tenant_id')) != business_id or saved != payload:
            raise GooglePublicationError('Для записи требуется действующее подтверждение именно этих изменений.')
        cursor.execute('SELECT id,business_id FROM agent_runs WHERE id=%s FOR UPDATE', (payload.get('run_id'),))
        run = cursor.fetchone() or {}
        if str(run.get('business_id')) != business_id:
            raise GooglePublicationError('Пакет не относится к выбранной компании.')
        _report, _progress, state = package(cursor, payload['run_id'])
        if not all((state.get('steps') or {}).get(key) for key in ('data', 'services', 'photos')):
            raise GooglePublicationError('Подготовка больше не подтверждена. Проверьте шаги и подготовьте новое сравнение.')
        if package_digest(state) != payload.get('package_digest'):
            raise GooglePublicationError('Пакет изменён после подготовки. Сначала подготовьте новое сравнение.')
        # Serialize writes to the same Google location across runs and companies.
        cursor.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', ('map-google:' + payload['binding']['external_id'],))
        client, info = binding(cursor, business_id)
        if info != payload.get('binding'):
            raise GooglePublicationError('Подключение или выбранная карточка Google изменились. Подготовьте правки заново.')
        result = apply_preview(client, payload['preview'])
        result.update({'location': client.location, 'run_id': payload['run_id'], 'approval_digest': payload['digest'],
                       'billing': {'total_tokens': 0, 'cost': 0, 'tariff_id': 'maps.google.publish'}})
        db.conn.commit()
        return result
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


def orchestrator():
    from core.action_orchestrator import ActionOrchestrator
    return ActionOrchestrator({CAPABILITY: handle_apply})


def remember(cursor, run_id, action_id, payload, outcome=None):
    cursor.execute("SELECT id FROM agent_artifacts WHERE run_id=%s AND artifact_type='map_google_publication' AND payload_json->>'action_id'=%s", (run_id, action_id))
    row = cursor.fetchone()
    data = {'action_id': action_id, 'approval_digest': payload['digest'], 'preview': payload['preview'], 'outcome': outcome}
    if row:
        cursor.execute('UPDATE agent_artifacts SET payload_json=%s::jsonb WHERE id=%s', (json.dumps(data, ensure_ascii=False), row['id']))
    else:
        cursor.execute('INSERT INTO agent_artifacts(id,run_id,artifact_type,title,payload_json) VALUES(%s,%s,%s,%s,%s::jsonb)',
                       (str(uuid.uuid4()), run_id, 'map_google_publication', 'Правки Google: подтверждение и проверка', json.dumps(data, ensure_ascii=False)))


def workspace(run_id, user_data, body=None):
    from database_manager import DatabaseManager
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        cursor.execute('SELECT id,business_id,blueprint_id FROM agent_runs WHERE id=%s', (run_id,))
        run = cursor.fetchone()
        if not run: return {'error': 'Запуск не найден.'}, 404
        business_id = str(run['business_id'])
        authorize(cursor, business_id, user_data, write=body is not None)
        load_report(cursor, run_id)  # No write controls for previews, check reports or other agents.
        if body is None:
            status = connection_status(cursor, business_id)
            cursor.execute("SELECT payload_json FROM agent_artifacts WHERE run_id=%s AND artifact_type='map_google_publication' ORDER BY created_at DESC LIMIT 1", (run_id,))
            latest = record((cursor.fetchone() or {}).get('payload_json'))
            if latest:
                action, saved = load_action(cursor, run_id, latest['action_id'])
                if str(action.get('tenant_id')) == business_id:
                    status['publication'] = {**latest, 'status': action.get('status'), 'outcome': latest.get('outcome') or record(action.get('result_json'))}
            return status, 200
        operation = body.get('operation')
        if operation == 'prepare':
            cursor.execute('SELECT id FROM agent_runs WHERE id=%s FOR UPDATE', (run_id,))
            prepared, preview = prepare(cursor, run, user_data, body)
            db.conn.commit()
            if preview is None: return prepared, 200
            outcome = orchestrator().execute(prepared, user_data)
            if not outcome.get('success'):
                return {'error': 'Не удалось подготовить подтверждение Google. Проверьте права доступа.', 'status': outcome.get('status')}, 409
            remember(cursor, run_id, outcome['action_id'], prepared['payload'])
            db.conn.commit()
            return {**outcome, 'preview': preview, 'approval_digest': prepared['payload']['digest']}, 200
        action, saved = load_action(cursor, run_id, body.get('action_id'))
        if str(action.get('tenant_id')) != business_id or saved.get('business_id') != business_id:
            raise PermissionError('Подтверждение относится к другой компании.')
        if operation in ('approve', 'reject'):
            if body.get('approved_digest') != saved.get('digest') or operation == 'approve' and body.get('approved') is not True:
                raise GooglePublicationError('Подтвердите показанное сравнение изменений.')
            if action.get('status') in ('completed', 'failed', 'rejected', 'expired'):
                return {'success': True, 'action_id': body['action_id'], 'status': action['status'], 'result': record(action.get('result_json'))}, 200
            db.conn.commit()
            outcome = orchestrator().resolve_human_decision(body['action_id'], 'approved' if operation == 'approve' else 'rejected', user_data)
            remember(cursor, run_id, body['action_id'], saved, outcome.get('result'))
            db.conn.commit()
            return outcome, 200 if outcome.get('success') else 409
        if operation == 'verify':
            if action.get('status') not in ('completed', 'failed'):
                raise GooglePublicationError('Сначала подтвердите отправку изменений в Google.')
            client, info = binding(cursor, business_id)
            if info != saved.get('binding'):
                raise GooglePublicationError('Подключение Google изменилось. Проверка старого подтверждения остановлена.')
            result = verification(request_json(client, 'get'), saved['preview'])
            result['verification_only'] = True
            remember(cursor, run_id, body['action_id'], saved, result)
            db.conn.commit()
            return {'success': True, 'result': result, 'status': action.get('status')}, 200
        raise GooglePublicationError('Неизвестное действие.')
    except PermissionError as error:
        db.conn.rollback()
        return {'error': str(error)}, 403
    except GooglePublicationError as error:
        db.conn.rollback()
        return {'error': str(error)}, 409
    except ValueError:
        db.conn.rollback()
        return {'error': 'Проверьте пакет и выбранные поля Google.'}, 400
    except Exception:
        db.conn.rollback()
        return {'error': 'Не удалось обработать Google. Повторите проверку подключения; изменения автоматически не отправляются повторно.'}, 503
    finally:
        db.close()
