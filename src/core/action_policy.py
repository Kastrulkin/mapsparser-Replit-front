import os
from datetime import datetime, timezone
from typing import Any, Dict


DEFAULT_MONTHLY_TOKEN_LIMIT = int(os.getenv("ORCHESTRATOR_MONTHLY_TOKEN_LIMIT", "500000"))


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _row_value(row: Any, index: int, key: str, default: Any = None) -> Any:
    if row is None:
        return default
    if isinstance(row, (tuple, list)):
        try:
            return row[index]
        except Exception:
            return default
    if hasattr(row, "get"):
        try:
            return row.get(key, default)
        except Exception:
            return default
    return default


def check_tenant_access(cursor, tenant_id: str, actor_user_id: str, is_superadmin: bool) -> Dict[str, Any]:
    if not tenant_id:
        return {"ok": False, "code": "TENANT_REQUIRED", "reason": "tenant_id is required"}

    cursor.execute("SELECT owner_id FROM businesses WHERE id = %s LIMIT 1", (tenant_id,))
    row = cursor.fetchone()
    owner_id = None
    if row:
        if isinstance(row, (tuple, list)):
            owner_id = row[0]
        elif hasattr(row, "keys"):
            owner_id = row.get("owner_id")

    if not owner_id:
        return {"ok": False, "code": "TENANT_NOT_FOUND", "reason": "tenant_id not found"}

    if str(owner_id) != str(actor_user_id) and not is_superadmin:
        return {"ok": False, "code": "TENANT_MISMATCH", "reason": "actor has no access to tenant"}

    return {"ok": True}


def evaluate_risk_policy(capability: str, payload: Dict[str, Any], approval: Dict[str, Any]) -> Dict[str, Any]:
    mode = str((approval or {}).get("mode") or "auto").strip().lower()
    if mode == "required":
        return {"ok": True, "requires_human": True, "reason": "approval.mode=required"}

    # Minimum Phase 1 risk policy.
    if capability == "services.optimize":
        if bool(payload.get("bulk")) or str(payload.get("source") or "").lower() == "file":
            return {"ok": True, "requires_human": True, "reason": "bulk optimization requires review"}

    if capability == "reviews.reply":
        if bool(payload.get("publish")):
            return {"ok": True, "requires_human": True, "reason": "publishing replies requires review"}

    return {"ok": True, "requires_human": False, "reason": ""}


def check_token_limit(cursor, tenant_id: str, reserve_tokens: int) -> Dict[str, Any]:
    reserve_tokens = max(_to_int(reserve_tokens, 0), 0)
    month_key = utcnow().strftime("%Y-%m")

    cursor.execute(
        """
        SELECT COALESCE(SUM(tokens_out), 0) AS spent_tokens
        FROM billing_ledger
        WHERE tenant_id = %s
          AND month_key = %s
          AND entry_type IN ('settle')
        """,
        (tenant_id, month_key),
    )
    spent = _to_int(_row_value(cursor.fetchone(), 0, "spent_tokens", 0), 0)

    cursor.execute(
        """
        SELECT COALESCE(SUM(tokens_out), 0) AS reserved_tokens
        FROM billing_ledger
        WHERE tenant_id = %s
          AND month_key = %s
          AND entry_type IN ('reserve')
        """,
        (tenant_id, month_key),
    )
    reserved_total = _to_int(_row_value(cursor.fetchone(), 0, "reserved_tokens", 0), 0)

    cursor.execute(
        """
        SELECT COALESCE(SUM(tokens_out), 0) AS released_tokens
        FROM billing_ledger
        WHERE tenant_id = %s
          AND month_key = %s
          AND entry_type IN ('release')
        """,
        (tenant_id, month_key),
    )
    released_total = _to_int(_row_value(cursor.fetchone(), 0, "released_tokens", 0), 0)
    active_reserved = max(reserved_total - released_total - spent, 0)
    projected = spent + active_reserved + reserve_tokens

    if projected > DEFAULT_MONTHLY_TOKEN_LIMIT:
        return {
            "ok": False,
            "code": "LIMIT_EXCEEDED",
            "reason": "token limit exceeded",
            "limit_tokens": DEFAULT_MONTHLY_TOKEN_LIMIT,
            "spent_tokens": spent,
            "reserved_tokens": active_reserved,
            "requested_tokens": reserve_tokens,
        }

    return {
        "ok": True,
        "limit_tokens": DEFAULT_MONTHLY_TOKEN_LIMIT,
        "spent_tokens": spent,
        "reserved_tokens": active_reserved,
        "requested_tokens": reserve_tokens,
    }
