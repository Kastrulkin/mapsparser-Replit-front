"""Read-only, evidence-bound map workflows for the existing compiled runtime."""
import json
import os
from datetime import datetime, timezone
from urllib.parse import urlsplit

from core.card_platform_policy import POLICY_VERSION, PROVIDERS, provider_rules


TEMPLATE_KEYS = ('maps_initial_setup', 'maps_card_check')
PILOT_BUSINESS_ID = '37dad308-0f37-4397-abe8-25aa472329cc'
LABELS = {'google': 'Google', 'yandex': 'Яндекс', '2gis': '2ГИС'}
FACT_LABELS = {
    'access': 'Данные доступны', 'verified': 'Подтверждение карточки',
    'duplicate': 'Дубли', 'category': 'Категория', 'contacts': 'Контакты',
    'schedule': 'Расписание', 'action_path': 'Путь до обращения',
    'services': 'Услуги', 'prices': 'Цены', 'reviews': 'Отзывы',
    'review_responses': 'Ответы на отзывы', 'photos': 'Фотографии',
    'publications': 'Публикации',
}


def pilot_allowed(business_id):
    configured = os.getenv('MAP_CARD_AGENTS_BUSINESS_IDS', PILOT_BUSINESS_ID)
    return business_id in {item.strip() for item in configured.split(',') if item.strip()}


def template_definitions():
    return [
        {'key': TEMPLATE_KEYS[0], 'version': '1.0.0',
         'name': 'Первичное оформление карт', 'vertical': 'local_seo',
         'business_result': 'Пакет правок Google, Яндекса и 2ГИС: поля, услуги, цены, фотографии и вопросы владельцу. Размещение вручную.',
         'prompt': 'Подготовь первичное оформление карточек Google, Яндекса и 2ГИС по подтверждённым данным бизнеса. Покажи сейчас и предлагается, источники и недостающие сведения. Ничего не публикуй.',
         'required_connections': [], 'risk_level': 'low', 'certification_status': 'beta', 'pilot_required': True},
        {'key': TEMPLATE_KEYS[1], 'version': '1.0.0',
         'name': 'Проверка карточек на картах', 'vertical': 'local_seo',
         'business_result': 'Независимая проверка карточек с источниками, датой и ограничениями. Вручную или по вашему расписанию.',
         'prompt': 'Независимо проверь опубликованные карточки Google, Яндекса и 2ГИС. Сверь контакты, часы, услуги, цены, фотографии и путь обращения. Сохрани доказательства; недоступные данные не считай отсутствующими. Ничего не меняй.',
         'required_connections': [], 'risk_level': 'low', 'certification_status': 'beta', 'pilot_required': True},
    ]


def template_preset(key):
    return {'trigger': 'manual.run', 'sources': ['business_profile', 'services', 'external_reviews'],
            'model_preset': key, 'result_format': 'map_card_report_v1', 'max_items': 30,
            'internal_read_capability': 'maps.cards.read'}


def install_agent(cursor, business_id, user_data, template_key):
    """Shared by the UI and the explicit backfill command. Never activates a task."""
    import uuid
    from services.agent_template_catalog import build_agent_from_template
    from services.agent_version_store import insert_version
    if template_key not in TEMPLATE_KEYS or not pilot_allowed(business_id):
        raise ValueError('Агенты карт не включены для этого бизнеса.')
    cursor.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', (f'map-agent:{business_id}:{template_key}',))
    cursor.execute("""SELECT * FROM agent_blueprints WHERE business_id=%s
        AND metadata_json->>'template_key'=%s ORDER BY created_at LIMIT 1""", (business_id, template_key))
    existing = cursor.fetchone()
    if existing:
        return {'created': False, 'blueprint': dict(existing), 'template_key': template_key}
    bundle = build_agent_from_template(template_key)
    definition, draft = bundle['definition'], bundle['draft']
    user_id = str(user_data.get('user_id') or user_data.get('id') or '')
    blueprint_id = str(uuid.uuid4())
    metadata = {**draft['metadata'], 'template_key': template_key, 'template_version': definition['version'],
                'created_from_template': True, 'is_account_example': False,
                'execution_mode': 'manual', 'execution_mode_confirmed_at': datetime.now(timezone.utc).isoformat(),
                'execution_mode_confirmed_by_user_id': user_id, 'required_connectors': [],
                'template_certification_status': 'beta'}
    cursor.execute("""INSERT INTO agent_blueprints
        (id,business_id,name,category,description,status,created_by_user_id,metadata_json)
        VALUES (%s,%s,%s,%s,%s,'draft',%s,%s::jsonb)""",
                   (blueprint_id, business_id, definition['name'], draft['category'],
                    definition['business_result'], user_id, json.dumps(metadata, ensure_ascii=False)))
    version = insert_version(cursor, blueprint_id, draft['version_payload'], user_data, trusted_compiled=True)
    cursor.execute('SELECT * FROM agent_blueprints WHERE id=%s', (blueprint_id,))
    return {'created': True, 'blueprint': dict(cursor.fetchone()), 'version': version,
            'template_key': template_key, 'template_version': definition['version'], 'next_step': 'review_scenario'}


def selected_providers(value):
    if value in (None, '', 'all'):
        return list(PROVIDERS)
    if value in PROVIDERS:
        return [value]
    raise ValueError('Выберите Google, Яндекс, 2ГИС или все площадки.')


def validate_schedule(template_key, execution_mode):
    if template_key == 'maps_initial_setup' and execution_mode == 'scheduled':
        raise ValueError('Первичное оформление запускается вручную. Для расписания используйте «Проверка карточек на картах».')


def listing_url(provider, value):
    """Only registry links to actual provider hosts; never URLs supplied by a model."""
    parsed = urlsplit(str(value or ''))
    host = (parsed.hostname or '').lower()
    domains = {'google': ('google.com', 'google.ru', 'maps.app.goo.gl', 'goo.gl'),
               'yandex': ('yandex.ru', 'yandex.com', 'yandex.kz'), '2gis': ('2gis.ru', '2gis.com', '2gis.kz')}
    if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port not in (None, 443):
        return ''
    if not any(host == domain or host.endswith('.' + domain) for domain in domains[provider]):
        return ''
    if provider == 'google' and host not in ('maps.app.goo.gl', 'goo.gl', 'maps.google.com', 'maps.google.ru') and not parsed.path.startswith('/maps'):
        return ''
    return str(value)


def _json(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            result = json.loads(value)
            return result if isinstance(result, dict) else {}
        except ValueError:
            return {}
    return {}


def _read_page(cursor, user_id, business_id, url):
    # Reuse the already deployed OpenClaw route; no second scraper or paid fallback.
    try:
        from services.openclaw_website_reader import read_business_website
        source = read_business_website(cursor, user_id, business_id, url)
        if source:
            return {'state': 'observed', 'url': url, 'observed_at': source['fetched_at'],
                    'text': str(source['text'])[:9000], 'provider': source['provider'],
                    'untrusted': True, 'visual_state': 'unknown', 'screenshots': []}
    except (ImportError, ValueError, OSError):
        pass
    return {'state': 'blocked', 'url': url, 'visual_state': 'unknown', 'screenshots': [],
            'reason': 'Живое чтение OpenClaw недоступно для этого бизнеса. Внешний вид не проверен.'}


def collect(cursor, business_id, user_id, providers, *, preview=False):
    from services.card_growth_service import _business, _latest_sources, _provider_state, _table_exists
    business = _business(cursor, business_id)
    if not business:
        raise ValueError('Бизнес не найден.')
    links, parses = _latest_sources(cursor, business_id)
    cards = []
    for provider in providers:
        link, snapshot = links.get(provider), parses.get(provider)
        url = listing_url(provider, (link or {}).get('url')) or listing_url(provider, (snapshot or {}).get('url'))
        state = _provider_state(cursor, business, provider, link, snapshot)
        page = {'state': 'unknown', 'url': url, 'visual_state': 'unknown', 'screenshots': [],
                'reason': 'Ссылка карточки не подтверждена.' if not url else 'Preview без внешнего чтения.'}
        if url and not preview:
            page = _read_page(cursor, user_id, business_id, url)
        checks = []
        for rule in provider_rules(provider):
            fact = state.get('facts', {}).get(rule['fact'], {})
            checks.append({'rule_id': rule['rule_id'], 'field': rule['fact'],
                           'title': FACT_LABELS[rule['fact']], 'state': fact.get('state', 'unknown'),
                           'value': fact.get('value'), 'source': fact.get('source'),
                           'observed_at': fact.get('observed_at'), 'evidence': fact.get('evidence'),
                           'official_url': rule['url'], 'priority': rule['gate']})
        for field, title in (('name', 'Название и вывеска'), ('address', 'Адрес и вход')):
            value = (snapshot or {}).get(field)
            checks.insert(0, {'rule_id': f'{provider}.{field}', 'field': field, 'title': title,
                              'state': 'observed' if value and state.get('source_state') == 'observed' else 'unknown',
                              'value': value, 'source': f'map_snapshot.{provider}',
                              'observed_at': state.get('observed_at'), 'priority': 1,
                              'official_url': 'https://support.google.com/business/answer/3038177' if provider == 'google' else provider_rules(provider)[0]['url']})
        cards.append({'provider': provider, 'label': LABELS[provider], 'url': url,
                      'checks': checks, 'public_page': page,
                      'status': 'insufficient_data',
                      'visual_note': 'Внешний вид не проверен: текущий маршрут возвращает текст без скриншота.'})
    if _table_exists(cursor, 'agent_artifacts'):
        from services.map_card_initial_audit import items, apply_saved_audits
        apply_saved_audits(cards, items(cursor, business_id))
    cursor.execute('SELECT id, name, description, price FROM userservices WHERE business_id=%s AND COALESCE(is_active, TRUE)=TRUE ORDER BY name LIMIT 100', (business_id,))
    services = [dict(row) for row in cursor.fetchall() or []]
    website = str(business.get('website') or '')
    website_source = {'state': 'unknown', 'url': website}
    if website and not preview:
        website_source = _read_page(cursor, user_id, business_id, website)
    photos = []
    if _table_exists(cursor, 'photo_assets'):
        from services.media_library_scope import PHOTO_LIBRARY_SCOPE_SQL, PHOTO_PUBLICATION_SQL
        cursor.execute(f'''SELECT id, original_url, category, quality_score, updated_at FROM photo_assets
            WHERE business_id IN ({PHOTO_LIBRARY_SCOPE_SQL}) AND {PHOTO_PUBLICATION_SQL}
              AND metadata_json->>'disk_import_available' IS DISTINCT FROM 'false'
            ORDER BY quality_score DESC, updated_at DESC LIMIT 30''', (business_id,))
        photos = [dict(row) for row in cursor.fetchall() or []]
    return {'schema': 'map_card_sources_v1', 'business_id': business_id,
            'business': business, 'services': services, 'photos': photos, 'cards': cards,
            'official_website': website_source,
            'observed_at': datetime.now(timezone.utc).isoformat(), 'policy_version': POLICY_VERSION,
            'source_scope': 'confirmed_business_links_only', 'provider_write_performed': False,
            'external_dispatch_performed': False, 'preview': preview}


def handle_read(envelope, user_data):
    from database_manager import DatabaseManager
    from core.auth_helpers import verify_business_access
    business_id = str(envelope.get('tenant_id') or '')
    actor = envelope.get('actor') or {}
    user_id = str(actor.get('user_id') or actor.get('id') or user_data.get('user_id') or user_data.get('id') or '')
    if not pilot_allowed(business_id):
        raise PermissionError('Агенты карт пока доступны только в пилотных аккаунтах.')
    payload = envelope.get('payload') or {}
    if payload.get('policy_version') != POLICY_VERSION:
        raise ValueError('Правила проверки обновились. Создайте и утвердите новую версию агента.')
    providers = selected_providers(payload.get('platform'))
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        allowed, _owner = verify_business_access(cursor, business_id, user_data)
        if not allowed:
            raise PermissionError('Нет доступа к карточкам этого бизнеса.')
        preview = payload.get('preview_mode') is True or payload.get('external_side_effects_allowed') is False
        result = collect(cursor, business_id, user_id, providers, preview=preview)
        result = json.loads(json.dumps(result, ensure_ascii=False, default=str))
        return {'result': {'status': 'read_completed', **result}, 'billing': {'total_tokens': 0, 'cost': 0.0}}
    finally:
        db.close()


def preparation_fields(sources, card):
    business = sources.get('business') or {}
    current = {check['field']: check.get('value') for check in card['checks']}
    fields = []
    for key, title, target in (('name', 'Название', business.get('name')),
                               ('address', 'Адрес', business.get('address')),
                               ('phone', 'Телефон', business.get('phone')),
                               ('website', 'Сайт', business.get('website')),
                               ('schedule', 'Расписание', business.get('working_hours'))):
        before = current.get(key)
        if key in ('phone', 'website'):
            contacts = current.get('contacts') or {}
            before = contacts.get(key) if isinstance(contacts, dict) else None
        fields.append({'field': key, 'title': title, 'before': before, 'proposed': target,
                       'status': 'needs_review' if target else 'needs_information',
                       'source': 'business_profile',
                       'reason': 'Сверить с владельцем перед размещением.' if target else 'Уточнить у владельца.'})
    return fields


def finalize_report(sources, model_result, previous=None, *, preparation=False, preview=False, model_state=None):
    """AI cannot turn cached metrics or a text fetch into a visual pass."""
    model_state = model_state or {}
    ai_blocked = not preview and bool(model_state) and model_state.get('status') != 'completed'
    summary = 'Пакет оформления подготовлен для проверки владельцем.' if preparation else 'Проверка сохранена. Внешний вид требует отдельного подтверждения.'
    if ai_blocked:
        reason = ('Нет доступных токенов для выбранной модели (HTTP 402).'
                  if model_state.get('fallback_reason') == 'gigachat_payment_required'
                  else 'AI-провайдер недоступен или ответ не прошёл проверку.')
        if model_state.get('fallback_reason') == 'gigachat_budget_exceeded':
            from services.map_card_ai_preparation import map_preparation_failure_message
            reason = map_preparation_failure_message('gigachat_budget_exceeded')
        summary = 'Данные собраны. AI-подготовка не выполнена. ' + reason
        if preparation:
            summary += ' Описание и новые услуги не созданы.'
    cards = []
    old = {item['provider']: item for item in (previous or {}).get('cards', [])}
    for source_card in sources.get('cards', []):
        card = dict(source_card)
        page = card.get('public_page') or {}
        card['status'] = 'insufficient_data'
        card['visual_state'] = 'unknown'
        card['public_read_state'] = page.get('state', 'unknown')
        card['observed_at'] = page.get('observed_at')
        card['changes'] = []
        before = {item['field']: item for item in old.get(card['provider'], {}).get('checks', [])}
        for check in card.get('checks', []):
            prior = before.get(check['field'])
            if prior and check['state'] == 'observed' and prior.get('state') == 'observed' and prior.get('value') != check.get('value'):
                card['changes'].append({'title': check.get('title') or FACT_LABELS.get(check['field'], check['field']), 'before': prior.get('value'), 'after': check.get('value'),
                                        'source': check.get('source'), 'observed_at': check.get('observed_at')})
        if preparation:
            card['fields'] = preparation_fields(sources, card)
        # The full source body is an internal model input, not a public result.
        card.pop('public_page', None)
        cards.append(card)
    return {'schema': 'map_card_report_v1', 'kind': 'preparation' if preparation else 'check',
            'status': 'preview_only' if preview else 'blocked' if ai_blocked else 'prepared_for_review' if preparation else 'insufficient_data',
            'summary': summary,
            'ai_preparation': {'status': model_state.get('status', 'unknown'),
                               'model': model_state.get('model', ''),
                               'reason': model_state.get('fallback_reason', '')},
            'cards': cards, 'services': sources.get('services', []) if preparation else [],
            'photos': sources.get('photos', []) if preparation else [],
            'photo_brief': ['Вход и вывеска', 'Интерьер', 'Команда', 'Процесс работы', 'Результаты и примеры работ'] if preparation else [],
            'editorial': model_result, 'policy_version': sources.get('policy_version'),
            'observed_at': sources.get('observed_at'), 'previous_report_available': bool(previous),
            'manual_publication_required': preparation, 'provider_write_performed': False,
            'preview': preview, 'external_dispatch_performed': False}


def build_final_artifact(cursor, run, step):
    from services.agent_blueprint_workspace import _latest_artifact_payload, _run_capability_result
    sources = _run_capability_result(cursor, str(run['id']), 'read_map_cards')
    # The runner stores the action envelope around the provider result.
    if isinstance(sources.get('result'), dict):
        sources = sources['result']
    draft = _latest_artifact_payload(cursor, str(run['id']), 'agent_output_draft')
    previous = None
    cursor.execute("""SELECT a.payload_json FROM agent_artifacts a JOIN agent_runs r ON r.id=a.run_id
        WHERE r.business_id=%s AND r.blueprint_id=%s AND r.id<>%s AND r.status='completed'
          AND a.artifact_type='agent_final_result'
        ORDER BY a.created_at DESC LIMIT 10""", (run['business_id'], run['blueprint_id'], run['id']))
    for row in cursor.fetchall() or []:
        candidate = _json(row.get('payload_json')).get('result') or {}
        if candidate.get('schema') == 'map_card_report_v1' and not candidate.get('preview'):
            previous = candidate
            break
    run_input = _json(run.get('input_json'))
    if not run_input.get('preview_mode') and (step.get('payload') or {}).get('map_mode') == 'preparation':
        from services.map_card_initial_audit import apply_saved_audits, items
        apply_saved_audits(sources.get('cards', []), items(cursor, str(run['business_id'])))
    report = finalize_report(sources, draft.get('result') or {}, previous,
                             preparation=(step.get('payload') or {}).get('map_mode') == 'preparation',
                             preview=run_input.get('preview_mode') is True,
                             model_state=draft.get('bounded_model'))
    return {'status': 'saved', 'result': report, 'external_dispatch_performed': False}
