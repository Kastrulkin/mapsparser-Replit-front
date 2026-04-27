#!/usr/bin/env python3
import json
import os
import uuid
from typing import Any

import psycopg2
from psycopg2.extras import Json
from psycopg2.extras import RealDictCursor

from api.admin_prospecting import DRAFT_GENERATED
from api.admin_prospecting import _attach_admin_prospecting_public_offer_metadata
from api.admin_prospecting import _generate_superadmin_deterministic_first_message
from api.admin_prospecting import _normalize_lead_for_display
from api.admin_prospecting import _to_json_compatible
from core.card_audit import build_lead_card_preview_snapshot


def _connect():
    return psycopg2.connect(os.environ["DATABASE_URL"], cursor_factory=RealDictCursor)


def _pick_superadmin_user_id(cur) -> str | None:
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


def _normalize_text(value: Any) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _pick_target_channel(lead: dict[str, Any]) -> tuple[str, str]:
    telegram_url = _normalize_text(lead.get("telegram_url"))
    whatsapp_url = _normalize_text(lead.get("whatsapp_url"))
    email = _normalize_text(lead.get("email"))
    website = (_normalize_text(lead.get("website")) or "").lower()
    messenger_links = str(lead.get("messenger_links_json") or "").lower()

    if telegram_url:
        return "telegram", "telegram"
    if whatsapp_url:
        return "whatsapp", "whatsapp"
    if "vk.com" in website or "vk.com" in messenger_links:
        return "manual", "vk_candidate"
    if email:
        return "email", "email"
    return "manual", "manual"


def _load_active_leads(cur) -> list[dict[str, Any]]:
    cur.execute(
        """
        SELECT *
        FROM prospectingleads
        WHERE COALESCE(intent, 'client_outreach') = 'client_outreach'
          AND status IN ('selected_for_outreach', 'channel_selected')
        ORDER BY updated_at DESC NULLS LAST, created_at DESC
        """
    )
    return [dict(row) for row in cur.fetchall() or []]


def _load_latest_generated_draft(cur, lead_id: str) -> dict[str, Any] | None:
    cur.execute(
        """
        SELECT id
        FROM outreachmessagedrafts
        WHERE lead_id = %s
          AND status = %s
        ORDER BY updated_at DESC NULLS LAST, created_at DESC
        LIMIT 1
        """,
        (lead_id, DRAFT_GENERATED),
    )
    row = cur.fetchone()
    return dict(row) if row else None


def main() -> None:
    conn = _connect()
    try:
        cur = conn.cursor()
        user_id = _pick_superadmin_user_id(cur)
        leads = _load_active_leads(cur)
        totals = {
            "processed": 0,
            "telegram": 0,
            "whatsapp": 0,
            "email": 0,
            "manual": 0,
            "vk_candidate": 0,
            "errors": 0,
        }
        print(json.dumps({"total_active": len(leads)}, ensure_ascii=False), flush=True)

        for raw_lead in leads:
            lead_id = str(raw_lead.get("id") or "")
            try:
                selected_channel, bucket = _pick_target_channel(raw_lead)
                totals[selected_channel] += 1
                if bucket == "vk_candidate":
                    totals["vk_candidate"] += 1

                cur.execute(
                    """
                    UPDATE prospectingleads
                    SET selected_channel = %s,
                        status = 'channel_selected',
                        updated_at = NOW()
                    WHERE id = %s
                    RETURNING *
                    """,
                    (selected_channel, lead_id),
                )
                updated_row = cur.fetchone()
                if not updated_row:
                    raise RuntimeError("lead_not_found")
                updated_lead = dict(updated_row)
                display_lead = _normalize_lead_for_display(dict(updated_lead))
                if not display_lead:
                    raise RuntimeError("display_lead_unavailable")
                display_lead = _attach_admin_prospecting_public_offer_metadata(conn, display_lead)
                preview = _to_json_compatible(build_lead_card_preview_snapshot(display_lead))
                draft_payload = _generate_superadmin_deterministic_first_message(display_lead, preview)

                existing_draft = _load_latest_generated_draft(cur, lead_id)
                learning_note = {
                    "source": draft_payload.get("prompt_source") or "deterministic",
                    "prompt_key": draft_payload.get("prompt_key"),
                    "prompt_version": draft_payload.get("prompt_version"),
                    "channel_bucket": bucket,
                }
                if existing_draft and existing_draft.get("id"):
                    cur.execute(
                        """
                        UPDATE outreachmessagedrafts
                        SET channel = %s,
                            angle_type = %s,
                            tone = %s,
                            status = %s,
                            generated_text = %s,
                            edited_text = %s,
                            approved_text = NULL,
                            learning_note_json = %s,
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (
                            selected_channel,
                            draft_payload["angle_type"],
                            draft_payload["tone"],
                            DRAFT_GENERATED,
                            draft_payload["generated_text"],
                            draft_payload["generated_text"],
                            Json(learning_note),
                            str(existing_draft["id"]),
                        ),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO outreachmessagedrafts (
                            id, lead_id, channel, angle_type, tone, status,
                            generated_text, edited_text, learning_note_json, created_by
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        )
                        """,
                        (
                            str(uuid.uuid4()),
                            lead_id,
                            selected_channel,
                            draft_payload["angle_type"],
                            draft_payload["tone"],
                            DRAFT_GENERATED,
                            draft_payload["generated_text"],
                            draft_payload["generated_text"],
                            Json(learning_note),
                            user_id,
                        ),
                    )

                conn.commit()
                totals["processed"] += 1
                print(
                    json.dumps(
                        {
                            "lead_id": lead_id,
                            "name": str(updated_lead.get("name") or ""),
                            "selected_channel": selected_channel,
                            "bucket": bucket,
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
            except Exception as exc:
                conn.rollback()
                totals["errors"] += 1
                print(
                    json.dumps(
                        {
                            "lead_id": lead_id,
                            "name": str(raw_lead.get("name") or ""),
                            "error": str(exc),
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )

        print(json.dumps({"summary": totals}, ensure_ascii=False), flush=True)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
