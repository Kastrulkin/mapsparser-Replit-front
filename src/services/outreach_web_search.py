"""Free-only web discovery for the existing outreach worker. Never calls Maps.

Enable each provider only after checking its account has no paid overage or
payment method. In particular Exa has no documented free-balance endpoint here;
EXA_FREE_ONLY_VERIFIED is an operator attestation, not inferred from an API key.
"""
from __future__ import annotations

import os
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


def configured() -> bool:
    return bool(_providers())


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


def search(query: str, geography: str, limit: int, index: int = 0) -> list[dict]:
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
