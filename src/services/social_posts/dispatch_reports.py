from __future__ import annotations

import json
import os
import sys
import ipaddress
import urllib.error
import urllib.request
import urllib.parse
import uuid
from datetime import date, datetime, timezone
from typing import Any

from auth_encryption import decrypt_auth_data
from database_manager import DatabaseManager
from core.outbound_network import outbound_urlopen
from core.telegram_network import telegram_urlopen
from core.telegram_token_store import decode_telegram_bot_token
from core.helpers import get_business_owner_id
from services.media_file_storage import load_media_file
from services.openclaw_capability_catalog import get_openclaw_capability_catalog


SOCIAL_POST_PLATFORMS = [
    "yandex_maps",
    "two_gis",
    "google_business",
    "telegram",
    "vk",
    "instagram",
    "facebook",
]

API_PLATFORMS = {"google_business", "telegram", "vk", "instagram", "facebook"}
BROWSER_OR_MANUAL_PLATFORMS = {"yandex_maps", "two_gis"}
FIRST_API_PROOF_PLATFORMS = ("telegram", "vk")

SOCIAL_POST_STATUSES = {
    "draft",
    "needs_review",
    "approved",
    "queued",
    "publishing",
    "published",
    "failed",
    "needs_manual_publish",
    "needs_supervised_publish",
}

SOCIAL_POST_TABLES = (
    "social_posts",
    "social_post_metrics",
    "social_post_attribution_events",
)

SOCIAL_QUEUE_GROUPS = (
    {
        "key": "needs_review",
        "label_ru": "Нужно проверить",
        "label_en": "Needs review",
        "next_action_ru": "Проверить тексты и подтвердить публикации.",
        "next_action_en": "Review copy and approve posts.",
    },
    {
        "key": "api_ready",
        "label_ru": "Готово к API",
        "label_en": "API ready",
        "next_action_ru": "Поставить подтверждённые API-каналы в очередь публикации.",
        "next_action_en": "Queue approved API channels for publishing.",
    },
    {
        "key": "scheduled",
        "label_ru": "Запланировано",
        "label_en": "Scheduled",
        "next_action_ru": "Ждёт даты публикации. Исполнитель выполнит API-публикацию или создаст контролируемое размещение.",
        "next_action_en": "Waiting for schedule. The worker will publish via API or create supervised placement.",
    },
    {
        "key": "needs_supervised_publish",
        "label_ru": "Нужно контролируемое размещение",
        "label_en": "Needs supervised placement",
        "next_action_ru": "Открыть контролируемое размещение для Яндекс/2ГИС и остановиться перед финальной публикацией.",
        "next_action_en": "Open supervised Yandex/2GIS placement and stop before final publishing.",
    },
    {
        "key": "needs_manual_publish",
        "label_ru": "Нужно вручную / подключить канал",
        "label_en": "Manual / connection needed",
        "next_action_ru": "Подключить ключи или права, либо разместить вручную и отметить результат.",
        "next_action_en": "Connect keys or permissions, or publish manually and mark the result.",
    },
    {
        "key": "published",
        "label_ru": "Опубликовано",
        "label_en": "Published",
        "next_action_ru": "Собрать реакции и отметить заявки/обращения.",
        "next_action_en": "Collect reactions and record leads/inquiries.",
    },
    {
        "key": "failed",
        "label_ru": "Ошибка",
        "label_en": "Failed",
        "next_action_ru": "Исправить подключение, повторить публикацию или перевести в ручной режим.",
        "next_action_en": "Fix connection, retry, or move to manual publishing.",
    },
)

def _social_launch_runbook_success_criteria(
    external_publish_count: int,
    controlled_count: int,
    manual_count: int,
    skipped_no_access: int,
    is_ru: bool,
) -> list[str]:
    criteria = []
    if int(external_publish_count or 0) > 0:
        criteria.append(
            "API-каналы стали published или failed с recoverable причиной."
            if is_ru
            else "API channels become published or failed with a recoverable reason."
        )
    if int(controlled_count or 0) > 0:
        criteria.append(
            "Яндекс/2ГИС перешли в needs_supervised_publish/needs_manual_publish без финального клика."
            if is_ru
            else "Yandex/2GIS move to needs_supervised_publish/needs_manual_publish without the final click."
        )
    if int(manual_count or 0) > 0:
        criteria.append(
            "Manual fallback показывает инструкцию и copy-ready текст."
            if is_ru
            else "Manual fallback shows instructions and copy-ready text."
        )
    if int(skipped_no_access or 0) > 0:
        criteria.append(
            "Skipped posts остались без изменений и требуют проверки прав/scope."
            if is_ru
            else "Skipped posts remain unchanged and require permission/scope review."
        )
    if not criteria:
        criteria.append(
            "Worker не отправил ничего наружу, потому что due-постов нет."
            if is_ru
            else "The worker sends nothing externally because there are no due posts."
        )
    return criteria

def _social_launch_runbook_blocked_reason(
    scope: str,
    due_count: int,
    skipped_no_access: int,
    status: str,
    is_ru: bool,
) -> str:
    if str(status or "").strip() == "api_preflight_blocked":
        return (
            "Live API-preflight заблокировал первый цикл: есть due API-пост по каналу без готового подключения."
            if is_ru
            else "Live API preflight blocked the first cycle: a due API post targets a channel without a ready connection."
        )
    if not str(scope or "").strip():
        return (
            "Нельзя включать production dispatch без SOCIAL_POST_DISPATCH_BUSINESS_ID."
            if is_ru
            else "Do not enable production dispatch without SOCIAL_POST_DISPATCH_BUSINESS_ID."
        )
    if int(due_count or 0) <= 0:
        return (
            "Нет due-постов: сначала подготовьте, утвердите и поставьте публикации в расписание."
            if is_ru
            else "No due posts: prepare, approve, and queue publications first."
        )
    if int(skipped_no_access or 0) > 0:
        return (
            "Есть skipped_no_access: сначала проверьте права или business scope."
            if is_ru
            else "skipped_no_access exists: check permissions or business scope first."
        )
    return ""

def _dispatch_preview_recommended_env(business_scope: str) -> dict[str, str]:
    scope = str(business_scope or "").strip()
    return {
        "SOCIAL_POST_DISPATCH_ENABLED": "true",
        "SOCIAL_POST_DISPATCH_INTERVAL_SEC": "60",
        "SOCIAL_POST_DISPATCH_BATCH_SIZE": "10",
        "SOCIAL_POST_DISPATCH_BUSINESS_ID": scope,
    }

def collect_due_social_post_metrics(batch_size: int = 50, business_id: str = "") -> dict[str, Any]:
    picked: list[dict[str, Any]] = []
    business_scope = _social_metrics_business_scope(business_id)
    if not business_scope and not _social_metrics_allow_unscoped():
        return {
            "picked": 0,
            "collected": 0,
            "failed": 0,
            "errors": [],
            "business_scope": "",
            "blocked": True,
            "blocked_reason": "business_scope_required",
            "message": "SOCIAL_POST_METRICS_BUSINESS_ID is required unless SOCIAL_POST_METRICS_ALLOW_UNSCOPED=true.",
        }
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_social_post_tables(cursor)
        scope_clause = "AND sp.business_id = %s" if business_scope else ""
        params: list[Any] = []
        if business_scope:
            params.append(business_scope)
        params.append(max(1, min(int(batch_size or 50), 500)))
        cursor.execute(
            f"""
            SELECT sp.id, sp.business_id
            FROM social_posts sp
            LEFT JOIN social_post_metrics m
              ON m.social_post_id = sp.id
             AND m.metric_date = CURRENT_DATE
            WHERE sp.status = 'published'
              AND m.id IS NULL
              {scope_clause}
            ORDER BY sp.published_at ASC NULLS LAST, sp.updated_at ASC
            LIMIT %s
            """,
            tuple(params),
        )
        picked = [_row_to_dict(cursor, row) for row in cursor.fetchall() or []]
    finally:
        db.close()

    collected = 0
    failed = 0
    errors: list[dict[str, str]] = []
    details: list[dict[str, Any]] = []
    for item in picked:
        post_id = str(item.get("id") or "").strip()
        try:
            owner_id = _owner_id_for_business(str(item.get("business_id") or "").strip())
            if not owner_id:
                raise RuntimeError("business owner not found")
            payload = collect_social_post_metrics(owner_id, post_id=post_id)
            collected += int(payload.get("collected") or 0)
            if isinstance(payload.get("metric_details"), list):
                details.extend([detail for detail in payload.get("metric_details") or [] if isinstance(detail, dict)])
        except Exception:
            failed += 1
            errors.append({"id": post_id, "error": str(sys.exc_info()[1])})
            details.append({"id": post_id, "status": "failed", "source": "collector_error", "error": str(sys.exc_info()[1])})
    return {
        "picked": len(picked),
        "collected": collected,
        "failed": failed,
        "errors": errors,
        "details": details,
        "result_summaries_ru": _social_metrics_result_summaries(details, True),
        "result_summaries_en": _social_metrics_result_summaries(details, False),
        "business_scope": business_scope,
    }

def recommend_next_plan_from_social_posts(user_id: str, plan_id: str) -> dict[str, Any]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_social_post_tables(cursor)
        _load_plan_for_user(cursor, user_id, plan_id)
        posts_payload = list_social_posts_for_plan(user_id, plan_id)
        performance_rows = _social_plan_performance_rows(cursor, plan_id)
        posts = list(posts_payload.get("posts") or [])
        proposed_changes = _add_channel_breakdown_to_changes(
            _build_next_plan_changes(performance_rows),
            posts,
        )
        recommendation = dict(posts_payload.get("recommendation") or {})
        recommendation.update(
            _build_social_learning_insights(
                performance_rows,
                posts,
            )
        )
        application_preview = _social_recommendation_application_preview(cursor, plan_id, proposed_changes)
        return {
            "recommendation": recommendation,
            "proposed_changes": proposed_changes,
            "application_preview": application_preview,
            "learning_readiness": _social_learning_readiness(posts),
            "applies_automatically": False,
            "approval_required": True,
        }
    finally:
        db.close()

def apply_social_post_recommendation(user_id: str, plan_id: str, approved: bool = False) -> dict[str, Any]:
    if not approved:
        raise PermissionError("Для изменения контент-плана нужно явное подтверждение")
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_social_post_tables(cursor)
        plan = _load_plan_for_user(cursor, user_id, plan_id)
        recommendation_payload = recommend_next_plan_from_social_posts(user_id, plan_id)
        proposed_changes = [
            item for item in recommendation_payload.get("proposed_changes", [])
            if str(item.get("item_id") or "").strip() and str(item.get("proposed_goal") or "").strip()
        ]
        applied: list[dict[str, Any]] = []
        for change in proposed_changes:
            cursor.execute(
                """
                UPDATE contentplanitems
                SET goal = %s,
                    updated_at = NOW()
                WHERE id = %s
                  AND plan_id = %s
                  AND COALESCE(usernews_id, '') = ''
                  AND COALESCE(status, '') NOT IN ('skipped', 'published')
                  AND scheduled_for >= CURRENT_DATE
                RETURNING id, theme, goal
                """,
                (
                    str(change.get("proposed_goal") or "").strip(),
                    str(change.get("item_id") or "").strip(),
                    plan_id,
                ),
            )
            row = _row_to_dict(cursor, cursor.fetchone())
            if row:
                applied.append(row)
        edited_plan_json = _json_dict(plan.get("edited_plan_json"))
        history = edited_plan_json.get("social_recommendation_history")
        if not isinstance(history, list):
            history = []
        approval_record = {
            "source": "social_post_recommendation",
            "approved_by": user_id,
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "human_approved": True,
            "scope": "future_unpublished_content_plan_items",
            "recommendation": recommendation_payload,
            "proposed_count": len(proposed_changes),
            "applied_item_ids": [str(item.get("id") or "") for item in applied],
            "applied_count": len(applied),
        }
        edited_plan_json["last_social_recommendation_apply"] = approval_record
        edited_plan_json["social_recommendation_history"] = [*history, approval_record][-20:]
        cursor.execute(
            """
            UPDATE contentplans
            SET edited_plan_json = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (_json_dumps(edited_plan_json), plan_id),
        )
        db.conn.commit()
        return {
            "applied_count": len(applied),
            "applied_items": applied,
            "approval_record": approval_record,
            "applies_automatically": False,
            "application_preview": recommendation_payload.get("application_preview") or {},
            "recommendation": recommendation_payload.get("recommendation") or {},
            "proposed_changes": proposed_changes,
        }
    except Exception:
        db.conn.rollback()
        raise sys.exc_info()[1]
    finally:
        db.close()

def _social_recommendation_application_preview(
    cursor: Any,
    plan_id: str,
    proposed_changes: list[dict[str, Any]],
) -> dict[str, Any]:
    item_ids = [
        str(item.get("item_id") or "").strip()
        for item in proposed_changes
        if str(item.get("item_id") or "").strip()
    ]
    if not item_ids:
        return {
            "schema": "localos_social_recommendation_application_preview_v1",
            "scope": "future_unpublished_content_plan_items",
            "total": 0,
            "applicable_count": 0,
            "skipped_count": 0,
            "items": [],
            "summary_ru": "Нет изменений для применения.",
            "summary_en": "There are no changes to apply.",
        }
    cursor.execute(
        """
        SELECT id, theme, scheduled_for, status, usernews_id
        FROM contentplanitems
        WHERE plan_id = %s
          AND id = ANY(%s)
        """,
        (plan_id, item_ids),
    )
    rows = [_row_to_dict(cursor, row) for row in cursor.fetchall()]
    rows_by_id = {str(row.get("id") or "").strip(): row for row in rows}
    preview_items: list[dict[str, Any]] = []
    for change in proposed_changes:
        item_id = str(change.get("item_id") or "").strip()
        if not item_id:
            continue
        row = rows_by_id.get(item_id) or {}
        eligible, reason = _social_recommendation_application_eligibility(row)
        preview_items.append(
            {
                "item_id": item_id,
                "theme": str(change.get("theme") or row.get("theme") or "").strip(),
                "applicable": eligible,
                "skip_reason": "" if eligible else reason,
                "status": str(row.get("status") or "").strip(),
                "scheduled_for": _iso_or_empty(row.get("scheduled_for")),
                "has_news": bool(str(row.get("usernews_id") or "").strip()),
                "label_ru": "Будет изменён" if eligible else _social_recommendation_skip_reason_label(reason, True),
                "label_en": "Will be changed" if eligible else _social_recommendation_skip_reason_label(reason, False),
            }
        )
    applicable = sum(1 for item in preview_items if bool(item.get("applicable")))
    skipped = len(preview_items) - applicable
    return {
        "schema": "localos_social_recommendation_application_preview_v1",
        "scope": "future_unpublished_content_plan_items",
        "total": len(preview_items),
        "applicable_count": applicable,
        "skipped_count": skipped,
        "items": preview_items,
        "summary_ru": (
            f"Можно применить: {applicable}; будет пропущено: {skipped}. Меняются только будущие неопубликованные пункты."
        ),
        "summary_en": (
            f"Applicable: {applicable}; skipped: {skipped}. Only future unpublished items are changed."
        ),
    }

def _social_recommendation_application_eligibility(row: dict[str, Any]) -> tuple[bool, str]:
    if not row:
        return False, "missing_or_no_access"
    if str(row.get("usernews_id") or "").strip():
        return False, "already_has_news"
    status = str(row.get("status") or "").strip()
    if status in {"skipped", "published"}:
        return False, f"status_{status}"
    scheduled_for = row.get("scheduled_for")
    scheduled_date = scheduled_for.date() if isinstance(scheduled_for, datetime) else scheduled_for
    if isinstance(scheduled_date, str):
        try:
            scheduled_date = date.fromisoformat(scheduled_date[:10])
        except ValueError:
            scheduled_date = None
    if isinstance(scheduled_date, date) and scheduled_date < date.today():
        return False, "past_item"
    return True, ""

def _iso_or_empty(value: Any) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value or "").strip()

def _social_recommendation_skip_reason_label(reason: str, is_ru: bool) -> str:
    normalized = str(reason or "").strip()
    if normalized == "already_has_news":
        return "Уже создана новость" if is_ru else "News already exists"
    if normalized == "status_published":
        return "Уже опубликован" if is_ru else "Already published"
    if normalized == "status_skipped":
        return "Пропущен" if is_ru else "Skipped"
    if normalized == "past_item":
        return "Прошлая дата" if is_ru else "Past date"
    if normalized == "missing_or_no_access":
        return "Не найден в плане" if is_ru else "Not found in plan"
    return "Будет пропущен" if is_ru else "Will be skipped"

def _social_openclaw_browser_readiness(status: dict[str, Any] | None = None, cursor: Any | None = None) -> dict[str, Any]:
    capability_status = status if isinstance(status, dict) else openclaw_browser_capability_status()
    ready = bool(capability_status.get("ready"))
    delivery_readiness = _social_openclaw_handoff_delivery_readiness(cursor)
    handoff_ready = ready and bool(delivery_readiness.get("ready"))
    safety_contract = _social_supervised_safety_contract()
    missing_reason = str(capability_status.get("reason") or "").strip()
    catalog_error = missing_reason == "openclaw_catalog_error" or str(capability_status.get("source") or "").strip() == "catalog_error"
    private_sandbox_bridge = missing_reason == "sandbox_bridge_private_host" or str(capability_status.get("source") or "").strip() == "sandbox_bridge_private_host"
    if ready and handoff_ready:
        message_ru = "OpenClaw browser-use готов: Яндекс/2ГИС можно вести как контролируемое размещение без финального клика."
        message_en = "OpenClaw browser-use is ready: Yandex/2GIS can use supervised placement without the final click."
        next_action_ru = "Подготовьте контролируемое размещение у поста карты и проверьте предпросмотр перед финальным размещением."
        next_action_en = "Create supervised placement on the map post and review the preview before final placement."
    elif ready:
        message_ru = "OpenClaw browser-use найден, но доставка контролируемой задачи не готова: LocalOS подготовит ручной режим вместо внешней задачи."
        message_en = "OpenClaw browser-use is available, but supervised task delivery is not ready: LocalOS will prepare manual fallback instead of an external task."
        next_action_ru = str(delivery_readiness.get("next_action_ru") or "Настройте доставку задачи OpenClaw или используйте ручное размещение.").strip()
        next_action_en = str(delivery_readiness.get("next_action_en") or "Configure the OpenClaw callback/outbox or use manual placement.").strip()
    elif private_sandbox_bridge:
        message_ru = "OpenClaw browser-use не подтверждён: настроен только приватный sandbox bridge, поэтому Яндекс/2ГИС останутся в ручном режиме."
        message_en = "OpenClaw browser-use is not confirmed: only a private sandbox bridge is configured, so Yandex/2GIS will stay in manual fallback."
        next_action_ru = "Настройте публичный OPENCLAW_BASE_URL или OPENCLAW_SOCIAL_SUPERVISED_CALLBACK_URL для production handoff; до этого используйте ручное размещение."
        next_action_en = "Set a public OPENCLAW_BASE_URL or OPENCLAW_SOCIAL_SUPERVISED_CALLBACK_URL for production handoff; use manual placement until then."
    elif catalog_error:
        message_ru = "OpenClaw browser-use не подтверждён: LocalOS не смог прочитать capability catalog, поэтому Яндекс/2ГИС останутся в ручном режиме."
        message_en = "OpenClaw browser-use is not confirmed: LocalOS could not read the capability catalog, so Yandex/2GIS will stay in manual fallback."
        next_action_ru = "Проверьте доступность OPENCLAW_BASE_URL или OPENCLAW_SANDBOX_BRIDGE_URL с production VPS; до этого используйте ручное размещение."
        next_action_en = "Check that OPENCLAW_BASE_URL or OPENCLAW_SANDBOX_BRIDGE_URL is reachable from the production VPS; use manual placement until then."
    else:
        message_ru = "OpenClaw browser-use не подтверждён: Яндекс/2ГИС останутся в ручном fallback."
        message_en = "OpenClaw browser-use is not confirmed: Yandex/2GIS will stay in manual fallback."
        next_action_ru = "Проверьте capability catalog/OpenClaw настройки или используйте ручное размещение."
        next_action_en = "Check the capability catalog/OpenClaw settings or use manual placement."
    return {
        "ready": ready,
        "handoff_ready": handoff_ready,
        "status": "ready" if handoff_ready else "manual_fallback",
        "delivery_readiness": delivery_readiness,
        "capability": str(capability_status.get("capability") or "social.post.publish_supervised_browser").strip(),
        "action_ref": str(capability_status.get("action_ref") or "").strip(),
        "source": str(capability_status.get("source") or "").strip(),
        "provider_status": str(capability_status.get("status") or "").strip(),
        "reason": missing_reason,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "external_publish_performed": False,
        "browser_final_click_allowed": False,
        "stop_before_final_publish": True,
        "requires_final_human_confirmation": True,
        "side_effect_policy": str(safety_contract.get("side_effect_policy") or "fill_preview_only"),
        "final_publish_policy": str(safety_contract.get("final_publish_policy") or "human_final_click_required"),
        "allowed_actions": safety_contract.get("allowed_actions") if isinstance(safety_contract.get("allowed_actions"), list) else [],
        "forbidden_actions": safety_contract.get("forbidden_actions") if isinstance(safety_contract.get("forbidden_actions"), list) else [],
        "manual_fallback_triggers": safety_contract.get("manual_fallback_triggers") if isinstance(safety_contract.get("manual_fallback_triggers"), list) else [],
        "diagnostics_ru": _social_openclaw_browser_diagnostics(capability_status, True),
        "diagnostics_en": _social_openclaw_browser_diagnostics(capability_status, False),
        "message_ru": message_ru,
        "message_en": message_en,
        "next_action_ru": next_action_ru,
        "next_action_en": next_action_en,
    }

def _social_openclaw_handoff_delivery_readiness(cursor: Any | None = None) -> dict[str, Any]:
    callback_url = _social_supervised_openclaw_callback_url()
    callback_configured = bool(callback_url)
    suggested_callback_url = _social_supervised_openclaw_suggested_callback_url()
    suggestion_blocked_reason = _social_supervised_openclaw_suggested_callback_blocked_reason()
    outbox_available: bool | None = None
    if cursor is not None:
        try:
            outbox_available = _table_exists(cursor, "action_callback_outbox")
        except Exception:
            outbox_available = False
    ready = callback_configured and outbox_available is not False
    if ready:
        status = "ready"
        message_ru = "Доставка OpenClaw task готова: LocalOS сможет поставить controlled task в outbox."
        message_en = "OpenClaw task delivery is ready: LocalOS can enqueue a controlled task in the outbox."
        next_action_ru = "После approval создайте контролируемое размещение у поста Яндекс/2ГИС."
        next_action_en = "After approval, create supervised placement for the Yandex/2GIS post."
    elif not callback_configured:
        status = "callback_missing"
        message_ru = "Callback для OpenClaw supervised task не настроен; внешняя задача не будет отправлена."
        message_en = "The OpenClaw supervised task callback is not configured; no external task will be sent."
        if suggested_callback_url:
            next_action_ru = f"Добавьте OPENCLAW_SOCIAL_SUPERVISED_CALLBACK_URL={suggested_callback_url} или используйте ручное размещение."
            next_action_en = f"Set OPENCLAW_SOCIAL_SUPERVISED_CALLBACK_URL={suggested_callback_url} or use manual placement."
        elif suggestion_blocked_reason:
            next_action_ru = (
                "Укажите публичный/доступный OPENCLAW_SOCIAL_SUPERVISED_CALLBACK_URL или OPENCLAW_BASE_URL; "
                "текущий sandbox bridge не годится для доставки task из production."
            )
            next_action_en = (
                "Set a public/reachable OPENCLAW_SOCIAL_SUPERVISED_CALLBACK_URL or OPENCLAW_BASE_URL; "
                "the current sandbox bridge is not suitable for production task delivery."
            )
        else:
            next_action_ru = "Добавьте OPENCLAW_SOCIAL_SUPERVISED_CALLBACK_URL или используйте ручное размещение."
            next_action_en = "Set OPENCLAW_SOCIAL_SUPERVISED_CALLBACK_URL or use manual placement."
    else:
        status = "outbox_missing"
        message_ru = "Callback настроен, но action_callback_outbox недоступен; task не будет поставлена на доставку."
        message_en = "The callback is configured, but action_callback_outbox is unavailable; the task will not be queued for delivery."
        next_action_ru = "Проверьте миграции/outbox таблицу или используйте ручное размещение."
        next_action_en = "Check migrations/the outbox table or use manual placement."
    return {
        "ready": ready,
        "status": status,
        "callback_configured": callback_configured,
        "callback_url_configured": callback_configured,
        "callback_env_var": "OPENCLAW_SOCIAL_SUPERVISED_CALLBACK_URL",
        "suggested_callback_url": suggested_callback_url,
        "suggested_callback_blocked_reason": suggestion_blocked_reason,
        "outbox_available": outbox_available,
        "read_only": True,
        "external_publish_performed": False,
        "message_ru": message_ru,
        "message_en": message_en,
        "next_action_ru": next_action_ru,
        "next_action_en": next_action_en,
    }

def _social_openclaw_browser_diagnostics(capability_status: dict[str, Any], is_ru: bool) -> list[str]:
    source = str(capability_status.get("source") or "").strip()
    provider_status = str(capability_status.get("status") or "").strip()
    reason = str(capability_status.get("reason") or "").strip()
    action_ref = str(capability_status.get("action_ref") or "").strip()
    error = str(capability_status.get("error") or "").strip()
    ready = bool(capability_status.get("ready"))
    if is_ru:
        lines = [
            "Безопасная проверка: LocalOS только читает каталог возможностей OpenClaw и ничего не публикует.",
            f"Проверяемая возможность: {str(capability_status.get('capability') or 'social.post.publish_supervised_browser').strip()}.",
            "Финальная кнопка публикации запрещена до отдельного подтверждения человека.",
        ]
        if source:
            lines.append(f"Источник проверки: {source}.")
        if provider_status:
            lines.append(f"Статус провайдера: {provider_status}.")
        if action_ref:
            lines.append(f"Действие OpenClaw: {action_ref}.")
        if reason and not ready:
            lines.append(f"Причина ручного режима: {reason}.")
        if error and not ready and reason == "sandbox_bridge_private_host":
            lines.append("Sandbox bridge указывает на приватный или локальный адрес; production handoff через него не включается.")
        elif error and not ready:
            lines.append(f"Ошибка каталога OpenClaw: {error}.")
        if ready:
            lines.append("Следующий шаг: создать контролируемую задачу у поста Яндекс/2ГИС и проверить предпросмотр.")
        elif reason == "sandbox_bridge_private_host" or source == "sandbox_bridge_private_host":
            lines.append("Следующий шаг: настроить публичный OPENCLAW_BASE_URL/callback или использовать ручной режим.")
        elif reason == "openclaw_catalog_error" or source == "catalog_error":
            lines.append("Следующий шаг: сделать OpenClaw catalog доступным с production VPS или оставить ручной режим.")
        else:
            lines.append("Следующий шаг: проверить OPENCLAW_BASE_URL/catalog или использовать ручной режим.")
        return lines
    lines = [
        "Read-only check: LocalOS only reads the capability catalog and publishes nothing.",
        f"Capability: {str(capability_status.get('capability') or 'social.post.publish_supervised_browser').strip()}.",
        "The final publish button is forbidden until separate human confirmation.",
    ]
    if source:
        lines.append(f"Check source: {source}.")
    if provider_status:
        lines.append(f"Provider status: {provider_status}.")
    if action_ref:
        lines.append(f"OpenClaw action: {action_ref}.")
    if reason and not ready:
        lines.append(f"Fallback reason: {reason}.")
    if error and not ready and reason == "sandbox_bridge_private_host":
        lines.append("The sandbox bridge points to a private or local host; production handoff is not enabled through it.")
    elif error and not ready:
        lines.append(f"OpenClaw catalog error: {error}.")
    if ready:
        lines.append("Next step: create supervised Yandex/2GIS placement and review the preview.")
    elif reason == "sandbox_bridge_private_host" or source == "sandbox_bridge_private_host":
        lines.append("Next step: set a public OPENCLAW_BASE_URL/callback or use manual fallback.")
    elif reason == "openclaw_catalog_error" or source == "catalog_error":
        lines.append("Next step: make the OpenClaw catalog reachable from the production VPS or keep manual fallback.")
    else:
        lines.append("Next step: check OPENCLAW_BASE_URL/catalog or use manual fallback.")
    return lines

def openclaw_browser_capability_status(fetcher: Any = None) -> dict[str, Any]:
    env_value = str(os.getenv("OPENCLAW_BROWSER_USE_ENABLED") or os.getenv("OPENCLAW_BROWSER_USE_AVAILABLE") or "").strip().lower()
    if env_value in {"1", "true", "yes", "on", "enabled", "available"}:
        return {
            "ready": True,
            "source": "env_override",
            "status": "available",
            "reason": "browser_use_enabled_by_env",
            "action_ref": "openclaw.browser.supervised_publish",
            "capability": "social.post.publish_supervised_browser",
        }
    if env_value in {"0", "false", "no", "off", "disabled", "unavailable"}:
        return {
            "ready": False,
            "source": "env_override",
            "status": "disabled",
            "reason": "browser_use_disabled_by_env",
            "action_ref": "",
            "capability": "social.post.publish_supervised_browser",
        }
    sandbox_bridge_url = str(os.getenv("OPENCLAW_SANDBOX_BRIDGE_URL") or "").strip()
    if (
        not fetcher
        and sandbox_bridge_url
        and not (os.getenv("OPENCLAW_CAPABILITY_CATALOG_URL") or os.getenv("OPENCLAW_BASE_URL"))
        and _url_uses_private_or_local_host(sandbox_bridge_url)
        and not _env_flag_enabled("OPENCLAW_SOCIAL_SUPERVISED_ALLOW_SANDBOX_CALLBACK")
    ):
        return {
            "ready": False,
            "source": "sandbox_bridge_private_host",
            "status": "unreachable_from_production",
            "reason": "sandbox_bridge_private_host",
            "error": "OPENCLAW_SANDBOX_BRIDGE_URL points to a private/local host and is not allowed for production social browser-use.",
            "action_ref": "",
            "capability": "social.post.publish_supervised_browser",
        }
    if not fetcher and not (
        os.getenv("OPENCLAW_CAPABILITY_CATALOG_URL")
        or os.getenv("OPENCLAW_BASE_URL")
        or os.getenv("OPENCLAW_SANDBOX_BRIDGE_URL")
    ):
        return {
            "ready": False,
            "source": "not_configured",
            "status": "missing_catalog",
            "reason": "openclaw_catalog_not_configured",
            "action_ref": "",
            "capability": "social.post.publish_supervised_browser",
        }
    try:
        catalog = get_openclaw_capability_catalog(fetcher=fetcher)
    except Exception:
        return {
            "ready": False,
            "source": "catalog_error",
            "status": "error",
            "reason": "openclaw_catalog_error",
            "error": str(sys.exc_info()[1]),
            "action_ref": "",
            "capability": "social.post.publish_supervised_browser",
        }
    if isinstance(catalog, dict) and str(catalog.get("source") or "").strip() == "static_fallback" and str(catalog.get("error") or "").strip():
        return {
            "ready": False,
            "source": "catalog_error",
            "status": "error",
            "reason": "openclaw_catalog_error",
            "error": str(catalog.get("error") or "").strip(),
            "action_ref": "",
            "capability": "social.post.publish_supervised_browser",
        }
    for action in catalog.get("actions", []) if isinstance(catalog, dict) else []:
        if not isinstance(action, dict):
            continue
        action_status = str(action.get("status") or "").strip().lower()
        action_ref = str(action.get("openclaw_action_ref") or "").strip()
        capability = str(action.get("localos_capability") or "").strip()
        blob = " ".join(
            str(action.get(key) or "")
            for key in ("openclaw_action_ref", "title", "service", "localos_capability", "status")
        ).lower()
        supervised_browser = capability == "social.post.publish_supervised_browser" or (
            "browser" in blob and ("supervised" in blob or "fill_form" in blob or "publish" in blob)
        )
        if supervised_browser and action_status == "available":
            return {
                "ready": True,
                "source": str(catalog.get("source") or "openclaw") if isinstance(catalog, dict) else "openclaw",
                "status": "available",
                "reason": "openclaw_supervised_browser_available",
                "action_ref": action_ref,
                "capability": capability or "social.post.publish_supervised_browser",
            }
    return {
        "ready": False,
        "source": str(catalog.get("source") or "openclaw") if isinstance(catalog, dict) else "openclaw",
        "status": str(catalog.get("status") or "unavailable") if isinstance(catalog, dict) else "unavailable",
        "reason": "openclaw_supervised_browser_missing",
        "action_ref": "",
        "capability": "social.post.publish_supervised_browser",
        "error": str(catalog.get("error") or "") if isinstance(catalog, dict) else "",
    }

def openclaw_browser_available(fetcher: Any = None) -> bool:
    return bool(openclaw_browser_capability_status(fetcher=fetcher).get("ready"))

def default_publish_mode(platform: str, browser_available: bool | None = None) -> str:
    platform_key = str(platform or "").strip()
    if platform_key in API_PLATFORMS:
        return "api"
    if platform_key in BROWSER_OR_MANUAL_PLATFORMS:
        is_browser_available = openclaw_browser_available() if browser_available is None else bool(browser_available)
        return "openclaw_browser" if is_browser_available else "manual"
    return "manual"

def next_action_for_social_post(post: dict[str, Any]) -> str:
    status = str(post.get("status") or "").strip()
    platform = str(post.get("platform") or "").strip()
    if status in {"draft", "needs_review"}:
        return "review_required"
    if status == "approved" and platform in BROWSER_OR_MANUAL_PLATFORMS:
        return "start_supervised_publish"
    if status == "approved":
        return "wait_for_api_publish"
    if status == "queued" and platform in BROWSER_OR_MANUAL_PLATFORMS:
        return "wait_for_scheduled_supervised_publish"
    if status == "queued":
        return "wait_for_scheduled_publish"
    if status == "needs_supervised_publish":
        return "open_supervised_publish"
    if status == "needs_manual_publish":
        return "manual_publish"
    if status == "failed":
        return "retry_or_manual"
    if status == "published":
        return "collect_metrics"
    return "none"

def _status_after_social_text_edit(current_status: str, platform_text: str) -> str:
    if not str(platform_text or "").strip():
        return "draft"
    if str(current_status or "").strip() == "published":
        return "published"
    return "needs_review"

def _social_post_has_text(post: dict[str, Any]) -> bool:
    return bool(str(post.get("platform_text") or post.get("base_text") or "").strip())

def build_social_queue_groups(posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {str(group["key"]): [] for group in SOCIAL_QUEUE_GROUPS}
    for post in posts:
        key = _queue_group_key(post)
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(post)
    result = []
    for group in SOCIAL_QUEUE_GROUPS:
        key = str(group["key"])
        group_posts = grouped.get(key, [])
        result.append(
            {
                **group,
                "count": len(group_posts),
                "post_ids": [str(post.get("id") or "") for post in group_posts if str(post.get("id") or "").strip()],
                "item_ids": sorted(
                    {
                        str(post.get("content_plan_item_id") or "").strip()
                        for post in group_posts
                        if str(post.get("content_plan_item_id") or "").strip()
                    }
                ),
                "platforms": _summary_for_posts(group_posts).get("by_platform", {}),
            }
        )
    return result

def _queue_group_key(post: dict[str, Any]) -> str:
    status = str(post.get("status") or "").strip()
    platform = str(post.get("platform") or "").strip()
    if status in {"draft", "needs_review"}:
        return "needs_review"
    if status == "queued":
        return "scheduled"
    if status == "published":
        return "published"
    if status == "failed":
        return "failed"
    if status == "needs_manual_publish":
        return "needs_manual_publish"
    if platform in BROWSER_OR_MANUAL_PLATFORMS or status == "needs_supervised_publish":
        return "needs_supervised_publish"
    if platform in API_PLATFORMS and status in {"approved", "publishing"}:
        return "api_ready"
    return "needs_review"

def _preview_dispatch_decision(cursor: Any, post: dict[str, Any]) -> dict[str, Any]:
    platform = str(post.get("platform") or "").strip()
    publish_mode = str(post.get("publish_mode") or "").strip()
    scheduled_for = post.get("scheduled_for")
    approved_at = post.get("approved_at")
    item = {
        "id": str(post.get("id") or "").strip(),
        "business_id": str(post.get("business_id") or "").strip(),
        "content_plan_id": str(post.get("content_plan_id") or "").strip(),
        "content_plan_item_id": str(post.get("content_plan_item_id") or "").strip(),
        "platform": platform,
        "platform_label": platform_label(platform),
        "publish_mode": publish_mode,
        "scheduled_for": scheduled_for.isoformat() if isinstance(scheduled_for, (datetime, date)) else scheduled_for,
        "approved_at": approved_at.isoformat() if isinstance(approved_at, (datetime, date)) else approved_at,
        "current_status": str(post.get("status") or "").strip(),
        "dry_run": True,
    }
    if platform in BROWSER_OR_MANUAL_PLATFORMS:
        if not _social_post_has_text(post):
            return _with_dispatch_preview_labels(
                {
                    **item,
                    "dispatch_action": "manual_handoff",
                    "would_status": "needs_review",
                    "reason": "empty_post_copy",
                    "external_publish": False,
                    "approval_required": True,
                    "stop_before_final_publish": True,
                }
            )
        browser_ready = (
            publish_mode == "openclaw_browser"
            and openclaw_browser_available()
            and bool(_social_openclaw_handoff_delivery_readiness(cursor).get("ready"))
        )
        return _with_dispatch_preview_labels(
            {
                **item,
                "dispatch_action": "create_supervised_task" if browser_ready else "manual_handoff",
                "would_status": "needs_supervised_publish" if browser_ready else "needs_manual_publish",
                "reason": "openclaw_browser_ready" if browser_ready else "openclaw_browser_unavailable",
                "external_publish": False,
                "approval_required": True,
                "stop_before_final_publish": True,
            }
        )
    if publish_mode != "api":
        return _with_dispatch_preview_labels(
            {
                **item,
                "dispatch_action": "manual_handoff",
                "would_status": "needs_manual_publish",
                "reason": "publish_mode_not_api",
                "external_publish": False,
                "approval_required": True,
            }
        )
    if not _social_post_has_text(post):
        return _with_dispatch_preview_labels(
            {
                **item,
                "dispatch_action": "manual_handoff",
                "would_status": "needs_review",
                "reason": "empty_post_copy",
                "external_publish": False,
                "approval_required": True,
            }
        )
    queue_block = _queue_preflight_block(cursor, post)
    if queue_block:
        return _with_dispatch_preview_labels(
            {
                **item,
                "dispatch_action": "manual_handoff",
                "would_status": str(queue_block.get("status") or "needs_manual_publish"),
                "reason": str(queue_block.get("last_error") or "channel_not_ready"),
                "external_publish": False,
                "approval_required": True,
                "metadata_json": queue_block.get("metadata_json") or {},
            }
        )
    return _with_dispatch_preview_labels(
        {
            **item,
            "dispatch_action": "publish_api",
            "would_status": "published_or_failed",
            "reason": "channel_ready",
            "external_publish": True,
            "approval_required": True,
        }
    )

def _with_dispatch_preview_labels(item: dict[str, Any]) -> dict[str, Any]:
    action = str(item.get("dispatch_action") or "").strip()
    reason = str(item.get("reason") or "").strip()
    would_status = str(item.get("would_status") or "").strip()
    item["action_label_ru"] = _dispatch_preview_action_label(action, True)
    item["action_label_en"] = _dispatch_preview_action_label(action, False)
    item["reason_label_ru"] = _dispatch_preview_reason_label(reason, True)
    item["reason_label_en"] = _dispatch_preview_reason_label(reason, False)
    item["safety_summary_ru"] = _dispatch_preview_safety_summary(action, would_status, bool(item.get("external_publish")), True)
    item["safety_summary_en"] = _dispatch_preview_safety_summary(action, would_status, bool(item.get("external_publish")), False)
    return item

def _build_social_post_publish_rehearsal(cursor: Any, post: dict[str, Any]) -> dict[str, Any]:
    decision = _preview_dispatch_decision(cursor, post)
    current_status = str(post.get("status") or "").strip()
    platform = str(post.get("platform") or "").strip()
    has_approval = bool(post.get("approved_at")) or current_status in {"approved", "queued", "needs_supervised_publish"}
    has_text = _social_post_has_text(post)
    allowed_status = current_status in {"approved", "queued", "needs_supervised_publish"}
    blockers: list[dict[str, str]] = []
    if current_status == "published":
        blockers.append(
            {
                "code": "already_published",
                "message_ru": "Пост уже опубликован; следующий шаг - сбор реакций и заявок.",
                "message_en": "The post is already published; the next step is collecting reactions and leads.",
            }
        )
    elif not has_text:
        blockers.append(
            {
                "code": "missing_text",
                "message_ru": "Сначала заполните и сохраните текст поста.",
                "message_en": "Fill and save the post copy first.",
            }
        )
    elif not has_approval:
        blockers.append(
            {
                "code": "missing_approval",
                "message_ru": "Перед запуском человек должен подтвердить preview.",
                "message_en": "A human must approve the preview before launch.",
            }
        )
    elif not allowed_status:
        blockers.append(
            {
                "code": "not_queued_or_approved",
                "message_ru": "Пост ещё не утверждён и не поставлен в расписание.",
                "message_en": "The post is not approved or queued yet.",
            }
        )
    metadata = _json_dict(decision.get("metadata_json"))
    provider_status = str(metadata.get("provider_status") or metadata.get("queue_preflight_status") or "").strip()
    if provider_status:
        blockers.append(
            {
                "code": provider_status,
                "message_ru": str(metadata.get("queue_preflight_message_ru") or decision.get("reason_label_ru") or "").strip(),
                "message_en": str(metadata.get("queue_preflight_message_en") or decision.get("reason_label_en") or "").strip(),
            }
        )
    rules_readiness = evaluate_social_post_publish_rules(cursor, post)
    for item in rules_readiness:
        if str(item.get("severity") or "").strip() != "blocking" or bool(item.get("ready")):
            continue
        code = str(item.get("status") or "").strip()
        if any(str(blocker.get("code") or "") == code for blocker in blockers):
            continue
        blockers.append(
            {
                "code": code,
                "message_ru": str(item.get("message") or item.get("label") or "").strip(),
                "message_en": str(item.get("message_en") or item.get("message") or item.get("label") or "").strip(),
            }
        )
    ready_for_execution = not blockers and str(decision.get("dispatch_action") or "") in {
        "publish_api",
        "create_supervised_task",
    }
    return {
        "schema": "localos_social_publish_rehearsal_v1",
        "dry_run": True,
        "post_id": str(post.get("id") or "").strip(),
        "platform": platform,
        "platform_label": platform_label(platform),
        "publish_mode": str(post.get("publish_mode") or "").strip(),
        "current_status": current_status,
        "scheduled_for": decision.get("scheduled_for"),
        "approved_at": decision.get("approved_at"),
        "has_text": has_text,
        "has_approval": has_approval,
        "ready_for_execution": ready_for_execution,
        "external_publish_performed": False,
        "provider_write_performed": False,
        "would_external_publish": bool(decision.get("external_publish")) and ready_for_execution,
        "would_create_supervised_task": str(decision.get("dispatch_action") or "") == "create_supervised_task" and ready_for_execution,
        "browser_final_click_allowed": False,
        "stop_before_final_publish": bool(decision.get("stop_before_final_publish")) or platform in BROWSER_OR_MANUAL_PLATFORMS,
        "dispatch_decision": decision,
        "rules_readiness": rules_readiness,
        "blockers": blockers,
        "summary_ru": _publish_rehearsal_summary(ready_for_execution, decision, blockers, True),
        "summary_en": _publish_rehearsal_summary(ready_for_execution, decision, blockers, False),
        "next_action_ru": _publish_rehearsal_next_action(ready_for_execution, decision, blockers, True),
        "next_action_en": _publish_rehearsal_next_action(ready_for_execution, decision, blockers, False),
        "publish_evidence": _social_publish_evidence(post),
    }

def _social_publish_rehearsal_summary(rehearsals: list[dict[str, Any]], failed: list[dict[str, str]]) -> dict[str, Any]:
    total = len(rehearsals) + len(failed)
    ready = [item for item in rehearsals if bool(item.get("ready_for_execution"))]
    blocked = [item for item in rehearsals if not bool(item.get("ready_for_execution"))]
    api_ready = [item for item in ready if bool(item.get("would_external_publish"))]
    supervised_ready = [item for item in ready if bool(item.get("would_create_supervised_task"))]
    manual_or_blocked = len(blocked) + len(failed)
    status = "empty"
    if total > 0 and not ready:
        status = "blocked"
    elif total > 0 and manual_or_blocked > 0:
        status = "partial"
    elif total > 0:
        status = "ready"
    return {
        "status": status,
        "total": total,
        "ready": len(ready),
        "blocked": len(blocked),
        "failed": len(failed),
        "api_ready": len(api_ready),
        "supervised_ready": len(supervised_ready),
        "manual_or_blocked": manual_or_blocked,
        "external_publish_performed": False,
        "provider_write_performed": False,
        "browser_final_click_allowed": False,
        "message_ru": _social_publish_rehearsal_bulk_message(status, len(ready), len(api_ready), len(supervised_ready), manual_or_blocked, True),
        "message_en": _social_publish_rehearsal_bulk_message(status, len(ready), len(api_ready), len(supervised_ready), manual_or_blocked, False),
        "next_action_ru": _social_publish_rehearsal_bulk_next_action(status, blocked, failed, True),
        "next_action_en": _social_publish_rehearsal_bulk_next_action(status, blocked, failed, False),
    }

def _social_publish_rehearsal_bulk_message(
    status: str,
    ready: int,
    api_ready: int,
    supervised_ready: int,
    manual_or_blocked: int,
    is_ru: bool,
) -> str:
    if status == "ready":
        return (
            f"Проверка пройдена: готово {ready}, API {api_ready}, контролируемое размещение {supervised_ready}."
            if is_ru
            else f"Check passed: ready {ready}, API {api_ready}, supervised placement {supervised_ready}."
        )
    if status == "partial":
        return (
            f"Часть постов готова: {ready}. Требуют внимания: {manual_or_blocked}."
            if is_ru
            else f"Some posts are ready: {ready}. Need attention: {manual_or_blocked}."
        )
    if status == "blocked":
        return (
            f"Запуск пока заблокирован: требуют внимания {manual_or_blocked}."
            if is_ru
            else f"Launch is blocked for now: {manual_or_blocked} need attention."
        )
    return "Выберите посты для проверки запуска." if is_ru else "Select posts to check launch readiness."

def _social_publish_rehearsal_bulk_next_action(
    status: str,
    blocked: list[dict[str, Any]],
    failed: list[dict[str, str]],
    is_ru: bool,
) -> str:
    if status == "ready":
        return (
            "Можно ставить в расписание: API выйдет только по approval/дате, карты останутся контролируемыми."
            if is_ru
            else "You can queue them: API publishes only after approval/date, maps stay supervised."
        )
    if blocked:
        first = blocked[0]
        return str(first.get("next_action_ru" if is_ru else "next_action_en") or "").strip() or (
            "Исправьте первый блокер и повторите проверку."
            if is_ru
            else "Fix the first blocker and run the check again."
        )
    if failed:
        return (
            "Проверьте доступ к выбранным постам и повторите проверку."
            if is_ru
            else "Check access to the selected posts and run the check again."
        )
    return "Выберите посты и повторите проверку." if is_ru else "Select posts and run the check again."

def _publish_rehearsal_summary(
    ready_for_execution: bool,
    decision: dict[str, Any],
    blockers: list[dict[str, str]],
    is_ru: bool,
) -> str:
    action = str(decision.get("dispatch_action") or "").strip()
    if ready_for_execution and action == "publish_api":
        return (
            "Проверка пройдена: канал готов, при запуске worker сможет опубликовать пост по API."
            if is_ru
            else "Check passed: the channel is ready and the worker can publish this post through the API."
        )
    if ready_for_execution and action == "create_supervised_task":
        return (
            "Проверка пройдена: LocalOS создаст контролируемую задачу, финальная публикация останется за человеком."
            if is_ru
            else "Check passed: LocalOS will create a supervised task and final publishing stays human-controlled."
        )
    if blockers:
        message = str(blockers[0].get("message_ru" if is_ru else "message_en") or "").strip()
        return message or (
            "Проверка нашла блокер перед запуском."
            if is_ru
            else "The check found a launch blocker."
        )
    return (
        "Проверка выполнена: наружу ничего не отправлено."
        if is_ru
        else "Check completed: nothing was sent externally."
    )

def _publish_rehearsal_next_action(
    ready_for_execution: bool,
    decision: dict[str, Any],
    blockers: list[dict[str, str]],
    is_ru: bool,
) -> str:
    action = str(decision.get("dispatch_action") or "").strip()
    if ready_for_execution and action == "publish_api":
        return (
            "Поставьте пост в расписание или дождитесь worker’а, если он уже queued."
            if is_ru
            else "Queue the post or wait for the worker if it is already queued."
        )
    if ready_for_execution and action == "create_supervised_task":
        return (
            "Создайте контролируемое размещение и проверьте preview перед финальным действием."
            if is_ru
            else "Create supervised placement and review the preview before the final action."
        )
    if blockers:
        code = str(blockers[0].get("code") or "").strip()
        if code == "missing_text":
            return "Сохраните текст и повторите проверку." if is_ru else "Save the copy and run the check again."
        if code == "missing_approval":
            return "Откройте preview и подтвердите пост." if is_ru else "Open the preview and approve the post."
        if code in {"missing_connection", "missing_binding", "missing_permissions", "adapter_pending"}:
            return (
                "Подключите канал или используйте ручное размещение."
                if is_ru
                else "Connect the channel or use manual placement."
            )
        if code == "already_published":
            return "Соберите реакции и отметьте заявки." if is_ru else "Collect reactions and record leads."
    return (
        str(decision.get("safety_summary_ru") or "Проверьте статус поста и повторите запуск.")
        if is_ru
        else str(decision.get("safety_summary_en") or "Check the post status and try again.")
    )

def _dispatch_preview_action_label(action: str, is_ru: bool) -> str:
    clean = str(action or "").strip()
    if clean == "publish_api":
        return "API-публикация" if is_ru else "API publish"
    if clean == "create_supervised_task":
        return "Контролируемое размещение" if is_ru else "Supervised placement"
    if clean == "manual_handoff":
        return "Ручной режим" if is_ru else "Manual fallback"
    return "Без действия" if is_ru else "No action"

def _dispatch_preview_reason_label(reason: str, is_ru: bool) -> str:
    clean = str(reason or "").strip()
    if clean == "channel_ready":
        return "Канал готов, есть подтверждение и расписание." if is_ru else "Channel is ready, approved, and scheduled."
    if clean == "openclaw_browser_ready":
        return "OpenClaw browser-use доступен; будет создана контролируемая задача." if is_ru else "OpenClaw browser-use is available; a supervised task will be created."
    if clean == "openclaw_browser_unavailable":
        return "OpenClaw browser-use не подтверждён; нужен ручной режим." if is_ru else "OpenClaw browser-use is not confirmed; manual fallback is required."
    if clean == "empty_post_copy":
        return "Текст пустой: сначала верните пост на проверку и заполните copy." if is_ru else "Copy is empty: send the post back to review and fill it first."
    if clean == "publish_mode_not_api":
        return "Канал не настроен как API-публикация." if is_ru else "The channel is not configured for API publishing."
    if clean:
        return clean
    return "Причина не указана." if is_ru else "No reason provided."

def _dispatch_preview_safety_summary(action: str, would_status: str, external_publish: bool, is_ru: bool) -> str:
    clean_action = str(action or "").strip()
    clean_status = str(would_status or "").strip()
    if bool(external_publish):
        return (
            "Worker может отправить наружу только этот API-пост; итог будет published или failed."
            if is_ru
            else "The worker may send only this API post externally; result will be published or failed."
        )
    if clean_action == "create_supervised_task":
        return (
            "Worker создаст контролируемое размещение и не нажмёт финальную кнопку публикации."
            if is_ru
            else "The worker will create supervised placement and will not click the final publish button."
        )
    if clean_status == "needs_review":
        return (
            "Worker не будет публиковать: сначала нужен текст и повторное подтверждение."
            if is_ru
            else "The worker will not publish: copy and another review are required first."
        )
    return (
        "Worker не будет публиковать наружу; пост перейдёт в ручной понятный статус."
        if is_ru
        else "The worker will not publish externally; the post will move to a clear manual status."
    )

def _load_plan_item_for_user(cursor: Any, user_id: str, item_id: str) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT
            i.*,
            p.business_id AS plan_business_id,
            p.id AS parent_plan_id,
            p.title AS plan_title
        FROM contentplanitems i
        JOIN contentplans p ON p.id = i.plan_id
        WHERE i.id = %s
        """,
        (item_id,),
    )
    item = _row_to_dict(cursor, cursor.fetchone())
    if not item:
        raise ValueError("Пункт контент-плана не найден")
    business_id = str(item.get("business_id") or item.get("plan_business_id") or "").strip()
    _require_business_access(cursor, user_id, business_id)
    return item

def _load_plan_for_user(cursor: Any, user_id: str, plan_id: str) -> dict[str, Any]:
    cursor.execute("SELECT * FROM contentplans WHERE id = %s", (plan_id,))
    plan = _row_to_dict(cursor, cursor.fetchone())
    if not plan:
        raise ValueError("Контент-план не найден")
    _require_business_access(cursor, user_id, str(plan.get("business_id") or ""))
    return plan

def _content_plan_item_count(cursor: Any, plan_id: str) -> int:
    cursor.execute("SELECT COUNT(*) AS item_count FROM contentplanitems WHERE plan_id = %s", (plan_id,))
    row = cursor.fetchone()
    return int(_row_get(row, "item_count", 0, 0) or 0)

def _load_post_for_user(cursor: Any, user_id: str, post_id: str) -> dict[str, Any]:
    cursor.execute("SELECT * FROM social_posts WHERE id = %s", (post_id,))
    post = _serialize_social_post(cursor, cursor.fetchone())
    if not post:
        raise ValueError("Публикация не найдена")
    _require_business_access(cursor, user_id, str(post.get("business_id") or ""))
    return post

def _require_business_access(cursor: Any, user_id: str, business_id: str) -> None:
    owner_id = get_business_owner_id(cursor, business_id)
    if str(owner_id or "").strip() == str(user_id or "").strip():
        return
    cursor.execute("SELECT COALESCE(is_superadmin, FALSE) FROM users WHERE id = %s", (user_id,))
    row = cursor.fetchone()
    if bool(_row_get(row, "coalesce", 0, False)):
        return
    raise PermissionError("Нет доступа к бизнесу")

def _upsert_social_post(cursor: Any, user_id: str, item: dict[str, Any], platform: str, base_text: str) -> dict[str, Any]:
    item_id = str(item.get("id") or "").strip()
    plan_id = str(item.get("plan_id") or item.get("parent_plan_id") or "").strip()
    business_id = str(item.get("business_id") or item.get("plan_business_id") or "").strip()
    scheduled_for = item.get("scheduled_for")
    publish_mode = default_publish_mode(platform)
    platform_text = _platform_text(platform, base_text)
    status = "needs_review" if platform_text.strip() else "draft"
    cursor.execute(
        """
        INSERT INTO social_posts (
            id, business_id, content_plan_id, content_plan_item_id, platform, publish_mode, status,
            scheduled_for, base_text, platform_text, media_json, metadata_json, created_by, created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, '[]', %s, %s, NOW(), NOW())
        ON CONFLICT (content_plan_item_id, platform)
        DO UPDATE SET
            scheduled_for = EXCLUDED.scheduled_for,
            base_text = CASE
                WHEN social_posts.status IN ('published', 'queued', 'publishing') THEN social_posts.base_text
                ELSE EXCLUDED.base_text
            END,
            platform_text = CASE
                WHEN social_posts.status IN ('published', 'queued', 'publishing') THEN social_posts.platform_text
                ELSE EXCLUDED.platform_text
            END,
            publish_mode = EXCLUDED.publish_mode,
            status = CASE
                WHEN social_posts.status IN ('published', 'queued', 'publishing') THEN social_posts.status
                WHEN social_posts.status = 'approved'
                  AND COALESCE(social_posts.base_text, '') = COALESCE(EXCLUDED.base_text, '')
                  AND COALESCE(social_posts.platform_text, '') = COALESCE(EXCLUDED.platform_text, '')
                THEN social_posts.status
                ELSE EXCLUDED.status
            END,
            approved_at = CASE
                WHEN social_posts.status IN ('published', 'queued', 'publishing') THEN social_posts.approved_at
                WHEN social_posts.status = 'approved'
                  AND COALESCE(social_posts.base_text, '') = COALESCE(EXCLUDED.base_text, '')
                  AND COALESCE(social_posts.platform_text, '') = COALESCE(EXCLUDED.platform_text, '')
                THEN social_posts.approved_at
                ELSE NULL
            END,
            approval_id = CASE
                WHEN social_posts.status IN ('published', 'queued', 'publishing') THEN social_posts.approval_id
                WHEN social_posts.status = 'approved'
                  AND COALESCE(social_posts.base_text, '') = COALESCE(EXCLUDED.base_text, '')
                  AND COALESCE(social_posts.platform_text, '') = COALESCE(EXCLUDED.platform_text, '')
                THEN social_posts.approval_id
                ELSE NULL
            END,
            metadata_json = EXCLUDED.metadata_json,
            updated_at = NOW()
        RETURNING *
        """,
        (
            _new_id(),
            business_id,
            plan_id,
            item_id,
            platform,
            publish_mode,
            status,
            scheduled_for,
            base_text,
            platform_text,
            _json_dumps(_initial_metadata(platform, publish_mode)),
            user_id,
        ),
    )
    return _serialize_social_post(cursor, cursor.fetchone())

def _existing_social_posts_for_item(cursor: Any, item_id: str) -> dict[str, dict[str, Any]]:
    cursor.execute(
        """
        SELECT *
        FROM social_posts
        WHERE content_plan_item_id = %s
        """,
        (item_id,),
    )
    result: dict[str, dict[str, Any]] = {}
    for row in cursor.fetchall() or []:
        post = _serialize_social_post(cursor, row)
        platform = str(post.get("platform") or "").strip()
        if platform:
            result[platform] = post
    return result

def _preview_social_post_for_platform(
    item: dict[str, Any],
    platform: str,
    base_text: str,
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    item_id = str(item.get("id") or "").strip()
    plan_id = str(item.get("plan_id") or item.get("parent_plan_id") or "").strip()
    business_id = str(item.get("business_id") or item.get("plan_business_id") or "").strip()
    publish_mode = default_publish_mode(platform)
    platform_text = _platform_text(platform, base_text)
    status = "needs_review" if platform_text.strip() else "draft"
    existing_post = existing if isinstance(existing, dict) else {}
    existing_status = str(existing_post.get("status") or "").strip()
    prepare_action = "would_create"
    preview_status = status
    preview_base_text = base_text
    preview_platform_text = platform_text
    if existing_post:
        prepare_action = "would_update"
        text_unchanged = (
            str(existing_post.get("base_text") or "").strip() == str(base_text or "").strip()
            and str(existing_post.get("platform_text") or "").strip() == str(platform_text or "").strip()
        )
        if existing_status in {"published", "queued", "publishing"} or (existing_status == "approved" and text_unchanged):
            prepare_action = f"preserve_{existing_status}"
            preview_status = existing_status
            preview_base_text = str(existing_post.get("base_text") or base_text or "").strip()
            preview_platform_text = str(existing_post.get("platform_text") or platform_text or "").strip()
    metadata = _initial_metadata(platform, publish_mode)
    metadata["prepare_preview"] = True
    metadata["read_only"] = True
    return {
        "id": str(existing_post.get("id") or "").strip(),
        "business_id": business_id,
        "content_plan_id": plan_id,
        "content_plan_item_id": item_id,
        "platform": platform,
        "platform_label": platform_label(platform),
        "publish_mode": publish_mode,
        "status": preview_status,
        "scheduled_for": item.get("scheduled_for"),
        "base_text": preview_base_text,
        "platform_text": preview_platform_text,
        "media_json": existing_post.get("media_json") if existing_post else [],
        "metadata_json": metadata,
        "prepare_action": prepare_action,
        "existing_status": existing_status,
        "read_only": True,
        "external_publish_performed": False,
    }

def _initial_metadata(platform: str, publish_mode: str) -> dict[str, Any]:
    data = {
        "platform_label": platform_label(platform),
        "approval_required": True,
        "source": "localos_content_plan",
    }
    if platform in BROWSER_OR_MANUAL_PLATFORMS:
        data["supervised_notice"] = "Канал требует ручного или контролируемого размещения; это не production API."
        data["browser_mode_available"] = publish_mode == "openclaw_browser"
    if platform in {"instagram", "facebook"}:
        data["permissions_notice"] = "Публикация зависит от Meta Graph permissions и подключенной страницы/аккаунта."
    return data

def _supervised_publish_metadata(cursor: Any, post: dict[str, Any], automation_task_id: str) -> dict[str, Any]:
    platform = str(post.get("platform") or "").strip()
    target = _map_publish_target(cursor, str(post.get("business_id") or ""), platform)
    task_payload = _build_openclaw_supervised_task_payload(post, automation_task_id, target)
    capability_status = openclaw_browser_capability_status()
    manual_handoff = _manual_publish_handoff_payload(post, target, "browser_capability_unavailable")
    safety_contract = _social_supervised_safety_contract()
    completion_contract = _social_supervised_completion_contract()
    handoff_checklist = _social_supervised_handoff_checklist()
    handoff_state = _social_supervised_handoff_state(post, task_payload, capability_status)
    return {
        "automation_task_id": automation_task_id,
        "openclaw_task": task_payload,
        "supervised_publish": {
            "mode": str(post.get("publish_mode") or "manual"),
            "platform": platform,
            "platform_label": platform_label(platform),
            "capability": str(task_payload.get("capability") or "social.post.publish_supervised_browser").strip(),
            "openclaw_action_ref": str(task_payload.get("openclaw_action_ref") or "openclaw.browser.supervised_publish").strip(),
            "task_status": str(task_payload.get("status") or "ready_for_supervised_or_manual_handoff").strip(),
            "target_url": target.get("target_url", ""),
            "target_url_source": target.get("target_url_source", ""),
            "profile_hint": target.get("profile_hint", ""),
            "copy_ready_text": str(post.get("platform_text") or post.get("base_text") or "").strip(),
            "instruction_ru": "Открыть площадку, вставить текст и медиа, показать предпросмотр, остановиться перед финальной публикацией до подтверждения.",
            "instruction_en": "Open the platform, fill text and media, show preview, and stop before final publish until explicit approval.",
            "manual_instruction_ru": manual_handoff["instruction_ru"],
            "manual_instruction_en": manual_handoff["instruction_en"],
            "handoff_checklist_ru": handoff_checklist["ru"],
            "handoff_checklist_en": handoff_checklist["en"],
            "manual_checklist_ru": manual_handoff["checklist_ru"],
            "manual_checklist_en": manual_handoff["checklist_en"],
            "manual_handoff": manual_handoff,
            "stop_before_final_publish": True,
            "final_publish_policy": "human_final_click_required",
            "handoff_state": handoff_state,
            "safety_contract": safety_contract,
            "completion_contract": completion_contract,
            "operator_next_action_ru": str(task_payload.get("operator_next_action_ru") or "").strip(),
            "operator_next_action_en": str(task_payload.get("operator_next_action_en") or "").strip(),
            "fallback_reasons": ["captcha", "login_required", "changed_ui", "browser_capability_unavailable"],
            "openclaw_capability_status": capability_status,
        },
    }

def _supervised_publish_state(post: dict[str, Any], cursor: Any | None = None) -> dict[str, str | None]:
    publish_mode = str(post.get("publish_mode") or "").strip()
    browser_ready = (
        publish_mode == "openclaw_browser"
        and openclaw_browser_available()
        and bool(_social_openclaw_handoff_delivery_readiness(cursor).get("ready"))
    )
    return {
        "status": "needs_supervised_publish" if browser_ready else "needs_manual_publish",
        "last_error": None if browser_ready else "OpenClaw browser-use или доставка supervised task недоступны; используйте ручное контролируемое размещение.",
    }

def _social_supervised_handoff_state(
    post: dict[str, Any],
    task_payload: dict[str, Any],
    capability_status: dict[str, Any],
    ledger_id: str = "",
) -> dict[str, Any]:
    publish_mode = str(post.get("publish_mode") or "").strip()
    openclaw_ready = publish_mode == "openclaw_browser" and bool(capability_status.get("ready"))
    state = "ready_for_openclaw_handoff" if openclaw_ready else "manual_fallback_required"
    if openclaw_ready:
        owner_status_ru = "Задача готова для контролируемого OpenClaw browser-use."
        owner_status_en = "Task is ready for supervised OpenClaw browser-use."
        owner_next_action_ru = "Откройте контролируемое размещение, проверьте предпросмотр и подтвердите финальное действие человеком."
        owner_next_action_en = "Open supervised placement, review the preview, and let a human confirm the final action."
    else:
        owner_status_ru = "OpenClaw browser-use не подтверждён; включён ручной режим."
        owner_status_en = "OpenClaw browser-use is not confirmed; manual fallback is active."
        owner_next_action_ru = "Скопируйте готовый текст, разместите пост вручную и отметьте публикацию размещённой."
        owner_next_action_en = "Copy the prepared text, publish it manually, and mark the post as published."
    return {
        "schema": "localos_social_supervised_handoff_state_v1",
        "state": state,
        "publish_mode": publish_mode,
        "openclaw_ready": openclaw_ready,
        "task_payload_ready": bool(task_payload.get("task_id")),
        "openclaw_task_requested": False,
        "ledger_recorded": bool(str(ledger_id or "").strip()),
        "ledger_id": str(ledger_id or "").strip(),
        "owner_status_ru": owner_status_ru,
        "owner_status_en": owner_status_en,
        "owner_next_action_ru": owner_next_action_ru,
        "owner_next_action_en": owner_next_action_en,
        "stop_before_final_publish": True,
        "final_publish_policy": "human_final_click_required",
        "browser_final_click_allowed": False,
    }

def _build_openclaw_supervised_task_payload(
    post: dict[str, Any],
    automation_task_id: str,
    target: dict[str, Any] | None = None,
) -> dict[str, Any]:
    platform = str(post.get("platform") or "").strip()
    target_payload = target if isinstance(target, dict) else {}
    text = str(post.get("platform_text") or post.get("base_text") or "").strip()
    safety_contract = _social_supervised_safety_contract()
    completion_contract = _social_supervised_completion_contract()
    done_criteria = _social_supervised_done_criteria()
    handoff_checklist = _social_supervised_handoff_checklist()
    return {
        "schema": "localos_social_supervised_publish_task_v1",
        "task_id": str(automation_task_id or "").strip(),
        "capability": "social.post.publish_supervised_browser",
        "openclaw_action_ref": "openclaw.browser.supervised_publish",
        "risk_class": "external_publish",
        "approval_class": "external_publish",
        "approval_required": True,
        "stop_before_final_publish": True,
        "auto_final_click_allowed": False,
        "safety_contract": safety_contract,
        "completion_contract": completion_contract,
        "handoff_checklist_ru": handoff_checklist["ru"],
        "handoff_checklist_en": handoff_checklist["en"],
        "done_criteria_ru": done_criteria["ru"],
        "done_criteria_en": done_criteria["en"],
        "operator_next_action_ru": "Заполнить форму, показать предпросмотр и остановиться до финальной публикации; результат вернуть как preview_ready или manual_fallback.",
        "operator_next_action_en": "Fill the form, show the preview, and stop before final publishing; return preview_ready or manual_fallback.",
        "status": "ready_for_supervised_or_manual_handoff",
        "platform": platform,
        "platform_label": platform_label(platform),
        "business": {
            "id": str(post.get("business_id") or "").strip(),
            "name": str(target_payload.get("business_name") or "").strip(),
            "location_label": str(target_payload.get("location_label") or "").strip(),
        },
        "target": {
            "url": str(target_payload.get("target_url") or "").strip(),
            "url_source": str(target_payload.get("target_url_source") or "").strip(),
            "profile_hint": str(target_payload.get("profile_hint") or "").strip(),
        },
        "content": {
            "text": text,
            "media": post.get("media_json") if isinstance(post.get("media_json"), list) else [],
        },
        "approval_evidence": {
            "social_post_id": str(post.get("id") or "").strip(),
            "content_plan_id": str(post.get("content_plan_id") or "").strip(),
            "content_plan_item_id": str(post.get("content_plan_item_id") or "").strip(),
            "approved_at": str(post.get("approved_at") or "").strip(),
            "approval_id": str(post.get("approval_id") or "").strip(),
        },
        "instructions": {
            "ru": [
                "Открыть целевую площадку или профиль бизнеса.",
                "Вставить подготовленный текст и медиа.",
                "Показать предпросмотр человеку.",
                "Остановиться перед финальной кнопкой публикации.",
                "Если логин, капча или интерфейс изменился, вернуть manual fallback.",
            ],
            "en": [
                "Open the target platform or business profile.",
                "Fill the prepared text and media.",
                "Show preview to a human.",
                "Stop before the final publish button.",
                "If login, captcha, or UI changed, return manual fallback.",
            ],
        },
        "fallback": {
            "status": "needs_manual_publish",
            "reasons": ["captcha", "login_required", "changed_ui", "browser_capability_unavailable"],
            "manual_instruction_ru": "Скопируйте текст из LocalOS, разместите его на площадке вручную и отметьте публикацию размещённой.",
            "manual_instruction_en": "Copy the text from LocalOS, publish it manually on the platform, and mark the post as published.",
        },
    }

def _social_supervised_completion_contract() -> dict[str, Any]:
    done_criteria = _social_supervised_done_criteria()
    return {
        "schema": "localos_social_supervised_completion_contract_v1",
        "success_state": "preview_ready",
        "fallback_state": "manual_fallback_required",
        "preview_required": True,
        "final_publish_click_owner": "human",
        "browser_final_click_allowed": False,
        "external_publish_performed_by_task": False,
        "required_result_fields": [
            "status",
            "preview_available",
            "target_url",
            "filled_text",
            "blocked_reason",
        ],
        "allowed_result_statuses": [
            "preview_ready",
            "manual_fallback_required",
            "blocked_by_login",
            "blocked_by_captcha",
            "blocked_by_changed_ui",
            "blocked_by_missing_target",
        ],
        "manual_fallback_triggers": [
            "captcha",
            "login_required",
            "changed_ui",
            "missing_target_url",
            "browser_capability_unavailable",
            "unexpected_external_prompt",
        ],
        "done_criteria_ru": done_criteria["ru"],
        "done_criteria_en": done_criteria["en"],
        "owner_completion_instruction_ru": "После предпросмотра человек сам нажимает финальную публикацию и отмечает пост размещённым в LocalOS.",
        "owner_completion_instruction_en": "After preview, a human clicks the final publish button and marks the post as published in LocalOS.",
    }

def _social_supervised_done_criteria() -> dict[str, list[str]]:
    return {
        "ru": [
            "Предпросмотр на площадке показан человеку.",
            "Финальную публикацию нажал человек, не браузер-автоматизация.",
            "В LocalOS внесена ссылка или ID опубликованного поста, если площадка их даёт.",
            "Пост отмечен размещённым, чтобы реакции и заявки попали в следующий план.",
        ],
        "en": [
            "The platform preview was shown to a human.",
            "The final publish click was made by a human, not browser automation.",
            "LocalOS has the published post URL or ID if the platform provides one.",
            "The post is marked as published so reactions and leads can inform the next plan.",
        ],
    }

def _social_supervised_handoff_checklist() -> dict[str, list[str]]:
    return {
        "ru": [
            "Открыть профиль нужной точки на площадке.",
            "Вставить подготовленный текст и медиа из LocalOS.",
            "Показать предпросмотр человеку и сверить, что площадка/точка выбраны верно.",
            "Остановиться перед финальной кнопкой публикации.",
            "После ручного финального клика сохранить ссылку или ID и отметить пост размещённым.",
        ],
        "en": [
            "Open the correct location profile on the platform.",
            "Paste the prepared LocalOS copy and media.",
            "Show the preview to a human and verify the platform/location.",
            "Stop before the final publish button.",
            "After the human final click, save the URL or ID and mark the post as published.",
        ],
    }

def _social_supervised_safety_contract() -> dict[str, Any]:
    return {
        "schema": "localos_social_supervised_safety_contract_v1",
        "risk_class": "external_publish",
        "approval_class": "external_publish",
        "side_effect_policy": "fill_preview_only",
        "final_publish_policy": "human_final_click_required",
        "provider_write_performed_by_localos": False,
        "external_publish_performed_by_openclaw": False,
        "stop_before_final_publish": True,
        "auto_final_click_allowed": False,
        "requires_final_human_confirmation": True,
        "allowed_actions": [
            "open_platform",
            "fill_text",
            "attach_media",
            "show_preview",
            "return_task_status",
        ],
        "forbidden_actions": [
            "click_final_publish",
            "bypass_login",
            "solve_captcha_without_user",
            "change_business_profile_data",
            "publish_without_human_confirmation",
        ],
        "manual_fallback_triggers": [
            "captcha",
            "login_required",
            "changed_ui",
            "missing_target_url",
            "browser_capability_unavailable",
            "unexpected_external_prompt",
        ],
    }

def _manual_publish_handoff_payload(post: dict[str, Any], target: dict[str, Any], reason: str = "") -> dict[str, Any]:
    platform = str(post.get("platform") or "").strip()
    text = str(post.get("platform_text") or post.get("base_text") or "").strip()
    target_url = str(target.get("target_url") or "").strip()
    reason_text = str(reason or "").strip()
    checklist_ru = [
        "Скопировать готовый текст из LocalOS.",
        "Открыть профиль площадки для нужной точки бизнеса.",
        "Вставить текст и медиа в форму публикации.",
        "Проверить предпросмотр и не публиковать без финального подтверждения.",
        "После размещения вставить ссылку или ID поста и нажать «Отметить размещённым».",
    ]
    checklist_en = [
        "Copy the prepared text from LocalOS.",
        "Open the platform profile for the right business location.",
        "Paste text and media into the post form.",
        "Review the preview and do not publish without final confirmation.",
        "After publishing, paste the post URL or ID and click Mark published.",
    ]
    return {
        "schema": "localos_social_manual_publish_handoff_v1",
        "platform": platform,
        "platform_label": platform_label(platform),
        "target_url": target_url,
        "target_url_source": str(target.get("target_url_source") or "").strip(),
        "profile_hint": str(target.get("profile_hint") or "").strip(),
        "copy_ready_text": text,
        "reason": reason_text,
        "instruction_ru": "Разместите этот пост вручную или под контролем OpenClaw. LocalOS хранит текст, ссылку на площадку и чеклист, а финальная публикация остаётся за человеком.",
        "instruction_en": "Publish this post manually or with OpenClaw supervision. LocalOS keeps the copy, platform link, and checklist, while final publishing stays human-controlled.",
        "checklist_ru": checklist_ru,
        "checklist_en": checklist_en,
        "final_publish_policy": "human_final_click_required",
        "stop_before_final_publish": True,
        "browser_final_click_allowed": False,
    }
