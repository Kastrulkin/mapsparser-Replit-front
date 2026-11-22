"""One-shot, evidence-bound initial map parsing in the existing parsequeue.

No LLM, content regeneration, external writes, automatic fallback or paid retry.
The attempt is committed before I/O; a worker restart cannot buy another run.
"""
import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from urllib.parse import parse_qs, urlsplit

from core.card_platform_policy import provider_rules
from services.map_card_agents import FACT_LABELS, LABELS, listing_url

ARTIFACT = 'map_card_initial_audit'
TASK = 'map_card_initial_audit'
APIFY_CAP = Decimal('0.50')
GOOGLE_MASK = 'name,title,storefrontAddress,phoneNumbers,websiteUri,profile,categories,regularHours,specialHours,serviceItems,metadata,openInfo'


class AuditReadError(ValueError):
    """Only fixed, user-safe messages from this module may enter the report."""


def now():
    return datetime.now(timezone.utc).isoformat()


def record(value):
    if hasattr(value, 'model_dump'):
        return value.model_dump(by_alias=True, mode='json')
    return json.loads(value) if isinstance(value, str) else value or {}


def public_url(provider, value):
    url = listing_url(provider, value)
    path = urlsplit(url).path
    if provider == 'yandex' and not re.search(r'/org/(?:[^/]+/)?\d+/?$', path):
        return ''
    if provider == '2gis' and not re.search(r'/firm/\d+/?$', path):
        return ''
    return url


def entity_key(provider, url):
    parsed = urlsplit(url)
    if provider in ('yandex', '2gis'):
        return parsed.path.rstrip('/').rsplit('/', 1)[-1]
    query = parse_qs(parsed.query)
    return (query.get('query_place_id') or query.get('cid') or [url])[0]


def items(cursor, business_id):
    cursor.execute('''SELECT a.id, a.payload_json FROM agent_artifacts a
        JOIN agent_runs r ON r.id=a.run_id
        WHERE r.business_id=%s AND a.artifact_type=%s ORDER BY a.created_at DESC''',
        (business_id, ARTIFACT))
    return [{**record(row['payload_json']), 'id': str(row['id'])} for row in cursor.fetchall()]


def combined_checks(audits):
    """Unknown parser fields never erase an explicit observation of the same card."""
    complete = [a for a in audits if a.get('status') == 'completed']
    if not complete:
        return []
    identity = entity_key(complete[0]['provider'], complete[0].get('url') or '')
    fields = {}
    for audit in complete:
        if entity_key(audit['provider'], audit.get('url') or '') != identity:
            continue
        for check in audit.get('checks', []):
            previous = fields.get(check['field'])
            if previous is None or previous.get('state') in ('unknown','blocked') and check.get('state') in ('observed','missing'):
                fields[check['field']] = check
    return list(fields.values())


def view(cursor, business_id):
    from services.card_growth_service import _latest_sources
    links, snapshots = _latest_sources(cursor, business_id)
    latest = {}
    saved = items(cursor, business_id)
    for item in saved:
        latest.setdefault(item['provider'], item)
    cards = []
    for provider in LABELS:
        url = public_url(provider, (links.get(provider) or {}).get('url')) or public_url(provider, (snapshots.get(provider) or {}).get('url')) or public_url(provider, (latest.get(provider) or {}).get('url'))
        completed = next((a for a in saved if a['provider'] == provider and a.get('status') == 'completed' and entity_key(provider, a.get('url') or '') == entity_key(provider, url)), None)
        cards.append({'provider': provider, 'label': LABELS[provider], 'url': url,
                      'audit': latest.get(provider), 'attempts': [i for i in saved if i['provider'] == provider],
                      'combined_checks': combined_checks([i for i in saved if i['provider'] == provider]),
                      'default_method': completed['method'] if completed else 'google_api' if provider == 'google' else 'native'})
    return {'cards': cards, 'apify_cap_usd': str(APIFY_CAP), 'llm_calls': 0, 'provider_write_performed': False}


def ensure_initial_read(cursor, run, providers):
    """First setup reads once. Never buys Apify, retries, or refreshes old cards."""
    results = []
    for card in view(cursor, str(run['business_id']))['cards']:
        provider = card['provider']
        if provider not in providers:
            continue
        saved = [a for a in card['attempts'] if (
            (card['url'] and entity_key(provider, a.get('url') or '') == entity_key(provider, card['url']))
            or (not card['url'] and a.get('status') == 'not_created'))]
        # A completed paid snapshot is reused; a failed paid attempt never buys
        # another request or silently switches to a different parser.
        audit = next((a for a in saved if a.get('status') == 'completed'), None) or next(iter(saved), None)
        if not audit:
            method = 'google_api' if provider == 'google' else 'native'
            try:
                audit = enqueue(cursor, run, run['created_by_user_id'], provider, method, card['url'])
            except ValueError:
                results.append({'provider': provider, 'status': 'unknown',
                    'reason': 'Подключите Google Business для бесплатного чтения.' if provider == 'google' else 'Добавьте ссылку на карточку или подтвердите, что она пока не создана.'})
                continue
        if audit.get('status') == 'queued' and audit.get('method') != 'apify':
            # Make the run and attempt durable before another connection reads
            # them. Claim only this task, never drain the shared parsing queue.
            cursor.connection.commit()
            cursor.execute("UPDATE parsequeue SET status='processing',updated_at=CURRENT_TIMESTAMP WHERE id=%s AND status='pending' RETURNING *", (audit['id'],))
            task = cursor.fetchone()
            cursor.connection.commit()
            if task:
                execute_task(dict(task), initial_native_readers() if audit['method'] == 'native' else {})
            audit = next(a for a in items(cursor, str(run['business_id'])) if a['id'] == audit['id'])
        if audit.get('status') in ('queued', 'reading'):
            audit = await_initial_read(cursor, str(run['business_id']), audit)
        results.append({key: audit.get(key) for key in ('id', 'provider', 'method', 'status', 'reason', 'observed_at')})
    return results


def await_initial_read(cursor, business_id, audit):
    """A competing worker owns the same task; wait without launching another."""
    import time
    deadline = time.monotonic() + 190
    while audit.get('status') in ('queued', 'reading') and time.monotonic() < deadline:
        time.sleep(1)
        audit = next(a for a in items(cursor, business_id) if a['id'] == audit['id'])
    return audit


def initial_native_readers():
    # Reuse the exact bounded readers used by the existing parsing worker.
    # Import only when an actual unsaved native task is claimed.
    def read_yandex(url):
        from worker import _parse_yandex_card_with_playwright_fallback
        return _parse_yandex_card_with_playwright_fallback(url, keep_open_on_captcha=False, timeout_sec=90, force_subprocess=True, headless=True)

    def read_2gis(url):
        from worker import _parse_2gis_card_with_playwright_fallback
        return _parse_2gis_card_with_playwright_fallback(url, timeout_sec=90, headless=True)

    return {
        'yandex': read_yandex,
        '2gis': read_2gis,
    }


def enqueue(cursor, run, user_id, provider, method, url='', paid_consent=False, previous_attempt_id=None):
    if provider not in LABELS or method not in ('native', 'google_api', 'apify'):
        raise ValueError('Выберите площадку и способ чтения.')
    if method == 'google_api' and provider != 'google' or method == 'native' and provider == 'google':
        raise ValueError('Для Google выберите Google API или Apify; для Яндекса и 2ГИС — встроенный парсер или Apify.')
    if method == 'apify' and paid_consent is not True:
        raise ValueError('Сначала подтвердите один платный запуск Apify с лимитом $0.50. Автоматической замены парсера нет.')
    identity = public_url(provider, url)
    if method == 'google_api':
        from services.map_google_publication import binding
        _client, account = binding(cursor, str(run['business_id']), read_client=False)
        identity = account['external_id']
    elif not identity:
        raise ValueError('Нужна публичная ссылка на конкретную карточку выбранной площадки.')
    previous = None
    if previous_attempt_id:
        previous = next((a for a in items(cursor, str(run['business_id'])) if a.get('id') == previous_attempt_id), None)
        if not previous or method != 'apify' or previous.get('method') != method or previous['provider'] != provider or previous.get('status') != 'blocked' or entity_key(provider, previous.get('url') or '') != entity_key(provider, identity):
            raise ValueError('Новая попытка требует сохранённой ошибки именно этой карточки и нового согласования Apify.')
        if previous.get('provider_start_attempted_at') and previous.get('apify_run_status') not in ('SUCCEEDED','FAILED','TIMED-OUT','ABORTED'):
            raise ValueError('Исход предыдущего платного запроса не определён. Сначала проверьте его, новый запуск запрещён.')
    key_parts = [provider, method, identity if method == 'google_api' else entity_key(provider, identity)]
    if previous:
        key_parts.append(previous_attempt_id)
    key = hashlib.sha256(json.dumps(key_parts).encode()).hexdigest()
    # Serialize across different agent runs as well as double clicks.
    cursor.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', ('map-initial:'+str(run['business_id'])+key,))
    existing = next((item for item in items(cursor, str(run['business_id'])) if item.get('key') == key), None)
    if existing:
        return existing
    audit_id = str(uuid.uuid4())
    payload = {'key': key, 'provider': provider, 'method': method, 'url': identity if method != 'google_api' else '',
               'identity': identity, 'business_id': str(run['business_id']), 'user_id': str(user_id),
               'status': 'queued', 'requested_at': now(), 'paid_consent': method == 'apify',
               'max_charge_usd': str(APIFY_CAP) if method == 'apify' else '0',
               'llm_calls': 0, 'provider_write_performed': False}
    if previous:
        payload['previous_attempt_id'] = previous_attempt_id
        payload['manual_retry_consent_at'] = now()
    cursor.execute('INSERT INTO agent_artifacts (id,run_id,artifact_type,title,payload_json) VALUES (%s,%s,%s,%s,%s::jsonb)',
                   (audit_id, str(run['id']), ARTIFACT, 'Начальная проверка '+LABELS[provider], json.dumps(payload)))
    cursor.execute('''INSERT INTO parsequeue (id,url,user_id,business_id,status,task_type,source,created_at,updated_at)
                      VALUES (%s,%s,%s,%s,'pending',%s,%s,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)''',
                   (audit_id, identity, str(user_id), str(run['business_id']), TASK, provider))
    return {**payload, 'id': audit_id}


def confirm_not_created(cursor, run, user_id, provider):
    if provider not in ('yandex','2gis'):
        raise ValueError('Отметка доступна для ещё не созданной карточки Яндекса или 2ГИС.')
    card = next(c for c in view(cursor, str(run['business_id']))['cards'] if c['provider'] == provider)
    if card.get('url'):
        raise ValueError('Уже есть ссылка карточки. Сначала проверьте её, чтобы не потерять существующие данные.')
    cursor.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', ('map-not-created:'+str(run['business_id'])+provider,))
    saved = next((a for a in items(cursor, str(run['business_id'])) if a['provider'] == provider and a.get('status') == 'not_created'), None)
    if saved:
        return saved
    payload = {'provider':provider,'method':'owner_confirmation','status':'not_created',
               'observed_at':now(),'confirmed_by':str(user_id),'url':'',
               'reason':'Владелец подтвердил: карточка пока не создана. Сначала создайте её вручную по подготовленному пакету.',
               'llm_calls':0,'provider_write_performed':False}
    audit_id=str(uuid.uuid4())
    cursor.execute('INSERT INTO agent_artifacts (id,run_id,artifact_type,title,payload_json) VALUES (%s,%s,%s,%s,%s::jsonb)',
        (audit_id,str(run['id']),ARTIFACT,'Карточка '+LABELS[provider]+' пока не создана',json.dumps(payload)))
    return {**payload,'id':audit_id}


def _first(data, *keys):
    for key in keys:
        value = data.get(key)
        if value is not None and value != '' and value != [] and value != {}:
            return value
    return None


def _flatten_services(value):
    result = []
    for item in value if isinstance(value, list) else []:
        if isinstance(item, dict) and isinstance(item.get('items'), list):
            result.extend(item['items'])
        elif isinstance(item, dict):
            result.append(item)
    return result


def checklist(provider, data, method, url, observed_at):
    """Empty parser defaults are NOT proof of missing fields (notably 2GIS)."""
    raw = record(data.get('raw_payload_json'))
    overview = record(data.get('overview'))
    services = _flatten_services(_first(data, 'serviceItems', 'products', 'services_json', 'services') or [])
    photos = _first(data, 'photos', 'photos_json', 'imageUrls')
    preview_only = method == 'apify' and raw.get('imagesCount') == 0 and not raw.get('imageUrls') and not raw.get('photos')
    if preview_only:
        photos = None  # A cover/Street View thumbnail is not a confirmed photo collection.
    prices = [s for s in services if any(s.get(k) is not None and s.get(k) != '' for k in ('price', 'price_from', 'price_to'))]
    regular = _first(data, 'regularHours', 'hours_full', 'working_hours', 'hours', 'openingHours') or _first(raw, 'openingHours')
    # A plain 'open now / until 18:00' is not a full weekly schedule.
    full_schedule = regular if regular and (not isinstance(regular, str) or any(day in regular.lower() for day in ('понедельник', 'пн', 'monday', 'mon', 'ежедневно', 'круглосуточно', '24/7'))) else None
    if isinstance(full_schedule, dict) and not full_schedule.get('periods'):
        full_schedule = None
    api = method == 'google_api'
    if api:
        addr = data.get('storefrontAddress') or {}
        address = ', '.join([*addr.get('addressLines', []), str(addr.get('locality') or '')]).strip(', ')
        phone = (data.get('phoneNumbers') or {}).get('primaryPhone')
        category = (data.get('categories') or {}).get('primaryCategory', {}).get('displayName')
        description = (data.get('profile') or {}).get('description')
    else:
        address = data.get('address'); phone = data.get('phone')
        category = _first(data, 'categories', 'category'); description = data.get('description') or overview.get('description')
    address_snippet = provider == 'yandex' and method == 'apify' and description and raw.get('house') and str(raw['house']) in description and any(token in description.lower() for token in ('ул.', 'улица', 'проспект', 'переулок'))
    if address_snippet:
        description = None
    reviews_count = _first(data, 'reviews_count', 'reviewsCount', 'totalScoreCount')
    values = {
        'name': _first(data, 'title', 'name', 'title_or_name'), 'address': address,
        'phone': phone, 'website': _first(data, 'websiteUri', 'website', 'site'),
        'description': description, 'category': category,
        'schedule': full_schedule, 'special_hours': data.get('specialHours'),
        'services': len(services) if services else None, 'prices': len(prices) if prices else None,
        'photos': len(photos) if isinstance(photos, list) and photos else None,
        'reviews': reviews_count if reviews_count else None,
        'review_responses': None, 'duplicate': None, 'verified': None,
        'action_path': phone or _first(data, 'websiteUri', 'website', 'site'),
        'publications': len(data.get('news') or data.get('posts') or []) or None,
    }
    if api:
        metadata = data.get('metadata') or {}
        values['verified'] = metadata.get('hasVoiceOfMerchant')
    else:
        values['verified'] = data.get('is_verified') if isinstance(data.get('is_verified'), bool) else raw.get('isVerifiedOwner')
    rules = {r['fact']: r for r in provider_rules(provider)}
    fields = ['name', 'address', 'phone', 'website', 'description', *[f for f in rules if f not in ('contacts', 'access')]]
    fields.insert(fields.index('schedule')+1, 'special_hours')
    complete_api = {'name','address','phone','website','description','category','schedule','services','action_path'}
    if not (data.get('metadata') or {}).get('canModifyServiceList'):
        complete_api.discard('services')
    checks = []
    for field in fields:
        value = values.get(field)
        state = 'observed' if value is not None and value != '' and value != [] and value != {} and value is not False else 'missing' if api and field in complete_api else 'unknown'
        note = ''
        if field == 'description' and address_snippet:
            note = 'Источник вернул адрес вместо описания компании; описание не подтверждено.'
        if field == 'verified' and value is False:
            state = 'missing'; note = 'Площадка не подтверждает управление карточкой.'
        if field == 'photos':
            note = 'Найдены изображения; это нижняя граница количества. Категории и качество фото требуют просмотра.' if value else 'Источник не подтвердил наличие или отсутствие фотографий.'
            if preview_only:
                note = 'Получено только превью, коллекция фотографий не подтверждена. Превью не считается проверкой фото профиля.'
        if field == 'schedule':
            note = 'Текущее расписание площадки; фактические часы нужно сверить с владельцем.' if value else 'Полное недельное расписание не получено.'
            if regular and not value:
                note += ' Видимый статус: '+str(regular)[:160]
            if not value and raw.get('workingHoursText'):
                note += ' Текст площадки: '+str(raw['workingHoursText'])[:160]+'. Структурированное недельное расписание не подтверждено; требуется сверка.'
        if field == 'special_hours':
            note = 'Особые часы на праздники; отсутствие записи не означает ошибку.'
        if field == 'duplicate':
            note = 'Чтение одной карточки не доказывает отсутствие дублей.'
        if field == 'review_responses':
            note = 'Нужна полная выборка отзывов и ответов, а не только счётчик.'
        if field == 'publications' and provider == '2gis':
            state = 'not_applicable'
        rule = rules.get(field) or rules.get('contacts') or {}
        checks.append({'field': field, 'title': {'special_hours':'Особые часы', 'name':'Название', 'address':'Адрес', 'phone':'Телефон', 'website':'Сайт', 'description':'Описание'}.get(field, FACT_LABELS.get(field, field)),
                       'state': state, 'value': value, 'evidence': note,
                       'source': method, 'source_url': url, 'observed_at': observed_at,
                       'official_url': rule.get('url')})
    return checks


def read_google(cursor, payload):
    from services.map_google_publication import binding
    client, account = binding(cursor, payload['business_id'])
    if account['external_id'] != payload['identity']:
        raise AuditReadError('Подключённая карточка Google изменилась.')
    response = client.session.get(client.url, params={'readMask': GOOGLE_MASK}, timeout=25)
    response.raise_for_status()
    data = response.json()
    return data, (data.get('metadata') or {}).get('mapsUri') or '', {}


def read_apify(payload, save_provider_run):
    """Reuse current HTTP transport/input/normalization, never SDK POST retries."""
    from services.prospecting_service import ProspectingService
    service = ProspectingService(source='apify_'+payload['provider'])
    if not service.api_token:
        raise AuditReadError('Apify не подключён.')
    actor_id = service.actor_id.replace('/', '~', 1)
    response = service._apify_request('GET', 'https://api.apify.com/v2/acts/'+actor_id,
        params={'token':service.api_token}, timeout=25, allow_redirects=False)
    response.raise_for_status()
    actor_info = response.json().get('data') or {}
    pricing = record(actor_info.get('pricingInfo') or actor_info.get('currentPricingInfo'))
    if not pricing:
        versions = [record(p) for p in actor_info.get('pricingInfos', [])]
        versions = [p for p in versions if str(p.get('startedAt') or '') <= now()]
        pricing = max(versions, key=lambda p: str(p.get('startedAt') or ''), default={})
    if pricing.get('pricingModel') != 'PAY_PER_EVENT':
        raise AuditReadError('Для выбранного Apify-парсера не подтверждён тариф с ограничением расходов за события. Платный запуск остановлен.')
    if Decimal(str(pricing.get('minimalMaxTotalChargeUsd') or 0)) > APIFY_CAP:
        raise AuditReadError('Минимальный лимит Apify выше согласованного. Запуск остановлен.')
    run_input = service._build_run_input_for_map_url(payload['url'], limit=1)
    run_input.update({'maxReviews':20, 'maxImages':20, 'maxPhotos':20,
                      'startUrls':[{'url':payload['url']}]})
    if payload['provider'] == 'google':
        run_input.pop('searchStringsArray', None)
    elif payload['provider'] == 'yandex':
        # This actor processes search before direct URLs. With maxResults=1 a
        # name query can consume the budget on a namesake in a different city.
        run_input.update(query=[], category='', location='',
            businessIds=[entity_key('yandex', payload['url'])],
            enrichBusinessData=False, includeReviews=True, maxPosts=10)
    # Existing requests transport has no retry adapter; redirects are forbidden
    # as 307/308 could resend the paid POST. Never call the SDK start method.
    save_provider_run(None)  # Durable ambiguous-POST boundary, even without run ID.
    response = service._apify_request('POST', 'https://api.apify.com/v2/acts/'+actor_id+'/runs',
        params={'token':service.api_token,'maxTotalChargeUsd':str(APIFY_CAP),'maxItems':1,
                'timeout':180,'restartOnError':'false','waitForFinish':0},
        json=run_input, timeout=30, allow_redirects=False)
    if not 200 <= response.status_code < 300:
        raise AuditReadError('Apify не подтвердил запуск. Автоматический повтор запрещён.')
    started = response.json().get('data') or {}
    run_id = started.get('id')
    if not run_id:
        raise AuditReadError('Apify не вернул номер запуска. Автоматический повтор запрещён.')
    save_provider_run(run_id)
    import time
    deadline = time.monotonic()+195
    final = started
    while final.get('status') in ('READY','RUNNING','TIMING-OUT','ABORTING'):
        if time.monotonic() >= deadline:
            service._apify_request('POST', 'https://api.apify.com/v2/actor-runs/'+run_id+'/abort',
                params={'token':service.api_token}, timeout=20, allow_redirects=False)
            raise AuditReadError('Apify не завершил чтение. Автоматический повтор остановлен.')
        time.sleep(4)
        final = service.get_run(run_id)
    save_provider_run({'apify_run_id':run_id,'usage_total_usd':final.get('usageTotalUsd'),'apify_run_status':final.get('status')})
    if final.get('status') != 'SUCCEEDED':
        raise AuditReadError('Apify не завершил чтение. Автоматический повтор остановлен.')
    candidates = service.fetch_dataset_items(final.get('defaultDatasetId') or '')
    candidates = [i for i in candidates if matches_entity(service, payload, i)]
    if len(candidates) != 1:
        raise AuditReadError('Apify не подтвердил единственную нужную карточку. Результат не используется.')
    return candidates[0], payload['url'], {'apify_run_id':run_id,'usage_total_usd':final.get('usageTotalUsd')}


def matches_entity(service, payload, item):
    raw = record(item.get('raw_payload_json'))
    if payload['provider'] == 'google':
        query = parse_qs(urlsplit(payload['url']).query)
        if query.get('cid'):
            return str(raw.get('cid') or '') == query['cid'][0]
        if query.get('query_place_id'):
            return str(raw.get('placeId') or item.get('source_external_id') or '') == query['query_place_id'][0]
    return service._matches_requested_map_entity(normalized_item=item,
        raw_item=raw, map_url=payload['url'], city='')


def execute_task(queue, native_readers):
    """Called only by existing worker; parser side effects never reach general pipeline."""
    from database_manager import DatabaseManager
    db = DatabaseManager()
    cursor = db.conn.cursor()
    audit_id = str(queue['id'])
    try:
        cursor.execute('SELECT payload_json FROM agent_artifacts WHERE id=%s AND artifact_type=%s FOR UPDATE', (audit_id, ARTIFACT))
        row = cursor.fetchone()
        if not row:
            raise ValueError('Запрос начальной проверки не найден.')
        payload = record(row['payload_json'])
        if payload.get('status') != 'queued':
            if payload.get('status') == 'reading':
                payload.update(status='blocked', reason='Предыдущая попытка была прервана. Новый запрос к площадке автоматически не выполняется.', observed_at=now())
                _save(cursor, audit_id, payload)
            cursor.execute("UPDATE parsequeue SET status='error',error_message='Initial audit already attempted; automatic retry blocked',updated_at=CURRENT_TIMESTAMP WHERE id=%s", (audit_id,))
            db.conn.commit()
            return
        payload.update(status='reading', started_at=now())
        _save(cursor, audit_id, payload)
        db.conn.commit()  # Durable one-attempt boundary BEFORE external I/O.
        def save_provider_run(run_id):
            if isinstance(run_id, dict):
                payload.update({key:value for key,value in run_id.items() if key in ('apify_run_id','usage_total_usd','apify_run_status')})
            elif run_id:
                payload['apify_run_id'] = run_id
            else:
                payload['provider_start_attempted_at'] = now()
            _save(cursor, audit_id, payload); db.conn.commit()
        try:
            method = payload['method']
            if method == 'google_api':
                data, url, cost = read_google(cursor, payload)
            elif method == 'apify':
                if not payload.get('paid_consent'):
                    raise ValueError('Нет подтверждения расходов Apify.')
                data, url, cost = read_apify(payload, save_provider_run)
            else:
                data = native_readers[payload['provider']](payload['url'])
                url, cost = payload['url'], {}
            if not isinstance(data, dict):
                raise AuditReadError('Парсер не вернул данные страницы.')
            problem = str(data.get('error') or data.get('message') or '').lower()
            if data.get('captcha_required') or 'captcha' in problem:
                raise AuditReadError('Площадка показала капчу. Поля не проверены, повтор автоматически не выполняется.')
            if 'timeout' in problem:
                raise AuditReadError('Время чтения страницы истекло. Поля не проверены, повтор автоматически не выполняется.')
            if data.get('error'):
                raise AuditReadError('Страница недоступна или парсер не получил данные. Поля не проверены.')
            if not _first(data, 'title', 'name', 'title_or_name'):
                raise AuditReadError('Парсер не подтвердил карточку компании.')
            stamp = now()
            payload.update(status='completed', observed_at=stamp, url=url, **cost,
                           checks=checklist(payload['provider'], data, method, url, stamp))
        except Exception as exc:
            db.conn.rollback()
            # No secrets, provider response bodies or raw exception strings in UI.
            payload.update(status='blocked', observed_at=now(),
                reason=str(exc) if isinstance(exc, AuditReadError) else 'Чтение не завершено: ошибка доступа или ответа провайдера. Повтор и платная замена автоматически не запускаются.')
        _save(cursor, audit_id, payload)
        cursor.execute('UPDATE parsequeue SET status=%s,error_message=%s,updated_at=CURRENT_TIMESTAMP WHERE id=%s',
            ('completed' if payload['status'] == 'completed' else 'error', payload.get('reason'), audit_id))
        db.conn.commit()
    finally:
        db.close()


def _save(cursor, audit_id, payload):
    cursor.execute('UPDATE agent_artifacts SET payload_json=%s::jsonb WHERE id=%s AND artifact_type=%s',
                   (json.dumps(payload, ensure_ascii=False, default=str), audit_id, ARTIFACT))


def apply_saved_audits(cards, audits):
    """Primary/checker reuse dated initial observations, without another scrape."""
    latest = {}
    for audit in audits:
        latest.setdefault(audit['provider'], audit)
    for card in cards:
        audit = latest.get(card['provider'])
        if not audit:
            continue
        card['initial_audit'] = {key: audit.get(key) for key in ('id','method','status','observed_at','reason')}
        if audit.get('status') != 'completed':
            continue
        by_field = {check['field']: check for check in combined_checks([a for a in audits if a['provider'] == card['provider']])}
        for check in card.get('checks', []):
            if check['field'] in by_field:
                check.update(by_field[check['field']])
        for field in ('phone','website','description','special_hours'):
            if field in by_field and not any(c['field'] == field for c in card['checks']):
                card['checks'].append(by_field[field])
        contacts = next((c for c in card['checks'] if c['field'] == 'contacts'), None)
        if contacts is not None:
            p, w = by_field.get('phone', {}), by_field.get('website', {})
            contacts.update(value={'phone':p.get('value'),'website':w.get('value')},
                state='observed' if p.get('state') == w.get('state') == 'observed' else 'missing' if 'missing' in (p.get('state'),w.get('state')) else 'unknown',
                source=audit['method'], observed_at=audit.get('observed_at'))
        if audit.get('url'):
            card['url'] = audit['url']
    return cards
