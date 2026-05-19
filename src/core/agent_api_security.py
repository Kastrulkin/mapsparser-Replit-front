import hashlib
import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any


AGENT_CLIENT_STATUSES = {"sandbox", "live", "suspended"}

DEFAULT_SCOPES = [
    "audit:read",
    "services:draft",
    "reviews:draft",
    "content:draft",
    "finance:read",
    "partners:read",
    "approvals:create",
    "publish:request",
]

BLOCKED_DIRECT_ACTIONS = {
    "publish_posts",
    "publish_review_replies",
    "mass_edit_cards",
    "send_customer_messages",
    "send_partner_messages",
    "initiate_payments",
    "change_billing",
    "delete_records",
    "disable_records",
    "rollback_records",
    "change_external_credentials",
    "act_in_external_systems",
}

RISK_LEVELS = {"low", "medium", "high", "critical"}
APPROVAL_REQUIRED_RISKS = {"high", "critical"}

TRACKED_DISCOVERY_FILES = {
    "/llms.txt",
    "/localos-agents.txt",
    "/localos-agent-policy.json",
    "/localos-agent-tools.json",
    "/localos-agent-openapi.json",
}


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_scope(scope: str) -> str:
    return str(scope or "").strip().lower()


def normalize_risk_level(value: str | None, action_type: str | None = None) -> str:
    raw = str(value or "").strip().lower()
    if raw in RISK_LEVELS:
        return raw
    action = str(action_type or "").strip().lower()
    if action in BLOCKED_DIRECT_ACTIONS:
        return "critical"
    if action.endswith(":publish") or action.startswith("publish"):
        return "critical"
    if "bulk" in action or "sync" in action or "import" in action:
        return "high"
    if "draft" in action or "preview" in action:
        return "medium"
    return "low"


def action_requires_approval(action_type: str, risk_level: str) -> bool:
    action = str(action_type or "").strip().lower()
    risk = normalize_risk_level(risk_level, action)
    return action in BLOCKED_DIRECT_ACTIONS or risk in APPROVAL_REQUIRED_RISKS


def generate_agent_key(status: str = "sandbox") -> str:
    normalized_status = str(status or "sandbox").strip().lower()
    if normalized_status not in AGENT_CLIENT_STATUSES:
        normalized_status = "sandbox"
    return f"localos_agent_{normalized_status}_{secrets.token_urlsafe(32)}"


def hash_agent_key(agent_key: str) -> str:
    value = str(agent_key or "").strip()
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _to_json(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed
        except Exception:
            return default
    return default


def _row_get(row: Any, key: str, default: Any = None) -> Any:
    if row is None:
        return default
    if hasattr(row, "get"):
        return row.get(key, default)
    return default


def _safe_text(value: Any, limit: int = 1200) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def normalize_telegram_bot_username(value: Any) -> str:
    return str(value or "").strip().lstrip("@").lower()


def ensure_agent_security_tables(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_clients (
            id TEXT PRIMARY KEY,
            owner_user_id TEXT NOT NULL,
            organization_name TEXT NOT NULL,
            contact_email TEXT NOT NULL,
            key_hash TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'sandbox',
            allowed_scopes JSONB NOT NULL DEFAULT '[]'::jsonb,
            rate_limits JSONB NOT NULL DEFAULT '{}'::jsonb,
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            last_seen_at TIMESTAMPTZ
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_action_ledger (
            id TEXT PRIMARY KEY,
            agent_client_id TEXT,
            business_id TEXT,
            action_type TEXT NOT NULL,
            capability TEXT,
            required_scope TEXT,
            risk_level TEXT NOT NULL,
            input_summary TEXT,
            output_summary TEXT,
            approval_id TEXT,
            status TEXT NOT NULL,
            reason_code TEXT,
            ip TEXT,
            user_agent TEXT,
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_discovery_events (
            id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,
            path TEXT NOT NULL,
            method TEXT NOT NULL,
            status_code INT,
            agent_family TEXT NOT NULL DEFAULT 'unknown',
            ip_hash TEXT,
            user_agent TEXT,
            referrer TEXT,
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_clients_key_hash ON agent_clients(key_hash)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_agent_clients_owner ON agent_clients(owner_user_id, created_at DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_agent_clients_status ON agent_clients(status)")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_agent_action_ledger_client_created ON agent_action_ledger(agent_client_id, created_at DESC)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_agent_action_ledger_business_created ON agent_action_ledger(business_id, created_at DESC)"
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_agent_action_ledger_risk ON agent_action_ledger(risk_level, created_at DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_agent_action_ledger_status ON agent_action_ledger(status, created_at DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_agent_discovery_events_created ON agent_discovery_events(created_at DESC)")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_agent_discovery_events_family_created ON agent_discovery_events(agent_family, created_at DESC)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_agent_discovery_events_type_created ON agent_discovery_events(event_type, created_at DESC)"
    )


def _cursor_row_to_dict(cursor, row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    if isinstance(row, dict):
        return row
    if hasattr(row, "keys"):
        try:
            return dict(row)
        except Exception:
            return {}
    description = getattr(cursor, "description", None) or []
    columns = [col[0] for col in description]
    if isinstance(row, (list, tuple)) and columns:
        return {columns[idx]: row[idx] for idx in range(min(len(columns), len(row)))}
    return {}


def identify_agent_family(user_agent: str) -> str:
    value = str(user_agent or "").strip().lower()
    if not value:
        return "unknown"
    if "chatgpt" in value or "gptbot" in value or "openai" in value:
        return "openai"
    if "claude" in value or "anthropic" in value:
        return "anthropic"
    if "perplexity" in value:
        return "perplexity"
    if "google-extended" in value or "googlebot" in value:
        return "google"
    if "applebot" in value:
        return "apple"
    if "bot" in value or "crawler" in value or "spider" in value:
        return "other_bot"
    return "browser_or_unknown"


def classify_discovery_path(path: str) -> str:
    normalized = "/" + str(path or "").strip().lstrip("/")
    if normalized.startswith("/api/agent-api/"):
        return "agent_api"
    if normalized in TRACKED_DISCOVERY_FILES:
        return "machine_readable_docs"
    if normalized == "/docs" or normalized.startswith("/docs/"):
        return "docs_view"
    return ""


def should_track_discovery_path(path: str) -> bool:
    return bool(classify_discovery_path(path))


def hash_ip_for_discovery(ip_value: str) -> str:
    raw = str(ip_value or "").split(",")[0].strip()
    if not raw:
        return ""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def log_agent_discovery_event(
    cursor,
    path: str,
    method: str,
    status_code: int | None,
    user_agent: str,
    ip_value: str,
    referrer: str,
    metadata: dict[str, Any] | None = None,
) -> str | None:
    event_type = classify_discovery_path(path)
    if not event_type:
        return None
    ensure_agent_security_tables(cursor)
    event_id = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO agent_discovery_events (
            id, event_type, path, method, status_code, agent_family,
            ip_hash, user_agent, referrer, metadata_json, created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, NOW())
        """,
        (
            event_id,
            event_type,
            "/" + str(path or "").strip().lstrip("/"),
            str(method or "GET").strip().upper(),
            status_code,
            identify_agent_family(user_agent),
            hash_ip_for_discovery(ip_value),
            str(user_agent or "").strip()[:500],
            str(referrer or "").strip()[:500],
            json.dumps(metadata or {}, ensure_ascii=False),
        ),
    )
    return event_id


def build_agent_activity_digest(conn, now_value: datetime | None = None, hours: int = 24) -> str:
    now_dt = now_value or datetime.utcnow()
    since_dt = now_dt - timedelta(hours=max(1, int(hours or 24)))
    cursor = conn.cursor()
    ensure_agent_security_tables(cursor)
    cursor.execute(
        """
        SELECT
            COUNT(*) FILTER (WHERE event_type = 'docs_view')::INT docs_views,
            COUNT(*) FILTER (WHERE event_type = 'machine_readable_docs')::INT machine_docs,
            COUNT(*) FILTER (WHERE event_type = 'agent_api')::INT api_hits
        FROM agent_discovery_events
        WHERE created_at >= %s
        """,
        (since_dt,),
    )
    discovery = _cursor_row_to_dict(cursor, cursor.fetchone())
    cursor.execute(
        """
        SELECT agent_family, COUNT(*)::INT total
        FROM agent_discovery_events
        WHERE created_at >= %s
        GROUP BY agent_family
        ORDER BY total DESC, agent_family
        LIMIT 5
        """,
        (since_dt,),
    )
    family_rows = [_cursor_row_to_dict(cursor, row) for row in cursor.fetchall() or []]
    cursor.execute(
        """
        SELECT
            COUNT(*)::INT total_actions,
            COUNT(*) FILTER (WHERE status = 'pending_human')::INT pending_human,
            COUNT(*) FILTER (WHERE status = 'denied')::INT denied,
            COUNT(*) FILTER (WHERE action_type = 'agent_api_self_test')::INT self_tests,
            COUNT(*) FILTER (WHERE reason_code IN ('AGENT_AUTH_REQUIRED', 'SCOPE_REQUIRED'))::INT auth_scope_errors,
            COUNT(*) FILTER (WHERE action_type = 'agent_client_promotion_request')::INT promotion_requests
        FROM agent_action_ledger
        WHERE created_at >= %s
        """,
        (since_dt,),
    )
    ledger = _cursor_row_to_dict(cursor, cursor.fetchone())
    cursor.execute(
        """
        SELECT COALESCE(c.organization_name, l.agent_client_id, 'unknown') AS agent_name,
               COUNT(*)::INT total
        FROM agent_action_ledger l
        LEFT JOIN agent_clients c ON c.id = l.agent_client_id
        WHERE l.created_at >= %s
          AND l.action_type = 'agent_api_self_test'
        GROUP BY COALESCE(c.organization_name, l.agent_client_id, 'unknown')
        ORDER BY total DESC, agent_name
        LIMIT 5
        """,
        (since_dt,),
    )
    self_test_rows = [_cursor_row_to_dict(cursor, row) for row in cursor.fetchall() or []]
    cursor.execute(
        """
        SELECT COUNT(*)::INT seen_clients
        FROM agent_clients
        WHERE last_seen_at >= %s
        """,
        (since_dt,),
    )
    clients = _cursor_row_to_dict(cursor, cursor.fetchone())

    docs_views = int(discovery.get("docs_views") or 0)
    machine_docs = int(discovery.get("machine_docs") or 0)
    api_hits = int(discovery.get("api_hits") or 0)
    seen_clients = int(clients.get("seen_clients") or 0)
    total_actions = int(ledger.get("total_actions") or 0)
    pending_human = int(ledger.get("pending_human") or 0)
    denied = int(ledger.get("denied") or 0)
    self_tests = int(ledger.get("self_tests") or 0)
    auth_scope_errors = int(ledger.get("auth_scope_errors") or 0)
    promotion_requests = int(ledger.get("promotion_requests") or 0)
    families = []
    for item in family_rows:
        family = str(item.get("agent_family") or "unknown").strip()
        total = int(item.get("total") or 0)
        if total > 0:
            families.append(f"{family}: {total}")
    family_text = ", ".join(families) if families else "не обнаружены"
    tested_agents = []
    for item in self_test_rows:
        agent_name = str(item.get("agent_name") or "unknown").strip()
        total = int(item.get("total") or 0)
        if total > 0:
            tested_agents.append(f"{agent_name}: {total}")
    tested_agents_text = ", ".join(tested_agents) if tested_agents else "нет"
    if docs_views <= 0 and machine_docs <= 0 and api_hits <= 0 and total_actions <= 0 and seen_clients <= 0:
        return (
            "🤖 ИИ-агенты\n"
            "За последние 24 часа явных заходов в docs/API не видно."
        )
    return (
        "🤖 ИИ-агенты\n"
        f"Docs: {docs_views}, agent-файлы: {machine_docs}, API hits: {api_hits}.\n"
        f"Клиенты API: активных за 24ч — {seen_clients}; действий — {total_actions}, approval — {pending_human}, отказов — {denied}.\n"
        f"Self-test: {self_tests}; auth/scope ошибок — {auth_scope_errors}; promotion requests — {promotion_requests}.\n"
        f"Проверялись: {tested_agents_text}.\n"
        f"User-Agent группы: {family_text}."
    )


def create_agent_client(
    cursor,
    *,
    owner_user_id: str,
    organization_name: str,
    contact_email: str,
    allowed_scopes: list[str] | None = None,
    status: str = "sandbox",
    rate_limits: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ensure_agent_security_tables(cursor)
    normalized_status = str(status or "sandbox").strip().lower()
    if normalized_status not in AGENT_CLIENT_STATUSES:
        normalized_status = "sandbox"
    scopes = [normalize_scope(item) for item in (allowed_scopes or DEFAULT_SCOPES) if normalize_scope(item)]
    client_id = str(uuid.uuid4())
    agent_key = generate_agent_key(normalized_status)
    cursor.execute(
        """
        INSERT INTO agent_clients (
            id, owner_user_id, organization_name, contact_email, key_hash,
            status, allowed_scopes, rate_limits, metadata_json
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            client_id,
            str(owner_user_id),
            str(organization_name or "").strip(),
            str(contact_email or "").strip().lower(),
            hash_agent_key(agent_key),
            normalized_status,
            json.dumps(scopes, ensure_ascii=False),
            json.dumps(rate_limits or {}, ensure_ascii=False),
            json.dumps(metadata or {}, ensure_ascii=False),
        ),
    )
    return {
        "client_id": client_id,
        "agent_key": agent_key,
        "status": normalized_status,
        "allowed_scopes": scopes,
    }


def update_agent_client(
    cursor,
    *,
    client_id: str,
    status: str | None = None,
    allowed_scopes: list[str] | None = None,
    rate_limits: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    ensure_agent_security_tables(cursor)
    cursor.execute(
        """
        SELECT id, status, allowed_scopes, rate_limits, metadata_json
        FROM agent_clients
        WHERE id = %s
        LIMIT 1
        """,
        (str(client_id or "").strip(),),
    )
    row = cursor.fetchone()
    existing = _cursor_row_to_dict(cursor, row)
    if not existing:
        return None
    normalized_status = str(status or existing.get("status") or "sandbox").strip().lower()
    if normalized_status not in AGENT_CLIENT_STATUSES:
        normalized_status = str(existing.get("status") or "sandbox").strip().lower()
    existing_scopes = _to_json(existing.get("allowed_scopes"), [])
    scopes_source = allowed_scopes if isinstance(allowed_scopes, list) else existing_scopes
    scopes = [normalize_scope(item) for item in scopes_source if normalize_scope(item)]
    existing_rate_limits = _to_json(existing.get("rate_limits"), {})
    rate_limit_payload = rate_limits if isinstance(rate_limits, dict) else existing_rate_limits
    existing_metadata = _to_json(existing.get("metadata_json"), {})
    metadata_payload = existing_metadata if isinstance(existing_metadata, dict) else {}
    if isinstance(metadata, dict):
        metadata_payload.update(metadata)
    cursor.execute(
        """
        UPDATE agent_clients
        SET status = %s,
            allowed_scopes = %s::jsonb,
            rate_limits = %s::jsonb,
            metadata_json = %s::jsonb,
            updated_at = NOW()
        WHERE id = %s
        """,
        (
            normalized_status,
            json.dumps(scopes, ensure_ascii=False),
            json.dumps(rate_limit_payload or {}, ensure_ascii=False),
            json.dumps(metadata_payload or {}, ensure_ascii=False),
            str(client_id or "").strip(),
        ),
    )
    return {
        "client_id": str(client_id or "").strip(),
        "status": normalized_status,
        "allowed_scopes": scopes,
        "rate_limits": rate_limit_payload or {},
        "metadata": metadata_payload or {},
    }


def find_agent_client_by_telegram_sender(cursor, sender_context: dict[str, Any]) -> dict[str, Any] | None:
    ensure_agent_security_tables(cursor)
    username = normalize_telegram_bot_username(sender_context.get("username"))
    telegram_id = str(sender_context.get("telegram_id") or "").strip()
    if not username and not telegram_id:
        return None
    cursor.execute(
        """
        SELECT id, organization_name, contact_email, status, allowed_scopes, rate_limits, metadata_json
        FROM agent_clients
        WHERE (
            %s <> '' AND LOWER(COALESCE(metadata_json->>'telegram_bot_username', '')) = %s
        ) OR (
            %s <> '' AND COALESCE(metadata_json->>'telegram_bot_id', '') = %s
        )
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (username, username, telegram_id, telegram_id),
    )
    row = cursor.fetchone()
    payload = _cursor_row_to_dict(cursor, row)
    if not payload:
        return None
    payload["allowed_scopes"] = _to_json(payload.get("allowed_scopes"), [])
    payload["rate_limits"] = _to_json(payload.get("rate_limits"), {})
    payload["metadata_json"] = _to_json(payload.get("metadata_json"), {})
    return payload


def rotate_agent_client_key(cursor, client_id: str) -> dict[str, Any] | None:
    ensure_agent_security_tables(cursor)
    cursor.execute(
        """
        SELECT id, status
        FROM agent_clients
        WHERE id = %s
        LIMIT 1
        """,
        (str(client_id or "").strip(),),
    )
    row = cursor.fetchone()
    existing = _cursor_row_to_dict(cursor, row)
    if not existing:
        return None
    status = str(existing.get("status") or "sandbox").strip().lower()
    agent_key = generate_agent_key(status)
    cursor.execute(
        """
        UPDATE agent_clients
        SET key_hash = %s,
            updated_at = NOW(),
            last_seen_at = NULL
        WHERE id = %s
        """,
        (hash_agent_key(agent_key), str(client_id or "").strip()),
    )
    return {
        "client_id": str(client_id or "").strip(),
        "status": status,
        "agent_key": agent_key,
    }


def request_agent_client_promotion(
    cursor,
    *,
    client: dict[str, Any],
    requested_scopes: list[str] | None = None,
    use_case: str = "",
    contact: str = "",
) -> str:
    scopes = [normalize_scope(item) for item in (requested_scopes or []) if normalize_scope(item)]
    return log_agent_action(
        cursor,
        agent_client_id=str(client.get("id") or ""),
        business_id=None,
        action_type="agent_client_promotion_request",
        capability="agent_api.security",
        required_scope="approvals:create",
        risk_level="high",
        input_summary={
            "requested_scopes": scopes,
            "use_case": str(use_case or "").strip(),
            "contact": str(contact or "").strip(),
        },
        status="pending_human",
        reason_code="PROMOTION_REVIEW_REQUIRED",
        metadata={
            "current_status": str(client.get("status") or ""),
            "organization_name": str(client.get("organization_name") or ""),
        },
    )


def decide_agent_client_promotion(
    cursor,
    *,
    client_id: str,
    decision: str,
    reviewer_user_id: str,
    allowed_scopes: list[str] | None = None,
    note: str = "",
) -> dict[str, Any] | None:
    normalized_decision = str(decision or "").strip().lower()
    if normalized_decision not in {"approve", "reject"}:
        normalized_decision = "reject"
    cursor.execute(
        """
        SELECT id, organization_name, contact_email, status, allowed_scopes, rate_limits, metadata_json
        FROM agent_clients
        WHERE id = %s
        LIMIT 1
        """,
        (str(client_id or "").strip(),),
    )
    existing = _cursor_row_to_dict(cursor, cursor.fetchone())
    if not existing:
        return None
    scopes = [normalize_scope(item) for item in (allowed_scopes or _to_json(existing.get("allowed_scopes"), [])) if normalize_scope(item)]
    if normalized_decision == "approve":
        update_agent_client(
            cursor,
            client_id=client_id,
            status="live",
            allowed_scopes=scopes,
            metadata={
                "promotion_decision": "approved",
                "promotion_reviewed_by": str(reviewer_user_id or ""),
                "promotion_note": str(note or "").strip(),
                "promotion_reviewed_at": utcnow_iso(),
            },
        )
        status = "completed"
        reason_code = "PROMOTION_APPROVED"
        final_status = "live"
    else:
        update_agent_client(
            cursor,
            client_id=client_id,
            metadata={
                "promotion_decision": "rejected",
                "promotion_reviewed_by": str(reviewer_user_id or ""),
                "promotion_note": str(note or "").strip(),
                "promotion_reviewed_at": utcnow_iso(),
            },
        )
        status = "rejected"
        reason_code = "PROMOTION_REJECTED"
        final_status = str(existing.get("status") or "sandbox")
    ledger_id = log_agent_action(
        cursor,
        agent_client_id=str(client_id or "").strip(),
        business_id=None,
        action_type=f"agent_client_promotion_{normalized_decision}",
        capability="agent_api.security",
        required_scope="superadmin",
        risk_level="high",
        input_summary={
            "decision": normalized_decision,
            "allowed_scopes": scopes,
            "note": str(note or "").strip(),
        },
        status=status,
        reason_code=reason_code,
        metadata={
            "reviewer_user_id": str(reviewer_user_id or ""),
            "previous_status": str(existing.get("status") or ""),
            "final_status": final_status,
        },
    )
    return {
        "client_id": str(client_id or "").strip(),
        "decision": normalized_decision,
        "status": final_status,
        "allowed_scopes": scopes,
        "ledger_id": ledger_id,
    }


def load_agent_client_by_key(cursor, agent_key: str) -> dict[str, Any] | None:
    key_hash = hash_agent_key(agent_key)
    ensure_agent_security_tables(cursor)
    cursor.execute(
        """
        SELECT id, owner_user_id, organization_name, contact_email, status,
               allowed_scopes, rate_limits, metadata_json, created_at, last_seen_at
        FROM agent_clients
        WHERE key_hash = %s
        LIMIT 1
        """,
        (key_hash,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    client = dict(row)
    client["allowed_scopes"] = _to_json(client.get("allowed_scopes"), [])
    client["rate_limits"] = _to_json(client.get("rate_limits"), {})
    client["metadata_json"] = _to_json(client.get("metadata_json"), {})
    return client


def mark_agent_seen(cursor, client_id: str) -> None:
    cursor.execute(
        "UPDATE agent_clients SET last_seen_at = NOW(), updated_at = NOW() WHERE id = %s",
        (str(client_id),),
    )


def evaluate_agent_access(
    client: dict[str, Any] | None,
    *,
    required_scope: str,
    risk_level: str = "low",
    action_type: str = "",
    business_id: str = "",
) -> dict[str, Any]:
    scope = normalize_scope(required_scope)
    action = str(action_type or "").strip().lower()
    risk = normalize_risk_level(risk_level, action)
    if not client:
        return {"ok": False, "http_status": 401, "code": "AGENT_AUTH_REQUIRED", "reason": "agent key is missing or invalid"}
    status = str(client.get("status") or "").strip().lower()
    if status == "suspended":
        return {"ok": False, "http_status": 403, "code": "AGENT_SUSPENDED", "reason": "agent client is suspended"}
    if status not in AGENT_CLIENT_STATUSES:
        return {"ok": False, "http_status": 403, "code": "AGENT_STATUS_INVALID", "reason": "agent status is invalid"}
    scopes = set()
    for item in client.get("allowed_scopes") or []:
        normalized = normalize_scope(item)
        if normalized:
            scopes.add(normalized)
    if scope and scope not in scopes:
        return {"ok": False, "http_status": 403, "code": "SCOPE_REQUIRED", "reason": f"scope required: {scope}"}
    if status == "sandbox" and risk in {"high", "critical"}:
        return {
            "ok": False,
            "http_status": 403,
            "code": "SANDBOX_RISK_BLOCKED",
            "reason": "sandbox clients cannot execute high or critical risk actions",
        }
    if action in BLOCKED_DIRECT_ACTIONS:
        return {
            "ok": False,
            "http_status": 403,
            "code": "DIRECT_ACTION_BLOCKED",
            "reason": "this action must go through approval request",
        }
    return {
        "ok": True,
        "http_status": 200,
        "code": "OK",
        "reason": "",
        "risk_level": risk,
        "approval_required": action_requires_approval(action, risk),
        "business_id": str(business_id or ""),
    }


def build_agent_self_test_summary(client: dict[str, Any], access: dict[str, Any]) -> dict[str, Any]:
    scopes = []
    for item in client.get("allowed_scopes") or []:
        normalized = normalize_scope(item)
        if normalized:
            scopes.append(normalized)
    scope_set = set(scopes)
    draft_scopes = [
        scope for scope in ["services:draft", "reviews:draft", "content:draft", "approvals:create"] if scope in scope_set
    ]
    read_scopes = [
        scope for scope in ["audit:read", "finance:read", "partners:read"] if scope in scope_set
    ]
    blocked_actions = sorted(BLOCKED_DIRECT_ACTIONS)
    return {
        "client": {
            "client_id": str(client.get("id") or ""),
            "organization_name": str(client.get("organization_name") or ""),
            "status": str(client.get("status") or ""),
            "allowed_scopes": scopes,
        },
        "access": {
            "ok": bool(access.get("ok")),
            "code": str(access.get("code") or ""),
            "reason": str(access.get("reason") or ""),
        },
        "available": {
            "read_scopes": read_scopes,
            "draft_scopes": draft_scopes,
            "can_create_approval_request": "approvals:create" in scope_set,
            "can_request_publish_approval": "publish:request" in scope_set,
            "live_external_execution": False,
        },
        "approval_required_for": [
            "publishing",
            "customer_messages",
            "partner_messages",
            "payments",
            "destructive_actions",
            "external_system_actions",
        ],
        "blocked_direct_actions": blocked_actions,
        "next_steps": [
            "Read /localos-agent-openapi.json.",
            "Create a test approval request with POST /api/agent-api/approvals/request.",
            "Ask a superadmin to review promotion before live access.",
        ],
    }


def log_agent_action(
    cursor,
    *,
    agent_client_id: str | None,
    business_id: str | None,
    action_type: str,
    capability: str | None = None,
    required_scope: str | None = None,
    risk_level: str = "low",
    input_summary: Any = "",
    output_summary: Any = "",
    approval_id: str | None = None,
    status: str = "recorded",
    reason_code: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    ensure_agent_security_tables(cursor)
    entry_id = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO agent_action_ledger (
            id, agent_client_id, business_id, action_type, capability, required_scope,
            risk_level, input_summary, output_summary, approval_id, status,
            reason_code, ip, user_agent, metadata_json
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            entry_id,
            agent_client_id,
            business_id,
            str(action_type or "unknown"),
            capability,
            required_scope,
            normalize_risk_level(risk_level, action_type),
            _safe_text(input_summary),
            _safe_text(output_summary),
            approval_id,
            str(status or "recorded"),
            reason_code,
            ip,
            user_agent,
            json.dumps(metadata or {}, ensure_ascii=False),
        ),
    )
    return entry_id


def public_agent_policy() -> dict[str, Any]:
    return {
        "schema_version": "2026-05-14",
        "product": "LocalOS",
        "status": "implemented_foundation",
        "principle": "Do not guess intent. Limit damage with identity, scopes, sandbox, human approval, rate limits, abuse detection, and audit trails.",
        "scopes": list(DEFAULT_SCOPES),
        "blocked_direct_actions": sorted(BLOCKED_DIRECT_ACTIONS),
        "risk_levels": sorted(RISK_LEVELS),
        "new_client_default_status": "sandbox",
        "approval_required_risks": sorted(APPROVAL_REQUIRED_RISKS),
        "promotion_flow": {
            "request_endpoint": "/api/agent-api/clients/promotion/request",
            "decision_endpoint": "/api/agent-api/clients/{client_id}/promotion/decide",
            "live_access_requires_human_review": True,
        },
        "onboarding": {
            "self_test_endpoint": "/api/agent-api/self-test",
            "self_test_writes_ledger": True,
            "self_test_side_effect": "safe internal ledger record only",
        },
        "telegram_transport": {
            "status": "foundation_with_binding_ledger_alerts",
            "trust_chain": "agent_clients -> scopes -> agent_action_ledger -> human approval",
            "binding": "telegram_bot_username and telegram_bot_id are stored in agent_clients.metadata_json",
            "unknown_bots": "deny automation, write ledger, and alert superadmin",
            "max_bot_to_bot_hops": 3,
        },
    }
