from __future__ import annotations

import os
import sys
import time
from collections import defaultdict, deque
from typing import Deque

from flask import Blueprint, jsonify, request

from auth_system import verify_session
from services.social_post_service import (
    apply_social_post_recommendation,
    approve_social_post,
    approve_social_posts,
    collect_social_post_metrics,
    list_social_posts_for_plan,
    mark_manual_published,
    mark_manual_published_posts,
    prepare_social_posts_for_item,
    prepare_social_posts_for_items,
    preview_due_social_post_dispatch,
    publish_social_post,
    publish_social_posts,
    queue_social_post,
    queue_social_posts,
    recommend_next_plan_from_social_posts,
    record_social_post_attribution_event,
    update_social_post_text,
)


social_posts_bp = Blueprint("social_posts", __name__)
_WRITE_RATE_BUCKETS: dict[str, Deque[float]] = defaultdict(deque)


def _int_env(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _bool_env(name: str, default: bool = False) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on", "enabled"}


def social_post_runtime_status_payload() -> dict[str, object]:
    return {
        "dispatch": {
            "enabled": _bool_env("SOCIAL_POST_DISPATCH_ENABLED", False),
            "interval_sec": max(15, _int_env("SOCIAL_POST_DISPATCH_INTERVAL_SEC", 60)),
            "batch_size": max(1, min(_int_env("SOCIAL_POST_DISPATCH_BATCH_SIZE", 20), 200)),
        },
        "metrics": {
            "enabled": _bool_env("SOCIAL_POST_METRICS_ENABLED", False),
            "interval_sec": max(60, _int_env("SOCIAL_POST_METRICS_INTERVAL_SEC", 3600)),
            "batch_size": max(1, min(_int_env("SOCIAL_POST_METRICS_BATCH_SIZE", 50), 500)),
        },
        "approval_required": True,
        "browser_final_click_allowed": False,
    }


def _check_write_rate_limit(user_id: str, action: str):
    limit = max(_int_env("SOCIAL_POST_WRITE_RATE_LIMIT", 40), 1)
    window_sec = max(_int_env("SOCIAL_POST_WRITE_RATE_WINDOW_SEC", 3600), 60)
    now = time.time()
    bucket_key = f"{user_id}:{action}"
    bucket = _WRITE_RATE_BUCKETS[bucket_key]
    while bucket and now - bucket[0] >= window_sec:
        bucket.popleft()
    if len(bucket) >= limit:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "rate_limited",
                    "message": "Слишком много действий с публикациями. Повторите позже.",
                }
            ),
            429,
        )
    bucket.append(now)
    return None


def _require_auth():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, (jsonify({"success": False, "error": "Требуется авторизация"}), 401)
    user_data = verify_session(auth_header.split(" ", 1)[1])
    if not user_data:
        return None, (jsonify({"success": False, "error": "Недействительный токен"}), 401)
    return user_data, None


@social_posts_bp.route("/api/content-plans/items/<item_id>/social-posts/prepare", methods=["POST"])
def social_posts_prepare(item_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    rate_error = _check_write_rate_limit(str(user_data.get("user_id") or ""), "prepare")
    if rate_error:
        return rate_error
    data = request.get_json(silent=True) or {}
    platforms = data.get("platforms") if isinstance(data.get("platforms"), list) else None
    try:
        payload = prepare_social_posts_for_item(str(user_data.get("user_id") or ""), item_id, platforms)
        return jsonify({"success": True, **payload})
    except PermissionError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 403
    except ValueError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 400
    except Exception:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500


@social_posts_bp.route("/api/content-plans/social-posts/bulk-prepare", methods=["POST"])
def social_posts_bulk_prepare():
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    rate_error = _check_write_rate_limit(str(user_data.get("user_id") or ""), "bulk-prepare")
    if rate_error:
        return rate_error
    data = request.get_json(silent=True) or {}
    item_ids = data.get("item_ids") if isinstance(data.get("item_ids"), list) else []
    platforms = data.get("platforms") if isinstance(data.get("platforms"), list) else None
    try:
        payload = prepare_social_posts_for_items(str(user_data.get("user_id") or ""), item_ids, platforms)
        return jsonify({"success": True, **payload})
    except PermissionError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 403
    except ValueError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 400
    except Exception:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500


@social_posts_bp.route("/api/content-plans/<plan_id>/social-posts", methods=["GET"])
def social_posts_list(plan_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    try:
        payload = list_social_posts_for_plan(str(user_data.get("user_id") or ""), plan_id)
        return jsonify({"success": True, **payload})
    except PermissionError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 403
    except ValueError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 404
    except Exception:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500


@social_posts_bp.route("/api/social-posts/runtime-status", methods=["GET"])
def social_posts_runtime_status():
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    return jsonify({"success": True, **social_post_runtime_status_payload()})


@social_posts_bp.route("/api/social-posts/bulk-approve", methods=["POST"])
def social_posts_bulk_approve():
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    rate_error = _check_write_rate_limit(str(user_data.get("user_id") or ""), "bulk-approve")
    if rate_error:
        return rate_error
    data = request.get_json(silent=True) or {}
    post_ids = data.get("post_ids") if isinstance(data.get("post_ids"), list) else []
    try:
        payload = approve_social_posts(str(user_data.get("user_id") or ""), post_ids)
        return jsonify({"success": True, **payload})
    except PermissionError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 403
    except ValueError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 400
    except Exception:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500


@social_posts_bp.route("/api/social-posts/<post_id>/approve", methods=["POST"])
def social_posts_approve(post_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    rate_error = _check_write_rate_limit(str(user_data.get("user_id") or ""), "approve")
    if rate_error:
        return rate_error
    try:
        post = approve_social_post(str(user_data.get("user_id") or ""), post_id)
        return jsonify({"success": True, "post": post})
    except PermissionError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 403
    except ValueError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 400
    except Exception:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500


@social_posts_bp.route("/api/social-posts/<post_id>", methods=["PATCH"])
def social_posts_update(post_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    rate_error = _check_write_rate_limit(str(user_data.get("user_id") or ""), "update")
    if rate_error:
        return rate_error
    data = request.get_json(silent=True) or {}
    try:
        post = update_social_post_text(
            str(user_data.get("user_id") or ""),
            post_id,
            platform_text=str(data.get("platform_text") or ""),
            base_text=str(data.get("base_text") or ""),
        )
        return jsonify({"success": True, "post": post})
    except PermissionError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 403
    except ValueError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 400
    except Exception:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500


@social_posts_bp.route("/api/social-posts/bulk-publish", methods=["POST"])
def social_posts_bulk_publish():
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    rate_error = _check_write_rate_limit(str(user_data.get("user_id") or ""), "bulk-publish")
    if rate_error:
        return rate_error
    data = request.get_json(silent=True) or {}
    post_ids = data.get("post_ids") if isinstance(data.get("post_ids"), list) else []
    try:
        payload = publish_social_posts(str(user_data.get("user_id") or ""), post_ids)
        return jsonify({"success": True, **payload})
    except PermissionError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 403
    except ValueError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 400
    except Exception:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500


@social_posts_bp.route("/api/social-posts/bulk-queue", methods=["POST"])
def social_posts_bulk_queue():
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    rate_error = _check_write_rate_limit(str(user_data.get("user_id") or ""), "bulk-queue")
    if rate_error:
        return rate_error
    data = request.get_json(silent=True) or {}
    post_ids = data.get("post_ids") if isinstance(data.get("post_ids"), list) else []
    try:
        payload = queue_social_posts(str(user_data.get("user_id") or ""), post_ids)
        return jsonify({"success": True, **payload})
    except PermissionError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 403
    except ValueError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 400
    except Exception:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500


@social_posts_bp.route("/api/social-posts/<post_id>/queue", methods=["POST"])
def social_posts_queue(post_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    rate_error = _check_write_rate_limit(str(user_data.get("user_id") or ""), "queue")
    if rate_error:
        return rate_error
    try:
        post = queue_social_post(str(user_data.get("user_id") or ""), post_id)
        return jsonify({"success": True, "post": post})
    except PermissionError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 403
    except ValueError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 400
    except Exception:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500


@social_posts_bp.route("/api/social-posts/dispatch/preview", methods=["POST"])
def social_posts_dispatch_preview():
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    rate_error = _check_write_rate_limit(str(user_data.get("user_id") or ""), "dispatch-preview")
    if rate_error:
        return rate_error
    data = request.get_json(silent=True) or {}
    try:
        payload = preview_due_social_post_dispatch(
            str(user_data.get("user_id") or ""),
            batch_size=int(data.get("batch_size") or 20),
        )
        return jsonify({"success": True, **payload})
    except PermissionError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 403
    except ValueError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 400
    except Exception:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500


@social_posts_bp.route("/api/social-posts/<post_id>/publish", methods=["POST"])
def social_posts_publish(post_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    rate_error = _check_write_rate_limit(str(user_data.get("user_id") or ""), "publish")
    if rate_error:
        return rate_error
    try:
        post = publish_social_post(str(user_data.get("user_id") or ""), post_id)
        return jsonify({"success": True, "post": post})
    except PermissionError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 403
    except ValueError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 400
    except Exception:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500


@social_posts_bp.route("/api/social-posts/bulk-mark-manual-published", methods=["POST"])
def social_posts_bulk_mark_manual_published():
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    rate_error = _check_write_rate_limit(str(user_data.get("user_id") or ""), "bulk-manual-published")
    if rate_error:
        return rate_error
    data = request.get_json(silent=True) or {}
    post_ids = data.get("post_ids") if isinstance(data.get("post_ids"), list) else []
    try:
        payload = mark_manual_published_posts(
            str(user_data.get("user_id") or ""),
            post_ids,
            provider_post_url=str(data.get("provider_post_url") or "").strip(),
            provider_post_id=str(data.get("provider_post_id") or "").strip(),
        )
        return jsonify({"success": True, **payload})
    except PermissionError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 403
    except ValueError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 400
    except Exception:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500


@social_posts_bp.route("/api/social-posts/<post_id>/mark-manual-published", methods=["POST"])
def social_posts_mark_manual_published(post_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    rate_error = _check_write_rate_limit(str(user_data.get("user_id") or ""), "manual-published")
    if rate_error:
        return rate_error
    data = request.get_json(silent=True) or {}
    try:
        post = mark_manual_published(
            str(user_data.get("user_id") or ""),
            post_id,
            provider_post_url=str(data.get("provider_post_url") or "").strip(),
            provider_post_id=str(data.get("provider_post_id") or "").strip(),
        )
        return jsonify({"success": True, "post": post})
    except PermissionError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 403
    except ValueError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 400
    except Exception:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500


@social_posts_bp.route("/api/social-posts/<post_id>/attribution-events", methods=["POST"])
def social_posts_attribution_event(post_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    rate_error = _check_write_rate_limit(str(user_data.get("user_id") or ""), "attribution")
    if rate_error:
        return rate_error
    data = request.get_json(silent=True) or {}
    try:
        payload = record_social_post_attribution_event(
            str(user_data.get("user_id") or ""),
            post_id,
            event_type=str(data.get("event_type") or "").strip(),
            value=int(data.get("value") or 1),
            event_source=str(data.get("event_source") or "manual").strip(),
            metadata=data.get("metadata") if isinstance(data.get("metadata"), dict) else {},
        )
        return jsonify({"success": True, **payload})
    except PermissionError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 403
    except ValueError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 400
    except Exception:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500


@social_posts_bp.route("/api/content-plans/<plan_id>/social-posts/recommend-next-plan", methods=["POST"])
def social_posts_recommend_next_plan(plan_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    rate_error = _check_write_rate_limit(str(user_data.get("user_id") or ""), "recommend")
    if rate_error:
        return rate_error
    try:
        payload = recommend_next_plan_from_social_posts(str(user_data.get("user_id") or ""), plan_id)
        return jsonify({"success": True, **payload})
    except PermissionError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 403
    except ValueError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 400
    except Exception:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500


@social_posts_bp.route("/api/content-plans/<plan_id>/social-posts/apply-recommendation", methods=["POST"])
def social_posts_apply_recommendation(plan_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    rate_error = _check_write_rate_limit(str(user_data.get("user_id") or ""), "apply-recommendation")
    if rate_error:
        return rate_error
    data = request.get_json(silent=True) or {}
    try:
        payload = apply_social_post_recommendation(
            str(user_data.get("user_id") or ""),
            plan_id,
            approved=bool(data.get("approved") is True),
        )
        return jsonify({"success": True, **payload})
    except PermissionError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 403
    except ValueError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 400
    except Exception:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500


@social_posts_bp.route("/api/social-posts/metrics/collect", methods=["POST"])
def social_posts_metrics_collect():
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    rate_error = _check_write_rate_limit(str(user_data.get("user_id") or ""), "metrics")
    if rate_error:
        return rate_error
    data = request.get_json(silent=True) or {}
    try:
        payload = collect_social_post_metrics(
            str(user_data.get("user_id") or ""),
            business_id=str(data.get("business_id") or "").strip(),
            post_id=str(data.get("post_id") or "").strip(),
        )
        return jsonify({"success": True, **payload})
    except PermissionError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 403
    except ValueError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 400
    except Exception:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500
