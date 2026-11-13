"""Evidence-based owner classification; channel kind is separate from a human author."""
from __future__ import annotations

import json
import re
from typing import Any

IDENTITY_VERSION = 'creator-identity-v1'
PROFILE_TYPES = {'author', 'channel', 'community', 'media', 'aggregator'}


def _object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except ValueError:
            return {}
    return {}


def creator_catalog_eligible(profile: dict[str, Any]) -> bool:
    metadata = _object(profile.get('profile_metadata_json') or profile.get('metadata_json') or profile.get('metadata'))
    decision = _object(metadata.get('identity_classification'))
    return decision.get('creator_eligible') is not False


def creator_eligibility_sql(alias: str = 'profile') -> str:
    if alias not in {'profile', 'p'}:
        raise ValueError('Unsupported catalog alias')
    return f"COALESCE({alias}.metadata_json->'identity_classification'->>'creator_eligible', 'true') <> 'false'"


def classify_creator_identity(profile: dict[str, Any]) -> dict[str, Any]:
    """Confirm only self-identification; weaker signals remain review candidates."""
    metadata = _object(profile.get('metadata_json') or profile.get('metadata'))
    previous = _object(metadata.get('identity_classification') or profile.get('identity_classification'))
    if previous.get('status') == 'reviewed':
        return previous
    name = str(profile.get('display_name') or profile.get('name') or '').strip()
    description = str(profile.get('description') or '').strip()
    title = name.casefold().replace('ё', 'е')
    text = description.casefold().replace('ё', 'е')
    supplied = str(profile.get('profile_type') or '').lower()
    fallback = supplied if supplied in PROFILE_TYPES else 'channel'
    result = {'version': IDENTITY_VERSION, 'status': 'unchanged', 'owner_kind': 'unknown',
              'role': 'unknown', 'profile_type': fallback, 'creator_eligible': None, 'reasons': []}
    personal = bool(re.search(r'\b(?:я\s+(?:[а-яa-z-]+\s+){0,3}(?:блогер|автор|рассказываю|показываю|живу|делюсь|обозреваю|пропагандирую)|меня зовут|мой личный|личный (?:блог|влог)|i am|i\x27m|my name is|personal blog)\b', text))
    brand_metadata = metadata.get('official_brand_source') is True or metadata.get('source_owner_type') in {'business', 'company', 'brand'}
    publisher_title = bool(re.search(r'телеканал|телевидени|газета|журнал\b|\bновост(?:и|ной|ное|ная|ные|ного|ям|ей)\b|news\b|медиа|(?:тв|tv)\d|\b(?:тв|tv)\b', title))
    publisher_body = bool(re.search(r'телевидени|журналист|редакци|новостн|новости|телеканал|newsroom', text))
    publisher_self = bool(re.match(r'(?:[а-яa-z-]+\s+){0,3}(?:независимое медиа|новостное издание|новостное агентство|independent newsroom)\b', text))
    community_owner = bool(re.search(r'сообществ|альянс|федераци|ассоциаци|\bклуб\b|\bчат\b', title)) or bool(title and re.search(re.escape(title) + r'\s*[—–-]\s*[^.\n]{0,100}(?:альянс|федераци|ассоциаци)', text[:200]))
    community = community_owner and bool(re.search(r'турнир|соревнован|участник|сообществ|объединяем', text))
    company_self = bool(re.search(r'(?:^|[.!?\n])\s*(?:наша компания|мы\s*[—–-]?\s*(?:это\s+)?(?:компания|команда|студия|магазин|производитель)|компания\s+[^.!?\n]{1,75}(?:выполнит|предлагает|занимается|оказывает|производит)|официальный (?:канал|сайт) (?:компании|магазина|клиники|салона|бренда))', text))
    owned_clients = bool(re.search(r'\b(?:наши клиенты|наша компания|наши адреса|наши магазины|наш интернет-магазин|our company|our stores|our customers)\b', text))
    services = bool(re.search(r'строительств|остеклени|балкон|демонтаж|автосервис|ремонт\s+(?:авто|квартир|коттедж)|производств|доставк|продаж|интернет-магазин|клиник|салон\s+красот|дизайн\s+интерьер|архитектур|проектировани|проектируем', text))
    commercial_title = bool(re.search(r'строительств|балкон|автосервис|магазин|клиника|салон\s+красот|ремонт\s|стоматологи', title))
    explicit_store_title = bool(re.search(r'^(?:сеть\s+)?(?:клиника|стоматология|ветклиника|салон(?:\s+красоты)?|магазин)(?:\b|\s)', title))
    business_details = bool(re.search(r'адрес|запис[ьи]|прайс|услуг|пациент|врач|прием|клиент|ассортимент|достав|продукц|официальн', text))
    if company_self and not re.search(r'\b(?:компания|компании|магазин|производитель)\b', text):
        company_self = services or commercial_title
    operating_business = brand_metadata or company_self or (owned_clients and services) or (explicit_store_title and (services or business_details)) or (commercial_title and services and bool(re.search(r'\b(?:мы|работаем|наша|наши|компания)\b', text)))
    personal_name = bool(re.match(r'^(?:Александр|Алексей|Андрей|Антон|Артем|Артём|Владимир|Дмитрий|Евгений|Иван|Игорь|Кирилл|Максим|Михаил|Николай|Олег|Павел|Роман|Сергей|Юрий|Анна|Валерия|Вера|Виктория|Дарья|Екатерина|Елена|Ирина|Ксения|Мария|Наталья|Ольга|Светлана|Татьяна|Юлия)\s+[А-ЯЁ][а-яё]+', name))
    if operating_business and personal_name and not brand_metadata:
        return {**result, 'status': 'needs_review', 'reasons': ['personal_name_business_context']}
    if personal and not operating_business:
        return {**result, 'status': 'confirmed', 'owner_kind': 'person', 'role': 'author',
                'profile_type': 'author', 'creator_eligible': True, 'reasons': ['personal_self_description']}
    if (publisher_self or (publisher_title and publisher_body)) and not personal:
        return {**result, 'status': 'confirmed', 'owner_kind': 'organization', 'role': 'publisher',
                'profile_type': 'media', 'creator_eligible': True, 'reasons': ['editorial_self_description']}
    if community and not operating_business and not personal:
        return {**result, 'status': 'confirmed', 'owner_kind': 'organization', 'role': 'community',
                'profile_type': 'community', 'creator_eligible': True, 'reasons': ['community_self_description']}
    if operating_business and not personal:
        reasons = [key for key, yes in [('explicit_brand_owner', brand_metadata), ('company_self_description', company_self),
                   ('owned_client_services', owned_clients and services), ('commercial_title_services', commercial_title and services), ('store_title_business_details', explicit_store_title and business_details)] if yes]
        return {**result, 'status': 'confirmed', 'owner_kind': 'organization', 'role': 'commercial_business',
                'profile_type': 'channel', 'creator_eligible': False, 'reasons': reasons}
    if operating_business or commercial_title or re.search(r'\b(?:компания|интернет-магазин|corporate|official brand)\b', text):
        return {**result, 'status': 'needs_review', 'reasons': ['possible_business_owner']}
    return result
