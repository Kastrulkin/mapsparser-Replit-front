"""Deterministic finance-data health used by the shared growth surfaces."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any


FRESH_DAYS = 7
DUE_DAYS = 14


def _row_value(row: Any, key: str, default: Any = None) -> Any:
    return row.get(key, default) if hasattr(row, "get") else default


def _table_exists(cursor: Any, table_name: str) -> bool:
    cursor.execute("SELECT to_regclass(%s) AS relation", (f"public.{table_name}",))
    return bool(_row_value(cursor.fetchone(), "relation"))


def _as_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc)
    if value:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def build_data_health(latest_at: Any, source: str | None, record_count: int = 0, now: datetime | None = None) -> dict[str, Any]:
    """Return a stable, UI-safe quality contract without claiming unavailable data."""
    observed_at = now or datetime.now(timezone.utc)
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=timezone.utc)
    updated_at = _as_datetime(latest_at)
    if not updated_at or record_count <= 0:
        status, age_days = "missing", None
    else:
        age_days = max(0, (observed_at.astimezone(timezone.utc).date() - updated_at.astimezone(timezone.utc).date()).days)
        if age_days <= FRESH_DAYS:
            status = "fresh"
        elif age_days <= DUE_DAYS:
            status = "due"
        else:
            status = "stale"
    next_due_at = None
    if updated_at:
        next_due_at = (updated_at.astimezone(timezone.utc) + timedelta(days=FRESH_DAYS)).isoformat()
    return {
        "status": status,
        "source": str(source or "unknown"),
        "source_updated_at": updated_at.isoformat() if updated_at else None,
        "age_days": age_days,
        "next_due_at": next_due_at,
        "record_count": max(0, int(record_count or 0)),
    }


def build_analytics_level(data_health: dict[str, Any], source_count: int = 0) -> dict[str, Any]:
    status = str(data_health.get("status") or "missing")
    if status == "fresh" and source_count >= 2:
        return {"level": "actionable", "label": "Готово к решениям", "next_unlock": None}
    if status in {"fresh", "due"}:
        return {
            "level": "baseline",
            "label": "Базовая аналитика",
            "next_unlock": "Добавьте регулярные продажи и расходы, чтобы видеть точки роста.",
        }
    return {
        "level": "setup",
        "label": "Нужны данные",
        "next_unlock": "Загрузите первую финансовую сводку, чтобы открыть аналитику.",
    }


def build_rhythm(data_health: dict[str, Any], active_weeks: int) -> dict[str, Any]:
    status = str(data_health.get("status") or "missing")
    if status == "fresh" and active_weeks >= 3:
        rhythm_status, label = "active", "Регулярный ритм"
    elif active_weeks > 0:
        rhythm_status, label = "forming", "Ритм формируется"
    else:
        rhythm_status, label = "not_started", "Ритм ещё не начат"
    return {"active_weeks": max(0, int(active_weeks or 0)), "status": rhythm_status, "label": label}


def load_finance_data_health(cursor: Any, business_ids: list[str]) -> dict[str, Any]:
    sources: list[tuple[str, str, str, str]] = []
    for table, timestamp_column, source_expression, dataset in (
        ("finance_entries", "updated_at", "COALESCE(NULLIF(TRIM(source), ''), 'manual')", "sales"),
        ("finance_service_metrics", "updated_at", "COALESCE(NULLIF(TRIM(source), ''), 'manual')", "services"),
        ("finance_staff_metrics", "updated_at", "COALESCE(NULLIF(TRIM(source), ''), 'manual')", "capacity"),
        ("finance_workplace_metrics", "updated_at", "COALESCE(NULLIF(TRIM(source), ''), 'manual')", "capacity"),
        ("financialtransactions", "created_at", "'manual'", "sales"),
    ):
        if _table_exists(cursor, table):
            sources.append((table, timestamp_column, source_expression, dataset))
    if not sources:
        health = build_data_health(None, None)
        health["coverage"] = []
        health["missing"] = ["продажи и средний чек", "услуги и допродажи", "загрузка команды и рабочих мест"]
        return {"data_health": health, "analytics_level": build_analytics_level(health), "rhythm": build_rhythm(health, 0)}

    union_queries = []
    for table, timestamp_column, source_value, dataset in sources:
        union_queries.append(
            f"SELECT {timestamp_column} AS occurred_at, {source_value} AS source, '{dataset}' AS dataset FROM {table} WHERE business_id::text = ANY(%s)"
        )
    query = " UNION ALL ".join(union_queries)
    params: list[list[str]] = [business_ids for _ in sources]
    cursor.execute(
        f"""
        WITH finance_events AS ({query})
        SELECT COUNT(*) AS record_count,
               MAX(occurred_at) AS latest_at,
               (ARRAY_AGG(source ORDER BY occurred_at DESC))[1] AS latest_source,
               COUNT(DISTINCT source) AS source_count,
               ARRAY_AGG(DISTINCT dataset) AS datasets,
               COUNT(DISTINCT date_trunc('week', occurred_at)) FILTER (
                   WHERE occurred_at >= NOW() - INTERVAL '56 days'
               ) AS active_weeks
        FROM finance_events
        """,
        tuple(params),
    )
    row = cursor.fetchone()
    health = build_data_health(_row_value(row, "latest_at"), _row_value(row, "latest_source"), int(_row_value(row, "record_count") or 0))
    datasets = {str(item) for item in (_row_value(row, "datasets") or []) if str(item) in {"sales", "services", "capacity"}}
    labels = {"sales": "продажи и средний чек", "services": "услуги и допродажи", "capacity": "загрузка команды и рабочих мест"}
    health["coverage"] = sorted(datasets)
    health["missing"] = [labels[key] for key in ("sales", "services", "capacity") if key not in datasets]
    return {
        "data_health": health,
        "analytics_level": build_analytics_level(health, len(datasets)),
        "rhythm": build_rhythm(health, int(_row_value(row, "active_weeks") or 0)),
    }
