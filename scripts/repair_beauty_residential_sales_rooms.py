#!/usr/bin/env python3
"""Version and replace generic beauty-to-residential sales-room proposals."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import Json, RealDictCursor


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
for candidate in (str(REPO_ROOT), str(SRC_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from api.admin_prospecting import (  # noqa: E402
    SALES_ROOM_DATA_TEMPLATE,
    SALES_ROOM_MODE_PARTNER,
    _build_sales_room_proposal,
    _create_sales_room_proposal_version,
    _ensure_sales_room_proposal_version,
)
from core.ai_learning import record_ai_learning_event  # noqa: E402


def _connect():
    return psycopg2.connect(os.environ["DATABASE_URL"], cursor_factory=RealDictCursor)


def _load_business(cur, business_id: str) -> dict[str, Any]:
    cur.execute(
        """
        SELECT id, name, business_type, industry, categories
        FROM businesses
        WHERE id = %s
        LIMIT 1
        """,
        (business_id,),
    )
    row = cur.fetchone()
    if not row:
        raise ValueError("business not found")
    return dict(row)


def _load_superadmin_user_id(cur) -> str | None:
    cur.execute(
        """
        SELECT id
        FROM users
        WHERE COALESCE(is_superadmin, FALSE) = TRUE
        ORDER BY created_at ASC NULLS LAST, id ASC
        LIMIT 1
        """
    )
    row = cur.fetchone()
    return str(row["id"]) if row and row.get("id") else None


def _load_rooms(cur, business_id: str) -> list[dict[str, Any]]:
    cur.execute(
        """
        SELECT sr.*, pl.name, pl.category, pl.address, pl.city
        FROM sales_rooms sr
        JOIN prospectingleads pl ON pl.id = sr.lead_id
        WHERE sr.business_id = %s
          AND sr.mode = %s
          AND LOWER(COALESCE(pl.category, '')) LIKE '%%жилой комплекс%%'
        ORDER BY pl.name, sr.created_at
        FOR UPDATE OF sr
        """,
        (business_id, SALES_ROOM_MODE_PARTNER),
    )
    return [dict(row) for row in (cur.fetchall() or [])]


def _repair_room(
    cur,
    *,
    room: dict[str, Any],
    business: dict[str, Any],
    user_id: str | None,
) -> dict[str, Any]:
    previous_proposal = room.get("proposal_json") if isinstance(room.get("proposal_json"), dict) else {}
    previous_body = str(previous_proposal.get("body_text") or "").strip()
    lead = {
        "id": room.get("lead_id"),
        "name": room.get("name"),
        "category": room.get("category"),
        "address": room.get("address"),
        "city": room.get("city"),
    }
    proposal = _build_sales_room_proposal(
        mode=SALES_ROOM_MODE_PARTNER,
        data_mode=str(room.get("data_mode") or SALES_ROOM_DATA_TEMPLATE),
        lead=lead,
        business_name=str(business.get("name") or "бизнес").strip() or "бизнес",
        audit_json={},
        match_json=room.get("match_json") if isinstance(room.get("match_json"), dict) else {},
        business_profile=business,
    )
    next_body = str(proposal.get("body_text") or "").strip()
    if not next_body or next_body == previous_body:
        return {"room_id": str(room.get("id") or ""), "lead": str(room.get("name") or ""), "changed": False}

    room_id = str(room.get("id") or "")
    _ensure_sales_room_proposal_version(
        cur,
        room_id=room_id,
        body_text=previous_body,
        author_name=str(business.get("name") or ""),
        metadata={"source": "existing_room_proposal_before_beauty_residential_correction"},
    )
    version = _create_sales_room_proposal_version(
        cur,
        room_id=room_id,
        body_text=next_body,
        author_name="LocalOS",
        author_contact="",
        metadata={
            "source": "manual_product_correction_beauty_residential_v1",
            "lead_id": str(room.get("lead_id") or ""),
            "recipient_type": "residential_complex",
            "allowed_formats": ["flyers", "salon_masterclasses"],
        },
    )

    room_json = room.get("room_json") if isinstance(room.get("room_json"), dict) else {}
    room_json = {**room_json, "proposal": proposal}
    cur.execute(
        """
        UPDATE sales_rooms
        SET proposal_json = %s,
            room_json = %s,
            updated_at = NOW()
        WHERE id = %s
        """,
        (Json(proposal), Json(room_json), room_id),
    )
    record_ai_learning_event(
        capability="sales_room.partner_offer",
        event_type="accepted",
        intent="partnership_outreach",
        user_id=user_id,
        business_id=str(business.get("id") or ""),
        accepted=True,
        edited_before_accept=True,
        prompt_key="beauty_to_residential_complex",
        prompt_version="deterministic_v1",
        draft_text=previous_body[:3000],
        final_text=next_body[:3000],
        metadata={
            "room_id": room_id,
            "lead_id": str(room.get("lead_id") or ""),
            "recipient_category": str(room.get("category") or ""),
            "correction_reason": "generic partnership test is not applicable to a residential complex",
            "allowed_formats": ["flyers", "salon_masterclasses"],
        },
        conn=cur.connection,
    )
    return {
        "room_id": room_id,
        "lead": str(room.get("name") or ""),
        "changed": True,
        "version": int(version.get("version_no") or 0),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--business-id", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    conn = _connect()
    try:
        cur = conn.cursor()
        business = _load_business(cur, args.business_id)
        user_id = _load_superadmin_user_id(cur)
        rooms = _load_rooms(cur, args.business_id)
        results = [
            _repair_room(cur, room=room, business=business, user_id=user_id)
            for room in rooms
        ]
        changed = sum(1 for item in results if item.get("changed"))
        if args.apply:
            conn.commit()
        else:
            conn.rollback()
        print(
            json.dumps(
                {
                    "dry_run": not args.apply,
                    "business_id": args.business_id,
                    "business_name": business.get("name"),
                    "rooms_found": len(rooms),
                    "rooms_changed": changed,
                    "results": results,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
