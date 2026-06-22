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
    check_social_api_channel_preflight,
    check_social_openclaw_browser_readiness,
    collect_social_post_metrics,
    create_supervised_publish_task,
    get_social_channel_readiness,
    get_social_launch_preflight,
    list_social_posts_for_plan,
    mark_manual_published,
    mark_manual_published_posts,
    mark_supervised_publish_blocked,
    prepare_social_posts_for_item,
    prepare_social_posts_for_items,
    preview_social_posts_for_item,
    preview_due_social_post_dispatch,
    publish_social_post,
    publish_social_posts,
    queue_social_post,
    queue_social_posts,
    recommend_next_plan_from_social_posts,
    record_social_post_attribution_event,
    run_scoped_social_dispatch_once,
    run_scoped_social_metrics_once,
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


def _bounded_int_payload(data: dict, key: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(data.get(key) or default)
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(value, maximum))


def _bool_env(name: str, default: bool = False) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on", "enabled"}


def social_post_runtime_status_payload() -> dict[str, object]:
    dispatch_business_scope = str(os.getenv("SOCIAL_POST_DISPATCH_BUSINESS_ID") or "").strip()
    metrics_business_scope = str(os.getenv("SOCIAL_POST_METRICS_BUSINESS_ID") or "").strip()
    dispatch_allow_unscoped = _bool_env("SOCIAL_POST_DISPATCH_ALLOW_UNSCOPED", False)
    dispatch_enabled = _bool_env("SOCIAL_POST_DISPATCH_ENABLED", False)
    metrics_allow_unscoped = _bool_env("SOCIAL_POST_METRICS_ALLOW_UNSCOPED", False)
    metrics_enabled = _bool_env("SOCIAL_POST_METRICS_ENABLED", False)
    return {
        "dispatch": {
            "enabled": dispatch_enabled,
            "interval_sec": max(15, _int_env("SOCIAL_POST_DISPATCH_INTERVAL_SEC", 60)),
            "batch_size": max(1, min(_int_env("SOCIAL_POST_DISPATCH_BATCH_SIZE", 20), 200)),
            "business_scope": dispatch_business_scope,
            "scoped": bool(dispatch_business_scope),
            "allow_unscoped": dispatch_allow_unscoped,
            "requires_business_scope": not dispatch_allow_unscoped,
            "blocked_without_scope": dispatch_enabled and not dispatch_business_scope and not dispatch_allow_unscoped,
        },
        "metrics": {
            "enabled": metrics_enabled,
            "interval_sec": max(60, _int_env("SOCIAL_POST_METRICS_INTERVAL_SEC", 3600)),
            "batch_size": max(1, min(_int_env("SOCIAL_POST_METRICS_BATCH_SIZE", 50), 500)),
            "business_scope": metrics_business_scope,
            "scoped": bool(metrics_business_scope),
            "allow_unscoped": metrics_allow_unscoped,
            "requires_business_scope": not metrics_allow_unscoped,
            "blocked_without_scope": metrics_enabled and not metrics_business_scope and not metrics_allow_unscoped,
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


@social_posts_bp.route("/api/content-plans/items/<item_id>/social-posts/prepare-preview", methods=["POST"])
def social_posts_prepare_preview(item_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    data = request.get_json(silent=True) or {}
    platforms = data.get("platforms") if isinstance(data.get("platforms"), list) else None
    try:
        payload = preview_social_posts_for_item(str(user_data.get("user_id") or ""), item_id, platforms)
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


@social_posts_bp.route("/api/business/<business_id>/social-posts/channel-readiness", methods=["GET"])
def social_posts_channel_readiness(business_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    try:
        payload = get_social_channel_readiness(str(user_data.get("user_id") or ""), business_id)
        return jsonify({"success": True, **payload})
    except PermissionError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 403
    except ValueError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 400
    except Exception:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500


@social_posts_bp.route("/api/business/<business_id>/social-posts/api-channel-preflight", methods=["GET"])
def social_posts_api_channel_preflight(business_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    try:
        payload = check_social_api_channel_preflight(str(user_data.get("user_id") or ""), business_id)
        return jsonify({"success": True, **payload})
    except PermissionError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 403
    except ValueError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 400
    except Exception:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500


@social_posts_bp.route("/api/business/<business_id>/social-posts/openclaw-browser-check", methods=["GET"])
def social_posts_openclaw_browser_check(business_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    try:
        payload = check_social_openclaw_browser_readiness(str(user_data.get("user_id") or ""), business_id)
        return jsonify({"success": True, **payload})
    except PermissionError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 403
    except ValueError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 400
    except Exception:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500


@social_posts_bp.route("/api/business/<business_id>/social-posts/launch-preflight", methods=["GET"])
def social_posts_launch_preflight(business_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    try:
        payload = get_social_launch_preflight(
            str(user_data.get("user_id") or ""),
            business_id,
            batch_size=_int_env("SOCIAL_POST_PREFLIGHT_BATCH_SIZE", 10),
        )
        return jsonify({"success": True, **payload})
    except PermissionError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 403
    except ValueError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 400
    except Exception:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500


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
            batch_size=_bounded_int_payload(data, "batch_size", 20, 1, 50),
            business_id=str(data.get("business_id") or ""),
        )
        return jsonify({"success": True, **payload})
    except PermissionError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 403
    except ValueError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 400
    except Exception:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500


@social_posts_bp.route("/api/social-posts/dispatch/run-once", methods=["POST"])
def social_posts_dispatch_run_once():
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    rate_error = _check_write_rate_limit(str(user_data.get("user_id") or ""), "dispatch-run-once")
    if rate_error:
        return rate_error
    data = request.get_json(silent=True) or {}
    if not bool(data.get("approved")):
        return jsonify({"success": False, "error": "Для запуска первого цикла публикаций нужно явное подтверждение"}), 403
    try:
        payload = run_scoped_social_dispatch_once(
            str(user_data.get("user_id") or ""),
            business_id=str(data.get("business_id") or ""),
            batch_size=_bounded_int_payload(data, "batch_size", 10, 1, 50),
            approved=bool(data.get("approved")),
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


@social_posts_bp.route("/api/social-posts/<post_id>/mark-supervised-blocked", methods=["POST"])
def social_posts_mark_supervised_blocked(post_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    rate_error = _check_write_rate_limit(str(user_data.get("user_id") or ""), "supervised-blocked")
    if rate_error:
        return rate_error
    data = request.get_json(silent=True) or {}
    try:
        post = mark_supervised_publish_blocked(
            str(user_data.get("user_id") or ""),
            post_id,
            reason=str(data.get("reason") or "").strip(),
            blocked_source=str(data.get("blocked_source") or "manual").strip(),
        )
        return jsonify({"success": True, "post": post})
    except PermissionError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 403
    except ValueError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 400
    except Exception:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500


@social_posts_bp.route("/api/social-posts/<post_id>/supervised-task", methods=["POST"])
def social_posts_create_supervised_task(post_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    rate_error = _check_write_rate_limit(str(user_data.get("user_id") or ""), "supervised-task")
    if rate_error:
        return rate_error
    data = request.get_json(silent=True) or {}
    if not bool(data.get("approved")):
        return jsonify({"success": False, "error": "Для создания контролируемой задачи нужно явное подтверждение"}), 403
    try:
        post = create_supervised_publish_task(
            str(user_data.get("user_id") or ""),
            post_id,
            approved=bool(data.get("approved")),
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


@social_posts_bp.route("/api/social-posts/metrics/run-once", methods=["POST"])
def social_posts_metrics_run_once():
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    rate_error = _check_write_rate_limit(str(user_data.get("user_id") or ""), "metrics-run-once")
    if rate_error:
        return rate_error
    data = request.get_json(silent=True) or {}
    if not bool(data.get("approved")):
        return jsonify({"success": False, "error": "Для сбора реакций нужно явное подтверждение"}), 403
    try:
        payload = run_scoped_social_metrics_once(
            str(user_data.get("user_id") or ""),
            business_id=str(data.get("business_id") or ""),
            batch_size=_bounded_int_payload(data, "batch_size", 25, 1, 100),
            approved=bool(data.get("approved")),
        )
        return jsonify({"success": True, **payload})
    except PermissionError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 403
    except ValueError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 400
    except Exception:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 500
