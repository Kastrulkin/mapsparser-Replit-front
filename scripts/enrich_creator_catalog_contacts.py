#!/usr/bin/env python3
"""Research public creator contact routes without sending or queueing outreach."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from psycopg2.extras import Json, RealDictCursor

from database_manager import DatabaseManager


USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/127 Safari/537.36"
EMAIL_PATTERN = re.compile(r"(?<![\w.+-])([a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,})(?![\w.-])", re.IGNORECASE)
TELEGRAM_PATTERN = re.compile(r"(?<![\w@])@([a-zA-Z][a-zA-Z0-9_]{4,31})(?![\w])")
CONTACT_CONTEXT = re.compile(r"(\u0440\u0435\u043a\u043b\u0430\u043c|\u0441\u043e\u0442\u0440\u0443\u0434\u043d\u0438\u0447|\u043f\u0430\u0440\u0442\u043d[\u0435\u0451]р|\u0440\u0430\u0437\u043c\u0435\u0449|\u043f\u043e \u0432\u043e\u043f\u0440\u043e\u0441|\u0441\u0432\u044f\u0437|\u043a\u043e\u043d\u0442\u0430\u043a\u0442|advertis|collab|business|media[ -]?kit|booking)", re.IGNORECASE)
MANUAL_DM_PLATFORMS = {"instagram", "threads", "tiktok"}
PRIORITY = {
    "explicit_email": 100,
    "explicit_telegram": 95,
    "email": 100,
    "telegram": 95,
    "vk_messages": 85,
    "existing_contact": 80,
    "existing": 80,
    "website_contact": 70,
    "instagram_dm": 50,
    "tiktok_dm": 45,
    "threads_dm": 40,
    "cross_platform": 30,
}


def fetch(url: str) -> str:
    result = subprocess.run(
        ["curl", "-L", "--max-time", "8", "-A", USER_AGENT, "-s", url],
        capture_output=True,
        check=False,
        timeout=11,
    )
    if result.returncode != 0 or not result.stdout:
        return ""
    return result.stdout.decode("utf-8", errors="replace")


def json_value(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return fallback


def canonical(value: str) -> str:
    return value.strip().rstrip("/\n\r\t .,;:)")


def add_contact(
    contacts: list[dict[str, Any]],
    *,
    kind: str,
    value: str,
    source_url: str,
    source_channel_id: str | None,
    status: str,
    confidence: float,
    researched_at: str | None = None,
) -> None:
    normalized = canonical(value)
    if not normalized:
        return
    key = normalized.lower()
    if any(str(item["value"]).lower() == key for item in contacts):
        return
    contacts.append({
        "type": kind,
        "value": normalized,
        "source_url": source_url,
        "source_channel_id": source_channel_id,
        "status": status,
        "confidence": confidence,
        "researched_at": researched_at or datetime.now(timezone.utc).isoformat(),
    })


def merge_contact(contacts: list[dict[str, Any]], contact: dict[str, Any]) -> None:
    add_contact(
        contacts,
        kind=str(contact["type"]),
        value=str(contact["value"]),
        source_url=str(contact.get("source_url") or ""),
        source_channel_id=str(contact.get("source_channel_id") or "") or None,
        status=str(contact["status"]),
        confidence=float(contact["confidence"]),
        researched_at=str(contact.get("researched_at") or "") or None,
    )


def extract_explicit_contacts(
    text: str,
    *,
    source_url: str,
    source_channel_id: str | None,
) -> list[dict[str, Any]]:
    contacts: list[dict[str, Any]] = []
    for email in EMAIL_PATTERN.findall(text):
        add_contact(
            contacts,
            kind="email",
            value=email.lower(),
            source_url=source_url,
            source_channel_id=source_channel_id,
            status="public_explicit",
            confidence=0.92,
        )
    for context_match in CONTACT_CONTEXT.finditer(text):
        window = text[max(0, context_match.start() - 160):min(len(text), context_match.end() + 260)]
        for handle in TELEGRAM_PATTERN.findall(window):
            add_contact(
                contacts,
                kind="telegram",
                value=f"https://t.me/{handle}",
                source_url=source_url,
                source_channel_id=source_channel_id,
                status="public_explicit",
                confidence=0.9,
            )
    return contacts


def same_as_routes(document: str) -> list[str]:
    routes: list[str] = []
    for raw in re.findall(r'"sameAs":\[(.*?)\]', document, flags=re.DOTALL):
        routes.extend(re.findall(r'"(https?://[^"\\]+)"', raw))
    return list(dict.fromkeys(value.replace("\\u0026", "&").replace("\\/", "/") for value in routes))


def research_profile(profile: dict[str, Any]) -> dict[str, Any]:
    contacts: list[dict[str, Any]] = []
    existing = str(profile.get("preferred_contact") or "").strip()
    if existing:
        add_contact(
            contacts,
            kind="existing",
            value=existing,
            source_url=str(profile.get("contact_source_url") or ""),
            source_channel_id=None,
            status="existing_needs_periodic_confirmation",
            confidence=0.8,
        )
    description = str(profile.get("description") or "")
    channels = [item for item in json_value(profile.get("channels_json"), []) if isinstance(item, dict)]
    for channel in channels:
        platform = str(channel.get("platform") or "")
        url = str(channel.get("canonical_url") or "")
        channel_id = str(channel.get("id") or "") or None
        metadata = json_value(channel.get("metadata_json"), {})
        observed_identity = json_value(metadata.get("observed_identity"), {})
        stored_text = " ".join([
            description,
            str(observed_identity.get("description") or ""),
            str(metadata.get("description") or ""),
        ])
        for contact in extract_explicit_contacts(stored_text, source_url=url, source_channel_id=channel_id):
            merge_contact(contacts, contact)
        if platform == "telegram":
            document = fetch(url)
            for contact in extract_explicit_contacts(document, source_url=url, source_channel_id=channel_id):
                merge_contact(contacts, contact)
        elif platform == "youtube":
            about_url = f"{url.rstrip('/')}/about?hl=en"
            document = fetch(about_url)
            for contact in extract_explicit_contacts(document, source_url=about_url, source_channel_id=channel_id):
                merge_contact(contacts, contact)
            for route in same_as_routes(document):
                lowered = route.lower()
                if any(marker in lowered for marker in ("youtube.com", "youtu.be", "boosty.to", "patreon.com", "donationalerts.com")):
                    continue
                route_type = "cross_platform"
                if "instagram.com/" in lowered:
                    route_type = "instagram_dm"
                elif "tiktok.com/" in lowered:
                    route_type = "tiktok_dm"
                elif "threads.net/" in lowered or "threads.com/" in lowered:
                    route_type = "threads_dm"
                add_contact(
                    contacts,
                    kind=route_type,
                    value=route,
                    source_url=about_url,
                    source_channel_id=channel_id,
                    status="cross_platform_needs_confirmation",
                    confidence=0.7,
                )
        elif platform == "vk":
            document = fetch(url)
            for contact in extract_explicit_contacts(document, source_url=url, source_channel_id=channel_id):
                merge_contact(contacts, contact)
            vk_handle = str(channel.get("username") or "").strip()
            if vk_handle and re.search(r"(\u043d\u0430\u043f\u0438\u0441\u0430\u0442\u044c \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0435|community_messages|vk\.me/)", document, flags=re.IGNORECASE):
                add_contact(
                    contacts,
                    kind="vk_messages",
                    value=f"https://vk.me/{vk_handle}",
                    source_url=url,
                    source_channel_id=channel_id,
                    status="public_message_route",
                    confidence=0.82,
                )
        elif platform in MANUAL_DM_PLATFORMS:
            add_contact(
                contacts,
                kind=f"{platform}_dm",
                value=url,
                source_url=url,
                source_channel_id=channel_id,
                status="manual_dm_needs_confirmation",
                confidence=0.55,
            )
    contacts.sort(key=lambda item: (-PRIORITY.get(str(item["type"]), 0), -float(item["confidence"]), str(item["value"])))
    preferred = contacts[0] if contacts else None
    return {
        "profile_id": str(profile["id"]),
        "display_name": str(profile.get("display_name") or ""),
        "existing_contact": existing or None,
        "preferred_contact": preferred,
        "alternatives": contacts[1:6],
        "contact_count": len(contacts),
        "state": "public_explicit" if preferred and preferred["status"] == "public_explicit" else "manual_route_needs_confirmation" if preferred else "no_public_route_found",
    }


def load_profiles(cursor: Any, limit: int) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT profile.id, profile.display_name, profile.description,
               commercial.preferred_contact,
               commercial.metadata_json->>'contact_source_url' AS contact_source_url,
               COALESCE(JSONB_AGG(JSONB_BUILD_OBJECT(
                   'id', channel.id,
                   'platform', channel.platform,
                   'canonical_url', channel.canonical_url,
                   'username', channel.username,
                   'metadata_json', channel.metadata_json
               ) ORDER BY channel.platform) FILTER (WHERE channel.id IS NOT NULL), '[]'::jsonb) AS channels_json
        FROM creator_profiles profile
        LEFT JOIN creator_channels channel ON channel.creator_profile_id = profile.id
        LEFT JOIN creator_commercial_profiles commercial ON commercial.creator_profile_id = profile.id
        GROUP BY profile.id, commercial.creator_profile_id, commercial.preferred_contact, commercial.metadata_json
        ORDER BY profile.updated_at DESC, profile.id
        LIMIT %s
        """,
        (limit,),
    )
    return [dict(row) for row in cursor.fetchall()]


def apply_results(cursor: Any, results: list[dict[str, Any]]) -> dict[str, int]:
    inserted = 0
    preserved = 0
    channels_updated = 0
    metadata_updated = 0
    for result in results:
        preferred = result.get("preferred_contact")
        cursor.execute("SELECT preferred_contact FROM creator_commercial_profiles WHERE creator_profile_id = %s", (result["profile_id"],))
        existing_row = cursor.fetchone()
        existing = str(existing_row["preferred_contact"] or "").strip() if existing_row else ""
        preferred_reachable = bool(preferred and json_value(preferred.get("validation"), {}).get("reachable") is True)
        preferred_value = str(preferred["value"]) if preferred and preferred_reachable else None
        metadata = {
            "contact_research": {
                "version": "creator-contact-v1",
                "researched_at": datetime.now(timezone.utc).isoformat(),
                "state": result["state"],
                "preferred": preferred,
                "alternatives": result["alternatives"],
                "messages_sent": 0,
            },
            "public_contacts": [item for item in [preferred, *result["alternatives"]] if item],
        }
        cursor.execute(
            """
            INSERT INTO creator_commercial_profiles (
                id, creator_profile_id, preferred_contact, confirmation_status, metadata_json
            ) VALUES (gen_random_uuid(), %s, %s, 'observed', %s)
            ON CONFLICT (creator_profile_id) DO UPDATE SET
                preferred_contact = CASE
                    WHEN NULLIF(BTRIM(creator_commercial_profiles.preferred_contact), '') IS NULL
                    THEN EXCLUDED.preferred_contact
                    ELSE creator_commercial_profiles.preferred_contact
                END,
                metadata_json = creator_commercial_profiles.metadata_json || EXCLUDED.metadata_json,
                updated_at = NOW()
            """,
            (result["profile_id"], preferred_value, Json(metadata)),
        )
        metadata_updated += 1
        if existing:
            preserved += 1
        elif preferred_value:
            inserted += 1
        source_channel_id = preferred.get("source_channel_id") if preferred and preferred_reachable else None
        if source_channel_id and preferred:
            contactability = "advertising_contact" if preferred["status"] == "public_explicit" else "public_contact"
            cursor.execute(
                "UPDATE creator_channels SET contactability = %s, updated_at = NOW() WHERE id = %s",
                (contactability, source_channel_id),
            )
            channels_updated += cursor.rowcount
    return {"inserted": inserted, "preserved": preserved, "channels_updated": channels_updated, "metadata_updated": metadata_updated}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=2000)
    parser.add_argument("--workers", type=int, default=32)
    parser.add_argument("--output", type=Path, default=Path("outputs/creator-contact-research-20260825.json"))
    parser.add_argument("--input-report", type=Path)
    parser.add_argument("--apply", action="store_true")
    arguments = parser.parse_args()
    database = DatabaseManager()
    cursor = database.conn.cursor(cursor_factory=RealDictCursor)
    try:
        if arguments.input_report:
            summary = json.loads(arguments.input_report.read_text(encoding="utf-8"))
            results = [item for item in summary.get("results", []) if isinstance(item, dict)]
            if not summary.get("validation") or any(
                item.get("preferred_contact") and not json_value(item["preferred_contact"].get("validation"), {})
                for item in results
            ):
                raise ValueError("Для импорта нужен полностью валидированный отчёт")
            if arguments.apply:
                summary["apply"] = apply_results(cursor, results)
                database.conn.commit()
            else:
                database.conn.rollback()
                summary["apply"] = {"dry_run": True, "validated_report": True}
            print(json.dumps({key: value for key, value in summary.items() if key != "results"}, ensure_ascii=False, sort_keys=True))
            return 0
        profiles = load_profiles(cursor, max(1, min(arguments.limit, 5000)))
        results: list[dict[str, Any]] = []
        executor = ThreadPoolExecutor(max_workers=max(1, min(arguments.workers, 64)))
        try:
            futures = [executor.submit(research_profile, profile) for profile in profiles]
            for future in as_completed(futures):
                results.append(future.result())
        finally:
            executor.shutdown(wait=True)
        results.sort(key=lambda item: (item["state"], item["display_name"].lower()))
        summary: dict[str, Any] = {
            "schema_version": "1.0",
            "status": "public_contact_research_no_messages_sent",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "profile_count": len(results),
            "with_route": sum(bool(item["preferred_contact"]) for item in results),
            "explicit_public_contact": sum(item["state"] == "public_explicit" for item in results),
            "manual_route_needs_confirmation": sum(item["state"] == "manual_route_needs_confirmation" for item in results),
            "no_public_route_found": sum(item["state"] == "no_public_route_found" for item in results),
            "results": results,
        }
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        if arguments.apply:
            summary["apply"] = apply_results(cursor, results)
            database.conn.commit()
        else:
            database.conn.rollback()
            summary["apply"] = {"dry_run": True}
        print(json.dumps({key: value for key, value in summary.items() if key != "results"}, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception:
        database.conn.rollback()
        raise
    finally:
        database.close()


if __name__ == "__main__":
    raise SystemExit(main())
