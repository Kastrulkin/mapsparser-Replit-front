"""Turn public Telegram links found during lead parsing into scoped evidence sources."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from psycopg2.extras import Json, RealDictCursor

from services.knowledge_graph_service import upsert_source


TELEGRAM_HOSTS = {"t.me", "telegram.me"}
RESERVED_PATHS = {
    "addemoji",
    "addlist",
    "addstickers",
    "c",
    "confirmphone",
    "contact",
    "invoice",
    "iv",
    "joinchat",
    "login",
    "proxy",
    "s",
    "share",
    "socks",
}
SIGNAL_MARKERS = (
    "акци",
    "ваканс",
    "запуск",
    "мероприят",
    "набор",
    "нов",
    "обнов",
    "откры",
    "партнер",
    "расписан",
    "скид",
    "событ",
    "сегодня",
    "теперь",
    "услуг",
    "курс",
    "мест",
    "launch",
    "new ",
    "open",
    "schedule",
)


def _row_dict(row: Any, cursor: Any | None = None) -> dict[str, Any]:
    if isinstance(row, dict):
        return dict(row)
    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}
    if row and cursor is not None and getattr(cursor, "description", None):
        return {item[0]: value for item, value in zip(cursor.description, row)}
    return {}


def parse_telegram_reference(value: Any) -> dict[str, str] | None:
    """Return a canonical public username reference, without assuming it is a channel."""
    raw = str(value or "").strip()
    if not raw:
        return None
    candidate = raw if re.match(r"^https?://", raw, re.IGNORECASE) else f"https://{raw.lstrip('/')}"
    try:
        parsed = urlparse(candidate)
    except ValueError:
        return None
    host = parsed.netloc.lower().removeprefix("www.")
    if host not in TELEGRAM_HOSTS:
        return None
    parts = [part for part in (parsed.path or "").split("/") if part]
    if not parts:
        return None
    if parts[0].lower() == "s" and len(parts) > 1:
        parts = parts[1:]
    username = parts[0].lstrip("@").strip()
    username_lower = username.lower()
    if (
        username_lower in RESERVED_PATHS
        or username.startswith("+")
        or not re.fullmatch(r"[A-Za-z0-9_]{4,32}", username)
    ):
        return None
    if username_lower.endswith("bot"):
        return {
            "kind": "bot",
            "username": username,
            "canonical_url": f"https://t.me/{username}",
            "discovered_url": raw,
        }
    message_id = parts[1] if len(parts) > 1 and parts[1].isdigit() else ""
    return {
        "kind": "public_reference",
        "username": username,
        "canonical_url": f"https://t.me/{username}",
        "discovered_url": raw,
        "message_id": message_id,
    }


def _scoped_radar_account(cursor: Any, workstream: dict[str, Any]) -> dict[str, Any]:
    scope_type = "platform" if workstream.get("workstream_type") == "localos_sales" else "business"
    business_id = None if scope_type == "platform" else str(workstream.get("client_business_id") or "").strip()
    cursor.execute(
        """
        SELECT sender.external_account_id AS account_id,
               COALESCE(permission.radar_enabled, FALSE) AS radar_enabled
        FROM outreach_sender_accounts sender
        JOIN externalbusinessaccounts account
          ON account.id = sender.external_account_id
         AND account.source = 'telegram_app'
         AND account.is_active = TRUE
        LEFT JOIN telegram_account_permissions permission
          ON permission.account_id = sender.external_account_id
        WHERE sender.scope_type = %s
          AND COALESCE(sender.business_id, '') = COALESCE(%s, '')
          AND sender.channel = 'telegram'
          AND sender.status = 'connected'
        ORDER BY COALESCE(permission.radar_enabled, FALSE) DESC,
                 sender.updated_at DESC,
                 sender.id
        LIMIT 1
        """,
        (scope_type, business_id),
    )
    row = cursor.fetchone()
    account = _row_dict(row, cursor)
    return {
        "scope_type": scope_type,
        "business_id": business_id,
        "account_id": str(account.get("account_id") or "").strip() or None,
        "radar_enabled": bool(account.get("radar_enabled")),
    }


def sync_discovered_telegram_sources(
    conn: Any,
    lead: dict[str, Any],
    links: list[Any] | None = None,
) -> dict[str, int]:
    """Idempotently register public Telegram references for every lead workstream."""
    lead_id = str(lead.get("id") or "").strip()
    if not lead_id:
        return {"references": 0, "sources": 0, "queued": 0}
    raw_links = list(links or [])
    if lead.get("telegram_url"):
        raw_links.append(lead.get("telegram_url"))
    messenger_links = lead.get("messenger_links_json")
    if isinstance(messenger_links, list):
        raw_links.extend(
            item.get("url") if isinstance(item, dict) else item
            for item in messenger_links
        )
    references: dict[str, dict[str, str]] = {}
    for raw_link in raw_links:
        reference = parse_telegram_reference(raw_link)
        if not reference or reference.get("kind") != "public_reference":
            continue
        references[reference["username"].lower()] = reference
    if not references:
        return {"references": 0, "sources": 0, "queued": 0}

    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            SELECT id, workstream_type, client_business_id
            FROM lead_workstreams
            WHERE lead_id = %s
            ORDER BY created_at
            """,
            (lead_id,),
        )
        workstreams = [_row_dict(row, cursor) for row in cursor.fetchall() or []]
        sources_saved = 0
        queued = 0
        for workstream in workstreams:
            scope = _scoped_radar_account(cursor, workstream)
            permission_reason = (
                "ready"
                if scope["radar_enabled"]
                else "radar_permission_required" if scope["account_id"] else "telegram_account_required"
            )
            for reference in references.values():
                external_scope = scope["business_id"] or "platform"
                source = upsert_source(
                    conn,
                    source_type="telegram",
                    external_key=f"lead-parse:{scope['scope_type']}:{external_scope}:{reference['username'].lower()}",
                    title=f"Telegram · {str(lead.get('name') or reference['username']).strip()}",
                    canonical_url=reference["canonical_url"],
                    source_role="service",
                    visibility="public",
                    sensitivity_class="public",
                    allowed_uses=["market", "outreach"],
                    status="candidate",
                    metadata={
                        "auto_discovered": True,
                        "discovery_origin": "map_parse",
                        "telegram_username": reference["username"],
                        "telegram_reference_type": "public_reference_unverified",
                        "permission_reason": permission_reason,
                    },
                    business_id=scope["business_id"],
                    account_id=scope["account_id"],
                    sync_mode="public_preview",
                    sync_status="queued" if scope["radar_enabled"] else "needs_account",
                    backfill_days=180,
                )
                cursor.execute(
                    """
                    UPDATE knowledge_sources
                    SET account_id = COALESCE(%s, account_id),
                        sync_status = CASE
                            WHEN status = 'candidate' AND %s THEN 'queued'
                            WHEN status = 'candidate' THEN 'needs_account'
                            ELSE sync_status
                        END,
                        next_sync_at = CASE WHEN %s THEN COALESCE(next_sync_at, NOW()) ELSE next_sync_at END,
                        metadata_json = metadata_json || %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (
                        scope["account_id"],
                        scope["radar_enabled"],
                        scope["radar_enabled"],
                        Json({"permission_reason": permission_reason}),
                        source["id"],
                    ),
                )
                cursor.execute(
                    """
                    INSERT INTO lead_signal_links (
                        id, workstream_id, source_type, source_id, status, created_at, updated_at
                    ) VALUES (%s, %s, 'telegram_knowledge_source', %s, 'selected', NOW(), NOW())
                    ON CONFLICT (workstream_id, source_type, source_id)
                    DO UPDATE SET updated_at = NOW()
                    """,
                    (str(uuid.uuid4()), workstream["id"], str(source["id"])),
                )
                sources_saved += 1
                queued += 1 if scope["radar_enabled"] else 0
        return {"references": len(references), "sources": sources_saved, "queued": queued}
    finally:
        cursor.close()


def mark_discovered_source_classification(
    conn: Any,
    *,
    source_id: str,
    is_public_channel: bool,
    title: str | None = None,
    reason: str = "",
) -> list[str]:
    """Persist preflight classification and prevent channels from being used as DM contacts."""
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            UPDATE knowledge_sources
            SET title = COALESCE(NULLIF(%s, ''), title),
                status = %s,
                sync_status = %s,
                last_sync_error = %s,
                metadata_json = metadata_json || %s,
                updated_at = NOW()
            WHERE id = %s
              AND COALESCE((metadata_json->>'auto_discovered')::boolean, FALSE) = TRUE
            RETURNING canonical_url
            """,
            (
                str(title or "").strip(),
                "active" if is_public_channel else "paused",
                "ready" if is_public_channel else "idle",
                None if is_public_channel else (reason or "not_public_channel"),
                Json({
                    "telegram_reference_type": "public_channel" if is_public_channel else "personal_or_unavailable",
                    "classified_at": datetime.now(timezone.utc).isoformat(),
                    "classification_reason": reason or ("public_preview" if is_public_channel else "not_public_channel"),
                }),
                source_id,
            ),
        )
        source_row = cursor.fetchone()
        if not source_row:
            return []
        canonical_url = str(_row_dict(source_row, cursor).get("canonical_url") or "")
        cursor.execute(
            """
            UPDATE lead_signal_links
            SET status = %s, updated_at = NOW()
            WHERE source_type = 'telegram_knowledge_source' AND source_id = %s
            RETURNING workstream_id
            """,
            ("selected" if is_public_channel else "rejected", source_id),
        )
        workstream_ids = [str(_row_dict(row, cursor).get("workstream_id") or "") for row in cursor.fetchall() or []]
        workstream_ids = [item for item in workstream_ids if item]
        if is_public_channel and workstream_ids:
            cursor.execute(
                """
                UPDATE lead_contact_points contact
                SET verification_status = 'invalid',
                    metadata_json = contact.metadata_json || %s,
                    updated_at = NOW()
                FROM lead_workstreams workstream
                WHERE workstream.id = ANY(%s::uuid[])
                  AND contact.lead_id = workstream.lead_id
                  AND contact.contact_type = 'telegram'
                  AND contact.normalized_value = %s
                """,
                (Json({"reason_code": "telegram_public_channel_source"}), workstream_ids, canonical_url),
            )
            cursor.execute(
                """
                UPDATE lead_workstreams workstream
                SET selected_contact_point_id = NULL, updated_at = NOW()
                FROM lead_contact_points contact
                WHERE workstream.id = ANY(%s::uuid[])
                  AND contact.id = workstream.selected_contact_point_id
                  AND contact.verification_status = 'invalid'
                """,
                (workstream_ids,),
            )
        return workstream_ids
    finally:
        cursor.close()


def discovered_telegram_signals(
    cursor: Any,
    lead: dict[str, Any],
    workstream: dict[str, Any],
    *,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Return fresh, specific, permission-scoped posts linked to this exact lead."""
    cursor.execute(
        """
        SELECT document.content_text AS message_text,
               document.permalink AS message_link,
               document.published_at AS message_date,
               source.title AS chat_title,
               source.metadata_json
        FROM lead_signal_links link
        JOIN knowledge_sources source
          ON source.id::text = link.source_id
        JOIN knowledge_documents document
          ON document.source_id = source.id
         AND document.invalidated_at IS NULL
        JOIN telegram_account_permissions permission
          ON permission.account_id = source.account_id
         AND permission.radar_enabled = TRUE
        WHERE link.workstream_id = %s
          AND link.source_type = 'telegram_knowledge_source'
          AND link.status = 'selected'
          AND source.status = 'active'
          AND source.sync_status = 'ready'
          AND source.visibility = 'public'
          AND source.sync_mode = 'public_preview'
          AND source.allowed_uses ? 'outreach'
          AND document.document_type = 'telegram_message'
          AND document.published_at >= NOW() - INTERVAL '180 days'
          AND document.permalink IS NOT NULL
        ORDER BY document.published_at DESC
        LIMIT 50
        """,
        (workstream.get("id"),),
    )
    category_tokens = {
        token
        for token in re.findall(r"[a-zа-яё0-9]{4,}", " ".join([
            str(lead.get("name") or ""),
            str(lead.get("category") or ""),
            str(lead.get("city") or ""),
        ]).lower())
        if token
    }
    now = datetime.now(timezone.utc)
    ranked: list[tuple[int, dict[str, Any]]] = []
    for raw_row in cursor.fetchall() or []:
        row = _row_dict(raw_row, cursor)
        text = re.sub(r"\s+", " ", str(row.get("message_text") or "")).strip()
        if len(text) < 40 or len(set(re.findall(r"[a-zа-яё0-9]{3,}", text.lower()))) < 6:
            continue
        lower = text.lower()
        has_marker = any(marker in lower for marker in SIGNAL_MARKERS)
        has_number = bool(re.search(r"\b\d{1,4}(?:[.,]\d+)?\b", lower))
        has_overlap = bool(category_tokens.intersection(re.findall(r"[a-zа-яё0-9]{4,}", lower)))
        published_at = row.get("message_date")
        if published_at and published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)
        if not published_at or (now - published_at).days > 180:
            continue
        fresh_60 = bool(published_at and (now - published_at).days <= 60)
        score = 45 + (20 if has_marker else 0) + (10 if has_number else 0) + (10 if has_overlap else 0) + (10 if fresh_60 else 0)
        if score < 60:
            continue
        ranked.append((min(score, 95), {
            "message_text": text,
            "message_link": row.get("message_link"),
            "message_date": published_at,
            "chat_title": row.get("chat_title") or "Telegram",
            "relevance_score": min(score, 95),
            "auto_discovered": True,
            "discovery_origin": "map_parse",
        }))
    ranked.sort(key=lambda item: (item[0], item[1].get("message_date") or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
    return [item[1] for item in ranked[: max(1, min(limit, 10))]]
