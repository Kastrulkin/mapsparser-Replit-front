"""Turn public Telegram links found during enrichment into shared evidence sources."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from psycopg2.extras import Json, RealDictCursor

from services.knowledge_graph_service import upsert_source


TELEGRAM_HOSTS = {"t.me", "telegram.me"}
SHARED_SERVICE_TELEGRAM_SOURCES = {
    "dikidi_business": {
        "owner": "dikidi",
        "title": "Telegram · Dikidi",
    },
}
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


def source_attribution_for_lead(lead: dict[str, Any]) -> dict[str, Any]:
    combined = " ".join(
        str(value or "").strip().lower()
        for value in (
            lead.get("name"),
            lead.get("category"),
            lead.get("partner_kind"),
        )
        if str(value or "").strip()
    )
    residential = any(
        token in combined
        for token in (
            "residential_complex",
            "residential complex",
            "жилой комплекс",
            "жилкомплекс",
        )
    ) or combined.startswith("жк ")
    return {
        "source_owner_type": "residential_complex" if residential else "prospecting_recipient",
        "source_owner_role": "outreach_recipient",
        "source_owner_scope": "lead_signal_links",
        "sender_business_is_owner": False,
        "lead_attribution": "recipient_signal_source",
    }


def public_source_profile_for_lead(lead: dict[str, Any]) -> dict[str, Any]:
    """Describe an official recipient channel without making it a DM contact."""
    combined = " ".join(
        str(value or "").strip().lower()
        for value in (lead.get("name"), lead.get("category"), lead.get("partner_kind"))
        if str(value or "").strip()
    )
    beauty = any(token in combined for token in (
        "beauty",
        "wellness",
        "барбершоп",
        "косметолог",
        "маникюр",
        "ногт",
        "парикмах",
        "салон красоты",
        "спа",
    ))
    if beauty:
        return {
            "source_role": "salon",
            "metadata": {
                "source_owner_type": "owned_business_channel",
                "source_owner_role": "outreach_recipient",
                "audience": "b2c",
                "industry": "beauty_salon",
                "recipient_eligible": False,
                "signal_source_eligible": True,
                "learning_eligible": True,
                "corpus_tag": "telegram_b2c_beauty",
            },
        }
    return {"source_role": "community", "metadata": {}}


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


def _existing_public_source(cursor: Any, canonical_url: str) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT *
        FROM knowledge_sources
        WHERE source_type = 'telegram'
          AND visibility = 'public'
          AND sensitivity_class = 'public'
          AND LOWER(RTRIM(canonical_url, '/')) = LOWER(RTRIM(%s, '/'))
        ORDER BY CASE status WHEN 'active' THEN 0 WHEN 'candidate' THEN 1 ELSE 2 END,
                 last_collected_at DESC NULLS LAST,
                 created_at
        LIMIT 1
        """,
        (canonical_url,),
    )
    return _row_dict(cursor.fetchone(), cursor)


def _register_global_public_source(
    conn: Any,
    cursor: Any,
    *,
    lead: dict[str, Any],
    reference: dict[str, str],
    discovery_origin: str,
) -> dict[str, Any]:
    """Reuse a public Telegram source globally, independent of a tenant account."""
    cursor.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(LOWER(RTRIM(%s, '/')), 0))",
        (reference["canonical_url"],),
    )
    profile = public_source_profile_for_lead(lead)
    existing = _existing_public_source(cursor, reference["canonical_url"])
    if existing:
        cursor.execute(
            """
            UPDATE knowledge_sources
            SET source_role = CASE
                    WHEN %s = 'salon' THEN 'salon'
                    ELSE source_role
                END,
                business_id = NULL,
                account_id = NULL,
                visibility = 'public',
                sensitivity_class = 'public',
                sync_mode = 'public_preview',
                sync_status = CASE WHEN status = 'active' THEN sync_status ELSE 'queued' END,
                next_sync_at = CASE
                    WHEN status = 'active' THEN next_sync_at
                    ELSE LEAST(COALESCE(next_sync_at, NOW()), NOW())
                END,
                metadata_json = metadata_json || %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (
                profile["source_role"],
                Json({
                    "auto_discovered": True,
                    "discovery_origin": discovery_origin,
                    "telegram_username": reference["username"],
                    "permission_reason": "public_preview_ready",
                    **profile["metadata"],
                }),
                existing["id"],
            ),
        )
        return existing

    shared_service = SHARED_SERVICE_TELEGRAM_SOURCES.get(reference["username"].lower())
    attribution = (
        {
            "source_owner": shared_service.get("owner"),
            "source_owner_type": "external_service",
            "source_owner_role": "service_provider",
            "source_owner_scope": "shared_service",
        }
        if shared_service
        else {"source_owner_type": "unconfirmed_public_source"}
    )
    residential_source = source_attribution_for_lead(lead).get("source_owner_type") == "residential_complex"
    return upsert_source(
        conn,
        source_type="telegram",
        external_key=f"telegram-public:{reference['username'].lower()}",
        title=(
            str(shared_service["title"])
            if shared_service
            else f"Telegram ЖК · @{reference['username']}"
            if residential_source
            else f"Telegram · @{reference['username']}"
        ),
        canonical_url=reference["canonical_url"],
        source_role="service" if shared_service else profile["source_role"],
        visibility="public",
        sensitivity_class="public",
        allowed_uses=[
            "market",
            "outreach",
            "localos_content",
            "client_content",
            "industry_recommendations",
        ],
        status="candidate",
        metadata={
            "auto_discovered": True,
            "discovery_origin": discovery_origin,
            "added_manually": discovery_origin == "manual_lead_contact",
            "telegram_username": reference["username"],
            "telegram_reference_type": "public_reference_unverified",
            "permission_reason": "public_preview_ready",
            **attribution,
            **profile["metadata"],
        },
        business_id=None,
        account_id=None,
        sync_mode="public_preview",
        sync_status="queued",
        backfill_days=180,
    )


def _link_source_to_company(
    cursor: Any,
    *,
    lead: dict[str, Any],
    source_id: str,
    reference: dict[str, str],
    discovery_origin: str,
) -> None:
    company_id = str(lead.get("company_id") or "").strip()
    if not company_id:
        return
    company_location_id = str(lead.get("company_location_id") or "").strip() or None
    cursor.execute(
        """
        INSERT INTO company_social_source_links (
            id, company_id, company_location_id, source_id, relation_type,
            confidence, verification_status, evidence_json, created_at, updated_at
        ) VALUES (%s, %s, %s, %s, 'unconfirmed', 0.6500, 'observed', %s, NOW(), NOW())
        ON CONFLICT (company_id, source_id, relation_type) DO UPDATE SET
            company_location_id = COALESCE(EXCLUDED.company_location_id, company_social_source_links.company_location_id),
            confidence = GREATEST(company_social_source_links.confidence, EXCLUDED.confidence),
            evidence_json = company_social_source_links.evidence_json || EXCLUDED.evidence_json,
            updated_at = NOW()
        """,
        (
            str(uuid.uuid4()),
            company_id,
            company_location_id,
            source_id,
            Json({
                "lead_id": str(lead.get("id") or ""),
                "discovery_origin": discovery_origin,
                "discovered_url": reference.get("discovered_url"),
                "canonical_url": reference.get("canonical_url"),
                "relation_claim": "unconfirmed_until_verified",
            }),
        ),
    )


def sync_discovered_telegram_sources(
    conn: Any,
    lead: dict[str, Any],
    links: list[Any] | None = None,
    *,
    discovery_origin: str = "map_parse",
) -> dict[str, int]:
    """Register public Telegram references once and link them to lead contexts."""
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
        for reference in references.values():
            shared_service = SHARED_SERVICE_TELEGRAM_SOURCES.get(reference["username"].lower())
            source = _register_global_public_source(
                conn,
                cursor,
                lead=lead,
                reference=reference,
                discovery_origin=discovery_origin,
            )
            source_id = str(source["id"])
            _link_source_to_company(
                cursor,
                lead=lead,
                source_id=source_id,
                reference=reference,
                discovery_origin=discovery_origin,
            )
            if not shared_service:
                for workstream in workstreams:
                    cursor.execute(
                        """
                        INSERT INTO lead_signal_links (
                            id, workstream_id, source_type, source_id, status, created_at, updated_at
                        ) VALUES (%s, %s, 'telegram_knowledge_source', %s, 'selected', NOW(), NOW())
                        ON CONFLICT (workstream_id, source_type, source_id)
                        DO UPDATE SET updated_at = NOW()
                        """,
                        (str(uuid.uuid4()), workstream["id"], source_id),
                    )
            sources_saved += 1
            queued += 1 if str(source.get("status") or "candidate") != "active" else 0
        return {"references": len(references), "sources": sources_saved, "queued": queued}
    finally:
        cursor.close()


def mark_discovered_source_classification(
    conn: Any,
    *,
    source_id: str,
    is_public_channel: bool | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    username: str | None = None,
    signal_source_eligible: bool | None = None,
    recipient_eligible: bool | None = None,
    classification_method: str = "public_preview",
    title: str | None = None,
    reason: str = "",
) -> list[str]:
    """Persist entity classification and keep non-users out of DM recipients."""
    normalized_entity_type = str(entity_type or "").strip().lower()
    if signal_source_eligible is None:
        signal_source_eligible = bool(is_public_channel)
    if recipient_eligible is None:
        recipient_eligible = normalized_entity_type == "user"
    reference_types = {
        "broadcast_channel": "public_channel",
        "channel": "public_channel",
        "megagroup": "public_group",
        "gigagroup": "public_group",
        "group_chat": "public_group",
        "user": "personal_account",
        "bot": "bot",
        "unknown": "unavailable",
    }
    reference_type = reference_types.get(normalized_entity_type)
    if not reference_type:
        reference_type = "public_channel" if signal_source_eligible else "personal_or_unavailable"
    should_block_recipient = bool(signal_source_eligible) or reference_type == "bot"
    status = "active" if signal_source_eligible else "paused"
    sync_status = "ready" if signal_source_eligible else "idle"
    last_sync_error = None if signal_source_eligible or recipient_eligible else (reason or "unsupported_telegram_entity")
    reason_code = {
        "public_channel": "telegram_public_channel_source",
        "public_group": "telegram_public_group_source",
        "bot": "telegram_bot_not_recipient",
    }.get(reference_type, "telegram_non_recipient_entity")
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
                status,
                sync_status,
                last_sync_error,
                Json({
                    "telegram_reference_type": reference_type,
                    "telegram_entity_type": normalized_entity_type or None,
                    "telegram_entity_id": str(entity_id or "").strip() or None,
                    "telegram_username": str(username or "").strip() or None,
                    "signal_source_eligible": bool(signal_source_eligible),
                    "recipient_eligible": bool(recipient_eligible),
                    "classified_at": datetime.now(timezone.utc).isoformat(),
                    "classification_method": classification_method,
                    "classification_reason": reason or classification_method,
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
            ("selected" if signal_source_eligible else "rejected", source_id),
        )
        workstream_ids = [str(_row_dict(row, cursor).get("workstream_id") or "") for row in cursor.fetchall() or []]
        workstream_ids = [item for item in workstream_ids if item]
        if should_block_recipient and workstream_ids:
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
                (Json({"reason_code": reason_code}), workstream_ids, canonical_url),
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
        elif recipient_eligible and workstream_ids:
            cursor.execute(
                """
                UPDATE lead_contact_points contact
                SET verification_status = 'found',
                    metadata_json = contact.metadata_json - 'reason_code',
                    updated_at = NOW()
                FROM lead_workstreams workstream
                WHERE workstream.id = ANY(%s::uuid[])
                  AND contact.lead_id = workstream.lead_id
                  AND contact.contact_type = 'telegram'
                  AND contact.normalized_value = %s
                  AND contact.verification_status = 'invalid'
                  AND contact.metadata_json->>'reason_code' IN (
                      'telegram_public_channel_source',
                      'telegram_public_group_source',
                      'telegram_non_recipient_entity'
                  )
                """,
                (workstream_ids, canonical_url),
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
    attribution = source_attribution_for_lead(lead)
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
        WHERE link.workstream_id = %s
          AND link.source_type = 'telegram_knowledge_source'
          AND link.status = 'selected'
          AND source.status = 'active'
          AND source.sync_status = 'ready'
          AND source.visibility = 'public'
          AND source.sensitivity_class = 'public'
          AND source.sync_mode = 'public_preview'
          AND COALESCE((source.metadata_json->>'signal_source_eligible')::boolean, TRUE) = TRUE
          AND source.allowed_uses @> '["outreach"]'::jsonb
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
        source_metadata = row.get("metadata_json") if isinstance(row.get("metadata_json"), dict) else {}
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
            "auto_discovered": bool(source_metadata.get("auto_discovered", True)),
            "discovery_origin": str(source_metadata.get("discovery_origin") or "map_parse"),
            "source_owner_type": attribution["source_owner_type"],
            "source_owner_name": str(lead.get("name") or "").strip(),
            "sender_business_is_owner": False,
        }))
    ranked.sort(key=lambda item: (item[0], item[1].get("message_date") or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
    return [item[1] for item in ranked[: max(1, min(limit, 10))]]
