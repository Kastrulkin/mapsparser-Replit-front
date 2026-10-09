"""Free-only web discovery for the existing outreach worker. Never calls Maps.

Enable each provider only after checking its account has no paid overage or
payment method. In particular Exa has no documented free-balance endpoint here;
EXA_FREE_ONLY_VERIFIED is an operator attestation, not inferred from an API key.
"""
from __future__ import annotations

import os
import base64
import binascii
import xml.etree.ElementTree as ET
import re
from urllib.parse import urlparse
import requests


class QuotaExhausted(Exception):
    """Only an explicit credit exhaustion permits switching providers."""


def _providers() -> list[str]:
    if os.getenv('OUTREACH_WEB_SEARCH_ENABLED', 'false').lower() != 'true':
        return []
    return [name for name in ('tavily', 'exa')
            if os.getenv(f'{name.upper()}_API_KEY')
            and os.getenv(f'{name.upper()}_FREE_ONLY_VERIFIED', 'false').lower() == 'true']


def configured(provider: str | None = None) -> bool:
    if provider == 'yandex':
        return (os.getenv('OUTREACH_WEB_SEARCH_ENABLED', 'false').lower() == 'true'
                and os.getenv('YANDEX_SEARCH_PAID_REQUESTS_ENABLED', 'false').lower() == 'true'
                and bool(os.getenv('YANDEX_SEARCH_API_KEY') and os.getenv('YANDEX_SEARCH_FOLDER_ID')))
    return bool(_providers())


def readiness_request(message: str) -> bool:
    text = str(message or '')
    return (bool(re.search(r'веб[- ]?поиск|web search|поисков.{0,12}api|tavily|exa|яндекс.{0,15}(?:поиск|api)|yandex.{0,15}(?:search|api)', text, re.I))
            and bool(re.search(r'подключ|готовност|провер.{0,20}(?:api|квот|источник)|connection|readiness', text, re.I)))


def readiness() -> dict:
    providers = _providers()
    yandex_credentials = bool(os.getenv('YANDEX_SEARCH_API_KEY') and os.getenv('YANDEX_SEARCH_FOLDER_ID'))
    connected = bool(providers)
    text = ('Веб-поиск подключён: ' + ', '.join(providers) + '. Остаток бесплатной квоты сейчас не проверялся.'
            if connected else 'Веб-поиск не подключён. Нужен ключ поискового API с подтверждённым бесплатным тарифом.')
    return {'status': 'completed' if connected else 'blocked',
            'reason_code': '' if connected else 'web_search_not_configured',
            'chat_response': text + ' Поиск, карты и платные запросы не запускались; списаний за поиск нет.',
            'providers': providers, 'quota_status': 'unknown', 'search_started': False,
            'external_calls_performed': False, 'paid_actions_performed': False,
            'yandex': {'credentials_present': yandex_credentials, 'billing': 'paid',
                       'automatic_fallback': False, 'requires_separate_approval': True}}


def _check_response(response, quota_statuses: set[int]) -> None:
    if response.status_code in quota_statuses:
        raise QuotaExhausted()
    if response.status_code in {401, 403}:
        raise RuntimeError('web_search_access_denied')
    if response.status_code == 429:
        raise RuntimeError('web_search_rate_limited')
    if not 200 <= response.status_code < 300:
        # Do not propagate response bodies/URLs that could expose credentials.
        raise RuntimeError('web_search_failed')


def _tavily(query: str, limit: int) -> list[dict]:
    headers = {'Authorization': f"Bearer {os.environ['TAVILY_API_KEY']}"}
    usage = requests.get('https://api.tavily.com/usage', headers=headers, timeout=15)
    _check_response(usage, {432})
    data = usage.json()
    account = data.get('account') or {}
    key = data.get('key') or {}
    # Fail closed if billing details are missing, paid, or permit overage.
    if (str(account.get('current_plan', '')).lower() not in {'researcher', 'free'}
            or account.get('paygo_limit') != 0
            or not isinstance(account.get('plan_limit'), (int, float))
            or not isinstance(account.get('plan_usage'), (int, float))):
        raise RuntimeError('web_search_free_plan_unverified')
    if account['plan_usage'] >= min(account['plan_limit'], 1000):
        raise QuotaExhausted()
    if isinstance(key.get('limit'), (int, float)) and key['limit'] > 0:
        if not isinstance(key.get('usage'), (int, float)):
            raise RuntimeError('web_search_free_plan_unverified')
        if key['usage'] >= key['limit']:
            raise QuotaExhausted()
    response = requests.post('https://api.tavily.com/search', headers=headers,
        json={'query': query, 'search_depth': 'basic', 'auto_parameters': False,
              'max_results': min(limit, 20), 'include_answer': False,
              'include_raw_content': False, 'include_images': False,
              'include_usage': True}, timeout=30)
    _check_response(response, {432})
    return response.json().get('results') or []


def _exa(query: str, limit: int) -> list[dict]:
    # Free-only account must reject the request at exhaustion. No paid upgrade,
    # additional contents, summaries, contact enrichment, or transport retries.
    response = requests.post('https://api.exa.ai/search',
        headers={'x-api-key': os.environ['EXA_API_KEY']},
        json={'query': query, 'type': 'auto', 'numResults': min(limit, 10)}, timeout=30)
    _check_response(response, {402})
    return response.json().get('results') or []


def _yandex(query: str, limit: int) -> list[dict]:
    """One synchronous web request; no images, maps or generative snippets."""
    if not os.getenv('YANDEX_SEARCH_API_KEY') or not os.getenv('YANDEX_SEARCH_FOLDER_ID'):
        raise RuntimeError('web_search_not_configured')
    if len(query) > 400:
        raise ValueError('web_search_query_too_long')
    search_type = os.getenv('YANDEX_SEARCH_TYPE', 'SEARCH_TYPE_COM')
    if search_type not in {'SEARCH_TYPE_RU', 'SEARCH_TYPE_COM', 'SEARCH_TYPE_TR',
                            'SEARCH_TYPE_KK', 'SEARCH_TYPE_BE', 'SEARCH_TYPE_UZ'}:
        raise ValueError('web_search_invalid_search_type')
    response = requests.post('https://searchapi.api.cloud.yandex.net/v2/web/search',
        headers={'Authorization': f"Api-Key {os.environ['YANDEX_SEARCH_API_KEY']}"},
        json={'query': {'searchType': search_type, 'queryText': query,
                        'familyMode': 'FAMILY_MODE_MODERATE', 'page': '0'},
              'groupSpec': {'groupMode': 'GROUP_MODE_DEEP',
                            'groupsOnPage': str(max(1, min(limit, 100))), 'docsInGroup': '1'},
              'maxPassages': '2', 'folderId': os.environ['YANDEX_SEARCH_FOLDER_ID'],
              'responseFormat': 'FORMAT_XML'}, timeout=30)
    # 429 is a rate limit, not evidence of exhausted free quota. Never fall back.
    _check_response(response, set())
    raw = response.json().get('rawData')
    if not isinstance(raw, str) or not raw or len(raw) > 4_000_000:
        raise RuntimeError('web_search_invalid_response')
    try:
        data = base64.b64decode(raw, validate=True)
        if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
            raise ValueError('xml_entities_not_allowed')
        root = ET.fromstring(data)
    except (binascii.Error, ET.ParseError, ValueError):
        raise RuntimeError('web_search_invalid_response') from None
    if root.find('.//error') is not None:
        raise RuntimeError('web_search_failed')
    results = []
    for doc in root.findall('.//doc'):
        title = doc.find('title')
        url = doc.findtext('url') or ''
        passages = doc.findall('./passages/passage')
        results.append({'title': ''.join(title.itertext()) if title is not None else '',
                        'url': url, 'content': ' '.join(''.join(p.itertext()) for p in passages)})
    return results


def _normalize(items: list[dict], provider: str, limit: int) -> list[dict]:
    results, seen = [], set()
    for item in items:
        url = str(item.get('url') or '')
        parsed = urlparse(url)
        if parsed.scheme not in {'https', 'http'} or not parsed.hostname or parsed.username or parsed.password:
            continue
        host = parsed.hostname.lower().removeprefix('www.')
        if host in seen:
            continue
        title = str(item.get('title') or '').strip()
        if not title:
            continue
        seen.add(host)
        results.append({'name': title[:300], 'source_url': url, 'url': url,
            'website': f'{parsed.scheme}://{parsed.netloc}/',
            'search_snippet': str(item.get('content') or item.get('text') or '')[:1500],
            'source_provider': f'{provider}_web', 'qualification_required': True})
    return results[:limit]


def search(query: str, geography: str, limit: int, index: int = 0, *,
           provider: str | None = None, paid_search_approved: bool = False) -> list[dict]:
    # Existing outreach tasks stay on the free-only route. A Yandex key alone
    # must never make an old task or exhausted free quota start paid requests.
    if provider == 'yandex':
        if (not paid_search_approved
                or os.getenv('YANDEX_SEARCH_PAID_REQUESTS_ENABLED', 'false').lower() != 'true'):
            raise RuntimeError('web_search_paid_approval_required')
        if os.getenv('OUTREACH_WEB_SEARCH_ENABLED', 'false').lower() != 'true':
            raise RuntimeError('web_search_not_configured')
        if limit < 1:
            return []
        return _normalize(_yandex(f'{query} {geography}'.strip(), limit), 'yandex', limit)
    if provider is not None:
        raise ValueError('web_search_invalid_provider')
    providers = _providers()
    if not providers:
        raise RuntimeError('web_search_not_configured')
    if limit < 1:
        return []
    for provider in providers:
        try:
            items = (_tavily if provider == 'tavily' else _exa)(f'{query} {geography}'.strip(), limit)
        except QuotaExhausted:
            continue
        # An empty successful result is not quota exhaustion and is not retried.
        return _normalize(items, provider, limit)
    raise RuntimeError('web_search_free_quota_exhausted')
