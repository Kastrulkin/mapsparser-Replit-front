"""Durable, fail-closed reservations before GigaChat/DeepSeek generation; no provider calls."""
import json
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

_SCOPE = ContextVar('ai_spend_scope', default={})
DEFAULT_LIMITS = {'daily_tokens': 100000, 'monthly_tokens': 300000,
                  'daily_calls': 20, 'monthly_calls': 100,
                  'operation_tokens': 80000, 'operation_calls': 4,
                  'request_tokens': 60000}
DEEPSEEK_LIMITS = {'daily_tokens': 300000, 'monthly_tokens': 1000000,
                   'daily_calls': 20, 'monthly_calls': 100,
                   'operation_tokens': 200000, 'operation_calls': 4,
                   'request_tokens': 150000}


class BudgetDenied(RuntimeError):
    code = 'gigachat_budget_exceeded'
    retryable = False


@contextmanager
def request_scope(**scope):
    token = _SCOPE.set({**_SCOPE.get(), **scope})
    try:
        yield
    finally:
        _SCOPE.reset(token)


def spend_operation(function):
    @wraps(function)
    def run(*args, **kwargs):
        operation = _SCOPE.get().get('operation_id') or str(uuid.uuid4())
        with request_scope(operation_id=operation):
            return function(*args, **kwargs)
    return run


def limits(provider='gigachat'):
    # One shared code policy for app, worker, operator and Telegram processes.
    # Raising a limit requires an explicit reviewed change; provider-profile switches cannot change it.
    if provider not in {'gigachat', 'deepseek', 'gigachat_embeddings'}:
        raise BudgetDenied('Неизвестный бюджет провайдера. Генерация остановлена.')
    return dict(DEEPSEEK_LIMITS if provider == 'deepseek' else DEFAULT_LIMITS)


def windows(now=None):
    current = (now or datetime.now(timezone.utc)).astimezone(ZoneInfo('Europe/Moscow'))
    day = current.replace(hour=0, minute=0, second=0, microsecond=0)
    return day, day.replace(day=1)


def reservation_tokens(body):
    # UTF-8 bytes conservatively bound text tokenization, including JSON/function framing.
    payload = {'messages': body.get('messages', []), 'functions': body.get('functions', [])}
    if 'input' in body:
        payload['input'] = body['input']
    text = json.dumps(payload, ensure_ascii=False)
    if '"attachments"' in text or '"image_url"' in text:
        raise BudgetDenied('Для файлов и изображений нужен отдельный подтверждённый бюджет. Генерация остановлена.')
    output = body.get('max_tokens', (body.get('parameters') or {}).get('max_tokens', 4000))
    if not isinstance(output, int) or isinstance(output, bool) or output <= 0:
        raise BudgetDenied('Не задан предел ответа AI. Генерация остановлена.')
    return len(text.encode('utf-8')) + 1024 + output


def _usage(cursor, day, month, operation_id, provider='gigachat'):
    cursor.execute('''SELECT row_to_json(totals) usage FROM (SELECT
        COALESCE(SUM(CASE WHEN created_at >= %s THEN CASE WHEN state='completed' THEN actual_tokens
          WHEN state IN ('reserved','uncertain') THEN reserved_tokens ELSE 0 END ELSE 0 END),0) daily_tokens,
        COALESCE(SUM(CASE WHEN state='completed' THEN actual_tokens
          WHEN state IN ('reserved','uncertain') THEN reserved_tokens ELSE 0 END),0) monthly_tokens,
        COUNT(*) FILTER (WHERE created_at >= %s) daily_calls, COUNT(*) monthly_calls,
        COALESCE(SUM(CASE WHEN operation_id=%s THEN CASE WHEN state='completed' THEN actual_tokens
          WHEN state IN ('reserved','uncertain') THEN reserved_tokens ELSE 0 END ELSE 0 END),0) operation_tokens,
        COUNT(*) FILTER (WHERE operation_id=%s) operation_calls
        FROM ai_spend_reservations WHERE provider=%s AND created_at >= %s) totals''',
        (day, day, operation_id, operation_id, provider, month))
    return dict(cursor.fetchone()['usage'])


def _check(used, policy, reserved):
    for key in ('daily_tokens', 'monthly_tokens', 'operation_tokens'):
        if used[key] + reserved > policy[key]:
            raise BudgetDenied('Достигнут лимит AI: ' + key + '. Генерация остановлена; повтор без изменения лимита не поможет.')
    for key in ('daily_calls', 'monthly_calls', 'operation_calls'):
        if used[key] + 1 > policy[key]:
            raise BudgetDenied('Достигнут лимит AI: ' + key + '. Генерация остановлена.')
    if reserved > policy['request_tokens']:
        raise BudgetDenied('Контекст AI превышает лимит одного запроса. Сократите данные перед повтором.')


def reserve(body, context=None, *, database_factory=None):
    from database_manager import DatabaseManager
    scope = {**(context or {}), **_SCOPE.get()}
    provider = scope.get('provider', 'gigachat')
    policy = limits() if provider == 'gigachat' else limits(provider)
    reserved = reservation_tokens(body)
    operation = str(scope.get('operation_id') or uuid.uuid4())
    try:
        db = (database_factory or DatabaseManager)()
    except Exception:
        raise BudgetDenied('Журнал бюджета AI недоступен. Генерация остановлена.') from None
    try:
        cursor = db.conn.cursor()
        cursor.execute("SELECT pg_advisory_xact_lock(hashtext('gigachat-spend-budget:v1'))")
        day, month = windows()
        used = _usage(cursor, day, month, operation) if provider == 'gigachat' else _usage(cursor, day, month, operation, provider)
        _check(used, policy, reserved)
        identifier = str(uuid.uuid4())
        cursor.execute('''INSERT INTO ai_spend_reservations
            (id,provider,model,task_key,business_id,actor_user_id,operation_id,state,reserved_tokens)
            VALUES (%s,%s,%s,%s,%s,%s,%s,'reserved',%s)''',
            (identifier, provider, str(body.get('model') or ''), str(scope.get('task_key') or 'generation'),
             str(scope.get('business_id') or ''), str(scope.get('user_id') or ''), operation, reserved))
        db.conn.commit()
        return identifier
    except BudgetDenied:
        db.conn.rollback()
        raise
    except Exception:
        db.conn.rollback()
        raise BudgetDenied('Журнал бюджета AI недоступен. Генерация остановлена.') from None
    finally:
        db.close()


def settle(identifier, state, actual_tokens=0, error_code='', *, database_factory=None):
    from database_manager import DatabaseManager
    db = (database_factory or DatabaseManager)()
    try:
        cursor = db.conn.cursor()
        cursor.execute('''UPDATE ai_spend_reservations SET state=%s,actual_tokens=%s,error_code=%s,
            settled_at=NOW() WHERE id=%s AND state='reserved' ''',
            (state, actual_tokens, error_code, identifier))
        db.conn.commit()
    finally:
        db.close()


def guarded_post(post, body, context=None):
    if 'max_tokens' not in body:
        body['max_tokens'] = (body.get('parameters') or {}).get('max_tokens', 4000)
    identifier = reserve(body, context)
    try:
        response = post()
    except Exception:
        # A timeout does not prove that the provider did not consume tokens.
        try:
            settle(identifier, 'uncertain', error_code='transport_unknown')
        except Exception:
            pass  # durable reservation remains held
        raise
    state, actual = 'uncertain', 0
    if 400 <= response.status_code < 500:
        state = 'rejected'
    elif 200 <= response.status_code < 300:
        try:
            usage = response.json().get('usage', {})
            value = usage.get('total_tokens')
            if value is None and isinstance(usage.get('prompt_tokens'), int):
                value = usage['prompt_tokens'] + usage.get('completion_tokens', 0)
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                state, actual = 'completed', value
        except (ValueError, TypeError, AttributeError):
            pass
    try:
        settle(identifier, state, actual, '' if state == 'completed' else str(response.status_code))
    except Exception:
        pass  # fail closed for future calls: the reservation remains held
    return response


def status(*, database_factory=None, provider='gigachat'):
    from database_manager import DatabaseManager
    policy = limits() if provider == 'gigachat' else limits(provider)
    db = (database_factory or DatabaseManager)()
    try:
        day, month = windows()
        used = _usage(db.conn.cursor(), day, month, '') if provider == 'gigachat' else _usage(db.conn.cursor(), day, month, '', provider)
        return {'provider': provider, 'limits': policy, 'used': {k: used[k] for k in ('daily_tokens','monthly_tokens','daily_calls','monthly_calls')},
                'timezone': 'Europe/Moscow', 'manual_preparation_only': True,
                'warning': any(used[k] >= policy[k] * .8 for k in ('daily_tokens','monthly_tokens','daily_calls','monthly_calls'))}
    finally:
        db.close()
