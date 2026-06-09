from __future__ import annotations

import json
import hashlib
from typing import Any, Dict, List

from core.agent_api_security import log_agent_action


APPROVED_EXECUTOR_REASON = "HUMAN_APPROVED_CONTROLLED_EXECUTOR"


def execute_approved_domain_requests(
    cursor: Any,
    *,
    run: Dict[str, Any],
    step: Dict[str, Any],
    orchestrator_result: Dict[str, Any],
    user_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Move capability-created domain requests into their post-approval execution state.

    Handlers create request records only. This layer runs after the blueprint human
    gate and records a controlled execution handoff without provider writes.
    """
    refs = _extract_refs(orchestrator_result)
    business_id = str(run.get("business_id") or "").strip()
    if not business_id:
        return _empty_result()
    user_id = str(user_data.get("user_id") or user_data.get("id") or "").strip()
    run_id = str(run.get("id") or "").strip()
    step_key = str(step.get("key") or "").strip()
    items: List[Dict[str, Any]] = []
    items.extend(_approve_sheet_requests(cursor, business_id, user_id, run_id, step_key, refs))
    items.extend(_approve_communication_requests(cursor, business_id, user_id, run_id, step_key, refs))
    items.extend(_approve_review_publish_requests(cursor, business_id, user_id, run_id, step_key, refs))
    items.extend(_approve_service_optimization_requests(cursor, business_id, user_id, run_id, step_key, refs))
    return {
        "executor": "agent_domain_request_executor_v1",
        "executed": len(items),
        "items": items,
        "external_dispatch_performed": False,
        "provider_writes_performed": False,
        "reason_code": APPROVED_EXECUTOR_REASON,
    }


def _empty_result() -> Dict[str, Any]:
    return {
        "executor": "agent_domain_request_executor_v1",
        "executed": 0,
        "items": [],
        "external_dispatch_performed": False,
        "provider_writes_performed": False,
        "reason_code": "NO_DOMAIN_REQUESTS",
    }


def _extract_refs(orchestrator_result: Dict[str, Any]) -> Dict[str, List[str]]:
    result = orchestrator_result.get("result") if isinstance(orchestrator_result.get("result"), dict) else {}
    refs = {
        "action_ids": [],
        "request_ids": [],
        "draft_ids": [],
        "review_ids": [],
    }
    candidates = {
        "action_ids": [orchestrator_result.get("action_id"), result.get("action_id")],
        "request_ids": [result.get("request_id")],
        "draft_ids": [result.get("draft_id")],
        "review_ids": [result.get("review_id")],
    }
    for key, values in candidates.items():
        for value in values:
            text = str(value or "").strip()
            if text and text not in refs[key]:
                refs[key].append(text)
    return refs


def _table_exists(cursor: Any, table_name: str) -> bool:
    try:
        cursor.execute("SELECT to_regclass(%s)", (table_name,))
        row = cursor.fetchone()
    except Exception:
        return False
    if not row:
        return False
    if isinstance(row, dict):
        return bool(row.get("to_regclass") or row.get("table_name"))
    if isinstance(row, (tuple, list)):
        return bool(row[0])
    return bool(row)


def _fetch_rows(cursor: Any, table_name: str, query: str, params: tuple[Any, ...], has_refs: bool) -> List[Dict[str, Any]]:
    if not has_refs or not _table_exists(cursor, table_name):
        return []
    cursor.execute(query, params)
    return [dict(row) for row in (cursor.fetchall() or [])]


def _approve_sheet_requests(cursor: Any, business_id: str, user_id: str, run_id: str, step_key: str, refs: Dict[str, List[str]]) -> List[Dict[str, Any]]:
    rows = _fetch_rows(
        cursor,
        "agent_sheet_operation_requests",
        """
        SELECT id, action_id, status, approval_state, apply_state, operation, sheet_name,
               provider_write_performed
        FROM agent_sheet_operation_requests
        WHERE business_id = %s AND (id = ANY(%s) OR action_id = ANY(%s))
        """,
        (business_id, refs.get("request_ids") or [], refs.get("action_ids") or []),
        bool(refs.get("request_ids") or refs.get("action_ids")),
    )
    items = []
    for row in rows:
        if bool(row.get("provider_write_performed")):
            continue
        cursor.execute(
            """
            UPDATE agent_sheet_operation_requests
            SET status = 'approved_for_execution',
                approval_state = 'approved',
                apply_state = 'approved_not_applied',
                updated_at = NOW()
            WHERE id = %s AND business_id = %s AND provider_write_performed = FALSE
            """,
            (row.get("id"), business_id),
        )
        ledger_id = _record_executor_ledger(
            cursor,
            business_id=business_id,
            user_id=user_id,
            run_id=run_id,
            step_key=step_key,
            request_id=str(row.get("id") or ""),
            action_id=str(row.get("action_id") or ""),
            capability="sheets.append_row_request",
            output_state="approved_not_applied",
            summary={"operation": row.get("operation"), "sheet_name": row.get("sheet_name")},
        )
        items.append(
            {
                "kind": "sheet_operation_request",
                "id": row.get("id"),
                "action_id": row.get("action_id"),
                "status": "approved_for_execution",
                "approval_state": "approved",
                "apply_state": "approved_not_applied",
                "ledger_id": ledger_id,
                "provider_write_performed": False,
            }
        )
    return items


def _approve_communication_requests(cursor: Any, business_id: str, user_id: str, run_id: str, step_key: str, refs: Dict[str, List[str]]) -> List[Dict[str, Any]]:
    rows = _fetch_rows(
        cursor,
        "agent_communication_requests",
        """
        SELECT id, action_id, capability, message_type, status, channel, recipient_count,
               recipients_json, message_template, limits_json, consent_json, delivery_state
        FROM agent_communication_requests
        WHERE business_id = %s AND (id = ANY(%s) OR action_id = ANY(%s))
        """,
        (business_id, refs.get("request_ids") or [], refs.get("action_ids") or []),
        bool(refs.get("request_ids") or refs.get("action_ids")),
    )
    if not rows:
        return []
    _ensure_communication_delivery_journal(cursor)
    items = []
    for row in rows:
        handoff = _create_communication_delivery_journal_rows(cursor, business_id, user_id, run_id, row)
        delivery_state = "queued_for_dispatch" if handoff.get("queued_count") else "blocked_by_consent"
        cursor.execute(
            """
            UPDATE agent_communication_requests
            SET status = 'approved_for_dispatch',
                delivery_state = %s,
                updated_at = NOW()
            WHERE id = %s AND business_id = %s AND delivery_state <> 'dispatched'
            """,
            (delivery_state, row.get("id"), business_id),
        )
        capability = str(row.get("capability") or "communications.send_reminder")
        ledger_id = _record_executor_ledger(
            cursor,
            business_id=business_id,
            user_id=user_id,
            run_id=run_id,
            step_key=step_key,
            request_id=str(row.get("id") or ""),
            action_id=str(row.get("action_id") or ""),
            capability=capability,
            output_state=delivery_state,
            summary={
                "channel": row.get("channel"),
                "recipient_count": row.get("recipient_count"),
                "queued_count": handoff.get("queued_count"),
                "blocked_count": handoff.get("blocked_count"),
            },
        )
        items.append(
            {
                "kind": "communication_request",
                "id": row.get("id"),
                "action_id": row.get("action_id"),
                "status": "approved_for_dispatch",
                "delivery_state": delivery_state,
                "queued_count": handoff.get("queued_count"),
                "blocked_count": handoff.get("blocked_count"),
                "ledger_id": ledger_id,
                "provider_write_performed": False,
            }
        )
    return items


def _ensure_communication_delivery_journal(cursor: Any) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_communication_delivery_journal (
            id TEXT PRIMARY KEY,
            request_id TEXT NOT NULL,
            action_id TEXT,
            business_id TEXT NOT NULL,
            run_id TEXT,
            user_id TEXT,
            recipient_key TEXT NOT NULL,
            channel TEXT,
            message_template TEXT,
            status TEXT NOT NULL,
            delivery_state TEXT NOT NULL,
            consent_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            limits_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            router_handoff_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            provider_write_performed BOOLEAN NOT NULL DEFAULT FALSE,
            error_text TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_communication_delivery_request_recipient
        ON agent_communication_delivery_journal(request_id, recipient_key)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_agent_communication_delivery_business_state
        ON agent_communication_delivery_journal(business_id, delivery_state, created_at DESC)
        """
    )


def _create_communication_delivery_journal_rows(
    cursor: Any,
    business_id: str,
    user_id: str,
    run_id: str,
    row: Dict[str, Any],
) -> Dict[str, Any]:
    request_id = str(row.get("id") or "").strip()
    action_id = str(row.get("action_id") or "").strip()
    channel = str(row.get("channel") or "manual").strip()
    message_template = str(row.get("message_template") or "").strip()
    message_type = str(row.get("message_type") or "").strip()
    recipients = _decode_json(row.get("recipients_json"), [])
    limits = _decode_json(row.get("limits_json"), {})
    consent_policy = _decode_json(row.get("consent_json"), {})
    if not isinstance(recipients, list):
        recipients = []
    daily_cap = _positive_int(limits.get("daily_cap"), 10)
    queued_count = 0
    blocked_count = 0
    for recipient in recipients[:daily_cap]:
        recipient_payload = recipient if isinstance(recipient, dict) else {"value": recipient}
        recipient_key = _communication_recipient_key(recipient_payload)
        if not recipient_key:
            blocked_count += 1
            continue
        recipient_consent = recipient_payload.get("consent") if isinstance(recipient_payload.get("consent"), dict) else {}
        requires_marketing = bool(consent_policy.get("required")) or message_type == "package_offer"
        consent_ok = bool(recipient_consent.get("marketing")) if requires_marketing else bool(recipient_consent.get("transactional") is not False)
        delivery_state = "queued_for_dispatch" if consent_ok else "blocked_by_consent"
        status = "queued" if consent_ok else "blocked"
        if consent_ok:
            queued_count += 1
        else:
            blocked_count += 1
        cursor.execute(
            """
            INSERT INTO agent_communication_delivery_journal (
                id, request_id, action_id, business_id, run_id, user_id, recipient_key,
                channel, message_template, status, delivery_state, consent_json,
                limits_json, router_handoff_json, provider_write_performed
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, FALSE)
            ON CONFLICT (request_id, recipient_key) DO UPDATE SET
                status = EXCLUDED.status,
                delivery_state = EXCLUDED.delivery_state,
                consent_json = EXCLUDED.consent_json,
                limits_json = EXCLUDED.limits_json,
                router_handoff_json = EXCLUDED.router_handoff_json,
                provider_write_performed = FALSE,
                updated_at = NOW()
            """,
            (
                _stable_delivery_id(request_id, recipient_key),
                request_id,
                action_id,
                business_id,
                run_id,
                user_id,
                recipient_key,
                channel,
                message_template,
                status,
                delivery_state,
                json.dumps(recipient_consent or {}, ensure_ascii=False),
                json.dumps(limits or {}, ensure_ascii=False),
                json.dumps(
                    {
                        "router": "localos_channel_router",
                        "handoff_state": delivery_state,
                        "channel": channel,
                        "recipient": recipient_payload,
                        "external_dispatch_performed": False,
                    },
                    ensure_ascii=False,
                ),
            ),
        )
    if len(recipients) > daily_cap:
        blocked_count += len(recipients) - daily_cap
    return {
        "queued_count": queued_count,
        "blocked_count": blocked_count,
        "daily_cap": daily_cap,
    }


def _communication_recipient_key(recipient: Dict[str, Any]) -> str:
    for key in ("client_id", "client_phone", "phone", "telegram_user_id", "email", "value"):
        value = str(recipient.get(key) or "").strip()
        if value:
            return value
    return ""


def _stable_delivery_id(request_id: str, recipient_key: str) -> str:
    raw = f"{request_id}|{recipient_key}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value or default)
    except Exception:
        parsed = default
    return max(1, min(parsed, 100))


def _approve_review_publish_requests(cursor: Any, business_id: str, user_id: str, run_id: str, step_key: str, refs: Dict[str, List[str]]) -> List[Dict[str, Any]]:
    rows = _fetch_rows(
        cursor,
        "reviewreplydrafts",
        """
        SELECT id, review_id, status, source, generated_text, edited_text, tone
        FROM reviewreplydrafts
        WHERE business_id = %s AND (id = ANY(%s) OR review_id = ANY(%s))
        """,
        (business_id, refs.get("draft_ids") or refs.get("request_ids") or [], refs.get("review_ids") or []),
        bool(refs.get("draft_ids") or refs.get("request_ids") or refs.get("review_ids")),
    )
    if not rows:
        return []
    _ensure_review_publish_requests(cursor)
    items = []
    for row in rows:
        reply_text = str(row.get("edited_text") or row.get("generated_text") or "").strip()
        if not reply_text:
            continue
        cursor.execute(
            """
            UPDATE reviewreplydrafts
            SET status = 'approved_for_publish',
                updated_at = NOW()
            WHERE id = %s AND business_id = %s AND status IN ('publish_requested', 'generated', 'edited', 'pending_review')
            """,
            (row.get("id"), business_id),
        )
        publish_request_id = _stable_review_publish_request_id(str(row.get("id") or ""))
        provider_request = {
            "provider_executor": "manual_controlled_review_reply_publisher",
            "publish_mode": "controlled_request_only",
            "source": row.get("source"),
            "review_id": row.get("review_id"),
            "draft_id": row.get("id"),
            "provider_write_performed": False,
        }
        audit_payload = {
            "approval_reason": APPROVED_EXECUTOR_REASON,
            "run_id": run_id,
            "step_key": step_key,
            "approved_by_user_id": user_id,
            "tone": row.get("tone"),
        }
        cursor.execute(
            """
            INSERT INTO agent_review_publish_requests (
                id, draft_id, review_id, business_id, run_id, user_id, source, reply_text,
                status, publish_state, provider_request_json, audit_json, provider_write_performed
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'provider_publish_requested',
                    'provider_request_queued', %s, %s, FALSE)
            ON CONFLICT (draft_id) DO UPDATE SET
                review_id = EXCLUDED.review_id,
                run_id = EXCLUDED.run_id,
                user_id = EXCLUDED.user_id,
                source = EXCLUDED.source,
                reply_text = EXCLUDED.reply_text,
                status = EXCLUDED.status,
                publish_state = EXCLUDED.publish_state,
                provider_request_json = EXCLUDED.provider_request_json,
                audit_json = EXCLUDED.audit_json,
                provider_write_performed = FALSE,
                updated_at = NOW()
            """,
            (
                publish_request_id,
                row.get("id"),
                row.get("review_id"),
                business_id,
                run_id,
                user_id,
                row.get("source"),
                reply_text,
                json.dumps(provider_request, ensure_ascii=False),
                json.dumps(audit_payload, ensure_ascii=False),
            ),
        )
        ledger_id = _record_executor_ledger(
            cursor,
            business_id=business_id,
            user_id=user_id,
            run_id=run_id,
            step_key=step_key,
            request_id=str(row.get("id") or ""),
            action_id="",
            capability="reviews.reply.publish_request",
            output_state="provider_request_queued",
            summary={
                "review_id": row.get("review_id"),
                "source": row.get("source"),
                "publish_request_id": publish_request_id,
            },
        )
        items.append(
            {
                "kind": "review_publish_request",
                "id": row.get("id"),
                "review_id": row.get("review_id"),
                "status": "approved_for_publish",
                "publish_request_id": publish_request_id,
                "publish_state": "provider_request_queued",
                "ledger_id": ledger_id,
                "provider_write_performed": False,
            }
        )
    return items


def _ensure_review_publish_requests(cursor: Any) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_review_publish_requests (
            id TEXT PRIMARY KEY,
            draft_id TEXT NOT NULL,
            review_id TEXT NOT NULL,
            business_id TEXT NOT NULL,
            run_id TEXT,
            user_id TEXT,
            source TEXT,
            reply_text TEXT NOT NULL,
            status TEXT NOT NULL,
            publish_state TEXT NOT NULL,
            provider_request_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            audit_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            provider_write_performed BOOLEAN NOT NULL DEFAULT FALSE,
            error_text TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_review_publish_requests_draft
        ON agent_review_publish_requests(draft_id)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_agent_review_publish_requests_business_state
        ON agent_review_publish_requests(business_id, publish_state, created_at DESC)
        """
    )


def _stable_review_publish_request_id(draft_id: str) -> str:
    raw = f"agent_review_publish_request|{draft_id}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _approve_service_optimization_requests(cursor: Any, business_id: str, user_id: str, run_id: str, step_key: str, refs: Dict[str, List[str]]) -> List[Dict[str, Any]]:
    rows = _fetch_rows(
        cursor,
        "agent_service_optimization_requests",
        """
        SELECT id, action_id, status, service_count, suggestions_json, diff_json, apply_state
        FROM agent_service_optimization_requests
        WHERE business_id = %s AND (id = ANY(%s) OR action_id = ANY(%s))
        """,
        (business_id, refs.get("request_ids") or [], refs.get("action_ids") or []),
        bool(refs.get("request_ids") or refs.get("action_ids")),
    )
    items = []
    for row in rows:
        suggestions = _decode_json(row.get("suggestions_json"), [])
        apply_result = _apply_service_suggestions(cursor, business_id, suggestions)
        apply_state = "applied" if apply_result.get("applied_count") else "apply_ready"
        status = "applied" if apply_result.get("applied_count") else "approved_for_apply"
        cursor.execute(
            """
            UPDATE agent_service_optimization_requests
            SET status = %s,
                apply_state = %s,
                updated_at = NOW()
            WHERE id = %s AND business_id = %s AND apply_state <> 'applied'
            """,
            (status, apply_state, row.get("id"), business_id),
        )
        ledger_id = _record_executor_ledger(
            cursor,
            business_id=business_id,
            user_id=user_id,
            run_id=run_id,
            step_key=step_key,
            request_id=str(row.get("id") or ""),
            action_id=str(row.get("action_id") or ""),
            capability="services.optimize",
            output_state=apply_state,
            summary={
                "service_count": row.get("service_count"),
                "applied_count": apply_result.get("applied_count"),
                "skipped_count": apply_result.get("skipped_count"),
            },
        )
        items.append(
            {
                "kind": "service_optimization_request",
                "id": row.get("id"),
                "action_id": row.get("action_id"),
                "status": status,
                "apply_state": apply_state,
                "applied_count": apply_result.get("applied_count"),
                "skipped_count": apply_result.get("skipped_count"),
                "ledger_id": ledger_id,
                "provider_write_performed": False,
            }
        )
    return items


def _decode_json(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return fallback
    return fallback


def _table_columns(cursor: Any, table_name: str) -> set[str]:
    cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND lower(table_name) = %s
        """,
        (str(table_name).lower(),),
    )
    columns = set()
    for row in cursor.fetchall() or []:
        value = row.get("column_name") if isinstance(row, dict) else row[0]
        if value:
            columns.add(str(value).lower())
    return columns


def _apply_service_suggestions(cursor: Any, business_id: str, suggestions: Any) -> Dict[str, Any]:
    if not isinstance(suggestions, list) or not _table_exists(cursor, "userservices"):
        return {"applied_count": 0, "skipped_count": 0, "applied_ids": [], "skipped_ids": []}
    columns = _table_columns(cursor, "userservices")
    required = {"optimized_name", "optimized_description"}
    if not required.issubset(columns):
        return {"applied_count": 0, "skipped_count": len(suggestions), "applied_ids": [], "skipped_ids": []}
    applied_ids = []
    skipped_ids = []
    for suggestion in suggestions:
        if not isinstance(suggestion, dict):
            continue
        service_id = str(suggestion.get("service_id") or "").strip()
        proposed_name = str(suggestion.get("proposed_name") or "").strip()
        proposed_description = str(suggestion.get("proposed_description") or "").strip()
        if not service_id or not (proposed_name or proposed_description):
            if service_id:
                skipped_ids.append(service_id)
            continue
        cursor.execute(
            """
            UPDATE userservices
            SET optimized_name = COALESCE(NULLIF(%s, ''), optimized_name),
                optimized_description = COALESCE(NULLIF(%s, ''), optimized_description),
                updated_at = NOW()
            WHERE id = %s AND business_id = %s
            """,
            (proposed_name, proposed_description, service_id, business_id),
        )
        applied_ids.append(service_id)
    return {
        "applied_count": len(applied_ids),
        "skipped_count": len(skipped_ids),
        "applied_ids": applied_ids,
        "skipped_ids": skipped_ids,
    }


def _record_executor_ledger(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    run_id: str,
    step_key: str,
    request_id: str,
    action_id: str,
    capability: str,
    output_state: str,
    summary: Dict[str, Any],
) -> str:
    return log_agent_action(
        cursor,
        agent_client_id=None,
        business_id=business_id,
        action_type="agent_domain_request_approved",
        capability=capability,
        required_scope=None,
        risk_level="high",
        input_summary=json.dumps({"request_id": request_id, "action_id": action_id}, ensure_ascii=False),
        output_summary=json.dumps({"state": output_state, **summary}, ensure_ascii=False),
        approval_id=None,
        status="approved_pending_provider_executor",
        reason_code=APPROVED_EXECUTOR_REASON,
        ip=None,
        user_agent=None,
        metadata={
            "run_id": run_id,
            "step_key": step_key,
            "request_id": request_id,
            "action_id": action_id,
            "approved_by_user_id": user_id,
            "external_dispatch_performed": False,
            "provider_write_performed": False,
            "executor": "agent_domain_request_executor_v1",
        },
    )
