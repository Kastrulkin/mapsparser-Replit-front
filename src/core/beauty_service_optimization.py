"""Beauty-specific service optimization rules.

The rules in this module are intentionally scoped to beauty/salon services.
Other business verticals should get their own profiles instead of reusing this
one globally.
"""

from __future__ import annotations

import re
from typing import Any


BEAUTY_FORBIDDEN_PHRASES = (
    "профессиональный",
    "профессиональная",
    "премиум",
    "премиальный",
    "натуральный",
    "натуральная",
    "натуральными",
    "эффект",
    "идеальный",
    "уникальный",
    "лучший",
    "без вреда",
    "безболезненно",
    "безопасно",
    "стойкий результат",
    "до полугода",
    "мгновенный эффект",
    "сияние кожи",
    "молодость кожи",
    "омоложение кожи",
)

BEAUTY_RISK_PROMISES = (
    "гарантированный результат",
    "гарантия результата",
    "глубокое увлажнение",
    "лифтинг кожи",
    "улучшает состояние кожи",
    "улучшает качество кожи",
    "улучшает цвет лица",
    "восстанавливает кожу",
    "восстановление кожи",
    "устраняет воспаления",
    "устраняет сухость",
    "устраняет морщины",
    "стимулирует рост волос",
    "избавит от",
    "вылечит",
    "лечит",
    "без боли",
    "без вреда",
    "мгновенный эффект",
    "стойкий результат",
)

BEAUTY_PROFILE_MARKERS = (
    "beauty",
    "beauty_salon",
    "салон красоты",
    "парикмах",
    "барбер",
    "маник",
    "педик",
    "космет",
    "бров",
    "ресниц",
    "эпиля",
    "депиля",
    "шугар",
    "визаж",
    "makeup",
)

BEAUTY_ZONE_MARKERS = (
    "бров",
    "ресниц",
    "лицо",
    "губ",
    "лоб",
    "подбород",
    "скул",
    "щеки",
    "шея",
    "декольте",
    "подмыш",
    "рук",
    "ног",
    "бедр",
    "голен",
    "бикини",
    "спин",
    "живот",
    "кожа головы",
    "головы",
    "тело",
    "тела",
)

BEAUTY_SERVICE_MARKERS = (
    "биозавив",
    "афро",
    "афрокудр",
    "ваксинг",
    "восков",
    "депиля",
    "эпиля",
    "шугар",
    "бров",
    "ресниц",
    "визаж",
    "макияж",
    "стриж",
    "окраш",
    "маник",
    "педик",
    "биоревитал",
    "мезотерап",
    "ботокс",
    "филлер",
    "пилинг",
    "чистка лица",
    "косметолог",
)


def normalize_beauty_text(value: Any) -> str:
    text = str(value or "").strip().lower().replace("ё", "е")
    text = re.sub(r"[^0-9a-zа-я\s]+", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def is_beauty_profile_text(value: Any) -> bool:
    normalized = normalize_beauty_text(value)
    return any(marker in normalized for marker in BEAUTY_PROFILE_MARKERS)


def is_beauty_service_text(value: Any) -> bool:
    normalized = normalize_beauty_text(value)
    return any(marker in normalized for marker in BEAUTY_SERVICE_MARKERS)


def is_beauty_optimization_context(
    *,
    vertical_key: Any = "",
    business_profile: Any = "",
    service_name: Any = "",
    category: Any = "",
) -> bool:
    if str(vertical_key or "").strip() == "beauty":
        return True
    joined = " ".join(
        str(item or "")
        for item in (business_profile, service_name, category)
        if str(item or "").strip()
    )
    return is_beauty_profile_text(joined) or is_beauty_service_text(joined)


def _unique(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        cleaned = str(item or "").strip(" ,.;:-–—")
        key = normalize_beauty_text(cleaned)
        if cleaned and key and key not in seen:
            result.append(cleaned)
            seen.add(key)
    return result


def extract_beauty_service_attributes(service_name: Any, source_description: Any = "") -> dict[str, list[str]]:
    source = " ".join(
        str(item or "")
        for item in (service_name, source_description)
        if str(item or "").strip()
    )
    normalized = normalize_beauty_text(source)
    attrs: dict[str, list[str]] = {
        "zone": [],
        "hair_length": [],
        "gender": [],
        "age": [],
        "product_or_drug": [],
        "dosage_or_volume": [],
        "count_or_sessions": [],
        "qualifiers": [],
        "technique_or_type": [],
    }

    if "экстра длин" in normalized:
        attrs["hair_length"].append("экстра длинные волосы")
    elif "длинные волос" in normalized or "длинные" in normalized:
        attrs["hair_length"].append("длинные волосы")
    if "средние волос" in normalized:
        attrs["hair_length"].append("средние волосы")
    if "короткие волос" in normalized:
        attrs["hair_length"].append("короткие волосы")

    if re.search(r"\bмужск", normalized):
        attrs["gender"].append("мужская")
    if re.search(r"\bженск", normalized):
        attrs["gender"].append("женская")

    for match in re.finditer(r"(\d{1,2}\s*[-–]\s*\d{1,2}\s*лет|\d{1,2}\s*лет)", source, flags=re.IGNORECASE):
        attrs["age"].append(match.group(1).strip())

    for match in re.finditer(r"(?:препарат|бренд)\s+([A-Za-zА-Яа-я0-9][A-Za-zА-Яа-я0-9\s.+-]{1,40}?)(?=\s+\d|[,;.)]|$)", source, flags=re.IGNORECASE):
        attrs["product_or_drug"].append(match.group(1).strip())

    for match in re.finditer(r"\b\d+(?:[,.]\d+)?\s*(?:ml|мл|мг|g|гр|ед|единиц[а-я]*)\b", source, flags=re.IGNORECASE):
        attrs["dosage_or_volume"].append(match.group(0).strip())

    for match in re.finditer(r"\b\d+\s*(?:зон[а-я]*|сеанс[а-я]*|процедур[а-я]*|посещени[а-я]*)\b", source, flags=re.IGNORECASE):
        attrs["count_or_sessions"].append(match.group(0).strip())

    if "афро" in normalized:
        attrs["technique_or_type"].append("афро")
    if "биозавив" in normalized:
        attrs["technique_or_type"].append("биозавивка")
    if "ваксинг" in normalized:
        attrs["technique_or_type"].append("ваксинг")
    if "восков" in normalized:
        attrs["technique_or_type"].append("восковая депиляция")

    for marker in BEAUTY_ZONE_MARKERS:
        if marker in normalized:
            attrs["zone"].append(marker)

    if "экстра длин" in normalized:
        attrs["qualifiers"].append("экстра длинные")
    if "детск" in normalized:
        attrs["qualifiers"].append("детская")

    return {key: _unique(value) for key, value in attrs.items()}


def flatten_beauty_attributes(attributes: dict[str, list[str]]) -> list[str]:
    flattened: list[str] = []
    for key in (
        "zone",
        "hair_length",
        "gender",
        "age",
        "product_or_drug",
        "dosage_or_volume",
        "count_or_sessions",
        "qualifiers",
        "technique_or_type",
    ):
        values = attributes.get(key)
        if isinstance(values, list):
            flattened.extend(values)
    return _unique(flattened)


def beauty_canonical_service_key(service_name: Any, source_description: Any = "") -> str:
    text = normalize_beauty_text(" ".join([str(service_name or ""), str(source_description or "")]))
    text = re.sub(r"\b\d+(?:[,.]\d+)?\b", "#", text)
    return text


def format_beauty_generation_context(content: Any) -> str:
    lines = [line.strip() for line in str(content or "").splitlines() if line.strip()]
    if not lines:
        return ""
    blocks: list[str] = []
    for line in lines[:20]:
        attributes = extract_beauty_service_attributes(line)
        flattened = flatten_beauty_attributes(attributes)
        if flattened:
            blocks.append(f"- {line}: сохранить атрибуты: {', '.join(flattened)}")
    if not blocks:
        return ""
    return (
        "BEAUTY ATTRIBUTE MAP:\n"
        "Эти атрибуты извлечены из исходных beauty-услуг до генерации. "
        "В optimized_name и seo_description нельзя терять или подменять указанные атрибуты.\n"
        + "\n".join(blocks)
    )


def _contains_forbidden_added_phrase(candidate: str, original: str) -> bool:
    candidate_normalized = normalize_beauty_text(candidate)
    original_normalized = normalize_beauty_text(original)
    for phrase in BEAUTY_FORBIDDEN_PHRASES:
        phrase_normalized = normalize_beauty_text(phrase)
        if phrase_normalized in candidate_normalized and phrase_normalized not in original_normalized:
            return True
    return False


def _contains_risk_promise(candidate: str, original: str) -> bool:
    candidate_normalized = normalize_beauty_text(candidate)
    original_normalized = normalize_beauty_text(original)
    for phrase in BEAUTY_RISK_PROMISES:
        phrase_normalized = normalize_beauty_text(phrase)
        if phrase_normalized in candidate_normalized and phrase_normalized not in original_normalized:
            return True
    return False


def _added_unconfirmed_medical_claim(candidate: str, original: str) -> bool:
    candidate_normalized = normalize_beauty_text(candidate)
    original_normalized = normalize_beauty_text(original)
    claim_markers = (
        "акне",
        "постакне",
        "купероз",
        "воспален",
        "морщин",
        "сухост",
        "выпадени",
        "рост волос",
        "гиалуронов",
        "коллаген",
        "эластин",
        "увлажн",
        "лифтинг",
    )
    for marker in claim_markers:
        if marker in candidate_normalized and marker not in original_normalized:
            return True
    return False


def _missing_required_attributes(candidate: str, original: str, attributes: dict[str, list[str]]) -> list[str]:
    candidate_normalized = normalize_beauty_text(candidate)
    original_normalized = normalize_beauty_text(original)
    missing: list[str] = []
    for value in flatten_beauty_attributes(attributes):
        normalized_value = normalize_beauty_text(value)
        if not normalized_value:
            continue
        if normalized_value in original_normalized and normalized_value not in candidate_normalized:
            missing.append(value)
    return missing


def _added_unconfirmed_zone(candidate: str, original: str) -> bool:
    candidate_normalized = normalize_beauty_text(candidate)
    original_normalized = normalize_beauty_text(original)
    for marker in BEAUTY_ZONE_MARKERS:
        if marker in candidate_normalized and marker not in original_normalized:
            return True
    return False


def compose_beauty_fallback_name(original_name: Any, attributes: dict[str, list[str]] | None = None) -> str:
    source = str(original_name or "").strip()
    if not source:
        return ""
    attrs = attributes if isinstance(attributes, dict) else extract_beauty_service_attributes(source)
    normalized = normalize_beauty_text(source)

    if "афро" in normalized and "биозавив" not in normalized:
        pieces = ["Биозавивка афрокудри"]
        for value in attrs.get("hair_length") or []:
            if normalize_beauty_text(value) not in normalize_beauty_text(" ".join(pieces)):
                pieces.append(value)
        return " на ".join(pieces) if len(pieces) > 1 else pieces[0]

    return source


def compose_beauty_fallback_description(optimized_name: Any, original_name: Any) -> str:
    name = str(optimized_name or original_name or "").strip()
    if not name:
        return ""
    return f"{name}: услуга по исходному формату записи."


def apply_beauty_service_guardrails(
    *,
    original_name: Any,
    optimized_name: Any,
    seo_description: Any,
    source_description: Any = "",
) -> dict[str, Any]:
    original = str(original_name or "").strip()
    source_desc = str(source_description or "").strip()
    name = str(optimized_name or "").strip()
    description = str(seo_description or "").strip()
    attributes = extract_beauty_service_attributes(original, source_desc)
    reasons: list[str] = []

    joined_original = " ".join([original, source_desc]).strip()
    joined_candidate_name = " ".join([name]).strip()
    joined_candidate_description = " ".join([description]).strip()

    if not name:
        reasons.append("empty_name")
    if name and _contains_forbidden_added_phrase(joined_candidate_name, joined_original):
        reasons.append("forbidden_name_phrase")
    if description and _contains_forbidden_added_phrase(joined_candidate_description, joined_original):
        reasons.append("forbidden_description_phrase")
    if name and _contains_risk_promise(joined_candidate_name, joined_original):
        reasons.append("risk_name_promise")
    if description and _contains_risk_promise(joined_candidate_description, joined_original):
        reasons.append("risk_description_promise")
    if name and _added_unconfirmed_medical_claim(joined_candidate_name, joined_original):
        reasons.append("added_unconfirmed_medical_claim_name")
    if description and _added_unconfirmed_medical_claim(joined_candidate_description, joined_original):
        reasons.append("added_unconfirmed_medical_claim_description")
    if name and _added_unconfirmed_zone(name, joined_original):
        reasons.append("added_unconfirmed_zone")

    missing_name_attrs = _missing_required_attributes(name, joined_original, attributes) if name else flatten_beauty_attributes(attributes)
    if missing_name_attrs:
        reasons.append("missing_name_attributes:" + ",".join(missing_name_attrs))

    if description:
        sentence_parts = [part for part in re.split(r"[.!?]+", description) if part.strip()]
        if len(sentence_parts) > 1:
            reasons.append("description_too_many_sentences")
        if len(description) > 180:
            reasons.append("description_too_long")

    if reasons:
        fallback_name = compose_beauty_fallback_name(original, attributes)
        return {
            "optimized_name": fallback_name,
            "seo_description": compose_beauty_fallback_description(fallback_name, original),
            "guardrail_reasons": reasons,
            "beauty_attributes": attributes,
            "fallback_used": True,
        }

    if not description:
        description = compose_beauty_fallback_description(name, original)

    return {
        "optimized_name": name,
        "seo_description": description,
        "guardrail_reasons": [],
        "beauty_attributes": attributes,
        "fallback_used": False,
    }
