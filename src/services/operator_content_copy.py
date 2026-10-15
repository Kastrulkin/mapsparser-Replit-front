"""Copy explicitly selected saved content through existing post writers, without AI."""
import re
import json
from datetime import timedelta

from services import social_post_service, media_intelligence

UUID_PATTERN = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'


def require_business_write(cursor, user_id, business_id):
    from core.auth_helpers import verify_business_write_access
    cursor.execute('SELECT COALESCE(is_superadmin,FALSE) superadmin FROM users WHERE id=%s', (user_id,))
    actor = cursor.fetchone() or {}
    allowed, _ = verify_business_write_access(cursor, business_id,
        {'user_id': user_id, 'is_superadmin': bool(actor.get('superadmin'))})
    if not allowed:
        raise PermissionError('Нет прав на изменение выбранного бизнеса.')


def load_plan_for_write(cursor, user_id, plan_id):
    plan = social_post_service._load_plan_for_user(cursor, user_id, plan_id)
    require_business_write(cursor, user_id, str(plan.get('business_id') or ''))
    return plan


def load_item_for_write(cursor, user_id, item_id):
    item = social_post_service._load_plan_item_for_user(cursor, user_id, item_id)
    require_business_write(cursor, user_id, str(item.get('business_id') or ''))
    return item


def require_write_request(message):
    if re.search(r'только\s+чтени[ея]|read[\s-]+only|ничего\s+не\s+(?:меня|измен|сохраня|созда)|не\s+(?:скопир|копир|подключ)', str(message or ''), re.I):
        raise ValueError('В режиме только чтения версии и подключения не изменяются.')


def matches(message):
    text = str(message or '').casefold()
    return ('copy_text_to_channels=true' in text or
            (re.search(r'скопир|дословн', text) and 'текст' in text
             and re.search(r'готов|сохран[её]н', text)
             and re.search(r'верси|канал|площад', text)))


def connects_successor(message):
    return bool(re.search(r'подключи\w*.{0,100}(?:план|продолжение)', str(message or ''), re.I)
                and re.search(r'продолжени\w*', str(message or ''), re.I)
                and re.search(r'автоматизаци\w*', str(message or ''), re.I))


def connect_saved_successor(cursor, *, business_id, user_id, message):
    require_write_request(message)
    from services.compiled_content_program import contract_for, authorize_contract
    from services.content_network_renewal import approved_plan_ids, approve_successor
    patterns = {'plan': r'план(?:а)?', 'previous': r'предыдущ(?:ий|его)\s+план(?:а)?',
                'blueprint': r'автоматизаци(?:я|и|ю)'}
    selection = {}
    for key, pattern in patterns.items():
        found = re.search(pattern + r'\s*[:=]?\s*(' + UUID_PATTERN + ')', str(message or ''), re.I)
        if not found:
            raise ValueError('Укажите ID нового плана, предыдущего плана и автоматизации.')
        selection[key] = found.group(1).lower()
    cursor.execute('SELECT b.business_id anchor_business_id,v.* FROM agent_blueprints b JOIN agent_blueprint_versions v ON v.id=b.compiled_approved_version_id WHERE b.id=%s', (selection['blueprint'],))
    version = cursor.fetchone() or {}
    contract = contract_for(version, str(version.get('anchor_business_id') or ''))
    authorize_contract(cursor, contract, user_id)
    scope = contract['scope']
    if (business_id not in scope.get('business_ids', []) or
            (scope.get('renewal') or {}).get('reviewer_user_id') != user_id):
        raise PermissionError('Продолжение подключает выбранный владелец в разрешённом филиале.')
    if selection['previous'] not in approved_plan_ids(cursor, scope, business_id, selection['blueprint'], str(version['id'])):
        raise ValueError('Предыдущий план не подключён к этой автоматизации.')
    if selection['plan'] == selection['previous']:
        raise ValueError('Выберите новый план.')
    plan = load_plan_for_write(cursor, user_id, selection['plan'])
    if str(plan.get('business_id')) != business_id or plan.get('plan_status') == 'archived':
        raise PermissionError('План недоступен в выбранном филиале.')
    cursor.execute('SELECT MIN(scheduled_for) first_date,MAX(scheduled_for) last_date FROM contentplanitems WHERE plan_id=%s AND business_id=%s', (selection['plan'], business_id))
    dates = cursor.fetchone() or {}
    cursor.execute('SELECT MAX(scheduled_for) last_date FROM contentplanitems WHERE plan_id=%s AND business_id=%s', (selection['previous'], business_id))
    previous = cursor.fetchone() or {}
    if not dates.get('first_date') or not previous.get('last_date') or dates['first_date'] <= previous['last_date']:
        raise ValueError('Продолжение должно идти после предыдущего плана.')
    period_end = dates['first_date'] + timedelta(days=int(plan.get('period_days') or 30) - 1)
    if dates['last_date'] > period_end:
        raise ValueError('Даты постов выходят за период продолжения.')
    generated = dict(plan.get('generated_plan_json') or {})
    metadata = dict(generated.get('meta') or {})
    if metadata.get('previous_plan_id') not in {None, selection['previous']} or metadata.get('network_automation_id') not in {None, selection['blueprint']}:
        raise ValueError('План уже связан с другим продолжением.')
    metadata.update(previous_plan_id=selection['previous'], network_automation_id=selection['blueprint'])
    generated['meta'] = metadata
    cursor.execute('SAVEPOINT connect_content_successor')
    try:
        cursor.execute('UPDATE contentplans SET generated_plan_json=%s::jsonb,period_start=%s,period_end=%s,updated_at=NOW() WHERE id=%s',
            (json.dumps(generated, ensure_ascii=False), dates['first_date'], period_end, selection['plan']))
        result = approve_successor(cursor.connection, blueprint_id=selection['blueprint'], plan_id=selection['plan'], user_id=user_id)
    except Exception:
        cursor.execute('ROLLBACK TO SAVEPOINT connect_content_successor')
        raise
    cursor.execute('RELEASE SAVEPOINT connect_content_successor')
    return {'status': 'completed', 'capability': 'content.item.edit', 'successor': result,
        'external_writes_performed': False, 'charged_credits': 0,
        'chat_response': 'Продолжение проверено и подключено к той же автоматизации. Филиалы, получатели и время не менялись. Расписание не включалось; сообщений и публикаций нет.',
        'result_ref': {'href': '/dashboard/content?business_id=' + business_id + '&plan_id=' + selection['plan'],
                       'label': 'Открыть продолжение', 'entity_id': selection['plan'], 'entity_type': 'content_plan'}}


def copy_saved_content(cursor, *, business_id, user_id, message, request_id):
    text = str(message or '')
    require_write_request(message)
    plan_match = re.search(r'(?:в\s+плане|план(?:а|у)?|plan_id)\s*[:=]?\s*(' + UUID_PATTERN + ')', text, re.I)
    item_match = re.search(r'(?:пост(?:а)?|item_id)\s*[:=]?\s*(' + UUID_PATTERN + ')', text, re.I)
    whole_plan = bool(re.search(r'все\s+посты|всех\s+постов', text, re.I))
    if not plan_match or (not item_match and not whole_plan):
        raise ValueError('Укажите ссылку или ID плана и поста; для всего плана напишите «все посты».')
    plan_id = plan_match.group(1).lower()
    plan = load_plan_for_write(cursor, user_id, plan_id)
    if str(plan.get('business_id')) != business_id:
        raise PermissionError('План относится к другому выбранному бизнесу.')
    if plan.get('plan_status') == 'archived':
        raise ValueError('Архивный план не изменяется.')
    item_id = item_match.group(1).lower() if item_match else None
    cursor.execute('''SELECT id FROM contentplanitems WHERE plan_id=%s AND business_id=%s
        AND (%s IS NULL OR id=%s) ORDER BY scheduled_for,id LIMIT 101 FOR UPDATE''',
        (plan_id, business_id, item_id, item_id))
    identifiers = [str(row['id']) for row in cursor.fetchall()]
    if not identifiers or len(identifiers) > 100:
        raise ValueError('Нужен план с 1–100 доступными постами.')
    available_photos = {str(asset['id']) for asset in media_intelligence.list_photo_assets(cursor, business_id)}
    prepared = []
    for identifier in identifiers:
        item = load_item_for_write(cursor, user_id, identifier)
        if str(item.get('business_id')) != business_id or str(item.get('plan_id')) != plan_id:
            raise PermissionError('Пост недоступен в выбранном плане.')
        if item.get('status') not in {'planned', 'draft_generated', 'edited'}:
            raise ValueError('Можно копировать только неопубликованные черновики.')
        body = str(item.get('draft_text') or '').strip()
        if not body:
            raise ValueError('Сначала сохраните текст каждого выбранного поста.')
        metadata = item.get('metadata_json') or {}
        generated = plan.get('generated_plan_json') or {}
        channels = (metadata.get('selected_channels') or generated.get('selected_channels')
                    or (generated.get('meta') or {}).get('selected_channels') or [])
        if not channels or any(channel not in social_post_service.CONTENT_PUBLICATION_PLATFORMS for channel in channels):
            raise ValueError('Выберите поддерживаемые площадки.')
        photo = str(metadata.get('selected_photo_asset_id') or '')
        if photo and photo not in available_photos:
            raise ValueError('Выбранное фото недоступно; выберите другое в медиатеке.')
        prepared.append((item, body, list(dict.fromkeys(channels)), photo))
    created = 0
    existing_count = 0
    for item, body, channels, photo in prepared:
        existing = social_post_service._existing_social_posts_for_item(cursor, str(item['id']))
        for channel in channels:
            if channel in existing:
                existing_count += 1
                continue
            post = social_post_service._upsert_social_post(cursor, user_id, item, channel, body,
                {'text': body, 'metadata': {'manually_edited': True, 'variant_source': 'user_supplied',
                    'operator_source_request_id': request_id}})
            if photo:
                cursor.execute('UPDATE social_posts SET media_json=jsonb_build_array(jsonb_build_object(\'photo_asset_id\',%s::text)) WHERE id=%s',
                    (photo, post['id']))
            created += 1
    return {'status': 'completed', 'capability': 'content.item.edit', 'created_versions': created,
        'existing_versions_preserved': existing_count, 'items_count': len(prepared),
        'external_writes_performed': False, 'charged_credits': 0,
        'chat_response': f'Готовый текст скопирован без генерации. Постов: {len(prepared)}, новых версий: {created}, сохранённых без изменений: {existing_count}. Фото сохранены. Ничего не опубликовано и не отправлено; расписание не включалось.',
        'result_ref': {'href': '/dashboard/content?business_id=' + business_id + '&plan_id=' + plan_id,
                       'label': 'Открыть контент-план', 'entity_id': plan_id, 'entity_type': 'content_plan'}}
