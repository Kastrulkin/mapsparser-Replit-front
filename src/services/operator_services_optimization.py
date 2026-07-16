from __future__ import annotations

import json
import uuid
from typing import Any, Callable

from services.gigachat_client import analyze_text_with_gigachat
from services.operator_credit_reservation import finalize_reserved_action_credits, reserve_paid_action_credits
from services.operator_manual_review import BILLING_URL, _build_ui_action
from services.operator_news_generation import _clean_text, _extract_json_candidate, _row_to_dict, _stable_id
from services.operator_paid_preflight import build_paid_action_preflight


SERVICES_OPTIMIZE_ACTION_KEY = "services_optimize"
SERVICES_OPTIMIZE_CREDITS_PER_SERVICE = 1
SERVICES_OPTIMIZE_MAX_LIMIT = 5
SERVICES_URL = "/dashboard/card?tab=services"


def classify_services_optimize_intent(message: Any) -> bool:
    text = _clean_text(message).lower()
    if not text:
        return False
    if classify_services_apply_intent(message):
        return False
    has_service_word = "услуг" in text or "прайс" in text or "позици" in text
    has_action = "оптимиз" in text or "улучш" in text or "перепиш" in text or "seo" in text or "сео" in text
    return has_service_word and has_action


def classify_services_apply_intent(message: Any) -> bool:
    text = _clean_text(message).lower()
    if not text:
        return False
    has_service_word = "услуг" in text or "прайс" in text or "позици" in text
    has_apply = "примен" in text or "подтверж" in text or "внеси" in text
    has_suggestions = "предлож" in text or "изменен" in text or "улучшен" in text
    return has_service_word and has_apply and has_suggestions


def _positive_limit(value: Any) -> int:
    try:
        parsed = int(value or SERVICES_OPTIMIZE_MAX_LIMIT)
    except Exception:
        return SERVICES_OPTIMIZE_MAX_LIMIT
    if parsed <= 0:
        return SERVICES_OPTIMIZE_MAX_LIMIT
    return min(parsed, SERVICES_OPTIMIZE_MAX_LIMIT)


def _ensure_service_regeneration_tables(cursor: Any) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS serviceregenerationjobs (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            business_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'awaiting_confirmation',
            requested_by TEXT NOT NULL DEFAULT 'ui',
            limit_count INTEGER NOT NULL DEFAULT 10,
            total_problem_count INTEGER NOT NULL DEFAULT 0,
            selected_count INTEGER NOT NULL DEFAULT 0,
            fixed_count INTEGER NOT NULL DEFAULT 0,
            failed_count INTEGER NOT NULL DEFAULT 0,
            manual_review_count INTEGER NOT NULL DEFAULT 0,
            remaining_count INTEGER,
            remaining_after_batch INTEGER NOT NULL DEFAULT 0,
            confirmation_required BOOLEAN NOT NULL DEFAULT TRUE,
            cooldown_until TIMESTAMPTZ,
            message TEXT,
            summary_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            started_at TIMESTAMPTZ,
            finished_at TIMESTAMPTZ
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS serviceregenerationjobitems (
            id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL REFERENCES serviceregenerationjobs(id) ON DELETE CASCADE,
            service_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            attempt_no INTEGER NOT NULL DEFAULT 0,
            issue_codes_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            issue_labels_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            keyword_score_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            instructions TEXT,
            before_optimized_name TEXT,
            before_optimized_description TEXT,
            after_optimized_name TEXT,
            after_optimized_description TEXT,
            after_issue_labels_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            error TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )


def _load_services(cursor: Any, *, business_id: str, limit: int) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT id, name, description, optimized_name, optimized_description, category, price
        FROM userservices
        WHERE business_id = %s
          AND COALESCE(is_active, TRUE) = TRUE
        ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST
        LIMIT %s
        """,
        (business_id, limit),
    )
    services: list[dict[str, Any]] = []
    for row in cursor.fetchall() or []:
        item = _row_to_dict(cursor, row) or {}
        if _clean_text(item.get("id")) and _clean_text(item.get("name") or item.get("optimized_name")):
            services.append(item)
    return services


def _build_services_prompt(services: list[dict[str, Any]]) -> str:
    payload = []
    for item in services:
        payload.append(
            {
                "id": _clean_text(item.get("id")),
                "name": _clean_text(item.get("optimized_name") or item.get("name")),
                "description": _clean_text(item.get("optimized_description") or item.get("description")),
                "category": _clean_text(item.get("category")),
                "price": _clean_text(item.get("price")),
            }
        )
    return "\n".join(
        [
            "Ты - SEO-редактор услуг локального бизнеса.",
            "Предложи улучшенные названия и короткие SEO-описания для услуг.",
            "Не меняй смысл услуги, не выдумывай бренды, препараты, цены или ограничения.",
            "Верни СТРОГО JSON: {\"services\": [{\"service_id\": \"...\", \"optimized_name\": \"...\", \"seo_description\": \"...\"}]}",
            "",
            json.dumps(payload, ensure_ascii=False),
        ]
    )


def _default_services_generator(prompt: str, *, business_id: str, user_id: str) -> str:
    return analyze_text_with_gigachat(
        prompt,
        task_type="service_optimization",
        business_id=business_id,
        user_id=user_id,
    )


def _parse_suggestions(value: Any, services: list[dict[str, Any]]) -> list[dict[str, Any]]:
    parsed = _extract_json_candidate(_clean_text(value))
    raw_items = []
    if isinstance(parsed, dict) and isinstance(parsed.get("services"), list):
        raw_items = parsed.get("services") or []
    elif isinstance(parsed, list):
        raw_items = parsed
    by_id = {_clean_text(item.get("id")): item for item in services}
    suggestions: list[dict[str, Any]] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        service_id = _clean_text(raw.get("service_id") or raw.get("id"))
        source = by_id.get(service_id)
        if not source:
            continue
        optimized_name = _clean_text(raw.get("optimized_name") or raw.get("name") or source.get("optimized_name") or source.get("name"))
        seo_description = _clean_text(raw.get("seo_description") or raw.get("description") or source.get("optimized_description") or source.get("description"))
        if optimized_name:
            suggestions.append(
                {
                    "service_id": service_id,
                    "before_name": _clean_text(source.get("optimized_name") or source.get("name")),
                    "before_description": _clean_text(source.get("optimized_description") or source.get("description")),
                    "optimized_name": optimized_name,
                    "seo_description": seo_description,
                }
            )
    if suggestions:
        return suggestions
    for source in services:
        suggestions.append(
            {
                "service_id": _clean_text(source.get("id")),
                "before_name": _clean_text(source.get("optimized_name") or source.get("name")),
                "before_description": _clean_text(source.get("optimized_description") or source.get("description")),
                "optimized_name": _clean_text(source.get("optimized_name") or source.get("name")),
                "seo_description": _clean_text(source.get("optimized_description") or source.get("description")),
            }
        )
    return suggestions


def _save_suggestions(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    suggestions: list[dict[str, Any]],
    channel: str,
) -> dict[str, Any]:
    _ensure_service_regeneration_tables(cursor)
    job_id = str(uuid.uuid4())
    summary = {
        "source": "operator_services_optimize",
        "channel": channel,
        "manual_apply_required": True,
        "external_writes_performed": False,
    }
    cursor.execute(
        """
        INSERT INTO serviceregenerationjobs (
            id, user_id, business_id, status, requested_by, limit_count,
            total_problem_count, selected_count, fixed_count, failed_count,
            manual_review_count, remaining_count, remaining_after_batch,
            confirmation_required, message, summary_json, created_at, updated_at, started_at, finished_at
        )
        VALUES (%s, %s, %s, 'suggested', %s, %s, %s, %s, 0, 0, %s, 0, 0, TRUE, %s, %s, NOW(), NOW(), NOW(), NOW())
        RETURNING id, status, selected_count, created_at
        """,
        (
            job_id,
            user_id,
            business_id,
            channel,
            len(suggestions),
            len(suggestions),
            len(suggestions),
            len(suggestions),
            "Operator подготовил предложения. Применение требует отдельного подтверждения.",
            json.dumps(summary, ensure_ascii=False),
        ),
    )
    job = _row_to_dict(cursor, cursor.fetchone()) or {"id": job_id, "status": "suggested", "selected_count": len(suggestions)}
    saved_items: list[dict[str, Any]] = []
    for suggestion in suggestions:
        item_id = _stable_id("operator_services_optimize_item", job_id, suggestion.get("service_id"))
        cursor.execute(
            """
            INSERT INTO serviceregenerationjobitems (
                id, job_id, service_id, status, attempt_no,
                issue_codes_json, issue_labels_json, keyword_score_json, instructions,
                before_optimized_name, before_optimized_description,
                after_optimized_name, after_optimized_description, after_issue_labels_json,
                created_at, updated_at
            )
            VALUES (%s, %s, %s, 'suggested', 1, '[]'::jsonb, '[]'::jsonb, '{}'::jsonb, %s, %s, %s, %s, %s, '[]'::jsonb, NOW(), NOW())
            RETURNING id, service_id, status, before_optimized_name, after_optimized_name, after_optimized_description
            """,
            (
                item_id,
                job_id,
                suggestion.get("service_id"),
                "Operator suggestion; apply requires separate approval.",
                suggestion.get("before_name"),
                suggestion.get("before_description"),
                suggestion.get("optimized_name"),
                suggestion.get("seo_description"),
            ),
        )
        saved = _row_to_dict(cursor, cursor.fetchone()) or {}
        saved_items.append(
            {
                "id": saved.get("id") or item_id,
                "service_id": saved.get("service_id") or suggestion.get("service_id"),
                "status": saved.get("status") or "suggested",
                "before_name": suggestion.get("before_name"),
                "optimized_name": saved.get("after_optimized_name") or suggestion.get("optimized_name"),
                "seo_description": saved.get("after_optimized_description") or suggestion.get("seo_description"),
            }
        )
    job["items"] = saved_items
    return job


def optimize_services_from_operator(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    limit: Any = SERVICES_OPTIMIZE_MAX_LIMIT,
    channel: str = "web",
    services_generator: Callable[..., str] | None = None,
) -> dict[str, Any]:
    clean_limit = _positive_limit(limit)
    services = _load_services(cursor, business_id=business_id, limit=clean_limit)
    if not services:
        return {
            "status": "blocked",
            "intent": SERVICES_OPTIMIZE_ACTION_KEY,
            "chat_response": "Не нашёл сохранённых услуг для оптимизации.",
            "service_suggestions": [],
            "charged_credits": 0,
            "credit_charged": False,
            "blocked_reasons": ["services_not_found"],
        }

    estimated_credits = len(services) * SERVICES_OPTIMIZE_CREDITS_PER_SERVICE
    preflight = build_paid_action_preflight(
        cursor,
        business_id=business_id,
        user_id=user_id,
        action_key=SERVICES_OPTIMIZE_ACTION_KEY,
        estimated_credits=estimated_credits,
    )
    if preflight.get("status") != "ready":
        blocked = list(preflight.get("blocked_reasons") or [])
        if "insufficient_balance" in blocked:
            return {
                "status": "blocked",
                "intent": SERVICES_OPTIMIZE_ACTION_KEY,
                "chat_response": "Недостаточно кредитов для оптимизации услуг. Пополните счёт или выберите тариф: /dashboard/billing",
                "billing_url": BILLING_URL,
                "preflight": preflight,
                "service_suggestions": [],
                "charged_credits": 0,
                "credit_charged": False,
                "blocked_reasons": blocked,
                "ui_actions": [_build_ui_action("open_billing", "Пополнить счёт", href=BILLING_URL)],
            }
        return {
            "status": "blocked",
            "intent": SERVICES_OPTIMIZE_ACTION_KEY,
            "chat_response": "Не удалось запустить оптимизацию услуг. Причины: " + ", ".join(blocked),
            "preflight": preflight,
            "service_suggestions": [],
            "charged_credits": 0,
            "credit_charged": False,
            "blocked_reasons": blocked,
        }

    service_ids = ",".join(_clean_text(item.get("id")) for item in services)
    idempotency_key = _stable_id("operator_services_optimize", business_id, user_id, service_ids)
    reservation = reserve_paid_action_credits(
        cursor,
        business_id=business_id,
        user_id=user_id,
        action_key=SERVICES_OPTIMIZE_ACTION_KEY,
        estimated_credits=estimated_credits,
        idempotency_key=idempotency_key,
        metadata={"source": "operator_services_optimize", "channel": channel, "service_count": len(services)},
    )
    if reservation.get("status") != "reserved":
        blocked = list(reservation.get("blocked_reasons") or [])
        return {
            "status": "blocked",
            "intent": SERVICES_OPTIMIZE_ACTION_KEY,
            "chat_response": "Не удалось зарезервировать кредиты для оптимизации услуг. Причины: " + ", ".join(blocked),
            "preflight": preflight,
            "reservation_result": reservation,
            "service_suggestions": [],
            "charged_credits": 0,
            "credit_charged": False,
            "blocked_reasons": blocked,
        }

    generator = services_generator or _default_services_generator
    try:
        generated = generator(
            _build_services_prompt(services),
            business_id=business_id,
            user_id=user_id,
        )
        suggestions = _parse_suggestions(generated, services)
    except Exception:
        suggestions = []

    if not suggestions:
        release = finalize_reserved_action_credits(
            cursor,
            reservation_id=_clean_text(reservation.get("reservation_id")),
            business_id=business_id,
            user_id=user_id,
            finalization_mode="release",
            external_id=idempotency_key,
        )
        return {
            "status": "blocked",
            "intent": SERVICES_OPTIMIZE_ACTION_KEY,
            "chat_response": "Не удалось подготовить предложения по услугам. Кредиты не списаны.",
            "preflight": preflight,
            "reservation_result": reservation,
            "finalization_result": release,
            "service_suggestions": [],
            "charged_credits": 0,
            "credit_charged": False,
            "blocked_reasons": ["services_optimization_failed"],
        }

    job = _save_suggestions(cursor, business_id=business_id, user_id=user_id, suggestions=suggestions, channel=channel)
    actual_credits = len(suggestions) * SERVICES_OPTIMIZE_CREDITS_PER_SERVICE
    finalization = finalize_reserved_action_credits(
        cursor,
        reservation_id=_clean_text(reservation.get("reservation_id")),
        business_id=business_id,
        user_id=user_id,
        actual_credits=actual_credits,
        finalization_mode="charge",
        external_id=idempotency_key,
    )
    charged = int(finalization.get("charge_credits") or 0)
    return {
        "status": "completed",
        "intent": SERVICES_OPTIMIZE_ACTION_KEY,
        "optimization_job": job,
        "service_suggestions": job.get("items") or suggestions,
        "preflight": preflight,
        "reservation_result": reservation,
        "finalization_result": finalization,
        "charged_credits": charged,
        "credit_charged": finalization.get("status") == "charged",
        "external_calls_performed": False,
        "external_writes_performed": False,
        "manual_apply_required": True,
        "manual_publication_only": True,
        "ui_actions": [_build_ui_action("open_services", "Открыть услуги", href=SERVICES_URL)],
        "chat_response": "\n".join(
            [
                f"Подготовил предложения по услугам: {len(job.get('items') or suggestions)}.",
                f"Списано кредитов: {charged}.",
                "Изменения не применялись: применение названий и описаний должно идти отдельным подтверждённым действием.",
            ]
        ),
        "blocked_reasons": [],
    }


def _load_service_suggestion_job(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    job_id: str,
) -> dict[str, Any] | None:
    cursor.execute(
        """
        SELECT id, status, selected_count, fixed_count, failed_count, manual_review_count, message, created_at
        FROM serviceregenerationjobs
        WHERE id = %s
          AND business_id = %s
          AND user_id = %s
        LIMIT 1
        """,
        (job_id, business_id, user_id),
    )
    return _row_to_dict(cursor, cursor.fetchone())


def _load_latest_service_suggestion_job(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
) -> dict[str, Any] | None:
    _ensure_service_regeneration_tables(cursor)
    cursor.execute(
        """
        SELECT id, status, selected_count, fixed_count, failed_count, manual_review_count, message, created_at
        FROM serviceregenerationjobs
        WHERE business_id = %s
          AND user_id = %s
          AND status IN ('suggested', 'partially_applied')
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (business_id, user_id),
    )
    return _row_to_dict(cursor, cursor.fetchone())


def _load_suggested_service_items(
    cursor: Any,
    *,
    business_id: str,
    job_id: str,
    item_ids: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    params: list[Any] = [job_id, business_id]
    item_filter = ""
    if item_ids:
        item_filter = "AND i.id = ANY(%s)"
        params.append(item_ids)
    params.append(limit)
    cursor.execute(
        f"""
        SELECT i.id, i.job_id, i.service_id, i.status,
               i.before_optimized_name, i.before_optimized_description,
               i.after_optimized_name, i.after_optimized_description,
               s.name, s.description, s.optimized_name, s.optimized_description
        FROM serviceregenerationjobitems i
        JOIN userservices s ON s.id = i.service_id
        WHERE i.job_id = %s
          AND s.business_id = %s
          AND i.status = 'suggested'
          {item_filter}
        ORDER BY i.created_at ASC
        LIMIT %s
        """,
        tuple(params),
    )
    return [_row_to_dict(cursor, row) or {} for row in cursor.fetchall() or []]


def apply_service_optimization_suggestions(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    job_id: Any,
    item_ids: Any = None,
    limit: Any = SERVICES_OPTIMIZE_MAX_LIMIT,
    channel: str = "web",
    explicit_confirmation: bool = False,
) -> dict[str, Any]:
    clean_job_id = _clean_text(job_id)
    if not clean_job_id:
        latest_job = _load_latest_service_suggestion_job(cursor, business_id=business_id, user_id=user_id)
        clean_job_id = _clean_text((latest_job or {}).get("id"))
    if not clean_job_id:
        return {
            "status": "blocked",
            "intent": "services_optimize_apply",
            "chat_response": "Не нашёл активные предложения по услугам. Сначала напишите «оптимизируй услуги».",
            "applied_count": 0,
            "applied_items": [],
            "blocked_reasons": ["job_id_required"],
        }
    if not explicit_confirmation:
        return {
            "status": "blocked",
            "intent": "services_optimize_apply",
            "chat_response": "Перед применением предложений нужно явное подтверждение.",
            "applied_count": 0,
            "applied_items": [],
            "external_calls_performed": False,
            "external_writes_performed": False,
            "manual_approval_received": False,
            "credit_charged": False,
            "charged_credits": 0,
            "blocked_reasons": ["explicit_confirmation_required"],
        }

    _ensure_service_regeneration_tables(cursor)
    job = _load_service_suggestion_job(cursor, business_id=business_id, user_id=user_id, job_id=clean_job_id)
    if not job:
        return {
            "status": "blocked",
            "intent": "services_optimize_apply",
            "chat_response": "Не нашёл предложения по услугам для этого бизнеса.",
            "applied_count": 0,
            "applied_items": [],
            "external_calls_performed": False,
            "external_writes_performed": False,
            "manual_approval_received": True,
            "credit_charged": False,
            "charged_credits": 0,
            "blocked_reasons": ["service_suggestion_job_not_found"],
        }

    raw_item_ids = item_ids if isinstance(item_ids, list) else []
    clean_item_ids = [_clean_text(item_id) for item_id in raw_item_ids if _clean_text(item_id)]
    clean_limit = _positive_limit(limit)
    items = _load_suggested_service_items(
        cursor,
        business_id=business_id,
        job_id=clean_job_id,
        item_ids=clean_item_ids,
        limit=clean_limit,
    )
    if not items:
        return {
            "status": "blocked",
            "intent": "services_optimize_apply",
            "optimization_job": job,
            "chat_response": "Нет предложений в статусе suggested для применения.",
            "applied_count": 0,
            "applied_items": [],
            "external_calls_performed": False,
            "external_writes_performed": False,
            "manual_approval_received": True,
            "credit_charged": False,
            "charged_credits": 0,
            "blocked_reasons": ["service_suggestions_not_found"],
        }

    applied_items: list[dict[str, Any]] = []
    for item in items:
        item_id = _clean_text(item.get("id"))
        service_id = _clean_text(item.get("service_id"))
        optimized_name = _clean_text(item.get("after_optimized_name"))
        optimized_description = _clean_text(item.get("after_optimized_description"))
        if not item_id or not service_id or not optimized_name:
            continue
        cursor.execute(
            """
            UPDATE userservices
            SET optimized_name = %s,
                optimized_description = %s,
                updated_at = NOW()
            WHERE id = %s
              AND business_id = %s
            """,
            (optimized_name, optimized_description, service_id, business_id),
        )
        cursor.execute(
            """
            UPDATE serviceregenerationjobitems
            SET status = 'fixed',
                updated_at = NOW()
            WHERE id = %s
              AND job_id = %s
            """,
            (item_id, clean_job_id),
        )
        applied_items.append(
            {
                "id": item_id,
                "service_id": service_id,
                "before_name": _clean_text(item.get("optimized_name") or item.get("name") or item.get("before_optimized_name")),
                "before_description": _clean_text(item.get("optimized_description") or item.get("description") or item.get("before_optimized_description")),
                "optimized_name": optimized_name,
                "seo_description": optimized_description,
                "status": "fixed",
            }
        )

    if not applied_items:
        return {
            "status": "blocked",
            "intent": "services_optimize_apply",
            "optimization_job": job,
            "chat_response": "Не удалось применить предложения: в них нет подходящих названий услуг.",
            "applied_count": 0,
            "applied_items": [],
            "external_calls_performed": False,
            "external_writes_performed": False,
            "manual_approval_received": True,
            "credit_charged": False,
            "charged_credits": 0,
            "blocked_reasons": ["service_suggestions_invalid"],
        }

    cursor.execute(
        """
        SELECT
            COUNT(*) FILTER (WHERE status = 'fixed') AS fixed_count,
            COUNT(*) FILTER (WHERE status = 'suggested') AS suggested_count,
            COUNT(*) FILTER (WHERE status = 'failed') AS failed_count,
            COUNT(*) FILTER (WHERE status IN ('manual_review', 'manual_review_skipped')) AS manual_review_count,
            COUNT(*) AS selected_count
        FROM serviceregenerationjobitems
        WHERE job_id = %s
        """,
        (clean_job_id,),
    )
    counts = _row_to_dict(cursor, cursor.fetchone()) or {}
    suggested_count = int(counts.get("suggested_count") or 0)
    fixed_count = int(counts.get("fixed_count") or 0)
    failed_count = int(counts.get("failed_count") or 0)
    manual_review_count = int(counts.get("manual_review_count") or 0)
    selected_count = int(counts.get("selected_count") or 0)
    next_status = "completed" if suggested_count == 0 else "partially_applied"
    cursor.execute(
        """
        UPDATE serviceregenerationjobs
        SET status = %s,
            selected_count = %s,
            fixed_count = %s,
            failed_count = %s,
            manual_review_count = %s,
            message = %s,
            updated_at = NOW(),
            finished_at = CASE WHEN %s = 'completed' THEN NOW() ELSE finished_at END
        WHERE id = %s
        RETURNING id, status, selected_count, fixed_count, failed_count, manual_review_count, message
        """,
        (
            next_status,
            selected_count,
            fixed_count,
            failed_count,
            manual_review_count,
            f"Применено предложений: {len(applied_items)}. Осталось: {suggested_count}.",
            next_status,
            clean_job_id,
        ),
    )
    updated_job = _row_to_dict(cursor, cursor.fetchone()) or {**job, "status": next_status}
    knowledge_savepoint_created = False
    try:
        from services.knowledge_graph_service import knowledge_layer_enabled, record_action_event

        if knowledge_layer_enabled():
            cursor.execute("SAVEPOINT knowledge_service_action")
            knowledge_savepoint_created = True
            record_action_event(
                cursor.connection,
                business_id=business_id,
                action_type="service_optimization_applied",
                source_type="serviceregenerationjob",
                source_id=clean_job_id,
                status="confirmed",
                approval_id=f"explicit:{user_id}:{clean_job_id}",
                before={"items": [item.get("before_name") for item in applied_items]},
                after={"items": [item.get("optimized_name") for item in applied_items]},
                limitations=["Изменения сохранены в LocalOS и не опубликованы во внешних картах"],
                metadata={"applied_count": len(applied_items), "channel": channel},
            )
            cursor.execute("RELEASE SAVEPOINT knowledge_service_action")
    except Exception:
        if knowledge_savepoint_created:
            cursor.execute("ROLLBACK TO SAVEPOINT knowledge_service_action")
            cursor.execute("RELEASE SAVEPOINT knowledge_service_action")
    return {
        "status": "completed",
        "intent": "services_optimize_apply",
        "optimization_job": updated_job,
        "applied_count": len(applied_items),
        "applied_items": applied_items,
        "external_calls_performed": False,
        "external_writes_performed": False,
        "manual_approval_received": True,
        "credit_charged": False,
        "charged_credits": 0,
        "channel": channel,
        "ui_actions": [_build_ui_action("open_services", "Открыть услуги", href=SERVICES_URL)],
        "chat_response": "\n".join(
            [
                f"Применил предложений по услугам: {len(applied_items)}.",
                "Изменения сохранены только в LocalOS. Во внешние карты ничего не публиковалось.",
            ]
        ),
        "blocked_reasons": [],
    }
