"""Chat adapter to the same authenticated compiled operations used by the menu.

Only an already-authorized Operator actor enters this module. Approval and
execution are proposed as durable Operator actions, never performed by a tool
call alone. No HTTP session or bearer token is manufactured here.
"""
from contextlib import nullcontext
import json

from flask import Flask, has_app_context

from services.operator_agent_management import _authorized_actor
from services.outreach_ai_authorization import digest


def _invoke(operation, blueprint_id, actor, payload):
    from api import agent_blueprints_api
    functions = {
        'compile': agent_blueprints_api.compiled_compile_for_actor,
        'snapshot': agent_blueprints_api.compiled_snapshot_for_actor,
        'preview': agent_blueprints_api.compiled_preview_for_actor,
        'approve': agent_blueprints_api.compiled_approve_for_actor,
        'run': agent_blueprints_api.compiled_run_for_actor,
    }
    # The common operations serialize their result with Flask.jsonify. A queue
    # worker has no request context; this supplies serialization only, not auth.
    context = nullcontext() if has_app_context() else Flask('compiled-response').app_context()
    with context:
        response = functions[operation](blueprint_id, actor, payload)
        status = response[1] if isinstance(response, tuple) else 200
        value = response[0] if isinstance(response, tuple) else response
        result = value.get_json() if hasattr(value, 'get_json') else value
    if not isinstance(result, dict):
        raise ValueError('compiled_operation_response_invalid')
    return result, status


def _load(cursor, business_id, blueprint_id, operation):
    cursor.execute('SELECT * FROM agent_blueprints WHERE id=%s AND business_id=%s AND status<>\'archived\'',
        (blueprint_id, business_id))
    blueprint = cursor.fetchone()
    if not blueprint:
        raise ValueError('agent_not_found')
    if operation == 'run':
        cursor.execute('SELECT * FROM agent_blueprint_versions WHERE blueprint_id=%s AND id=%s',
            (blueprint_id, blueprint.get('compiled_approved_version_id')))
    else:
        cursor.execute('SELECT * FROM agent_blueprint_versions WHERE blueprint_id=%s ORDER BY version_number DESC LIMIT 1',
            (blueprint_id,))
    version = cursor.fetchone()
    if not version:
        raise ValueError('compiled_version_required')
    from services.compiled_content_program import contract_for
    contract_for(version, business_id)
    return dict(blueprint), dict(version)


def _error(result):
    return {'status': 'blocked', 'blocked_reasons': [str(result.get('code') or 'compiled_operation_failed')],
        'chat_response': str(result.get('error') or 'Не удалось выполнить шаг. Проверьте состояние автоматизации.'),
        'external_writes_performed': False}


def _summary(snapshot):
    context = snapshot.get('delivery_context') or {}
    scope = context.get('scope') or {}
    lines = [f"{context.get('business_name') or 'Выбранная точка'} · {context.get('address') or ''}",
        f"Получатель: {context.get('recipient_name') or ''} · Telegram ID {context.get('telegram_id') or ''}",
        f"За {scope.get('lead_days')} день до публикации, {scope.get('time')} · {scope.get('timezone')}",
        'Передача через бот — не публикация на площадках.']
    for row in (snapshot.get('input') or {}).get('posts', []):
        lines.extend([f"{row.get('platform')} — {'готово' if row.get('eligible') else row.get('blocked_reason') or 'не готово'}",
            str(row.get('text') or ''), f"Фото: {row.get('photo_asset_id') or 'нет'}"])
    if not (snapshot.get('input') or {}).get('posts'):
        lines.append('Подходящих постов в текущем плане нет; отправки не будет.')
    return '\n'.join(lines)


def prepare(cursor, *, business_id, user_id, arguments, actor_context=None):
    actor = _authorized_actor(cursor, business_id=business_id, user_id=user_id, actor_context=actor_context)
    if not actor:
        return {'status': 'blocked', 'blocked_reasons': ['access_denied']}
    operation = str(arguments.get('operation') or '')
    blueprint_id = str(arguments.get('blueprint_id') or '')
    try:
        blueprint, version = _load(cursor, business_id, blueprint_id, operation)
        if arguments.get('expected_version_id') and arguments['expected_version_id'] != str(version['id']):
            raise ValueError('compiled_version_changed')
        payload = {'version_id': str(version['id'])}
        content_input = None
        if operation == 'compile':
            payload = {'content_handoff': True, 'expected_version_id': str(version['id']),
                'description': str(version.get('goal') or blueprint.get('description') or ''),
                'idempotency_key': f"operator-content-compile:{blueprint_id}:{version['id']}",
                'fixtures': [{'source': 'user', 'input': {'posts': [
                    {'post_id': 'пример', 'revision': 'версия-1', 'eligible': True}]},
                    'expected': {'requests': [{'post_id': 'пример', 'revision': 'версия-1'}]}}]}
            summary = ('Создать сохранённую программу по текущим условиям. Пример: готовый комплект с фото передаётся; '
                'неполный комплект и уже переданная версия пропускаются. Отправки и включения расписания сейчас нет.')
        elif operation in {'preview', 'run'}:
            snapshot_result, status = _invoke('snapshot', blueprint_id, actor,
                {'source_kind': 'content_plan', 'version_id': str(version['id'])})
            if status >= 400:
                return _error(snapshot_result)
            snapshot = snapshot_result['snapshot']
            content_input = snapshot.get('input')
            payload['snapshot_id'] = snapshot['id']
            summary = _summary(snapshot)
            if operation == 'preview':
                result, status = _invoke('preview', blueprint_id, actor, payload)
                if status >= 400:
                    return _error(result)
                return {'status': 'completed', 'blueprint_id': blueprint_id, 'version_id': str(version['id']),
                    'preview': result['preview'], 'content_input': snapshot['input'],
                    'chat_response': summary + '\nПроверка завершена без отправки. Следующий шаг — утвердить программу.',
                    'external_writes_performed': False, 'result_ref': {'href': '/dashboard/agents', 'label': 'Открыть автоматизацию'}}
            payload['idempotency_key'] = f"operator-content-run:{blueprint_id}:{snapshot['id']}"
            summary += '\nПосле подтверждения запустится передача этих материалов. Регулярное расписание не включается.'
        elif operation == 'approve':
            evidence = version.get('compiled_preview_json') or {}
            if isinstance(evidence, str):
                evidence = json.loads(evidence)
            if version.get('compiled_state') != 'ready_approval' or evidence.get('status') != 'passed':
                raise ValueError('compiled_successful_preview_required')
            payload.update(approval_digest=version.get('compiled_artifact_hash'),
                fixture_digest=evidence.get('fixture_digest'),
                delivery_context_digest=(evidence.get('delivery_context') or {}).get('digest'))
            summary = 'Утвердить эту проверенную программу и неизменные условия передачи. Расписание и отправка не запускаются.\n' + _summary({'delivery_context': evidence.get('delivery_context')})
        else:
            raise ValueError('unsupported_operation')
        envelope = {'compiled_operation': operation, 'business_id': business_id, 'blueprint_id': blueprint_id,
            'user_id': user_id, 'version_id': str(version['id']), 'payload': payload}
        envelope['intent_digest'] = digest(envelope)
        return {'status': 'approval_required', 'chat_response': summary, 'blueprint_id': blueprint_id,
            'content_input': content_input,
            'approval': {'status': 'pending', 'capability': 'content.handoff', 'summary': summary, 'envelope': envelope},
            'external_writes_performed': False}
    except (ValueError, PermissionError) as error:
        return {'status': 'blocked', 'blocked_reasons': [str(error)],
            'chat_response': 'Состояние или условия изменились. Покажите автоматизацию и повторите шаг.',
            'external_writes_performed': False}


def execute(cursor, *, business_id, user_id, envelope, actor_context=None):
    actor = _authorized_actor(cursor, business_id=business_id, user_id=user_id, actor_context=actor_context)
    intent = {key: value for key, value in envelope.items() if key != 'intent_digest'}
    if not actor or intent.get('business_id') != business_id or intent.get('user_id') != user_id or digest(intent) != envelope.get('intent_digest'):
        return {'status': 'blocked', 'blocked_reasons': ['compiled_intent_changed']}
    operation = str(intent.get('compiled_operation') or '')
    if operation not in {'compile', 'approve', 'run'}:
        return {'status': 'blocked', 'blocked_reasons': ['unsupported_operation']}
    try:
        blueprint_id = str(intent.get('blueprint_id') or '')
        _, version = _load(cursor, business_id, blueprint_id, operation)
        if str(version['id']) != str(intent.get('version_id')):
            raise ValueError('compiled_version_changed')
        result, status = _invoke(operation, blueprint_id, actor, intent['payload'])
        if status >= 400:
            return _error(result)
        messages = {'compile': 'Программа создана и сохранена. Проверьте её на текущем плане; отправки нет.',
            'approve': 'Программа и условия утверждены. Регулярное расписание остаётся выключенным.',
            'run': 'Тестовый запуск принят в очередь. Доставка ещё не подтверждена; результат смотрите в журнале.'}
        return {'status': 'completed', 'blueprint_id': blueprint_id,
            'version_id': result.get('version_id') or (result.get('candidate_version') or {}).get('id'),
            'run_id': (result.get('run') or {}).get('id'), 'run_status': result.get('status'),
            'chat_response': messages[operation], 'external_writes_performed': False,
            'result_ref': {'href': '/dashboard/agents', 'label': 'Открыть автоматизацию'}}
    except (ValueError, PermissionError) as error:
        return {'status': 'blocked', 'blocked_reasons': [str(error)], 'external_writes_performed': False}
