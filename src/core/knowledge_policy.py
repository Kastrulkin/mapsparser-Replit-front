import re
from typing import Any


SENSITIVITY_CLASSES = {
    "public",
    "internal",
    "tenant_confidential",
    "personal_data",
    "shared_deidentified",
}

KNOWLEDGE_USES = {
    "market",
    "outreach",
    "localos_content",
    "client_content",
    "industry_recommendations",
    "shared_learning",
}

EXTERNAL_MODEL_ALLOWED_CLASSES = {"public", "shared_deidentified"}

_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)")
_TELEGRAM_RE = re.compile(r"(?:https?://)?t\.me/[A-Za-z0-9_]{4,}|(?<!\w)@[A-Za-z0-9_]{4,}", re.IGNORECASE)
_SECRET_RE = re.compile(
    r"(?i)\b(?:api[_ -]?key|token|secret|password|пароль|токен)\b\s*[:=]\s*[^\s,;]+"
)


class KnowledgePolicyError(ValueError):
    pass


def normalize_sensitivity_class(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in SENSITIVITY_CLASSES:
        raise KnowledgePolicyError(f"Unknown sensitivity class: {normalized or 'empty'}")
    return normalized


def normalize_allowed_uses(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    result: list[str] = []
    for raw_value in values:
        value = str(raw_value or "").strip().lower()
        if value in KNOWLEDGE_USES and value not in result:
            result.append(value)
    return result


def detect_pii_flags(text: Any) -> list[str]:
    value = str(text or "")
    flags: list[str] = []
    if _EMAIL_RE.search(value):
        flags.append("email")
    if _PHONE_RE.search(value):
        flags.append("phone")
    if _TELEGRAM_RE.search(value):
        flags.append("social_identifier")
    if _SECRET_RE.search(value):
        flags.append("secret")
    return flags


def redact_text(text: Any) -> tuple[str, list[str]]:
    value = str(text or "")
    flags = detect_pii_flags(value)
    value = _SECRET_RE.sub("[SECRET REDACTED]", value)
    value = _EMAIL_RE.sub("[EMAIL REDACTED]", value)
    value = _PHONE_RE.sub("[PHONE REDACTED]", value)
    value = _TELEGRAM_RE.sub("[SOCIAL ID REDACTED]", value)
    return value, flags


def prepare_external_model_text(
    text: Any,
    *,
    sensitivity_class: str,
    pii_flags: Any = None,
    allowed_uses: Any = None,
    purpose: str,
    source_visibility: str = "public",
) -> dict[str, Any]:
    normalized_class = normalize_sensitivity_class(sensitivity_class)
    normalized_uses = normalize_allowed_uses(allowed_uses)
    normalized_purpose = str(purpose or "").strip().lower()
    normalized_visibility = str(source_visibility or "").strip().lower()

    if normalized_purpose not in KNOWLEDGE_USES:
        raise KnowledgePolicyError("Knowledge LLM purpose is not allowed")
    if normalized_purpose not in normalized_uses:
        raise KnowledgePolicyError("Source does not allow this use")
    if normalized_visibility in {"private", "invite"}:
        raise KnowledgePolicyError("Private or invite-only sources cannot be sent to an external model")
    if normalized_class not in EXTERNAL_MODEL_ALLOWED_CLASSES:
        raise KnowledgePolicyError("Sensitivity class cannot be sent to an external model")

    redacted_text, detected_flags = redact_text(text)
    declared_flags = [str(item) for item in pii_flags] if isinstance(pii_flags, list) else []
    combined_flags = sorted(set(declared_flags + detected_flags))
    if "secret" in combined_flags:
        raise KnowledgePolicyError("Secret-like content cannot be sent to an external model")

    return {
        "text": redacted_text,
        "sensitivity_class": normalized_class,
        "pii_flags": combined_flags,
        "allowed_uses": normalized_uses,
        "purpose": normalized_purpose,
        "redacted": redacted_text != str(text or ""),
    }


def deidentify_shared_payload(payload: dict[str, Any]) -> dict[str, Any]:
    blocked_keys = {
        "business_id",
        "business_name",
        "source_id",
        "document_id",
        "permalink",
        "exact_date",
        "content_text",
        "excerpt",
        "address",
        "phone",
        "email",
    }
    cleaned: dict[str, Any] = {}
    for key, value in payload.items():
        if str(key).lower() in blocked_keys:
            continue
        if isinstance(value, dict):
            cleaned[key] = deidentify_shared_payload(value)
        elif isinstance(value, list):
            cleaned[key] = [
                deidentify_shared_payload(item) if isinstance(item, dict) else item
                for item in value
            ]
        elif isinstance(value, str):
            cleaned[key] = redact_text(value)[0]
        else:
            cleaned[key] = value
    return cleaned
