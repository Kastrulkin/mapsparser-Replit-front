from __future__ import annotations

from auth_encryption import decrypt_auth_data, encrypt_auth_data


TELEGRAM_TOKEN_PREFIX = "enc_tg:"


def encode_telegram_bot_token(raw_token: str) -> str:
    token = str(raw_token or "").strip()
    if not token:
        return ""
    encrypted = encrypt_auth_data(token)
    return f"{TELEGRAM_TOKEN_PREFIX}{encrypted}"


def decode_telegram_bot_token(stored_value: str | None) -> str:
    raw = str(stored_value or "").strip()
    if not raw:
        return ""
    if raw.startswith(TELEGRAM_TOKEN_PREFIX):
        encrypted = raw[len(TELEGRAM_TOKEN_PREFIX):].strip()
        decrypted = decrypt_auth_data(encrypted)
        return str(decrypted or "").strip()
    return raw


def is_telegram_bot_token_configured(stored_value: str | None) -> bool:
    return bool(str(stored_value or "").strip())


def mask_telegram_bot_token(stored_value: str | None) -> str:
    token = decode_telegram_bot_token(stored_value)
    if not token:
        return ""
    if len(token) <= 10:
        return "•" * len(token)
    return f"{token[:6]}••••{token[-4:]}"
