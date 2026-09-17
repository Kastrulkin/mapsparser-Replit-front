"""Authentication primitives for business-scoped Telegram Bot API webhooks."""
from __future__ import annotations

import hashlib
import hmac


TELEGRAM_WEBHOOK_SECRET_HEADER = "X-Telegram-Bot-Api-Secret-Token"
_TELEGRAM_WEBHOOK_SECRET_DOMAIN = "localos.telegram.webhook.v1:"


def derive_telegram_webhook_secret(bot_token: str, business_id: str) -> str:
    """Derive the Bot API secret token without storing another credential."""
    token = str(bot_token or "").strip()
    canonical_business_id = str(business_id or "").strip()
    if not token or not canonical_business_id:
        return ""
    message = f"{_TELEGRAM_WEBHOOK_SECRET_DOMAIN}{canonical_business_id}".encode("utf-8")
    return hmac.new(token.encode("utf-8"), message, hashlib.sha256).hexdigest()


def has_valid_telegram_webhook_secret(
    supplied_secret: str | None,
    bot_token: str,
    business_id: str,
) -> bool:
    supplied = str(supplied_secret or "")
    expected = derive_telegram_webhook_secret(bot_token, business_id)
    return bool(supplied and expected and hmac.compare_digest(expected, supplied))
