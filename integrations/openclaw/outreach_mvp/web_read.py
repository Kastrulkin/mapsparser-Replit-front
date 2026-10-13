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
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit, urljoin
from urllib.request import Request, urlopen

CONFIG_PATH = Path('/root/openclaw_runtime/var/localos-web-read.json')
GATEWAY_CONFIG = Path('/root/.openclaw-localos/openclaw.json')
ACTION = 'browser_use.read_page'
RESEARCH_ACTION = 'partners.research_website'
_verification_lock = threading.Lock()
_last_verification_attempt = 0.0


def invoke_fetch(url, *, extract_mode='markdown', max_chars=12000):
    gateway = json.loads(GATEWAY_CONFIG.read_text())
    fetch = gateway.get('tools', {}).get('web', {}).get('fetch', {})
    if fetch.get('firecrawl', {}).get('enabled') is not False:
        raise ValueError('paid_fallback_not_disabled')
    request = Request('http://127.0.0.1:18891/tools/invoke',
        data=json.dumps({'tool': 'web_fetch', 'args': {
            'url': url, 'extractMode': extract_mode, 'maxChars': max_chars,
        }}).encode(), headers={'Authorization': 'Bearer ' + gateway['gateway']['auth']['token'],
                              'Content-Type': 'application/json'}, method='POST')
    with urlopen(request, timeout=25) as response:
        return json.loads(response.read(256000))


def reverify_fetch(config):
    """Renew readiness only after a real read with paid fallback disabled."""
    global _last_verification_attempt
    if not _verification_lock.acquire(blocking=False):
        return False
    try:
        now = time.monotonic()
        if _last_verification_attempt and now - _last_verification_attempt < 600:
            return False
        _last_verification_attempt = now
        result = invoke_fetch('https://localos.pro/robots.txt', max_chars=1500)
        details = result.get('result', {}).get('details', {})
        if result.get('ok') is not True or details.get('status') != 200:
            return False
        if urlsplit(str(details.get('finalUrl', ''))).hostname != 'localos.pro' or 'User-agent:' not in str(details.get('text', '')):
            return False
        config['verified_at'] = datetime.now(timezone.utc).isoformat()
        temporary = CONFIG_PATH.with_suffix('.verified.tmp')
        temporary.write_text(json.dumps(config))
        temporary.chmod(0o600)
        temporary.replace(CONFIG_PATH)
        return True
    except Exception:
        return False  # Never leak upstream URLs or credentials.
    finally:
        _verification_lock.release()


def same_website(left, right):
    """Accept only the apex/www alias, never arbitrary subdomains."""
    def identity(parsed):
        host = (parsed.hostname or '').lower()
        return (host.removeprefix('www.'), parsed.port)
    return bool(left.hostname and right.hostname) and identity(left) == identity(right)


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
        businesses = config.get('business_ids', [])
        if method == 'POST' and (not isinstance(payload, dict) or payload.get('business_id') not in businesses):
            return 403, {'ok': False, 'error': 'business_not_allowed'}
        checked = datetime.fromisoformat(config['verified_at'].replace('Z', '+00:00'))
        age = datetime.now(timezone.utc) - checked
        ready = config.get('enabled') is True and timedelta(minutes=-1) <= age <= timedelta(hours=24)
        if config.get('enabled') is True and age > timedelta(hours=24):
            ready = reverify_fetch(config)
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
        result = invoke_fetch(url, extract_mode='markdown' if payload.get('_research') else 'text')
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
    except ValueError as error:
        if str(error) == 'paid_fallback_not_disabled':
            return 503, {'ok': False, 'error': 'paid_fallback_not_disabled'}
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
    known_sources = payload.get('known_source_urls', [])
    if not isinstance(known_sources, list) or len(known_sources) > 4:
        raise ValueError('invalid_known_sources')
    for candidate in known_sources:
        if not isinstance(candidate, str) or not same_website(urlsplit(candidate), origin):
            raise ValueError('invalid_known_sources')
        candidate = candidate.split('#', 1)[0]
        if candidate not in pending:
            pending.append(candidate)
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
        if not same_website(final, origin):
            gaps.append({'url': current, 'reason': 'redirect_outside_site'})
            continue
        page['content_text'] = source_text(page['text'])
        pages.append(page)
        # Only links actually present on a fetched page; do not guess paths.
        discovered = []
        for raw in re.findall(r'\[[^]\n]*\]\(([^)\s]+)\)', page['text']):
            candidate = urljoin(page['final_url'], raw).split('#', 1)[0]
            parsed = urlsplit(candidate)
            if not same_website(parsed, origin):
                continue
            if parsed.scheme not in ('https', 'http') or candidate in visited or candidate in pending:
                continue
            if any(hint in parsed.path.lower() for hint in ('contact', 'about', 'service', 'контакт', 'услуг', 'tour')):
                if candidate not in discovered:
                    discovered.append(candidate)
        # Contact and company pages must fit within the same five-page budget.
        # Never guess URLs or add a second search merely to fill that budget.
        def priority(candidate):
            path = urlsplit(candidate).path.lower()
            if any(word in path for word in ('contact', 'контакт')):
                return 0
            if 'about' in path:
                return 1
            return 2
        pending = sorted(dict.fromkeys([*pending, *discovered]), key=priority)[:4]
    contacts, facts, seen, candidate_facts = [], [], set(), []
    terms = set(re.findall(r'\w{3,}', ' '.join(map(str, requirements)).casefold()))
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
            if len(line) >= 20 and not line.startswith('[UNTRUSTED'):
                candidate_facts.append({'fact': line[:700], 'source_url': source,
                    'observed_at': page.get('fetched_at'), 'untrusted': True})
    def relevance(fact):
        text = fact['fact'].casefold()
        return -sum(term in text for term in terms)
    for page in pages:
        page_facts = [fact for fact in candidate_facts if fact['source_url'] == page['final_url']]
        facts.extend(sorted(page_facts, key=relevance)[:4])
    for fact in sorted(candidate_facts, key=relevance):
        if len(facts) >= 20:
            break
        if fact not in facts:
            facts.append(fact)
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
