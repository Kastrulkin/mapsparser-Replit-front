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


def parse_trusted_telegram_agent_bots(value: str) -> set[str]:
    return {
        str(item or "").strip().lower().lstrip("@")
        for item in str(value or "").split(",")
        if str(item or "").strip()
    }


def telegram_bot_to_bot_policy_decision(
    update_payload: dict[str, Any],
    *,
    trusted_bot_usernames: set[str] | None = None,
    local_bot_username: str = "",
    hop_count: int = 0,
    bound_agent_client: dict[str, Any] | None = None,
) -> dict[str, Any]:
    sender_context = classify_telegram_sender(update_payload, local_bot_username=local_bot_username)
    client_status = str((bound_agent_client or {}).get("status") or "").strip().lower()
    effective_trusted = set(trusted_bot_usernames or set())
    if bound_agent_client and sender_context.get("username"):
        effective_trusted.add(str(sender_context.get("username") or "").strip().lower())
    if sender_context.get("sender_type") == "human":
        return {
            "allow_normal_routing": True,
            "should_alert": False,
            "code": "HUMAN_SENDER",
            "reason": "",
            "sender": sender_context,
            "ledger_payload": build_telegram_agent_ledger_payload(sender_context, hop_count),
        }

    verdict = should_accept_telegram_agent_message(sender_context, trusted_bot_usernames=effective_trusted, hop_count=hop_count)
    if not verdict.get("ok"):
        code = str(verdict.get("code") or "TELEGRAM_AGENT_BLOCKED")
        return {
            "allow_normal_routing": False,
            "should_alert": code != "LOCALOS_SELF_MESSAGE",
            "code": code,
            "reason": str(verdict.get("reason") or "Telegram bot message blocked by policy"),
            "sender": sender_context,
            "ledger_payload": build_telegram_agent_ledger_payload(sender_context, hop_count),
            "agent_client_id": str((bound_agent_client or {}).get("id") or ""),
            "agent_client_status": client_status,
        }

    if not bound_agent_client:
        return {
            "allow_normal_routing": False,
            "should_alert": True,
            "code": "TELEGRAM_AGENT_CLIENT_BINDING_REQUIRED",
            "reason": "trusted Telegram bot must be bound to an Agent API client before automation",
            "sender": sender_context,
            "ledger_payload": build_telegram_agent_ledger_payload(sender_context, hop_count),
            "agent_client_id": "",
            "agent_client_status": "",
        }

    if client_status == "suspended":
        return {
            "allow_normal_routing": False,
            "should_alert": True,
            "code": "AGENT_CLIENT_SUSPENDED",
            "reason": "bound Agent API client is suspended",
            "sender": sender_context,
            "ledger_payload": build_telegram_agent_ledger_payload(sender_context, hop_count),
            "agent_client_id": str(bound_agent_client.get("id") or ""),
            "agent_client_status": client_status,
        }

    if client_status == "live":
        return {
            "allow_normal_routing": False,
            "should_alert": False,
            "code": "TELEGRAM_AGENT_API_REQUIRED",
            "reason": "live Telegram agent must use Agent API scopes and approval flow",
            "sender": sender_context,
            "ledger_payload": build_telegram_agent_ledger_payload(sender_context, hop_count),
            "agent_client_id": str(bound_agent_client.get("id") or ""),
            "agent_client_status": client_status,
        }

    return {
        "allow_normal_routing": False,
        "should_alert": True,
        "code": "TELEGRAM_AGENT_TRANSPORT_SANDBOX",
        "reason": "sandbox Telegram agent cannot trigger automation without human approval",
        "sender": sender_context,
        "ledger_payload": build_telegram_agent_ledger_payload(sender_context, hop_count),
        "agent_client_id": str(bound_agent_client.get("id") or ""),
        "agent_client_status": client_status,
    }


def evaluate_and_record_telegram_agent_transport(
    cursor,
    update_payload: dict[str, Any],
    *,
    local_bot_username: str = "",
    hop_count: int = 0,
    business_id: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    from core.agent_api_alerts import notify_superadmins_agent_alert
    from core.agent_api_security import find_agent_client_by_telegram_sender, log_agent_action

    sender = classify_telegram_sender(update_payload, local_bot_username=local_bot_username)
    if sender.get("sender_type") == "human":
        return telegram_bot_to_bot_policy_decision(update_payload, local_bot_username=local_bot_username, hop_count=hop_count)

    client = find_agent_client_by_telegram_sender(cursor, sender)
    decision = telegram_bot_to_bot_policy_decision(
        update_payload,
        local_bot_username=local_bot_username,
        hop_count=hop_count,
        bound_agent_client=client,
    )
    code = str(decision.get("code") or "TELEGRAM_AGENT_TRANSPORT_EVENT")
    if code == "LOCALOS_SELF_MESSAGE":
        return decision
    status = "denied"
    if code in {"TELEGRAM_AGENT_TRANSPORT_SANDBOX", "TELEGRAM_AGENT_API_REQUIRED"}:
        status = "recorded"
    ledger_id = log_agent_action(
        cursor,
        agent_client_id=str((client or {}).get("id") or "") or None,
        business_id=business_id,
        action_type="telegram_agent_transport_message",
        capability="agent_api.telegram_transport",
        required_scope="telegram:transport",
        risk_level="medium",
        input_summary=decision.get("ledger_payload") or {},
        output_summary={"allow_normal_routing": bool(decision.get("allow_normal_routing"))},
        status=status,
        reason_code=code,
        ip=ip,
        user_agent=user_agent,
        metadata={
            "sender": sender,
            "agent_client_status": str((client or {}).get("status") or ""),
            "transport_reason": str(decision.get("reason") or ""),
        },
    )
    decision["ledger_id"] = ledger_id
    if decision.get("should_alert"):
        notify_superadmins_agent_alert(
            cursor,
            "Telegram agent transport event",
            {
                "reason_code": code,
                "agent_client_id": str((client or {}).get("id") or ""),
                "agent_status": str((client or {}).get("status") or ""),
                "telegram_bot": str(sender.get("username") or sender.get("telegram_id") or ""),
                "ledger_id": ledger_id,
            },
        )
    return decision
