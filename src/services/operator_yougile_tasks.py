"""Shared task tools for web, Telegram and MAX."""
import sys
from services import yougile_tasks
from services.yougile_client import YouGileError


def preview(cursor, business_id, user_id, args, channel='web', orchestrator=None):
    try:
        payload = yougile_tasks.prepare(cursor, business_id, user_id, args)
        from services.operator_core import _prepare_registered_capability_approval
        result = _prepare_registered_capability_approval(cursor=cursor, capability='tasks.yougile',
            tool_name='tasks.yougile.prepare', business_id=business_id, user_id=user_id,
            channel=channel, message=payload['summary'], payload=payload,
            backend_capability='yougile.task.apply', orchestrator=orchestrator)
        if result.get('status') == 'approval_required':
            result['chat_response'] = payload['summary'] + '\n\nПодтвердите изменение в YouGile.'
            result['approval']['summary'] = result['chat_response']
        return result
    except YouGileError:
        error = sys.exception()
        return {'status': 'blocked', 'capability': 'tasks.yougile', 'chat_response': str(error), 'blocked_reasons': [error.code]}


def tools(cursor, business_id, user_id, channel, orchestrator=None):
    if not yougile_tasks.enabled():
        return []
    def read(_args):
        try:
            data = yougile_tasks.read_tasks(cursor, business_id, user_id)
            data['total'] = len(data['items'])
            data['has_more'] = len(data['items']) > 200
            data['items'] = data['items'][:200]
            return {'status': 'completed', 'capability': 'tasks.yougile', 'chat_response': 'Задачи выбранной доски YouGile.', **data}
        except YouGileError:
            error = sys.exception()
            return {'status': 'blocked', 'capability': 'tasks.yougile', 'chat_response': str(error), 'blocked_reasons': [error.code]}
    return [
        {'name': 'tasks.yougile.list', 'capability': 'tasks.yougile', 'title': 'Задачи команды в YouGile',
         'description': 'Читает задачи, статусы и пользователей выбранной доски. Перед подготовкой поручения прочитай реальные ID исполнителей. Не выдумывай сотрудников и результаты выполнения.',
         'input_schema': {'type': 'object', 'properties': {}, 'additionalProperties': False},
         'risk_class': 'read_only', 'approval_required': False, 'execute': read},
        {'name': 'tasks.yougile.prepare', 'capability': 'tasks.yougile', 'title': 'Подготовить поручение в YouGile',
         'description': 'Готовит одну задачу или завершение существующей на проверку. Запись только после отдельного подтверждения. Срок: точная дата ISO со смещением часового пояса; если неизвестна, уточни. Исполнители по ID из tasks.yougile.list. Не означает выполнения работы, доставки сообщения или создания напоминания.',
         'input_schema': {'type': 'object', 'required': ['operation'], 'additionalProperties': False, 'properties': {
             'operation': {'type': 'string', 'enum': ['create', 'complete']}, 'title': {'type': 'string', 'maxLength': 300},
             'description': {'type': 'string', 'maxLength': 5000}, 'assigned': {'type': 'array', 'maxItems': 10, 'items': {'type': 'string'}},
             'deadline': {'type': 'string'}, 'task_id': {'type': 'string'}}},
         'risk_class': 'external_write', 'approval_required': True,
         'prepare_approval': lambda args: preview(cursor, business_id, user_id, args, channel, orchestrator)},
    ]
