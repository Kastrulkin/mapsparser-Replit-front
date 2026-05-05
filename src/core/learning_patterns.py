from __future__ import annotations

from typing import Any

from core.ai_learning import ensure_ai_learning_events_table


def _row_value(row: Any, key: str, index: int, default: Any = None) -> Any:
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return row[index]
    except Exception:
        return default


def _clean_text(value: Any, limit: int = 260) -> str:
    text = " ".join(str(value or "").strip().split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def get_service_optimization_learning_candidates(conn, *, days: int = 30, limit: int = 8) -> list[dict[str, Any]]:
    """Return human-review candidates for turning individual edits into shared prompt rules."""
    ensure_ai_learning_events_table(conn)
    cur = conn.cursor()
    safe_days = max(1, min(int(days or 30), 180))
    safe_limit = max(1, min(int(limit or 8), 25))
    cur.execute(
        """
        SELECT
            e.id,
            e.user_id,
            e.business_id,
            e.draft_text,
            e.final_text,
            e.metadata_json,
            e.created_at,
            b.name AS business_name,
            u.email AS user_email
        FROM ailearningevents e
        LEFT JOIN businesses b ON b.id = e.business_id
        LEFT JOIN users u ON u.id = e.user_id
        WHERE e.capability = 'services.optimize'
          AND e.event_type = 'accepted'
          AND COALESCE(e.accepted, FALSE) = TRUE
          AND COALESCE(e.edited_before_accept, FALSE) = TRUE
          AND e.created_at >= NOW() - (%s::text || ' days')::interval
          AND NULLIF(BTRIM(COALESCE(e.draft_text, '')), '') IS NOT NULL
          AND NULLIF(BTRIM(COALESCE(e.final_text, '')), '') IS NOT NULL
        ORDER BY e.created_at DESC
        LIMIT %s
        """,
        (str(safe_days), safe_limit),
    )
    items: list[dict[str, Any]] = []
    for row in cur.fetchall() or []:
        metadata = _row_value(row, "metadata_json", 5, {}) or {}
        if not isinstance(metadata, dict):
            metadata = {}
        field = str(metadata.get("field") or "text").strip() or "text"
        draft_text = _clean_text(_row_value(row, "draft_text", 3, ""))
        final_text = _clean_text(_row_value(row, "final_text", 4, ""))
        if not draft_text or not final_text or draft_text == final_text:
            continue
        created_at = _row_value(row, "created_at", 6)
        if hasattr(created_at, "isoformat"):
            created_at = created_at.isoformat()
        items.append(
            {
                "id": str(_row_value(row, "id", 0, "") or ""),
                "field": field,
                "business_id": str(_row_value(row, "business_id", 2, "") or ""),
                "business_name": str(_row_value(row, "business_name", 7, "") or ""),
                "user_id": str(_row_value(row, "user_id", 1, "") or ""),
                "user_email": str(_row_value(row, "user_email", 8, "") or ""),
                "service_id": str(metadata.get("service_id") or ""),
                "source": str(metadata.get("source") or ""),
                "draft_text": draft_text,
                "final_text": final_text,
                "created_at": str(created_at or ""),
                "candidate_rule": _candidate_rule(field, draft_text, final_text),
            }
        )
    return items


def _candidate_rule(field: str, draft_text: str, final_text: str) -> str:
    field_label = "названия" if field == "name" else "описания"
    return (
        f"Для {field_label} услуг избегать общих формулировок вроде «{draft_text}». "
        f"Писать конкретнее по реальному сценарию услуги: «{final_text}»."
    )


def format_learning_candidates_for_digest(items: list[dict[str, Any]], *, max_items: int = 3) -> str:
    if not items:
        return ""
    lines = [
        "🧠 Кандидаты Ralph-loop для общих промптов",
        "Нужна ручная проверка суперадмина: ничего не применяется автоматически.",
    ]
    for index, item in enumerate(items[:max(1, max_items)], start=1):
        field = "название" if item.get("field") == "name" else "описание"
        final_text = _clean_text(item.get("final_text"), 120)
        business_name = _clean_text(item.get("business_name"), 80) or "бизнес"
        lines.append(f"{index}. {field}: {final_text}")
        lines.append(f"   Источник: {business_name}")
    lines.append("Откройте админку → Промпты анализа → Кандидаты Ralph-loop.")
    return "\n".join(lines)
