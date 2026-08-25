from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from psycopg2.extras import Json

from services.creator_taxonomy_service import classify_creator_profile, upsert_creator_taxonomy


PLATFORMS = {"telegram", "vk", "website", "instagram", "threads", "tiktok", "youtube", "other"}
PROFILE_TYPES = {"author", "channel", "community", "media", "aggregator"}
CONTACTABILITY = {"unknown", "public_contact", "advertising_contact", "manual_only", "not_contactable"}


def _json(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return fallback


def _text_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def canonical_creator_url(value: Any) -> str:
    raw = str(value or "").strip().rstrip("/")
    if raw.startswith("@"):
        return f"https://t.me/{raw[1:]}"
    return raw


def creator_platform(url: Any, fallback: Any = "other") -> str:
    lowered = canonical_creator_url(url).lower()
    if "t.me/" in lowered or "telegram.me/" in lowered:
        return "telegram"
    if "vk.com/" in lowered:
        return "vk"
    if "instagram.com/" in lowered:
        return "instagram"
    if "threads.net/" in lowered or "threads.com/" in lowered:
        return "threads"
    if "tiktok.com/" in lowered:
        return "tiktok"
    if "youtube.com/" in lowered or "youtu.be/" in lowered:
        return "youtube"
    normalized_fallback = str(fallback or "other").strip().lower()
    if normalized_fallback in PLATFORMS:
        return normalized_fallback
    return "website" if lowered.startswith(("http://", "https://")) else "other"


def _profile_type(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in PROFILE_TYPES:
        return normalized
    if normalized in {"author_or_channel", "creator", "blogger"}:
        return "author"
    return "channel"


def _verification_status(channel: dict[str, Any]) -> str:
    explicit = str(channel.get("verification_status") or "").strip().lower()
    if explicit in {"pending", "verified", "stale", "mismatch", "inaccessible", "excluded"}:
        if explicit == "original_profile_opened":
            return "verified"
        return explicit
    if explicit in {"original_profile_opened", "public_profile_opened", "source_verified"}:
        return "verified"
    return "pending"


def _observed_at(entity: dict[str, Any], channel: dict[str, Any]) -> datetime:
    candidates = [
        channel.get("researched_at"),
        channel.get("observed_at"),
        _json(entity.get("research"), {}).get("researched_at"),
        entity.get("researched_at"),
    ]
    for candidate in candidates:
        if isinstance(candidate, datetime):
            return candidate if candidate.tzinfo else candidate.replace(tzinfo=timezone.utc)
        text = str(candidate or "").strip().replace("Z", "+00:00")
        if not text:
            continue
        try:
            parsed = datetime.fromisoformat(text)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return datetime.now(timezone.utc)


def _entity_channels(entity: dict[str, Any]) -> list[dict[str, Any]]:
    channels = [dict(item) for item in _json(entity.get("channels"), []) if isinstance(item, dict)]
    if channels:
        return channels
    urls = _text_list(entity.get("canonical_urls"))
    platforms = _text_list(entity.get("platforms"))
    if not urls:
        url = canonical_creator_url(entity.get("url") or entity.get("canonical_url"))
        urls = [url] if url else []
    return [
        {
            "canonical_url": url,
            "platform": platforms[index] if index < len(platforms) else creator_platform(url),
            "username": str(entity.get("primary_handle") or entity.get("username") or "").strip(),
        }
        for index, url in enumerate(urls)
    ]


def _stable_evidence_key(profile_id: str, source_url: str, summary: str) -> str:
    value = f"{profile_id}\n{source_url}\n{summary}".encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def upsert_creator_catalog_entity(
    cursor: Any,
    *,
    entity: dict[str, Any],
    public_contact: dict[str, Any] | None = None,
    import_source: str = "catalog_import",
) -> dict[str, Any]:
    name = str(entity.get("display_name") or entity.get("name") or "").strip()
    channels = _entity_channels(entity)
    channels = [item for item in channels if canonical_creator_url(item.get("canonical_url") or item.get("url"))]
    if not name or not channels:
        raise ValueError("Для каталога нужны имя и хотя бы одна публичная ссылка")

    profile_ids: set[str] = set()
    for channel in channels:
        url = canonical_creator_url(channel.get("canonical_url") or channel.get("url"))
        platform = creator_platform(url, channel.get("platform"))
        cursor.execute(
            """
            SELECT creator_profile_id FROM creator_channels
            WHERE platform = %s AND LOWER(RTRIM(canonical_url, '/')) = LOWER(RTRIM(%s, '/'))
            LIMIT 1
            """,
            (platform, url),
        )
        row = cursor.fetchone()
        if row:
            profile_ids.add(str(row["creator_profile_id"] if hasattr(row, "keys") else row[0]))
    if len(profile_ids) > 1:
        raise ValueError("Ссылки уже принадлежат нескольким профилям; требуется ручное объединение")
    profile_id = next(iter(profile_ids), str(uuid.uuid4()))

    cities = _text_list(entity.get("cities"))
    geography = _json(entity.get("geography"), {})
    city = str(geography.get("home_city") or entity.get("primary_city") or entity.get("city") or "").strip() or None
    area = str(geography.get("home_district") or entity.get("primary_area") or entity.get("area") or "").strip() or None
    topics = _text_list(entity.get("topics") or entity.get("matched_topics"))
    qualification = _json(entity.get("qualification"), {})
    metadata = {
        "catalog_entity_id": str(entity.get("entity_id") or entity.get("candidate_id") or "").strip() or None,
        "import_source": import_source,
        "qualification": qualification,
        "research": _json(entity.get("research"), {}),
        "discovery_geography": {
            "cities": cities,
            "areas": _text_list(entity.get("areas") or entity.get("districts")),
            "is_verified_home_geography": False,
        },
        "limitations": _text_list(entity.get("limitations")),
        "last_catalog_import_at": datetime.now(timezone.utc).isoformat(),
    }
    cursor.execute("SELECT id FROM creator_profiles WHERE id = %s", (profile_id,))
    existing = cursor.fetchone()
    if existing:
        cursor.execute(
            """
            UPDATE creator_profiles SET
                display_name = %s,
                description = COALESCE(NULLIF(%s, ''), description),
                primary_city = COALESCE(NULLIF(%s, ''), primary_city),
                primary_area = COALESCE(NULLIF(%s, ''), primary_area),
                topics_json = CASE WHEN %s::jsonb = '[]'::jsonb THEN topics_json ELSE %s::jsonb END,
                metadata_json = metadata_json || %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (name, str(entity.get("description") or ""), city or "", area or "", Json(topics), Json(topics), Json(metadata), profile_id),
        )
    else:
        cursor.execute(
            """
            INSERT INTO creator_profiles (
                id, profile_type, display_name, description, primary_city, primary_area,
                topics_json, verification_status, metadata_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'observed', %s)
            """,
            (
                profile_id, _profile_type(entity.get("profile_type")), name,
                str(entity.get("description") or "").strip() or None, city, area, Json(topics), Json(metadata),
            ),
        )

    for channel in channels:
        url = canonical_creator_url(channel.get("canonical_url") or channel.get("url"))
        platform = creator_platform(url, channel.get("platform"))
        observed_at = _observed_at(entity, channel)
        status = _verification_status(channel)
        channel_metadata = {
            "catalog_entity_id": metadata["catalog_entity_id"],
            "import_source": import_source,
            "source_url": channel.get("source_url"),
            "discovery_source_url": channel.get("discovery_source_url"),
            "secondary_source_url": channel.get("secondary_source_url"),
            "evidence_url": channel.get("evidence_url"),
            "follower_count": channel.get("follower_count"),
            "audience_band": channel.get("audience_band"),
            "observed_identity": {"title": name, "description": str(entity.get("description") or "")},
        }
        metrics = dict(_json(channel.get("public_metrics"), {}))
        if channel.get("follower_count") is not None:
            metrics["followers"] = channel.get("follower_count")
        contactability = str(entity.get("contactability") or channel.get("contactability") or "manual_only").strip()
        if contactability not in CONTACTABILITY:
            contactability = "manual_only"
        cursor.execute(
            """
            INSERT INTO creator_channels (
                id, creator_profile_id, platform, canonical_url, username, contactability,
                public_metrics_json, metadata_json, last_observed_at, verification_status,
                verified_at, next_check_at, verification_note
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (platform, canonical_url) DO UPDATE SET
                creator_profile_id = EXCLUDED.creator_profile_id,
                username = COALESCE(EXCLUDED.username, creator_channels.username),
                contactability = EXCLUDED.contactability,
                public_metrics_json = creator_channels.public_metrics_json || EXCLUDED.public_metrics_json,
                metadata_json = creator_channels.metadata_json || EXCLUDED.metadata_json,
                last_observed_at = EXCLUDED.last_observed_at,
                verification_status = CASE
                    WHEN creator_channels.verification_status IN ('mismatch', 'excluded') THEN creator_channels.verification_status
                    ELSE EXCLUDED.verification_status
                END,
                verified_at = COALESCE(EXCLUDED.verified_at, creator_channels.verified_at),
                next_check_at = LEAST(COALESCE(creator_channels.next_check_at, EXCLUDED.next_check_at), EXCLUDED.next_check_at),
                updated_at = NOW()
            """,
            (
                str(uuid.uuid4()), profile_id, platform, url,
                str(channel.get("username") or entity.get("primary_handle") or "").strip() or None,
                contactability, Json(metrics), Json(channel_metadata), observed_at, status,
                observed_at if status == "verified" else None,
                observed_at + timedelta(days=30),
                "Импортирован из проверенной публичной базы" if status == "verified" else "Ожидает перепроверки",
            ),
        )

    evidence_items = [item for item in _json(entity.get("evidence"), []) if isinstance(item, dict)]
    evidence_items.extend([item for item in _json(entity.get("signals"), []) if isinstance(item, dict)])
    for evidence in evidence_items:
        source_url = canonical_creator_url(evidence.get("source_url"))
        summary = str(evidence.get("observed") or evidence.get("summary") or "").strip()
        if not summary:
            continue
        evidence_key = _stable_evidence_key(profile_id, source_url, summary)
        cursor.execute(
            """
            SELECT id FROM creator_evidence
            WHERE creator_profile_id = %s AND metadata_json->>'catalog_evidence_key' = %s
            LIMIT 1
            """,
            (profile_id, evidence_key),
        )
        if cursor.fetchone():
            continue
        cursor.execute(
            """
            INSERT INTO creator_evidence (
                id, creator_profile_id, evidence_type, source_url, summary_text,
                confidence, observed_at, stale_after, metadata_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                str(uuid.uuid4()), profile_id,
                str(evidence.get("source_type") or evidence.get("kind") or "public_profile"),
                source_url or None, summary, float(evidence.get("confidence") or 0.8),
                _observed_at(entity, evidence), _observed_at(entity, evidence) + timedelta(days=90),
                Json({"catalog_evidence_key": evidence_key, "import_source": import_source}),
            ),
        )

    contact = dict(public_contact or {})
    preferred_contact = str(contact.get("value") or entity.get("preferred_contact") or "").strip() or None
    if preferred_contact:
        contact_status = str(contact.get("status") or "public_unverified")
        commercial_metadata = {
            "public_contacts": [contact],
            "contact_source_url": contact.get("source_url"),
            "contact_confidence": contact.get("confidence"),
            "contact_status": contact_status,
            "import_source": import_source,
        }
        cursor.execute(
            """
            INSERT INTO creator_commercial_profiles (
                id, creator_profile_id, preferred_contact, confirmation_status, metadata_json
            ) VALUES (%s, %s, %s, 'observed', %s)
            ON CONFLICT (creator_profile_id) DO UPDATE SET
                preferred_contact = COALESCE(EXCLUDED.preferred_contact, creator_commercial_profiles.preferred_contact),
                metadata_json = creator_commercial_profiles.metadata_json || EXCLUDED.metadata_json,
                updated_at = NOW()
            """,
            (str(uuid.uuid4()), profile_id, preferred_contact, Json(commercial_metadata)),
        )

    taxonomy = classify_creator_profile({
        "display_name": name,
        "description": str(entity.get("description") or "").strip() or None,
        "metadata": metadata,
        "channels": channels,
        "evidence": evidence_items,
        "commercial": {
            "formats": _text_list(entity.get("formats")),
        },
    })
    upsert_creator_taxonomy(cursor, profile_id=profile_id, taxonomy=taxonomy)

    return {
        "profile_id": profile_id,
        "channels": len(channels),
        "evidence": len(evidence_items),
        "contact": preferred_contact,
        "classification_status": taxonomy["classification_status"],
    }


def import_creator_catalog(
    cursor: Any,
    *,
    entities: list[dict[str, Any]],
    contacts_by_entity_id: dict[str, dict[str, Any]] | None = None,
    import_source: str = "catalog_import",
) -> dict[str, Any]:
    contacts = contacts_by_entity_id or {}
    imported = 0
    errors: list[dict[str, Any]] = []
    channel_count = 0
    for index, entity in enumerate(entities):
        cursor.execute("SAVEPOINT creator_catalog_item")
        try:
            entity_id = str(entity.get("entity_id") or entity.get("candidate_id") or "")
            result = upsert_creator_catalog_entity(
                cursor,
                entity=entity,
                public_contact=contacts.get(entity_id),
                import_source=import_source,
            )
            imported += 1
            channel_count += int(result["channels"])
            cursor.execute("RELEASE SAVEPOINT creator_catalog_item")
        except (ValueError, LookupError) as exc:
            cursor.execute("ROLLBACK TO SAVEPOINT creator_catalog_item")
            cursor.execute("RELEASE SAVEPOINT creator_catalog_item")
            errors.append({"row": index + 1, "entity_id": entity.get("entity_id"), "error": str(exc)})
    return {
        "imported_count": imported,
        "channel_count": channel_count,
        "error_count": len(errors),
        "errors": errors,
        "import_source": import_source,
    }
