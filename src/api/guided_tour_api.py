from __future__ import annotations

import json
import os
import threading
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Any

from flask import Blueprint, jsonify, request
from psycopg2.extras import Json

from auth_system import create_session, verify_session
from pg_db_utils import get_db_connection


guided_tour_bp = Blueprint("guided_tour_api", __name__)

TOUR_VERSION = 1
TOUR_KEYS = {"roga-i-kopyta-v1"}
PROGRESS_STATUSES = {"not_started", "active", "paused", "skipped", "completed"}
EVENT_TYPES = {
    "started",
    "step_viewed",
    "chapter_completed",
    "paused",
    "resumed",
    "skipped",
    "completed",
    "restarted",
    "target_missing",
    "registration_clicked",
    "room_opened",
}

DEMO_READ_PATH_PREFIXES = (
    "/api/auth/me",
    "/api/guided-tours/",
    "/api/business/",
    "/api/business-types",
    "/api/client-info",
    "/api/services",
    "/api/growth",
    "/api/progress",
    "/api/stage-progress",
    "/api/metrics",
    "/api/reports",
    "/api/operator/",
    "/api/partnership/",
    "/api/content-plans",
    "/api/social-posts",
    "/api/media-intelligence/",
    "/api/networks",
)
DEMO_DENIED_PATH_PARTS = (
    "external-accounts",
    "integrations",
    "credentials",
    "access-token",
    "auth-data",
    "/api/superadmin",
    "/api/agent-api",
    "/api/admin/knowledge",
)

_rate_lock = threading.Lock()
_rate_hits: dict[str, deque[float]] = defaultdict(deque)


def _row_value(row: Any, key: str, index: int = 0, default: Any = None) -> Any:
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key, default)
    if hasattr(row, "keys") and key in row.keys():
        return row[key]
    try:
        return row[index]
    except (IndexError, KeyError, TypeError):
        return default


def _auth_token() -> str:
    header = str(request.headers.get("Authorization") or "")
    if not header.startswith("Bearer "):
        return ""
    return header.split(" ", 1)[1].strip()


def _session_from_request() -> dict[str, Any] | None:
    token = _auth_token()
    return verify_session(token) if token else None


def _is_public_demo_enabled() -> bool:
    return str(os.getenv("PUBLIC_DEMO_ENABLED", "false")).strip().lower() in {"1", "true", "yes", "on"}


def _public_demo_rate_limited(remote_address: str, now: float | None = None) -> bool:
    timestamp = now if now is not None else time.time()
    key = str(remote_address or "unknown")
    cutoff = timestamp - 3600
    with _rate_lock:
        hits = _rate_hits[key]
        while hits and hits[0] <= cutoff:
            hits.popleft()
        if len(hits) >= 20:
            return True
        hits.append(timestamp)
    return False


def _tour_key_or_error(tour_key: str):
    normalized = str(tour_key or "").strip()
    if normalized not in TOUR_KEYS:
        return None, (jsonify({"success": False, "error": "tour_not_found"}), 404)
    return normalized, None


def _require_demo_session():
    session = _session_from_request()
    if not session:
        return None, (jsonify({"success": False, "error": "unauthorized"}), 401)
    if str(session.get("session_kind") or "standard") != "demo":
        return None, (jsonify({"success": False, "error": "demo_session_required"}), 403)
    if not session.get("session_id") or not session.get("scope_business_id"):
        return None, (jsonify({"success": False, "error": "invalid_demo_scope"}), 403)
    return session, None


def _serialize_progress(row: Any, *, tour_key: str, business_id: str) -> dict[str, Any]:
    if not row:
        return {
            "tour_key": tour_key,
            "tour_version": TOUR_VERSION,
            "business_id": business_id,
            "status": "not_started",
            "chapter_key": None,
            "step_key": None,
            "completed_steps": [],
            "started_at": None,
            "paused_at": None,
            "completed_at": None,
            "updated_at": None,
        }
    completed = _row_value(row, "completed_steps_json", 6, []) or []
    if isinstance(completed, str):
        try:
            completed = json.loads(completed)
        except json.JSONDecodeError:
            completed = []
    return {
        "tour_key": str(_row_value(row, "tour_key", 1, tour_key) or tour_key),
        "tour_version": int(_row_value(row, "tour_version", 2, TOUR_VERSION) or TOUR_VERSION),
        "business_id": business_id,
        "status": str(_row_value(row, "status", 3, "not_started") or "not_started"),
        "chapter_key": _row_value(row, "chapter_key", 4),
        "step_key": _row_value(row, "step_key", 5),
        "completed_steps": completed if isinstance(completed, list) else [],
        "started_at": _row_value(row, "started_at", 7),
        "paused_at": _row_value(row, "paused_at", 8),
        "completed_at": _row_value(row, "completed_at", 9),
        "updated_at": _row_value(row, "updated_at", 10),
    }


@guided_tour_bp.before_app_request
def enforce_demo_session_policy():
    if not request.path.startswith("/api/"):
        return None
    token = _auth_token()
    if not token or not token.startswith("demo_"):
        return None
    session = verify_session(token)
    if not session or str(session.get("session_kind") or "standard") != "demo":
        return None

    path = request.path
    method = request.method.upper()
    allowed_mutation = (
        (method == "POST" and path == "/api/auth/logout")
        or (method == "PUT" and path.startswith("/api/guided-tours/") and path.endswith("/progress"))
        or (method == "POST" and path.startswith("/api/guided-tours/") and path.endswith("/events"))
    )
    if allowed_mutation:
        return None
    if method not in {"GET", "HEAD", "OPTIONS"}:
        return jsonify({"success": False, "error": "demo_read_only", "message": "В демо-режиме данные не изменяются."}), 403
    if any(part in path for part in DEMO_DENIED_PATH_PARTS):
        return jsonify({"success": False, "error": "demo_route_not_allowed"}), 403
    if not any(path.startswith(prefix) for prefix in DEMO_READ_PATH_PREFIXES):
        return jsonify({"success": False, "error": "demo_route_not_allowed"}), 403
    return None


@guided_tour_bp.route("/api/public-demo/session", methods=["POST"])
def create_public_demo_session():
    if not _is_public_demo_enabled():
        return jsonify({"success": False, "error": "public_demo_disabled"}), 404
    if _public_demo_rate_limited(request.remote_addr or "unknown"):
        return jsonify({"success": False, "error": "rate_limited", "message": "Слишком много запросов. Повторите позже."}), 429

    user_id = str(os.getenv("PUBLIC_DEMO_USER_ID", "")).strip()
    business_id = str(os.getenv("PUBLIC_DEMO_BUSINESS_ID", "")).strip()
    if not user_id or not business_id:
        return jsonify({"success": False, "error": "public_demo_not_configured"}), 503

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT b.id, b.owner_id, b.is_active AS business_is_active,
                   u.is_active AS user_is_active
            FROM businesses b
            JOIN users u ON u.id = b.owner_id
            WHERE b.id = %s AND b.owner_id = %s
            LIMIT 1
            """,
            (business_id, user_id),
        )
        row = cursor.fetchone()
        if (
            not row
            or _row_value(row, "business_is_active", 2, False) is False
            or _row_value(row, "user_is_active", 3, False) is False
        ):
            return jsonify({"success": False, "error": "public_demo_unavailable"}), 503
    finally:
        conn.close()

    try:
        configured_ttl = int(os.getenv("DEMO_SESSION_TTL_DAYS", "30"))
    except (TypeError, ValueError):
        configured_ttl = 30
    ttl_days = max(1, min(configured_ttl, 90))
    token = create_session(
        user_id,
        ip_address=request.remote_addr,
        user_agent=str(request.headers.get("User-Agent") or "")[:500],
        session_kind="demo",
        scope_business_id=business_id,
        expires_days=ttl_days,
    )
    if not token:
        return jsonify({"success": False, "error": "demo_session_create_failed"}), 500
    return jsonify(
        {
            "success": True,
            "token": token,
            "business_id": business_id,
            "tour_key": "roga-i-kopyta-v1",
            "tour_version": TOUR_VERSION,
            "start_path": "/dashboard/operator",
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=ttl_days)).isoformat(),
        }
    )


@guided_tour_bp.route("/api/guided-tours/<tour_key>/progress", methods=["GET"])
def get_guided_tour_progress(tour_key: str):
    normalized_key, error = _tour_key_or_error(tour_key)
    if error:
        return error
    session, error = _require_demo_session()
    if error:
        return error

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT id, tour_key, tour_version, status, chapter_key, step_key,
                   completed_steps_json, started_at, paused_at, completed_at, updated_at
            FROM guided_tour_progress
            WHERE session_id = %s AND tour_key = %s AND tour_version = %s
            LIMIT 1
            """,
            (session["session_id"], normalized_key, TOUR_VERSION),
        )
        progress = _serialize_progress(
            cursor.fetchone(),
            tour_key=normalized_key,
            business_id=str(session["scope_business_id"]),
        )
        return jsonify({"success": True, "progress": progress})
    finally:
        conn.close()


@guided_tour_bp.route("/api/guided-tours/<tour_key>/progress", methods=["PUT"])
def save_guided_tour_progress(tour_key: str):
    normalized_key, error = _tour_key_or_error(tour_key)
    if error:
        return error
    session, error = _require_demo_session()
    if error:
        return error
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"success": False, "error": "invalid_json"}), 400

    status = str(payload.get("status") or "").strip()
    if status not in PROGRESS_STATUSES:
        return jsonify({"success": False, "error": "invalid_status"}), 400
    raw_tour_version = payload.get("tour_version", TOUR_VERSION)
    try:
        tour_version = int(TOUR_VERSION if raw_tour_version in (None, "") else raw_tour_version)
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "invalid_tour_version"}), 400
    if tour_version != TOUR_VERSION:
        return jsonify({"success": False, "error": "tour_version_mismatch", "current_version": TOUR_VERSION}), 409
    chapter_key = str(payload.get("chapter_key") or "").strip()[:100] or None
    step_key = str(payload.get("step_key") or "").strip()[:100] or None
    completed_steps = payload.get("completed_steps") or []
    if not isinstance(completed_steps, list):
        return jsonify({"success": False, "error": "completed_steps_must_be_array"}), 400
    completed_steps = [str(item).strip()[:100] for item in completed_steps[:100] if str(item).strip()]

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO guided_tour_progress (
                id, session_id, business_id, tour_key, tour_version, status,
                chapter_key, step_key, completed_steps_json, started_at, paused_at,
                completed_at, created_at, updated_at
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s,
                CASE WHEN %s IN ('active', 'paused', 'completed') THEN NOW() ELSE NULL END,
                CASE WHEN %s = 'paused' THEN NOW() ELSE NULL END,
                CASE WHEN %s = 'completed' THEN NOW() ELSE NULL END,
                NOW(), NOW()
            )
            ON CONFLICT (session_id, tour_key, tour_version) DO UPDATE SET
                status = EXCLUDED.status,
                chapter_key = EXCLUDED.chapter_key,
                step_key = EXCLUDED.step_key,
                completed_steps_json = EXCLUDED.completed_steps_json,
                started_at = COALESCE(guided_tour_progress.started_at, EXCLUDED.started_at),
                paused_at = CASE WHEN EXCLUDED.status = 'paused' THEN NOW() ELSE guided_tour_progress.paused_at END,
                completed_at = CASE WHEN EXCLUDED.status = 'completed' THEN NOW() ELSE guided_tour_progress.completed_at END,
                updated_at = NOW()
            RETURNING id, tour_key, tour_version, status, chapter_key, step_key,
                      completed_steps_json, started_at, paused_at, completed_at, updated_at
            """,
            (
                str(uuid.uuid4()),
                session["session_id"],
                session["scope_business_id"],
                normalized_key,
                TOUR_VERSION,
                status,
                chapter_key,
                step_key,
                Json(completed_steps),
                status,
                status,
                status,
            ),
        )
        row = cursor.fetchone()
        conn.commit()
        return jsonify(
            {
                "success": True,
                "progress": _serialize_progress(
                    row,
                    tour_key=normalized_key,
                    business_id=str(session["scope_business_id"]),
                ),
            }
        )
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@guided_tour_bp.route("/api/guided-tours/<tour_key>/events", methods=["POST"])
def record_guided_tour_event(tour_key: str):
    normalized_key, error = _tour_key_or_error(tour_key)
    if error:
        return error
    session, error = _require_demo_session()
    if error:
        return error
    payload = request.get_json(silent=True) or {}
    event_type = str(payload.get("event_type") or "").strip()
    if event_type not in EVENT_TYPES:
        return jsonify({"success": False, "error": "unsupported_event_type"}), 400
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    if len(json.dumps(metadata, ensure_ascii=False)) > 4096:
        return jsonify({"success": False, "error": "metadata_too_large"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO guided_tour_events (
                id, session_id, business_id, tour_key, tour_version, event_type,
                chapter_key, step_key, route, metadata_json, created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """,
            (
                str(uuid.uuid4()),
                session["session_id"],
                session["scope_business_id"],
                normalized_key,
                TOUR_VERSION,
                event_type,
                str(payload.get("chapter_key") or "").strip()[:100] or None,
                str(payload.get("step_key") or "").strip()[:100] or None,
                str(payload.get("route") or "").strip()[:500] or None,
                Json(metadata),
            ),
        )
        conn.commit()
        return jsonify({"success": True}), 201
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@guided_tour_bp.route("/api/admin/guided-tours/summary", methods=["GET"])
def get_guided_tour_summary():
    session = _session_from_request()
    if not session:
        return jsonify({"success": False, "error": "unauthorized"}), 401
    if not session.get("is_superadmin"):
        return jsonify({"success": False, "error": "forbidden"}), 403
    tour_key = str(request.args.get("tour_key") or "roga-i-kopyta-v1").strip()
    if tour_key not in TOUR_KEYS:
        return jsonify({"success": False, "error": "tour_not_found"}), 404

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT status, COUNT(*)::INT AS total
            FROM guided_tour_progress
            WHERE tour_key = %s AND tour_version = %s
            GROUP BY status
            ORDER BY status
            """,
            (tour_key, TOUR_VERSION),
        )
        progress = {str(_row_value(row, "status", 0, "")): int(_row_value(row, "total", 1, 0) or 0) for row in cursor.fetchall()}
        cursor.execute(
            """
            SELECT event_type, COUNT(*)::INT AS total
            FROM guided_tour_events
            WHERE tour_key = %s AND tour_version = %s
            GROUP BY event_type
            ORDER BY event_type
            """,
            (tour_key, TOUR_VERSION),
        )
        events = {str(_row_value(row, "event_type", 0, "")): int(_row_value(row, "total", 1, 0) or 0) for row in cursor.fetchall()}
        return jsonify({"success": True, "tour_key": tour_key, "tour_version": TOUR_VERSION, "progress": progress, "events": events})
    finally:
        conn.close()
