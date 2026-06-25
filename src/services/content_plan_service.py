from __future__ import annotations

import json
import re
import uuid
import unicodedata
from datetime import date, datetime, timedelta
from typing import Any

import requests
from bs4 import BeautifulSoup

from database_manager import DatabaseManager
from core.ai_learning import ensure_ai_learning_events_table, record_ai_learning_event
from core.card_audit import build_card_audit_snapshot
from core.helpers import get_business_owner_id
from core.industry_patterns import detect_industry_key, format_industry_pattern_prompt
from core.industry_pattern_recalibration import (
    build_pattern_impact_metrics,
    format_loaded_active_industry_patterns,
    load_active_industry_patterns,
    record_industry_pattern_impact_event,
)
from core.seo_keywords import collect_ranked_keywords
from core.content_plan_generator import build_content_plan_skeleton
from services.gigachat_client import analyze_text_with_gigachat
from subscription_manager import get_allowed_content_plan_horizons, get_subscription_access


def _row_get(row: Any, key: str, index: int = 0, default: Any = None) -> Any:
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key, default)
    if hasattr(row, "keys"):
        try:
            return row[key]
        except Exception:
            return default
    try:
        return row[index]
    except Exception:
        return default


def _row_to_dict(cursor: Any, row: Any) -> dict[str, Any]:
    if not row:
        return {}
    if isinstance(row, dict):
        return dict(row)
    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}
    description = getattr(cursor, "description", None) or []
    if description and isinstance(row, (tuple, list)):
        return {
            str(column[0]): row[idx]
            for idx, column in enumerate(description)
            if idx < len(row)
        }
    return {}


def _json_ready(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    return value


def _build_learning_metrics_summary(rows: list[Any]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    totals = {
        "generated_total": 0,
        "accepted_total": 0,
        "accepted_edited_total": 0,
        "skipped_total": 0,
        "rescheduled_total": 0,
        "minor_edit_total": 0,
        "major_rewrite_total": 0,
    }
    for row in rows:
        capability = str(_row_get(row, "capability", 0, "") or "").strip()
        generated_total = int(_row_get(row, "generated_total", 1, 0) or 0)
        accepted_total = int(_row_get(row, "accepted_total", 2, 0) or 0)
        accepted_edited_total = int(_row_get(row, "accepted_edited_total", 3, 0) or 0)
        skipped_total = int(_row_get(row, "skipped_total", 4, 0) or 0)
        rescheduled_total = int(_row_get(row, "rescheduled_total", 5, 0) or 0)
        minor_edit_total = int(_row_get(row, "minor_edit_total", 6, 0) or 0)
        major_rewrite_total = int(_row_get(row, "major_rewrite_total", 7, 0) or 0)
        edited_before_accept_pct = (accepted_edited_total / accepted_total * 100.0) if accepted_total else 0.0
        items.append(
            {
                "capability": capability,
                "generated_total": generated_total,
                "accepted_total": accepted_total,
                "accepted_edited_total": accepted_edited_total,
                "skipped_total": skipped_total,
                "rescheduled_total": rescheduled_total,
                "minor_edit_total": minor_edit_total,
                "major_rewrite_total": major_rewrite_total,
                "edited_before_accept_pct": round(edited_before_accept_pct, 2),
            }
        )
        totals["generated_total"] += generated_total
        totals["accepted_total"] += accepted_total
        totals["accepted_edited_total"] += accepted_edited_total
        totals["skipped_total"] += skipped_total
        totals["rescheduled_total"] += rescheduled_total
        totals["minor_edit_total"] += minor_edit_total
        totals["major_rewrite_total"] += major_rewrite_total
    totals["edited_before_accept_pct"] = round(
        (totals["accepted_edited_total"] / totals["accepted_total"] * 100.0) if totals["accepted_total"] else 0.0,
        2,
    )
    return {
        "items": items,
        "summary": totals,
    }


def _build_learning_breakdown_summary(rows: list[Any], key_field: str, label_field: str | None = None) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for row in rows:
        key = str(_row_get(row, key_field, 0, "") or "").strip() or "unknown"
        label = str(_row_get(row, label_field or "", 1, "") or "").strip() if label_field else ""
        accepted_index = 2 if label_field else 1
        edited_index = 3 if label_field else 2
        accepted_total = int(_row_get(row, "accepted_total", accepted_index, 0) or 0)
        accepted_edited_total = int(_row_get(row, "accepted_edited_total", edited_index, 0) or 0)
        skipped_total = int(_row_get(row, "skipped_total", edited_index + 1, 0) or 0)
        rescheduled_total = int(_row_get(row, "rescheduled_total", edited_index + 2, 0) or 0)
        major_rewrite_total = int(_row_get(row, "major_rewrite_total", edited_index + 3, 0) or 0)
        draft_generated_total = int(_row_get(row, "draft_generated_total", edited_index + 4, 0) or 0)
        edited_before_accept_pct = (accepted_edited_total / accepted_total * 100.0) if accepted_total else 0.0
        item = {
            "key": key,
            "accepted_total": accepted_total,
            "accepted_edited_total": accepted_edited_total,
            "skipped_total": skipped_total,
            "rescheduled_total": rescheduled_total,
            "major_rewrite_total": major_rewrite_total,
            "draft_generated_total": draft_generated_total,
            "edited_before_accept_pct": round(edited_before_accept_pct, 2),
        }
        if label:
            item["label"] = label
        items.append(item)
    return items


def _learning_score_adjustment(
    accepted_total: int,
    accepted_edited_total: int,
    skipped_total: int = 0,
    major_rewrite_total: int = 0,
    draft_generated_total: int = 0,
) -> int:
    operational_penalty = min(28, int(skipped_total or 0) * 7 + int(major_rewrite_total or 0) * 10)
    if int(draft_generated_total or 0) > int(accepted_total or 0):
        operational_penalty += min(12, (int(draft_generated_total or 0) - int(accepted_total or 0)) * 3)
    if accepted_total < 2:
        return max(-35, min(18, -operational_penalty))
    edit_pct = (accepted_edited_total / accepted_total * 100.0) if accepted_total else 0.0
    base_adjustment = 0
    if edit_pct >= 75:
        base_adjustment = -22
    elif edit_pct >= 50:
        base_adjustment = -14
    elif edit_pct >= 25:
        base_adjustment = -6
    elif accepted_total >= 3 and edit_pct <= 5:
        base_adjustment = 8
    elif accepted_total >= 3 and edit_pct <= 15:
        base_adjustment = 4
    return max(-35, min(18, base_adjustment - operational_penalty))


def _location_quality_score_adjustment(item: dict[str, Any]) -> int:
    risk_score = float(item.get("risk_score") or 0.0)
    if risk_score >= 85:
        return -18
    if risk_score >= 60:
        return -12
    if risk_score >= 35:
        return -6
    accepted_total = int(item.get("accepted_total") or 0)
    edit_pct = float(item.get("edited_before_accept_pct") or 0.0)
    if accepted_total >= 3 and edit_pct <= 10 and int(item.get("skipped_total") or 0) == 0:
        return 5
    return 0


def _build_learning_feedback_from_breakdowns(
    source_kind_breakdown: list[dict[str, Any]],
    content_type_breakdown: list[dict[str, Any]],
    network_quality: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    def build_index(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        indexed: dict[str, dict[str, Any]] = {}
        for item in items:
            key = str(item.get("key") or "").strip()
            if not key:
                continue
            accepted_total = int(item.get("accepted_total") or 0)
            accepted_edited_total = int(item.get("accepted_edited_total") or 0)
            skipped_total = int(item.get("skipped_total") or 0)
            major_rewrite_total = int(item.get("major_rewrite_total") or 0)
            draft_generated_total = int(item.get("draft_generated_total") or 0)
            indexed[key] = {
                "accepted_total": accepted_total,
                "accepted_edited_total": accepted_edited_total,
                "edited_before_accept_pct": float(item.get("edited_before_accept_pct") or 0.0),
                "score_adjustment": _learning_score_adjustment(
                    accepted_total,
                    accepted_edited_total,
                    skipped_total,
                    major_rewrite_total,
                    draft_generated_total,
                ),
                "skipped_total": skipped_total,
                "rescheduled_total": int(item.get("rescheduled_total") or 0),
                "major_rewrite_total": major_rewrite_total,
                "draft_generated_total": draft_generated_total,
            }
        return indexed

    location_feedback: dict[str, dict[str, Any]] = {}
    for item in network_quality or []:
        key = str(item.get("key") or "").strip()
        if not key:
            continue
        location_feedback[key] = {
            "label": str(item.get("label") or "").strip(),
            "risk_score": float(item.get("risk_score") or 0.0),
            "reasons": item.get("reasons") if isinstance(item.get("reasons"), list) else [],
            "score_adjustment": _location_quality_score_adjustment(item),
            "accepted_total": int(item.get("accepted_total") or 0),
            "skipped_total": int(item.get("skipped_total") or 0),
            "major_rewrite_total": int(item.get("major_rewrite_total") or 0),
            "draft_generated_total": int(item.get("draft_generated_total") or 0),
        }

    return {
        "source_kind": build_index(source_kind_breakdown),
        "content_type": build_index(content_type_breakdown),
        "location": location_feedback,
    }


def _source_kind_insight_label(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized == "seo_keyword":
        return "SEO-темы"
    if normalized == "service":
        return "темы по услугам"
    if normalized == "transaction":
        return "темы на основе продаж"
    if normalized == "audit_signal":
        return "темы из аудита"
    if normalized == "seasonal":
        return "сезонные темы"
    return "часть тем"


def _content_type_insight_label(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized == "seo":
        return "SEO-публикации"
    if normalized == "service":
        return "публикации про услуги"
    if normalized == "sales":
        return "публикации по продажам"
    if normalized == "audit":
        return "публикации по аудиту"
    if normalized == "seasonal":
        return "сезонные публикации"
    return "публикации"


def _build_learning_quality_insights(
    source_kind_breakdown: list[dict[str, Any]],
    content_type_breakdown: list[dict[str, Any]],
    network_quality: list[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    insights: list[dict[str, str]] = []
    weak_locations = [
        item for item in network_quality or []
        if float(item.get("risk_score") or 0) >= 35
    ]
    risky_sources = [
        item for item in source_kind_breakdown
        if (
            int(item.get("accepted_total") or 0) >= 2
            and float(item.get("edited_before_accept_pct") or 0) >= 50
        )
        or int(item.get("skipped_total") or 0) > 0
        or int(item.get("major_rewrite_total") or 0) > 0
    ]
    strong_sources = [
        item for item in source_kind_breakdown
        if int(item.get("accepted_total") or 0) >= 3 and float(item.get("edited_before_accept_pct") or 0) <= 15
    ]
    risky_types = [
        item for item in content_type_breakdown
        if (
            int(item.get("accepted_total") or 0) >= 2
            and float(item.get("edited_before_accept_pct") or 0) >= 50
        )
        or int(item.get("skipped_total") or 0) > 0
        or int(item.get("major_rewrite_total") or 0) > 0
    ]
    if weak_locations:
        item = weak_locations[0]
        label = str(item.get("label") or item.get("key") or "Одна из точек").strip()
        reasons = item.get("reasons") if isinstance(item.get("reasons"), list) else []
        reason_text = "часто требуют ручной доработки"
        if "skipped_items" in reasons:
            reason_text = "часть тем пропускается, значит план не попадает в операционный ритм"
        if "major_rewrites" in reasons:
            reason_text = "часть тем переписывается существенно, значит черновики нужно делать конкретнее"
        if "drafts_not_published" in reasons:
            reason_text = "черновики создаются, но не доходят до публикации"
        insights.append(
            {
                "kind": "network_location_gap",
                "text_ru": f"{label}: {reason_text}. Генератору стоит давать более конкретные темы и CTA для этой точки.",
                "text_en": f"{label}: content needs a tighter brief and clearer CTA before publishing.",
            }
        )
    if risky_sources:
        item = risky_sources[0]
        source_reason = "чаще требуют ручной правки перед публикацией"
        if int(item.get("skipped_total") or 0) > 0:
            source_reason = "часто пропускаются, значит темы нужно делать проще и ближе к готовому поводу"
        if int(item.get("major_rewrite_total") or 0) > 0:
            source_reason = "часто переписываются по смыслу, значит нужен более конкретный brief"
        insights.append(
            {
                "kind": "needs_work",
                "text_ru": f"{_source_kind_insight_label(str(item.get('key') or ''))} {source_reason}.",
                "text_en": f"{str(item.get('key') or 'Some signals')} themes are edited more often before publishing.",
            }
        )
    if strong_sources:
        item = strong_sources[0]
        insights.append(
            {
                "kind": "works_well",
                "text_ru": f"{_source_kind_insight_label(str(item.get('key') or ''))} чаще принимают почти без правок.",
                "text_en": f"{str(item.get('key') or 'Some signals')} themes are accepted with fewer edits.",
            }
        )
    if risky_types:
        item = risky_types[0]
        type_reason = "по ним видно больше правок"
        if int(item.get("skipped_total") or 0) > 0:
            type_reason = "по ним есть пропуски, значит формат нужно упростить"
        if int(item.get("major_rewrite_total") or 0) > 0:
            type_reason = "по ним есть смысловые переписывания"
        insights.append(
            {
                "kind": "content_type_gap",
                "text_ru": f"{_content_type_insight_label(str(item.get('key') or ''))} стоит формулировать конкретнее: {type_reason}.",
                "text_en": f"{str(item.get('key') or 'Some content')} posts need more specific framing.",
            }
        )
    return insights[:4]


def _build_network_quality_summary(rows: list[Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for row in rows:
        key = str(_row_get(row, "location_scope", 0, "") or "").strip() or "current"
        label = str(_row_get(row, "location_label", 1, "") or "").strip()
        accepted_total = int(_row_get(row, "accepted_total", 2, 0) or 0)
        accepted_edited_total = int(_row_get(row, "accepted_edited_total", 3, 0) or 0)
        skipped_total = int(_row_get(row, "skipped_total", 4, 0) or 0)
        rescheduled_total = int(_row_get(row, "rescheduled_total", 5, 0) or 0)
        major_rewrite_total = int(_row_get(row, "major_rewrite_total", 6, 0) or 0)
        draft_generated_total = int(_row_get(row, "draft_generated_total", 7, 0) or 0)
        edit_pct = round((accepted_edited_total / accepted_total * 100.0) if accepted_total else 0.0, 2)
        planned_activity = accepted_total + skipped_total + rescheduled_total + major_rewrite_total + draft_generated_total
        risk_score = min(
            100,
            round(
                edit_pct
                + skipped_total * 12
                + major_rewrite_total * 18
                + max(0, draft_generated_total - accepted_total) * 5
                - accepted_total * 3,
                2,
            ),
        )
        if risk_score < 0:
            risk_score = 0
        reasons: list[str] = []
        if edit_pct >= 50:
            reasons.append("many_edits")
        if skipped_total > 0:
            reasons.append("skipped_items")
        if major_rewrite_total > 0:
            reasons.append("major_rewrites")
        if draft_generated_total > accepted_total:
            reasons.append("drafts_not_published")
        if not reasons and accepted_total > 0:
            reasons.append("stable")
        items.append(
            {
                "key": key,
                "label": label,
                "accepted_total": accepted_total,
                "accepted_edited_total": accepted_edited_total,
                "skipped_total": skipped_total,
                "rescheduled_total": rescheduled_total,
                "major_rewrite_total": major_rewrite_total,
                "draft_generated_total": draft_generated_total,
                "edited_before_accept_pct": edit_pct,
                "planned_activity_total": planned_activity,
                "risk_score": risk_score,
                "reasons": reasons,
            }
        )
    return sorted(items, key=lambda item: (float(item.get("risk_score") or 0), int(item.get("planned_activity_total") or 0)), reverse=True)


def _classify_text_edit(previous_text: str, next_text: str) -> str:
    previous = str(previous_text or "").strip()
    current = str(next_text or "").strip()
    if not previous and current:
        return "major_rewrite"
    if previous == current:
        return "unchanged"
    previous_words = set(previous.lower().split())
    current_words = set(current.lower().split())
    shared = len(previous_words & current_words)
    largest = max(len(previous_words), len(current_words), 1)
    overlap = shared / largest
    length_delta = abs(len(current) - len(previous)) / max(len(previous), 1)
    if overlap < 0.45 or length_delta > 0.55:
        return "major_rewrite"
    return "minor_edit"


def _edit_reason_from_class(edit_class: str) -> str:
    normalized = str(edit_class or "").strip()
    if normalized == "major_rewrite":
        return "semantic_rewrite_before_publish"
    if normalized == "minor_edit":
        return "copy_polish_before_publish"
    if normalized == "unchanged":
        return "no_text_change"
    return ""


def _acceptance_reason(item: dict[str, Any], edited_before_accept: bool) -> str:
    if edited_before_accept:
        return "accepted_after_manual_edit"
    source_kind = str(item.get("source_kind") or "").strip()
    if source_kind == "seo_keyword":
        return "accepted_grounded_in_search_demand"
    if source_kind == "audit_signal":
        return "accepted_from_card_weak_zone"
    if source_kind == "transaction":
        return "accepted_from_sales_signal"
    if source_kind == "service":
        return "accepted_from_service_catalog"
    return "accepted_without_manual_edit"


def _table_has_column(cursor: Any, table_name: str, column_name: str) -> bool:
    cursor.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
          AND column_name = %s
        LIMIT 1
        """,
        (str(table_name or "").lower(), str(column_name or "").lower()),
    )
    return bool(cursor.fetchone())


def _normalize_scope_type(raw_scope_type: str) -> str:
    value = str(raw_scope_type or "").strip().lower()
    if value in {"network_parent", "network_location"}:
        return value
    return "single_business"


def _scope_target_business_id(cursor: Any, business_id: str, scope_type: str, scope_target_id: str | None) -> str:
    normalized_scope = _normalize_scope_type(scope_type)
    target_id = str(scope_target_id or "").strip() or str(business_id or "").strip()
    if normalized_scope in {"network_location", "network_parent"}:
        return target_id
    return str(business_id or "").strip()


def _scope_description(scope_type: str, label: str, city: str, address: str) -> str:
    normalized_scope = _normalize_scope_type(scope_type)
    clean_label = str(label or "").strip()
    clean_city = str(city or "").strip()
    clean_address = str(address or "").strip()
    if normalized_scope == "network_parent":
        if clean_label:
            return f"Общий план для сети {clean_label}: брендовые темы, сезонные акценты и единый ритм публикаций."
        return "Общий план для всей сети: брендовые темы, сезонные акценты и единый ритм публикаций."
    if normalized_scope == "network_location":
        location_hint = clean_city or clean_address or clean_label
        if location_hint:
            return f"Локальный план для точки {location_hint}: адресные поводы, отзывы, локальный спрос и конкретные услуги."
        return "Локальный план для отдельной точки: адресные поводы, отзывы, локальный спрос и конкретные услуги."
    return "План для текущего бизнеса: новости, услуги, SEO-сценарии и регулярные обновления карточки."


def _fetch_business_row(cursor: Any, business_id: str) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT id, owner_id, name, city, address, network_id, business_type, categories,
               industry, description, site, website
        FROM businesses
        WHERE id = %s
        LIMIT 1
        """,
        (business_id,),
    )
    return _row_to_dict(cursor, cursor.fetchone())


def _resolve_scope_target_meta(cursor: Any, plan_business_id: str, scope_type: str, scope_target_id: str | None) -> dict[str, str]:
    normalized_scope = _normalize_scope_type(scope_type)
    target_id = str(scope_target_id or "").strip()
    fallback_business_id = str(plan_business_id or "").strip()
    lookup_id = target_id or fallback_business_id
    row = _fetch_business_row(cursor, lookup_id) if lookup_id else {}
    if not row and fallback_business_id and fallback_business_id != lookup_id:
        row = _fetch_business_row(cursor, fallback_business_id)
    label = str(row.get("name") or "").strip()
    city = str(row.get("city") or "").strip()
    address = str(row.get("address") or "").strip()
    if not label:
        if normalized_scope == "network_parent":
            label = "Материнская точка"
        elif normalized_scope == "network_location":
            label = "Точка сети"
        else:
            label = "Текущий бизнес"
    return {
        "scope_target_label": label,
        "scope_target_city": city,
        "scope_target_address": address,
    }


def _network_location_targets_from_context(context: dict[str, Any]) -> list[dict[str, str]]:
    scope = context.get("scope") if isinstance(context.get("scope"), dict) else {}
    scope_options = scope.get("scope_options") if isinstance(scope.get("scope_options"), list) else []
    targets: list[dict[str, str]] = []
    for item in scope_options:
        if not isinstance(item, dict):
            continue
        if str(item.get("scope_type") or "").strip() != "network_location":
            continue
        target_id = str(item.get("scope_target_id") or "").strip()
        if not target_id:
            continue
        targets.append(
            {
                "business_id": target_id,
                "label": str(item.get("label") or "").strip(),
                "city": str(item.get("city") or "").strip(),
                "address": str(item.get("address") or "").strip(),
            }
        )
    return targets


def _fetch_network_scope_options(cursor: Any, business_row: dict[str, Any]) -> list[dict[str, Any]]:
    network_id = str(business_row.get("network_id") or "").strip()
    business_id = str(business_row.get("id") or "").strip()
    if not network_id:
        return [
            {
                "scope_type": "single_business",
                "scope_target_id": business_id,
                "label": str(business_row.get("name") or "Текущий бизнес"),
                "is_current": True,
            }
        ]

    cursor.execute(
        """
        SELECT id, name, city, address
        FROM businesses
        WHERE network_id = %s OR id = %s
        ORDER BY created_at ASC, name ASC
        """,
        (network_id, network_id),
    )
    rows = cursor.fetchall() or []
    options = []
    parent_business_id = network_id
    for row in rows:
        item = _row_to_dict(cursor, row)
        item_id = str(item.get("id") or "").strip()
        if not item_id:
            continue
        is_parent = item_id == parent_business_id
        scope_type = "network_parent" if is_parent else "network_location"
        options.append(
            {
                "scope_type": scope_type,
                "scope_target_id": item_id,
                "label": str(item.get("name") or "Точка").strip() or "Точка",
                "city": str(item.get("city") or "").strip(),
                "address": str(item.get("address") or "").strip(),
                "is_parent": is_parent,
                "is_current": item_id == business_id,
            }
        )
    if not options:
        options.append(
            {
                "scope_type": "single_business",
                "scope_target_id": business_id,
                "label": str(business_row.get("name") or "Текущий бизнес"),
                "is_current": True,
            }
        )
    return options


def _fetch_services(cursor: Any, business_id: str) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT id, name, description, category, price
        FROM userservices
        WHERE business_id = %s
          AND (is_active IS TRUE OR is_active IS NULL)
        ORDER BY updated_at DESC NULLS LAST, created_at DESC
        LIMIT 100
        """,
        (business_id,),
    )
    rows = cursor.fetchall() or []
    return [
        {
            "id": str(_row_get(row, "id", 0, "") or "").strip(),
            "name": str(_row_get(row, "name", 1, "") or "").strip(),
            "description": str(_row_get(row, "description", 2, "") or "").strip(),
            "category": str(_row_get(row, "category", 3, "") or "").strip(),
            "price": str(_row_get(row, "price", 4, "") or "").strip(),
        }
        for row in rows
        if str(_row_get(row, "name", 1, "") or "").strip()
    ]


def _fetch_recent_news(cursor: Any, user_id: str, business_id: str) -> list[dict[str, Any]]:
    has_business_id = _table_has_column(cursor, "usernews", "business_id")
    if has_business_id:
        cursor.execute(
            """
            SELECT id, generated_text, approved, created_at
            FROM usernews
            WHERE user_id = %s AND business_id = %s
            ORDER BY created_at DESC
            LIMIT 20
            """,
            (user_id, business_id),
        )
    else:
        cursor.execute(
            """
            SELECT id, generated_text, approved, created_at
            FROM usernews
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT 20
            """,
            (user_id,),
        )
    rows = cursor.fetchall() or []
    return [
        {
            "id": str(_row_get(row, "id", 0, "") or "").strip(),
            "text": str(_row_get(row, "generated_text", 1, "") or "").strip(),
            "approved": bool(_row_get(row, "approved", 2, False)),
            "created_at": _row_get(row, "created_at", 3),
        }
        for row in rows
        if str(_row_get(row, "generated_text", 1, "") or "").strip()
    ]


def _fetch_map_link_count(cursor: Any, business_id: str) -> int:
    try:
        cursor.execute("SELECT to_regclass('public.businessmaplinks')")
        row = cursor.fetchone()
        if not _row_get(row, "to_regclass", 0, None):
            return 0
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM businessmaplinks
            WHERE business_id = %s
            """,
            (business_id,),
        )
        count_row = cursor.fetchone()
        return int(_row_get(count_row, "count", 0, 0) or 0)
    except Exception:
        return 0


def _fetch_sales_signals(cursor: Any, user_id: str, business_id: str) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT id, transaction_date, amount, services, notes
        FROM financialtransactions
        WHERE user_id = %s AND business_id = %s
        ORDER BY transaction_date DESC NULLS LAST, created_at DESC
        LIMIT 20
        """,
        (user_id, business_id),
    )
    rows = cursor.fetchall() or []
    signals = []
    for row in rows:
        services_raw = _row_get(row, "services", 3, None)
        services_list = []
        if services_raw:
            try:
                parsed = json.loads(services_raw) if isinstance(services_raw, str) else services_raw
                if isinstance(parsed, list):
                    services_list = [str(item).strip() for item in parsed if str(item).strip()]
            except Exception:
                services_list = []
        title = ", ".join(services_list[:3]) if services_list else str(_row_get(row, "notes", 4, "") or "").strip()
        if not title:
            title = f"Продажа на {_row_get(row, 'transaction_date', 1, '')}"
        signals.append(
            {
                "transaction_id": str(_row_get(row, "id", 0, "") or "").strip(),
                "title": title,
                "amount": float(_row_get(row, "amount", 2, 0) or 0),
                "transaction_date": _row_get(row, "transaction_date", 1),
            }
        )
    return signals


def _fetch_seo_keywords(cursor: Any, user_id: str, business_id: str) -> list[dict[str, Any]]:
    payload = collect_ranked_keywords(
        cursor,
        business_id,
        user_id,
        limit=30,
        add_city_suffix=True,
        # Content planning should stay grounded in real business context.
        # If the card has no services/business-type hints yet, returning empty
        # is safer than proposing unrelated global demand topics.
        fallback_global_when_empty_terms=False,
    )
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    return [
        {
            "keyword": str(item.get("keyword") or "").strip(),
            "views": int(item.get("views") or 0),
            "category": str(item.get("category") or "").strip(),
        }
        for item in items[:20]
        if str(item.get("keyword") or "").strip()
    ]


def _fetch_seo_keywords_isolated(user_id: str, business_id: str) -> list[dict[str, Any]]:
    seo_db = DatabaseManager()
    seo_cursor = seo_db.conn.cursor()
    try:
        return _fetch_seo_keywords(seo_cursor, user_id, business_id)
    except Exception:
        try:
            seo_db.conn.rollback()
        except Exception:
            pass
        return []
    finally:
        seo_db.close()


def _fetch_audit_signals(scope_business_id: str) -> list[dict[str, Any]]:
    try:
        audit = build_card_audit_snapshot(scope_business_id)
    except Exception:
        return []
    issue_blocks = audit.get("issue_blocks") if isinstance(audit.get("issue_blocks"), list) else []
    signals = [
        {
            "id": str(item.get("id") or "").strip(),
            "title": str(item.get("title") or "").strip(),
            "problem": str(item.get("problem") or "").strip(),
            "priority": str(item.get("priority") or "").strip(),
            "section": str(item.get("section") or "").strip(),
            "evidence": str(item.get("evidence") or "").strip(),
        }
        for item in issue_blocks[:10]
        if str(item.get("title") or item.get("problem") or "").strip()
    ]
    reasoning = audit.get("reasoning") if isinstance(audit.get("reasoning"), dict) else {}
    search_intents = (
        reasoning.get("search_intents_to_target")
        if isinstance(reasoning.get("search_intents_to_target"), list)
        else audit.get("search_intents_to_target")
    )
    if isinstance(search_intents, list):
        for intent in search_intents[:4]:
            clean_intent = str(intent or "").strip()
            if not clean_intent:
                continue
            signals.append(
                {
                    "id": f"search_intent:{clean_intent}",
                    "title": _search_intent_content_title(clean_intent),
                    "problem": _search_intent_content_problem(clean_intent),
                    "priority": "medium",
                    "section": "search",
                    "evidence": clean_intent,
                }
            )
    return signals


def _search_intent_content_title(intent: str) -> str:
    clean = str(intent or "").strip()
    normalized = clean.lower()
    if any(marker in normalized for marker in ("цен", "стоимост", "прайс", "пример", "работ", "фото")):
        return "Показать цену и примеры работ"
    if any(marker in normalized for marker in ("рядом", "поблизости", "около", "возле")):
        return f"Почему выбрать вас по запросу «{clean}»" if clean else "Объяснить, почему выбрать вас рядом"
    if clean:
        return f"Ответить на запрос клиента: {clean}"
    return "Ответить на важный поисковый запрос"


def _search_intent_content_problem(intent: str) -> str:
    clean = str(intent or "").strip()
    normalized = clean.lower()
    if any(marker in normalized for marker in ("цен", "стоимост", "прайс", "пример", "работ", "фото")):
        return "Клиенту не хватает цены, примеров результата и понятного следующего шага."
    if clean:
        return f"Карточке нужен понятный ответ на запрос клиента: {clean}."
    return "Карточке нужен отдельный понятный ответ под этот сценарий выбора."


def _build_planning_readiness(
    *,
    map_links_count: int,
    services_count: int,
    seo_keywords_count: int,
    sales_signals_count: int,
    audit_signals_count: int,
) -> dict[str, Any]:
    missing_inputs: list[str] = []
    if map_links_count <= 0:
        missing_inputs.append("map_links")
    if services_count <= 0:
        missing_inputs.append("services")
    if seo_keywords_count <= 0:
        missing_inputs.append("seo_keywords")

    return {
        "map_links_count": int(map_links_count or 0),
        "has_map_links": map_links_count > 0,
        "has_services": services_count > 0,
        "has_seo_keywords": seo_keywords_count > 0,
        "has_sales_signals": sales_signals_count > 0,
        "has_audit_signals": audit_signals_count > 0,
        "missing_inputs": missing_inputs,
        "is_grounded_for_search": map_links_count > 0 and services_count > 0 and seo_keywords_count > 0,
    }


def _load_content_plan_learning_feedback(cursor: Any, business_id: str, window_days: int = 90) -> dict[str, Any]:
    try:
        normalized_window = max(1, min(int(window_days or 90), 365))
        ensure_ai_learning_events_table(cursor.connection)
        cursor.execute(
            """
            SELECT
                COALESCE(NULLIF(metadata_json->>'source_kind', ''), 'unknown') AS source_kind,
                COUNT(*) FILTER (WHERE capability = 'content_plan.publish' AND event_type = 'accepted') AS accepted_total,
                COUNT(*) FILTER (
                    WHERE capability = 'content_plan.publish'
                      AND event_type = 'accepted'
                      AND COALESCE(edited_before_accept, FALSE) = TRUE
                ) AS accepted_edited_total,
                COUNT(*) FILTER (WHERE capability = 'content_plan.item' AND event_type = 'skipped') AS skipped_total,
                COUNT(*) FILTER (WHERE capability = 'content_plan.item' AND event_type = 'rescheduled') AS rescheduled_total,
                COUNT(*) FILTER (WHERE capability = 'content_plan.item' AND event_type = 'major_rewrite') AS major_rewrite_total,
                COUNT(*) FILTER (WHERE capability = 'content_plan.draft' AND event_type = 'generated') AS draft_generated_total
            FROM ailearningevents
            WHERE business_id = NULLIF(%s, '')::uuid
              AND capability LIKE 'content_plan.%%'
              AND created_at >= NOW() - (%s * INTERVAL '1 day')
            GROUP BY source_kind
            HAVING
                COUNT(*) FILTER (WHERE capability = 'content_plan.publish' AND event_type = 'accepted') > 0
                OR COUNT(*) FILTER (WHERE capability = 'content_plan.item' AND event_type IN ('skipped', 'rescheduled', 'major_rewrite')) > 0
                OR COUNT(*) FILTER (WHERE capability = 'content_plan.draft' AND event_type = 'generated') > 0
            """,
            (str(business_id or "").strip(), normalized_window),
        )
        source_kind_breakdown = _build_learning_breakdown_summary(cursor.fetchall() or [], "source_kind")
        cursor.execute(
            """
            SELECT
                COALESCE(NULLIF(metadata_json->>'content_type', ''), 'unknown') AS content_type,
                COUNT(*) FILTER (WHERE capability = 'content_plan.publish' AND event_type = 'accepted') AS accepted_total,
                COUNT(*) FILTER (
                    WHERE capability = 'content_plan.publish'
                      AND event_type = 'accepted'
                      AND COALESCE(edited_before_accept, FALSE) = TRUE
                ) AS accepted_edited_total,
                COUNT(*) FILTER (WHERE capability = 'content_plan.item' AND event_type = 'skipped') AS skipped_total,
                COUNT(*) FILTER (WHERE capability = 'content_plan.item' AND event_type = 'rescheduled') AS rescheduled_total,
                COUNT(*) FILTER (WHERE capability = 'content_plan.item' AND event_type = 'major_rewrite') AS major_rewrite_total,
                COUNT(*) FILTER (WHERE capability = 'content_plan.draft' AND event_type = 'generated') AS draft_generated_total
            FROM ailearningevents
            WHERE business_id = NULLIF(%s, '')::uuid
              AND capability LIKE 'content_plan.%%'
              AND created_at >= NOW() - (%s * INTERVAL '1 day')
            GROUP BY content_type
            HAVING
                COUNT(*) FILTER (WHERE capability = 'content_plan.publish' AND event_type = 'accepted') > 0
                OR COUNT(*) FILTER (WHERE capability = 'content_plan.item' AND event_type IN ('skipped', 'rescheduled', 'major_rewrite')) > 0
                OR COUNT(*) FILTER (WHERE capability = 'content_plan.draft' AND event_type = 'generated') > 0
            """,
            (str(business_id or "").strip(), normalized_window),
        )
        content_type_breakdown = _build_learning_breakdown_summary(cursor.fetchall() or [], "content_type")
        cursor.execute(
            """
            SELECT
                COALESCE(NULLIF(metadata_json->>'location_scope', ''), 'current') AS location_scope,
                COALESCE(NULLIF(metadata_json->>'location_label', ''), '') AS location_label,
                COUNT(*) FILTER (WHERE capability = 'content_plan.publish' AND event_type = 'accepted') AS accepted_total,
                COUNT(*) FILTER (
                    WHERE capability = 'content_plan.publish'
                      AND event_type = 'accepted'
                      AND COALESCE(edited_before_accept, FALSE) = TRUE
                ) AS accepted_edited_total,
                COUNT(*) FILTER (WHERE capability = 'content_plan.item' AND event_type = 'skipped') AS skipped_total,
                COUNT(*) FILTER (WHERE capability = 'content_plan.item' AND event_type = 'rescheduled') AS rescheduled_total,
                COUNT(*) FILTER (WHERE capability = 'content_plan.item' AND event_type = 'major_rewrite') AS major_rewrite_total,
                COUNT(*) FILTER (WHERE capability = 'content_plan.draft' AND event_type = 'generated') AS draft_generated_total
            FROM ailearningevents
            WHERE business_id = NULLIF(%s, '')::uuid
              AND capability LIKE 'content_plan.%%'
              AND created_at >= NOW() - (%s * INTERVAL '1 day')
            GROUP BY location_scope, location_label
            HAVING
                COUNT(*) FILTER (WHERE capability = 'content_plan.publish' AND event_type = 'accepted') > 0
                OR COUNT(*) FILTER (WHERE capability = 'content_plan.item' AND event_type IN ('skipped', 'rescheduled', 'major_rewrite')) > 0
                OR COUNT(*) FILTER (WHERE capability = 'content_plan.draft' AND event_type = 'generated') > 0
            """,
            (str(business_id or "").strip(), normalized_window),
        )
        network_quality = _build_network_quality_summary(cursor.fetchall() or [])
        return _build_learning_feedback_from_breakdowns(source_kind_breakdown, content_type_breakdown, network_quality)
    except Exception:
        return {"source_kind": {}, "content_type": {}, "location": {}}


def _record_content_plan_event(
    *,
    conn: Any,
    user_id: str,
    business_id: str,
    capability: str,
    event_type: str,
    accepted: bool | None = None,
    edited_before_accept: bool | None = None,
    outcome: str | None = None,
    draft_text: str | None = None,
    final_text: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    try:
        record_ai_learning_event(
            capability=capability,
            event_type=event_type,
            intent="operations",
            user_id=user_id,
            business_id=business_id,
            accepted=accepted,
            edited_before_accept=edited_before_accept,
            outcome=outcome,
            draft_text=draft_text,
            final_text=final_text,
            metadata=metadata or {},
            conn=conn,
        )
    except Exception:
        return


def ensure_content_plan_tables(cursor: Any) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS contentplans (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            network_id TEXT,
            scope_type TEXT NOT NULL DEFAULT 'single_business',
            scope_target_id TEXT,
            title TEXT NOT NULL,
            period_days INTEGER NOT NULL,
            period_start DATE NOT NULL,
            period_end DATE NOT NULL,
            plan_status TEXT NOT NULL DEFAULT 'generated',
            generation_mode TEXT NOT NULL DEFAULT 'manual',
            input_snapshot_json JSONB,
            generated_plan_json JSONB,
            edited_plan_json JSONB,
            published_plan_json JSONB,
            created_by TEXT REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS contentplanitems (
            id TEXT PRIMARY KEY,
            plan_id TEXT NOT NULL REFERENCES contentplans(id) ON DELETE CASCADE,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            scheduled_for DATE NOT NULL,
            content_type TEXT NOT NULL DEFAULT 'news',
            theme TEXT NOT NULL,
            goal TEXT,
            source_kind TEXT,
            source_ref TEXT,
            seo_keyword TEXT,
            service_id TEXT,
            transaction_id TEXT,
            seo_views INTEGER NOT NULL DEFAULT 0,
            location_scope TEXT,
            draft_text TEXT,
            status TEXT NOT NULL DEFAULT 'planned',
            usernews_id TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def _ensure_usernews_table(cursor: Any) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS usernews (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            service_id TEXT,
            source_text TEXT,
            generated_text TEXT NOT NULL,
            approved INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute("ALTER TABLE usernews ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP")
    cursor.execute("ALTER TABLE usernews ADD COLUMN IF NOT EXISTS business_id TEXT")
    cursor.execute("ALTER TABLE usernews ADD COLUMN IF NOT EXISTS original_generated_text TEXT")
    cursor.execute("ALTER TABLE usernews ADD COLUMN IF NOT EXISTS edited_before_approve BOOLEAN DEFAULT FALSE")
    cursor.execute("ALTER TABLE usernews ADD COLUMN IF NOT EXISTS prompt_key TEXT")
    cursor.execute("ALTER TABLE usernews ADD COLUMN IF NOT EXISTS prompt_version TEXT")


def _build_scope_business_context(cursor: Any, business_row: dict[str, Any], scope_type: str, scope_target_id: str | None) -> dict[str, Any]:
    scope_business_id = _scope_target_business_id(cursor, str(business_row.get("id") or ""), scope_type, scope_target_id)
    scope_business_row = _fetch_business_row(cursor, scope_business_id)
    if not scope_business_row:
        return business_row
    return scope_business_row


def _scope_context_business_ids(cursor: Any, business_row: dict[str, Any], scope_type: str, scope_target_id: str | None) -> list[str]:
    normalized_scope = _normalize_scope_type(scope_type)
    if normalized_scope != "network_parent":
        scope_business_id = _scope_target_business_id(
            cursor,
            str(business_row.get("id") or ""),
            normalized_scope,
            scope_target_id,
        )
        return [scope_business_id] if scope_business_id else []

    network_id = (
        str(scope_target_id or "").strip()
        or str(business_row.get("network_id") or "").strip()
        or str(business_row.get("id") or "").strip()
    )
    if not network_id:
        return []
    try:
        cursor.execute(
            """
            SELECT id
            FROM businesses
            WHERE network_id = %s OR id = %s
            ORDER BY created_at ASC, name ASC
            """,
            (network_id, network_id),
        )
        rows = cursor.fetchall() or []
    except Exception:
        rows = []
    ids: list[str] = []
    for row in rows:
        current_id = str(_row_get(row, "id", 0, "") or "").strip()
        if current_id and current_id not in ids:
            ids.append(current_id)
    if network_id not in ids:
        ids.insert(0, network_id)
    return ids


def _fetch_map_link_count_for_businesses(cursor: Any, business_ids: list[str]) -> int:
    clean_ids = [str(item or "").strip() for item in business_ids if str(item or "").strip()]
    if not clean_ids:
        return 0
    if len(clean_ids) == 1:
        return _fetch_map_link_count(cursor, clean_ids[0])
    try:
        cursor.execute("SELECT to_regclass('public.businessmaplinks')")
        row = cursor.fetchone()
        if not _row_get(row, "to_regclass", 0, None):
            return 0
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM businessmaplinks
            WHERE business_id = ANY(%s)
            """,
            (clean_ids,),
        )
        count_row = cursor.fetchone()
        return int(_row_get(count_row, "count", 0, 0) or 0)
    except Exception:
        return 0


def _fetch_services_for_businesses(cursor: Any, business_ids: list[str]) -> list[dict[str, Any]]:
    clean_ids = [str(item or "").strip() for item in business_ids if str(item or "").strip()]
    if not clean_ids:
        return []
    if len(clean_ids) == 1:
        return _fetch_services(cursor, clean_ids[0])
    try:
        cursor.execute(
            """
            SELECT id, name, description, category, price
            FROM userservices
            WHERE business_id = ANY(%s)
              AND (is_active IS TRUE OR is_active IS NULL)
            ORDER BY updated_at DESC NULLS LAST, created_at DESC
            LIMIT 300
            """,
            (clean_ids,),
        )
        rows = cursor.fetchall() or []
    except Exception:
        return []
    return [
        {
            "id": str(_row_get(row, "id", 0, "") or "").strip(),
            "name": str(_row_get(row, "name", 1, "") or "").strip(),
            "description": str(_row_get(row, "description", 2, "") or "").strip(),
            "category": str(_row_get(row, "category", 3, "") or "").strip(),
            "price": str(_row_get(row, "price", 4, "") or "").strip(),
        }
        for row in rows
        if str(_row_get(row, "name", 1, "") or "").strip()
    ]


def _fetch_recent_news_for_businesses(cursor: Any, user_id: str, business_ids: list[str]) -> list[dict[str, Any]]:
    clean_ids = [str(item or "").strip() for item in business_ids if str(item or "").strip()]
    if not clean_ids:
        return []
    if len(clean_ids) == 1:
        return _fetch_recent_news(cursor, user_id, clean_ids[0])
    has_business_id = _table_has_column(cursor, "usernews", "business_id")
    if not has_business_id:
        return _fetch_recent_news(cursor, user_id, clean_ids[0])
    try:
        cursor.execute(
            """
            SELECT id, generated_text, approved, created_at
            FROM usernews
            WHERE user_id = %s AND business_id = ANY(%s)
            ORDER BY created_at DESC
            LIMIT 20
            """,
            (user_id, clean_ids),
        )
        rows = cursor.fetchall() or []
    except Exception:
        return []
    return [
        {
            "id": str(_row_get(row, "id", 0, "") or "").strip(),
            "text": str(_row_get(row, "generated_text", 1, "") or "").strip(),
            "approved": bool(_row_get(row, "approved", 2, False)),
            "created_at": _row_get(row, "created_at", 3),
        }
        for row in rows
        if str(_row_get(row, "generated_text", 1, "") or "").strip()
    ]


def _fetch_sales_signals_for_businesses(cursor: Any, user_id: str, business_ids: list[str]) -> list[dict[str, Any]]:
    clean_ids = [str(item or "").strip() for item in business_ids if str(item or "").strip()]
    if not clean_ids:
        return []
    if len(clean_ids) == 1:
        return _fetch_sales_signals(cursor, user_id, clean_ids[0])
    try:
        cursor.execute(
            """
            SELECT id, transaction_date, amount, services, notes
            FROM financialtransactions
            WHERE user_id = %s AND business_id = ANY(%s)
            ORDER BY transaction_date DESC NULLS LAST, created_at DESC
            LIMIT 20
            """,
            (user_id, clean_ids),
        )
        rows = cursor.fetchall() or []
    except Exception:
        return []
    signals = []
    for row in rows:
        services_raw = _row_get(row, "services", 3, None)
        services_list = []
        if services_raw:
            try:
                parsed = json.loads(services_raw) if isinstance(services_raw, str) else services_raw
                if isinstance(parsed, list):
                    services_list = [str(item).strip() for item in parsed if str(item).strip()]
            except Exception:
                services_list = []
        title = ", ".join(services_list[:3]) if services_list else str(_row_get(row, "notes", 4, "") or "").strip()
        if not title:
            title = f"Продажа на {_row_get(row, 'transaction_date', 1, '')}"
        signals.append(
            {
                "transaction_id": str(_row_get(row, "id", 0, "") or "").strip(),
                "title": title,
                "amount": float(_row_get(row, "amount", 2, 0) or 0),
                "transaction_date": _row_get(row, "transaction_date", 1),
            }
        )
    return signals


def _fetch_custom_seo_keywords_for_businesses(cursor: Any, business_ids: list[str], limit: int = 20) -> list[dict[str, Any]]:
    clean_ids = [str(item or "").strip() for item in business_ids if str(item or "").strip()]
    if not clean_ids:
        return []
    try:
        cursor.execute("SELECT to_regclass('public.wordstatkeywordscustom')")
        row = cursor.fetchone()
        if not _row_get(row, "to_regclass", 0, None):
            return []
        cursor.execute(
            """
            SELECT keyword, views, category
            FROM wordstatkeywordscustom
            WHERE business_id = ANY(%s)
            ORDER BY views DESC, updated_at DESC
            LIMIT %s
            """,
            (clean_ids, max(1, int(limit or 20))),
        )
        rows = cursor.fetchall() or []
    except Exception:
        return []
    return [
        {
            "keyword": str(_row_get(row, "keyword", 0, "") or "").strip(),
            "views": int(_row_get(row, "views", 1, 0) or 0),
            "category": str(_row_get(row, "category", 2, "") or "").strip(),
        }
        for row in rows
        if str(_row_get(row, "keyword", 0, "") or "").strip()
    ]


def _merge_seo_keyword_lists(primary: list[dict[str, Any]], fallback: list[dict[str, Any]], limit: int = 20) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source in (primary, fallback):
        for item in source:
            keyword = str(item.get("keyword") or "").strip()
            key = keyword.lower()
            if not keyword or key in seen:
                continue
            seen.add(key)
            merged.append(item)
            if len(merged) >= limit:
                return merged
    return merged


_FOREIGN_BRAND_SEO_KEYWORDS = {
    "точка красоты",
    "город красоты",
    "истинная красота",
    "персона",
    "мастерская красоты",
}


def _normalize_keyword_for_filter(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().replace("ё", "е").split())


def _filter_foreign_brand_seo_keywords(keywords: list[dict[str, Any]], business_name: str) -> list[dict[str, Any]]:
    normalized_business = _normalize_keyword_for_filter(business_name)
    filtered: list[dict[str, Any]] = []
    excluded = {_normalize_keyword_for_filter(item) for item in _FOREIGN_BRAND_SEO_KEYWORDS}
    for item in keywords:
        keyword = str(item.get("keyword") or "").strip()
        normalized_keyword = _normalize_keyword_for_filter(keyword)
        if not normalized_keyword:
            continue
        if normalized_keyword in excluded and not (
            normalized_business
            and (normalized_keyword in normalized_business or normalized_business in normalized_keyword)
        ):
            continue
        filtered.append(item)
    return filtered


def _select_context_seo_keywords(
    ranked_keywords: list[dict[str, Any]],
    custom_keywords: list[dict[str, Any]],
    business_name: str = "",
    limit: int = 20,
) -> list[dict[str, Any]]:
    if len(custom_keywords) >= 5:
        return _filter_foreign_brand_seo_keywords(_merge_seo_keyword_lists(custom_keywords, [], limit=limit), business_name)
    return _filter_foreign_brand_seo_keywords(_merge_seo_keyword_lists(ranked_keywords, custom_keywords, limit=limit), business_name)


def load_plan_context_for_business(user_id: str, business_id: str, scope_type: str, scope_target_id: str | None = None) -> dict[str, Any]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_content_plan_tables(cursor)
        business_row = _fetch_business_row(cursor, business_id)
        if not business_row:
            raise ValueError("Бизнес не найден")
        owner_id = get_business_owner_id(cursor, business_id)
        if str(owner_id or "").strip() != str(user_id or "").strip():
            cursor.execute("SELECT COALESCE(is_superadmin, FALSE) FROM users WHERE id = %s", (user_id,))
            superadmin_row = cursor.fetchone()
            if not bool(_row_get(superadmin_row, "coalesce", 0, False)):
                raise PermissionError("Нет доступа к бизнесу")

        subscription = get_subscription_access(business_id)
        allowed_horizons = get_allowed_content_plan_horizons(business_id)
        scope_options = _fetch_network_scope_options(cursor, business_row)
        normalized_scope = _normalize_scope_type(scope_type)
        target_id = str(scope_target_id or "").strip()
        if not target_id:
            current_scope_option = next((item for item in scope_options if item.get("is_current")), None)
            if current_scope_option:
                normalized_scope = str(current_scope_option.get("scope_type") or normalized_scope)
                target_id = str(current_scope_option.get("scope_target_id") or business_id)
            else:
                target_id = business_id
        selected_scope_option = next(
            (
                item
                for item in scope_options
                if str(item.get("scope_type") or "") == normalized_scope
                and str(item.get("scope_target_id") or "") == target_id
            ),
            None,
        )
        scope_business_row = _build_scope_business_context(cursor, business_row, normalized_scope, target_id)
        scope_business_id = str(scope_business_row.get("id") or business_id)
        context_business_ids = _scope_context_business_ids(cursor, business_row, normalized_scope, target_id)
        if not context_business_ids:
            context_business_ids = [scope_business_id]
        map_links_count = _fetch_map_link_count_for_businesses(cursor, context_business_ids)
        services = _fetch_services_for_businesses(cursor, context_business_ids)
        custom_seo_keywords = _fetch_custom_seo_keywords_for_businesses(cursor, context_business_ids)
        seo_keywords = _select_context_seo_keywords(
            _fetch_seo_keywords_isolated(user_id, scope_business_id),
            custom_seo_keywords,
            str(scope_business_row.get("name") or business_row.get("name") or ""),
        )
        sales_signals = _fetch_sales_signals_for_businesses(cursor, user_id, context_business_ids)
        recent_news = _fetch_recent_news_for_businesses(cursor, user_id, context_business_ids)
        audit_signals = _fetch_audit_signals(scope_business_id)
        learning_feedback = _load_content_plan_learning_feedback(cursor, business_id)
        readiness = _build_planning_readiness(
            map_links_count=map_links_count,
            services_count=len(services),
            seo_keywords_count=len(seo_keywords),
            sales_signals_count=len(sales_signals),
            audit_signals_count=len(audit_signals),
        )
        selected_scope_label = str(selected_scope_option.get("label") or "").strip() if selected_scope_option else str(scope_business_row.get("name") or "").strip()
        selected_scope_city = str(selected_scope_option.get("city") or "").strip() if selected_scope_option else str(scope_business_row.get("city") or "").strip()
        selected_scope_address = str(selected_scope_option.get("address") or "").strip() if selected_scope_option else str(scope_business_row.get("address") or "").strip()

        return {
            "business": {
                "id": str(scope_business_row.get("id") or ""),
                "name": str(scope_business_row.get("name") or "").strip(),
                "city": str(scope_business_row.get("city") or "").strip(),
                "address": str(scope_business_row.get("address") or "").strip(),
                "business_type": str(scope_business_row.get("business_type") or "").strip(),
                "industry": str(scope_business_row.get("industry") or "").strip(),
                "categories": str(scope_business_row.get("categories") or "").strip(),
                "description": str(scope_business_row.get("description") or "").strip(),
                "site": str(scope_business_row.get("site") or scope_business_row.get("website") or "").strip(),
            },
            "root_business": {
                "id": str(business_row.get("id") or ""),
                "name": str(business_row.get("name") or "").strip(),
                "network_id": str(business_row.get("network_id") or "").strip(),
            },
            "scope": {
                "scope_type": normalized_scope,
                "scope_target_id": target_id,
                "scope_options": scope_options,
                "selected_scope_label": selected_scope_label,
                "selected_scope_description": _scope_description(
                    normalized_scope,
                    selected_scope_label,
                    selected_scope_city,
                    selected_scope_address,
                ),
                "network": {
                    "is_network": len(scope_options) > 1,
                    "locations_count": len([item for item in scope_options if str(item.get("scope_type") or "") == "network_location"]),
                    "has_parent_scope": any(str(item.get("scope_type") or "") == "network_parent" for item in scope_options),
                },
            },
            "subscription": {
                "tier": subscription.get("tier"),
                "status": subscription.get("status"),
                "allowed_horizons": allowed_horizons,
                "automation_access": bool(subscription.get("automation_access")),
                "reason": subscription.get("reason"),
            },
            "services": services,
            "seo_keywords": seo_keywords,
            "sales_signals": sales_signals,
            "recent_news": recent_news,
            "audit_signals": audit_signals,
            "readiness": readiness,
            "learning_feedback": learning_feedback,
        }
    finally:
        db.close()


def list_content_plans(user_id: str, business_id: str) -> list[dict[str, Any]]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_content_plan_tables(cursor)
        owner_id = get_business_owner_id(cursor, business_id)
        if str(owner_id or "").strip() != str(user_id or "").strip():
            cursor.execute("SELECT COALESCE(is_superadmin, FALSE) FROM users WHERE id = %s", (user_id,))
            if not bool(_row_get(cursor.fetchone(), "coalesce", 0, False)):
                raise PermissionError("Нет доступа к бизнесу")
        cursor.execute(
            """
            SELECT
                p.id,
                p.title,
                p.scope_type,
                p.scope_target_id,
                p.period_days,
                p.period_start,
                p.period_end,
                p.plan_status,
                p.generation_mode,
                p.created_at,
                p.updated_at,
                COALESCE(stats.total_items, 0) AS total_items,
                COALESCE(stats.needs_draft_items, 0) AS needs_draft_items,
                COALESCE(stats.ready_items, 0) AS ready_items,
                COALESCE(stats.news_items, 0) AS news_items,
                COALESCE(stats.skipped_items, 0) AS skipped_items
            FROM contentplans p
            LEFT JOIN (
                SELECT
                    plan_id,
                    COUNT(*) AS total_items,
                    COUNT(*) FILTER (
                        WHERE COALESCE(status, '') <> 'skipped'
                          AND COALESCE(NULLIF(TRIM(draft_text), ''), '') = ''
                    ) AS needs_draft_items,
                    COUNT(*) FILTER (
                        WHERE COALESCE(NULLIF(TRIM(draft_text), ''), '') <> ''
                          AND COALESCE(NULLIF(usernews_id, ''), '') = ''
                    ) AS ready_items,
                    COUNT(*) FILTER (
                        WHERE COALESCE(NULLIF(usernews_id, ''), '') <> ''
                    ) AS news_items,
                    COUNT(*) FILTER (
                        WHERE COALESCE(status, '') = 'skipped'
                    ) AS skipped_items
                FROM contentplanitems
                GROUP BY plan_id
            ) stats ON stats.plan_id = p.id
            WHERE p.business_id = %s
            ORDER BY p.created_at DESC
            LIMIT 50
            """,
            (business_id,),
        )
        rows = cursor.fetchall() or []
        plans = []
        for row in rows:
            plan_business_id = str(business_id or "").strip()
            scope_type = str(_row_get(row, "scope_type", 2, "") or "").strip()
            scope_target_id = str(_row_get(row, "scope_target_id", 3, "") or "").strip()
            target_meta = _resolve_scope_target_meta(cursor, plan_business_id, scope_type, scope_target_id)
            plans.append(
                {
                    "id": str(_row_get(row, "id", 0, "") or "").strip(),
                    "title": str(_row_get(row, "title", 1, "") or "").strip(),
                    "scope_type": scope_type,
                    "scope_target_id": scope_target_id,
                    "scope_target_label": str(target_meta.get("scope_target_label") or "").strip(),
                    "scope_target_city": str(target_meta.get("scope_target_city") or "").strip(),
                    "scope_target_address": str(target_meta.get("scope_target_address") or "").strip(),
                    "period_days": int(_row_get(row, "period_days", 4, 30) or 30),
                    "period_start": _row_get(row, "period_start", 5),
                    "period_end": _row_get(row, "period_end", 6),
                    "plan_status": str(_row_get(row, "plan_status", 7, "") or "").strip(),
                    "generation_mode": str(_row_get(row, "generation_mode", 8, "") or "").strip(),
                    "created_at": _row_get(row, "created_at", 9),
                    "updated_at": _row_get(row, "updated_at", 10),
                    "items_count": int(_row_get(row, "total_items", 11, 0) or 0),
                    "needs_draft_count": int(_row_get(row, "needs_draft_items", 12, 0) or 0),
                    "ready_count": int(_row_get(row, "ready_items", 13, 0) or 0),
                    "news_count": int(_row_get(row, "news_items", 14, 0) or 0),
                    "skipped_count": int(_row_get(row, "skipped_items", 15, 0) or 0),
                }
            )
        return plans
    finally:
        db.close()


def get_content_plan_learning_metrics(user_id: str, business_id: str, window_days: int = 30) -> dict[str, Any]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_content_plan_tables(cursor)
        owner_id = get_business_owner_id(cursor, business_id)
        if str(owner_id or "").strip() != str(user_id or "").strip():
            cursor.execute("SELECT COALESCE(is_superadmin, FALSE) FROM users WHERE id = %s", (user_id,))
            if not bool(_row_get(cursor.fetchone(), "coalesce", 0, False)):
                raise PermissionError("Нет доступа к бизнесу")
        normalized_window = max(1, min(int(window_days or 30), 365))
        ensure_ai_learning_events_table(db.conn)
        cursor.execute(
            """
            SELECT
                capability,
                COUNT(*) FILTER (WHERE event_type = 'generated') AS generated_total,
                COUNT(*) FILTER (WHERE event_type = 'accepted') AS accepted_total,
                COUNT(*) FILTER (
                    WHERE event_type = 'accepted'
                      AND COALESCE(edited_before_accept, FALSE) = TRUE
                ) AS accepted_edited_total,
                COUNT(*) FILTER (WHERE event_type = 'skipped') AS skipped_total,
                COUNT(*) FILTER (WHERE event_type = 'rescheduled') AS rescheduled_total,
                COUNT(*) FILTER (WHERE event_type = 'minor_edit') AS minor_edit_total,
                COUNT(*) FILTER (WHERE event_type = 'major_rewrite') AS major_rewrite_total
            FROM ailearningevents
            WHERE business_id = NULLIF(%s, '')::uuid
              AND capability LIKE 'content_plan.%%'
              AND created_at >= NOW() - (%s * INTERVAL '1 day')
            GROUP BY capability
            ORDER BY capability
            """,
            (str(business_id or "").strip(), normalized_window),
        )
        metrics = _build_learning_metrics_summary(cursor.fetchall() or [])
        cursor.execute(
            """
            SELECT
                COALESCE(NULLIF(metadata_json->>'source_kind', ''), 'unknown') AS source_kind,
                COUNT(*) FILTER (WHERE capability = 'content_plan.publish' AND event_type = 'accepted') AS accepted_total,
                COUNT(*) FILTER (
                    WHERE capability = 'content_plan.publish'
                      AND event_type = 'accepted'
                      AND COALESCE(edited_before_accept, FALSE) = TRUE
                ) AS accepted_edited_total,
                COUNT(*) FILTER (WHERE capability = 'content_plan.item' AND event_type = 'skipped') AS skipped_total,
                COUNT(*) FILTER (WHERE capability = 'content_plan.item' AND event_type = 'rescheduled') AS rescheduled_total,
                COUNT(*) FILTER (WHERE capability = 'content_plan.item' AND event_type = 'major_rewrite') AS major_rewrite_total,
                COUNT(*) FILTER (WHERE capability = 'content_plan.draft' AND event_type = 'generated') AS draft_generated_total
            FROM ailearningevents
            WHERE business_id = NULLIF(%s, '')::uuid
              AND capability LIKE 'content_plan.%%'
              AND created_at >= NOW() - (%s * INTERVAL '1 day')
            GROUP BY source_kind
            HAVING
                COUNT(*) FILTER (WHERE capability = 'content_plan.publish' AND event_type = 'accepted') > 0
                OR COUNT(*) FILTER (WHERE capability = 'content_plan.item' AND event_type IN ('skipped', 'rescheduled', 'major_rewrite')) > 0
                OR COUNT(*) FILTER (WHERE capability = 'content_plan.draft' AND event_type = 'generated') > 0
            ORDER BY skipped_total DESC, major_rewrite_total DESC, accepted_edited_total DESC, accepted_total DESC, source_kind ASC
            """,
            (str(business_id or "").strip(), normalized_window),
        )
        source_kind_breakdown = _build_learning_breakdown_summary(cursor.fetchall() or [], "source_kind")
        cursor.execute(
            """
            SELECT
                COALESCE(NULLIF(metadata_json->>'content_type', ''), 'unknown') AS content_type,
                COUNT(*) FILTER (WHERE capability = 'content_plan.publish' AND event_type = 'accepted') AS accepted_total,
                COUNT(*) FILTER (
                    WHERE capability = 'content_plan.publish'
                      AND event_type = 'accepted'
                      AND COALESCE(edited_before_accept, FALSE) = TRUE
                ) AS accepted_edited_total,
                COUNT(*) FILTER (WHERE capability = 'content_plan.item' AND event_type = 'skipped') AS skipped_total,
                COUNT(*) FILTER (WHERE capability = 'content_plan.item' AND event_type = 'rescheduled') AS rescheduled_total,
                COUNT(*) FILTER (WHERE capability = 'content_plan.item' AND event_type = 'major_rewrite') AS major_rewrite_total,
                COUNT(*) FILTER (WHERE capability = 'content_plan.draft' AND event_type = 'generated') AS draft_generated_total
            FROM ailearningevents
            WHERE business_id = NULLIF(%s, '')::uuid
              AND capability LIKE 'content_plan.%%'
              AND created_at >= NOW() - (%s * INTERVAL '1 day')
            GROUP BY content_type
            HAVING
                COUNT(*) FILTER (WHERE capability = 'content_plan.publish' AND event_type = 'accepted') > 0
                OR COUNT(*) FILTER (WHERE capability = 'content_plan.item' AND event_type IN ('skipped', 'rescheduled', 'major_rewrite')) > 0
                OR COUNT(*) FILTER (WHERE capability = 'content_plan.draft' AND event_type = 'generated') > 0
            ORDER BY skipped_total DESC, major_rewrite_total DESC, accepted_edited_total DESC, accepted_total DESC, content_type ASC
            """,
            (str(business_id or "").strip(), normalized_window),
        )
        content_type_breakdown = _build_learning_breakdown_summary(cursor.fetchall() or [], "content_type")
        cursor.execute(
            """
            SELECT
                COALESCE(NULLIF(metadata_json->>'location_scope', ''), 'current') AS location_scope,
                COALESCE(NULLIF(metadata_json->>'location_label', ''), '') AS location_label,
                COUNT(*) FILTER (WHERE event_type = 'accepted') AS accepted_total,
                COUNT(*) FILTER (
                    WHERE event_type = 'accepted'
                      AND COALESCE(edited_before_accept, FALSE) = TRUE
                ) AS accepted_edited_total
            FROM ailearningevents
            WHERE business_id = NULLIF(%s, '')::uuid
              AND capability = 'content_plan.publish'
              AND created_at >= NOW() - (%s * INTERVAL '1 day')
            GROUP BY location_scope, location_label
            HAVING COUNT(*) FILTER (WHERE event_type = 'accepted') > 0
            ORDER BY accepted_edited_total DESC, accepted_total DESC, location_label ASC
            """,
            (str(business_id or "").strip(), normalized_window),
        )
        location_breakdown = _build_learning_breakdown_summary(cursor.fetchall() or [], "location_scope", "location_label")
        cursor.execute(
            """
            SELECT
                COALESCE(NULLIF(metadata_json->>'location_scope', ''), 'current') AS location_scope,
                COALESCE(NULLIF(metadata_json->>'location_label', ''), '') AS location_label,
                COUNT(*) FILTER (WHERE capability = 'content_plan.publish' AND event_type = 'accepted') AS accepted_total,
                COUNT(*) FILTER (
                    WHERE capability = 'content_plan.publish'
                      AND event_type = 'accepted'
                      AND COALESCE(edited_before_accept, FALSE) = TRUE
                ) AS accepted_edited_total,
                COUNT(*) FILTER (WHERE capability = 'content_plan.item' AND event_type = 'skipped') AS skipped_total,
                COUNT(*) FILTER (WHERE capability = 'content_plan.item' AND event_type = 'rescheduled') AS rescheduled_total,
                COUNT(*) FILTER (WHERE capability = 'content_plan.item' AND event_type = 'major_rewrite') AS major_rewrite_total,
                COUNT(*) FILTER (WHERE capability = 'content_plan.draft' AND event_type = 'generated') AS draft_generated_total
            FROM ailearningevents
            WHERE business_id = NULLIF(%s, '')::uuid
              AND capability LIKE 'content_plan.%%'
              AND created_at >= NOW() - (%s * INTERVAL '1 day')
            GROUP BY location_scope, location_label
            HAVING
                COUNT(*) FILTER (WHERE capability = 'content_plan.publish' AND event_type = 'accepted') > 0
                OR COUNT(*) FILTER (WHERE capability = 'content_plan.item' AND event_type IN ('skipped', 'rescheduled', 'major_rewrite')) > 0
                OR COUNT(*) FILTER (WHERE capability = 'content_plan.draft' AND event_type = 'generated') > 0
            ORDER BY skipped_total DESC, major_rewrite_total DESC, accepted_edited_total DESC, accepted_total DESC
            """,
            (str(business_id or "").strip(), normalized_window),
        )
        network_quality = _build_network_quality_summary(cursor.fetchall() or [])
        return {
            "window_days": normalized_window,
            "items": metrics.get("items", []),
            "summary": metrics.get("summary", {}),
            "source_kind_breakdown": source_kind_breakdown,
            "content_type_breakdown": content_type_breakdown,
            "location_breakdown": location_breakdown,
            "network_quality": network_quality,
            "quality_insights": _build_learning_quality_insights(source_kind_breakdown, content_type_breakdown, network_quality),
            "ranking_feedback": _build_learning_feedback_from_breakdowns(source_kind_breakdown, content_type_breakdown, network_quality),
        }
    finally:
        db.close()


def create_generated_content_plan(
    user_id: str,
    business_id: str,
    *,
    scope_type: str,
    scope_target_id: str | None,
    period_days: int,
    density: str,
    content_mix: dict[str, Any] | None,
) -> dict[str, Any]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_content_plan_tables(cursor)
        allowed_horizons = get_allowed_content_plan_horizons(business_id)
        normalized_period = int(period_days or 30)
        if normalized_period not in allowed_horizons:
            raise PermissionError("Горизонт планирования недоступен на текущем тарифе")
        context = load_plan_context_for_business(user_id, business_id, scope_type, scope_target_id)
        if not bool(context.get("subscription", {}).get("automation_access")):
            raise PermissionError(context.get("subscription", {}).get("reason") or "Автоматизация недоступна")
        skeleton = build_content_plan_skeleton(
            context,
            period_days=normalized_period,
            density=str(density or "standard"),
            content_mix=content_mix if isinstance(content_mix, dict) else {},
        )
        plan_id = str(uuid.uuid4())
        normalized_scope = _normalize_scope_type(scope_type)
        target_id = str(scope_target_id or "").strip() or str(context.get("scope", {}).get("scope_target_id") or business_id)
        root_business = context.get("root_business") if isinstance(context.get("root_business"), dict) else {}
        scope_business = context.get("business") if isinstance(context.get("business"), dict) else {}
        network_location_targets = _network_location_targets_from_context(context)
        context_json = _json_ready(context)
        skeleton_json = _json_ready(skeleton)
        title = str(skeleton.get("title") or "").strip() or f"Контент-план на {normalized_period} дней"
        period_start = str(skeleton.get("period_start") or date.today().isoformat())
        period_end = str(skeleton.get("period_end") or date.today().isoformat())
        cursor.execute(
            """
            INSERT INTO contentplans (
                id, business_id, network_id, scope_type, scope_target_id, title,
                period_days, period_start, period_end, plan_status, generation_mode,
                input_snapshot_json, generated_plan_json, published_plan_json, created_by
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'generated', 'manual', %s::jsonb, %s::jsonb, %s::jsonb, %s)
            """,
            (
                plan_id,
                business_id,
                str(root_business.get("network_id") or "").strip() or None,
                normalized_scope,
                target_id or None,
                title,
                normalized_period,
                period_start,
                period_end,
                json.dumps(context_json, ensure_ascii=False),
                json.dumps(skeleton_json, ensure_ascii=False),
                json.dumps(skeleton_json, ensure_ascii=False),
                user_id,
            ),
        )

        items = skeleton.get("items") if isinstance(skeleton.get("items"), list) else []
        for idx, item in enumerate(items):
            item_id = str(uuid.uuid4())
            item_business_id = str(scope_business.get("id") or business_id)
            item_location_scope = target_id
            if normalized_scope == "network_parent" and network_location_targets:
                assigned_target = network_location_targets[idx % len(network_location_targets)]
                item_business_id = str(assigned_target.get("business_id") or item_business_id)
                item_location_scope = item_business_id
            cursor.execute(
                """
                INSERT INTO contentplanitems (
                    id, plan_id, business_id, scheduled_for, content_type, theme, goal,
                    source_kind, source_ref, seo_keyword, service_id, transaction_id,
                    seo_views, location_scope, status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'planned')
                """,
                (
                    item_id,
                    plan_id,
                    item_business_id,
                    item.get("scheduled_for"),
                    item.get("content_type") or "news",
                    item.get("theme") or "Тема публикации",
                    item.get("goal") or "",
                    item.get("source_kind") or "",
                    item.get("source_ref") or "",
                    item.get("seo_keyword") or None,
                    item.get("service_id") or None,
                    item.get("transaction_id") or None,
                    int(item.get("seo_views") or 0),
                    item_location_scope,
                ),
            )
        _record_content_plan_event(
            conn=db.conn,
            user_id=user_id,
            business_id=business_id,
            capability="content_plan.generate",
            event_type="generated",
            final_text=title,
            metadata={
                "plan_id": plan_id,
                "scope_type": normalized_scope,
                "scope_target_id": target_id,
                "period_days": normalized_period,
                "density": str(density or "standard"),
                "items_count": len(items),
                "sources_used": skeleton.get("meta", {}).get("sources_used") if isinstance(skeleton.get("meta"), dict) else [],
            },
        )
        db.conn.commit()
        return get_content_plan(user_id, plan_id)
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


def get_content_plan(user_id: str, plan_id: str) -> dict[str, Any]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_content_plan_tables(cursor)
        cursor.execute(
            """
            SELECT id, business_id, network_id, scope_type, scope_target_id, title,
                   period_days, period_start, period_end, plan_status, generation_mode,
                   input_snapshot_json, generated_plan_json, edited_plan_json, published_plan_json,
                   created_by, created_at, updated_at
            FROM contentplans
            WHERE id = %s
            LIMIT 1
            """,
            (plan_id,),
        )
        plan_row = cursor.fetchone()
        if not plan_row:
            raise ValueError("Контент-план не найден")
        plan = _row_to_dict(cursor, plan_row)
        owner_id = get_business_owner_id(cursor, str(plan.get("business_id") or ""))
        if str(owner_id or "").strip() != str(user_id or "").strip():
            cursor.execute("SELECT COALESCE(is_superadmin, FALSE) FROM users WHERE id = %s", (user_id,))
            if not bool(_row_get(cursor.fetchone(), "coalesce", 0, False)):
                raise PermissionError("Нет доступа к плану")

        cursor.execute(
            """
            SELECT id, business_id, scheduled_for, content_type, theme, goal, source_kind, source_ref,
                   seo_keyword, service_id, transaction_id, seo_views, location_scope, draft_text, status, usernews_id,
                   created_at, updated_at
            FROM contentplanitems
            WHERE plan_id = %s
            ORDER BY scheduled_for ASC, created_at ASC
            """,
            (plan_id,),
        )
        item_rows = cursor.fetchall() or []
        items = []
        for row in item_rows:
            item_business_id = str(_row_get(row, "business_id", 1, "") or "").strip()
            item_location_scope = str(_row_get(row, "location_scope", 12, "") or "").strip()
            location_meta = _resolve_scope_target_meta(
                cursor,
                item_business_id or str(plan.get("business_id") or ""),
                "network_location" if item_location_scope else str(plan.get("scope_type") or ""),
                item_location_scope or item_business_id,
            )
            items.append(
                {
                    "id": str(_row_get(row, "id", 0, "") or "").strip(),
                    "business_id": item_business_id,
                    "scheduled_for": _row_get(row, "scheduled_for", 2),
                    "content_type": str(_row_get(row, "content_type", 3, "") or "").strip(),
                    "theme": str(_row_get(row, "theme", 4, "") or "").strip(),
                    "goal": str(_row_get(row, "goal", 5, "") or "").strip(),
                    "source_kind": str(_row_get(row, "source_kind", 6, "") or "").strip(),
                    "source_ref": str(_row_get(row, "source_ref", 7, "") or "").strip(),
                    "seo_keyword": str(_row_get(row, "seo_keyword", 8, "") or "").strip(),
                    "service_id": str(_row_get(row, "service_id", 9, "") or "").strip(),
                    "transaction_id": str(_row_get(row, "transaction_id", 10, "") or "").strip(),
                    "seo_views": int(_row_get(row, "seo_views", 11, 0) or 0),
                    "location_scope": item_location_scope,
                    "location_label": str(location_meta.get("scope_target_label") or "").strip(),
                    "location_city": str(location_meta.get("scope_target_city") or "").strip(),
                    "location_address": str(location_meta.get("scope_target_address") or "").strip(),
                    "draft_text": str(_row_get(row, "draft_text", 13, "") or "").strip(),
                    "status": str(_row_get(row, "status", 14, "") or "").strip(),
                    "usernews_id": str(_row_get(row, "usernews_id", 15, "") or "").strip(),
                    "created_at": _row_get(row, "created_at", 16),
                    "updated_at": _row_get(row, "updated_at", 17),
                }
            )
        target_meta = _resolve_scope_target_meta(
            cursor,
            str(plan.get("business_id") or ""),
            str(plan.get("scope_type") or ""),
            str(plan.get("scope_target_id") or ""),
        )
        return {
            "id": str(plan.get("id") or ""),
            "business_id": str(plan.get("business_id") or ""),
            "network_id": str(plan.get("network_id") or ""),
            "scope_type": str(plan.get("scope_type") or ""),
            "scope_target_id": str(plan.get("scope_target_id") or ""),
            "scope_target_label": str(target_meta.get("scope_target_label") or "").strip(),
            "scope_target_city": str(target_meta.get("scope_target_city") or "").strip(),
            "scope_target_address": str(target_meta.get("scope_target_address") or "").strip(),
            "title": str(plan.get("title") or ""),
            "period_days": int(plan.get("period_days") or 30),
            "period_start": plan.get("period_start"),
            "period_end": plan.get("period_end"),
            "plan_status": str(plan.get("plan_status") or ""),
            "generation_mode": str(plan.get("generation_mode") or ""),
            "input_snapshot_json": plan.get("input_snapshot_json") if isinstance(plan.get("input_snapshot_json"), dict) else {},
            "generated_plan_json": plan.get("generated_plan_json") if isinstance(plan.get("generated_plan_json"), dict) else {},
            "edited_plan_json": plan.get("edited_plan_json") if isinstance(plan.get("edited_plan_json"), dict) else {},
            "published_plan_json": plan.get("published_plan_json") if isinstance(plan.get("published_plan_json"), dict) else {},
            "items": items,
            "created_at": plan.get("created_at"),
            "updated_at": plan.get("updated_at"),
        }
    finally:
        db.close()


def delete_content_plan(user_id: str, plan_id: str) -> None:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_content_plan_tables(cursor)
        cursor.execute(
            """
            SELECT id, business_id, title
            FROM contentplans
            WHERE id = %s
            LIMIT 1
            """,
            (plan_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise ValueError("Контент-план не найден")
        plan = _row_to_dict(cursor, row)
        business_id = str(plan.get("business_id") or "").strip()
        owner_id = get_business_owner_id(cursor, business_id)
        if str(owner_id or "").strip() != str(user_id or "").strip():
            cursor.execute("SELECT COALESCE(is_superadmin, FALSE) FROM users WHERE id = %s", (user_id,))
            if not bool(_row_get(cursor.fetchone(), "coalesce", 0, False)):
                raise PermissionError("Нет доступа к плану")
        cursor.execute("DELETE FROM contentplans WHERE id = %s", (plan_id,))
        _record_content_plan_event(
            conn=db.conn,
            user_id=user_id,
            business_id=business_id,
            capability="content_plan.plan",
            event_type="deleted",
            final_text=str(plan.get("title") or "").strip(),
            metadata={"plan_id": plan_id},
        )
        db.conn.commit()
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


def delete_content_plan_item(user_id: str, item_id: str) -> dict[str, Any]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_content_plan_tables(cursor)
        cursor.execute(
            """
            SELECT
                i.id,
                i.plan_id,
                i.business_id,
                i.theme,
                i.source_kind,
                i.content_type,
                i.location_scope,
                p.business_id AS root_business_id
            FROM contentplanitems i
            JOIN contentplans p ON p.id = i.plan_id
            WHERE i.id = %s
            LIMIT 1
            """,
            (item_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise ValueError("Элемент плана не найден")
        item = _row_to_dict(cursor, row)
        root_business_id = str(item.get("root_business_id") or item.get("business_id") or "").strip()
        owner_id = get_business_owner_id(cursor, root_business_id)
        if str(owner_id or "").strip() != str(user_id or "").strip():
            cursor.execute("SELECT COALESCE(is_superadmin, FALSE) FROM users WHERE id = %s", (user_id,))
            if not bool(_row_get(cursor.fetchone(), "coalesce", 0, False)):
                raise PermissionError("Нет доступа к элементу плана")
        plan_id = str(item.get("plan_id") or "").strip()
        cursor.execute("DELETE FROM contentplanitems WHERE id = %s", (item_id,))
        location_scope = str(item.get("location_scope") or item.get("business_id") or "").strip()
        _record_content_plan_event(
            conn=db.conn,
            user_id=user_id,
            business_id=root_business_id,
            capability="content_plan.item",
            event_type="deleted",
            final_text=str(item.get("theme") or "").strip(),
            metadata={
                "item_id": item_id,
                "plan_id": plan_id,
                "source_kind": str(item.get("source_kind") or "").strip(),
                "content_type": str(item.get("content_type") or "").strip(),
                "location_scope": location_scope,
            },
        )
        db.conn.commit()
        return get_content_plan(user_id, plan_id)
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


def update_content_plan_item(user_id: str, item_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_content_plan_tables(cursor)
        cursor.execute(
            """
            SELECT i.id, i.plan_id, i.business_id, i.status, i.source_kind, i.content_type, i.theme, i.draft_text,
                   i.location_scope, p.business_id AS root_business_id
            FROM contentplanitems i
            JOIN contentplans p ON p.id = i.plan_id
            WHERE i.id = %s
            LIMIT 1
            """,
            (item_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise ValueError("Элемент плана не найден")
        data = _row_to_dict(cursor, row)
        previous_status = str(data.get("status") or "").strip()
        owner_id = get_business_owner_id(cursor, str(data.get("root_business_id") or ""))
        if str(owner_id or "").strip() != str(user_id or "").strip():
            cursor.execute("SELECT COALESCE(is_superadmin, FALSE) FROM users WHERE id = %s", (user_id,))
            if not bool(_row_get(cursor.fetchone(), "coalesce", 0, False)):
                raise PermissionError("Нет доступа к элементу плана")

        updates = []
        params: list[Any] = []
        for field in ("scheduled_for", "theme", "goal", "content_type", "seo_keyword", "draft_text"):
            if field in payload:
                updates.append(f"{field} = %s")
                params.append(payload.get(field))
        if "status" in payload:
            next_status = str(payload.get("status") or "").strip()
            if next_status in {"planned", "draft_generated", "edited", "approved", "published", "skipped"}:
                updates.append("status = %s")
                params.append(next_status)
        if "draft_text" in payload:
            updates.append("status = %s")
            params.append("edited")
        if not updates:
            return get_content_plan(user_id, str(data.get("plan_id") or ""))
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.extend([item_id])
        cursor.execute(
            f"""
            UPDATE contentplanitems
            SET {', '.join(updates)}
            WHERE id = %s
            """,
            tuple(params),
        )
        next_status = str(payload.get("status") or "").strip() if "status" in payload else previous_status
        event_type = "edited"
        edit_class = ""
        if "status" in payload and next_status == "skipped":
            event_type = "skipped"
        elif "scheduled_for" in payload and "draft_text" not in payload and "theme" not in payload:
            event_type = "rescheduled"
        elif "draft_text" in payload:
            edit_class = _classify_text_edit(str(data.get("draft_text") or ""), str(payload.get("draft_text") or ""))
            if edit_class in {"minor_edit", "major_rewrite"}:
                event_type = edit_class
        location_scope = str(data.get("location_scope") or data.get("business_id") or "").strip()
        location_meta = _resolve_scope_target_meta(
            cursor,
            str(data.get("business_id") or ""),
            "network_location" if location_scope else "single_business",
            location_scope or str(data.get("business_id") or ""),
        )
        _record_content_plan_event(
            conn=db.conn,
            user_id=user_id,
            business_id=str(data.get("root_business_id") or data.get("business_id") or ""),
            capability="content_plan.item",
            event_type=event_type,
            draft_text=str(payload.get("draft_text") or "").strip() if "draft_text" in payload else None,
            final_text=str(payload.get("theme") or "").strip() if "theme" in payload else None,
            metadata={
                "item_id": item_id,
                "plan_id": str(data.get("plan_id") or ""),
                "fields": sorted([str(key) for key in payload.keys()]),
                "previous_status": previous_status,
                "next_status": next_status,
                "source_kind": str(data.get("source_kind") or "").strip(),
                "content_type": str(data.get("content_type") or "").strip(),
                "theme": str(payload.get("theme") or data.get("theme") or "").strip(),
                "edit_class": edit_class,
                "edit_reason": _edit_reason_from_class(edit_class),
                "location_scope": location_scope,
                "location_label": str(location_meta.get("scope_target_label") or "").strip(),
            },
        )
        db.conn.commit()
        return get_content_plan(user_id, str(data.get("plan_id") or ""))
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


def duplicate_content_plan_item(user_id: str, item_id: str) -> dict[str, Any]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_content_plan_tables(cursor)
        cursor.execute(
            """
            SELECT i.id, i.plan_id, i.business_id, i.scheduled_for, i.content_type, i.theme, i.goal,
                   i.source_kind, i.source_ref, i.seo_keyword, i.seo_views, i.service_id, i.transaction_id,
                   i.location_scope, p.business_id AS root_business_id
            FROM contentplanitems i
            JOIN contentplans p ON p.id = i.plan_id
            WHERE i.id = %s
            LIMIT 1
            """,
            (item_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise ValueError("Элемент плана не найден")
        item = _row_to_dict(cursor, row)
        owner_id = get_business_owner_id(cursor, str(item.get("root_business_id") or ""))
        if str(owner_id or "").strip() != str(user_id or "").strip():
            cursor.execute("SELECT COALESCE(is_superadmin, FALSE) FROM users WHERE id = %s", (user_id,))
            if not bool(_row_get(cursor.fetchone(), "coalesce", 0, False)):
                raise PermissionError("Нет доступа к элементу плана")

        scheduled_for = item.get("scheduled_for")
        next_scheduled_for: Any = scheduled_for
        if isinstance(scheduled_for, datetime):
            next_scheduled_for = (scheduled_for.date() + timedelta(days=7)).isoformat()
        elif isinstance(scheduled_for, date):
            next_scheduled_for = (scheduled_for + timedelta(days=7)).isoformat()
        else:
            raw_date = str(scheduled_for or "").strip()
            if raw_date:
                try:
                    next_scheduled_for = (date.fromisoformat(raw_date) + timedelta(days=7)).isoformat()
                except Exception:
                    next_scheduled_for = raw_date

        duplicated_id = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT INTO contentplanitems (
                id, plan_id, business_id, scheduled_for, content_type, theme, goal,
                source_kind, source_ref, seo_keyword, seo_views, service_id, transaction_id,
                location_scope, draft_text, status, usernews_id, created_at, updated_at
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            """,
            (
                duplicated_id,
                str(item.get("plan_id") or ""),
                str(item.get("business_id") or ""),
                next_scheduled_for,
                str(item.get("content_type") or "").strip(),
                str(item.get("theme") or "").strip(),
                str(item.get("goal") or "").strip(),
                str(item.get("source_kind") or "").strip(),
                str(item.get("source_ref") or "").strip(),
                str(item.get("seo_keyword") or "").strip(),
                int(item.get("seo_views") or 0),
                str(item.get("service_id") or "").strip() or None,
                str(item.get("transaction_id") or "").strip() or None,
                str(item.get("location_scope") or "").strip() or None,
                "",
                "planned",
                None,
            ),
        )
        _record_content_plan_event(
            conn=db.conn,
            user_id=user_id,
            business_id=str(item.get("root_business_id") or item.get("business_id") or ""),
            capability="content_plan.item",
            event_type="duplicated",
            final_text=str(item.get("theme") or "").strip(),
            metadata={
                "source_item_id": item_id,
                "duplicated_item_id": duplicated_id,
                "plan_id": str(item.get("plan_id") or ""),
                "scheduled_for": str(next_scheduled_for or ""),
                "source_kind": str(item.get("source_kind") or "").strip(),
                "content_type": str(item.get("content_type") or "").strip(),
                "theme": str(item.get("theme") or "").strip(),
                "location_scope": str(item.get("location_scope") or item.get("business_id") or "").strip(),
            },
        )
        db.conn.commit()
        return get_content_plan(user_id, str(item.get("plan_id") or ""))
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


def duplicate_content_plan_item_to_locations(user_id: str, item_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_content_plan_tables(cursor)
        cursor.execute(
            """
            SELECT i.id, i.plan_id, i.business_id, i.scheduled_for, i.content_type, i.theme, i.goal,
                   i.source_kind, i.source_ref, i.seo_keyword, i.seo_views, i.service_id, i.transaction_id,
                   i.location_scope, i.draft_text, p.business_id AS root_business_id
            FROM contentplanitems i
            JOIN contentplans p ON p.id = i.plan_id
            WHERE i.id = %s
            LIMIT 1
            """,
            (item_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise ValueError("Элемент плана не найден")
        item = _row_to_dict(cursor, row)
        owner_id = get_business_owner_id(cursor, str(item.get("root_business_id") or ""))
        if str(owner_id or "").strip() != str(user_id or "").strip():
            cursor.execute("SELECT COALESCE(is_superadmin, FALSE) FROM users WHERE id = %s", (user_id,))
            if not bool(_row_get(cursor.fetchone(), "coalesce", 0, False)):
                raise PermissionError("Нет доступа к элементу плана")

        request_payload = payload if isinstance(payload, dict) else {}
        requested_locations = request_payload.get("target_location_scopes")
        requested_set = {
            str(value or "").strip()
            for value in requested_locations
            if str(value or "").strip()
        } if isinstance(requested_locations, list) else set()
        source_location_scope = str(item.get("location_scope") or item.get("business_id") or "").strip()
        cursor.execute(
            """
            SELECT DISTINCT COALESCE(NULLIF(location_scope, ''), business_id) AS location_scope
            FROM contentplanitems
            WHERE plan_id = %s
              AND COALESCE(NULLIF(location_scope, ''), business_id) <> ''
            ORDER BY location_scope ASC
            """,
            (str(item.get("plan_id") or ""),),
        )
        location_rows = cursor.fetchall() or []
        available_locations = [
            str(_row_get(location_row, "location_scope", 0, "") or "").strip()
            for location_row in location_rows
            if str(_row_get(location_row, "location_scope", 0, "") or "").strip()
        ]
        target_locations = [
            location_scope
            for location_scope in available_locations
            if location_scope != source_location_scope and (not requested_set or location_scope in requested_set)
        ]
        if not target_locations:
            raise ValueError("Нет других точек для дублирования")

        scheduled_for = str(request_payload.get("scheduled_for") or item.get("scheduled_for") or "").strip() or item.get("scheduled_for")
        draft_text = str(item.get("draft_text") or "").strip()
        next_status = "draft_generated" if draft_text else "planned"
        duplicated_ids: list[str] = []
        for location_scope in target_locations:
            duplicated_id = str(uuid.uuid4())
            cursor.execute(
                """
                INSERT INTO contentplanitems (
                    id, plan_id, business_id, scheduled_for, content_type, theme, goal,
                    source_kind, source_ref, seo_keyword, seo_views, service_id, transaction_id,
                    location_scope, draft_text, status, usernews_id, created_at, updated_at
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                """,
                (
                    duplicated_id,
                    str(item.get("plan_id") or ""),
                    location_scope,
                    scheduled_for,
                    str(item.get("content_type") or "").strip(),
                    str(item.get("theme") or "").strip(),
                    str(item.get("goal") or "").strip(),
                    str(item.get("source_kind") or "").strip(),
                    str(item.get("source_ref") or "").strip(),
                    str(item.get("seo_keyword") or "").strip(),
                    int(item.get("seo_views") or 0),
                    str(item.get("service_id") or "").strip() or None,
                    str(item.get("transaction_id") or "").strip() or None,
                    location_scope,
                    draft_text,
                    next_status,
                    None,
                ),
            )
            duplicated_ids.append(duplicated_id)
        _record_content_plan_event(
            conn=db.conn,
            user_id=user_id,
            business_id=str(item.get("root_business_id") or item.get("business_id") or ""),
            capability="content_plan.item",
            event_type="duplicated_to_locations",
            draft_text=draft_text or None,
            final_text=str(item.get("theme") or "").strip(),
            metadata={
                "source_item_id": item_id,
                "duplicated_item_ids": duplicated_ids,
                "plan_id": str(item.get("plan_id") or ""),
                "scheduled_for": str(scheduled_for or ""),
                "source_kind": str(item.get("source_kind") or "").strip(),
                "content_type": str(item.get("content_type") or "").strip(),
                "theme": str(item.get("theme") or "").strip(),
                "location_scope": source_location_scope,
                "target_location_scopes": target_locations,
                "template_has_draft": bool(draft_text),
            },
        )
        db.conn.commit()
        return get_content_plan(user_id, str(item.get("plan_id") or ""))
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


def _service_names_from_fact_block(service_facts: Any, limit: int = 5) -> list[str]:
    names: list[str] = []
    for line in str(service_facts or "").splitlines():
        cleaned = line.strip().lstrip("-").strip()
        if not cleaned:
            continue
        name = cleaned.split("(", 1)[0].strip()
        if name:
            names.append(name)
        if len(names) >= limit:
            break
    return names


def _tokenize_content_plan_topic(value: Any) -> set[str]:
    normalized = str(value or "").lower().replace("ё", "е")
    tokens = set(re.findall(r"[a-zа-я0-9]+", normalized))
    stop_words = {
        "для",
        "как",
        "что",
        "это",
        "или",
        "при",
        "про",
        "без",
        "под",
        "над",
        "детей",
        "ребенка",
        "ребёнка",
        "детям",
        "подростков",
        "направление",
        "направления",
        "программа",
        "программе",
        "раскрыть",
        "усилить",
        "доверие",
    }
    return {token for token in tokens if len(token) >= 3 and token not in stop_words}


def _normalize_website_url(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.startswith(("http://", "https://")):
        return text
    return f"https://{text}"


def _clean_site_description_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    text = text.strip(" \t\r\n|—-")
    return text[:500]


def _extract_site_description_from_html(html: str) -> str:
    if not html:
        return ""
    try:
        soup = BeautifulSoup(html, "html.parser")
        for selector in (
            {"name": "description"},
            {"property": "og:description"},
            {"name": "twitter:description"},
        ):
            tag = soup.find("meta", attrs=selector)
            content = _clean_site_description_text(tag.get("content") if tag else "")
            if content:
                return content
        title = _clean_site_description_text(soup.title.string if soup.title else "")
        if title:
            return title
        h1 = soup.find("h1")
        return _clean_site_description_text(h1.get_text(" ", strip=True) if h1 else "")
    except Exception:
        return ""


def _fetch_site_description(site_url: Any) -> str:
    url = _normalize_website_url(site_url)
    if not url:
        return ""
    try:
        response = requests.get(
            url,
            headers={"User-Agent": "LocalOSBot/1.0 (+https://localos.pro)"},
            timeout=5,
        )
        if response.status_code >= 400:
            return ""
        return _extract_site_description_from_html(response.text or "")
    except Exception:
        return ""


def _relevant_service_names_for_item(service_facts: Any, item: dict[str, Any], limit: int = 5) -> list[str]:
    topic_tokens = _tokenize_content_plan_topic(
        " ".join(
            [
                str(item.get("theme") or ""),
                str(item.get("goal") or ""),
                str(item.get("seo_keyword") or ""),
            ]
        )
    )
    if not topic_tokens:
        return _service_names_from_fact_block(service_facts, limit=limit)

    scored: list[tuple[int, str]] = []
    fallback: list[str] = []
    for line in str(service_facts or "").splitlines():
        cleaned = line.strip().lstrip("-").strip()
        if not cleaned:
            continue
        name = cleaned.split("(", 1)[0].strip()
        if not name:
            continue
        fallback.append(name)
        haystack_tokens = _tokenize_content_plan_topic(cleaned)
        score = len(topic_tokens.intersection(haystack_tokens))
        if score > 0:
            scored.append((score, name))

    if scored:
        scored.sort(key=lambda pair: (-pair[0], fallback.index(pair[1]) if pair[1] in fallback else 999))
        result: list[str] = []
        for _, name in scored:
            if name not in result:
                result.append(name)
            if len(result) >= limit:
                break
        return result
    return fallback[:limit]


def _is_general_school_intro_topic(theme: str, goal: str) -> bool:
    text = f"{theme} {goal}".lower().replace("ё", "е")
    markers = [
        "что такое",
        "чем школа полезна",
        "общий пост",
        "подход к обучению",
        "подходе к обучению",
        "направлениях для детей",
        "о школе",
    ]
    return any(marker in text for marker in markers)


def _school_goal_sentence(goal: str) -> str:
    normalized = str(goal or "").strip().lower().replace("ё", "е")
    if not normalized:
        return "Это помогает родителям выбрать обучение под возраст и учебную задачу ребёнка."
    if "младших школьников" in normalized:
        return "Это помогает родителям младших школьников понять, как устроено направление и какие учебные задачи оно закрывает."
    if "дошколь" in normalized or "подготов" in normalized:
        return "Это помогает родителям понять, как мягко подготовить ребёнка к школе и первым учебным задачам."
    if normalized.startswith("общий пост") or normalized.startswith("раскрыть"):
        return "Это помогает родителям быстро понять, кому подходит направление и с какого шага начать знакомство."
    return str(goal or "").strip().rstrip(".") + "."


CONTENT_PLAN_LANGUAGE_LABELS = {
    "ru": "Russian",
    "en": "English",
    "es": "Spanish",
    "de": "German",
    "fr": "French",
    "tr": "Turkish",
    "it": "Italian",
    "pt": "Portuguese",
    "zh": "Chinese",
}


def _normalize_content_plan_language(language: str | None) -> str:
    normalized = str(language or "").strip().lower()
    return normalized if normalized in CONTENT_PLAN_LANGUAGE_LABELS else "ru"


def _content_plan_language_instruction(language: str) -> str:
    normalized = _normalize_content_plan_language(language)
    label = CONTENT_PLAN_LANGUAGE_LABELS.get(normalized, "Russian")
    if normalized == "ru":
        return (
            "Язык готовой новости: русский. Пиши обычным русским текстом.\n"
            "Если факты на другом языке, всё равно верни только русский текст."
        )
    return (
        f"Language of the final news post: {label}. Write the final publication only in {label}.\n"
        "The business facts, service names, theme, or SEO query may be in Russian; use them as source facts, "
        f"but translate the final wording into {label}. Do not include Russian explanatory text unless it is a brand or service name."
    )


PUBLICATION_OBJECTIVES: dict[str, dict[str, Any]] = {
    "announcement": {
        "label": "Анонс",
        "goal": "Привести людей на конкретное событие.",
        "rules": (
            "Пиши только про одно событие.",
            "Сохрани название, дату, время, формат и возрастное ограничение, если они есть в фактах.",
            "Создай интерес к событию, но не выдумывай программу, участников, цены или условия входа.",
            "Не описывай бизнес или площадку вместо события.",
        ),
    },
    "agenda": {
        "label": "Афиша",
        "goal": "Показать ближайшие события одной публикацией.",
        "rules": (
            "Сделай короткую подборку ближайших подтверждённых событий.",
            "На каждое событие дай одну понятную мысль: что это и для кого.",
            "Не превращай афишу в рекламный текст о площадке.",
        ),
    },
    "news": {
        "label": "Новость",
        "goal": "Сообщить о произошедшем изменении.",
        "rules": (
            "Пиши только о факте, который уже произошёл или точно подтверждён.",
            "Не используй новость для анонса будущего события.",
            "Не растягивай новость в общий рассказ о бизнесе.",
        ),
    },
    "story": {
        "label": "История",
        "goal": "Передать атмосферу, эмоцию или закулисный контекст.",
        "rules": (
            "Главная цель — атмосфера, а не продажа.",
            "Расскажи одну короткую историю: подготовка, впечатление гостя, момент события или деталь пространства.",
            "Не добавляй факты, которых нет в исходных данных.",
        ),
    },
    "photo_report": {
        "label": "Фотоотчёт",
        "goal": "Показать, что событие уже состоялось и оставило впечатление.",
        "rules": (
            "Пиши после события.",
            "Передай настроение вечера через детали, людей, свет, музыку или реакцию гостей.",
            "Не выдумывай фотографии, цитаты, количество гостей или отзывы.",
        ),
    },
    "author_story": {
        "label": "История автора",
        "goal": "Заинтересовать личностью участника события.",
        "rules": (
            "Познакомь читателя с артистом, лектором, музыкантом или гостем события.",
            "Не пересказывай биографию.",
            "Покажи одну деталь, которая делает человека интересным.",
        ),
    },
    "case": {
        "label": "Кейс",
        "goal": "Показать результат или понятную историю клиента.",
        "rules": (
            "Покажи исходную задачу, действие и результат только по подтверждённым фактам.",
            "Не выдумывай цифры, до/после, медицинский или финансовый эффект.",
        ),
    },
    "before_after": {
        "label": "До / После",
        "goal": "Продать результат через преображение клиента.",
        "rules": (
            "Используй только если есть фото, результат или конкретная задача клиента.",
            "Не описывай технику работы вместо результата.",
            "Покажи, что изменилось в ощущениях человека.",
        ),
    },
    "master_work": {
        "label": "Работа мастера",
        "goal": "Показать экспертизу мастера через решение и выбор.",
        "rules": (
            "Покажи, как мастер принимает решение.",
            "Объясни простым языком, почему выбран цвет, длина, форма, уход или материал.",
            "Не превращай публикацию в резюме мастера.",
        ),
    },
    "advice": {
        "label": "Совет",
        "goal": "Дать пользу без прямой продажи.",
        "rules": (
            "Дай один практический совет.",
            "Не начинай с продажи и не превращай совет в список услуг.",
            "В конце можно мягко дать следующий шаг без рекламного нажима.",
        ),
    },
    "promo": {
        "label": "Акция",
        "goal": "Мотивировать прийти сейчас.",
        "rules": (
            "Используй акцию только если скидка, цена, подарок или срок есть в фактах.",
            "Если фактов акции нет, напиши нейтральный повод прийти без слова «акция».",
        ),
    },
    "seasonal": {
        "label": "Сезонная публикация",
        "goal": "Использовать календарный или локальный повод.",
        "rules": (
            "Свяжи тему с текущим сезоном, датой или локальным поводом.",
            "Не добавляй сезонность, если она не следует из темы или источника идеи.",
        ),
    },
    "atmosphere": {
        "label": "Атмосфера",
        "goal": "Напомнить, зачем люди приходят на культурные события.",
        "rules": (
            "Пиши без программы и без афиши.",
            "Опиши один вечер через ощущения: свет, звук, паузы, разговоры, ожидание или послевкусие.",
            "Не продавай и не перечисляй мероприятия.",
        ),
    },
    "faq": {
        "label": "FAQ",
        "goal": "Ответить на один популярный вопрос.",
        "rules": (
            "Ответь на один вопрос, не на несколько сразу.",
            "Пиши коротко и практично.",
            "Если точного ответа нет в фактах, не выдумывай его.",
        ),
    },
    "client_mistake": {
        "label": "Ошибка клиента",
        "goal": "Показать экспертность через спокойное объяснение ошибки.",
        "rules": (
            "Разбери только одну распространённую ошибку.",
            "Не пугай и не стыди клиента.",
            "Дай спокойное решение.",
        ),
    },
    "myth": {
        "label": "Миф или правда",
        "goal": "Обучить и снять неверное представление.",
        "rules": (
            "Разбери один миф или вопрос.",
            "Пиши спокойно и доказательно, без категоричности.",
            "Не обещай медицинский или гарантированный результат.",
        ),
    },
    "review_social_proof": {
        "label": "Отзыв",
        "goal": "Дать социальное доказательство через реальную проблему клиента.",
        "rules": (
            "Опирайся только на настоящий отзыв или подтверждённый сигнал.",
            "Не копируй отзыв дословно.",
            "Покажи, какую проблему помог решить салон.",
        ),
    },
    "service_intro": {
        "label": "Знакомство с услугой",
        "goal": "Объяснить, кому подходит услуга и какую задачу решает.",
        "rules": (
            "Не описывай услугу как прайс-лист.",
            "Ответь: для кого это, какую проблему решает и что изменится после.",
            "Не добавляй цены, сроки и гарантии, если их нет в фактах.",
        ),
    },
    "brand_story": {
        "label": "История бренда",
        "goal": "Объяснить выбор косметики, материалов или подхода.",
        "rules": (
            "Расскажи, почему выбран бренд, материал или производитель.",
            "Покажи пользу для клиента простым языком.",
            "Не делай рекламный обзор бренда.",
        ),
    },
    "today": {
        "label": "Сегодня в салоне",
        "goal": "Показать живой день и актуальный контекст.",
        "rules": (
            "Покажи, что происходит сегодня.",
            "Не продавай напрямую.",
            "Используй конкретный живой повод: цвет, выпускные, новый уход, подготовка, сезон.",
        ),
    },
    "behind_scenes": {
        "label": "Behind the scenes",
        "goal": "Показать процесс, подготовку или работу команды.",
        "rules": (
            "Покажи один процесс: подготовку, репетицию, настройку, сборку или работу команды.",
            "Не выдумывай закулисье, если оно не следует из темы или фактов.",
        ),
    },
    "selection": {
        "label": "Подборка",
        "goal": "Помочь выбрать из нескольких вариантов.",
        "rules": (
            "Сделай короткую подборку из подтверждённых услуг, событий или вариантов.",
            "У каждого пункта должна быть своя причина выбрать.",
            "Не добавляй варианты, которых нет в фактах.",
        ),
    },
    "quote": {
        "label": "Цитата",
        "goal": "Построить публикацию вокруг одной сильной мысли.",
        "rules": (
            "Используй только одну цитату, если она есть в фактах.",
            "Не объясняй цитату слишком подробно.",
            "Дай читателю самому задуматься.",
        ),
    },
    "reminder": {
        "label": "Напоминание",
        "goal": "Напомнить о близком событии или действии.",
        "rules": (
            "Пиши коротко: что, когда и что сделать сейчас.",
            "Не пересказывай всю афишу и не описывай бизнес.",
            "Сохрани дату и время, если они есть в теме.",
        ),
    },
}


def _normalized_publication_blob(item: dict[str, Any]) -> str:
    return " ".join(
        str(item.get(key) or "")
        for key in ("content_type", "source_kind", "theme", "goal", "source_ref", "seo_keyword")
    ).lower().replace("ё", "е")


def _normalize_publication_objective(item: dict[str, Any]) -> str:
    blob = _normalized_publication_blob(item)
    content_type = str(item.get("content_type") or "").strip().lower()
    if any(marker in blob for marker in ("до после", "до / после", "до/после", "преображен", "преображение", "результат клиента", "хорошие фото")):
        return "before_after"
    if any(marker in blob for marker in ("отзыв", "новый отзыв", "социальное доказательство")):
        return "review_social_proof"
    if any(marker in blob for marker in ("работа мастера", "решение мастера", "как мастер", "почему выбран", "почему выбрана")):
        return "master_work"
    if any(marker in blob for marker in ("ошибка клиент", "ошибки клиент", "распространенная ошибка", "распространённая ошибка")):
        return "client_mistake"
    if any(marker in blob for marker in ("миф", "правда", "растущую луну", "частое мытье", "частое мытьё")):
        return "myth"
    if any(marker in blob for marker in ("новый мастер", "история мастера", "познакомить с мастером")):
        return "author_story"
    if any(marker in blob for marker in ("новая услуга", "знакомство с услугой", "для кого услуга", "какую проблему решает")):
        return "service_intro"
    if any(marker in blob for marker in ("новый цвет", "новая техника", "новый уход", "новая коллекция", "новый материал")):
        return "news"
    if any(marker in blob for marker in ("история бренда", "почему выбрали", "почему работаете", "косметик", "производител")):
        return "brand_story"
    if any(marker in blob for marker in ("сегодня в салоне", "сегодня красим", "сегодня готовимся", "сегодня приехала")):
        return "today"
    if any(marker in blob for marker in ("напомин", "через два дня", "завтра", "сегодня")):
        return "reminder"
    if any(marker in blob for marker in ("цитат", "сильная мысль", "мысль лектора")):
        return "quote"
    if any(marker in blob for marker in ("фотоотчет", "фотоотчёт", "после мероприятия", "прошедшего события", "итоги прошед")):
        return "photo_report"
    if any(marker in blob for marker in ("за кулис", "репетиц", "подготовк", "процесс", "свет", "звук")):
        return "behind_scenes"
    if any(marker in blob for marker in ("история автора", "автор", "лектор", "артист", "музыкант", "участник события", "резидент")):
        return "author_story"
    if any(marker in blob for marker in ("атмосфер", "одного вечера", "вечер без афиши", "нет инфоповодов")):
        return "atmosphere"
    if any(marker in blob for marker in ("ближайшее событие", "одно событие", "конкретное событие")):
        return "announcement"
    if any(marker in blob for marker in ("афиша", "подборк", "ближайшие события", "события июля", "5 ", "3 ", "4 идеи")):
        return "agenda"
    if any(marker in blob for marker in ("анонс", "событие", "концерт", "лекци", "стендап", "спектак", "выставк")) or content_type == "event":
        return "announcement"
    if any(marker in blob for marker in ("faq", "вопрос", "можно ли", "как проходит", "что взять", "когда откры")):
        return "faq"
    if any(marker in blob for marker in ("behind",)):
        return "behind_scenes"
    if any(marker in blob for marker in ("истори", "атмосфер", "впечатлен", "community", "space")):
        return "story"
    if any(marker in blob for marker in ("кейс", "до после", "результат клиента")):
        return "case"
    if any(marker in blob for marker in ("совет", "как выбрать", "как подготов")):
        return "advice"
    if any(marker in blob for marker in ("акци", "скидк", "промо", "sale")) or content_type == "sales":
        return "promo"
    if "seasonal" in blob or "сезон" in blob:
        return "seasonal"
    if any(marker in blob for marker in ("новост", "появил", "открыл", "изменил", "обновил")):
        return "news"
    if content_type in {"service", "seo", "audit"}:
        return "advice"
    return "news"


def _publication_objective_prompt_block(industry_key: str, item: dict[str, Any]) -> str:
    objective_key = _normalize_publication_objective(item)
    objective = PUBLICATION_OBJECTIVES.get(objective_key) or PUBLICATION_OBJECTIVES["news"]
    industry_specific: list[str] = []
    if str(industry_key or "") == "culture":
        culture_common = [
            "Сначала определи контекст: что сейчас происходит в жизни площадки.",
            "До события подходят анонс, подготовка за кулисами или история автора.",
            "За 1-3 дня до события подходит короткое напоминание.",
            "После события подходят история, фотоотчёт или цитата.",
            "Если событий нет, подходят атмосфера, FAQ, сезонный повод или подборка.",
            "Не используй фразы: «Культурный центр», «Мы приглашаем», «У нас проходят», «Уточнить можно».",
            "Не используй клише: уникальный, незабываемый, прекрасная возможность, не пропустите.",
            "Главная задача — заинтересовать, а не описать площадку.",
        ]
        if objective_key == "announcement":
            industry_specific = culture_common + [
                "Ты опытный культурный редактор.",
                "Для культурного центра анонс должен вызывать желание прийти на конкретное мероприятие.",
                "Не описывай культурный центр и не перечисляй всю афишу.",
                "Покажи, почему именно это событие интересно.",
                "Передай атмосферу, но не пересказывай программу.",
                "Используй короткие предложения.",
                "Заканчивай мягким приглашением без рекламного нажима.",
            ]
        elif objective_key in {"agenda", "selection"}:
            industry_specific = culture_common + [
                "Для культурного центра афиша помогает выбрать событие, а не рекламирует площадку.",
                "По одному короткому предложению на каждое событие.",
                "Покажи, кому событие может понравиться.",
            ]
        elif objective_key == "reminder":
            industry_specific = culture_common + [
                "Создай ощущение, что событие уже совсем скоро.",
                "Не пересказывай афишу.",
                "Не повторяй предыдущий анонс.",
                "Максимум 700 символов.",
            ]
        elif objective_key in {"story", "photo_report"}:
            industry_specific = culture_common + [
                "Для культурного центра история должна передавать атмосферу события, подготовки или впечатлений.",
                "Опиши, что происходило на мероприятии и какую реакцию это вызвало.",
                "Пусть человек почувствует, что пропустил интересный вечер.",
            ]
        elif objective_key == "behind_scenes":
            industry_specific = culture_common + [
                "Покажи подготовку: людей, репетицию, свет, звук или детали.",
                "Главное — ощущение живого процесса.",
                "Не продавай событие напрямую.",
            ]
        elif objective_key == "author_story":
            industry_specific = culture_common + [
                "Не пересказывай биографию.",
                "Покажи, что делает участника события интересным.",
                "Свяжи личность с ожиданием события.",
            ]
        elif objective_key == "atmosphere":
            industry_specific = culture_common + [
                "Опиши атмосферу одного вечера без программы и афиши.",
                "Пиши через ощущения: свет, музыку, паузы, разговоры после мероприятия.",
            ]
        elif objective_key == "quote":
            industry_specific = culture_common + [
                "Возьми одну сильную мысль лектора, артиста или гостя.",
                "Не объясняй её полностью.",
                "Построй вокруг неё короткую публикацию.",
            ]
        elif objective_key == "faq":
            industry_specific = culture_common + [
                "Для культурного центра FAQ отвечает на практический вопрос посетителя: вход, дети, время, парковка, запись.",
                "Отвечай только на один вопрос.",
                "Не объединяй несколько вопросов в одной публикации.",
            ]
        elif objective_key == "seasonal":
            industry_specific = culture_common + [
                "Свяжи сезон с культурной жизнью только если связь естественная.",
                "Если повод выглядит искусственным, не используй его.",
            ]
    if str(industry_key or "") == "beauty":
        beauty_common = [
            "Сначала определи маркетинговую цель публикации: привлечение, доверие, запись, возврат, удержание или сарафан.",
            "Потом выбери форму текста под контекст: фото результата, отзыв, новая услуга, мало записей, частый вопрос, сезон, пустая неделя или новый мастер.",
            "Не начинай с описания салона.",
            "Не используй фразы: «Салон красоты», «Мы предлагаем», «У нас есть», «Успейте записаться».",
            "Не используй клише: идеальный образ, роскошный результат, преобразитесь, будь лучшей версией себя.",
            "Не обещай медицинский, гарантированный или вечный результат.",
            "Главная задача — показать пользу, ощущение и понятный следующий шаг.",
        ]
        if objective_key == "before_after":
            industry_specific = beauty_common + [
                "Ты опытный beauty-копирайтер.",
                "Пиши про преображение клиента, а не про технику работы.",
                "Покажи, что изменилось в ощущениях человека.",
                "Пусть читатель представит себя на месте клиента.",
                "Заканчивай мягким приглашением записаться.",
            ]
        elif objective_key == "case":
            industry_specific = beauty_common + [
                "Расскажи историю клиента: с какой задачей пришёл, почему это было важно, что изменилось.",
                "Не выдумывай детали, эмоции, диагнозы, цифры или результат.",
                "Не используй рекламные штампы.",
            ]
        elif objective_key == "master_work":
            industry_specific = beauty_common + [
                "Покажи, как мастер принимает решения.",
                "Объясни простым языком, почему выбран именно такой цвет, длина, форма, уход или материал.",
                "Сделай фокус на экспертизе, а не на продаже.",
            ]
        elif objective_key == "advice":
            industry_specific = beauty_common + [
                "Дай один практический совет: как сохранить цвет, ухаживать летом, выбрать домашний уход или подготовиться к визиту.",
                "Не продавай услугу внутри совета.",
                "Оставь ощущение пользы и спокойной экспертности.",
            ]
        elif objective_key == "client_mistake":
            industry_specific = beauty_common + [
                "Расскажи об одной распространённой ошибке клиента.",
                "Не пугай и не обвиняй.",
                "Спокойно объясни, что делать вместо этого.",
            ]
        elif objective_key == "behind_scenes":
            industry_specific = beauty_common + [
                "Покажи один закулисный процесс: начало дня, рабочее место, стерилизацию, выбор материалов или подготовку мастера.",
                "Пиши через детали и безопасность, не через рекламу.",
            ]
        elif objective_key == "author_story":
            industry_specific = beauty_common + [
                "Познакомь с мастером через человека, а не через резюме.",
                "Лучше показать, почему мастер выбрал профессию или за что любит работу.",
                "Не перечисляй стаж, дипломы и услуги списком.",
            ]
        elif objective_key == "news":
            industry_specific = beauty_common + [
                "Используй новость только если появилось что-то новое: мастер, цвет, техника, уход, материал или формат.",
                "Объясни, почему это интересно и кому подходит.",
                "Не превращай новость в общий рекламный текст.",
            ]
        elif objective_key == "promo":
            industry_specific = beauty_common + [
                "Покажи, почему сейчас хороший момент записаться.",
                "Не пиши «успейте» и не дави срочностью без факта срока.",
                "Если скидки или срока нет в фактах, не выдумывай их.",
            ]
        elif objective_key == "seasonal":
            industry_specific = beauty_common + [
                "Свяжи сезон с уходом, цветом, стрижкой, образом, отпуском, выпускным или праздником.",
                "Не натягивай праздник, если связь искусственная.",
            ]
        elif objective_key == "faq":
            industry_specific = beauty_common + [
                "Сними один страх или сомнение: больно ли, сколько держится, можно ли беременным, сколько длится процедура.",
                "Отвечай на один вопрос, не делай FAQ-список.",
                "Если факта нет, не выдумывай медицинский ответ.",
            ]
        elif objective_key == "review_social_proof":
            industry_specific = beauty_common + [
                "Возьми настоящий отзыв как источник смысла, но не копируй его дословно.",
                "Покажи, какую проблему решил салон.",
                "Сохрани человеческий тон без самохвальства.",
            ]
        elif objective_key == "myth":
            industry_specific = beauty_common + [
                "Разбери один миф или вопрос: растущая луна, частое мытьё, бассейн после окрашивания и похожие темы.",
                "Объясни спокойно и просто.",
                "Не делай категоричных обещаний.",
            ]
        elif objective_key == "atmosphere":
            industry_specific = beauty_common + [
                "Опиши один обычный вечер или момент в салоне.",
                "Пиши через кофе, разговоры, музыку, запах, свет и ощущение спокойствия.",
                "Не перечисляй услуги.",
            ]
        elif objective_key == "selection":
            industry_specific = beauty_common + [
                "Сделай подборку, которая помогает выбрать: оттенки лета, идеи для отпуска, стрижки для жары, варианты ухода.",
                "У каждого пункта должна быть короткая причина.",
                "Не добавляй варианты, которых нет в фактах.",
            ]
        elif objective_key == "reminder":
            industry_specific = beauty_common + [
                "Напомни о поводе: выпускной, отпуск, праздник, сезон или регулярный уход.",
                "Не продавай агрессивно.",
                "Покажи, почему лучше подумать о записи заранее.",
            ]
        elif objective_key == "service_intro":
            industry_specific = beauty_common + [
                "Это не описание услуги.",
                "Ответь: для кого услуга, какую проблему решает, что изменится после.",
                "Пиши без прайс-листа и без неподтверждённых обещаний.",
            ]
        elif objective_key == "brand_story":
            industry_specific = beauty_common + [
                "Расскажи, почему выбран бренд косметики, материал или производитель.",
                "Объясни, что это даёт клиенту.",
                "Не делай рекламный обзор бренда.",
            ]
        elif objective_key == "today":
            industry_specific = beauty_common + [
                "Покажи живой формат «сегодня в салоне».",
                "Например: сегодня красим в медный, готовимся к выпускным, приехала новая коллекция ухода.",
                "Не продавай напрямую; покажи жизнь салона.",
            ]
    lines = [
        f"Тип публикации: {objective['label']}",
        f"Бизнес-задача: {objective['goal']}",
        "Правила типа публикации:",
        *[f"- {rule}" for rule in objective.get("rules") or ()],
        "Общие правила контент-движка:",
        "- Одна публикация = одна идея.",
        "- Не начинай публикацию с описания компании.",
        "- Не повторяй описание карточки.",
        "- Не перечисляй все услуги или все направления.",
        "- Не используй рекламные штампы.",
    ]
    if industry_specific:
        lines.extend(["Правила ниши:", *[f"- {rule}" for rule in industry_specific]])
    return "\n".join(lines)


def _content_matrix_prompt_key(industry_key: str, objective_key: str) -> str:
    clean_industry = re.sub(r"[^0-9a-z_]+", "_", str(industry_key or "local_business").strip().lower())
    clean_objective = re.sub(r"[^0-9a-z_]+", "_", str(objective_key or "news").strip().lower())
    return f"content_matrix.{clean_industry or 'local_business'}.{clean_objective or 'news'}"


def _load_publication_matrix_override(cursor: Any, industry_key: str, objective_key: str) -> str:
    prompt_key = _content_matrix_prompt_key(industry_key, objective_key)
    try:
        cursor.execute(
            "SELECT prompt_text FROM aiprompts WHERE prompt_type = %s LIMIT 1",
            (prompt_key,),
        )
        row = cursor.fetchone()
        return str(_row_get(row, "prompt_text", 0, "") or "").strip()
    except Exception:
        return ""


def _fallback_draft_text(
    business_name: str,
    item: dict[str, Any],
    business_facts: dict[str, Any] | None = None,
    language: str | None = None,
) -> str:
    normalized_language = _normalize_content_plan_language(language)
    theme = str(item.get("theme") or "Новость компании").strip()
    keyword = str(item.get("seo_keyword") or "").strip()
    goal = str(item.get("goal") or "").strip()
    facts = business_facts if isinstance(business_facts, dict) else {}
    service_names = _relevant_service_names_for_item(facts.get("services"), item)
    lower_identity = " ".join(
        [
            business_name,
            str(facts.get("business_type") or ""),
            str(facts.get("industry") or ""),
            str(facts.get("categories") or ""),
            theme,
            goal,
        ]
    ).lower()

    if "riderra" in lower_identity:
        if normalized_language == "en":
            return (
                "Riderra helps plan an airport transfer in advance: add the route, flight number, destination address, "
                "number of passengers, and luggage details when booking. This makes it easier to prepare the trip before arrival "
                "and confirm the route details. Transfers can be booked online at riderra.com."
            )
        return (
            "Riderra помогает заранее спланировать трансфер из аэропорта: при заказе стоит указать маршрут, "
            "номер рейса, адрес назначения, количество пассажиров и багаж. Так проще подготовить поездку до прилёта "
            "и проверить детали маршрута. Забронировать трансфер можно онлайн на riderra.com."
        )

    if normalized_language == "en":
        city = str(facts.get("city") or "").strip()
        city_text = f" in {city}" if city else ""
        directions = ", ".join(service_names[:5]) if service_names else "the available services"
        if service_names:
            return (
                f"{business_name}{city_text}: {theme}. The listing includes: {directions}. "
                "Choose the service that matches your current need and check the details before booking. "
                "Contact information is available in the listing."
            )
        lines = [f"{business_name}{city_text}: {theme}."]
        if keyword:
            lines.append(f"This also helps answer the local search query: {keyword}.")
        if goal:
            lines.append(goal)
        lines.append("Details, booking, and current offers can be checked through the contacts in the listing.")
        return " ".join(lines)

    if bool(facts.get("is_cultural_space")):
        objective_key = _normalize_publication_objective(item)
        directions = ", ".join(service_names[:5])
        clean_theme = theme.rstrip(".")
        clean_goal = goal.rstrip(".")
        if objective_key in {"announcement", "reminder"}:
            return (
                f"{clean_theme}. "
                f"{clean_goal + '. ' if clean_goal else 'Это событие из афиши площадки. '}"
                "Дата, время и запись — в карточке."
            )
        if objective_key in {"agenda", "selection"} and directions:
            return (
                f"В ближайшей афише: {directions}. "
                "Выберите событие по настроению и проверьте дату, время и условия посещения в карточке."
            )
        if objective_key in {"story", "photo_report", "behind_scenes", "author_story", "atmosphere", "quote"}:
            return (
                f"{clean_theme}. "
                "Такие публикации помогают почувствовать атмосферу события ещё до визита. "
                "Ближайшие даты и запись — в карточке."
            )
        if directions:
            return (
                f"{clean_theme}. В афише и направлениях: {directions}. "
                "Дата, время и запись — в карточке."
            )
        return (
            f"{theme.rstrip('.') + '.' if theme else 'Ближайшие события появятся в карточке.'} "
            "Дата, время и запись — в карточке."
        )

    if "school" in lower_identity or "школ" in lower_identity or "образован" in lower_identity:
        city = str(facts.get("city") or "").strip()
        city_text = f" в {city}" if city else ""
        if _is_general_school_intro_topic(theme, goal):
            directions = ", ".join(service_names[:5]) if service_names else "подготовка к школе, английский, программирование и творческие направления"
            return (
                f"{business_name}{city_text} — школа и пространство для детей и подростков. "
                f"В карточке можно выбрать направление под возраст и интересы ребёнка: {directions}. "
                "Такой формат помогает поддерживать учебный ритм, развивать самостоятельность и пробовать новые навыки. "
                "Подробности и запись можно уточнить по контактам в карточке."
            )
        directions = service_names[0] if service_names else theme
        focus = theme.rstrip(".")
        goal_sentence = _school_goal_sentence(goal)
        return (
            f"{business_name}{city_text}: {focus}. "
            f"В фокусе публикации — {directions}. {goal_sentence} "
            "Подробности и запись можно уточнить по контактам в карточке."
        )

    if "салон красоты" in lower_identity or "парикмахер" in lower_identity:
        objective_key = _normalize_publication_objective(item)
        clean_theme = theme.rstrip(".")
        if objective_key == "before_after":
            return (
                f"{clean_theme}. Такая публикация показывает результат через ощущение клиента после визита. "
                "Если есть реальные фото или задача клиента, используйте их как главный факт. Запись — по контактам в карточке."
            )
        if objective_key in {"case", "review_social_proof"}:
            return (
                f"{clean_theme}. В фокусе — задача клиента и то, что изменилось после визита. "
                "Опирайтесь только на реальные отзывы или подтверждённые детали. Запись — по контактам в карточке."
            )
        if objective_key in {"master_work", "author_story"}:
            return (
                f"{clean_theme}. Покажите, как мастер принимает решение и почему выбран именно такой подход. "
                "Пишите простым языком, без резюме и списка услуг. Запись — по контактам в карточке."
            )
        if objective_key in {"advice", "client_mistake", "myth", "faq"}:
            return (
                f"{clean_theme}. Дайте один спокойный и практичный ответ без запугивания и агрессивной продажи. "
                "Если точных фактов нет, не выдумывайте медицинские обещания. Запись — по контактам в карточке."
            )
        if objective_key in {"atmosphere", "behind_scenes", "today"}:
            return (
                f"{clean_theme}. Покажите один живой момент салона: детали, материалы, свет, разговоры или подготовку рабочего места. "
                "Не перечисляйте все услуги. Запись — по контактам в карточке."
            )
        if objective_key in {"service_intro", "brand_story", "news", "seasonal", "selection", "reminder", "promo"}:
            return (
                f"{clean_theme}. Объясните, для кого это актуально и какую задачу помогает решить. "
                "Не добавляйте цены, сроки и скидки, если их нет в фактах. Запись — по контактам в карточке."
            )
        return (
            f"{clean_theme}. Выберите один фокус: результат, доверие, запись, возврат, удержание или рекомендация. "
            "Публикация должна помогать клиенту понять следующий шаг. Запись — по контактам в карточке."
        )

    if service_names:
        directions = ", ".join(service_names[:5])
        return (
            f"{business_name}: {theme}. В карточке представлены направления: {directions}. "
            f"{goal.rstrip('.') + '.' if goal else 'Можно выбрать услугу под текущую задачу и уточнить детали перед записью.'} "
            "Подробности и запись можно уточнить по контактам в карточке."
        )

    lines = [f"{business_name}: {theme}."]
    if keyword:
        lines.append(f"Это также помогает закрыть спрос по запросу: {keyword}.")
    if goal:
        lines.append(goal)
    lines.append("Подробности, запись или актуальные предложения можно уточнить по контактам в карточке.")
    return " ".join(lines)


def _normalize_fact_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        parsed = json.loads(text)
    except Exception:
        parsed = None
    if isinstance(parsed, list):
        return ", ".join(str(item).strip() for item in parsed if str(item).strip())
    if isinstance(parsed, dict):
        return ", ".join(str(item).strip() for item in parsed.values() if str(item).strip())
    return text


def _content_plan_business_facts(business_row: Any, item: dict[str, Any]) -> dict[str, Any]:
    name = str(_row_get(business_row, "name", 0, "Бизнес") or "Бизнес").strip() or "Бизнес"
    city = str(_row_get(business_row, "city", 1, "") or "").strip()
    business_type = _normalize_fact_text(_row_get(business_row, "business_type", 2, ""))
    industry = _normalize_fact_text(_row_get(business_row, "industry", 3, ""))
    categories = _normalize_fact_text(_row_get(business_row, "categories", 4, ""))
    address = _normalize_fact_text(_row_get(business_row, "address", 5, ""))
    description = _normalize_fact_text(_row_get(business_row, "description", 6, ""))
    site = _normalize_fact_text(_row_get(business_row, "site", 7, ""))
    website = _normalize_fact_text(_row_get(business_row, "website", 8, ""))
    website_url = site or website
    site_description = _fetch_site_description(website_url)
    theme = str(item.get("theme") or "").strip()
    goal = str(item.get("goal") or "").strip()
    combined = " ".join([name, business_type, industry, categories, description, site_description, theme, goal]).lower()
    cultural_markers = [
        "культур",
        "галере",
        "лекци",
        "лектор",
        "концерт",
        "пространств",
        "практикум",
        "образован",
        "событи",
        "выстав",
    ]
    ice_markers = ["лед", "лёд", "коньк", "катани", "зимн", "каток на льду"]
    is_cultural_space = any(marker in combined for marker in cultural_markers)
    return {
        "name": name,
        "city": city,
        "business_type": business_type,
        "industry": industry,
        "categories": categories,
        "address": address,
        "description": description,
        "site": website_url,
        "site_description": site_description,
        "is_cultural_space": is_cultural_space,
        "ice_markers": ice_markers,
    }


def _load_content_plan_service_facts(cursor: Any, business_id: str, limit: int = 10) -> str:
    try:
        cursor.execute(
            """
            SELECT name, description, category
            FROM userservices
            WHERE business_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (business_id, limit),
        )
        rows = cursor.fetchall() or []
    except Exception:
        return ""
    lines: list[str] = []
    for row in rows:
        name = _normalize_fact_text(_row_get(row, "name", 0, ""))
        category = _normalize_fact_text(_row_get(row, "category", 2, ""))
        description = _normalize_fact_text(_row_get(row, "description", 1, ""))
        if not name:
            continue
        detail_parts = [part for part in [category, description[:180]] if part]
        detail = f" ({'; '.join(detail_parts)})" if detail_parts else ""
        lines.append(f"- {name}{detail}")
    return "\n".join(lines)


def _build_content_plan_business_fact_block(facts: dict[str, Any]) -> str:
    lines = [
        f"Название/бренд: {facts.get('name') or 'Бизнес'}",
        f"Город: {facts.get('city') or 'не указан'}",
        f"Тип бизнеса: {facts.get('business_type') or 'не указан'}",
        f"Индустрия: {facts.get('industry') or 'не указана'}",
        f"Категории на картах: {facts.get('categories') or 'не указаны'}",
        f"Адрес: {facts.get('address') or 'не указан'}",
        f"Описание карточки: {facts.get('description') or 'не указано'}",
        f"Сайт: {facts.get('site') or 'не указан'}",
        f"Описание с сайта: {facts.get('site_description') or 'не найдено'}",
        f"Реальные услуги/направления:\n{facts.get('services') or 'не указаны'}",
        (
            "Название бизнеса может быть метафорой или брендом. "
            "Не выводи сферу деятельности из одного названия: опирайся на тип, категории, описание, тему и цель."
        ),
    ]
    if facts.get("is_cultural_space"):
        lines.append(
            "Фактическая сфера: культурное пространство для лекций, концертов, камерных событий, практикумов и встреч."
        )
        lines.append(
            "Запрещено писать про лёд, коньки, катание, зимние развлечения и ледовую площадку, если это явно не указано в теме или цели."
        )
    return "\n".join(lines)


def _looks_like_ice_rink_hallucination(text: str, facts: dict[str, Any]) -> bool:
    if not bool(facts.get("is_cultural_space")):
        return False
    lower_text = str(text or "").lower()
    return any(marker in lower_text for marker in facts.get("ice_markers", []))


def _content_plan_draft_needs_fallback(text: str, facts: dict[str, Any]) -> bool:
    lower_text = str(text or "").lower()
    if not lower_text.strip():
        return True
    if bool(facts.get("is_cultural_space")):
        school_markers = ["школ", "учебн", "обучен", "детей и подростков", "ребенка", "ребёнка"]
        if any(marker in lower_text for marker in school_markers):
            return True
    technical_markers = [
        "manual_strategy:",
        "google_doc",
        "source_ref",
        "seo-запрос",
    ]
    if any(marker in lower_text for marker in technical_markers):
        return True
    empty_marketing_markers = [
        "профессиональные мастера",
        "профессиональная команда",
        "профессиональные стриж",
        "профессиональные услуг",
        "профессиональные процедур",
        "профессиональные женские",
        "ждут вас",
        "лично в салоне",
        "откройте для себя",
        "приходите к нам",
        "уютное пространство",
        "стильный салон",
        "без лишних хлопот",
        "без забот",
        "идеальный выбор",
        "наслаждайтесь комфортом",
        "приглашает",
        "уникальн",
        "пробное занят",
        "очно или онлайн",
        "онлайн?",
        "комфорте и качестве",
        "комфорт и качество",
        "сияния кожи",
        "эффектом омбре",
        "омбре",
        "без лишнего декора",
    ]
    if any(marker in lower_text for marker in empty_marketing_markers):
        return True
    combined_facts = " ".join(
        [
            str(facts.get("business_type") or ""),
            str(facts.get("industry") or ""),
            str(facts.get("categories") or ""),
            str(facts.get("services") or ""),
        ]
    ).lower()
    event_markers = ["концерт", "лекци", "мастерск", "событи", "встреч"]
    if not bool(facts.get("is_cultural_space")) and any(marker in lower_text for marker in event_markers):
        if not any(marker in combined_facts for marker in event_markers):
            return True
    return False


def _sanitize_generated_news_text(raw_text: str) -> str:
    text = str(raw_text or "").strip()
    if not text:
        return ""

    fenced_match = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    if fenced_match:
        text = str(fenced_match.group(1) or "").strip()

    payload_candidates = [text]
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace >= 0 and last_brace > first_brace:
        payload_candidates.append(text[first_brace:last_brace + 1])

    for candidate in payload_candidates:
        try:
            parsed = json.loads(candidate)
        except Exception:
            continue
        if isinstance(parsed, dict):
            for key in ("news", "text", "content", "draft"):
                value = str(parsed.get(key) or "").strip()
                if value:
                    text = value
                    break
        elif isinstance(parsed, str):
            text = parsed.strip()
        if text:
            break

    text = text.replace("\\n", "\n")
    text = re.sub(r"[*_`]+", "", text)
    text = re.sub(r"^\s*#+\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"#[\wа-яА-ЯёЁ-]+", "", text)
    text = text.replace("{", "").replace("}", "")
    text = "".join(
        char
        for char in text
        if unicodedata.category(char) not in {"So", "Sk"}
    )
    text = re.sub(r"\s+", " ", text).strip()
    return text


def generate_draft_for_plan_item(user_id: str, item_id: str, language: str | None = None) -> dict[str, Any]:
    normalized_language = _normalize_content_plan_language(language)
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_content_plan_tables(cursor)
        cursor.execute(
            """
            SELECT i.id, i.plan_id, i.business_id, i.theme, i.goal, i.content_type, i.source_kind, i.source_ref,
                   i.seo_keyword, i.seo_views, i.service_id, i.transaction_id, i.location_scope,
                   i.usernews_id,
                   p.business_id AS root_business_id
            FROM contentplanitems i
            JOIN contentplans p ON p.id = i.plan_id
            WHERE i.id = %s
            LIMIT 1
            """,
            (item_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise ValueError("Элемент плана не найден")
        item = _row_to_dict(cursor, row)
        owner_id = get_business_owner_id(cursor, str(item.get("root_business_id") or ""))
        if str(owner_id or "").strip() != str(user_id or "").strip():
            cursor.execute("SELECT COALESCE(is_superadmin, FALSE) FROM users WHERE id = %s", (user_id,))
            if not bool(_row_get(cursor.fetchone(), "coalesce", 0, False)):
                raise PermissionError("Нет доступа к элементу плана")
        cursor.execute(
            """
            SELECT name, city, business_type, industry, categories, address, description, site, website
            FROM businesses
            WHERE id = %s
            """,
            (item.get("business_id"),),
        )
        business_row = cursor.fetchone()
        business_facts = _content_plan_business_facts(business_row, item)
        business_facts["services"] = _load_content_plan_service_facts(
            cursor,
            str(item.get("business_id") or ""),
            limit=12,
        )
        business_name = str(business_facts.get("name") or "Бизнес").strip() or "Бизнес"
        business_type = str(business_facts.get("business_type") or "").strip()
        industry_key = detect_industry_key(
            business_name=business_name,
            business_type=business_type,
            industry=business_facts.get("industry"),
            categories=business_facts.get("categories"),
            service_text=str(item.get("theme") or ""),
        )
        industry_pattern_context = format_industry_pattern_prompt(industry_key, mode="news")
        active_patterns = load_active_industry_patterns(db.conn, industry_key, "news")
        active_pattern_text = format_loaded_active_industry_patterns(active_patterns)
        if active_pattern_text:
            industry_pattern_context += f"\n{active_pattern_text}"
        source_kind = str(item.get("source_kind") or "").strip()
        publication_objective_key = _normalize_publication_objective(item)
        publication_objective_context = (
            _load_publication_matrix_override(cursor, industry_key, publication_objective_key)
            or _publication_objective_prompt_block(industry_key, item)
        )
        prompt = (
            "Ты — маркетолог локального бизнеса. Напиши короткую новость для публикации на картах. "
            "До 700 символов.\n\n"
            f"{_content_plan_language_instruction(normalized_language)}\n\n"
            "Тип публикации и бизнес-задача:\n"
            f"{publication_objective_context}\n\n"
            "Жёсткие правила:\n"
            "- не возвращай JSON, markdown, эмодзи, хештеги, фигурные скобки или технические символы;\n"
            "- не выдумывай цены, скидки, акции, режим работы, бесплатные консультации, адрес, район, центр города;\n"
            "- не выдумывай пол, возраст или тип аудитории, если этого нет в фактах;\n"
            "- не трактуй название/бренд как услугу или категорию, если это не подтверждено типом бизнеса, категориями или темой;\n"
            "- не добавляй лекции, концерты, мастерские, события, команду, специалистов, атмосферу или оборудование, если этого нет в фактах;\n"
            "- не начинай публикацию с описания компании или карточки;\n"
            "- одна публикация должна раскрывать только одну мысль;\n"
            "- не используй пустые рекламные клише вроде уютное пространство, профессиональная команда, без забот, идеальный выбор;\n"
            "- не используй сезонность, если источник идеи не seasonal;\n"
            "- главная тема новости обязана совпадать с полем «Тема» ниже;\n"
            "- поле «Цель» объясняет, что именно раскрыть; выполни эту цель напрямую;\n"
            "- не превращай узкую тему в общий обзор всех услуг/направлений бизнеса;\n"
            "- реальные услуги/направления используй только как факты, выбирай только те, которые относятся к теме;\n"
            "- если данных мало, пиши нейтрально: что можно уточнить в карточке и как связаться.\n\n"
            "Факты о бизнесе:\n"
            f"{_build_content_plan_business_fact_block(business_facts)}\n\n"
            "Факты о публикации:\n"
            f"Тип публикации: {publication_objective_key}\n"
            f"Тема: {str(item.get('theme') or '').strip()}\n"
            f"Цель: {str(item.get('goal') or '').strip()}\n"
            f"Источник идеи: {source_kind} / {str(item.get('source_ref') or '').strip()}\n"
            f"SEO-запрос: {str(item.get('seo_keyword') or '').strip()}\n"
            f"Частотность SEO-запроса: {int(item.get('seo_views') or 0)}\n"
            f"Дата генерации: {datetime.utcnow().date().isoformat()}\n\n"
            "Рабочие паттерны индустрии:\n"
            f"{industry_pattern_context}\n\n"
            "Верни только готовый текст новости."
        )
        try:
            result = analyze_text_with_gigachat(
                prompt,
                task_type="news_generation",
                business_id=str(item.get("business_id") or ""),
                user_id=user_id,
            )
            generated_text = _sanitize_generated_news_text(str(result or ""))
            if not generated_text:
                generated_text = _fallback_draft_text(business_name, item, business_facts, normalized_language)
        except Exception:
            generated_text = _fallback_draft_text(business_name, item, business_facts, normalized_language)
        if _looks_like_ice_rink_hallucination(generated_text, business_facts) or _content_plan_draft_needs_fallback(generated_text, business_facts):
            generated_text = _fallback_draft_text(business_name, item, business_facts, normalized_language)
        if active_patterns:
            record_industry_pattern_impact_event(
                db.conn,
                active_patterns,
                industry_key=industry_key,
                pattern_type="news",
                business_id=str(item.get("business_id") or ""),
                user_id=user_id,
                source="content_plan_draft",
                event_type="applied",
                result_status="used_in_prompt",
                metrics={"item_id": item_id, "source_kind": source_kind},
            )
            news_impact_metrics = build_pattern_impact_metrics(
                {"generated_text": generated_text},
                "news",
                industry_key=industry_key,
                source_text=(
                    f"{business_name} {business_type} {str(item.get('theme') or '')} "
                    f"{str(item.get('goal') or '')} {str(item.get('seo_keyword') or '')}"
                ),
            )
            record_industry_pattern_impact_event(
                db.conn,
                active_patterns,
                industry_key=industry_key,
                pattern_type="news",
                business_id=str(item.get("business_id") or ""),
                user_id=user_id,
                source="content_plan_draft",
                event_type="result",
                result_status="needs_review" if int(news_impact_metrics.get("needs_review") or 0) > 0 else "good",
                metrics=news_impact_metrics,
            )
        location_scope = str(item.get("location_scope") or item.get("business_id") or "").strip()
        location_meta = _resolve_scope_target_meta(
            cursor,
            str(item.get("business_id") or ""),
            "network_location" if location_scope else "single_business",
            location_scope or str(item.get("business_id") or ""),
        )
        cursor.execute(
            """
            UPDATE contentplanitems
            SET draft_text = %s,
                status = 'draft_generated',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (generated_text, item_id),
        )
        usernews_id = str(item.get("usernews_id") or "").strip()
        if usernews_id:
            _ensure_usernews_table(cursor)
            cursor.execute(
                """
                UPDATE usernews
                SET generated_text = %s,
                    original_generated_text = %s,
                    edited_before_approve = FALSE,
                    approved = 0,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                  AND user_id = %s
                  AND (business_id IS NULL OR business_id = %s)
                """,
                (
                    generated_text,
                    generated_text,
                    usernews_id,
                    user_id,
                    str(item.get("business_id") or ""),
                ),
            )
        _record_content_plan_event(
            conn=db.conn,
            user_id=user_id,
            business_id=str(item.get("root_business_id") or item.get("business_id") or ""),
            capability="content_plan.draft",
            event_type="generated",
            draft_text=generated_text,
            metadata={
                "item_id": item_id,
                "plan_id": str(item.get("plan_id") or ""),
                "source_kind": str(item.get("source_kind") or "").strip(),
                "source_ref": str(item.get("source_ref") or "").strip(),
                "content_type": str(item.get("content_type") or "").strip(),
                "theme": str(item.get("theme") or "").strip(),
                "seo_keyword": str(item.get("seo_keyword") or "").strip(),
                "location_scope": location_scope,
                "location_label": str(location_meta.get("scope_target_label") or "").strip(),
                "language": normalized_language,
                "updated_usernews_id": usernews_id,
            },
        )
        db.conn.commit()
        return get_content_plan(user_id, str(item.get("plan_id") or ""))
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


def create_news_from_plan_item(user_id: str, item_id: str, language: str | None = None) -> dict[str, Any]:
    normalized_language = _normalize_content_plan_language(language)
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_content_plan_tables(cursor)
        _ensure_usernews_table(cursor)
        cursor.execute(
            """
            SELECT i.id, i.plan_id, i.business_id, i.theme, i.goal, i.source_ref, i.draft_text, i.service_id, i.status,
                   i.source_kind, i.content_type, i.location_scope,
                   p.business_id AS root_business_id
            FROM contentplanitems i
            JOIN contentplans p ON p.id = i.plan_id
            WHERE i.id = %s
            LIMIT 1
            """,
            (item_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise ValueError("Элемент плана не найден")
        item = _row_to_dict(cursor, row)
        owner_id = get_business_owner_id(cursor, str(item.get("root_business_id") or ""))
        if str(owner_id or "").strip() != str(user_id or "").strip():
            cursor.execute("SELECT COALESCE(is_superadmin, FALSE) FROM users WHERE id = %s", (user_id,))
            if not bool(_row_get(cursor.fetchone(), "coalesce", 0, False)):
                raise PermissionError("Нет доступа к элементу плана")
        generated_text = str(item.get("draft_text") or "").strip()
        if not generated_text:
            generated_text = _fallback_draft_text("Бизнес", item, language=normalized_language)
        edited_before_accept = str(item.get("status") or "").strip() == "edited"
        news_id = str(uuid.uuid4())
        source_text = "\n".join(
            part
            for part in [
                str(item.get("theme") or "").strip(),
                str(item.get("goal") or "").strip(),
                str(item.get("source_ref") or "").strip(),
            ]
            if part
        )
        cursor.execute(
            """
            INSERT INTO usernews (
                id, user_id, business_id, service_id, source_text, generated_text,
                original_generated_text, edited_before_approve, prompt_key, prompt_version, approved, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, FALSE, 'content_plan', 'v1', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                news_id,
                user_id,
                str(item.get("business_id") or ""),
                str(item.get("service_id") or "").strip() or None,
                source_text,
                generated_text,
                generated_text,
            ),
        )
        cursor.execute(
            """
            UPDATE contentplanitems
            SET usernews_id = %s,
                status = 'draft_generated',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (news_id, item_id),
        )
        location_scope = str(item.get("location_scope") or item.get("business_id") or "").strip()
        location_meta = _resolve_scope_target_meta(
            cursor,
            str(item.get("business_id") or ""),
            "network_location" if location_scope else "single_business",
            location_scope or str(item.get("business_id") or ""),
        )
        _record_content_plan_event(
            conn=db.conn,
            user_id=user_id,
            business_id=str(item.get("root_business_id") or item.get("business_id") or ""),
            capability="content_plan.publish",
            event_type="accepted",
            accepted=True,
            edited_before_accept=edited_before_accept,
            outcome="news_created",
            draft_text=generated_text,
            final_text=generated_text,
            metadata={
                "item_id": item_id,
                "plan_id": str(item.get("plan_id") or ""),
                "news_id": news_id,
                "service_id": str(item.get("service_id") or "").strip(),
                "source_ref": str(item.get("source_ref") or "").strip(),
                "source_kind": str(item.get("source_kind") or "").strip(),
                "content_type": str(item.get("content_type") or "").strip(),
                "theme": str(item.get("theme") or "").strip(),
                "location_scope": location_scope,
                "location_label": str(location_meta.get("scope_target_label") or "").strip(),
                "acceptance_reason": _acceptance_reason(item, edited_before_accept),
                "created_via": "content_plan",
                "language": normalized_language,
            },
        )
        db.conn.commit()
        return get_content_plan(user_id, str(item.get("plan_id") or ""))
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()
