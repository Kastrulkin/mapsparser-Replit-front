#!/usr/bin/env python3
"""Select untouched v4 email campaigns for the second follow-up review batch."""

import json
from pathlib import Path

from psycopg2.extras import RealDictCursor

from database_manager import get_db_connection


MANIFEST_PATH = Path("/app/debug_data/localos-1000-safe-final-manifest-v4-20260814.json")
EXPECTED_SHA = "4b21c0f98df7a726e0afae3504692e0b7c2a4faace8cdddf733590257a46a386"
EXCLUDED_FIRST_TOUCH_IDS = {
    "278fbd9b-099e-4f4c-92d8-be0940d9b6a6", "377b5a10-6f94-46d7-a272-82be2935ba69",
    "91768999-9b0e-491e-971b-a254ae6004e1", "5a44990d-ddb6-4bd3-98f0-8ff037f7ab09",
    "2eaa0456-53da-44d2-ac50-39d066fe2ee0", "904c7c7d-c4b5-4c9c-b55e-e85982312ad9",
    "036855ec-c6cb-4614-9860-fbd568b44835", "b45c92d1-d573-4c54-a70b-e10446d36e89",
    "e4d01c5e-cde9-40ce-b2b1-277979a58378", "dddb13f5-f975-4880-808a-1880b6907405",
    "cfcb52e9-ed92-4c81-8d6e-d28431e83a73", "3faf5e4a-65e8-4bbd-b6a1-76dff8644a2c",
    "81d05112-c7ab-4652-baf6-cf9bfd06d17a", "1f18629e-4b8c-460d-8f73-4cff7a027a59",
    "c120ed60-8264-4cfa-ad27-d78fa2f1b175", "fd4d61a6-868d-4223-8da7-efc13fb177d9",
    "8a44c65a-1f60-4f29-bfee-1189348ae150", "acbe68af-2d6b-4363-a6d3-fcdcaa2408e4",
    "24dd0497-df0f-48c5-998d-83f9ae5db693", "42632dd1-bfff-4c73-b226-034c6948171c",
    "eec099a7-1dc8-40c2-a447-ec7c71981471", "0de0ab17-fbcc-4e4c-9092-02fdac747b28",
    "b4fd28c5-ed44-4b81-a83b-43ee961e2476", "655252e2-7645-49ef-910b-bcb109afd61b",
    "8ed9698b-9fbe-45a9-b08e-e7ef9e4e8c23", "ffa3939c-17f9-4dea-b166-a6b3f081eaf6",
    "a4c53e8a-1ace-435e-b78a-05e73f39be61", "f106ead4-dbaa-4e28-8029-5a08fedb9a9f",
    "6458edba-5e57-42a2-8e5a-1602b7f1b879", "702b914f-1ce4-4fa8-89a5-51498ab27856",
    "bc710318-7fed-4ba4-9c4b-54c005fb3a87", "e508043d-db67-49d8-895c-5485c8282d28",
    "1f304a37-6b58-45d8-9a25-0ba7baa0102c", "bf88fd9e-1066-4e74-9f53-2b6855c7f13e",
    "74c81164-e73c-41f1-a0b6-fd290856b72e", "2588f100-a8bc-4552-9efb-b9c524513140",
    "6d5f7b89-d70a-4a08-a272-e092f06f8a8e", "d40dbba7-4623-47a3-b0fb-e6222704bf2d",
    "db240633-d2f4-410c-93a1-8e4206e5742b", "a8b9c709-8df7-41a6-b68e-79ba7b90faa9",
    "3ab0a45b-8271-4a22-ae6b-1c0c38319644", "e3385891-c79c-48c7-bb2a-75fdff785251",
    "6ff2e1ff-2983-44be-9917-17bf7bd6de91", "7745e1f8-b13f-47df-bb76-a5959d6c2881",
    "c40f43d1-f3f7-4be4-83ff-6c4407709db4",
}


def main():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("canonical_sha256") != EXPECTED_SHA:
        raise RuntimeError("manifest_canonical_sha_mismatch")
    rows = [
        row for row in manifest.get("touches") or []
        if row.get("channel") == "email"
        and int(row.get("sequence_index") or 0) == 0
        and row.get("touch_id") not in EXCLUDED_FIRST_TOUCH_IDS
        and str(row.get("name") or "").casefold() not in {"hairfcker", "diadema"}
    ]
    connection = get_db_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    selected = []
    try:
        for row in rows:
            cursor.execute(
                """
                SELECT t.status, c.lead_id, l.name, cp.normalized_value recipient,
                       cp.verification_status,
                       (SELECT COUNT(*) FROM outreach_campaign_touches t2
                        WHERE t2.campaign_id=c.id AND t2.sequence_index>0
                          AND t2.channel='email' AND t2.status<>'cancelled') later_email,
                       (SELECT COUNT(*) FROM outreach_suppressions s
                        WHERE s.lead_id=c.lead_id AND (s.expires_at IS NULL OR s.expires_at>NOW())) suppressions,
                       (SELECT COUNT(*) FROM outreach_inbound_events i
                        WHERE i.lead_id=c.lead_id AND (COALESCE(i.is_human,FALSE) OR COALESCE(i.stops_campaign,FALSE))) inbound,
                       (SELECT COUNT(*) FROM outreachreactions r WHERE r.lead_id=c.lead_id) reactions,
                       (SELECT COUNT(*) FROM outreach_sender_health_events h
                        WHERE h.campaign_id=c.id AND h.event_type='delivery_failed') delivery_failures,
                       (SELECT COUNT(DISTINCT cp2.lead_id) FROM lead_contact_points cp2
                        WHERE cp2.contact_type='email' AND lower(cp2.normalized_value)=lower(cp.normalized_value)) email_leads
                FROM outreach_campaign_touches t
                JOIN outreach_campaigns c ON c.id=t.campaign_id
                JOIN prospectingleads l ON l.id=c.lead_id
                LEFT JOIN lead_contact_points cp ON cp.id=t.contact_point_id
                WHERE t.id=%s AND c.id=%s AND c.lead_id=%s
                """,
                (row.get("touch_id"), row.get("campaign_id"), row.get("lead_id")),
            )
            runtime = dict(cursor.fetchone() or {})
            if not runtime:
                continue
            if runtime.get("status") not in {"sent", "manual_sent", "delivered"}:
                continue
            if any(int(runtime.get(key) or 0) for key in ("later_email", "suppressions", "inbound", "reactions", "delivery_failures")):
                continue
            if int(runtime.get("email_leads") or 0) != 1:
                continue
            if runtime.get("verification_status") not in {"confirmed_source", "valid_format", "found"}:
                continue
            selected.append({
                "name": row.get("name"), "first_touch_id": row.get("touch_id"),
                "lead_id": row.get("lead_id"), "campaign_id": row.get("campaign_id"),
                "recipient": row.get("recipient"), "first_angle": row.get("angle_type"),
            })
        print(json.dumps({"eligible_count": len(selected), "items": selected}, ensure_ascii=False, indent=2))
    finally:
        connection.rollback()
        connection.close()


if __name__ == "__main__":
    main()
