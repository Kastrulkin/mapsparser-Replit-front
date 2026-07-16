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

def _social_launch_runtime_alignment(business_id: str) -> dict[str, Any]:
    scope = str(business_id or "").strip()
    dispatch_multi_tenant = _social_dispatch_multi_tenant()
    dispatch_scope = "" if dispatch_multi_tenant else str(os.getenv("SOCIAL_POST_DISPATCH_BUSINESS_ID") or "").strip()
    dispatch_enabled = _social_bool_env("SOCIAL_POST_DISPATCH_ENABLED")
    dispatch_allow_unscoped = _social_dispatch_allow_unscoped()
    metrics_multi_tenant = _social_metrics_multi_tenant()
    metrics_scope = "" if metrics_multi_tenant else str(os.getenv("SOCIAL_POST_METRICS_BUSINESS_ID") or "").strip()
    metrics_enabled = _social_bool_env("SOCIAL_POST_METRICS_ENABLED")
    metrics_allow_unscoped = _social_metrics_allow_unscoped()

    if not dispatch_enabled:
        dispatch_status = "dispatch_disabled"
    elif dispatch_scope and dispatch_scope == scope:
        dispatch_status = "ready"
    elif dispatch_scope and dispatch_scope != scope:
        dispatch_status = "scope_mismatch"
    elif dispatch_allow_unscoped:
        dispatch_status = "unscoped_allowed"
    else:
        dispatch_status = "blocked_without_scope"

    if not metrics_enabled:
        metrics_status = "metrics_disabled"
    elif metrics_scope and metrics_scope == scope:
        metrics_status = "ready"
    elif metrics_scope and metrics_scope != scope:
        metrics_status = "scope_mismatch"
    elif metrics_allow_unscoped:
        metrics_status = "unscoped_allowed"
    else:
        metrics_status = "blocked_without_scope"

    dispatch_can_process_this_business = dispatch_status in {"ready", "unscoped_allowed"}
    metrics_can_collect_this_business = metrics_status in {"ready", "unscoped_allowed"}
    return {
        "schema": "localos_social_launch_runtime_alignment_v1",
        "business_id": scope,
        "dispatch": {
            "enabled": dispatch_enabled,
            "mode": "multi_tenant" if dispatch_multi_tenant else "scoped",
            "business_scope": dispatch_scope,
            "allow_unscoped": dispatch_allow_unscoped,
            "status": dispatch_status,
            "can_process_this_business": dispatch_can_process_this_business,
            "message_ru": _social_launch_runtime_message("dispatch", dispatch_status, dispatch_scope, scope, True),
            "message_en": _social_launch_runtime_message("dispatch", dispatch_status, dispatch_scope, scope, False),
        },
        "metrics": {
            "enabled": metrics_enabled,
            "mode": "multi_tenant" if metrics_multi_tenant else "scoped",
            "business_scope": metrics_scope,
            "allow_unscoped": metrics_allow_unscoped,
            "status": metrics_status,
            "can_collect_this_business": metrics_can_collect_this_business,
            "message_ru": _social_launch_runtime_message("metrics", metrics_status, metrics_scope, scope, True),
            "message_en": _social_launch_runtime_message("metrics", metrics_status, metrics_scope, scope, False),
        },
        "next_action_ru": _social_launch_runtime_next_action(dispatch_status, metrics_status, scope, True),
        "next_action_en": _social_launch_runtime_next_action(dispatch_status, metrics_status, scope, False),
    }

def _social_launch_runtime_message(kind: str, status: str, runtime_scope: str, business_scope: str, is_ru: bool) -> str:
    label_ru = "Dispatch" if kind == "dispatch" else "Сбор реакций"
    label_en = "Dispatch" if kind == "dispatch" else "Metrics"
    label = label_ru if is_ru else label_en
    if status in {"dispatch_disabled", "metrics_disabled"}:
        return (
            f"{label} выключен: можно готовить и ставить посты в расписание, но внешний цикл сам не стартует."
            if is_ru
            else f"{label} is disabled: posts can be prepared and queued, but the external loop will not start by itself."
        )
    if status == "ready":
        return (
            f"{label} включён для этого бизнеса ({business_scope})."
            if is_ru
            else f"{label} is enabled for this business ({business_scope})."
        )
    if status == "scope_mismatch":
        return (
            f"{label} включён для другого бизнеса ({runtime_scope}); текущий бизнес {business_scope} не будет обработан."
            if is_ru
            else f"{label} is scoped to another business ({runtime_scope}); current business {business_scope} will not be processed."
        )
    if status == "unscoped_allowed":
        return (
            f"{label} включён без scope через явный allow-all; для первого запуска безопаснее указать business scope."
            if is_ru
            else f"{label} is enabled without a scope via explicit allow-all; a business scope is safer for the first launch."
        )
    return (
        f"{label} включён, но заблокирован защитой: нужен business scope."
        if is_ru
        else f"{label} is enabled but guarded: a business scope is required."
    )

def _social_launch_runtime_next_action(dispatch_status: str, metrics_status: str, business_scope: str, is_ru: bool) -> str:
    if dispatch_status == "dispatch_disabled":
        return (
            f"Для автозапуска включите SOCIAL_POST_DISPATCH_ENABLED=true и SOCIAL_POST_DISPATCH_BUSINESS_ID={business_scope}."
            if is_ru
            else f"To auto-run, enable SOCIAL_POST_DISPATCH_ENABLED=true and SOCIAL_POST_DISPATCH_BUSINESS_ID={business_scope}."
        )
    if dispatch_status == "blocked_without_scope":
        return (
            f"Добавьте SOCIAL_POST_DISPATCH_BUSINESS_ID={business_scope}, иначе исполнитель не начнёт внешние действия."
            if is_ru
            else f"Add SOCIAL_POST_DISPATCH_BUSINESS_ID={business_scope}; otherwise the worker will not start external actions."
        )
    if dispatch_status == "scope_mismatch":
        return (
            f"Смените SOCIAL_POST_DISPATCH_BUSINESS_ID на {business_scope} или запускайте другой бизнес."
            if is_ru
            else f"Change SOCIAL_POST_DISPATCH_BUSINESS_ID to {business_scope} or run the other business."
        )
    if metrics_status in {"metrics_disabled", "blocked_without_scope", "scope_mismatch"}:
        return (
            "Публикации можно исполнять, но для learning loop отдельно включите сбор реакций с тем же business scope."
            if is_ru
            else "Publishing can run, but enable metrics with the same business scope to close the learning loop."
        )
    return (
        "Исполнитель совпадает с текущим бизнесом: после подтверждения и расписания он может выполнить первый цикл."
        if is_ru
        else "Runtime matches this business: after approval and queueing, the worker can run the first cycle."
    )

def dispatch_due_social_posts(batch_size: int = 20, business_id: str = "") -> dict[str, Any]:
    picked: list[dict[str, Any]] = []
    business_scope = _social_dispatch_business_scope(business_id)
    if not business_scope and not _social_dispatch_allow_unscoped():
        return {
            "picked": 0,
            "published": 0,
            "supervised": 0,
            "manual": 0,
            "failed": 0,
            "by_status": {},
            "by_action": {"blocked_without_scope": 1},
            "details": [],
            "errors": [],
            "posts": [],
            "business_scope": "",
            "blocked": True,
            "blocked_reason": "business_scope_required",
            "message": "SOCIAL_POST_DISPATCH_BUSINESS_ID is required unless SOCIAL_POST_DISPATCH_ALLOW_UNSCOPED=true.",
        }
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_social_post_tables(cursor)
        scope_clause = "AND sp.business_id = %s" if business_scope else ""
        params: list[Any] = []
        if business_scope:
            params.append(business_scope)
        params.append(max(1, min(int(batch_size or 20), 200)))
        cursor.execute(
            f"""
            SELECT sp.id, sp.business_id, sp.platform, sp.status, sp.scheduled_for
            FROM social_posts sp
            WHERE sp.status = 'queued'
              AND sp.approved_at IS NOT NULL
              AND COALESCE(sp.scheduled_for, NOW()) <= NOW()
              {scope_clause}
            ORDER BY sp.scheduled_for ASC NULLS FIRST, sp.updated_at ASC
            LIMIT %s
            """,
            tuple(params),
        )
        picked = [_row_to_dict(cursor, row) for row in cursor.fetchall() or []]
    finally:
        db.close()

    published = 0
    supervised = 0
    manual = 0
    failed = 0
    errors: list[dict[str, str]] = []
    posts: list[dict[str, Any]] = []
    details: list[dict[str, Any]] = []
    by_status: dict[str, int] = {}
    by_action: dict[str, int] = {}
    for item in picked:
        post_id = str(item.get("id") or "").strip()
        business_id = str(item.get("business_id") or "").strip()
        owner_id = ""
        try:
            owner_id = _owner_id_for_business(business_id)
            if not owner_id:
                raise RuntimeError("business owner not found")
            post = _dispatch_live_api_preflight_block(owner_id, post_id) or publish_social_post(owner_id, post_id)
            posts.append(post)
            status = str(post.get("status") or "").strip()
            action = _dispatch_action_for_status(status)
            by_status[status or "unknown"] = by_status.get(status or "unknown", 0) + 1
            by_action[action] = by_action.get(action, 0) + 1
            details.append(
                {
                    "id": post_id,
                    "business_id": business_id,
                    "platform": str(post.get("platform") or item.get("platform") or "").strip(),
                    "status": status,
                    "action": action,
                    "automation_task_id": str(post.get("automation_task_id") or "").strip(),
                    "provider_post_id": str(post.get("provider_post_id") or "").strip(),
                    "provider_post_url": str(post.get("provider_post_url") or "").strip(),
                    "last_error": str(post.get("last_error") or "").strip(),
                }
            )
            if status == "published":
                published += 1
            elif status == "needs_supervised_publish":
                supervised += 1
            elif status == "needs_manual_publish":
                manual += 1
            elif status == "failed":
                failed += 1
        except Exception:
            failed += 1
            message = str(sys.exc_info()[1])
            errors.append({"id": post_id, "error": message})
            by_status["failed"] = by_status.get("failed", 0) + 1
            by_action["failed"] = by_action.get("failed", 0) + 1
            details.append(
                {
                    "id": post_id,
                    "business_id": business_id,
                    "platform": str(item.get("platform") or "").strip(),
                    "status": "failed",
                    "action": "failed",
                    "automation_task_id": "",
                    "provider_post_id": "",
                    "provider_post_url": "",
                    "last_error": message,
                }
            )
            _mark_dispatch_failure(post_id, message)
    return {
        "picked": len(picked),
        "published": published,
        "supervised": supervised,
        "manual": manual,
        "failed": failed,
        "by_status": by_status,
        "by_action": by_action,
        "details": details,
        "errors": errors,
        "posts": posts,
        "business_scope": business_scope,
        "followup_actions_ru": _social_dispatch_followup_actions(
            len(picked), published, supervised, manual, failed, errors, True
        ),
        "followup_actions_en": _social_dispatch_followup_actions(
            len(picked), published, supervised, manual, failed, errors, False
        ),
        "result_summaries_ru": _social_dispatch_result_summaries(details, True),
        "result_summaries_en": _social_dispatch_result_summaries(details, False),
    }

def _dispatch_live_api_preflight_block(user_id: str, post_id: str) -> dict[str, Any] | None:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_social_post_tables(cursor)
        post = _load_post_for_user(cursor, user_id, post_id)
        platform = str(post.get("platform") or "").strip()
        publish_mode = str(post.get("publish_mode") or "").strip()
        if platform not in API_PLATFORMS or publish_mode != "api":
            return None
        preflight = _api_channel_preflight_for_platform(cursor, str(post.get("business_id") or ""), platform)
        if bool(preflight.get("ready")):
            return None
        status = str(preflight.get("status") or "not_ready").strip()
        metadata = _json_dict(post.get("metadata_json"))
        metadata.update(
            {
                "provider_status": status,
                "queue_preflight_status": status,
                "queue_preflight_ready": False,
                "queue_preflight_live_checked_at": datetime.now(timezone.utc).isoformat(),
                "queue_preflight_source": "worker_dispatch_live_api_preflight",
                "queue_preflight_message_ru": str(preflight.get("message_ru") or "").strip(),
                "queue_preflight_message_en": str(preflight.get("message_en") or "").strip(),
            }
        )
        cursor.execute(
            """
            UPDATE social_posts
            SET status = 'needs_manual_publish',
                metadata_json = %s,
                last_error = %s,
                updated_at = NOW()
            WHERE id = %s
            RETURNING *
            """,
            (
                _json_dumps(metadata),
                _queue_preflight_error(platform, status),
                post_id,
            ),
        )
        updated = _serialize_social_post(cursor, cursor.fetchone())
        db.conn.commit()
        return updated
    except Exception:
        db.conn.rollback()
        raise sys.exc_info()[1]
    finally:
        db.close()

def run_scoped_social_dispatch_once(
    user_id: str,
    business_id: str,
    batch_size: int = 10,
    approved: bool = False,
    approval_text: str = "",
) -> dict[str, Any]:
    if not approved:
        raise PermissionError("Для запуска первого цикла публикаций нужно явное подтверждение")
    normalized_business_id = str(business_id or "").strip()
    if not normalized_business_id:
        raise ValueError("Бизнес не выбран")
    clean_batch_size = max(1, min(int(batch_size or 10), 50))
    preflight = get_social_launch_preflight(user_id, normalized_business_id, batch_size=clean_batch_size)
    launch_gate = preflight.get("launch_gate") if isinstance(preflight.get("launch_gate"), dict) else {}
    if launch_gate and not bool(launch_gate.get("allowed")):
        raise PermissionError(
            str(launch_gate.get("next_action_ru") or "").strip()
            or "Preflight не разрешил запуск первого scoped цикла"
        )
    summary = preflight.get("summary") if isinstance(preflight.get("summary"), dict) else {}
    if int(summary.get("skipped_no_access") or 0) > 0:
        raise PermissionError("Есть посты на текущую дату вне доступа текущего пользователя; проверьте бизнес для запуска")
    if int(summary.get("api_preflight_blocked_due_posts") or 0) > 0:
        raise PermissionError("Live API-проверка нашла неготовый канал; исправьте ключи/права или переведите пост в ручной режим")
    api_due_posts = int(summary.get("api_due_posts") or launch_gate.get("api_posts") or 0)
    if api_due_posts > 0 and not _social_external_publish_confirmation_matches(approval_text):
        phrase = _social_external_publish_confirmation_phrase()
        raise PermissionError(f"Для API-публикации подтвердите внешний запуск фразой: {phrase}")
    dispatch_result = dispatch_due_social_posts(
        batch_size=clean_batch_size,
        business_id=normalized_business_id,
    )
    execution_report = _social_dispatch_execution_report(dispatch_result)
    return {
        "approved": True,
        "business_id": normalized_business_id,
        "batch_size": clean_batch_size,
        "preflight": preflight,
        "dispatch_result": dispatch_result,
        "execution_report": execution_report,
        "external_publish_only_after_approval": True,
        "external_publish_confirmation_phrase": _social_external_publish_confirmation_phrase() if api_due_posts > 0 else "",
        "browser_final_click_allowed": False,
        "maps_are_supervised_or_manual": True,
        "message_ru": _social_dispatch_once_message(dispatch_result, True),
        "message_en": _social_dispatch_once_message(dispatch_result, False),
    }

def _social_external_publish_confirmation_phrase() -> str:
    return "ПУБЛИКУЮ"

def _social_external_publish_confirmation_matches(value: str) -> bool:
    return str(value or "").strip().upper() == _social_external_publish_confirmation_phrase()

def run_scoped_social_metrics_once(
    user_id: str,
    business_id: str,
    batch_size: int = 25,
    approved: bool = False,
) -> dict[str, Any]:
    if not approved:
        raise PermissionError("Для сбора реакций нужно явное подтверждение")
    normalized_business_id = str(business_id or "").strip()
    if not normalized_business_id:
        raise ValueError("Бизнес не выбран")
    clean_batch_size = max(1, min(int(batch_size or 25), 100))
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_social_post_tables(cursor)
        _require_business_access(cursor, user_id, normalized_business_id)
    finally:
        db.close()
    metrics_result = collect_due_social_post_metrics(
        batch_size=clean_batch_size,
        business_id=normalized_business_id,
    )
    return {
        "approved": True,
        "business_id": normalized_business_id,
        "batch_size": clean_batch_size,
        "metrics_result": metrics_result,
        "metrics_learning_packet": _social_metrics_learning_packet(metrics_result),
        "external_publish_performed": False,
        "message_ru": _social_metrics_once_message(metrics_result, True),
        "message_en": _social_metrics_once_message(metrics_result, False),
    }

def _social_dispatch_once_message(result: dict[str, Any], is_ru: bool) -> str:
    picked = int(result.get("picked") or 0)
    published = int(result.get("published") or 0)
    supervised = int(result.get("supervised") or 0)
    manual = int(result.get("manual") or 0)
    failed = int(result.get("failed") or 0)
    if picked <= 0:
        return (
            "Due-постов для этого бизнеса нет; внешний запуск ничего не отправил."
            if is_ru
            else "There are no due posts for this business; no external action was sent."
        )
    if is_ru:
        return (
            f"Первый scoped цикл выполнен: взято {picked}, опубликовано {published}, "
            f"контролируемое размещение {supervised}, вручную {manual}, ошибок {failed}."
        )
    return (
        f"First scoped cycle finished: picked {picked}, published {published}, "
        f"supervised {supervised}, manual {manual}, failed {failed}."
    )

def _social_dispatch_execution_report(dispatch_result: dict[str, Any]) -> dict[str, Any]:
    details = dispatch_result.get("details") if isinstance(dispatch_result.get("details"), list) else []
    by_status = dispatch_result.get("by_status") if isinstance(dispatch_result.get("by_status"), dict) else {}
    by_action = dispatch_result.get("by_action") if isinstance(dispatch_result.get("by_action"), dict) else {}
    errors = dispatch_result.get("errors") if isinstance(dispatch_result.get("errors"), list) else []
    picked = int(dispatch_result.get("picked") or 0)
    published = int(dispatch_result.get("published") or 0)
    supervised = int(dispatch_result.get("supervised") or 0)
    manual = int(dispatch_result.get("manual") or 0)
    failed = int(dispatch_result.get("failed") or 0)
    status = "empty"
    if failed > 0:
        status = "attention"
    elif manual > 0:
        status = "manual_action_needed"
    elif picked > 0:
        status = "completed"
    first_api_proof_summary = _social_dispatch_first_api_proof_summary(details)
    post_publish_learning_gate = _social_post_publish_learning_gate(details, first_api_proof_summary)
    return {
        "schema": "localos_social_dispatch_execution_report_v1",
        "status": status,
        "picked": picked,
        "published": published,
        "supervised": supervised,
        "manual": manual,
        "failed": failed,
        "business_scope": str(dispatch_result.get("business_scope") or "").strip(),
        "by_status": by_status,
        "by_action": by_action,
        "details": details,
        "errors": errors,
        "external_publish_only_after_approval": True,
        "maps_are_supervised_or_manual": True,
        "browser_final_click_allowed": False,
        "provider_write_summary": {
            "api_publish_attempted": published > 0 or bool(by_action.get("failed")),
            "published_with_provider_proof": len(
                [
                    item for item in details
                    if str(item.get("status") or "").strip() == "published"
                    and (
                        str(item.get("provider_post_id") or "").strip()
                        or str(item.get("provider_post_url") or "").strip()
                    )
                ]
            ),
            "supervised_tasks_created": len(
                [
                    item for item in details
                    if str(item.get("status") or "").strip() == "needs_supervised_publish"
                    and str(item.get("automation_task_id") or "").strip()
                ]
            ),
        },
        "first_api_proof_summary": first_api_proof_summary,
        "post_publish_learning_gate": post_publish_learning_gate,
        "after_run_proof_packet": _social_after_run_proof_packet(
            status,
            picked,
            published,
            supervised,
            manual,
            failed,
            first_api_proof_summary,
            post_publish_learning_gate,
        ),
        "title_ru": _social_dispatch_execution_title(status, True),
        "title_en": _social_dispatch_execution_title(status, False),
        "summary_ru": _social_dispatch_execution_summary(picked, published, supervised, manual, failed, True),
        "summary_en": _social_dispatch_execution_summary(picked, published, supervised, manual, failed, False),
        "next_action_ru": _social_dispatch_execution_next_action(status, errors, True),
        "next_action_en": _social_dispatch_execution_next_action(status, errors, False),
    }

def _social_after_run_proof_packet(
    status: str,
    picked: int,
    published: int,
    supervised: int,
    manual: int,
    failed: int,
    first_api_proof_summary: dict[str, Any],
    post_publish_learning_gate: dict[str, Any],
) -> dict[str, Any]:
    api_proof_ready = bool(first_api_proof_summary.get("ready"))
    can_collect = bool(post_publish_learning_gate.get("can_collect_metrics"))
    has_maps_handoff = int(supervised or 0) > 0 or int(manual or 0) > 0
    has_failures = int(failed or 0) > 0
    if has_failures:
        proof_status = "needs_recovery"
    elif api_proof_ready and can_collect:
        proof_status = "loop_proven_collect_results"
    elif can_collect:
        proof_status = "published_collect_results"
    elif has_maps_handoff:
        proof_status = "finish_maps_handoff"
    elif int(picked or 0) <= 0:
        proof_status = "no_due_posts"
    else:
        proof_status = "check_details"
    return {
        "schema": "localos_social_after_run_proof_packet_v1",
        "status": proof_status,
        "dispatch_status": str(status or "").strip(),
        "picked": int(picked or 0),
        "published": int(published or 0),
        "supervised": int(supervised or 0),
        "manual": int(manual or 0),
        "failed": int(failed or 0),
        "api_proof_ready": api_proof_ready,
        "can_collect_results": can_collect,
        "maps_handoff_created": has_maps_handoff,
        "browser_final_click_allowed": False,
        "primary_metric_ru": "Заявки и обращения",
        "primary_metric_en": "Leads and inquiries",
        "title_ru": _social_after_run_proof_title(proof_status, True),
        "title_en": _social_after_run_proof_title(proof_status, False),
        "next_action_ru": _social_after_run_proof_next_action(proof_status, True),
        "next_action_en": _social_after_run_proof_next_action(proof_status, False),
        "checks_ru": _social_after_run_proof_checks(proof_status, True),
        "checks_en": _social_after_run_proof_checks(proof_status, False),
    }

def _social_after_run_proof_title(status: str, is_ru: bool) -> str:
    if status == "loop_proven_collect_results":
        return "Цикл доказан: собирайте результат" if is_ru else "Loop proven: collect results"
    if status == "published_collect_results":
        return "Пост опубликован: добавьте proof и результат" if is_ru else "Post published: add proof and results"
    if status == "finish_maps_handoff":
        return "Карты ждут контролируемое размещение" if is_ru else "Maps wait for supervised placement"
    if status == "needs_recovery":
        return "Есть ошибки запуска" if is_ru else "Launch has errors"
    if status == "no_due_posts":
        return "На текущую дату нечего запускать" if is_ru else "No due posts to run"
    return "Проверьте детали запуска" if is_ru else "Check launch details"

def _social_after_run_proof_next_action(status: str, is_ru: bool) -> str:
    if status == "loop_proven_collect_results":
        return (
            "Нажмите “Собрать реакции”, отметьте заявки/обращения и откройте предложения следующего плана."
            if is_ru
            else "Click “Collect reactions”, record leads/inquiries, and open next-plan suggestions."
        )
    if status == "published_collect_results":
        return (
            "Сохраните provider_post_id/provider_post_url, затем соберите реакции и отметьте заявки."
            if is_ru
            else "Save provider_post_id/provider_post_url, then collect reactions and record leads."
        )
    if status == "finish_maps_handoff":
        return (
            "Откройте пакет размещения Яндекс/2ГИС, завершите публикацию человеком и отметьте размещённым."
            if is_ru
            else "Open the Yandex/2GIS placement packet, finish publishing as a human, and mark it published."
        )
    if status == "needs_recovery":
        return (
            "Откройте ошибочные посты, исправьте ключи/права или переведите в ручной режим."
            if is_ru
            else "Open failed posts, fix keys/permissions, or move them to manual mode."
        )
    if status == "no_due_posts":
        return (
            "Подтвердите посты, поставьте их в расписание на текущую дату и повторите запуск."
            if is_ru
            else "Approve posts, queue them for the current date, and run again."
        )
    return (
        "Сверьте статусы published/failed/needs_supervised_publish и обновите результат."
        if is_ru
        else "Check published/failed/needs_supervised_publish statuses and update results."
    )

def _social_after_run_proof_checks(status: str, is_ru: bool) -> list[str]:
    if is_ru:
        return [
            "Сверьте provider_post_id/provider_post_url для API-поста.",
            "Проверьте, что Яндекс/2ГИС не были автопубликованы без человека.",
            "Соберите реакции и вручную отметьте заявки/обращения.",
            "Откройте рекомендации следующего плана только после результата.",
        ]
    return [
        "Verify provider_post_id/provider_post_url for the API post.",
        "Confirm Yandex/2GIS were not autopublished without a human.",
        "Collect reactions and manually record leads/inquiries.",
        "Open next-plan recommendations only after results exist.",
    ]

def _social_post_publish_learning_gate(
    details: list[dict[str, Any]],
    first_api_proof_summary: dict[str, Any],
) -> dict[str, Any]:
    published_items = [
        item for item in details or []
        if str(item.get("status") or "").strip() == "published"
    ]
    failed_items = [
        item for item in details or []
        if str(item.get("status") or "").strip() == "failed"
    ]
    manual_or_supervised = [
        item for item in details or []
        if str(item.get("status") or "").strip() in {"needs_manual_publish", "needs_supervised_publish"}
    ]
    proof_ready = bool(first_api_proof_summary.get("ready"))
    can_collect = len(published_items) > 0
    if proof_ready:
        status = "ready_for_metrics_and_attribution"
    elif can_collect:
        status = "published_without_api_proof"
    elif manual_or_supervised:
        status = "finish_supervised_or_manual_publish"
    elif failed_items:
        status = "fix_failed_publish"
    else:
        status = "publish_first"
    return {
        "schema": "localos_social_post_publish_learning_gate_v1",
        "status": status,
        "allowed": can_collect,
        "can_collect_metrics": can_collect,
        "can_record_attribution": can_collect,
        "api_proof_ready": proof_ready,
        "published_posts": len(published_items),
        "published_with_api_proof": int(first_api_proof_summary.get("published_with_provider_proof") or 0),
        "manual_or_supervised_posts": len(manual_or_supervised),
        "failed_posts": len(failed_items),
        "primary_metric_ru": "Заявки и обращения",
        "primary_metric_en": "Leads and inquiries",
        "external_publish_performed": False,
        "summary_ru": _social_post_publish_learning_gate_summary(status, True),
        "summary_en": _social_post_publish_learning_gate_summary(status, False),
        "next_action_ru": _social_post_publish_learning_gate_next_action(status, True),
        "next_action_en": _social_post_publish_learning_gate_next_action(status, False),
        "learning_actions": _social_post_publish_learning_actions(status),
    }

def _social_post_publish_learning_actions(status: str) -> list[dict[str, Any]]:
    if status in {"ready_for_metrics_and_attribution", "published_without_api_proof"}:
        return [
            {
                "key": "collect_reactions",
                "order": 1,
                "enabled": True,
                "label_ru": "Собрать реакции",
                "label_en": "Collect reactions",
                "summary_ru": "Обновить просмотры, комментарии и доступные provider-метрики без новой публикации.",
                "summary_en": "Update views, comments, and available provider metrics without publishing again.",
                "primary_metric": False,
            },
            {
                "key": "record_leads",
                "order": 2,
                "enabled": True,
                "label_ru": "Отметить заявки/обращения",
                "label_en": "Record leads/inquiries",
                "summary_ru": "Главный KPI: заявки и обращения важнее охватов и лайков.",
                "summary_en": "Main KPI: leads and inquiries matter more than reach and likes.",
                "primary_metric": True,
            },
            {
                "key": "recommend_next_plan",
                "order": 3,
                "enabled": True,
                "label_ru": "Предложить изменения следующего плана",
                "label_en": "Suggest next-plan changes",
                "summary_ru": "LocalOS предлагает изменения, но не применяет их без подтверждения.",
                "summary_en": "LocalOS suggests changes but does not apply them without approval.",
                "primary_metric": False,
            },
        ]
    if status == "finish_supervised_or_manual_publish":
        return [
            {
                "key": "finish_manual_or_supervised_publish",
                "order": 1,
                "enabled": True,
                "label_ru": "Завершить ручное/контролируемое размещение",
                "label_en": "Finish manual/supervised placement",
                "summary_ru": "Сначала разместите пост на площадке человеком и сохраните ссылку или ID.",
                "summary_en": "Publish on the platform as a human first and save the URL or ID.",
                "primary_metric": False,
            }
        ]
    if status == "fix_failed_publish":
        return [
            {
                "key": "recover_failed_publish",
                "order": 1,
                "enabled": True,
                "label_ru": "Исправить ошибку публикации",
                "label_en": "Recover failed publish",
                "summary_ru": "Проверьте ключи, права или переведите пост в ручной режим.",
                "summary_en": "Check keys, permissions, or move the post to manual flow.",
                "primary_metric": False,
            }
        ]
    return [
        {
            "key": "publish_first",
            "order": 1,
            "enabled": False,
            "label_ru": "Сначала опубликовать пост",
            "label_en": "Publish a post first",
            "summary_ru": "Сбор результата появится после published или ручной отметки размещения.",
            "summary_en": "Result collection appears after published status or manual publish marking.",
            "primary_metric": False,
        }
    ]

def _social_post_publish_learning_gate_summary(status: str, is_ru: bool) -> str:
    if status == "ready_for_metrics_and_attribution":
        return (
            "API-публикация доказана: можно собирать реакции и отмечать заявки/обращения."
            if is_ru
            else "API publishing is proven: collect reactions and record leads/inquiries."
        )
    if status == "published_without_api_proof":
        return (
            "Есть опубликованные посты, но первый API-proof неполный: сохраните ссылку или provider ID, затем собирайте реакции."
            if is_ru
            else "Published posts exist, but first API proof is incomplete: save URL or provider ID, then collect reactions."
        )
    if status == "finish_supervised_or_manual_publish":
        return (
            "Сначала завершите контролируемое или ручное размещение и отметьте публикацию."
            if is_ru
            else "Finish supervised/manual placement and mark the post as published first."
        )
    if status == "fix_failed_publish":
        return (
            "Публикация упала: исправьте канал или переведите пост в ручной режим."
            if is_ru
            else "Publishing failed: fix the channel or move the post to manual flow."
        )
    return (
        "Сначала опубликуйте хотя бы один approved/queued пост."
        if is_ru
        else "Publish at least one approved/queued post first."
    )

def _social_post_publish_learning_gate_next_action(status: str, is_ru: bool) -> str:
    if status == "ready_for_metrics_and_attribution":
        return (
            "Нажмите “Собрать реакции”, затем отметьте заявки/обращения и откройте рекомендации следующего плана."
            if is_ru
            else "Click “Collect reactions”, then mark leads/inquiries and open next-plan recommendations."
        )
    if status == "published_without_api_proof":
        return (
            "Сохраните provider_post_id/provider_post_url или отметьте публикацию вручную, чтобы proof был проверяемым."
            if is_ru
            else "Save provider_post_id/provider_post_url or mark the publish manually so proof is verifiable."
        )
    if status == "finish_supervised_or_manual_publish":
        return (
            "Откройте контролируемое размещение или ручной режим; после фактической публикации сохраните ссылку/ID."
            if is_ru
            else "Open supervised placement or manual fallback; after the real publish, save URL/ID."
        )
    if status == "fix_failed_publish":
        return (
            "Откройте ошибочный пост, исправьте ключи/права или повторите публикацию после подтверждения."
            if is_ru
            else "Open the failed post, fix keys/permissions, or retry publishing after approval."
        )
    return (
        "Подготовьте, подтвердите и поставьте пост в расписание, затем запустите ограниченный цикл."
        if is_ru
        else "Prepare, approve, and queue a post, then run a scoped cycle."
    )

def _social_dispatch_first_api_proof_summary(details: list[dict[str, Any]]) -> dict[str, Any]:
    api_details = [
        item for item in details or []
        if str(item.get("platform") or "").strip() in API_PLATFORMS
    ]
    published_api = [
        item for item in api_details
        if str(item.get("status") or "").strip() == "published"
    ]
    proof_items = [
        item for item in published_api
        if str(item.get("provider_post_id") or "").strip()
        or str(item.get("provider_post_url") or "").strip()
    ]
    first = proof_items[0] if proof_items else (published_api[0] if published_api else (api_details[0] if api_details else {}))
    platform = str(first.get("platform") or "").strip()
    label = str(first.get("platform_label") or platform_label(platform)).strip() if platform else ""
    ready = bool(proof_items)
    return {
        "schema": "localos_social_first_api_proof_summary_v1",
        "ready": ready,
        "api_posts_checked": len(api_details),
        "published_api_posts": len(published_api),
        "published_with_provider_proof": len(proof_items),
        "platform": platform,
        "platform_label": label,
        "post_id": str(first.get("id") or "").strip(),
        "provider_post_id": str(first.get("provider_post_id") or "").strip(),
        "provider_post_url": str(first.get("provider_post_url") or "").strip(),
        "last_error": str(first.get("last_error") or "").strip(),
        "required_proof_fields": ["provider_post_id", "provider_post_url"],
        "summary_ru": (
            f"Первый API-loop доказан: {label} сохранил provider_post_id/provider_post_url."
            if ready
            else "Первый API-loop ещё не доказан: нет published API-поста с provider_post_id/provider_post_url."
        ),
        "summary_en": (
            f"First API loop is proven: {label} saved provider_post_id/provider_post_url."
            if ready
            else "First API loop is not proven yet: no published API post has provider_post_id/provider_post_url."
        ),
        "next_action_ru": (
            "Соберите реакции/заявки и отметьте обращения перед корректировкой следующего плана."
            if ready
            else "Откройте details dispatch: если есть failed, исправьте канал; если published без proof, сохраните ссылку/ID вручную."
        ),
        "next_action_en": (
            "Collect reactions/leads and mark inquiries before adjusting the next plan."
            if ready
            else "Open dispatch details: if failed, fix the channel; if published without proof, save the URL/ID manually."
        ),
    }

def _social_dispatch_execution_title(status: str, is_ru: bool) -> str:
    if status == "completed":
        return "Цикл выполнен" if is_ru else "Cycle completed"
    if status == "manual_action_needed":
        return "Цикл выполнен, нужен ручной шаг" if is_ru else "Cycle completed, manual step needed"
    if status == "attention":
        return "Цикл выполнен с ошибками" if is_ru else "Cycle completed with errors"
    return "Due-постов не было" if is_ru else "No due posts"

def _social_dispatch_execution_summary(
    picked: int,
    published: int,
    supervised: int,
    manual: int,
    failed: int,
    is_ru: bool,
) -> str:
    if is_ru:
        return (
            f"Взято {picked}: опубликовано {published}, контролируемое размещение {supervised}, "
            f"вручную {manual}, ошибок {failed}."
        )
    return (
        f"Picked {picked}: published {published}, supervised {supervised}, manual {manual}, failed {failed}."
    )

def _social_dispatch_execution_next_action(status: str, errors: list[Any], is_ru: bool) -> str:
    if status == "completed":
        return (
            "Проверьте provider ID/URL у API-постов, завершите supervised preview для карт и затем соберите реакции."
            if is_ru
            else "Check provider IDs/URLs for API posts, finish supervised map previews, then collect reactions."
        )
    if status == "manual_action_needed":
        return (
            "Откройте ручные/контролируемые публикации, разместите их и отметьте результат."
            if is_ru
            else "Open manual/supervised posts, publish them, and mark the result."
        )
    if status == "attention":
        first_error = ""
        if errors and isinstance(errors[0], dict):
            first_error = str(errors[0].get("error") or "").strip()
        return (
            f"Разберите первую ошибку и повторите запуск для оставшихся постов на текущую дату: {first_error}".strip()
            if is_ru
            else f"Review the first error and rerun for remaining due posts: {first_error}".strip()
        )
    return (
        "Сначала поставьте утверждённые посты в расписание и дождитесь даты публикации."
        if is_ru
        else "Queue approved posts and wait for the due date first."
    )

def _social_dispatch_followup_actions(
    picked: int,
    published: int,
    supervised: int,
    manual: int,
    failed: int,
    errors: list[dict[str, str]] | None,
    is_ru: bool,
) -> list[str]:
    if picked <= 0:
        return [
            "Постов на текущую дату нет: сначала подготовьте, подтвердите и поставьте публикации в расписание."
            if is_ru
            else "No due posts: prepare, approve, and queue posts first."
        ]

    actions: list[str] = []
    if published > 0:
        actions.append(
            "Проверьте опубликованные API-посты: в карточке должны быть ссылка или provider ID."
            if is_ru
            else "Check published API posts: each card should have a URL or provider ID."
        )
    if supervised > 0:
        actions.append(
            "Завершите контролируемое размещение для Яндекс/2ГИС: финальный клик остаётся за человеком."
            if is_ru
            else "Finish supervised placement for Yandex/2GIS: the final click stays with a human."
        )
    if manual > 0:
        actions.append(
            "Откройте посты в ручном режиме: подключите ключи/права или разместите вручную и сохраните ссылку."
            if is_ru
            else "Open manual posts: connect keys/permissions or publish manually and save the URL."
        )
    if failed > 0:
        sample_error = ""
        if errors:
            sample_error = str((errors[0] or {}).get("error") or "").strip()
        if sample_error:
            actions.append(
                f"Есть ошибки запуска: {sample_error[:180]}. Исправьте причину и повторите ограниченный цикл."
                if is_ru
                else f"Dispatch has failures: {sample_error[:180]}. Fix the cause and rerun the scoped cycle."
            )
        else:
            actions.append(
                "Есть ошибки запуска: откройте карточки с ошибкой и выберите повтор или ручной режим."
                if is_ru
                else "Dispatch has failures: open failed cards and choose retry or manual fallback."
            )
    if not actions:
        actions.append(
            "Цикл завершён без внешних изменений: обновите очередь и проверьте даты публикаций."
            if is_ru
            else "The cycle finished without external changes: refresh the queue and check due dates."
        )
    actions.append(
        "После публикаций соберите реакции и отметьте заявки/обращения для корректировки следующего плана."
        if is_ru
        else "After publishing, collect reactions and mark leads/inquiries for next-plan correction."
    )
    return actions[:5]

def _social_dispatch_result_summaries(details: list[dict[str, Any]], is_ru: bool) -> list[str]:
    summaries: list[str] = []
    for item in (details or [])[:5]:
        platform = str(item.get("platform") or "").strip()
        label = platform_label(platform) if platform else ("Канал" if is_ru else "Channel")
        status = str(item.get("status") or "").strip()
        provider_url = str(item.get("provider_post_url") or "").strip()
        provider_id = str(item.get("provider_post_id") or "").strip()
        automation_task_id = str(item.get("automation_task_id") or "").strip()
        last_error = str(item.get("last_error") or "").strip()
        if status == "published":
            proof = provider_url or provider_id
            summaries.append(
                f"{label}: опубликовано" + (f", proof {proof}." if proof else ".")
                if is_ru
                else f"{label}: published" + (f", proof {proof}." if proof else ".")
            )
        elif status == "needs_supervised_publish":
            summaries.append(
                f"{label}: контролируемое размещение готово" + (f" ({automation_task_id})." if automation_task_id else ".")
                if is_ru
                else f"{label}: supervised placement is ready" + (f" ({automation_task_id})." if automation_task_id else ".")
            )
        elif status == "needs_manual_publish":
            reason = f": {last_error}" if last_error else ""
            summaries.append(
                f"{label}: нужен ручной шаг или подключение канала{reason}."
                if is_ru
                else f"{label}: manual step or channel connection is needed{reason}."
            )
        elif status == "failed":
            reason = f": {last_error}" if last_error else ""
            summaries.append(
                f"{label}: ошибка публикации{reason}."
                if is_ru
                else f"{label}: publishing failed{reason}."
            )
        else:
            summaries.append(
                f"{label}: статус после dispatch - {status or 'unknown'}."
                if is_ru
                else f"{label}: status after dispatch is {status or 'unknown'}."
            )
    if len(details or []) > 5:
        remaining = len(details or []) - 5
        summaries.append(
            f"Ещё {remaining} результатов смотрите в карточках постов."
            if is_ru
            else f"See {remaining} more results in post cards."
        )
    return summaries

def _social_metrics_once_message(result: dict[str, Any], is_ru: bool) -> str:
    if result.get("blocked"):
        return (
            "Сбор реакций заблокирован: нужен явный business scope."
            if is_ru
            else "Metrics collection is blocked: an explicit business scope is required."
        )
    picked = int(result.get("picked") or 0)
    collected = int(result.get("collected") or 0)
    failed = int(result.get("failed") or 0)
    if picked <= 0:
        return (
            "Новых опубликованных постов для сбора реакций нет."
            if is_ru
            else "There are no new published posts to collect reactions for."
        )
    if is_ru:
        return f"Сбор реакций выполнен: проверено {picked}, обновлено {collected}, ошибок {failed}."
    return f"Metrics collection finished: checked {picked}, updated {collected}, failed {failed}."

def _social_metrics_learning_packet(result: dict[str, Any]) -> dict[str, Any]:
    details = result.get("metric_details") if isinstance(result.get("metric_details"), list) else []
    leads = sum(int(item.get("leads") or 0) for item in details if isinstance(item, dict))
    inquiries = sum(int(item.get("inquiries") or 0) for item in details if isinstance(item, dict))
    comments = sum(int(item.get("comments") or 0) for item in details if isinstance(item, dict))
    shares = sum(int(item.get("shares") or 0) for item in details if isinstance(item, dict))
    clicks = sum(int(item.get("clicks") or 0) for item in details if isinstance(item, dict))
    likes = sum(int(item.get("likes") or 0) for item in details if isinstance(item, dict))
    views = sum(int(item.get("views") or 0) for item in details if isinstance(item, dict))
    failed = int(result.get("failed") or 0)
    collected = int(result.get("collected") or 0)
    primary_total = leads + inquiries
    early_total = comments + shares + clicks + likes + views
    if primary_total > 0:
        status = "ready_from_leads"
    elif early_total > 0:
        status = "early_signals_only"
    elif collected > 0:
        status = "collected_without_signals"
    elif failed > 0:
        status = "metrics_failed"
    else:
        status = "no_metrics_yet"
    return {
        "schema": "localos_social_metrics_learning_packet_v1",
        "status": status,
        "collected_posts": collected,
        "failed_posts": failed,
        "primary_metric_ru": "Заявки и обращения",
        "primary_metric_en": "Leads and inquiries",
        "primary_result_total": primary_total,
        "early_signal_total": early_total,
        "leads": leads,
        "inquiries": inquiries,
        "comments": comments,
        "shares": shares,
        "clicks": clicks,
        "likes": likes,
        "views": views,
        "safe_to_recommend_next_plan": primary_total > 0 or early_total > 0,
        "safe_to_apply_without_approval": False,
        "external_publish_performed": False,
        "summary_ru": _social_metrics_learning_summary(status, True),
        "summary_en": _social_metrics_learning_summary(status, False),
        "next_action_ru": _social_metrics_learning_next_action(status, True),
        "next_action_en": _social_metrics_learning_next_action(status, False),
    }

def _social_metrics_learning_summary(status: str, is_ru: bool) -> str:
    if status == "ready_from_leads":
        return (
            "Есть заявки или обращения: можно предлагать изменения следующего плана по главной метрике."
            if is_ru
            else "Leads or inquiries exist: next-plan changes can be suggested from the primary metric."
        )
    if status == "early_signals_only":
        return (
            "Есть ранние сигналы, но перед применением изменений проверьте заявки и обращения."
            if is_ru
            else "Early signals exist, but check leads and inquiries before applying changes."
        )
    if status == "collected_without_signals":
        return (
            "Метрики обновлены, но результата пока не видно: отметьте заявки/обращения вручную, если они были."
            if is_ru
            else "Metrics were updated, but no result is visible yet: manually record leads/inquiries if they happened."
        )
    if status == "metrics_failed":
        return (
            "Сбор реакций завершился с ошибками: исправьте доступы или используйте ручную разметку результата."
            if is_ru
            else "Metrics collection had errors: fix access or use manual result attribution."
        )
    return (
        "Сначала опубликуйте посты или отметьте результат вручную."
        if is_ru
        else "Publish posts or record results manually first."
    )

def _social_metrics_learning_next_action(status: str, is_ru: bool) -> str:
    if status == "ready_from_leads":
        return (
            "Откройте предложения следующего плана; применять их можно только после подтверждения."
            if is_ru
            else "Open next-plan suggestions; apply them only after approval."
        )
    if status == "early_signals_only":
        return (
            "Проверьте, были ли заявки/обращения, затем откройте рекомендации как предварительные."
            if is_ru
            else "Check whether leads/inquiries happened, then open recommendations as preliminary."
        )
    if status == "collected_without_signals":
        return (
            "Отметьте заявку, обращение или ранний сигнал на опубликованных постах."
            if is_ru
            else "Record a lead, inquiry, or early signal on published posts."
        )
    if status == "metrics_failed":
        return (
            "Откройте ошибки сбора метрик и исправьте канал или права."
            if is_ru
            else "Open metric collection errors and fix the channel or permissions."
        )
    return (
        "Подготовьте публикацию, дождитесь результата и повторите сбор реакций."
        if is_ru
        else "Prepare a post, wait for results, and collect reactions again."
    )

def _social_metrics_result_summaries(details: list[dict[str, Any]], is_ru: bool) -> list[str]:
    summaries: list[str] = []
    for item in (details or [])[:5]:
        platform = str(item.get("platform") or "").strip()
        label = platform_label(platform) if platform else ("Пост" if is_ru else "Post")
        source = str(item.get("source") or "").strip()
        status = str(item.get("status") or "").strip()
        error = str(item.get("error") or "").strip()
        leads = int(item.get("leads") or 0)
        inquiries = int(item.get("inquiries") or 0)
        comments = int(item.get("comments") or 0)
        reach = int(item.get("views") or item.get("reach") or 0)
        if status == "failed" or source == "collector_error":
            summaries.append(
                f"{label}: реакции не обновились" + (f": {error}." if error else ".")
                if is_ru
                else f"{label}: reactions were not updated" + (f": {error}." if error else ".")
            )
        elif source == "vk_api":
            summaries.append(
                f"{label}: API-снимок обновлён; заявки {leads}, обращения {inquiries}, комментарии {comments}, охват {reach}."
                if is_ru
                else f"{label}: API snapshot updated; leads {leads}, inquiries {inquiries}, comments {comments}, reach {reach}."
            )
        elif source == "telegram_bot_api":
            summaries.append(
                f"{label}: Bot API опубликовал пост, но не отдаёт просмотры/реакции; отмечайте заявки и обращения вручную. Заявки {leads}, обращения {inquiries}."
                if is_ru
                else f"{label}: Bot API published the post but does not expose views/reactions; mark leads and inquiries manually. Leads {leads}, inquiries {inquiries}."
            )
        elif source == "google_business_api":
            summaries.append(
                f"{label}: публикация учтена, но сбор реакций через Google Business пока не включён; заявки и обращения отмечаются вручную. Заявки {leads}, обращения {inquiries}."
                if is_ru
                else f"{label}: publishing is tracked, but Google Business reaction collection is not enabled yet; mark leads and inquiries manually. Leads {leads}, inquiries {inquiries}."
            )
        elif source == "meta_graph_api":
            summaries.append(
                f"{label}: Meta Graph метрики требуют готовых прав; пока используйте ручную разметку заявок/обращений. Заявки {leads}, обращения {inquiries}."
                if is_ru
                else f"{label}: Meta Graph metrics require ready permissions; use manual lead/inquiry marking for now. Leads {leads}, inquiries {inquiries}."
            )
        elif source == "manual_or_supervised_map":
            summaries.append(
                f"{label}: реакции с карт собираются вручную после контролируемого размещения; заявки {leads}, обращения {inquiries}."
                if is_ru
                else f"{label}: map reactions are collected manually after supervised placement; leads {leads}, inquiries {inquiries}."
            )
        elif source == "manual_attribution_only":
            summaries.append(
                f"{label}: доступна ручная разметка; заявки {leads}, обращения {inquiries}, реакции {comments}, просмотры {reach}."
                if is_ru
                else f"{label}: manual result marking is available; leads {leads}, inquiries {inquiries}, reactions {comments}, views {reach}."
            )
        else:
            summaries.append(
                f"{label}: метрики обновлены из {source or status or 'collector'}; заявки {leads}, обращения {inquiries}."
                if is_ru
                else f"{label}: metrics updated from {source or status or 'collector'}; leads {leads}, inquiries {inquiries}."
            )
    if len(details or []) > 5:
        remaining = len(details or []) - 5
        summaries.append(
            f"Ещё {remaining} результатов смотрите в карточках постов."
            if is_ru
            else f"See {remaining} more results in post cards."
        )
    return summaries

def preview_due_social_post_dispatch(user_id: str, batch_size: int = 20, business_id: str = "") -> dict[str, Any]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    business_scope = _social_dispatch_business_scope(business_id)
    try:
        ensure_social_post_tables(cursor)
        scope_clause = "AND sp.business_id = %s" if business_scope else ""
        params: list[Any] = []
        if business_scope:
            params.append(business_scope)
        params.append(max(1, min(int(batch_size or 20), 200)))
        cursor.execute(
            f"""
            SELECT sp.*
            FROM social_posts sp
            WHERE sp.status = 'queued'
              AND sp.approved_at IS NOT NULL
              AND COALESCE(sp.scheduled_for, NOW()) <= NOW()
              {scope_clause}
            ORDER BY sp.scheduled_for ASC NULLS FIRST, sp.updated_at ASC
            LIMIT %s
            """,
            tuple(params),
        )
        due_posts = [_serialize_social_post(cursor, row) for row in cursor.fetchall() or []]
        preview_items: list[dict[str, Any]] = []
        skipped = 0
        for post in due_posts:
            try:
                _require_business_access(cursor, user_id, str(post.get("business_id") or ""))
            except PermissionError:
                skipped += 1
                continue
            preview_items.append(_preview_dispatch_decision(cursor, post))
        counts: dict[str, int] = {}
        for item in preview_items:
            action = str(item.get("dispatch_action") or "unknown")
            counts[action] = counts.get(action, 0) + 1
        readiness = _dispatch_preview_readiness(preview_items, counts, skipped, business_scope)
        return {
            "dry_run": True,
            "picked": len(preview_items),
            "skipped_no_access": skipped,
            "batch_size": max(1, min(int(batch_size or 20), 200)),
            "business_scope": business_scope,
            "by_action": counts,
            "readiness": readiness,
            "items": preview_items,
        }
    finally:
        db.close()

def _dispatch_action_for_status(status: str) -> str:
    clean_status = str(status or "").strip()
    if clean_status == "published":
        return "published"
    if clean_status == "needs_supervised_publish":
        return "supervised"
    if clean_status == "needs_manual_publish":
        return "manual"
    if clean_status == "failed":
        return "failed"
    if clean_status == "publishing":
        return "publishing"
    return "other"

def _dispatch_preview_readiness(
    preview_items: list[dict[str, Any]],
    counts: dict[str, int],
    skipped_no_access: int = 0,
    business_scope: str = "",
) -> dict[str, Any]:
    external_publish_count = int(counts.get("publish_api") or 0)
    controlled_count = int(counts.get("create_supervised_task") or 0)
    manual_count = int(counts.get("manual_handoff") or 0)
    due_count = len(preview_items)
    has_due_work = due_count > 0
    has_only_manual_work = has_due_work and external_publish_count == 0 and controlled_count == 0 and manual_count > 0
    status = "no_due_posts"
    if external_publish_count > 0:
        status = "external_publish_ready"
    elif controlled_count > 0:
        status = "controlled_tasks_ready"
    elif has_only_manual_work:
        status = "manual_only"
    elif skipped_no_access > 0:
        status = "access_limited"
    return {
        "status": status,
        "due_count": due_count,
        "external_publish_count": external_publish_count,
        "controlled_count": controlled_count,
        "manual_count": manual_count,
        "skipped_no_access": int(skipped_no_access or 0),
        "has_external_publish": external_publish_count > 0,
        "has_controlled_tasks": controlled_count > 0,
        "has_manual_fallback": manual_count > 0,
        "safe_dry_run": True,
        "external_publish_requires_approval": True,
        "browser_final_click_allowed": False,
        "message_ru": _dispatch_preview_readiness_message(status, True),
        "message_en": _dispatch_preview_readiness_message(status, False),
        "next_action_ru": _dispatch_preview_next_action(status, business_scope, True),
        "next_action_en": _dispatch_preview_next_action(status, business_scope, False),
        "recommended_dispatch_env": _dispatch_preview_recommended_env(business_scope),
        "first_cycle_steps": _dispatch_preview_first_cycle_steps(
            external_publish_count,
            controlled_count,
            manual_count,
            skipped_no_access,
        ),
        "first_cycle_verification": _social_worker_first_cycle_verification(
            external_publish_count,
            controlled_count,
            manual_count,
            skipped_no_access,
            business_scope,
        ),
        "first_api_proof_candidate": _dispatch_first_api_proof_candidate(preview_items),
        "safety_notes_ru": [
            "Внешние публикации уходят только из подтверждённых постов в расписании.",
            "Яндекс/2ГИС остаются контролируемыми или ручными: финальный клик публикации не выполняется исполнителем.",
            "Проверка ничего не отправляет наружу и нужна для первого цикла.",
        ],
        "safety_notes_en": [
            "External publishing runs only for approved/queued posts.",
            "Yandex/2GIS stay supervised/manual: the worker does not perform the final publish click.",
            "Dry-run sends nothing externally and exists to verify the first cycle.",
        ],
    }

def _dispatch_preview_first_cycle_steps(
    external_publish_count: int,
    controlled_count: int,
    manual_count: int,
    skipped_no_access: int = 0,
) -> list[dict[str, Any]]:
    steps = [
        {
            "key": "api_publish_after_approval",
            "label_ru": "API: публикация после подтверждения",
            "label_en": "API: publish after approval",
            "count": int(external_publish_count or 0),
            "external_publish": True,
            "requires_approval": True,
            "stop_before_final_publish": False,
            "expected_status_ru": "published или failed с понятной причиной",
            "expected_status_en": "published or failed with a clear reason",
            "description_ru": "Telegram/VK/Google/Meta уйдут наружу только если пост уже подтверждён, стоит в расписании и канал готов.",
            "description_en": "Telegram/VK/Google/Meta publish externally only when the post is already approved, queued, and the channel is ready.",
        },
        {
            "key": "maps_controlled_without_final_click",
            "label_ru": "Карты: контроль/вручную без финального клика",
            "label_en": "Maps: supervised/manual without final click",
            "count": int(controlled_count or 0),
            "external_publish": False,
            "requires_approval": True,
            "stop_before_final_publish": True,
            "expected_status_ru": "needs_supervised_publish",
            "expected_status_en": "needs_supervised_publish",
            "description_ru": "Яндекс/2ГИС получают контролируемую задачу для OpenClaw, но финальная публикация остаётся за человеком.",
            "description_en": "Yandex/2GIS receive an OpenClaw supervised task, while final publishing stays human-controlled.",
        },
        {
            "key": "manual_handoff_or_connection",
            "label_ru": "Ручной режим или подключение канала",
            "label_en": "Manual fallback or channel connection",
            "count": int(manual_count or 0),
            "external_publish": False,
            "requires_approval": True,
            "stop_before_final_publish": True,
            "expected_status_ru": "needs_manual_publish",
            "expected_status_en": "needs_manual_publish",
            "description_ru": "Посты без ключей, browser-use или готового текста не будут скрыто публиковаться.",
            "description_en": "Posts without credentials, browser-use, or ready copy will not publish silently.",
        },
    ]
    if int(skipped_no_access or 0) > 0:
        steps.append(
            {
                "key": "skipped_no_access",
                "label_ru": "Пропущено без доступа",
                "label_en": "Skipped without access",
                "count": int(skipped_no_access or 0),
                "external_publish": False,
                "requires_approval": True,
                "stop_before_final_publish": True,
                "expected_status_ru": "без изменений",
                "expected_status_en": "unchanged",
                "description_ru": "Эти посты не попали в первый цикл для текущего пользователя или business scope.",
                "description_en": "These posts are outside the current user or business scope for the first cycle.",
            }
        )
    return steps

def _dispatch_first_api_proof_candidate(preview_items: list[dict[str, Any]]) -> dict[str, Any]:
    for item in preview_items or []:
        if str(item.get("dispatch_action") or "").strip() != "publish_api":
            continue
        platform = str(item.get("platform") or "").strip()
        label = str(item.get("platform_label") or platform_label(platform)).strip()
        return {
            "schema": "localos_social_first_api_proof_candidate_v1",
            "ready": True,
            "id": str(item.get("id") or "").strip(),
            "business_id": str(item.get("business_id") or "").strip(),
            "content_plan_id": str(item.get("content_plan_id") or "").strip(),
            "content_plan_item_id": str(item.get("content_plan_item_id") or "").strip(),
            "platform": platform,
            "platform_label": label,
            "scheduled_for": item.get("scheduled_for"),
            "required_proof_fields": ["provider_post_id", "provider_post_url"],
            "expected_status_ru": "published с provider_post_id/provider_post_url или failed с понятной причиной",
            "expected_status_en": "published with provider_post_id/provider_post_url or failed with a clear reason",
            "proof_check_ru": f"После worker откройте {label}: у этого post должен появиться provider_post_id/provider_post_url.",
            "proof_check_en": f"After the worker runs, open {label}: this post must get provider_post_id/provider_post_url.",
            "metrics_followup_ru": "Если proof есть, сразу соберите реакции/заявки и отметьте обращения.",
            "metrics_followup_en": "If proof exists, immediately collect reactions/leads and mark inquiries.",
            "external_publish_requires_approval": True,
            "external_publish_performed": False,
            "dry_run": True,
        }
    return {
        "schema": "localos_social_first_api_proof_candidate_v1",
        "ready": False,
        "required_proof_fields": ["provider_post_id", "provider_post_url"],
        "expected_status_ru": "нет due API-поста для доказательства первого API-loop",
        "expected_status_en": "no due API post is available to prove the first API loop",
        "proof_check_ru": "Сначала подготовьте, подтвердите и поставьте в расписание один Telegram/VK/API-пост.",
        "proof_check_en": "First prepare, approve, and queue one Telegram/VK/API post.",
        "metrics_followup_ru": "Метрики и заявки появятся после первого доказанного API-поста.",
        "metrics_followup_en": "Metrics and leads come after the first proven API post.",
        "external_publish_requires_approval": True,
        "external_publish_performed": False,
        "dry_run": True,
    }

def _social_worker_first_cycle_verification(
    external_publish_count: int,
    controlled_count: int,
    manual_count: int,
    skipped_no_access: int = 0,
    business_scope: str = "",
) -> dict[str, Any]:
    expected_statuses = []
    if int(external_publish_count or 0) > 0:
        expected_statuses.append(
            {
                "key": "api_channels",
                "label_ru": "API-каналы",
                "label_en": "API channels",
                "expected_ru": "published или failed с понятной причиной",
                "expected_en": "published or failed with a clear reason",
            }
        )
    if int(controlled_count or 0) > 0:
        expected_statuses.append(
            {
                "key": "maps_controlled",
                "label_ru": "Яндекс/2ГИС",
                "label_en": "Yandex/2GIS",
                "expected_ru": "needs_supervised_publish или needs_manual_publish; финального клика нет",
                "expected_en": "needs_supervised_publish or needs_manual_publish; no final click",
            }
        )
    if int(manual_count or 0) > 0:
        expected_statuses.append(
            {
                "key": "manual_fallback",
                "label_ru": "Ручной режим",
                "label_en": "Manual fallback",
                "expected_ru": "needs_manual_publish с инструкцией и готовым текстом",
                "expected_en": "needs_manual_publish with instructions and copy-ready text",
            }
        )
    if int(skipped_no_access or 0) > 0:
        expected_statuses.append(
            {
                "key": "skipped_no_access",
                "label_ru": "Нет доступа",
                "label_en": "No access",
                "expected_ru": "без изменений; проверить права или business scope",
                "expected_en": "unchanged; check permissions or business scope",
            }
        )
    if not expected_statuses:
        expected_statuses.append(
            {
                "key": "noop",
                "label_ru": "Нет due-постов",
                "label_en": "No due posts",
                "expected_ru": "worker не должен ничего отправить",
                "expected_en": "worker should not send anything",
            }
        )
    log_filter = "[SOCIAL_POST_DISPATCH]"
    return {
        "log_filter": log_filter,
        "business_scope": str(business_scope or "").strip(),
        "expected_statuses": expected_statuses,
        "checks_ru": [
            f"В логах worker найти строку {log_filter}.",
            "Сверить picked/published/supervised/manual/failed с dry-run перед запуском.",
            "Если есть failed: открыть карточку поста, last_error и readiness канала.",
            "Если есть ручное или контролируемое размещение: завершить его из карточки поста и отметить ссылку/ID.",
        ],
        "checks_en": [
            f"Find the {log_filter} line in worker logs.",
            "Compare picked/published/supervised/manual/failed with the pre-launch dry-run.",
            "If failed exists: open the post card, last_error, and channel readiness.",
            "If manual/supervised exists: complete placement from the post card and record URL/ID.",
        ],
    }

def _dispatch_preview_readiness_message(status: str, is_ru: bool) -> str:
    if status == "external_publish_ready":
        return (
            "Есть due API-посты: после включения dispatch они смогут уйти наружу только потому, что уже approved."
            if is_ru
            else "Due API posts exist: after dispatch is enabled they can publish externally only because they are already approved."
        )
    if status == "controlled_tasks_ready":
        return (
            "Есть due карты: worker создаст контролируемое или ручное размещение, финальная публикация остаётся за человеком."
            if is_ru
            else "Due map posts exist: the worker will create supervised placement or manual handoff, while final publishing stays human-controlled."
        )
    if status == "manual_only":
        return (
            "Все due-посты сейчас требуют ручного fallback или подключения канала; автопубликации не будет."
            if is_ru
            else "All due posts currently require manual fallback or channel connection; no autopublish will happen."
        )
    if status == "access_limited":
        return (
            "Есть due-посты вне доступа текущего пользователя; dry-run их пропустил."
            if is_ru
            else "Some due posts are outside the current user's access; the dry-run skipped them."
        )
    return (
        "Due-постов нет: включение dispatch сейчас ничего не отправит."
        if is_ru
        else "There are no due posts: enabling dispatch now would not send anything."
    )

def _dispatch_preview_next_action(status: str, business_scope: str, is_ru: bool) -> str:
    scope = str(business_scope or "").strip()
    if status == "external_publish_ready":
        if scope:
            return (
                f"Можно включать scoped dispatch для бизнеса {scope}: проверьте ключи и логи после первого цикла."
                if is_ru
                else f"You can enable scoped dispatch for business {scope}: check credentials and logs after the first cycle."
            )
        return (
            "Перед включением реального dispatch задайте SOCIAL_POST_DISPATCH_BUSINESS_ID."
            if is_ru
            else "Set SOCIAL_POST_DISPATCH_BUSINESS_ID before enabling real dispatch."
        )
    if status == "controlled_tasks_ready":
        return (
            "Можно запускать scoped dispatch: карты перейдут в контролируемое или ручное размещение без финального клика."
            if is_ru
            else "Scoped dispatch can run: map posts will move to supervised placement or manual handoff without a final click."
        )
    if status == "manual_only":
        return (
            "Сначала подключите каналы или подготовьте ручное размещение; API-публикации в этом dry-run нет."
            if is_ru
            else "Connect channels or prepare manual placement first; this dry-run has no API publishing."
        )
    if status == "access_limited":
        return (
            "Запустите dry-run пользователем с доступом к нужному бизнесу или сузьте business scope."
            if is_ru
            else "Run the dry-run as a user with access to the business or narrow the business scope."
        )
    return (
        "Новых due-постов нет: продолжайте готовить, утверждать и ставить публикации в расписание."
        if is_ru
        else "No due posts yet: continue preparing, approving, and queueing posts."
    )

def _social_launch_runbook(
    status: str,
    business_scope: str,
    due_count: int,
    external_publish_count: int,
    controlled_count: int,
    manual_count: int,
    skipped_no_access: int,
    first_cycle_verification: dict[str, Any],
) -> dict[str, Any]:
    scope = str(business_scope or "").strip()
    log_filter = str(first_cycle_verification.get("log_filter") or "[SOCIAL_POST_DISPATCH]").strip()
    due = int(due_count or 0)
    external = int(external_publish_count or 0)
    controlled = int(controlled_count or 0)
    manual = int(manual_count or 0)
    skipped = int(skipped_no_access or 0)
    normalized_status = str(status or "").strip()
    can_launch = bool(scope) and due > 0 and skipped == 0 and normalized_status != "api_preflight_blocked"
    return {
        "ready": can_launch,
        "scope": scope,
        "status": normalized_status,
        "title_ru": "Runbook первого цикла dispatch",
        "title_en": "First-cycle dispatch runbook",
        "summary_ru": (
            f"Due {due}: API {external}, контролируемо {controlled}, вручную {manual}. "
            f"Scope: {scope or 'не задан'}."
        ),
        "summary_en": (
            f"Due {due}: API {external}, supervised {controlled}, manual {manual}. "
            f"Scope: {scope or 'not set'}."
        ),
        "steps_ru": _social_launch_runbook_steps(
            scope,
            due,
            external,
            controlled,
            manual,
            skipped,
            log_filter,
            normalized_status,
            True,
        ),
        "steps_en": _social_launch_runbook_steps(
            scope,
            due,
            external,
            controlled,
            manual,
            skipped,
            log_filter,
            normalized_status,
            False,
        ),
        "success_criteria_ru": _social_launch_runbook_success_criteria(external, controlled, manual, skipped, True),
        "success_criteria_en": _social_launch_runbook_success_criteria(external, controlled, manual, skipped, False),
        "blocked_reason_ru": _social_launch_runbook_blocked_reason(scope, due, skipped, normalized_status, True),
        "blocked_reason_en": _social_launch_runbook_blocked_reason(scope, due, skipped, normalized_status, False),
    }

def _social_launch_runbook_steps(
    scope: str,
    due_count: int,
    external_publish_count: int,
    controlled_count: int,
    manual_count: int,
    skipped_no_access: int,
    log_filter: str,
    status: str,
    is_ru: bool,
) -> list[str]:
    if str(status or "").strip() == "api_preflight_blocked":
        return [
            "Исправьте live API-проверку: ключи, права, локацию или адаптер для заблокированного канала."
            if is_ru
            else "Fix live API preflight first: keys, permissions, location, or native adapter for the blocked channel.",
            "Если канал пока нельзя подключить, переведите конкретный пост в ручной режим и повторите проверку."
            if is_ru
            else "If the channel cannot be connected yet, move that specific post to manual fallback and run preflight again.",
        ]
    if int(due_count or 0) <= 0:
        return [
            "Подготовьте посты, утвердите их и поставьте в расписание."
            if is_ru
            else "Prepare posts, approve them, and queue them on schedule.",
            "Запустите preflight снова перед включением worker."
            if is_ru
            else "Run preflight again before enabling the worker.",
        ]
    steps = [
        (
            f"Включите dispatch только со scope: SOCIAL_POST_DISPATCH_BUSINESS_ID={scope}."
            if is_ru
            else f"Enable dispatch only with scope: SOCIAL_POST_DISPATCH_BUSINESS_ID={scope}."
        )
        if scope
        else (
            "Сначала задайте SOCIAL_POST_DISPATCH_BUSINESS_ID для тестового бизнеса."
            if is_ru
            else "Set SOCIAL_POST_DISPATCH_BUSINESS_ID for the test business first."
        ),
        (
            f"Дождитесь одного цикла worker и найдите в логах {log_filter}."
            if is_ru
            else f"Wait for one worker cycle and find {log_filter} in logs."
        ),
        (
            "Сверьте picked/published/supervised/manual/failed с dry-run."
            if is_ru
            else "Compare picked/published/supervised/manual/failed with the dry-run."
        ),
    ]
    if int(external_publish_count or 0) > 0:
        steps.append(
            "Для API-постов проверьте provider_post_id/provider_post_url или понятный last_error."
            if is_ru
            else "For API posts, check provider_post_id/provider_post_url or a clear last_error."
        )
    if int(controlled_count or 0) > 0:
        steps.append(
            "Для Яндекс/2ГИС проверьте контролируемое или ручное размещение: финальный клик не должен быть выполнен worker."
            if is_ru
            else "For Yandex/2GIS, check the supervised/manual task: the worker must not perform the final click."
        )
    if int(manual_count or 0) > 0:
        steps.append(
            "Для manual fallback откройте карточку поста, скопируйте текст и отметьте размещение вручную."
            if is_ru
            else "For manual fallback, open the post card, copy text, and mark placement manually."
        )
    if int(skipped_no_access or 0) > 0:
        steps.append(
            "Есть skipped_no_access: сузьте scope или проверьте права перед запуском."
            if is_ru
            else "skipped_no_access exists: narrow scope or check permissions before launch."
        )
    return steps
