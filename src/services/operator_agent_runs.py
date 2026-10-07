"""Existing agents.run command shared by Operator chat/voice and mobile menu."""
import json
from core.auth_context import AuthContext
from core.auth_helpers import verify_business_write_access
from services.agent_run_admission import AgentRunAdmissionService
from services.agent_run_queue import async_agent_runs_enabled
from services.operator_conversations import _row


def _actor(cursor, business_id, user_id, actor_context=None):
    context = actor_context or {}
    if context.get('session_kind') == 'demo' or context.get('impersonating') or context.get('impersonated_by'):
        raise PermissionError('direct_session_required')
    cursor.execute('SELECT * FROM users WHERE id=%s', (user_id,))
    actor = _row(cursor, cursor.fetchone())
    actor['user_id'] = user_id
    actor.update(session_kind=context.get('session_kind', 'standard'), impersonating=context.get('impersonating', False))
    if not actor.get('is_active') or not verify_business_write_access(cursor, business_id, actor)[0]:
        raise PermissionError('access_denied')
    return AuthContext.from_session(actor)


def prepare(cursor, *, business_id, user_id, arguments, actor_context=None):
    try:
        _actor(cursor, business_id, user_id, actor_context)
    except PermissionError:
        return {'status': 'blocked', 'blocked_reasons': ['access_denied']}
    cursor.execute('SELECT * FROM agent_blueprints WHERE id=%s AND business_id=%s', (arguments.get('blueprint_id'), business_id))
    blueprint = _row(cursor, cursor.fetchone())
    preview_mode = arguments.get('preview_mode') is True
    active = (blueprint.get('metadata_json') or {}).get('active_version_id')
    if preview_mode:
        if not blueprint or blueprint.get('status') not in {'draft','active'}:
            return {'status':'blocked','blocked_reasons':['preview_automation_required']}
        if arguments.get('version_id'):
            cursor.execute('SELECT * FROM agent_blueprint_versions WHERE id=%s AND blueprint_id=%s',(arguments['version_id'],blueprint['id']))
        else:
            cursor.execute('SELECT * FROM agent_blueprint_versions WHERE blueprint_id=%s ORDER BY version_number DESC LIMIT 1',(blueprint['id'],))
        version = _row(cursor,cursor.fetchone())
        active = version.get('id')
    else:
        if not active or blueprint.get('status') != 'active':
            return {'status': 'blocked', 'blocked_reasons': ['active_automation_required']}
        cursor.execute('SELECT * FROM agent_blueprint_versions WHERE id=%s AND blueprint_id=%s', (active, blueprint['id']))
        version = _row(cursor, cursor.fetchone())
    if not version:
        return {'status': 'blocked', 'blocked_reasons': ['agent_version_required']}
    inputs = arguments.get('inputs') or {}
    snapshot_id = arguments.get('input_snapshot_id') or ''
    if version.get('compiled_state', 'legacy') != 'legacy' and (preview_mode or not snapshot_id):
        return {'status': 'blocked', 'blocked_reasons': ['compiled_input_snapshot_required'],
                'chat_response': 'Для этого поручения сначала выберите проверенные исходные данные в карточке автоматизации.'}
    summary = (('Проверка без внешних действий: ' if preview_mode else 'Разовый запуск: ') + str(blueprint.get('name') or '') + '\n' + str(version.get('goal') or '')
               + '\nУсловия: ' + json.dumps({'inputs': inputs, 'limits': version.get('limits_json') or {}, 'schedule': version.get('schedule_json') or {}}, ensure_ascii=False, default=str))
    return {'status': 'approval_required', 'chat_response': summary,
            'approval': {'status': 'pending', 'capability': 'agents.run', 'summary': summary,
                         'envelope': {'business_id': business_id, 'blueprint_id': blueprint['id'],
                                      'active_version_id': active, 'preview_mode': preview_mode, 'inputs': inputs, 'input_snapshot_id': snapshot_id}}}


def execute(cursor, *, business_id, user_id, envelope, idempotency_key, actor_context=None):
    try:
        auth = _actor(cursor, business_id, user_id, actor_context)
    except PermissionError:
        return {'status': 'blocked', 'blocked_reasons': ['access_denied']}
    if envelope.get('business_id') != business_id or not idempotency_key:
        return {'status': 'blocked', 'blocked_reasons': ['agent_preview_changed']}
    if not async_agent_runs_enabled(business_id):
        return {'status': 'blocked', 'blocked_reasons': ['agent_async_runs_disabled']}
    cursor.execute('SELECT * FROM agent_blueprints WHERE id=%s AND business_id=%s', (envelope.get('blueprint_id'), business_id))
    blueprint = _row(cursor, cursor.fetchone())
    cursor.execute('SELECT * FROM agent_blueprint_versions WHERE id=%s AND blueprint_id=%s', (envelope.get('active_version_id'), envelope.get('blueprint_id')))
    version = _row(cursor, cursor.fetchone())
    if not blueprint or not version:
        return {'status': 'blocked', 'blocked_reasons': ['agent_version_changed']}
    snapshot = {'snapshot_id': envelope['input_snapshot_id']} if envelope.get('input_snapshot_id') else None
    inputs = envelope.get('inputs') or {}
    from services.agent_run_contract import RESERVED_AGENT_INPUT_FIELDS, validate_agent_run_input
    inputs = {key:value for key,value in inputs.items() if key not in RESERVED_AGENT_INPUT_FIELDS}
    validated = validate_agent_run_input(version.get('inputs_schema_json'),inputs,version.get('steps_json'))
    if not validated.get('valid'):
        return {'status':'blocked','blocked_reasons':['agent_input_invalid'],'validation_errors':validated.get('errors')}
    inputs = validated.get('input') or {}
    if envelope.get('preview_mode') is True:
        if version.get('compiled_state','legacy') != 'legacy':
            return {'status':'blocked','blocked_reasons':['compiled_preview_requires_verified_runtime']}
        from api.agent_blueprints_api import _build_agent_preview_run_input
        inputs = _build_agent_preview_run_input(blueprint,version,{'input':inputs})
    result = AgentRunAdmissionService(cursor).admit(auth=auth, blueprint=blueprint, version=version,
        input_payload=inputs, idempotency_key=idempotency_key, input_snapshot=snapshot,
        require_execution_mode_confirmation=True)
    if not result.get('success'):
        return {'status': 'blocked', 'blocked_reasons': [result.get('code') or 'agent_run_failed'], 'agent_result': result}
    run = result.get('run') or {}
    return {'status': 'completed', 'capability': 'agents.run', 'job_id': str(run.get('id') or ''),
            'job_kind': 'agent_run', 'run': run, 'external_writes_performed': False,
            'chat_response': 'Разовый запуск принят. Результат появится в журнале этой автоматизации.'}


def execute_mobile(cursor, *, business_id, user_id, envelope, actor_context=None):
    action_id = str(envelope.get('_action_id') or '')
    if not action_id:
        return {'status': 'blocked', 'blocked_reasons': ['action_required']}
    return execute(cursor, business_id=business_id, user_id=user_id, envelope=envelope,
                   idempotency_key='mobile:' + action_id, actor_context=actor_context)
