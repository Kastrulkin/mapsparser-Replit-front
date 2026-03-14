from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
from flask import Blueprint, jsonify, request
from psycopg2.extras import Json

from auth_system import verify_session
from core.channel_delivery import normalize_phone, send_maton_bridge_message
from core.card_audit import build_lead_card_preview_snapshot
from core.ai_learning import ensure_ai_learning_events_table, record_ai_learning_event
from core.helpers import get_business_id_from_user
from database_manager import DatabaseManager
from pg_db_utils import get_db_connection
from services.gigachat_client import analyze_text_with_gigachat
from services.prospecting_service import ProspectingService


admin_prospecting_bp = Blueprint("admin_prospecting", __name__)

SHORTLIST_APPROVED = "shortlist_approved"
SHORTLIST_REJECTED = "shortlist_rejected"
SELECTED_FOR_OUTREACH = "selected_for_outreach"
CHANNEL_SELECTED = "channel_selected"
ALLOWED_OUTREACH_CHANNELS = {"telegram", "whatsapp", "email", "manual"}
DRAFT_GENERATED = "generated"
DRAFT_APPROVED = "approved"
DRAFT_REJECTED = "rejected"
QUEUED_FOR_SEND = "queued_for_send"
BATCH_DRAFT = "draft"
BATCH_APPROVED = "approved"
QUEUE_STATUS_QUEUED = "queued"
QUEUE_STATUS_SENDING = "sending"
QUEUE_STATUS_SENT = "sent"
QUEUE_STATUS_DELIVERED = "delivered"
QUEUE_STATUS_RETRY = "retry"
QUEUE_STATUS_DLQ = "dlq"
QUEUE_STATUS_FAILED = "failed"
MAX_DAILY_OUTREACH_BATCH = 10
ALLOWED_REPLY_OUTCOMES = {"positive", "question", "no_response", "hard_no"}
SEARCH_JOB_TIMEOUT_SEC = int(os.environ.get("APIFY_SEARCH_TIMEOUT_SEC", "180"))
OUTREACH_SEND_MAX_ATTEMPTS = int(os.environ.get("OUTREACH_SEND_MAX_ATTEMPTS", "3"))
OUTREACH_RETRY_DELAY_DAYS = (1, 2)  # D1, D3 относительно D0
LEAD_OUTREACH_MODERATION_STATUS = "lead_outreach"


def _normalize_learning_intent(raw_intent: str | None) -> str:
    value = str(raw_intent or "client_outreach").strip().lower()
    allowed = {"client_outreach", "partnership_outreach", "operations"}
    return value if value in allowed else "client_outreach"


def _resolve_lead_intent(cur, lead_id: str) -> str:
    try:
        cur.execute("SELECT intent FROM prospectingleads WHERE id = %s", (lead_id,))
        row = cur.fetchone()
        if not row:
            return "client_outreach"
        if hasattr(row, "get"):
            return _normalize_learning_intent(row.get("intent"))
        if isinstance(row, (tuple, list)):
            return _normalize_learning_intent(row[0] if row else None)
    except Exception:
        pass
    return "client_outreach"


def _remaining_daily_outreach_slots(conn) -> int:
    """Hard-cap daily outreach slots based on queued items for today's batches."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM outreachsendqueue q
        JOIN outreachsendbatches b ON b.id = q.batch_id
        WHERE b.batch_date = CURRENT_DATE
        """
    )
    row = cur.fetchone()
    if not row:
        used = 0
    elif hasattr(row, "get"):
        used = int((row.get("cnt") or 0))
    else:
        used = int((row[0] if row else 0) or 0)
    return max(0, MAX_DAILY_OUTREACH_BATCH - used)


def _outreach_retry_delay_for_attempt(attempt_no: int) -> timedelta | None:
    # attempt_no считается уже после инкремента:
    # 1 => первый fail после D0, retry через 1 день
    # 2 => второй fail, retry через 2 дня (D3 относительно D0)
    if attempt_no <= 0:
        return None
    idx = attempt_no - 1
    if idx < len(OUTREACH_RETRY_DELAY_DAYS):
        return timedelta(days=int(OUTREACH_RETRY_DELAY_DAYS[idx]))
    return None


def _auth_error(message: str, status_code: int):
    return jsonify({"error": message}), status_code


def _require_superadmin():
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None, _auth_error("Authorization required", 401)

    token = auth_header.split(" ", 1)[1]
    user_data = verify_session(token)
    if not user_data:
        return None, _auth_error("Invalid token", 401)
    if not user_data.get("is_superadmin"):
        return None, _auth_error("Superadmin access required", 403)
    return user_data, None


def _require_auth():
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None, _auth_error("Authorization required", 401)

    token = auth_header.split(" ", 1)[1]
    user_data = verify_session(token)
    if not user_data:
        return None, _auth_error("Invalid token", 401)
    return user_data, None


def _resolve_business_for_user(cur, user_data: dict, requested_business_id: str | None) -> str | None:
    is_superadmin = bool(user_data.get("is_superadmin"))
    user_id = str(user_data.get("user_id") or "")
    business_id = (requested_business_id or "").strip() or get_business_id_from_user(user_id, None)
    if not business_id:
        return None
    if is_superadmin:
        return business_id
    cur.execute(
        """
        SELECT id
        FROM businesses
        WHERE id = %s AND owner_id = %s
        LIMIT 1
        """,
        (business_id, user_id),
    )
    row = cur.fetchone()
    return (row["id"] if hasattr(row, "get") else row[0]) if row else None


def _ensure_partnership_columns(conn) -> None:
    cur = conn.cursor()
    cur.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS intent TEXT DEFAULT 'client_outreach'")
    cur.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS partnership_stage TEXT DEFAULT 'imported'")
    cur.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS business_id UUID")
    cur.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS created_by UUID")
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_prospectingleads_intent_stage
        ON prospectingleads (intent, partnership_stage)
        """
    )
    # DDL в PostgreSQL транзакционный; без commit изменения могут откатиться при закрытии conn.
    conn.commit()


def _create_search_job(
    *,
    query: str,
    location: str,
    search_limit: int,
    actor_id: str,
    user_id: str,
) -> str:
    job_id = str(uuid.uuid4())
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO outreachsearchjobs (
                id, source, actor_id, query, location, search_limit, status, created_by
            ) VALUES (
                %s, %s, %s, %s, %s, %s, 'queued', %s
            )
            """,
            (job_id, "apify_yandex", actor_id, query, location, search_limit, user_id),
        )
        conn.commit()
        return job_id
    finally:
        conn.close()


def _update_search_job(job_id: str, **updates: Any) -> None:
    if not updates:
        return

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        assignments = []
        values = []
        for key, value in updates.items():
            assignments.append(f"{key} = %s")
            values.append(Json(value) if key == "results_json" else value)
        assignments.append("updated_at = NOW()")
        if "status" in updates and updates["status"] in {"completed", "failed"}:
            assignments.append("completed_at = NOW()")
        values.append(job_id)
        cur.execute(
            f"UPDATE outreachsearchjobs SET {', '.join(assignments)} WHERE id = %s",
            values,
        )
        conn.commit()
    finally:
        conn.close()


def _get_search_job(job_id: str):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                id, source, actor_id, query, location, search_limit, status,
                result_count, created_by, error_text, results_json,
                created_at, updated_at, completed_at
            FROM outreachsearchjobs
            WHERE id = %s
            """,
            (job_id,),
        )
        return cur.fetchone()
    finally:
        conn.close()


def _to_bool_filter(value: str | None):
    if value is None or value == "":
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes"}:
        return True
    if normalized in {"0", "false", "no"}:
        return False
    return None


def _is_placeholder_like(value: Any) -> bool:
    if value is None:
        return False
    text = str(value).strip().lower()
    return text in {
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


def _normalize_lead_for_display(lead: dict[str, Any]) -> dict[str, Any] | None:
    normalized = dict(lead)
    if _is_placeholder_like(normalized.get("name")):
        normalized["name"] = None

    if not normalized.get("name"):
        for fallback_field in ("title", "company_name", "company"):
            fallback_value = normalized.get(fallback_field)
            if fallback_value and not _is_placeholder_like(fallback_value):
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
    ):
        if _is_placeholder_like(normalized.get(field)):
            normalized[field] = None

    for field in ("rating", "reviews_count"):
        if _is_placeholder_like(normalized.get(field)):
            normalized[field] = None

    if not normalized.get("name"):
        return None

    has_identity = any(
        normalized.get(field)
        for field in ("name", "address", "website", "phone", "source_url")
    )
    if not has_identity:
        return None

    return normalized


def _lead_matches_filters(lead: dict[str, Any], filters: dict[str, Any]) -> bool:
    category = filters.get("category")
    if category and category.lower() not in (lead.get("category") or "").lower():
        return False

    city = filters.get("city")
    if city:
        haystack = " ".join(
            part for part in [lead.get("city"), lead.get("address"), lead.get("location")] if part
        ).lower()
        if city.lower() not in haystack:
            return False

    status = filters.get("status")
    if status and (lead.get("status") or "") != status:
        return False

    min_rating = filters.get("min_rating")
    if min_rating is not None and float(lead.get("rating") or 0) < min_rating:
        return False

    max_rating = filters.get("max_rating")
    if max_rating is not None and float(lead.get("rating") or 0) > max_rating:
        return False

    min_reviews = filters.get("min_reviews")
    if min_reviews is not None and int(lead.get("reviews_count") or 0) < min_reviews:
        return False

    max_reviews = filters.get("max_reviews")
    if max_reviews is not None and int(lead.get("reviews_count") or 0) > max_reviews:
        return False

    has_website = filters.get("has_website")
    if has_website is not None and bool(lead.get("website")) != has_website:
        return False

    has_phone = filters.get("has_phone")
    if has_phone is not None and bool(lead.get("phone")) != has_phone:
        return False

    has_email = filters.get("has_email")
    if has_email is not None and bool(lead.get("email")) != has_email:
        return False

    has_messengers = filters.get("has_messengers")
    if has_messengers is not None:
        messenger_links = lead.get("messenger_links_json") or []
        if isinstance(messenger_links, str):
            try:
                import json

                messenger_links = json.loads(messenger_links)
            except Exception:
                messenger_links = []
        has_any_messenger = bool(
            lead.get("telegram_url") or lead.get("whatsapp_url") or (messenger_links if isinstance(messenger_links, list) else [])
        )
        if has_any_messenger != has_messengers:
            return False

    return True


def _insert_partnership_lead_if_new(
    cur,
    *,
    business_id: str,
    created_by: str,
    source_url: str,
    name: str | None,
    city: str | None,
    category: str | None,
    source: str,
    phone: str | None = None,
    email: str | None = None,
    website: str | None = None,
    telegram_url: str | None = None,
    whatsapp_url: str | None = None,
    rating: float | None = None,
    reviews_count: int | None = None,
) -> tuple[str | None, bool]:
    normalized_url = str(source_url or "").strip()
    if not normalized_url:
        return None, False
    cur.execute(
        """
        SELECT id
        FROM prospectingleads
        WHERE business_id = %s
          AND source_url = %s
          AND COALESCE(intent, 'client_outreach') = 'partnership_outreach'
        LIMIT 1
        """,
        (business_id, normalized_url),
    )
    existing = cur.fetchone()
    if existing:
        return (existing["id"] if hasattr(existing, "get") else existing[0]), False

    lead_id = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO prospectingleads (
            id, name, address, city, source_url, source, category, status,
            phone, email, website, telegram_url, whatsapp_url, rating, reviews_count,
            intent, partnership_stage, business_id, created_by, created_at, updated_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, NOW(), NOW()
        )
        """,
        (
            lead_id,
            (name or "Новый партнёр"),
            "",
            city,
            normalized_url,
            source,
            category,
            "imported",
            phone,
            email,
            website,
            telegram_url,
            whatsapp_url,
            rating,
            reviews_count,
            "partnership_outreach",
            "imported",
            business_id,
            created_by,
        ),
    )
    return lead_id, True


def _run_search_job(job_id: str, query: str, location: str, search_limit: int) -> None:
    _update_search_job(job_id, status="running", error_text=None)
    try:
        service = ProspectingService()
        run_meta = service.start_search_run(query, location, search_limit)
        _update_search_job(
            job_id,
            status="running",
            error_text=None,
            results_json={
                "_apify": {
                    "run_id": run_meta.get("run_id"),
                    "dataset_id": run_meta.get("dataset_id"),
                    "status": run_meta.get("status"),
                }
            },
        )
    except Exception as exc:
        if "timed out" in str(exc).lower():
            _update_search_job(
                job_id,
                status="running",
                error_text=None,
                results_json={"_apify": {"status": "START_PENDING"}},
            )
            return
        print(f"Error in async prospecting search job {job_id}: {exc}")
        _update_search_job(job_id, status="failed", error_text=str(exc))


def _refresh_search_job_from_apify(row: dict[str, Any]) -> dict[str, Any]:
    status = (row.get("status") or "").strip().lower()
    if status not in {"queued", "running"}:
        return row

    results_blob = row.get("results_json")
    apify_meta = None
    if isinstance(results_blob, dict):
        apify_meta = results_blob.get("_apify")
    if not isinstance(apify_meta, dict):
        return row

    run_id = apify_meta.get("run_id")
    dataset_id = apify_meta.get("dataset_id")
    if not run_id:
        try:
            service = ProspectingService()
            run_meta = service.start_search_run(
                row.get("query") or "",
                row.get("location") or "",
                int(row.get("search_limit") or 50),
            )
            _update_search_job(
                row["id"],
                status="running",
                error_text=None,
                results_json={
                    "_apify": {
                        "run_id": run_meta.get("run_id"),
                        "dataset_id": run_meta.get("dataset_id"),
                        "status": run_meta.get("status"),
                    }
                },
            )
            refreshed = _get_search_job(row["id"])
            return dict(refreshed) if refreshed else row
        except Exception as exc:
            if "timed out" in str(exc).lower():
                _update_search_job(
                    row["id"],
                    status="running",
                    error_text=None,
                    results_json={"_apify": {"status": "START_PENDING"}},
                )
                refreshed = _get_search_job(row["id"])
                return dict(refreshed) if refreshed else {**row, "status": "running", "error_text": None}
            print(f"Error starting Apify search job {row.get('id')}: {exc}")
            _update_search_job(row["id"], status="failed", error_text=str(exc))
            refreshed = _get_search_job(row["id"])
            return dict(refreshed) if refreshed else {**row, "status": "failed", "error_text": str(exc)}

    try:
        service = ProspectingService()
        run_info = service.get_run(run_id)
        run_status = (run_info.get("status") or "").strip().upper()
        dataset_id = run_info.get("defaultDatasetId") or dataset_id

        if run_status in {"SUCCEEDED"}:
            results = service.fetch_dataset_items(dataset_id)
            _update_search_job(
                row["id"],
                status="completed",
                result_count=len(results),
                results_json=results,
                error_text=None,
            )
        elif run_status in {"FAILED", "ABORTED", "TIMED-OUT"}:
            status_message = (
                run_info.get("statusMessage")
                or run_info.get("status_message")
                or f"Apify run {run_status.lower()}"
            )
            _update_search_job(
                row["id"],
                status="failed",
                error_text=str(status_message),
                results_json={"_apify": {"run_id": run_id, "dataset_id": dataset_id, "status": run_status}},
            )
        else:
            _update_search_job(
                row["id"],
                status="running",
                error_text=None,
                results_json={"_apify": {"run_id": run_id, "dataset_id": dataset_id, "status": run_status}},
            )
        refreshed = _get_search_job(row["id"])
        return dict(refreshed) if refreshed else row
    except Exception as exc:
        if "timed out" in str(exc).lower():
            _update_search_job(
                row["id"],
                status="running",
                error_text=None,
                results_json={"_apify": {"run_id": run_id, "dataset_id": dataset_id, "status": "RUNNING"}},
            )
            refreshed = _get_search_job(row["id"])
            return dict(refreshed) if refreshed else {**row, "status": "running", "error_text": None}
        print(f"Error polling Apify search job {row.get('id')}: {exc}")
        return row


def _mark_search_job_failed_if_stale(row: dict[str, Any]) -> dict[str, Any]:
    row = _refresh_search_job_from_apify(row)
    status = (row.get("status") or "").strip().lower()
    if status not in {"queued", "running"}:
        return row

    results_blob = row.get("results_json")
    apify_meta = None
    if isinstance(results_blob, dict):
        apify_meta = results_blob.get("_apify")
    apify_status = ""
    if isinstance(apify_meta, dict):
        apify_status = str(apify_meta.get("status") or "").strip().upper()

    deadline_anchor = row.get("created_at") if apify_status == "START_PENDING" else (row.get("updated_at") or row.get("created_at"))
    if not isinstance(deadline_anchor, datetime):
        return row

    if deadline_anchor.tzinfo is None:
        deadline_anchor = deadline_anchor.replace(tzinfo=timezone.utc)

    deadline = deadline_anchor + timedelta(seconds=SEARCH_JOB_TIMEOUT_SEC)
    if datetime.now(timezone.utc) <= deadline:
        return row

    if apify_status == "START_PENDING":
        stale_error = f"Apify actor did not acknowledge start within {SEARCH_JOB_TIMEOUT_SEC} seconds"
    else:
        stale_error = f"Search timed out after {SEARCH_JOB_TIMEOUT_SEC} seconds"
    _update_search_job(row["id"], status="failed", error_text=stale_error)
    refreshed = _get_search_job(row["id"])
    return dict(refreshed) if refreshed else {**row, "status": "failed", "error_text": stale_error}


def _expire_stale_search_jobs() -> None:
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, status, error_text, created_at, updated_at
            FROM outreachsearchjobs
            WHERE status IN ('queued', 'running')
            """
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    for row in rows:
        _mark_search_job_failed_if_stale(dict(row))


def _generate_first_message_draft(lead: dict[str, Any], channel: str) -> dict[str, str]:
    company_name = (lead.get("name") or "вашей компании").strip()
    category = (lead.get("category") or "локального бизнеса").strip()
    city = (lead.get("city") or "").strip()
    rating = lead.get("rating")
    reviews_count = lead.get("reviews_count") or 0

    weak_points = []
    if reviews_count < 20:
        weak_points.append("мало отзывов")
    if rating and float(rating) < 4.7:
        weak_points.append("есть запас роста по рейтингу")
    if not lead.get("website"):
        weak_points.append("не видно отдельного сайта")
    if not lead.get("phone"):
        weak_points.append("не указан удобный контакт")
    if not weak_points:
        weak_points.append("карточку можно усилить по конверсии")

    angle = f"обратили внимание, что у {company_name} в Яндекс.Картах {', '.join(weak_points[:2])}"
    money_hint = "По нашей модели это может стоить бизнесу части входящих обращений каждый месяц."

    if channel == "telegram":
        opening = f"Здравствуйте. Посмотрели карточку {company_name}"
        cta = "Если хотите, пришлю короткий разбор и покажу, что можно быстро улучшить."
    elif channel == "whatsapp":
        opening = f"Здравствуйте! Посмотрели карточку {company_name}"
        cta = "Могу отправить короткий разбор с конкретными точками роста, если это актуально."
    elif channel == "email":
        opening = f"Здравствуйте! Мы посмотрели карточку {company_name} в Яндекс.Картах."
        cta = "Если интересно, отправим короткий разбор с конкретными доработками и прогнозом эффекта."
    else:
        opening = f"Здравствуйте. Изучили карточку {company_name}."
        cta = "Если удобно, покажу короткий разбор и объясню, какие доработки дадут эффект."

    location_line = f" Видим вас по направлению «{category}»{f' в {city}' if city else ''}."
    draft_text = f"{opening}:{location_line} {angle}. {money_hint} {cta}".strip()

    return {
        "angle_type": "maps_growth",
        "tone": "professional",
        "generated_text": draft_text,
    }


def _generate_audit_first_message_draft(
    lead: dict[str, Any],
    preview: dict[str, Any],
    channel: str,
) -> dict[str, str]:
    company_name = (lead.get("name") or "вашей компании").strip()
    category = (lead.get("category") or "локального бизнеса").strip()
    city = (lead.get("city") or "").strip()

    findings = preview.get("findings") or []
    recommended_actions = preview.get("recommended_actions") or []
    revenue = preview.get("revenue_potential") or {}
    total_min = revenue.get("total_min")
    total_max = revenue.get("total_max")

    top_findings = [str(item.get("title") or "").strip() for item in findings if isinstance(item, dict)]
    top_findings = [item for item in top_findings if item][:2]
    key_issue = ", ".join(top_findings) if top_findings else "есть резерв роста карточки"

    top_action = ""
    for item in recommended_actions:
        if isinstance(item, dict):
            top_action = str(item.get("title") or "").strip()
            if top_action:
                break
    if not top_action:
        top_action = "быстрое усиление карточки по услугам и контенту"

    money_hint = "потери по карте не оценены"
    if isinstance(total_min, (int, float)) and isinstance(total_max, (int, float)):
        min_value = int(round(float(total_min)))
        max_value = int(round(float(total_max)))
        money_hint = f"потенциал роста оценивается в {min_value:,}–{max_value:,} ₽/мес".replace(",", " ")

    location_line = f"по направлению «{category}»{f' в {city}' if city else ''}"
    message_core = (
        f"Посмотрели карточку {company_name} ({location_line}) и видим, что {key_issue}. "
        f"По нашей модели {money_hint}. "
        f"Первый шаг, который даст эффект: {top_action.lower()}."
    )

    if channel == "telegram":
        opening = "Здравствуйте!"
        closing = "Если хотите, отправлю краткий аудит с конкретными шагами в ответ."
    elif channel == "whatsapp":
        opening = "Здравствуйте!"
        closing = "Готов отправить короткий аудит и 3 приоритетных шага, если актуально."
    elif channel == "email":
        opening = "Здравствуйте."
        closing = "Если это актуально, направим короткий аудит и план действий на ближайшие 2 недели."
    else:
        opening = "Здравствуйте."
        closing = "Если удобно, отправлю краткий аудит и приоритетные доработки."

    return {
        "angle_type": "audit_preview",
        "tone": "professional",
        "generated_text": f"{opening} {message_core} {closing}".strip(),
    }


def _serialize_draft(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    payload = dict(row)
    learning = payload.get("learning_note_json")
    if isinstance(learning, str) and learning:
        try:
            payload["learning_note_json"] = json.loads(learning)
        except Exception:
            payload["learning_note_json"] = None
    return payload


def _serialize_batch_row(row: dict[str, Any]) -> dict[str, Any]:
    payload = dict(row)
    payload["items"] = []
    return payload


def _load_prospecting_lead(lead_id: str) -> dict[str, Any] | None:
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM prospectingleads WHERE id = %s", (lead_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _get_table_columns(table_name: str) -> set[str]:
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            """,
            (table_name,),
        )
        cols = set()
        for row in cur.fetchall():
            if hasattr(row, "get"):
                col = row.get("column_name")
            else:
                col = row[0] if row else None
            if col:
                cols.add(str(col))
        return cols
    finally:
        conn.close()


def _extract_yandex_org_id_from_url(url: Any) -> str:
    import re

    text = str(url or "").strip()
    if not text:
        return ""
    match = re.search(r"/org/(?:[^/]+/)?(\d+)", text)
    return match.group(1) if match else ""


def _extract_links_recursive(value: Any) -> list[str]:
    links: list[str] = []

    def _walk(node: Any) -> None:
        if node is None:
            return
        if isinstance(node, str):
            raw = node.strip()
            if raw:
                links.append(raw)
            return
        if isinstance(node, dict):
            for item in node.values():
                _walk(item)
            return
        if isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(value)
    deduped: list[str] = []
    seen = set()
    for item in links:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _extract_parsed_contacts(card_overview: Any) -> dict[str, str | list[str] | None]:
    overview = card_overview if isinstance(card_overview, dict) else {}
    social_links = _extract_links_recursive(overview.get("social_links"))
    telegram_url = None
    whatsapp_url = None
    email = None
    for item in social_links:
        low = item.lower()
        if not telegram_url and ("t.me/" in low or "telegram.me/" in low):
            telegram_url = item
        if not whatsapp_url and ("wa.me/" in low or "whatsapp.com/" in low or "api.whatsapp.com/" in low):
            whatsapp_url = item
        if not email:
            if low.startswith("mailto:"):
                email = item.split(":", 1)[1].strip()
            elif "@" in item and " " not in item and "/" not in item:
                email = item
    return {
        "telegram_url": telegram_url,
        "whatsapp_url": whatsapp_url,
        "email": email,
        "social_links": social_links,
    }


def _update_lead_business_link(lead_id: str, business_id: str) -> None:
    columns = _get_table_columns("prospectingleads")
    if "business_id" not in columns:
        return
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE prospectingleads
            SET business_id = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (business_id, lead_id),
        )
        conn.commit()
    finally:
        conn.close()


def _sync_lead_business_link_from_parse_history(lead: dict[str, Any]) -> dict[str, Any]:
    """Ensure lead.business_id points to latest parsed business for this lead URL/org."""
    lead_id = str(lead.get("id") or "").strip()
    if not lead_id:
        return lead

    source_url = str(lead.get("source_url") or "").strip()
    source_external_id = str(
        lead.get("source_external_id")
        or lead.get("google_id")
        or _extract_yandex_org_id_from_url(source_url)
        or ""
    ).strip()
    current_business_id = str(lead.get("business_id") or "").strip()

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'parsequeue'
            """
        )
        parsequeue_columns = {
            str(row.get("column_name") if hasattr(row, "get") else row[0])
            for row in (cur.fetchall() or [])
            if (row.get("column_name") if hasattr(row, "get") else (row[0] if row else None))
        }

        if current_business_id:
            cur.execute("SELECT 1 FROM businesses WHERE id = %s LIMIT 1", (current_business_id,))
            if cur.fetchone():
                return lead

        filters: list[str] = ["pq.business_id IS NOT NULL", "pq.status IN ('completed', 'done')"]
        params: list[Any] = []

        if source_url:
            filters.append("(pq.url = %s OR pq.url ILIKE %s)")
            params.extend([source_url, f"%{source_external_id}%"] if source_external_id else [source_url, source_url])

        if source_external_id and "url" in parsequeue_columns:
            filters.append("pq.url ILIKE %s")
            params.append(f"%{source_external_id}%")

        if not source_url and not source_external_id:
            return lead

        where_sql = " OR ".join(f"({flt})" for flt in filters[2:]) if len(filters) > 2 else ""
        if where_sql:
            where_sql = f"({where_sql}) AND " + " AND ".join(filters[:2])
        else:
            where_sql = " AND ".join(filters)

        cur.execute(
            f"""
            SELECT pq.business_id
            FROM parsequeue pq
            WHERE {where_sql}
            ORDER BY pq.updated_at DESC NULLS LAST, pq.created_at DESC
            LIMIT 1
            """,
            params,
        )
        row = cur.fetchone()
        matched_business_id = str((row.get("business_id") if hasattr(row, "get") else (row[0] if row else "")) or "").strip()
        if not matched_business_id:
            return lead

        if matched_business_id == current_business_id:
            return lead

        cur.execute(
            """
            UPDATE prospectingleads
            SET business_id = %s,
                updated_at = NOW()
            WHERE id = %s
            RETURNING *
            """,
            (matched_business_id, lead_id),
        )
        updated = cur.fetchone()
        if updated:
            conn.commit()
            return dict(updated)
        return lead
    finally:
        conn.close()


def _find_existing_business_for_lead(lead: dict[str, Any]) -> dict[str, Any] | None:
    source_url = str(lead.get("source_url") or "").strip()
    source_external_id = str(
        lead.get("source_external_id")
        or lead.get("google_id")
        or _extract_yandex_org_id_from_url(source_url)
        or ""
    ).strip()
    explicit_business_id = str(lead.get("business_id") or "").strip()
    lead_name = str(lead.get("name") or "").strip()
    lead_city = str(lead.get("city") or "").strip()

    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'businesses'
            """
        )
        business_columns = set()
        for row in cursor.fetchall():
            if hasattr(row, "get"):
                col = row.get("column_name")
            else:
                col = row[0] if row else None
            if col:
                business_columns.add(str(col))

        business = None
        if explicit_business_id:
            cursor.execute("SELECT * FROM businesses WHERE id = %s LIMIT 1", (explicit_business_id,))
            row = cursor.fetchone()
            business = dict(row) if row else None

        if not business and source_external_id and "yandex_org_id" in business_columns:
            cursor.execute("SELECT * FROM businesses WHERE yandex_org_id = %s LIMIT 1", (source_external_id,))
            row = cursor.fetchone()
            business = dict(row) if row else None

        if not business and source_url and "yandex_url" in business_columns:
            if source_external_id:
                cursor.execute(
                    """
                    SELECT *
                    FROM businesses
                    WHERE yandex_url = %s OR yandex_url ILIKE %s
                    ORDER BY updated_at DESC NULLS LAST, created_at DESC
                    LIMIT 1
                    """,
                    (source_url, f"%{source_external_id}%"),
                )
            else:
                cursor.execute(
                    """
                    SELECT *
                    FROM businesses
                    WHERE yandex_url = %s
                    ORDER BY updated_at DESC NULLS LAST, created_at DESC
                    LIMIT 1
                    """,
                    (source_url,),
                )
            row = cursor.fetchone()
            business = dict(row) if row else None

        if not business and lead_name:
            cursor.execute(
                """
                SELECT *
                FROM businesses
                WHERE LOWER(name) = LOWER(%s)
                  AND (%s = '' OR LOWER(COALESCE(city, '')) = LOWER(%s))
                ORDER BY updated_at DESC NULLS LAST, created_at DESC
                LIMIT 1
                """,
                (lead_name, lead_city, lead_city),
            )
            row = cursor.fetchone()
            business = dict(row) if row else None

        if business:
            return business
        return None
    finally:
        db.close()


def _create_shadow_business_for_lead(lead: dict[str, Any], user_id: str) -> dict[str, Any]:
    """Create isolated business entity for lead parsing without mixing it into active client list."""
    source_url = str(lead.get("source_url") or "").strip()
    source_external_id = str(
        lead.get("source_external_id")
        or lead.get("google_id")
        or _extract_yandex_org_id_from_url(source_url)
        or ""
    ).strip()
    lead_name = str(lead.get("name") or "Lead without name").strip()[:255]
    lead_city = str(lead.get("city") or "").strip()[:120] or None
    lead_address = str(lead.get("address") or "").strip()[:400] or None
    lead_category = str(lead.get("category") or "").strip()[:120] or None

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'businesses'
            """
        )
        columns = set()
        for row in cur.fetchall():
            if hasattr(row, "get"):
                col = row.get("column_name")
            else:
                col = row[0] if row else None
            if col:
                columns.add(str(col))

        values: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "name": lead_name,
            "owner_id": user_id,
            "description": f"Lead shadow business for outreach lead {lead.get('id')}",
            "industry": lead_category,
            "business_type": lead_category,
            "address": lead_address,
            "city": lead_city,
            "website": (str(lead.get("website") or "").strip() or None),
            "phone": (str(lead.get("phone") or "").strip() or None),
            "email": (str(lead.get("email") or "").strip() or None),
            "yandex_url": source_url or None,
            "moderation_status": LEAD_OUTREACH_MODERATION_STATUS,
            "is_active": True,
        }
        if source_external_id and "yandex_org_id" in columns:
            values["yandex_org_id"] = source_external_id

        fields: list[str] = []
        params: list[Any] = []
        for key, value in values.items():
            if key in columns:
                fields.append(key)
                params.append(value)

        placeholders = ", ".join(["%s"] * len(fields))
        cur.execute(
            f"""
            INSERT INTO businesses ({", ".join(fields)})
            VALUES ({placeholders})
            RETURNING *
            """,
            params,
        )
        row = cur.fetchone()
        conn.commit()
        return dict(row)
    finally:
        conn.close()


def _ensure_parse_business_for_lead(lead: dict[str, Any], user_id: str) -> tuple[dict[str, Any], bool]:
    existing = _find_existing_business_for_lead(lead)
    if existing:
        return existing, False
    created = _create_shadow_business_for_lead(lead, user_id)
    return created, True


def _enqueue_parse_task_for_business(business_id: str, user_id: str, source_url: str) -> dict[str, Any]:
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, status, task_type, source, updated_at, retry_after
            FROM parsequeue
            WHERE business_id = %s
              AND task_type IN ('parse_card', 'sync_yandex_business')
              AND status IN ('pending', 'processing', 'captcha')
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (business_id,),
        )
        active = cur.fetchone()
        if active:
            payload = dict(active)
            payload["existing"] = True
            return payload

        task_id = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO parsequeue (
                id, business_id, task_type, source, status, user_id, url, created_at, updated_at
            )
            VALUES (%s, %s, 'parse_card', 'yandex_maps', 'pending', %s, %s, NOW(), NOW())
            RETURNING id, status, task_type, source, updated_at, retry_after
            """,
            (task_id, business_id, user_id, source_url),
        )
        created = dict(cur.fetchone())
        created["existing"] = False
        conn.commit()
        return created
    finally:
        conn.close()


def _sync_lead_contacts_from_parsed_data(lead: dict[str, Any]) -> dict[str, Any]:
    business_id = str(lead.get("business_id") or "").strip()
    if not business_id:
        return lead

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT phone, site, overview, rating, reviews_count
            FROM cards
            WHERE business_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (business_id,),
        )
        row = cur.fetchone()
        if not row:
            return lead
        card = dict(row)

        overview = card.get("overview")
        if isinstance(overview, str):
            try:
                overview = json.loads(overview)
            except Exception:
                overview = {}
        if not isinstance(overview, dict):
            overview = {}
        parsed = _extract_parsed_contacts(overview)
        updates: dict[str, Any] = {}
        if not str(lead.get("phone") or "").strip() and str(card.get("phone") or "").strip():
            updates["phone"] = str(card.get("phone")).strip()
        if not str(lead.get("website") or "").strip() and str(card.get("site") or "").strip():
            updates["website"] = str(card.get("site")).strip()
        if not str(lead.get("telegram_url") or "").strip() and parsed.get("telegram_url"):
            updates["telegram_url"] = parsed.get("telegram_url")
        if not str(lead.get("whatsapp_url") or "").strip() and parsed.get("whatsapp_url"):
            updates["whatsapp_url"] = parsed.get("whatsapp_url")
        if not str(lead.get("email") or "").strip() and parsed.get("email"):
            updates["email"] = parsed.get("email")
        if (lead.get("rating") is None or str(lead.get("rating")).strip() == "") and card.get("rating") is not None:
            updates["rating"] = card.get("rating")
        if (lead.get("reviews_count") is None or int(lead.get("reviews_count") or 0) == 0) and card.get("reviews_count") is not None:
            updates["reviews_count"] = int(card.get("reviews_count") or 0)
        if parsed.get("social_links"):
            updates["messenger_links_json"] = Json(parsed.get("social_links"))

        if not updates:
            return lead

        assignments = []
        values: list[Any] = []
        for field, value in updates.items():
            assignments.append(f"{field} = %s")
            values.append(value)
        assignments.append("updated_at = NOW()")
        values.append(lead["id"])

        cur.execute(
            f"""
            UPDATE prospectingleads
            SET {', '.join(assignments)}
            WHERE id = %s
            RETURNING *
            """,
            values,
        )
        updated = cur.fetchone()
        if updated:
            conn.commit()
            return dict(updated)
        return lead
    finally:
        conn.close()


def _get_prompt_from_db(prompt_type: str, fallback: str = "") -> str:
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT prompt_text FROM AIPrompts WHERE prompt_type = %s", (prompt_type,))
        row = cur.fetchone()
        if not row:
            return fallback
        if hasattr(row, "get"):
            value = row.get("prompt_text")
        elif isinstance(row, dict):
            value = row.get("prompt_text")
        else:
            value = row[0] if len(row) > 0 else None
        text = str(value or "").strip()
        return text or fallback
    except Exception:
        return fallback
    finally:
        conn.close()


def _extract_json_candidate(raw_text: str) -> dict[str, Any] | None:
    if not isinstance(raw_text, str):
        return None
    text = raw_text.strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    start = text.find("{")
    end = text.rfind("}") + 1
    if start != -1 and end > start:
        try:
            parsed = json.loads(text[start:end])
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return None
    return None


def _classify_reply_outcome(raw_reply: str) -> tuple[str, float]:
    text = (raw_reply or "").strip().lower()
    if not text:
        return "no_response", 0.9

    hard_no_signals = [
        "не интересно",
        "неактуально",
        "не надо",
        "не пишите",
        "удалите",
        "отстаньте",
        "stop",
        "не беспокоить",
    ]
    if any(signal in text for signal in hard_no_signals):
        return "hard_no", 0.9

    question_signals = ["?", "сколько", "как", "что", "подробнее", "цена", "стоимость", "какая"]
    if any(signal in text for signal in question_signals):
        return "question", 0.75

    positive_signals = [
        "интересно",
        "давайте",
        "актуально",
        "хорошо",
        "ок",
        "окей",
        "пришлите",
        "отправьте",
        "можно",
        "свяжитесь",
    ]
    if any(signal in text for signal in positive_signals):
        return "positive", 0.8

    return "question", 0.55


def _classify_reply_outcome_ai(raw_reply: str) -> tuple[str, float, str]:
    raw_reply = str(raw_reply or "").strip()
    if not raw_reply:
        outcome, confidence = _classify_reply_outcome("")
        return outcome, confidence, "heuristic"

    fallback_prompt = (
        "Ты классифицируешь ответ лида на первое аутрич-сообщение.\n"
        "Верни ТОЛЬКО JSON без пояснений.\n"
        "Допустимые значения outcome: positive, question, no_response, hard_no.\n"
        "confidence: число от 0 до 1.\n"
        "Правила:\n"
        "- positive: согласие, интерес, запрос прислать детали, готовность обсудить\n"
        "- question: вопрос, запрос уточнений, цены, условий, деталей\n"
        "- no_response: пустой/неинформативный ответ без явного интереса или отказа\n"
        "- hard_no: отказ, просьба не писать, негатив, stop\n"
        "Формат ответа:\n"
        "{\"outcome\":\"question\",\"confidence\":0.74}\n"
        "Текст ответа лида:\n"
        "{raw_reply}"
    )
    prompt_template = _get_prompt_from_db("outreach_reply_classification", fallback_prompt)
    prompt = prompt_template.replace("{raw_reply}", raw_reply)

    try:
        result_text = analyze_text_with_gigachat(prompt, task_type="ai_agent_marketing")
        parsed = _extract_json_candidate(result_text)
        if not parsed:
            raise ValueError("AI classifier did not return JSON")
        outcome = str(parsed.get("outcome") or "").strip().lower()
        if outcome not in ALLOWED_REPLY_OUTCOMES:
            raise ValueError(f"Unsupported outcome: {outcome}")
        confidence_raw = parsed.get("confidence", 0.7)
        try:
            confidence = float(confidence_raw)
        except Exception:
            confidence = 0.7
        confidence = max(0.0, min(1.0, confidence))
        return outcome, confidence, "ai"
    except Exception as exc:
        print(f"Outreach reply AI classification fallback: {exc}")
        outcome, confidence = _classify_reply_outcome(raw_reply)
        return outcome, confidence, "heuristic"


def _load_send_queue_snapshot():
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                d.id, d.lead_id, d.channel, d.status,
                d.generated_text, d.edited_text, d.approved_text,
                d.created_at, d.updated_at,
                l.name AS lead_name, l.category, l.city, l.selected_channel, l.status AS lead_status
            FROM outreachmessagedrafts d
            JOIN prospectingleads l ON l.id = d.lead_id
            WHERE d.status = %s
              AND NOT EXISTS (
                    SELECT 1
                    FROM outreachsendqueue q
                    WHERE q.draft_id = d.id
              )
            ORDER BY d.updated_at DESC, d.created_at DESC
            """,
            (DRAFT_APPROVED,),
        )
        ready_drafts = [_serialize_draft(dict(row)) for row in cur.fetchall()]

        cur.execute(
            """
            SELECT
                b.id, b.batch_date, b.daily_limit, b.status,
                b.created_by, b.approved_by, b.created_at, b.updated_at
            FROM outreachsendbatches b
            ORDER BY b.batch_date DESC, b.created_at DESC
            LIMIT 20
            """
        )
        batch_rows = [_serialize_batch_row(dict(row)) for row in cur.fetchall()]
        batches_by_id = {row["id"]: row for row in batch_rows}

        if batches_by_id:
            cur.execute(
                """
                SELECT
                    q.id, q.batch_id, q.lead_id, q.draft_id, q.channel,
                    q.delivery_status, q.provider_message_id, q.error_text,
                    q.sent_at, q.attempts, q.last_attempt_at, q.next_retry_at, q.dlq_at,
                    q.created_at, q.updated_at,
                    l.name AS lead_name,
                    d.approved_text, d.generated_text,
                    r.classified_outcome AS latest_outcome,
                    r.human_confirmed_outcome AS latest_human_outcome,
                    r.raw_reply AS latest_raw_reply,
                    r.created_at AS latest_reaction_at
                FROM outreachsendqueue q
                JOIN prospectingleads l ON l.id = q.lead_id
                JOIN outreachmessagedrafts d ON d.id = q.draft_id
                LEFT JOIN LATERAL (
                    SELECT classified_outcome, human_confirmed_outcome, raw_reply, created_at
                    FROM outreachreactions rx
                    WHERE rx.queue_id = q.id
                    ORDER BY rx.created_at DESC
                    LIMIT 1
                ) r ON TRUE
                WHERE q.batch_id = ANY(%s)
                ORDER BY q.created_at ASC
                """,
                (list(batches_by_id.keys()),),
            )
            for row in cur.fetchall():
                payload = dict(row)
                batches_by_id[payload["batch_id"]]["items"].append(payload)

        return {"ready_drafts": ready_drafts, "batches": batch_rows}
    finally:
        conn.close()


def _load_reactions(limit: int = 50):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                r.id, r.queue_id, r.lead_id, r.raw_reply,
                r.classified_outcome, r.confidence, r.human_confirmed_outcome,
                r.note, r.created_by, r.created_at, r.updated_at,
                l.name AS lead_name,
                q.batch_id, q.channel, q.delivery_status
            FROM outreachreactions r
            JOIN prospectingleads l ON l.id = r.lead_id
            JOIN outreachsendqueue q ON q.id = r.queue_id
            ORDER BY r.created_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def _create_send_batch(user_id: str, draft_ids: list[str] | None = None):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        remaining_slots = _remaining_daily_outreach_slots(conn)
        if remaining_slots <= 0:
            return None, f"Daily outreach cap reached ({MAX_DAILY_OUTREACH_BATCH}/day)"

        query = """
            SELECT
                d.id, d.lead_id, d.channel,
                l.status AS lead_status
            FROM outreachmessagedrafts d
            JOIN prospectingleads l ON l.id = d.lead_id
            WHERE d.status = %s
              AND NOT EXISTS (
                    SELECT 1
                    FROM outreachsendqueue q
                    WHERE q.draft_id = d.id
              )
        """
        params: list[Any] = [DRAFT_APPROVED]
        if draft_ids:
            query += " AND d.id = ANY(%s)"
            params.append(draft_ids)
        query += " ORDER BY d.updated_at DESC, d.created_at DESC LIMIT %s"
        params.append(remaining_slots)
        cur.execute(query, params)
        selected_rows = [dict(row) for row in cur.fetchall()]

        if not selected_rows:
            return None, "No approved drafts available for queue"

        batch_id = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO outreachsendbatches (
                id, batch_date, daily_limit, status, created_by
            ) VALUES (
                %s, CURRENT_DATE, %s, %s, %s
            )
            """,
            (batch_id, MAX_DAILY_OUTREACH_BATCH, BATCH_DRAFT, user_id),
        )

        for row in selected_rows:
            queue_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO outreachsendqueue (
                    id, batch_id, lead_id, draft_id, channel, delivery_status
                ) VALUES (
                    %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    queue_id,
                    batch_id,
                    row["lead_id"],
                    row["id"],
                    row["channel"],
                    QUEUE_STATUS_QUEUED,
                ),
            )
            cur.execute(
                """
                UPDATE prospectingleads
                SET status = %s,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (QUEUED_FOR_SEND, row["lead_id"]),
            )

        conn.commit()
        return batch_id, None
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _approve_send_batch(batch_id: str, user_id: str):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE outreachsendbatches
            SET status = %s,
                approved_by = %s,
                updated_at = NOW()
            WHERE id = %s
              AND status = %s
            RETURNING id, batch_date, daily_limit, status, created_by, approved_by, created_at, updated_at
            """,
            (BATCH_APPROVED, user_id, batch_id, BATCH_DRAFT),
        )
        row = cur.fetchone()
        if not row:
            cur.execute(
                """
                SELECT id, batch_date, daily_limit, status, created_by, approved_by, created_at, updated_at
                FROM outreachsendbatches
                WHERE id = %s
                """,
                (batch_id,),
            )
            existing = cur.fetchone()
            if not existing:
                return None, "Batch not found"
            return None, "Batch is not in draft status"
        batch_payload = _serialize_batch_row(dict(row))
        cur.execute(
            """
            SELECT
                q.id
            FROM outreachsendqueue q
            WHERE q.batch_id = %s
            ORDER BY q.created_at ASC
            """,
            (batch_id,),
        )
        queue_rows = [dict(item) for item in cur.fetchall()]
        conn.commit()
        return batch_payload | {"dispatch_summary": {"queued": len(queue_rows), "sent": 0, "failed": 0}}, None
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def dispatch_due_outreach_queue(batch_size: int = 20) -> dict[str, Any]:
    """Фоновый диспетчер outbound-очереди outreach: queued/retry -> sent/retry/dlq."""
    safe_batch_size = max(1, min(int(batch_size or 20), 200))
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            WITH due AS (
                SELECT
                    q.id
                FROM outreachsendqueue q
                JOIN outreachsendbatches b ON b.id = q.batch_id
                WHERE b.status = %s
                  AND (
                    q.delivery_status = %s
                    OR (
                        q.delivery_status = %s
                        AND q.next_retry_at IS NOT NULL
                        AND q.next_retry_at <= NOW()
                    )
                  )
                ORDER BY COALESCE(q.next_retry_at, q.created_at) ASC
                LIMIT %s
                FOR UPDATE SKIP LOCKED
            )
            UPDATE outreachsendqueue q
            SET delivery_status = %s,
                attempts = COALESCE(q.attempts, 0) + 1,
                last_attempt_at = NOW(),
                updated_at = NOW()
            FROM due
            WHERE q.id = due.id
            RETURNING q.id, q.batch_id, q.lead_id, q.draft_id, q.channel, q.delivery_status,
                      q.attempts, q.provider_message_id, q.error_text
            """,
            (
                BATCH_APPROVED,
                QUEUE_STATUS_QUEUED,
                QUEUE_STATUS_RETRY,
                safe_batch_size,
                QUEUE_STATUS_SENDING,
            ),
        )
        claimed = [dict(row) for row in cur.fetchall()]
        if claimed:
            queue_ids = [str(row.get("id") or "") for row in claimed if str(row.get("id") or "")]
            if queue_ids:
                placeholders = ",".join(["%s"] * len(queue_ids))
                cur.execute(
                    f"""
                    SELECT
                        q.id,
                        l.name AS lead_name,
                        l.phone,
                        l.email,
                        l.telegram_url,
                        l.whatsapp_url,
                        l.selected_channel,
                        d.approved_text,
                        d.generated_text
                    FROM outreachsendqueue q
                    LEFT JOIN outreachmessagedrafts d ON d.id = q.draft_id
                    LEFT JOIN prospectingleads l ON l.id = q.lead_id
                    WHERE q.id IN ({placeholders})
                    """,
                    tuple(queue_ids),
                )
                detail_map = {str(row.get("id") or ""): dict(row) for row in cur.fetchall()}
                for row in claimed:
                    row_id = str(row.get("id") or "")
                    details = detail_map.get(row_id) or {}
                    row.update(
                        {
                            "lead_name": details.get("lead_name"),
                            "phone": details.get("phone"),
                            "email": details.get("email"),
                            "telegram_url": details.get("telegram_url"),
                            "whatsapp_url": details.get("whatsapp_url"),
                            "selected_channel": details.get("selected_channel"),
                            "approved_text": details.get("approved_text"),
                            "generated_text": details.get("generated_text"),
                        }
                    )
        conn.commit()

        summary = {
            "success": True,
            "picked": len(claimed),
            "sent": 0,
            "delivered": 0,
            "retry": 0,
            "dlq": 0,
            "failed": 0,
            "results": [],
        }
        if not claimed:
            return summary

        for item in claimed:
            queue_id = str(item.get("id") or "")
            lead_id = str(item.get("lead_id") or "")
            attempt_no = int(item.get("attempts") or 1)
            dispatch_result = _dispatch_outreach_queue_item(item)
            delivery_status = str(dispatch_result.get("delivery_status") or QUEUE_STATUS_FAILED).strip().lower()
            provider_message_id = dispatch_result.get("provider_message_id")
            error_text = str(dispatch_result.get("error_text") or "").strip()[:500] or None

            update_conn = get_db_connection()
            try:
                update_cur = update_conn.cursor()
                if delivery_status in {QUEUE_STATUS_SENT, QUEUE_STATUS_DELIVERED}:
                    update_cur.execute(
                        """
                        UPDATE outreachsendqueue
                        SET delivery_status = %s,
                            provider_message_id = %s,
                            error_text = NULL,
                            sent_at = COALESCE(sent_at, NOW()),
                            next_retry_at = NULL,
                            dlq_at = NULL,
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (delivery_status, provider_message_id, queue_id),
                    )
                    update_cur.execute(
                        """
                        UPDATE prospectingleads
                        SET status = %s,
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        ("sent", lead_id),
                    )
                    if delivery_status == QUEUE_STATUS_DELIVERED:
                        summary["delivered"] += 1
                    else:
                        summary["sent"] += 1
                else:
                    retry_delay = _outreach_retry_delay_for_attempt(attempt_no)
                    exhausted = attempt_no >= OUTREACH_SEND_MAX_ATTEMPTS or retry_delay is None
                    if exhausted:
                        next_status = QUEUE_STATUS_DLQ
                        next_retry_at = None
                        dlq_at_sql = "NOW()"
                        summary["dlq"] += 1
                    else:
                        next_status = QUEUE_STATUS_RETRY
                        next_retry_at = datetime.now(timezone.utc) + retry_delay
                        dlq_at_sql = "NULL"
                        summary["retry"] += 1
                    update_cur.execute(
                        f"""
                        UPDATE outreachsendqueue
                        SET delivery_status = %s,
                            provider_message_id = %s,
                            error_text = %s,
                            next_retry_at = %s,
                            dlq_at = {dlq_at_sql},
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (next_status, provider_message_id, error_text, next_retry_at, queue_id),
                    )
                    update_cur.execute(
                        """
                        UPDATE prospectingleads
                        SET status = %s,
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (CHANNEL_SELECTED, lead_id),
                    )
                    summary["failed"] += 1
                update_conn.commit()
            except Exception:
                update_conn.rollback()
                raise
            finally:
                update_conn.close()

            summary["results"].append(
                {
                    "queue_id": queue_id,
                    "lead_id": lead_id,
                    "channel": item.get("channel"),
                    "attempt_no": attempt_no,
                    "delivery_status": delivery_status,
                    "provider_message_id": provider_message_id,
                    "error_text": error_text,
                }
            )
        return summary
    finally:
        conn.close()


def _extract_telegram_handle(raw_value: str | None) -> str:
    raw = str(raw_value or "").strip()
    if not raw:
        return ""
    if raw.startswith("@"):
        return raw[1:].strip()
    for prefix in ("https://t.me/", "http://t.me/", "https://telegram.me/", "http://telegram.me/"):
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
            break
    raw = raw.strip().strip("/")
    if "/" in raw:
        raw = raw.split("/", 1)[0]
    if "?" in raw:
        raw = raw.split("?", 1)[0]
    return raw.strip().lstrip("@")


def _resolve_outreach_maton_key() -> str:
    return (
        str(os.getenv("MATON_OUTREACH_API_KEY", "") or "").strip()
        or str(os.getenv("MATON_API_KEY", "") or "").strip()
    )


def _resolve_outreach_openclaw_endpoint() -> str:
    return str(os.getenv("OPENCLAW_OUTREACH_SEND_URL", "") or "").strip()


def _resolve_outreach_openclaw_token() -> str:
    return (
        str(os.getenv("OPENCLAW_OUTREACH_TOKEN", "") or "").strip()
        or str(os.getenv("OPENCLAW_LOCALOS_TOKEN", "") or "").strip()
    )


def _is_outreach_openclaw_strict() -> bool:
    return str(os.getenv("OPENCLAW_OUTREACH_STRICT", "") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _resolve_outreach_openclaw_health_endpoint() -> str:
    explicit = str(os.getenv("OPENCLAW_OUTREACH_HEALTH_URL", "") or "").strip()
    if explicit:
        return explicit
    endpoint = _resolve_outreach_openclaw_endpoint()
    if not endpoint:
        return ""
    base = endpoint.split("?", 1)[0].rstrip("/")
    if "/" in base:
        base = base.rsplit("/", 1)[0]
    if base.endswith("/capabilities"):
        base = base.rsplit("/", 1)[0]
    return f"{base}/healthz"


def _resolve_partnership_openclaw_caps_endpoint() -> str:
    return (
        str(os.getenv("OPENCLAW_PARTNERS_CAPS_URL", "") or "").strip()
        or str(os.getenv("OPENCLAW_SANDBOX_BRIDGE_URL", "") or "").strip()
    )


def _resolve_partnership_openclaw_token() -> str:
    return (
        str(os.getenv("OPENCLAW_PARTNERS_TOKEN", "") or "").strip()
        or str(os.getenv("OPENCLAW_SANDBOX_BRIDGE_TOKEN", "") or "").strip()
        or str(os.getenv("OPENCLAW_LOCALOS_TOKEN", "") or "").strip()
    )


def _is_partnership_openclaw_enabled() -> bool:
    value = str(os.getenv("OPENCLAW_PARTNERS_ENABLED", "1") or "1").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _call_partnership_openclaw_capability(
    capability: str,
    *,
    tenant_id: str,
    payload: dict[str, Any],
    timeout_sec: int = 35,
) -> dict[str, Any]:
    endpoint = _resolve_partnership_openclaw_caps_endpoint()
    token = _resolve_partnership_openclaw_token()
    if not endpoint:
        return {"success": False, "error": "OPENCLAW_PARTNERS_CAPS_URL is not configured"}
    if not token:
        return {"success": False, "error": "OPENCLAW_PARTNERS_TOKEN is not configured"}

    base = endpoint.rstrip("/")
    if base.endswith("/capabilities"):
        url = f"{base}/{capability}"
    else:
        url = base

    body = dict(payload or {})
    body.setdefault("tenant_id", tenant_id)

    headers = {
        "Authorization": f"Bearer {token}",
        "X-OpenClaw-Internal-Token": token,
        "X-Tenant-Id": tenant_id,
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(url, json=body, headers=headers, timeout=timeout_sec)
    except Exception as exc:
        return {"success": False, "error": f"OpenClaw request failed: {exc}"}

    try:
        data = response.json() if response.content else {}
    except Exception:
        data = {}

    if response.status_code >= 400:
        return {"success": False, "error": f"OpenClaw HTTP {response.status_code}: {data or response.text}"}

    ok = bool(data.get("success", True) or data.get("ok"))
    return {"success": ok, "data": data, "error": str(data.get("error") or "").strip() or None}


def _dispatch_via_openclaw(item: dict[str, Any], channel: str, message: str) -> dict[str, Any]:
    endpoint = _resolve_outreach_openclaw_endpoint()
    token = _resolve_outreach_openclaw_token()
    if not endpoint:
        return {"success": False, "error": "OPENCLAW_OUTREACH_SEND_URL is not configured"}
    if not token:
        return {"success": False, "error": "OPENCLAW_OUTREACH_TOKEN is not configured"}

    payload = {
        "channel": channel,
        "message": message,
        "lead": {
            "id": item.get("lead_id"),
            "name": item.get("lead_name"),
            "phone": item.get("phone"),
            "email": item.get("email"),
            "telegram_url": item.get("telegram_url"),
            "whatsapp_url": item.get("whatsapp_url"),
        },
        "meta": {
            "queue_id": item.get("id"),
            "batch_id": item.get("batch_id"),
            "draft_id": item.get("draft_id"),
            "source": "localos_outreach",
        },
    }

    try:
        resp = requests.post(
            endpoint,
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=30,
        )
    except Exception as exc:
        return {"success": False, "error": f"OpenClaw request failed: {exc}"}

    try:
        data = resp.json() if resp.content else {}
    except Exception:
        data = {}

    if resp.status_code >= 400:
        return {"success": False, "error": f"OpenClaw HTTP {resp.status_code}: {data or resp.text}"}

    ok = bool(data.get("success") or data.get("ok") or data.get("accepted"))
    if not ok:
        return {"success": False, "error": str(data.get('error') or data or 'OpenClaw delivery failed')}
    provider_id = (
        str(data.get("message_id") or data.get("delivery_id") or data.get("action_id") or "").strip()
        or f"openclaw:{channel}:{item.get('id')}"
    )
    return {"success": True, "provider_message_id": provider_id}


def _dispatch_outreach_queue_item(item: dict[str, Any]) -> dict[str, Any]:
    channel = str(item.get("channel") or item.get("selected_channel") or "").strip().lower()
    message = str(item.get("approved_text") or item.get("generated_text") or "").strip()
    strict_openclaw = _is_outreach_openclaw_strict()
    if not channel:
        return {"delivery_status": QUEUE_STATUS_FAILED, "error_text": "No channel selected"}
    if not message:
        return {"delivery_status": QUEUE_STATUS_FAILED, "error_text": "Draft text is empty"}

    if channel == "manual":
        return {
            "delivery_status": QUEUE_STATUS_DELIVERED,
            "provider_message_id": f"manual:{item.get('id')}",
            "error_text": None,
        }

    if channel == "email":
        return {
            "delivery_status": QUEUE_STATUS_FAILED,
            "error_text": "Email provider is not configured for outreach yet",
        }

    # Runtime-first outbound via OpenClaw for supported machine channels.
    if channel in {"telegram", "whatsapp", "email"}:
        openclaw_result = _dispatch_via_openclaw(item, channel, message)
        if openclaw_result.get("success"):
            return {
                "delivery_status": QUEUE_STATUS_SENT,
                "provider_message_id": str(openclaw_result.get("provider_message_id") or "")[:255] or None,
                "error_text": None,
            }
        if strict_openclaw:
            return {
                "delivery_status": QUEUE_STATUS_FAILED,
                "error_text": f"OpenClaw strict mode: {str(openclaw_result.get('error') or 'delivery failed')[:430]}",
            }
        # fallback to legacy bridge path below if strict mode is disabled.

    maton_key = _resolve_outreach_maton_key()
    if not maton_key:
        return {
            "delivery_status": QUEUE_STATUS_FAILED,
            "error_text": "MATON_OUTREACH_API_KEY is not configured",
        }

    whatsapp_phone = normalize_phone(item.get("whatsapp_url") or item.get("phone"))
    telegram_handle = _extract_telegram_handle(item.get("telegram_url"))
    if channel == "telegram" and not telegram_handle:
        return {
            "delivery_status": QUEUE_STATUS_FAILED,
            "error_text": "Lead has no telegram handle/url",
        }
    if channel == "whatsapp" and not whatsapp_phone:
        return {
            "delivery_status": QUEUE_STATUS_FAILED,
            "error_text": "Lead has no WhatsApp phone",
        }

    response = send_maton_bridge_message(
        maton_key,
        message,
        target_channel=channel,
        business_id="outreach",
        business_name="LocalOS Outreach",
        telegram_handle=telegram_handle or None,
        whatsapp_phone=whatsapp_phone or None,
        metadata={
            "lead_id": item.get("lead_id"),
            "queue_id": item.get("id"),
            "lead_name": item.get("lead_name"),
            "channel": channel,
        },
    )
    if response.get("success"):
        provider_marker = (
            response.get("response_excerpt")
            or f"maton:{channel}:{item.get('id')}"
        )
        return {
            "delivery_status": QUEUE_STATUS_SENT,
            "provider_message_id": str(provider_marker)[:255],
            "error_text": None,
        }
    return {
        "delivery_status": QUEUE_STATUS_FAILED,
        "error_text": str(response.get("error") or "Maton bridge delivery failed")[:500],
        "provider_message_id": None,
    }


@admin_prospecting_bp.route("/api/admin/prospecting/outbound/health", methods=["GET"])
def get_outbound_health():
    """Return outbound runtime bridge health for prospecting dispatch."""
    _, error = _require_superadmin()
    if error:
        return error

    endpoint = _resolve_outreach_openclaw_endpoint()
    health_url = _resolve_outreach_openclaw_health_endpoint()
    token = _resolve_outreach_openclaw_token()
    strict_mode = _is_outreach_openclaw_strict()

    payload: dict[str, Any] = {
        "success": True,
        "strict_openclaw": strict_mode,
        "openclaw": {
            "configured": bool(endpoint and token),
            "endpoint": endpoint or None,
            "health_url": health_url or None,
            "token_configured": bool(token),
            "status": "not_configured",
            "http_status": None,
            "error": None,
        },
        "fallback": {
            "maton_configured": bool(_resolve_outreach_maton_key()),
            "enabled_when_strict_off": not strict_mode,
        },
    }

    if not endpoint or not token:
        return jsonify(payload)

    if not health_url:
        payload["openclaw"]["status"] = "unknown"
        payload["openclaw"]["error"] = "Health URL is not resolvable"
        return jsonify(payload)

    try:
        resp = requests.get(
            health_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=8,
        )
        payload["openclaw"]["http_status"] = resp.status_code
        if resp.status_code < 400:
            payload["openclaw"]["status"] = "ready"
        else:
            payload["openclaw"]["status"] = "degraded"
            payload["openclaw"]["error"] = f"HTTP {resp.status_code}"
    except Exception as exc:
        payload["openclaw"]["status"] = "down"
        payload["openclaw"]["error"] = str(exc)

    return jsonify(payload)


def _update_send_queue_delivery(queue_id: str, delivery_status: str, provider_message_id: str | None, error_text: str | None):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        sent_at_sql = "NOW()" if delivery_status in {QUEUE_STATUS_SENT, QUEUE_STATUS_DELIVERED, QUEUE_STATUS_FAILED} else "NULL"
        cur.execute(
            f"""
            UPDATE outreachsendqueue
            SET delivery_status = %s,
                provider_message_id = %s,
                error_text = %s,
                sent_at = {sent_at_sql},
                updated_at = NOW()
            WHERE id = %s
            RETURNING id, batch_id, lead_id, draft_id, channel, delivery_status,
                      provider_message_id, error_text, sent_at, created_at, updated_at
            """,
            (delivery_status, provider_message_id, error_text, queue_id),
        )
        row = cur.fetchone()
        if not row:
            return None
        payload = dict(row)
        lead_status = "sent" if delivery_status in {QUEUE_STATUS_SENT, QUEUE_STATUS_DELIVERED} else CHANNEL_SELECTED
        cur.execute(
            """
            UPDATE prospectingleads
            SET status = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (lead_status, payload.get("lead_id")),
        )
        conn.commit()
        return payload
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _record_reaction(queue_id: str, raw_reply: str | None, outcome: str | None, note: str | None, user_id: str):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT q.id, q.lead_id, q.delivery_status
            FROM outreachsendqueue q
            WHERE q.id = %s
            """,
            (queue_id,),
        )
        queue_row = cur.fetchone()
        if not queue_row:
            return None, "Queue item not found"

        queue_payload = dict(queue_row)
        if queue_payload.get("delivery_status") == QUEUE_STATUS_FAILED:
            return None, "Cannot attach reaction to failed delivery"

        normalized_outcome = (outcome or "").strip().lower() or None
        if normalized_outcome and normalized_outcome not in ALLOWED_REPLY_OUTCOMES:
            return None, "Outcome must be one of: positive, question, no_response, hard_no"

        classified_outcome, confidence, classifier_source = _classify_reply_outcome_ai(raw_reply or "")
        final_outcome = normalized_outcome or classified_outcome
        note_prefix = f"classifier={classifier_source}"
        note_value = f"{note_prefix}; {note}" if note else note_prefix

        reaction_id = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO outreachreactions (
                id, queue_id, lead_id, raw_reply, classified_outcome,
                confidence, human_confirmed_outcome, note, created_by
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s
            )
            RETURNING id, queue_id, lead_id, raw_reply, classified_outcome,
                      confidence, human_confirmed_outcome, note, created_by, created_at, updated_at
            """,
            (
                reaction_id,
                queue_id,
                queue_payload["lead_id"],
                (raw_reply or "").strip() or None,
                classified_outcome,
                confidence,
                final_outcome,
                note_value,
                user_id,
            ),
        )
        reaction = dict(cur.fetchone())

        next_lead_status = _lead_status_for_outcome(final_outcome)
        cur.execute(
            """
            UPDATE prospectingleads
            SET status = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (next_lead_status, queue_payload["lead_id"]),
        )
        conn.commit()
        return reaction, None
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _delete_outreach_draft(draft_id: str) -> dict[str, Any] | None:
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            DELETE FROM outreachmessagedrafts
            WHERE id = %s
            RETURNING id, lead_id, channel, angle_type, tone, status,
                      generated_text, edited_text, approved_text,
                      learning_note_json, created_at, updated_at
            """,
            (draft_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        conn.commit()
        return dict(row)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _delete_send_queue_item(queue_id: str) -> dict[str, Any] | None:
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            DELETE FROM outreachsendqueue
            WHERE id = %s
            RETURNING id, batch_id, lead_id, draft_id, channel, delivery_status,
                      provider_message_id, error_text, sent_at, created_at, updated_at
            """,
            (queue_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        payload = dict(row)
        cur.execute(
            """
            UPDATE prospectingleads
            SET status = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (CHANNEL_SELECTED, payload.get("lead_id")),
        )
        conn.commit()
        return payload
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _delete_send_batch(batch_id: str) -> dict[str, Any] | None:
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            DELETE FROM outreachsendbatches
            WHERE id = %s
            RETURNING id, batch_date, daily_limit, status, created_by, approved_by, created_at, updated_at
            """,
            (batch_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        conn.commit()
        return dict(row)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _cleanup_test_send_batches() -> dict[str, int]:
    """Remove batches in draft state and their queue rows (test/abandoned batches)."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id
            FROM outreachsendbatches
            WHERE status = %s
            """,
            (BATCH_DRAFT,),
        )
        batch_ids = [str((row.get("id") if hasattr(row, "get") else row[0])) for row in (cur.fetchall() or [])]
        if not batch_ids:
            return {"deleted_batches": 0, "deleted_queue_items": 0}

        cur.execute(
            """
            DELETE FROM outreachsendqueue
            WHERE batch_id = ANY(%s)
            RETURNING id
            """,
            (batch_ids,),
        )
        deleted_queue = len(cur.fetchall() or [])
        cur.execute(
            """
            DELETE FROM outreachsendbatches
            WHERE id = ANY(%s)
            RETURNING id
            """,
            (batch_ids,),
        )
        deleted_batches = len(cur.fetchall() or [])
        conn.commit()
        return {"deleted_batches": deleted_batches, "deleted_queue_items": deleted_queue}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _lead_status_for_outcome(outcome: str | None) -> str:
    return {
        "positive": "responded",
        "question": "responded",
        "hard_no": "closed_negative",
        "no_response": "closed_no_response",
    }.get(outcome or "", "responded")


def _confirm_reaction(reaction_id: str, outcome: str, note: str | None, user_id: str):
    normalized_outcome = (outcome or "").strip().lower()
    if normalized_outcome not in ALLOWED_REPLY_OUTCOMES:
        return None, "Outcome must be one of: positive, question, no_response, hard_no"

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT r.id, r.lead_id, r.note
            FROM outreachreactions r
            WHERE r.id = %s
            """,
            (reaction_id,),
        )
        row = cur.fetchone()
        if not row:
            return None, "Reaction not found"

        payload = dict(row)
        note_parts = []
        if payload.get("note"):
            note_parts.append(str(payload["note"]).strip())
        note_parts.append(f"human_override={normalized_outcome}")
        note_parts.append(f"confirmed_by={user_id}")
        if note:
            note_parts.append(note)
        note_value = "; ".join(part for part in note_parts if part)

        cur.execute(
            """
            UPDATE outreachreactions
            SET human_confirmed_outcome = %s,
                note = %s,
                updated_at = NOW()
            WHERE id = %s
            RETURNING id, queue_id, lead_id, raw_reply, classified_outcome,
                      confidence, human_confirmed_outcome, note, created_by, created_at, updated_at
            """,
            (normalized_outcome, note_value, reaction_id),
        )
        reaction = dict(cur.fetchone())

        cur.execute(
            """
            UPDATE prospectingleads
            SET status = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (_lead_status_for_outcome(normalized_outcome), payload["lead_id"]),
        )
        conn.commit()
        return reaction, None
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@admin_prospecting_bp.route("/api/admin/prospecting/search", methods=["POST"])
def search_businesses():
    """Queue Yandex prospecting search via Apify."""
    user_data, error = _require_superadmin()
    if error:
        return error

    _expire_stale_search_jobs()
    data = request.get_json(silent=True) or {}
    query = (data.get("query") or "").strip()
    location = (data.get("location") or "").strip()
    search_limit = int(data.get("limit", 50) or 50)

    if not query or not location:
        return jsonify({"error": "Query and location are required"}), 400
    if search_limit < 1:
        return jsonify({"error": "Limit must be positive"}), 400
    search_limit = min(search_limit, 200)

    service = ProspectingService()
    if not service.client:
        return jsonify({"error": "APIFY_TOKEN is not configured"}), 500

    try:
        job_id = _create_search_job(
            query=query,
            location=location,
            search_limit=search_limit,
            actor_id=service.actor_id,
            user_id=user_data["user_id"],
        )
        worker = threading.Thread(
            target=_run_search_job,
            args=(job_id, query, location, search_limit),
            daemon=True,
            name=f"outreach-search-{job_id}",
        )
        worker.start()
        return (
            jsonify(
                {
                    "success": True,
                    "job_id": job_id,
                    "status": "queued",
                    "source": "apify_yandex",
                    "actor_id": service.actor_id,
                }
            ),
            202,
        )
    except Exception as e:
        print(f"Error queueing prospecting search: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/admin/prospecting/search-job/<string:job_id>", methods=["GET"])
def get_search_job_status(job_id):
    """Get async search job status and results."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        row = _get_search_job(job_id)
        if not row:
            return jsonify({"error": "Search job not found"}), 404
        row = _mark_search_job_failed_if_stale(dict(row))
        raw_results = row.get("results_json")
        apify_status = None
        results_payload = []
        if isinstance(raw_results, list):
            results_payload = raw_results
        elif isinstance(raw_results, dict):
            apify_status = ((raw_results.get("_apify") or {}).get("status") if isinstance(raw_results.get("_apify"), dict) else None)
        return jsonify(
            {
                "success": True,
                "job": {
                    "id": row.get("id"),
                    "source": row.get("source"),
                    "actor_id": row.get("actor_id"),
                    "query": row.get("query"),
                    "location": row.get("location"),
                    "limit": row.get("search_limit"),
                    "status": row.get("status"),
                    "result_count": row.get("result_count") or 0,
                    "apify_status": apify_status,
                    "error_text": row.get("error_text"),
                    "results": results_payload,
                    "created_at": row.get("created_at"),
                    "updated_at": row.get("updated_at"),
                    "completed_at": row.get("completed_at"),
                },
            }
        )
    except Exception as e:
        print(f"Error getting prospecting search job: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/admin/prospecting/leads", methods=["GET"])
def get_leads():
    """Get all saved leads."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        filters = {
            "category": (request.args.get("category") or "").strip() or None,
            "city": (request.args.get("city") or "").strip() or None,
            "status": (request.args.get("status") or "").strip() or None,
            "min_rating": float(request.args.get("min_rating")) if request.args.get("min_rating") not in {None, ""} else None,
            "max_rating": float(request.args.get("max_rating")) if request.args.get("max_rating") not in {None, ""} else None,
            "min_reviews": int(request.args.get("min_reviews")) if request.args.get("min_reviews") not in {None, ""} else None,
            "max_reviews": int(request.args.get("max_reviews")) if request.args.get("max_reviews") not in {None, ""} else None,
            "has_website": _to_bool_filter(request.args.get("has_website")),
            "has_phone": _to_bool_filter(request.args.get("has_phone")),
            "has_email": _to_bool_filter(request.args.get("has_email")),
            "has_messengers": _to_bool_filter(request.args.get("has_messengers")),
        }
        with DatabaseManager() as db:
            leads = db.get_all_leads()
        normalized = []
        for lead in leads:
            display_lead = _normalize_lead_for_display(lead)
            if not display_lead:
                continue
            normalized.append(display_lead)
        filtered = [lead for lead in normalized if _lead_matches_filters(lead, filters)]
        return jsonify({"leads": filtered, "count": len(filtered)})
    except Exception as e:
        print(f"Error getting leads: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/admin/prospecting/save", methods=["POST"])
def save_lead():
    """Save a lead to database."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        lead_data = data.get("lead")

        if not lead_data:
            return jsonify({"error": "Lead data is required"}), 400

        lead_data.setdefault("source", "apify_yandex")
        lead_data.setdefault("source_external_id", lead_data.get("google_id"))
        lead_data.setdefault("status", "new")

        with DatabaseManager() as db:
            lead_id = db.save_lead(lead_data)

        return jsonify({"success": True, "lead_id": lead_id})
    except Exception as e:
        print(f"Error saving lead: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/admin/prospecting/import", methods=["POST"])
def import_leads():
    """Bulk import leads from external JSON payload (e.g. manual Apify export)."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        data = request.get_json(silent=True)
        if isinstance(data, list):
            raw_items = data
        else:
            payload = data or {}
            raw_items = (
                payload.get("items")
                or payload.get("results")
                or payload.get("leads")
                or []
            )

        if not isinstance(raw_items, list) or not raw_items:
            return jsonify({"error": "Items array is required"}), 400

        service = ProspectingService()
        normalized = service.normalize_results(raw_items)
        if not normalized:
            return jsonify({"error": "No valid lead items to import"}), 400

        imported_ids: list[str] = []
        with DatabaseManager() as db:
            for lead_data in normalized:
                lead_data.setdefault("source", "external_import")
                lead_data.setdefault("status", "new")
                lead_data.setdefault("source_external_id", lead_data.get("source_external_id") or lead_data.get("google_id"))
                imported_ids.append(db.save_lead(lead_data))

        return jsonify({
            "success": True,
            "imported_count": len(imported_ids),
            "skipped_count": max(0, len(raw_items) - len(normalized)),
            "lead_ids": imported_ids,
        })
    except Exception as e:
        print(f"Error importing leads: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/partnership/leads/import-links", methods=["POST"])
def partnership_import_links():
    """User-level import of partnership candidates via direct map links."""
    user_data, error = _require_auth()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        links = data.get("links") or []
        requested_business_id = str(data.get("business_id") or "").strip() or None
        default_city = str(data.get("city") or "").strip()
        default_category = str(data.get("category") or "").strip()
        if not isinstance(links, list) or not links:
            return jsonify({"error": "links array is required"}), 400

        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            cur = conn.cursor()
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403

            imported_ids: list[str] = []
            skipped = 0
            for raw_link in links:
                source_url = str(raw_link or "").strip()
                if not source_url:
                    continue
                lead_id, created = _insert_partnership_lead_if_new(
                    cur,
                    business_id=business_id,
                    created_by=user_data["user_id"],
                    source_url=source_url,
                    name="Новый партнёр",
                    city=default_city or None,
                    category=default_category or None,
                    source="manual_link",
                )
                if not created:
                    skipped += 1
                    continue
                if lead_id:
                    imported_ids.append(lead_id)
            conn.commit()
        finally:
            conn.close()

        return jsonify(
            {
                "success": True,
                "imported_count": len(imported_ids),
                "skipped_count": skipped,
                "lead_ids": imported_ids,
            }
        )
    except Exception as e:
        print(f"Error importing partnership links: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/partnership/geo-search", methods=["POST"])
def partnership_geo_search():
    """OpenClaw geo-search import for partnership leads (P8 baseline)."""
    user_data, error = _require_auth()
    if error:
        return error

    if not _is_partnership_openclaw_enabled():
        return jsonify({"error": "OpenClaw partnership integration is disabled"}), 400

    try:
        data = request.get_json(silent=True) or {}
        requested_business_id = str(data.get("business_id") or "").strip() or None
        city = str(data.get("city") or "").strip()
        category = str(data.get("category") or "").strip()
        query = str(data.get("query") or "").strip()
        radius_km = int(data.get("radius_km") or 5)
        limit = int(data.get("limit") or 25)
        radius_km = max(1, min(radius_km, 100))
        limit = max(1, min(limit, 200))
        if not city and not query:
            return jsonify({"error": "city or query is required"}), 400

        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            cur = conn.cursor()
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403
            cap_payload = {
                "query": query,
                "city": city,
                "category": category,
                "radius_km": radius_km,
                "limit": limit,
                "intent": "partnership_outreach",
                "business_id": business_id,
            }
            openclaw_result = _call_partnership_openclaw_capability(
                "partners.search_geo",
                tenant_id=business_id,
                payload=cap_payload,
                timeout_sec=60,
            )
            if not openclaw_result.get("success"):
                return jsonify({"error": str(openclaw_result.get("error") or "OpenClaw geo-search failed")}), 502

            data_blob = openclaw_result.get("data") or {}
            result_blob = data_blob.get("result") if isinstance(data_blob, dict) else {}
            candidates = (
                (result_blob.get("items") if isinstance(result_blob, dict) else None)
                or (data_blob.get("items") if isinstance(data_blob, dict) else None)
                or []
            )
            if not isinstance(candidates, list):
                candidates = []

            imported_ids: list[str] = []
            skipped = 0
            for item in candidates:
                if not isinstance(item, dict):
                    continue
                source_url = str(item.get("source_url") or item.get("url") or item.get("maps_url") or "").strip()
                lead_name = str(item.get("name") or item.get("title") or "Новый партнёр").strip()
                lead_city = str(item.get("city") or city or "").strip() or None
                lead_category = str(item.get("category") or category or "").strip() or None
                phone = str(item.get("phone") or "").strip() or None
                email = str(item.get("email") or "").strip() or None
                website = str(item.get("website") or item.get("website_url") or "").strip() or None
                telegram_url = str(item.get("telegram_url") or "").strip() or None
                whatsapp_url = str(item.get("whatsapp_url") or "").strip() or None
                try:
                    rating = float(item.get("rating")) if item.get("rating") is not None else None
                except Exception:
                    rating = None
                try:
                    reviews_count = int(item.get("reviews_count")) if item.get("reviews_count") is not None else None
                except Exception:
                    reviews_count = None
                lead_id, created = _insert_partnership_lead_if_new(
                    cur,
                    business_id=business_id,
                    created_by=user_data["user_id"],
                    source_url=source_url,
                    name=lead_name,
                    city=lead_city,
                    category=lead_category,
                    source="openclaw_geo",
                    phone=phone,
                    email=email,
                    website=website,
                    telegram_url=telegram_url,
                    whatsapp_url=whatsapp_url,
                    rating=rating,
                    reviews_count=reviews_count,
                )
                if created:
                    if lead_id:
                        imported_ids.append(lead_id)
                else:
                    skipped += 1
            conn.commit()
        finally:
            conn.close()

        return jsonify(
            {
                "success": True,
                "imported_count": len(imported_ids),
                "skipped_count": skipped,
                "lead_ids": imported_ids,
                "source_total": len(candidates),
            }
        )
    except Exception as e:
        print(f"Error partnership geo search: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/partnership/leads", methods=["GET"])
def partnership_list_leads():
    """User-level list of partnership leads for one business."""
    user_data, error = _require_auth()
    if error:
        return error

    try:
        requested_business_id = str(request.args.get("business_id") or "").strip() or None
        stage_filter = str(request.args.get("stage") or "").strip().lower() or None
        q = str(request.args.get("q") or "").strip().lower()
        limit = max(1, min(int(request.args.get("limit") or 100), 500))
        offset = max(0, int(request.args.get("offset") or 0))

        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            cur = conn.cursor()
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403

            where_sql = [
                "business_id = %s",
                "COALESCE(intent, 'client_outreach') = 'partnership_outreach'",
            ]
            params: list[Any] = [business_id]
            if stage_filter:
                where_sql.append("COALESCE(partnership_stage, 'imported') = %s")
                params.append(stage_filter)
            if q:
                where_sql.append("(LOWER(COALESCE(name, '')) LIKE %s OR LOWER(COALESCE(source_url, '')) LIKE %s)")
                q_like = f"%{q}%"
                params.extend([q_like, q_like])

            cur.execute(
                f"""
                SELECT id, name, address, city, category, source_url, source, phone, email,
                       telegram_url, whatsapp_url, website, rating, reviews_count,
                       status, selected_channel, intent, partnership_stage, updated_at, created_at
                FROM prospectingleads
                WHERE {' AND '.join(where_sql)}
                ORDER BY updated_at DESC NULLS LAST, created_at DESC
                LIMIT %s OFFSET %s
                """,
                (*params, limit, offset),
            )
            rows = cur.fetchall()
        finally:
            conn.close()

        items = [dict(r) if hasattr(r, "keys") else {} for r in rows]
        return jsonify({"success": True, "count": len(items), "items": items})
    except Exception as e:
        print(f"Error listing partnership leads: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/partnership/leads/<string:lead_id>", methods=["PATCH"])
def partnership_update_lead(lead_id):
    """User-level stage update for partnership lead."""
    user_data, error = _require_auth()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        requested_business_id = str(data.get("business_id") or "").strip() or None
        stage = str(data.get("partnership_stage") or "").strip().lower()
        status = str(data.get("status") or "").strip().lower()
        selected_channel = str(data.get("selected_channel") or "").strip().lower() or None
        if not stage and not status and selected_channel is None:
            return jsonify({"error": "Nothing to update"}), 400

        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            cur = conn.cursor()
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403

            assignments = ["updated_at = NOW()"]
            params: list[Any] = []
            if stage:
                assignments.append("partnership_stage = %s")
                params.append(stage)
            if status:
                assignments.append("status = %s")
                params.append(status)
            if selected_channel is not None:
                assignments.append("selected_channel = %s")
                params.append(selected_channel)

            params.extend([lead_id, business_id])
            cur.execute(
                f"""
                UPDATE prospectingleads
                SET {', '.join(assignments)}
                WHERE id = %s
                  AND business_id = %s
                  AND COALESCE(intent, 'client_outreach') = 'partnership_outreach'
                RETURNING id, name, source_url, status, selected_channel, partnership_stage, updated_at
                """,
                tuple(params),
            )
            updated = cur.fetchone()
            if not updated:
                return jsonify({"error": "Lead not found"}), 404
            conn.commit()
        finally:
            conn.close()

        return jsonify({"success": True, "item": dict(updated) if hasattr(updated, "keys") else updated})
    except Exception as e:
        print(f"Error updating partnership lead: {e}")
        return jsonify({"error": str(e)}), 500


def _ensure_partnership_artifacts_table(conn) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS partnershipleadartifacts (
            lead_id TEXT PRIMARY KEY REFERENCES prospectingleads(id) ON DELETE CASCADE,
            audit_json JSONB,
            match_json JSONB,
            offer_draft_json JSONB,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )


def _load_partnership_lead(cur, *, lead_id: str, business_id: str):
    cur.execute(
        """
        SELECT *
        FROM prospectingleads
        WHERE id = %s
          AND business_id = %s
          AND COALESCE(intent, 'client_outreach') = 'partnership_outreach'
        LIMIT 1
        """,
        (lead_id, business_id),
    )
    row = cur.fetchone()
    return dict(row) if row and hasattr(row, "keys") else None


def _collect_business_service_names(cur, business_id: str) -> list[str]:
    cur.execute(
        """
        SELECT name
        FROM userservices
        WHERE business_id = %s
          AND (is_active IS TRUE OR is_active IS NULL)
          AND COALESCE(TRIM(name), '') <> ''
        ORDER BY updated_at DESC NULLS LAST, created_at DESC
        LIMIT 200
        """,
        (business_id,),
    )
    rows = cur.fetchall()
    result: list[str] = []
    for row in rows:
        if hasattr(row, "get"):
            value = row.get("name")
        else:
            value = row[0] if row else None
        text = str(value or "").strip()
        if text:
            result.append(text)
    return result


def _tokenize_match_text(text: str) -> set[str]:
    import re
    return {t.lower() for t in re.findall(r"[a-zA-Zа-яА-ЯёЁ0-9]{4,}", str(text or ""))}


def _extract_partner_service_names_from_snapshot(snapshot: dict[str, Any]) -> list[str]:
    services_preview = snapshot.get("services_preview") if isinstance(snapshot, dict) else []
    if not isinstance(services_preview, list):
        return []
    names: list[str] = []
    for item in services_preview:
        if not isinstance(item, dict):
            continue
        current_name = str(item.get("current_name") or "").strip()
        if current_name:
            names.append(current_name)
    return names


def _extract_openclaw_result_blob(resp: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(resp, dict):
        return {}
    data = resp.get("data")
    if not isinstance(data, dict):
        return {}
    result = data.get("result")
    if isinstance(result, dict):
        return result
    return data


@admin_prospecting_bp.route("/api/partnership/leads/<string:lead_id>/audit", methods=["POST"])
def partnership_audit_lead(lead_id):
    user_data, error = _require_auth()
    if error:
        return error
    try:
        data = request.get_json(silent=True) or {}
        requested_business_id = str(data.get("business_id") or "").strip() or None
        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            _ensure_partnership_artifacts_table(conn)
            cur = conn.cursor()
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403
            lead = _load_partnership_lead(cur, lead_id=lead_id, business_id=business_id)
            if not lead:
                return jsonify({"error": "Lead not found"}), 404

            snapshot: dict[str, Any] | None = None
            if _is_partnership_openclaw_enabled():
                openclaw_result = _call_partnership_openclaw_capability(
                    "partners.audit_card",
                    tenant_id=business_id,
                    payload={
                        "business_id": business_id,
                        "lead_id": lead_id,
                        "lead": lead,
                        "intent": "partnership_outreach",
                    },
                    timeout_sec=40,
                )
                if openclaw_result.get("success"):
                    result_blob = _extract_openclaw_result_blob(openclaw_result)
                    candidate_snapshot = result_blob.get("snapshot")
                    if isinstance(candidate_snapshot, dict) and candidate_snapshot:
                        snapshot = candidate_snapshot
            if not snapshot:
                snapshot = build_lead_card_preview_snapshot(lead)
            cur.execute(
                """
                INSERT INTO partnershipleadartifacts (lead_id, audit_json, updated_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (lead_id) DO UPDATE
                SET audit_json = EXCLUDED.audit_json,
                    updated_at = NOW()
                """,
                (lead_id, Json(snapshot)),
            )
            cur.execute(
                """
                UPDATE prospectingleads
                SET partnership_stage = %s,
                    status = %s,
                    updated_at = NOW()
                WHERE id = %s
                """,
                ("audited", "audited", lead_id),
            )
            conn.commit()
        finally:
            conn.close()
        return jsonify({"success": True, "snapshot": snapshot})
    except Exception as e:
        print(f"Error partnership audit lead: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/partnership/leads/<string:lead_id>/match", methods=["POST"])
def partnership_match_lead(lead_id):
    user_data, error = _require_auth()
    if error:
        return error
    try:
        data = request.get_json(silent=True) or {}
        requested_business_id = str(data.get("business_id") or "").strip() or None
        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            _ensure_partnership_artifacts_table(conn)
            cur = conn.cursor()
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403
            lead = _load_partnership_lead(cur, lead_id=lead_id, business_id=business_id)
            if not lead:
                return jsonify({"error": "Lead not found"}), 404

            cur.execute("SELECT audit_json FROM partnershipleadartifacts WHERE lead_id = %s", (lead_id,))
            artifact_row = cur.fetchone()
            audit_json = {}
            if artifact_row:
                audit_json = artifact_row["audit_json"] if hasattr(artifact_row, "get") else artifact_row[0]
            if not isinstance(audit_json, dict) or not audit_json:
                audit_json = build_lead_card_preview_snapshot(lead)

            own_services = _collect_business_service_names(cur, business_id)
            partner_services = _extract_partner_service_names_from_snapshot(audit_json)
            match_result: dict[str, Any] | None = None
            if _is_partnership_openclaw_enabled():
                openclaw_result = _call_partnership_openclaw_capability(
                    "partners.match_services",
                    tenant_id=business_id,
                    payload={
                        "business_id": business_id,
                        "lead_id": lead_id,
                        "intent": "partnership_outreach",
                        "our_services": own_services,
                        "partner_services": partner_services,
                        "audit_snapshot": audit_json,
                    },
                    timeout_sec=40,
                )
                if openclaw_result.get("success"):
                    result_blob = _extract_openclaw_result_blob(openclaw_result)
                    candidate_match = result_blob.get("match")
                    if isinstance(candidate_match, dict) and candidate_match:
                        match_result = candidate_match

            if not match_result:
                own_tokens = _tokenize_match_text(" ".join(own_services))
                partner_tokens = _tokenize_match_text(" ".join(partner_services))
                overlap_tokens = sorted(list(own_tokens & partner_tokens))
                own_unique = sorted(list(own_tokens - partner_tokens))
                partner_unique = sorted(list(partner_tokens - own_tokens))

                denominator = max(1, len(own_tokens | partner_tokens))
                score = int(round((len(overlap_tokens) / denominator) * 100))
                match_result = {
                    "match_score": score,
                    "overlap": overlap_tokens[:30],
                    "complement": {
                        "our_strength_tokens": own_unique[:30],
                        "partner_strength_tokens": partner_unique[:30],
                    },
                    "risks": [
                        "Низкая точность, если у партнёра мало структурированных услуг."
                        if not partner_services
                        else "Проверьте каннибализацию по пересекающимся услугам."
                    ],
                    "offer_angles": [
                        "Кросс-рекомендации по непересекающимся услугам",
                        "Пакетные предложения с взаимной скидкой",
                        "Совместный контент/новости для карт и соцсетей",
                    ],
                    "source_counts": {
                        "our_services": len(own_services),
                        "partner_services": len(partner_services),
                    },
                }

            cur.execute(
                """
                INSERT INTO partnershipleadartifacts (lead_id, audit_json, match_json, updated_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (lead_id) DO UPDATE
                SET audit_json = EXCLUDED.audit_json,
                    match_json = EXCLUDED.match_json,
                    updated_at = NOW()
                """,
                (lead_id, Json(audit_json), Json(match_result)),
            )
            cur.execute(
                """
                UPDATE prospectingleads
                SET partnership_stage = %s,
                    status = %s,
                    updated_at = NOW()
                WHERE id = %s
                """,
                ("matched", "matched", lead_id),
            )
            conn.commit()
        finally:
            conn.close()
        return jsonify({"success": True, "result": match_result})
    except Exception as e:
        print(f"Error partnership match lead: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/partnership/leads/<string:lead_id>/draft-offer", methods=["POST"])
def partnership_draft_offer(lead_id):
    user_data, error = _require_auth()
    if error:
        return error
    try:
        data = request.get_json(silent=True) or {}
        requested_business_id = str(data.get("business_id") or "").strip() or None
        tone = str(data.get("tone") or "профессиональный").strip()
        channel = str(data.get("channel") or "telegram").strip().lower()
        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            _ensure_partnership_artifacts_table(conn)
            cur = conn.cursor()
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403
            lead = _load_partnership_lead(cur, lead_id=lead_id, business_id=business_id)
            if not lead:
                return jsonify({"error": "Lead not found"}), 404

            cur.execute("SELECT match_json FROM partnershipleadartifacts WHERE lead_id = %s", (lead_id,))
            row = cur.fetchone()
            match_json = row["match_json"] if row and hasattr(row, "get") else (row[0] if row else {})
            if not isinstance(match_json, dict):
                match_json = {}

            draft_text: str | None = None
            if _is_partnership_openclaw_enabled():
                openclaw_result = _call_partnership_openclaw_capability(
                    "partners.draft_first_offer",
                    tenant_id=business_id,
                    payload={
                        "business_id": business_id,
                        "lead_id": lead_id,
                        "intent": "partnership_outreach",
                        "lead": lead,
                        "match": match_json,
                        "tone": tone,
                        "channel": channel,
                    },
                    timeout_sec=40,
                )
                if openclaw_result.get("success"):
                    result_blob = _extract_openclaw_result_blob(openclaw_result)
                    candidate_text = str(result_blob.get("text") or result_blob.get("draft_text") or "").strip()
                    if candidate_text:
                        draft_text = candidate_text

            if not draft_text:
                lead_name = str(lead.get("name") or "коллеги").strip()
                city = str(lead.get("city") or "").strip()
                overlap = match_json.get("overlap") or []
                complement = ((match_json.get("complement") or {}).get("partner_strength_tokens") or [])
                opener = f"Здравствуйте! Мы посмотрели вашу карточку на картах и видим потенциал для партнёрства."
                if city:
                    opener += f" Работаем рядом в {city}."
                value_line = "Можем предложить кросс-рекомендации и совместные офферы для обмена клиентским потоком."
                if overlap:
                    value_line += f" Уже есть пересечения по темам: {', '.join(overlap[:5])}."
                if complement:
                    value_line += f" И есть комплементарные направления: {', '.join(complement[:5])}."
                draft_text = "\n".join(
                    [
                        opener,
                        value_line,
                        "Если вам интересно, подготовим короткий план пилота на 2 недели с метриками и прозрачной механикой.",
                        "Готовы обсудить удобный формат созвона/чата?",
                    ]
                ).strip()

            draft_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO outreachmessagedrafts (
                    id, lead_id, channel, angle_type, tone, status,
                    generated_text, edited_text, learning_note_json, created_by, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, NOW(), NOW()
                )
                """,
                (
                    draft_id,
                    lead_id,
                    channel,
                    "partnership_offer",
                    tone,
                    DRAFT_GENERATED,
                    draft_text,
                    draft_text,
                    Json({"intent": "partnership_outreach", "auto_generated": True}),
                    user_data["user_id"],
                ),
            )
            cur.execute(
                """
                INSERT INTO partnershipleadartifacts (lead_id, offer_draft_json, updated_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (lead_id) DO UPDATE
                SET offer_draft_json = EXCLUDED.offer_draft_json,
                    updated_at = NOW()
                """,
                (lead_id, Json({"draft_id": draft_id, "text": draft_text, "channel": channel, "tone": tone})),
            )
            cur.execute(
                """
                UPDATE prospectingleads
                SET partnership_stage = %s,
                    status = %s,
                    selected_channel = %s,
                    updated_at = NOW()
                WHERE id = %s
                """,
                ("proposal_draft_ready", "proposal_draft_ready", channel, lead_id),
            )
            conn.commit()
        finally:
            conn.close()

        try:
            record_ai_learning_event(
                capability="partnership.draft_offer",
                event_type="generated",
                intent="partnership_outreach",
                user_id=user_data.get("user_id"),
                business_id=business_id,
                draft_text="",
                final_text=draft_text[:3000],
                metadata={"lead_id": lead_id, "draft_id": draft_id, "channel": channel},
            )
        except Exception as learning_exc:
            print(f"⚠️ partnership.draft_offer learning skipped: {learning_exc}")

        return jsonify({"success": True, "draft_id": draft_id, "text": draft_text, "channel": channel})
    except Exception as e:
        print(f"Error partnership draft offer: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/partnership/drafts", methods=["GET"])
def partnership_list_drafts():
    """User-level list of partnership outreach drafts."""
    user_data, error = _require_auth()
    if error:
        return error
    try:
        requested_business_id = str(request.args.get("business_id") or "").strip() or None
        status_filter = str(request.args.get("status") or "").strip().lower() or None
        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            cur = conn.cursor()
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403

            query = """
                SELECT
                    d.id, d.lead_id, d.channel, d.angle_type, d.tone, d.status,
                    d.generated_text, d.edited_text, d.approved_text,
                    d.learning_note_json, d.created_at, d.updated_at,
                    l.name AS lead_name, l.category, l.city, l.selected_channel, l.status AS lead_status
                FROM outreachmessagedrafts d
                JOIN prospectingleads l ON l.id = d.lead_id
                WHERE l.business_id = %s
                  AND COALESCE(l.intent, 'client_outreach') = 'partnership_outreach'
            """
            params: list[Any] = [business_id]
            if status_filter:
                query += " AND d.status = %s"
                params.append(status_filter)
            query += " ORDER BY d.updated_at DESC, d.created_at DESC LIMIT 200"
            cur.execute(query, tuple(params))
            rows = [_serialize_draft(dict(row)) for row in cur.fetchall()]
        finally:
            conn.close()
        return jsonify({"success": True, "drafts": rows, "count": len(rows)})
    except Exception as e:
        print(f"Error listing partnership drafts: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/partnership/drafts/<string:draft_id>/approve", methods=["POST"])
def partnership_approve_draft(draft_id):
    """User-level approval for partnership draft."""
    user_data, error = _require_auth()
    if error:
        return error
    try:
        data = request.get_json(silent=True) or {}
        requested_business_id = str(data.get("business_id") or "").strip() or None
        approved_text = str(data.get("approved_text") or "").strip()
        if not approved_text:
            return jsonify({"error": "approved_text is required"}), 400

        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            ensure_ai_learning_events_table(conn)
            cur = conn.cursor()
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403
            cur.execute(
                """
                SELECT d.id, d.lead_id, d.generated_text, d.edited_text, d.status
                FROM outreachmessagedrafts d
                JOIN prospectingleads l ON l.id = d.lead_id
                WHERE d.id = %s
                  AND l.business_id = %s
                  AND COALESCE(l.intent, 'client_outreach') = 'partnership_outreach'
                LIMIT 1
                """,
                (draft_id, business_id),
            )
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Draft not found"}), 404
            draft_row = dict(row) if hasattr(row, "keys") else {
                "id": row[0], "lead_id": row[1], "generated_text": row[2], "edited_text": row[3], "status": row[4]
            }

            edited_text = str(draft_row.get("edited_text") or "")
            generated_text = str(draft_row.get("generated_text") or "")
            edited_before_accept = approved_text != generated_text

            cur.execute(
                """
                UPDATE outreachmessagedrafts
                SET approved_text = %s,
                    status = %s,
                    learning_note_json = %s,
                    updated_at = NOW()
                WHERE id = %s
                RETURNING id, lead_id, channel, angle_type, tone, status,
                          generated_text, edited_text, approved_text,
                          learning_note_json, created_at, updated_at
                """,
                (
                    approved_text,
                    DRAFT_APPROVED,
                    Json({"intent": "partnership_outreach"}),
                    draft_id,
                ),
            )
            updated = cur.fetchone()
            cur.execute(
                """
                UPDATE prospectingleads
                SET status = %s,
                    partnership_stage = %s,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (DRAFT_APPROVED, "proposal_approved", draft_row["lead_id"]),
            )
            record_ai_learning_event(
                capability="partnership.draft_offer",
                event_type="accepted",
                intent="partnership_outreach",
                user_id=user_data.get("user_id"),
                business_id=business_id,
                accepted=True,
                edited_before_accept=edited_before_accept,
                draft_text=generated_text[:3000] if generated_text else None,
                final_text=approved_text[:3000],
                metadata={"draft_id": draft_id, "lead_id": draft_row["lead_id"]},
                conn=conn,
            )
            conn.commit()
        finally:
            conn.close()

        payload = dict(updated) if hasattr(updated, "keys") else updated
        return jsonify({"success": True, "draft": _serialize_draft(payload)})
    except Exception as e:
        print(f"Error approving partnership draft: {e}")
        return jsonify({"error": str(e)}), 500


def _load_partnership_send_snapshot(*, business_id: str) -> dict[str, Any]:
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                d.id, d.lead_id, d.channel, d.status,
                d.generated_text, d.edited_text, d.approved_text,
                d.created_at, d.updated_at,
                l.name AS lead_name, l.category, l.city, l.selected_channel, l.status AS lead_status
            FROM outreachmessagedrafts d
            JOIN prospectingleads l ON l.id = d.lead_id
            WHERE d.status = %s
              AND l.business_id = %s
              AND COALESCE(l.intent, 'client_outreach') = 'partnership_outreach'
              AND NOT EXISTS (
                    SELECT 1
                    FROM outreachsendqueue q
                    WHERE q.draft_id = d.id
              )
            ORDER BY d.updated_at DESC, d.created_at DESC
            """,
            (DRAFT_APPROVED, business_id),
        )
        ready_drafts = [_serialize_draft(dict(row)) for row in cur.fetchall()]

        cur.execute(
            """
            SELECT DISTINCT b.id, b.batch_date, b.daily_limit, b.status, b.created_by, b.approved_by, b.created_at, b.updated_at
            FROM outreachsendbatches b
            JOIN outreachsendqueue q ON q.batch_id = b.id
            JOIN prospectingleads l ON l.id = q.lead_id
            WHERE l.business_id = %s
              AND COALESCE(l.intent, 'client_outreach') = 'partnership_outreach'
            ORDER BY b.batch_date DESC, b.created_at DESC
            LIMIT 20
            """,
            (business_id,),
        )
        batch_rows = [_serialize_batch_row(dict(row)) for row in cur.fetchall()]
        batches_by_id = {row["id"]: row for row in batch_rows}
        if batches_by_id:
            cur.execute(
                """
                SELECT
                    q.id, q.batch_id, q.lead_id, q.draft_id, q.channel,
                    q.delivery_status, q.provider_message_id, q.error_text,
                    q.sent_at, q.attempts, q.last_attempt_at, q.next_retry_at, q.dlq_at,
                    q.created_at, q.updated_at,
                    l.name AS lead_name,
                    d.approved_text, d.generated_text,
                    r.classified_outcome AS latest_outcome,
                    r.human_confirmed_outcome AS latest_human_outcome,
                    r.raw_reply AS latest_raw_reply,
                    r.created_at AS latest_reaction_at
                FROM outreachsendqueue q
                JOIN prospectingleads l ON l.id = q.lead_id
                JOIN outreachmessagedrafts d ON d.id = q.draft_id
                LEFT JOIN LATERAL (
                    SELECT classified_outcome, human_confirmed_outcome, raw_reply, created_at
                    FROM outreachreactions rx
                    WHERE rx.queue_id = q.id
                    ORDER BY rx.created_at DESC
                    LIMIT 1
                ) r ON TRUE
                WHERE q.batch_id = ANY(%s)
                ORDER BY q.created_at ASC
                """,
                (list(batches_by_id.keys()),),
            )
            for row in cur.fetchall():
                payload = dict(row)
                batches_by_id[payload["batch_id"]]["items"].append(payload)

        cur.execute(
            """
            SELECT
                r.id, r.queue_id, r.lead_id, r.raw_reply,
                r.classified_outcome, r.confidence, r.human_confirmed_outcome,
                r.note, r.created_by, r.created_at, r.updated_at,
                l.name AS lead_name,
                q.batch_id, q.channel, q.delivery_status
            FROM outreachreactions r
            JOIN outreachsendqueue q ON q.id = r.queue_id
            JOIN prospectingleads l ON l.id = r.lead_id
            WHERE l.business_id = %s
              AND COALESCE(l.intent, 'client_outreach') = 'partnership_outreach'
            ORDER BY r.created_at DESC
            LIMIT 50
            """,
            (business_id,),
        )
        reactions = [_serialize_timestamp_fields(dict(row)) for row in cur.fetchall()]
        return {"ready_drafts": ready_drafts, "batches": batch_rows, "reactions": reactions}
    finally:
        conn.close()


@admin_prospecting_bp.route("/api/partnership/send-batches", methods=["GET"])
def partnership_send_batches():
    """User-level partnership send queue snapshot."""
    user_data, error = _require_auth()
    if error:
        return error
    try:
        requested_business_id = str(request.args.get("business_id") or "").strip() or None
        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            cur = conn.cursor()
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403
        finally:
            conn.close()
        snapshot = _load_partnership_send_snapshot(business_id=business_id)
        return jsonify({"success": True, "daily_cap": MAX_DAILY_OUTREACH_BATCH, **snapshot})
    except Exception as e:
        print(f"Error loading partnership send batches: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/partnership/send-batches", methods=["POST"])
def partnership_create_send_batch():
    """Create partnership send batch from approved drafts of one business."""
    user_data, error = _require_auth()
    if error:
        return error
    try:
        data = request.get_json(silent=True) or {}
        requested_business_id = str(data.get("business_id") or "").strip() or None
        draft_ids = data.get("draft_ids") or None
        if draft_ids is not None and not isinstance(draft_ids, list):
            return jsonify({"error": "draft_ids must be an array"}), 400

        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            cur = conn.cursor()
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403
        finally:
            conn.close()

        conn = get_db_connection()
        try:
            cur = conn.cursor()
            remaining_slots = _remaining_daily_outreach_slots(conn)
            if remaining_slots <= 0:
                return jsonify({"error": f"Daily outreach cap reached ({MAX_DAILY_OUTREACH_BATCH}/day)"}), 400

            query = """
                SELECT d.id, d.lead_id, d.channel
                FROM outreachmessagedrafts d
                JOIN prospectingleads l ON l.id = d.lead_id
                WHERE d.status = %s
                  AND l.business_id = %s
                  AND COALESCE(l.intent, 'client_outreach') = 'partnership_outreach'
                  AND NOT EXISTS (
                        SELECT 1
                        FROM outreachsendqueue q
                        WHERE q.draft_id = d.id
                  )
            """
            params: list[Any] = [DRAFT_APPROVED, business_id]
            if draft_ids:
                query += " AND d.id = ANY(%s)"
                params.append(draft_ids)
            query += " ORDER BY d.updated_at DESC, d.created_at DESC LIMIT %s"
            params.append(remaining_slots)
            cur.execute(query, tuple(params))
            rows = [dict(row) for row in cur.fetchall()]
            if not rows:
                return jsonify({"error": "No approved partnership drafts available for queue"}), 400

            batch_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO outreachsendbatches (
                    id, batch_date, daily_limit, status, created_by
                ) VALUES (%s, CURRENT_DATE, %s, %s, %s)
                """,
                (batch_id, MAX_DAILY_OUTREACH_BATCH, BATCH_DRAFT, user_data["user_id"]),
            )
            for row in rows:
                cur.execute(
                    """
                    INSERT INTO outreachsendqueue (
                        id, batch_id, lead_id, draft_id, channel, delivery_status
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (str(uuid.uuid4()), batch_id, row["lead_id"], row["id"], row["channel"], QUEUE_STATUS_QUEUED),
                )
                cur.execute(
                    """
                    UPDATE prospectingleads
                    SET status = %s,
                        partnership_stage = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (QUEUED_FOR_SEND, "queued_for_send", row["lead_id"]),
                )
            conn.commit()
        finally:
            conn.close()

        snapshot = _load_partnership_send_snapshot(business_id=business_id)
        batch = next((item for item in snapshot["batches"] if item["id"] == batch_id), None)
        return jsonify({"success": True, "daily_cap": MAX_DAILY_OUTREACH_BATCH, "batch": batch, **snapshot})
    except Exception as e:
        print(f"Error creating partnership send batch: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/partnership/send-batches/<string:batch_id>/approve", methods=["POST"])
def partnership_approve_send_batch(batch_id):
    """Approve partnership batch for dispatch."""
    user_data, error = _require_auth()
    if error:
        return error
    try:
        data = request.get_json(silent=True) or {}
        requested_business_id = str(data.get("business_id") or "").strip() or None
        conn = get_db_connection()
        try:
            _ensure_partnership_columns(conn)
            cur = conn.cursor()
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403
            cur.execute(
                """
                SELECT 1
                FROM outreachsendqueue q
                JOIN prospectingleads l ON l.id = q.lead_id
                WHERE q.batch_id = %s
                  AND l.business_id = %s
                  AND COALESCE(l.intent, 'client_outreach') = 'partnership_outreach'
                LIMIT 1
                """,
                (batch_id, business_id),
            )
            if not cur.fetchone():
                return jsonify({"error": "Batch not found"}), 404
        finally:
            conn.close()

        batch, approve_error = _approve_send_batch(batch_id, user_data["user_id"])
        if approve_error:
            return jsonify({"error": approve_error}), 400
        snapshot = _load_partnership_send_snapshot(business_id=business_id)
        return jsonify({"success": True, "batch": batch, **snapshot})
    except Exception as e:
        print(f"Error approving partnership send batch: {e}")
        return jsonify({"error": str(e)}), 500


def _partnership_queue_access(cur, *, queue_id: str, business_id: str) -> dict[str, Any] | None:
    cur.execute(
        """
        SELECT q.id AS queue_id, q.lead_id, q.delivery_status
        FROM outreachsendqueue q
        JOIN prospectingleads l ON l.id = q.lead_id
        WHERE q.id = %s
          AND l.business_id = %s
          AND COALESCE(l.intent, 'client_outreach') = 'partnership_outreach'
        LIMIT 1
        """,
        (queue_id, business_id),
    )
    row = cur.fetchone()
    return dict(row) if row else None


@admin_prospecting_bp.route("/api/partnership/send-queue/<string:queue_id>/reaction", methods=["POST"])
def partnership_record_queue_reaction(queue_id):
    """Record reaction/outcome for partnership queue item (user-level)."""
    user_data, error = _require_auth()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        requested_business_id = str(data.get("business_id") or "").strip() or None
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403
            if not _partnership_queue_access(cur, queue_id=queue_id, business_id=business_id):
                return jsonify({"error": "Queue item not found"}), 404
        finally:
            conn.close()

        reaction, reaction_error = _record_reaction(
            queue_id,
            data.get("raw_reply"),
            data.get("outcome"),
            (data.get("note") or "").strip() or None,
            user_data["user_id"],
        )
        if reaction_error:
            status_code = 404 if reaction_error == "Queue item not found" else 400
            return jsonify({"error": reaction_error}), status_code
        return jsonify({"success": True, "reaction": reaction})
    except Exception as e:
        print(f"Error recording partnership reaction: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/partnership/reactions/<string:reaction_id>/confirm", methods=["POST"])
def partnership_confirm_reaction(reaction_id):
    """Confirm/override partnership reaction outcome (user-level)."""
    user_data, error = _require_auth()
    if error:
        return error
    try:
        data = request.get_json(silent=True) or {}
        requested_business_id = str(data.get("business_id") or "").strip() or None
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            business_id = _resolve_business_for_user(cur, user_data, requested_business_id)
            if not business_id:
                return jsonify({"error": "Business not found or access denied"}), 403
            cur.execute(
                """
                SELECT 1
                FROM outreachreactions r
                JOIN outreachsendqueue q ON q.id = r.queue_id
                JOIN prospectingleads l ON l.id = q.lead_id
                WHERE r.id = %s
                  AND l.business_id = %s
                  AND COALESCE(l.intent, 'client_outreach') = 'partnership_outreach'
                LIMIT 1
                """,
                (reaction_id, business_id),
            )
            if not cur.fetchone():
                return jsonify({"error": "Reaction not found"}), 404
        finally:
            conn.close()

        reaction, reaction_error = _confirm_reaction(
            reaction_id,
            data.get("outcome"),
            (data.get("note") or "").strip() or None,
            user_data["user_id"],
        )
        if reaction_error:
            status_code = 404 if reaction_error == "Reaction not found" else 400
            return jsonify({"error": reaction_error}), status_code
        return jsonify({"success": True, "reaction": reaction})
    except Exception as e:
        print(f"Error confirming partnership reaction: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/admin/prospecting/lead/<string:lead_id>/status", methods=["POST"])
def update_lead_status(lead_id):
    """Update lead status."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        status = data.get("status")

        if not status:
            return jsonify({"error": "Status is required"}), 400

        with DatabaseManager() as db:
            success = db.update_lead_status(lead_id, status)

        if success:
            return jsonify({"success": True})
        return jsonify({"error": "Lead not found"}), 404
    except Exception as e:
        print(f"Error updating lead status: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/admin/prospecting/lead/<string:lead_id>/shortlist", methods=["POST"])
def review_lead_shortlist(lead_id):
    """Approve or reject lead for shortlist."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        decision = (data.get("decision") or "").strip().lower()
        if decision not in {"approved", "rejected"}:
            return jsonify({"error": "Decision must be approved or rejected"}), 400

        new_status = SHORTLIST_APPROVED if decision == "approved" else SHORTLIST_REJECTED
        with DatabaseManager() as db:
            success = db.update_lead_status(lead_id, new_status)
            if not success:
                return jsonify({"error": "Lead not found"}), 404
            lead = db.get_lead_by_id(lead_id)

        return jsonify({"success": True, "lead": lead, "status": new_status})
    except Exception as e:
        print(f"Error reviewing lead shortlist: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/admin/prospecting/lead/<string:lead_id>/select", methods=["POST"])
def select_lead_for_outreach(lead_id):
    """Move shortlisted lead into outreach selection stage."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        with DatabaseManager() as db:
            lead = db.get_lead_by_id(lead_id)
            if not lead:
                return jsonify({"error": "Lead not found"}), 404
            if lead.get("status") != SHORTLIST_APPROVED:
                return jsonify({"error": "Lead must be in shortlist before outreach selection"}), 400
            success = db.update_lead_outreach(lead_id, SELECTED_FOR_OUTREACH, lead.get("selected_channel"))
            if not success:
                return jsonify({"error": "Lead not found"}), 404
            lead = db.get_lead_by_id(lead_id)

        return jsonify({"success": True, "lead": lead, "status": SELECTED_FOR_OUTREACH})
    except Exception as e:
        print(f"Error selecting lead for outreach: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/admin/prospecting/lead/<string:lead_id>/channel", methods=["POST"])
def select_outreach_channel(lead_id):
    """Select outreach channel for lead and advance to channel_selected."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        channel = (data.get("channel") or "").strip().lower()
        if channel not in ALLOWED_OUTREACH_CHANNELS:
            return jsonify({"error": "Channel must be one of: telegram, whatsapp, email, manual"}), 400

        with DatabaseManager() as db:
            lead = db.get_lead_by_id(lead_id)
            if not lead:
                return jsonify({"error": "Lead not found"}), 404
            if lead.get("status") not in {SELECTED_FOR_OUTREACH, CHANNEL_SELECTED}:
                return jsonify({"error": "Lead must be selected for outreach before channel selection"}), 400
            success = db.update_lead_outreach(lead_id, CHANNEL_SELECTED, channel)
            if not success:
                return jsonify({"error": "Lead not found"}), 404
            lead = db.get_lead_by_id(lead_id)

        return jsonify({"success": True, "lead": lead, "status": CHANNEL_SELECTED, "selected_channel": channel})
    except Exception as e:
        print(f"Error selecting outreach channel: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/admin/prospecting/lead/<string:lead_id>/contacts", methods=["POST"])
def update_lead_contacts(lead_id):
    """Manually update lead contact fields (telegram/whatsapp/email/phone/website)."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        allowed_fields = ("telegram_url", "whatsapp_url", "email", "phone", "website")
        updates: dict[str, Any] = {}
        for field in allowed_fields:
            if field in data:
                raw_value = data.get(field)
                if raw_value is None:
                    updates[field] = None
                else:
                    text_value = str(raw_value).strip()
                    updates[field] = text_value or None

        if not updates:
            return jsonify({"error": "No contact fields provided"}), 400

        conn = get_db_connection()
        try:
            cur = conn.cursor()
            assignments = []
            values: list[Any] = []
            for field, value in updates.items():
                assignments.append(f"{field} = %s")
                values.append(value)
            assignments.append("updated_at = NOW()")
            values.append(lead_id)
            cur.execute(
                f"""
                UPDATE prospectingleads
                SET {', '.join(assignments)}
                WHERE id = %s
                RETURNING *
                """,
                values,
            )
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Lead not found"}), 404
            conn.commit()
            lead = dict(row)
        finally:
            conn.close()

        return jsonify({"success": True, "lead": _normalize_lead_for_display(lead)})
    except Exception as e:
        print(f"Error updating lead contacts: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/admin/prospecting/drafts", methods=["GET"])
def get_outreach_drafts():
    """List outreach message drafts."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        status_filter = (request.args.get("status") or "").strip().lower() or None
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            query = """
                SELECT
                    d.id, d.lead_id, d.channel, d.angle_type, d.tone, d.status,
                    d.generated_text, d.edited_text, d.approved_text,
                    d.learning_note_json, d.created_at, d.updated_at,
                    l.name AS lead_name, l.category, l.city, l.selected_channel, l.status AS lead_status
                FROM outreachmessagedrafts d
                JOIN prospectingleads l ON l.id = d.lead_id
            """
            params: list[Any] = []
            if status_filter:
                query += " WHERE d.status = %s"
                params.append(status_filter)
            query += " ORDER BY d.created_at DESC"
            cur.execute(query, params)
            rows = [_serialize_draft(dict(row)) for row in cur.fetchall()]
        finally:
            conn.close()

        return jsonify({"success": True, "drafts": rows, "count": len(rows)})
    except Exception as e:
        print(f"Error loading outreach drafts: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/admin/prospecting/send-batches", methods=["GET"])
def get_outreach_send_batches():
    """List approved drafts ready for queue and recent batches."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        snapshot = _load_send_queue_snapshot()
        return jsonify(
            {
                "success": True,
                "ready_drafts": snapshot["ready_drafts"],
                "batches": snapshot["batches"],
                "reactions": _load_reactions(),
                "daily_cap": MAX_DAILY_OUTREACH_BATCH,
            }
        )
    except Exception as e:
        print(f"Error loading outreach send batches: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/admin/prospecting/send-batches", methods=["POST"])
def create_outreach_send_batch():
    """Create capped daily outreach batch from approved drafts."""
    user_data, error = _require_superadmin()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        draft_ids = data.get("draft_ids") or None
        if draft_ids is not None and not isinstance(draft_ids, list):
            return jsonify({"error": "draft_ids must be an array"}), 400

        batch_id, batch_error = _create_send_batch(user_data["user_id"], draft_ids)
        if batch_error:
            return jsonify({"error": batch_error}), 400
        snapshot = _load_send_queue_snapshot()
        batch = next((item for item in snapshot["batches"] if item["id"] == batch_id), None)
        return jsonify(
            {
                "success": True,
                "batch": batch,
                "daily_cap": MAX_DAILY_OUTREACH_BATCH,
            }
        )
    except Exception as e:
        print(f"Error creating outreach send batch: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/admin/prospecting/send-batches/<string:batch_id>/approve", methods=["POST"])
def approve_outreach_send_batch(batch_id):
    """Manual approval before actual sending."""
    user_data, error = _require_superadmin()
    if error:
        return error

    try:
        batch, batch_error = _approve_send_batch(batch_id, user_data["user_id"])
        if batch_error:
            return jsonify({"error": batch_error}), 400 if batch_error != "Batch not found" else 404
        return jsonify({"success": True, "batch": batch})
    except Exception as e:
        print(f"Error approving outreach send batch: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/admin/prospecting/send-batches/<string:batch_id>", methods=["DELETE"])
def delete_outreach_send_batch(batch_id):
    """Delete full outreach batch (queue rows are removed by cascade)."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        deleted = _delete_send_batch(batch_id)
        if not deleted:
            # Idempotent delete: treat missing row as already deleted.
            return jsonify({"success": True, "already_deleted": True, "batch_id": batch_id})
        return jsonify({"success": True, "batch": deleted})
    except Exception as e:
        print(f"Error deleting outreach batch: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/admin/prospecting/send-batches/cleanup-test", methods=["POST"])
def cleanup_outreach_test_batches():
    """Delete draft/test batches to keep queue clean."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        summary = _cleanup_test_send_batches()
        return jsonify({"success": True, **summary})
    except Exception as e:
        print(f"Error cleaning outreach test batches: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/admin/prospecting/send-dispatch", methods=["POST"])
def dispatch_outreach_send_queue():
    """Run one manual dispatch cycle for due outreach queue items."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        batch_size = max(1, min(int(data.get("batch_size", 20) or 20), 200))
        summary = dispatch_due_outreach_queue(batch_size=batch_size)
        return jsonify(summary)
    except Exception as e:
        print(f"Error dispatching outreach queue: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@admin_prospecting_bp.route("/api/admin/prospecting/send-queue/<string:queue_id>/delivery", methods=["POST"])
def update_send_queue_delivery(queue_id):
    """Manually mark delivery result for queued item."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        delivery_status = (data.get("delivery_status") or "").strip().lower()
        if delivery_status not in {QUEUE_STATUS_SENT, QUEUE_STATUS_DELIVERED, QUEUE_STATUS_FAILED}:
            return jsonify({"error": "delivery_status must be sent, delivered or failed"}), 400

        row = _update_send_queue_delivery(
            queue_id,
            delivery_status,
            (data.get("provider_message_id") or "").strip() or None,
            (data.get("error_text") or "").strip() or None,
        )
        if not row:
            return jsonify({"error": "Queue item not found"}), 404
        return jsonify({"success": True, "item": row})
    except Exception as e:
        print(f"Error updating send queue delivery: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/admin/prospecting/send-queue/<string:queue_id>", methods=["DELETE"])
def delete_outreach_send_queue_item(queue_id):
    """Delete queued/sent item from outreach queue."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        deleted = _delete_send_queue_item(queue_id)
        if not deleted:
            # Idempotent delete: treat missing row as already deleted.
            return jsonify({"success": True, "already_deleted": True, "queue_id": queue_id})
        return jsonify({"success": True, "item": deleted})
    except Exception as e:
        print(f"Error deleting outreach queue item: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/admin/prospecting/send-queue/<string:queue_id>/reaction", methods=["POST"])
def record_send_queue_reaction(queue_id):
    """Record inbound reaction and classify basic outcome."""
    user_data, error = _require_superadmin()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        reaction, reaction_error = _record_reaction(
            queue_id,
            data.get("raw_reply"),
            data.get("outcome"),
            (data.get("note") or "").strip() or None,
            user_data["user_id"],
        )
        if reaction_error:
            status_code = 404 if reaction_error == "Queue item not found" else 400
            return jsonify({"error": reaction_error}), status_code
        return jsonify({"success": True, "reaction": reaction})
    except Exception as e:
        print(f"Error recording outreach reaction: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/admin/prospecting/reactions/<string:reaction_id>/confirm", methods=["POST"])
def confirm_outreach_reaction(reaction_id):
    """Override the detected outcome for an existing reaction."""
    user_data, error = _require_superadmin()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        reaction, reaction_error = _confirm_reaction(
            reaction_id,
            data.get("outcome"),
            (data.get("note") or "").strip() or None,
            user_data["user_id"],
        )
        if reaction_error:
            status_code = 404 if reaction_error == "Reaction not found" else 400
            return jsonify({"error": reaction_error}), status_code
        return jsonify({"success": True, "reaction": reaction})
    except Exception as e:
        print(f"Error confirming outreach reaction: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/admin/prospecting/lead/<string:lead_id>/draft-generate", methods=["POST"])
def generate_outreach_draft(lead_id):
    """Generate initial first-contact draft for lead in channel_selected."""
    user_data, error = _require_superadmin()
    if error:
        return error

    try:
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM prospectingleads WHERE id = %s", (lead_id,))
            lead = cur.fetchone()
            if not lead:
                return jsonify({"error": "Lead not found"}), 404
            lead_dict = dict(lead)
            if lead_dict.get("status") != CHANNEL_SELECTED:
                return jsonify({"error": "Lead must be channel_selected before draft generation"}), 400

            channel = (lead_dict.get("selected_channel") or "").strip().lower()
            if channel not in ALLOWED_OUTREACH_CHANNELS:
                return jsonify({"error": "Lead has no approved outreach channel"}), 400

            draft_payload = _generate_first_message_draft(lead_dict, channel)
            draft_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO outreachmessagedrafts (
                    id, lead_id, channel, angle_type, tone, status,
                    generated_text, created_by
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s
                )
                RETURNING id, lead_id, channel, angle_type, tone, status,
                          generated_text, edited_text, approved_text,
                          learning_note_json, created_at, updated_at
                """,
                (
                    draft_id,
                    lead_id,
                    channel,
                    draft_payload["angle_type"],
                    draft_payload["tone"],
                    DRAFT_GENERATED,
                    draft_payload["generated_text"],
                    user_data["user_id"],
                ),
            )
            draft = dict(cur.fetchone())
            conn.commit()
        finally:
            conn.close()

        return jsonify({"success": True, "draft": _serialize_draft(draft)})
    except Exception as e:
        print(f"Error generating outreach draft: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/admin/prospecting/lead/<string:lead_id>/draft-generate-from-audit", methods=["POST"])
def generate_outreach_draft_from_audit(lead_id):
    """Generate first-contact draft from lead card preview and move lead to outreach flow."""
    user_data, error = _require_superadmin()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        requested_channel = str(data.get("channel") or "").strip().lower()
        channel = requested_channel if requested_channel in ALLOWED_OUTREACH_CHANNELS else "telegram"

        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM prospectingleads WHERE id = %s", (lead_id,))
            lead = cur.fetchone()
            if not lead:
                return jsonify({"error": "Lead not found"}), 404
            lead_dict = dict(lead)

            display_lead = _normalize_lead_for_display(dict(lead_dict))
            if not display_lead:
                return jsonify({"error": "Lead is not available for preview"}), 404
            preview = build_lead_card_preview_snapshot(display_lead)

            cur.execute(
                """
                UPDATE prospectingleads
                SET status = %s,
                    selected_channel = %s,
                    updated_at = NOW()
                WHERE id = %s
                RETURNING *
                """,
                (CHANNEL_SELECTED, channel, lead_id),
            )
            updated_lead = dict(cur.fetchone())

            draft_payload = _generate_audit_first_message_draft(updated_lead, preview, channel)
            draft_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO outreachmessagedrafts (
                    id, lead_id, channel, angle_type, tone, status,
                    generated_text, edited_text, learning_note_json, created_by
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                RETURNING id, lead_id, channel, angle_type, tone, status,
                          generated_text, edited_text, approved_text,
                          learning_note_json, created_at, updated_at
                """,
                (
                    draft_id,
                    lead_id,
                    channel,
                    draft_payload["angle_type"],
                    draft_payload["tone"],
                    DRAFT_GENERATED,
                    draft_payload["generated_text"],
                    draft_payload["generated_text"],
                    Json({"source": "lead_preview_audit"}),
                    user_data["user_id"],
                ),
            )
            draft = dict(cur.fetchone())
            conn.commit()
        finally:
            conn.close()

        return jsonify(
            {
                "success": True,
                "lead": _normalize_lead_for_display(updated_lead),
                "draft": _serialize_draft(draft),
            }
        )
    except Exception as e:
        print(f"Error generating outreach draft from audit: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/admin/prospecting/lead/<string:lead_id>/parse", methods=["POST"])
def parse_lead_card(lead_id):
    """Link lead to LocalOS business if needed and enqueue Yandex card parse."""
    user_data, error = _require_superadmin()
    if error:
        return error

    try:
        lead = _load_prospecting_lead(lead_id)
        if not lead:
            return jsonify({"error": "Lead not found"}), 404

        display_lead = _normalize_lead_for_display(dict(lead))
        if not display_lead:
            return jsonify({"error": "Lead is not available for parsing"}), 400

        business, business_created = _ensure_parse_business_for_lead(display_lead, str(user_data["user_id"]))
        business_id = str(business.get("id") or "").strip()
        if not business_id:
            return jsonify({"error": "Failed to resolve business for lead"}), 500

        _update_lead_business_link(lead_id, business_id)
        source_url = str(
            business.get("yandex_url")
            or display_lead.get("source_url")
            or ""
        ).strip()
        if not source_url:
            return jsonify({"error": "У лида нет ссылки на Яндекс Карты для запуска парсинга"}), 400

        task = _enqueue_parse_task_for_business(business_id, user_data["user_id"], source_url)
        refreshed_lead = _load_prospecting_lead(lead_id) or display_lead
        return jsonify(
            {
                "success": True,
                "lead": _normalize_lead_for_display(refreshed_lead),
                "business": {
                    "id": business_id,
                    "name": business.get("name"),
                    "created": bool(business_created),
                    "shadow": str(business.get("moderation_status") or "").strip().lower() == LEAD_OUTREACH_MODERATION_STATUS,
                },
                "parse_task": {
                    "id": task.get("id"),
                    "status": task.get("status"),
                    "task_type": task.get("task_type"),
                    "source": task.get("source"),
                    "updated_at": task.get("updated_at"),
                    "retry_after": task.get("retry_after"),
                    "existing": bool(task.get("existing")),
                },
            }
        )
    except Exception as e:
        print(f"Error parsing lead card: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/admin/prospecting/shortlist/parse", methods=["POST"])
def parse_shortlist_cards():
    """Bulk enqueue parsing for shortlist leads."""
    user_data, error = _require_superadmin()
    if error:
        return error

    try:
        payload = request.get_json(silent=True) or {}
        lead_ids = payload.get("lead_ids")
        ids: list[str] = [str(item).strip() for item in (lead_ids or []) if str(item).strip()]

        conn = get_db_connection()
        try:
            cur = conn.cursor()
            if ids:
                cur.execute("SELECT * FROM prospectingleads WHERE id = ANY(%s)", (ids,))
            else:
                cur.execute("SELECT * FROM prospectingleads WHERE status = %s", (SHORTLIST_APPROVED,))
            leads = [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

        if not leads:
            return jsonify({"error": "No leads found for parsing"}), 404

        results = []
        enqueued = 0
        skipped = 0
        failed = 0
        for raw_lead in leads:
            lead = _normalize_lead_for_display(dict(raw_lead))
            if not lead:
                skipped += 1
                results.append({"lead_id": raw_lead.get("id"), "status": "skipped", "error": "invalid_lead_payload"})
                continue
            try:
                business, business_created = _ensure_parse_business_for_lead(lead, str(user_data["user_id"]))
                business_id = str(business.get("id") or "").strip()
                if not business_id:
                    failed += 1
                    results.append({"lead_id": lead.get("id"), "status": "failed", "error": "business_resolution_failed"})
                    continue
                _update_lead_business_link(str(lead.get("id")), business_id)
                source_url = str(business.get("yandex_url") or lead.get("source_url") or "").strip()
                if not source_url:
                    failed += 1
                    results.append({"lead_id": lead.get("id"), "status": "failed", "error": "missing_source_url"})
                    continue
                task = _enqueue_parse_task_for_business(business_id, user_data["user_id"], source_url)
                if task.get("existing"):
                    skipped += 1
                    state = "already_running"
                else:
                    enqueued += 1
                    state = "enqueued"
                results.append(
                    {
                        "lead_id": lead.get("id"),
                        "business_id": business_id,
                        "business_created": bool(business_created),
                        "business_shadow": str(business.get("moderation_status") or "").strip().lower() == LEAD_OUTREACH_MODERATION_STATUS,
                        "status": state,
                        "task_id": task.get("id"),
                        "task_status": task.get("status"),
                    }
                )
            except Exception as exc:
                failed += 1
                results.append({"lead_id": lead.get("id"), "status": "failed", "error": str(exc)})

        return jsonify(
            {
                "success": True,
                "total": len(leads),
                "enqueued": enqueued,
                "skipped": skipped,
                "failed": failed,
                "results": results,
            }
        )
    except Exception as e:
        print(f"Error bulk parsing shortlist: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/admin/prospecting/drafts/<string:draft_id>/approve", methods=["POST"])
def approve_outreach_draft(draft_id):
    """Approve outreach draft and persist learning example."""
    user_data, error = _require_superadmin()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        approved_text = (data.get("approved_text") or "").strip()
        note = (data.get("note") or "").strip() or None
        if not approved_text:
            return jsonify({"error": "approved_text is required"}), 400

        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM outreachmessagedrafts WHERE id = %s", (draft_id,))
            draft = cur.fetchone()
            if not draft:
                return jsonify({"error": "Draft not found"}), 404
            draft_dict = dict(draft)

            cur.execute(
                """
                UPDATE outreachmessagedrafts
                SET approved_text = %s,
                    edited_text = %s,
                    status = %s,
                    approved_by = %s,
                    learning_note_json = %s,
                    updated_at = NOW()
                WHERE id = %s
                RETURNING id, lead_id, channel, angle_type, tone, status,
                          generated_text, edited_text, approved_text,
                          learning_note_json, created_at, updated_at
                """,
                (
                    approved_text,
                    approved_text,
                    DRAFT_APPROVED,
                    user_data["user_id"],
                    Json({"note": note} if note else {}),
                    draft_id,
                ),
            )
            updated = dict(cur.fetchone())

            learning_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO outreachlearningexamples (
                    id, example_type, lead_id, input_text, output_text, metadata_json, created_by
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    learning_id,
                    "approved_opening",
                    draft_dict["lead_id"],
                    draft_dict.get("generated_text"),
                    approved_text,
                    Json({"draft_id": draft_id, "note": note}),
                    user_data["user_id"],
                ),
            )
            lead_intent = _resolve_lead_intent(cur, str(draft_dict["lead_id"]))
            record_ai_learning_event(
                conn=conn,
                capability="outreach.draft_first_message",
                event_type="accepted",
                intent=lead_intent,
                user_id=user_data.get("user_id"),
                accepted=True,
                edited_before_accept=(
                    str(draft_dict.get("generated_text") or "").strip() != approved_text
                ),
                draft_text=str(draft_dict.get("generated_text") or "")[:3000],
                final_text=approved_text[:3000],
                metadata={
                    "draft_id": draft_id,
                    "lead_id": str(draft_dict.get("lead_id") or ""),
                    "channel": draft_dict.get("channel"),
                    "angle_type": draft_dict.get("angle_type"),
                    "tone": draft_dict.get("tone"),
                },
            )
            conn.commit()
        finally:
            conn.close()

        return jsonify({"success": True, "draft": _serialize_draft(updated)})
    except Exception as e:
        print(f"Error approving outreach draft: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/admin/prospecting/drafts/<string:draft_id>/save", methods=["POST"])
def save_outreach_draft(draft_id):
    """Save edited outreach draft without approving it."""
    user_data, error = _require_superadmin()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        edited_text = (data.get("edited_text") or "").strip()
        if not edited_text:
            return jsonify({"error": "edited_text is required"}), 400

        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT status FROM outreachmessagedrafts WHERE id = %s", (draft_id,))
            draft = cur.fetchone()
            if not draft:
                return jsonify({"error": "Draft not found"}), 404

            current_status = draft["status"] if hasattr(draft, "__getitem__") else draft[0]
            next_status = DRAFT_GENERATED if current_status == DRAFT_REJECTED else current_status

            cur.execute(
                """
                UPDATE outreachmessagedrafts
                SET edited_text = %s,
                    status = %s,
                    updated_at = NOW()
                WHERE id = %s
                RETURNING id, lead_id, channel, angle_type, tone, status,
                          generated_text, edited_text, approved_text,
                          learning_note_json, created_at, updated_at
                """,
                (
                    edited_text,
                    next_status,
                    draft_id,
                ),
            )
            updated = dict(cur.fetchone())
            lead_intent = _resolve_lead_intent(cur, str(updated.get("lead_id") or ""))
            record_ai_learning_event(
                conn=conn,
                capability="outreach.draft_first_message",
                event_type="edited",
                intent=lead_intent,
                user_id=user_data.get("user_id"),
                draft_text=str(updated.get("generated_text") or "")[:3000],
                final_text=str(edited_text or "")[:3000],
                metadata={
                    "draft_id": draft_id,
                    "lead_id": str(updated.get("lead_id") or ""),
                    "channel": updated.get("channel"),
                },
            )
            conn.commit()
        finally:
            conn.close()

        return jsonify({"success": True, "draft": _serialize_draft(updated)})
    except Exception as e:
        print(f"Error saving outreach draft: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/admin/prospecting/drafts/<string:draft_id>/reject", methods=["POST"])
def reject_outreach_draft(draft_id):
    """Reject outreach draft."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE outreachmessagedrafts
                SET status = %s,
                    updated_at = NOW()
                WHERE id = %s
                RETURNING id, lead_id, channel, angle_type, tone, status,
                          generated_text, edited_text, approved_text,
                          learning_note_json, created_at, updated_at
                """,
                (DRAFT_REJECTED, draft_id),
            )
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Draft not found"}), 404
            updated = dict(row)
            lead_intent = _resolve_lead_intent(cur, str(updated.get("lead_id") or ""))
            record_ai_learning_event(
                conn=conn,
                capability="outreach.draft_first_message",
                event_type="rejected",
                intent=lead_intent,
                user_id=user_data.get("user_id"),
                rejected=True,
                draft_text=str(updated.get("edited_text") or updated.get("generated_text") or "")[:3000],
                final_text="",
                metadata={
                    "draft_id": draft_id,
                    "lead_id": str(updated.get("lead_id") or ""),
                    "channel": updated.get("channel"),
                },
            )
            conn.commit()
        finally:
            conn.close()

        return jsonify({"success": True, "draft": _serialize_draft(updated)})
    except Exception as e:
        print(f"Error rejecting outreach draft: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/admin/ai/learning-metrics", methods=["GET"])
def ai_learning_metrics():
    """Basic acceptance/edit metrics for P0 learning visibility."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        intent = _normalize_learning_intent(request.args.get("intent") or "operations")
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            ensure_ai_learning_events_table(conn)
            cur.execute(
                """
                SELECT
                    capability,
                    COUNT(*) FILTER (WHERE event_type = 'accepted') AS accepted_total,
                    COUNT(*) FILTER (WHERE event_type = 'accepted' AND COALESCE(edited_before_accept, FALSE) = FALSE) AS accepted_raw_total,
                    COUNT(*) FILTER (WHERE event_type = 'accepted' AND COALESCE(edited_before_accept, FALSE) = TRUE) AS accepted_edited_total
                FROM ailearningevents
                WHERE intent = %s
                  AND created_at >= NOW() - INTERVAL '30 days'
                GROUP BY capability
                ORDER BY capability
                """,
                (intent,),
            )
            rows = cur.fetchall()
        finally:
            conn.close()

        items = []
        for row in rows:
            capability = row["capability"] if hasattr(row, "get") else row[0]
            accepted_total = int((row["accepted_total"] if hasattr(row, "get") else row[1]) or 0)
            accepted_raw_total = int((row["accepted_raw_total"] if hasattr(row, "get") else row[2]) or 0)
            accepted_edited_total = int((row["accepted_edited_total"] if hasattr(row, "get") else row[3]) or 0)
            accepted_raw_pct = (accepted_raw_total / accepted_total * 100.0) if accepted_total else 0.0
            edited_before_accept_pct = (accepted_edited_total / accepted_total * 100.0) if accepted_total else 0.0
            items.append(
                {
                    "capability": capability,
                    "accepted_total": accepted_total,
                    "accepted_raw_total": accepted_raw_total,
                    "accepted_edited_total": accepted_edited_total,
                    "accepted_raw_pct": round(accepted_raw_pct, 2),
                    "edited_before_accept_pct": round(edited_before_accept_pct, 2),
                }
            )

        return jsonify({"success": True, "intent": intent, "window_days": 30, "items": items})
    except Exception as e:
        print(f"Error loading ai learning metrics: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/admin/prospecting/drafts/<string:draft_id>", methods=["DELETE"])
def delete_outreach_draft(draft_id):
    """Delete outreach draft."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        deleted = _delete_outreach_draft(draft_id)
        if not deleted:
            # Idempotent delete: treat missing row as already deleted.
            return jsonify({"success": True, "already_deleted": True, "draft_id": draft_id})
        return jsonify({"success": True, "draft": _serialize_draft(deleted)})
    except Exception as e:
        print(f"Error deleting outreach draft: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/admin/prospecting/lead/<string:lead_id>/preview", methods=["GET"])
def preview_lead_card(lead_id):
    """Return deterministic preview snapshot for an outreach lead."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        with DatabaseManager() as db:
            lead = db.get_lead_by_id(lead_id)

        if not lead:
            return jsonify({"error": "Lead not found"}), 404

        lead = _sync_lead_business_link_from_parse_history(dict(lead))
        lead = _sync_lead_contacts_from_parsed_data(dict(lead))
        display_lead = _normalize_lead_for_display(dict(lead))
        if not display_lead:
            return jsonify({"error": "Lead is not available for preview"}), 404

        preview = build_lead_card_preview_snapshot(display_lead)
        return jsonify({"success": True, "lead": display_lead, "preview": preview})
    except Exception as e:
        print(f"Error building outreach lead preview: {e}")
        return jsonify({"error": str(e)}), 500


@admin_prospecting_bp.route("/api/admin/prospecting/lead/<string:lead_id>", methods=["DELETE"])
def delete_lead(lead_id):
    """Delete a lead."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        with DatabaseManager() as db:
            success = db.delete_lead(lead_id)

        if success:
            return jsonify({"success": True})
        return jsonify({"error": "Lead not found"}), 404
    except Exception as e:
        print(f"Error deleting lead: {e}")
        return jsonify({"error": str(e)}), 500
