from __future__ import annotations

from typing import Any, Optional


def _coerce_response_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, dict):
        for key in ("text", "message", "content", "body", "comment"):
            nested = _coerce_response_text(value.get(key))
            if nested:
                return nested
        return None
    if isinstance(value, list):
        for item in value:
            nested = _coerce_response_text(item)
            if nested:
                return nested
        return None
    text = str(value).strip()
    return text or None


def extract_review_response_text(review: Any) -> Optional[str]:
    if not isinstance(review, dict):
        return None
    for key in (
        "org_reply",
        "response_text",
        "business_comment",
        "businessComment",
        "response",
        "reply",
        "organization_response",
        "company_response",
        "owner_response",
        "owner_comment",
        "answer",
        "answers",
    ):
        text = _coerce_response_text(review.get(key))
        if text:
            return text
    return None
