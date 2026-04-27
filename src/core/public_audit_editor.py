from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any


SUMMARY_BLOCK_KEY = "summary"
STRONG_DEMAND_BLOCK_KEY = "strong_demand"
WEAK_DEMAND_BLOCK_KEY = "weak_demand"
WHY_BLOCK_KEY = "why"
TOP_ISSUES_BLOCK_KEY = "top_issues"
ACTION_PLAN_BLOCK_KEY = "action_plan"

EDITOR_BLOCK_KEYS = [
    SUMMARY_BLOCK_KEY,
    STRONG_DEMAND_BLOCK_KEY,
    WEAK_DEMAND_BLOCK_KEY,
    WHY_BLOCK_KEY,
    TOP_ISSUES_BLOCK_KEY,
    ACTION_PLAN_BLOCK_KEY,
]

ACTION_PLAN_SECTION_TITLES = {
    "next_24h": "Следующие 24 часа",
    "next_7d": "Следующие 7 дней",
    "ongoing": "На постоянной основе",
}


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_match_text(value: Any) -> str:
    return _normalize_text(value).lower().replace("ё", "е")


def _normalize_string_list(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    result: list[str] = []
    for item in items:
        text = _normalize_text(item)
        if text:
            result.append(text)
    return result


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        normalized = _normalize_text(item)
        if not normalized:
            continue
        lowered = normalized.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        result.append(normalized)
    return result


def _first_non_empty_list(*candidates: Any) -> list[str]:
    for candidate in candidates:
        normalized = _normalize_string_list(candidate)
        if normalized:
            return normalized
    return []


def _extract_positioning_why(page_json: dict[str, Any]) -> list[str]:
    audit = page_json.get("audit") if isinstance(page_json.get("audit"), dict) else {}
    issue_blocks = audit.get("issue_blocks") if isinstance(audit.get("issue_blocks"), list) else []
    result: list[str] = []
    for item in issue_blocks:
        if not isinstance(item, dict):
            continue
        section = _normalize_text(item.get("section")).lower()
        if section != "positioning":
            continue
        for field in ("problem", "evidence"):
            text = _normalize_text(item.get(field))
            if text:
                result.append(text)
    return _dedupe_preserve_order(result)[:5]


def _extract_slug(page_json: dict[str, Any], slug: str | None = None) -> str:
    if _normalize_text(slug):
        return _normalize_text(slug).lower()
    return _normalize_text(page_json.get("slug")).lower()


def _extract_beauty_focus_terms(page_json: dict[str, Any]) -> list[str]:
    audit = page_json.get("audit") if isinstance(page_json.get("audit"), dict) else {}
    city = _normalize_match_text(page_json.get("city"))
    candidates: list[str] = []
    for item in audit.get("search_intents_to_target") if isinstance(audit.get("search_intents_to_target"), list) else []:
        text = _normalize_text(item)
        if text:
            candidates.append(text)
    for item in audit.get("services_preview") if isinstance(audit.get("services_preview"), list) else []:
        if not isinstance(item, dict):
            continue
        text = _normalize_text(item.get("current_name"))
        if text:
            candidates.append(text)

    result: list[str] = []
    seen: set[str] = set()
    blocked_parts = {
        "салон красоты",
        "рядом",
        "по цене",
        "с ценой",
        "процедура",
        "примеры работ",
    }
    for candidate in candidates:
        lowered = _normalize_match_text(candidate)
        if city:
            lowered = lowered.replace(city, "").strip(" ,")
        if not lowered:
            continue
        if any(part in lowered for part in blocked_parts):
            continue
        if lowered in seen:
            continue
        seen.add(lowered)
        result.append(candidate.replace(page_json.get("city") or "", "").strip(" ,"))
        if len(result) >= 3:
            break
    return result


def _normalize_beauty_summary_text(text: Any) -> str:
    normalized = _normalize_text(text)
    if not normalized:
        return normalized
    return (
        normalized
        .replace("beauty-услуги", "направления услуг")
        .replace("beauty-услугу", "услугу")
        .replace("beauty-описание", "описание услуг")
    )


def _normalize_issue_blocks(issue_blocks: Any) -> list[dict[str, Any]]:
    if not isinstance(issue_blocks, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in issue_blocks:
        if not isinstance(item, dict):
            continue
        next_item = copy.deepcopy(item)
        for key in ("title", "problem", "evidence", "impact", "fix"):
            text = _normalize_text(next_item.get(key))
            if not text:
                continue
            next_item[key] = (
                text
                .replace("beauty-услуги", "ключевые услуги")
                .replace("beauty-услугу", "услугу")
                .replace("beauty-описание", "описание услуг")
            )
        normalized.append(next_item)
    return normalized


def _needs_service_count_mask(page_json: dict[str, Any]) -> bool:
    audit = page_json.get("audit") if isinstance(page_json.get("audit"), dict) else {}
    current_state = audit.get("current_state") if isinstance(audit.get("current_state"), dict) else {}
    services_preview = audit.get("services_preview") if isinstance(audit.get("services_preview"), list) else []
    services_count = int(current_state.get("services_count") or 0)
    priced_services_count = int(current_state.get("services_with_price_count") or 0)
    return services_count > 0 and priced_services_count <= 0 and len(services_preview) > 0


def normalize_public_audit_page_json(page_json: dict[str, Any], *, slug: str | None = None) -> dict[str, Any]:
    output = copy.deepcopy(page_json if isinstance(page_json, dict) else {})
    audit = output.get("audit") if isinstance(output.get("audit"), dict) else {}
    output_slug = _extract_slug(output, slug)
    audit_profile = _normalize_text(audit.get("audit_profile")).lower()

    if audit_profile == "beauty":
        focus_terms = _extract_beauty_focus_terms(output)
        strong_items = focus_terms or _first_non_empty_list(audit.get("search_intents_to_target"))
        weak_items = [
            "общий поиск «салон красоты рядом»",
            "выбор между направлениями услуг",
            "поиск услуги по цене",
        ]
        why_items = [
            "в карточке уже видны отдельные направления, но не объяснено, какие из них ключевые",
            "часть услуг выглядит как общий список, а не как понятные сценарии выбора",
            "не везде хватает цены и короткого объяснения, чем одна услуга отличается от другой",
        ]

        if output_slug == "dom-krasoty-capri-oblastnaya-ulitsa":
            strong_items = ["педикюр", "косметология", "оформление бровей"]

        audit["summary_text"] = _normalize_beauty_summary_text(audit.get("summary_text"))
        audit["search_intents_to_target"] = strong_items
        audit["weak_fit_customer_profile"] = weak_items
        audit["weak_fit_guest_profile"] = list(weak_items)
        audit["issue_blocks"] = _normalize_issue_blocks(audit.get("issue_blocks"))
        audit["top_3_issues"] = _normalize_issue_blocks(audit.get("top_3_issues"))
        audit["editor_blocks"] = normalize_editor_blocks(
            {
                "summary": {
                    "title": "Итог",
                    "body": audit.get("summary_text"),
                },
                "strong_demand": {
                    "title": "Карточка лучше всего отвечает на запросы",
                    "items": strong_items,
                },
                "weak_demand": {
                    "title": "Карточка слабее отвечает на запросы",
                    "items": weak_items,
                },
                "why": {
                    "title": "Почему",
                    "items": why_items,
                },
                "top_issues": {
                    "title": "Что исправить в первую очередь",
                    "items": audit.get("top_3_issues"),
                },
                "action_plan": {
                    "title": "План внедрения",
                    "sections": _normalize_action_plan_sections(audit.get("action_plan")),
                },
            }
        )

    if _needs_service_count_mask(output):
        current_state = audit.get("current_state") if isinstance(audit.get("current_state"), dict) else {}
        next_state = copy.deepcopy(current_state)
        next_state["services_count"] = 0
        audit["current_state"] = next_state

    output["audit"] = audit
    return output


def _normalize_top_issue_items(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    result: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = _normalize_text(item.get("title"))
        body = _normalize_text(item.get("problem") or item.get("description"))
        priority = _normalize_text(item.get("priority"))
        if not title and not body:
            continue
        result.append(
            {
                "title": title or "Проблема",
                "body": body,
                "priority": priority,
            }
        )
    return result


def _normalize_action_plan_sections(action_plan: Any) -> list[dict[str, Any]]:
    data = action_plan if isinstance(action_plan, dict) else {}
    sections: list[dict[str, Any]] = []
    for key in ("next_24h", "next_7d", "ongoing"):
        sections.append(
            {
                "key": key,
                "title": ACTION_PLAN_SECTION_TITLES[key],
                "items": _normalize_string_list(data.get(key)),
            }
        )
    return sections


def _normalize_editor_summary(block: Any) -> dict[str, Any]:
    data = block if isinstance(block, dict) else {}
    return {
        "title": _normalize_text(data.get("title")) or "Итог",
        "body": _normalize_text(data.get("body")),
    }


def _normalize_editor_string_items_block(block: Any, *, fallback_title: str) -> dict[str, Any]:
    data = block if isinstance(block, dict) else {}
    return {
        "title": _normalize_text(data.get("title")) or fallback_title,
        "items": _normalize_string_list(data.get("items")),
    }


def _normalize_editor_top_issues_block(block: Any) -> dict[str, Any]:
    data = block if isinstance(block, dict) else {}
    return {
        "title": _normalize_text(data.get("title")) or "Что исправить в первую очередь",
        "items": _normalize_top_issue_items(data.get("items")),
    }


def _normalize_editor_action_plan_block(block: Any) -> dict[str, Any]:
    data = block if isinstance(block, dict) else {}
    sections = data.get("sections") if isinstance(data.get("sections"), list) else []
    by_key: dict[str, dict[str, Any]] = {}
    for section in sections:
        if not isinstance(section, dict):
            continue
        key = _normalize_text(section.get("key"))
        if key not in ACTION_PLAN_SECTION_TITLES:
            continue
        by_key[key] = {
            "key": key,
            "title": _normalize_text(section.get("title")) or ACTION_PLAN_SECTION_TITLES[key],
            "items": _normalize_string_list(section.get("items")),
        }
    normalized_sections: list[dict[str, Any]] = []
    for key in ("next_24h", "next_7d", "ongoing"):
        current = by_key.get(key)
        normalized_sections.append(
            current
            if current
            else {
                "key": key,
                "title": ACTION_PLAN_SECTION_TITLES[key],
                "items": [],
            }
        )
    return {
        "title": _normalize_text(data.get("title")) or "План внедрения",
        "sections": normalized_sections,
    }


def normalize_editor_blocks(blocks: Any) -> dict[str, Any]:
    data = blocks if isinstance(blocks, dict) else {}
    return {
        SUMMARY_BLOCK_KEY: _normalize_editor_summary(data.get(SUMMARY_BLOCK_KEY)),
        STRONG_DEMAND_BLOCK_KEY: _normalize_editor_string_items_block(
            data.get(STRONG_DEMAND_BLOCK_KEY),
            fallback_title="Карточка лучше всего отвечает на запросы",
        ),
        WEAK_DEMAND_BLOCK_KEY: _normalize_editor_string_items_block(
            data.get(WEAK_DEMAND_BLOCK_KEY),
            fallback_title="Карточка слабее отвечает на запросы",
        ),
        WHY_BLOCK_KEY: _normalize_editor_string_items_block(
            data.get(WHY_BLOCK_KEY),
            fallback_title="Почему",
        ),
        TOP_ISSUES_BLOCK_KEY: _normalize_editor_top_issues_block(data.get(TOP_ISSUES_BLOCK_KEY)),
        ACTION_PLAN_BLOCK_KEY: _normalize_editor_action_plan_block(data.get(ACTION_PLAN_BLOCK_KEY)),
    }


def build_generated_editor_blocks(page_json: dict[str, Any]) -> dict[str, Any]:
    audit = page_json.get("audit") if isinstance(page_json.get("audit"), dict) else {}
    best_fit_customer = audit.get("best_fit_customer_profile") if isinstance(audit.get("best_fit_customer_profile"), list) else []
    best_fit_guest = audit.get("best_fit_guest_profile") if isinstance(audit.get("best_fit_guest_profile"), list) else []
    weak_fit_customer = audit.get("weak_fit_customer_profile") if isinstance(audit.get("weak_fit_customer_profile"), list) else []
    weak_fit_guest = audit.get("weak_fit_guest_profile") if isinstance(audit.get("weak_fit_guest_profile"), list) else []
    blocks = {
        SUMMARY_BLOCK_KEY: {
            "title": "Итог",
            "body": _normalize_text(audit.get("summary_text")),
        },
        STRONG_DEMAND_BLOCK_KEY: {
            "title": "Карточка лучше всего отвечает на запросы",
            "items": _first_non_empty_list(
                audit.get("search_intents_to_target"),
                best_fit_customer,
                best_fit_guest,
            ),
        },
        WEAK_DEMAND_BLOCK_KEY: {
            "title": "Карточка слабее отвечает на запросы",
            "items": _first_non_empty_list(
                weak_fit_customer,
                weak_fit_guest,
            ),
        },
        WHY_BLOCK_KEY: {
            "title": "Почему",
            "items": _extract_positioning_why(page_json),
        },
        TOP_ISSUES_BLOCK_KEY: {
            "title": "Что исправить в первую очередь",
            "items": _normalize_top_issue_items(audit.get("top_3_issues")),
        },
        ACTION_PLAN_BLOCK_KEY: {
            "title": "План внедрения",
            "sections": _normalize_action_plan_sections(audit.get("action_plan")),
        },
    }
    return normalize_editor_blocks(blocks)


def render_block_text(block_key: str, block: Any) -> str:
    data = block if isinstance(block, dict) else {}
    if block_key == SUMMARY_BLOCK_KEY:
        return "\n".join([_normalize_text(data.get("title")), _normalize_text(data.get("body"))]).strip()
    if block_key in {STRONG_DEMAND_BLOCK_KEY, WEAK_DEMAND_BLOCK_KEY, WHY_BLOCK_KEY}:
        title = _normalize_text(data.get("title"))
        items = _normalize_string_list(data.get("items"))
        return "\n".join([title, *items]).strip()
    if block_key == TOP_ISSUES_BLOCK_KEY:
        title = _normalize_text(data.get("title"))
        rows = []
        for item in _normalize_top_issue_items(data.get("items")):
            rows.append(" | ".join([item.get("title") or "", item.get("body") or "", item.get("priority") or ""]).strip(" |"))
        return "\n".join([title, *rows]).strip()
    if block_key == ACTION_PLAN_BLOCK_KEY:
        title = _normalize_text(data.get("title"))
        rows = []
        sections = data.get("sections") if isinstance(data.get("sections"), list) else []
        for section in sections:
            if not isinstance(section, dict):
                continue
            section_title = _normalize_text(section.get("title"))
            section_items = _normalize_string_list(section.get("items"))
            rows.append(section_title)
            rows.extend(section_items)
        return "\n".join([title, *rows]).strip()
    return _normalize_text(block)


def classify_edit_kind(generated_text: str, edited_text: str) -> str:
    normalized_generated = _normalize_text(generated_text)
    normalized_edited = _normalize_text(edited_text)
    if normalized_generated == normalized_edited:
        return "unchanged"
    if not normalized_generated or not normalized_edited:
        return "semantic_rewrite"
    similarity = SequenceMatcher(None, normalized_generated, normalized_edited).ratio()
    generated_lines = [line for line in normalized_generated.splitlines() if _normalize_text(line)]
    edited_lines = [line for line in normalized_edited.splitlines() if _normalize_text(line)]
    if len(generated_lines) != len(edited_lines):
        return "structure_edit"
    if similarity >= 0.93:
        return "minor_copy_edit"
    if similarity >= 0.72:
        return "structure_edit"
    return "semantic_rewrite"


def compute_editor_diff(generated_blocks: dict[str, Any], edited_blocks: dict[str, Any], published_blocks: dict[str, Any]) -> dict[str, Any]:
    diff: dict[str, Any] = {}
    for block_key in EDITOR_BLOCK_KEYS:
        generated_block = generated_blocks.get(block_key)
        edited_block = edited_blocks.get(block_key)
        published_block = published_blocks.get(block_key)
        generated_text = render_block_text(block_key, generated_block)
        edited_text = render_block_text(block_key, edited_block)
        published_text = render_block_text(block_key, published_block)
        diff[block_key] = {
            "changed_in_draft": generated_text != edited_text,
            "changed_in_published": generated_text != published_text,
            "edit_kind": classify_edit_kind(generated_text, edited_text),
            "generated_text": generated_text,
            "edited_text": edited_text,
            "published_text": published_text,
        }
    return diff


def normalize_editor_state(
    *,
    generated_page_json: dict[str, Any],
    edited_json: dict[str, Any] | None,
    published_page_json: dict[str, Any] | None,
) -> dict[str, Any]:
    generated_blocks = build_generated_editor_blocks(generated_page_json)
    edited_blocks = normalize_editor_blocks((edited_json or {}).get("blocks"))
    if not edited_json or not isinstance(edited_json, dict):
        edited_blocks = copy.deepcopy(generated_blocks)
    published_blocks = build_generated_editor_blocks(published_page_json or generated_page_json)
    return {
        "generated": generated_blocks,
        "edited": edited_blocks,
        "published": published_blocks,
        "diff": compute_editor_diff(generated_blocks, edited_blocks, published_blocks),
    }


def build_action_plan_payload_from_block(block: dict[str, Any]) -> dict[str, list[str]]:
    sections = block.get("sections") if isinstance(block.get("sections"), list) else []
    result: dict[str, list[str]] = {"next_24h": [], "next_7d": [], "ongoing": []}
    for section in sections:
        if not isinstance(section, dict):
            continue
        key = _normalize_text(section.get("key"))
        if key not in result:
            continue
        result[key] = _normalize_string_list(section.get("items"))
    return result


def apply_editor_blocks_to_page_json(page_json: dict[str, Any], blocks: dict[str, Any]) -> dict[str, Any]:
    output = copy.deepcopy(page_json if isinstance(page_json, dict) else {})
    audit = output.get("audit") if isinstance(output.get("audit"), dict) else {}
    normalized_blocks = normalize_editor_blocks(blocks)
    summary_block = normalized_blocks[SUMMARY_BLOCK_KEY]
    strong_block = normalized_blocks[STRONG_DEMAND_BLOCK_KEY]
    weak_block = normalized_blocks[WEAK_DEMAND_BLOCK_KEY]
    why_block = normalized_blocks[WHY_BLOCK_KEY]
    top_issues_block = normalized_blocks[TOP_ISSUES_BLOCK_KEY]
    action_plan_block = normalized_blocks[ACTION_PLAN_BLOCK_KEY]

    audit["summary_text"] = _normalize_text(summary_block.get("body"))
    audit["search_intents_to_target"] = _normalize_string_list(strong_block.get("items"))
    audit["weak_fit_guest_profile"] = _normalize_string_list(weak_block.get("items"))
    audit["top_3_issues"] = [
        {
            "title": _normalize_text(item.get("title")),
            "problem": _normalize_text(item.get("body")),
            "priority": _normalize_text(item.get("priority")),
        }
        for item in _normalize_top_issue_items(top_issues_block.get("items"))
    ]
    audit["action_plan"] = build_action_plan_payload_from_block(action_plan_block)
    audit["editor_blocks"] = {
        SUMMARY_BLOCK_KEY: summary_block,
        STRONG_DEMAND_BLOCK_KEY: strong_block,
        WEAK_DEMAND_BLOCK_KEY: weak_block,
        WHY_BLOCK_KEY: why_block,
        TOP_ISSUES_BLOCK_KEY: top_issues_block,
        ACTION_PLAN_BLOCK_KEY: action_plan_block,
    }
    output["audit"] = audit
    output["updated_at"] = datetime.now(timezone.utc).isoformat()
    return output


def blocks_equal(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return json.dumps(normalize_editor_blocks(left), sort_keys=True, ensure_ascii=False) == json.dumps(
        normalize_editor_blocks(right),
        sort_keys=True,
        ensure_ascii=False,
    )


def build_learning_metadata(
    *,
    page_json: dict[str, Any],
    lead_id: str,
    audit_id: str,
    block_key: str,
    edit_kind: str,
) -> dict[str, Any]:
    audit = page_json.get("audit") if isinstance(page_json.get("audit"), dict) else {}
    current_state = audit.get("current_state") if isinstance(audit.get("current_state"), dict) else {}
    parse_context = audit.get("parse_context") if isinstance(audit.get("parse_context"), dict) else {}
    services_preview = audit.get("services_preview") if isinstance(audit.get("services_preview"), list) else []
    reviews_preview = audit.get("reviews_preview") if isinstance(audit.get("reviews_preview"), list) else []
    source_context = {
        "audit_profile": _normalize_text(audit.get("audit_profile")),
        "audit_profile_label": _normalize_text(audit.get("audit_profile_label")),
        "category": _normalize_text(page_json.get("category")),
        "city": _normalize_text(page_json.get("city")),
        "source_url": _normalize_text(page_json.get("source_url")),
    }
    input_features = {
        "services_count": current_state.get("services_count"),
        "priced_services_count": current_state.get("services_with_price_count"),
        "has_description": parse_context.get("description_present"),
        "photos_count": parse_context.get("photos_count"),
        "reviews_count": current_state.get("reviews_count"),
        "service_names": [
            _normalize_text(item.get("current_name"))
            for item in services_preview
            if isinstance(item, dict) and _normalize_text(item.get("current_name"))
        ][:20],
        "top_positive": [
            _normalize_text(item.get("review"))
            for item in reviews_preview
            if isinstance(item, dict) and _normalize_text(item.get("review"))
        ][:3],
    }
    return {
        "artifact_type": "audit_block",
        "audit_id": audit_id,
        "lead_id": lead_id,
        "block": block_key,
        "edit_kind": edit_kind,
        "business_profile": _normalize_text(audit.get("audit_profile")),
        "source_context": source_context,
        "input_features": input_features,
    }
