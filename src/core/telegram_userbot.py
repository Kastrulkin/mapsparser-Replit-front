import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Any

try:
    from telethon import TelegramClient
    from telethon.sessions import StringSession
except Exception:
    TelegramClient = None
    StringSession = None
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

REQUEST_TIMEOUT_SEC = max(5, int(os.getenv("TELEGRAM_USERBOT_REQUEST_TIMEOUT_SEC", "8")))
CONNECT_ATTEMPT_TIMEOUT_SEC = max(5, int(os.getenv("TELEGRAM_USERBOT_CONNECT_ATTEMPT_TIMEOUT_SEC", "10")))


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


def _build_mtproxy_attempts(mtproxy: tuple[str, int, str] | None) -> list[dict[str, Any]]:
    if mtproxy is None:
        return []
    attempts: list[dict[str, Any]] = []
    preferred_mode = os.getenv("TELEGRAM_USERBOT_MTPROXY_MODE", "randomized").strip().lower()
    connection_options = {
        "randomized": ConnectionTcpMTProxyRandomizedIntermediate,
        "classic": ConnectionTcpMTProxyIntermediate,
        "abridged": ConnectionTcpMTProxyAbridged,
    }

    ordered_modes = [preferred_mode] + [mode for mode in ("randomized", "classic", "abridged") if mode != preferred_mode]
    seen_modes: set[str] = set()
    for mode in ordered_modes:
        if mode in seen_modes:
            continue
        seen_modes.add(mode)
        connection_class = connection_options.get(mode)
        if connection_class is None:
            continue
        attempts.append({"connection": connection_class, "proxy": mtproxy})
    return attempts


def _describe_attempt(config: dict[str, Any]) -> dict[str, str]:
    if "connection" in config and "proxy" in config:
        proxy_host = str(config["proxy"][0])
        proxy_port = str(config["proxy"][1])
        connection_name = getattr(config["connection"], "__name__", "mtproxy")
        mode = "randomized"
        if "Abridged" in connection_name:
            mode = "abridged"
        elif "Intermediate" in connection_name and "Randomized" not in connection_name:
            mode = "classic"
        return {
            "route_kind": "mtproxy",
            "route_label": f"mtproxy:{mode}",
            "route_target": f"{proxy_host}:{proxy_port}",
        }
    if "proxy" in config:
        proxy = config["proxy"]
        proxy_host = str(proxy[1])
        proxy_port = str(proxy[2])
        return {
            "route_kind": "proxy",
            "route_label": "socks5",
            "route_target": f"{proxy_host}:{proxy_port}",
        }
    return {
        "route_kind": "direct",
        "route_label": "direct",
        "route_target": "telegram_dc",
    }


def load_userbot_account(cursor, business_id: str | None = None, account_id: str | None = None) -> dict[str, Any] | None:
    query = """
        SELECT id, business_id, auth_data_encrypted, is_active
        FROM externalbusinessaccounts
        WHERE source = %s AND is_active = TRUE
    """
    params: list[Any] = ["telegram_app"]
    if account_id:
        query += " AND id = %s"
        params.append(account_id)
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
    if TelegramClient is None or StringSession is None:
        raise RuntimeError("telethon is not installed")
    api_id = int(auth_data.get("api_id") or 0)
    api_hash = str(auth_data.get("api_hash") or "").strip()
    session_string = str(auth_data.get("session_string") or auth_data.get("pending_session_string") or "")
    proxy = _resolve_proxy()
    mtproxy = _resolve_mtproxy()
    client_kwargs = {
        "connection_retries": 1,
        "retry_delay": 0,
        "auto_reconnect": False,
        "request_retries": 1,
    }
    attempts: list[dict[str, Any]] = _build_mtproxy_attempts(mtproxy)
    if proxy:
        attempts.append({"proxy": proxy})
    attempts.append({})

    last_error: Exception | None = None
    for config in attempts:
        route_info = _describe_attempt(config)
        client = TelegramClient(
            StringSession(session_string),
            api_id,
            api_hash,
            **config,
            **client_kwargs,
        )
        try:
            await asyncio.wait_for(client.connect(), timeout=CONNECT_ATTEMPT_TIMEOUT_SEC)
            setattr(client, "_localos_route_info", route_info)
            print(
                "[telegram_userbot] connect_ok "
                f"route={route_info['route_label']} target={route_info['route_target']}",
                flush=True,
            )
            return client
        except Exception as exc:
            last_error = exc
            print(
                "[telegram_userbot] connect_fail "
                f"route={route_info['route_label']} target={route_info['route_target']} "
                f"error={type(exc).__name__}:{str(exc)[:160]}",
                flush=True,
            )
            try:
                await client.disconnect()
            except Exception:
                pass
    if last_error is not None:
        raise last_error
    raise RuntimeError("Telegram client connection failed")


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


async def _send_message_async(auth_data: dict[str, Any], recipient: str, message: str) -> dict[str, Any]:
    raw_recipient = str(recipient or "").strip()
    normalized = _normalize_phone(raw_recipient) if raw_recipient.startswith("+") or raw_recipient.isdigit() else raw_recipient
    client = await _connect_client(auth_data)
    try:
        route_info = getattr(client, "_localos_route_info", None) or {
            "route_kind": "unknown",
            "route_label": "unknown",
            "route_target": "unknown",
        }
        if not await client.is_user_authorized():
            return {
                "status": "not_authorized",
                "recipient": normalized,
                **route_info,
            }
        sent_message = await asyncio.wait_for(client.send_message(normalized, message), timeout=REQUEST_TIMEOUT_SEC)
        return {
            "status": "sent",
            "recipient": normalized,
            "message_id": getattr(sent_message, "id", None),
            **route_info,
        }
    finally:
        await client.disconnect()


def _normalize_datetime_utc(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except Exception:
        return None


async def _fetch_recent_replies_async(
    auth_data: dict[str, Any],
    recipient: str,
    *,
    sent_after: Any = None,
    after_message_id: Any = None,
    limit: int = 20,
) -> dict[str, Any]:
    raw_recipient = str(recipient or "").strip()
    normalized = _normalize_phone(raw_recipient) if raw_recipient.startswith("+") or raw_recipient.isdigit() else raw_recipient
    safe_limit = max(1, min(int(limit or 20), 50))
    cutoff = _normalize_datetime_utc(sent_after)
    try:
        min_message_id = int(str(after_message_id or "").strip()) if str(after_message_id or "").strip() else None
    except Exception:
        min_message_id = None

    client = await _connect_client(auth_data)
    try:
        if not await client.is_user_authorized():
            return {"status": "not_authorized", "recipient": normalized, "replies": []}

        messages = await asyncio.wait_for(client.get_messages(normalized, limit=safe_limit), timeout=REQUEST_TIMEOUT_SEC)
        replies: list[dict[str, Any]] = []
        for message in reversed(messages):
            if bool(getattr(message, "out", False)):
                continue
            message_id = getattr(message, "id", None)
            if min_message_id is not None:
                try:
                    if int(message_id or 0) <= min_message_id:
                        continue
                except Exception:
                    pass
            message_date = _normalize_datetime_utc(getattr(message, "date", None))
            if cutoff and message_date and message_date <= cutoff:
                continue
            text = str(
                getattr(message, "message", None)
                or getattr(message, "text", None)
                or ""
            ).strip()
            if not text:
                text = "[non-text reply]"
            replies.append(
                {
                    "message_id": message_id,
                    "text": text,
                    "created_at": message_date.isoformat() if message_date else None,
                    "sender_id": getattr(getattr(message, "from_id", None), "user_id", None),
                }
            )
        return {"status": "ok", "recipient": normalized, "replies": replies}
    finally:
        await client.disconnect()


def send_code(auth_data: dict[str, Any]) -> dict[str, Any]:
    return asyncio.run(_send_code_async(auth_data))


def confirm_code(auth_data: dict[str, Any], code: str) -> dict[str, Any]:
    return asyncio.run(_confirm_code_async(auth_data, code))


def send_message(auth_data: dict[str, Any], recipient: str, message: str) -> dict[str, Any]:
    return asyncio.run(_send_message_async(auth_data, recipient, message))


def fetch_recent_replies(
    auth_data: dict[str, Any],
    recipient: str,
    *,
    sent_after: Any = None,
    after_message_id: Any = None,
    limit: int = 20,
) -> dict[str, Any]:
    return asyncio.run(
        _fetch_recent_replies_async(
            auth_data,
            recipient,
            sent_after=sent_after,
            after_message_id=after_message_id,
            limit=limit,
        )
    )
