"""Durable idempotency and quotas for model-backed compiled generation."""
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any


MAX_REQUESTS_PER_DAY = 20
MIN_NEW_REQUEST_SECONDS = 60
STALE_GENERATING_SECONDS = 300


def input_digest(value: dict[str, Any]) -> str:
    material = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(material.encode("utf-8")).hexdigest()


def reserve_generation(
    cursor: Any,
    *,
    user_id: str,
    business_id: str,
    blueprint_id: str,
    idempotency_key: str,
    request_digest: str,
) -> dict[str, Any]:
    clean_key = str(idempotency_key or "").strip()
    if not clean_key:
        return {"status": "rejected", "code": "COMPILED_GENERATION_IDEMPOTENCY_REQUIRED"}
    cursor.execute(
        "SELECT pg_advisory_xact_lock(hashtext(%s))",
        (f"compiled-generation:{user_id}:{business_id}",),
    )
    cursor.execute(
        """SELECT * FROM compiled_generation_requests
           WHERE user_id=%s AND business_id=%s AND blueprint_id=%s AND idempotency_key=%s
           FOR UPDATE""",
        (user_id, business_id, blueprint_id, clean_key),
    )
    existing = cursor.fetchone()
    if existing:
        row = dict(existing)
        if str(row.get("input_digest") or "") != request_digest:
            return {"status": "rejected", "code": "COMPILED_GENERATION_IDEMPOTENCY_CONFLICT"}
        state = str(row.get("state") or "")
        if state == "succeeded":
            return {"status": "replayed", "request": row}
        if state == "failed":
            return {"status": "failed", "code": str(row.get("error_code") or "COMPILED_GENERATION_FAILED"), "request": row}
        cursor.execute(
            """UPDATE compiled_generation_requests
               SET state='failed', error_code='COMPILED_GENERATION_STALE_UNKNOWN',
                   updated_at=NOW(), completed_at=NOW()
               WHERE id=%s AND created_at < NOW() - INTERVAL '5 minutes'
               RETURNING id""",
            (row["id"],),
        )
        stale = cursor.fetchone()
        if stale:
            row["state"] = "failed"
            row["error_code"] = "COMPILED_GENERATION_STALE_UNKNOWN"
            return {"status": "failed", "code": "COMPILED_GENERATION_STALE_UNKNOWN", "request": row}
        return {"status": "in_progress", "code": "COMPILED_GENERATION_IN_PROGRESS", "request": row}
    cursor.execute(
        """SELECT COUNT(*) AS count FROM compiled_generation_requests
           WHERE user_id=%s AND business_id=%s AND created_at >= NOW() - INTERVAL '24 hours'""",
        (user_id, business_id),
    )
    count_row = cursor.fetchone() or {}
    if int(count_row.get("count") or 0) >= MAX_REQUESTS_PER_DAY:
        return {"status": "rejected", "code": "COMPILED_GENERATION_QUOTA_EXCEEDED"}
    cursor.execute(
        """SELECT id FROM compiled_generation_requests
           WHERE user_id=%s AND business_id=%s
             AND created_at > NOW() - INTERVAL '60 seconds'
           ORDER BY created_at DESC LIMIT 1""",
        (user_id, business_id),
    )
    if cursor.fetchone():
        return {"status": "rejected", "code": "COMPILED_GENERATION_RATE_LIMITED"}
    request_id = str(uuid.uuid4())
    cursor.execute(
        """INSERT INTO compiled_generation_requests(
            id,user_id,business_id,blueprint_id,idempotency_key,input_digest,state
        ) VALUES (%s,%s,%s,%s,%s,%s,'generating')""",
        (request_id, user_id, business_id, blueprint_id, clean_key, request_digest),
    )
    return {"status": "reserved", "request": {"id": request_id}}


def mark_generation_succeeded(cursor: Any, request_id: str, version_id: str) -> None:
    cursor.execute(
        """UPDATE compiled_generation_requests
           SET state='succeeded', result_version_id=%s, error_code=NULL,
               updated_at=NOW(), completed_at=NOW()
           WHERE id=%s AND state='generating'""",
        (version_id, request_id),
    )
    if not getattr(cursor, "rowcount", 1):
        raise RuntimeError("compiled generation admission is no longer generating")


def mark_generation_failed(cursor: Any, request_id: str, code: str) -> None:
    cursor.execute(
        """UPDATE compiled_generation_requests
           SET state='failed', error_code=%s, updated_at=NOW(), completed_at=NOW()
           WHERE id=%s AND state='generating'""",
        (str(code or "COMPILED_GENERATION_FAILED")[:120], request_id),
    )
