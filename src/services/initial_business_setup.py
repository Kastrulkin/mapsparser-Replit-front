"""Resumable setup for a single LocalOS business, with approved internal writes."""
import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone

from psycopg2.extras import Json

from services.initial_setup_sources import clean, dated, read_map, read_social, read_website, source_url
from services.website_seo_audit import unavailable as audit_unavailable


JOB_KIND = 'initial_setup_source'
CURRENT_FIELDS = ('name', 'address', 'city', 'country', 'business_type', 'website', 'contact_phone', 'contact_email')
MAX_SOURCES = 18
MAX_ANALYZED_SERVICES = 120


class Conflict(ValueError):
    pass


def enabled():
    return os.getenv('LOCALOS_INITIAL_SETUP_ENABLED', '').lower() in ('1', 'true', 'yes')


def targets(kind):
    return {value.strip() for value in os.getenv(f'LOCALOS_INITIAL_SETUP_{kind}_IDS', '').split(',') if value.strip()}


def allowed(business_id):
    cohort = targets('BUSINESS')
    return enabled() and (not cohort or business_id in cohort)


def installed(cursor):
    cursor.execute("SELECT to_regclass('public.initial_business_setups') AS present")
    return bool(cursor.fetchone()['present'])


def fingerprint(*fields):
    return hashlib.sha256(json.dumps(fields, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


def read_business(cursor, business_id, lock=False):
    cursor.execute("""SELECT b.id,b.owner_id,b.name,b.address,b.city,to_jsonb(b)->>'country' AS country,to_jsonb(b)->>'business_type' AS business_type,
        COALESCE(NULLIF(to_jsonb(b)->>'website',''), NULLIF(to_jsonb(b)->>'site',''),'') AS website,
        COALESCE(NULLIF(p.contact_phone,''), NULLIF(to_jsonb(b)->>'phone',''),'') AS contact_phone,
        COALESCE(NULLIF(p.contact_email,''), NULLIF(to_jsonb(b)->>'email',''),'') AS contact_email
        FROM businesses b LEFT JOIN businessprofiles p ON p.business_id=b.id
        WHERE b.id=%s AND b.is_active IS NOT FALSE""" + (' FOR UPDATE OF b' if lock else ''), (business_id,))
    return dict(cursor.fetchone() or {})


def load(cursor, business_id, lock=False):
    cursor.execute('SELECT * FROM initial_business_setups WHERE business_id=%s' + (' FOR UPDATE' if lock else ''), (business_id,))
    return dict(cursor.fetchone() or {})


def init(cursor, business_id, origin, *, lead_id=None, provisional=False):
    cursor.execute("""INSERT INTO initial_business_setups (business_id,origin,lead_id,provisional)
        VALUES (%s,%s,%s,%s) ON CONFLICT (business_id) DO NOTHING""",
        (business_id, origin, lead_id, provisional))
    return load(cursor, business_id, lock=True)


def verified_registration_business(cursor, user_id):
    if not enabled() or not installed(cursor):
        return None
    cursor.execute("""SELECT b.id FROM initial_business_setups s JOIN businesses b ON b.id=s.business_id
        WHERE b.owner_id=%s AND b.is_active IS NOT FALSE AND s.origin='registration' AND NOT s.provisional
        ORDER BY s.updated_at DESC LIMIT 2""", (user_id,))
    candidates = cursor.fetchall()
    if len(candidates) == 1 and allowed(str(candidates[0]['id'])):
        return str(candidates[0]['id'])
    return None


def persist(cursor, row):
    cursor.execute('''UPDATE initial_business_setups SET data=%s, revision=revision+1, updated_at=NOW()
        WHERE business_id=%s RETURNING revision''', (Json(row['data']), row['business_id']))
    row['revision'] = cursor.fetchone()['revision']


def register_source(row, value, *, competitor=False, found_on=None):
    kind, provider, url = source_url(value)
    if competitor and kind != 'map':
        raise ValueError('Для сравнения нужна ссылка на карточку конкурента на картах.')
    sources = row['data'].setdefault('sources', {})
    key = fingerprint(provider, url)
    if key in sources:
        if bool(sources[key].get('competitor')) != competitor:
            raise ValueError('Эта ссылка уже добавлена в другой роли.')
        return key
    retired = row['data'].get('retired_sources', {})
    if key in retired:
        if bool(retired[key].get('competitor')) != competitor:
            raise ValueError('Эта ссылка уже использовалась в другой роли.')
        if len(sources) >= MAX_SOURCES:
            raise ValueError('Достигнут предел источников для первой настройки.')
        sources[key] = retired.pop(key)
        if not competitor:
            row['data']['saved'] = False
        return key
    if len(sources) + len(retired) >= MAX_SOURCES:
        raise ValueError('Достигнут предел источников для первой настройки.')
    sources[key] = {'url': url, 'kind': kind, 'provider': provider, 'status': 'added', 'competitor': competitor}
    if not competitor:
        row['data']['saved'] = False
    if found_on:
        sources[key]['found_on'] = found_on
    return key


def queue_source(cursor, row, actor_id, key, retry=False, *, audit_only=False):
    from services.operator_async_jobs import create_operator_async_job
    item = row['data']['sources'][key]
    tracker = item
    if audit_only:
        if item['kind'] != 'website' or item['status'] != 'ready':
            raise ValueError('Для SEO-проверки сначала прочитайте сайт.')
        tracker = item.setdefault('website_audit_job', {})
        if tracker.get('job_id'):
            cursor.execute('SELECT status FROM operator_async_jobs WHERE id=%s AND business_id=%s',
                           (tracker['job_id'], row['business_id']))
            prior = cursor.fetchone()
            if prior and prior['status'] in ('queued', 'running'):
                return
    elif item['status'] != 'added' and not (retry and item['status'] in ('unavailable', 'link_only')):
        return
    attempt = int(tracker.get('attempt') or 0) + 1
    if not audit_only and attempt > 3:
        raise ValueError('Три попытки чтения уже выполнены. Проверьте источник отдельно.')
    job_scope = 'website-seo' if audit_only else 'initial-setup'
    job = create_operator_async_job(
        cursor, user_id=actor_id, action_id=None, business_id=row['business_id'], kind=JOB_KIND,
        payload={'source_key': key, 'attempt': attempt, 'audit_only': audit_only},
        idempotency_key=f'{job_scope}:{row["business_id"]}:{key}:{attempt}',
        stage='Ожидает SEO-проверки' if audit_only else 'Ожидает чтения', max_attempts=1,
    )
    tracker.update(attempt=attempt, job_id=job['id'])
    if not audit_only:
        item.update(status='queued', note='')


def queue_added(cursor, row, actor_id):
    for key in list(row['data'].get('sources', {})):
        queue_source(cursor, row, actor_id, key)


def seed_profile_sources(cursor, row, profile):
    candidates = [profile.get('website')]
    cursor.execute('SELECT url FROM businessmaplinks WHERE business_id=%s ORDER BY created_at DESC LIMIT 8', (row['business_id'],))
    candidates.extend(item['url'] for item in cursor.fetchall())
    for value in candidates:
        if value:
            try:
                register_source(row, value)
            except ValueError:
                continue


def _link_matches(provider, left, right):
    if not left or not right:
        return False
    try:
        left_kind, left_provider, left_url = source_url(left)
        right_kind, right_provider, right_url = source_url(right)
    except ValueError:
        return False
    if left_kind != 'map' or right_kind != 'map' or left_provider != provider or right_provider != provider:
        return False
    if left_url == right_url:
        return True
    from services.map_card_initial_audit import entity_key
    left_id, right_id = entity_key(provider, left_url), entity_key(provider, right_url)
    if provider == 'google':
        return left_id != left_url and right_id != right_url and left_id == right_id
    return left_id.isdigit() and left_id == right_id


def snapshot(cursor, business_id, source):
    if source.get('competitor'):
        return None
    from services.card_growth_service import _latest_sources
    _, parses = _latest_sources(cursor, business_id)
    card = parses.get(source['provider'])
    if card and _link_matches(source['provider'], card.get('url'), source['url']):
        return card
    cursor.execute('SELECT * FROM cards WHERE business_id=%s ORDER BY created_at DESC LIMIT 25', (business_id,))
    for item in cursor.fetchall():
        if _link_matches(source['provider'], item.get('url'), source['url']):
            return dict(item)
    return None


def process_source(claimed):
    """Read outside the transaction, then commit the observation only under the same lease."""
    from database_manager import DatabaseManager
    from services.business_permissions import load_actor, require_permission

    business_id, actor_id = claimed['business_id'], claimed['user_id']
    payload = claimed['payload_json']
    key = payload['source_key']
    audit_only = payload.get('audit_only', False)
    if not allowed(business_id):
        return {'state': 'setup_disabled'}
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        actor = load_actor(cursor, actor_id)
        require_permission(cursor, business_id, actor, 'business.settings.write')
        row = load(cursor, business_id)
        item = row.get('data', {}).get('sources', {}).get(key, {})
        tracker = item.get('website_audit_job', {}) if audit_only else item
        if tracker.get('job_id') != str(claimed['id']) or tracker.get('attempt') != payload['attempt']:
            return {'state': 'obsolete'}
        item_snapshot = snapshot(cursor, business_id, item) if item['kind'] == 'map' else None
        db.conn.rollback()
        try:
            if item['kind'] == 'website':
                result = read_website(item['url'])
            elif item['kind'] == 'social':
                result = read_social(item['provider'], item['url'])
            else:
                if not item_snapshot and item['provider'] == 'google' and not item.get('competitor'):
                    from services.map_card_initial_audit import read_google
                    from services.map_google_publication import GooglePublicationError, binding
                    try:
                        _, account = binding(cursor, business_id, read_client=False)
                        google, maps_url, _ = read_google(cursor, {'business_id': business_id, 'identity': account['external_id']})
                        if _link_matches('google', item['url'], maps_url):
                            item_snapshot = google
                    except GooglePublicationError:
                        pass
                    finally:
                        db.conn.rollback()
                result = read_map(item, item_snapshot)
        except Exception:
            result = {'status': 'unavailable', 'note': 'Не удалось прочитать источник. Попробуйте ещё раз позже.'}
        row = load(cursor, business_id, lock=True)
        actor = load_actor(cursor, actor_id)
        require_permission(cursor, business_id, actor, 'business.settings.write')
        current = row.get('data', {}).get('sources', {}).get(key, {})
        tracker = current.get('website_audit_job', {}) if audit_only else current
        cursor.execute("SELECT 1 FROM operator_async_jobs WHERE id=%s AND lease_token=%s AND status='running' FOR UPDATE",
                       (claimed['id'], claimed['lease_token']))
        if not cursor.fetchone() or tracker.get('job_id') != str(claimed['id']) or not allowed(business_id):
            return {'state': 'obsolete'}
        if audit_only:
            audit = result.get('website_audit') or audit_unavailable(
                result.get('note') or 'Не удалось завершить SEO-проверку сайта. Можно повторить.')
            current['website_audit'] = audit
            tracker.pop('job_id')
            persist(cursor, row)
            db.conn.commit()
            return {'state': audit['status']}
        current.update({k: v for k, v in result.items() if k != 'links'})
        current['checked_at'] = datetime.now(timezone.utc).isoformat()
        if not current.get('competitor'):
            row['data']['seo_dirty'] = True
        for link in result.get('links', []):
            if len(row['data']['sources']) >= MAX_SOURCES:
                break
            try:
                found = register_source(row, link['url'], found_on=link.get('found_on'))
            except ValueError:
                continue
            queue_source(cursor, row, actor_id, found)
        persist(cursor, row)
        db.conn.commit()
        return {'state': current['status']}
    finally:
        db.rollback_and_close()


def _wordstat(cursor, business_id, actor_id, service):
    from core.seo_keywords import collect_ranked_keywords
    from services.operator_search_demand import relevant_candidates

    cursor.execute('SAVEPOINT setup_wordstat')
    try:
        ranked = collect_ranked_keywords(cursor, business_id, actor_id, service_name=service['name'],
                                         service_description=service.get('description'), limit=100,
                                         fallback_global_when_empty_terms=False)
        candidates = relevant_candidates(ranked.get('items') or [], [service])
        cursor.execute('RELEASE SAVEPOINT setup_wordstat')
    except Exception:
        cursor.execute('ROLLBACK TO SAVEPOINT setup_wordstat')
        cursor.execute('RELEASE SAVEPOINT setup_wordstat')
        raise
    keywords = []
    for item in candidates[:5]:
        word = clean(item.get('keyword'), 220)
        if word and item.get('source') != 'safe_seed':
            keywords.append({'text': word, 'views': item.get('views'), 'source': 'Wordstat',
                             'dated': str(item.get('updated_at') or '')[:10]})
    return keywords


def _comparison(row):
    entries = list(row['data'].get('sources', {}).values())
    own = {item['provider']: item for item in entries if item['kind'] == 'map' and item['status'] == 'ready' and not item.get('competitor')}
    comparisons = []
    for item in entries:
        if not item.get('competitor') or item['status'] != 'ready':
            continue
        ours = own.get(item['provider'])
        comparisons.append({'url': item['url'], 'name': item.get('name'), 'platform': item['provider'],
                            'checked_at': item.get('observed_at') or item.get('checked_at'),
                            'our_checked_at': (ours or {}).get('observed_at') or (ours or {}).get('checked_at'),
                            'ours': (ours or {}).get('metrics'), 'theirs': item.get('metrics'),
                            'our_services': [service['name'] for service in (ours or {}).get('catalog', [])][:12],
                            'their_services': [service['name'] for service in item.get('catalog', [])][:12]})
    return comparisons


def _local_topics(name, city, source):
    topics = [{'text': name, 'source': source, 'views': None, 'dated': ''}]
    city_words = ' '.join(re.findall(r'\w+', city.casefold()))
    name_words = ' '.join(re.findall(r'\w+', name.casefold()))
    if city_words and f' {city_words} ' not in f' {name_words} ' and len(name) + len(city) < 220:
        topics.append({'text': f'{name} {city}', 'source': 'Тема с городом', 'views': None, 'dated': ''})
    return topics


def prepare_seo(cursor, row, actor_id, profile):
    cursor.execute('''SELECT DISTINCT ON (LOWER(BTRIM(name)))
        id,name,description,category,optimized_name,optimized_description FROM userservices
        WHERE business_id=%s AND is_active IS NOT FALSE
        ORDER BY LOWER(BTRIM(name)),name,id LIMIT %s''', (row['business_id'], MAX_ANALYZED_SERVICES + 1))
    services = {}
    for value in cursor.fetchall():
        item = dict(value)
        services.setdefault(clean(item['name']).casefold(), item)
    for item in row['data'].get('declared_services', []):
        services.setdefault(item['name'].casefold(), dict(item))
    for source in row['data'].get('sources', {}).values():
        if source['status'] != 'ready' or source.get('competitor'):
            continue
        for item in source.get('catalog', []):
            services.setdefault(item['name'].casefold(), dict(item))
    city = clean(profile.get('city'), 120)
    category = row['data'].get('activity_type')
    if not category and profile.get('business_type'):
        cursor.execute('SELECT label FROM businesstypes WHERE type_key=%s LIMIT 1', (profile['business_type'],))
        category = (cursor.fetchone() or {}).get('label')
    row['data']['category_keywords'] = []
    if category:
        keywords = _wordstat(cursor, row['business_id'], actor_id, {'name': category})
        row['data']['category_keywords'] = keywords or _local_topics(category, city, 'Вид деятельности')
    previous_by_key = {item['key']: item for item in row['data'].get('services', [])}
    proposals = []
    for service in list(services.values())[:MAX_ANALYZED_SERVICES]:
        name = service['name']
        keywords = _wordstat(cursor, row['business_id'], actor_id, service)
        description = service.get('description') or ''
        proposed = service.get('optimized_name') or name
        proposed_desc = service.get('optimized_description') or description
        # A conservative draft must not infer a service feature from a search term.
        if city and not service.get('optimized_name'):
            original_key = ' '.join(re.findall(r'\w+', name.casefold()))
            city_key = ' '.join(re.findall(r'\w+', city.casefold()))
            safe_names = {original_key + ' ' + city_key, city_key + ' ' + original_key}
            for query in keywords:
                candidate = ' '.join(re.findall(r'\w+', query['text'].casefold()))
                if original_key and city_key and candidate in safe_names:
                    proposed = name + ' — ' + city
                    break
        if not service.get('optimized_description') and city and city.casefold() not in description.casefold():
            context = f'{name} — {profile["name"]}, {city}.'
            proposed_desc = f'{description} {context}'.strip()[:1200]
        if not keywords:
            keywords = _local_topics(name, city, 'Тема из каталога')
        key = fingerprint(name.casefold())
        previous = previous_by_key.get(key) or {}
        accepted = bool(previous.get('accepted') and previous.get('service_id') == service.get('id')
                        and previous['proposed'] == proposed and previous['proposed_description'] == proposed_desc)
        proposals.append({'key': key, 'service_id': service.get('id'), 'original': name, 'accepted': accepted,
                          'description': description, 'previous_name': service.get('optimized_name'),
                          'previous_description': service.get('optimized_description'),
                          'proposed': proposed, 'proposed_description': proposed_desc,
                          'source_url': service.get('url'), 'category': service.get('category'),
                          'keywords': keywords})
    row['data'].update(services=proposals, seo_dirty=False, seo_prepared=True)
    return len(services) > MAX_ANALYZED_SERVICES


def source_findings(row, kind):
    findings = {}
    for source in row['data'].get('sources', {}).values():
        if source['status'] != 'ready' or source.get('competitor'):
            continue
        for finding in source.get(kind, []):
            key = fingerprint(finding.get('field'), finding['text'], finding['url'])
            findings[key] = finding
    if kind == 'profile':
        for finding in row['data'].get('lead_contacts', []):
            findings[fingerprint(finding.get('field'), finding['text'], finding['url'])] = finding
    return findings


def status(cursor, row, profile, can_edit):
    data = row['data']
    items = data.get('sources', {})
    ids = [item['job_id'] for item in items.values() if item.get('job_id') and item['status'] == 'queued']
    ids.extend(track['job_id'] for item in items.values()
               if (track := item.get('website_audit_job')) and track.get('job_id'))
    jobs = {}
    if ids:
        cursor.execute('SELECT id,status FROM operator_async_jobs WHERE business_id=%s AND id=ANY(%s)',
                       (row['business_id'], ids))
        jobs = {str(item['id']): item['status'] for item in cursor.fetchall()}
    sources = []
    for key, item in items.items():
        visible = {k: v for k, v in item.items()
                   if k not in ('profile', 'facts', 'links', 'catalog', 'job_id', 'website_audit_job')}
        if item['status'] == 'queued':
            state = jobs.get(item.get('job_id'))
            if not state or state in ('failed', 'cancelled', 'completed'):
                visible.update(status='unavailable', note='Чтение прервано. Можно повторить.')
            elif state == 'running':
                visible['status'] = 'running'
        audit_job = item.get('website_audit_job', {}).get('job_id')
        if audit_job:
            audit_state = jobs.get(audit_job)
            visible['website_audit'] = ({'status': audit_state} if audit_state in ('queued', 'running') else
                                        audit_unavailable('SEO-проверка была прервана. Можно повторить.'))
        visible.update(key=key, service_count=len(item.get('catalog', [])))
        sources.append(visible)
    return {'business_id': row['business_id'], 'revision': row['revision'], 'origin': row['origin'], 'can_edit': can_edit,
            'provisional': row['provisional'], 'profile': {k: profile.get(k) for k in CURRENT_FIELDS},
            'sources': sources, 'services': data.get('services', []), 'seo_dirty': bool(data.get('seo_dirty')),
            'seo_prepared': bool(data.get('seo_prepared')), 'saved': bool(data.get('saved')),
            'started': bool(data.get('started')), 'activity_type': data.get('activity_type'),
            'category_keywords': data.get('category_keywords', []),
            'facts': [{'key': key, **value, 'accepted': key in data.get('accepted_facts', [])}
                      for key, value in source_findings(row, 'facts').items()],
            'profile_choices': [{'key': key, **value} for key, value in source_findings(row, 'profile').items()],
            'comparisons': _comparison(row), 'activity': data.get('activity', [])}


def log(row, message, reply):
    history = row['data'].setdefault('activity', [])
    history.append({'message': message, 'reply': reply, 'at': datetime.now(timezone.utc).isoformat()})
    del history[:-12]


def _update_profile(cursor, row, actor_id, patch):
    from services.business_chat_changes import save_values
    save_values(cursor, row['business_id'], actor_id, patch, 'initial-setup:' + str(uuid.uuid4()))
    if set(patch).intersection(('name', 'city', 'address', 'business_type')):
        row['data']['seo_dirty'] = True


def _apply_service(cursor, row, actor_id, payload):
    key = payload.get('key')
    selected = next((item for item in row['data'].get('services', []) if item['key'] == key), None)
    if not selected or row['data'].get('seo_dirty'):
        raise Conflict('Сначала обновите разбор услуг.')
    override_name = clean(payload.get('name', selected['proposed']), 240)
    override_desc = clean(payload.get('description', selected['proposed_description']), 1200)
    if not override_name:
        raise ValueError('Укажите название услуги.')
    if selected.get('accepted'):
        return 'Изменение уже сохранено в «Услугах».'
    business_id = row['business_id']
    if selected.get('service_id'):
        cursor.execute('''SELECT * FROM userservices WHERE business_id=%s AND id=%s AND is_active IS NOT FALSE FOR UPDATE''',
                       (business_id, selected['service_id']))
        current = cursor.fetchone()
        if not current or any((current[field] or '') != (selected[original] or '') for field, original in (
            ('name', 'original'), ('description', 'description'), ('optimized_name', 'previous_name'),
            ('optimized_description', 'previous_description')
        )):
            raise Conflict('Услугу изменили. Обновите разбор перед сохранением.')
        cursor.execute('''UPDATE userservices SET optimized_name=%s,optimized_description=%s,updated_at=NOW()
            WHERE business_id=%s AND id=%s''', (override_name, override_desc, business_id, current['id']))
    else:
        cursor.execute('SELECT id FROM userservices WHERE business_id=%s AND LOWER(BTRIM(name))=LOWER(%s) AND is_active IS NOT FALSE LIMIT 1',
                       (business_id, selected['original']))
        if cursor.fetchone():
            raise Conflict('Услуга уже появилась в каталоге. Обновите разбор.')
        service_id = str(uuid.uuid4())
        cursor.execute('''INSERT INTO userservices (id,user_id,business_id,name,description,category,
            optimized_name,optimized_description,source,is_active,created_at,updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'initial_setup',TRUE,NOW(),NOW())''',
            (service_id, actor_id, business_id, selected['original'], selected['description'],
             selected.get('category') or '', override_name, override_desc))
        selected['service_id'] = service_id
    selected.update(accepted=True, proposed=override_name, proposed_description=override_desc)
    return 'Исходник и выбранный вариант доступны в разделе «Услуги».'


def _save_fact(cursor, row, actor, payload):
    from services import business_knowledge

    key = payload.get('key')
    fact = source_findings(row, 'facts').get(key)
    if not fact:
        raise Conflict('Источник изменился. Проверьте факты ещё раз.')
    approved = row['data'].setdefault('accepted_facts', [])
    if key in approved:
        return 'Факт уже сохранён.'
    fact_text = clean(payload.get('text', fact['text']), 700)
    if not fact_text:
        raise ValueError('Укажите текст подтверждаемого факта.')
    business_knowledge.mutate(cursor, 'business', row['business_id'], actor, {
        'operation': 'rule',
        'request_id': 'initial-setup-fact:' + key,
        'payload': {'label': 'Факт из первичной настройки', 'text': fact_text, 'source': fact['url'],
                    'observed_at': fact['observed_at']},
    })
    approved.append(key)
    return 'Факт сохранён в «Знаниях о бизнесе». Его можно использовать в черновиках материалов.'


def _save_sources(cursor, row, actor, profile):
    business_id = row['business_id']
    website = []
    cursor.execute('SELECT url FROM businessmaplinks WHERE business_id=%s', (business_id,))
    map_urls = [item['url'] for item in cursor.fetchall()]
    for item in row['data'].get('sources', {}).values():
        if item.get('competitor'):
            continue
        if item['kind'] == 'website' and item['status'] == 'ready':
            website.append(item['url'])
        if item['kind'] == 'map' and item['status'] == 'ready':
            if not any(_link_matches(item['provider'], url, item['url']) for url in map_urls):
                cursor.execute('''INSERT INTO businessmaplinks(id,user_id,business_id,url,map_type) VALUES(%s,%s,%s,%s,%s)''',
                               (str(uuid.uuid4()), actor['user_id'], business_id, item['url'], item['provider']))
                map_urls.append(item['url'])
    if not profile.get('website') and len(website) == 1:
        _update_profile(cursor, row, actor['user_id'], {'website': website[0]})
    row['data']['saved'] = True
    return 'Данные сохранены. Кабинет и подготовленные разделы доступны через меню.'


FIELD_MESSAGE = re.compile(r'(?i)^(название|телефон|почта|email|адрес|город)\s*:\s*(.+)$')
DECLARATION = re.compile(r'(?i)^(вид деятельности|услуга)\s*:\s*(.+)$')


def message(cursor, row, actor, profile, payload):
    text = clean(payload.get('message'), 1500)
    if not text:
        raise ValueError('Напишите сообщение или вставьте ссылку.')
    links = [url.rstrip('.,);') for url in re.findall(r'https?://[^\s<>]+', text)]
    if len(links) > 5:
        raise ValueError('За один раз можно добавить до пяти ссылок.')
    display = 'Уточнение по настройке'
    if links:
        display = 'Добавлены ссылки к настройке'
        competitor = payload.get('competitor') is True or bool(re.match(r'(?i)конкурент\s*[: ]', text))
        for value in links:
            key = register_source(row, value, competitor=competitor)
            queue_source(cursor, row, actor['user_id'], key)
        reply = 'Ссылки появились в списке источников. Ход чтения виден рядом с чатом.'
    elif declaration := DECLARATION.match(text):
        display = text
        if declaration[1].lower() == 'вид деятельности':
            row['data']['activity_type'] = clean(declaration[2], 160)
            reply = 'Вид деятельности учтён при подборе поисковых запросов.'
        else:
            name, _, description = declaration[2].partition('|')
            name = clean(name, 240)
            services = row['data'].setdefault('declared_services', [])
            existing = next((item for item in services if item['name'].casefold() == name.casefold()), None)
            if not name or (not existing and len(services) >= 30):
                raise ValueError('Укажите название услуги. Можно добавить до 30 услуг.')
            if existing:
                existing['description'] = clean(description, 900)
            else:
                services.append({'name': name, 'description': clean(description, 900)})
            reply = 'Услуга добавлена для разбора. После проверки её можно сохранить в каталог.'
        row['data']['seo_dirty'] = True
    else:
        match = FIELD_MESSAGE.match(text)
        fields = {'название': 'name', 'телефон': 'contact_phone', 'почта': 'contact_email', 'email': 'contact_email', 'адрес': 'address', 'город': 'city'}
        if match:
            display = text
            field = fields[match[1].lower()]
            _update_profile(cursor, row, actor['user_id'], {field: match[2]})
            reply = 'Поле обновлено в профиле LocalOS.'
        else:
            reply = 'Пришлите ссылку или напишите, например, «Название: Новое название» или «Телефон: …».'
    # Message history belongs to the intake record. Keep link contents bounded and canonical.
    log(row, display, reply)
    return reply


def operate(cursor, row, actor, profile, payload):
    action = payload.get('action')
    actor_id = actor['user_id']
    if action == 'message':
        return message(cursor, row, actor, profile, payload)
    if action == 'read':
        queue_added(cursor, row, actor_id)
        return 'Чтение добавленных источников запущено.'
    if action == 'website_audit':
        key = payload.get('key')
        if not isinstance(key, str) or key not in row['data'].get('sources', {}):
            raise ValueError('Источник недоступен.')
        queue_source(cursor, row, actor_id, key, audit_only=True)
        return 'SEO-проверка сайта запущена.'
    if action == 'retry':
        key = payload.get('key')
        item = row['data'].get('sources', {}).get(key)
        if not item:
            raise ValueError('Источник недоступен.')
        if item['status'] == 'queued':
            cursor.execute('SELECT status FROM operator_async_jobs WHERE id=%s', (item['job_id'],))
            job = cursor.fetchone()
            if not job or job['status'] not in ('queued', 'running'):
                item['status'] = 'unavailable'
        queue_source(cursor, row, actor_id, key, retry=True)
        return 'Проверьте статус чтения в списке источников.'
    if action == 'remove':
        key = payload.get('key')
        item = row['data'].get('sources', {}).pop(key, None)
        if item:
            row['data'].setdefault('retired_sources', {})[key] = item
            if not item.get('competitor'):
                row['data']['seo_dirty'] = True
                row['data']['saved'] = False
        return 'Источник исключён из подготовки.'
    if action == 'prepare':
        sources = status(cursor, row, profile, True)['sources']
        if any(source['status'] in ('added', 'queued', 'running') for source in sources):
            raise Conflict('Дождитесь чтения источников перед разбором услуг.')
        if prepare_seo(cursor, row, actor_id, profile):
            return f'Разбор и поисковые запросы готовы для первых {MAX_ANALYZED_SERVICES} услуг. В каталоге есть и другие позиции.'
        return 'Разбор каталога и поисковые запросы готовы к проверке.'
    if action == 'profile':
        choice = source_findings(row, 'profile').get(payload.get('key'))
        if not choice:
            raise Conflict('Источник изменился. Проверьте значения ещё раз.')
        _update_profile(cursor, row, actor_id, {choice['field']: choice['text']})
        return 'Выбранное значение сохранено в профиле.'
    if action == 'service':
        return _apply_service(cursor, row, actor_id, payload)
    if action == 'fact':
        return _save_fact(cursor, row, actor, payload)
    if action == 'save':
        sources = status(cursor, row, profile, True)['sources']
        if (not row['data'].get('seo_prepared') or row['data'].get('seo_dirty')
                or any(source['status'] in ('added', 'queued', 'running') for source in sources)):
            raise Conflict('Сначала завершите разбор услуг.')
        return _save_sources(cursor, row, actor, profile)
    raise ValueError('Выберите действие настройки.')


def lead_allowed(lead_id):
    cohort = targets('LEAD')
    return enabled() and (lead_id in cohort if cohort else not targets('BUSINESS'))


def start_lead(db, cursor, lead, actor_id):
    from services.company_registry_service import ensure_company_for_lead

    lead_id = str(lead['id'])
    identity = ensure_company_for_lead(db.conn, lead_id, lead, source='initial_setup_lead')
    city = clean(lead.get('city'), 120)
    name = clean(lead['name'], 250)
    identity_lock = identity['company_location_id'] or f'{name.casefold()}|{city.casefold()}'
    cursor.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', ('initial-setup-lead:' + identity_lock,))
    cursor.execute("""SELECT DISTINCT b.id FROM businesses b
        LEFT JOIN business_company_links relation ON relation.business_id=b.id
        WHERE b.is_active IS NOT FALSE AND b.entity_group IN ('client','internal')
          AND (b.id=%s OR (relation.company_location_id=%s::uuid)
               OR (LOWER(BTRIM(b.name))=LOWER(%s) AND LOWER(COALESCE(b.city,''))=LOWER(%s)))
        LIMIT 3""", (lead.get('business_id'), identity['company_location_id'] or None, name, city))
    match = cursor.fetchall()
    business_id = None
    if match:
        if len(match) != 1 or not identity['company_location_id']:
            raise Conflict('Возможно, компания уже есть. Откройте нужную компанию в админке и начните настройку оттуда.')
        candidate_id = str(match[0]['id'])
        cursor.execute('''SELECT 1 FROM business_company_links WHERE business_id=%s AND company_location_id=%s::uuid''',
                       (candidate_id, identity['company_location_id']))
        if not cursor.fetchone():
            raise Conflict('Проверьте компанию с похожим названием в админке.')
        business_id = candidate_id
    provisional = business_id is None
    if provisional:
        if os.getenv('LOCALOS_INITIAL_SETUP_BUSINESS_IDS', '').strip():
            raise Conflict('В пилоте сначала подготовьте существующий кабинет в админке.')
        business_id = db.create_business(name=name, address=clean(lead.get('address'), 1000) or None, city=city or None,
                                         owner_id=actor_id, entity_group='internal', moderation_status='pending',
                                         country=clean(lead.get('country_code') or lead.get('country'), 2) or None)
        cursor.execute('''INSERT INTO business_company_links(business_id,company_id,company_location_id,relation_role,is_primary)
            VALUES (%s,%s,%s::uuid,'operator',TRUE) ON CONFLICT DO NOTHING''',
            (business_id, identity['company_id'], identity['company_location_id'] or None))
    if not allowed(business_id):
        raise Conflict('Этот бизнес пока не входит в пилот настройки.')
    profile = read_business(cursor, business_id, lock=True)
    row = init(cursor, business_id, 'staff', lead_id=lead_id, provisional=provisional)
    if row['lead_id'] not in (None, lead_id):
        raise Conflict('У этого кабинета уже есть связанный лид.')
    if not row['lead_id']:
        cursor.execute('UPDATE initial_business_setups SET lead_id=%s WHERE business_id=%s', (lead_id, business_id))
    seed_profile_sources(cursor, row, profile)
    if not row['data'].get('activity_type') and clean(lead.get('category'), 160):
        row['data']['activity_type'] = clean(lead.get('category'), 160)
    for column in ('website', 'source_url', 'telegram_url', 'whatsapp_url'):
        value = lead.get(column)
        if isinstance(value, str) and value.startswith(('http://', 'https://')):
            try:
                register_source(row, value)
            except ValueError:
                continue
    # Keep lead contact data as observations to review, separate from ownership.
    try:
        _, _, observed_url = source_url(lead.get('source_url'))
    except ValueError:
        observed_url = ''
    row['data']['lead_contacts'] = [
        {'field': field, **dated(clean(lead.get(column), 240), observed_url)}
        for field, column in [('contact_phone', 'phone'), ('contact_email', 'email')]
        if clean(lead.get(column), 240)
    ]
    persist(cursor, row)
    return business_id


def prepare_owner(cursor, business_id, actor_id, email, revision):
    from core.email_delivery import build_password_setup_link
    import secrets

    profile = read_business(cursor, business_id, lock=True)
    row = load(cursor, business_id, lock=True)
    if (not profile or not row or row['revision'] != revision
            or not row['data'].get('saved') or row['data'].get('seo_dirty')
            or any(source['status'] in ('added', 'queued') for source in row['data'].get('sources', {}).values())):
        raise Conflict('Сначала проверьте и сохраните данные кабинета.')
    cursor.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', ('initial-setup-owner:' + email,))
    cursor.execute('SELECT id,is_active,password_hash,LOWER(email) AS email FROM users WHERE LOWER(email)=%s FOR UPDATE', (email,))
    owner = cursor.fetchone()
    if owner and owner['is_active'] is False:
        raise Conflict('Аккаунт владельца отключён. Проверьте email.')
    if not row['provisional'] and (not owner or owner['id'] != profile['owner_id']):
        raise Conflict('У компании уже есть владелец. Проверьте его email в админке.')
    if row['provisional'] and profile['owner_id'] != actor_id:
        raise Conflict('Передать черновик может создавший его сотрудник.')
    if not owner:
        owner_id = str(uuid.uuid4())
        cursor.execute('INSERT INTO users(id,email,is_active,is_verified,created_at) VALUES (%s,%s,TRUE,FALSE,NOW())',
                       (owner_id, email))
        password_set = False
    else:
        owner_id = owner['id']
        password_set = bool(owner['password_hash'])
    if row['provisional']:
        cursor.execute("UPDATE businesses SET owner_id=%s,entity_group='client',updated_at=NOW() WHERE id=%s",
                       (owner_id, business_id))
        cursor.execute('UPDATE userservices SET user_id=%s WHERE business_id=%s AND user_id=%s AND source=%s',
                       (owner_id, business_id, actor_id, 'initial_setup'))
        cursor.execute("UPDATE business_company_links SET relation_role='owner' WHERE business_id=%s AND relation_role='operator'", (business_id,))
        cursor.execute('UPDATE initial_business_setups SET provisional=FALSE,revision=revision+1 WHERE business_id=%s',
                       (business_id,))
    if password_set:
        return {'email': email, 'existing_account': True, 'login_path': '/dashboard/operator?business_id=' + business_id + '&setup=1'}
    from services.prepared_cabinet import TOKEN_PREFIX, _digest
    token = TOKEN_PREFIX + secrets.token_urlsafe(32)
    cursor.execute("""INSERT INTO prepared_cabinets (business_id,owner_id,materials,invite_hash,invite_expires_at)
        VALUES (%s,%s,'{}'::jsonb,%s,NOW()+INTERVAL '7 days')
        ON CONFLICT(business_id) DO UPDATE SET invite_hash=EXCLUDED.invite_hash,invite_expires_at=EXCLUDED.invite_expires_at
        WHERE prepared_cabinets.owner_id=EXCLUDED.owner_id RETURNING business_id""", (business_id, owner_id, _digest(token)))
    if not cursor.fetchone():
        raise Conflict('Владелец кабинета изменился. Проверьте его доступ.')
    return {'email': email, 'existing_account': False,
            'invite_url': build_password_setup_link(email, token, private_fragment=True)}
