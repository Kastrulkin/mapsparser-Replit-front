from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any


TECHNICAL_MARKERS = (
    "openclaw",
    "payload",
    "fallback",
    "preview run",
    "preflight",
    "blueprint",
    "default_local_business",
    "audit_profile",
)

PROFILE_DRIFT_MARKERS = {
    "shopping_center": ("записаться", "консультация специалиста", "цена услуги"),
    "education_children": ("пациент", "лечение", "косметолог"),
    "family_entertainment": ("пациент", "лечение", "консультация врача"),
    "travel": ("пациент", "лечение", "маникюр"),
    "financial_services": ("пациент", "лечение", "запись на услугу"),
    "repair_service": ("пациент", "лечение", "косметолог"),
    "commercial_center": ("пациент", "лечение", "запись на услугу"),
    "medical": ("скидка гарантирована", "без боли", "гарантируем лечение"),
}


def _normalize_identity(value: Any) -> str:
    return re.sub(r"[^a-zа-яё0-9]+", " ", str(value or "").lower()).strip()


def _public_text(audit: dict[str, Any]) -> str:
    fields: list[str] = [
        str(audit.get("summary_text") or ""),
        str(audit.get("health_label") or ""),
    ]
    for key in ("issue_blocks", "top_3_issues", "findings", "recommended_actions"):
        items = audit.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            for text_key in ("title", "problem", "evidence", "impact", "fix", "description"):
                fields.append(str(item.get(text_key) or ""))
    action_plan = audit.get("action_plan")
    if isinstance(action_plan, dict):
        for value in action_plan.values():
            if isinstance(value, list):
                fields.extend(str(item or "") for item in value)
            else:
                fields.append(str(value or ""))
    return " ".join(fields).lower().replace("ё", "е")


def evaluate_audit_quality(
    audit: dict[str, Any],
    *,
    expected_name: str = "",
    expected_address: str = "",
    expected_profile: str = "",
) -> dict[str, Any]:
    flags: list[dict[str, str]] = []
    public_text = _public_text(audit)
    profile = str(audit.get("audit_profile") or "").strip().lower()

    for marker in TECHNICAL_MARKERS:
        if marker in public_text:
            flags.append({"code": "technical_copy", "detail": marker})

    for marker in PROFILE_DRIFT_MARKERS.get(profile, ()):
        if marker.replace("ё", "е") in public_text:
            flags.append({"code": "industry_drift", "detail": marker})

    if expected_profile and profile != expected_profile:
        flags.append({"code": "profile_mismatch", "detail": f"{profile or 'missing'} != {expected_profile}"})

    business = audit.get("business") if isinstance(audit.get("business"), dict) else {}
    actual_name = _normalize_identity(business.get("name"))
    normalized_expected_name = _normalize_identity(expected_name)
    if normalized_expected_name and actual_name:
        similarity = SequenceMatcher(None, normalized_expected_name, actual_name).ratio()
        if similarity < 0.72:
            flags.append({"code": "business_identity_mismatch", "detail": f"name_similarity={similarity:.2f}"})

    current_state = audit.get("current_state") if isinstance(audit.get("current_state"), dict) else {}
    actual_address = _normalize_identity(current_state.get("address") or business.get("address"))
    normalized_expected_address = _normalize_identity(expected_address)
    if normalized_expected_address and actual_address:
        expected_tokens = set(normalized_expected_address.split())
        actual_tokens = set(actual_address.split())
        meaningful_tokens = {item for item in expected_tokens if len(item) > 3 or item.isdigit()}
        if meaningful_tokens and not meaningful_tokens.intersection(actual_tokens):
            flags.append({"code": "business_identity_mismatch", "detail": "address_tokens_do_not_match"})

    if not str(audit.get("summary_text") or "").strip():
        flags.append({"code": "missing_business_result", "detail": "summary_text"})
    if not isinstance(audit.get("issue_blocks"), list) or not audit.get("issue_blocks"):
        flags.append({"code": "missing_business_result", "detail": "issue_blocks"})
    if profile == "default_local_business" and expected_profile:
        flags.append({"code": "unsupported_profile_fallback", "detail": expected_profile})

    unique_flags: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for flag in flags:
        key = (flag["code"], flag["detail"])
        if key in seen:
            continue
        seen.add(key)
        unique_flags.append(flag)
    return {"passed": not unique_flags, "flags": unique_flags}
