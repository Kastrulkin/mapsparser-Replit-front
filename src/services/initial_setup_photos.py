"""Select photos from a verified map snapshot and build an onboarding report."""
import hashlib
import io
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

from PIL import Image, ImageFilter, ImageOps, ImageStat
from urllib3.exceptions import HTTPError

from core.outbound_network import public_pinned_get


JOB_KIND = 'initial_setup_photos'
LABELS = {
    'entrance': 'Вход и ориентиры', 'interior': 'Интерьер', 'team': 'Команда',
    'process': 'Рабочий процесс', 'result': 'Примеры работ', 'product': 'Продукт',
    'bedroom': 'Спальня', 'kitchen': 'Кухня', 'bathroom': 'Санузел', 'exterior': 'Фасад',
}
TAG_GROUPS = {
    'entrance': ('enter', 'entrance', 'вход'),
    'exterior': ('exterior', 'outside', 'снаружи', 'фасад'),
    'interior': ('interior', 'inside', 'внутри', 'интерьер', 'помещение', 'зона ожидания'),
    'team': ('team', 'staff', 'команда', 'сотрудники', 'мастера'),
    'process': ('process', 'equipment', 'процесс', 'оборудование', 'за работой', 'токарная', 'образцом'),
    'result': ('result', 'beforeafter', 'результат', 'детали', 'металлический узел'),
    'product': ('goods', 'products', 'product', 'food', 'товары', 'продукт', 'ассортимент'),
    'bedroom': ('bedroom', 'спальня'), 'kitchen': ('kitchen', 'кухня'), 'bathroom': ('bathroom', 'санузел'),
}
SKIP_TAGS = {'video', 'panorama', 'panoramas', 'streetview', 'logo', 'price', 'prices', 'menu',
             'видео', 'панорама', 'логотип', 'цены', 'прайс', 'меню'}
DEFAULT_CHECKLIST = {
    'entrance': 'Снимите подход с улицы, читаемую вывеску и нужную дверь.',
    'interior': 'Снимите светлый общий план помещения, где принимают клиентов или выполняют работу.',
    'team': 'Добавьте актуальное фото команды на рабочем месте.',
    'process': 'Покажите ключевой этап работы или оказания услуги.',
    'result': 'Снимите завершённую работу крупным планом, чтобы был виден результат.',
}
MAX_CANDIDATES = 24
MAX_PHOTOS = 8
MAX_IMAGE_BYTES = 5_000_000
SUPPORTED_FORMATS = {'JPEG', 'PNG', 'WEBP'}


def _image_url(provider, value):
    if not isinstance(value, str) or len(value) > 1500 or re.search(r'[\s\\]', value):
        return ''
    try:
        parsed = urlsplit(value)
        host = parsed.hostname or ''
        if parsed.scheme != 'https' or parsed.port not in (None, 443) or parsed.username or parsed.password:
            return ''
    except ValueError:
        return ''
    path = parsed.path
    if provider == 'yandex' and host in {'avatars.mds.yandex.net', 'avatars.mdst.yandex.net'}:
        match = re.fullmatch(r'(/get-altay/[0-9]+/[a-zA-Z0-9_-]+)/[^/]+', path)
        return f'https://avatars.mds.yandex.net{match[1]}/XXXL' if match else ''
    if provider == '2gis' and (host == 'photo.2gis.com' or host.endswith('.photo.2gis.com')):
        return urlunsplit(('https', host, path, parsed.query, ''))
    if (provider == 'google' and re.fullmatch(r'lh[3456]\.googleusercontent\.com', host)
            and path.startswith(('/p/', '/gps-cs-s/'))):
        return urlunsplit(('https', host, path, parsed.query, ''))
    return ''


def _tag(value):
    return re.sub(r'[^а-яa-z\d]', '', value.casefold().replace('ё', 'е')) if isinstance(value, str) else ''


def _category(values):
    tags = {_tag(value) for value in values}
    if tags & SKIP_TAGS:
        return None
    return next((key for key, aliases in TAG_GROUPS.items() if tags.intersection(map(_tag, aliases))), '')


def _subject_category(subject):
    if not isinstance(subject, str):
        return ''
    value = subject.casefold()
    return next((key for key, aliases in TAG_GROUPS.items()
                 if any(re.search(r'\b' + re.escape(alias) + r'\b', value) for alias in aliases)), '')


def candidates(provider, raw):
    """Read only gallery fields of a matching card. Counts and cover previews are not galleries."""
    rows = {}
    for field in ('photos', 'photos_json', 'imageUrls'):
        values = raw.get(field)
        if isinstance(values, dict):
            values = values.get('items')
        if isinstance(values, str):
            try:
                values = json.loads(values)
            except ValueError:
                continue
        if not isinstance(values, list):
            continue
        for original in values[:160]:
            item = original if isinstance(original, dict) else {'url': original}
            tags = item.get('tags')
            labels = [
                value.get('id') or value.get('name') if isinstance(value, dict) else value
                for value in tags
            ] if isinstance(tags, list) else []
            category = _category([*labels, item.get('category'), item.get('type')])
            url = _image_url(provider, item.get('url') or item.get('imageUrl') or item.get('urlTemplate'))
            if not url or category is None:
                continue
            rows.setdefault(url, {'key': hashlib.sha256(url.encode()).hexdigest(), 'image_url': url, 'category': category})
            if category:
                rows[url]['category'] = category
    # Keep a representative of each known category even if many earlier photos show the same view.
    by_category = {}
    for row in rows.values():
        by_category.setdefault(row['category'], []).append(row)
    ordered = []
    for i in range(4):
        for category, photos in by_category.items():
            if category and len(photos) > i:
                ordered.append(photos[i])
    return (ordered + by_category.get('', [])[:8])[:MAX_CANDIDATES]


def inspect(candidate):
    try:
        response = public_pinned_get(candidate['image_url'], {'Accept': 'image/jpeg,image/png,image/webp'},
                                     timeout=5, max_bytes=MAX_IMAGE_BYTES + 1)
        if response.status_code != 200 or len(response.body) > MAX_IMAGE_BYTES:
            return None
        with Image.open(io.BytesIO(response.body)) as source:
            if (source.format not in SUPPORTED_FORMATS or source.width * source.height > 12_000_000
                    or min(source.size) < 480 or max(source.size) < 640 or getattr(source, 'is_animated', False)):
                return None
            frame = ImageOps.exif_transpose(source).convert('L')
            width, height = frame.size
            frame.thumbnail((192, 192))
            light = ImageStat.Stat(frame)
            detail = ImageStat.Stat(frame.filter(ImageFilter.FIND_EDGES).crop((2, 2, frame.width - 2, frame.height - 2)))
            if not (28 <= light.mean[0] <= 235) or light.stddev[0] < 13 or detail.mean[0] < 2.5:
                return None
        return {**candidate, 'hash': hashlib.sha256(response.body).hexdigest(),
                'horizontal': width >= height, 'detail': detail.mean[0]}
    except (ValueError, OSError, HTTPError, Image.DecompressionBombError):
        return None


def photo_checklist(profile, activity):
    value = ' '.join(str(item or '') for item in (profile.get('business_type'), profile.get('name'), activity)).casefold()
    if any(word in value for word in ('посуточ', 'квартир', 'short-term rental', 'apartment')):
        return {
            'interior': 'Снимите горизонтальный общий план гостиной при дневном свете для обложки.',
            'bedroom': 'Покажите спальню и спальные места.',
            'kitchen': 'Снимите кухню и доступное гостям оборудование.',
            'bathroom': 'Добавьте светлый кадр санузла.',
            'entrance': 'Покажите подход с улицы, номер дома и дверь крупным планом.',
        }
    if any(word in value for word in ('ice cream', 'морожен', 'производство', 'металлообработ')):
        return {**DEFAULT_CHECKLIST, 'product': 'Снимите готовый продукт и упаковку с читаемой этикеткой.'}
    return DEFAULT_CHECKLIST


def review_cards(cards, picks):
    selected, review, sources, seen = [], [], [], set()
    for card in cards:
        rows = [item for item in card.get('photo_candidates', []) if item['key'] not in seen]
        seen.update(item['key'] for item in rows)
        labeled = []
        for row in rows:
            item = {**row, 'card_url': card['url'], 'provider': card['provider']}
            category = picks.get(row['key'], row['category'])
            if category:
                labeled.append({**item, 'category': category})
            else:
                review.append(item)
        selected.extend(labeled)
        sources.append({'url': card['url'], 'provider': card['provider'], 'count': len(rows),
                        'status': 'sample' if rows else 'unavailable'})
    # Prioritise manual choices and diversity in the bounded download batch.
    selected.sort(key=lambda item: item['key'] not in picks)
    primary = {}
    secondary = []
    for item in selected:
        if item['category'] in primary:
            secondary.append(item)
        else:
            primary[item['category']] = item
    batch = [*primary.values(), *secondary][:MAX_CANDIDATES]
    with ThreadPoolExecutor(max_workers=4) as pool:
        checked = [item for item in pool.map(inspect, batch) if item]
    checked.sort(key=lambda item: (item['key'] not in picks, not item['horizontal'], -item['detail']))
    photos, hashes = {}, set()
    for item in checked:
        if item['category'] not in photos and item['hash'] not in hashes:
            photos[item['category']] = item
            hashes.add(item['hash'])
    return list(photos.values())[:MAX_PHOTOS], review[:8], sources, len(batch) - len(checked)


def build_report(cursor, business_id, profile, activity, selection):
    photos, review, sources, rejected = selection
    cursor.execute("""
        SELECT category, quality_score, analysis_status,
               metadata_json#>>'{selection,category}' AS selection_category,
               metadata_json#>>'{selection,subject}' AS selection_subject
        FROM photo_assets WHERE business_id=%s AND metadata_json->>'disk_import_available' IS DISTINCT FROM 'false'
    """, (business_id,))
    assets = cursor.fetchall()
    library_categories = set()
    for item in assets:
        category = item['selection_category'] or _subject_category(item['selection_subject'])
        if item.get('analysis_status') == 'analyzed' and int(item.get('quality_score') or 0) >= 35:
            category = _category([item.get('category')])
        if category in LABELS:
            library_categories.add(category)
    shortlist = [{
        'key': photo['key'], 'label': LABELS[photo['category']],
        'source_url': photo['card_url'], 'image_url': photo['image_url'],
    } for photo in photos]
    categories = library_categories | {photo['category'] for photo in photos}
    checklist = photo_checklist(profile, activity)
    cover = next((LABELS[item['category']] for item in photos if item['horizontal']
                  and item['category'] in ('interior', 'exterior', 'result', 'product')), None)
    return {
        'status': 'ready', 'checked_at': datetime.now(timezone.utc).isoformat(),
        'library_categories': [LABELS[key] for key in LABELS if key in library_categories],
        'missing': [{'label': LABELS[key], 'tip': tip} for key, tip in checklist.items() if key not in categories],
        'shortlist': shortlist, 'review': review, 'sources': sources, 'library_count': len(assets),
        'cover': cover, 'rejected': rejected,
    }
