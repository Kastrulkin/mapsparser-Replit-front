from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from psycopg2.extras import Json

from pg_db_utils import get_db_connection


def ensure_ai_learning_events_table(conn) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS ailearningevents (
            id UUID PRIMARY KEY,
            intent TEXT NOT NULL DEFAULT 'operations',
            capability TEXT NOT NULL,
            event_type TEXT NOT NULL,
            accepted BOOLEAN,
            rejected BOOLEAN,
            edited_before_accept BOOLEAN,
            outcome TEXT,
            user_id UUID,
            business_id UUID,
            action_id UUID,
            prompt_key TEXT,
            prompt_version TEXT,
            draft_text TEXT,
            final_text TEXT,
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ailearningevents_created_at
        ON ailearningevents (created_at DESC)
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ailearningevents_capability_intent
        ON ailearningevents (capability, intent)
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ailearningevents_user_business
        ON ailearningevents (user_id, business_id)
        """
    )


def record_ai_learning_event(
    *,
    capability: str,
    event_type: str,
    intent: str = "operations",
    user_id: str | None = None,
    business_id: str | None = None,
    accepted: bool | None = None,
    rejected: bool | None = None,
    edited_before_accept: bool | None = None,
    outcome: str | None = None,
    action_id: str | None = None,
    prompt_key: str | None = None,
    prompt_version: str | None = None,
    draft_text: str | None = None,
    final_text: str | None = None,
    metadata: dict[str, Any] | None = None,
    conn=None,
) -> bool:
    own_conn = conn is None
    db_conn = conn or get_db_connection()
    try:
        ensure_ai_learning_events_table(db_conn)
        cur = db_conn.cursor()
        cur.execute(
            """
            INSERT INTO ailearningevents (
                id, intent, capability, event_type,
                accepted, rejected, edited_before_accept, outcome,
                user_id, business_id, action_id, prompt_key, prompt_version,
                draft_text, final_text, metadata_json, created_at
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                NULLIF(%s, '')::uuid,
                NULLIF(%s, '')::uuid,
                NULLIF(%s, '')::uuid,
                %s, %s,
                %s, %s, %s, %s
            )
            """,
            (
                str(uuid.uuid4()),
                str(intent or "operations").strip(),
                str(capability or "").strip(),
                str(event_type or "").strip(),
                accepted,
                rejected,
                edited_before_accept,
                (str(outcome).strip() if outcome else None),
                (str(user_id).strip() if user_id else ""),
                (str(business_id).strip() if business_id else ""),
                (str(action_id).strip() if action_id else ""),
                (str(prompt_key).strip() if prompt_key else None),
                (str(prompt_version).strip() if prompt_version else None),
                (str(draft_text).strip() if draft_text is not None else None),
                (str(final_text).strip() if final_text is not None else None),
                Json(metadata or {}),
                datetime.now(timezone.utc),
            ),
        )
        if own_conn:
            db_conn.commit()
        return True
    except Exception as exc:
        print(f"⚠️ ai_learning_event skipped: {exc}")
        if own_conn:
            try:
                db_conn.rollback()
            except Exception:
                pass
        return False
    finally:
        if own_conn:
            try:
                db_conn.close()
            except Exception:
                pass
