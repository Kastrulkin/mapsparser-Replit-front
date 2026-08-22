"""Public event ingestion and tenant-scoped website analytics API."""

from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
import os
import re
import time
import threading
from urllib.parse import urlparse

from flask import Blueprint, jsonify, make_response, request

from core.auth_helpers import require_auth_from_request, verify_business_access
from database_manager import DatabaseManager
from services.web_tracking_service import (
    MAX_REQUEST_BYTES,
    WebTrackingConflictError,
    WebTrackingDeletionError,
    WebTrackingLimitError,
    delete_business_web_analytics,
    ensure_tracker,
    get_business_web_metrics,
    get_web_tracking_health,
    ingest_events,
    normalize_hostname,
    tracker_status,
    validate_batch,
    validate_tracker_domains,
)
from services.web_tracking_observability import get_ingestion_metrics, record_ingestion_metrics
from services.web_tracking_goals_service import (
    WebConversionAuthenticationError,
    WebTrackingConfigurationError,
    conversion_key_status,
    delete_annotation,
    delete_campaign_cost,
    delete_goal,
    delete_page_group,
    get_web_analytics_extensions,
    ingest_confirmed_conversion,
    list_annotations,
    list_campaign_costs,
    list_goals,
    list_page_groups,
    preview_page_group,
    resolve_conversion_tracker,
    rotate_conversion_key,
    save_annotation,
    save_campaign_cost,
    save_goal,
    save_page_group,
    save_system_annotation,
)


web_tracking_bp = Blueprint("web_tracking_api", __name__)
_rate_lock = threading.Lock()
_rate_windows = defaultdict(deque)


def _positive_int_env(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


_RATE_LIMIT = _positive_int_env("WEB_TRACKING_IN_PROCESS_RATE_LIMIT", 120)
_RATE_WINDOW = timedelta(minutes=1)
logger = logging.getLogger(__name__)


def _flag(name: str, default: bool = False) -> bool:
    fallback = "true" if default else "false"
    return os.getenv(name, fallback).strip().lower() in {"1", "true", "yes", "on"}


def _business_allowlisted(business_id: str) -> bool:
    configured = {
        item.strip() for item in os.getenv("WEB_TRACKING_BUSINESS_IDS", "").split(",") if item.strip()
    }
    return not configured or business_id in configured


def _web_configuration_unavailable(business_id: str) -> bool:
    return not _flag("WEB_TRACKING_ENABLED") or not _flag("WEB_TRACKING_ANALYTICS_ENABLED") or not _business_allowlisted(business_id)


def tracking_rate_limit_key() -> str:
    oversized = request.content_length and request.content_length > MAX_REQUEST_BYTES
    raw_prefix = b"oversized" if oversized else request.get_data(cache=True)[:2048]
    match = re.search(rb'"tracker_id"\s*:\s*"(pub_[A-Za-z0-9_-]{16,80})"', raw_prefix)
    tracker_value = match.group(1) if match else b"invalid-tracker"
    tracker_hash = hashlib.sha256(tracker_value).hexdigest()[:16]
    return f"{request.remote_addr or 'unknown'}:{tracker_hash}"


def _request_payload():
    payload = request.get_json(silent=True)
    if payload is not None:
        return payload
    try:
        return json.loads(request.get_data(cache=True).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
        return None


def _tracker_log_key(tracker_id: str) -> str:
    return hashlib.sha256(tracker_id.encode("utf-8")).hexdigest()[:16] if tracker_id else ""


def _ingestion_response(*, started_at: float, status: int, outcome: str, tracker_id: str = "", **fields):
    latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
    log_payload = {
        "event": "web_tracking_ingestion",
        "outcome": outcome,
        "status": status,
        "tracker_key": _tracker_log_key(tracker_id),
        "latency_ms": latency_ms,
        "request_bytes": int(request.content_length or 0),
        **fields,
    }
    record_ingestion_metrics(
        status=status,
        outcome=outcome,
        latency_ms=latency_ms,
        received=fields.get("received", 0),
        accepted=fields.get("accepted", 0),
        duplicates=fields.get("duplicates", 0),
    )
    log_method = logger.error if status >= 500 else logger.info
    log_method("%s", json.dumps(log_payload, ensure_ascii=True, sort_keys=True))
    body = {"success": status < 400, **fields}
    if status >= 400:
        body["error"] = outcome
    return _cors(jsonify(body)), status


def ingestion_rate_limited_response(started_at: float):
    """Use the same safe telemetry path when Flask-Limiter rejects before the view runs."""
    return _ingestion_response(started_at=started_at, status=429, outcome="rate_limited")


def _cors(response):
    origin = request.headers.get("Origin", "")
    if origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
    response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Max-Age"] = "86400"
    return response


def _rate_allowed(key: str) -> bool:
    now = datetime.now(timezone.utc)
    cutoff = now - _RATE_WINDOW
    with _rate_lock:
        window = _rate_windows[key]
        while window and window[0] < cutoff:
            window.popleft()
        if len(window) >= _RATE_LIMIT:
            return False
        window.append(now)
        return True


def _record_tracker_error(db, tracker: dict | None, error_code: str) -> None:
    if not tracker:
        return
    try:
        cursor = db.conn.cursor()
        cursor.execute(
            "UPDATE business_web_trackers SET last_error_code = %s, last_error_at = NOW() WHERE id = %s",
            (error_code[:120], tracker["id"]),
        )
        db.conn.commit()
    except Exception:
        db.conn.rollback()
        logger.warning("failed to persist web tracking error code", exc_info=True)


def _require_business(cursor, business_id: str):
    user_data = require_auth_from_request()
    if not user_data:
        return None, (jsonify({"success": False, "error": "Требуется авторизация"}), 401)
    has_access, owner_id = verify_business_access(cursor, business_id, user_data)
    if not has_access:
        status = 403 if owner_id else 404
        message = "Нет доступа к бизнесу" if owner_id else "Бизнес не найден"
        return None, (jsonify({"success": False, "error": message}), status)
    return user_data, None


def _user_id(user_data: dict) -> str:
    return str(user_data.get("user_id") or user_data.get("id") or "")


@web_tracking_bp.route("/api/tracking/events", methods=["POST", "OPTIONS"])
def receive_tracking_events():
    started_at = time.perf_counter()
    if request.method == "OPTIONS":
        return _cors(make_response("", 204))
    if not _flag("WEB_TRACKING_ENABLED") or not _flag("WEB_TRACKING_INGEST_ENABLED"):
        return _ingestion_response(started_at=started_at, status=503, outcome="tracking_ingestion_disabled")
    if request.content_length and request.content_length > MAX_REQUEST_BYTES:
        return _ingestion_response(started_at=started_at, status=413, outcome="payload_too_large")
    payload = _request_payload()
    tracker_id, events, validation_error = validate_batch(payload)
    if validation_error:
        return _ingestion_response(started_at=started_at, status=400, outcome=validation_error, tracker_id=tracker_id)
    rate_key = f"{request.remote_addr or 'unknown'}:{tracker_id}"
    if not _rate_allowed(rate_key):
        return _ingestion_response(started_at=started_at, status=429, outcome="rate_limited", tracker_id=tracker_id)

    db = DatabaseManager()
    cursor = db.conn.cursor()
    tracker = None
    try:
        cursor.execute(
            """
            SELECT id, business_id, public_tracker_id, allowed_domains
            FROM business_web_trackers
            WHERE public_tracker_id = %s AND enabled = TRUE AND tracking_enabled = TRUE
            LIMIT 1
            """,
            (tracker_id,),
        )
        tracker = cursor.fetchone()
        if not tracker or not _business_allowlisted(str(tracker["business_id"])):
            return _ingestion_response(started_at=started_at, status=404, outcome="tracker_not_found", tracker_id=tracker_id)
        domain_error = validate_tracker_domains(events, tracker.get("allowed_domains"))
        if domain_error:
            _record_tracker_error(db, dict(tracker), domain_error)
            return _ingestion_response(started_at=started_at, status=403, outcome=domain_error, tracker_id=tracker_id)
        result = ingest_events(cursor, dict(tracker), events)
        db.conn.commit()
        return _ingestion_response(
            started_at=started_at,
            status=202,
            outcome="accepted",
            tracker_id=tracker_id,
            received=len(events),
            accepted=result["accepted"],
            duplicates=result["duplicates"],
        )
    except WebTrackingLimitError as error:
        db.conn.rollback()
        _record_tracker_error(db, dict(tracker) if tracker else None, str(error))
        return _ingestion_response(started_at=started_at, status=429, outcome=str(error), tracker_id=tracker_id)
    except WebTrackingConflictError as error:
        db.conn.rollback()
        _record_tracker_error(db, dict(tracker) if tracker else None, str(error))
        return _ingestion_response(started_at=started_at, status=409, outcome=str(error), tracker_id=tracker_id)
    except Exception:
        db.conn.rollback()
        _record_tracker_error(db, dict(tracker) if tracker else None, "ingestion_failed")
        logger.exception("web tracking ingestion transaction failed")
        return _ingestion_response(started_at=started_at, status=500, outcome="ingestion_failed", tracker_id=tracker_id)
    finally:
        db.close()


@web_tracking_bp.route("/api/business/<business_id>/web-tracking", methods=["GET", "POST"])
def business_web_tracking(business_id: str):
    if not _flag("WEB_TRACKING_ENABLED") or not _business_allowlisted(business_id):
        return jsonify({"success": False, "error": "web_tracking_unavailable"}), 404
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        _user, access_error = _require_business(cursor, business_id)
        if access_error:
            return access_error
        allow_create = _flag("WEB_TRACKING_CREATE_ENABLED")
        tracker = ensure_tracker(cursor, business_id, allow_create=allow_create)
        if not tracker:
            return jsonify({"success": False, "error": "tracker_creation_disabled"}), 409
        if request.method == "POST":
            payload = request.get_json(silent=True) or {}
            if "tracking_enabled" in payload:
                if type(payload.get("tracking_enabled")) is not bool:
                    return jsonify({"success": False, "error": "invalid_tracking_enabled"}), 400
                cursor.execute(
                    "UPDATE business_web_trackers SET tracking_enabled = %s WHERE id = %s",
                    (payload.get("tracking_enabled"), tracker["id"]),
                )
                tracker["tracking_enabled"] = payload.get("tracking_enabled")
            if "allowed_domains" in payload:
                raw_domains = payload.get("allowed_domains")
                if not isinstance(raw_domains, list) or len(raw_domains) > 20:
                    return jsonify({"success": False, "error": "invalid_allowed_domains"}), 400
                allowed_domains = []
                for raw_domain in raw_domains:
                    candidate = str(raw_domain or "").strip()
                    parsed = urlparse(candidate if "://" in candidate else f"https://{candidate}")
                    hostname = normalize_hostname(parsed.hostname or "")
                    if not hostname:
                        return jsonify({"success": False, "error": "invalid_allowed_domain"}), 400
                    if hostname not in allowed_domains:
                        allowed_domains.append(hostname)
                cursor.execute(
                    "UPDATE business_web_trackers SET allowed_domains = %s, domain = %s WHERE id = %s",
                    (allowed_domains, allowed_domains[0] if allowed_domains else None, tracker["id"]),
                )
                tracker["allowed_domains"] = allowed_domains
                tracker["domain"] = allowed_domains[0] if allowed_domains else None
        db.conn.commit()
        result = tracker_status(tracker)
        result["embed_code"] = (
            '<script async src="https://localos.pro/tracker.js" '
            f'data-business="{result["public_tracker_id"]}"></script>'
        )
        return jsonify({"success": True, "tracker": result})
    except Exception:
        db.conn.rollback()
        return jsonify({"success": False, "error": "Не удалось получить настройки tracking"}), 500
    finally:
        db.close()


@web_tracking_bp.route("/api/business/<business_id>/web-analytics", methods=["GET"])
def business_web_analytics(business_id: str):
    if not _flag("WEB_TRACKING_ENABLED") or not _flag("WEB_TRACKING_ANALYTICS_ENABLED") or not _business_allowlisted(business_id):
        return jsonify({"success": False, "error": "web_analytics_unavailable"}), 404
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        _user, access_error = _require_business(cursor, business_id)
        if access_error:
            return access_error
        try:
            period_days = int(request.args.get("period", "30"))
        except ValueError:
            period_days = 30
        metrics = get_business_web_metrics(cursor, business_id, period_days)
        metrics.update(get_web_analytics_extensions(cursor, business_id, period_days))
        return jsonify({"success": True, "metrics": metrics})
    except Exception:
        return jsonify({"success": False, "error": "Не удалось собрать аналитику сайта"}), 500
    finally:
        db.close()


@web_tracking_bp.route("/api/business/<business_id>/web-analytics/configuration", methods=["GET"])
def web_analytics_configuration(business_id: str):
    if _web_configuration_unavailable(business_id):
        return jsonify({"success": False, "error": "web_analytics_unavailable"}), 404
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        _user, access_error = _require_business(cursor, business_id)
        if access_error:
            return access_error
        return jsonify({
            "success": True,
            "page_groups": list_page_groups(cursor, business_id),
            "goals": list_goals(cursor, business_id),
            "annotations": list_annotations(cursor, business_id),
            "campaign_costs": list_campaign_costs(cursor, business_id),
            "conversion_key": conversion_key_status(cursor, business_id),
        })
    finally:
        db.close()


@web_tracking_bp.route("/api/business/<business_id>/web-page-groups/preview", methods=["POST"])
def web_page_group_preview(business_id: str):
    if _web_configuration_unavailable(business_id):
        return jsonify({"success": False, "error": "web_analytics_unavailable"}), 404
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        _user, access_error = _require_business(cursor, business_id)
        if access_error:
            return access_error
        return jsonify({"success": True, "preview": preview_page_group(cursor, business_id, request.get_json(silent=True))})
    except WebTrackingConfigurationError as error:
        return jsonify({"success": False, "error": str(error)}), 400
    finally:
        db.close()


@web_tracking_bp.route("/api/business/<business_id>/web-page-groups", methods=["POST"])
@web_tracking_bp.route("/api/business/<business_id>/web-page-groups/<group_id>", methods=["PATCH", "DELETE"])
def web_page_group_mutation(business_id: str, group_id: str = ""):
    if _web_configuration_unavailable(business_id):
        return jsonify({"success": False, "error": "web_analytics_unavailable"}), 404
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        user_data, access_error = _require_business(cursor, business_id)
        if access_error:
            return access_error
        if request.method == "DELETE":
            if not delete_page_group(cursor, business_id, group_id):
                return jsonify({"success": False, "error": "page_group_not_found"}), 404
            save_system_annotation(cursor, business_id, "Удалена группа страниц", "page")
            db.conn.commit()
            return jsonify({"success": True})
        group = save_page_group(
            cursor, business_id, _user_id(user_data), request.get_json(silent=True), group_id,
        )
        save_system_annotation(cursor, business_id, f"Настроена группа страниц: {group['name']}", "page")
        db.conn.commit()
        return jsonify({"success": True, "page_group": group})
    except WebTrackingConfigurationError as error:
        db.conn.rollback()
        status = 404 if str(error) == "page_group_not_found" else 400
        return jsonify({"success": False, "error": str(error)}), status
    except Exception:
        db.conn.rollback()
        logger.exception("web page group mutation failed")
        return jsonify({"success": False, "error": "page_group_save_failed"}), 500
    finally:
        db.close()


@web_tracking_bp.route("/api/business/<business_id>/web-goals", methods=["POST"])
@web_tracking_bp.route("/api/business/<business_id>/web-goals/<goal_id>", methods=["PATCH", "DELETE"])
def web_goal_mutation(business_id: str, goal_id: str = ""):
    if _web_configuration_unavailable(business_id):
        return jsonify({"success": False, "error": "web_analytics_unavailable"}), 404
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        user_data, access_error = _require_business(cursor, business_id)
        if access_error:
            return access_error
        if request.method == "DELETE":
            if not delete_goal(cursor, business_id, goal_id):
                return jsonify({"success": False, "error": "goal_not_found"}), 404
            save_system_annotation(cursor, business_id, "Удалена цель сайта", "tracker")
            db.conn.commit()
            return jsonify({"success": True})
        goal = save_goal(cursor, business_id, _user_id(user_data), request.get_json(silent=True), goal_id)
        save_system_annotation(cursor, business_id, f"Настроена цель: {goal['name']}", "tracker")
        db.conn.commit()
        return jsonify({"success": True, "goal": goal})
    except WebTrackingConfigurationError as error:
        db.conn.rollback()
        status = 404 if str(error) == "goal_not_found" else 400
        return jsonify({"success": False, "error": str(error)}), status
    except Exception:
        db.conn.rollback()
        logger.exception("web goal mutation failed")
        return jsonify({"success": False, "error": "goal_save_failed"}), 500
    finally:
        db.close()


@web_tracking_bp.route("/api/business/<business_id>/web-change-annotations", methods=["POST"])
@web_tracking_bp.route("/api/business/<business_id>/web-change-annotations/<annotation_id>", methods=["DELETE"])
def web_change_annotation_mutation(business_id: str, annotation_id: str = ""):
    if _web_configuration_unavailable(business_id):
        return jsonify({"success": False, "error": "web_analytics_unavailable"}), 404
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        user_data, access_error = _require_business(cursor, business_id)
        if access_error:
            return access_error
        if request.method == "DELETE":
            if not delete_annotation(cursor, business_id, annotation_id):
                return jsonify({"success": False, "error": "annotation_not_found"}), 404
            db.conn.commit()
            return jsonify({"success": True})
        annotation = save_annotation(cursor, business_id, _user_id(user_data), request.get_json(silent=True))
        db.conn.commit()
        return jsonify({"success": True, "annotation": annotation})
    except WebTrackingConfigurationError as error:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(error)}), 400
    except Exception:
        db.conn.rollback()
        logger.exception("web change annotation mutation failed")
        return jsonify({"success": False, "error": "annotation_save_failed"}), 500
    finally:
        db.close()


@web_tracking_bp.route("/api/business/<business_id>/web-campaign-costs", methods=["POST"])
@web_tracking_bp.route("/api/business/<business_id>/web-campaign-costs/<cost_id>", methods=["DELETE"])
def web_campaign_cost_mutation(business_id: str, cost_id: str = ""):
    if _web_configuration_unavailable(business_id):
        return jsonify({"success": False, "error": "web_analytics_unavailable"}), 404
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        user_data, access_error = _require_business(cursor, business_id)
        if access_error:
            return access_error
        if request.method == "DELETE":
            if not delete_campaign_cost(cursor, business_id, cost_id):
                return jsonify({"success": False, "error": "campaign_cost_not_found"}), 404
            db.conn.commit()
            return jsonify({"success": True})
        cost = save_campaign_cost(cursor, business_id, _user_id(user_data), request.get_json(silent=True))
        save_system_annotation(cursor, business_id, f"Добавлены расходы кампании: {cost['source']}", "campaign")
        db.conn.commit()
        return jsonify({"success": True, "campaign_cost": cost})
    except WebTrackingConfigurationError as error:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(error)}), 400
    except Exception:
        db.conn.rollback()
        logger.exception("web campaign cost mutation failed")
        return jsonify({"success": False, "error": "campaign_cost_save_failed"}), 500
    finally:
        db.close()


@web_tracking_bp.route("/api/business/<business_id>/web-conversion-key", methods=["POST"])
def web_conversion_key_rotation(business_id: str):
    if _web_configuration_unavailable(business_id):
        return jsonify({"success": False, "error": "web_analytics_unavailable"}), 404
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        _user, access_error = _require_business(cursor, business_id)
        if access_error:
            return access_error
        result = rotate_conversion_key(cursor, business_id)
        save_system_annotation(cursor, business_id, "Обновлён ключ подтверждённых конверсий", "tracker")
        db.conn.commit()
        return jsonify({"success": True, "conversion_key": result})
    except WebTrackingConfigurationError as error:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(error)}), 409
    except Exception:
        db.conn.rollback()
        logger.exception("web conversion key rotation failed")
        return jsonify({"success": False, "error": "conversion_key_rotation_failed"}), 500
    finally:
        db.close()


@web_tracking_bp.route("/api/web-tracking/conversions", methods=["POST"])
def receive_confirmed_conversion():
    if not _flag("WEB_TRACKING_ENABLED"):
        return jsonify({"success": False, "error": "web_tracking_unavailable"}), 404
    authorization = request.headers.get("Authorization", "")
    token = authorization[7:] if authorization.startswith("Bearer ") else ""
    rate_key = f"conversion:{hashlib.sha256(token.encode('utf-8')).hexdigest()[:16]}"
    if not _rate_allowed(rate_key):
        return jsonify({"success": False, "error": "rate_limited"}), 429
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        tracker = resolve_conversion_tracker(cursor, token)
        result = ingest_confirmed_conversion(cursor, tracker, request.get_json(silent=True))
        db.conn.commit()
        return jsonify({"success": True, **result}), 202
    except WebConversionAuthenticationError:
        db.conn.rollback()
        return jsonify({"success": False, "error": "invalid_conversion_key"}), 401
    except WebTrackingConfigurationError as error:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(error)}), 400
    except Exception:
        db.conn.rollback()
        logger.exception("confirmed web conversion ingestion failed")
        return jsonify({"success": False, "error": "conversion_ingestion_failed"}), 500
    finally:
        db.close()


@web_tracking_bp.route("/api/admin/web-tracking/health", methods=["GET"])
def web_tracking_health():
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    if not user_data.get("is_superadmin"):
        return jsonify({"success": False, "error": "Недостаточно прав"}), 403
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        return jsonify({"success": True, **get_web_tracking_health(cursor), "ingestion": get_ingestion_metrics()})
    finally:
        db.close()


@web_tracking_bp.route("/api/admin/business/<business_id>/web-tracking/delete", methods=["POST"])
def delete_business_web_tracking(business_id: str):
    user_data = require_auth_from_request()
    if not user_data:
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    if not user_data.get("is_superadmin"):
        return jsonify({"success": False, "error": "Недостаточно прав"}), 403
    payload = request.get_json(silent=True) or {}
    dry_run = payload.get("dry_run", True) is not False
    if not dry_run and (
        payload.get("confirm_business_id") != business_id
        or payload.get("acknowledge_irreversible") is not True
    ):
        return jsonify({"success": False, "error": "deletion_confirmation_required"}), 400
    requested_by = str(user_data.get("user_id") or user_data.get("id") or "")
    if not requested_by:
        return jsonify({"success": False, "error": "invalid_admin_identity"}), 403
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        cursor.execute("SELECT id FROM businesses WHERE id = %s", (business_id,))
        if not cursor.fetchone():
            return jsonify({"success": False, "error": "business_not_found"}), 404
        result = delete_business_web_analytics(
            cursor,
            business_id,
            requested_by,
            dry_run=dry_run,
        )
        db.conn.commit()
        return jsonify({"success": True, "deletion": result})
    except WebTrackingDeletionError as error:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(error)}), 409
    except Exception:
        db.conn.rollback()
        logger.exception("web tracking administrative deletion failed")
        return jsonify({"success": False, "error": "web_tracking_deletion_failed"}), 500
    finally:
        db.close()
