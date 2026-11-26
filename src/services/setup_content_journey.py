"""Follow-up in setup chat, using the content calendar and the existing automation queue."""
import uuid
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from psycopg2.extras import Json

from services import business_knowledge
from services import initial_business_setup as setup
from services.agent_version_store import insert_version
from services.business_input_settings import resolve
from services.operator_async_jobs import create_operator_async_job
from subscription_manager import get_subscription_access


EXECUTOR = 'monthly_content_drafts_v1'
LABEL = 'Контент-план раз в месяц'
MAP_CHANNELS = {'yandex': 'yandex_maps', 'google': 'google_business', '2gis': 'two_gis'}
SOCIAL_CHANNELS = {
    'telegram': 'telegram', 'telegram_bot': 'telegram', 'vk': 'vk', 'vk_group': 'vk',
    'vk_business': 'vk', 'max_bot': 'max', 'instagram': 'instagram', 'facebook': 'facebook',
}
APPROVED_POSTS = ('approved', 'scheduled', 'publishing', 'published')


def lock(cursor, business_id):
    cursor.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', ('setup-content:' + business_id,))


def _monthly(cursor, business_id):
    cursor.execute("""SELECT id,status,metadata_json FROM agent_blueprints
        WHERE business_id=%s AND metadata_json->>'native_executor'=%s AND status<>'archived'
        ORDER BY created_at,id LIMIT 1""", (business_id, EXECUTOR))
    return cursor.fetchone() or {}


def _plan(cursor, business_id, *, lock_items=False):
    cursor.execute("""SELECT id, title, COALESCE(period_end,period_start) period_end, generated_plan_json->'meta' meta
        FROM contentplans WHERE business_id=%s AND plan_status<>'archived'
          AND COALESCE(scope_type,'single_business')<>'network_parent'
        ORDER BY period_start DESC,created_at DESC,id LIMIT 1""", (business_id,))
    plan = cursor.fetchone()
    if not plan:
        return None
    cursor.execute("""SELECT i.id,i.theme,i.goal,i.scheduled_for,
        COALESCE(NULLIF(BTRIM(i.draft_text),''),'')<>'' OR i.status IN ('approved','published') OR EXISTS (
            SELECT 1 FROM social_posts p WHERE p.business_id=i.business_id AND p.content_plan_item_id=i.id
              AND COALESCE(NULLIF(BTRIM(p.platform_text),''),NULLIF(BTRIM(p.base_text),'')) IS NOT NULL
        ) has_text,
        (i.status IN ('approved','published') OR EXISTS (SELECT 1 FROM social_posts p WHERE p.business_id=i.business_id AND p.content_plan_item_id=i.id
              AND p.status=ANY(%s)))
          AND NOT EXISTS (SELECT 1 FROM social_posts p WHERE p.business_id=i.business_id AND p.content_plan_item_id=i.id
              AND p.status<>ALL(%s) AND p.status NOT IN ('cancelled','skipped','archived')) approved
        FROM contentplanitems i WHERE i.plan_id=%s AND i.business_id=%s AND i.status<>'skipped'
        ORDER BY i.scheduled_for,i.id""" + (' FOR UPDATE OF i' if lock_items else ''),
        (list(APPROVED_POSTS), list(APPROVED_POSTS), plan['id'], business_id))
    items = cursor.fetchall()
    version = setup.fingerprint([(str(item['id']), item['theme'], item['goal'], str(item['scheduled_for'])) for item in items])
    review = (plan['meta'] or {}).get('initial_setup_review') or {}
    return {'id': str(plan['id']), 'title': plan['title'], 'period_end': plan['period_end'].isoformat(),
            'version': version, 'topics': [item['theme'] for item in items],
            'reviewed': review.get('approved_version') == version and bool(items),
            'needs_text': sum(not item['has_text'] for item in items),
            'needs_post_review': sum(not item['approved'] for item in items)}


def _recorded_channels(cursor, business_id):
    cursor.execute("""SELECT DISTINCT source FROM externalbusinessaccounts
        WHERE business_id=%s AND is_active IS TRUE AND NULLIF(BTRIM(external_id),'') IS NOT NULL
          AND COALESCE(last_error,'')=''""", (business_id,))
    sources = {item['source'] for item in cursor.fetchall()}
    cursor.execute("SELECT to_jsonb(b)->>'telegram_chat_id' AS telegram_chat FROM businesses b WHERE id=%s",
                   (business_id,))
    if (cursor.fetchone() or {}).get('telegram_chat'):
        sources.add('telegram')
    return sources


def _job(cursor, business_id):
    cursor.execute("""SELECT id,status FROM operator_async_jobs
        WHERE business_id=%s AND kind='content_plan_generate' AND payload_json->>'setup_content'='true'
        ORDER BY created_at DESC,id DESC LIMIT 1""", (business_id,))
    row = cursor.fetchone()
    return {'id': str(row['id']), 'status': row['status']} if row else None


def state(cursor, row, profile, actor, can_edit):
    business_id = str(row['business_id'])
    plan = _plan(cursor, business_id)
    prefs = row['data'].get('content_journey') or {}
    record = _monthly(cursor, business_id)
    config = (record.get('metadata_json') or {}).get('monthly_content') or {}
    sources = _recorded_channels(cursor, business_id)
    socials = sorted({SOCIAL_CHANNELS[source] for source in sources if source in SOCIAL_CHANNELS})
    saved_maps = {source.get('provider') for source in row['data'].get('sources', {}).values()
                  if source.get('kind') == 'map' and not source.get('competitor') and source.get('status') == 'ready'}
    map_channels = {MAP_CHANNELS[key] for key in saved_maps if key in MAP_CHANNELS}
    if 'google_business' in sources:
        saved_maps.discard('google')
        map_channels.add('google_business')
    cursor.execute("""SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE analysis_status='analyzed') AS analyzed
        FROM photo_assets WHERE business_id=%s AND metadata_json->>'disk_import_available' IS DISTINCT FROM 'false'""",
                   (business_id,))
    photos = cursor.fetchone()
    job = _job(cursor, business_id)
    facts = business_knowledge.planning_facts(cursor, business_id, actor['user_id'])
    zone = resolve(cursor, business_id).get('timezone')
    owner = str(profile['owner_id']) == str(actor['user_id']) and not row['provisional']
    capabilities = get_subscription_access(business_id).get('capabilities') or []
    can_plan = 'maps.news' in capabilities
    active = record.get('status') == 'active' and config.get('owner_id') == str(profile['owner_id'])
    if saved_maps and not prefs.get('maps_done') and not plan:
        step = 'maps'
    elif job and job['status'] in ('queued', 'running'):
        step = 'generating'
    elif not plan:
        step = 'plan'
    elif not plan['reviewed'] and not photos['analyzed'] and not prefs.get('photos_skipped') and not config:
        step = 'photos'
    elif not plan['reviewed']:
        step = 'review'
    elif not active and plan['needs_post_review'] and prefs.get('texts_deferred') != plan['id']:
        step = 'texts'
    elif not active and not socials and not prefs.get('socials_deferred'):
        step = 'socials'
    else:
        step = 'monthly'
    return {'step': step, 'plan': plan, 'photos': photos, 'fact_count': len(facts), 'job': job,
            'socials': socials, 'map_channels': sorted(map_channels), 'viewer_is_owner': owner,
            'can_edit': can_edit, 'can_plan': can_plan, 'timezone': zone,
            'monthly': {'active': active, 'id': str(record.get('id') or ''), 'first_month': config.get('first_month'),
                        'can_enable': owner and 'automation' in capabilities, 'can_pause': owner and active}}


def _enqueue(cursor, business_id, owner_id, channels, *, blueprint_id=None, month=None, start=None):
    key = f'setup-content:{business_id}:{month or "first"}'
    return create_operator_async_job(cursor, user_id=owner_id, action_id=None, business_id=business_id,
        kind='content_plan_generate', idempotency_key=key, stage='Подбираем темы для контент-плана',
        payload={'setup_content': True, 'period_days': 30, 'scope_type': 'single_business',
                 'density': 'standard', 'content_mix': {'channels': channels}, 'blueprint_id': blueprint_id,
                 'period_start': start.isoformat() if start else None})


def _next_month(day):
    return (day.replace(day=28) + timedelta(days=4)).replace(day=1)


def update(cursor, row, profile, actor, can_edit, data, *, now=None):
    if not can_edit:
        raise PermissionError('У вас нет права менять настройки кабинета.')
    business_id = str(row['business_id'])
    owner_id = str(profile['owner_id'])
    current = state(cursor, row, profile, actor, can_edit)
    action = data.get('action')
    plan = current['plan']
    if action in {'maps_done', 'photos_skipped', 'socials_deferred', 'texts_deferred'}:
        if action == 'texts_deferred' and not plan:
            raise setup.Conflict('Сначала подготовьте план.')
        row['data'].setdefault('content_journey', {})[action] = plan['id'] if action == 'texts_deferred' else True
        setup.persist(cursor, row)
    elif action == 'generate':
        if not current['can_plan']:
            raise PermissionError('Для подготовки контент-плана нужен доступ к разделу «Контент».')
        if plan:
            raise setup.Conflict('Контент-план уже есть. Откройте его на проверку.')
        channels = current['map_channels'] + current['socials']
        _enqueue(cursor, business_id, owner_id, channels or ['yandex_maps'])
    elif action == 'retry':
        if not current['can_plan'] or (current['job'] or {}).get('status') not in ('failed', 'cancelled'):
            raise setup.Conflict('Сейчас нет подготовки, которую можно повторить.')
        cursor.execute("""UPDATE operator_async_jobs SET status='queued',attempt_count=0,error_text=NULL,
            next_attempt_at=NOW(),updated_at=NOW() WHERE id=%s AND business_id=%s AND status IN ('failed','cancelled')""",
            (current['job']['id'], business_id))
    elif action == 'approve':
        if not current['viewer_is_owner']:
            raise PermissionError('Темы утверждает владелец компании.')
        plan = _plan(cursor, business_id, lock_items=True)
        if not plan or not plan['topics'] or data.get('plan_id') != plan['id'] or data.get('version') != plan['version']:
            raise setup.Conflict('План изменился. Откройте свежие темы и проверьте их.')
        review = {'required': True, 'approved_version': plan['version'], 'approved_by': actor['user_id'],
                  'approved_at': datetime.now(timezone.utc).isoformat()}
        cursor.execute("""UPDATE contentplans SET generated_plan_json=jsonb_set(
            COALESCE(generated_plan_json,'{}'::jsonb),'{meta}',
            COALESCE(generated_plan_json->'meta','{}'::jsonb)||%s::jsonb,TRUE)
            WHERE id=%s AND business_id=%s""", (Json({'initial_setup_review': review}), plan['id'], business_id))
        cursor.execute("""UPDATE operator_async_jobs SET status='completed',completed_at=NOW(),updated_at=NOW(),
            stage='Темы контент-плана утверждены' WHERE business_id=%s AND status='waiting_for_review'
            AND payload_json->>'setup_content'='true' AND result_json->>'plan_id'=%s""", (business_id, plan['id']))
    elif action in ('enable_monthly', 'pause_monthly'):
        if str(actor['user_id']) != owner_id or row['provisional']:
            raise PermissionError('Расписание подтверждает владелец компании.')
        if action == 'pause_monthly':
            if current['monthly']['can_pause']:
                cursor.execute("UPDATE agent_blueprints SET status='paused',updated_at=NOW() WHERE id=%s AND business_id=%s",
                               (current['monthly']['id'], business_id))
        else:
            if not current['monthly']['can_enable'] or not plan or not plan['reviewed'] or not current['timezone']:
                raise setup.Conflict('Для расписания утвердите темы и укажите часовой пояс компании.')
            if not current['monthly']['active']:
                zone = current['timezone']
                now = now or datetime.now(timezone.utc)
                first_month = _next_month(now.astimezone(ZoneInfo(zone)).date()).isoformat()
                config = {'owner_id': owner_id, 'first_month': first_month, 'timezone': zone}
                record = _monthly(cursor, business_id)
                blueprint_id = str(record['id']) if record else str(uuid.uuid4())
                metadata = {**(record.get('metadata_json') or {}), 'native_executor': EXECUTOR,
                            'execution_mode': 'scheduled', 'monthly_content': config}
                if not record:
                    cursor.execute("""INSERT INTO agent_blueprints
                        (id,business_id,name,category,description,status,created_by_user_id,metadata_json)
                        VALUES (%s,%s,%s,'content','Темы на утверждение владельцу','draft',%s,%s)""",
                        (blueprint_id, business_id, LABEL, owner_id, Json(metadata)))
                version = insert_version(cursor, blueprint_id, {
                    'goal': 'Подготовить черновик контент-плана на утверждение',
                    'execution_mode': 'scheduled', 'trigger': 'schedule.daily',
                    'schedule': {'time': '09:00', 'timezone': zone, 'cadence': 'monthly'},
                    'output_schema': {'native_executor': EXECUTOR},
                    'approval_policy': {'content_plan_review': 'owner'},
                }, actor)
                metadata['active_version_id'] = version['id']
                cursor.execute("UPDATE agent_blueprints SET status='active',metadata_json=%s,updated_at=NOW() WHERE id=%s",
                               (Json(metadata), blueprint_id))
    else:
        raise ValueError('Выберите действие для контент-плана.')
    return state(cursor, row, profile, actor, can_edit)


def scheduled_dispatch(cursor, blueprint, now):
    business_id = str(blueprint['business_id'])
    lock(cursor, business_id)
    fresh = _monthly(cursor, business_id)
    settings = (fresh.get('metadata_json') or {}).get('monthly_content') or {}
    owner_id = settings.get('owner_id')
    if not owner_id or fresh.get('status') != 'active' or fresh.get('id') != blueprint['id']:
        return None
    profile = setup.read_business(cursor, business_id)
    if not profile or str(profile['owner_id']) != owner_id:
        return None
    local_now = now.astimezone(ZoneInfo(settings['timezone']))
    today = local_now.date()
    month = today.replace(day=1)
    if local_now.hour < 9 or month < date.fromisoformat(settings['first_month']):
        return None
    cursor.execute('SELECT 1 FROM operator_async_jobs WHERE user_id=%s AND idempotency_key=%s',
                   (owner_id, f"setup-content:{business_id}:{month:%Y-%m}"))
    if cursor.fetchone():
        return None
    plan = _plan(cursor, business_id)
    job = _job(cursor, business_id)
    if (job or {}).get('status') in ('queued', 'running') or (plan and not plan['reviewed']):
        return None
    start = max(today, date.fromisoformat(plan['period_end']) + timedelta(days=1)) if plan else today
    if start >= _next_month(month):
        return None
    if 'automation' not in (get_subscription_access(business_id).get('capabilities') or []):
        return None
    sources = _recorded_channels(cursor, business_id)
    channels = {SOCIAL_CHANNELS[source] for source in sources if source in SOCIAL_CHANNELS}
    cursor.execute('SELECT map_type FROM businessmaplinks WHERE business_id=%s', (business_id,))
    channels.update(MAP_CHANNELS[row['map_type']] for row in cursor.fetchall() if row['map_type'] in MAP_CHANNELS)
    return _enqueue(cursor, business_id, owner_id, sorted(channels) or ['yandex_maps'],
                    blueprint_id=str(fresh['id']), month=month.strftime('%Y-%m'), start=start)


def generate_for_review(job):
    from database_manager import DatabaseManager
    from services.content_plan_service import create_generated_content_plan

    business_id = str(job['business_id'])
    user_id = str(job['user_id'])
    payload = job['payload_json']
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        lock(cursor, business_id)
        profile = setup.read_business(cursor, business_id)
        cursor.execute('SELECT is_active FROM users WHERE id=%s', (user_id,))
        account = cursor.fetchone()
        if not profile or str(profile['owner_id']) != user_id or not account or account['is_active'] is False:
            return {'status': 'cancelled'}
        if payload.get('blueprint_id'):
            record = _monthly(cursor, business_id)
            config = (record.get('metadata_json') or {}).get('monthly_content') or {}
            if (record.get('status') != 'active' or str(record.get('id')) != payload['blueprint_id']
                    or config.get('owner_id') != user_id
                    or 'automation' not in (get_subscription_access(business_id).get('capabilities') or [])):
                return {'status': 'cancelled'}
        start = payload.get('period_start')
        plan = create_generated_content_plan(user_id, business_id, scope_type='single_business',
            scope_target_id=business_id, period_days=30, density='standard', content_mix=payload['content_mix'],
            operator_request_id=str(job['id']), period_start=date.fromisoformat(start) if start else None,
            needs_setup_review=True)
        return {'plan_id': str(plan.get('id') or '')}
    finally:
        db.rollback_and_close()
