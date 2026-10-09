"""Canonical editable profile contract shared by forms and Operator tools."""
import re
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# Column identifiers are server constants, never model-provided SQL.
FIELDS = {
    'name': {'label': 'Название', 'aliases': ['businessName', 'название'], 'max_length': 300, 'required': True, 'columns': ['name']},
    'business_type': {'label': 'Тип бизнеса', 'aliases': ['businessType', 'категория'], 'max_length': 100, 'columns': ['business_type']},
    'address': {'label': 'Адрес', 'aliases': ['адрес'], 'max_length': 1000, 'columns': ['address']},
    'city': {'label': 'Город', 'aliases': ['город'], 'max_length': 120, 'columns': ['city'], 'dependencies': ['timezone', 'coordinates']},
    'website': {'label': 'Сайт', 'aliases': ['site', 'сайт'], 'max_length': 2000, 'columns': ['site', 'website']},
    'working_hours': {'label': 'График работы', 'aliases': ['workingHours', 'график', 'часы работы'], 'max_length': 1000, 'columns': ['working_hours']},
    'contact_name': {'label': 'Контактное лицо', 'aliases': ['контактное лицо'], 'max_length': 200, 'table': 'businessprofiles'},
    'contact_phone': {'label': 'Телефон бизнеса', 'aliases': ['phone', 'телефон'], 'max_length': 100, 'table': 'businessprofiles'},
    'contact_email': {'label': 'Email бизнеса', 'aliases': ['email', 'почта'], 'max_length': 254, 'table': 'businessprofiles'},
    'currency': {'label': 'Валюта', 'aliases': ['валюта'], 'max_length': 3, 'table': 'business_finance_settings'},
    'timezone': {'label': 'Часовой пояс', 'aliases': ['часовой пояс', 'часовые пояса'], 'max_length': 100, 'table': 'business_finance_settings'},
}


def public_registry():
    return [{'key': key, 'label': spec['label'], 'aliases': spec['aliases'],
             'max_length': spec['max_length'], 'required': spec.get('required', False),
             'dependencies': spec.get('dependencies', []), 'permission': 'business.settings.write',
             'destination': 'LocalOS', 'approval_required': True} for key, spec in FIELDS.items()]


def patch_schema():
    return {'type': 'object', 'additionalProperties': False, 'minProperties': 1,
            'properties': {key: {'type': 'string', 'maxLength': spec['max_length'],
                                 'description': spec['label']} for key, spec in FIELDS.items()}}


def normalize_patch(patch):
    if not isinstance(patch, dict) or not patch:
        raise ValueError('Укажите настройки и новые значения.')
    aliases = {alias: key for key, spec in FIELDS.items() for alias in spec['aliases']}
    result = {}
    for field, value in patch.items():
        key = aliases.get(field, field)
        if key not in FIELDS:
            raise ValueError('Эта настройка не поддерживается: ' + field)
        if not isinstance(value, str):
            raise ValueError(FIELDS[key]['label'] + ': укажите текстовое значение.')
        value = value.strip()
        if len(value) > FIELDS[key]['max_length'] or (FIELDS[key].get('required') and not value):
            raise ValueError('Проверьте поле «' + FIELDS[key]['label'] + '».')
        if key in result and result[key] != value:
            raise ValueError('Переданы разные значения одного поля: ' + key)
        if key in {'address', 'city'} and (re.search(r'https?://|www\.', value, re.I)):
            raise ValueError(FIELDS[key]['label'] + ' не должен содержать ссылку.')
        if key == 'website' and value:
            if '://' not in value:
                value = 'https://' + value
            url = urlsplit(value)
            if url.scheme not in {'http', 'https'} or not url.hostname or '.' not in url.hostname or url.username or url.password or re.search(r'\s', value):
                raise ValueError('Укажите адрес сайта, например https://example.ru.')
        if key == 'contact_email' and value and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
            raise ValueError('Укажите корректный email бизнеса.')
        if key == 'currency':
            value = value.upper()
            if not re.fullmatch(r'[A-Z]{3}', value):
                raise ValueError('Укажите валюту в формате ISO, например RUB или AED.')
        if key == 'timezone':
            try:
                ZoneInfo(value)
            except (ValueError, ZoneInfoNotFoundError):
                raise ValueError('Укажите часовой пояс IANA, например Europe/Moscow.') from None
        result[key] = value
    return result
