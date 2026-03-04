from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from flask import Blueprint, jsonify, request
from psycopg2.extras import Json

from auth_system import verify_session
from core.channel_delivery import normalize_phone, send_maton_bridge_message
from core.card_audit import build_lead_card_preview_snapshot
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
QUEUE_STATUS_SENT = "sent"
QUEUE_STATUS_FAILED = "failed"
MAX_DAILY_OUTREACH_BATCH = 10
ALLOWED_REPLY_OUTCOMES = {"positive", "question", "no_response", "hard_no"}
SEARCH_JOB_TIMEOUT_SEC = int(os.environ.get("APIFY_SEARCH_TIMEOUT_SEC", "180"))


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
    for field in (
        "name",
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
                    q.sent_at, q.created_at, q.updated_at,
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
        params.append(MAX_DAILY_OUTREACH_BATCH)
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
                q.id, q.batch_id, q.lead_id, q.draft_id, q.channel, q.delivery_status,
                l.name AS lead_name, l.phone, l.email, l.telegram_url, l.whatsapp_url, l.selected_channel,
                d.approved_text, d.generated_text
            FROM outreachsendqueue q
            JOIN prospectingleads l ON l.id = q.lead_id
            JOIN outreachmessagedrafts d ON d.id = q.draft_id
            WHERE q.batch_id = %s
            ORDER BY q.created_at ASC
            """,
            (batch_id,),
        )
        queue_rows = [dict(item) for item in cur.fetchall()]
        dispatch_summary = {"total": len(queue_rows), "sent": 0, "failed": 0, "results": []}
        for item in queue_rows:
            dispatch_result = _dispatch_outreach_queue_item(item)
            delivery_status = dispatch_result["delivery_status"]
            provider_message_id = dispatch_result.get("provider_message_id")
            error_text = dispatch_result.get("error_text")
            sent_at_sql = "NOW()" if delivery_status == QUEUE_STATUS_SENT else "NULL"
            cur.execute(
                f"""
                UPDATE outreachsendqueue
                SET delivery_status = %s,
                    provider_message_id = %s,
                    error_text = %s,
                    sent_at = {sent_at_sql},
                    updated_at = NOW()
                WHERE id = %s
                """,
                (delivery_status, provider_message_id, error_text, item["id"]),
            )
            cur.execute(
                """
                UPDATE prospectingleads
                SET status = %s,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (
                    "sent" if delivery_status == QUEUE_STATUS_SENT else CHANNEL_SELECTED,
                    item["lead_id"],
                ),
            )
            dispatch_summary["sent" if delivery_status == QUEUE_STATUS_SENT else "failed"] += 1
            dispatch_summary["results"].append(
                {
                    "queue_id": item["id"],
                    "lead_id": item["lead_id"],
                    "lead_name": item.get("lead_name"),
                    "channel": item.get("channel"),
                    "delivery_status": delivery_status,
                    "provider_message_id": provider_message_id,
                    "error_text": error_text,
                }
            )
        conn.commit()
        return batch_payload | {"dispatch_summary": dispatch_summary}, None
    except Exception:
        conn.rollback()
        raise
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


def _dispatch_outreach_queue_item(item: dict[str, Any]) -> dict[str, Any]:
    channel = str(item.get("channel") or item.get("selected_channel") or "").strip().lower()
    message = str(item.get("approved_text") or item.get("generated_text") or "").strip()
    if not channel:
        return {"delivery_status": QUEUE_STATUS_FAILED, "error_text": "No channel selected"}
    if not message:
        return {"delivery_status": QUEUE_STATUS_FAILED, "error_text": "Draft text is empty"}

    if channel == "manual":
        return {
            "delivery_status": QUEUE_STATUS_SENT,
            "provider_message_id": f"manual:{item.get('id')}",
            "error_text": None,
        }

    if channel == "email":
        return {
            "delivery_status": QUEUE_STATUS_FAILED,
            "error_text": "Email provider is not configured for outreach yet",
        }

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


def _update_send_queue_delivery(queue_id: str, delivery_status: str, provider_message_id: str | None, error_text: str | None):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        sent_at_sql = "NOW()" if delivery_status == QUEUE_STATUS_SENT else "NULL"
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
        conn.commit()
        return dict(row)
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


@admin_prospecting_bp.route("/api/admin/prospecting/send-queue/<string:queue_id>/delivery", methods=["POST"])
def update_send_queue_delivery(queue_id):
    """Manually mark delivery result for queued item."""
    _, error = _require_superadmin()
    if error:
        return error

    try:
        data = request.get_json(silent=True) or {}
        delivery_status = (data.get("delivery_status") or "").strip().lower()
        if delivery_status not in {QUEUE_STATUS_SENT, QUEUE_STATUS_FAILED}:
            return jsonify({"error": "delivery_status must be sent or failed"}), 400

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
            updated = cur.fetchone()
            conn.commit()
        finally:
            conn.close()

        return jsonify({"success": True, "draft": _serialize_draft(dict(updated))})
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
            conn.commit()
            updated = dict(row)
        finally:
            conn.close()

        return jsonify({"success": True, "draft": _serialize_draft(updated)})
    except Exception as e:
        print(f"Error rejecting outreach draft: {e}")
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
