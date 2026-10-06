"""Draft-only follow-up for an existing partner search.

The search keeps its find_only contract. This service uses the existing Operator
job queue and partnership draft table; it never approves, queues, or sends mail.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from typing import Any
from urllib.parse import urlparse

from psycopg2.extras import Json, RealDictCursor

from services.operator_async_jobs import create_operator_async_job
from services.outreach_continuation import actor_can_write, qualified_contact_ids


KIND = "partner_search_drafts"
DRAFT_CREDITS = 1
MAX_DRAFTS = 100


def _task(cursor: Any, business_id: str, task_id: str) -> dict[str, Any] | None:
    cursor.execute(
        """SELECT * FROM operator_async_jobs
           WHERE id=%s AND business_id=%s AND kind='outreach_continue'""",
        (task_id, business_id),
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def _candidates(cursor: Any, task: dict[str, Any], scope: str) -> list[dict[str, Any]]:
    state = task.get("result_json") or {}
    ids = [str(value) for value in state.get("lead_ids") or [] if value]
    if not ids:
        return []
    cursor.execute(
        """SELECT lead.id, lead.name, lead.city, lead.website, lead.source_url,
                  lead.pipeline_status, lead.status, workstream.id AS workstream_id
           FROM prospectingleads lead
           JOIN lead_workstreams workstream ON workstream.lead_id=lead.id
             AND workstream.client_business_id=%s
             AND workstream.workstream_type='client_partnership'
           WHERE lead.id::text=ANY(%s::text[]) AND lead.business_id=%s
             AND COALESCE(lead.intent,'client_outreach')='partnership_outreach'
             AND NOT EXISTS (SELECT 1 FROM outreach_inbound_events reply
                             WHERE reply.lead_id=lead.id AND reply.is_human=TRUE)
             AND NOT EXISTS (SELECT 1 FROM outreach_suppressions suppression
                             WHERE suppression.lead_id=lead.id
                               AND (suppression.expires_at IS NULL OR suppression.expires_at>NOW()))
           ORDER BY lead.created_at, lead.id""",
        (task["business_id"], ids, task["business_id"]),
    )
    found = {str(row["id"]): dict(row) for row in cursor.fetchall()}
    suitable = set(qualified_contact_ids(state))
    result = []
    seen_ids: set[str] = set()
    seen_names: set[str] = set()
    seen_sites: set[str] = set()
    for lead_id in ids:
        lead = found.get(lead_id)
        if not lead or lead_id in seen_ids:
            continue
        if str(lead.get("status") or "").lower() in {"not_relevant", "suppressed", "replied", "closed_lost"}:
            continue
        if scope == "shortlist" and str(lead.get("pipeline_status") or "").lower() != "in_progress" and str(lead.get("workstream_id")) not in suitable:
            continue
        name_key = re.sub(r"\s+", " ", str(lead.get("name") or "").casefold()).strip()
        city_key = re.sub(r"\s+", " ", str(lead.get("city") or "").casefold()).strip()
        identity_key = f"{name_key}|{city_key}"
        site = str(lead.get("website") or "").strip()
        host = urlparse(site if "://" in site else "https://" + site).hostname if site else None
        site_key = (host or "").casefold().removeprefix("www.")
        if identity_key in seen_names or (site_key and site_key in seen_sites):
            continue
        seen_ids.add(lead_id)
        seen_names.add(identity_key)
        if site_key:
            seen_sites.add(site_key)
        result.append(lead)
    return result


def _offer(task: dict[str, Any], supplied: str) -> str:
    value = supplied.strip() or str((task.get("payload_json") or {}).get("offer") or "").strip()
    if not 20 <= len(value) <= 1000:
        raise ValueError("offer_required")
    return value


def _revision(task_id: str, scope: str, ids: list[str], offer: str) -> str:
    raw = json.dumps([task_id, scope, ids, offer], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def operator_task(cursor: Any, *, business_id: str, user_id: str,
                  arguments: dict[str, Any], actor_context: dict[str, Any] | None = None) -> dict[str, Any]:
    if not actor_can_write(cursor, business_id, actor_context or {}):
        return {"status": "blocked", "chat_response": "Нет доступа к изменению партнёрств этого бизнеса.", "blocked_reasons": ["access_denied"]}
    operation = str(arguments.get("operation") or "preview")
    scope = str(arguments.get("scope") or "shortlist")
    if scope not in {"shortlist", "all_new"} or operation not in {"preview", "start", "status"}:
        raise ValueError("invalid_draft_request")
    task_id = str(arguments.get("task_id") or "").strip()
    if not task_id:
        cursor.execute(
            """SELECT id FROM operator_async_jobs WHERE business_id=%s
               AND kind='outreach_continue' AND payload_json->>'mode'='find_only'
               ORDER BY created_at DESC LIMIT 2""",
            (business_id,),
        )
        recent = cursor.fetchall()
        if len(recent) != 1:
            return {"status": "clarification_required", "chat_response": "Укажите поиск: откройте его карточку или назовите группу, для которой нужны тексты.", "blocked_reasons": ["search_ambiguous"]}
        task_id = str(recent[0]["id"])
    task = _task(cursor, business_id, task_id)
    if not task:
        return {"status": "blocked", "chat_response": "Поиск не найден для выбранного бизнеса.", "blocked_reasons": ["task_not_found"]}
    if str((task.get("payload_json") or {}).get("mode")) != "find_only":
        return {"status": "blocked", "chat_response": "Эта команда предназначена для завершённого поиска без писем.", "blocked_reasons": ["wrong_search_mode"]}
    if str((task.get("payload_json") or {}).get("language") or "en").lower() != "en":
        return {"status": "blocked", "chat_response": "Для этой группы пока доступна массовая подготовка английских черновиков. Уточните язык и предложение.", "blocked_reasons": ["language_not_supported"]}
    if operation == "status":
        cursor.execute("""SELECT * FROM operator_async_jobs WHERE business_id=%s AND kind=%s
                          AND payload_json->>'search_task_id'=%s ORDER BY created_at DESC LIMIT 1""",
                       (business_id, KIND, task_id))
        job = cursor.fetchone()
        if not job:
            return {"status": "completed", "chat_response": "Для этого поиска подготовка текстов ещё не запускалась.", "external_dispatch_performed": False}
        state = job.get("result_json") or {}
        reasons = {str(item.get("reason") or "") for item in state.get("errors") or [] if isinstance(item, dict)}
        blocker = " Не хватило кредитов для продолжения." if "insufficient_credits" in reasons else ""
        return {"status": "completed", "job_id": str(job["id"]), "job_status": job["status"],
                "chat_response": f"Тексты: готово {state.get('created', 0)} из {state.get('total', 0)}; требуют внимания {state.get('failed', 0)}. Списано {state.get('created', 0)} кредитов за готовые тексты.{blocker}",
                "result_ref": {"entity_id": task_id, "href": f"/dashboard/partnerships?search_task_id={task_id}&section=drafts", "label": "Открыть черновики"},
                "external_dispatch_performed": False}
    candidates = _candidates(cursor, task, scope)
    try:
        offer = _offer(task, str(arguments.get("offer") or ""))
    except ValueError:
        return {"status": "clarification_required", "chat_response": "Какое предложение включить в письма? Укажите услуги и допустимые обещания. Отправки пока не будет.", "blocked_reasons": ["offer_required"]}
    ids = [str(item["id"]) for item in candidates]
    revision = _revision(task_id, scope, ids, offer)
    if not ids:
        if scope == "shortlist":
            all_new = _candidates(cursor, task, "all_new")
            available = len(all_new)
            requested = arguments.get("count")
            if available and isinstance(requested, int) and not isinstance(requested, bool):
                all_ids = [str(item["id"]) for item in all_new]
                return {"status": "clarification_required", "preview_ready": True,
                        "task_id": task_id, "scope": "all_new", "offer": offer,
                        "revision": _revision(task_id, "all_new", all_ids, offer),
                        "eligible_count": available,
                        "chat_response": f"Вы запросили {requested} текстов, но в отборе пока нет компаний. В поиске есть {available} уникальных новых компаний без дублей. Они ещё не проверены по стране, направлению и контакту. Подготовить {available} черновиков по всем новым компаниям без отправки? Стоимость — до {available * DRAFT_CREDITS} кредитов за успешно созданные тексты.",
                        "blocked_reasons": ["scope_and_count_clarification"]}
            return {"status": "clarification_required",
                    "chat_response": f"В отборе пока нет компаний; в поиске есть {available} уникальных новых записей. Подготовить черновики для всех {available} с пометкой «компания и контакт не проверены» или сначала отобрать подходящие кнопкой «В отбор»?",
                    "blocked_reasons": ["shortlist_empty"], "available_count": available}
        return {"status": "clarification_required", "chat_response": "В этом поиске нет новых компаний для подготовки текстов.", "blocked_reasons": ["no_candidates"]}
    requested = arguments.get("count")
    if requested is not None and (not isinstance(requested, int) or isinstance(requested, bool) or requested != len(ids)):
        return {"status": "clarification_required", "preview_ready": True,
                "task_id": task_id, "scope": scope, "offer": offer, "revision": revision,
                "chat_response": f"В этом поиске для выбранного режима доступно {len(ids)} уникальных компаний, а запрошено {requested}. Повторы не попадут в подготовку. Подготовить {len(ids)} отдельных черновиков?",
                "blocked_reasons": ["count_mismatch"], "eligible_count": len(ids)}
    if len(ids) > MAX_DRAFTS:
        return {"status": "blocked", "chat_response": f"За одно поручение можно подготовить до {MAX_DRAFTS} текстов.", "blocked_reasons": ["too_many_drafts"]}
    link = f"/dashboard/partnerships?search_task_id={task_id}"
    if operation == "preview":
        return {"status": "completed", "preview_ready": True, "task_id": task_id, "scope": scope,
                "offer": offer, "eligible_count": len(ids), "revision": revision,
                "chat_response": f"Подготовлю {len(ids)} отдельных черновиков на английском для {'компаний в отборе' if scope == 'shortlist' else 'всех новых компаний поиска'}. Отправки не будет. Не проверенные по стране, направлению или контакту останутся помечены для проверки. Сама подготовка — не более {len(ids) * DRAFT_CREDITS} кредитов с общего баланса, по {DRAFT_CREDITS} за успешно созданный текст; обращение к чату учитывается отдельно. Предложение: {offer} Скажите «создай тексты по этому поиску», чтобы начать.",
                "result_ref": {"entity_id": task_id, "href": link, "label": "Открыть поиск"}, "external_dispatch_performed": False}
    if str(arguments.get("revision") or "") != revision:
        return {"status": "blocked", "chat_response": "Состав группы изменился. Покажите условия снова перед запуском.", "blocked_reasons": ["stale_review"]}
    key = f"partner-search-drafts:{business_id}:{revision}"
    job = create_operator_async_job(cursor, user_id=user_id, action_id=None, business_id=business_id,
        kind=KIND, payload={"search_task_id": task_id, "lead_ids": ids, "offer": offer,
                            "language": str((task.get("payload_json") or {}).get("language") or "en"), "scope": scope,
                            "revision": revision}, idempotency_key=key, stage="Подготовка черновиков ожидает запуска", max_attempts=10)
    return {"status": "queued", "job_id": job["id"], "eligible_count": len(ids),
            "chat_response": f"Запустил подготовку {len(ids)} черновиков. Отправки нет. Ход работы и результаты будут в этом поиске.",
            "result_ref": {"entity_id": task_id, "href": link + "&section=drafts", "label": "Открыть черновики"}, "external_dispatch_performed": False}


def load_preparation_contract(cursor: Any, job_id: str, workstream_id: str) -> dict[str, Any] | None:
    """A durable confirmed preparation job grants drafting only, never sending."""
    cursor.execute("""SELECT job.payload_json FROM operator_async_jobs job
        JOIN lead_workstreams ws ON ws.client_business_id=job.business_id
        JOIN prospectingleads lead ON lead.id=ws.lead_id AND lead.business_id=job.business_id
        JOIN operator_async_jobs search ON search.id::text=job.payload_json->>'search_task_id'
          AND search.business_id=job.business_id AND search.kind='outreach_continue'
        WHERE job.id=%s AND job.kind=%s AND job.status='running'
          AND ws.id=%s AND ws.workstream_type='client_partnership'
          AND job.payload_json->'lead_ids' @> jsonb_build_array(lead.id)
          AND search.result_json->'lead_ids' @> jsonb_build_array(lead.id)
          AND search.status <> 'cancelled'""", (job_id, KIND, workstream_id))
    row = cursor.fetchone()
    payload = (row or {}).get("payload_json") or {}
    return payload if payload.get("revision") and payload.get("offer") else None


def _draft_id(task_id: str, lead_id: str, revision: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"partner-search-draft:{task_id}:{lead_id}:{revision}"))


def process_job(claimed: dict[str, Any]) -> dict[str, Any]:
    from pg_db_utils import get_db_connection
    from services.operator_credit_reservation import reserve_paid_action_credits, finalize_reserved_action_credits

    job_id = str(claimed["id"])
    lease = str(claimed.get("lease_token") or "")
    business_id = str(claimed["business_id"])
    user_id = str(claimed["user_id"])
    payload = claimed.get("payload_json") or {}
    ids = [str(value) for value in payload.get("lead_ids") or []]
    task_id = str(payload["search_task_id"])
    revision = str(payload["revision"])
    offer = str(payload["offer"])
    language = str(payload.get("language") or "en")
    prior = claimed.get("result_json") if isinstance(claimed.get("result_json"), dict) else {}
    completed = int(prior.get("created") or 0)
    failed = int(prior.get("failed") or 0)
    errors: list[dict[str, str]] = list(prior.get("errors") or [])
    processed = {str(value) for value in prior.get("processed_ids") or []}
    blocked = False
    blocker_reason = None
    for lead_id in [value for value in ids if value not in processed][:5]:
        conn = get_db_connection()
        reservation_id: str | None = None
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("SELECT id FROM operator_async_jobs WHERE id=%s AND status='running' AND lease_token=%s", (job_id, lease))
            if not cursor.fetchone():
                conn.rollback()
                return {"status": "stopped", "created": completed, "failed": failed, "total": len(ids)}
            from services.outreach_continuation import _require_current_actor
            _require_current_actor(cursor, claimed)
            draft_id = _draft_id(task_id, lead_id, revision)
            cursor.execute("SELECT id FROM outreachmessagedrafts WHERE id=%s", (draft_id,))
            if cursor.fetchone():
                completed += 1
                processed.add(lead_id)
                conn.rollback()
                continue
            cursor.execute(
                """SELECT lead.id, lead.name, lead.website, lead.source_url, lead.pipeline_status,
                          lead.status,
                          workstream.id AS workstream_id
                   FROM prospectingleads lead JOIN lead_workstreams workstream ON workstream.lead_id=lead.id
                   WHERE lead.id=%s AND lead.business_id=%s AND workstream.client_business_id=%s
                     AND workstream.workstream_type='client_partnership'
                     AND NOT EXISTS (SELECT 1 FROM outreach_inbound_events reply
                                     WHERE reply.lead_id=lead.id AND reply.is_human=TRUE)
                     AND NOT EXISTS (SELECT 1 FROM outreach_suppressions suppression
                                     WHERE suppression.lead_id=lead.id
                                       AND (suppression.expires_at IS NULL OR suppression.expires_at>NOW()))""",
                (lead_id, business_id, business_id),
            )
            lead = cursor.fetchone()
            if (not lead or str(lead.get("status") or "").lower() in {"not_relevant", "suppressed", "replied", "closed_lost"}
                    or (payload.get("scope") == "shortlist" and lead["pipeline_status"] != "in_progress" and str(lead["workstream_id"]) not in set(qualified_contact_ids((_task(cursor, business_id, task_id) or {}).get("result_json") or {})))):
                failed += 1
                processed.add(lead_id)
                errors.append({"lead_id": lead_id, "reason": "lead_no_longer_selected"})
                conn.rollback()
                continue
            reservation = reserve_paid_action_credits(cursor, business_id=business_id, user_id=user_id,
                action_key="partnership_draft_generate", estimated_credits=DRAFT_CREDITS,
                idempotency_key=f"{job_id}:{lead_id}", metadata={"search_task_id": task_id, "lead_id": lead_id})
            if reservation.get("blocked_reasons"):
                errors.append({"lead_id": lead_id, "reason": "insufficient_credits"})
                blocked = True
                blocker_reason = "insufficient_credits"
                conn.rollback()
                break
            reservation_id = str(reservation["reservation_id"])
            conn.commit()
            from services.outreach_campaign_service import build_preview, persist_preview
            preview = build_preview(cursor, str(lead["workstream_id"]),
                sender_mode="partner_business", generate_ai=True,
                preparation_job_id=job_id,
                sequence=[{"sequence_index": 0, "day_offset": 0,
                           "channel": "email", "angle": "business_reputation"}])
            if not preview.get("touches"):
                raise ValueError(str(preview.get("reason_code") or "personalization_evidence_required"))
            campaign = persist_preview(cursor, preview, user_id=user_id)
            cursor.execute("SELECT id FROM outreach_campaign_touches WHERE campaign_id=%s AND sequence_index=0",
                           (campaign["id"],))
            touch_id = str(cursor.fetchone()["id"])
            touch = preview["touches"][0]
            body = touch["text"]
            cursor.execute("SELECT id FROM operator_async_jobs WHERE id=%s AND status='running' AND lease_token=%s", (job_id, lease))
            if not cursor.fetchone():
                raise RuntimeError("draft_job_stopped")
            _require_current_actor(cursor, claimed)
            cursor.execute(
                """INSERT INTO outreachmessagedrafts
                   (id, lead_id, workstream_id, channel, angle_type, tone, status,
                    generated_text, edited_text, learning_note_json, created_by, created_at, updated_at)
                   VALUES (%s,%s,%s,'email','partnership_first_note','professional','generated',
                           %s,%s,%s,%s,NOW(),NOW()) ON CONFLICT (id) DO NOTHING""",
                (draft_id, lead_id, lead["workstream_id"], body, body,
                 Json({"search_task_id": task_id, "draft_batch_job_id": job_id,
                       "qualification": "qualified" if (preview.get("continuation_qualification") or {}).get("status") == "qualified" else "not_verified",
                       "campaign_id": campaign["id"], "campaign_touch_id": touch_id,
                       "campaign_version": campaign["version"],
                       "subject": touch.get("subject"), "source_url": touch.get("source_url"),
                       "evidence": preview.get("evidence") or [],
                       "manual_review_required": (preview.get("continuation_qualification") or {}).get("status") != "qualified" or preview.get("status") != "ready",
                       "external_dispatch_performed": False}), user_id),
            )
            charge = finalize_reserved_action_credits(cursor, reservation_id=reservation_id,
                business_id=business_id, user_id=user_id, actual_credits=DRAFT_CREDITS,
                external_id=f"partner-search-draft:{draft_id}")
            if charge.get("status") != "charged":
                raise ValueError("draft_credit_charge_failed")
            completed += 1
            processed.add(lead_id)
            conn.commit()
        except Exception as exc:
            conn.rollback()
            if reservation_id:
                try:
                    cleanup = conn.cursor(cursor_factory=RealDictCursor)
                    finalize_reserved_action_credits(cleanup, reservation_id=reservation_id,
                        business_id=business_id, user_id=user_id, actual_credits=0,
                        external_id=f"partner-search-draft-failed:{job_id}:{lead_id}")
                    conn.commit()
                except Exception:
                    conn.rollback()
            if isinstance(exc, PermissionError):
                blocked = True
                blocker_reason = "access_revoked"
                errors.append({"lead_id": lead_id, "reason": "access_revoked"})
            else:
                failed += 1
                processed.add(lead_id)
                errors.append({"lead_id": lead_id, "reason": str(exc) if isinstance(exc, ValueError) else type(exc).__name__})
        finally:
            conn.close()
            progress_db = get_db_connection()
            try:
                progress_db.cursor().execute(
                    """UPDATE operator_async_jobs SET progress=%s, stage=%s, result_json=%s,
                       updated_at=NOW() WHERE id=%s AND status='running' AND lease_token=%s""",
                    (round(100 * (completed + failed) / max(len(ids), 1)),
                     f"Подготовлено {completed} из {len(ids)}; требуют внимания {failed}",
                     Json({"created": completed, "failed": failed, "total": len(ids),
                           "processed_ids": list(processed), "errors": errors[-20:]}), job_id, lease),
                )
                progress_db.commit()
            finally:
                progress_db.close()
        if blocked:
            break
    return {"created": completed, "failed": failed, "total": len(ids), "remaining": max(0, len(ids) - len(processed)),
            "blocked": blocked, "blocker": blocker_reason, "processed_ids": list(processed),
            "charged_credits": completed * DRAFT_CREDITS, "errors": errors[-20:],
            "search_task_id": task_id, "external_dispatch_performed": False}


def resume_group_job(cursor, *, business_id, task_id):
    """Resume the existing draft job only; deterministic draft IDs prevent replay."""
    cursor.execute("""SELECT * FROM operator_async_jobs WHERE business_id=%s
        AND kind=%s AND payload_json->>'search_task_id'=%s
        ORDER BY created_at DESC LIMIT 1 FOR UPDATE""", (business_id, KIND, task_id))
    job = cursor.fetchone()
    if not job or job['status'] != 'waiting_for_review':
        raise ValueError('draft_job_not_paused')
    cursor.execute("""UPDATE operator_async_jobs SET status='queued', lease_token=NULL,
        next_attempt_at=NOW(), attempt_count=0, updated_at=NOW(),
        stage='Подготовка писем ожидает запуска' WHERE id=%s""", (job['id'],))
