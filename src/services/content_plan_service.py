from __future__ import annotations

import json
import re
import uuid
import unicodedata
from datetime import date, datetime, timedelta
from typing import Any

from database_manager import DatabaseManager
from core.ai_learning import ensure_ai_learning_events_table, record_ai_learning_event
from core.card_audit import build_card_audit_snapshot
from core.helpers import get_business_owner_id
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
        SELECT id, owner_id, name, city, address, network_id, business_type, categories
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
                    "title": f"Недопокрытый поисковый сценарий: {clean_intent}",
                    "problem": "Карточке нужен отдельный контент под этот сценарий выбора.",
                    "priority": "medium",
                    "section": "search",
                    "evidence": clean_intent,
                }
            )
    return signals


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


def _select_context_seo_keywords(
    ranked_keywords: list[dict[str, Any]],
    custom_keywords: list[dict[str, Any]],
    limit: int = 20,
) -> list[dict[str, Any]]:
    if len(custom_keywords) >= 5:
        return _merge_seo_keyword_lists(custom_keywords, [], limit=limit)
    return _merge_seo_keyword_lists(ranked_keywords, custom_keywords, limit=limit)


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

        return {
            "business": {
                "id": str(scope_business_row.get("id") or ""),
                "name": str(scope_business_row.get("name") or "").strip(),
                "city": str(scope_business_row.get("city") or "").strip(),
                "address": str(scope_business_row.get("address") or "").strip(),
                "business_type": str(scope_business_row.get("business_type") or "").strip(),
                "categories": str(scope_business_row.get("categories") or "").strip(),
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
                "selected_scope_label": str(selected_scope_option.get("label") or "").strip() if selected_scope_option else str(scope_business_row.get("name") or "").strip(),
                "selected_scope_description": _scope_description(
                    normalized_scope,
                    str(selected_scope_option.get("label") or scope_business_row.get("name") or "").strip(),
                    str(selected_scope_option.get("city") or scope_business_row.get("city") or "").strip(),
                    str(selected_scope_option.get("address") or scope_business_row.get("address") or "").strip(),
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
            SELECT id, title, scope_type, scope_target_id, period_days, period_start, period_end,
                   plan_status, generation_mode, created_at, updated_at
            FROM contentplans
            WHERE business_id = %s
            ORDER BY created_at DESC
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
                    location_scope, status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'planned')
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
                   seo_keyword, service_id, transaction_id, location_scope, draft_text, status, usernews_id,
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
            item_location_scope = str(_row_get(row, "location_scope", 11, "") or "").strip()
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
                    "location_scope": item_location_scope,
                    "location_label": str(location_meta.get("scope_target_label") or "").strip(),
                    "location_city": str(location_meta.get("scope_target_city") or "").strip(),
                    "location_address": str(location_meta.get("scope_target_address") or "").strip(),
                    "draft_text": str(_row_get(row, "draft_text", 12, "") or "").strip(),
                    "status": str(_row_get(row, "status", 13, "") or "").strip(),
                    "usernews_id": str(_row_get(row, "usernews_id", 14, "") or "").strip(),
                    "created_at": _row_get(row, "created_at", 15),
                    "updated_at": _row_get(row, "updated_at", 16),
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
                   i.source_kind, i.source_ref, i.seo_keyword, i.service_id, i.transaction_id,
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
                source_kind, source_ref, seo_keyword, service_id, transaction_id,
                location_scope, draft_text, status, usernews_id, created_at, updated_at
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
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
                   i.source_kind, i.source_ref, i.seo_keyword, i.service_id, i.transaction_id,
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
                    source_kind, source_ref, seo_keyword, service_id, transaction_id,
                    location_scope, draft_text, status, usernews_id, created_at, updated_at
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
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


def _fallback_draft_text(business_name: str, item: dict[str, Any]) -> str:
    theme = str(item.get("theme") or "Новость компании").strip()
    source_ref = str(item.get("source_ref") or "").strip()
    keyword = str(item.get("seo_keyword") or "").strip()
    goal = str(item.get("goal") or "").strip()
    lines = [f"{business_name}: {theme}."]
    if source_ref:
        lines.append(f"В фокусе сейчас: {source_ref}.")
    if keyword:
        lines.append(f"Это также помогает закрыть спрос по запросу: {keyword}.")
    if goal:
        lines.append(goal)
    lines.append("Подробности, запись или актуальные предложения можно уточнить по контактам в карточке.")
    return " ".join(lines)


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


def generate_draft_for_plan_item(user_id: str, item_id: str) -> dict[str, Any]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_content_plan_tables(cursor)
        cursor.execute(
            """
            SELECT i.id, i.plan_id, i.business_id, i.theme, i.goal, i.content_type, i.source_kind, i.source_ref,
                   i.seo_keyword, i.service_id, i.transaction_id, i.location_scope,
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
        cursor.execute("SELECT name, city, business_type FROM businesses WHERE id = %s", (item.get("business_id"),))
        business_row = cursor.fetchone()
        business_name = str(_row_get(business_row, "name", 0, "Бизнес") or "Бизнес").strip() or "Бизнес"
        business_city = str(_row_get(business_row, "city", 1, "") or "").strip()
        business_type = str(_row_get(business_row, "business_type", 2, "") or "").strip()
        source_kind = str(item.get("source_kind") or "").strip()
        prompt = (
            "Ты — маркетолог локального бизнеса. Напиши короткую новость для публикации на картах. "
            "До 700 символов, обычным русским текстом.\n\n"
            "Жёсткие правила:\n"
            "- не возвращай JSON, markdown, эмодзи, хештеги, фигурные скобки или технические символы;\n"
            "- не выдумывай цены, скидки, акции, режим работы, бесплатные консультации, адрес, район, центр города;\n"
            "- не выдумывай пол, возраст или тип аудитории, если этого нет в фактах;\n"
            "- не используй сезонность, если источник идеи не seasonal;\n"
            "- если данных мало, пиши нейтрально: что можно уточнить в карточке и как связаться.\n\n"
            "Факты:\n"
            f"Бизнес: {business_name}\n"
            f"Город: {business_city}\n"
            f"Тип бизнеса: {business_type}\n"
            f"Тема: {str(item.get('theme') or '').strip()}\n"
            f"Цель: {str(item.get('goal') or '').strip()}\n"
            f"Источник идеи: {source_kind} / {str(item.get('source_ref') or '').strip()}\n"
            f"SEO-запрос: {str(item.get('seo_keyword') or '').strip()}\n"
            f"Дата генерации: {datetime.utcnow().date().isoformat()}\n\n"
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
                generated_text = _fallback_draft_text(business_name, item)
        except Exception:
            generated_text = _fallback_draft_text(business_name, item)
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
            },
        )
        db.conn.commit()
        return get_content_plan(user_id, str(item.get("plan_id") or ""))
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


def create_news_from_plan_item(user_id: str, item_id: str) -> dict[str, Any]:
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
            generated_text = _fallback_draft_text("Бизнес", item)
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
            },
        )
        db.conn.commit()
        return get_content_plan(user_id, str(item.get("plan_id") or ""))
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()
