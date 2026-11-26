"""Private PDF export of the current first-setup proposal."""
from io import BytesIO
from pathlib import Path
from urllib.parse import quote, urlencode, urlsplit
from xml.sax.saxutils import escape, quoteattr

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from services.content_plan_export import display_date


PLATFORMS = {'yandex': 'Яндекс Карты', '2gis': '2ГИС', 'google': 'Google Maps', 'vk': 'ВКонтакте', 'telegram': 'Telegram'}
SOURCE_STATUS = {'ready': 'Прочитано', 'link_only': 'Ссылка сохранена', 'unavailable': 'Данные не получены'}
FIELDS = {'name': 'Название', 'address': 'Адрес', 'city': 'Город', 'website': 'Сайт', 'contact_phone': 'Телефон', 'contact_email': 'Почта'}


def _font():
    name = 'LocalOSSetup'
    if name not in pdfmetrics.getRegisteredFontNames():
        paths = (
            '/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            '/System/Library/Fonts/Supplemental/Arial.ttf',
        )
        font = next((Path(path) for path in paths if Path(path).is_file()), None)
        if not font:
            raise RuntimeError('PDF font unavailable')
        pdfmetrics.registerFont(TTFont(name, str(font)))
    return name


def _text(value):
    return escape(''.join(c for c in str(value or '') if c in '\n\t' or ord(c) >= 32)).replace('\n', '<br/>')


def _link(label, url):
    if url:
        try:
            target = urlsplit(url)
            if target.scheme in ('https', 'http') and target.hostname and not target.username and not target.password:
                return f'<a href={quoteattr(quote(url, safe=":/?%&=#@+;,-._~"))} color="#28477a">{_text(label)}</a>'
        except ValueError:
            pass
    return _text(label)


def render_report(state):
    """Render current results on demand without persisting another copy of the business data."""
    buffer = BytesIO()
    font = _font()
    body = ParagraphStyle('body', fontName=font, fontSize=10, leading=14, spaceAfter=6, splitLongWords=True)
    small = ParagraphStyle('small', parent=body, fontSize=9, leading=12, textColor=colors.HexColor('#475569'))
    heading = ParagraphStyle('heading', parent=body, fontSize=14, leading=18, spaceBefore=12, spaceAfter=7, keepWithNext=True)
    title_style = ParagraphStyle('title', parent=heading, fontSize=24, leading=29)
    group = ParagraphStyle('entry', parent=body, spaceBefore=6, textColor=colors.HexColor('#253e61'), keepWithNext=True)
    story = []

    def paragraph(value, style=body):
        story.append(Paragraph(_text(value), style))

    def rich(html, style=body):
        story.append(Paragraph(html, style))

    def localos(path, **params):
        return 'https://localos.pro/dashboard/' + path + '?' + urlencode({'business_id': state['business_id'], **params})

    def keywords(items):
        for item in items:
            views = item.get('views')
            detail = f'{views:,} показов'.replace(',', ' ') if isinstance(views, int) else 'Частотность не подтверждена'
            paragraph(' · '.join(filter(None, [item.get('text'), detail, item.get('source'), display_date(item['dated']) if item.get('dated') else ''])), small)

    profile = state['profile']
    business_name = profile.get('name') or 'Компания'
    paragraph(business_name, title_style)
    paragraph('Первичная настройка LocalOS', heading)
    paragraph('Кабинет сохранён' if state.get('saved') else 'Черновик для согласования', small)
    context = ' · '.join(filter(None, [profile.get('city'), profile.get('address'), state.get('activity_type')]))
    if context:
        paragraph(context)
    sources = state['sources']
    services = state['services']
    queries = {item['text'].strip().casefold() for item in state['category_keywords']}
    queries.update(item['text'].strip().casefold() for service in services for item in service['keywords'])
    paragraph(f'Источники · {len(sources)}    Услуги · {len(services)}    Поисковые запросы · {len(queries)}')
    rich(' &nbsp;·&nbsp; '.join([
        _link('Профиль', localos('profile')), _link('Услуги', localos('card', tab='services')),
        _link('Поисковые запросы', localos('card', tab='keywords')), _link('Медиатека', localos('content', tab='media')),
    ]), small)

    paragraph('Карты, сайт и контакты', heading)
    if not any(item['kind'] == 'map' and item['status'] == 'ready' and not item.get('competitor') for item in sources):
        paragraph('Проверьте действующие карточки компании. Пришлите ссылки, если они уже есть.')
    if not any(item['kind'] == 'website' and not item.get('competitor') for item in sources):
        paragraph('Если у компании есть сайт, добавьте ссылку для SEO-проверки.')
    for source in sources:
        platform = PLATFORMS.get(source['provider'], {'website': 'Сайт', 'social': 'Соцсеть'}.get(source['kind'], source['provider']))
        prefix = 'Конкурент · ' if source.get('competitor') else ''
        rich(_link(prefix + platform, source.get('url')) + ' · ' + _text(SOURCE_STATUS.get(source['status'], 'Ожидает проверки')))
        audit = source.get('website_audit') or {}
        if audit.get('status') == 'ready':
            for page in audit.get('pages', []):
                rich(_link(page['url'], page['url']), small)
                for finding in page['findings']:
                    paragraph(f'{finding["title"]}. {finding["fix"]}', small)
        elif audit.get('status') == 'unavailable':
            paragraph(audit.get('note') or 'SEO-проверка сайта требует повтора.', small)
    for item in state['profile_choices']:
        if item['text'] != profile.get(item['field']):
            rich(_text(f'Уточнить {FIELDS.get(item["field"], item["field"]).lower()} · {item["text"]}') +
                 (' · ' + _link('Источник', item['url']) if item.get('url') else ''), small)
    for field in ('contact_phone', 'contact_email', 'address'):
        if not profile.get(field) and not any(item['field'] == field for item in state['profile_choices']):
            paragraph(f'Уточнить {FIELDS[field].lower()}.', small)
    if not services:
        paragraph('Добавьте подтверждённый список услуг для подготовки предложений.', small)

    photo = state.get('photo_report') or {}
    paragraph('Фото для карт', heading)
    if photo.get('status') == 'ready':
        paragraph(f'В медиатеке · {photo["library_count"]}' +
                  (' · ' + ', '.join(photo['library_categories']) if photo['library_categories'] else ''))
        for item in photo['missing']:
            paragraph(f'Доснять {item["label"].lower()}. {item["tip"]}')
        for item in photo['shortlist']:
            rich(_link(item['label'], item['image_url']) + ' · ' + _link('Источник', item['source_url']), small)
        if photo.get('review'):
            paragraph(f'Нужно уточнить содержание снимков · {len(photo["review"])}', small)
    else:
        paragraph(photo.get('note') or 'Фото ещё нужно проверить.')
    if state['facts']:
        paragraph('Факты для контента', heading)
        for item in state['facts']:
            rich(_text(item['text']) + (' · ' + _link('Источник', item['url']) if item.get('url') else ''), small)
    if state['comparisons']:
        paragraph('Сравнение с конкурентами', heading)
        for item in state['comparisons']:
            rich(_link(item['name'] or 'Конкурент', item.get('url')))
            for label, values in [('Компания', item.get('ours')), ('Конкурент', item.get('theirs'))]:
                if values:
                    paragraph(f'{label} · оценка {values.get("rating") or "—"} · отзывы {values.get("reviews") or "—"}', small)

    if services or state['category_keywords']:
        story.append(Spacer(1, 6))
        paragraph('Приложение. Услуги и поисковые запросы', heading)
        if state['category_keywords']:
            paragraph('Запросы по виду деятельности', group)
            keywords(state['category_keywords'])
        for service in services:
            paragraph(service['proposed'] or service['original'], group)
            if service.get('has_original'):
                paragraph('В каталоге · ' + service['original'], small)
                if service.get('description') and service['description'] != service.get('proposed_description'):
                    paragraph(service['description'], small)
            else:
                paragraph('Предложение для каталога', small)
            if service.get('proposed_description'):
                paragraph(service['proposed_description'])
            keywords(service['keywords'])

    def footer(canvas, document):
        canvas.setFillColor(colors.HexColor('#475569'))
        canvas.setFont(font, 9)
        canvas.drawString(42, 24, 'LocalOS')
        canvas.drawRightString(A4[0] - 42, 24, str(document.page))

    SimpleDocTemplate(buffer, pagesize=A4, title=f'{business_name} · Первичная настройка LocalOS',
                      author='LocalOS', leftMargin=42, rightMargin=42, topMargin=42, bottomMargin=42).build(
                          story, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)
    return buffer
