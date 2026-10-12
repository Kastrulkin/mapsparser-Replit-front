"""Scoped read-only provider route shared by content draft entry points."""
import json
import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import requests


def read_business_website(cursor, user_id, business_id, url):
    config_path = Path(os.getenv('LOCALOS_WEB_READ_CONFIG', '/app/data/openclaw-web-read.json'))
    if not config_path.is_file():
        return None
    config = json.loads(config_path.read_text())
    if config.get('enabled') is not True or business_id not in config.get('business_ids', []):
        return None
    from core.auth_helpers import verify_business_access
    from core.outbound_network import validate_public_http_url
    cursor.execute('SELECT COALESCE(is_superadmin, FALSE) FROM users WHERE id = %s', (user_id,))
    row = cursor.fetchone()
    superadmin = bool(row and (row.get('coalesce') if isinstance(row, dict) else row[0]))
    allowed, _owner = verify_business_access(cursor, business_id, {'user_id': user_id, 'is_superadmin': superadmin})
    if not allowed:
        raise PermissionError('Нет доступа к источникам этого бизнеса')
    public_url = validate_public_http_url(url)
    bridge = urlsplit(os.getenv('OPENCLAW_SANDBOX_BRIDGE_URL', ''))
    if bridge.scheme not in ('http', 'https') or not bridge.hostname or bridge.path.rstrip('/') != '/capabilities':
        raise ValueError('Не настроен проверенный адрес OpenClaw')
    endpoint = urlunsplit((bridge.scheme, bridge.netloc, '/capabilities/browser_use.read_page', '', ''))
    token = os.getenv('OPENCLAW_SANDBOX_BRIDGE_TOKEN', '')
    if not token:
        raise ValueError('Не настроена авторизация OpenClaw')
    response = requests.post(endpoint, headers={'X-OpenClaw-Internal-Token': token},
                             json={'business_id': business_id, 'url': public_url},
                             timeout=(3, 30), allow_redirects=False)
    if response.status_code != 200:
        raise ValueError('OpenClaw не прочитал сайт; резервный платный маршрут не запускался')
    result = response.json()
    source = result.get('source')
    if result.get('ok') is not True or not isinstance(source, dict) or source.get('untrusted') is not True:
        raise ValueError('OpenClaw вернул неподтверждённый источник')
    if source.get('url') != public_url or not source.get('fetched_at') or not source.get('text'):
        raise ValueError('OpenClaw вернул неполный источник')
    validate_public_http_url(source.get('final_url', ''))
    return {key: source.get(key) for key in (
        'provider', 'url', 'final_url', 'fetched_at', 'untrusted', 'text', 'truncated', 'cached')}
