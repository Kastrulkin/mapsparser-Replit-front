from __future__ import annotations

import os
import sys
import base64
import json
import re
import uuid
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request

from auth_system import create_session
from core.auth_helpers import require_auth_from_request, verify_business_access
from database_manager import DatabaseManager
from services.operator_audit import list_operator_events, record_operator_event
from services.operator_capabilities import (
    build_operator_help_response,
    classify_operator_help_intent,
    classify_unanswered_reviews_status_intent,
    get_unanswered_reviews_status,
)
from services.operator_consent_policy import list_consent_policies, upsert_consent_policy
from services.operator_content_history import list_operator_content_history
from services.operator_attention import build_attention_brief
from services.operator_scope_summary import build_operator_scope_summary
from services.telegram_control_scope import (
    list_control_scopes,
    load_control_preferences,
    resolve_control_scope,
    save_scope_notification_preferences,
    toggle_favorite_control_scope,
)
from services.telegram_webapp_auth import load_localos_user_for_telegram, validate_telegram_webapp_init_data
from services.operator_fresh_reviews import classify_fresh_reviews_intent, refresh_reviews_from_operator
from services.operator_intent_ai_router import classify_operator_intent_with_ai, should_use_ai_intent_router
from services.operator_inbox import build_operator_inbox
from services.operator_manual_review import process_operator_chat_message
from services.operator_manual_publish import mark_review_reply_draft_manual_published
from services.operator_mobile_actions import confirm_mobile_action, create_mobile_action_preview
from services.operator_mobile_modules import list_operator_mobile_module
from services.operator_news_generation import classify_news_generate_intent, generate_news_draft_from_operator
from services.operator_paid_executor import build_paid_action_execution_attempt
from services.operator_paid_preflight import build_paid_action_preflight
from services.operator_refresh_result import build_refresh_result_status, list_refresh_jobs
from services.operator_refresh_recovery import build_refresh_recovery_plan, release_failed_refresh_reservation
from services.operator_refresh_retry import request_refresh_retry
from services.operator_review_reply_bulk import classify_bulk_review_reply_intent, generate_review_reply_drafts_for_unanswered_reviews
from services.operator_services_optimization import (
    apply_service_optimization_suggestions,
    classify_services_apply_intent,
    classify_services_optimize_intent,
    optimize_services_from_operator,
)
from services.operator_social_post_generation import classify_social_post_generate_intent, generate_social_post_draft_from_operator
from services.operator_core import confirm_pending_operator_action, operator_capability_catalog, route_operator_message
from services.operator_conversations import (
    append_operator_message,
    conversation_pending_context,
    create_pending_operator_action,
    find_latest_operator_conversation,
    get_or_create_operator_conversation,
    list_operator_messages,
    set_operator_pending_context,
)
from services.content_plan_service import create_generated_content_plan, delete_content_plan, generate_draft_for_plan_item, update_content_plan_item
from core.card_automation import get_card_automation_snapshot, save_card_automation_settings
from core.service_catalog_compression import build_service_catalog_compression_draft
from services.gigachat_client import analyze_screenshot_with_gigachat
from services.agent_source_ingestion import build_agent_source_from_upload
from services.llm import analyze_text_with_gigachat
from services.operator_map_refresh import DEFAULT_MAP_REFRESH_ESTIMATED_CREDITS
from services.operator_review_canonicalization import CANONICAL_REVIEWS_CTE
from services.operator_services_optimization import SERVICES_OPTIMIZE_CREDITS_PER_SERVICE
from subscription_manager import get_allowed_content_plan_horizons


operator_bp = Blueprint("operator_api", __name__, url_prefix="/api/operator")


def _mobile_navigation(scope: dict, is_superadmin: bool = False) -> list[dict]:
    kind = str(scope.get("kind") or "business")
    items = [
        {"key": "today", "label": "Сегодня", "group": "primary", "status": "available"},
        {"key": "tasks", "label": "Задачи", "group": "primary", "status": "available"},
        {"key": "reviews", "label": "Отзывы", "group": "primary", "status": "available"},
        {"key": "operator", "label": "Оператор", "group": "primary", "status": "available"},
        {"key": "cards", "label": "Карточки", "group": "more", "status": "available"},
        {"key": "content", "label": "Контент", "group": "more", "status": "available"},
        {"key": "services", "label": "Услуги", "group": "more", "status": "available"},
        {"key": "finance", "label": "Финансы", "group": "more", "status": "available"},
        {"key": "analytics", "label": "Аналитика", "group": "more", "status": "read_only"},
        {"key": "partnerships", "label": "Партнёрства", "group": "more", "status": "available"},
        {"key": "agents", "label": "ИИ-сотрудники", "group": "more", "status": "read_only"},
        {"key": "settings", "label": "Настройки", "group": "more", "status": "available"},
    ]
    if kind == "platform" and is_superadmin:
        items.append({"key": "diagnostics", "label": "Диагностика", "group": "more", "status": "read_only"})
    return items


def _mobile_task_item(item: dict) -> dict:
    value = dict(item)
    status = str(value.get("status") or "needs_attention")
    if status in {"draft", "generated", "pending_review", "approval_required"}:
        status = "needs_attention"
    elif status in {"queued", "running", "processing", "in_progress"}:
        status = "in_progress"
    elif status in {"completed", "manual_published", "done"}:
        status = "completed"
    value["status"] = status
    value["kind"] = str(value.get("kind") or value.get("id") or "operator_task")
    value["progress"] = value.get("progress") if value.get("progress") is not None else (100 if status == "completed" else None)
    value["available_actions"] = value.get("available_actions") or [value.get("primary_action") or "open"]
    return value


def _mobile_background_tasks(cursor, scope: dict) -> list[dict]:
    platform = scope.get("kind") == "platform"
    business_ids = [str(item) for item in scope.get("business_ids") or []]
    cursor.execute(
        """
        SELECT q.id, q.business_id, b.name AS business_name, q.status, q.task_type,
               q.error_message, q.retry_after, q.created_at, q.updated_at
        FROM parsequeue q
        LEFT JOIN businesses b ON b.id = q.business_id
        WHERE (%s OR q.business_id = ANY(%s))
          AND q.status IN ('pending', 'processing', 'completed', 'failed', 'error', 'captcha_required')
        ORDER BY q.updated_at DESC
        LIMIT 25
        """,
        (platform, business_ids),
    )
    tasks = []
    for value in cursor.fetchall() or []:
        row = dict(value)
        raw_status = str(row.get("status") or "")
        if raw_status in {"pending", "processing"}:
            status, progress, severity = "in_progress", 25 if raw_status == "pending" else 65, "low"
            description = "LocalOS собирает read-only данные. Экран можно закрыть."
        elif raw_status == "completed":
            status, progress, severity = "completed", 100, "low"
            description = "Данные собраны и готовы к просмотру."
        else:
            status, progress, severity = "needs_attention", None, "high"
            description = str(row.get("error_message") or "Обновление не завершилось. Повтор доступен только через отдельное подтверждение стоимости.")
        tasks.append({
            "id": f"refresh:{row.get('id')}",
            "object_id": row.get("id"),
            "kind": "map_refresh",
            "title": f"{'Обновление карточки'} · {row.get('business_name') or 'точка'}",
            "description": description,
            "status": status,
            "progress": progress,
            "severity": severity,
            "updated_at": row.get("updated_at"),
            "target_scope": {"kind": "business", "id": row.get("business_id")},
            "available_actions": ["open"] if status != "needs_attention" else [],
            "action_unavailable_reason": "Повтор платный и появится после preview" if status == "needs_attention" else None,
        })
    return tasks


def _operator_mobile_route(result: dict) -> dict:
    intent = str(result.get("intent") or result.get("capability") or "").lower()
    if "review" in intent:
        return {"screen": "reviews", "filters": {"status": "drafts" if result.get("draft") or result.get("drafts") else "unanswered"}, "capability": result.get("capability") or intent}
    if "service" in intent:
        return {"screen": "services", "filters": {}, "capability": result.get("capability") or intent}
    if "news" in intent or "content" in intent or "social" in intent:
        return {"screen": "content", "filters": {}, "capability": result.get("capability") or intent}
    if "partnership" in intent or "outreach" in intent:
        return {"screen": "partnerships", "filters": {}, "capability": result.get("capability") or intent}
    return {"screen": "tasks", "filters": {}, "capability": result.get("capability") or intent or None}


def _scope_request_values(payload: dict | None = None) -> tuple[str, str | None]:
    source = payload if isinstance(payload, dict) else request.args
    kind = str(source.get("scope_type") or source.get("kind") or "").strip().lower()
    scope_id = str(source.get("scope_id") or source.get("id") or "").strip() or None
    return kind, scope_id


def _telegram_control_actor(cursor, payload: dict):
    verified = validate_telegram_webapp_init_data(payload.get("init_data"))
    if not verified:
        return None, None
    user = load_localos_user_for_telegram(cursor, str(verified.get("telegram_id") or ""))
    if not user:
        return None, None
    return verified, user


def _attach_ai_router(result: dict, ai_router: dict) -> dict:
    combined = dict(result)
    combined["ai_router"] = {
        "status": ai_router.get("status"),
        "intent": ai_router.get("normalized_intent"),
        "charged_credits": ai_router.get("charged_credits"),
        "credit_charged": ai_router.get("credit_charged"),
        "finalization_result": ai_router.get("finalization_result"),
    }
    return combined


def _unsupported_operator_result(message: str) -> dict:
    help_response = build_operator_help_response()
    return {
        "status": "unsupported",
        "intent": "unknown",
        "message": message,
        "chat_response": (
            "Не понял команду. Я могу помочь с карточкой, отзывами, новостями, постами и услугами.\n\n"
            + str(help_response.get("chat_response") or "")
        ),
        "blocked_reasons": ["unsupported_operator_chat_intent"],
        "ui_actions": help_response.get("ui_actions") or [],
        "external_calls_performed": False,
        "external_writes_performed": False,
        "manual_publication_only": True,
        "paid_actions_performed": False,
        "credit_charged": False,
    }


def _manual_review_guard_result(message: str) -> dict:
    return {
        "status": "blocked",
        "intent": "manual_review_add_and_reply",
        "message": message,
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


def _has_explicit_manual_review_text(message: str) -> bool:
    text = str(message or "").strip().lower()
    if "отзыв:" in text:
        return True
    if "добав" in text and "отзыв" in text and ":" in text:
        return True
    return False


@operator_bp.route("/scopes", methods=["GET"])
def operator_scopes():
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    user_id = str(user_data.get("user_id") or user_data.get("id") or "")
    query = str(request.args.get("q") or "").strip()
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        catalog = list_control_scopes(cursor, user_id=user_id, search_query=query, business_limit=100)
        requested_kind, requested_id = _scope_request_values(payload)
        selected = resolve_control_scope(
            cursor,
            user_id=user_id,
            requested_kind=requested_kind,
            requested_id=requested_id,
        )
        return jsonify({"success": True, "catalog": catalog, "selected_scope": selected})
    finally:
        db.close()


@operator_bp.route("/summary", methods=["GET"])
def operator_scope_summary():
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    user_id = str(user_data.get("user_id") or user_data.get("id") or "")
    kind, scope_id = _scope_request_values()
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        scope = resolve_control_scope(
            cursor,
            user_id=user_id,
            requested_kind=kind,
            requested_id=scope_id,
        )
        if not scope:
            return jsonify({"success": False, "error": "Контекст не найден или недоступен"}), 403
        summary = build_operator_scope_summary(cursor, scope=scope, user_id=user_id)
        return jsonify({"success": True, "summary": summary})
    finally:
        db.close()


@operator_bp.route("/telegram/bootstrap", methods=["POST"])
def operator_telegram_bootstrap():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"success": False, "error": "Некорректный запрос"}), 400
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        verified, user = _telegram_control_actor(cursor, payload)
        if not verified or not user:
            return jsonify({"success": False, "error": "Telegram-сессия недействительна"}), 401
        user_id = str(user.get("id") or "")
        query = str(payload.get("q") or "").strip()
        catalog = list_control_scopes(cursor, user_id=user_id, search_query=query, business_limit=100)
        selected = resolve_control_scope(cursor, user_id=user_id)
        summary = build_operator_scope_summary(cursor, scope=selected, user_id=user_id) if selected else None
        preferences = load_control_preferences(cursor, user_id)
        web_session_token = None
        if not query:
            web_session_token = create_session(
                user_id,
                ip_address=request.headers.get("X-Forwarded-For") or request.remote_addr,
                user_agent="localos-telegram-mini-app",
                expires_days=1,
            )
        return jsonify(
            {
                "success": True,
                "user": {
                    "id": user_id,
                    "name": str(user.get("name") or verified.get("first_name") or ""),
                    "is_superadmin": bool(user.get("is_superadmin")),
                },
                "catalog": catalog,
                "selected_scope": selected,
                "summary": summary,
                "preferences": preferences,
                "notification_preferences": preferences.get("notifications") if isinstance(preferences, dict) else {},
                "deep_link_targets": [item["key"] for item in _mobile_navigation(selected or {}, bool(user.get("is_superadmin"))) if item.get("status") != "hidden"],
                "web_session_token": web_session_token,
                "mini_app_v2_enabled": str(os.getenv("TELEGRAM_MINI_APP_V2_ENABLED", "true")).lower() in {"1", "true", "yes", "on"},
                "navigation": _mobile_navigation(selected or {}, bool(user.get("is_superadmin"))),
            }
        )
    finally:
        db.close()


@operator_bp.route("/telegram/scope", methods=["POST"])
def operator_telegram_select_scope():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"success": False, "error": "Некорректный запрос"}), 400
    kind, scope_id = _scope_request_values(payload)
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        verified, user = _telegram_control_actor(cursor, payload)
        if not verified or not user:
            return jsonify({"success": False, "error": "Telegram-сессия недействительна"}), 401
        user_id = str(user.get("id") or "")
        scope = resolve_control_scope(
            cursor,
            user_id=user_id,
            requested_kind=kind,
            requested_id=scope_id,
            persist=True,
            telegram_id=str(verified.get("telegram_id") or ""),
        )
        if not scope:
            db.conn.rollback()
            return jsonify({"success": False, "error": "Контекст не найден или недоступен"}), 403
        db.conn.commit()
        summary = build_operator_scope_summary(cursor, scope=scope, user_id=user_id)
        return jsonify({"success": True, "selected_scope": scope, "summary": summary})
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


@operator_bp.route("/telegram/favorite", methods=["POST"])
def operator_telegram_toggle_favorite():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"success": False, "error": "Некорректный запрос"}), 400
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        verified, user = _telegram_control_actor(cursor, payload)
        if not verified or not user:
            return jsonify({"success": False, "error": "Telegram-сессия недействительна"}), 401
        user_id = str(user.get("id") or "")
        scope = resolve_control_scope(cursor, user_id=user_id)
        if not scope:
            return jsonify({"success": False, "error": "Рабочий раздел не найден"}), 404
        favorite = toggle_favorite_control_scope(
            cursor,
            user_id=user_id,
            telegram_id=str(verified.get("telegram_id") or ""),
            scope=scope,
        )
        db.conn.commit()
        return jsonify({"success": True, "favorite": favorite, "preferences": load_control_preferences(cursor, user_id)})
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


@operator_bp.route("/attention-brief", methods=["GET"])
def operator_attention_brief():
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401

    business_id = str(request.args.get("business_id") or "").strip()
    if not business_id:
        return jsonify({"success": False, "error": "business_id обязателен"}), 400

    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        has_access, owner_id = verify_business_access(cursor, business_id, user_data)
        if not has_access:
            status_code = 403 if owner_id else 404
            message = "Нет доступа" if owner_id else "Бизнес не найден"
            return jsonify({"success": False, "error": message}), status_code

        user_id = str(user_data.get("user_id") or user_data.get("id") or "")
        brief = build_attention_brief(cursor, business_id, user_id)
        record_operator_event(
            cursor,
            business_id=business_id,
            user_id=user_id,
            event_type="operator_context_built",
            input_summary={"query": brief.get("query"), "data_mode": brief.get("data_mode")},
            output_summary={
                "signals_count": (brief.get("summary") or {}).get("signals_count"),
                "paid_action_offers": len(brief.get("paid_action_offers") or []),
            },
            metadata={
                "data_mode": brief.get("data_mode"),
                "paid_refresh_required_for_fresh_data": (brief.get("freshness") or {}).get("paid_refresh_required_for_fresh_data"),
            },
        )
        db.conn.commit()
        return jsonify({"success": True, "brief": brief})
    except Exception:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500
    finally:
        db.close()


@operator_bp.route("/inbox", methods=["GET"])
def operator_inbox():
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401

    business_id = str(request.args.get("business_id") or "").strip()
    if not business_id:
        return jsonify({"success": False, "error": "business_id обязателен"}), 400

    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        has_access, owner_id = verify_business_access(cursor, business_id, user_data)
        if not has_access:
            status_code = 403 if owner_id else 404
            message = "Нет доступа" if owner_id else "Бизнес не найден"
            return jsonify({"success": False, "error": message}), status_code

        user_id = str(user_data.get("user_id") or user_data.get("id") or "")
        inbox = build_operator_inbox(cursor, business_id=business_id, user_id=user_id)
        record_operator_event(
            cursor,
            business_id=business_id,
            user_id=user_id,
            event_type="operator_context_built",
            status="completed",
            input_summary={"query": "operator_inbox"},
            output_summary={
                "items_count": (inbox.get("summary") or {}).get("items_count"),
                "paid_generation_offers": len(inbox.get("paid_generation_offers") or []),
            },
            metadata={
                "external_writes_performed": False,
                "manual_publication_only": True,
            },
        )
        db.conn.commit()
        return jsonify({"success": True, "inbox": inbox})
    except Exception:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500
    finally:
        db.close()


@operator_bp.route("/consent-policy", methods=["GET"])
def operator_consent_policy_list():
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401

    business_id = str(request.args.get("business_id") or "").strip()
    if not business_id:
        return jsonify({"success": False, "error": "business_id обязателен"}), 400

    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        has_access, owner_id = verify_business_access(cursor, business_id, user_data)
        if not has_access:
            status_code = 403 if owner_id else 404
            message = "Нет доступа" if owner_id else "Бизнес не найден"
            return jsonify({"success": False, "error": message}), status_code

        policies = list_consent_policies(cursor, business_id)
        return jsonify({"success": True, "policies": policies})
    except Exception:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500
    finally:
        db.close()


@operator_bp.route("/consent-policy/<action_key>", methods=["PUT"])
def operator_consent_policy_update(action_key: str):
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401

    payload = request.get_json(silent=True) or {}
    business_id = str(payload.get("business_id") or "").strip()
    if not business_id:
        return jsonify({"success": False, "error": "business_id обязателен"}), 400

    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        has_access, owner_id = verify_business_access(cursor, business_id, user_data)
        if not has_access:
            status_code = 403 if owner_id else 404
            message = "Нет доступа" if owner_id else "Бизнес не найден"
            return jsonify({"success": False, "error": message}), status_code

        user_id = str(user_data.get("user_id") or user_data.get("id") or "")
        policy, errors = upsert_consent_policy(cursor, business_id, action_key, user_id, payload)
        if errors or policy is None:
            return jsonify({"success": False, "error": "invalid_consent_policy", "details": errors}), 400
        record_operator_event(
            cursor,
            business_id=business_id,
            user_id=user_id,
            event_type="operator_consent_decision",
            action_key=action_key,
            status="completed",
            input_summary={"requested_mode": payload.get("mode")},
            output_summary={
                "mode": policy.get("mode"),
                "execution_allowed_without_prompt": policy.get("execution_allowed_without_prompt"),
            },
            metadata={
                "policy_id": policy.get("id"),
                "max_credits_per_action": policy.get("max_credits_per_action"),
                "max_credits_per_day": policy.get("max_credits_per_day"),
                "max_credits_per_month": policy.get("max_credits_per_month"),
                "low_balance_warning_threshold": policy.get("low_balance_warning_threshold"),
            },
        )
        db.conn.commit()
        return jsonify({"success": True, "policy": policy})
    except Exception:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500
    finally:
        db.close()


@operator_bp.route("/paid-actions/<action_key>/preflight", methods=["POST"])
def operator_paid_action_preflight(action_key: str):
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401

    payload = request.get_json(silent=True) or {}
    business_id = str(payload.get("business_id") or "").strip()
    if not business_id:
        return jsonify({"success": False, "error": "business_id обязателен"}), 400

    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        has_access, owner_id = verify_business_access(cursor, business_id, user_data)
        if not has_access:
            status_code = 403 if owner_id else 404
            message = "Нет доступа" if owner_id else "Бизнес не найден"
            return jsonify({"success": False, "error": message}), status_code

        user_id = str(user_data.get("user_id") or user_data.get("id") or "")
        preflight = build_paid_action_preflight(
            cursor,
            business_id=business_id,
            user_id=user_id,
            action_key=action_key,
            estimated_credits=payload.get("estimated_credits"),
            explicit_consent=bool(payload.get("explicit_consent")),
        )
        record_operator_event(
            cursor,
            business_id=business_id,
            user_id=user_id,
            event_type="operator_paid_action_estimated",
            action_key=action_key,
            status=str(preflight.get("status") or "recorded"),
            reason_code=",".join(preflight.get("blocked_reasons") or []) or None,
            input_summary={
                "estimated_credits": payload.get("estimated_credits"),
                "explicit_consent": bool(payload.get("explicit_consent")),
            },
            output_summary={
                "status": preflight.get("status"),
                "would_be_allowed": preflight.get("would_be_allowed"),
                "execution_status": preflight.get("execution_status"),
            },
            metadata={
                "estimated_credits": preflight.get("estimated_credits"),
                "balance_credits": preflight.get("balance_credits"),
                "usage_window": preflight.get("usage_window"),
                "blocked_reasons": preflight.get("blocked_reasons"),
                "warnings": preflight.get("warnings"),
                "execution_status": preflight.get("execution_status"),
                "execution_enabled": preflight.get("execution_enabled"),
            },
        )
        db.conn.commit()
        return jsonify({"success": True, "preflight": preflight})
    except Exception:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500
    finally:
        db.close()


@operator_bp.route("/paid-actions/<action_key>/execute", methods=["POST"])
def operator_paid_action_execute(action_key: str):
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401

    payload = request.get_json(silent=True) or {}
    business_id = str(payload.get("business_id") or "").strip()
    if not business_id:
        return jsonify({"success": False, "error": "business_id обязателен"}), 400

    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        has_access, owner_id = verify_business_access(cursor, business_id, user_data)
        if not has_access:
            status_code = 403 if owner_id else 404
            message = "Нет доступа" if owner_id else "Бизнес не найден"
            return jsonify({"success": False, "error": message}), status_code

        user_id = str(user_data.get("user_id") or user_data.get("id") or "")
        execution = build_paid_action_execution_attempt(
            cursor,
            business_id=business_id,
            user_id=user_id,
            action_key=action_key,
            estimated_credits=payload.get("estimated_credits"),
            explicit_consent=bool(payload.get("explicit_consent")),
        )
        record_operator_event(
            cursor,
            business_id=business_id,
            user_id=user_id,
            event_type="operator_execution_blocked",
            action_key=action_key,
            status=str(execution.get("status") or "blocked"),
            reason_code=",".join(execution.get("blocked_reasons") or []) or None,
            input_summary={
                "estimated_credits": payload.get("estimated_credits"),
                "explicit_consent": bool(payload.get("explicit_consent")),
            },
            output_summary={
                "status": execution.get("status"),
                "execution_status": execution.get("execution_status"),
                "next_step": execution.get("next_step"),
            },
            metadata={
                "estimated_credits": execution.get("estimated_credits"),
                "balance_credits": execution.get("balance_credits"),
                "adapter_status": (execution.get("adapter_result") or {}).get("adapter_status"),
                "adapter_runtime_mode": (execution.get("adapter_result") or {}).get("runtime_mode"),
                "adapter_dry_run": (execution.get("adapter_result") or {}).get("dry_run"),
                "adapter_idempotency_key": (execution.get("adapter_result") or {}).get("idempotency_key"),
                "reservation_status": (execution.get("reservation_plan") or {}).get("status"),
                "reservation_requested_credits": (execution.get("reservation_plan") or {}).get("requested_credits"),
                "reservation_blocked_reasons": (execution.get("reservation_plan") or {}).get("blocked_reasons"),
                "reservation_result_status": (execution.get("reservation_result") or {}).get("status"),
                "usage_window": (execution.get("preflight") or {}).get("usage_window"),
                "finalization_result_status": (execution.get("finalization_result") or {}).get("status"),
                "rollback_result_status": (execution.get("rollback_result") or {}).get("status"),
                "credit_charged": execution.get("credit_charged"),
                "credit_released": execution.get("credit_released"),
                "internal_fake_execution_performed": execution.get("internal_fake_execution_performed"),
                "blocked_reasons": execution.get("blocked_reasons"),
                "warnings": execution.get("warnings"),
                "execution_status": execution.get("execution_status"),
                "execution_enabled": execution.get("execution_enabled"),
                "credit_reserved": execution.get("credit_reserved"),
                "parsequeue_jobs_created": execution.get("parsequeue_jobs_created"),
                "ai_generation_performed": execution.get("ai_generation_performed"),
            },
        )
        db.conn.commit()
        return jsonify({"success": True, "execution": execution})
    except Exception:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500
    finally:
        db.close()


@operator_bp.route("/capabilities", methods=["GET"])
def operator_capabilities():
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    return jsonify({"success": True, "capabilities": operator_capability_catalog()})


@operator_bp.route("/conversations/<conversation_id>/messages", methods=["GET"])
def operator_conversation_messages(conversation_id: str):
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    business_id = str(request.args.get("business_id") or "").strip()
    if not business_id:
        return jsonify({"success": False, "error": "business_id обязателен"}), 400
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        has_access, owner_id = verify_business_access(cursor, business_id, user_data)
        if not has_access:
            return jsonify({"success": False, "error": "Нет доступа" if owner_id else "Бизнес не найден"}), 403 if owner_id else 404
        items = list_operator_messages(
            cursor,
            conversation_id=conversation_id,
            business_id=business_id,
            limit=request.args.get("limit") or 100,
        )
        return jsonify({"success": True, "conversation_id": conversation_id, "messages": items})
    finally:
        db.close()


@operator_bp.route("/conversations/current", methods=["GET"])
def current_operator_conversation():
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    business_id = str(request.args.get("business_id") or "").strip()
    channel = str(request.args.get("channel") or "web").strip() or "web"
    if not business_id:
        return jsonify({"success": False, "error": "business_id обязателен"}), 400
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        has_access, owner_id = verify_business_access(cursor, business_id, user_data)
        if not has_access:
            return jsonify({"success": False, "error": "Нет доступа" if owner_id else "Бизнес не найден"}), 403 if owner_id else 404
        user_id = str(user_data.get("user_id") or user_data.get("id") or "")
        conversation = find_latest_operator_conversation(
            cursor,
            business_id=business_id,
            user_id=user_id,
            channel=channel,
        )
        conversation_id = str(conversation.get("id") or "")
        messages = list_operator_messages(
            cursor,
            conversation_id=conversation_id,
            business_id=business_id,
            limit=request.args.get("limit") or 100,
        ) if conversation_id else []
        return jsonify({"success": True, "conversation": conversation or None, "messages": messages})
    finally:
        db.close()


@operator_bp.route("/chat", methods=["POST"])
def operator_chat():
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401

    payload = request.get_json(silent=True) or {}
    business_id = str(payload.get("business_id") or "").strip()
    message = str(payload.get("message") or "").strip()
    if not business_id:
        return jsonify({"success": False, "error": "business_id обязателен"}), 400
    if not message:
        return jsonify({"success": False, "error": "message обязателен"}), 400

    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        has_access, owner_id = verify_business_access(cursor, business_id, user_data)
        if not has_access:
            status_code = 403 if owner_id else 404
            message_text = "Нет доступа" if owner_id else "Бизнес не найден"
            return jsonify({"success": False, "error": message_text}), status_code

        user_id = str(user_data.get("user_id") or user_data.get("id") or "")
        record_operator_event(
            cursor,
            business_id=business_id,
            user_id=user_id,
            event_type="operator_message_received",
            status="received",
            input_summary={"message": message[:500]},
            output_summary={"channel": "web"},
        )
        conversation = get_or_create_operator_conversation(
            cursor,
            business_id=business_id,
            user_id=user_id,
            channel=str(payload.get("channel") or "web").strip() or "web",
            conversation_id=payload.get("conversation_id"),
            transport_key=payload.get("transport_key"),
        )
        conversation_id = str(conversation.get("id") or "")
        append_operator_message(
            cursor,
            conversation_id=conversation_id,
            business_id=business_id,
            user_id=user_id,
            role="user",
            content=message,
        )
        result, next_pending_context = route_operator_message(
            cursor,
            business_id=business_id,
            user_id=user_id,
            message=message,
            channel=str(payload.get("channel") or "web").strip() or "web",
            limit=payload.get("limit") or 5,
            explicit_url=payload.get("url"),
            pending_context=conversation_pending_context(conversation),
            action_payload=payload,
            refresh_handler=refresh_reviews_from_operator,
            ai_router_handler=classify_operator_intent_with_ai,
            manual_review_handler=process_operator_chat_message,
        )
        result["conversation_id"] = conversation_id
        result["mobile_route"] = _operator_mobile_route(result)
        approval = result.get("approval") if isinstance(result.get("approval"), dict) else {}
        approval_envelope = approval.get("envelope") if isinstance(approval.get("envelope"), dict) else {}
        if result.get("status") == "approval_required" and approval_envelope:
            pending_action = create_pending_operator_action(
                cursor,
                conversation_id=conversation_id,
                business_id=business_id,
                user_id=user_id,
                capability=str(result.get("capability") or result.get("intent") or "unknown"),
                envelope=approval_envelope,
            )
            action_id = str(pending_action.get("id") or "")
            approval["action_id"] = action_id
            result["approval"] = approval
            result["ui_actions"] = list(result.get("ui_actions") or []) + [
                {
                    "action": "confirm_operator_action",
                    "label": "Подтвердить",
                    "href": "",
                    "payload": {"action_id": action_id},
                }
            ]
        set_operator_pending_context(cursor, conversation_id, next_pending_context)
        append_operator_message(
            cursor,
            conversation_id=conversation_id,
            business_id=business_id,
            user_id=user_id,
            role="operator",
            content=result.get("chat_response") or result.get("summary"),
            capability=result.get("capability"),
            status=result.get("status"),
            result=result,
        )
        status = str(result.get("status") or "blocked")
        review = result.get("review") if isinstance(result.get("review"), dict) else {}
        draft = result.get("draft") if isinstance(result.get("draft"), dict) else {}
        news_draft = result.get("news_draft") if isinstance(result.get("news_draft"), dict) else {}
        social_post_draft = result.get("social_post_draft") if isinstance(result.get("social_post_draft"), dict) else {}
        optimization_job = result.get("optimization_job") if isinstance(result.get("optimization_job"), dict) else {}
        drafts = result.get("drafts") if isinstance(result.get("drafts"), list) else []
        finalization = result.get("finalization_result") if isinstance(result.get("finalization_result"), dict) else {}
        ai_router = result.get("ai_router") if isinstance(result.get("ai_router"), dict) else {}
        ai_router_finalization = (
            ai_router.get("finalization_result")
            if isinstance(ai_router.get("finalization_result"), dict)
            else {}
        )
        if ai_router_finalization:
            record_operator_event(
                cursor,
                business_id=business_id,
                user_id=user_id,
                event_type="operator_usage_charged",
                action_key="operator_intent_classify",
                status=str(ai_router_finalization.get("status") or "completed"),
                input_summary={"action_key": "operator_intent_classify"},
                output_summary={
                    "charge_credits": ai_router_finalization.get("charge_credits"),
                    "release_credits": ai_router_finalization.get("release_credits"),
                    "normalized_intent": ai_router.get("intent"),
                },
                metadata={
                    "credit_charged": bool(ai_router_finalization.get("side_effects", {}).get("credit_charged")),
                    "paid_actions_performed": bool(ai_router_finalization.get("side_effects", {}).get("credit_charged")),
                    "external_writes_performed": False,
                },
            )
        if review:
            record_operator_event(
                cursor,
                business_id=business_id,
                user_id=user_id,
                event_type="operator_review_added",
                status="completed",
                input_summary={"source": review.get("source")},
                output_summary={"review_id": review.get("id")},
                metadata={"review_id": review.get("id"), "external_writes_performed": False},
            )
        if draft:
            record_operator_event(
                cursor,
                business_id=business_id,
                user_id=user_id,
                event_type="operator_draft_created",
                action_key="review_replies_generate",
                status="completed",
                input_summary={"review_id": draft.get("review_id")},
                output_summary={"draft_id": draft.get("id")},
                metadata={"draft_id": draft.get("id"), "external_writes_performed": False},
            )
        if news_draft:
            record_operator_event(
                cursor,
                business_id=business_id,
                user_id=user_id,
                event_type="operator_draft_created",
                action_key="news_generate",
                status="completed",
                input_summary={"source": "operator_chat"},
                output_summary={"news_id": news_draft.get("id")},
                metadata={
                    "news_id": news_draft.get("id"),
                    "external_writes_performed": False,
                    "manual_publication_only": True,
                },
            )
        if optimization_job:
            record_operator_event(
                cursor,
                business_id=business_id,
                user_id=user_id,
                event_type="operator_draft_created",
                action_key="services_optimize",
                status="completed",
                input_summary={"source": "operator_chat"},
                output_summary={"job_id": optimization_job.get("id")},
                metadata={
                    "job_id": optimization_job.get("id"),
                    "external_writes_performed": False,
                    "manual_apply_required": True,
                },
            )
        if social_post_draft:
            record_operator_event(
                cursor,
                business_id=business_id,
                user_id=user_id,
                event_type="operator_draft_created",
                action_key="social_post_generate",
                status="completed",
                input_summary={"source": "operator_chat"},
                output_summary={"draft_id": social_post_draft.get("id")},
                metadata={
                    "draft_id": social_post_draft.get("id"),
                    "external_writes_performed": False,
                    "manual_publication_only": True,
                },
            )
        for bulk_draft in drafts:
            if not isinstance(bulk_draft, dict):
                continue
            record_operator_event(
                cursor,
                business_id=business_id,
                user_id=user_id,
                event_type="operator_draft_created",
                action_key="review_replies_generate",
                status="completed",
                input_summary={"review_id": bulk_draft.get("review_id")},
                output_summary={"draft_id": bulk_draft.get("id")},
                metadata={"draft_id": bulk_draft.get("id"), "external_writes_performed": False},
            )
        if finalization:
            record_operator_event(
                cursor,
                business_id=business_id,
                user_id=user_id,
                event_type="operator_usage_charged",
                action_key=str(result.get("intent") or "review_replies_generate"),
                status=str(finalization.get("status") or status),
                input_summary={"action_key": str(result.get("intent") or "review_replies_generate")},
                output_summary={
                    "charge_credits": finalization.get("charge_credits"),
                    "release_credits": finalization.get("release_credits"),
                },
                metadata={
                    "credit_charged": bool(finalization.get("side_effects", {}).get("credit_charged")),
                    "paid_actions_performed": bool(finalization.get("side_effects", {}).get("credit_charged")),
                    "external_writes_performed": False,
                },
            )
        db.conn.commit()
        return jsonify({
            "success": status in {"completed", "queued", "processing", "clarification_required", "manual_handoff", "approval_required"},
            "conversation_id": result.get("conversation_id"),
            "operator_result": result,
        })
    except Exception:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500
    finally:
        db.close()


@operator_bp.route("/actions/<action_id>/confirm", methods=["POST"])
def confirm_operator_action(action_id: str):
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    payload = request.get_json(silent=True) or {}
    business_id = str(payload.get("business_id") or "").strip()
    if not business_id:
        return jsonify({"success": False, "error": "business_id обязателен"}), 400
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        has_access, owner_id = verify_business_access(cursor, business_id, user_data)
        if not has_access:
            return jsonify({"success": False, "error": "Нет доступа" if owner_id else "Бизнес не найден"}), 403 if owner_id else 404
        user_id = str(user_data.get("user_id") or user_data.get("id") or "")
        result, idempotent = confirm_pending_operator_action(
            cursor,
            action_id=action_id,
            business_id=business_id,
            user_id=user_id,
        )
        if "action_not_found" in list(result.get("blocked_reasons") or []):
            return jsonify({"success": False, "error": "Действие не найдено"}), 404
        db.conn.commit()
        return jsonify({
            "success": str(result.get("status") or "") == "completed",
            "idempotent": idempotent,
            "operator_result": result,
        })
    except Exception:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500
    finally:
        db.close()


@operator_bp.route("/review-replies/generate", methods=["POST"])
def operator_review_replies_generate():
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401

    payload = request.get_json(silent=True) or {}
    business_id = str(payload.get("business_id") or "").strip()
    if not business_id:
        return jsonify({"success": False, "error": "business_id обязателен"}), 400

    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        has_access, owner_id = verify_business_access(cursor, business_id, user_data)
        if not has_access:
            status_code = 403 if owner_id else 404
            message = "Нет доступа" if owner_id else "Бизнес не найден"
            return jsonify({"success": False, "error": message}), status_code

        user_id = str(user_data.get("user_id") or user_data.get("id") or "")
        result = generate_review_reply_drafts_for_unanswered_reviews(
            cursor,
            business_id=business_id,
            user_id=user_id,
            limit=payload.get("limit") or 5,
            review_id=payload.get("review_id"),
            channel="web",
        )
        status = str(result.get("status") or "blocked")
        drafts = result.get("drafts") if isinstance(result.get("drafts"), list) else []
        for draft in drafts:
            if not isinstance(draft, dict):
                continue
            record_operator_event(
                cursor,
                business_id=business_id,
                user_id=user_id,
                event_type="operator_draft_created",
                action_key="review_replies_generate",
                status="completed",
                input_summary={"review_id": draft.get("review_id")},
                output_summary={"draft_id": draft.get("id")},
                metadata={"draft_id": draft.get("id"), "external_writes_performed": False},
            )
        finalization = result.get("finalization_result") if isinstance(result.get("finalization_result"), dict) else {}
        if finalization:
            record_operator_event(
                cursor,
                business_id=business_id,
                user_id=user_id,
                event_type="operator_usage_charged",
                action_key="review_replies_generate",
                status=str(finalization.get("status") or status),
                input_summary={"action_key": "review_replies_generate"},
                output_summary={
                    "charge_credits": finalization.get("charge_credits"),
                    "release_credits": finalization.get("release_credits"),
                },
                metadata={
                    "credit_charged": bool(finalization.get("side_effects", {}).get("credit_charged")),
                    "paid_actions_performed": bool(finalization.get("side_effects", {}).get("credit_charged")),
                    "external_writes_performed": False,
                },
            )
        db.conn.commit()
        return jsonify({"success": status == "completed", "operator_result": result})
    except Exception:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500
    finally:
        db.close()


@operator_bp.route("/reviews/refresh-results/<queue_id>", methods=["GET"])
def operator_review_refresh_result(queue_id: str):
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401

    business_id = str(request.args.get("business_id") or "").strip()
    if not business_id:
        return jsonify({"success": False, "error": "business_id обязателен"}), 400

    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        has_access, owner_id = verify_business_access(cursor, business_id, user_data)
        if not has_access:
            status_code = 403 if owner_id else 404
            message = "Нет доступа" if owner_id else "Бизнес не найден"
            return jsonify({"success": False, "error": message}), status_code

        user_id = str(user_data.get("user_id") or user_data.get("id") or "")
        result = build_refresh_result_status(
            cursor,
            business_id=business_id,
            user_id=user_id,
            queue_id=queue_id,
        )
        record_operator_event(
            cursor,
            business_id=business_id,
            user_id=user_id,
            event_type="operator_context_built",
            action_key="map_reviews_refresh",
            status=str(result.get("status") or "blocked"),
            reason_code=",".join(result.get("blocked_reasons") or []) or None,
            input_summary={"queue_id": queue_id},
            output_summary={
                "queue_status": result.get("queue_status"),
                "new_reviews_count": result.get("new_reviews_count"),
                "new_unanswered_reviews_count": result.get("new_unanswered_reviews_count"),
            },
            metadata={
                "external_writes_performed": False,
                "manual_publication_only": True,
            },
        )
        db.conn.commit()
        return jsonify({"success": result.get("status") in {"completed", "processing"}, "refresh_result": result})
    except Exception:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500
    finally:
        db.close()


@operator_bp.route("/reviews/refresh-jobs", methods=["GET"])
def operator_review_refresh_jobs():
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401

    business_id = str(request.args.get("business_id") or "").strip()
    if not business_id:
        return jsonify({"success": False, "error": "business_id обязателен"}), 400

    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        has_access, owner_id = verify_business_access(cursor, business_id, user_data)
        if not has_access:
            status_code = 403 if owner_id else 404
            message = "Нет доступа" if owner_id else "Бизнес не найден"
            return jsonify({"success": False, "error": message}), status_code

        user_id = str(user_data.get("user_id") or user_data.get("id") or "")
        result = list_refresh_jobs(
            cursor,
            business_id=business_id,
            user_id=user_id,
            limit=request.args.get("limit") or 10,
        )
        record_operator_event(
            cursor,
            business_id=business_id,
            user_id=user_id,
            event_type="operator_context_built",
            action_key="map_reviews_refresh",
            status=str(result.get("status") or "completed"),
            input_summary={"query": "operator_refresh_jobs"},
            output_summary=result.get("summary") or {},
            metadata={
                "external_writes_performed": False,
                "manual_publication_only": True,
            },
        )
        db.conn.commit()
        return jsonify({"success": True, "refresh_jobs": result})
    except Exception:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500
    finally:
        db.close()


@operator_bp.route("/reviews/refresh-jobs/<queue_id>/retry", methods=["POST"])
def operator_review_refresh_job_retry(queue_id: str):
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401

    payload = request.get_json(silent=True) or {}
    business_id = str(payload.get("business_id") or request.args.get("business_id") or "").strip()
    if not business_id:
        return jsonify({"success": False, "error": "business_id обязателен"}), 400

    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        has_access, owner_id = verify_business_access(cursor, business_id, user_data)
        if not has_access:
            status_code = 403 if owner_id else 404
            message = "Нет доступа" if owner_id else "Бизнес не найден"
            return jsonify({"success": False, "error": message}), status_code

        user_id = str(user_data.get("user_id") or user_data.get("id") or "")
        result = request_refresh_retry(
            cursor,
            business_id=business_id,
            user_id=user_id,
            queue_id=queue_id,
            estimated_credits=payload.get("estimated_credits"),
            confirm_retry=bool(payload.get("confirm_retry")),
        )
        record_operator_event(
            cursor,
            business_id=business_id,
            user_id=user_id,
            event_type="operator_tool_executed" if result.get("status") == "queued" else "operator_execution_blocked",
            action_key="map_reviews_refresh",
            status=str(result.get("status") or "blocked"),
            reason_code=",".join(result.get("blocked_reasons") or []) or None,
            input_summary={"queue_id": queue_id, "retry": True},
            output_summary={
                "new_queue_id": result.get("new_queue_id"),
                "reservation_id": result.get("reservation_id"),
                "estimated_credits": result.get("estimated_credits"),
            },
            metadata={
                "source_queue_id": queue_id,
                "retry_requested": True,
                "external_writes_performed": False,
                "manual_publication_only": True,
                "credit_reserved": bool((result.get("side_effects") or {}).get("credit_reserved")),
            },
        )
        db.conn.commit()
        return jsonify({"success": result.get("status") == "queued", "retry_result": result})
    except Exception:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500
    finally:
        db.close()


@operator_bp.route("/reviews/refresh-jobs/<queue_id>/recovery", methods=["GET", "POST"])
def operator_review_refresh_job_recovery(queue_id: str):
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401

    payload = request.get_json(silent=True) or {}
    business_id = str(payload.get("business_id") or request.args.get("business_id") or "").strip()
    if not business_id:
        return jsonify({"success": False, "error": "business_id обязателен"}), 400

    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        has_access, owner_id = verify_business_access(cursor, business_id, user_data)
        if not has_access:
            status_code = 403 if owner_id else 404
            message = "Нет доступа" if owner_id else "Бизнес не найден"
            return jsonify({"success": False, "error": message}), status_code

        user_id = str(user_data.get("user_id") or user_data.get("id") or "")
        if request.method == "POST" and bool(payload.get("confirm_release")):
            result = release_failed_refresh_reservation(
                cursor,
                business_id=business_id,
                user_id=user_id,
                queue_id=queue_id,
                confirm_release=True,
            )
            event_type = "operator_tool_executed" if result.get("status") == "released" else "operator_execution_blocked"
            status_value = str(result.get("status") or "blocked")
        else:
            result = build_refresh_recovery_plan(
                cursor,
                business_id=business_id,
                user_id=user_id,
                queue_id=queue_id,
            )
            event_type = "operator_context_built"
            status_value = str(result.get("status") or "blocked")

        record_operator_event(
            cursor,
            business_id=business_id,
            user_id=user_id,
            event_type=event_type,
            action_key="map_reviews_refresh",
            status=status_value,
            reason_code=",".join(result.get("blocked_reasons") or []) or None,
            input_summary={"queue_id": queue_id, "recovery": True, "method": request.method},
            output_summary={
                "retry_allowed": result.get("retry_allowed"),
                "release_allowed": result.get("release_allowed"),
                "reservation_id": result.get("reservation_id"),
                "outstanding_credits": result.get("outstanding_credits"),
            },
            metadata={
                "external_writes_performed": False,
                "manual_publication_only": True,
                "reservation_released": bool((result.get("side_effects") or {}).get("reservation_released")),
            },
        )
        db.conn.commit()
        return jsonify({"success": result.get("status") in {"ready", "released"}, "recovery_result": result})
    except Exception:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500
    finally:
        db.close()


@operator_bp.route("/content-history", methods=["GET"])
def operator_content_history():
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401

    business_id = str(request.args.get("business_id") or "").strip()
    if not business_id:
        return jsonify({"success": False, "error": "business_id обязателен"}), 400

    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        has_access, owner_id = verify_business_access(cursor, business_id, user_data)
        if not has_access:
            status_code = 403 if owner_id else 404
            message = "Нет доступа" if owner_id else "Бизнес не найден"
            return jsonify({"success": False, "error": message}), status_code

        user_id = str(user_data.get("user_id") or user_data.get("id") or "")
        history = list_operator_content_history(
            cursor,
            business_id=business_id,
            user_id=user_id,
            limit=request.args.get("limit") or 20,
        )
        record_operator_event(
            cursor,
            business_id=business_id,
            user_id=user_id,
            event_type="operator_context_built",
            action_key="content_history_read",
            status=str(history.get("status") or "completed"),
            input_summary={"query": "operator_content_history"},
            output_summary=history.get("summary") or {},
            metadata={
                "external_writes_performed": False,
                "manual_publication_only": True,
            },
        )
        db.conn.commit()
        return jsonify({"success": True, "content_history": history})
    except Exception:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500
    finally:
        db.close()


@operator_bp.route("/services/optimize", methods=["POST"])
def operator_services_optimize():
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401

    payload = request.get_json(silent=True) or {}
    business_id = str(payload.get("business_id") or "").strip()
    if not business_id:
        return jsonify({"success": False, "error": "business_id обязателен"}), 400

    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        has_access, owner_id = verify_business_access(cursor, business_id, user_data)
        if not has_access:
            status_code = 403 if owner_id else 404
            message = "Нет доступа" if owner_id else "Бизнес не найден"
            return jsonify({"success": False, "error": message}), status_code

        user_id = str(user_data.get("user_id") or user_data.get("id") or "")
        result = optimize_services_from_operator(
            cursor,
            business_id=business_id,
            user_id=user_id,
            limit=payload.get("limit") or 5,
            channel="web",
        )
        status = str(result.get("status") or "blocked")
        optimization_job = result.get("optimization_job") if isinstance(result.get("optimization_job"), dict) else {}
        if optimization_job:
            record_operator_event(
                cursor,
                business_id=business_id,
                user_id=user_id,
                event_type="operator_draft_created",
                action_key="services_optimize",
                status="completed",
                input_summary={"source": "operator_inbox"},
                output_summary={"job_id": optimization_job.get("id")},
                metadata={
                    "job_id": optimization_job.get("id"),
                    "external_writes_performed": False,
                    "manual_apply_required": True,
                },
            )
        finalization = result.get("finalization_result") if isinstance(result.get("finalization_result"), dict) else {}
        if finalization:
            record_operator_event(
                cursor,
                business_id=business_id,
                user_id=user_id,
                event_type="operator_usage_charged",
                action_key="services_optimize",
                status=str(finalization.get("status") or status),
                input_summary={"action_key": "services_optimize"},
                output_summary={
                    "charge_credits": finalization.get("charge_credits"),
                    "release_credits": finalization.get("release_credits"),
                },
                metadata={
                    "credit_charged": bool(finalization.get("side_effects", {}).get("credit_charged")),
                    "paid_actions_performed": bool(finalization.get("side_effects", {}).get("credit_charged")),
                    "external_writes_performed": False,
                    "manual_apply_required": True,
                },
            )
        db.conn.commit()
        return jsonify({"success": status == "completed", "operator_result": result})
    except Exception:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500
    finally:
        db.close()


@operator_bp.route("/services/optimize/apply", methods=["POST"])
def operator_services_optimize_apply():
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401

    payload = request.get_json(silent=True) or {}
    business_id = str(payload.get("business_id") or "").strip()
    if not business_id:
        return jsonify({"success": False, "error": "business_id обязателен"}), 400

    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        has_access, owner_id = verify_business_access(cursor, business_id, user_data)
        if not has_access:
            status_code = 403 if owner_id else 404
            message = "Нет доступа" if owner_id else "Бизнес не найден"
            return jsonify({"success": False, "error": message}), status_code

        user_id = str(user_data.get("user_id") or user_data.get("id") or "")
        result = apply_service_optimization_suggestions(
            cursor,
            business_id=business_id,
            user_id=user_id,
            job_id=payload.get("job_id"),
            item_ids=payload.get("item_ids"),
            limit=payload.get("limit") or 5,
            channel="web",
            explicit_confirmation=bool(payload.get("confirm_apply")),
        )
        status = str(result.get("status") or "blocked")
        record_operator_event(
            cursor,
            business_id=business_id,
            user_id=user_id,
            event_type="operator_tool_executed",
            action_key="services_optimize_apply",
            status=status,
            input_summary={
                "job_id": payload.get("job_id"),
                "item_ids": payload.get("item_ids") if isinstance(payload.get("item_ids"), list) else [],
            },
            output_summary={
                "applied_count": result.get("applied_count"),
                "job_status": (result.get("optimization_job") or {}).get("status") if isinstance(result.get("optimization_job"), dict) else None,
            },
            metadata={
                "external_writes_performed": False,
                "manual_approval_received": bool(result.get("manual_approval_received")),
                "explicit_confirmation": bool(payload.get("confirm_apply")),
                "paid_actions_performed": False,
                "credit_charged": False,
            },
        )
        db.conn.commit()
        return jsonify({"success": status == "completed", "operator_result": result})
    except Exception:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500
    finally:
        db.close()


@operator_bp.route("/social-posts/generate", methods=["POST"])
def operator_social_posts_generate():
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401

    payload = request.get_json(silent=True) or {}
    business_id = str(payload.get("business_id") or "").strip()
    message = str(payload.get("message") or payload.get("source_text") or "").strip()
    if not business_id:
        return jsonify({"success": False, "error": "business_id обязателен"}), 400
    if not message:
        return jsonify({"success": False, "error": "message обязателен"}), 400

    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        has_access, owner_id = verify_business_access(cursor, business_id, user_data)
        if not has_access:
            status_code = 403 if owner_id else 404
            message_text = "Нет доступа" if owner_id else "Бизнес не найден"
            return jsonify({"success": False, "error": message_text}), status_code

        user_id = str(user_data.get("user_id") or user_data.get("id") or "")
        result = generate_social_post_draft_from_operator(
            cursor,
            business_id=business_id,
            user_id=user_id,
            message=message,
            channel="web",
        )
        status = str(result.get("status") or "blocked")
        social_post_draft = result.get("social_post_draft") if isinstance(result.get("social_post_draft"), dict) else {}
        if social_post_draft:
            record_operator_event(
                cursor,
                business_id=business_id,
                user_id=user_id,
                event_type="operator_draft_created",
                action_key="social_post_generate",
                status="completed",
                input_summary={"source": "operator_inbox"},
                output_summary={"draft_id": social_post_draft.get("id")},
                metadata={
                    "draft_id": social_post_draft.get("id"),
                    "external_writes_performed": False,
                    "manual_publication_only": True,
                },
            )
        finalization = result.get("finalization_result") if isinstance(result.get("finalization_result"), dict) else {}
        if finalization:
            record_operator_event(
                cursor,
                business_id=business_id,
                user_id=user_id,
                event_type="operator_usage_charged",
                action_key="social_post_generate",
                status=str(finalization.get("status") or status),
                input_summary={"action_key": "social_post_generate"},
                output_summary={
                    "charge_credits": finalization.get("charge_credits"),
                    "release_credits": finalization.get("release_credits"),
                },
                metadata={
                    "credit_charged": bool(finalization.get("side_effects", {}).get("credit_charged")),
                    "paid_actions_performed": bool(finalization.get("side_effects", {}).get("credit_charged")),
                    "external_writes_performed": False,
                },
            )
        db.conn.commit()
        return jsonify({"success": status == "completed", "operator_result": result})
    except Exception:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500
    finally:
        db.close()


@operator_bp.route("/news/generate", methods=["POST"])
def operator_news_generate():
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401

    payload = request.get_json(silent=True) or {}
    business_id = str(payload.get("business_id") or "").strip()
    message = str(payload.get("message") or payload.get("source_text") or "").strip()
    if not business_id:
        return jsonify({"success": False, "error": "business_id обязателен"}), 400
    if not message:
        return jsonify({"success": False, "error": "message обязателен"}), 400

    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        has_access, owner_id = verify_business_access(cursor, business_id, user_data)
        if not has_access:
            status_code = 403 if owner_id else 404
            message_text = "Нет доступа" if owner_id else "Бизнес не найден"
            return jsonify({"success": False, "error": message_text}), status_code

        user_id = str(user_data.get("user_id") or user_data.get("id") or "")
        result = generate_news_draft_from_operator(
            cursor,
            business_id=business_id,
            user_id=user_id,
            message=message,
            channel="web",
        )
        status = str(result.get("status") or "blocked")
        news_draft = result.get("news_draft") if isinstance(result.get("news_draft"), dict) else {}
        if news_draft:
            record_operator_event(
                cursor,
                business_id=business_id,
                user_id=user_id,
                event_type="operator_draft_created",
                action_key="news_generate",
                status="completed",
                input_summary={"source": "operator_inbox"},
                output_summary={"news_id": news_draft.get("id")},
                metadata={
                    "news_id": news_draft.get("id"),
                    "external_writes_performed": False,
                    "manual_publication_only": True,
                },
            )
        finalization = result.get("finalization_result") if isinstance(result.get("finalization_result"), dict) else {}
        if finalization:
            record_operator_event(
                cursor,
                business_id=business_id,
                user_id=user_id,
                event_type="operator_usage_charged",
                action_key="news_generate",
                status=str(finalization.get("status") or status),
                input_summary={"action_key": "news_generate"},
                output_summary={
                    "charge_credits": finalization.get("charge_credits"),
                    "release_credits": finalization.get("release_credits"),
                },
                metadata={
                    "credit_charged": bool(finalization.get("side_effects", {}).get("credit_charged")),
                    "paid_actions_performed": bool(finalization.get("side_effects", {}).get("credit_charged")),
                    "external_writes_performed": False,
                },
            )
        db.conn.commit()
        return jsonify({"success": status == "completed", "operator_result": result})
    except Exception:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500
    finally:
        db.close()


@operator_bp.route("/review-reply-drafts/<draft_id>/mark-manual-published", methods=["POST"])
def operator_review_reply_draft_mark_manual_published(draft_id: str):
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401

    payload = request.get_json(silent=True) or {}
    business_id = str(payload.get("business_id") or "").strip()
    if not business_id:
        return jsonify({"success": False, "error": "business_id обязателен"}), 400

    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        has_access, owner_id = verify_business_access(cursor, business_id, user_data)
        if not has_access:
            status_code = 403 if owner_id else 404
            message = "Нет доступа" if owner_id else "Бизнес не найден"
            return jsonify({"success": False, "error": message}), status_code

        user_id = str(user_data.get("user_id") or user_data.get("id") or "")
        result = mark_review_reply_draft_manual_published(
            cursor,
            business_id=business_id,
            user_id=user_id,
            draft_id=draft_id,
        )
        status = str(result.get("status") or "blocked")
        record_operator_event(
            cursor,
            business_id=business_id,
            user_id=user_id,
            event_type="operator_manual_publish_marked",
            channel="web",
            action_key="review_replies_generate",
            status=status,
            reason_code=",".join(result.get("blocked_reasons") or []) or None,
            input_summary={"draft_id": draft_id},
            output_summary={"status": status},
            metadata={
                "draft_id": draft_id,
                "manual_publication_only": True,
                "external_writes_performed": False,
            },
        )
        db.conn.commit()
        return jsonify({"success": status == "completed", "manual_publish": result})
    except Exception:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500
    finally:
        db.close()


def _resolve_mobile_scope(cursor, user_data: dict) -> dict | None:
    user_id = str(user_data.get("user_id") or user_data.get("id") or "")
    kind, scope_id = _scope_request_values()
    return resolve_control_scope(
        cursor,
        user_id=user_id,
        requested_kind=kind,
        requested_id=scope_id,
    )


@operator_bp.route("/mobile/workspace", methods=["GET"])
def operator_mobile_workspace():
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        scope = _resolve_mobile_scope(cursor, user_data)
        if not scope:
            return jsonify({"success": False, "error": "Раздел недоступен"}), 403
        user_id = str(user_data.get("user_id") or user_data.get("id") or "")
        summary = build_operator_scope_summary(cursor, scope=scope, user_id=user_id)
        items = list(summary.get("attention_items") or [])
        if scope.get("kind") == "business":
            inbox = build_operator_inbox(cursor, business_id=str(scope.get("id") or ""), user_id=user_id)
            items = list(inbox.get("items") or [])
        items.extend(_mobile_background_tasks(cursor, scope))
        items = [_mobile_task_item(item) for item in items]
        attention_count = len([item for item in items if item.get("status") == "needs_attention"])
        working_count = len([item for item in items if item.get("status") == "in_progress"])
        completed_count = len([item for item in items if item.get("status") == "completed"])
        return jsonify({
            "success": True,
            "scope": scope,
            "items": items,
            "counts": {
                "attention": attention_count,
                "working": working_count,
                "completed": completed_count,
                "total": len(items),
            },
            "cursor": None,
            "as_of": datetime.now(timezone.utc).isoformat(),
            "data_warnings": summary.get("data_warnings") or [],
            "available_actions": summary.get("available_actions") or [],
            "filters": {"statuses": ["needs_attention", "in_progress", "completed"]},
            "freshness": summary.get("freshness") or {"status": "live"},
            "summary": summary,
            "navigation": _mobile_navigation(scope, bool(user_data.get("is_superadmin"))),
        })
    finally:
        db.close()


@operator_bp.route("/mobile/modules/<module>", methods=["GET"])
def operator_mobile_module(module: str):
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    allowed_modules = {"cards", "content", "services", "finance", "analytics", "partnerships", "agents", "settings", "diagnostics"}
    if module not in allowed_modules or module in {"today", "tasks", "reviews", "operator"}:
        return jsonify({"success": False, "error": "Раздел пока недоступен"}), 404
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        scope = _resolve_mobile_scope(cursor, user_data)
        if not scope:
            return jsonify({"success": False, "error": "Раздел недоступен"}), 403
        if module == "settings":
            user_id = str(user_data.get("user_id") or user_data.get("id") or "")
            preferences = load_control_preferences(cursor, user_id)
            notifications = preferences.get("notification_preferences_json") if isinstance(preferences, dict) else {}
            preference_key = f"{scope.get('kind')}:{scope.get('id') or 'all'}"
            return jsonify({
                "success": True,
                "status": "available",
                "scope": scope,
                "items": [{"id": "notifications", "kind": "settings", "title": "Уведомления", "subtitle": "Настройки для выбранного масштаба", "status": "active"}],
                "counts": {"total": 1},
                "cursor": None,
                "as_of": datetime.now(timezone.utc).isoformat(),
                "freshness": {"status": "live"},
                "data_warnings": [],
                "available_actions": [{"key": "notifications.update", "label": "Сохранить"}],
                "filters": {},
                "preferences": (notifications or {}).get(preference_key, {}),
            })
        if module == "diagnostics" and scope.get("kind") != "platform":
            return jsonify({"success": False, "error": "Раздел недоступен"}), 403
        result = list_operator_mobile_module(cursor, module=module, scope=scope)
        if module == "content" and scope.get("kind") == "business" and scope.get("id"):
            filters = result.get("filters") if isinstance(result.get("filters"), dict) else {}
            filters["period_days"] = get_allowed_content_plan_horizons(str(scope.get("id")))
            filters["density"] = ["light", "standard", "active"]
            result["filters"] = filters
        return jsonify({"success": True, **result})
    finally:
        db.close()


def _mobile_scope_allows_business(scope: dict, business_id: str) -> bool:
    if scope.get("kind") == "platform":
        return True
    return business_id in {str(item) for item in scope.get("business_ids") or []}


def _mobile_business_from_payload(cursor, user_data: dict, payload: dict) -> tuple[dict | None, str, tuple | None]:
    user_id = str(user_data.get("user_id") or user_data.get("id") or "")
    kind, scope_id = _scope_request_values(payload)
    scope = resolve_control_scope(cursor, user_id=user_id, requested_kind=kind, requested_id=scope_id)
    business_id = str(payload.get("business_id") or (scope or {}).get("id") or "").strip()
    if not scope:
        return None, business_id, (jsonify({"success": False, "error": "Раздел недоступен"}), 403)
    if scope.get("kind") != "business" and not payload.get("business_id"):
        return scope, "", (jsonify({"success": False, "error": "Сначала выберите точку"}), 400)
    if not business_id or not _mobile_scope_allows_business(scope, business_id):
        return scope, business_id, (jsonify({"success": False, "error": "Точка недоступна"}), 403)
    has_access, _owner_id = verify_business_access(cursor, business_id, user_data)
    if not has_access:
        return scope, business_id, (jsonify({"success": False, "error": "Точка недоступна"}), 403)
    return scope, business_id, None


@operator_bp.route("/mobile/cards/schedule", methods=["PUT"])
def operator_mobile_card_schedule_update():
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    payload = request.get_json(silent=True) or {}
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        scope, business_id, error_response = _mobile_business_from_payload(cursor, user_data, payload)
        if error_response:
            return error_response
        current = get_card_automation_snapshot(db.conn, business_id).get("settings") or {}
        merged = dict(current)
        merged.update({
            "review_sync_enabled": bool(payload.get("enabled")),
            "review_sync_interval_hours": int(payload.get("interval_hours") or 24),
            "review_sync_schedule_mode": "interval",
            "review_sync_schedule_days": [],
            "review_sync_schedule_time": None,
        })
        snapshot = save_card_automation_settings(
            db.conn,
            business_id,
            str(user_data.get("user_id") or user_data.get("id") or ""),
            merged,
        )
        return jsonify({
            "success": True,
            "scope": scope,
            **snapshot,
            "cost_per_run_credits": DEFAULT_MAP_REFRESH_ESTIMATED_CREDITS,
        })
    except (TypeError, ValueError):
        db.conn.rollback()
        return jsonify({"success": False, "error": "Выберите корректный интервал"}), 400
    finally:
        db.close()


@operator_bp.route("/mobile/content/plans/generate", methods=["POST"])
def operator_mobile_content_plan_generate():
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    payload = request.get_json(silent=True) or {}
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        scope, business_id, error_response = _mobile_business_from_payload(cursor, user_data, payload)
        if error_response:
            return error_response
    finally:
        db.close()
    try:
        plan = create_generated_content_plan(
            str(user_data.get("user_id") or user_data.get("id") or ""),
            business_id,
            scope_type="single_business",
            scope_target_id=business_id,
            period_days=int(payload.get("period_days") or 30),
            density=str(payload.get("density") or "standard"),
            content_mix=payload.get("content_mix") if isinstance(payload.get("content_mix"), dict) else {},
        )
        return jsonify({"success": True, "scope": scope, "plan": plan})
    except (PermissionError, ValueError):
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 400


@operator_bp.route("/mobile/content/plans/<plan_id>", methods=["DELETE"])
def operator_mobile_content_plan_delete(plan_id: str):
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    payload = request.get_json(silent=True) or {}
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        scope, business_id, error_response = _mobile_business_from_payload(cursor, user_data, payload)
        if error_response:
            return error_response
        cursor.execute("SELECT business_id FROM contentplans WHERE id = %s", (plan_id,))
        plan_row = cursor.fetchone()
        plan_business_id = str(dict(plan_row or {}).get("business_id") or "")
        if not plan_row or plan_business_id != business_id:
            return jsonify({"success": False, "error": "Контент-план не найден в выбранном бизнесе"}), 404
    finally:
        db.close()
    try:
        delete_content_plan(str(user_data.get("user_id") or user_data.get("id") or ""), plan_id)
        return jsonify({"success": True, "scope": scope, "deleted_plan_id": plan_id})
    except PermissionError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 403
    except ValueError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 404


@operator_bp.route("/mobile/services/analyze", methods=["POST"])
def operator_mobile_services_analyze():
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    payload = request.get_json(silent=True) or {}
    mode = str(payload.get("mode") or "optimize").strip()
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        scope, business_id, error_response = _mobile_business_from_payload(cursor, user_data, payload)
        if error_response:
            return error_response
        cursor.execute(
            "SELECT id, name, description, category, price FROM userservices WHERE business_id = %s AND COALESCE(is_active, TRUE) ORDER BY category, name LIMIT 100",
            (business_id,),
        )
        services = [dict(item) for item in cursor.fetchall() or []]
        if not services:
            return jsonify({"success": False, "error": "Сначала добавьте услуги"}), 400
        service_ids = [str(item.get("id") or "") for item in services]
        user_id = str(user_data.get("user_id") or user_data.get("id") or "")
        action_id = str(payload.get("action_id") or "").strip()
        action = {}
        if bool(payload.get("confirmed")):
            cursor.execute("SELECT * FROM operatoractions WHERE id = %s AND user_id = %s FOR UPDATE", (action_id, user_id))
            action = dict(cursor.fetchone() or {})
            if not action or str(action.get("capability") or "") != f"services.{mode}":
                return jsonify({"success": False, "error": "Проверка устарела. Подготовьте её заново."}), 400
            if str(action.get("status") or "") == "completed":
                stored_result = action.get("result_json") if isinstance(action.get("result_json"), dict) else json.loads(str(action.get("result_json") or "{}"))
                return jsonify({"success": True, "scope": scope, "mode": mode, "result": stored_result, "idempotent": True})
            if action.get("expires_at") and action.get("expires_at") < datetime.now(timezone.utc):
                return jsonify({"success": False, "error": "Проверка устарела. Подготовьте её заново."}), 400
            envelope = action.get("envelope_json") if isinstance(action.get("envelope_json"), dict) else json.loads(str(action.get("envelope_json") or "{}"))
            if str(envelope.get("business_id") or "") != business_id or envelope.get("service_ids") != service_ids:
                return jsonify({"success": False, "error": "Список услуг изменился. Проверьте действие заново."}), 409

        def store_service_preview(preview_payload: dict) -> str:
            preview_action_id = str(uuid.uuid4())
            idempotency_key = f"mobile:{user_id}:services.{mode}:{preview_action_id}"
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
            cursor.execute(
                """
                INSERT INTO operatoractions (
                    id, conversation_id, business_id, user_id, capability, idempotency_key,
                    envelope_json, scope_type, scope_id, target_business_ids_json, preview_json,
                    estimated_credits, external_effects, is_mass_action, expires_at
                ) VALUES (%s, NULL, %s, %s, %s, %s, %s::jsonb, %s, %s, %s::jsonb, %s::jsonb, %s, FALSE, TRUE, %s)
                ON CONFLICT (user_id, idempotency_key)
                DO UPDATE SET preview_json = EXCLUDED.preview_json, envelope_json = EXCLUDED.envelope_json,
                              expires_at = EXCLUDED.expires_at, updated_at = NOW()
                RETURNING id
                """,
                (
                    preview_action_id,
                    business_id,
                    user_id,
                    f"services.{mode}",
                    idempotency_key,
                    json.dumps({"business_id": business_id, "service_ids": service_ids}, ensure_ascii=False),
                    str(scope.get("kind") or "business"),
                    str(scope.get("id") or "") or None,
                    json.dumps([business_id]),
                    json.dumps(preview_payload, ensure_ascii=False, default=str),
                    int(preview_payload.get("estimated_credits") or 0),
                    expires_at,
                ),
            )
            stored_id = str(dict(cursor.fetchone() or {}).get("id") or preview_action_id)
            db.conn.commit()
            return stored_id

        def complete_service_action(result_payload: dict) -> None:
            cursor.execute(
                """
                UPDATE operatoractions SET status = 'completed', confirmed_at = COALESCE(confirmed_at, NOW()),
                    executed_at = COALESCE(executed_at, NOW()), result_json = %s::jsonb, updated_at = NOW()
                WHERE id = %s AND user_id = %s
                """,
                (json.dumps(result_payload, ensure_ascii=False, default=str), action_id, user_id),
            )
        if mode == "compress":
            analysis = build_service_catalog_compression_draft(services)
            if bool(payload.get("confirmed")):
                created_service_ids = []
                archived_service_ids = []
                for group in analysis.get("groups") or []:
                    if str(group.get("action") or "") not in {"apply", "promotion"}:
                        continue
                    source_ids = [str(item) for item in group.get("source_service_ids") or [] if str(item)]
                    if not source_ids:
                        continue
                    cursor.execute(
                        "SELECT id FROM userservices WHERE business_id = %s AND id = ANY(%s) AND COALESCE(is_active, TRUE)",
                        (business_id, source_ids),
                    )
                    found_ids = [str(dict(item).get("id") or "") for item in cursor.fetchall() or []]
                    if not found_ids:
                        continue
                    if str(group.get("action") or "") == "apply":
                        target = group.get("target") if isinstance(group.get("target"), dict) else {}
                        created_id = str(uuid.uuid4())
                        cursor.execute(
                            """
                            INSERT INTO userservices (
                                id, user_id, business_id, category, name, description,
                                keywords, price, is_active, created_at, updated_at
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE, NOW(), NOW())
                            """,
                            (
                                created_id,
                                str(user_data.get("user_id") or user_data.get("id") or ""),
                                business_id,
                                str(target.get("category") or "Общие услуги"),
                                str(target.get("name") or group.get("title") or "Объединённая услуга"),
                                str(target.get("description") or ""),
                                json.dumps(target.get("keywords") or [], ensure_ascii=False),
                                str(target.get("price") or ""),
                            ),
                        )
                        created_service_ids.append(created_id)
                    cursor.execute(
                        "UPDATE userservices SET is_active = FALSE, updated_at = NOW() WHERE business_id = %s AND id = ANY(%s)",
                        (business_id, found_ids),
                    )
                    archived_service_ids.extend(found_ids)
                result_payload = {
                    "status": "completed",
                    "created_count": len(created_service_ids),
                    "archived_count": len(set(archived_service_ids)),
                    "provider_write_performed": False,
                }
                complete_service_action(result_payload)
                db.conn.commit()
                return jsonify({
                    "success": True,
                    "scope": scope,
                    "mode": mode,
                    "result": result_payload,
                })
            preview_payload = {"mode": mode, "analysis": analysis, "confirmation_required": True, "estimated_credits": 0}
            return jsonify({"success": True, "scope": scope, **preview_payload, "action_id": store_service_preview(preview_payload)})
        if bool(payload.get("confirmed")):
            result = optimize_services_from_operator(
                cursor,
                business_id=business_id,
                user_id=str(user_data.get("user_id") or user_data.get("id") or ""),
                limit=len(services),
                channel="telegram_mini_app",
            )
            if str(result.get("status") or "") != "completed":
                db.conn.rollback()
                return jsonify({"success": False, "error": result.get("chat_response") or "Не удалось улучшить услуги", "result": result}), 400
            complete_service_action(result)
            db.conn.commit()
            return jsonify({"success": True, "scope": scope, "mode": "optimize", "result": result})
        preview_payload = {
            "success": True,
            "scope": scope,
            "mode": "optimize",
            "service_count": len(services),
            "estimated_credits": len(services) * SERVICES_OPTIMIZE_CREDITS_PER_SERVICE,
            "confirmation_required": True,
            "changes": [{"id": item.get("id"), "name": item.get("name")} for item in services],
        }
        preview_payload["action_id"] = store_service_preview(preview_payload)
        return jsonify(preview_payload)
    finally:
        db.close()


def _operator_json_object(value: object) -> dict:
    text = str(value or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            try:
                parsed = json.loads(text[start:end + 1])
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                return {}
    return {}


def _normalize_finance_transaction_date(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return datetime.now(timezone.utc).date().isoformat()
    for date_format in ("%d.%m", "%d/%m", "%d-%m"):
        try:
            parsed = datetime.strptime(text, date_format).date()
            return parsed.replace(year=datetime.now(timezone.utc).year).isoformat()
        except ValueError:
            continue
    for date_format in ("%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, date_format).date().isoformat()
        except ValueError:
            continue
    return text


@operator_bp.route("/mobile/finance/recognize", methods=["POST"])
def operator_mobile_finance_recognize():
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    payload = request.form.to_dict() if request.files else (request.get_json(silent=True) or {})
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        scope, business_id, error_response = _mobile_business_from_payload(cursor, user_data, payload)
        if error_response:
            return error_response
    finally:
        db.close()
    today = datetime.now(timezone.utc).date()
    prompt = f"""Извлеки продажи из данных. Для каждой строки определи sale_type: service — основная услуга, upsell — допродажа к основной услуге, cross_sell — отдельный товар или кросс-продажа. Сегодня {today.isoformat()}. Если в дате не указан год, используй {today.year}. Не превращай день месяца в год. Верни только JSON: {{\"transactions\":[{{\"transaction_date\":\"YYYY-MM-DD\",\"amount\":0,\"title\":\"название\",\"sale_type\":\"service|upsell|cross_sell\",\"notes\":\"\"}}]}}"""
    uploaded = request.files.get("file") or request.files.get("photo")
    try:
        if uploaded and str(uploaded.mimetype or "").startswith("image/"):
            raw_result = analyze_screenshot_with_gigachat(
                base64.b64encode(uploaded.read()).decode("utf-8"),
                prompt,
                task_type="finance_sales_recognition",
                business_id=business_id,
                user_id=str(user_data.get("user_id") or user_data.get("id") or ""),
            )
        else:
            source_text = str(payload.get("text") or "").strip()
            if uploaded:
                source, extraction_error = build_agent_source_from_upload(uploaded)
                if extraction_error:
                    return jsonify({"success": False, "error": extraction_error.get("message") or "Не удалось прочитать документ"}), 400
                source_text = str(source.get("content_text") or "").strip()
            if not source_text:
                return jsonify({"success": False, "error": "Добавьте текст, фото или документ с продажами"}), 400
            raw_result = analyze_text_with_gigachat(
                f"{prompt}\n\nДанные:\n{source_text}",
                task_type="finance_sales_recognition",
                business_id=business_id,
                user_id=str(user_data.get("user_id") or user_data.get("id") or ""),
            )
        recognized = _operator_json_object(raw_result)
        transactions = recognized.get("transactions") if isinstance(recognized.get("transactions"), list) else []
        transactions = [
            {
                **item,
                "transaction_date": _normalize_finance_transaction_date(item.get("transaction_date")),
            }
            for item in transactions
            if isinstance(item, dict)
        ]
        return jsonify({"success": True, "scope": scope, "business_id": business_id, "transactions": transactions, "confirmation_required": True})
    except Exception:
        return jsonify({"success": False, "error": f"Не удалось распознать продажи: {sys.exc_info()[1]}"}), 400


@operator_bp.route("/mobile/services/<service_id>", methods=["PUT"])
def operator_mobile_service_update(service_id: str):
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    payload = request.get_json(silent=True) or {}
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        scope = _resolve_mobile_scope(cursor, user_data)
        cursor.execute("SELECT business_id FROM userservices WHERE id = %s", (service_id,))
        row = cursor.fetchone()
        business_id = str((dict(row) if row else {}).get("business_id") or "")
        if not business_id:
            return jsonify({"success": False, "error": "Услуга не найдена"}), 404
        if not scope or not _mobile_scope_allows_business(scope, business_id):
            return jsonify({"success": False, "error": "Услуга недоступна"}), 403
        updates = []
        params = []
        for field in ("name", "description", "price", "category"):
            if field not in payload:
                continue
            value = str(payload.get(field) or "").strip()
            if field == "name" and not value:
                return jsonify({"success": False, "error": "Название не может быть пустым"}), 400
            updates.append(f"{field} = %s")
            params.append(value)
        if not updates:
            return jsonify({"success": False, "error": "Нет изменений"}), 400
        params.extend([service_id, business_id])
        cursor.execute(
            f"""
            UPDATE userservices
            SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND business_id = %s
            RETURNING id, business_id, name AS title, description AS subtitle,
                      price, category, updated_at,
                      CASE WHEN COALESCE(is_active, TRUE) THEN 'active' ELSE 'archived' END AS status
            """,
            tuple(params),
        )
        updated = dict(cursor.fetchone() or {})
        db.conn.commit()
        return jsonify({"success": True, "scope": scope, "item": updated})
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


def _mobile_content_item_scope(cursor, user_data: dict, item_id: str):
    scope = _resolve_mobile_scope(cursor, user_data)
    cursor.execute("SELECT business_id FROM contentplanitems WHERE id = %s", (item_id,))
    row = cursor.fetchone()
    business_id = str((dict(row) if row else {}).get("business_id") or "")
    if not business_id:
        return scope, business_id, (jsonify({"success": False, "error": "Элемент плана не найден"}), 404)
    if not scope or not _mobile_scope_allows_business(scope, business_id):
        return scope, business_id, (jsonify({"success": False, "error": "Элемент плана недоступен"}), 403)
    return scope, business_id, None


@operator_bp.route("/mobile/content/items/<item_id>", methods=["PUT"])
def operator_mobile_content_item_update(item_id: str):
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    payload = request.get_json(silent=True) or {}
    allowed_payload = {
        key: payload.get(key)
        for key in ("theme", "goal", "draft_text", "scheduled_for")
        if key in payload
    }
    if not allowed_payload:
        return jsonify({"success": False, "error": "Нет изменений"}), 400
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        scope, _business_id, error_response = _mobile_content_item_scope(cursor, user_data, item_id)
        if error_response:
            return error_response
    finally:
        db.close()
    try:
        plan = update_content_plan_item(str(user_data.get("user_id") or user_data.get("id") or ""), item_id, allowed_payload)
        return jsonify({"success": True, "scope": scope, "plan": plan})
    except PermissionError as exc:
        return jsonify({"success": False, "error": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@operator_bp.route("/mobile/content/items/<item_id>/generate-draft", methods=["POST"])
def operator_mobile_content_item_generate_draft(item_id: str):
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        scope, _business_id, error_response = _mobile_content_item_scope(cursor, user_data, item_id)
        if error_response:
            return error_response
    finally:
        db.close()
    try:
        result = generate_draft_for_plan_item(str(user_data.get("user_id") or user_data.get("id") or ""), item_id)
        return jsonify({"success": True, "scope": scope, **result})
    except PermissionError as exc:
        return jsonify({"success": False, "error": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@operator_bp.route("/mobile/settings/notifications", methods=["PUT"])
def operator_mobile_notification_settings_update():
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    payload = request.get_json(silent=True) or {}
    notifications = payload.get("notifications") if isinstance(payload.get("notifications"), dict) else None
    if notifications is None:
        return jsonify({"success": False, "error": "Настройки не переданы"}), 400
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        scope = _resolve_mobile_scope(cursor, user_data)
        if not scope:
            return jsonify({"success": False, "error": "Раздел недоступен"}), 403
        user_id = str(user_data.get("user_id") or user_data.get("id") or "")
        saved = save_scope_notification_preferences(
            cursor,
            user_id=user_id,
            telegram_id=str(user_data.get("telegram_id") or ""),
            scope=scope,
            notifications=notifications,
        )
        db.conn.commit()
        return jsonify({"success": True, "scope": scope, "preferences": saved})
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


@operator_bp.route("/mobile/reviews", methods=["GET"])
def operator_mobile_reviews():
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        scope = _resolve_mobile_scope(cursor, user_data)
        if not scope:
            return jsonify({"success": False, "error": "Раздел недоступен"}), 403
        status = str(request.args.get("status") or "unanswered").strip().lower()
        source = str(request.args.get("source") or "").strip().lower()
        location_id = str(request.args.get("location_id") or "").strip()
        review_id = str(request.args.get("review_id") or "").strip()
        rating = str(request.args.get("rating") or "").strip()
        try:
            limit = max(1, min(int(request.args.get("limit") or 20), 50))
            offset = max(0, int(request.args.get("cursor") or 0))
        except ValueError:
            return jsonify({"success": False, "error": "Некорректная пагинация"}), 400
        conditions = ["COALESCE(TRIM(r.text), '') <> ''"]
        params: list = []
        business_ids = [str(item) for item in scope.get("business_ids") or [] if str(item)]
        if scope.get("kind") != "platform":
            conditions.append("r.business_id = ANY(%s)")
            params.append(business_ids)
        if location_id:
            if scope.get("kind") != "platform" and location_id not in business_ids:
                return jsonify({"success": False, "error": "Точка недоступна"}), 403
            conditions.append("r.business_id = %s")
            params.append(location_id)
        if source:
            conditions.append("LOWER(r.source) = %s")
            params.append(source)
        if rating:
            try:
                rating_value = max(1, min(int(rating), 5))
            except ValueError:
                return jsonify({"success": False, "error": "Некорректный рейтинг"}), 400
            conditions.append("r.rating = %s")
            params.append(rating_value)
        base_where_sql = " AND ".join(conditions)
        cursor.execute(
            f"""
            {CANONICAL_REVIEWS_CTE}
            SELECT COUNT(DISTINCT r.id) AS total,
                   COUNT(DISTINCT r.id) FILTER (WHERE COALESCE(TRIM(r.response_text), '') = '') AS unanswered,
                   COUNT(DISTINCT r.id) FILTER (WHERE d.id IS NOT NULL AND d.status IN ('draft','generated','pending_review','edited')) AS drafts
            FROM canonical_reviews r
            LEFT JOIN reviewreplydrafts d ON d.review_id = r.id
            WHERE {base_where_sql}
            """,
            tuple(params),
        )
        counts = dict(cursor.fetchone() or {})
        list_conditions = list(conditions)
        if review_id:
            list_conditions.append("r.id = %s")
            params.append(review_id)
        if status == "unanswered":
            list_conditions.append("COALESCE(TRIM(r.response_text), '') = ''")
        elif status == "drafts":
            list_conditions.append("d.id IS NOT NULL AND d.status IN ('draft','generated','pending_review','edited')")
        elif status == "answered":
            list_conditions.append("COALESCE(TRIM(r.response_text), '') <> ''")
        where_sql = " AND ".join(list_conditions)
        cursor.execute(
            f"""
            {CANONICAL_REVIEWS_CTE}
            SELECT COUNT(DISTINCT r.id) AS total
            FROM canonical_reviews r
            LEFT JOIN reviewreplydrafts d ON d.review_id = r.id
            WHERE {where_sql}
            """,
            tuple(params),
        )
        filtered_total = int(dict(cursor.fetchone() or {}).get("total") or 0)
        cursor.execute(
            f"""
            {CANONICAL_REVIEWS_CTE}
            SELECT r.id, r.business_id, r.source, r.rating, r.author_name, r.text,
                   r.response_text, r.response_at, COALESCE(r.published_at, r.created_at) AS published_at,
                   r.created_at AS loaded_at, r.updated_at, b.name AS location_name,
                   d.id AS reply_draft_id, d.generated_text AS reply_draft_text,
                   d.status AS reply_draft_status, d.updated_at AS reply_draft_updated_at
            FROM canonical_reviews r
            LEFT JOIN businesses b ON b.id = r.business_id
            LEFT JOIN LATERAL (
                SELECT id, COALESCE(edited_text, generated_text) AS generated_text, status, updated_at FROM reviewreplydrafts
                WHERE review_id = r.id ORDER BY updated_at DESC LIMIT 1
            ) d ON TRUE
            WHERE {where_sql}
            ORDER BY COALESCE(r.published_at, r.created_at) DESC
            LIMIT %s OFFSET %s
            """,
            tuple([*params, limit, offset]),
        )
        items = [dict(row) for row in cursor.fetchall() or []]
        total = int(counts.get("total") or 0)
        cursor.execute(
            """
            SELECT DISTINCT r.source FROM externalbusinessreviews r
            WHERE (%s OR r.business_id = ANY(%s)) AND COALESCE(TRIM(r.source), '') <> ''
            ORDER BY r.source
            """,
            (scope.get("kind") == "platform", business_ids),
        )
        sources = [str(dict(row).get("source") or "") for row in (cursor.fetchall() or [])]
        cursor.execute(
            """
            SELECT id, name FROM businesses
            WHERE (%s OR id = ANY(%s))
            ORDER BY name
            LIMIT 200
            """,
            (scope.get("kind") == "platform", business_ids),
        )
        locations = [dict(row) for row in (cursor.fetchall() or [])]
        return jsonify({
            "success": True,
            "scope": scope,
            "items": items,
            "counts": {"total": total, "unanswered": int(counts.get("unanswered") or 0), "drafts": int(counts.get("drafts") or 0)},
            "cursor": str(offset + limit) if offset + len(items) < filtered_total else None,
            "as_of": datetime.now(timezone.utc).isoformat(),
            "data_warnings": [],
            "available_actions": [{"key": "generate", "label": "Подготовить ответы"}],
            "filters": {"statuses": ["unanswered", "drafts", "answered", "all"], "sources": sources, "ratings": [1, 2, 3, 4, 5], "locations": locations},
        })
    finally:
        db.close()


@operator_bp.route("/mobile/actions/preview", methods=["POST"])
def operator_mobile_action_preview():
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    payload = request.get_json(silent=True) or {}
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        user_id = str(user_data.get("user_id") or user_data.get("id") or "")
        scope = resolve_control_scope(cursor, user_id=user_id, requested_kind=str(payload.get("scope_type") or ""), requested_id=str(payload.get("scope_id") or "") or None)
        if not scope:
            return jsonify({"success": False, "error": "Раздел недоступен"}), 403
        capability = str(payload.get("capability") or payload.get("action_key") or "").strip()
        input_payload = payload.get("input") if isinstance(payload.get("input"), dict) else payload
        preview = create_mobile_action_preview(
            cursor,
            user_id=user_id,
            scope=scope,
            capability=capability,
            input_payload=input_payload,
        )
        if preview.get("status") == "blocked":
            return jsonify({"success": False, "error": "Действие недоступно", "preview": preview}), 400
        db.conn.commit()
        return jsonify({"success": True, "preview": preview})
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


@operator_bp.route("/mobile/actions/<action_id>/confirm", methods=["POST"])
def operator_mobile_action_confirm(action_id: str):
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    user_id = str(user_data.get("user_id") or user_data.get("id") or "")
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        def scope_resolver(kind: str, scope_id: str | None):
            return resolve_control_scope(cursor, user_id=user_id, requested_kind=kind, requested_id=scope_id)

        def generate_executor(envelope: dict, targets: list[str], _scope: dict):
            review_ids = [str(item) for item in envelope.get("review_ids") or []]
            drafts: list[dict] = []
            charged_credits = 0
            blocked_reasons: list[str] = []
            for business_id in targets:
                cursor.execute(
                    "SELECT id FROM externalbusinessreviews WHERE business_id = %s AND id = ANY(%s)",
                    (business_id, review_ids),
                )
                scoped_review_ids = [str(dict(item).get("id") or "") for item in (cursor.fetchall() or [])]
                if not scoped_review_ids:
                    continue
                generated = generate_review_reply_drafts_for_unanswered_reviews(
                    cursor,
                    business_id=business_id,
                    user_id=user_id,
                    limit=len(scoped_review_ids),
                    review_ids=scoped_review_ids,
                    channel="telegram_mini_app",
                )
                if str(generated.get("status") or "") != "completed":
                    blocked_reasons.extend(str(item) for item in generated.get("blocked_reasons") or ["generation_failed"])
                drafts.extend(generated.get("drafts") or [])
                charged_credits += int(generated.get("charged_credits") or 0)
            if blocked_reasons:
                return {"status": "blocked", "blocked_reasons": list(dict.fromkeys(blocked_reasons))}
            return {
                "status": "completed",
                "capability": "review_replies.generate",
                "drafts": drafts,
                "charged_credits": charged_credits,
                "manual_publication_only": True,
                "external_writes_performed": False,
            }

        def finance_sales_executor(envelope: dict, targets: list[str], _scope: dict):
            business_id = str(envelope.get("business_id") or "")
            transactions = envelope.get("transactions") if isinstance(envelope.get("transactions"), list) else []
            if len(targets) != 1 or business_id != targets[0] or not transactions:
                return {"status": "blocked", "blocked_reasons": ["finance_preview_changed"]}
            cursor.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'financialtransactions'"
            )
            columns = {str(dict(item).get("column_name") or "") for item in cursor.fetchall() or []}
            created = []
            for item in transactions:
                transaction_id = str(uuid.uuid4())
                sale_type = str(item.get("sale_type") or "service")
                title = str(item.get("title") or "Продажа")
                notes = str(item.get("notes") or "")
                description = f"{title} · {sale_type}" + (f" · {notes}" if notes else "")
                fields = ["id", "business_id", "amount"]
                values = [transaction_id, business_id, item.get("amount")]
                if "user_id" in columns:
                    fields.append("user_id")
                    values.append(user_id)
                if "transaction_date" in columns:
                    fields.append("transaction_date")
                    values.append(str(item.get("transaction_date") or datetime.now(timezone.utc).date().isoformat()))
                if "transaction_type" in columns:
                    fields.append("transaction_type")
                    values.append("income")
                if "description" in columns:
                    fields.append("description")
                    values.append(description)
                if "client_type" in columns:
                    fields.append("client_type")
                    values.append("returning")
                if "services" in columns:
                    fields.append("services")
                    values.append(json.dumps([{"name": title, "sale_type": sale_type}], ensure_ascii=False))
                if "notes" in columns:
                    fields.append("notes")
                    values.append(description)
                placeholders = ", ".join(["%s"] * len(fields))
                cursor.execute(
                    f"INSERT INTO financialtransactions ({', '.join(fields)}) VALUES ({placeholders})",
                    tuple(values),
                )
                created.append({"id": transaction_id, **item})
            return {
                "status": "completed",
                "capability": "finance.sales_import",
                "transactions": created,
                "created_count": len(created),
                "external_writes_performed": False,
            }

        result, idempotent = confirm_mobile_action(
            cursor,
            action_id=action_id,
            user_id=user_id,
            scope_resolver=scope_resolver,
            executors={
                "review_replies.generate": generate_executor,
                "finance.sales_import": finance_sales_executor,
            },
        )
        if result.get("status") == "blocked":
            db.conn.rollback()
            return jsonify({"success": False, "error": "Действие не выполнено", "operator_result": result}), 400
        db.conn.commit()
        return jsonify({"success": True, "idempotent": idempotent, "operator_result": result})
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


@operator_bp.route("/mobile/review-drafts/<draft_id>", methods=["PUT"])
def operator_mobile_review_draft_update(draft_id: str):
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    payload = request.get_json(silent=True) or {}
    reply_text = str(payload.get("reply_text") or "").strip()
    if not reply_text:
        return jsonify({"success": False, "error": "Текст ответа не может быть пустым"}), 400
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        user_id = str(user_data.get("user_id") or user_data.get("id") or "")
        scope = resolve_control_scope(
            cursor,
            user_id=user_id,
            requested_kind=str(payload.get("scope_type") or ""),
            requested_id=str(payload.get("scope_id") or "") or None,
        )
        cursor.execute("SELECT business_id FROM reviewreplydrafts WHERE id = %s", (draft_id,))
        row = cursor.fetchone()
        business_id = str((dict(row) if row else {}).get("business_id") or "")
        if not scope or (scope.get("kind") != "platform" and business_id not in [str(item) for item in scope.get("business_ids") or []]):
            return jsonify({"success": False, "error": "Черновик недоступен"}), 403
        has_access, owner_id = verify_business_access(cursor, business_id, user_data)
        if not has_access:
            return jsonify({"success": False, "error": "Нет доступа" if owner_id else "Черновик не найден"}), 403 if owner_id else 404
        cursor.execute(
            """
            UPDATE reviewreplydrafts
            SET edited_text = %s, status = 'edited', updated_at = NOW()
            WHERE id = %s AND business_id = %s
            RETURNING id, review_id, edited_text, status, updated_at
            """,
            (reply_text, draft_id, business_id),
        )
        updated = dict(cursor.fetchone() or {})
        db.conn.commit()
        return jsonify({"success": True, "draft": updated})
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


@operator_bp.route("/mobile/review-drafts/<draft_id>/mark-manual-published", methods=["POST"])
def operator_mobile_review_draft_manual_publish(draft_id: str):
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    payload = request.get_json(silent=True) or {}
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        user_id = str(user_data.get("user_id") or user_data.get("id") or "")
        scope = resolve_control_scope(
            cursor,
            user_id=user_id,
            requested_kind=str(payload.get("scope_type") or ""),
            requested_id=str(payload.get("scope_id") or "") or None,
        )
        cursor.execute("SELECT business_id FROM reviewreplydrafts WHERE id = %s", (draft_id,))
        row = cursor.fetchone()
        business_id = str((dict(row) if row else {}).get("business_id") or "")
        if not scope or (scope.get("kind") != "platform" and business_id not in [str(item) for item in scope.get("business_ids") or []]):
            return jsonify({"success": False, "error": "Черновик недоступен"}), 403
        has_access, _owner_id = verify_business_access(cursor, business_id, user_data)
        if not has_access:
            return jsonify({"success": False, "error": "Черновик недоступен"}), 403
        result = mark_review_reply_draft_manual_published(
            cursor,
            business_id=business_id,
            user_id=user_id,
            draft_id=draft_id,
        )
        if result.get("status") != "completed":
            db.conn.rollback()
            return jsonify({"success": False, "error": "Не удалось отметить публикацию", "manual_publish": result}), 400
        db.conn.commit()
        return jsonify({"success": True, "manual_publish": result})
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


@operator_bp.route("/mobile/operator/history", methods=["GET"])
def operator_mobile_history():
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        scope = _resolve_mobile_scope(cursor, user_data)
        if not scope:
            return jsonify({"success": False, "error": "Раздел недоступен"}), 403
        if scope.get("kind") != "business":
            return jsonify({"success": True, "scope": scope, "conversation": None, "items": [], "requires_business_selection": True})
        user_id = str(user_data.get("user_id") or user_data.get("id") or "")
        business_id = str(scope.get("id") or "")
        conversation = find_latest_operator_conversation(
            cursor,
            business_id=business_id,
            user_id=user_id,
            channel="telegram_mini_app",
        )
        conversation_id = str(conversation.get("id") or "")
        items = list_operator_messages(
            cursor,
            conversation_id=conversation_id,
            business_id=business_id,
            limit=request.args.get("limit") or 100,
        ) if conversation_id else []
        return jsonify({
            "success": True,
            "scope": scope,
            "conversation": conversation or None,
            "items": items,
            "counts": {"total": len(items)},
            "cursor": None,
            "as_of": datetime.now(timezone.utc).isoformat(),
            "freshness": {"status": "live"},
            "data_warnings": [],
            "available_actions": [{"key": "send_message", "label": "Поручить LocalOS"}],
        })
    finally:
        db.close()


@operator_bp.route("/mobile/reviews/<review_id>/generate", methods=["POST"])
def operator_mobile_review_reply_generate(review_id: str):
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    payload = request.get_json(silent=True) or {}
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        user_id = str(user_data.get("user_id") or user_data.get("id") or "")
        scope = resolve_control_scope(
            cursor,
            user_id=user_id,
            requested_kind=str(payload.get("scope_type") or ""),
            requested_id=str(payload.get("scope_id") or "") or None,
        )
        if not scope:
            return jsonify({"success": False, "error": "Раздел недоступен"}), 403
        cursor.execute("SELECT business_id FROM externalbusinessreviews WHERE id = %s", (review_id,))
        row = cursor.fetchone()
        business_id = str((dict(row) if row else {}).get("business_id") or "")
        targets = [str(item) for item in scope.get("business_ids") or []]
        if scope.get("kind") != "platform" and business_id not in targets:
            return jsonify({"success": False, "error": "Отзыв недоступен"}), 403
        has_access, _owner_id = verify_business_access(cursor, business_id, user_data)
        if not has_access:
            return jsonify({"success": False, "error": "Отзыв недоступен"}), 403
        if not bool(payload.get("confirmed")):
            return jsonify({"success": True, "preview": {
                "action_key": "review_reply_generate",
                "scope": scope,
                "business_ids": [business_id],
                "changes": [{"review_id": review_id, "operation": "create_reply_draft"}],
                "estimated_credits": 1,
                "external_effects": False,
                "confirmation_required": True,
                "idempotency_key": f"mobile:{user_id}:review_reply_generate:{review_id}",
            }})
        result = generate_review_reply_drafts_for_unanswered_reviews(
            cursor,
            business_id=business_id,
            user_id=user_id,
            limit=1,
            review_id=review_id,
            channel="telegram_mini_app",
        )
        db.conn.commit()
        return jsonify({"success": str(result.get("status") or "") == "completed", "operator_result": result})
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


@operator_bp.route("/events", methods=["GET"])
def operator_events():
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401

    business_id = str(request.args.get("business_id") or "").strip()
    if not business_id:
        return jsonify({"success": False, "error": "business_id обязателен"}), 400

    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        has_access, owner_id = verify_business_access(cursor, business_id, user_data)
        if not has_access:
            status_code = 403 if owner_id else 404
            message = "Нет доступа" if owner_id else "Бизнес не найден"
            return jsonify({"success": False, "error": message}), status_code

        events = list_operator_events(cursor, business_id=business_id, limit=request.args.get("limit") or 20)
        return jsonify({"success": True, "events": events})
    except Exception:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500
    finally:
        db.close()
