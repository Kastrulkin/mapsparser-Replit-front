"""Validate managed-promotion requests without adding a second delivery pipeline."""
import re

PROMOTION_PAGES = {
    'home': '/',
    'maps': '/prodvizhenie-na-yandex-kartah',
    'bloggers': '/lokalnye-blogery',
    'partners': '/lokalnye-partnery',
}
ATTRIBUTION_KEYS = ('utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term')


def promotion_contact_fields(data):
    """Return existing contact-email fields or raise ValueError before delivery."""
    def bounded(key, limit):
        value = data.get(key)
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise ValueError('Проверьте имя, телефон и направление заявки')
        if any(ord(char) < 32 for char in value):
            raise ValueError('Недопустимые символы в заявке')
        return value.strip()

    name = bounded('name', 100)
    phone = bounded('phone', 32)
    direction = bounded('direction', 16)
    page = bounded('page', 100)
    if PROMOTION_PAGES.get(direction) != page:
        raise ValueError('Неизвестное направление заявки')
    if not re.fullmatch(r'[+0-9() .−-]+', phone) or not 7 <= len(re.sub(r'\D', '', phone)) <= 15:
        raise ValueError('Проверьте номер телефона')
    if data.get('personal_data_consent') is not True:
        raise ValueError('Подтвердите согласие на обработку данных')
    attribution = data.get('attribution', {})
    if not isinstance(attribution, dict):
        raise ValueError('Некорректный источник заявки')
    lines = ['Заявка на продвижение с сопровождением команды LocalOS', f'Направление: {direction}', f'Страница: {page}', 'Согласие на обработку данных: получено']
    for key in ATTRIBUTION_KEYS:
        value = attribution.get(key)
        if value is None:
            continue
        if not isinstance(value, str) or len(value) > 160 or any(ord(char) < 32 for char in value):
            raise ValueError('Некорректный источник заявки')
        lines.append(f'{key}: {value}')
    return name, '', phone, '\n'.join(lines)
