import asyncio
import json
import os
from typing import Any

from telethon import TelegramClient
from telethon.sessions import StringSession
try:
    from telethon.network.connection.tcpmtproxy import (
        ConnectionTcpMTProxyAbridged,
        ConnectionTcpMTProxyIntermediate,
        ConnectionTcpMTProxyRandomizedIntermediate,
    )
except Exception:
    ConnectionTcpMTProxyAbridged = None
    ConnectionTcpMTProxyIntermediate = None
    ConnectionTcpMTProxyRandomizedIntermediate = None

from auth_encryption import decrypt_auth_data, encrypt_auth_data

try:
    import socks
except Exception:
    socks = None


def _parse_auth_data(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _normalize_phone(value: str) -> str:
    phone = (value or "").strip()
    if not phone:
        return ""
    if phone.startswith("+"):
        return phone
    return f"+{phone}"


def _parse_proxy_url(raw: str | None):
    if not raw:
        return None
    value = str(raw).strip()
    if not value:
        return None
    if "://" in value:
        scheme, rest = value.split("://", 1)
    else:
        scheme, rest = "socks5", value
    scheme = scheme.lower().strip()
    creds = None
    hostport = rest
    if "@" in rest:
        creds, hostport = rest.split("@", 1)
    if ":" not in hostport:
        return None
    host, port_str = hostport.rsplit(":", 1)
    host = host.strip()
    port_str = port_str.strip()
    if not host or not port_str.isdigit():
        return None
    port = int(port_str)
    username = None
    password = None
    if creds:
        if ":" in creds:
            username, password = creds.split(":", 1)
        else:
            username = creds
    if scheme == "socks5" or scheme == "socks5h":
        proxy_type = socks.SOCKS5 if socks else None
        rdns = scheme == "socks5h"
    elif scheme == "socks4":
        proxy_type = socks.SOCKS4 if socks else None
        rdns = True
    elif scheme == "http":
        proxy_type = socks.HTTP if socks else None
        rdns = True
    else:
        return None
    if proxy_type is None:
        return None
    return (proxy_type, host, port, rdns, username, password)


def _resolve_proxy():
    raw_proxy = os.getenv("TELEGRAM_USERBOT_PROXY", "").strip()
    if not raw_proxy:
        return None
    if socks is None:
        raise RuntimeError("PySocks not installed; set TELEGRAM_USERBOT_PROXY requires pysocks.")
    return _parse_proxy_url(raw_proxy)


def _normalize_mtproxy_secret(value: str) -> str:
    candidate = value.strip().lower()
    if candidate.startswith("0x"):
        candidate = candidate[2:]
    if len(candidate) % 2 == 1:
        candidate = "0" + candidate
    return candidate


def _resolve_mtproxy():
    if ConnectionTcpMTProxyRandomizedIntermediate is None:
        return None
    host = os.getenv("TELEGRAM_USERBOT_MTPROXY_HOST", "").strip()
    port = os.getenv("TELEGRAM_USERBOT_MTPROXY_PORT", "").strip()
    secret = os.getenv("TELEGRAM_USERBOT_MTPROXY_SECRET", "").strip()
    if not host or not port or not secret:
        return None
    if not port.isdigit():
        return None
    return (host, int(port), _normalize_mtproxy_secret(secret))


def load_userbot_account(cursor, business_id: str | None = None) -> dict[str, Any] | None:
    query = """
        SELECT id, business_id, auth_data_encrypted, is_active
        FROM externalbusinessaccounts
        WHERE source = %s AND is_active = TRUE
    """
    params: list[Any] = ["telegram_app"]
    if business_id:
        query += " AND business_id = %s"
        params.append(business_id)
    query += " ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST LIMIT 1"

    cursor.execute(query, params)
    row = cursor.fetchone()
    if not row:
        return None
    if hasattr(row, "get"):
        account_id = row.get("id")
        account_business_id = row.get("business_id")
        auth_data_encrypted = row.get("auth_data_encrypted")
    else:
        account_id = row[0]
        account_business_id = row[1]
        auth_data_encrypted = row[2]
    auth_data_plain = decrypt_auth_data(auth_data_encrypted)
    auth_data = _parse_auth_data(auth_data_plain)
    auth_data["account_id"] = account_id
    auth_data["business_id"] = account_business_id
    return auth_data


def update_userbot_session(cursor, account_id: str, auth_data: dict[str, Any]) -> None:
    auth_data_str = json.dumps(auth_data, ensure_ascii=False)
    auth_data_encrypted = encrypt_auth_data(auth_data_str)
    cursor.execute(
        """
        UPDATE externalbusinessaccounts
        SET auth_data_encrypted = %s, updated_at = NOW()
        WHERE id = %s
        """,
        (auth_data_encrypted, account_id),
    )


async def _connect_client(auth_data: dict[str, Any]) -> TelegramClient:
    api_id = int(auth_data.get("api_id") or 0)
    api_hash = str(auth_data.get("api_hash") or "").strip()
    session_string = str(auth_data.get("session_string") or auth_data.get("pending_session_string") or "")
    proxy = _resolve_proxy()
    mtproxy = _resolve_mtproxy()
    if mtproxy:
        mode = os.getenv("TELEGRAM_USERBOT_MTPROXY_MODE", "randomized").strip().lower()
        connection_class = (
            ConnectionTcpMTProxyIntermediate
            if mode == "classic"
            else ConnectionTcpMTProxyRandomizedIntermediate
        )
        client = TelegramClient(
            StringSession(session_string),
            api_id,
            api_hash,
            connection=connection_class,
            proxy=mtproxy,
        )
    elif proxy:
        client = TelegramClient(StringSession(session_string), api_id, api_hash, proxy=proxy)
    else:
        client = TelegramClient(StringSession(session_string), api_id, api_hash)
    await client.connect()
    return client


async def _send_code_async(auth_data: dict[str, Any]) -> dict[str, Any]:
    phone = _normalize_phone(str(auth_data.get("phone") or ""))
    client = await _connect_client(auth_data)
    try:
        if not await client.is_user_authorized():
            sent = await client.send_code_request(phone)
            return {
                "status": "code_sent",
                "phone": phone,
                "phone_code_hash": getattr(sent, "phone_code_hash", None),
                "pending_session_string": client.session.save(),
            }
        return {"status": "already_authorized", "phone": phone}
    finally:
        await client.disconnect()


async def _confirm_code_async(auth_data: dict[str, Any], code: str) -> dict[str, Any]:
    phone = _normalize_phone(str(auth_data.get("phone") or ""))
    phone_code_hash = str(auth_data.get("phone_code_hash") or "").strip()
    client = await _connect_client(auth_data)
    try:
        if not await client.is_user_authorized():
            sign_in_kwargs: dict[str, Any] = {
                "phone": phone,
                "code": code,
            }
            if phone_code_hash:
                sign_in_kwargs["phone_code_hash"] = phone_code_hash
            await client.sign_in(**sign_in_kwargs)
        session_string = client.session.save()
        return {
            "status": "authorized",
            "session_string": session_string,
            "phone": phone,
        }
    finally:
        await client.disconnect()


async def _send_message_async(auth_data: dict[str, Any], phone: str, message: str) -> dict[str, Any]:
    normalized = _normalize_phone(phone)
    client = await _connect_client(auth_data)
    try:
        if not await client.is_user_authorized():
            return {"status": "not_authorized", "phone": normalized}
        await client.send_message(normalized, message)
        return {"status": "sent", "phone": normalized}
    finally:
        await client.disconnect()


def send_code(auth_data: dict[str, Any]) -> dict[str, Any]:
    return asyncio.run(_send_code_async(auth_data))


def confirm_code(auth_data: dict[str, Any], code: str) -> dict[str, Any]:
    return asyncio.run(_confirm_code_async(auth_data, code))


def send_message(auth_data: dict[str, Any], phone: str, message: str) -> dict[str, Any]:
    return asyncio.run(_send_message_async(auth_data, phone, message))
