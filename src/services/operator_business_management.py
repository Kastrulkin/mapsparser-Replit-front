"""Registry-driven profile and team tools for both Web and Telegram Operator."""
import re
import sys
from services import business_chat_changes, business_team_management
from services.business_settings_registry import patch_schema, public_registry
from services.business_permissions import load_actor, require_permission


def preview(cursor, business_id, user_id, arguments, *, kind, channel, message, orchestrator=None, session=None):
    from services.operator_core import _prepare_registered_capability_approval
    service = business_team_management if kind == 'team' else business_chat_changes
    capability = 'team.manage' if kind == 'team' else 'settings.profile'
    try:
        if kind == 'settings':
            for request in arguments.get('changes') or []:
                patch = request.get('patch') or {}
                explicit_utc = re.search(r'\b(?:установ\w*|укаж\w*|измени\w*|постав\w*|простав\w*|сохран\w*)\b[^\n]*\bUTC\b|\b(?:часовой пояс|timezone)\s*[:=]\s*UTC\b|\bна\s+UTC\b',message,re.I)
                if patch.get('timezone') == 'UTC' and re.search(r'использован\s+UTC', message, re.I) and not explicit_utc:
                    raise ValueError('UTC из предупреждения не является новым часовым поясом. Укажите нужный пояс или город.')
        payload = service.prepare(cursor, business_id, user_id, arguments, session=session)
    except PermissionError:
        error = sys.exception()
        return {'status': 'blocked', 'chat_response': str(error), 'external_writes_performed': False}
    except ValueError:
        error = sys.exception()
        return {'status': 'clarification_required', 'chat_response': str(error), 'external_writes_performed': False}
    summary = service.preview_text(payload)
    prepared = _prepare_registered_capability_approval(cursor=cursor, capability=capability, tool_name=capability,
        business_id=business_id, user_id=user_id, channel=channel, message=summary, payload=payload, orchestrator=orchestrator)
    if prepared.get('status') == 'approval_required':
        prepared['chat_response'] = summary
        prepared['preview'] = payload
        prepared['approval']['summary'] = summary
    return prepared


def tools(cursor, business_id, user_id, message, channel, orchestrator=None, session=None):
    def read(arguments):
        user = load_actor(cursor, user_id)
        if session:
            user.update({key: session[key] for key in ('session_kind', 'scope_business_id') if key in session})
        target = business_chat_changes.resolve_target(cursor, user, arguments.get('business'), business_id)
        require_permission(cursor, target, user, 'business.read')
        return {'status': 'completed', 'profile': business_chat_changes.read_profile(cursor, target),
                'fields': public_registry(), 'external_writes_performed': False}

    def list_targets(arguments):
        user = load_actor(cursor, user_id)
        if session:
            user.update({key: session[key] for key in ('session_kind', 'scope_business_id') if key in session})
        require_permission(cursor, business_id, user, 'business.read')
        query = arguments.get('query')
        if query is not None and not isinstance(query,str):
            raise ValueError('Укажите название для поиска.')
        query = (query or '').strip()
        selected = business_chat_changes.selected_business(cursor,user,business_id)
        items = business_chat_changes.search_businesses(cursor,user,query)
        has_more = len(items) > 50
        items = items[:50]
        if not query and selected and not any(item['id'] == selected['id'] for item in items):
            has_more = has_more or len(items) == 50
            items = items[:49]
            items.insert(0,selected)
        return {'status': 'completed', 'businesses': items, 'selected_business':selected,
                'query':query, 'has_more':has_more, 'external_writes_performed': False}

    def list_team(_arguments):
        from services.business_member_directory import list_business_members
        require_permission(cursor, business_id, load_actor(cursor, user_id), 'business.read')
        target=business_chat_changes.resolve_target(cursor,load_actor(cursor,user_id),_arguments.get('business'),business_id)
        require_permission(cursor,target,load_actor(cursor,user_id),'business.read')
        return {'status': 'completed', 'members': list_business_members(cursor, target), 'roles': business_team_management.role_options(), 'external_writes_performed': False}

    return [
        {'name': 'settings.get_profile', 'capability': 'settings.read', 'title': 'Настройки бизнеса',
         'description': 'Читает профиль и единый реестр изменяемых полей. Без business читает выбранный филиал. Название его сети также означает выбранный филиал; для всей сети нужен явный запрос. Другой бизнес указывай только по поручению пользователя. Не требуй наличия бизнеса в предварительном списке: этот инструмент ищет напрямую.',
         'input_schema': {'type': 'object', 'properties': {'business': {'type': 'string'}}}, 'risk_class': 'read_only',
         'approval_required': False, 'execute': read},
        {'name': 'settings.list_businesses', 'capability': 'settings.read', 'title': 'Бизнесы для изменения настроек',
         'description': 'Ищет доступные бизнесы и сети напрямую в БД. Если пользователь назвал бизнес, передай его название в query. selected_business — текущий выбранный филиал; название его сети означает этот филиал, а не отсутствие бизнеса. Список ограничен 50 совпадениями: has_more=true требует более точного поиска. Не выбирай первый при неоднозначном имени.',
         'input_schema': {'type': 'object', 'properties': {'query': {'type':'string','description':'Название бизнеса или сети из запроса пользователя'}}}, 'risk_class': 'read_only', 'approval_required': False, 'execute': list_targets},
        {'name': 'settings.prepare_changes', 'capability': 'settings.profile', 'title': 'Изменить настройки бизнеса',
         'description': 'Готовит подтверждение настроек одного или нескольких явно названных бизнесов: название, адрес, город, сайт, контакты, график, валюта и часовой пояс. Реестр полей доступен через settings.get_profile. Значения извлекай из поручения пользователя. UTC из предупреждения «использован UTC» не сохраняй. Для пояса Москва=Europe/Moscow, Дубай=Asia/Dubai, Орхус=Europe/Copenhagen. Не меняет внешние карты. Уточни недостающие сведения. Не обещай выполнение до подтверждения.',
         'input_schema': {'type': 'object', 'additionalProperties': False, 'required': ['changes'], 'properties': {
             'changes': {'type': 'array', 'minItems': 1, 'maxItems': 20, 'items': {'type': 'object', 'additionalProperties': False,
                 'required': ['patch'], 'properties': {'business': {'type': 'string', 'description': 'Точное имя или ID. Пропуск означает выбранный бизнес.'}, 'patch': patch_schema()}}}}},
         'risk_class': 'owner_profile_write', 'approval_required': True, 'deterministic_preparation_response': True,
         'prepare_approval': lambda arguments: preview(cursor,business_id,user_id,arguments,kind='settings',channel=channel,message=message,orchestrator=orchestrator,session=session)},
        {'name': 'settings.list_users', 'capability': 'team.read', 'title': 'Пользователи бизнеса',
         'description': 'Читает владельца и сотрудников выбранного или явно названного бизнеса (business), роли и доступ через сеть. При поиске человека в филиале передай название филиала. Если человека нет, не создавай нового вместо изменения доступа.',
         'input_schema': {'type': 'object', 'properties': {'business':{'type':'string'}}}, 'risk_class': 'read_only', 'approval_required': False, 'execute': list_team},
        {'name': 'settings.prepare_user', 'capability': 'team.manage', 'title': 'Добавить сотрудника или изменить роль',
         'description': 'Готовит подтверждение добавления сотрудника, изменения его роли или снятия доступа (operation=remove) только в названной области. Для remove существующий email, role не нужен. Остальные филиалы сохраняют доступ. Сначала найди человека через list_users с business явно названного филиала. Только владелец. Нужны email, роль и область доступа. admin=администратор, master=мастер, viewer=наблюдатель. scope=network только по явному запросу на всю сеть выбранного бизнеса, иначе конкретные бизнесы. Отправку приглашения включай только по явному поручению; покажи её отдельно. Заблокированные аккаунты не активирует, владельца не меняет.',
         'input_schema': {'type': 'object', 'additionalProperties': False, 'required': ['email','scope','send_invitation'], 'properties': {
             'operation':{'type':'string','enum':['grant','remove']},'email': {'type': 'string'}, 'name': {'type': 'string'}, 'role': {'type': 'string', 'enum': list(business_team_management.ASSIGNABLE_ROLES)},
             'scope': {'type': 'string', 'enum': ['business','network']}, 'businesses': {'type': 'array', 'maxItems': 20, 'items': {'type': 'string'}}, 'send_invitation': {'type': 'boolean'}}},
         'risk_class': 'access_change', 'approval_required': True, 'deterministic_preparation_response': True,
         'prepare_approval': lambda arguments: preview(cursor,business_id,user_id,arguments,kind='team',channel=channel,message=message,orchestrator=orchestrator,session=session)},
    ]


def matches(message):
    # Intent routing only. Fields and values are handled by the typed registry tools.
    if re.match(r'\s*(?:если|например|допустим|как\b)', message, re.I):
        return False
    field_words = '|'.join(re.escape(alias) for field in public_registry() for alias in [field['label'], *field['aliases']])
    settings = bool(re.search(field_words, message, re.I))
    team = bool(re.search(r'пользоват|сотрудник|администратор|мастер|наблюдател', message, re.I))
    operation = bool(re.search(r'измени|поменя|обнови|сохран|укаж|установ|простав|постав|добав|приглас|переех|покажи|список', message, re.I))
    unrelated = bool(re.search(r'\bпост(?:а|ы|ов|у|ом|е)?\b|контент|отзыв|новост|прайс|услуг', message, re.I))
    return operation and (settings or team) and not unrelated


def timezone_lines(message):
    """Recognize explicit per-business assignments while ignoring warning values."""
    if not re.search(r'простав|установ|поменя|измени|укаж', message, re.I) or not re.search(r'часов.*пояс', message, re.I):
        return None
    from services.business_input_settings import parse_settings, city_timezone
    changes = []
    for line in message.splitlines():
        if ':' not in line:
            continue
        reference, text = line.split(':', 1)
        if re.search(r'установ|измени|поменя|сохран|настро|часов.*пояс|^\s*город\b',reference,re.I):
            continue
        if re.search(r'не задан|неверен|использован', text, re.I):
            if ' - ' not in text:
                changes.append({'business':reference.strip(),'patch':{}})
                continue
            text = text.rsplit(' - ', 1)[1]
        parsed = parse_settings(text)
        # Explicit city takes precedence over a copied offset/UTC fragment.
        zone = city_timezone(parsed.get('city')) or parsed.get('timezone')
        changes.append({'business':reference.strip(),'patch':{'timezone':zone} if zone else {}})
    return {'changes': changes} if changes else None
