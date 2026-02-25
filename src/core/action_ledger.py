import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def month_key(dt: Optional[datetime] = None) -> str:
    dt = dt or utcnow()
    return dt.strftime("%Y-%m")


def ensure_ledger_tables(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS billing_ledger (
            id TEXT PRIMARY KEY,
            action_id TEXT NOT NULL,
            tenant_id TEXT NOT NULL,
            entry_type TEXT NOT NULL,
            tokens_in INTEGER DEFAULT 0,
            tokens_out INTEGER DEFAULT 0,
            cost NUMERIC(18,6) DEFAULT 0,
            tariff_id TEXT,
            month_key TEXT NOT NULL,
            meta_json JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_billing_ledger_action_id ON billing_ledger(action_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_billing_ledger_tenant_month ON billing_ledger(tenant_id, month_key)")


def write_ledger_entry(
    cursor,
    *,
    action_id: str,
    tenant_id: str,
    entry_type: str,
    tokens_in: int = 0,
    tokens_out: int = 0,
    cost: float = 0.0,
    tariff_id: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> str:
    entry_id = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO billing_ledger (
            id, action_id, tenant_id, entry_type, tokens_in, tokens_out, cost, tariff_id, month_key, meta_json
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            entry_id,
            action_id,
            tenant_id,
            entry_type,
            int(tokens_in or 0),
            int(tokens_out or 0),
            float(cost or 0.0),
            tariff_id,
            month_key(),
            json.dumps(meta or {}, ensure_ascii=False),
        ),
    )
    return entry_id
