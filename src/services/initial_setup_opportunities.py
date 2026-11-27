"""First local opportunities, using the company and creator catalogs."""
import math
import time
import uuid
from urllib.parse import urlsplit

from psycopg2.extras import Json

from services import initial_business_setup as setup
from services.business_permissions import load_actor, require_permission
from services.company_registry_service import observe_company_candidate, resolve_company_coordinates
from services.operator_async_jobs import create_operator_async_job

KIND = 'initial_setup_opportunities'
RADIUS_KM = 2
RESULT_LIMIT = 5
SEARCH_LIMIT = 8
PARTNER_CATEGORIES = {
    'beauty': ('студия йоги', 'фитнес', 'магазин косметики', 'фотостудия', 'ювелирный'),
    'food': ('коворкинг', 'фитнес', 'школа', 'магазин продуктов', 'организация мероприятий'),
    'lodging': ('экскурсии', 'прокат', 'кафе', 'туристическое агентство', 'трансфер'),
    'production': ('рекламное агентство', 'типография', 'коворкинг', 'организация мероприятий'),
}


def categories(activity):
    name = activity.casefold()
    for kind, stems in (
        ('beauty', ('beauty','salon','красот','космет','лазер','массаж')),
        ('food', ('food','cafe','коф','морожен','кондитер','ресторан','ice cream')),
        ('lodging', ('hotel','апартамент','аренд','гостиниц','гостев')),
        ('production', ('manufactur','пошив','мерч','производ','экспертиз','резка')),
    ):
        if any(stem in name for stem in stems):
            return PARTNER_CATEGORIES[kind]
    return ('коворкинг', 'бизнес-центр', 'организация мероприятий')


def queue(cursor, row, profile, actor_id, *, refresh=False):
    data = row['data']
    previous = data.get('opportunities') or {}
    if previous and not refresh:
        return
    if previous.get('job_id') and previous.get('status') == 'queued':
        cursor.execute("SELECT status FROM operator_async_jobs WHERE id=%s AND business_id=%s",
                       (previous['job_id'],row['business_id']))
        if (cursor.fetchone() or {}).get('status') in ('queued','running'):
            return
    city = str(profile.get('city') or '').strip()
    if not city:
        data['opportunities'] = {**previous, 'status': 'needs_city'}
        return
    job = create_operator_async_job(cursor, user_id=actor_id, action_id=None, business_id=row['business_id'],
        kind=KIND, idempotency_key=f"initial-opportunities:{row['business_id']}:{row['revision']}",
        stage='Ищем партнёров и блогеров', payload={}, max_attempts=1)
    data['opportunities'] = {**previous, 'status': 'queued', 'job_id': job['id']}


def map_center(profile, sources):
    coordinates = resolve_company_coordinates(profile)
    if coordinates != (None, None):
        return coordinates
    for source in sources:
        if source.get('kind') == 'map' and source.get('status') == 'ready' and not source.get('competitor'):
            coordinates = resolve_company_coordinates(source)
            if coordinates != (None, None):
                return coordinates
    return None, None


def nearby(cursor, business_id, lat, lon, suitable):
    dy = RADIUS_KM / 110
    dx = dy / max(0.01, math.cos(math.radians(lat)))
    cursor.execute("""SELECT c.id,c.canonical_name name,c.primary_category category,l.address,l.latitude,l.longitude,
        l.id location_id, (SELECT canonical_url FROM company_external_profiles p
        WHERE p.company_location_id=l.id AND p.canonical_url IS NOT NULL ORDER BY p.last_collected_at DESC NULLS LAST, p.id LIMIT 1) url
        FROM company_locations l JOIN companies c ON c.id=l.company_id
        WHERE l.status='active' AND c.status IN ('active','observed')
          AND l.latitude BETWEEN %s AND %s AND l.longitude BETWEEN %s AND %s
          AND NOT EXISTS (SELECT 1 FROM business_company_links b
            WHERE b.business_id=%s AND b.company_id=c.id)
          AND c.primary_category ILIKE ANY(%s)
        ORDER BY ABS(l.latitude-%s) + ABS(l.longitude-%s),c.id LIMIT 60""",
        (lat-dy, lat+dy, lon-dx, lon+dx, business_id, ['%'+category+'%' for category in suitable], lat, lon))
    from api.prospecting.search_routes import _geo_distance_km
    selected = {}
    for row in cursor.fetchall():
        distance = _geo_distance_km(lat, lon, float(row['latitude']), float(row['longitude']))
        if distance <= RADIUS_KM:
            company_id = str(row['id'])
            item = {**dict(row), 'id':company_id, 'location_id':str(row['location_id']), 'distance_m':round(distance*1000)}
            item.pop('latitude')
            item.pop('longitude')
            if company_id not in selected or item['distance_m'] < selected[company_id]['distance_m']:
                selected[company_id] = item
    return sorted(selected.values(), key=lambda item: item['distance_m'])[:RESULT_LIMIT]


def creator_shortlist(cursor, business_id, actor_id, city, topics):
    from services.creator_city_service import city_matches
    from services.creator_promotion_service import run_creator_search
    result = run_creator_search(cursor, business_id=business_id, user_id=actor_id,
                               brief={'city':city,'topics':topics,'result_limit':10})
    good = {'best_fit','strong_local','precise_small_audience'}
    matches = [item for item in result.get('results', []) if item.get('result_group') in good
               and city_matches(item.get('home_city') or item.get('primary_city'), city)]
    return str(result['id']), [{'name':item['display_name'],'url':item['canonical_url'],
                               'platform':item['platform']} for item in matches[:RESULT_LIMIT]]


def notify_catalog_gap(cursor, business_id, city):
    from subscription_manager import SUPERADMIN_EMAIL
    key = 'initial-setup-creator-gap:' + city.casefold()
    cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",(key,))
    cursor.execute("""INSERT INTO journey_actions(id,business_id,user_id,flow_type,entity_type,entity_id,
        action_type,status,title,description,cta_label,cta_target_json,payload_json,dedupe_key,due_at)
        SELECT %s,%s,u.id,'work_journal','owner_task',%s,'owner_action','ready',%s,%s,'Открыть базу блогеров',
               %s,%s,%s,NOW()
        FROM users u WHERE LOWER(u.email)=%s AND u.is_active IS NOT FALSE
          AND NOT EXISTS (SELECT 1 FROM journey_actions WHERE dedupe_key=%s)
        ON CONFLICT DO NOTHING RETURNING id""",
        (str(uuid.uuid4()),business_id,city,'Найти блогеров в городе '+city,
         'В базе LocalOS пока нет подходящих авторов для первичной настройки.',
         Json({'href':'/dashboard/influencers','business_id':business_id}),
         Json({'kind':'task','delivery':'in_app','city':city}),key,SUPERADMIN_EMAIL,key))
    if cursor.fetchone():
        return True
    cursor.execute("SELECT 1 FROM journey_actions WHERE dedupe_key=%s", (key,))
    return bool(cursor.fetchone())


def _map_search(city, address, category):
    from services.outreach_continuation import _start_search, _poll_search
    config = {'search_source':'apify','billing_mode':'shared_balance_actual',
              'search_call_cap_cents':int(setup.SETUP_APIFY_CAP * 100),
              'max_candidates':SEARCH_LIMIT,'batch_size':SEARCH_LIMIT,
              'queries':[{'query':category,'city':', '.join(part for part in (address,city) if part)}]}
    run = _start_search(config, 0)
    deadline = time.monotonic()+90
    while time.monotonic()<deadline:
        results = _poll_search(run, SEARCH_LIMIT)
        if results is not None:
            return results
        time.sleep(3)
    raise TimeoutError('Поиск рядом ещё не завершился.')


def _save_neighbors(cursor, profile, partners):
    from services.company_registry_service import ensure_company_for_business
    identity = ensure_company_for_business(cursor.connection, profile, source='initial_setup_nearby')
    for item in partners:
        cursor.execute("""INSERT INTO company_relationships(subject_company_id,object_company_id,context_business_id,
            relationship_type,status,source_url,confidence)
            VALUES (%s,%s,%s,'partner','observed',%s,0.8)
            ON CONFLICT DO NOTHING""", (identity['company_id'], item['id'], profile['id'], item.get('url')))


def process(claimed):
    from database_manager import DatabaseManager

    db = DatabaseManager()
    business_id, actor_id = claimed['business_id'], claimed['user_id']
    try:
        cursor = db.conn.cursor()
        require_permission(cursor,business_id,load_actor(cursor,actor_id),'business.settings.write')
        row = setup.load(cursor,business_id,lock=True)
        profile = setup.read_business(cursor,business_id)
        current = row.get('data', {}).get('opportunities') or {}
        if current.get('job_id') != str(claimed['id']) or not profile:
            return {'status':'obsolete'}
        city = str(profile.get('city') or '').strip()
        activity = row['data'].get('activity_type') or str(profile.get('business_type') or '')
        suitable = categories(activity)
        lat, lon = map_center(profile,row['data'].get('sources',{}).values())
        if lat is not None:
            profile.update(latitude=lat, longitude=lon)
        partners = nearby(cursor,business_id,lat,lon,suitable) if lat is not None else []
        cursor.execute("""SELECT 1 FROM operator_async_jobs WHERE business_id=%s
            AND kind=%s AND jsonb_exists(payload_json,'apify_started') LIMIT 1""",
            (business_id,setup.JOB_KIND))
        read_budget_used = bool(cursor.fetchone())
        can_search = lat is not None and city and not partners and not current.get('provider_started') and not read_budget_used
        if can_search:
            current['provider_started'] = True
            setup.persist(cursor,row)
        db.conn.commit()
        provider_error = False
        if can_search:
            try:
                for candidate in _map_search(city,str(profile.get('address') or ''),suitable[0]):
                    url = str(candidate.get('source_url') or '')
                    if urlsplit(url).scheme in ('http','https') and candidate.get('name'):
                        observe_company_candidate(db.conn,candidate,source='initial_setup_nearby')
            except Exception:
                db.conn.rollback()
                provider_error = True
            if not provider_error:
                partners = nearby(cursor,business_id,lat,lon,suitable)
        row = setup.load(cursor,business_id,lock=True)
        if (row.get('data', {}).get('opportunities') or {}).get('job_id') != str(claimed['id']):
            return {'status':'obsolete'}
        creator_job, creators = creator_shortlist(cursor,business_id,actor_id,city,[activity] if activity else [])
        gap_reported = not creators and notify_catalog_gap(cursor,business_id,city)
        if partners:
            _save_neighbors(cursor,profile,partners)
        row['data']['opportunities'] = {**current, 'status':'ready','city':city,'partner_search_unavailable':provider_error,
                                        'partners':partners,'creators':creators,'creator_search_id':creator_job,
                                        'gap_reported':gap_reported,
                                        'has_location':lat is not None,'suggested_categories':list(suitable)}
        setup.persist(cursor,row)
        db.conn.commit()
        return {'status':'ready','partners':len(partners),'creators':len(creators)}
    finally:
        db.rollback_and_close()
