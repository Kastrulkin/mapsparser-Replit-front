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
    return hashlib.sha256(json.dumps(values, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")).encode("utf-8")).hexdigest()
