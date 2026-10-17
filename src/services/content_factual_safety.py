"""Local checks for procedural claims; not a general semantic fact checker."""
import re
from collections.abc import Callable, Iterable

URL_PATTERN = re.compile(r'https?://[^\s<>"`]+|www\.[^\s<>"`]+', re.IGNORECASE)

PROCEDURE_FACT_CONTRACT = (
    'Название услуги или системы не подтверждает её свойства. Без прямого подтверждения в источниках '
    'не описывай стерильность, безопасность, безболезненность, ощущения, щелчки, скорость процедуры '
    'или соблюдение всех норм и требований. Не дополняй факты общими знаниями о технологии. '
    'Ссылки из источников переноси посимвольно, сохраняя путь, параметры и фрагмент.'
)


def transform_outside_urls(text: str, transform: Callable[[str], str]) -> str:
    parts = []
    offset = 0
    for match in URL_PATTERN.finditer(text):
        parts.extend((transform(text[offset:match.start()]), match.group()))
        offset = match.end()
    parts.append(transform(text[offset:]))
    return ''.join(parts)


def strip_generated_markup(text: str) -> str:
    def clean(fragment):
        fragment = re.sub(r'[*_`]+', '', fragment)
        fragment = re.sub(r'^\s*#+\s*', '', fragment, flags=re.MULTILINE)
        fragment = re.sub(r'#[\wа-яА-ЯёЁ-]+', '', fragment)
        fragment = fragment.replace('{', '').replace('}', '')
        import unicodedata
        return ''.join(char for char in fragment if unicodedata.category(char) not in {'So', 'Sk'})
    return transform_outside_urls(text, clean)


# Separate properties require separate evidence; "быстро" never licenses "стерильно".
CLAIMS = tuple((label, re.compile(pattern, re.IGNORECASE)) for label, pattern in (
    ('стерильность', r'\bстерильн\w*\b'),
    ('безопасность', r'\bбезопасн\w*\b'),
    ('безболезненность', r'\bбезболезнен\w*\b|\bбез\s+боли\b'),
    ('ощущение пощипывания', r'\bпощипыва\w*\b'),
    ('щелчок при процедуре', r'\bщ[её]лч\w*\b'),
    ('соблюдение всех требований', r'\b(?:соблюд\w*|соответств\w*)\s+(?:(?:всем?|всех|необходим\w*|установлен\w*|санитарн\w*|строг\w*)\s+){0,4}(?:требован\w*|норм\w*|стандарт\w*)\b'),
    ('скорость процедуры', r'\b(?:прокол\w*|процедур\w*|инструмент\w*)\b[^.!?\n]{0,80}\bбыстр\w*\b|\bбыстр\w*\b[^.!?\n]{0,80}\b(?:прокол\w*|процедур\w*)\b'),
))
NEGATED_SOURCE = re.compile(r'\b(?:не|нет|нельзя|запрещ\w*|неподтвержд\w*|неизвестн\w*)\b', re.IGNORECASE)


def unsupported_procedure_claims(text: str, sources: Iterable[str]) -> list[str]:
    # Rules, questions, negative evidence and URL path names cannot confirm a claim.
    statements = []
    for source in sources:
        plain = URL_PATTERN.sub('', str(source or ''))
        statements.extend(part for part in re.findall(r'[^.!?\n]+[.!?]?', plain)
                          if not part.endswith('?') and not NEGATED_SOURCE.search(part))
    plain_text = URL_PATTERN.sub('', text)
    return [f'Утверждение «{label}» не подтверждено источниками'
            for label, pattern in CLAIMS
            if pattern.search(plain_text) and not any(pattern.search(fact) for fact in statements)]


class UnsupportedContentClaims(ValueError):
    def __init__(self, issues):
        super().__init__('Текст содержит неподтверждённые утверждения')
        self.issues = issues


def validate_procedure_claims(text: str, sources: Iterable[str]) -> str:
    issues = unsupported_procedure_claims(text, sources)
    if issues:
        raise UnsupportedContentClaims(issues)
    return text
