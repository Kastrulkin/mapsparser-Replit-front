"""Transport to installed OpenClaw research; persistence belongs to LocalOS."""
from __future__ import annotations
import os
import re
from pathlib import Path
from dotenv import load_dotenv
from urllib.parse import urlsplit, urlunsplit
import requests


class WebsiteResearchUnavailable(RuntimeError):
    retryable = False
    code = 'openclaw_research_unavailable'


def same_website(left: str, right: str) -> bool:
    first, second = urlsplit(left), urlsplit(right)
    return bool(first.hostname and second.hostname) and (
        first.hostname.lower().removeprefix('www.'), first.port
    ) == (second.hostname.lower().removeprefix('www.'), second.port)


def enabled() -> bool:
    load_dotenv(Path(__file__).resolve().parents[2] / 'config' / 'outreach-search.env', override=False)
    return os.getenv('OPENCLAW_WEBSITE_RESEARCH_ENABLED', '').lower() in {'1', 'true', 'yes'}


def research_website(*, business_id: str, job_id: str, url: str, requirements: list[str], known_source_urls: list[str] | None = None) -> dict:
    endpoint = (os.getenv('OPENCLAW_PARTNERS_CAPS_URL') or os.getenv('OPENCLAW_SANDBOX_BRIDGE_URL') or '').strip()
    token = (os.getenv('OPENCLAW_PARTNERS_TOKEN') or os.getenv('OPENCLAW_SANDBOX_BRIDGE_TOKEN') or os.getenv('OPENCLAW_LOCALOS_TOKEN') or '').strip()
    if not endpoint or not token or not business_id or not job_id:
        raise WebsiteResearchUnavailable('Исследование сайта не подключено; результаты сохранены.')
    parsed = urlsplit(endpoint)
    prefix = parsed.path.split('/capabilities', 1)[0]
    endpoint = urlunsplit((parsed.scheme, parsed.netloc, prefix + '/capabilities/partners.research_website', '', ''))
    try:
        response = requests.post(endpoint, json={'business_id': business_id, 'tenant_id': business_id,
            'job_id': job_id, 'url': url, 'requirements': requirements,
            'known_source_urls': list(known_source_urls or [])[:4]},
            headers={'X-OpenClaw-Internal-Token': token, 'X-Tenant-Id': business_id}, timeout=135)
        response.raise_for_status()
        body = response.json()
        result = body.get('result')
        if body.get('ok') is not True or not isinstance(result, dict):
            raise ValueError('invalid_result')
        if result.get('business_id') != business_id or str(result.get('job_id')) != job_id:
            raise ValueError('scope_mismatch')
        if result.get('provider') != 'openclaw.web_fetch' or result.get('paid_fallback') is not False:
            raise ValueError('invalid_provider')
        pages = result.get('pages')
        if not isinstance(pages, list) or not pages or len(pages) > 5:
            raise ValueError('invalid_pages')
        for page in pages:
            if not isinstance(page, dict) or not same_website(str(page.get('final_url', '')), url):
                raise ValueError('source_mismatch')
        return result
    except (requests.RequestException, ValueError, TypeError, KeyError):
        # No secret-bearing response body, upstream URL or token in error logs.
        raise WebsiteResearchUnavailable('Не удалось исследовать сайт через OpenClaw. Проверьте подключение или укажите другой публичный источник.') from None


def publication_facts(research: dict) -> list[dict]:
    """Project stored public page text; transport labels are never copy evidence."""
    facts=[]
    seen=set()
    for page in research.get('pages') or []:
        source=str(page.get('final_url') or '')
        text=str(page.get('content_text') or '')
        if 'Main page content:' in text:
            text=text.split('Main page content:',1)[1]
        for paragraph in text.splitlines():
            if paragraph.lstrip().startswith(('#','[','http',':')):continue
            paragraph=re.sub(r'\[([^\]]+)\]\([^)]*\)',r'\1',paragraph)
            paragraph=re.sub(r'\s+',' ',paragraph).strip()
            for sentence in re.split(r'(?<=[.!?])\s+',paragraph):
                if not 7<=len(sentence.split())<=65 or not sentence.endswith(('.', '!', '?')):continue
                if re.search(r'page title|public contact|main page content|публичный фрагмент|крупнейш|лучш|лидер',sentence,re.I):continue
                if sentence in seen or not source:continue
                seen.add(sentence)
                facts.append({'fact':'На сайте компании сказано: «'+sentence.rstrip('.!?')+'».','source_url':source,'observed_at':page.get('fetched_at'),
                              'evidence_type':'page_excerpt','untrusted':True})
                if len(facts)>=20:return facts
    return facts
