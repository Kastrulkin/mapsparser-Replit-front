"""Finance API routes for LocalOS.

Routes are intentionally kept on their historical /api/finance/* paths while
main.py is split into domain blueprints.
"""
from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timedelta

from flask import Blueprint, Response, jsonify, request

from auth_encryption import encrypt_auth_data, decrypt_auth_data
from auth_system import verify_session
from core import finance_crm, finance_imports
from core.finance_kpis import calculate_finance_snapshot, default_period_range, get_default_finance_thresholds
from core.helpers import get_business_id_from_user, get_business_owner_id
from database_manager import DatabaseManager


finance_bp = Blueprint("finance_api", __name__)


def _row_to_dict(cursor, row):
    """Map dict-like or tuple DB rows to dicts."""
    if row is None:
        return None
    if hasattr(row, "keys"):
        return {k: row[k] for k in row.keys()}
    cols = [d[0] for d in cursor.description]
    return dict(zip(cols, row))


def _table_columns(cursor, table_name: str) -> set:
    """Return lowercase Postgres column names for a table."""
    cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        """,
        (table_name.lower(),),
    )
    cols = set()
    for row in cursor.fetchall() or []:
        if hasattr(row, "get"):
            name = row.get("column_name")
        else:
            name = row[0] if row else None
        if name:
            cols.add(str(name).lower())
    return cols


# ==================== ФИНАНСОВЫЕ ЭНДПОИНТЫ ====================

def _require_finance_user_and_business():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None, None, (jsonify({"error": "Требуется авторизация"}), 401)

    token = auth_header.split(' ')[1]
    user_data = verify_session(token)
    if not user_data:
        return None, None, (jsonify({"error": "Недействительный токен"}), 401)

    requested_business_id = request.args.get('business_id')
    if request.method in {'POST', 'PUT', 'PATCH'}:
        request_json = request.get_json(silent=True) or {}
        requested_business_id = requested_business_id or request_json.get('business_id')

    business_id = get_business_id_from_user(user_data['user_id'], requested_business_id)
    if not business_id:
        return user_data, None, (jsonify({"error": "Сначала выберите бизнес"}), 400)

    db = DatabaseManager()
    cursor = db.conn.cursor()
    owner_id = get_business_owner_id(cursor, business_id, include_active_check=True)
    db.close()

    if not owner_id:
        return user_data, business_id, (jsonify({"error": "Бизнес не найден"}), 404)
    if owner_id != user_data['user_id'] and not user_data.get('is_superadmin'):
        return user_data, business_id, (jsonify({"error": "Нет доступа к этому бизнесу"}), 403)

    return user_data, business_id, None


def _finance_period_from_request():
    start_date = request.args.get('from') or request.args.get('start_date')
    end_date = request.args.get('to') or request.args.get('end_date')
    if start_date and end_date:
        return start_date, end_date
    return default_period_range()


def _finance_all_time_period(cursor, business_id):
    cursor.execute(
        """
        SELECT MIN(period_start), MAX(period_end)
        FROM (
            SELECT date AS period_start, date AS period_end
            FROM finance_entries
            WHERE business_id = %s
            UNION ALL
            SELECT period_start, period_end
            FROM finance_service_metrics
            WHERE business_id = %s
            UNION ALL
            SELECT period_start, period_end
            FROM finance_staff_metrics
            WHERE business_id = %s
            UNION ALL
            SELECT period_start, period_end
            FROM finance_workplace_metrics
            WHERE business_id = %s
        ) finance_dates
        """,
        (business_id, business_id, business_id, business_id),
    )
    row = cursor.fetchone()
    start_date = _finance_row_value(row, "min", 0)
    end_date = _finance_row_value(row, "max", 1)
    if start_date and end_date:
        return str(start_date), str(end_date)
    return default_period_range()


def _parse_finance_date(value):
    return datetime.strptime(str(value), "%Y-%m-%d").date()


def _add_months(value, months):
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, 28)
    return value.replace(year=year, month=month, day=day)


def _month_range(value):
    start = value.replace(day=1)
    next_month = _add_months(start, 1)
    end = next_month - timedelta(days=1)
    return start.isoformat(), end.isoformat()


def _finance_row_value(row, key, index):
    if row is None:
        return None
    if hasattr(row, "get"):
        return row.get(key)
    return row[index]


def _finance_period_overlap_ratio(row_start, row_end, request_start, request_end):
    row_start_date = _parse_finance_date(row_start)
    row_end_date = _parse_finance_date(row_end)
    request_start_date = _parse_finance_date(request_start)
    request_end_date = _parse_finance_date(request_end)
    if not row_start_date or not row_end_date or not request_start_date or not request_end_date:
        return 1.0

    total_days = max((row_end_date - row_start_date).days + 1, 1)
    overlap_start = max(row_start_date, request_start_date)
    overlap_end = min(row_end_date, request_end_date)
    if overlap_end < overlap_start:
        return 0.0

    overlap_days = (overlap_end - overlap_start).days + 1
    return max(0.0, min(1.0, overlap_days / total_days))


def _finance_prorate_value(value, ratio):
    return float(value or 0) * ratio


def _finance_prorate_count(value, ratio):
    raw_value = float(value or 0)
    if ratio >= 0.999:
        return int(raw_value)
    return raw_value * ratio


def _normalize_finance_service_name(value):
    return " ".join(str(value or "").strip().casefold().split())


def _load_finance_service_catalog(cursor, business_id):
    """Load the same active service catalog used by the map-card workspace."""
    user_columns = _table_columns(cursor, "userservices")
    user_fields = ["id", "name", "category", "price", "updated_at"]
    if "source" in user_columns:
        user_fields.append("source")
    cursor.execute(
        f"""
        SELECT {', '.join(user_fields)}
        FROM userservices
        WHERE business_id = %s AND (is_active IS TRUE OR is_active IS NULL)
        ORDER BY category NULLS LAST, name NULLS LAST, updated_at DESC NULLS LAST
        """,
        (business_id,),
    )
    catalog = [_row_to_dict(cursor, row) for row in cursor.fetchall() or []]

    cursor.execute("SELECT to_regclass('public.externalbusinessservices')")
    table_row = cursor.fetchone()
    if not _finance_row_value(table_row, "to_regclass", 0):
        return catalog

    external_columns = _table_columns(cursor, "externalbusinessservices")
    external_fields = ["id", "name", "category", "price"]
    if "updated_at" in external_columns:
        external_fields.append("updated_at")
    elif "created_at" in external_columns:
        external_fields.append("created_at")
    if "source" in external_columns:
        external_fields.append("source")
    cursor.execute(
        f"""
        SELECT {', '.join(external_fields)}
        FROM externalbusinessservices
        WHERE business_id = %s
        ORDER BY category NULLS LAST, name NULLS LAST
        """,
        (business_id,),
    )
    for row in cursor.fetchall() or []:
        item = _row_to_dict(cursor, row)
        item["is_external"] = True
        item["source"] = item.get("source") or "external"
        if "created_at" in item and "updated_at" not in item:
            item["updated_at"] = item.get("created_at")
        catalog.append(item)
    return catalog


def _finance_catalog_rows(catalog, finance_metrics):
    """Overlay period metrics on the canonical card-service list without creating a second catalog."""
    grouped = {}
    for item in finance_metrics or []:
        key = _normalize_finance_service_name(item.get("service_name"))
        if not key:
            continue
        group = grouped.setdefault(key, [])
        group.append(item)

    merged = []
    metadata = []
    for service in catalog or []:
        service_name = service.get("name") or "Услуга"
        matched = grouped.get(_normalize_finance_service_name(service_name), [])
        visits = sum(float(item.get("visits_count") or 0) for item in matched)
        weighted_price = sum(
            float(item.get("avg_price") or 0) * float(item.get("visits_count") or 0)
            for item in matched
        )
        catalog_price = service.get("price")
        try:
            fallback_price = float(catalog_price or 0)
        except (TypeError, ValueError):
            fallback_price = 0
        merged.append({
            "service_name": service_name,
            "category": service.get("category") or "",
            "revenue": sum(float(item.get("revenue") or 0) for item in matched),
            "visits_count": visits,
            "avg_price": weighted_price / visits if visits > 0 else fallback_price,
            "duration_minutes": max([int(item.get("duration_minutes") or 0) for item in matched] or [0]),
            "material_cost": sum(float(item.get("material_cost") or 0) for item in matched),
            "staff_payout": sum(float(item.get("staff_payout") or 0) for item in matched),
        })
        metadata.append({
            "service_id": service.get("id"),
            "catalog_price": catalog_price,
            "source": service.get("source") or "localos",
            "updated_at": service.get("updated_at"),
            "is_external": bool(service.get("is_external")),
            "has_finance_data": bool(matched),
        })

    if not merged:
        return []
    calculated = calculate_finance_snapshot({"services": merged}).get("services") or []
    for index, row in enumerate(calculated):
        row.update(metadata[index])
        if not metadata[index]["has_finance_data"]:
            row["status"] = "no_finance_data"
    return calculated


def _load_finance_payload(cursor, business_id, start_date, end_date):
    cursor.execute(
        """
        SELECT id, date, type, category, amount, source, comment
        FROM finance_entries
        WHERE business_id = %s AND date BETWEEN %s AND %s
        ORDER BY date DESC, created_at DESC
        """,
        (business_id, start_date, end_date),
    )
    entries = [
        {
            "id": _finance_row_value(row, "id", 0),
            "date": str(_finance_row_value(row, "date", 1)),
            "type": _finance_row_value(row, "type", 2),
            "category": _finance_row_value(row, "category", 3),
            "amount": float(_finance_row_value(row, "amount", 4) or 0),
            "source": _finance_row_value(row, "source", 5),
            "comment": _finance_row_value(row, "comment", 6),
        }
        for row in cursor.fetchall() or []
    ]

    cursor.execute(
        """
        SELECT id, period_start, period_end, service_name, category, revenue, visits_count,
               avg_price, duration_minutes, material_cost, staff_payout, source
        FROM finance_service_metrics
        WHERE business_id = %s AND period_start <= %s AND period_end >= %s
        ORDER BY revenue DESC
        """,
        (business_id, end_date, start_date),
    )
    services = []
    for row in cursor.fetchall() or []:
        period_start = str(_finance_row_value(row, "period_start", 1))
        period_end = str(_finance_row_value(row, "period_end", 2))
        ratio = _finance_period_overlap_ratio(period_start, period_end, start_date, end_date)
        services.append({
            "id": _finance_row_value(row, "id", 0),
            "period_start": period_start,
            "period_end": period_end,
            "service_name": _finance_row_value(row, "service_name", 3),
            "category": _finance_row_value(row, "category", 4),
            "revenue": _finance_prorate_value(_finance_row_value(row, "revenue", 5), ratio),
            "visits_count": _finance_prorate_count(_finance_row_value(row, "visits_count", 6), ratio),
            "avg_price": float(_finance_row_value(row, "avg_price", 7) or 0),
            "duration_minutes": int(_finance_row_value(row, "duration_minutes", 8) or 0),
            "material_cost": _finance_prorate_value(_finance_row_value(row, "material_cost", 9), ratio),
            "staff_payout": _finance_prorate_value(_finance_row_value(row, "staff_payout", 10), ratio),
            "source": _finance_row_value(row, "source", 11),
        })

    cursor.execute(
        """
        SELECT id, period_start, period_end, staff_name, role, revenue, visits_count,
               booked_minutes, available_minutes, no_show_count, rebooking_count, source
        FROM finance_staff_metrics
        WHERE business_id = %s AND period_start <= %s AND period_end >= %s
        ORDER BY revenue DESC
        """,
        (business_id, end_date, start_date),
    )
    staff = []
    for row in cursor.fetchall() or []:
        period_start = str(_finance_row_value(row, "period_start", 1))
        period_end = str(_finance_row_value(row, "period_end", 2))
        ratio = _finance_period_overlap_ratio(period_start, period_end, start_date, end_date)
        staff.append({
            "id": _finance_row_value(row, "id", 0),
            "period_start": period_start,
            "period_end": period_end,
            "staff_name": _finance_row_value(row, "staff_name", 3),
            "role": _finance_row_value(row, "role", 4),
            "revenue": _finance_prorate_value(_finance_row_value(row, "revenue", 5), ratio),
            "visits_count": _finance_prorate_count(_finance_row_value(row, "visits_count", 6), ratio),
            "booked_minutes": _finance_prorate_count(_finance_row_value(row, "booked_minutes", 7), ratio),
            "available_minutes": _finance_prorate_count(_finance_row_value(row, "available_minutes", 8), ratio),
            "no_show_count": _finance_prorate_count(_finance_row_value(row, "no_show_count", 9), ratio),
            "rebooking_count": _finance_prorate_count(_finance_row_value(row, "rebooking_count", 10), ratio),
            "source": _finance_row_value(row, "source", 11),
        })

    cursor.execute(
        """
        SELECT id, name, type, is_active
        FROM finance_workplaces
        WHERE business_id = %s
        ORDER BY created_at ASC
        """,
        (business_id,),
    )
    workplaces = [
        {
            "id": _finance_row_value(row, "id", 0),
            "name": _finance_row_value(row, "name", 1),
            "type": _finance_row_value(row, "type", 2),
            "is_active": bool(_finance_row_value(row, "is_active", 3)),
        }
        for row in cursor.fetchall() or []
    ]

    cursor.execute(
        """
        SELECT id, workplace_id, period_start, period_end, available_minutes, booked_minutes,
               revenue, gross_profit, source
        FROM finance_workplace_metrics
        WHERE business_id = %s AND period_start <= %s AND period_end >= %s
        ORDER BY revenue DESC
        """,
        (business_id, end_date, start_date),
    )
    workplace_metrics = []
    for row in cursor.fetchall() or []:
        period_start = str(_finance_row_value(row, "period_start", 2))
        period_end = str(_finance_row_value(row, "period_end", 3))
        ratio = _finance_period_overlap_ratio(period_start, period_end, start_date, end_date)
        workplace_metrics.append({
            "id": _finance_row_value(row, "id", 0),
            "workplace_id": _finance_row_value(row, "workplace_id", 1),
            "period_start": period_start,
            "period_end": period_end,
            "available_minutes": _finance_prorate_count(_finance_row_value(row, "available_minutes", 4), ratio),
            "booked_minutes": _finance_prorate_count(_finance_row_value(row, "booked_minutes", 5), ratio),
            "revenue": _finance_prorate_value(_finance_row_value(row, "revenue", 6), ratio),
            "gross_profit": _finance_prorate_value(_finance_row_value(row, "gross_profit", 7), ratio),
            "source": _finance_row_value(row, "source", 8),
        })

    return {
        "entries": entries,
        "services": services,
        "staff": staff,
        "workplaces": workplaces,
        "workplace_metrics": workplace_metrics,
    }


def _load_finance_thresholds(cursor, business_id):
    defaults = get_default_finance_thresholds()
    cursor.execute(
        """
        SELECT metric_key, green_min, green_max, yellow_min, yellow_max,
               red_rule, label, unit, profile
        FROM finance_kpi_thresholds
        WHERE business_id = %s AND is_active = TRUE
        """,
        (business_id,),
    )
    rows = cursor.fetchall() or []
    custom = {}
    for row in rows:
        item = _row_to_dict(cursor, row)
        metric_key = item.get("metric_key")
        if not metric_key or metric_key not in defaults:
            continue
        custom[metric_key] = {
            "green_min": float(item["green_min"]) if item.get("green_min") is not None else None,
            "green_max": float(item["green_max"]) if item.get("green_max") is not None else None,
            "yellow_min": float(item["yellow_min"]) if item.get("yellow_min") is not None else None,
            "yellow_max": float(item["yellow_max"]) if item.get("yellow_max") is not None else None,
            "red_rule": item.get("red_rule"),
            "label": item.get("label"),
            "unit": item.get("unit"),
            "profile": item.get("profile") or "service_business",
            "source": "custom",
        }
    thresholds = {}
    for key, value in defaults.items():
        merged = dict(value)
        merged["profile"] = "service_business"
        merged["source"] = "default"
        if key in custom:
            for field, field_value in custom[key].items():
                if field_value is not None or field in {"green_min", "green_max", "yellow_min", "yellow_max"}:
                    merged[field] = field_value
        thresholds[key] = merged
    return thresholds


def _save_finance_thresholds(cursor, business_id, thresholds):
    defaults = get_default_finance_thresholds()
    saved = 0
    for item in thresholds or []:
        metric_key = str(item.get("metric_key") or "").strip()
        if metric_key not in defaults:
            continue
        current = dict(defaults[metric_key])
        for field in ("green_min", "green_max", "yellow_min", "yellow_max", "red_rule", "label", "unit"):
            if field in item:
                current[field] = item.get(field)
        cursor.execute(
            """
            INSERT INTO finance_kpi_thresholds
            (id, business_id, profile, metric_key, green_min, green_max, yellow_min,
             yellow_max, red_rule, label, unit, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
            ON CONFLICT (business_id, metric_key) WHERE is_active = TRUE
            DO UPDATE SET
                profile = EXCLUDED.profile,
                green_min = EXCLUDED.green_min,
                green_max = EXCLUDED.green_max,
                yellow_min = EXCLUDED.yellow_min,
                yellow_max = EXCLUDED.yellow_max,
                red_rule = EXCLUDED.red_rule,
                label = EXCLUDED.label,
                unit = EXCLUDED.unit,
                updated_at = NOW()
            """,
            (
                str(uuid.uuid4()),
                business_id,
                item.get("profile") or "service_business",
                metric_key,
                current.get("green_min"),
                current.get("green_max"),
                current.get("yellow_min"),
                current.get("yellow_max"),
                current.get("red_rule"),
                current.get("label"),
                current.get("unit"),
            ),
        )
        saved += 1
    return saved


def _load_finance_action_logs(cursor, business_id, start_date=None, end_date=None):
    params = [business_id]
    period_filter = ""
    if start_date and end_date:
        period_filter = "AND (period_start IS NULL OR period_end IS NULL OR (period_start <= %s AND period_end >= %s))"
        params.extend([end_date, start_date])
    cursor.execute(
        f"""
        SELECT id, recommendation_code, action_key, action_bucket, action_text,
               status, period_start, period_end, completed_at, created_by,
               created_at, updated_at
        FROM finance_action_logs
        WHERE business_id = %s {period_filter}
        ORDER BY updated_at DESC
        """,
        tuple(params),
    )
    actions = []
    for row in cursor.fetchall() or []:
        item = _row_to_dict(cursor, row)
        for date_key in ("period_start", "period_end", "completed_at", "created_at", "updated_at"):
            if item.get(date_key):
                item[date_key] = str(item[date_key])
        actions.append(item)
    return actions


def _finance_snapshot_for_period(cursor, business_id, start_date, end_date):
    payload = _load_finance_payload(cursor, business_id, start_date, end_date)
    thresholds = _load_finance_thresholds(cursor, business_id)
    snapshot = calculate_finance_snapshot(payload, thresholds)
    return payload, thresholds, snapshot


def _finance_metric_delta(current_kpis, previous_kpis, metric_key):
    current = current_kpis.get(metric_key)
    previous = previous_kpis.get(metric_key)
    if current is None or previous is None:
        return {
            "metric": metric_key,
            "current": current,
            "previous": previous,
            "delta": None,
            "direction": "unknown",
        }
    delta = current - previous
    direction = "up" if delta > 0 else "down" if delta < 0 else "flat"
    return {
        "metric": metric_key,
        "current": current,
        "previous": previous,
        "delta": delta,
        "direction": direction,
    }


def _build_finance_impact(cursor, business_id, start_date, end_date):
    current_start = _parse_finance_date(start_date)
    current_end = _parse_finance_date(end_date)
    period_days = max((current_end - current_start).days, 0)
    previous_end = current_start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=period_days)

    payload, thresholds, current_snapshot = _finance_snapshot_for_period(cursor, business_id, start_date, end_date)
    previous_payload, previous_thresholds, previous_snapshot = _finance_snapshot_for_period(
        cursor,
        business_id,
        previous_start.isoformat(),
        previous_end.isoformat(),
    )
    actions = _load_finance_action_logs(cursor, business_id, start_date, end_date)
    completed_actions = [item for item in actions if item.get("status") == "completed"]
    metrics = [
        "operating_margin",
        "revenue",
        "no_show_rate",
        "rebooking_rate",
        "workplace_occupancy",
        "revenue_per_workplace_hour",
        "gross_profit_per_workplace_hour",
    ]
    deltas = [
        _finance_metric_delta(current_snapshot.get("kpis") or {}, previous_snapshot.get("kpis") or {}, metric)
        for metric in metrics
    ]
    return {
        "period": {"start_date": start_date, "end_date": end_date},
        "previous_period": {"start_date": previous_start.isoformat(), "end_date": previous_end.isoformat()},
        "completed_actions_count": len(completed_actions),
        "completed_actions": completed_actions[:20],
        "deltas": deltas,
        "data_quality": current_snapshot.get("data_quality"),
        "previous_data_quality": previous_snapshot.get("data_quality"),
    }


def _build_finance_history(cursor, business_id, months):
    months = min(max(int(months or 6), 1), 12)
    today = datetime.utcnow().date()
    thresholds = _load_finance_thresholds(cursor, business_id)
    points = []
    for offset in range(months - 1, -1, -1):
        month_date = _add_months(today.replace(day=1), -offset)
        start_date, end_date = _month_range(month_date)
        payload = _load_finance_payload(cursor, business_id, start_date, end_date)
        snapshot = calculate_finance_snapshot(payload, thresholds)
        kpis = snapshot.get("kpis") or {}
        points.append({
            "period_start": start_date,
            "period_end": end_date,
            "label": month_date.strftime("%Y-%m"),
            "revenue": kpis.get("revenue"),
            "operating_profit": kpis.get("operating_profit"),
            "operating_margin": kpis.get("operating_margin"),
            "no_show_rate": kpis.get("no_show_rate"),
            "rebooking_rate": kpis.get("rebooking_rate"),
            "workplace_occupancy": kpis.get("workplace_occupancy"),
            "revenue_per_workplace_hour": kpis.get("revenue_per_workplace_hour"),
            "data_quality_score": (snapshot.get("data_quality") or {}).get("score"),
        })
    return points


def _insert_finance_manual_payload(cursor, business_id, data):
    period_start = data.get('period_start') or data.get('from') or default_period_range()[0]
    period_end = data.get('period_end') or data.get('to') or default_period_range()[1]
    inserted = {"entries": 0, "services": 0, "staff": 0, "workplaces": 0, "workplace_metrics": 0}

    for item in data.get('entries') or []:
        cursor.execute(
            """
            INSERT INTO finance_entries (id, business_id, date, type, category, amount, source, comment)
            VALUES (%s, %s, %s, %s, %s, %s, 'manual', %s)
            """,
            (
                str(uuid.uuid4()),
                business_id,
                item.get('date') or period_end,
                item.get('type') or 'revenue',
                item.get('category') or 'other',
                float(item.get('amount') or 0),
                item.get('comment') or '',
            ),
        )
        inserted["entries"] += 1

    for item in data.get('services') or []:
        cursor.execute(
            """
            INSERT INTO finance_service_metrics
            (id, business_id, period_start, period_end, service_name, category, revenue,
             visits_count, avg_price, duration_minutes, material_cost, staff_payout, source)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'manual')
            """,
            (
                str(uuid.uuid4()),
                business_id,
                item.get('period_start') or period_start,
                item.get('period_end') or period_end,
                item.get('service_name') or item.get('name') or 'Услуга',
                item.get('category') or '',
                float(item.get('revenue') or 0),
                int(item.get('visits_count') or 0),
                float(item.get('avg_price') or 0),
                int(item.get('duration_minutes') or 0),
                float(item.get('material_cost') or 0),
                float(item.get('staff_payout') or 0),
            ),
        )
        inserted["services"] += 1

    for item in data.get('staff') or []:
        cursor.execute(
            """
            INSERT INTO finance_staff_metrics
            (id, business_id, period_start, period_end, staff_name, role, revenue, visits_count,
             booked_minutes, available_minutes, no_show_count, rebooking_count, source)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'manual')
            """,
            (
                str(uuid.uuid4()),
                business_id,
                item.get('period_start') or period_start,
                item.get('period_end') or period_end,
                item.get('staff_name') or item.get('name') or 'Мастер',
                item.get('role') or '',
                float(item.get('revenue') or 0),
                int(item.get('visits_count') or 0),
                int(item.get('booked_minutes') or 0),
                int(item.get('available_minutes') or 0),
                int(item.get('no_show_count') or 0),
                int(item.get('rebooking_count') or 0),
            ),
        )
        inserted["staff"] += 1

    workplace_ids_by_client_key = {}
    for item in data.get('workplaces') or []:
        workplace_id = item.get('id') or str(uuid.uuid4())
        workplace_ids_by_client_key[item.get('client_key') or item.get('name') or workplace_id] = workplace_id
        cursor.execute(
            """
            INSERT INTO finance_workplaces (id, business_id, name, type, is_active)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                type = EXCLUDED.type,
                is_active = EXCLUDED.is_active,
                updated_at = NOW()
            """,
            (
                workplace_id,
                business_id,
                item.get('name') or 'Рабочее место',
                item.get('type') or 'other',
                bool(item.get('is_active', True)),
            ),
        )
        inserted["workplaces"] += 1

    for item in data.get('workplace_metrics') or []:
        client_key = item.get('workplace_client_key') or item.get('workplace_name') or item.get('workplace_id')
        workplace_id = item.get('workplace_id') or workplace_ids_by_client_key.get(client_key)
        cursor.execute(
            """
            INSERT INTO finance_workplace_metrics
            (id, business_id, workplace_id, period_start, period_end, available_minutes,
             booked_minutes, revenue, gross_profit, source)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'manual')
            """,
            (
                str(uuid.uuid4()),
                business_id,
                workplace_id,
                item.get('period_start') or period_start,
                item.get('period_end') or period_end,
                int(item.get('available_minutes') or 0),
                int(item.get('booked_minutes') or 0),
                float(item.get('revenue') or 0),
                float(item.get('gross_profit') or 0),
            ),
        )
        inserted["workplace_metrics"] += 1

    return inserted


def _finance_import_duplicate_exists(cursor, business_id, record_type, duplicate_key):
    table_by_type = {
        "entry": "finance_entries",
        "service": "finance_service_metrics",
        "staff": "finance_staff_metrics",
        "workplace": "finance_workplace_metrics",
    }
    table_name = table_by_type.get(record_type)
    if not table_name or not duplicate_key:
        return False
    cursor.execute(
        f"SELECT 1 FROM {table_name} WHERE business_id = %s AND duplicate_key = %s LIMIT 1",
        (business_id, duplicate_key),
    )
    return cursor.fetchone() is not None


def _insert_finance_import_item(cursor, business_id, batch_id, item):
    record_type = item.get("record_type")
    duplicate_key = item.get("duplicate_key")
    external_id = item.get("external_id") or None
    if record_type == "entry":
        cursor.execute(
            """
            INSERT INTO finance_entries
            (id, business_id, date, type, category, amount, source, comment,
             import_batch_id, external_id, duplicate_key)
            VALUES (%s, %s, %s, %s, %s, %s, 'file', %s, %s, %s, %s)
            """,
            (
                str(uuid.uuid4()),
                business_id,
                item.get("date"),
                item.get("type"),
                item.get("category"),
                item.get("amount"),
                item.get("comment") or "",
                batch_id,
                external_id,
                duplicate_key,
            ),
        )
        return
    if record_type == "service":
        cursor.execute(
            """
            INSERT INTO finance_service_metrics
            (id, business_id, period_start, period_end, service_name, category, revenue,
             visits_count, avg_price, duration_minutes, material_cost, staff_payout,
             source, import_batch_id, external_id, duplicate_key)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    'file', %s, %s, %s)
            """,
            (
                str(uuid.uuid4()),
                business_id,
                item.get("period_start"),
                item.get("period_end"),
                item.get("service_name"),
                item.get("category") or "",
                item.get("revenue") or 0,
                item.get("visits_count") or 0,
                item.get("avg_price") or 0,
                item.get("duration_minutes") or 0,
                item.get("material_cost") or 0,
                item.get("staff_payout") or 0,
                batch_id,
                external_id,
                duplicate_key,
            ),
        )
        return
    if record_type == "staff":
        cursor.execute(
            """
            INSERT INTO finance_staff_metrics
            (id, business_id, period_start, period_end, staff_name, role, revenue,
             visits_count, booked_minutes, available_minutes, no_show_count,
             rebooking_count, source, import_batch_id, external_id, duplicate_key)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    'file', %s, %s, %s)
            """,
            (
                str(uuid.uuid4()),
                business_id,
                item.get("period_start"),
                item.get("period_end"),
                item.get("staff_name"),
                item.get("role") or "",
                item.get("revenue") or 0,
                item.get("visits_count") or 0,
                item.get("booked_minutes") or 0,
                item.get("available_minutes") or 0,
                item.get("no_show_count") or 0,
                item.get("rebooking_count") or 0,
                batch_id,
                external_id,
                duplicate_key,
            ),
        )
        return
    if record_type == "workplace":
        cursor.execute(
            """
            SELECT id
            FROM finance_workplaces
            WHERE business_id = %s AND lower(name) = lower(%s)
            LIMIT 1
            """,
            (business_id, item.get("workplace_name") or "Рабочее место"),
        )
        existing_workplace = cursor.fetchone()
        workplace_id = _finance_row_value(existing_workplace, "id", 0) if existing_workplace else str(uuid.uuid4())
        cursor.execute(
            """
            INSERT INTO finance_workplaces (id, business_id, name, type, is_active)
            VALUES (%s, %s, %s, %s, TRUE)
            ON CONFLICT (id) DO NOTHING
            """,
            (
                workplace_id,
                business_id,
                item.get("workplace_name") or "Рабочее место",
                item.get("workplace_type") or "other",
            ),
        )
        cursor.execute(
            """
            INSERT INTO finance_workplace_metrics
            (id, business_id, workplace_id, period_start, period_end, available_minutes,
             booked_minutes, revenue, gross_profit, source, import_batch_id, external_id, duplicate_key)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'file', %s, %s, %s)
            """,
            (
                str(uuid.uuid4()),
                business_id,
                workplace_id,
                item.get("period_start"),
                item.get("period_end"),
                item.get("available_minutes") or 0,
                item.get("booked_minutes") or 0,
                item.get("revenue") or 0,
                item.get("gross_profit") or 0,
                batch_id,
                external_id,
                duplicate_key,
            ),
        )


def _finance_import_payload_from_request():
    uploaded_file = request.files.get("file")
    if not uploaded_file:
        raise ValueError("Файл обязателен")
    filename = uploaded_file.filename or "finance-import.csv"
    content = uploaded_file.read()
    if not content:
        raise ValueError("Файл пустой")
    mapping_raw = request.form.get("mapping") or "{}"
    try:
        mapping = json.loads(mapping_raw)
    except Exception:
        mapping = {}
    period_start = request.form.get("period_start") or default_period_range()[0]
    period_end = request.form.get("period_end") or default_period_range()[1]
    rows = finance_imports.parse_finance_file(filename, content)
    normalized = finance_imports.normalize_finance_import_rows(rows, mapping, period_start, period_end)
    return filename, content, normalized


def _load_finance_crm_connection(cursor, business_id, provider):
    cursor.execute(
        """
        SELECT id, business_id, provider, status, display_name, auth_data_encrypted,
               settings_json, last_sync_at, sync_status, error_log, created_at, updated_at
        FROM finance_crm_connections
        WHERE business_id = %s AND provider = %s
        LIMIT 1
        """,
        (business_id, provider),
    )
    row = cursor.fetchone()
    if not row:
        return None
    item = _row_to_dict(cursor, row)
    for json_key in ("settings_json", "error_log"):
        if item.get(json_key) and isinstance(item[json_key], str):
            try:
                item[json_key] = json.loads(item[json_key])
            except Exception:
                item[json_key] = {} if json_key == "settings_json" else []
    return item


def _public_finance_crm_connection(item):
    if not item:
        return None
    return {
        "id": item.get("id"),
        "business_id": item.get("business_id"),
        "provider": item.get("provider"),
        "status": item.get("status"),
        "display_name": item.get("display_name"),
        "settings": item.get("settings_json") or {},
        "last_sync_at": str(item.get("last_sync_at")) if item.get("last_sync_at") else None,
        "sync_status": item.get("sync_status"),
        "error_log": item.get("error_log") or [],
        "created_at": str(item.get("created_at")) if item.get("created_at") else None,
        "updated_at": str(item.get("updated_at")) if item.get("updated_at") else None,
    }


@finance_bp.route('/api/finance/dashboard', methods=['GET'])
def get_finance_dashboard():
    try:
        user_data, business_id, error_response = _require_finance_user_and_business()
        if error_response:
            return error_response

        db = DatabaseManager()
        cursor = db.conn.cursor()
        if request.args.get('range') == 'all':
            start_date, end_date = _finance_all_time_period(cursor, business_id)
        else:
            start_date, end_date = _finance_period_from_request()
        payload, thresholds, snapshot = _finance_snapshot_for_period(cursor, business_id, start_date, end_date)
        service_catalog = _load_finance_service_catalog(cursor, business_id)
        snapshot["services"] = _finance_catalog_rows(service_catalog, payload.get("services") or [])
        action_logs = _load_finance_action_logs(cursor, business_id, start_date, end_date)
        action_impact = _build_finance_impact(cursor, business_id, start_date, end_date)
        period_history = _build_finance_history(cursor, business_id, 6)
        db.close()

        return jsonify({
            "success": True,
            "business_id": business_id,
            "period": {"start_date": start_date, "end_date": end_date},
            "profile": {"global": True, "service_business": True, "beauty": True},
            "thresholds": thresholds,
            "action_logs": action_logs,
            "action_impact": action_impact,
            "period_history": period_history,
            "source_data": payload,
            **snapshot,
        })
    except Exception:
        return jsonify({"error": f"Ошибка получения финансового дашборда: {str(sys.exc_info()[1])}"}), 500


@finance_bp.route('/api/finance/manual-entry', methods=['POST', 'OPTIONS'])
def add_finance_manual_entry():
    try:
        if request.method == 'OPTIONS':
            return ('', 204)

        user_data, business_id, error_response = _require_finance_user_and_business()
        if error_response:
            return error_response

        data = request.get_json() or {}
        db = DatabaseManager()
        cursor = db.conn.cursor()
        inserted = _insert_finance_manual_payload(cursor, business_id, data)
        db.conn.commit()
        payload, thresholds, snapshot = _finance_snapshot_for_period(
            cursor,
            business_id,
            data.get('period_start') or data.get('from') or default_period_range()[0],
            data.get('period_end') or data.get('to') or default_period_range()[1],
        )
        db.close()

        return jsonify({
            "success": True,
            "business_id": business_id,
            "inserted": inserted,
            "thresholds": thresholds,
            "dashboard": snapshot,
        })
    except Exception:
        return jsonify({"error": f"Ошибка сохранения финансовых данных: {str(sys.exc_info()[1])}"}), 500


@finance_bp.route('/api/finance/recalculate', methods=['POST', 'OPTIONS'])
def recalculate_finance_snapshot():
    try:
        if request.method == 'OPTIONS':
            return ('', 204)

        user_data, business_id, error_response = _require_finance_user_and_business()
        if error_response:
            return error_response

        data = request.get_json() or {}
        start_date = data.get('from') or data.get('period_start') or default_period_range()[0]
        end_date = data.get('to') or data.get('period_end') or default_period_range()[1]

        db = DatabaseManager()
        cursor = db.conn.cursor()
        payload, thresholds, snapshot = _finance_snapshot_for_period(cursor, business_id, start_date, end_date)
        snapshot_id = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT INTO finance_snapshots
            (id, business_id, period_start, period_end, calculated_json, data_quality_json)
            VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb)
            """,
            (
                snapshot_id,
                business_id,
                start_date,
                end_date,
                json.dumps(snapshot.get("kpis") or {}, ensure_ascii=False),
                json.dumps(snapshot.get("data_quality") or {}, ensure_ascii=False),
            ),
        )
        db.conn.commit()
        db.close()

        return jsonify({"success": True, "snapshot_id": snapshot_id, "thresholds": thresholds, **snapshot})
    except Exception:
        return jsonify({"error": f"Ошибка пересчета финансов: {str(sys.exc_info()[1])}"}), 500


@finance_bp.route('/api/finance/data-quality', methods=['GET'])
def get_finance_data_quality():
    try:
        user_data, business_id, error_response = _require_finance_user_and_business()
        if error_response:
            return error_response

        start_date, end_date = _finance_period_from_request()
        db = DatabaseManager()
        cursor = db.conn.cursor()
        payload, thresholds, snapshot = _finance_snapshot_for_period(cursor, business_id, start_date, end_date)
        db.close()

        return jsonify({
            "success": True,
            "business_id": business_id,
            "period": {"start_date": start_date, "end_date": end_date},
            "thresholds": thresholds,
            "data_quality": snapshot["data_quality"],
            "explanations": snapshot["explanations"],
        })
    except Exception:
        return jsonify({"error": f"Ошибка оценки качества данных: {str(sys.exc_info()[1])}"}), 500


@finance_bp.route('/api/finance/recommendations', methods=['GET'])
def get_finance_recommendations():
    try:
        user_data, business_id, error_response = _require_finance_user_and_business()
        if error_response:
            return error_response

        start_date, end_date = _finance_period_from_request()
        db = DatabaseManager()
        cursor = db.conn.cursor()
        payload, thresholds, snapshot = _finance_snapshot_for_period(cursor, business_id, start_date, end_date)
        db.close()

        return jsonify({
            "success": True,
            "business_id": business_id,
            "period": {"start_date": start_date, "end_date": end_date},
            "thresholds": thresholds,
            "recommendations": snapshot["recommendations"],
            "statuses": snapshot["statuses"],
        })
    except Exception:
        return jsonify({"error": f"Ошибка получения рекомендаций: {str(sys.exc_info()[1])}"}), 500


@finance_bp.route('/api/finance/thresholds', methods=['GET'])
def get_finance_thresholds():
    try:
        user_data, business_id, error_response = _require_finance_user_and_business()
        if error_response:
            return error_response

        db = DatabaseManager()
        cursor = db.conn.cursor()
        thresholds = _load_finance_thresholds(cursor, business_id)
        db.close()

        return jsonify({
            "success": True,
            "business_id": business_id,
            "thresholds": thresholds,
        })
    except Exception:
        return jsonify({"error": f"Ошибка получения порогов KPI: {str(sys.exc_info()[1])}"}), 500


@finance_bp.route('/api/finance/thresholds', methods=['PUT', 'OPTIONS'])
def update_finance_thresholds():
    try:
        if request.method == 'OPTIONS':
            return ('', 204)

        user_data, business_id, error_response = _require_finance_user_and_business()
        if error_response:
            return error_response

        data = request.get_json() or {}
        thresholds = data.get("thresholds")
        if isinstance(thresholds, dict):
            thresholds = [
                {"metric_key": metric_key, **config}
                for metric_key, config in thresholds.items()
                if isinstance(config, dict)
            ]
        if not isinstance(thresholds, list):
            return jsonify({"error": "thresholds должен быть списком или объектом"}), 400

        db = DatabaseManager()
        cursor = db.conn.cursor()
        saved = _save_finance_thresholds(cursor, business_id, thresholds)
        db.conn.commit()
        updated = _load_finance_thresholds(cursor, business_id)
        db.close()

        return jsonify({
            "success": True,
            "business_id": business_id,
            "saved": saved,
            "thresholds": updated,
        })
    except Exception:
        return jsonify({"error": f"Ошибка сохранения порогов KPI: {str(sys.exc_info()[1])}"}), 500


@finance_bp.route('/api/finance/thresholds/reset', methods=['POST', 'OPTIONS'])
def reset_finance_thresholds():
    try:
        if request.method == 'OPTIONS':
            return ('', 204)

        user_data, business_id, error_response = _require_finance_user_and_business()
        if error_response:
            return error_response

        db = DatabaseManager()
        cursor = db.conn.cursor()
        cursor.execute(
            """
            DELETE FROM finance_kpi_thresholds
            WHERE business_id = %s
            """,
            (business_id,),
        )
        db.conn.commit()
        thresholds = _load_finance_thresholds(cursor, business_id)
        db.close()

        return jsonify({
            "success": True,
            "business_id": business_id,
            "thresholds": thresholds,
        })
    except Exception:
        return jsonify({"error": f"Ошибка сброса порогов KPI: {str(sys.exc_info()[1])}"}), 500


@finance_bp.route('/api/finance/actions', methods=['GET'])
def get_finance_actions():
    try:
        user_data, business_id, error_response = _require_finance_user_and_business()
        if error_response:
            return error_response

        start_date, end_date = _finance_period_from_request()
        db = DatabaseManager()
        cursor = db.conn.cursor()
        actions = _load_finance_action_logs(cursor, business_id, start_date, end_date)
        db.close()

        return jsonify({
            "success": True,
            "business_id": business_id,
            "period": {"start_date": start_date, "end_date": end_date},
            "actions": actions,
        })
    except Exception:
        return jsonify({"error": f"Ошибка получения действий по финансам: {str(sys.exc_info()[1])}"}), 500


@finance_bp.route('/api/finance/actions', methods=['POST', 'OPTIONS'])
def update_finance_action():
    try:
        if request.method == 'OPTIONS':
            return ('', 204)

        user_data, business_id, error_response = _require_finance_user_and_business()
        if error_response:
            return error_response

        data = request.get_json() or {}
        action_key = str(data.get("action_key") or "").strip()
        recommendation_code = str(data.get("recommendation_code") or "").strip()
        action_bucket = str(data.get("action_bucket") or "").strip()
        action_text = str(data.get("action_text") or "").strip()
        status = str(data.get("status") or "completed").strip()
        if status not in {"pending", "completed"}:
            return jsonify({"error": "status должен быть pending или completed"}), 400
        if not action_key or not recommendation_code or not action_bucket or not action_text:
            return jsonify({"error": "action_key, recommendation_code, action_bucket и action_text обязательны"}), 400

        period_start = data.get("period_start") or data.get("from")
        period_end = data.get("period_end") or data.get("to")
        completed_at_sql = "NOW()" if status == "completed" else "NULL"

        db = DatabaseManager()
        cursor = db.conn.cursor()
        cursor.execute(
            f"""
            INSERT INTO finance_action_logs
            (id, business_id, recommendation_code, action_key, action_bucket,
             action_text, status, period_start, period_end, completed_at, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, {completed_at_sql}, %s)
            ON CONFLICT (business_id, action_key) DO UPDATE SET
                recommendation_code = EXCLUDED.recommendation_code,
                action_bucket = EXCLUDED.action_bucket,
                action_text = EXCLUDED.action_text,
                status = EXCLUDED.status,
                period_start = EXCLUDED.period_start,
                period_end = EXCLUDED.period_end,
                completed_at = {completed_at_sql},
                created_by = EXCLUDED.created_by,
                updated_at = NOW()
            RETURNING id
            """,
            (
                str(uuid.uuid4()),
                business_id,
                recommendation_code,
                action_key,
                action_bucket,
                action_text,
                status,
                period_start,
                period_end,
                user_data.get("user_id"),
            ),
        )
        row = cursor.fetchone()
        action_id = _finance_row_value(row, "id", 0) if row else None
        db.conn.commit()
        actions = _load_finance_action_logs(cursor, business_id, period_start, period_end)
        db.close()

        return jsonify({
            "success": True,
            "business_id": business_id,
            "action_id": action_id,
            "actions": actions,
        })
    except Exception:
        return jsonify({"error": f"Ошибка сохранения действия по финансам: {str(sys.exc_info()[1])}"}), 500


@finance_bp.route('/api/finance/import-template', methods=['GET'])
def get_finance_import_template():
    profile = request.args.get("profile") or request.args.get("source") or "manual"
    content = finance_imports.finance_import_template_csv(profile)
    return Response(
        content,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=finance-import-template.csv"},
    )


@finance_bp.route('/api/finance/import-templates', methods=['GET'])
def get_finance_import_templates():
    return jsonify({
        "success": True,
        "templates": finance_imports.finance_import_templates(),
    })


@finance_bp.route('/api/finance/history', methods=['GET'])
def get_finance_history():
    try:
        user_data, business_id, error_response = _require_finance_user_and_business()
        if error_response:
            return error_response

        months = request.args.get("months") or 6
        db = DatabaseManager()
        cursor = db.conn.cursor()
        points = _build_finance_history(cursor, business_id, months)
        db.close()

        return jsonify({
            "success": True,
            "business_id": business_id,
            "months": min(max(int(months or 6), 1), 12),
            "history": points,
        })
    except Exception:
        return jsonify({"error": f"Ошибка получения истории финансов: {str(sys.exc_info()[1])}"}), 500


@finance_bp.route('/api/finance/impact', methods=['GET'])
def get_finance_action_impact():
    try:
        user_data, business_id, error_response = _require_finance_user_and_business()
        if error_response:
            return error_response

        start_date, end_date = _finance_period_from_request()
        db = DatabaseManager()
        cursor = db.conn.cursor()
        impact = _build_finance_impact(cursor, business_id, start_date, end_date)
        db.close()

        return jsonify({
            "success": True,
            "business_id": business_id,
            **impact,
        })
    except Exception:
        return jsonify({"error": f"Ошибка расчета влияния действий: {str(sys.exc_info()[1])}"}), 500


@finance_bp.route('/api/finance/import-preview', methods=['POST', 'OPTIONS'])
def preview_finance_import():
    try:
        if request.method == 'OPTIONS':
            return ('', 204)

        user_data, business_id, error_response = _require_finance_user_and_business()
        if error_response:
            return error_response

        filename, content, normalized = _finance_import_payload_from_request()
        preview_rows = normalized.get("rows", [])[:10]
        return jsonify({
            "success": True,
            "business_id": business_id,
            "file_name": filename,
            "file_hash": finance_imports.file_hash(content),
            "rows_total": normalized.get("total", 0),
            "valid_rows": len(normalized.get("rows", [])),
            "failed_rows": len(normalized.get("errors", [])),
            "mapping": normalized.get("mapping", {}),
            "preview": preview_rows,
            "errors": normalized.get("errors", [])[:20],
        })
    except Exception:
        return jsonify({"error": f"Ошибка preview импорта: {str(sys.exc_info()[1])}"}), 500


@finance_bp.route('/api/finance/import-file', methods=['POST', 'OPTIONS'])
def import_finance_file():
    try:
        if request.method == 'OPTIONS':
            return ('', 204)

        user_data, business_id, error_response = _require_finance_user_and_business()
        if error_response:
            return error_response

        filename, content, normalized = _finance_import_payload_from_request()
        batch_id = str(uuid.uuid4())
        content_hash = finance_imports.file_hash(content)
        rows = normalized.get("rows", [])
        errors = normalized.get("errors", [])
        imported = 0
        skipped = 0
        import_errors = list(errors[:100])

        db = DatabaseManager()
        cursor = db.conn.cursor()
        cursor.execute(
            """
            INSERT INTO finance_import_batches
            (id, business_id, source_type, status, file_name, file_hash, rows_total,
             mapping_json, error_log)
            VALUES (%s, %s, 'file', 'processing', %s, %s, %s, %s::jsonb, %s::jsonb)
            """,
            (
                batch_id,
                business_id,
                filename,
                content_hash,
                normalized.get("total", 0),
                json.dumps(normalized.get("mapping", {}), ensure_ascii=False),
                json.dumps(import_errors, ensure_ascii=False),
            ),
        )

        for item in rows:
            if _finance_import_duplicate_exists(cursor, business_id, item.get("record_type"), item.get("duplicate_key")):
                skipped += 1
                continue
            try:
                _insert_finance_import_item(cursor, business_id, batch_id, item)
                imported += 1
            except Exception:
                if len(import_errors) < 100:
                    import_errors.append({
                        "row": item.get("row_number"),
                        "errors": [str(sys.exc_info()[1])],
                    })

        failed = len(import_errors)
        status = "completed" if failed == 0 else "completed_with_errors"
        cursor.execute(
            """
            UPDATE finance_import_batches
            SET status = %s,
                rows_imported = %s,
                rows_skipped = %s,
                rows_failed = %s,
                error_log = %s::jsonb,
                completed_at = NOW()
            WHERE id = %s
            """,
            (
                status,
                imported,
                skipped,
                failed,
                json.dumps(import_errors, ensure_ascii=False),
                batch_id,
            ),
        )
        db.conn.commit()

        start_date = request.form.get("period_start") or default_period_range()[0]
        end_date = request.form.get("period_end") or default_period_range()[1]
        payload, thresholds, snapshot = _finance_snapshot_for_period(cursor, business_id, start_date, end_date)
        db.close()

        return jsonify({
            "success": True,
            "batch_id": batch_id,
            "file_hash": content_hash,
            "rows_total": normalized.get("total", 0),
            "rows_imported": imported,
            "rows_skipped": skipped,
            "rows_failed": failed,
            "errors": import_errors[:20],
            "thresholds": thresholds,
            "dashboard": snapshot,
        })
    except Exception:
        return jsonify({"error": f"Ошибка импорта финансов: {str(sys.exc_info()[1])}"}), 500


@finance_bp.route('/api/finance/imports', methods=['GET'])
def get_finance_import_batches():
    try:
        user_data, business_id, error_response = _require_finance_user_and_business()
        if error_response:
            return error_response

        db = DatabaseManager()
        cursor = db.conn.cursor()
        cursor.execute(
            """
            SELECT id, source_type, status, file_name, file_hash, rows_total,
                   rows_imported, rows_skipped, rows_failed, error_log,
                   created_at, completed_at
            FROM finance_import_batches
            WHERE business_id = %s
            ORDER BY created_at DESC
            LIMIT 20
            """,
            (business_id,),
        )
        batches = []
        for row in cursor.fetchall() or []:
            item = _row_to_dict(cursor, row)
            if item.get("error_log") and isinstance(item["error_log"], str):
                try:
                    item["error_log"] = json.loads(item["error_log"])
                except Exception:
                    item["error_log"] = []
            batches.append(item)
        db.close()

        return jsonify({"success": True, "business_id": business_id, "imports": batches})
    except Exception:
        return jsonify({"error": f"Ошибка получения истории импорта: {str(sys.exc_info()[1])}"}), 500


@finance_bp.route('/api/finance/crm/providers', methods=['GET'])
def get_finance_crm_providers():
    try:
        user_data, business_id, error_response = _require_finance_user_and_business()
        if error_response:
            return error_response

        db = DatabaseManager()
        cursor = db.conn.cursor()
        connections = []
        for provider in finance_crm.CRM_PROVIDERS:
            connection = _load_finance_crm_connection(cursor, business_id, provider["provider"])
            enriched = dict(provider)
            enriched["connection"] = _public_finance_crm_connection(connection)
            connections.append(enriched)
        db.close()

        return jsonify({"success": True, "business_id": business_id, "providers": connections})
    except Exception:
        return jsonify({"error": f"Ошибка получения CRM провайдеров: {str(sys.exc_info()[1])}"}), 500


@finance_bp.route('/api/finance/crm/connect', methods=['POST', 'OPTIONS'])
def connect_finance_crm():
    try:
        if request.method == 'OPTIONS':
            return ('', 204)

        user_data, business_id, error_response = _require_finance_user_and_business()
        if error_response:
            return error_response

        data = request.get_json() or {}
        provider = str(data.get("provider") or "").strip()
        provider_meta = finance_crm.get_crm_provider(provider)
        if not provider_meta:
            return jsonify({"error": "CRM provider is not supported"}), 400
        if provider_meta.get("status") != "available":
            return jsonify({"error": "CRM provider is planned but not available yet"}), 400

        auth_data = data.get("auth_data") or {}
        settings = data.get("settings") or {}
        missing_fields = []
        for field in provider_meta.get("required_auth_fields") or []:
            if not str(auth_data.get(field) or "").strip():
                missing_fields.append(field)
        for field in provider_meta.get("required_settings_fields") or []:
            if not str(settings.get(field) or auth_data.get(field) or "").strip():
                missing_fields.append(field)
        if missing_fields:
            return jsonify({
                "error": "CRM credentials are incomplete",
                "missing_fields": missing_fields,
            }), 400

        display_name = data.get("display_name") or provider_meta.get("label") or provider
        encrypted_auth_data = encrypt_auth_data(json.dumps(auth_data, ensure_ascii=False)) if auth_data else ""

        db = DatabaseManager()
        cursor = db.conn.cursor()
        connection_id = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT INTO finance_crm_connections
            (id, business_id, provider, status, display_name, auth_data_encrypted,
             settings_json, sync_status, error_log)
            VALUES (%s, %s, %s, 'connected', %s, %s, %s::jsonb, 'never_synced', '[]'::jsonb)
            ON CONFLICT (business_id, provider) DO UPDATE SET
                status = 'connected',
                display_name = EXCLUDED.display_name,
                auth_data_encrypted = EXCLUDED.auth_data_encrypted,
                settings_json = EXCLUDED.settings_json,
                sync_status = COALESCE(finance_crm_connections.sync_status, 'never_synced'),
                updated_at = NOW()
            RETURNING id
            """,
            (
                connection_id,
                business_id,
                provider,
                display_name,
                encrypted_auth_data,
                json.dumps(settings, ensure_ascii=False),
            ),
        )
        row = cursor.fetchone()
        resolved_id = _finance_row_value(row, "id", 0) if row else connection_id
        db.conn.commit()
        connection = _load_finance_crm_connection(cursor, business_id, provider)
        db.close()

        return jsonify({
            "success": True,
            "connection_id": resolved_id,
            "connection": _public_finance_crm_connection(connection),
        })
    except Exception:
        return jsonify({"error": f"Ошибка подключения CRM: {str(sys.exc_info()[1])}"}), 500


@finance_bp.route('/api/finance/crm/status', methods=['GET'])
def get_finance_crm_status():
    try:
        user_data, business_id, error_response = _require_finance_user_and_business()
        if error_response:
            return error_response

        provider = request.args.get("provider")
        db = DatabaseManager()
        cursor = db.conn.cursor()
        if provider:
            connection = _load_finance_crm_connection(cursor, business_id, provider)
            db.close()
            return jsonify({
                "success": True,
                "business_id": business_id,
                "connection": _public_finance_crm_connection(connection),
            })

        cursor.execute(
            """
            SELECT id, business_id, provider, status, display_name, settings_json,
                   last_sync_at, sync_status, error_log, created_at, updated_at
            FROM finance_crm_connections
            WHERE business_id = %s
            ORDER BY updated_at DESC
            """,
            (business_id,),
        )
        connections = [_public_finance_crm_connection(_row_to_dict(cursor, row)) for row in cursor.fetchall() or []]
        db.close()
        return jsonify({"success": True, "business_id": business_id, "connections": connections})
    except Exception:
        return jsonify({"error": f"Ошибка статуса CRM: {str(sys.exc_info()[1])}"}), 500


def _finance_crm_auth_settings_from_connection(connection):
    auth_data = {}
    encrypted = connection.get("auth_data_encrypted")
    if encrypted:
        decrypted = decrypt_auth_data(encrypted)
        if decrypted:
            try:
                auth_data = json.loads(decrypted)
            except Exception:
                auth_data = {}
    return auth_data, connection.get("settings_json") or {}


def _store_finance_crm_preview(cursor, business_id, provider, preview):
    connection = _load_finance_crm_connection(cursor, business_id, provider)
    settings = dict((connection or {}).get("settings_json") or {})
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=60)).isoformat()
    settings["last_preview"] = {
        "provider": provider,
        "token": preview.get("preview_token"),
        "period": preview.get("period") or {},
        "rows_total": preview.get("rows_total"),
        "valid_rows": preview.get("valid_rows"),
        "failed_rows": preview.get("failed_rows"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": expires_at,
    }
    cursor.execute(
        """
        UPDATE finance_crm_connections
        SET settings_json = %s::jsonb,
            sync_status = 'preview_ok',
            error_log = %s::jsonb,
            updated_at = NOW()
        WHERE business_id = %s AND provider = %s
        """,
        (
            json.dumps(settings, ensure_ascii=False),
            json.dumps(preview.get("errors") or [], ensure_ascii=False),
            business_id,
            provider,
        ),
    )


def _validate_finance_crm_preview_confirmation(connection, provider, start_date, end_date, token):
    if not token:
        return "Сначала проверьте данные CRM через preview, затем подтвердите импорт."
    settings = connection.get("settings_json") or {}
    last_preview = settings.get("last_preview") or {}
    if last_preview.get("provider") != provider:
        return "Preview относится к другой CRM. Запустите проверку данных заново."
    period = last_preview.get("period") or {}
    if period.get("start_date") != start_date or period.get("end_date") != end_date:
        return "Preview относится к другому периоду. Запустите проверку данных заново."
    if last_preview.get("token") != token:
        return "Preview устарел или не совпадает с импортом. Запустите проверку данных заново."
    expires_at = last_preview.get("expires_at")
    if expires_at:
        try:
            expires_at_dt = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
            if expires_at_dt < datetime.now(timezone.utc):
                return "Preview устарел. Запустите проверку данных заново."
        except Exception:
            return "Preview сохранён некорректно. Запустите проверку данных заново."
    return None


def _run_finance_crm_preview(cursor, business_id, provider, start_date, end_date, sample_limit=5):
    connection = _load_finance_crm_connection(cursor, business_id, provider)
    if not connection or connection.get("status") != "connected":
        raise finance_crm.CRMConnectionError("CRM is not connected")

    auth_data, settings = _finance_crm_auth_settings_from_connection(connection)
    connector = finance_crm.create_crm_connector(provider, auth_data, settings)
    dataset = connector.fetch_all(start_date, end_date)
    return finance_crm.build_crm_sync_preview(provider, dataset, start_date, end_date, sample_limit)


@finance_bp.route('/api/finance/crm/preview', methods=['POST', 'OPTIONS'])
def preview_finance_crm_sync():
    try:
        if request.method == 'OPTIONS':
            return ('', 204)

        user_data, business_id, error_response = _require_finance_user_and_business()
        if error_response:
            return error_response

        data = request.get_json() or {}
        provider = str(data.get("provider") or "").strip()
        if not provider:
            return jsonify({"error": "provider is required"}), 400

        start_date = data.get("from") or data.get("period_start") or default_period_range()[0]
        end_date = data.get("to") or data.get("period_end") or default_period_range()[1]
        sample_limit = int(data.get("sample_limit") or 5)
        sample_limit = min(max(sample_limit, 1), 20)

        db = DatabaseManager()
        cursor = db.conn.cursor()
        try:
            preview = _run_finance_crm_preview(cursor, business_id, provider, start_date, end_date, sample_limit)
        except finance_crm.CRMConnectionError:
            error_message = str(sys.exc_info()[1])
            cursor.execute(
                """
                UPDATE finance_crm_connections
                SET sync_status = 'preview_failed',
                    error_log = %s::jsonb,
                    updated_at = NOW()
                WHERE business_id = %s AND provider = %s
                """,
                (
                    json.dumps([{"errors": [error_message]}], ensure_ascii=False),
                    business_id,
                    provider,
                ),
            )
            db.conn.commit()
            db.close()
            return jsonify({"error": error_message, "will_write": False}), 400

        _store_finance_crm_preview(cursor, business_id, provider, preview)
        db.conn.commit()
        updated_connection = _load_finance_crm_connection(cursor, business_id, provider)
        db.close()

        return jsonify({
            "success": True,
            "business_id": business_id,
            "connection": _public_finance_crm_connection(updated_connection),
            **preview,
        })
    except Exception:
        return jsonify({"error": f"Ошибка preview CRM: {str(sys.exc_info()[1])}"}), 500


@finance_bp.route('/api/finance/crm/sync', methods=['POST', 'OPTIONS'])
def sync_finance_crm():
    try:
        if request.method == 'OPTIONS':
            return ('', 204)

        user_data, business_id, error_response = _require_finance_user_and_business()
        if error_response:
            return error_response

        data = request.get_json() or {}
        provider = str(data.get("provider") or "").strip()
        if not provider:
            return jsonify({"error": "provider is required"}), 400

        start_date = data.get("from") or data.get("period_start") or default_period_range()[0]
        end_date = data.get("to") or data.get("period_end") or default_period_range()[1]
        confirm_preview_token = str(data.get("confirm_preview_token") or data.get("preview_token") or "").strip()

        db = DatabaseManager()
        cursor = db.conn.cursor()
        connection = _load_finance_crm_connection(cursor, business_id, provider)
        if not connection or connection.get("status") != "connected":
            db.close()
            return jsonify({"error": "CRM is not connected"}), 400

        preview_error = _validate_finance_crm_preview_confirmation(
            connection,
            provider,
            start_date,
            end_date,
            confirm_preview_token,
        )
        if preview_error:
            db.close()
            return jsonify({"error": preview_error, "requires_preview": True}), 400

        auth_data, settings = _finance_crm_auth_settings_from_connection(connection)

        connector = finance_crm.create_crm_connector(provider, auth_data, settings)
        try:
            dataset = connector.fetch_all(start_date, end_date)
        except finance_crm.CRMConnectionError:
            error_message = str(sys.exc_info()[1])
            cursor.execute(
                """
                UPDATE finance_crm_connections
                SET sync_status = 'failed',
                    error_log = %s::jsonb,
                    updated_at = NOW()
                WHERE business_id = %s AND provider = %s
                """,
                (
                    json.dumps([{"errors": [error_message]}], ensure_ascii=False),
                    business_id,
                    provider,
                ),
            )
            db.conn.commit()
            db.close()
            return jsonify({"error": error_message}), 400
        preview = finance_crm.build_crm_sync_preview(provider, dataset, start_date, end_date, 1)
        if preview.get("preview_token") != confirm_preview_token:
            db.close()
            return jsonify({
                "error": "Данные CRM изменились после preview. Запустите проверку данных заново.",
                "requires_preview": True,
            }), 400
        normalized = finance_crm.crm_dataset_to_finance_rows(dataset, start_date, end_date)

        batch_id = str(uuid.uuid4())
        rows = normalized.get("rows", [])
        import_errors = list((normalized.get("errors") or [])[:100])
        imported = 0
        skipped = 0

        cursor.execute(
            """
            INSERT INTO finance_import_batches
            (id, business_id, source_type, status, file_name, file_hash, rows_total,
             mapping_json, error_log)
            VALUES (%s, %s, 'crm', 'processing', %s, %s, %s, %s::jsonb, %s::jsonb)
            """,
            (
                batch_id,
                business_id,
                f"{provider}-sync",
                f"crm:{provider}:{start_date}:{end_date}",
                normalized.get("total", 0),
                json.dumps({"provider": provider}, ensure_ascii=False),
                json.dumps(import_errors, ensure_ascii=False),
            ),
        )

        for item in rows:
            if _finance_import_duplicate_exists(cursor, business_id, item.get("record_type"), item.get("duplicate_key")):
                skipped += 1
                continue
            try:
                _insert_finance_import_item(cursor, business_id, batch_id, item)
                imported += 1
            except Exception:
                if len(import_errors) < 100:
                    import_errors.append({"row": item.get("row_number"), "errors": [str(sys.exc_info()[1])]})

        failed = len(import_errors)
        status = "completed" if failed == 0 else "completed_with_errors"
        cursor.execute(
            """
            UPDATE finance_import_batches
            SET status = %s,
                rows_imported = %s,
                rows_skipped = %s,
                rows_failed = %s,
                error_log = %s::jsonb,
                completed_at = NOW()
            WHERE id = %s
            """,
            (
                status,
                imported,
                skipped,
                failed,
                json.dumps(import_errors, ensure_ascii=False),
                batch_id,
            ),
        )
        cursor.execute(
            """
            UPDATE finance_crm_connections
            SET last_sync_at = NOW(),
                sync_status = %s,
                error_log = %s::jsonb,
                updated_at = NOW()
            WHERE business_id = %s AND provider = %s
            """,
            (
                status,
                json.dumps(import_errors, ensure_ascii=False),
                business_id,
                provider,
            ),
        )
        db.conn.commit()

        payload, thresholds, snapshot = _finance_snapshot_for_period(cursor, business_id, start_date, end_date)
        updated_connection = _load_finance_crm_connection(cursor, business_id, provider)
        db.close()

        return jsonify({
            "success": True,
            "business_id": business_id,
            "provider": provider,
            "batch_id": batch_id,
            "rows_total": normalized.get("total", 0),
            "rows_imported": imported,
            "rows_skipped": skipped,
            "rows_failed": failed,
            "errors": import_errors[:20],
            "connection": _public_finance_crm_connection(updated_connection),
            "thresholds": thresholds,
            "dashboard": snapshot,
        })
    except Exception:
        return jsonify({"error": f"Ошибка синхронизации CRM: {str(sys.exc_info()[1])}"}), 500


@finance_bp.route('/api/finance/transaction', methods=['POST'])
def add_transaction():
    """Добавить финансовую транзакцию"""
    try:
        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        data = request.get_json()

        # Валидация данных
        required_fields = ['transaction_date', 'amount', 'client_type']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Поле {field} обязательно"}), 400

        if data['client_type'] not in ['new', 'returning']:
            return jsonify({"error": "client_type должен быть 'new' или 'returning'"}), 400

        if data['amount'] <= 0:
            return jsonify({"error": "Сумма должна быть больше 0"}), 400

        # Сохраняем транзакцию
        db = DatabaseManager()
        cursor = db.conn.cursor()

        transaction_id = str(uuid.uuid4())

        # Проверяем наличие поля master_id в таблице
        columns = _table_columns(cursor, "financialtransactions")
        has_master_id = 'master_id' in columns

        if has_master_id:
            cursor.execute(
                """
                INSERT INTO financialtransactions
                (id, user_id, transaction_date, amount, client_type, services, notes, master_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    transaction_id,
                    user_data['user_id'],
                    data['transaction_date'],
                    data['amount'],
                    data['client_type'],
                    json.dumps(data.get('services', [])),
                    data.get('notes', ''),
                    data.get('master_id'),
                ),
            )
        else:
            cursor.execute(
                """
                INSERT INTO financialtransactions
                (id, user_id, transaction_date, amount, client_type, services, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    transaction_id,
                    user_data['user_id'],
                    data['transaction_date'],
                    data['amount'],
                    data['client_type'],
                    json.dumps(data.get('services', [])),
                    data.get('notes', ''),
                ),
            )

        db.conn.commit()
        db.close()

        return jsonify({
            "success": True,
            "transaction_id": transaction_id,
            "message": "Транзакция добавлена успешно"
        })

    except Exception as e:
        return jsonify({"error": f"Ошибка добавления транзакции: {str(e)}"}), 500


@finance_bp.route('/api/finance/transaction/<string:transaction_id>', methods=['PUT', 'OPTIONS'])
def update_transaction(transaction_id):
    """Обновить финансовую транзакцию"""
    try:
        if request.method == 'OPTIONS':
            return ('', 204)

        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        data = request.get_json() or {}

        db = DatabaseManager()
        cursor = db.conn.cursor()

        # Проверяем принадлежность транзакции пользователю
        cursor.execute("SELECT id, user_id FROM financialtransactions WHERE id = %s LIMIT 1", (transaction_id,))
        row = cursor.fetchone()
        if not row:
            db.close()
            return jsonify({"error": "Транзакция не найдена"}), 404
        owner_id = row.get("user_id") if hasattr(row, "get") else row[1]
        if owner_id != user_data['user_id']:
            db.close()
            return jsonify({"error": "Нет доступа к транзакции"}), 403

        fields = []
        params = []
        if 'transaction_date' in data:
            fields.append("transaction_date = %s")
            params.append(data.get('transaction_date'))
        if 'amount' in data:
            fields.append("amount = %s")
            params.append(float(data.get('amount') or 0))
        if 'client_type' in data:
            fields.append("client_type = %s")
            params.append(data.get('client_type') or 'new')
        if 'services' in data:
            fields.append("services = %s")
            params.append(json.dumps(data.get('services') or []))
        if 'notes' in data:
            fields.append("notes = %s")
            params.append(data.get('notes') or '')

        if not fields:
            db.close()
            return jsonify({"error": "Нет полей для обновления"}), 400

        params.append(transaction_id)
        cursor.execute(f"UPDATE financialtransactions SET {', '.join(fields)} WHERE id = %s", params)
        db.conn.commit()
        db.close()

        return jsonify({"success": True, "message": "Транзакция обновлена"})

    except Exception as e:
        return jsonify({"error": f"Ошибка обновления транзакции: {str(e)}"}), 500


@finance_bp.route('/api/finance/transaction/<string:transaction_id>', methods=['DELETE', 'OPTIONS'])
def delete_transaction(transaction_id):
    """Удалить финансовую транзакцию"""
    try:
        if request.method == 'OPTIONS':
            return ('', 204)

        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        db = DatabaseManager()
        cursor = db.conn.cursor()

        # Проверяем принадлежность транзакции пользователю
        cursor.execute("SELECT id, user_id FROM financialtransactions WHERE id = %s LIMIT 1", (transaction_id,))
        row = cursor.fetchone()
        if not row:
            db.close()
            return jsonify({"error": "Транзакция не найдена"}), 404
        owner_id = row.get("user_id") if hasattr(row, "get") else row[1]
        if owner_id != user_data['user_id']:
            db.close()
            return jsonify({"error": "Нет доступа к транзакции"}), 403

        cursor.execute("DELETE FROM financialtransactions WHERE id = %s", (transaction_id,))
        db.conn.commit()
        db.close()

        return jsonify({"success": True, "message": "Транзакция удалена"})

    except Exception as e:
        return jsonify({"error": f"Ошибка удаления транзакции: {str(e)}"}), 500

@finance_bp.route('/api/finance/transaction/upload', methods=['POST', 'OPTIONS'])
def upload_transaction_file():
    """Загрузить файл или фото с транзакциями и распознать их"""
    try:
        if request.method == 'OPTIONS':
            return ('', 204)

        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        # Проверяем наличие файла
        file = None
        is_image = False

        if 'file' in request.files:
            file = request.files['file']
            if file.filename == '':
                file = None
        elif 'photo' in request.files:
            file = request.files['photo']
            is_image = True
            if file.filename == '':
                file = None

        if not file:
            return jsonify({"error": "Файл не выбран"}), 400

        # Проверяем тип файла
        if is_image:
            allowed_types = ['image/png', 'image/jpeg', 'image/jpg']
            if file.content_type not in allowed_types:
                return jsonify({"error": "Неподдерживаемый тип файла. Разрешены: PNG, JPG, JPEG"}), 400
        else:
            allowed_types = ['application/pdf', 'application/msword',
                           'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                           'application/vnd.ms-excel',
                           'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                           'text/plain', 'text/csv']
            if file.content_type not in allowed_types:
                return jsonify({"error": "Неподдерживаемый тип файла. Разрешены: PDF, DOC, DOCX, XLS, XLSX, TXT, CSV"}), 400

        # Читаем промпт для анализа транзакций
        try:
            with open('prompts/transaction-analysis-prompt.txt', 'r', encoding='utf-8') as f:
                prompt_content = f.read()
        except FileNotFoundError:
            prompt_content = """Проанализируй документ/фото и извлеки все транзакции (продажи услуг).
Верни результат в формате JSON:
{
  "transactions": [
    {
      "transaction_date": "YYYY-MM-DD",
      "amount": число,
      "client_type": "new" или "returning",
      "services": ["услуга1", "услуга2"],
      "master_name": "имя мастера" или null,
      "notes": "дополнительная информация" или null
    }
  ]
}"""

        # Обрабатываем файл
        if is_image:
            # Для изображений - анализ через GigaChat
            import base64
            image_data = file.read()
            image_base64 = base64.b64encode(image_data).decode('utf-8')

            business_id = get_business_id_from_user(user_data['user_id'])
            result = analyze_screenshot_with_gigachat(
                image_base64,
                prompt_content,
                business_id=business_id,
                user_id=user_data['user_id']
            )

            if 'error' in result:
                return jsonify({"error": result['error']}), 500

            # Парсим JSON из результата
            try:
                analysis_result = json.loads(result) if isinstance(result, str) else result
                transactions = analysis_result.get('transactions', [])
            except:
                return jsonify({"error": "Не удалось распарсить результат анализа"}), 500
        else:
            # Для текстовых файлов - читаем содержимое и анализируем
            file_content = file.read().decode('utf-8', errors='ignore')
            business_id = get_business_id_from_user(user_data['user_id'])
            result = analyze_text_with_gigachat(
                prompt_content + "\n\nСодержимое файла:\n" + file_content,
                business_id=business_id,
                user_id=user_data['user_id']
            )

            if 'error' in result:
                return jsonify({"error": result['error']}), 500

            try:
                analysis_result = json.loads(result) if isinstance(result, str) else result
                transactions = analysis_result.get('transactions', [])
            except:
                return jsonify({"error": "Не удалось распарсить результат анализа"}), 500

        # Сохраняем транзакции в БД
        db = DatabaseManager()
        cursor = db.conn.cursor()

        # Проверяем наличие полей master_id и business_id
        columns = _table_columns(cursor, "financialtransactions")
        has_master_id = 'master_id' in columns
        has_business_id = 'business_id' in columns

        saved_transactions = []
        for trans in transactions:
            transaction_id = str(uuid.uuid4())

            # Получаем master_id по имени мастера (если есть таблица Masters)
            master_id = None
            if trans.get('master_name'):
                cursor.execute("SELECT to_regclass('public.masters')")
                masters_table_exists = cursor.fetchone()
                if masters_table_exists:
                    cursor.execute("SELECT id FROM masters WHERE name = %s LIMIT 1", (trans['master_name'],))
                    master_row = cursor.fetchone()
                    if master_row:
                        master_id = master_row[0]

            # Получаем business_id из текущего бизнеса пользователя
            business_id = None
            if has_business_id:
                cursor.execute("SELECT id FROM businesses WHERE owner_id = %s LIMIT 1", (user_data['user_id'],))
                business_row = cursor.fetchone()
                if business_row:
                    business_id = business_row.get("id") if hasattr(business_row, "get") else business_row[0]

            if has_master_id and has_business_id:
                cursor.execute("""
                    INSERT INTO financialtransactions
                    (id, user_id, business_id, transaction_date, amount, client_type, services, notes, master_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    transaction_id,
                    user_data['user_id'],
                    business_id,
                    trans.get('transaction_date', datetime.now().strftime('%Y-%m-%d')),
                    trans.get('amount', 0),
                    trans.get('client_type', 'new'),
                    json.dumps(trans.get('services', [])),
                    trans.get('notes', ''),
                    master_id
                ))
            elif has_master_id:
                cursor.execute("""
                    INSERT INTO financialtransactions
                    (id, user_id, transaction_date, amount, client_type, services, notes, master_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    transaction_id,
                    user_data['user_id'],
                    trans.get('transaction_date', datetime.now().strftime('%Y-%m-%d')),
                    trans.get('amount', 0),
                    trans.get('client_type', 'new'),
                    json.dumps(trans.get('services', [])),
                    trans.get('notes', ''),
                    master_id
                ))
            elif has_business_id:
                cursor.execute("""
                    INSERT INTO financialtransactions
                    (id, user_id, business_id, transaction_date, amount, client_type, services, notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    transaction_id,
                    user_data['user_id'],
                    business_id,
                    trans.get('transaction_date', datetime.now().strftime('%Y-%m-%d')),
                    trans.get('amount', 0),
                    trans.get('client_type', 'new'),
                    json.dumps(trans.get('services', [])),
                    trans.get('notes', '')
                ))
            else:
                cursor.execute("""
                    INSERT INTO financialtransactions
                    (id, user_id, transaction_date, amount, client_type, services, notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    transaction_id,
                    user_data['user_id'],
                    trans.get('transaction_date', datetime.now().strftime('%Y-%m-%d')),
                    trans.get('amount', 0),
                    trans.get('client_type', 'new'),
                    json.dumps(trans.get('services', [])),
                    trans.get('notes', '')
                ))

            saved_transactions.append({
                "id": transaction_id,
                "transaction_date": trans.get('transaction_date'),
                "amount": trans.get('amount'),
                "client_type": trans.get('client_type'),
                "services": trans.get('services', []),
                "master_id": master_id,
                "notes": trans.get('notes')
            })

        db.conn.commit()
        db.close()

        return jsonify({
            "success": True,
            "transactions": saved_transactions,
            "count": len(saved_transactions),
            "message": f"Успешно добавлено {len(saved_transactions)} транзакций"
        })

    except Exception as e:
        return jsonify({"error": f"Ошибка обработки файла: {str(e)}"}), 500

@finance_bp.route('/api/finance/transactions', methods=['GET'])
def get_transactions():
    """Получить список транзакций"""
    try:
        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        # Параметры запроса
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))

        db = DatabaseManager()
        cursor = db.conn.cursor()

        # Строим запрос с явными полями (без SELECT *)
        query = """
            SELECT
                id,
                business_id,
                transaction_date,
                amount,
                client_type,
                services,
                notes,
                created_at
            FROM FinancialTransactions
            WHERE user_id = ?
        """
        params = [user_data['user_id']]

        # Фильтр по бизнесу, если передан
        current_business_id = request.args.get('business_id')
        if current_business_id:
            query += " AND business_id = ?"
            params.append(current_business_id)

        if start_date:
            query += " AND transaction_date >= ?"
            params.append(start_date)

        if end_date:
            query += " AND transaction_date <= ?"
            params.append(end_date)

        query += " ORDER BY transaction_date DESC, created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, params)
        transactions = cursor.fetchall()

        # Преобразуем в словари
        result = []
        for t in transactions:
            tx_id = t[0]
            business_id = t[1]
            tx_date = t[2]
            amount = float(t[3] or 0)
            client_type_val = t[4] or 'new'
            services_raw = t[5]
            notes_val = t[6] or ''
            created_at_val = t[7]

            services_list = []
            if services_raw:
                try:
                    services_list = json.loads(services_raw) if isinstance(services_raw, str) else services_raw
                    if not isinstance(services_list, list):
                        services_list = []
                except Exception:
                    services_list = []

            result.append({
                "id": tx_id,
                "business_id": business_id,
                "transaction_date": tx_date,
                "amount": amount,
                "client_type": client_type_val,
                "services": services_list,
                "notes": notes_val,
                "created_at": created_at_val
            })

        db.close()

        return jsonify({
            "success": True,
            "transactions": result,
            "count": len(result)
        })

    except Exception as e:
        return jsonify({"error": f"Ошибка получения транзакций: {str(e)}"}), 500

@finance_bp.route('/api/finance/metrics', methods=['GET'])
def get_financial_metrics():
    """Получить финансовые метрики"""
    try:
        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        # Параметры периода
        period = request.args.get('period', 'month')  # week, month, quarter, year
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        business_id = request.args.get('business_id')

        db = DatabaseManager()
        cursor = db.conn.cursor()

        # Если передан business_id - проверяем доступ
        if business_id:
            owner_id = get_business_owner_id(cursor, business_id, include_active_check=True)
            if not owner_id:
                db.close()
                return jsonify({"error": "Бизнес не найден"}), 404
            if owner_id != user_data['user_id'] and not user_data.get('is_superadmin'):
                db.close()
                return jsonify({"error": "Нет доступа к этому бизнесу"}), 403

        # Если даты не указаны, вычисляем период
        if not start_date or not end_date:
            from datetime import datetime, timedelta
            now = datetime.now()

            if period == 'week':
                start_date = (now - timedelta(days=7)).strftime('%Y-%m-%d')
                end_date = now.strftime('%Y-%m-%d')
            elif period == 'month':
                start_date = (now - timedelta(days=30)).strftime('%Y-%m-%d')
                end_date = now.strftime('%Y-%m-%d')
            elif period == 'quarter':
                start_date = (now - timedelta(days=90)).strftime('%Y-%m-%d')
                end_date = now.strftime('%Y-%m-%d')
            elif period == 'year':
                start_date = (now - timedelta(days=365)).strftime('%Y-%m-%d')
                end_date = now.strftime('%Y-%m-%d')

        # Формируем WHERE условие с учётом business_id
        where_clause = "transaction_date BETWEEN %s AND %s"
        where_params = [start_date, end_date]

        if business_id:
            where_clause = f"business_id = %s AND {where_clause}"
            where_params = [business_id] + where_params
        else:
            # Старая логика для обратной совместимости
            where_clause = f"user_id = %s AND {where_clause}"
            where_params = [user_data['user_id']] + where_params

        # Получаем агрегированные данные
        cursor.execute(f"""
            SELECT
                COUNT(*) as total_orders,
                SUM(amount) as total_revenue,
                AVG(amount) as average_check,
                SUM(CASE WHEN client_type = 'new' THEN 1 ELSE 0 END) as new_clients,
                SUM(CASE WHEN client_type = 'returning' THEN 1 ELSE 0 END) as returning_clients
            FROM financialtransactions
            WHERE {where_clause}
        """, tuple(where_params))

        raw_metrics = cursor.fetchone()
        metrics = _row_to_dict(cursor, raw_metrics) if raw_metrics else {}

        # Вычисляем retention rate
        # Вычисляем retention rate
        new_clients = metrics.get("new_clients") or 0
        returning_clients = metrics.get("returning_clients") or 0
        total_clients = new_clients + returning_clients
        retention_rate = (returning_clients / total_clients * 100) if total_clients > 0 else 0

        # Получаем данные за предыдущий период для сравнения
        from datetime import datetime, timedelta
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        period_days = (end_dt - start_dt).days

        prev_start = (start_dt - timedelta(days=period_days)).strftime('%Y-%m-%d')
        prev_end = start_date

        # Формируем WHERE условие для предыдущего периода
        prev_where_clause = "transaction_date BETWEEN %s AND %s"
        prev_where_params = [prev_start, prev_end]

        if business_id:
            prev_where_clause = f"business_id = %s AND {prev_where_clause}"
            prev_where_params = [business_id] + prev_where_params
        else:
            prev_where_clause = f"user_id = %s AND {prev_where_clause}"
            prev_where_params = [user_data['user_id']] + prev_where_params

        cursor.execute(f"""
            SELECT
                COUNT(*) as prev_orders,
                SUM(amount) as prev_revenue
            FROM financialtransactions
            WHERE {prev_where_clause}
        """, tuple(prev_where_params))

        raw_prev_metrics = cursor.fetchone()
        prev_metrics = _row_to_dict(cursor, raw_prev_metrics) if raw_prev_metrics else {}

        # Вычисляем рост
        revenue_growth = 0
        orders_growth = 0

        prev_revenue = prev_metrics.get("prev_revenue")
        prev_orders = prev_metrics.get("prev_orders")
        total_revenue = metrics.get("total_revenue")
        total_orders = metrics.get("total_orders")
        average_check = metrics.get("average_check")

        if prev_revenue and prev_revenue > 0:
            revenue_growth = ((total_revenue or 0) - prev_revenue) / prev_revenue * 100

        if prev_orders and prev_orders > 0:
            orders_growth = ((total_orders or 0) - prev_orders) / prev_orders * 100

        db.close()

        return jsonify({
            "success": True,
            "period": {
                "start_date": start_date,
                "end_date": end_date,
                "period_type": period
            },
            "metrics": {
                "total_revenue": float(total_revenue or 0),
                "total_orders": total_orders or 0,
                "average_check": float(average_check or 0),
                "new_clients": new_clients,
                "returning_clients": returning_clients,
                "retention_rate": round(retention_rate, 2)
            },
            "growth": {
                "revenue_growth": round(revenue_growth, 2),
                "orders_growth": round(orders_growth, 2)
            }
        })

    except Exception as e:
        return jsonify({"error": f"Ошибка получения метрик: {str(e)}"}), 500

@finance_bp.route('/api/finance/breakdown', methods=['GET'])
def get_financial_breakdown():
    """Получить разбивку доходов по услугам и мастерам для круговых диаграмм"""
    try:
        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        # Параметры периода
        period = request.args.get('period', 'month')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        db = DatabaseManager()
        cursor = db.conn.cursor()

        # Если даты не указаны, вычисляем период
        if not start_date or not end_date:
            from datetime import datetime, timedelta
            now = datetime.now()

            if period == 'week':
                start_date = (now - timedelta(days=7)).strftime('%Y-%m-%d')
                end_date = now.strftime('%Y-%m-%d')
            elif period == 'month':
                start_date = (now - timedelta(days=30)).strftime('%Y-%m-%d')
                end_date = now.strftime('%Y-%m-%d')
            elif period == 'quarter':
                start_date = (now - timedelta(days=90)).strftime('%Y-%m-%d')
                end_date = now.strftime('%Y-%m-%d')
            elif period == 'year':
                start_date = (now - timedelta(days=365)).strftime('%Y-%m-%d')
                end_date = now.strftime('%Y-%m-%d')

        # Проверяем наличие полей в таблице
        columns = _table_columns(cursor, "financialtransactions")
        has_business_id = 'business_id' in columns
        has_master_id = 'master_id' in columns

        # Получаем business_id из запроса
        current_business_id = request.args.get('business_id')

        # Получаем транзакции за период
        if has_business_id and current_business_id:
            if has_master_id:
                cursor.execute("""
                    SELECT services, amount, master_id
                    FROM financialtransactions
                    WHERE business_id = %s AND transaction_date BETWEEN %s AND %s
                """, (current_business_id, start_date, end_date))
            else:
                cursor.execute("""
                    SELECT services, amount, NULL as master_id
                    FROM financialtransactions
                    WHERE business_id = %s AND transaction_date BETWEEN %s AND %s
                """, (current_business_id, start_date, end_date))
        else:
            if has_master_id:
                cursor.execute("""
                    SELECT services, amount, master_id
                    FROM financialtransactions
                    WHERE user_id = %s AND transaction_date BETWEEN %s AND %s
                """, (user_data['user_id'], start_date, end_date))
            else:
                cursor.execute("""
                    SELECT services, amount, NULL as master_id
                    FROM financialtransactions
                    WHERE user_id = %s AND transaction_date BETWEEN %s AND %s
                """, (user_data['user_id'], start_date, end_date))

        transactions = cursor.fetchall()

        # Агрегируем по услугам
        def _row_val(row, idx, key):
            if isinstance(row, dict):
                return row.get(key)
            if row is None:
                return None
            return row[idx] if len(row) > idx else None

        services_revenue = {}
        for row in transactions:
            services_json = _row_val(row, 0, "services")  # services (JSON)
            amount = float(_row_val(row, 1, "amount") or 0)

            if services_json:
                try:
                    services = json.loads(services_json) if isinstance(services_json, str) else services_json
                    if isinstance(services, list):
                        # Распределяем сумму поровну между услугами
                        service_amount = amount / len(services) if len(services) > 0 else amount
                        for service in services:
                            service_name = service.strip() if isinstance(service, str) else str(service)
                            if service_name:
                                services_revenue[service_name] = services_revenue.get(service_name, 0) + service_amount
                except:
                    pass

        # Агрегируем по мастерам
        masters_revenue = {}
        for row in transactions:
            master_id = _row_val(row, 2, "master_id")
            amount = float(_row_val(row, 1, "amount") or 0)

            if master_id:
                # Проверяем наличие таблицы Masters
                cursor.execute("SELECT to_regclass('public.masters')")
                masters_table_exists = cursor.fetchone()

                if masters_table_exists:
                    cursor.execute("SELECT name FROM masters WHERE id = %s", (master_id,))
                    master_row = cursor.fetchone()
                    master_dict = _row_to_dict(cursor, master_row) if master_row else None
                    master_name = master_dict.get("name") if master_dict else f"Мастер {master_id[:8]}"
                else:
                    master_name = f"Мастер {master_id[:8]}"

                masters_revenue[master_name] = masters_revenue.get(master_name, 0) + amount
            else:
                # Если мастер не указан, добавляем в "Не указан"
                masters_revenue["Не указан"] = masters_revenue.get("Не указан", 0) + amount

        # Преобразуем в массивы для диаграмм
        services_data = [{"name": name, "value": round(value, 2)} for name, value in services_revenue.items()]
        masters_data = [{"name": name, "value": round(value, 2)} for name, value in masters_revenue.items()]

        # Сортируем по убыванию значения
        services_data.sort(key=lambda x: x['value'], reverse=True)
        masters_data.sort(key=lambda x: x['value'], reverse=True)

        db.close()

        return jsonify({
            "success": True,
            "period": {
                "start_date": start_date,
                "end_date": end_date,
                "period_type": period
            },
            "by_services": services_data,
            "by_masters": masters_data
        })

    except Exception as e:
        return jsonify({"error": f"Ошибка получения разбивки: {str(e)}"}), 500

@finance_bp.route('/api/finance/roi', methods=['GET'])
def get_roi_data():
    """Получить данные ROI"""
    try:
        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        db = DatabaseManager()
        cursor = db.conn.cursor()

        # Получаем последние данные ROI
        cursor.execute("""
            SELECT * FROM ROIData
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT 1
        """, (user_data['user_id'],))

        roi_data = cursor.fetchone()

        if not roi_data:
            # Если данных нет, возвращаем базовую структуру
            return jsonify({
                "success": True,
                "roi": {
                    "investment_amount": 0,
                    "returns_amount": 0,
                    "roi_percentage": 0,
                    "period_start": None,
                    "period_end": None
                },
                "message": "Данные ROI не найдены. Добавьте транзакции для расчета."
            })

        db.close()

        return jsonify({
            "success": True,
            "roi": {
                "investment_amount": float(roi_data[2]),
                "returns_amount": float(roi_data[3]),
                "roi_percentage": float(roi_data[4]),
                "period_start": roi_data[5],
                "period_end": roi_data[6]
            }
        })

    except Exception as e:
        return jsonify({"error": f"Ошибка получения ROI: {str(e)}"}), 500

@finance_bp.route('/api/finance/roi', methods=['POST'])
def calculate_roi():
    """Рассчитать и сохранить ROI"""
    try:
        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        data = request.get_json()

        # Валидация
        if 'investment_amount' not in data or 'returns_amount' not in data:
            return jsonify({"error": "Требуются investment_amount и returns_amount"}), 400

        investment = float(data['investment_amount'])
        returns = float(data['returns_amount'])

        if investment <= 0:
            return jsonify({"error": "Сумма инвестиций должна быть больше 0"}), 400

        # Вычисляем ROI
        roi_percentage = ((returns - investment) / investment * 100) if investment > 0 else 0

        # Сохраняем данные
        db = DatabaseManager()
        cursor = db.conn.cursor()

        roi_id = str(uuid.uuid4())
        period_start = data.get('period_start', datetime.now().strftime('%Y-%m-%d'))
        period_end = data.get('period_end', datetime.now().strftime('%Y-%m-%d'))

        cursor.execute("""
            INSERT INTO roidata
            (id, user_id, investment_amount, returns_amount, roi_percentage, period_start, period_end)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                investment_amount = EXCLUDED.investment_amount,
                returns_amount = EXCLUDED.returns_amount,
                roi_percentage = EXCLUDED.roi_percentage,
                period_start = EXCLUDED.period_start,
                period_end = EXCLUDED.period_end
        """, (roi_id, user_data['user_id'], investment, returns, roi_percentage, period_start, period_end))

        db.conn.commit()
        db.close()

        return jsonify({
            "success": True,
            "roi": {
                "investment_amount": investment,
                "returns_amount": returns,
                "roi_percentage": round(roi_percentage, 2)
            },
            "message": "ROI рассчитан и сохранен"
        })

    except Exception as e:
        return jsonify({"error": f"Ошибка расчета ROI: {str(e)}"}), 500
