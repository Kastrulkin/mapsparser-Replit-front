from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from typing import Any

from billing_constants import TARIFFS
from core.action_orchestrator import ActionOrchestrator
from database_manager import get_db_connection
from services.operator_attention import build_attention_brief
from services.operator_audit import record_operator_event
from services.operator_capabilities import (
    build_operator_help_response,
    classify_operator_help_intent,
    classify_unanswered_reviews_status_intent,
    get_unanswered_reviews_status,
)
from services.operator_fresh_reviews import classify_fresh_reviews_intent, refresh_reviews_from_operator
from services.operator_intent_ai_router import classify_operator_intent_with_ai, should_use_ai_intent_router
from services.operator_manual_review import process_operator_chat_message
from services.operator_news_generation import classify_news_generate_intent, generate_news_draft_from_operator
from services.operator_refresh_result import list_refresh_jobs
from services.operator_refresh_retry import request_refresh_retry
from services.operator_review_reply_bulk import (
    classify_bulk_review_reply_intent,
    format_bulk_review_reply_result_for_telegram,
    generate_review_reply_drafts_for_unanswered_reviews,
)
from services.operator_services_optimization import (
    apply_service_optimization_suggestions,
    classify_services_apply_intent,
    classify_services_optimize_intent,
    optimize_services_from_operator,
)
from services.operator_social_post_generation import classify_social_post_generate_intent, generate_social_post_draft_from_operator
from subscription_manager import get_subscription_access, get_subscription_info


def _row_to_dict(cursor, row) -> dict[str, Any] | None:
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    if hasattr(row, "keys"):
        try:
            return dict(row)
        except Exception:
            pass
    description = getattr(cursor, "description", None) or []
    columns = [col[0] for col in description]
    if isinstance(row, (list, tuple)) and columns:
        return {columns[idx]: row[idx] for idx in range(min(len(columns), len(row)))}
    return None


def _count_if_table_exists(cursor, table_name: str, query: str, params: tuple[Any, ...]) -> int:
    cursor.execute("SELECT to_regclass(%s) AS table_ref", (f"public.{table_name}",))
    row = _row_to_dict(cursor, cursor.fetchone()) or {}
    if not row.get("table_ref"):
        return 0
    cursor.execute(query, params)
    result = _row_to_dict(cursor, cursor.fetchone()) or {}
    return int(result.get("cnt") or 0)


def _base_web_url() -> str:
    return (os.getenv("FRONTEND_BASE_URL") or "https://localos.pro").rstrip("/")


def _cabinet_urls() -> dict[str, str]:
    base = _base_web_url()
    return {
        "profile": f"{base}/dashboard/profile",
        "card": f"{base}/dashboard/card",
        "progress": f"{base}/dashboard/progress",
        "settings": f"{base}/dashboard/settings",
    }


def _load_card_snapshot(cursor, business_id: str) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT id, created_at, rating, reviews_count, overview
        FROM cards
        WHERE business_id = %s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (business_id,),
    )
    row = _row_to_dict(cursor, cursor.fetchone()) or {}
    overview = row.get("overview")
    if isinstance(overview, str):
        try:
            row["overview"] = json.loads(overview)
        except Exception:
            row["overview"] = {}
    elif not isinstance(overview, dict):
        row["overview"] = {}
    return row


def _load_reviews_counts(cursor, business_id: str) -> dict[str, int]:
    cursor.execute(
        """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN response_text IS NOT NULL AND response_text != '' THEN 1 ELSE 0 END) AS with_response,
            SUM(CASE WHEN response_text IS NULL OR response_text = '' THEN 1 ELSE 0 END) AS without_response
        FROM externalbusinessreviews
        WHERE business_id = %s
        """,
        (business_id,),
    )
    row = _row_to_dict(cursor, cursor.fetchone()) or {}
    return {
        "total": int(row.get("total") or 0),
        "with_response": int(row.get("with_response") or 0),
        "without_response": int(row.get("without_response") or 0),
    }


def _pending_approvals_count(business_ctx: dict) -> int:
    orchestrator = ActionOrchestrator({})
    result = orchestrator.list_actions(
        {
            "user_id": str(business_ctx.get("user_id") or ""),
            "telegram_id": str(business_ctx.get("telegram_id") or ""),
            "is_superadmin": False,
        },
        tenant_id=str(business_ctx.get("business_id") or ""),
        status="pending_human",
        limit=25,
        offset=0,
    )
    if not result.get("success"):
        return 0
    return len(list(result.get("items") or []))


def _format_date(value: Any) -> str:
    if not value:
        return "—"
    if isinstance(value, datetime):
        return value.strftime("%d.%m %H:%M")
    if isinstance(value, str):
        raw = value.strip()
        if raw:
            try:
                return datetime.fromisoformat(raw.replace("Z", "+00:00")).strftime("%d.%m %H:%M")
            except Exception:
                return raw
    return str(value)


def _tier_label(tier: str) -> str:
    normalized = str(tier or "").strip().lower()
    labels = {
        "trial": "Триал",
        "starter": "Starter",
        "professional": "Professional",
        "concierge": "Concierge",
        "promo": "Promo",
        "elite": "Elite",
    }
    return labels.get(normalized, normalized or "—")


def _subscription_upgrade_prompt(info: dict[str, Any], access: dict[str, Any]) -> str:
    tier = str(info.get("tier") or "trial").strip().lower()
    status = str(info.get("status") or "inactive").strip().lower()

    if not info:
        return (
            "Рекомендация: подключить Starter, если хотите получить аудит, работу с отзывами и базовую автоматизацию в одном контуре."
        )

    if tier == "trial":
        if access.get("trial_expired"):
            return (
                "Рекомендация: перейти на Starter. После триала это самый короткий путь вернуть автоматизации и рабочий контур в Telegram."
            )
        return (
            "Рекомендация: если LocalOS уже заходит, следующий логичный шаг — Starter. Он переводит вас из ознакомления в рабочий режим."
        )

    if tier == "starter":
        return (
            "Рекомендация: если хотите плотнее работать с ростом и автоматизацией, следующим апгрейдом будет Professional."
        )

    if tier == "professional":
        return (
            "Рекомендация: если нужен более плотный ручной контур и сопровождение команды, можно рассмотреть Concierge."
        )

    if tier in {"concierge", "elite", "promo"} and status in {"active", "trialing"}:
        return "Сейчас у вас уже верхний уровень доступа. Следующий шаг — использовать его плотнее через отзывы, новости и автоматизации."

    if not access.get("automation_access"):
        return "Рекомендация: активировать оплаченный тариф, чтобы вернуть автоматизации и регулярные сценарии."

    return "Следующий шаг — использовать подписку плотнее через ежедневные действия в Telegram и в кабинете."


def _operator_action_class_label(action_class: str) -> str:
    labels = {
        "free_cached": "бесплатно, сохранённые данные",
        "paid_compute": "платная генерация",
        "paid_external": "платное обновление данных",
        "manual_external": "ручное внешнее действие",
        "approval_required": "требует подтверждения",
        "planned_gap": "планируется",
    }
    return labels.get(str(action_class or "").strip(), "сохранённые данные")


def _format_operator_attention_text(brief: dict[str, Any]) -> str:
    business = brief.get("business") if isinstance(brief.get("business"), dict) else {}
    summary = brief.get("summary") if isinstance(brief.get("summary"), dict) else {}
    metrics = brief.get("metrics") if isinstance(brief.get("metrics"), dict) else {}
    freshness = brief.get("freshness") if isinstance(brief.get("freshness"), dict) else {}
    items = brief.get("items") if isinstance(brief.get("items"), list) else []
    paid_action_offers = brief.get("paid_action_offers") if isinstance(brief.get("paid_action_offers"), list) else []

    lines = [
        "LocalOS Operator",
        "Что требует внимания сегодня",
        f"Бизнес: {business.get('name') or 'Бизнес'}",
        "",
        str(summary.get("text") or "Показываю последние известные данные LocalOS."),
        "",
        "Сводка:",
        f"• Отзывы без ответа: {int(metrics.get('reviews_without_response') or 0)}",
        f"• Ждут подтверждения: {int(metrics.get('pending_approvals') or 0)}",
        f"• Черновики новостей: {int(metrics.get('pending_news') or 0)}",
        f"• Черновики ответов: {int(metrics.get('review_reply_drafts') or 0)}",
        f"• Партнёрства к разбору: {int(metrics.get('partnership_leads_ready') or 0)}",
    ]

    if items:
        lines.extend(["", "Следующие шаги:"])
        for index, item in enumerate(items[:4], start=1):
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "Пункт").strip()
            description = str(item.get("description") or "").strip()
            action_class = _operator_action_class_label(str(item.get("action_class") or "free_cached"))
            count = int(item.get("count") or 0)
            prefix = f"{index}. {title}"
            if count > 0:
                prefix += f" — {count}"
            lines.append(prefix)
            if description:
                lines.append(f"   {description}")
            lines.append(f"   Класс действия: {action_class}.")

    latest_card_at = _format_date(freshness.get("latest_card_at"))
    card_age_days = freshness.get("card_age_days")
    age_text = f"{int(card_age_days)} дн." if card_age_days is not None else "нет данных"
    if paid_action_offers:
        first_offer = paid_action_offers[0] if isinstance(paid_action_offers[0], dict) else {}
        copy = first_offer.get("copy") if isinstance(first_offer.get("copy"), dict) else {}
        lines.extend(
            [
                "",
                "Платное обновление:",
                str(copy.get("primary") or "Могу предложить платное действие после вашего согласия."),
                str(copy.get("disclosure") or "До согласия платные действия не выполняются."),
            ]
        )

    lines.extend(
        [
            "",
            f"Свежесть данных: карточка обновлялась {latest_card_at}; возраст: {age_text}",
            "Платные действия не выполнялись. Чтобы получить свежие данные с карт, нужно отдельное платное обновление и consent-политика.",
            "Публикация ответов в карты сейчас ручная: LocalOS готовит черновики, а пользователь копирует и вставляет их сам.",
        ]
    )

    return "\n".join(lines)


def _format_operator_refresh_jobs_text(refresh_jobs: dict[str, Any]) -> str:
    summary = refresh_jobs.get("summary") if isinstance(refresh_jobs.get("summary"), dict) else {}
    jobs = refresh_jobs.get("jobs") if isinstance(refresh_jobs.get("jobs"), list) else []
    lines = [
        "LocalOS Operator",
        "Обновления отзывов",
        "",
        str(summary.get("text") or "Показываю последние read-only обновления карт."),
        "",
        "Сводка:",
        f"• Задач: {int(summary.get('jobs_count') or 0)}",
        f"• В работе: {int(summary.get('processing_count') or 0)}",
        f"• Завершено: {int(summary.get('completed_count') or 0)}",
        f"• Ошибки: {int(summary.get('failed_count') or 0)}",
        f"• Новых отзывов: {int(summary.get('new_reviews_count') or 0)}",
        f"• Без ответа: {int(summary.get('new_unanswered_reviews_count') or 0)}",
    ]

    if jobs:
        lines.extend(["", "Последние обновления:"])
        for index, job in enumerate(jobs[:5], start=1):
            if not isinstance(job, dict):
                continue
            status = str(job.get("status") or "processing").strip()
            queue_status = str(job.get("queue_status") or status).strip()
            created_at = _format_date(job.get("created_at"))
            new_reviews = int(job.get("new_reviews_count") or 0)
            unanswered = int(job.get("new_unanswered_reviews_count") or 0)
            lines.append(f"{index}. {created_at} — {status} ({queue_status})")
            lines.append(f"   Новых: {new_reviews}; без ответа: {unanswered}.")
            result_summary = job.get("result_summary") if isinstance(job.get("result_summary"), dict) else {}
            if result_summary.get("title"):
                lines.append(f"   Результат: {result_summary.get('title')}. {result_summary.get('text') or ''}".strip())
            error_message = str(job.get("error_message") or "").strip()
            if error_message:
                lines.append(f"   Ошибка: {error_message}")
            reliability = job.get("reliability_state") if isinstance(job.get("reliability_state"), dict) else {}
            reliability_title = str(reliability.get("title") or "").strip()
            reliability_reason = str(reliability.get("reason_code") or "").strip()
            reliability_next = str(reliability.get("next_step") or "").strip()
            if reliability_title and str(reliability.get("status") or "") not in {"ok", "processing"}:
                reason_suffix = f" ({reliability_reason})" if reliability_reason else ""
                lines.append(f"   Надёжность: {reliability_title}{reason_suffix}.")
                if reliability_next:
                    lines.append(f"   Что делать: {reliability_next}")
                if str(reliability.get("status") or "") in {"failed", "captcha_required", "paused", "warning"}:
                    queue_id = str(job.get("queue_id") or "").strip()
                    suffix = f" {queue_id}" if queue_id else ""
                    lines.append(f"   Можно написать: «повтори refresh{suffix}».")
            reviews = job.get("new_reviews") if isinstance(job.get("new_reviews"), list) else []
            for review in reviews[:2]:
                if not isinstance(review, dict):
                    continue
                author = str(review.get("author_name") or "Новый отзыв").strip()
                text = str(review.get("text") or "").strip()
                if text:
                    snippet = text[:180] + ("..." if len(text) > 180 else "")
                    lines.append(f"   • {author}: {snippet}")
    else:
        lines.extend(
            [
                "",
                "Пока нет запусков обновления отзывов.",
                "Можно написать: «Проверь новые отзывы». Если кредитов достаточно, LocalOS запустит read-only обновление карт.",
            ]
        )

    lines.extend(
        [
            "",
            "Следующий шаг:",
            "• если есть отзывы без ответа — напишите «подготовь ответы на отзывы»;",
            "• публикация в карты остаётся ручной: LocalOS готовит черновики, пользователь копирует и вставляет сам.",
            "Открыть Operator в кабинете: " + _base_web_url() + "/dashboard/operator",
        ]
    )
    return "\n".join(lines)


def _extract_refresh_queue_id(text: Any) -> str:
    raw = str(text or "").strip()
    for token in raw.replace("\n", " ").split():
        clean = token.strip(".,;:()[]{}<>")
        if len(clean) >= 8 and any(char.isdigit() for char in clean) and "-" in clean:
            return clean
    return ""


def _latest_retryable_refresh_queue_id(refresh_jobs: dict[str, Any]) -> str:
    jobs = refresh_jobs.get("jobs") if isinstance(refresh_jobs.get("jobs"), list) else []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        reliability = job.get("reliability_state") if isinstance(job.get("reliability_state"), dict) else {}
        if str(reliability.get("status") or "") in {"failed", "captcha_required", "paused", "warning"}:
            queue_id = str(job.get("queue_id") or "").strip()
            if queue_id:
                return queue_id
    return ""


def _format_refresh_retry_result_text(result: dict[str, Any]) -> str:
    status = str(result.get("status") or "blocked")
    lines = [
        "LocalOS Operator",
        "Повтор refresh",
        "",
        str(result.get("chat_response") or ("Повтор запущен." if status == "queued" else "Повтор refresh сейчас недоступен.")),
    ]
    if result.get("new_queue_id"):
        lines.append(f"Новая задача: {result.get('new_queue_id')}")
    if result.get("reservation_id"):
        lines.append(f"Резерв: {result.get('reservation_id')}")
    if result.get("estimated_credits"):
        lines.append(f"Оценка: до {result.get('estimated_credits')} кредитов.")
    if result.get("billing_url"):
        lines.append("Пополнить счёт: " + _base_web_url() + str(result.get("billing_url")))
    blocked = result.get("blocked_reasons") if isinstance(result.get("blocked_reasons"), list) else []
    if blocked:
        lines.append("Причины: " + ", ".join(str(item) for item in blocked))
    lines.append("Внешних публикаций нет. Ответы в карты остаются ручными.")
    return "\n".join(lines)


def _attach_ai_router(result: dict[str, Any], ai_router: dict[str, Any]) -> dict[str, Any]:
    combined = dict(result)
    combined["ai_router"] = {
        "status": ai_router.get("status"),
        "intent": ai_router.get("normalized_intent"),
        "charged_credits": ai_router.get("charged_credits"),
        "credit_charged": ai_router.get("credit_charged"),
        "finalization_result": ai_router.get("finalization_result"),
    }
    return combined


def _unsupported_operator_chat_result(message: Any) -> dict[str, Any]:
    help_response = build_operator_help_response()
    return {
        "status": "unsupported",
        "intent": "unknown",
        "message": str(message or ""),
        "chat_response": (
            "Не понял команду. Я могу помочь с карточкой, отзывами, новостями, постами и услугами.\n\n"
            + str(help_response.get("chat_response") or "")
        ),
        "blocked_reasons": ["unsupported_operator_chat_intent"],
        "external_calls_performed": False,
        "external_writes_performed": False,
        "manual_publication_only": True,
        "paid_actions_performed": False,
        "credit_charged": False,
    }


def _manual_review_guard_result(message: Any) -> dict[str, Any]:
    return {
        "status": "blocked",
        "intent": "manual_review_add_and_reply",
        "message": str(message or ""),
        "reply_text": "",
        "chat_response": (
            "Похоже, вы хотите добавить новый отзыв и подготовить ответ, но я не вижу явный текст отзыва. "
            "Пришлите команду в формате: «Добавь отзыв и сгенерируй ответ: текст отзыва»."
        ),
        "blocked_reasons": ["manual_review_text_not_explicit"],
        "external_calls_performed": False,
        "external_writes_performed": False,
        "manual_publication_only": True,
        "paid_actions_performed": False,
        "credit_charged": False,
    }


def _has_explicit_manual_review_text(message: Any) -> bool:
    text = str(message or "").strip().lower()
    if "отзыв:" in text:
        return True
    if "добав" in text and "отзыв" in text and ":" in text:
        return True
    return False


def route_operator_chat_for_telegram(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    message: Any,
    limit: Any = 5,
) -> dict[str, Any]:
    if classify_operator_help_intent(message):
        return build_operator_help_response()
    if classify_unanswered_reviews_status_intent(message):
        return get_unanswered_reviews_status(cursor, business_id=business_id, limit=limit)
    if classify_bulk_review_reply_intent(message):
        return generate_review_reply_drafts_for_unanswered_reviews(
            cursor,
            business_id=business_id,
            user_id=user_id,
            limit=limit,
            channel="telegram",
        )
    if classify_fresh_reviews_intent(message):
        return refresh_reviews_from_operator(
            cursor,
            business_id=business_id,
            user_id=user_id,
            channel="telegram",
        )
    if classify_services_apply_intent(message):
        return apply_service_optimization_suggestions(
            cursor,
            business_id=business_id,
            user_id=user_id,
            limit=limit,
            channel="telegram",
            explicit_confirmation=True,
        )
    if classify_services_optimize_intent(message):
        return optimize_services_from_operator(
            cursor,
            business_id=business_id,
            user_id=user_id,
            limit=limit,
            channel="telegram",
        )
    if classify_social_post_generate_intent(message):
        return generate_social_post_draft_from_operator(
            cursor,
            business_id=business_id,
            user_id=user_id,
            message=message,
            channel="telegram",
        )
    if classify_news_generate_intent(message):
        return generate_news_draft_from_operator(
            cursor,
            business_id=business_id,
            user_id=user_id,
            message=message,
            channel="telegram",
        )

    result = process_operator_chat_message(
        cursor,
        business_id=business_id,
        user_id=user_id,
        message=message,
        channel="telegram",
    )
    if result.get("status") != "unsupported":
        return result
    if not should_use_ai_intent_router(message):
        return _unsupported_operator_chat_result(message)

    ai_router = classify_operator_intent_with_ai(
        cursor,
        business_id=business_id,
        user_id=user_id,
        message=message,
        channel="telegram",
    )
    if ai_router.get("status") != "completed":
        return ai_router

    ai_intent = str(ai_router.get("normalized_intent") or "unknown")
    if ai_intent == "operator_help":
        routed = build_operator_help_response()
    elif ai_intent == "card_refresh":
        routed = refresh_reviews_from_operator(
            cursor,
            business_id=business_id,
            user_id=user_id,
            channel="telegram",
        )
    elif ai_intent == "review_replies_generate":
        routed = generate_review_reply_drafts_for_unanswered_reviews(
            cursor,
            business_id=business_id,
            user_id=user_id,
            limit=limit,
            channel="telegram",
        )
    elif ai_intent == "manual_review_add_and_reply":
        if _has_explicit_manual_review_text(message):
            routed = process_operator_chat_message(
                cursor,
                business_id=business_id,
                user_id=user_id,
                message="добавь отзыв и сгенерируй ответ: " + str(message or ""),
                channel="telegram",
            )
        else:
            routed = _manual_review_guard_result(message)
    elif ai_intent == "services_apply":
        routed = apply_service_optimization_suggestions(
            cursor,
            business_id=business_id,
            user_id=user_id,
            limit=limit,
            channel="telegram",
            explicit_confirmation=True,
        )
    elif ai_intent == "services_optimize":
        routed = optimize_services_from_operator(
            cursor,
            business_id=business_id,
            user_id=user_id,
            limit=limit,
            channel="telegram",
        )
    elif ai_intent == "social_post_generate":
        routed = generate_social_post_draft_from_operator(
            cursor,
            business_id=business_id,
            user_id=user_id,
            message=message,
            channel="telegram",
        )
    elif ai_intent == "news_generate":
        routed = generate_news_draft_from_operator(
            cursor,
            business_id=business_id,
            user_id=user_id,
            message=message,
            channel="telegram",
        )
    else:
        routed = _unsupported_operator_chat_result(message)
    return _attach_ai_router(routed, ai_router)


def _format_operator_chat_result_for_telegram(result: dict[str, Any]) -> str:
    if result.get("intent") == "bulk_review_replies_generate" or result.get("drafts"):
        return format_bulk_review_reply_result_for_telegram(result)

    lines = [str(result.get("chat_response") or "Команда обработана.")]
    ai_router = result.get("ai_router") if isinstance(result.get("ai_router"), dict) else {}
    if ai_router.get("credit_charged"):
        lines.extend(["", f"AI-разбор команды: -{int(ai_router.get('charged_credits') or 1)} кредит."])
    if result.get("queue_id"):
        lines.append(f"Задача обновления: {result.get('queue_id')}")
    if result.get("reservation_id"):
        lines.append(f"Резерв: {result.get('reservation_id')}")
    if result.get("estimated_credits"):
        lines.append(f"Оценка: до {result.get('estimated_credits')} кредитов.")
    reply_text = str(result.get("reply_text") or "").strip()
    if reply_text:
        lines.extend(["", "Черновик ответа:", reply_text])
    draft = result.get("draft") if isinstance(result.get("draft"), dict) else {}
    generated_text = str(draft.get("generated_text") or "").strip()
    if generated_text and generated_text != reply_text:
        lines.extend(["", "Черновик:", generated_text])
    if result.get("billing_url"):
        lines.append("Пополнить счёт: " + _base_web_url() + str(result.get("billing_url")))
    lines.extend(
        [
            "",
            "Внешних публикаций нет. Ответы, новости и посты нужно копировать и публиковать вручную.",
            "Открыть Operator в кабинете: " + _base_web_url() + "/dashboard/operator",
        ]
    )
    return "\n".join(line for line in lines if line is not None)


def build_operator_chat_text(business_ctx: dict[str, Any], message_text: Any) -> str:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        business_id = str(business_ctx.get("business_id") or "")
        user_id = str(business_ctx.get("user_id") or "")
        result = route_operator_chat_for_telegram(
            cursor,
            business_id=business_id,
            user_id=user_id,
            message=message_text,
            limit=5,
        )
        ai_router = result.get("ai_router") if isinstance(result.get("ai_router"), dict) else {}
        ai_finalization = ai_router.get("finalization_result") if isinstance(ai_router.get("finalization_result"), dict) else {}
        if ai_finalization:
            record_payload = {
                "status": str(ai_finalization.get("status") or "completed"),
                "charge_credits": ai_finalization.get("charge_credits"),
                "release_credits": ai_finalization.get("release_credits"),
                "normalized_intent": ai_router.get("intent"),
            }
        else:
            record_payload = {}
        if record_payload:
            record_operator_event(
                cursor,
                business_id=business_id,
                user_id=user_id,
                event_type="operator_usage_charged",
                action_key="operator_intent_classify",
                channel="telegram",
                status=str(record_payload.get("status") or "completed"),
                input_summary={"action_key": "operator_intent_classify"},
                output_summary=record_payload,
                metadata={
                    "credit_charged": bool(ai_finalization.get("side_effects", {}).get("credit_charged")),
                    "paid_actions_performed": bool(ai_finalization.get("side_effects", {}).get("credit_charged")),
                    "external_writes_performed": False,
                },
            )
        conn.commit()
        return _format_operator_chat_result_for_telegram(result)
    except Exception:
        conn.rollback()
        return "Не удалось выполнить команду Operator: " + str(sys.exc_info()[1])
    finally:
        conn.close()


def build_refresh_retry_text(business_ctx: dict, message_text: Any = "") -> str:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        business_id = str(business_ctx.get("business_id") or "")
        user_id = str(business_ctx.get("user_id") or "")
        refresh_jobs = list_refresh_jobs(cursor, business_id=business_id, user_id=user_id, limit=5)
        queue_id = _extract_refresh_queue_id(message_text) or _latest_retryable_refresh_queue_id(refresh_jobs)
        if not queue_id:
            return "\n".join(
                [
                    "LocalOS Operator",
                    "Повтор refresh",
                    "",
                    "Не нашёл failed/captcha refresh job, который можно повторить.",
                    "Напишите «статус обновлений отзывов», чтобы увидеть последние задачи.",
                ]
            )
        result = request_refresh_retry(
            cursor,
            business_id=business_id,
            user_id=user_id,
            queue_id=queue_id,
            confirm_retry=True,
        )
        if result.get("status") == "queued":
            conn.commit()
        else:
            conn.rollback()
        return _format_refresh_retry_result_text(result)
    except Exception as exc:
        conn.rollback()
        return "Не удалось запустить повтор refresh: " + str(exc)
    finally:
        conn.close()


def build_today_text(business_ctx: dict) -> str:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        business_id = str(business_ctx.get("business_id") or "")
        user_id = str(business_ctx.get("user_id") or "")
        brief = build_attention_brief(cursor, business_id, user_id)
        return _format_operator_attention_text(brief)
    finally:
        conn.close()


def build_refresh_jobs_text(business_ctx: dict) -> str:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        business_id = str(business_ctx.get("business_id") or "")
        user_id = str(business_ctx.get("user_id") or "")
        refresh_jobs = list_refresh_jobs(cursor, business_id=business_id, user_id=user_id, limit=5)
        return _format_operator_refresh_jobs_text(refresh_jobs)
    finally:
        conn.close()


def build_card_text(business_ctx: dict) -> str:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        card = _load_card_snapshot(cursor, str(business_ctx.get("business_id") or ""))
    finally:
        conn.close()
    urls = _cabinet_urls()
    if not card:
        return "\n".join(
            [
                "Карточка бизнеса",
                f"Бизнес: {business_ctx['business_name']}",
                "",
                "Данные карточки ещё не собраны.",
                "Следующий шаг: откройте профиль в кабинете, сохраните ссылку на карту и запустите сбор данных.",
                "",
                f"Профиль: {urls['profile']}",
            ]
        )
    rating = card.get("rating")
    reviews_count = int(card.get("reviews_count") or 0)
    return "\n".join(
        [
            "Карточка бизнеса",
            f"Бизнес: {business_ctx['business_name']}",
            "",
            f"• Рейтинг: {rating if rating is not None else '—'}",
            f"• Отзывов: {reviews_count}",
            f"• Последнее обновление: {_format_date(card.get('created_at'))}",
            "",
            "Полный аудит и редактирование данных лучше открывать в личном кабинете.",
            f"Прогресс: {urls['progress']}",
            f"Профиль: {urls['profile']}",
        ]
    )


def build_reviews_text(business_ctx: dict) -> str:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        reviews = _load_reviews_counts(cursor, str(business_ctx.get("business_id") or ""))
        reply_drafts = _count_if_table_exists(
            cursor,
            "reviewreplydrafts",
            "SELECT COUNT(*) AS cnt FROM reviewreplydrafts WHERE business_id = %s AND status IN ('generated', 'pending_review')",
            (str(business_ctx.get("business_id") or ""),),
        )
    finally:
        conn.close()
    return "\n".join(
        [
            "Отзывы",
            f"Бизнес: {business_ctx['business_name']}",
            "",
            f"• Всего отзывов в базе: {reviews['total']}",
            f"• Уже с ответом: {reviews['with_response']}",
            f"• Без ответа: {reviews['without_response']}",
            f"• Подготовленные черновики: {reply_drafts}",
            "",
            "Можно быстро подготовить новые ответы и подтвердить их прямо в Telegram.",
        ]
    )


def build_growth_text(business_ctx: dict) -> str:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        pending_news = _count_if_table_exists(
            cursor,
            "usernews",
            "SELECT COUNT(*) AS cnt FROM usernews WHERE user_id = %s AND COALESCE(approved, 0) = 0",
            (str(business_ctx.get("user_id") or ""),),
        )
        partnership_leads = _count_if_table_exists(
            cursor,
            "prospectingleads",
            """
            SELECT COUNT(*) AS cnt
            FROM prospectingleads
            WHERE business_id = %s
              AND COALESCE(intent, 'client_outreach') = 'partnership_outreach'
            """,
            (str(business_ctx.get("business_id") or ""),),
        )
    finally:
        conn.close()
    return "\n".join(
        [
            "Рост",
            f"Бизнес: {business_ctx['business_name']}",
            "",
            f"• Черновики новостей: {pending_news}",
            f"• Лидов в партнёрском потоке: {partnership_leads}",
            "",
            "Через этот раздел удобно запускать новости, смотреть партнёрства и позже сравнивать себя с конкурентами.",
        ]
    )


def build_automation_text(business_ctx: dict) -> str:
    access = get_subscription_access(str(business_ctx.get("business_id") or ""))
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT to_regclass('public.businesscardautomationsettings') AS table_ref")
        table_row = _row_to_dict(cursor, cursor.fetchone()) or {}
        if not table_row.get("table_ref"):
            return "\n".join(
                [
                    "Автоматизация",
                    f"Бизнес: {business_ctx['business_name']}",
                    "",
                    "Автоматизации ещё не настроены.",
                ]
            )
        cursor.execute(
            """
            SELECT
                news_enabled,
                review_sync_enabled,
                review_reply_enabled,
                digest_enabled,
                news_next_run_at,
                review_sync_next_run_at,
                review_reply_next_run_at
            FROM businesscardautomationsettings
            WHERE business_id = %s
            LIMIT 1
            """,
            (str(business_ctx.get("business_id") or ""),),
        )
        row = _row_to_dict(cursor, cursor.fetchone()) or {}
    finally:
        conn.close()
    enabled_items = []
    if row.get("news_enabled"):
        enabled_items.append(f"новости → {_format_date(row.get('news_next_run_at'))}")
    if row.get("review_sync_enabled"):
        enabled_items.append(f"сбор отзывов → {_format_date(row.get('review_sync_next_run_at'))}")
    if row.get("review_reply_enabled"):
        enabled_items.append(f"ответы на отзывы → {_format_date(row.get('review_reply_next_run_at'))}")
    if row.get("digest_enabled"):
        enabled_items.append("утренний дайджест включён")
    lines = [
        "Автоматизация",
        f"Бизнес: {business_ctx['business_name']}",
        "",
    ]
    if enabled_items:
        lines.append("Включено сейчас:")
        lines.extend(f"• {item}" for item in enabled_items)
    else:
        lines.append("Сейчас автоматизации не настроены.")
    lines.extend(
        [
            "",
            f"Доступ к автоматизациям: {'есть' if access.get('automation_access') else 'пока нет'}",
        ]
    )
    if not access.get("automation_access"):
        lines.extend(
            [
                access.get("reason") or "Автоматизации доступны после оплаты тарифа.",
                "Если хотите, я подскажу, какой тариф откроет этот режим.",
            ]
        )
    lines.extend(
        [
            "",
            "Если хотите, можно прислать запрос, что именно вы хотите автоматизировать.",
        ]
    )
    return "\n".join(lines)


def build_subscription_text(business_ctx: dict) -> str:
    info = get_subscription_info(str(business_ctx.get("business_id") or ""))
    access = get_subscription_access(str(business_ctx.get("business_id") or ""))
    urls = _cabinet_urls()
    if not info:
        return "\n".join(
            [
                "Подписка",
                f"Бизнес: {business_ctx['business_name']}",
                "",
                "Подписка пока не найдена.",
                "Что это даст после подключения:",
                "• аудит и прогресс по карточке,",
                "• работу с отзывами и новостями,",
                "• автоматизацию и Telegram-управление.",
                "",
                "Оплатить подписку можно в кабинете LocalOS.",
                f"Оплата: {urls['profile']}?payment=required",
            ]
        )

    tier = str(info.get("tier") or "trial").strip().lower()
    status = str(info.get("status") or "inactive").strip().lower()
    current_tariff = next(
        (
            payload
            for payload in TARIFFS.values()
            if str(payload.get("business_tier") or "").strip().lower() == tier
        ),
        None,
    )
    price_line = ""
    if current_tariff:
        price_line = f"• Стоимость: {int(current_tariff['amount'])} ₽/мес"
    lines = [
        "Подписка",
        f"Бизнес: {business_ctx['business_name']}",
        "",
        f"• Тариф: {_tier_label(tier)}",
        f"• Статус: {status}",
    ]
    if price_line:
        lines.append(price_line)
    if info.get("subscription_ends_at"):
        lines.append(f"• Действует до: {_format_date(info.get('subscription_ends_at'))}")
    if info.get("trial_ends_at"):
        lines.append(f"• Триал до: {_format_date(info.get('trial_ends_at'))}")
    lines.extend(
        [
            "",
            "Что открывает подписка:",
            "• управление карточкой и аудитами,",
            "• ответы на отзывы и новости,",
            "• автоматизации и рабочий Telegram-контур.",
            "",
            _subscription_upgrade_prompt(info, access),
            "",
            "Оплата и смена тарифа сейчас доступны в личном кабинете LocalOS.",
            f"К оплате: {urls['profile']}?payment=required",
        ]
    )
    if access.get("reason"):
        lines.extend(["", f"Комментарий: {access['reason']}"])
    return "\n".join(lines)
