from __future__ import annotations

import json
from typing import Any


_PLACEHOLDER_VALUES = {
    "",
    "name",
    "title",
    "category",
    "source",
    "address",
    "location",
    "phone",
    "email",
    "website",
    "rating",
    "reviews_count",
    "status",
}

_PIPELINE_STATUSES = {
    "unprocessed",
    "in_progress",
    "postponed",
    "not_relevant",
    "contacted",
    "waiting_reply",
    "second_message_sent",
    "replied",
    "converted",
    "closed_lost",
}


def _placeholder_like(value: Any) -> bool:
    if value is None:
        return False
    return str(value).strip().lower() in _PLACEHOLDER_VALUES


def _pipeline_status(lead: dict[str, Any]) -> str:
    explicit = str(lead.get("pipeline_status") or "").strip().lower()
    if explicit in _PIPELINE_STATUSES:
        return explicit
    legacy = str(lead.get("status") or "").strip().lower()
    if not legacy or legacy == "new":
        return "unprocessed"
    if legacy in {"deferred", "shortlist_rejected", "rejected", "closed"}:
        return "not_relevant"
    if legacy in {
        "shortlist_approved",
        "selected_for_outreach",
        "channel_selected",
        "draft_ready",
        "queued_for_send",
        "audited",
        "matched",
        "proposal_draft_ready",
        "proposal_approved",
        "approved_for_send",
    }:
        return "in_progress"
    if legacy in {"sent", "delivered"}:
        return "contacted"
    if legacy == "responded":
        return "replied"
    if legacy == "second_message_sent":
        return "second_message_sent"
    if legacy in {"qualified", "converted"}:
        return "converted"
    return "in_progress"


def normalize_lead_for_registry(lead: dict[str, Any]) -> dict[str, Any] | None:
    normalized = dict(lead)
    if _placeholder_like(normalized.get("name")):
        normalized["name"] = None
    if not normalized.get("name"):
        for fallback_field in ("title", "company_name", "company"):
            fallback_value = normalized.get(fallback_field)
            if fallback_value and not _placeholder_like(fallback_value):
                normalized["name"] = str(fallback_value).strip()
                break
    for field in (
        "category",
        "address",
        "location",
        "phone",
        "email",
        "website",
        "source",
        "status",
        "pipeline_status",
        "rating",
        "reviews_count",
    ):
        if _placeholder_like(normalized.get(field)):
            normalized[field] = None
    enabled_languages = normalized.get("enabled_languages")
    if isinstance(enabled_languages, str) and enabled_languages:
        try:
            normalized["enabled_languages"] = json.loads(enabled_languages)
        except Exception:
            normalized["enabled_languages"] = None
    if not normalized.get("name"):
        return None
    if not any(normalized.get(field) for field in ("name", "address", "website", "phone", "source_url")):
        return None
    normalized["pipeline_status"] = _pipeline_status(normalized)
    return normalized


def lead_matches_registry_filters(lead: dict[str, Any], filters: dict[str, Any]) -> bool:
    category = filters.get("category")
    if category and category.lower() not in (lead.get("category") or "").lower():
        return False
    city = filters.get("city")
    if city:
        haystack = " ".join(
            part for part in (lead.get("city"), lead.get("address"), lead.get("location")) if part
        ).lower()
        if city.lower() not in haystack:
            return False
    status = filters.get("status")
    if status and (lead.get("pipeline_status") or lead.get("status") or "") != status:
        return False
    for filter_name, field_name, converter, default in (
        ("min_rating", "rating", float, 0),
        ("max_rating", "rating", float, 0),
        ("min_reviews", "reviews_count", int, 0),
        ("max_reviews", "reviews_count", int, 0),
    ):
        threshold = filters.get(filter_name)
        if threshold is None:
            continue
        value = converter(lead.get(field_name) or default)
        if filter_name.startswith("min_") and value < threshold:
            return False
        if filter_name.startswith("max_") and value > threshold:
            return False
    for filter_name, field_name in (
        ("has_website", "website"),
        ("has_phone", "phone"),
        ("has_email", "email"),
    ):
        expected = filters.get(filter_name)
        if expected is not None and bool(lead.get(field_name)) != expected:
            return False
    has_messengers = filters.get("has_messengers")
    if has_messengers is not None:
        messenger_links = lead.get("messenger_links_json") or []
        if isinstance(messenger_links, str):
            try:
                messenger_links = json.loads(messenger_links)
            except Exception:
                messenger_links = []
        has_any = bool(
            lead.get("telegram_url")
            or lead.get("whatsapp_url")
            or (messenger_links if isinstance(messenger_links, list) else [])
        )
        if has_any != has_messengers:
            return False
    return True
