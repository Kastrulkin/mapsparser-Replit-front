from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from core.service_catalog_compression import build_service_catalog_compression_draft


MOBILE_ACTION_TTL_MINUTES = 15
MOBILE_ACTIONS = {
    "review_replies.generate": {"estimated_credits_per_item": 1, "external_effects": False},
    "finance.sales_import": {"estimated_credits_per_item": 0, "external_effects": False},
    "finance.transaction.delete": {"estimated_credits_per_item": 0, "external_effects": False},
    "cards.schedule.update": {"estimated_credits_per_item": 0, "external_effects": False},
    "content.plan.delete": {"estimated_credits_per_item": 0, "external_effects": False},
    "services.optimize": {"estimated_credits_per_item": 1, "external_effects": False},
    "services.compress": {"estimated_credits_per_item": 0, "external_effects": False},
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


def _requested_business_id(scope: dict[str, Any], input_payload: dict[str, Any]) -> str:
    if scope.get("kind") == "business":
        return str(scope.get("id") or "")
    return str(input_payload.get("business_id") or "").strip()


def _business_allowed(scope: dict[str, Any], business_id: str) -> bool:
    if scope.get("kind") == "platform":
        return bool(business_id)
    return business_id in {str(item) for item in scope.get("business_ids") or []}


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
    envelope: dict[str, Any]
    changes: list[dict[str, Any]] = []
    preview_extras: dict[str, Any] = {}
    if capability == "finance.sales_import":
        requested_business_id = _requested_business_id(scope, input_payload)
        if not _business_allowed(scope, requested_business_id):
            return {"status": "blocked", "blocked_reasons": ["business_selection_required"]}
        cursor.execute("SELECT id, name FROM businesses WHERE id = %s", (requested_business_id,))
        business = _row(cursor, cursor.fetchone())
        raw_transactions = input_payload.get("transactions") if isinstance(input_payload.get("transactions"), list) else []
        transactions = []
        for item in raw_transactions[:100]:
            if not isinstance(item, dict):
                continue
            try:
                amount = float(item.get("amount") or 0)
            except (TypeError, ValueError):
                amount = 0
            if amount <= 0:
                continue
            sale_type = str(item.get("sale_type") or "service").strip().lower()
            if sale_type not in {"service", "upsell", "cross_sell"}:
                sale_type = "service"
            transactions.append({
                "id": str(item.get("id") or uuid.uuid4()),
                "transaction_date": str(item.get("transaction_date") or "").strip(),
                "amount": amount,
                "sale_type": sale_type,
                "title": str(item.get("title") or item.get("service") or "Продажа").strip() or "Продажа",
                "notes": str(item.get("notes") or "").strip(),
            })
        if not business or not transactions:
            return {"status": "blocked", "blocked_reasons": ["transactions_not_found_or_forbidden"]}
        targets = [requested_business_id]
        objects = [
            {**item, "business_id": requested_business_id, "business_name": str(business.get("name") or "")}
            for item in transactions
        ]
        envelope = {"transactions": transactions, "business_id": requested_business_id}
    elif capability == "finance.transaction.delete":
        transaction_id = str(input_payload.get("transaction_id") or "").strip()
        requested_business_id = _requested_business_id(scope, input_payload)
        if not transaction_id or not _business_allowed(scope, requested_business_id):
            return {"status": "blocked", "blocked_reasons": ["transaction_not_found_or_forbidden"]}
        cursor.execute(
            """
            SELECT transaction.id, transaction.business_id, transaction.amount,
                   transaction.transaction_date, transaction.description, business.name AS business_name
            FROM financialtransactions transaction
            JOIN businesses business ON business.id = transaction.business_id
            WHERE transaction.id = %s AND transaction.business_id = %s
            """,
            (transaction_id, requested_business_id),
        )
        transaction = _row(cursor, cursor.fetchone())
        if not transaction:
            return {"status": "blocked", "blocked_reasons": ["transaction_not_found_or_forbidden"]}
        targets = [requested_business_id]
        objects = [transaction]
        envelope = {"transaction_id": transaction_id, "business_id": requested_business_id}
        changes = [{"object_id": transaction_id, "operation": capability, "label": "Удалить финансовую операцию"}]
    elif capability == "cards.schedule.update":
        requested_business_id = _requested_business_id(scope, input_payload)
        if not _business_allowed(scope, requested_business_id):
            return {"status": "blocked", "blocked_reasons": ["business_selection_required"]}
        cursor.execute("SELECT id, name FROM businesses WHERE id = %s", (requested_business_id,))
        business = _row(cursor, cursor.fetchone())
        try:
            interval_hours = max(24, min(24 * 30, int(input_payload.get("interval_hours") or 24)))
        except (TypeError, ValueError):
            return {"status": "blocked", "blocked_reasons": ["invalid_schedule"]}
        if not business:
            return {"status": "blocked", "blocked_reasons": ["business_not_found_or_forbidden"]}
        enabled = bool(input_payload.get("enabled"))
        targets = [requested_business_id]
        objects = [{"id": requested_business_id, "business_id": requested_business_id, "business_name": str(business.get("name") or ""), "enabled": enabled, "interval_hours": interval_hours}]
        envelope = {"business_id": requested_business_id, "enabled": enabled, "interval_hours": interval_hours}
        changes = [{"object_id": requested_business_id, "operation": capability, "label": "Включить проверку карточек" if enabled else "Выключить проверку карточек", "interval_hours": interval_hours}]
    elif capability == "content.plan.delete":
        plan_id = str(input_payload.get("plan_id") or "").strip()
        if not plan_id:
            return {"status": "blocked", "blocked_reasons": ["plan_required"]}
        cursor.execute(
            """
            SELECT plan.id, plan.business_id, plan.title, business.name AS business_name,
                   COUNT(item.id) AS items_count
            FROM contentplans plan
            JOIN businesses business ON business.id = plan.business_id
            LEFT JOIN contentplanitems item ON item.plan_id = plan.id
            WHERE plan.id = %s
            GROUP BY plan.id, business.name
            """,
            (plan_id,),
        )
        plan = _row(cursor, cursor.fetchone())
        plan_business_id = str(plan.get("business_id") or "")
        if not plan or not _business_allowed(scope, plan_business_id):
            return {"status": "blocked", "blocked_reasons": ["plan_not_found_or_forbidden"]}
        targets = [plan_business_id]
        objects = [{**plan, "id": plan_id}]
        envelope = {"plan_id": plan_id, "business_id": plan_business_id}
        changes = [{"object_id": plan_id, "operation": capability, "label": "Удалить контент-план", "items_count": int(plan.get("items_count") or 0)}]
    elif capability in {"services.optimize", "services.compress"}:
        requested_business_id = _requested_business_id(scope, input_payload)
        if not _business_allowed(scope, requested_business_id):
            return {"status": "blocked", "blocked_reasons": ["business_selection_required"]}
        cursor.execute("SELECT id, name FROM businesses WHERE id = %s", (requested_business_id,))
        business = _row(cursor, cursor.fetchone())
        cursor.execute(
            """
            SELECT id, business_id, name, description, category, price
            FROM userservices
            WHERE business_id = %s AND COALESCE(is_active, TRUE)
            ORDER BY category, name
            LIMIT 100
            """,
            (requested_business_id,),
        )
        services = [_row(cursor, item) for item in (cursor.fetchall() or [])]
        if not business or not services:
            return {"status": "blocked", "blocked_reasons": ["services_not_found_or_forbidden"]}
        targets = [requested_business_id]
        objects = [{**item, "business_name": str(business.get("name") or "")} for item in services]
        envelope = {
            "business_id": requested_business_id,
            "service_ids": [str(item.get("id") or "") for item in services],
            "request_id": str(input_payload.get("request_id") or "").strip()[:100],
        }
        if capability == "services.compress":
            preview_extras["analysis"] = build_service_catalog_compression_draft(services)
            changes = [{"object_id": item.get("id"), "operation": capability, "label": str(item.get("name") or "Услуга")} for item in services]
        else:
            changes = [{"object_id": item.get("id"), "operation": capability, "label": f"Подготовить улучшение: {item.get('name') or 'услуга'}"} for item in services]
    else:
        targets, objects = _resolve_review_targets(cursor, scope, review_ids)
        envelope = {"review_ids": [str(item.get("id") or "") for item in objects]}
    if not objects:
        return {"status": "blocked", "blocked_reasons": ["objects_not_found_or_forbidden"]}
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=MOBILE_ACTION_TTL_MINUTES)
    stable_input = json.dumps(
        {"scope_type": scope.get("kind"), "scope_id": scope.get("id"), "capability": capability, "input": envelope},
        ensure_ascii=False,
        sort_keys=True,
    )
    idempotency_key = hashlib.sha256(f"{user_id}|{stable_input}".encode("utf-8")).hexdigest()[:32]
    action_id = str(uuid.uuid4())
    estimated = int(spec.get("estimated_credits_per_item") or 0) * len(objects)
    preview = {
        "capability": capability,
        "scope": scope,
        "target_businesses": [{"id": item, "name": next((str(row.get("business_name") or "") for row in objects if str(row.get("business_id") or item) == item), "")} for item in targets],
        "objects": objects,
        "changes": changes or [{"object_id": item.get("id"), "operation": capability} for item in objects],
        "estimated_credits": estimated,
        "external_effects": bool(spec.get("external_effects")),
        "is_mass_action": len(objects) > 1 or len(targets) > 1,
        "confirmation_required": True,
        "expires_at": expires_at.isoformat(),
        **preview_extras,
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
            json.dumps(envelope, ensure_ascii=False),
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
