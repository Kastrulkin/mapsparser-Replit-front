from __future__ import annotations

import json
from typing import Any

from parsing_failure_taxonomy import classify_failure_reason
from services.operator_manual_review import _build_ui_action
from services.operator_news_generation import _clean_text, _row_to_dict


REVIEWS_URL = "/dashboard/card?tab=reviews&review_filter=needs_reply"
MAP_REFRESH_SOURCE = "apify_yandex"
MAP_REFRESH_TASK_TYPE = "parse_card"

REASON_LABELS = {
    "captcha": "Нужна проверка",
    "empty_payload": "Пустой ответ парсера",
    "parser_mismatch": "Ошибка парсера",
    "proxy_transport": "Сетевая ошибка",
    "timeout": "Таймаут парсинга",
    "blocked_session": "Сессия парсинга прервана",
    "invalid_org_url": "Некорректная ссылка",
    "quality_gate_fail": "Данные не прошли проверку",
    "retry_exhausted": "Повторы исчерпаны",
    "task_ttl_exceeded": "Задача устарела",
    "closed_business": "Бизнес закрыт в источнике",
    "unknown": "Причина уточняется",
}

REASON_EXPLANATIONS = {
    "captcha": "Источник запросил дополнительную проверку. LocalOS не публикует ничего во внешние карты и ждёт безопасного продолжения парсинга.",
    "empty_payload": "Провайдер или парсер вернул недостаточно данных, поэтому LocalOS не стал обновлять карточку слабым результатом.",
    "parser_mismatch": "Структура ответа отличалась от ожидаемой. Нужна повторная попытка или разбор парсера.",
    "proxy_transport": "Запрос не прошёл через транспортный слой или прокси. Обычно помогает повтор после восстановления сети.",
    "timeout": "Источник отвечал слишком долго. Если есть retry, LocalOS попробует снова по расписанию.",
    "blocked_session": "Сессия парсинга была потеряна или заблокирована. Нужно дождаться новой попытки или запустить обновление позже.",
    "invalid_org_url": "Ссылка на карточку выглядит некорректной. Проверьте URL в профиле бизнеса.",
    "quality_gate_fail": "Данные пришли, но не прошли внутреннюю проверку качества. Старый snapshot сохранён.",
    "retry_exhausted": "Автоматические повторы закончились. Лучше проверить ссылку и запустить обновление заново.",
    "task_ttl_exceeded": "Задача слишком долго не могла завершиться и была остановлена.",
    "closed_business": "Источник сообщает, что бизнес закрыт. Проверьте карточку и ссылку.",
    "unknown": "LocalOS сохранил техническую причину. Если ошибка повторяется, её стоит передать в поддержку.",
}


def _extract_reason_code(status: Any, error_message: Any) -> str:
    message = _clean_text(error_message)
    marker = "reason_code="
    if marker in message:
        tail = message.split(marker, 1)[1]
        code = tail.split(";", 1)[0].strip()
        if code:
            return code
    return classify_failure_reason(status, message)


def _load_queue(cursor: Any, *, business_id: str, user_id: str, queue_id: str) -> dict[str, Any] | None:
    cursor.execute(
        """
        SELECT id, business_id, user_id, status, source, task_type, error_message,
               retry_after, captcha_required, captcha_url, captcha_status, resume_requested,
               warnings, created_at, updated_at
        FROM parsequeue
        WHERE id = %s
          AND business_id = %s
          AND user_id = %s
        LIMIT 1
        """,
        (queue_id, business_id, user_id),
    )
    return _row_to_dict(cursor, cursor.fetchone())


def _table_exists(cursor: Any, table_name: str) -> bool:
    cursor.execute("SELECT to_regclass(%s)", (f"public.{table_name}",))
    row = _row_to_dict(cursor, cursor.fetchone()) or {}
    return bool(row.get("to_regclass") or row.get("table_ref") or row.get("?column?"))


def _json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return _clean_text(value).lower() in {"1", "true", "yes", "y", "on"}


def _split_notes(value: Any) -> list[str]:
    text = _clean_text(value)
    if not text:
        return []
    chunks: list[str] = []
    for part in text.replace("\n", " | ").split("|"):
        clean = part.strip()
        if clean:
            chunks.append(clean)
    return chunks[:6]


def _extract_attempt_markers(error_message: Any) -> dict[str, Any]:
    text = _clean_text(error_message)
    details: dict[str, Any] = {}
    for marker, key in (
        ("transient_retry_attempt=", "transient_retry_attempt"),
        ("captcha_auto_retry_attempt=", "captcha_auto_retry_attempt"),
        ("attempt=", "attempt"),
        ("max_attempts=", "max_attempts"),
    ):
        if marker in text:
            tail = text.split(marker, 1)[1]
            value = tail.split(";", 1)[0].split(" ", 1)[0].strip()
            if value:
                details[key] = value
    return details


def _build_reliability_technical_details(queue: dict[str, Any], reason_code: str, warnings: list[str]) -> dict[str, Any]:
    attempts = _extract_attempt_markers(queue.get("error_message"))
    return {
        "queue_status": _clean_text(queue.get("status")).lower(),
        "reason_code": reason_code,
        "retry_after": queue.get("retry_after"),
        "captcha_required": _bool_value(queue.get("captcha_required")),
        "captcha_status": queue.get("captcha_status"),
        "resume_requested": _bool_value(queue.get("resume_requested")),
        "attempts": attempts,
        "warnings_count": len(warnings),
    }


def build_parse_reliability_state(queue: dict[str, Any] | None) -> dict[str, Any]:
    if not queue:
        return {
            "status": "unknown",
            "severity": "warning",
            "reason_code": "unknown",
            "title": "Статус парсинга не найден",
            "explanation": "LocalOS не нашёл задачу обновления.",
            "next_step": "Проверьте историю обновлений или запустите refresh заново.",
            "retry_after": None,
            "captcha_required": False,
            "resume_requested": False,
            "warnings": [],
            "technical_details": {},
        }

    queue_status = _clean_text(queue.get("status")).lower()
    error_message = _clean_text(queue.get("error_message"))
    warnings = _split_notes(queue.get("warnings"))
    retry_after = queue.get("retry_after")
    captcha_required = _bool_value(queue.get("captcha_required")) or queue_status == "captcha"
    resume_requested = _bool_value(queue.get("resume_requested"))
    reason_code = _extract_reason_code(queue_status, error_message)

    if queue_status in {"pending", "processing"} and retry_after:
        return {
            "status": "retrying",
            "severity": "warning",
            "reason_code": reason_code,
            "title": "Запланирована повторная попытка",
            "explanation": "Предыдущая попытка не дала стабильный результат. Worker попробует снова без публикаций во внешние карты.",
            "next_step": "Дождитесь времени retry и проверьте результат обновления позже.",
            "retry_after": retry_after,
            "captcha_required": captcha_required,
            "resume_requested": resume_requested,
            "warnings": warnings,
            "error_message": error_message,
            "technical_details": _build_reliability_technical_details(queue, reason_code, warnings),
        }

    if captcha_required:
        return {
            "status": "captcha_required",
            "severity": "warning",
            "reason_code": "captcha",
            "title": REASON_LABELS["captcha"],
            "explanation": REASON_EXPLANATIONS["captcha"],
            "next_step": "Дождитесь обработки captcha-flow или запустите обновление позже, если задача перейдёт в ошибку.",
            "retry_after": retry_after,
            "captcha_required": True,
            "captcha_status": queue.get("captcha_status"),
            "resume_requested": resume_requested,
            "warnings": warnings,
            "error_message": error_message,
            "technical_details": _build_reliability_technical_details(queue, "captcha", warnings),
        }

    if queue_status in {"pending", "processing"}:
        return {
            "status": "processing",
            "severity": "info",
            "reason_code": "",
            "title": "Парсинг выполняется",
            "explanation": "Worker собирает read-only данные с карт. Внешние публикации и ответы не выполняются.",
            "next_step": "Проверьте результат немного позже.",
            "retry_after": retry_after,
            "captcha_required": False,
            "resume_requested": resume_requested,
            "warnings": warnings,
            "technical_details": _build_reliability_technical_details(queue, "", warnings),
        }

    if queue_status in {"completed", "done", "success"}:
        if warnings:
            return {
                "status": "warning",
                "severity": "warning",
                "reason_code": "completed_with_warnings",
                "title": "Обновление завершено с предупреждениями",
                "explanation": "Данные сохранены, но worker оставил технические предупреждения по качеству или settlement.",
                "next_step": "Проверьте найденные отзывы и billing details. Если предупреждение повторяется, передайте его в поддержку.",
                "retry_after": None,
                "captcha_required": False,
                "resume_requested": resume_requested,
                "warnings": warnings,
                "technical_details": _build_reliability_technical_details(queue, "completed_with_warnings", warnings),
            }
        return {
            "status": "ok",
            "severity": "success",
            "reason_code": "",
            "title": "Парсинг завершён",
            "explanation": "Read-only обновление завершилось штатно.",
            "next_step": "Если появились отзывы без ответа, подготовьте черновики ответов.",
            "retry_after": None,
            "captcha_required": False,
            "resume_requested": resume_requested,
            "warnings": [],
            "technical_details": _build_reliability_technical_details(queue, "", []),
        }

    if queue_status == "paused":
        return {
            "status": "paused",
            "severity": "warning",
            "reason_code": reason_code,
            "title": "Парсинг на паузе",
            "explanation": "Задача остановлена до следующего безопасного продолжения.",
            "next_step": "Проверьте статус позже или обратитесь в поддержку, если пауза не снимается.",
            "retry_after": retry_after,
            "captcha_required": captcha_required,
            "resume_requested": resume_requested,
            "warnings": warnings,
            "error_message": error_message,
            "technical_details": _build_reliability_technical_details(queue, reason_code, warnings),
        }

    return {
        "status": "failed",
        "severity": "error",
        "reason_code": reason_code,
        "title": REASON_LABELS.get(reason_code, REASON_LABELS["unknown"]),
        "explanation": REASON_EXPLANATIONS.get(reason_code, REASON_EXPLANATIONS["unknown"]),
        "next_step": "Проверьте ссылку на карту и повторите обновление позже. Если ошибка повторится, передайте код причины в поддержку.",
        "retry_after": retry_after,
        "captcha_required": captcha_required,
        "resume_requested": resume_requested,
        "warnings": warnings,
        "error_message": error_message,
        "technical_details": _build_reliability_technical_details(queue, reason_code, warnings),
    }


def _load_refresh_billing_state(cursor: Any, *, business_id: str, user_id: str, queue_id: str) -> dict[str, Any]:
    if not _table_exists(cursor, "operatorcreditreservations"):
        return {
            "status": "unavailable",
            "label": "Биллинг недоступен",
            "reserved_credits": 0,
            "charged_credits": 0,
            "released_credits": 0,
            "outstanding_credits": 0,
            "overage_credits": 0,
            "provider_actual_cost": None,
            "actual_credits": None,
        }
    cursor.execute(
        """
        SELECT id, status, estimated_credits, reserved_credits, charged_credits,
               released_credits, metadata, created_at, updated_at, finalized_at
        FROM operatorcreditreservations
        WHERE business_id = %s
          AND user_id = %s
          AND action_key = 'map_reviews_refresh'
          AND metadata ->> 'parsequeue_id' = %s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (business_id, user_id, queue_id),
    )
    row = _row_to_dict(cursor, cursor.fetchone()) or {}
    if not row:
        return {
            "status": "not_found",
            "label": "Резерв не найден",
            "reserved_credits": 0,
            "charged_credits": 0,
            "released_credits": 0,
            "outstanding_credits": 0,
            "overage_credits": 0,
            "provider_actual_cost": None,
            "actual_credits": None,
        }
    metadata = _json_dict(row.get("metadata"))
    reserved = _int_value(row.get("reserved_credits"))
    charged = _int_value(row.get("charged_credits"))
    released = _int_value(row.get("released_credits"))
    outstanding = max(reserved - charged - released, 0)
    overage = _int_value(metadata.get("overage_credits"))
    provider_actual_cost = metadata.get("provider_actual_cost")
    actual_credits = metadata.get("actual_credits")
    reservation_status = _clean_text(row.get("status"))
    if overage > 0:
        status = "overage_charged"
        label = f"Списано по факту: {charged} + overage {overage}"
        explanation = "Фактическая стоимость Apify оказалась выше резерва, поэтому LocalOS списал резерв и отдельно записал overage."
    elif reservation_status == "reserved" and outstanding > 0:
        status = "reserved"
        label = f"Зарезервировано: {outstanding}"
        explanation = "Кредиты пока только зарезервированы. Фактическое списание будет после результата парсинга и settlement."
    elif charged > 0:
        status = "charged"
        label = f"Списано по факту: {charged}"
        explanation = "Refresh завершён, provider cost пересчитан в кредиты, неиспользованный резерв возвращён или уже учтён."
    elif released > 0 or reservation_status == "released":
        status = "released"
        label = f"Резерв возвращён: {released}"
        explanation = "Резерв был освобождён без списания за этот refresh."
    else:
        status = reservation_status or "unknown"
        label = "Статус оплаты уточняется"
        explanation = "LocalOS пока не видит финальное состояние резерва для этого refresh."
    return {
        "status": status,
        "label": label,
        "explanation": explanation,
        "user_facing_summary": {
            "reserved": reserved,
            "charged": charged,
            "released": released,
            "outstanding": outstanding,
            "overage": overage,
            "provider_actual_cost": provider_actual_cost,
            "actual_credits": actual_credits,
        },
        "reservation_id": row.get("id"),
        "reservation_status": reservation_status,
        "estimated_credits": _int_value(row.get("estimated_credits")),
        "reserved_credits": reserved,
        "charged_credits": charged,
        "released_credits": released,
        "outstanding_credits": outstanding,
        "overage_credits": overage,
        "provider": metadata.get("provider") or "apify",
        "provider_actual_cost": provider_actual_cost,
        "credit_multiplier": metadata.get("credit_multiplier"),
        "actual_credits": actual_credits,
        "settlement_status": metadata.get("settlement_status"),
        "retry_source_queue_id": metadata.get("retry_source_queue_id"),
        "retry_source_status": metadata.get("retry_source_status"),
        "retry_requested_by_operator": _bool_value(metadata.get("retry_requested_by_operator")),
        "retry_reason_code": metadata.get("retry_reason_code"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "finalized_at": row.get("finalized_at"),
    }


def _load_reviews_since(cursor: Any, *, business_id: str, since_value: Any, limit: int = 10) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT id, source, external_review_id, rating, author_name, text,
               response_text, published_at, created_at
        FROM externalbusinessreviews
        WHERE business_id = %s
          AND created_at >= %s
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (business_id, since_value, limit),
    )
    reviews: list[dict[str, Any]] = []
    for row in cursor.fetchall() or []:
        item = _row_to_dict(cursor, row) or {}
        reviews.append(
            {
                "id": item.get("id"),
                "source": item.get("source"),
                "external_review_id": item.get("external_review_id"),
                "rating": item.get("rating"),
                "author_name": item.get("author_name"),
                "text": item.get("text"),
                "has_response": bool(_clean_text(item.get("response_text"))),
                "published_at": item.get("published_at"),
                "created_at": item.get("created_at"),
            }
        )
    return reviews


def build_refresh_result_status(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    queue_id: str,
) -> dict[str, Any]:
    clean_queue_id = _clean_text(queue_id)
    if not clean_queue_id:
        return {
            "status": "blocked",
            "queue_id": "",
            "blocked_reasons": ["queue_id_required"],
            "chat_response": "Нужен id задачи обновления, чтобы проверить результат.",
        }

    queue = _load_queue(cursor, business_id=business_id, user_id=user_id, queue_id=clean_queue_id)
    if not queue:
        return {
            "status": "blocked",
            "queue_id": clean_queue_id,
            "blocked_reasons": ["refresh_job_not_found"],
            "chat_response": "Не нашёл задачу обновления для этого бизнеса.",
        }

    queue_status = _clean_text(queue.get("status")).lower()
    billing_state = _load_refresh_billing_state(cursor, business_id=business_id, user_id=user_id, queue_id=clean_queue_id)
    reliability_state = build_parse_reliability_state(queue)
    if queue_status in {"pending", "processing", "captcha"}:
        return {
            "status": "processing",
            "queue": queue,
            "queue_id": clean_queue_id,
            "queue_status": queue_status,
            "billing_state": billing_state,
            "reliability_state": reliability_state,
            "new_reviews_count": 0,
            "new_unanswered_reviews_count": 0,
            "new_reviews": [],
            "chat_response": "Обновление ещё выполняется. Проверьте результат чуть позже.",
            "blocked_reasons": [],
        }
    if queue_status not in {"completed", "done", "success"}:
        return {
            "status": "failed",
            "queue": queue,
            "queue_id": clean_queue_id,
            "queue_status": queue_status,
            "billing_state": billing_state,
            "reliability_state": reliability_state,
            "new_reviews_count": 0,
            "new_unanswered_reviews_count": 0,
            "new_reviews": [],
            "chat_response": "Обновление завершилось с ошибкой: " + (_clean_text(queue.get("error_message")) or queue_status),
            "blocked_reasons": ["refresh_job_failed"],
        }

    new_reviews = _load_reviews_since(cursor, business_id=business_id, since_value=queue.get("created_at"))
    new_unanswered = [item for item in new_reviews if not item.get("has_response")]
    count = len(new_reviews)
    unanswered_count = len(new_unanswered)
    result_summary = {
        "status": "new_reviews_found" if count > 0 else "no_new_reviews",
        "title": f"Найдено новых отзывов: {count}" if count > 0 else "Новых отзывов не найдено",
        "text": f"Без ответа: {unanswered_count}. Можно подготовить ответы." if unanswered_count > 0 else "Нет новых отзывов без ответа.",
        "primary_action": "generate_review_replies" if unanswered_count > 0 else "open_reviews",
        "new_reviews_count": count,
        "new_unanswered_reviews_count": unanswered_count,
    }
    if count > 0:
        chat_response = "\n".join(
            [
                f"Обновление завершено. Найдено новых отзывов: {count}.",
                f"Без ответа: {unanswered_count}.",
                "Можно подготовить ответы на отзывы прямо из Operator.",
            ]
        )
    else:
        chat_response = "Обновление завершено. Новых отзывов после запуска задачи не найдено."

    return {
        "status": "completed",
        "queue": queue,
        "queue_id": clean_queue_id,
        "queue_status": queue_status,
        "billing_state": billing_state,
        "reliability_state": reliability_state,
        "new_reviews_count": count,
        "new_unanswered_reviews_count": unanswered_count,
        "new_reviews": new_reviews,
        "result_summary": result_summary,
        "chat_response": chat_response,
        "external_calls_performed": False,
        "external_writes_performed": False,
        "manual_publication_only": True,
        "blocked_reasons": [],
        "ui_actions": [
            _build_ui_action("open_reviews", "Открыть отзывы", href=REVIEWS_URL),
            _build_ui_action("generate_review_replies", "Подготовить ответы", payload={"action_key": "review_replies_generate"}),
        ],
    }


def _normalize_refresh_job_status(value: Any) -> str:
    status = _clean_text(value).lower()
    if status in {"pending", "processing", "captcha"}:
        return "processing"
    if status in {"completed", "done", "success"}:
        return "completed"
    if status:
        return "failed"
    return "processing"


def _load_recent_refresh_queues(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    limit: int,
) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT id, business_id, user_id, status, source, task_type, error_message,
               retry_after, captcha_required, captcha_url, captcha_status, resume_requested,
               warnings, created_at, updated_at
        FROM parsequeue
        WHERE business_id = %s
          AND user_id = %s
          AND source = %s
          AND task_type = %s
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (business_id, user_id, MAP_REFRESH_SOURCE, MAP_REFRESH_TASK_TYPE, limit),
    )
    return [_row_to_dict(cursor, row) or {} for row in cursor.fetchall() or []]


def list_refresh_jobs(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    limit: Any = 10,
) -> dict[str, Any]:
    try:
        clean_limit = int(limit)
    except (TypeError, ValueError):
        clean_limit = 10
    clean_limit = max(1, min(clean_limit, 25))

    queues = _load_recent_refresh_queues(
        cursor,
        business_id=business_id,
        user_id=user_id,
        limit=clean_limit,
    )
    jobs: list[dict[str, Any]] = []
    status_counts = {"processing": 0, "completed": 0, "failed": 0}
    reliability_counts = {"retrying": 0, "captcha_required": 0, "failed": 0, "warning": 0}
    total_new_reviews = 0
    total_new_unanswered = 0
    total_reserved_credits = 0
    total_charged_credits = 0
    total_released_credits = 0
    total_overage_credits = 0

    for queue in queues:
        queue_id = _clean_text(queue.get("id"))
        result = build_refresh_result_status(
            cursor,
            business_id=business_id,
            user_id=user_id,
            queue_id=queue_id,
        )
        status = _normalize_refresh_job_status(result.get("status") or queue.get("status"))
        status_counts[status] = status_counts.get(status, 0) + 1
        new_reviews_count = int(result.get("new_reviews_count") or 0)
        new_unanswered_count = int(result.get("new_unanswered_reviews_count") or 0)
        total_new_reviews += new_reviews_count
        total_new_unanswered += new_unanswered_count
        billing_state = result.get("billing_state") if isinstance(result.get("billing_state"), dict) else {}
        reliability_state = result.get("reliability_state") if isinstance(result.get("reliability_state"), dict) else {}
        reliability_status = _clean_text(reliability_state.get("status"))
        if reliability_status in reliability_counts:
            reliability_counts[reliability_status] = reliability_counts.get(reliability_status, 0) + 1
        total_reserved_credits += int(billing_state.get("outstanding_credits") or 0)
        total_charged_credits += int(billing_state.get("charged_credits") or 0)
        total_released_credits += int(billing_state.get("released_credits") or 0)
        total_overage_credits += int(billing_state.get("overage_credits") or 0)
        jobs.append(
            {
                "queue_id": queue_id,
                "retry_source_queue_id": billing_state.get("retry_source_queue_id"),
                "status": status,
                "queue_status": result.get("queue_status") or queue.get("status"),
                "created_at": queue.get("created_at"),
                "updated_at": queue.get("updated_at"),
                "error_message": queue.get("error_message"),
                "new_reviews_count": new_reviews_count,
                "new_unanswered_reviews_count": new_unanswered_count,
                "result_summary": result.get("result_summary"),
                "billing_state": billing_state,
                "reliability_state": reliability_state,
                "new_reviews": list(result.get("new_reviews") or [])[:5],
                "chat_response": result.get("chat_response"),
                "blocked_reasons": list(result.get("blocked_reasons") or []),
                "ui_actions": [
                    _build_ui_action("check_refresh_result", "Проверить результат", payload={"queue_id": queue_id}),
                    _build_ui_action("open_reviews", "Открыть отзывы", href=REVIEWS_URL),
                    _build_ui_action("generate_review_replies", "Подготовить ответы", payload={"action_key": "review_replies_generate"}),
                ],
                "external_calls_performed": False,
                "external_writes_performed": False,
                "manual_publication_only": True,
            }
        )

    return {
        "status": "completed",
        "business_id": business_id,
        "jobs": jobs,
        "summary": {
            "title": "История обновлений отзывов",
            "text": "Последние read-only обновления карт и найденные после них отзывы.",
            "jobs_count": len(jobs),
            "processing_count": status_counts.get("processing", 0),
            "completed_count": status_counts.get("completed", 0),
            "failed_count": status_counts.get("failed", 0),
            "new_reviews_count": total_new_reviews,
            "new_unanswered_reviews_count": total_new_unanswered,
            "reserved_credits": total_reserved_credits,
            "charged_credits": total_charged_credits,
            "released_credits": total_released_credits,
            "overage_credits": total_overage_credits,
            "retrying_count": reliability_counts.get("retrying", 0),
            "captcha_required_count": reliability_counts.get("captcha_required", 0),
            "reliability_failed_count": reliability_counts.get("failed", 0),
            "warning_count": reliability_counts.get("warning", 0),
        },
        "limits": {
            "external_calls_performed": False,
            "external_writes_performed": False,
            "manual_publication_only": True,
        },
    }
