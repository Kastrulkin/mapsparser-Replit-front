"""Narrow LocalOS bridge to the installed OpenClaw web_fetch tool.

The gateway credential never leaves this host. This is a transport adapter,
not a browser, planner, sender or connection registry.
"""
import hmac
import ipaddress
import json
import os
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

CONFIG_PATH = Path('/root/openclaw_runtime/var/localos-web-read.json')
GATEWAY_CONFIG = Path('/root/.openclaw-localos/openclaw.json')
ACTION = 'browser_use.read_page'


def public_url(value):
    parsed = urlsplit(value)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname:
        raise ValueError('public_url_required')
    if parsed.username is not None or parsed.password is not None:
        raise ValueError('public_url_required')
    if parsed.port not in (None, 80, 443):
        raise ValueError('public_url_required')
    addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
        raise ValueError('public_url_required')
    return value


def handle_web_read(method, path, headers, payload):
    if path not in ('/capabilities/catalog', '/capabilities/' + ACTION):
        return None
    token = os.environ.get('OPENCLAW_INTERNAL_TOKEN', '')
    received = headers.get('X-OpenClaw-Internal-Token', '')
    if not token or not hmac.compare_digest(token, received):
        return 401, {'ok': False, 'error': 'unauthorized'}
    try:
        config = json.loads(CONFIG_PATH.read_text())
        checked = datetime.fromisoformat(config['verified_at'].replace('Z', '+00:00'))
        age = datetime.now(timezone.utc) - checked
        ready = config.get('enabled') is True and timedelta(minutes=-1) <= age <= timedelta(hours=24)
        businesses = config.get('business_ids', [])
        if method == 'GET' and path == '/capabilities/catalog':
            return 200, {'actions': [{
                'openclaw_action_ref': 'openclaw.browser.read_page',
                'localos_capability': ACTION, 'risk_class': 'read',
                'configured': True, 'verified': ready,
                'verified_at': config['verified_at'], 'business_ids': businesses,
                'available': ready, 'side_effect': 'none',
            }]}
        if method != 'POST' or path != '/capabilities/' + ACTION:
            return 405, {'ok': False, 'error': 'method_not_allowed'}
        if not ready:
            return 503, {'ok': False, 'error': 'verification_required'}
        if not isinstance(payload, dict) or payload.get('business_id') not in businesses:
            return 403, {'ok': False, 'error': 'business_not_allowed'}
        url = public_url(str(payload.get('url', '')))
        gateway = json.loads(GATEWAY_CONFIG.read_text())
        fetch = gateway.get('tools', {}).get('web', {}).get('fetch', {})
        if fetch.get('firecrawl', {}).get('enabled') is not False:
            return 503, {'ok': False, 'error': 'paid_fallback_not_disabled'}
        credential = gateway['gateway']['auth']['token']
        request = Request('http://127.0.0.1:18891/tools/invoke',
            data=json.dumps({'tool': 'web_fetch', 'args': {
                'url': url, 'extractMode': 'text', 'maxChars': 12000,
            }}).encode(), headers={'Authorization': 'Bearer ' + credential,
                                  'Content-Type': 'application/json'}, method='POST')
        with urlopen(request, timeout=25) as response:
            result = json.loads(response.read(256000))
        details = result.get('result', {}).get('details', {})
        if result.get('ok') is not True or details.get('status') != 200:
            return 502, {'ok': False, 'error': 'read_failed'}
        # OpenClaw pins DNS and validates each redirect. Recheck its returned URL.
        final_url = public_url(str(details.get('finalUrl', '')))
        return 200, {'ok': True, 'source': {
            'provider': 'openclaw.web_fetch', 'url': url, 'final_url': final_url,
            'fetched_at': details.get('fetchedAt'), 'untrusted': True,
            'text': str(details.get('text', ''))[:16000],
            'truncated': bool(details.get('truncated')), 'cached': bool(details.get('cached')),
        }}
    except ValueError:
        return 400, {'ok': False, 'error': 'invalid_request_or_configuration'}
    except Exception:
        # Upstream errors can contain URLs or credentials; never echo them.
        return 502, {'ok': False, 'error': 'openclaw_read_unavailable'}
