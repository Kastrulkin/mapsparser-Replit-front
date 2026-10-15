"""Opt-in MAX delivery references the existing LocalOS work, never a second job."""
from datetime import datetime, timezone
import hashlib

from psycopg2.extras import Json

DEFAULT_MAX_NOTIFICATIONS = {'tasks': True, 'errors': True, 'daily_digest': False,
                             'reviews': False, 'agent_results': False, 'finance_rhythm': False,
                             'content_publications': False}


def queue_notification(cursor, *, user_id, max_id, business_id, category, key, text, **context):
    payload = {'update_type': 'localos_notification', 'user_id': user_id, 'max_id': max_id,
               'business_id': business_id, 'category': category, 'text': text, **context}
    cursor.execute('''INSERT INTO max_webhook_events(event_key,payload_json) VALUES (%s,%s)
        ON CONFLICT(event_key) DO NOTHING''', ('notify:' + user_id + ':' + key, Json(payload)))


def collect_max_notifications():
    from database_manager import DatabaseManager
    from services.operator_conversations import _row
    from services.max_webapp_auth import max_enabled
    from services.telegram_control_scope import resolve_control_scope, load_control_preferences
    from core.auth_helpers import verify_business_access
    if not max_enabled():
        return
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        from services.max_guest_audits import collect_guest_audit_results
        collect_guest_audit_results(cursor)
        cursor.execute('''SELECT m.max_id,u.id,u.is_active,u.is_superadmin FROM max_identities m
            JOIN users u ON u.id=m.user_id WHERE m.revoked_at IS NULL AND m.notifications_enabled
            AND COALESCE(u.is_active,TRUE)=TRUE''')
        actors = [dict(row) for row in cursor.fetchall()]
        for actor in actors:
            user_id = str(actor['id'])
            scope = resolve_control_scope(cursor, user_id=user_id, platform='max')
            if not scope:
                continue
            prefs = load_control_preferences(cursor, user_id, platform='max')
            context = scope
            for business_id in scope.get('business_ids') or []:
                business_id = str(business_id)
                cursor.execute('SELECT name FROM businesses WHERE id=%s', (business_id,))
                business = _row(cursor, cursor.fetchone())
                scope = {'kind': 'business', 'id': business_id, 'business_ids': [business_id], 'name': business.get('name') or 'LocalOS'}
                if not verify_business_access(cursor, business_id, actor)[0]:
                    continue
                categories = {**DEFAULT_MAX_NOTIFICATIONS, **(prefs.get('notification_preferences_json', {}).get(context['kind'] + ':' + str(context['id'])) or {})}
                cursor.execute('''SELECT id,kind,status FROM operator_async_jobs
                    WHERE user_id=%s AND business_id=%s AND status IN ('completed','failed')
                    AND NOT EXISTS(SELECT 1 FROM max_webhook_events e WHERE e.event_key='notify:' || operator_async_jobs.user_id || ':job:' || operator_async_jobs.id || ':' || operator_async_jobs.status)
                    AND completed_at>NOW()-INTERVAL '24 hours' ORDER BY completed_at DESC LIMIT 30''', (user_id, business_id))
                jobs = [dict(row) for row in cursor.fetchall()]
                for job in jobs:
                    category = 'errors' if job['status'] == 'failed' else 'agent_results' if str(job['kind']).startswith('agent') else 'tasks'
                    if categories.get(category):
                        queue_notification(cursor, user_id=user_id, max_id=actor['max_id'], business_id=business_id,
                            preference_scope=context['kind'] + ':' + str(context['id']), category=category, key='job:' + str(job['id']) + ':' + str(job['status']),
                            text=('Задание требует внимания' if job['status'] == 'failed' else 'Результат задания готов') + ': ' + str(scope.get('name') or 'LocalOS'))
                if categories.get('daily_digest'):
                    from services.operator_scope_summary import build_operator_scope_summary
                    summary = build_operator_scope_summary(cursor, scope=scope, user_id=user_id)
                    lines = [str(scope.get('name') or 'LocalOS')]
                    lines.extend(str(item.get('title') or '') for item in (summary.get('attention_items') or [])[:5])
                    from core.card_automation import _business_timezone_name, _zoneinfo
                    local_now = datetime.now(timezone.utc).astimezone(_zoneinfo(_business_timezone_name(db.conn, business_id)))
                    if local_now.hour >= 9:
                        day = local_now.date().isoformat()
                        queue_notification(cursor, user_id=user_id, max_id=actor['max_id'], business_id=business_id,
                            preference_scope=context['kind'] + ':' + str(context['id']), category='daily_digest', key='daily:' + business_id + ':' + day, text='\n'.join(lines))
                if categories.get('reviews'):
                    cursor.execute('''SELECT id FROM externalbusinessreviews WHERE business_id=%s
                        AND NOT EXISTS(SELECT 1 FROM max_webhook_events e WHERE e.event_key=%s || externalbusinessreviews.id::text)
                        AND created_at>NOW()-INTERVAL '24 hours' ORDER BY created_at DESC LIMIT 20''', (business_id, 'notify:' + user_id + ':review:'))
                    for review in cursor.fetchall():
                        queue_notification(cursor, user_id=user_id, max_id=actor['max_id'], business_id=business_id,
                            preference_scope=context['kind'] + ':' + str(context['id']), category='reviews', key='review:' + str(review['id']), text='Новый отзыв: ' + str(scope.get('name') or 'LocalOS'))
                if categories.get('agent_results'):
                    cursor.execute('''SELECT id,status FROM agent_runs WHERE business_id=%s AND created_by_user_id=%s
                        AND NOT EXISTS(SELECT 1 FROM max_webhook_events e WHERE e.event_key=%s || agent_runs.id::text)
                        AND completed_at>NOW()-INTERVAL '24 hours' ORDER BY completed_at DESC LIMIT 20''', (business_id, user_id, 'notify:' + user_id + ':agent:'))
                    for run in cursor.fetchall():
                        queue_notification(cursor, user_id=user_id, max_id=actor['max_id'], business_id=business_id,
                            preference_scope=context['kind'] + ':' + str(context['id']), category='agent_results', key='agent:' + str(run['id']), text='Готов результат автоматизации: ' + str(scope.get('name') or 'LocalOS'),
                            screen='agents', item_type='agent_run', item_id=str(run['id']))
                if categories.get('finance_rhythm'):
                    from services.growth_rhythm_notifications import _due_locations, _message
                    from services.growth_overview_service import load_growth_overview_for_scope
                    overview = load_growth_overview_for_scope(scope)
                    for reminder_kind, locations in _due_locations(overview.get('data_rhythm') or {}, datetime.now(timezone.utc).date()).items():
                        if locations:
                            identity = '|'.join(sorted(f"{item.get('location_id')}:{item.get('due_on')}" for item in locations))
                            queue_notification(cursor, user_id=user_id, max_id=actor['max_id'], business_id=business_id,
                                preference_scope=context['kind'] + ':' + str(context['id']), category='finance_rhythm', key='rhythm:' + business_id + ':' + reminder_kind + ':' + hashlib.sha256(identity.encode()).hexdigest(),
                                text=_message(scope, reminder_kind, locations), screen='finance_import')
                if categories.get('content_publications'):
                    collect_content_handoffs(cursor, actor=actor, scope={**scope, 'preference_scope': context['kind'] + ':' + str(context['id'])}, settings=categories)
        db.conn.commit()
    finally:
        db.conn.rollback()
        db.close()


def prepare_notification(cursor, payload):
    from services.max_webapp_auth import load_localos_user_for_max
    from services.telegram_control_scope import load_control_preferences
    from core.auth_helpers import verify_business_access
    from services.max_bot import response, app_keyboard
    actor = load_localos_user_for_max(cursor, payload.get('max_id'))
    if not actor or str(actor['id']) != str(payload.get('user_id')):
        return None
    cursor.execute('SELECT notifications_enabled FROM max_identities WHERE max_id=%s AND revoked_at IS NULL', (payload['max_id'],))
    from services.operator_conversations import _row
    if not _row(cursor, cursor.fetchone()).get('notifications_enabled'):
        return None
    if not verify_business_access(cursor, payload['business_id'], actor)[0]:
        return None
    prefs = load_control_preferences(cursor, str(actor['id']), platform='max')
    categories = {**DEFAULT_MAX_NOTIFICATIONS, **(prefs.get('notification_preferences_json', {}).get(payload.get('preference_scope') or 'business:' + payload['business_id']) or {})}
    if not categories.get(payload['category']):
        return None
    scope = {'kind': 'business', 'id': payload['business_id']}
    buttons = app_keyboard(payload.get('screen') or 'tasks', scope, payload.get('item_type'), payload.get('item_id'))
    if payload.get('post_id'):
        from services.content_publish_notifications import _selected_photos, handoff_revision, handoff_plan_current, handoff_kit_complete, HANDOFF_STATUSES
        from services.max_publication import upload_media
        from services.max_transport import MaxTransport
        cursor.execute('SELECT * FROM social_posts WHERE id=%s AND business_id=%s', (payload['post_id'], payload['business_id']))
        post = _row(cursor, cursor.fetchone())
        if not post or post.get('status') not in HANDOFF_STATUSES or post.get('publish_mode') != 'manual' or not handoff_plan_current(cursor, post):
            return None
        if not handoff_kit_complete(cursor, {**post, 'required_platforms': categories.get('content_publications_platforms') or []}):
            return None
        photos = _selected_photos(cursor, post)
        if handoff_revision({**post, 'selected_photos': photos}) != payload['revision']:
            return None
        if len(photos) > 10:
            raise ValueError('Слишком много медиа для одного комплекта MAX')
        buttons = [upload_media(MaxTransport(), photo) for photo in photos] + buttons
    return response(str(payload['max_id']), str(payload['text']), buttons=buttons)


def collect_content_handoffs(cursor, *, actor, scope, settings):
    from services.content_publish_notifications import (
        _selected_photos, handoff_due, handoff_revision, handoff_plan_current,
        handoff_kit_complete, format_content_publish_handoff, HANDOFF_STATUSES,
    )
    cursor.execute('''SELECT sp.*, b.name business_name, COALESCE(b.address,'') business_address,
        COALESCE(NULLIF(settings.timezone,''),to_jsonb(b)->>'timezone') business_timezone
        FROM social_posts sp JOIN businesses b ON b.id=sp.business_id
        LEFT JOIN business_finance_settings settings ON settings.business_id=b.id
        WHERE sp.business_id=%s AND sp.publish_mode='manual' AND sp.status=ANY(%s)
        AND sp.scheduled_for>NOW()-INTERVAL '1 day' AND sp.scheduled_for<NOW()+INTERVAL '9 days'
        ORDER BY sp.scheduled_for LIMIT 30''', (scope['id'], list(HANDOFF_STATUSES)))
    posts = [dict(post) for post in cursor.fetchall()]
    for post in posts:
        item = {**post, 'user_id': str(actor['id']), 'scope_type': 'business', 'scope_id': scope['id'],
                'lead_days': str(settings.get('content_publications_lead_days') or 0),
                'handoff_time': settings.get('content_publications_time') or '',
                'required_platforms': settings.get('content_publications_platforms') or []}
        item['selected_photos'] = _selected_photos(cursor, post)
        if not handoff_due(item, datetime.now(timezone.utc)) or not handoff_plan_current(cursor, post) or not handoff_kit_complete(cursor, item):
            continue
        revision = handoff_revision(item)
        message, _ = format_content_publish_handoff(item)
        queue_notification(cursor, user_id=str(actor['id']), max_id=actor['max_id'], business_id=scope['id'],
            preference_scope=scope.get('preference_scope'), category='content_publications', key='content:' + str(post['id']) + ':' + revision,
            text=message, post_id=post['id'], revision=revision, screen='content', item_type='post', item_id=post['id'])
