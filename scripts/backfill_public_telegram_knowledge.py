#!/usr/bin/env python3
"""Consolidate public Telegram knowledge sources and queue them for collection.

Dry-run is the default. Pass ``--apply`` only after a production backup.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from typing import Any

import psycopg2
from psycopg2.extras import Json, RealDictCursor


PUBLIC_USES = [
    "market",
    "outreach",
    "localos_content",
    "client_content",
    "industry_recommendations",
]


def _connect():
    return psycopg2.connect(os.environ["DATABASE_URL"], cursor_factory=RealDictCursor)


def _normalized_url(value: Any) -> str:
    return str(value or "").strip().rstrip("/").lower()


def _username(value: Any) -> str:
    normalized = _normalized_url(value)
    prefix = "https://t.me/"
    if not normalized.startswith(prefix):
        return ""
    result = normalized.removeprefix(prefix).split("/", 1)[0]
    return result if result and not result.startswith("+") and result != "joinchat" else ""


def _merge_source(cursor: Any, winner: dict[str, Any], loser: dict[str, Any]) -> None:
    winner_id = str(winner["id"])
    loser_id = str(loser["id"])
    cursor.execute(
        """
        INSERT INTO company_social_source_links (
            id, company_id, company_location_id, source_id, relation_type,
            confidence, verification_status, evidence_json, created_at, updated_at
        )
        SELECT gen_random_uuid(), company_id, company_location_id, %s, relation_type,
               confidence, verification_status, evidence_json, created_at, NOW()
        FROM company_social_source_links WHERE source_id = %s
        ON CONFLICT (company_id, source_id, relation_type) DO UPDATE SET
            company_location_id = COALESCE(
                company_social_source_links.company_location_id,
                EXCLUDED.company_location_id
            ),
            confidence = GREATEST(company_social_source_links.confidence, EXCLUDED.confidence),
            evidence_json = company_social_source_links.evidence_json || EXCLUDED.evidence_json,
            updated_at = NOW()
        """,
        (winner_id, loser_id),
    )
    cursor.execute("DELETE FROM company_social_source_links WHERE source_id = %s", (loser_id,))
    cursor.execute(
        """
        INSERT INTO knowledge_source_subscriptions (
            id, business_id, source_id, purposes_json, topics_json,
            schedule_json, is_active, created_at, updated_at
        )
        SELECT gen_random_uuid(), business_id, %s, purposes_json, topics_json,
               schedule_json, is_active, created_at, NOW()
        FROM knowledge_source_subscriptions WHERE source_id = %s
        ON CONFLICT (business_id, source_id) DO UPDATE SET
            is_active = knowledge_source_subscriptions.is_active OR EXCLUDED.is_active,
            updated_at = NOW()
        """,
        (winner_id, loser_id),
    )
    cursor.execute("DELETE FROM knowledge_source_subscriptions WHERE source_id = %s", (loser_id,))
    cursor.execute(
        """
        INSERT INTO lead_signal_links (
            id, workstream_id, source_type, source_id, status, created_at, updated_at
        )
        SELECT gen_random_uuid(), workstream_id, source_type, %s, status, created_at, NOW()
        FROM lead_signal_links
        WHERE source_type = 'telegram_knowledge_source' AND source_id = %s
        ON CONFLICT (workstream_id, source_type, source_id) DO UPDATE SET
            status = EXCLUDED.status,
            updated_at = NOW()
        """,
        (winner_id, loser_id),
    )
    cursor.execute(
        "DELETE FROM lead_signal_links WHERE source_type = 'telegram_knowledge_source' AND source_id = %s",
        (loser_id,),
    )
    cursor.execute(
        """
        DELETE FROM knowledge_documents losing
        USING knowledge_documents kept
        WHERE losing.source_id = %s AND kept.source_id = %s
          AND losing.external_id = kept.external_id
        """,
        (loser_id, winner_id),
    )
    cursor.execute("UPDATE knowledge_documents SET source_id = %s WHERE source_id = %s", (winner_id, loser_id))
    cursor.execute("UPDATE knowledge_analysis_runs SET source_id = %s WHERE source_id = %s", (winner_id, loser_id))
    cursor.execute("UPDATE knowledge_evidence SET source_id = %s WHERE source_id = %s", (winner_id, loser_id))
    cursor.execute(
        "UPDATE telegram_opportunity_sources SET knowledge_source_id = %s WHERE knowledge_source_id = %s",
        (winner_id, loser_id),
    )
    cursor.execute(
        """
        UPDATE knowledge_sources kept
        SET metadata_json = %s || kept.metadata_json,
            allowed_uses = %s,
            last_collected_at = GREATEST(kept.last_collected_at, %s),
            updated_at = NOW()
        WHERE kept.id = %s
        """,
        (
            Json(loser.get("metadata_json") or {}),
            Json(PUBLIC_USES),
            loser.get("last_collected_at"),
            winner_id,
        ),
    )
    cursor.execute("DELETE FROM knowledge_sources WHERE id = %s", (loser_id,))


def run(*, apply: bool) -> dict[str, int]:
    conn = _connect()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            SELECT * FROM knowledge_sources
            WHERE source_type = 'telegram'
              AND visibility = 'public'
              AND canonical_url LIKE 'https://t.me/%%'
            ORDER BY CASE status WHEN 'active' THEN 0 WHEN 'candidate' THEN 1 ELSE 2 END,
                     last_collected_at DESC NULLS LAST,
                     created_at
            """
        )
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in cursor.fetchall() or []:
            groups[_normalized_url(row.get("canonical_url"))].append(dict(row))
        duplicate_groups = [group for group in groups.values() if len(group) > 1]
        merged = 0
        for group in duplicate_groups:
            winner = group[0]
            for loser in group[1:]:
                _merge_source(cursor, winner, loser)
                merged += 1

        cursor.execute(
            """
            UPDATE knowledge_sources
            SET visibility = 'public', sensitivity_class = 'public', status = 'active',
                source_role = CASE WHEN source_role = 'unknown' THEN 'community' ELSE source_role END,
                allowed_uses = %s, business_id = NULL, account_id = NULL,
                metadata_json = metadata_json || %s, updated_at = NOW()
            WHERE source_type = 'telegram' AND sensitivity_class = 'internal'
              AND business_id IS NULL AND account_id IS NULL
            RETURNING id
            """,
            (Json(PUBLIC_USES), Json({"public_confirmed_by_owner": True})),
        )
        promoted_source_ids = [str(row["id"]) for row in cursor.fetchall() or []]
        promoted_documents = 0
        if promoted_source_ids:
            cursor.execute(
                """
                UPDATE knowledge_documents
                SET sensitivity_class = 'public', allowed_uses = %s,
                    business_id = NULL, updated_at = NOW()
                WHERE source_id = ANY(%s::uuid[])
                """,
                (Json(PUBLIC_USES), promoted_source_ids),
            )
            promoted_documents = max(int(cursor.rowcount or 0), 0)

        cursor.execute(
            """
            UPDATE knowledge_sources
            SET business_id = NULL, account_id = NULL,
                visibility = 'public', sensitivity_class = 'public',
                sync_mode = 'public_preview', sync_status = 'queued',
                allowed_uses = %s,
                next_sync_at = LEAST(COALESCE(next_sync_at, NOW()), NOW()),
                metadata_json = metadata_json || %s,
                updated_at = NOW()
            WHERE source_type = 'telegram' AND status = 'candidate'
              AND canonical_url LIKE 'https://t.me/%%'
              AND canonical_url NOT LIKE '%%/+%%'
              AND canonical_url NOT LIKE '%%/joinchat%%'
            RETURNING id
            """,
            (
                Json(PUBLIC_USES),
                Json({
                    "auto_discovered": True,
                    "permission_reason": "public_preview_ready",
                }),
            ),
        )
        queued_sources = len(cursor.fetchall() or [])

        cursor.execute(
            """
            INSERT INTO company_social_source_links (
                id, company_id, company_location_id, source_id, relation_type,
                confidence, verification_status, evidence_json, created_at, updated_at
            )
            SELECT DISTINCT ON (lead.company_id, source.id)
                   gen_random_uuid(), lead.company_id, lead.company_location_id, source.id,
                   'unconfirmed', 0.6500, 'observed',
                   jsonb_build_object(
                       'lead_id', lead.id,
                       'workstream_id', workstream.id,
                       'discovery_origin', COALESCE(source.metadata_json->>'discovery_origin', 'legacy_backfill'),
                       'canonical_url', source.canonical_url,
                       'relation_claim', 'unconfirmed_until_verified'
                   ),
                   NOW(), NOW()
            FROM lead_signal_links signal
            JOIN lead_workstreams workstream ON workstream.id = signal.workstream_id
            JOIN prospectingleads lead ON lead.id = workstream.lead_id
            JOIN knowledge_sources source ON source.id::text = signal.source_id
            WHERE signal.source_type = 'telegram_knowledge_source'
              AND lead.company_id IS NOT NULL
            ORDER BY lead.company_id, source.id, workstream.updated_at DESC
            ON CONFLICT (company_id, source_id, relation_type) DO UPDATE SET
                company_location_id = COALESCE(
                    EXCLUDED.company_location_id,
                    company_social_source_links.company_location_id
                ),
                confidence = GREATEST(company_social_source_links.confidence, EXCLUDED.confidence),
                evidence_json = company_social_source_links.evidence_json || EXCLUDED.evidence_json,
                updated_at = NOW()
            """
        )
        company_links_created = max(int(cursor.rowcount or 0), 0)

        cursor.execute(
            """
            SELECT id, canonical_url FROM knowledge_sources
            WHERE source_type = 'telegram' AND visibility = 'public'
              AND sensitivity_class = 'public' AND canonical_url LIKE 'https://t.me/%'
            """
        )
        normalized_keys = 0
        for source in cursor.fetchall() or []:
            username = _username(source.get("canonical_url"))
            if not username:
                continue
            target_key = f"telegram-public:{username}"
            cursor.execute(
                """
                UPDATE knowledge_sources SET external_key = %s, updated_at = NOW()
                WHERE id = %s
                  AND NOT EXISTS (
                      SELECT 1 FROM knowledge_sources other
                      WHERE other.source_type = 'telegram' AND other.external_key = %s
                        AND other.id <> %s
                  )
                """,
                (target_key, source["id"], target_key, source["id"]),
            )
            normalized_keys += max(int(cursor.rowcount or 0), 0)

        result = {
            "duplicate_groups": len(duplicate_groups),
            "sources_merged": merged,
            "legacy_sources_promoted": len(promoted_source_ids),
            "legacy_documents_promoted": promoted_documents,
            "candidate_sources_queued": queued_sources,
            "company_source_links_upserted": company_links_created,
            "external_keys_normalized": normalized_keys,
        }
        if apply:
            conn.commit()
        else:
            conn.rollback()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    result = run(apply=bool(args.apply))
    print(json.dumps({"mode": "apply" if args.apply else "dry-run", **result}, ensure_ascii=False))


if __name__ == "__main__":
    main()
