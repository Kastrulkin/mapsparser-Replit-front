"""LocalOS field/format rules, independent of evaluation fixtures and names."""

import re
import unicodedata

from services.pii_protection.engines import EngineResult, Finding
from services.pii_protection.name_context import contextual_names


LABELS = {
    "PERSON": r"фио|имя|full[ _-]?name|customer[ _-]?name|client[ _-]?name|name|ad soyad|الاسم",
    "ADDRESS": r"домашний адрес|адрес|home[ _-]?address|address|ev adresi|privatadresse|العنوان",
    "PASSPORT": r"паспорт|passport|pasaport|reisepass|جواز السفر",
    "BANK": r"iban|bank[ _-]?account|card[ _-]?number|номер карты|расч[её]тный сч[её]т|сч[её]т",
    "IDENTIFIER": r"customer[ _-]?id|client[ _-]?id|order[ _-]?id|идентификатор клиента|номер заказа",
    "SECRET": r"api[ _-]?(?:key|token)|access[ _-]?token|refresh[ _-]?token|client[ _-]?secret|password|token|secret|authorization|пароль|токен|секрет",
    "ORGANIZATION": r"организация|organization|organisation|company|business[ _-]?name|şirket|الشركة",
}
TYPE_MAP = {"PERSON": "PERSON", "PER": "PERSON", "NAME": "PERSON",
            "EMAIL_ADDRESS": "EMAIL", "EMAIL": "EMAIL", "PHONE_NUMBER": "PHONE", "PHONE": "PHONE",
            "CREDIT_CARD": "BANK", "IBAN_CODE": "BANK", "IBAN": "BANK", "BANK_ACCOUNT": "BANK",
            "LOCATION": "ADDRESS", "ADDRESS": "ADDRESS", "ORG": "ORGANIZATION"}
PRIORITY = {"SECRET": 10, "BANK": 9, "PASSPORT": 8, "PHONE": 7, "EMAIL": 6,
            "IDENTIFIER": 5, "ADDRESS": 4, "PERSON": 3, "ORGANIZATION": 2}
EMAIL = re.compile(r"[\w.+%-]+@[\w.-]+\.[^\W\d_]{2,}", re.UNICODE)
OBFUSCATED_EMAIL = re.compile(r"[\w.+%-]+\s*(?:\[at\]|\(at\)|\[собака\])\s*[\w-]+\s*(?:\[dot\]|\(dot\)|\[точка\])\s*[^\W\d_]{2,}", re.I)
PHONE = re.compile(r"(?<!\w)(?:\+\d|8(?=[\s(.-]))[\d\s().·*\-]{7,}\d(?!\w)")
CARD = re.compile(r"(?<!\d)(?:\d[ -]?){15}\d(?!\d)")
IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]){11,30}\b")
JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{7,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")
PRIVATE_KEY = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----.*?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", re.S)


def normalized_with_offsets(text):
    normalized = []
    offsets = []
    for index, character in enumerate(text):
        if unicodedata.category(character) == "Cf":
            continue
        for value in unicodedata.normalize("NFKC", character):
            normalized.append(value)
            offsets.append(index)
    return "".join(normalized), offsets


def protected_findings(text, native, policy="private", public_spans=()):
    if policy not in {"private", "public_geo", "content"}:
        raise ValueError("PII_POLICY_UNKNOWN")
    findings = []

    def public_soft_match(finding):
        return (policy in {"public_geo", "content"}
                and finding.kind in {"PERSON", "ADDRESS", "ORGANIZATION"}
                and any(start <= finding.start and finding.end <= end for start, end in public_spans))

    field_name = re.compile(r"^(?:" + "|".join(LABELS.values()) + r"|email|phone|телефон|telefon|الهاتف)$", re.I)
    contextual = contextual_names(text)
    known_names = {text[finding.start:finding.end] for finding in contextual}
    if len(known_names) > 256:
        raise ValueError("PII_TOO_MANY_ENTITIES")
    repeated = [Finding(match.start(), match.end(), "PERSON")
                for value in known_names
                for match in re.finditer(r"(?<!\w)" + re.escape(value) + r"(?!\w)", text)]
    for finding in list(native) + repeated:
        # A label such as "Email:" is schema vocabulary, not a person's name.
        if (field_name.fullmatch(text[finding.start:finding.end].strip())
                and re.match(r"[\"']?\s*[:=]", text[finding.end:])):
            continue
        kind = TYPE_MAP.get(finding.kind)
        if kind:
            converted = Finding(finding.start, finding.end, kind, finding.score)
            if not public_soft_match(converted):
                findings.append(converted)
    normalized, offsets = normalized_with_offsets(text)

    def add(start, end, kind):
        if end > start:
            findings.append(Finding(offsets[start], offsets[end - 1] + 1, kind))

    for kind, labels in LABELS.items():
        value = r"[^;\n<>\"}{]{1,160}"
        pattern = re.compile(r"(?<!\w)(?:" + labels + r")[\"']?\s*[:=]\s*[\"']?(?P<value>" + value + ")", re.I)
        for match in pattern.finditer(normalized):
            start, end = match.span("value")
            while end > start and normalized[end - 1] in " .,\t\r":
                end -= 1
            original_span = Finding(offsets[start], offsets[end - 1] + 1, kind) if end > start else None
            # Explicit private name/address labels and critical formats always win.
            if not (kind == "ORGANIZATION" and original_span and public_soft_match(original_span)):
                add(start, end, kind)
    for kind, pattern in (("EMAIL", EMAIL), ("EMAIL", OBFUSCATED_EMAIL),
                          ("PHONE", PHONE), ("BANK", CARD), ("BANK", IBAN),
                          ("SECRET", JWT), ("SECRET", PRIVATE_KEY)):
        for match in pattern.finditer(normalized):
            if kind == "PHONE" and sum(character.isdigit() for character in match.group()) < 9:
                continue
            add(match.start(), match.end(), kind)
    return merge_findings(text, findings)


def merge_findings(text, findings):
    """Union overlapping spans so a partial NER match cannot expose a suffix."""
    merged = []
    for item in sorted(findings, key=lambda finding: (finding.start, finding.end)):
        if not 0 <= item.start < item.end <= len(text):
            raise ValueError("PII_INVALID_SPAN")
        if merged and item.start < merged[-1].end:
            previous = merged.pop()
            kind = max((previous.kind, item.kind), key=lambda value: PRIORITY.get(value, 0))
            merged.append(Finding(previous.start, max(previous.end, item.end), kind))
        else:
            merged.append(item)
    return merged


def render(text, findings):
    """Reversible evaluation rendering only; runtime uses encrypted scoped tokens."""
    result = text
    replacements = {}
    for index, finding in reversed(list(enumerate(findings))):
        token = f"<<EVAL_{finding.kind}:{index}>>"
        replacements[token] = text[finding.start:finding.end]
        result = result[:finding.start] + token + result[finding.end:]
    return EngineResult(result, findings, replacements)
