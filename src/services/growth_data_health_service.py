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


def _coverage_fields(row: Any) -> tuple[set[str], list[str]]:
    datasets = {
        str(item)
        for item in (_row_value(row, "datasets") or [])
        if str(item) in {"sales", "services", "capacity"}
    }
    labels = {
        "sales": "продажи и средний чек",
        "services": "услуги и допродажи",
        "capacity": "загрузка команды и рабочих мест",
    }
    return datasets, [labels[key] for key in ("sales", "services", "capacity") if key not in datasets]


def _location_status_summary(location_health: list[dict[str, Any]]) -> dict[str, int]:
    summary = {"total": len(location_health), "fresh": 0, "due": 0, "stale": 0, "missing": 0}
    for item in location_health:
        status = str(item.get("status") or "missing")
        if status in summary:
            summary[status] += 1
        else:
            summary["missing"] += 1
    return summary


def _network_status(summary: dict[str, int]) -> str:
    """A network is fresh only when every location has fresh confirmed data."""
    if summary["total"] == 0 or summary["missing"]:
        return "missing"
    if summary["stale"]:
        return "stale"
    if summary["due"]:
        return "due"
    return "fresh"


def load_finance_data_health(cursor: Any, business_ids: list[str], now: datetime | None = None) -> dict[str, Any]:
    """Load finance freshness without allowing one location to mask another.

    Finance rows are canonical only after they are stored in their domain table. Rows
    from an import batch are additionally included only after that batch is completed;
    pending previews therefore never make analytics look current.
    """
    observed_at = now or datetime.now(timezone.utc)
    sources: list[tuple[str, str, str, str, bool]] = []
    import_batches_exist = _table_exists(cursor, "finance_import_batches")
    for table, timestamp_column, source_expression, dataset in (
        ("finance_entries", "updated_at", "COALESCE(NULLIF(TRIM(source), ''), 'manual')", "sales"),
        ("finance_service_metrics", "updated_at", "COALESCE(NULLIF(TRIM(source), ''), 'manual')", "services"),
        ("finance_staff_metrics", "updated_at", "COALESCE(NULLIF(TRIM(source), ''), 'manual')", "capacity"),
        ("finance_workplace_metrics", "updated_at", "COALESCE(NULLIF(TRIM(source), ''), 'manual')", "capacity"),
        ("financialtransactions", "created_at", "'manual'", "sales"),
    ):
        if _table_exists(cursor, table):
            sources.append((table, timestamp_column, source_expression, dataset, table != "financialtransactions"))
    if not sources:
        health = build_data_health(None, None)
        health["coverage"] = []
        health["missing"] = ["продажи и средний чек", "услуги и допродажи", "загрузка команды и рабочих мест"]
        return {
            "data_health": health,
            "analytics_level": build_analytics_level(health),
            "rhythm": build_rhythm(health, 0),
            "location_health": [],
            "location_summary": _location_status_summary([]),
        }

    union_queries = []
    for table, timestamp_column, source_value, dataset, supports_batch in sources:
        confirmed_clause = ""
        if supports_batch and import_batches_exist:
            confirmed_clause = f"""
                AND (
                    {table}.import_batch_id IS NULL
                    OR EXISTS (
                        SELECT 1
                        FROM finance_import_batches AS batch
                        WHERE batch.id = {table}.import_batch_id
                          AND batch.business_id = {table}.business_id
                          AND batch.status = 'completed'
                    )
                )
            """
        union_queries.append(
            f"""SELECT business_id::text AS business_id, {timestamp_column} AS occurred_at,
                       {source_value} AS source, '{dataset}' AS dataset
                FROM {table}
                WHERE business_id::text = ANY(%s) {confirmed_clause}"""
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
    health = build_data_health(
        _row_value(row, "latest_at"),
        _row_value(row, "latest_source"),
        int(_row_value(row, "record_count") or 0),
        now=observed_at,
    )
    datasets, missing = _coverage_fields(row)
    health["coverage"] = sorted(datasets)
    health["missing"] = missing

    # The aggregate above preserves the existing business-level contract. For a
    # network we also calculate every location explicitly, including locations
    # with no rows at all. This prevents a recently updated branch from hiding
    # an overdue or missing branch.
    cursor.execute(
        f"""
        WITH finance_events AS ({query})
        SELECT business_id,
               COUNT(*) AS record_count,
               MAX(occurred_at) AS latest_at,
               (ARRAY_AGG(source ORDER BY occurred_at DESC))[1] AS latest_source,
               COUNT(DISTINCT source) AS source_count,
               ARRAY_AGG(DISTINCT dataset) AS datasets,
               COUNT(DISTINCT date_trunc('week', occurred_at)) FILTER (
                   WHERE occurred_at >= NOW() - INTERVAL '56 days'
               ) AS active_weeks
        FROM finance_events
        GROUP BY business_id
        """,
        tuple(params),
    )
    fetchall = getattr(cursor, "fetchall", None)
    location_rows = fetchall() if callable(fetchall) else []
    by_business = {
        str(_row_value(item, "business_id")): item
        for item in (location_rows or [])
        if _row_value(item, "business_id") is not None
    }
    location_health = []
    for business_id in [str(item) for item in business_ids]:
        location_row = by_business.get(business_id)
        location = build_data_health(
            _row_value(location_row, "latest_at"),
            _row_value(location_row, "latest_source"),
            int(_row_value(location_row, "record_count") or 0),
            now=observed_at,
        )
        location_datasets, location_missing = _coverage_fields(location_row)
        location["business_id"] = business_id
        location["coverage"] = sorted(location_datasets)
        location["missing"] = location_missing
        location["analytics_level"] = build_analytics_level(location, len(location_datasets))
        location["rhythm"] = build_rhythm(location, int(_row_value(location_row, "active_weeks") or 0))
        location_health.append(location)
    location_summary = _location_status_summary(location_health)
    health["location_summary"] = location_summary
    if len(location_health) > 1:
        health["status"] = _network_status(location_summary)
        # A network cannot truthfully name one branch's source as the source for
        # every branch; the per-location records retain the exact provenance.
        health["source"] = "multiple" if len({item["source"] for item in location_health if item["source"] != "unknown"}) > 1 else health["source"]
    return {
        "data_health": health,
        "analytics_level": build_analytics_level(health, len(datasets)),
        "rhythm": build_rhythm(health, int(_row_value(row, "active_weeks") or 0)),
        "location_health": location_health,
        "location_summary": location_summary,
    }
