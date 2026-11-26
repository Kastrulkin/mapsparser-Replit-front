"""Bounded public observations for initial setup, using the existing readers."""
import json
import re
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from services import initial_setup_photos, map_card_initial_audit, website_seo_audit


SOCIALS = {
    't.me': 'telegram', 'telegram.me': 'telegram', 'vk.com': 'vk', 'vk.ru': 'vk',
    'instagram.com': 'instagram', 'facebook.com': 'facebook', 'wa.me': 'whatsapp',
    'whatsapp.com': 'whatsapp', 'youtube.com': 'youtube', 'youtu.be': 'youtube', 'tiktok.com': 'tiktok',
}


def clean(value, limit=500):
    return ' '.join(str(value or '').split())[:limit] if isinstance(value, (str, int, float)) else ''


def source_url(value):
    if not isinstance(value, str):
        raise ValueError('Укажите публичную ссылку.')
    try:
        parsed = urlsplit(value.strip())
        domain = (parsed.hostname or '').lower().rstrip('.')
        port = parsed.port
    except ValueError:
        raise ValueError('Укажите публичную ссылку.') from None
    if (parsed.scheme not in ('http', 'https') or parsed.username or parsed.password or port not in (None, 80, 443)
            or not re.fullmatch(r'[a-z0-9-]+(?:\.[a-z0-9-]+)+', domain)
            or domain.endswith(('.local', '.localhost')) or re.fullmatch(r'[0-9.]+', domain)
            or len(value) > 1500 or re.search(r'[\s\\]', str(value))):
        raise ValueError('Укажите публичную ссылку вида https://example.com.')
    host = domain.removeprefix('www.')
    query = urlencode([(k, v) for k, v in parse_qsl(parsed.query) if k in ('cid', 'query_place_id', 'place_id', 'id')])
    url = urlunsplit((parsed.scheme, domain, parsed.path.rstrip('/') or '/', query, ''))
    maps = (
        ('yandex', ('yandex.ru', 'yandex.com', 'yandex.kz', 'yandex.com.tr', 'yandex.eu', 'ya.ru'), '/maps'),
        ('2gis', ('2gis.ru', '2gis.com', '2gis.kz', '2gis.am', '2gis.ae', '2gis.kg'), ''),
        ('google', ('google.com', 'google.ru', 'google.am', 'google.co.th'), '/maps'),
    )
    for provider, domains, path in maps:
        if (host in domains and parsed.path.startswith(path)) or (
            provider == 'google' and host in ('maps.app.goo.gl', 'maps.google.com', 'goo.gl')
        ):
            return 'map', provider, url
    if host in SOCIALS:
        platform = SOCIALS[host]
        if platform == 'telegram':
            slug = parsed.path.removeprefix('/s/').strip('/').split('/')[0]
            if not re.fullmatch(r'[A-Za-z0-9_]{5,32}', slug) or slug.lower() in ('share', 'login', 'proxy'):
                raise ValueError('Укажите публичный канал Telegram.')
            url = 'https://t.me/' + slug.lower()
        return 'social', platform, url
    return 'website', 'website', url


def dated(text, url):
    return {'text': text, 'url': url, 'observed_at': datetime.now(timezone.utc).isoformat()}


def read_website(url):
    from services.contact_intelligence_service import collect_public_website_intelligence

    facts, catalog, pages, links = [], [], [], {}
    audit_inputs = {}
    requested = urlsplit(url)
    page_limit = 1 if requested.path.strip('/') or requested.query else 3
    requested_host = (requested.hostname or '').removeprefix('www.')

    def visit(page, html):
        if (urlsplit(page).hostname or '').removeprefix('www.') != requested_host:
            return
        pages.append(page)
        if len(audit_inputs) < page_limit:
            audit_inputs.setdefault(page, html)
        soup = BeautifulSoup(html, 'html.parser')
        for anchor in soup.find_all('a', href=True, limit=800):
            try:
                target = urljoin(page, anchor['href'])
                if (urlsplit(target).hostname or '').removeprefix('www.') not in SOCIALS:
                    continue
                kind, provider, link = source_url(target)
            except ValueError:
                continue
            if kind == 'social':
                links.setdefault(link, {'kind': kind, 'provider': provider, 'url': link, 'found_on': page})
        description = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', attrs={'property': 'og:description'})
        if description and len(facts) < 6:
            content = clean(description.get('content'), 700)
            if content and not any(fact['text'] == content for fact in facts):
                facts.append(dated(content, page))
        for tag in soup.select('script[type="application/ld+json"]')[:20]:
            try:
                value = json.loads(tag.string or tag.get_text())
            except (ValueError, RecursionError):
                continue
            nodes = value if isinstance(value, list) else [value]
            for node in nodes[:50]:
                if not isinstance(node, dict):
                    continue
                graph = node.get('@graph')
                for item in ([node, *graph[:50]] if isinstance(graph, list) else [node]):
                    if isinstance(item, dict) and item.get('@type') in ('Service', 'Product', 'MenuItem') and len(catalog) < 40:
                        name = clean(item.get('name'), 240)
                        if name:
                            catalog.append({'name': name, 'description': clean(item.get('description'), 900), 'url': page})

    contacts, _, _ = collect_public_website_intelligence(url, observe_page=visit)
    if not pages:
        return {'status': 'unavailable', 'note': 'Сайт не удалось прочитать. Можно проверить ссылку и повторить.'}
    values = []
    for row in contacts:
        page = row.get('source_url') or ''
        if page not in pages or row.get('owner_type') == 'person':
            continue
        value = row.get('value') or row.get('normalized_value') or row.get('raw_value')
        contact = row.get('contact_type')
        if contact in ('phone', 'email') and clean(value, 250):
            values.append({'field': 'contact_' + contact, **dated(clean(value, 250), page)})
        elif isinstance(value, str) and value.startswith(('https://', 'http://')):
            try:
                kind, provider, link = source_url(value)
            except ValueError:
                continue
            if kind == 'social':
                links.setdefault(link, {'kind': kind, 'provider': provider, 'url': link, 'found_on': page})
    audit = website_seo_audit.audit_pages([{'url': page, 'html': html} for page, html in audit_inputs.items()])
    return {'status': 'ready', 'note': 'Сайт прочитан.', 'facts': facts, 'catalog': catalog,
            'profile': values[:20], 'links': list(links.values())[:15], 'website_audit': audit}


def read_social(provider, url):
    if provider != 'telegram':
        return {'status': 'link_only', 'note': 'Ссылка сохранена. Для этой площадки чтение публикаций в настройке пока недоступно.'}
    from services.knowledge_public_telegram import inspect_public_channel
    result = inspect_public_channel(url, timeout=12)
    if not result['is_public_channel']:
        return {'status': 'link_only', 'note': 'Публичные публикации по этой ссылке недоступны.'}
    facts = []
    for message in result['messages'][-5:]:
        text = clean(message.get('content_text'), 450)
        if not text:
            continue
        link = message.get('permalink') or url
        evidence = dated(text, link if link.startswith(('https://t.me/', 'http://t.me/')) else url)
        if message.get('published_at'):
            evidence['published_at'] = message['published_at'].isoformat()
        facts.append(evidence)
    return {'status': 'ready', 'note': 'Публичный канал прочитан.', 'facts': facts, 'name': clean(result.get('title'))}


def catalog_rows(raw, url):
    value = raw.get('serviceItems') or raw.get('products') or raw.get('services_json') or raw.get('services') or []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return []
    rows = []
    for row in map_card_initial_audit._flatten_services(value):
        if not isinstance(row, dict):
            continue
        structured = row.get('structuredServiceItem') or {}
        free = row.get('freeFormServiceItem') or {}
        label = free.get('label') or {}
        name = clean(row.get('name') or row.get('title') or label.get('displayName'), 240)
        if name:
            rows.append({'name': name, 'description': clean(row.get('description') or label.get('description') or structured.get('description'), 900),
                         'category': clean(row.get('category'), 140), 'url': url})
        if len(rows) == 60:
            break
    return rows


def _map_source_links(source, raw, website):
    if source.get('competitor'):
        return []
    from services.prospecting_service import ProspectingService

    links = {}

    def add(value, allowed_kinds):
        try:
            kind, provider, url = source_url(value)
        except ValueError:
            return
        if kind in allowed_kinds:
            links.setdefault(url, {'kind': kind, 'provider': provider, 'url': url, 'found_on': source['url']})

    def social_links(value):
        try:
            payload = map_card_initial_audit.record(value)
        except ValueError:
            return None
        return payload.get('social_links') if isinstance(payload, dict) else None

    if website:
        add(website if '://' in website else 'https://' + website.lstrip('/'), ('website', 'social'))
    for social in ProspectingService._collect_nested_strings([
        raw.get('telegram_url'), raw.get('whatsapp_url'), raw.get('social_links'), raw.get('messenger_links'),
        social_links(raw.get('overview')), social_links(raw.get('search_payload_json')),
    ])[:30]:
        add(social, ('social',))
    return list(links.values())[:15]


def read_map(source, snapshot, *, capture_method=None):
    provider, url = source['provider'], source['url']
    if snapshot:
        raw = snapshot
        message = ('Карточка прочитана.' if capture_method == 'apify'
                   else 'Использован сохранённый снимок этой карточки.')
    elif provider in ('yandex', '2gis') and map_card_initial_audit.public_url(provider, url):
        raw = map_card_initial_audit.initial_native_readers(content_only=True)[provider](url)
        message = 'Карточка прочитана.'
    else:
        reason = 'Для Google добавьте подключение или сначала получите снимок точной карточки.' if provider == 'google' else 'Нужна прямая ссылка на карточку компании.'
        return {'status': 'link_only', 'note': reason}
    if isinstance(raw, dict) and raw.get('error') == 'yandex_rate_limited':
        return {'status': 'unavailable', 'note': 'Яндекс временно ограничил чтение карточки. Повторите сбор позже.'}
    if not isinstance(raw, dict) or raw.get('error') or raw.get('captcha_required'):
        return {'status': 'unavailable', 'note': 'Площадка не отдала карточку. Проверьте ссылку или повторите чтение позже.'}
    title = clean(raw.get('name') or raw.get('title') or raw.get('title_or_name'), 260)
    if not title or title.casefold() == 'untitled':
        return {'status': 'unavailable', 'note': 'Парсер не подтвердил название карточки.'}
    description = clean(raw.get('description') or map_card_initial_audit.record(raw.get('profile')).get('description'), 700)
    website = clean(raw.get('website') or raw.get('site') or raw.get('websiteUri'), 500)
    profile = [{'field': field, **dated(value, url)} for field, value in (
        ('contact_phone', clean(raw.get('phone') or map_card_initial_audit.record(raw.get('phoneNumbers')).get('primaryPhone'), 100)),
        ('address', clean(raw.get('address'))),
        ('website', website),
    ) if value]
    observed_at = raw.get('updated_at') or raw.get('created_at')
    if isinstance(observed_at, datetime):
        observed_at = observed_at.isoformat()
    photos = initial_setup_photos.candidates(provider, raw) if not source.get('competitor') else []
    return {'status': 'ready', 'note': message, 'name': title, 'catalog': catalog_rows(raw, url), 'profile': profile,
            'links': _map_source_links(source, raw, website),
            'facts': [dated(description, url)] if description else [],
            'metrics': {'rating': clean(raw.get('rating'), 20), 'reviews': clean(raw.get('reviews_count'), 20)},
            'observed_at': clean(observed_at, 60), 'photo_candidates': photos,
            'capture_method': capture_method or ('snapshot' if snapshot else 'live')}
