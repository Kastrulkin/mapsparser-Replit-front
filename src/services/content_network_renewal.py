"""Per-plan completion on existing receipts, jobs and notification outbox.

No sender, schedule, model or provider credentials live in compiled source.
"""
import json
from datetime import date, datetime, timedelta, timezone
from statistics import median
from zoneinfo import ZoneInfo

from services.compiled_content_handoff import handoff_targets
from services.content_publish_notifications import (
    HANDOFF_STATUSES, _json_object, _selected_photos, handoff_revision, queue_handoff_alert,
)

KIND = 'content_plan_network_renewal'


def service_changes(current, previous):
    before = {str(row.get('id') or row.get('name')): row for row in previous if isinstance(row, dict)}
    after = {str(row.get('id') or row.get('name')): row for row in current if isinstance(row, dict)}
    return {
        'added': [after[key] for key in sorted(after.keys()-before.keys())],
        'removed': [before[key] for key in sorted(before.keys()-after.keys())],
        'changed': [{'before': before[key], 'after': after[key]} for key in sorted(before.keys() & after.keys())
                    if any(str(before[key].get(field) or '') != str(after[key].get(field) or '') for field in ('name','price'))],
    }


def approved_plan_ids(cursor, scope, business_id, blueprint_id, version_id):
    """Only the reviewed lineage of the originally approved plans is connected."""
    roots = scope['plan_ids'][business_id]
    cursor.execute("""WITH RECURSIVE connected(id) AS (
        SELECT id FROM contentplans WHERE business_id=%s AND id::text=ANY(%s)
        UNION
        SELECT child.id FROM contentplans child JOIN connected parent
          ON child.generated_plan_json->'meta'->>'previous_plan_id'=parent.id::text
        WHERE child.business_id=%s AND child.plan_status<>'archived'
          AND child.generated_plan_json->'meta'->'handoff_approval'->>'blueprint_id'=%s
          AND child.generated_plan_json->'meta'->'handoff_approval'->>'version_id'=%s
          AND child.generated_plan_json->'meta'->'handoff_approval'->>'approved_by_user_id'=%s
    ) SELECT id FROM connected""", (business_id, roots, business_id, blueprint_id, version_id, scope['renewal']['reviewer_user_id']))
    return sorted({str(row['id']) for row in cursor.fetchall()})


def approve_successor(conn, *, blueprint_id, plan_id, user_id):
    """User reviews the normal plan first; this never queues external publishing."""
    from services.compiled_content_program import contract_for, authorize_contract
    from services.social_post_service import approve_social_posts
    cursor = conn.cursor()
    cursor.execute('SELECT b.business_id anchor_business_id,v.* FROM agent_blueprints b JOIN agent_blueprint_versions v ON v.id=b.compiled_approved_version_id WHERE b.id=%s', (blueprint_id,))
    version = cursor.fetchone() or {}
    contract = contract_for(version, str(version.get('anchor_business_id') or ''))
    scope = contract['scope']
    if not scope.get('renewal') or scope['renewal']['reviewer_user_id'] != user_id:
        raise PermissionError('Только выбранный владелец может утвердить продолжение')
    authorize_contract(cursor, contract, user_id)
    cursor.execute("SELECT * FROM contentplans WHERE id=%s AND plan_status<>'archived'", (plan_id,))
    plan = cursor.fetchone() or {}
    meta = (plan.get('generated_plan_json') or {}).get('meta') or {}
    business_id = str(plan.get('business_id') or '')
    if (business_id not in scope['business_ids'] or meta.get('network_automation_id') != blueprint_id
            or meta.get('previous_plan_id') not in approved_plan_ids(cursor, scope, business_id, blueprint_id, str(version['id']))):
        raise ValueError('Продолжение не относится к этой автоматизации')
    cursor.execute("SELECT id FROM contentplanitems WHERE plan_id=%s AND business_id=%s AND status<>'skipped'", (plan_id,business_id))
    items = cursor.fetchall()
    post_ids = []
    for item in items:
        cursor.execute('SELECT * FROM social_posts WHERE content_plan_item_id=%s AND business_id=%s AND platform=ANY(%s)', (item['id'],business_id,scope['platforms']))
        posts = cursor.fetchall()
        if len(posts) != len(scope['platforms']) or {row['platform'] for row in posts} != set(scope['platforms']):
            raise ValueError('Не все варианты подготовлены')
        if any(not _selected_photos(cursor,post) or not str(post.get('platform_text') or post.get('base_text') or '').strip() for post in posts):
            raise ValueError('Для каждого поста нужны проверенные текст и фото')
        post_ids.extend(str(post['id']) for post in posts)
    if not post_ids:
        raise ValueError('В продолжении нет постов')
    # Each existing approval validates editorial quality and records learning.
    result = approve_social_posts(user_id, post_ids)
    if result.get('failed'):
        raise ValueError('Не все тексты прошли редакционную проверку; план не подключён')
    approval = {'blueprint_id': blueprint_id, 'version_id': str(version['id']), 'approved_by_user_id': user_id,
                'approved_at': datetime.now(timezone.utc).isoformat()}
    cursor.execute("UPDATE contentplans SET generated_plan_json=jsonb_set(generated_plan_json,'{meta,handoff_approval}',%s::jsonb,TRUE) WHERE id=%s", (json.dumps(approval),plan_id))
    return {'plan_id': plan_id, 'connected': True, 'publication_status_unchanged': True}


def successor_dates(dates, *, today, period_days=30):
    ordered = sorted(set(date.fromisoformat(str(value)[:10]) for value in dates))
    if len(ordered) < 2:
        raise ValueError('Для сохранения частоты нужны хотя бы две даты предыдущего плана')
    interval = max(1, round(median((right-left).days for left, right in zip(ordered, ordered[1:]))))
    start = ordered[-1] + timedelta(days=interval)
    while start <= today:
        start += timedelta(days=interval)
    end = start + timedelta(days=period_days-1)
    return start, end, [(start+timedelta(days=offset)).isoformat() for offset in range(0, period_days, interval)]


def existing_successor(cursor, business_id, plan_id):
    cursor.execute("""SELECT id FROM contentplans WHERE business_id=%s
        AND plan_status<>'archived'
        AND generated_plan_json->'meta'->>'previous_plan_id'=%s
        ORDER BY created_at,id LIMIT 1""", (business_id, str(plan_id)))
    return cursor.fetchone()


def resolve_successor_context(cursor, business_id, context):
    plan_id = context['previous_plan_id']
    # The caller holds the content-plan business transaction lock. This fence
    # also covers jobs queued before an existing continuation was approved.
    if existing_successor(cursor, business_id, plan_id):
        raise ValueError('Продолжение этого плана уже существует; повторное создание запрещено')
    cursor.execute("SELECT id FROM contentplans WHERE id=%s AND business_id=%s AND plan_status<>'archived'", (plan_id, business_id))
    if not cursor.fetchone():
        raise ValueError('Предыдущий план недоступен')
    cursor.execute("SELECT scheduled_for,theme FROM contentplanitems WHERE plan_id=%s AND business_id=%s AND status<>'skipped' ORDER BY scheduled_for,id", (plan_id, business_id))
    items = cursor.fetchall()
    today = datetime.now(timezone.utc).astimezone(ZoneInfo(context['timezone'])).date()
    start, end, dates = successor_dates([item['scheduled_for'] for item in items], today=today)
    # All historical topics for this branch, not only the immediately preceding month.
    cursor.execute('SELECT theme FROM contentplanitems WHERE business_id=%s AND theme IS NOT NULL', (business_id,))
    return {'previous_plan_id': plan_id, 'period_start': start, 'period_end': end,
            'dates': dates, 'excluded_themes': [row['theme'] for row in cursor.fetchall()],
            'channels': context['channels']}


def last_packet_complete(posts, recipients, platforms):
    """Current revision AND every recipient/channel; uncertain is never success."""
    if set(post.get('platform') for post in posts) != set(platforms) or len(posts) != len(platforms):
        return False
    for post in posts:
        if post.get('status') not in HANDOFF_STATUSES or not post.get('selected_photos'):
            return False
        revision = handoff_revision(post)
        receipts = _json_object(_json_object(_json_object(post.get('metadata_json')).get('staff_handoff')).get('telegram_deliveries'))
        for user_id in recipients:
            receipt = receipts.get(user_id) or {}
            parts = _json_object(receipt.get('parts'))
            if not receipt.get('sent_at') or receipt.get('revision') != revision or not parts:
                return False
            if any(part.get('status') != 'sent' for part in parts.values()):
                return False
    return True


def enqueue_completed_plans(conn, contract, *, blueprint_id, version_id):
    scope = contract['scope']
    renewal = scope.get('renewal')
    if contract.get('version') != 2 or not renewal:
        return []
    cursor = conn.cursor()
    cursor.execute('SELECT status,compiled_approved_version_id FROM agent_blueprints WHERE id=%s FOR UPDATE', (blueprint_id,))
    blueprint = cursor.fetchone() or {}
    if blueprint.get('status') != 'active' or str(blueprint.get('compiled_approved_version_id')) != str(version_id):
        return []
    from services.operator_async_jobs import create_operator_async_job
    jobs = []
    for business_id in scope['business_ids']:
        for plan_id in scope['plan_ids'][business_id]:
            # The approved lineage contains ancestors too. Renew only its leaf;
            # an existing draft also reserves the continuation until reviewed.
            if existing_successor(cursor, business_id, plan_id):
                continue
            cursor.execute("""SELECT id,scheduled_for FROM contentplanitems WHERE plan_id=%s AND business_id=%s
                AND status<>'skipped' AND scheduled_for IS NOT NULL ORDER BY scheduled_for DESC,id""", (plan_id, business_id))
            items = cursor.fetchall()
            if not items:
                continue
            last_date = items[0]['scheduled_for']
            complete = True
            attempted = False
            for item in (row for row in items if row['scheduled_for'] == last_date):
                cursor.execute('SELECT * FROM social_posts WHERE content_plan_item_id=%s AND business_id=%s AND platform=ANY(%s)',
                               (item['id'], business_id, scope['platforms']))
                posts = cursor.fetchall()
                for post in posts:
                    post['selected_photos'] = _selected_photos(cursor, post)
                    receipts = _json_object(_json_object(_json_object(post.get('metadata_json')).get('staff_handoff')).get('telegram_deliveries'))
                    attempted = attempted or any((receipts.get(user_id) or {}).get('parts') for user_id in scope['recipient_user_ids'])
                    scheduled = post.get('scheduled_for')
                    complete = complete and isinstance(scheduled, datetime) and scheduled.astimezone(ZoneInfo(scope['timezone'])).date() == date.fromisoformat(str(last_date)[:10])
                complete = complete and last_packet_complete(posts, scope['recipient_user_ids'], scope['platforms'])
            if not complete:
                if attempted:
                    queue_handoff_alert(conn, business_id=business_id, event_key=f'last-packet-incomplete:{blueprint_id}:{plan_id}',
                        recipient_user_id=renewal['reviewer_user_id'],
                        message=f'Последний пакет плана на {str(last_date)[:10]} передан не всем получателям или требует сверки. Продолжение не запускается до подтверждённой доставки. Проверьте квитанции в LocalOS.')
                continue
            cursor.execute('SELECT name,address FROM businesses WHERE id=%s', (business_id,))
            business = cursor.fetchone() or {}
            cursor.execute('SELECT DISTINCT platform FROM social_posts WHERE content_plan_id=%s AND business_id=%s', (plan_id,business_id))
            channels = sorted({str(row['platform']) for row in cursor.fetchall()} | set(scope['platforms']))
            key = f'content-network-renewal:{blueprint_id}:{plan_id}'
            job = create_operator_async_job(cursor, user_id=renewal['reviewer_user_id'], action_id=None,
                business_id=business_id, kind=KIND, payload={'blueprint_id': blueprint_id, 'version_id': version_id,
                    'previous_plan_id': plan_id, 'timezone': scope['timezone'], 'channels': channels,
                    'period_days': 30}, idempotency_key=key, stage='Обновляем источники следующего плана', max_attempts=10)
            queue_handoff_alert(conn, business_id=business_id, event_key=key+':last', recipient_user_id=renewal['reviewer_user_id'],
                message=f"{business.get('name')} · {business.get('address')}: это последний пост текущего плана, дата публикации {str(last_date)[:10]}. Материалы переданы всем получателям. Подготовка продолжения поставлена в очередь.")
            jobs.append(job)
    return jobs


def refresh_sources(conn, job):
    """Provider refreshes use existing bounded integrations; freshness is explicit."""
    cursor = conn.cursor()
    state = dict(job.get('result_json') or {})
    sources = state.get('sources') or {}
    if not sources:
        from api.wordstat_api import _refresh_business_wordstat_keywords
        from services.operator_fresh_reviews import refresh_reviews_from_operator
        observed = datetime.now(timezone.utc).isoformat()
        cursor.execute('SAVEPOINT renewal_wordstat')
        try:
            summary = _refresh_business_wordstat_keywords(cursor, str(job['business_id']))
            sources['keywords'] = {'state': 'fresh', 'updated_at': observed, 'summary': summary}
        except Exception:
            cursor.execute('ROLLBACK TO SAVEPOINT renewal_wordstat')
            sources['keywords'] = {'state': 'cached', 'warning': 'Частотности не обновились; использованы последние сохранённые данные'}
        cursor.execute('RELEASE SAVEPOINT renewal_wordstat')
        cursor.execute('SAVEPOINT renewal_reviews')
        try:
            result = refresh_reviews_from_operator(cursor, business_id=str(job['business_id']), user_id=str(job['user_id']))
            sources['reviews'] = {'state': 'pending' if result.get('status') == 'queued' else 'cached',
                'queue_id': result.get('queue_id'), 'requested_at': observed,
                'previous_snapshot': result.get('review_snapshot_before'), 'blocked_reasons': result.get('blocked_reasons')}
        except Exception:
            cursor.execute('ROLLBACK TO SAVEPOINT renewal_reviews')
            sources['reviews'] = {'state': 'cached', 'warning': 'Обновление отзывов недоступно; используем сохранённые отзывы'}
        cursor.execute('RELEASE SAVEPOINT renewal_reviews')
        state['sources'] = sources
        cursor.execute('UPDATE operator_async_jobs SET result_json=%s::jsonb WHERE id=%s AND lease_token=%s',
                       (json.dumps(state, default=str, ensure_ascii=False), job['id'], job['lease_token']))
        conn.commit()
    reviews = sources.get('reviews') or {}
    if reviews.get('state') == 'pending':
        cursor.execute('SELECT status,updated_at FROM parsequeue WHERE id=%s AND business_id=%s', (reviews.get('queue_id'), job['business_id']))
        row = cursor.fetchone() or {}
        if row.get('status') in {'completed', 'done'}:
            reviews.update(state='fresh', updated_at=str(row.get('updated_at')))
        elif row.get('status') in {'pending', 'processing', 'running', 'queued'} and (
                datetime.now(timezone.utc)-datetime.fromisoformat(reviews['requested_at'])).total_seconds() < 300:
            return sources, True
        else:
            reviews.update(state='cached', warning='Свежие отзывы не получены вовремя; использованы последние сохранённые данные')
    cursor.execute('SELECT MAX(updated_at) latest_seen_at,COUNT(*) count FROM externalbusinessreviews WHERE business_id=%s', (job['business_id'],))
    sources['reviews']['cached_snapshot'] = dict(cursor.fetchone() or {})
    cursor.execute('SAVEPOINT renewal_keyword_dates')
    try:
        cursor.execute('SELECT MAX(updated_at) latest_seen_at,COUNT(*) count FROM wordstatkeywordscustom WHERE business_id=%s', (job['business_id'],))
        sources['keywords']['cached_snapshot'] = dict(cursor.fetchone() or {})
    except Exception:
        cursor.execute('ROLLBACK TO SAVEPOINT renewal_keyword_dates')
        sources['keywords']['cached_snapshot'] = {'latest_seen_at': None, 'warning': 'Дата сохранённых частотностей неизвестна'}
    cursor.execute('RELEASE SAVEPOINT renewal_keyword_dates')
    cursor.execute('SELECT id,name,price,updated_at FROM userservices WHERE business_id=%s AND is_active IS TRUE ORDER BY id', (job['business_id'],))
    sources['services'] = {'state': 'current_localos', 'read_at': datetime.now(timezone.utc).isoformat(), 'rows': cursor.fetchall()}
    cursor.execute('SELECT input_snapshot_json FROM contentplans WHERE id=%s AND business_id=%s', (job['payload_json']['previous_plan_id'],job['business_id']))
    previous = (cursor.fetchone() or {}).get('input_snapshot_json') or {}
    sources['services']['previous_rows'] = previous.get('services') or []
    sources['services']['changes'] = service_changes(sources['services']['rows'], sources['services']['previous_rows'])
    return sources, False


def process_job(job):
    from database_manager import DatabaseManager
    from services.compiled_content_program import authorize_contract, contract_for
    from services.content_plan_service import create_generated_content_plan, generate_draft_for_plan_item
    from services.social_post_service import prepare_social_posts_for_items
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        payload = job['payload_json']
        cursor.execute('SELECT b.status,b.business_id anchor_business_id,v.* FROM agent_blueprints b JOIN agent_blueprint_versions v ON v.id=b.compiled_approved_version_id WHERE b.id=%s', (payload['blueprint_id'],))
        version = cursor.fetchone() or {}
        if version.get('status') != 'active' or str(version.get('id')) != str(payload['version_id']):
            raise ValueError('Автоматизация приостановлена или утверждённая версия изменена')
        contract = contract_for(version, str(version['anchor_business_id']))
        authorize_contract(cursor, contract, str(job['user_id']))
        successor = existing_successor(cursor, str(job['business_id']), payload['previous_plan_id'])
        if successor:
            return {'plan_id': str(successor['id']), 'reused_existing_successor': True,
                    'requires_owner_review': True}
        sources, pending = refresh_sources(db.conn, job)
        if pending:
            return {'sources': sources, 'pending_sources': True}
        continuation = {**payload, 'sources': sources}
        plan = create_generated_content_plan(str(job['user_id']), str(job['business_id']), scope_type='business',
            scope_target_id=str(job['business_id']), period_days=30, density='standard', content_mix={'channels': payload['channels']},
            continuation_context=continuation, operator_request_id=str(job['id']),
            editorial_brief='Подготовь профессиональные полезные темы на основе услуг и интересов клиентов. Не повторяй использованные темы. Для Долгоозёрной основной ориентир — ТРК «5 озёр». Не выдумывай цены, факты и контакты.')
        failures = []
        for item in plan['items']:
            try:
                if not str(item.get('draft_text') or '').strip():
                    generate_draft_for_plan_item(str(job['user_id']), str(item['id']), 'ru')
                result = prepare_social_posts_for_items(str(job['user_id']), [str(item['id'])], payload['channels'])
                failures.extend(result.get('failed') or [])
            except Exception:
                failures.append({'id': str(item['id']), 'error': 'Не удалось подготовить тексты; требуется проверка в плане'})
        cursor.execute('SELECT id,metadata_json FROM contentplanitems WHERE plan_id=%s AND business_id=%s', (plan['id'], job['business_id']))
        sources['editorial_examples'] = {'state': 'used_generation_metadata', 'items': [
            {'item_id': str(row['id']), 'source_ids': (_json_object(row.get('metadata_json')).get('content_generation_v2') or {}).get('editorial_pattern_source_ids') or [],
             'voice_profile_version': (_json_object(row.get('metadata_json')).get('content_generation_v2') or {}).get('voice_profile_version')}
            for row in cursor.fetchall()]}
        cursor.execute("UPDATE contentplans SET input_snapshot_json=jsonb_set(COALESCE(input_snapshot_json,'{}'::jsonb),'{source_refresh_snapshot}',%s::jsonb,TRUE) WHERE id=%s AND business_id=%s",
                       (json.dumps(sources, default=str, ensure_ascii=False),plan['id'],job['business_id']))
        warnings = [(value.get('warning') or f"{key}: использованы сохранённые данные")
                    + f". Последнее обновление: {(value.get('cached_snapshot') or {}).get('latest_seen_at') or 'дата неизвестна'}"
                    for key, value in sources.items() if value.get('state') == 'cached']
        href = f"https://localos.pro/dashboard/content?business_id={job['business_id']}&plan_id={plan['id']}"
        message = (f"Продолжение контент-плана подготовлено на проверку: {len(plan['items'])} постов, {plan['period_start']} — {plan['period_end']}.\n{href}\n"
                   + 'Источники: частотности, отзывы, актуальные услуги LocalOS, редакционные ориентиры и память правок.\n'
                   + '\n'.join(warnings) + (f"\nНе завершена подготовка {len(failures)} материалов." if failures else '')
                   + '\nДо утверждения новые материалы сотрудникам не передаются.')
        queue_handoff_alert(db.conn, business_id=str(job['business_id']), event_key=f"renewal-result:{job['id']}",
                            recipient_user_id=str(job['user_id']), message=message)
        db.conn.commit()
        return {'plan_id': plan['id'], 'sources': sources, 'failures': failures, 'requires_owner_review': True}
    finally:
        db.close()


def record_failure(conn, job, error):
    queue_handoff_alert(conn, business_id=str(job['business_id']), event_key=f"renewal-error:{job['id']}",
        recipient_user_id=str(job['user_id']), message=f"Следующий контент-план не готов. Причина: {str(error)[:500] if isinstance(error, (ValueError, PermissionError)) else type(error).__name__}. Проверьте очередь подготовки в LocalOS; материалы Ирине не отправлялись.")
