"""Control the existing bot handoff preferences from the common Operator."""
from datetime import datetime
from services.outreach_ai_authorization import digest
from services.operator_agent_management import _authorized_actor


def normalize_changes(raw):
    if not isinstance(raw,dict) or not raw:
        raise ValueError('handoff_changes_required')
    clean={}
    for key,value in raw.items():
        if key=='content_publications':
            if type(value) is not bool:raise ValueError('invalid_enabled')
            clean[key]=value
        elif key=='content_publications_lead_days':
            if type(value) is not int or not 0<=value<=7:raise ValueError('invalid_lead_days')
            clean[key]=value
        elif key=='content_publications_time':
            if not isinstance(value,str):raise ValueError('invalid_time')
            clean[key]=datetime.strptime(value,'%H:%M').strftime('%H:%M')
        elif key=='content_publications_platforms':
            if not isinstance(value,list) or not value or len(value)>3 or any(p not in ('vk','telegram','max') for p in value):
                raise ValueError('invalid_platforms')
            clean[key]=sorted(set(value))
        else:raise ValueError('unsupported_setting')
    return clean


def _binding(cursor, business_id, recipient_id=''):
    scope_key = 'business:' + business_id
    cursor.execute("""SELECT p.user_id,p.telegram_id,p.notification_preferences_json,u.name,u.is_active
        FROM telegramcontrolpreferences p JOIN users u ON u.id=p.user_id
        WHERE p.notification_preferences_json ? %s AND NULLIF(p.telegram_id::text,'') IS NOT NULL
          AND (%s='' OR p.user_id=%s) ORDER BY p.user_id""",(scope_key,recipient_id,recipient_id))
    rows = [dict(row) for row in cursor.fetchall()]
    if len(rows) != 1:
        return None, [{'recipient_user_id':row['user_id'],'name':row.get('name')} for row in rows]
    row=rows[0]
    if not row.get('is_active'):
        raise PermissionError('handoff_recipient_inactive')
    from services.operator_audio import authorize_actor
    authorize_actor(cursor,row['user_id'],business_id,check_subscription=False)
    settings=(row.get('notification_preferences_json') or {}).get(scope_key) or {}
    from services.business_input_settings import resolve
    zone=resolve(cursor,business_id).get('timezone')
    revision=digest({'timezone':zone,'business_id':business_id,'recipient_user_id':row['user_id'],
                     'telegram_id':str(row['telegram_id']),'settings':settings})
    return {**row,'settings':settings,'revision':revision,'timezone':zone},[]


def operator_task(cursor, *, business_id, user_id, arguments, actor_context=None):
    # Chat and menu prepare the same blueprint; do not enable legacy bot
    # preferences as a substitute for a compiled program.
    from services.operator_agent_management import configure, prepare_lifecycle
    operation = str(arguments.get('operation') or 'status')
    if operation in {'compile', 'preview', 'approve', 'run'}:
        from services.operator_compiled_content import prepare
        return prepare(cursor, business_id=business_id, user_id=user_id,
            arguments=arguments, actor_context=actor_context)
    if operation in {'pause', 'resume'}:
        return prepare_lifecycle(cursor, business_id=business_id, user_id=user_id,
            arguments={**arguments, 'operation': operation}, actor_context=actor_context)
    if operation == 'status':
        return configure(cursor, business_id=business_id, user_id=user_id,
            arguments={**arguments, 'operation': 'status' if arguments.get('blueprint_id') else 'list'}, actor_context=actor_context)
    if operation == 'configure':
        settings = arguments.get('settings') or {}
        if settings.get('time', '10:00') != '10:00' or settings.get('lead_days', 1) != 1 or set(settings.get('platforms', ['telegram','vk','max'])) != {'telegram','vk','max'}:
            return {'status':'clarification_required','chat_response':'Для пилота поддержаны Telegram, VK и MAX, за день до публикации в 10:00. Другие условия не сохранены.'}
        recipient = str(arguments.get('recipient_user_id') or user_id)
        if recipient != user_id:
            return {'status':'clarification_required','chat_response':'Тест выполняется только на вашем подключённом Telegram. Переключение получателя требует отдельной проверки и утверждения.'}
        return configure(cursor, business_id=business_id, user_id=user_id, actor_context=actor_context,
            arguments={'operation':'create', 'name':'Передача готовых публикаций через бот',
                'selected_provider_routes': {'telegram_delivery': {'provider': 'native_localos'}},
                'accepted_provider_routes': True,
                'description':'За день до публикации в 10:00 отправлять через подключённого бота готовые версии постов для Telegram, VK и MAX с выбранным фото. Получатель — мой подключённый аккаунт. Регулярный запуск оставить на паузе.'})
    return {'status':'blocked','blocked_reasons':['unsupported_operation']}


def legacy_operator_task(cursor, *, business_id, user_id, arguments, actor_context=None):
    actor=_authorized_actor(cursor,business_id=business_id,user_id=user_id,actor_context=actor_context)
    if not actor:
        return {'status':'blocked','blocked_reasons':['access_denied']}
    try:
        binding,choices=_binding(cursor,business_id,str(arguments.get('recipient_user_id') or ''))
        if not binding:
            return {'status':'clarification_required','recipients':choices,
                    'chat_response':'Уточните существующую привязку получателя к боту для выбранного бизнеса. Получатель автоматически не заменяется.'}
        if not actor.get('is_superadmin') and str(binding['user_id']) != user_id:
            return {'status':'blocked','blocked_reasons':['handoff_recipient_management_denied']}
        zone=binding['timezone']
        operation=str(arguments.get('operation') or 'status')
        current=binding['settings']
        if operation=='status':
            return {'status':'completed','business_id':business_id,'recipient_user_id':binding['user_id'],
                    'recipient_name':binding.get('name'),'settings':current,'revision':binding['revision'],
                    'timezone':zone,'state':'active' if current.get('content_publications') else 'paused',
                    'chat_response':'Это существующая передача подготовленных публикаций через подключённого бота.'}
        if operation not in {'configure','pause','resume'}:
            raise ValueError('unsupported_operation')
        changes={}
        if operation in {'pause','resume'}:
            changes['content_publications']=operation=='resume'
        if operation=='configure':
            supplied=arguments.get('settings') or {}
            if not isinstance(supplied,dict):raise ValueError('invalid_settings')
            mapping={'lead_days':'content_publications_lead_days','time':'content_publications_time',
                     'platforms':'content_publications_platforms','enabled':'content_publications'}
            if any(key not in mapping for key in supplied):raise ValueError('unsupported_setting')
            changes={mapping[key]:value for key,value in supplied.items()}
        changes=normalize_changes(changes)
        if 'content_publications_time' in changes and not zone:
            raise ValueError('business_timezone_required')
        updated={**current,**changes}
        if updated.get('content_publications') and not zone:raise ValueError('business_timezone_required')
        summary=(f"Передача материалов: {binding.get('name') or 'сохранённый получатель'} через подключённого бота. "
                 f"За {updated.get('content_publications_lead_days',0)} календарных дней до публикации; "
                 f"время: {updated.get('content_publications_time') or 'по существующему порядку проверок'}, пояс: {zone or 'не задан'}. "
                 f"Площадки: {', '.join(updated.get('content_publications_platforms') or ['как в текущей настройке'])}. "
                 f"Состояние: {'включено' if updated.get('content_publications') else 'пауза'}. Публикация в соцсетях не выполняется.")
        return {'status':'approval_required','chat_response':summary,
                'approval':{'status':'pending','capability':'content.handoff','summary':summary,
                    'envelope':{'business_id':business_id,'recipient_user_id':binding['user_id'],
                                'revision':binding['revision'],'changes':changes}},'external_writes_performed':False}
    except (ValueError,PermissionError) as exc:
        return {'status':'blocked','blocked_reasons':[str(exc)]}


def execute(cursor, *, business_id, user_id, envelope, actor_context=None):
    if envelope.get('compiled_operation'):
        from services import operator_compiled_content
        return operator_compiled_content.execute(cursor, business_id=business_id, user_id=user_id,
            envelope=envelope, actor_context=actor_context)
    actor=_authorized_actor(cursor,business_id=business_id,user_id=user_id,actor_context=actor_context)
    recipient=str(envelope.get('recipient_user_id') or '')
    if not actor or envelope.get('business_id')!=business_id or (not actor.get('is_superadmin') and recipient!=user_id):
        return {'status':'blocked','blocked_reasons':['access_denied']}
    cursor.execute('SELECT user_id FROM telegramcontrolpreferences WHERE user_id=%s FOR UPDATE',(recipient,))
    try:
        changes=normalize_changes(envelope.get('changes'))
        binding,_=_binding(cursor,business_id,recipient)
        if not binding or binding['revision']!=envelope.get('revision'):
            raise ValueError('handoff_binding_changed')
        if (changes.get('content_publications',binding['settings'].get('content_publications')) or 'content_publications_time' in changes) and not binding['timezone']:
            raise ValueError('business_timezone_required')
        from services.telegram_control_scope import save_scope_notification_preferences
        settings=save_scope_notification_preferences(cursor,user_id=recipient,telegram_id=str(binding['telegram_id']),
            scope={'kind':'business','id':business_id},notifications=changes)
        return {'status':'completed','business_id':business_id,'recipient_user_id':recipient,'settings':settings,
                'chat_response':'Настройка передачи материалов сохранена для прежнего получателя и бота.',
                'external_writes_performed':False}
    except (ValueError,PermissionError) as exc:
        return {'status':'blocked','blocked_reasons':[str(exc)]}
