from __future__ import annotations

import json
import uuid
from typing import Any


def save_bot_feature_request(
    conn,
    *,
    telegram_id: str,
    user_id: str | None,
    business_id: str | None,
    source: str,
    category: str,
    request_text: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "id": str(uuid.uuid4()),
        "telegram_id": str(telegram_id or "").strip(),
        "user_id": str(user_id or "").strip() or None,
        "business_id": str(business_id or "").strip() or None,
        "source": str(source or "telegram_bot").strip() or "telegram_bot",
        "category": str(category or "other").strip().lower() or "other",
        "request_text": str(request_text or "").strip(),
        "metadata_json": json.dumps(metadata or {}, ensure_ascii=False),
    }
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO botfeaturerequests (
            id,
            telegram_id,
            user_id,
            business_id,
            source,
            category,
            request_text,
            metadata_json,
            status,
            created_at,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, NOW(), NOW())
        """,
        (
            payload["id"],
            payload["telegram_id"],
            payload["user_id"],
            payload["business_id"],
            payload["source"],
            payload["category"],
            payload["request_text"],
            payload["metadata_json"],
            "new",
        ),
    )
    conn.commit()
    return payload
