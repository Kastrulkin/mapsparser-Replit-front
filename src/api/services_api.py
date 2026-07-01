"""
API для управления услугами бизнеса
"""
from flask import Blueprint, request, jsonify
from database_manager import DatabaseManager
from auth_system import verify_session
from core.ai_learning import record_ai_learning_event
from core.helpers import get_business_owner_id
from core.service_keyword_scoring import build_services_quality_audit
from core.service_keyword_enrichment import (
    attach_service_quality_metadata,
    enrich_service_keywords_from_wordstat,
)
from core.service_problem_regeneration import (
    SERVICE_REGENERATION_BATCH_LIMIT,
    SERVICE_REGENERATION_ITEM_DELAY_SECONDS,
    SERVICE_REGENERATION_RATE_LIMIT_COOLDOWN_MINUTES,
    select_problem_services_for_regeneration,
)
from core.service_catalog_compression import build_service_catalog_compression_draft
import json
import os
import sys
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

import requests
from psycopg2.extras import Json

services_bp = Blueprint('services', __name__)
SERVICE_REGENERATION_JOBS = {}
SERVICE_REGENERATION_ATTEMPTS = {}
SERVICE_REGENERATION_LOCK = threading.Lock()
SERVICE_REGENERATION_FINAL_STATUSES = {"completed", "rate_limited", "failed", "cancelled"}


def _cell(row, key_or_index, default=None):
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key_or_index, default)
    try:
        return row[key_or_index]
    except Exception:
        return default


def _resolve_network_scope(cursor, business_id, requested_scope):
    cursor.execute(
        """
        SELECT network_id
        FROM businesses
        WHERE id = %s
        LIMIT 1
        """,
        (business_id,),
    )
    business_row = cursor.fetchone()
    network_id = _cell(business_row, 'network_id', _cell(business_row, 0))
    network_id_value = str(network_id or '').strip()
    if not network_id_value:
        cursor.execute("SELECT id FROM networks WHERE id = %s LIMIT 1", (business_id,))
        network_row = cursor.fetchone()
        network_id_value = str(_cell(network_row, 'id', _cell(network_row, 0, '')) or '').strip()
    aggregate_network = bool(network_id_value) and requested_scope == 'network'
    return aggregate_network, network_id_value or None


def _network_business_where(column_name):
    return f"({column_name} IN (SELECT id FROM businesses WHERE network_id = %s) OR {column_name} = %s)"


def _naive_utc_datetime(value):
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _normalize_learning_text(value):
    return " ".join(str(value or "").strip().lower().replace("ё", "е").split())


def _parse_service_keywords(raw_keywords):
    if not raw_keywords:
        return []
    try:
        parsed_keywords = json.loads(raw_keywords) if isinstance(raw_keywords, str) else raw_keywords
        if isinstance(parsed_keywords, list):
            return parsed_keywords
    except Exception:
        pass
    return [item.strip() for item in str(raw_keywords).split(',') if item.strip()]


def _service_row_to_dict(row, col_names):
    if hasattr(row, 'keys'):
        return dict(row)
    return dict(zip(col_names, row)) if col_names else {}


def _load_active_services_for_business(cursor, business_id):
    cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'userservices'
        ORDER BY ordinal_position
        """
    )
    columns = [_cell(row, 'column_name', _cell(row, 0)) for row in cursor.fetchall()]
    select_fields = ['id', 'category', 'name', 'description', 'keywords', 'price', 'updated_at']
    for optional_field in [
        'optimized_name',
        'optimized_description',
        'source',
        'fallback_used',
        'fallback_reason',
        'guardrail_reasons',
        'pattern_version_ids',
    ]:
        if optional_field in columns:
            select_fields.append(optional_field)

    cursor.execute(
        f"""
        SELECT {', '.join(select_fields)}
        FROM userservices
        WHERE business_id = %s AND (is_active IS TRUE OR is_active IS NULL)
        ORDER BY category NULLS LAST, name NULLS LAST, updated_at DESC NULLS LAST
        """,
        (business_id,),
    )
    rows = cursor.fetchall()
    col_names = [d[0] for d in cursor.description] if cursor.description else select_fields
    services = []
    for row in rows:
        service = _service_row_to_dict(row, col_names)
        service['keywords'] = _parse_service_keywords(service.get('keywords'))
        services.append(service)
    _attach_service_regeneration_metadata(cursor, services)
    return services


def _attach_service_regeneration_metadata(cursor, services):
    service_ids = [str(service.get("id") or "").strip() for service in services if str(service.get("id") or "").strip()]
    if not service_ids:
        return
    placeholders = ", ".join(["%s"] * len(service_ids))
    try:
        cursor.execute(
            f"""
            SELECT DISTINCT ON (service_id)
                service_id,
                status,
                attempt_no,
                issue_labels_json,
                after_issue_labels_json,
                before_optimized_name,
                before_optimized_description,
                after_optimized_name,
                after_optimized_description,
                error,
                created_at,
                updated_at
            FROM serviceregenerationjobitems
            WHERE service_id IN ({placeholders})
            ORDER BY service_id, updated_at DESC, created_at DESC
            """,
            tuple(service_ids),
        )
        rows = cursor.fetchall()
    except Exception:
        return

    latest_by_service_id = {}
    col_names = [d[0] for d in cursor.description] if cursor.description else []
    for row in rows:
        item = _service_row_to_dict(row, col_names)
        latest_by_service_id[str(item.get("service_id") or "")] = item

    for service in services:
        service_id = str(service.get("id") or "")
        latest = latest_by_service_id.get(service_id)
        if not latest:
            continue
        service_updated_at = _naive_utc_datetime(service.get("updated_at"))
        latest_updated_at = _naive_utc_datetime(latest.get("updated_at") or latest.get("created_at"))
        if service_updated_at and latest_updated_at and service_updated_at > latest_updated_at:
            continue
        latest_status = str(latest.get("status") or "")
        service["regeneration_status"] = "manual_review" if latest_status == "manual_review_skipped" else latest_status
        service["regeneration_attempts"] = int(latest.get("attempt_no") or 0)
        service["regeneration_history"] = [_jsonable_job_value(latest)]


def _get_service_regeneration_attempts(cursor, service_ids):
    clean_ids = [str(item or "").strip() for item in service_ids if str(item or "").strip()]
    if not clean_ids:
        return {}
    placeholders = ", ".join(["%s"] * len(clean_ids))
    try:
        cursor.execute(
            f"""
            SELECT service_id, COUNT(*) AS attempt_count
            FROM serviceregenerationjobitems
            WHERE service_id IN ({placeholders})
              AND status IN ('fixed', 'manual_review', 'failed', 'rate_limited')
            GROUP BY service_id
            """,
            tuple(clean_ids),
        )
    except Exception:
        return {}
    attempts = {}
    for row in cursor.fetchall():
        service_id = str(_cell(row, "service_id", _cell(row, 0)) or "")
        attempts[service_id] = int(_cell(row, "attempt_count", _cell(row, 1, 0)) or 0)
    return attempts


def _get_user_business_id(user_data, business_id):
    db = DatabaseManager()
    cursor = db.conn.cursor()
    owner_id = get_business_owner_id(cursor, business_id, include_active_check=True)
    if not owner_id:
        db.close()
        return None, jsonify({"error": "Бизнес не найден"}), 404
    if owner_id != user_data["user_id"] and not user_data.get("is_superadmin"):
        db.close()
        return None, jsonify({"error": "Нет доступа к этому бизнесу"}), 403
    db.close()
    return business_id, None, None


def _job_row_to_public(row, col_names, items=None):
    if not row:
        return None
    job = _service_row_to_dict(row, col_names)
    public_job = {
        "id": str(job.get("id") or ""),
        "status": str(job.get("status") or ""),
        "business_id": str(job.get("business_id") or ""),
        "user_id": str(job.get("user_id") or ""),
        "requested_by": str(job.get("requested_by") or ""),
        "limit": int(job.get("limit_count") or 0),
        "selected": int(job.get("selected_count") or 0),
        "fixed": int(job.get("fixed_count") or 0),
        "failed": int(job.get("failed_count") or 0),
        "manual_review": int(job.get("manual_review_count") or 0),
        "remaining": job.get("remaining_count"),
        "remaining_after_batch": int(job.get("remaining_after_batch") or 0),
        "total_problem_count": int(job.get("total_problem_count") or 0),
        "confirmation_required": bool(job.get("confirmation_required")),
        "cooldown_until": job.get("cooldown_until"),
        "message": str(job.get("message") or ""),
        "summary": job.get("summary_json") or {},
        "created_at": job.get("created_at"),
        "updated_at": job.get("updated_at"),
        "started_at": job.get("started_at"),
        "finished_at": job.get("finished_at"),
    }
    public_job["processed"] = items if isinstance(items, list) else []
    return _jsonable_job_value(public_job)


def _load_regeneration_job(cursor, job_id, include_items=True):
    cursor.execute(
        """
        SELECT *
        FROM serviceregenerationjobs
        WHERE id = %s
        LIMIT 1
        """,
        (job_id,),
    )
    row = cursor.fetchone()
    col_names = [d[0] for d in cursor.description] if cursor.description else []
    if not row:
        return None
    items = []
    if include_items:
        cursor.execute(
            """
            SELECT id, service_id, status, attempt_no, issue_labels_json, after_issue_labels_json,
                   before_optimized_name, before_optimized_description,
                   after_optimized_name, after_optimized_description, error, updated_at
            FROM serviceregenerationjobitems
            WHERE job_id = %s
            ORDER BY created_at ASC
            """,
            (job_id,),
        )
        item_col_names = [d[0] for d in cursor.description] if cursor.description else []
        for item_row in cursor.fetchall():
            items.append(_jsonable_job_value(_service_row_to_dict(item_row, item_col_names)))
    return _job_row_to_public(row, col_names, items)


def _public_job(job_id):
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        return _load_regeneration_job(cursor, job_id, include_items=True)
    finally:
        db.close()


def _jsonable_job_value(value):
    if isinstance(value, dict):
        return {str(key): _jsonable_job_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable_job_value(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable_job_value(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _require_services_user():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None, jsonify({"error": "Требуется авторизация"}), 401
    token = auth_header.split(' ')[1]
    user_data = verify_session(token)
    if not user_data:
        return None, jsonify({"error": "Недействительный токен"}), 401
    return user_data, None, None


def _ensure_business_access(db, cursor, business_id, user_data):
    owner_id = get_business_owner_id(cursor, business_id, include_active_check=True)
    if not owner_id:
        return jsonify({"error": "Бизнес не найден"}), 404
    if owner_id != user_data["user_id"] and not user_data.get("is_superadmin") and not db.is_superadmin(user_data["user_id"]):
        return jsonify({"error": "Нет доступа к этому бизнесу"}), 403
    return None, None


def _load_compression_request(cursor, request_id):
    cursor.execute(
        """
        SELECT id, business_id, user_id, status, before_count, after_count,
               groups_json, diff_json, created_service_ids, archived_service_ids,
               created_at, updated_at, applied_at
        FROM service_catalog_compression_requests
        WHERE id = %s
        """,
        (request_id,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    col_names = [d[0] for d in cursor.description] if cursor.description else []
    item = _service_row_to_dict(row, col_names)
    for field, empty in [
        ("groups_json", []),
        ("diff_json", {}),
        ("created_service_ids", []),
        ("archived_service_ids", []),
    ]:
        if item.get(field) is None:
            item[field] = empty
    return _jsonable_job_value(item)


def _compression_counts(groups):
    apply_groups = [group for group in groups if str(group.get("action") or "") in {"apply", "promotion"}]
    archived_count = sum(len(group.get("source_service_ids") or []) for group in apply_groups)
    created_count = sum(1 for group in apply_groups if str(group.get("action") or "") == "apply")
    return archived_count, created_count


def _update_regeneration_job(job_id, patch):
    db = DatabaseManager()
    cursor = db.conn.cursor()
    fields = []
    params = []
    allowed = {
        "status": "status",
        "message": "message",
        "fixed": "fixed_count",
        "failed": "failed_count",
        "manual_review": "manual_review_count",
        "remaining": "remaining_count",
        "cooldown_until": "cooldown_until",
        "started_at": "started_at",
        "finished_at": "finished_at",
    }
    for key, column in allowed.items():
        if key in patch:
            fields.append(column + " = %s")
            params.append(patch.get(key))
    if not fields:
        db.close()
        return _public_job(job_id)
    fields.append("updated_at = NOW()")
    params.append(job_id)
    cursor.execute(
        f"""
        UPDATE serviceregenerationjobs
        SET {', '.join(fields)}
        WHERE id = %s
        """,
        tuple(params),
    )
    db.conn.commit()
    job = _load_regeneration_job(cursor, job_id, include_items=True)
    db.close()
    return job


def _service_regeneration_api_base():
    return (
        os.getenv("LOCALOS_INTERNAL_API_BASE_URL")
        or os.getenv("LOCALOS_API_BASE_URL")
        or "http://127.0.0.1:8000"
    ).rstrip("/")


def _refresh_regeneration_job_counts(cursor, job_id, remaining=None):
    cursor.execute(
        """
        SELECT
            COUNT(*) FILTER (WHERE status NOT IN ('manual_review_skipped')) AS selected_count,
            COUNT(*) FILTER (WHERE status = 'fixed') AS fixed_count,
            COUNT(*) FILTER (WHERE status = 'failed') AS failed_count,
            COUNT(*) FILTER (WHERE status IN ('manual_review', 'manual_review_skipped')) AS manual_review_count
        FROM serviceregenerationjobitems
        WHERE job_id = %s
        """,
        (job_id,),
    )
    row = cursor.fetchone()
    selected_count = int(_cell(row, "selected_count", _cell(row, 0, 0)) or 0)
    fixed_count = int(_cell(row, "fixed_count", _cell(row, 1, 0)) or 0)
    failed_count = int(_cell(row, "failed_count", _cell(row, 2, 0)) or 0)
    manual_review_count = int(_cell(row, "manual_review_count", _cell(row, 3, 0)) or 0)
    if remaining is None:
        cursor.execute(
            """
            UPDATE serviceregenerationjobs
            SET selected_count = %s,
                fixed_count = %s,
                failed_count = %s,
                manual_review_count = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (selected_count, fixed_count, failed_count, manual_review_count, job_id),
        )
    else:
        cursor.execute(
            """
            UPDATE serviceregenerationjobs
            SET selected_count = %s,
                fixed_count = %s,
                failed_count = %s,
                manual_review_count = %s,
                remaining_count = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (selected_count, fixed_count, failed_count, manual_review_count, remaining, job_id),
        )


def _insert_regeneration_job(
    *,
    cursor,
    user_id,
    business_id,
    requested_by,
    limit,
    audit,
    selection,
    confirmation_required,
):
    job_id = str(uuid.uuid4())
    selected = selection.get("selected") if isinstance(selection.get("selected"), list) else []
    manual_review_items = selection.get("manual_review") if isinstance(selection.get("manual_review"), list) else []
    summary = audit.get("summary") if isinstance(audit.get("summary"), dict) else {}
    status = "awaiting_confirmation" if confirmation_required and selected else "queued" if selected else "completed"
    message = "Подтвердите запуск: до " + str(limit) + " услуг" if status == "awaiting_confirmation" else "Нет проблемных услуг для повторной генерации" if not selected else "Взял " + str(len(selected)) + " проблемных услуг"
    cursor.execute(
        """
        INSERT INTO serviceregenerationjobs (
            id, user_id, business_id, status, requested_by, limit_count,
            total_problem_count, selected_count, manual_review_count,
            remaining_count, remaining_after_batch, confirmation_required,
            message, summary_json, created_at, updated_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s, NOW(), NOW()
        )
        """,
        (
            job_id,
            user_id,
            business_id,
            status,
            requested_by,
            limit,
            int(summary.get("needs_review") or 0) + len(manual_review_items),
            len(selected),
            len(manual_review_items),
            int(summary.get("needs_review") or 0),
            int(selection.get("remaining_after_batch") or 0),
            bool(confirmation_required and selected),
            message,
            Json(summary),
        ),
    )
    for item in selected:
        service = item.get("service") if isinstance(item, dict) else {}
        quality = item.get("quality") if isinstance(item, dict) else {}
        cursor.execute(
            """
            INSERT INTO serviceregenerationjobitems (
                id, job_id, service_id, status, attempt_no,
                issue_codes_json, issue_labels_json, keyword_score_json,
                instructions, before_optimized_name, before_optimized_description,
                created_at, updated_at
            ) VALUES (
                %s, %s, %s, 'queued', %s,
                %s, %s, %s,
                %s, %s, %s,
                NOW(), NOW()
            )
            """,
            (
                str(uuid.uuid4()),
                job_id,
                str(service.get("id") or ""),
                int(item.get("attempts") or 0) + 1,
                Json(quality.get("issue_codes") or []),
                Json(quality.get("issue_labels") or []),
                Json(quality.get("keyword_score") or {}),
                item.get("instructions") or "",
                str(service.get("optimized_name") or ""),
                str(service.get("optimized_description") or ""),
            ),
        )
    for item in manual_review_items:
        service = item.get("service") if isinstance(item, dict) else {}
        quality = item.get("quality") if isinstance(item, dict) else {}
        cursor.execute(
            """
            INSERT INTO serviceregenerationjobitems (
                id, job_id, service_id, status, attempt_no,
                issue_codes_json, issue_labels_json, keyword_score_json,
                instructions, before_optimized_name, before_optimized_description,
                after_issue_labels_json, error, created_at, updated_at
            ) VALUES (
                %s, %s, %s, 'manual_review_skipped', %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, NOW(), NOW()
            )
            """,
            (
                str(uuid.uuid4()),
                job_id,
                str(service.get("id") or ""),
                int(item.get("attempts") or 0),
                Json(quality.get("issue_codes") or []),
                Json(quality.get("issue_labels") or []),
                Json(quality.get("keyword_score") or {}),
                item.get("instructions") or "",
                str(service.get("optimized_name") or ""),
                str(service.get("optimized_description") or ""),
                Json(["нужна ручная проверка после повторной плохой генерации"]),
                "attempt_limit_reached",
            ),
        )
    return job_id


def _start_persistent_regeneration_job(job_id, token):
    db = DatabaseManager()
    cursor = db.conn.cursor()
    cursor.execute(
        """
        UPDATE serviceregenerationjobs
        SET status = 'queued',
            confirmation_required = FALSE,
            message = 'Job поставлен в очередь',
            updated_at = NOW()
        WHERE id = %s AND status = 'awaiting_confirmation'
        """,
        (job_id,),
    )
    db.conn.commit()
    db.close()
    thread = threading.Thread(
        target=_run_service_regeneration_job,
        args=(job_id, token),
        daemon=True,
    )
    thread.start()


def _apply_regenerated_service(service, optimized):
    db = DatabaseManager()
    cursor = db.conn.cursor()
    optimized_name = str(optimized.get("optimized_name") or optimized.get("optimizedName") or "").strip()
    optimized_description = str(optimized.get("seo_description") or optimized.get("seoDescription") or "").strip()
    fallback_reason = str(optimized.get("fallback_reason") or "").strip()
    guardrail_reasons = optimized.get("guardrail_reasons") if isinstance(optimized.get("guardrail_reasons"), list) else []
    pattern_version_ids = optimized.get("pattern_version_ids") if isinstance(optimized.get("pattern_version_ids"), list) else []
    cursor.execute(
        """
        UPDATE userservices
        SET optimized_name = %s,
            optimized_description = %s,
            fallback_used = %s,
            fallback_reason = %s,
            guardrail_reasons = %s,
            pattern_version_ids = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (
            optimized_name,
            optimized_description,
            bool(optimized.get("fallback_used")),
            fallback_reason,
            Json(guardrail_reasons),
            Json(pattern_version_ids),
            service.get("id"),
        ),
    )
    db.conn.commit()
    db.close()
    return {
        "optimized_name": optimized_name,
        "optimized_description": optimized_description,
        "fallback_used": bool(optimized.get("fallback_used")),
        "fallback_reason": fallback_reason,
        "guardrail_reasons": guardrail_reasons,
        "pattern_version_ids": pattern_version_ids,
    }


def _run_service_regeneration_job(job_id, token):
    db = DatabaseManager()
    cursor = db.conn.cursor()
    cursor.execute(
        """
        SELECT *
        FROM serviceregenerationjobs
        WHERE id = %s
        LIMIT 1
        """,
        (job_id,),
    )
    job_row = cursor.fetchone()
    if not job_row:
        db.close()
        return
    job_cols = [d[0] for d in cursor.description] if cursor.description else []
    job = _service_row_to_dict(job_row, job_cols)
    business_id = str(job.get("business_id") or "").strip()
    user_id = str(job.get("user_id") or "").strip()
    cooldown_until = job.get("cooldown_until")
    now_value = datetime.now(timezone.utc)
    if cooldown_until and cooldown_until > now_value:
        db.close()
        return

    cursor.execute(
        """
        UPDATE serviceregenerationjobs
        SET status = 'running',
            started_at = COALESCE(started_at, NOW()),
            message = 'Перегенерируем проблемные услуги',
            updated_at = NOW()
        WHERE id = %s
        """,
        (job_id,),
    )
    db.conn.commit()

    cursor.execute(
        """
        SELECT i.*, s.category, s.name, s.description, s.keywords, s.price
        FROM serviceregenerationjobitems i
        JOIN userservices s ON s.id = i.service_id
        WHERE i.job_id = %s AND i.status = 'queued'
        ORDER BY i.created_at ASC
        """,
        (job_id,),
    )
    item_rows = cursor.fetchall()
    item_cols = [d[0] for d in cursor.description] if cursor.description else []
    items = [_service_row_to_dict(row, item_cols) for row in item_rows]
    db.close()

    record_ai_learning_event(
        capability="services.regenerate_problematic",
        event_type="job_started",
        intent="operations",
        user_id=user_id,
        business_id=business_id,
        metadata={"job_id": job_id, "selected": len(items)},
    )

    for item in items:
        item_id = str(item.get("id") or "").strip()
        service_id = str(item.get("service_id") or "").strip()
        if not item_id or not service_id:
            continue
        db = DatabaseManager()
        cursor = db.conn.cursor()
        cursor.execute(
            """
            UPDATE serviceregenerationjobitems
            SET status = 'running', updated_at = NOW()
            WHERE id = %s
            """,
            (item_id,),
        )
        db.conn.commit()
        db.close()

        before_text = " | ".join([
            str(item.get("before_optimized_name") or ""),
            str(item.get("before_optimized_description") or ""),
        ]).strip()
        try:
            response = requests.post(
                _service_regeneration_api_base() + "/api/services/optimize",
                headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
                json={
                    "text": str(item.get("name") or "") + ("\n" + str(item.get("description") or "") if item.get("description") else ""),
                    "business_id": business_id,
                    "service_category": item.get("category") or "",
                    "instructions": item.get("instructions") or "",
                },
                timeout=90,
            )
            if response.status_code == 429:
                cooldown = datetime.now(timezone.utc) + timedelta(minutes=SERVICE_REGENERATION_RATE_LIMIT_COOLDOWN_MINUTES)
                db = DatabaseManager()
                cursor = db.conn.cursor()
                cursor.execute(
                    """
                    UPDATE serviceregenerationjobitems
                    SET status = 'rate_limited', error = 'rate_limit', updated_at = NOW()
                    WHERE id = %s
                    """,
                    (item_id,),
                )
                cursor.execute(
                    """
                    UPDATE serviceregenerationjobs
                    SET status = 'rate_limited',
                        cooldown_until = %s,
                        message = 'Остановлено из-за лимита GigaChat',
                        updated_at = NOW(),
                        finished_at = NOW()
                    WHERE id = %s
                    """,
                    (cooldown, job_id),
                )
                _refresh_regeneration_job_counts(cursor, job_id)
                db.conn.commit()
                db.close()
                break
            data = response.json()
            services = data.get("result", {}).get("services", []) if isinstance(data, dict) else []
            optimized = services[0] if isinstance(services, list) and services else {}
            if not response.ok or not data.get("success") or not isinstance(optimized, dict):
                db = DatabaseManager()
                cursor = db.conn.cursor()
                cursor.execute(
                    """
                    UPDATE serviceregenerationjobitems
                    SET status = 'failed', error = %s, updated_at = NOW()
                    WHERE id = %s
                    """,
                    (data.get("error") if isinstance(data, dict) else "bad_response", item_id),
                )
                _refresh_regeneration_job_counts(cursor, job_id)
                db.conn.commit()
                db.close()
                continue

            next_data = _apply_regenerated_service({"id": service_id}, optimized)
            after_service = {
                "id": service_id,
                "name": item.get("name"),
                "description": item.get("description"),
                "keywords": _parse_service_keywords(item.get("keywords")),
            }
            after_service.update(next_data)
            after_audit = build_services_quality_audit([after_service])
            after_items = after_audit.get("items") if isinstance(after_audit, dict) else []
            after_quality = after_items[0] if isinstance(after_items, list) and after_items else {}
            next_status = "manual_review" if after_quality.get("needs_review") else "fixed"
            db = DatabaseManager()
            cursor = db.conn.cursor()
            cursor.execute(
                """
                UPDATE serviceregenerationjobitems
                SET status = %s,
                    after_optimized_name = %s,
                    after_optimized_description = %s,
                    after_issue_labels_json = %s,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (
                    next_status,
                    next_data.get("optimized_name") or "",
                    next_data.get("optimized_description") or "",
                    Json(after_quality.get("issue_labels") or []),
                    item_id,
                ),
            )
            _refresh_regeneration_job_counts(cursor, job_id)
            db.conn.commit()
            db.close()
            if after_quality.get("needs_review"):
                result_status = "manual_review"
            else:
                result_status = "fixed"

            record_ai_learning_event(
                capability="services.regenerate_problematic",
                event_type="service_regenerated",
                intent="operations",
                user_id=user_id,
                business_id=business_id,
                draft_text=before_text or None,
                final_text=" | ".join([next_data.get("optimized_name") or "", next_data.get("optimized_description") or ""]).strip() or None,
                metadata={
                    "job_id": job_id,
                    "service_id": service_id,
                    "before_issues": item.get("issue_labels_json") or [],
                    "after_issues": after_quality.get("issue_labels") or [],
                    "result": result_status,
                },
            )
            time.sleep(SERVICE_REGENERATION_ITEM_DELAY_SECONDS)
        except Exception:
            error = sys.exc_info()[1]
            db = DatabaseManager()
            cursor = db.conn.cursor()
            cursor.execute(
                """
                UPDATE serviceregenerationjobitems
                SET status = 'failed', error = %s, updated_at = NOW()
                WHERE id = %s
                """,
                (str(error), item_id),
            )
            _refresh_regeneration_job_counts(cursor, job_id)
            db.conn.commit()
            db.close()

    try:
        db = DatabaseManager()
        cursor = db.conn.cursor()
        services = _load_active_services_for_business(cursor, business_id)
        db.close()
        final_audit = build_services_quality_audit(services)
        remaining = int((final_audit.get("summary") or {}).get("needs_review") or 0)
    except Exception:
        remaining = None

    db = DatabaseManager()
    cursor = db.conn.cursor()
    cursor.execute("SELECT status FROM serviceregenerationjobs WHERE id = %s", (job_id,))
    status_row = cursor.fetchone()
    current_status = str(_cell(status_row, "status", _cell(status_row, 0, "")) or "")
    if current_status != "rate_limited":
        _refresh_regeneration_job_counts(cursor, job_id, remaining=remaining)
        cursor.execute(
            """
            SELECT fixed_count, failed_count, manual_review_count
            FROM serviceregenerationjobs
            WHERE id = %s
            """,
            (job_id,),
        )
        counts_row = cursor.fetchone()
        fixed_count = int(_cell(counts_row, "fixed_count", _cell(counts_row, 0, 0)) or 0)
        failed_count = int(_cell(counts_row, "failed_count", _cell(counts_row, 1, 0)) or 0)
        manual_review_count = int(_cell(counts_row, "manual_review_count", _cell(counts_row, 2, 0)) or 0)
        cursor.execute(
            """
            UPDATE serviceregenerationjobs
            SET status = 'completed',
                message = %s,
                finished_at = NOW(),
                updated_at = NOW()
            WHERE id = %s
            """,
            (
                "Исправлено: " + str(fixed_count) + ". Осталось: " + str(remaining if remaining is not None else "неизвестно") + ".",
                job_id,
            ),
        )
        db.conn.commit()
    else:
        cursor.execute(
            """
            SELECT fixed_count, failed_count, manual_review_count, remaining_count
            FROM serviceregenerationjobs
            WHERE id = %s
            """,
            (job_id,),
        )
        counts_row = cursor.fetchone()
        fixed_count = int(_cell(counts_row, "fixed_count", _cell(counts_row, 0, 0)) or 0)
        failed_count = int(_cell(counts_row, "failed_count", _cell(counts_row, 1, 0)) or 0)
        manual_review_count = int(_cell(counts_row, "manual_review_count", _cell(counts_row, 2, 0)) or 0)
        remaining = _cell(counts_row, "remaining_count", _cell(counts_row, 3))
    db.close()
    record_ai_learning_event(
        capability="services.regenerate_problematic",
        event_type="job_finished",
        intent="operations",
        user_id=user_id,
        business_id=business_id,
        outcome=current_status if current_status == "rate_limited" else "completed",
        metadata={"job_id": job_id, "fixed": fixed_count, "failed": failed_count, "manual_review": manual_review_count, "remaining": remaining},
    )


def _record_service_optimization_learning(
    *,
    user_id,
    business_id,
    service_id,
    previous_data,
    next_data,
    conn,
):
    prev_name = str(previous_data.get("name") or "")
    prev_description = str(previous_data.get("description") or "")
    prev_optimized_name = str(previous_data.get("optimized_name") or "")
    prev_optimized_description = str(previous_data.get("optimized_description") or "")
    next_name = str(next_data.get("name") or "")
    next_description = str(next_data.get("description") or "")
    next_optimized_name = str(next_data.get("optimized_name") or "")
    next_optimized_description = str(next_data.get("optimized_description") or "")

    if prev_optimized_name and not next_optimized_name:
        accepted_name = _normalize_learning_text(next_name) != _normalize_learning_text(prev_name)
        if accepted_name:
            record_ai_learning_event(
                capability="services.optimize",
                event_type="accepted",
                intent="operations",
                user_id=user_id,
                business_id=business_id,
                accepted=True,
                edited_before_accept=_normalize_learning_text(next_name) != _normalize_learning_text(prev_optimized_name),
                prompt_key="service_optimization",
                prompt_version="v1",
                draft_text=prev_optimized_name,
                final_text=next_name,
                metadata={"field": "name", "service_id": service_id, "source": "services_api"},
                conn=conn,
            )
        else:
            record_ai_learning_event(
                capability="services.optimize",
                event_type="rejected",
                intent="operations",
                user_id=user_id,
                business_id=business_id,
                rejected=True,
                prompt_key="service_optimization",
                prompt_version="v1",
                draft_text=prev_optimized_name,
                final_text=prev_name,
                metadata={"field": "name", "service_id": service_id, "source": "services_api"},
                conn=conn,
            )

    if prev_optimized_description and not next_optimized_description:
        accepted_description = _normalize_learning_text(next_description) != _normalize_learning_text(prev_description)
        if accepted_description:
            record_ai_learning_event(
                capability="services.optimize",
                event_type="accepted",
                intent="operations",
                user_id=user_id,
                business_id=business_id,
                accepted=True,
                edited_before_accept=_normalize_learning_text(next_description) != _normalize_learning_text(prev_optimized_description),
                prompt_key="service_optimization",
                prompt_version="v1",
                draft_text=prev_optimized_description,
                final_text=next_description,
                metadata={"field": "description", "service_id": service_id, "source": "services_api"},
                conn=conn,
            )
        else:
            record_ai_learning_event(
                capability="services.optimize",
                event_type="rejected",
                intent="operations",
                user_id=user_id,
                business_id=business_id,
                rejected=True,
                prompt_key="service_optimization",
                prompt_version="v1",
                draft_text=prev_optimized_description,
                final_text=prev_description,
                metadata={"field": "description", "service_id": service_id, "source": "services_api"},
                conn=conn,
            )

@services_bp.route('/api/services/add', methods=['POST', 'OPTIONS'])
def add_service():
    """Добавить услугу"""
    if request.method == 'OPTIONS':
        return ('', 204)
    
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "Нет данных"}), 400
        
        business_id = data.get('business_id')
        if not business_id:
            return jsonify({"error": "business_id обязателен"}), 400
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Проверяем доступ
        owner_id = get_business_owner_id(cursor, business_id)
        if not owner_id:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404
        
        if owner_id != user_data["user_id"] and not db.is_superadmin(user_data["user_id"]):
            db.close()
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403
        
        # Добавляем услугу
        import uuid
        service_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO userservices (id, user_id, business_id, category, name, description, keywords, price, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        """, (
            service_id,
            user_data["user_id"],
            business_id,
            data.get('category', ''),
            data.get('name', ''),
            data.get('description', ''),
            data.get('keywords', ''),
            data.get('price', 0)
        ))
        
        db.conn.commit()
        db.close()
        
        return jsonify({"success": True, "service_id": service_id})
    
    except Exception as e:
        print(f"❌ Ошибка добавления услуги: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@services_bp.route('/api/services/list', methods=['GET', 'OPTIONS'])
def get_services():
    """Получить список услуг"""
    if request.method == 'OPTIONS':
        return ('', 204)
    
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        user_id = user_data['user_id']

        # Получаем business_id из query параметров
        business_id = request.args.get('business_id')
        requested_scope = str(request.args.get('scope') or '').strip().lower()
        source_filter_raw = str(request.args.get('source') or '').strip().lower()

        # PostgreSQL: список колонок таблицы userservices
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'userservices'
            ORDER BY ordinal_position
        """)
        columns = [row[0] if isinstance(row, (list, tuple)) else row.get('column_name') for row in cursor.fetchall()]
        has_optimized_desc = 'optimized_description' in columns
        has_optimized_name = 'optimized_name' in columns
        has_price_from = 'price_from' in columns

        select_fields = ['id', 'category', 'name', 'description', 'keywords', 'price', 'created_at', 'updated_at']
        if 'source' in columns:
            select_fields.append('source')
        if has_optimized_desc:
            select_fields.insert(select_fields.index('description') + 1, 'optimized_description')
        if has_optimized_name:
            select_fields.insert(select_fields.index('name') + 1, 'optimized_name')
        if has_price_from:
            select_fields.append('price_from')
            select_fields.append('price_to')
        for optional_field in ['fallback_used', 'fallback_reason', 'guardrail_reasons', 'pattern_version_ids']:
            if optional_field in columns:
                select_fields.append(optional_field)

        def _service_source_condition(alias: str = ''):
            prefix = f"{alias}." if alias else ""
            if source_filter_raw in ('2gis', 'two_gis'):
                return f"LOWER(COALESCE({prefix}source, '')) IN ('2gis', 'apify_2gis', 'two_gis')", []
            if source_filter_raw in ('yandex', 'yandex_maps', 'yandex_business'):
                return f"LOWER(COALESCE({prefix}source, '')) IN ('yandex_maps', 'yandex_business', 'apify_yandex')", []
            if source_filter_raw in ('google', 'google_maps', 'google_business'):
                return f"LOWER(COALESCE({prefix}source, '')) IN ('google_maps', 'google_business', 'apify_google')", []
            if source_filter_raw in ('apple', 'apple_maps', 'apple_business'):
                return f"LOWER(COALESCE({prefix}source, '')) IN ('apple_maps', 'apple_business', 'apify_apple')", []
            return None, []

        aggregate_network = False
        network_id = None

        # Если передан business_id — фильтруем по нему и is_active, иначе по user_id
        if business_id:
            owner_id = get_business_owner_id(cursor, business_id, include_active_check=True)
            if not owner_id:
                db.close()
                return jsonify({"error": "Бизнес не найден"}), 404
            if owner_id != user_id and not user_data.get('is_superadmin'):
                db.close()
                return jsonify({"error": "Нет доступа к этому бизнесу"}), 403

            aggregate_network, network_id = _resolve_network_scope(cursor, business_id, requested_scope)

            order_by = "ORDER BY category NULLS LAST, name NULLS LAST"
            if has_price_from:
                order_by += ", price_from NULLS LAST"
            order_by += ", updated_at DESC NULLS LAST"

            if aggregate_network:
                where_parts = [
                    _network_business_where("business_id"),
                    "(is_active IS TRUE OR is_active IS NULL)",
                ]
                params = [network_id, network_id]
            else:
                where_parts = [
                    "business_id = %s",
                    "(is_active IS TRUE OR is_active IS NULL)",
                ]
                params = [business_id]
            source_condition, source_params = _service_source_condition()
            if source_condition:
                where_parts.append(source_condition)
                params.extend(source_params)

            select_sql = (
                f"SELECT {', '.join(select_fields)} FROM userservices "
                f"WHERE {' AND '.join(where_parts)} "
                f"{order_by}"
            )
            cursor.execute(select_sql, tuple(params))
        else:
            where_parts = ["user_id = %s"]
            params = [user_id]
            source_condition, source_params = _service_source_condition()
            if source_condition:
                where_parts.append(source_condition)
                params.extend(source_params)

            select_sql = (
                f"SELECT {', '.join(select_fields)} FROM userservices "
                f"WHERE {' AND '.join(where_parts)} ORDER BY created_at DESC NULLS LAST"
            )
            cursor.execute(select_sql, tuple(params))

        services_rows = cursor.fetchall()
        col_names = [d[0] for d in cursor.description] if cursor.description else select_fields
        external_services = []

        if business_id:
            try:
                cursor.execute("SELECT to_regclass('public.externalbusinessservices') AS table_ref")
                table_ref_row = cursor.fetchone()
                table_ref = _cell(table_ref_row, 'table_ref', _cell(table_ref_row, 0))
                if table_ref:
                    cursor.execute(
                        """
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema = 'public' AND table_name = 'externalbusinessservices'
                        ORDER BY ordinal_position
                        """
                    )
                    external_columns = [
                        _cell(column_row, 'column_name', _cell(column_row, 0))
                        for column_row in cursor.fetchall()
                    ]
                    external_has_updated_at = 'updated_at' in external_columns
                    external_has_source = 'source' in external_columns
                    external_has_keywords = 'keywords' in external_columns

                    external_select_fields = ['id', 'business_id', 'category', 'name', 'description', 'price', 'created_at']
                    if external_has_updated_at:
                        external_select_fields.append('updated_at')
                    if external_has_source:
                        external_select_fields.append('source')
                    if external_has_keywords:
                        external_select_fields.append('keywords')

                    if aggregate_network:
                        external_where_parts = [
                            _network_business_where("business_id"),
                        ]
                        external_params = [network_id, network_id]
                    else:
                        external_where_parts = ["business_id = %s"]
                        external_params = [business_id]

                    source_condition, source_params = _service_source_condition()
                    if source_condition:
                        external_where_parts.append(source_condition)
                        external_params.extend(source_params)

                    external_query = (
                        f"SELECT {', '.join(external_select_fields)} "
                        f"FROM externalbusinessservices "
                        f"WHERE {' AND '.join(external_where_parts)} "
                        f"ORDER BY category NULLS LAST, name NULLS LAST, created_at DESC NULLS LAST"
                    )
                    cursor.execute(external_query, tuple(external_params))
                    external_rows = cursor.fetchall()
                    external_col_names = [d[0] for d in cursor.description] if cursor.description else external_select_fields

                    for service_row in external_rows:
                        if hasattr(service_row, 'keys'):
                            service_dict = dict(service_row)
                        else:
                            service_dict = dict(zip(external_col_names, service_row)) if external_col_names else {}

                        if service_dict.get('description') is None:
                            service_dict['description'] = ''
                        if service_dict.get('category') is None:
                            service_dict['category'] = ''
                        if service_dict.get('name') is None:
                            service_dict['name'] = ''
                        if service_dict.get('price') is None:
                            service_dict['price'] = ''

                        service_dict['keywords'] = _parse_service_keywords(service_dict.get('keywords'))
                        service_dict['source'] = service_dict.get('source') or 'external'
                        service_dict['is_external'] = True
                        external_services.append(service_dict)
            except Exception:
                external_services = []

        last_parse_date = None
        no_new_services_found = False
        if business_id:
            try:
                if aggregate_network:
                    parse_where = [
                        _network_business_where("business_id"),
                        "status IN ('completed', 'done')",
                        "task_type = 'parse_card'",
                    ]
                    parse_params = [network_id, network_id]
                else:
                    parse_where = [
                        "business_id = %s",
                        "status IN ('completed', 'done')",
                        "task_type = 'parse_card'",
                    ]
                    parse_params = [business_id]
                if source_filter_raw in ('2gis', 'two_gis'):
                    parse_where.append("source IN ('2gis', 'apify_2gis', 'two_gis')")
                elif source_filter_raw in ('yandex', 'yandex_maps', 'yandex_business'):
                    parse_where.append("source IN ('yandex_maps', 'yandex_business', 'apify_yandex')")
                elif source_filter_raw in ('google', 'google_maps', 'google_business'):
                    parse_where.append("source IN ('google_maps', 'google_business', 'apify_google')")
                elif source_filter_raw in ('apple', 'apple_maps', 'apple_business'):
                    parse_where.append("source IN ('apple_maps', 'apple_business', 'apify_apple')")
                cursor.execute(
                    f"""
                    SELECT MAX(COALESCE(updated_at, created_at)) AS ts
                    FROM parsequeue
                    WHERE {' AND '.join(parse_where)}
                    """,
                    tuple(parse_params),
                )
                row = cursor.fetchone()
                if isinstance(row, dict):
                    last_parse_date = row.get('ts')
                elif row:
                    last_parse_date = row[0]
            except Exception:
                last_parse_date = None

        db.close()

        services = []
        seen_network_services = set()
        for service in services_rows:
            if hasattr(service, 'keys'):
                service_dict = dict(service)
            else:
                service_dict = dict(zip(col_names, service)) if col_names else {}
            # Нормализация NULL
            for k in list(service_dict.keys()):
                if service_dict[k] is None and k in ('description', 'category', 'name', 'price', 'keywords'):
                    service_dict[k] = '' if k != 'keywords' else []
            service_dict['keywords'] = _parse_service_keywords(service_dict.get('keywords'))
            if aggregate_network:
                service_key = (
                    str(service_dict.get('category') or '').strip().lower(),
                    str(service_dict.get('name') or '').strip().lower(),
                    str(service_dict.get('description') or '').strip().lower(),
                    str(service_dict.get('price') or '').strip().lower(),
                )
                if service_key in seen_network_services:
                    continue
                seen_network_services.add(service_key)
            services.append(service_dict)

        try:
            metadata_db = DatabaseManager()
            metadata_cursor = metadata_db.conn.cursor()
            _attach_service_regeneration_metadata(metadata_cursor, services)
            metadata_db.close()
        except Exception:
            pass

        attach_service_quality_metadata(services)
        attach_service_quality_metadata(external_services)

        return jsonify({
            "success": True,
            "services": services,
            "external_services": external_services,
            "last_parse_date": last_parse_date,
            "no_new_services_found": no_new_services_found,
            "scope": "network" if aggregate_network else "business",
            "network_id": network_id if aggregate_network else None,
        })
    
    except Exception as e:
        print(f"❌ Ошибка получения услуг: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@services_bp.route('/api/services/seo-audit', methods=['GET', 'OPTIONS'])
def get_services_seo_audit():
    """Аудит качества SEO-предложений по услугам."""
    if request.method == 'OPTIONS':
        return ('', 204)

    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        business_id = str(request.args.get('business_id') or '').strip()
        if not business_id:
            return jsonify({"error": "business_id обязателен"}), 400

        db = DatabaseManager()
        cursor = db.conn.cursor()
        owner_id = get_business_owner_id(cursor, business_id, include_active_check=True)
        if not owner_id:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404
        if owner_id != user_data["user_id"] and not user_data.get("is_superadmin"):
            db.close()
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403

        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'userservices'
            ORDER BY ordinal_position
            """
        )
        columns = [_cell(row, 'column_name', _cell(row, 0)) for row in cursor.fetchall()]
        select_fields = ['id', 'category', 'name', 'description', 'keywords', 'price', 'updated_at']
        if 'optimized_name' in columns:
            select_fields.append('optimized_name')
        if 'optimized_description' in columns:
            select_fields.append('optimized_description')
        if 'source' in columns:
            select_fields.append('source')
        for optional_field in ['fallback_used', 'fallback_reason', 'guardrail_reasons', 'pattern_version_ids']:
            if optional_field in columns:
                select_fields.append(optional_field)

        cursor.execute(
            f"""
            SELECT {', '.join(select_fields)}
            FROM userservices
            WHERE business_id = %s AND (is_active IS TRUE OR is_active IS NULL)
            ORDER BY category NULLS LAST, name NULLS LAST, updated_at DESC NULLS LAST
            """,
            (business_id,),
        )
        rows = cursor.fetchall()
        col_names = [d[0] for d in cursor.description] if cursor.description else select_fields
        db.close()

        services = []
        for row in rows:
            if hasattr(row, 'keys'):
                service = dict(row)
            else:
                service = dict(zip(col_names, row)) if col_names else {}
            service['keywords'] = _parse_service_keywords(service.get('keywords'))
            services.append(service)

        try:
            metadata_db = DatabaseManager()
            metadata_cursor = metadata_db.conn.cursor()
            _attach_service_regeneration_metadata(metadata_cursor, services)
            metadata_db.close()
        except Exception:
            pass

        audit = build_services_quality_audit(services)
        return jsonify({
            "success": True,
            "business_id": business_id,
            **audit,
        })

    except Exception:
        import sys
        error = sys.exc_info()[1]
        print(f"❌ Ошибка SEO-аудита услуг: {error}", flush=True)
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(error)}), 500


@services_bp.route('/api/services/enrich-keywords', methods=['POST', 'OPTIONS'])
def enrich_service_keywords():
    """Подобрать безопасные Wordstat-запросы для одной услуги и сохранить их."""
    if request.method == 'OPTIONS':
        return ('', 204)

    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        data = request.get_json(silent=True) if request.is_json else {}
        if not isinstance(data, dict):
            data = {}
        service_id = str(data.get("service_id") or "").strip()
        if not service_id:
            return jsonify({"error": "service_id обязателен"}), 400

        db = DatabaseManager()
        cursor = db.conn.cursor()
        cursor.execute(
            """
            SELECT id, user_id, business_id, category, name, description, keywords, price
            FROM userservices
            WHERE id = %s AND (is_active IS TRUE OR is_active IS NULL)
            LIMIT 1
            """,
            (service_id,),
        )
        row = cursor.fetchone()
        if not row:
            db.close()
            return jsonify({"error": "Услуга не найдена"}), 404
        service = _service_row_to_dict(row, [d[0] for d in cursor.description])
        service_user_id = str(service.get("user_id") or "")
        if service_user_id != str(user_data["user_id"]) and not user_data.get("is_superadmin"):
            db.close()
            return jsonify({"error": "Нет доступа к этой услуге"}), 403

        result = enrich_service_keywords_from_wordstat(cursor, service, limit=int(data.get("limit") or 8))
        saved = False
        if result.get("status") == "auto_found" and result.get("keywords"):
            cursor.execute(
                """
                UPDATE userservices
                SET keywords = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (json.dumps(result.get("keywords") or [], ensure_ascii=False), service_id),
            )
            db.conn.commit()
            saved = True
        db.close()
        return jsonify({
            "success": True,
            "service_id": service_id,
            "saved": saved,
            "enrichment": result,
        })
    except Exception:
        import sys
        error = sys.exc_info()[1]
        print(f"❌ Ошибка enrich_service_keywords: {error}", flush=True)
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(error)}), 500


@services_bp.route('/api/services/enrich-problematic-keywords', methods=['POST', 'OPTIONS'])
def enrich_problematic_service_keywords():
    """Подобрать безопасные Wordstat-запросы для услуг без ключей, без автогенерации текстов."""
    if request.method == 'OPTIONS':
        return ('', 204)

    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        data = request.get_json(silent=True) if request.is_json else {}
        if not isinstance(data, dict):
            data = {}
        business_id = str(data.get("business_id") or "").strip()
        if not business_id:
            return jsonify({"error": "business_id обязателен"}), 400
        _business_id, error_response, error_status = _get_user_business_id(user_data, business_id)
        if error_response is not None:
            return error_response, error_status

        limit = max(1, min(int(data.get("limit") or 10), 10))
        db = DatabaseManager()
        cursor = db.conn.cursor()
        services = _load_active_services_for_business(cursor, business_id)
        selected = []
        for service in services:
            if len(selected) >= limit:
                break
            if _parse_service_keywords(service.get("keywords")):
                continue
            selected.append(service)

        items = []
        saved_count = 0
        for service in selected:
            result = enrich_service_keywords_from_wordstat(cursor, service, limit=8)
            saved = False
            if result.get("status") == "auto_found" and result.get("keywords"):
                cursor.execute(
                    """
                    UPDATE userservices
                    SET keywords = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (
                        json.dumps(result.get("keywords") or [], ensure_ascii=False),
                        str(service.get("id") or ""),
                    ),
                )
                saved = True
                saved_count += 1
            items.append({
                "service_id": str(service.get("id") or ""),
                "name": str(service.get("name") or ""),
                "saved": saved,
                "enrichment": result,
            })
        if saved_count > 0:
            db.conn.commit()
        db.close()
        return jsonify({
            "success": True,
            "business_id": business_id,
            "selected": len(selected),
            "saved": saved_count,
            "items": items,
        })
    except Exception:
        import sys
        error = sys.exc_info()[1]
        print(f"❌ Ошибка enrich_problematic_service_keywords: {error}", flush=True)
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(error)}), 500


@services_bp.route('/api/services/regenerate-problematic', methods=['POST', 'OPTIONS'])
def regenerate_problematic_services():
    """Подготовить или запустить job повторной генерации проблемных SEO-предложений."""
    if request.method == 'OPTIONS':
        return ('', 204)

    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        data = request.get_json(silent=True) if request.is_json else {}
        if not isinstance(data, dict):
            data = {}

        business_id = str(data.get('business_id') or request.args.get('business_id') or '').strip()
        if not business_id:
            return jsonify({"error": "business_id обязателен"}), 400

        _business_id, error_response, error_status = _get_user_business_id(user_data, business_id)
        if error_response is not None:
            return error_response, error_status

        confirm = bool(data.get("confirm"))
        requested_by = str(data.get("requested_by") or "ui").strip() or "ui"
        existing_job_id = str(data.get("job_id") or "").strip()
        limit = int(data.get("limit") or SERVICE_REGENERATION_BATCH_LIMIT)
        limit = max(1, min(limit, SERVICE_REGENERATION_BATCH_LIMIT))

        db = DatabaseManager()
        cursor = db.conn.cursor()

        if existing_job_id and confirm:
            job = _load_regeneration_job(cursor, existing_job_id, include_items=True)
            if not job:
                db.close()
                return jsonify({"error": "job не найден"}), 404
            if str(job.get("business_id") or "") != business_id:
                db.close()
                return jsonify({"error": "job принадлежит другому бизнесу"}), 403
            if str(job.get("user_id") or "") != str(user_data["user_id"]) and not user_data.get("is_superadmin"):
                db.close()
                return jsonify({"error": "Нет доступа к этому job"}), 403
            if str(job.get("status") or "") == "awaiting_confirmation":
                db.close()
                _start_persistent_regeneration_job(existing_job_id, token)
                return jsonify({"success": True, "job": _public_job(existing_job_id)})
            db.close()
            return jsonify({"success": True, "job": job})

        cursor.execute(
            """
            SELECT id, cooldown_until
            FROM serviceregenerationjobs
            WHERE business_id = %s
              AND status = 'rate_limited'
              AND cooldown_until IS NOT NULL
              AND cooldown_until > NOW()
            ORDER BY cooldown_until DESC
            LIMIT 1
            """,
            (business_id,),
        )
        cooldown_row = cursor.fetchone()
        if cooldown_row:
            cooldown_until = _cell(cooldown_row, "cooldown_until", _cell(cooldown_row, 1))
            db.close()
            return jsonify({
                "success": False,
                "error": "rate_limit_cooldown",
                "message": "Перегенерация временно на паузе из-за лимита GigaChat",
                "cooldown_until": cooldown_until,
            }), 429

        services = _load_active_services_for_business(cursor, business_id)
        audit = build_services_quality_audit(services)
        audit_items = audit.get("items") if isinstance(audit.get("items"), list) else []
        service_ids = [str(service.get("id") or "") for service in services]
        attempts = _get_service_regeneration_attempts(cursor, service_ids)
        selection = select_problem_services_for_regeneration(
            services,
            audit_items,
            attempts,
            limit=limit,
        )
        job_id = _insert_regeneration_job(
            cursor=cursor,
            user_id=user_data["user_id"],
            business_id=business_id,
            requested_by=requested_by,
            limit=limit,
            audit=audit,
            selection=selection,
            confirmation_required=not confirm,
        )
        db.conn.commit()
        job = _load_regeneration_job(cursor, job_id, include_items=True)
        db.close()

        if confirm and job and str(job.get("status") or "") == "queued":
            _run_thread = threading.Thread(
                target=_run_service_regeneration_job,
                args=(job_id, token),
                daemon=True,
            )
            _run_thread.start()
            job = _public_job(job_id)

        return jsonify({
            "success": True,
            "job": job,
            "summary": audit.get("summary") or {},
        })

    except Exception:
        error = sys.exc_info()[1]
        print(f"❌ Ошибка запуска перегенерации услуг: {error}", flush=True)
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(error)}), 500


@services_bp.route('/api/services/regenerate-problematic/<string:job_id>', methods=['GET', 'OPTIONS'])
def get_regenerate_problematic_job(job_id):
    """Статус job повторной генерации проблемных SEO-предложений."""
    if request.method == 'OPTIONS':
        return ('', 204)

    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        job = _public_job(job_id)
        if not job:
            return jsonify({"error": "job не найден"}), 404

        if str(job.get("user_id") or "") != str(user_data["user_id"]) and not user_data.get("is_superadmin"):
            return jsonify({"error": "Нет доступа к этому job"}), 403

        return jsonify({"success": True, "job": job})

    except Exception:
        error = sys.exc_info()[1]
        print(f"❌ Ошибка статуса перегенерации услуг: {error}", flush=True)
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(error)}), 500


@services_bp.route('/api/services/regeneration-history/<string:service_id>', methods=['GET', 'OPTIONS'])
def get_service_regeneration_history(service_id):
    """История качества и повторной генерации одной услуги."""
    if request.method == 'OPTIONS':
        return ('', 204)

    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        db = DatabaseManager()
        cursor = db.conn.cursor()
        cursor.execute(
            """
            SELECT user_id, business_id, name
            FROM userservices
            WHERE id = %s
            LIMIT 1
            """,
            (service_id,),
        )
        service_row = cursor.fetchone()
        if not service_row:
            db.close()
            return jsonify({"error": "Услуга не найдена"}), 404
        service_user_id = _cell(service_row, "user_id", _cell(service_row, 0))
        if service_user_id != user_data["user_id"] and not user_data.get("is_superadmin"):
            db.close()
            return jsonify({"error": "Нет доступа к этой услуге"}), 403

        cursor.execute(
            """
            SELECT i.id, i.job_id, i.status, i.attempt_no,
                   i.issue_labels_json, i.after_issue_labels_json,
                   i.before_optimized_name, i.before_optimized_description,
                   i.after_optimized_name, i.after_optimized_description,
                   i.error, i.created_at, i.updated_at,
                   j.status AS job_status, j.cooldown_until, j.requested_by
            FROM serviceregenerationjobitems i
            JOIN serviceregenerationjobs j ON j.id = i.job_id
            WHERE i.service_id = %s
            ORDER BY i.created_at DESC
            LIMIT 20
            """,
            (service_id,),
        )
        rows = cursor.fetchall()
        col_names = [d[0] for d in cursor.description] if cursor.description else []
        items = [_jsonable_job_value(_service_row_to_dict(row, col_names)) for row in rows]
        db.close()
        return jsonify({"success": True, "service_id": service_id, "items": items})

    except Exception:
        error = sys.exc_info()[1]
        print(f"❌ Ошибка истории перегенерации услуги: {error}", flush=True)
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(error)}), 500

@services_bp.route('/api/services/update/<string:service_id>', methods=['PUT', 'OPTIONS'])
def update_service(service_id):
    """Обновить услугу"""
    if request.method == 'OPTIONS':
        return ('', 204)
    
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "Нет данных"}), 400
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Проверяем, что услуга принадлежит пользователю
        cursor.execute(
            """
            SELECT user_id, business_id, name, description, optimized_name, optimized_description
            FROM userservices
            WHERE id = %s
            """,
            (service_id,),
        )
        row = cursor.fetchone()
        if not row:
            db.close()
            return jsonify({"error": "Услуга не найдена"}), 404
        
        service_user_id = _cell(row, 'user_id', _cell(row, 0))
        service_business_id = _cell(row, 'business_id', _cell(row, 1))
        previous_data = {
            "name": _cell(row, 'name', _cell(row, 2, '')),
            "description": _cell(row, 'description', _cell(row, 3, '')),
            "optimized_name": _cell(row, 'optimized_name', _cell(row, 4, '')),
            "optimized_description": _cell(row, 'optimized_description', _cell(row, 5, '')),
        }
        
        if service_user_id != user_data["user_id"] and not db.is_superadmin(user_data["user_id"]):
            db.close()
            return jsonify({"error": "Нет доступа к этой услуге"}), 403
        
        # Преобразуем keywords в строку JSON, если это массив
        keywords = data.get('keywords', [])
        if isinstance(keywords, list):
            keywords_str = json.dumps(keywords, ensure_ascii=False)
        elif isinstance(keywords, str):
            keywords_str = keywords
        else:
            keywords_str = json.dumps([])
        
        # Проверяем, есть ли поля optimized_description и optimized_name в таблице
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'userservices'
            ORDER BY ordinal_position
        """)
        columns = [_cell(column_row, 'column_name', _cell(column_row, 0)) for column_row in cursor.fetchall()]
        has_optimized_description = 'optimized_description' in columns
        has_optimized_name = 'optimized_name' in columns
        
        optimized_description = data.get('optimized_description', '')
        optimized_name = data.get('optimized_name', '')
        
        print(f"🔍 DEBUG services_api.update_service: has_optimized_description = {has_optimized_description}, has_optimized_name = {has_optimized_name}", flush=True)
        print(f"🔍 DEBUG services_api.update_service: optimized_name = '{optimized_name}' (length: {len(optimized_name) if optimized_name else 0})", flush=True)
        print(f"🔍 DEBUG services_api.update_service: optimized_description = '{optimized_description[:50] if optimized_description else ''}...' (length: {len(optimized_description) if optimized_description else 0})", flush=True)
        
        # Обновляем услугу с учетом наличия полей
        if has_optimized_description and has_optimized_name:
            print(f"🔍 DEBUG services_api.update_service: Обновление с optimized_description и optimized_name", flush=True)
            cursor.execute("""
                UPDATE userservices
                SET category = %s, name = %s, optimized_name = %s, description = %s,
                    optimized_description = %s, keywords = %s, price = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (
                data.get('category', ''),
                data.get('name', ''),
                optimized_name,
                data.get('description', ''),
                optimized_description,
                keywords_str,
                data.get('price', 0),
                service_id
            ))
            print(f"✅ DEBUG services_api.update_service: UPDATE выполнен, rowcount = {cursor.rowcount}", flush=True)
            
            # Проверяем, что данные сохранились
            cursor.execute("SELECT optimized_name, optimized_description FROM userservices WHERE id = %s", (service_id,))
            check_row = cursor.fetchone()
            if check_row:
                check_optimized_name = _cell(check_row, 'optimized_name', _cell(check_row, 0, ''))
                check_optimized_description = _cell(check_row, 'optimized_description', _cell(check_row, 1, ''))
                print(f"✅ DEBUG services_api.update_service: Проверка после UPDATE - optimized_name = '{check_optimized_name}', optimized_description = '{check_optimized_description[:50] if check_optimized_description else ''}...'", flush=True)
            else:
                print(f"❌ DEBUG services_api.update_service: Услуга не найдена после UPDATE!", flush=True)
        elif has_optimized_description:
            cursor.execute("""
                UPDATE userservices
                SET category = %s, name = %s, description = %s, optimized_description = %s,
                    keywords = %s, price = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (
                data.get('category', ''),
                data.get('name', ''),
                data.get('description', ''),
                optimized_description,
                keywords_str,
                data.get('price', 0),
                service_id
            ))
        elif has_optimized_name:
            cursor.execute("""
                UPDATE userservices
                SET category = %s, name = %s, optimized_name = %s, description = %s,
                    keywords = %s, price = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (
                data.get('category', ''),
                data.get('name', ''),
                optimized_name,
                data.get('description', ''),
                keywords_str,
                data.get('price', 0),
                service_id
            ))
        else:
            cursor.execute("""
                UPDATE userservices
                SET category = %s, name = %s, description = %s, keywords = %s,
                    price = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (
                data.get('category', ''),
                data.get('name', ''),
                data.get('description', ''),
                keywords_str,
                data.get('price', 0),
                service_id
            ))

        metadata_updates = []
        metadata_values = []
        if 'fallback_used' in columns:
            metadata_updates.append("fallback_used = %s")
            metadata_values.append(bool(data.get('fallback_used')))
        if 'fallback_reason' in columns:
            metadata_updates.append("fallback_reason = %s")
            metadata_values.append(str(data.get('fallback_reason') or '').strip())
        if 'guardrail_reasons' in columns:
            metadata_updates.append("guardrail_reasons = %s")
            metadata_values.append(Json(data.get('guardrail_reasons') if isinstance(data.get('guardrail_reasons'), list) else []))
        if 'pattern_version_ids' in columns:
            metadata_updates.append("pattern_version_ids = %s")
            metadata_values.append(Json(data.get('pattern_version_ids') if isinstance(data.get('pattern_version_ids'), list) else []))
        if metadata_updates:
            cursor.execute(
                "UPDATE userservices SET " + ", ".join(metadata_updates) + ", updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                [*metadata_values, service_id],
            )
        
        _record_service_optimization_learning(
            user_id=user_data["user_id"],
            business_id=service_business_id,
            service_id=service_id,
            previous_data=previous_data,
            next_data={
                "name": data.get('name', ''),
                "description": data.get('description', ''),
                "optimized_name": optimized_name,
                "optimized_description": optimized_description,
            },
            conn=db.conn,
        )
        db.conn.commit()
        db.close()
        return jsonify({
            "success": True,
            "service_id": service_id,
            "business_id": service_business_id,
        })
    except Exception as e:
        print(f"❌ Ошибка обновления услуги: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@services_bp.route('/api/services/compression/draft', methods=['POST', 'OPTIONS'])
def create_service_compression_draft():
    """Создать черновик сокращения меню услуг."""
    if request.method == 'OPTIONS':
        return ('', 204)

    user_data, error_response, error_status = _require_services_user()
    if error_response:
        return error_response, error_status

    try:
        data = request.get_json() or {}
        business_id = str(data.get("business_id") or "").strip()
        if not business_id:
            return jsonify({"error": "business_id обязателен"}), 400

        db = DatabaseManager()
        cursor = db.conn.cursor()
        access_response, access_status = _ensure_business_access(db, cursor, business_id, user_data)
        if access_response:
            db.close()
            return access_response, access_status

        services = _load_active_services_for_business(cursor, business_id)
        draft_payload = build_service_catalog_compression_draft(services)
        request_id = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT INTO service_catalog_compression_requests (
                id, business_id, user_id, status, before_count, after_count,
                groups_json, diff_json, created_service_ids, archived_service_ids
            )
            VALUES (%s, %s, %s, 'draft_ready', %s, %s, %s, %s, '[]'::jsonb, '[]'::jsonb)
            """,
            (
                request_id,
                business_id,
                user_data["user_id"],
                int(draft_payload.get("before_count") or 0),
                int(draft_payload.get("after_count") or 0),
                Json(draft_payload.get("groups") or []),
                Json({
                    "mode": "draft",
                    "general_recommendations": draft_payload.get("general_recommendations") or [],
                    "category_counts": draft_payload.get("category_counts") or [],
                }),
            ),
        )
        db.conn.commit()
        draft = _load_compression_request(cursor, request_id)
        db.close()
        return jsonify({"success": True, "draft": draft, "analysis": draft_payload})
    except Exception:
        error = sys.exc_info()[1]
        print(f"❌ Ошибка создания черновика сокращения услуг: {error}", flush=True)
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(error)}), 500


@services_bp.route('/api/services/compression/draft/<string:request_id>', methods=['PUT', 'OPTIONS'])
def update_service_compression_draft(request_id):
    """Сохранить ручные правки черновика сокращения услуг."""
    if request.method == 'OPTIONS':
        return ('', 204)

    user_data, error_response, error_status = _require_services_user()
    if error_response:
        return error_response, error_status

    try:
        data = request.get_json() or {}
        groups = data.get("groups")
        if not isinstance(groups, list):
            return jsonify({"error": "groups должен быть массивом"}), 400

        db = DatabaseManager()
        cursor = db.conn.cursor()
        draft = _load_compression_request(cursor, request_id)
        if not draft:
            db.close()
            return jsonify({"error": "Черновик не найден"}), 404
        access_response, access_status = _ensure_business_access(db, cursor, draft["business_id"], user_data)
        if access_response:
            db.close()
            return access_response, access_status
        if str(draft.get("status") or "") == "applied":
            db.close()
            return jsonify({"error": "Применённый черновик нельзя редактировать"}), 409

        before_count = int(draft.get("before_count") or 0)
        archived_count, created_count = _compression_counts(groups)
        after_count = max(0, before_count - archived_count + created_count)
        cursor.execute(
            """
            UPDATE service_catalog_compression_requests
            SET groups_json = %s,
                after_count = %s,
                status = 'needs_review',
                updated_at = NOW()
            WHERE id = %s
            """,
            (Json(groups), after_count, request_id),
        )
        db.conn.commit()
        updated = _load_compression_request(cursor, request_id)
        db.close()
        return jsonify({"success": True, "draft": updated})
    except Exception:
        error = sys.exc_info()[1]
        print(f"❌ Ошибка обновления черновика сокращения услуг: {error}", flush=True)
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(error)}), 500


@services_bp.route('/api/services/compression/draft/<string:request_id>/apply', methods=['POST', 'OPTIONS'])
def apply_service_compression_draft(request_id):
    """Применить черновик: создать объединённые услуги и мягко архивировать исходные."""
    if request.method == 'OPTIONS':
        return ('', 204)

    user_data, error_response, error_status = _require_services_user()
    if error_response:
        return error_response, error_status

    try:
        db = DatabaseManager()
        cursor = db.conn.cursor()
        draft = _load_compression_request(cursor, request_id)
        if not draft:
            db.close()
            return jsonify({"error": "Черновик не найден"}), 404
        access_response, access_status = _ensure_business_access(db, cursor, draft["business_id"], user_data)
        if access_response:
            db.close()
            return access_response, access_status
        if str(draft.get("status") or "") == "applied":
            db.close()
            return jsonify({"success": True, "draft": draft, "already_applied": True})

        groups = draft.get("groups_json") if isinstance(draft.get("groups_json"), list) else []
        applicable_groups = [group for group in groups if str(group.get("action") or "") in {"apply", "promotion"}]
        if not applicable_groups:
            db.close()
            return jsonify({"error": "Нет групп для применения"}), 400

        created_service_ids = []
        archived_service_ids = []
        group_results = []
        for group in applicable_groups:
            source_ids = [str(item or "").strip() for item in group.get("source_service_ids") or [] if str(item or "").strip()]
            if not source_ids:
                continue
            placeholders = ", ".join(["%s"] * len(source_ids))
            cursor.execute(
                f"""
                SELECT id
                FROM userservices
                WHERE business_id = %s
                  AND id IN ({placeholders})
                  AND (is_active IS TRUE OR is_active IS NULL)
                """,
                tuple([draft["business_id"], *source_ids]),
            )
            found_ids = [str(_cell(row, "id", _cell(row, 0)) or "") for row in cursor.fetchall()]
            if not found_ids:
                continue

            created_id = None
            if str(group.get("action") or "") == "apply":
                target = group.get("target") if isinstance(group.get("target"), dict) else {}
                created_id = str(uuid.uuid4())
                keywords = target.get("keywords") if isinstance(target.get("keywords"), list) else []
                cursor.execute(
                    """
                    INSERT INTO userservices (
                        id, user_id, business_id, category, name, description,
                        keywords, price, is_active, created_at, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    (
                        created_id,
                        user_data["user_id"],
                        draft["business_id"],
                        str(target.get("category") or "").strip() or "Общие услуги",
                        str(target.get("name") or "").strip() or str(group.get("title") or "Объединённая услуга"),
                        str(target.get("description") or "").strip(),
                        json.dumps(keywords, ensure_ascii=False),
                        str(target.get("price") or "").strip(),
                    ),
                )
                created_service_ids.append(created_id)

            cursor.execute(
                f"""
                UPDATE userservices
                SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
                WHERE business_id = %s AND id IN ({placeholders})
                """,
                tuple([draft["business_id"], *found_ids]),
            )
            archived_service_ids.extend(found_ids)
            group_results.append({
                "group_id": group.get("id"),
                "action": group.get("action"),
                "created_service_id": created_id,
                "archived_service_ids": found_ids,
            })

        before_count = int(draft.get("before_count") or 0)
        after_count = max(0, before_count - len(set(archived_service_ids)) + len(created_service_ids))
        diff = {
            "mode": "applied",
            "groups": group_results,
            "created_count": len(created_service_ids),
            "archived_count": len(set(archived_service_ids)),
            "provider_write_performed": False,
        }
        cursor.execute(
            """
            UPDATE service_catalog_compression_requests
            SET status = 'applied',
                after_count = %s,
                diff_json = %s,
                created_service_ids = %s,
                archived_service_ids = %s,
                updated_at = NOW(),
                applied_at = NOW()
            WHERE id = %s
            """,
            (
                after_count,
                Json(diff),
                Json(created_service_ids),
                Json(sorted(set(archived_service_ids))),
                request_id,
            ),
        )
        db.conn.commit()
        updated = _load_compression_request(cursor, request_id)
        db.close()
        return jsonify({"success": True, "draft": updated, "diff": diff})
    except Exception:
        error = sys.exc_info()[1]
        print(f"❌ Ошибка применения черновика сокращения услуг: {error}", flush=True)
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(error)}), 500


@services_bp.route('/api/services/compression/draft/<string:request_id>/rollback', methods=['POST', 'OPTIONS'])
def rollback_service_compression_draft(request_id):
    """Откатить применённую группировку услуг."""
    if request.method == 'OPTIONS':
        return ('', 204)

    user_data, error_response, error_status = _require_services_user()
    if error_response:
        return error_response, error_status

    try:
        db = DatabaseManager()
        cursor = db.conn.cursor()
        draft = _load_compression_request(cursor, request_id)
        if not draft:
            db.close()
            return jsonify({"error": "Черновик не найден"}), 404
        access_response, access_status = _ensure_business_access(db, cursor, draft["business_id"], user_data)
        if access_response:
            db.close()
            return access_response, access_status
        if str(draft.get("status") or "") != "applied":
            db.close()
            return jsonify({"error": "Откат доступен только для применённого черновика"}), 409

        created_ids = [str(item or "").strip() for item in draft.get("created_service_ids") or [] if str(item or "").strip()]
        archived_ids = [str(item or "").strip() for item in draft.get("archived_service_ids") or [] if str(item or "").strip()]
        if created_ids:
            placeholders = ", ".join(["%s"] * len(created_ids))
            cursor.execute(
                f"""
                UPDATE userservices
                SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
                WHERE business_id = %s AND id IN ({placeholders})
                """,
                tuple([draft["business_id"], *created_ids]),
            )
        if archived_ids:
            placeholders = ", ".join(["%s"] * len(archived_ids))
            cursor.execute(
                f"""
                UPDATE userservices
                SET is_active = TRUE, updated_at = CURRENT_TIMESTAMP
                WHERE business_id = %s AND id IN ({placeholders})
                """,
                tuple([draft["business_id"], *archived_ids]),
            )
        cursor.execute(
            """
            UPDATE service_catalog_compression_requests
            SET status = 'rolled_back',
                updated_at = NOW()
            WHERE id = %s
            """,
            (request_id,),
        )
        db.conn.commit()
        updated = _load_compression_request(cursor, request_id)
        db.close()
        return jsonify({"success": True, "draft": updated})
    except Exception:
        error = sys.exc_info()[1]
        print(f"❌ Ошибка отката сокращения услуг: {error}", flush=True)
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(error)}), 500


@services_bp.route('/api/services/delete/<string:service_id>', methods=['DELETE', 'OPTIONS'])
def delete_service(service_id):
    """Удалить услугу"""
    if request.method == 'OPTIONS':
        return ('', 204)
    
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Проверяем, что услуга принадлежит пользователю
        cursor.execute("SELECT user_id FROM userservices WHERE id = %s", (service_id,))
        row = cursor.fetchone()
        if not row:
            db.close()
            return jsonify({"error": "Услуга не найдена"}), 404
        
        service_user_id = _cell(row, 'user_id', _cell(row, 0))
        if service_user_id != user_data["user_id"] and not db.is_superadmin(user_data["user_id"]):
            db.close()
            return jsonify({"error": "Нет доступа к этой услуге"}), 403
        
        # Удаляем услугу
        cursor.execute("DELETE FROM userservices WHERE id = %s", (service_id,))
        db.conn.commit()
        db.close()
        
        return jsonify({"success": True})
    
    except Exception as e:
        print(f"❌ Ошибка удаления услуги: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
