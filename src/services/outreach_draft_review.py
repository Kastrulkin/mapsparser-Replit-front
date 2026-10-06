"""Bind a draft review to the exact text, lead, channel and known contact.

This is draft approval evidence; sender and delivery time are selected later
by the existing manual-send workflow and are not authorized by this digest.
"""
import hashlib
import json


def draft_review_digest(draft):
    fields = ("id", "lead_id", "channel", "status", "generated_text", "edited_text",
              "approved_text", "updated_at", "email", "selected_channel")
    values = {key: str(draft.get(key) or "") for key in fields}
    if draft.get("canonical_review") is not None:
        values["canonical_review"] = draft["canonical_review"]
    if draft.get("canonical_review") and draft["canonical_review"].get("text"):
        for key in ("generated_text", "edited_text", "approved_text"):
            values[key] = draft["canonical_review"]["text"]
    return hashlib.sha256(json.dumps(values, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")).encode("utf-8")).hexdigest()


def canonical_review(cursor, draft):
    """Current campaign text, recipient and sender shown before manual approval."""
    origin = draft.get("learning_note_json") or {}
    if not isinstance(origin, dict) or not origin.get("campaign_id"):
        return None
    from services.outreach_safety_service import approval_snapshot_hash
    cursor.execute("SELECT * FROM outreach_campaigns WHERE id=%s AND lead_id=%s AND status='draft'",
                   (origin["campaign_id"], draft["lead_id"]))
    campaign = cursor.fetchone()
    if not campaign:
        raise ValueError("campaign_review_stale")
    cursor.execute("""SELECT touch.*, contact.normalized_value AS recipient,
        sender.display_name AS sender_name, sender.sender_identity FROM outreach_campaign_touches touch
        LEFT JOIN lead_contact_points contact ON contact.id=touch.contact_point_id
        LEFT JOIN outreach_sender_accounts sender ON sender.id=touch.sender_account_id
        WHERE touch.campaign_id=%s ORDER BY touch.sequence_index""", (campaign["id"],))
    touches = [dict(row) for row in cursor.fetchall()]
    if len(touches) != 1 or str(touches[0]["id"]) != str(origin.get("campaign_touch_id")):
        raise ValueError("campaign_review_stale")
    touch = touches[0]
    snapshot = approval_snapshot_hash(dict(campaign), touches)
    fingerprint = hashlib.sha256(json.dumps([snapshot, touch.get("recipient"), touch.get("sender_name"), touch.get("sender_identity")],
        ensure_ascii=False).encode()).hexdigest()
    return {"hash": fingerprint, "campaign_id": str(campaign["id"]),
            "subject": touch.get("subject"), "recipient": touch.get("recipient"),
            "sender": " · ".join(str(value) for value in (touch.get("sender_name"), touch.get("sender_identity")) if value), "text": touch.get("generated_text"),
            "source_url": (touch.get("message_brief_json") or {}).get("source_url")}


def approve_reviewed_campaigns(cursor, batch_id, rows, user_id):
    """Replace draft batch placeholders with the existing native queue atomically."""
    from services.outreach_campaign_service import approve_campaign
    from services.outreach_safety_service import load_partnership_repeat_contact_guard
    for draft in rows:
        if load_partnership_repeat_contact_guard(cursor, lead_id=str(draft["lead_id"])).get("blocked"):
            return "Компания уже ответила или отказалась. Продолжите существующий диалог."
        reviewed = canonical_review(cursor, draft)
        origin = draft.get("learning_note_json") or {}
        if draft["generated_text"] != draft["approved_text"] or not reviewed or reviewed["hash"] != origin.get("reviewed_campaign_hash"):
            return "Получатель, отправитель или письмо изменились. Проверьте новую версию."
    campaign_ids = list(dict.fromkeys(str(row["campaign_id"]) for row in rows))
    cursor.execute("DELETE FROM outreachsendqueue WHERE id::text=ANY(%s::text[])",
                   ([str(row["id"]) for row in rows],))
    for campaign_id in campaign_ids:
        approve_campaign(cursor, campaign_id, user_id=user_id, reviewed_batch_id=batch_id)
    return None
