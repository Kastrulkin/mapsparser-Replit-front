"""Narrow LocalOS bridge to the installed OpenClaw web_fetch tool.

The gateway credential never leaves this host. This is a transport adapter,
not a browser, planner, sender or connection registry.
"""
import hmac
import ipaddress
import json
import os
import re
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit, urljoin
from urllib.request import Request, urlopen

CONFIG_PATH = Path('/root/openclaw_runtime/var/localos-web-read.json')
GATEWAY_CONFIG = Path('/root/.openclaw-localos/openclaw.json')
ACTION = 'browser_use.read_page'
RESEARCH_ACTION = 'partners.research_website'


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
    if path not in ('/capabilities/catalog', '/capabilities/' + ACTION, '/capabilities/' + RESEARCH_ACTION):
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
                'available': ready, 'status': 'available' if ready else 'verification_required', 'side_effect': 'none',
            }, {
                'openclaw_action_ref': 'openclaw.partners.research_website',
                'localos_capability': RESEARCH_ACTION, 'risk_class': 'read',
                'configured': True, 'verified': ready, 'available': ready,
                'status': 'available' if ready else 'verification_required',
                'verified_at': config['verified_at'], 'business_ids': businesses,
                'side_effect': 'none', 'max_pages': 5, 'paid_fallback': False,
            }]}
        if method != 'POST':
            return 405, {'ok': False, 'error': 'method_not_allowed'}
        if not ready:
            return 503, {'ok': False, 'error': 'verification_required'}
        if not isinstance(payload, dict) or payload.get('business_id') not in businesses:
            return 403, {'ok': False, 'error': 'business_not_allowed'}
        if path == '/capabilities/' + RESEARCH_ACTION:
            if not str(payload.get('job_id') or '').strip():
                return 400, {'ok': False, 'error': 'job_id_required'}
            return 200, {'ok': True, 'result': research_website(payload, headers)}
        url = public_url(str(payload.get('url', '')))
        gateway = json.loads(GATEWAY_CONFIG.read_text())
        fetch = gateway.get('tools', {}).get('web', {}).get('fetch', {})
        if fetch.get('firecrawl', {}).get('enabled') is not False:
            return 503, {'ok': False, 'error': 'paid_fallback_not_disabled'}
        credential = gateway['gateway']['auth']['token']
        request = Request('http://127.0.0.1:18891/tools/invoke',
            data=json.dumps({'tool': 'web_fetch', 'args': {
                'url': url, 'extractMode': 'markdown' if payload.get('_research') else 'text', 'maxChars': 12000,
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


def research_website(payload, headers):
    """Bounded same-origin reads via the installed gateway; no search or send."""
    url = public_url(str(payload.get('url', '')))
    origin = urlsplit(url)
    pending, visited, pages, gaps = [url], set(), [], []
    requirements = payload.get('requirements', [])
    if not isinstance(requirements, list) or len(requirements) > 10:
        raise ValueError('invalid_requirements')
    for _ in range(5):
        if not pending:
            break
        current = pending.pop(0)
        visited.add(current)
        status, result = handle_web_read('POST', '/capabilities/' + ACTION, headers,
            {'business_id': payload['business_id'], 'url': current, '_research': True})
        if status != 200:
            gaps.append({'url': current, 'reason': result.get('error', 'read_failed')})
            continue
        page = result['source']
        final = urlsplit(page['final_url'])
        if (final.hostname, final.port) != (origin.hostname, origin.port):
            gaps.append({'url': current, 'reason': 'redirect_outside_site'})
            continue
        page['content_text'] = source_text(page['text'])
        pages.append(page)
        # Only links actually present on a fetched page; do not guess paths.
        for raw in re.findall(r'\[[^]\n]*\]\(([^)\s]+)\)', page['text']):
            candidate = urljoin(page['final_url'], raw).split('#', 1)[0]
            parsed = urlsplit(candidate)
            if (parsed.hostname, parsed.port) != (origin.hostname, origin.port):
                continue
            if parsed.scheme not in ('https', 'http') or candidate in visited or candidate in pending:
                continue
            if any(hint in parsed.path.lower() for hint in ('contact', 'about', 'service', 'контакт', 'услуг', 'tour')):
                if len(pending) < 4:
                    pending.append(candidate)
    contacts, facts, seen = [], [], set()
    for page in pages:
        text, source = page['content_text'], page['final_url']
        for email in re.findall(r'(?<![\w.+-])([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})(?![\w.-])', text, re.I):
            if email.lower() not in seen:
                seen.add(email.lower())
                contacts.append({'contact_type': 'email', 'value': email, 'source_url': source,
                    'verification_status': 'confirmed_source', 'provider': 'openclaw.web_fetch',
                    'observed_at': page.get('fetched_at')})
        for line in text.splitlines():
            line = line.strip()
            # Excerpts are untrusted evidence, not automatic qualification.
            if len(line) >= 30 and not line.startswith('[UNTRUSTED') and len(facts) < 20:
                facts.append({'fact': line[:700], 'source_url': source,
                    'observed_at': page.get('fetched_at'), 'untrusted': True})
    if not contacts:
        gaps.append({'reason': 'public_email_not_found'})
    return {'business_id': payload['business_id'], 'job_id': payload['job_id'],
        'provider': 'openclaw.web_fetch', 'pages': pages, 'contacts': contacts,
        'facts': facts, 'requirements': [{'requirement': str(r), 'status': 'not_checked'} for r in requirements],
        'gaps': gaps, 'fetched_at': datetime.now(timezone.utc).isoformat(),
        'complete': bool(pages), 'paid_fallback': False}


def source_text(text):
    """Exclude OpenClaw's safety envelope from the website evidence itself."""
    match = re.search(r'<<<EXTERNAL_UNTRUSTED_CONTENT>>>\s*Source: Web Fetch\s*---\s*(.*?)\s*<<<END_EXTERNAL_UNTRUSTED_CONTENT>>>', text, re.S)
    if match:
        return match.group(1)
    if text.startswith('SECURITY NOTICE:'):
        return ''  # Truncated safety envelope is not a website fact.
    return text
