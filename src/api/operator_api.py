from __future__ import annotations

import sys

from flask import Blueprint, jsonify, request

from core.auth_helpers import require_auth_from_request, verify_business_access
from database_manager import DatabaseManager
from services.operator_audit import list_operator_events, record_operator_event
from services.operator_consent_policy import list_consent_policies, upsert_consent_policy
from services.operator_attention import build_attention_brief
from services.operator_inbox import build_operator_inbox
from services.operator_manual_review import process_operator_chat_message
from services.operator_manual_publish import mark_review_reply_draft_manual_published
from services.operator_paid_executor import build_paid_action_execution_attempt
from services.operator_paid_preflight import build_paid_action_preflight
from services.operator_review_reply_bulk import classify_bulk_review_reply_intent, generate_review_reply_drafts_for_unanswered_reviews


operator_bp = Blueprint("operator_api", __name__, url_prefix="/api/operator")


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
        if classify_bulk_review_reply_intent(message):
            result = generate_review_reply_drafts_for_unanswered_reviews(
                cursor,
                business_id=business_id,
                user_id=user_id,
                limit=payload.get("limit") or 5,
                channel="web",
            )
        else:
            result = process_operator_chat_message(
                cursor,
                business_id=business_id,
                user_id=user_id,
                message=message,
                channel="web",
            )
        status = str(result.get("status") or "blocked")
        review = result.get("review") if isinstance(result.get("review"), dict) else {}
        draft = result.get("draft") if isinstance(result.get("draft"), dict) else {}
        drafts = result.get("drafts") if isinstance(result.get("drafts"), list) else []
        finalization = result.get("finalization_result") if isinstance(result.get("finalization_result"), dict) else {}
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
