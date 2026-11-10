"""Bounded cloud-only YouGile API v2 transport; no generic URL escape hatch."""
import re
import requests

BASE_URL = 'https://ru.yougile.com/api-v2'


class YouGileError(ValueError):
    def __init__(self, code, message, status=400):
        super().__init__(message)
        self.code = code
        self.status = status


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-fA-F-]{36}', value):
        raise YouGileError('invalid_id', 'Выберите объект из списка YouGile.')
    import uuid
    try:
        return str(uuid.UUID(value))
    except ValueError:
        raise YouGileError('invalid_id', 'Выберите объект из списка YouGile.') from None


def request(token, method, path, payload=None, params=None):
    read = method == 'GET' and re.fullmatch(r'/(users(/me)?|projects|boards|columns|tasks)(/[0-9a-fA-F-]{36})?', path)
    write = (method == 'POST' and path == '/tasks') or (method == 'PUT' and re.fullmatch(r'/tasks/[0-9a-fA-F-]{36}', path))
    if not (read or write):
        raise YouGileError('unsupported_operation', 'Операция YouGile недоступна.', 403)
    try:
        response = requests.request(method, BASE_URL + path, params=params, json=payload,
            headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/json'},
            timeout=(5, 20), allow_redirects=False)
    except requests.RequestException:
        raise YouGileError('unknown_result' if write else 'provider_unavailable',
            'Результат записи неизвестен. Проверьте задачу в YouGile; повтор автоматически не выполняется.' if write
            else 'YouGile недоступен. Повторите загрузку позже.', 502) from None
    if response.status_code == 429:
        raise YouGileError('rate_limited', 'YouGile ограничил частоту запросов. Повторите позже.', 429)
    if response.status_code in (401, 403, 404):
        raise YouGileError('provider_access_denied', 'Проверьте ключ и доступ к выбранному проекту YouGile.', 403)
    if not 200 <= response.status_code < 300:
        raise YouGileError('unknown_result' if write else 'provider_unavailable',
            'YouGile не подтвердил результат. Проверьте его перед повтором.', 502)
    try:
        data = response.json()
    except ValueError:
        raise YouGileError('unknown_result' if write else 'invalid_response', 'YouGile вернул неполный ответ.', 502) from None
    if not isinstance(data, dict):
        raise YouGileError('unknown_result' if write else 'invalid_response', 'YouGile вернул неполный ответ.', 502)
    return data


def collection(token, resource, filters=None):
    items = []
    # Busy boards can reorder tasks between offset pages. Prefer the provider's
    # supported larger task page; still reject duplicates instead of claiming completeness.
    page_size = 1000 if resource == 'tasks' else 100
    for offset in range(0, 5000, page_size):
        page = request(token, 'GET', '/' + resource, params={**(filters or {}), 'limit': page_size, 'offset': offset})
        rows, paging = page.get('content'), page.get('paging')
        if not isinstance(rows, list) or len(rows) > page_size or not isinstance(paging, dict) or type(paging.get('next')) is not bool:
            raise YouGileError('invalid_response', 'YouGile не подтвердил полноту списка.', 502)
        if any(not isinstance(row, dict) or not row.get('id') for row in rows):
            raise YouGileError('invalid_response', 'YouGile вернул неполный список.', 502)
        if paging['next'] and not rows:
            raise YouGileError('invalid_response', 'YouGile не подтвердил полноту списка.', 502)
        items.extend(rows)
        if not paging['next']:
            ids = [row['id'] for row in items]
            if len(ids) != len(set(ids)):
                raise YouGileError('invalid_response', 'YouGile вернул повторяющиеся объекты.', 502)
            return [row for row in items if not row.get('deleted')]
    raise YouGileError('limit_exceeded', 'Список превышает лимит подключения: 5000 объектов.', 409)
