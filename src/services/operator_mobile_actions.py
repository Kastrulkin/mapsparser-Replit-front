from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable


MOBILE_ACTION_TTL_MINUTES = 15
MOBILE_ACTIONS = {
    "review_replies.generate": {"estimated_credits_per_item": 1, "external_effects": False},
    "review_replies.mark_manual_published": {"estimated_credits_per_item": 0, "external_effects": False},
}


def _row(cursor: Any, value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "keys"):
        return dict(value)
    columns = [item[0] for item in (getattr(cursor, "description", None) or [])]
    return {columns[index]: value[index] for index in range(min(len(columns), len(value)))}


def _json(value: Any, fallback: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return fallback
    return fallback


def _resolve_review_targets(cursor: Any, scope: dict[str, Any], review_ids: list[str]) -> tuple[list[str], list[dict[str, Any]]]:
    clean_ids = list(dict.fromkeys(str(item).strip() for item in review_ids if str(item).strip()))[:5]
    if not clean_ids:
        return [], []
    cursor.execute(
        """
        SELECT reviews.id, reviews.business_id, businesses.name AS business_name,
               reviews.author_name, reviews.rating, reviews.source
        FROM externalbusinessreviews reviews
        JOIN businesses ON businesses.id = reviews.business_id
        WHERE reviews.id = ANY(%s)
        ORDER BY reviews.published_at DESC NULLS LAST, reviews.created_at DESC
        """,
        (clean_ids,),
    )
    rows = [_row(cursor, item) for item in (cursor.fetchall() or [])]
    allowed = {str(item) for item in scope.get("business_ids") or []}
    if scope.get("kind") != "platform" and any(str(item.get("business_id") or "") not in allowed for item in rows):
        return [], []
    if len(rows) != len(clean_ids):
        return [], []
    targets = list(dict.fromkeys(str(item.get("business_id") or "") for item in rows if item.get("business_id")))
    return targets, rows


def create_mobile_action_preview(
    cursor: Any,
    *,
    user_id: str,
    scope: dict[str, Any],
    capability: str,
    input_payload: dict[str, Any],
) -> dict[str, Any]:
    spec = MOBILE_ACTIONS.get(capability)
    if not spec:
        return {"status": "blocked", "blocked_reasons": ["unsupported_mobile_action"]}
    review_ids = input_payload.get("review_ids") if isinstance(input_payload.get("review_ids"), list) else []
    targets, objects = _resolve_review_targets(cursor, scope, review_ids)
    if not objects:
        return {"status": "blocked", "blocked_reasons": ["objects_not_found_or_forbidden"]}
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=MOBILE_ACTION_TTL_MINUTES)
    stable_input = json.dumps(
        {"scope_type": scope.get("kind"), "scope_id": scope.get("id"), "capability": capability, "review_ids": review_ids},
        ensure_ascii=False,
        sort_keys=True,
    )
    idempotency_key = hashlib.sha256(f"{user_id}|{stable_input}".encode("utf-8")).hexdigest()[:32]
    action_id = str(uuid.uuid4())
    estimated = int(spec.get("estimated_credits_per_item") or 0) * len(objects)
    preview = {
        "capability": capability,
        "scope": scope,
        "target_businesses": [{"id": item, "name": next((str(row.get("business_name") or "") for row in objects if str(row.get("business_id")) == item), "")} for item in targets],
        "objects": objects,
        "changes": [{"review_id": item.get("id"), "operation": capability} for item in objects],
        "estimated_credits": estimated,
        "external_effects": bool(spec.get("external_effects")),
        "is_mass_action": len(objects) > 1 or len(targets) > 1,
        "confirmation_required": True,
        "expires_at": expires_at.isoformat(),
    }
    cursor.execute(
        """
        INSERT INTO operatoractions (
            id, conversation_id, business_id, user_id, capability, idempotency_key,
            envelope_json, scope_type, scope_id, target_business_ids_json, preview_json,
            estimated_credits, external_effects, is_mass_action, expires_at
        )
        VALUES (%s, NULL, %s, %s, %s, %s, %s::jsonb, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s, %s)
        ON CONFLICT (user_id, idempotency_key)
        DO UPDATE SET preview_json = EXCLUDED.preview_json, expires_at = EXCLUDED.expires_at, updated_at = NOW()
        RETURNING id, status, idempotency_key
        """,
        (
            action_id,
            targets[0] if len(targets) == 1 else None,
            user_id,
            capability,
            idempotency_key,
            json.dumps({"review_ids": [str(item.get("id") or "") for item in objects]}, ensure_ascii=False),
            str(scope.get("kind") or "business"),
            str(scope.get("id") or "") or None,
            json.dumps(targets),
            json.dumps(preview, ensure_ascii=False, default=str),
            estimated,
            bool(spec.get("external_effects")),
            bool(preview["is_mass_action"]),
            expires_at,
        ),
    )
    stored = _row(cursor, cursor.fetchone())
    return {"status": "preview", "action_id": stored.get("id") or action_id, "idempotency_key": idempotency_key, **preview}


def confirm_mobile_action(
    cursor: Any,
    *,
    action_id: str,
    user_id: str,
    scope_resolver: Callable[[str, str | None], dict[str, Any] | None],
    executors: dict[str, Callable[[dict[str, Any], list[str], dict[str, Any]], dict[str, Any]]],
) -> tuple[dict[str, Any], bool]:
    cursor.execute("SELECT * FROM operatoractions WHERE id = %s AND user_id = %s FOR UPDATE", (action_id, user_id))
    action = _row(cursor, cursor.fetchone())
    if not action:
        return {"status": "blocked", "blocked_reasons": ["action_not_found"]}, False
    if str(action.get("status") or "") == "completed":
        return _json(action.get("result_json"), {}), True
    expires_at = action.get("expires_at")
    if expires_at and expires_at < datetime.now(timezone.utc):
        return {"status": "blocked", "blocked_reasons": ["preview_expired"]}, False
    scope = scope_resolver(str(action.get("scope_type") or "business"), str(action.get("scope_id") or "") or None)
    if not scope:
        return {"status": "blocked", "blocked_reasons": ["scope_forbidden"]}, False
    stored_targets = [str(item) for item in _json(action.get("target_business_ids_json"), [])]
    allowed_targets = {str(item) for item in scope.get("business_ids") or []}
    if scope.get("kind") != "platform" and any(item not in allowed_targets for item in stored_targets):
        return {"status": "blocked", "blocked_reasons": ["targets_changed"]}, False
    capability = str(action.get("capability") or "")
    executor = executors.get(capability)
    if not executor:
        return {"status": "blocked", "blocked_reasons": ["confirm_handler_unavailable"]}, False
    envelope = _json(action.get("envelope_json"), {})
    result = executor(envelope, stored_targets, scope)
    if str(result.get("status") or "") != "completed":
        return result, False
    cursor.execute(
        """
        UPDATE operatoractions
        SET status = 'completed', confirmed_at = COALESCE(confirmed_at, NOW()),
            executed_at = COALESCE(executed_at, NOW()), result_json = %s::jsonb, updated_at = NOW()
        WHERE id = %s
        """,
        (json.dumps(result, ensure_ascii=False, default=str), action_id),
    )
    return result, False
