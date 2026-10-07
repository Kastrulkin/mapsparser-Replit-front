from __future__ import annotations

from typing import Any


def trusted_telegram_reply_sender_account_id(item: dict[str, Any]) -> str | None:
    sender_account_id = str(item.get("sender_account_id") or "").strip()
    provider_account_id = str(item.get("provider_account_id") or "").strip()
    sender_external_account_id = str(item.get("sender_external_account_id") or "").strip()
    sender_external_account_source = str(item.get("sender_external_account_source") or "").strip()
    if (
        not sender_account_id
        or not provider_account_id
        or provider_account_id != sender_external_account_id
        or sender_external_account_source != "telegram_app"
    ):
        return None
    return sender_account_id


def telegram_reply_sync_summary(
    *,
    batch_id: str | None,
    sender_account_id: str | None,
    picked: int,
) -> dict[str, Any]:
    return {
        "success": True,
        "batch_id": batch_id,
        "sender_account_id": sender_account_id,
        "picked": picked,
        "imported": 0,
        "duplicates": 0,
        "noops": 0,
        "failed": 0,
        "results": [],
        "sender_results": [],
    }


def telegram_reply_sync_result(
    item: dict[str, Any],
    result: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    sender_account_id = trusted_telegram_reply_sender_account_id(item)
    item_result = {
        "queue_id": item.get("id"),
        "lead_id": item.get("lead_id"),
        "lead_name": item.get("lead_name"),
        **result,
        "sender_account_id": sender_account_id,
    }
    sender_result = {
        "sender_account_id": sender_account_id,
        "status": str(result.get("status") or "failed"),
        "error_code": str(result.get("reason") or "").strip() or None,
    }
    return item_result, sender_result


def telegram_reply_sync_outcome(
    *,
    imported: int,
    duplicates: int,
    last_reaction: Any,
) -> dict[str, Any]:
    if imported > 0:
        return {
            "status": "imported",
            "imported": imported,
            "duplicates": duplicates,
            "last_reaction": last_reaction,
        }
    return {"status": "noop", "imported": 0, "duplicates": duplicates}
