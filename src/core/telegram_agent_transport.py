from __future__ import annotations

from typing import Any


MAX_BOT_TO_BOT_HOPS = 3
MAX_AUTO_TURNS_PER_THREAD = 6


def _pick_message(update_payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(update_payload, dict):
        return {}
    for key in ["message", "edited_message", "channel_post", "business_message"]:
        value = update_payload.get(key)
        if isinstance(value, dict):
            return value
    return {}


def classify_telegram_sender(update_payload: dict[str, Any], local_bot_username: str = "") -> dict[str, Any]:
    message = _pick_message(update_payload)
    sender = message.get("from")
    if not isinstance(sender, dict):
        sender = {}
    username = str(sender.get("username") or "").strip().lstrip("@")
    local_username = str(local_bot_username or "").strip().lstrip("@")
    is_bot = bool(sender.get("is_bot"))
    sender_id = str(sender.get("id") or "").strip()
    if is_bot and local_username and username.lower() == local_username.lower():
        sender_type = "localos_bot"
    elif is_bot:
        sender_type = "telegram_bot"
    else:
        sender_type = "human"
    return {
        "sender_type": sender_type,
        "telegram_id": sender_id,
        "username": username,
        "is_bot": is_bot,
        "chat_id": str((message.get("chat") or {}).get("id") or "").strip() if isinstance(message.get("chat"), dict) else "",
        "message_id": str(message.get("message_id") or "").strip(),
    }


def normalize_bot_to_bot_hop_count(value: Any) -> int:
    try:
        hop_count = int(value or 0)
    except Exception:
        hop_count = 0
    return max(0, hop_count)


def should_accept_telegram_agent_message(
    sender_context: dict[str, Any],
    *,
    trusted_bot_usernames: set[str] | None = None,
    hop_count: int = 0,
) -> dict[str, Any]:
    sender_type = str(sender_context.get("sender_type") or "unknown").strip()
    username = str(sender_context.get("username") or "").strip().lower()
    trusted = {str(item or "").strip().lower().lstrip("@") for item in (trusted_bot_usernames or set()) if str(item or "").strip()}
    normalized_hops = normalize_bot_to_bot_hop_count(hop_count)
    if normalized_hops > MAX_BOT_TO_BOT_HOPS:
        return {"ok": False, "code": "BOT_TO_BOT_HOP_LIMIT", "reason": "bot-to-bot hop limit exceeded"}
    if sender_type == "localos_bot":
        return {"ok": False, "code": "LOCALOS_SELF_MESSAGE", "reason": "ignore messages from LocalOS bot itself"}
    if sender_type == "telegram_bot" and username not in trusted:
        return {"ok": False, "code": "UNKNOWN_TELEGRAM_BOT", "reason": "unknown Telegram bot must not trigger automation"}
    return {"ok": True, "code": "OK", "reason": ""}


def build_telegram_agent_ledger_payload(sender_context: dict[str, Any], hop_count: int = 0) -> dict[str, Any]:
    return {
        "transport": "telegram",
        "sender_type": str(sender_context.get("sender_type") or "unknown"),
        "telegram_id": str(sender_context.get("telegram_id") or ""),
        "username": str(sender_context.get("username") or ""),
        "chat_id": str(sender_context.get("chat_id") or ""),
        "message_id": str(sender_context.get("message_id") or ""),
        "hop_count": normalize_bot_to_bot_hop_count(hop_count),
        "max_hops": MAX_BOT_TO_BOT_HOPS,
    }
