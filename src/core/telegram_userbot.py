import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

try:
    from telethon import TelegramClient
    from telethon.errors import SessionPasswordNeededError
    from telethon.sessions import StringSession
except Exception:
    TelegramClient = None
    SessionPasswordNeededError = None
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
    raw_proxy = ""
    for key in ("TELEGRAM_USERBOT_PROXY", "TELEGRAM_PROXY_URL"):
        raw_proxy = os.getenv(key, "").strip()
        if raw_proxy:
            break
    if not raw_proxy:
        return None
    if socks is None:
        raise RuntimeError("PySocks is required when a Telegram userbot proxy is configured.")
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
    if not attempts:
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


async def _confirm_code_async(auth_data: dict[str, Any], code: str, password: str = "") -> dict[str, Any]:
    phone = _normalize_phone(str(auth_data.get("phone") or ""))
    phone_code_hash = str(auth_data.get("phone_code_hash") or "").strip()
    client = await _connect_client(auth_data)
    try:
        if not await client.is_user_authorized():
            if password and str(auth_data.get("authorization_status") or "") == "password_required":
                await client.sign_in(password=password)
                return {
                    "status": "authorized",
                    "session_string": client.session.save(),
                    "phone": phone,
                }
            sign_in_kwargs: dict[str, Any] = {
                "phone": phone,
                "code": code,
            }
            if phone_code_hash:
                sign_in_kwargs["phone_code_hash"] = phone_code_hash
            try:
                await client.sign_in(**sign_in_kwargs)
            except Exception as error:
                if SessionPasswordNeededError is None or not isinstance(error, SessionPasswordNeededError):
                    raise
                if not password:
                    return {
                        "status": "password_required",
                        "pending_session_string": client.session.save(),
                        "phone": phone,
                        "authorization_status": "password_required",
                    }
                await client.sign_in(password=password)
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


def _normalize_telegram_peer(value: str):
    raw_peer = str(value or "").strip()
    if not raw_peer:
        return raw_peer
    if raw_peer.startswith("@") or raw_peer.startswith("+"):
        return raw_peer
    try:
        return int(raw_peer)
    except Exception:
        return raw_peer


def _normalize_entity_reference(value: str):
    raw_reference = str(value or "").strip()
    if not raw_reference:
        return raw_reference
    candidate = raw_reference
    if raw_reference.startswith("https://") or raw_reference.startswith("http://"):
        parsed = urlparse(raw_reference)
        if parsed.netloc.lower().removeprefix("www.") in {"t.me", "telegram.me"}:
            parts = [part for part in parsed.path.split("/") if part]
            if parts and parts[0].lower() == "s":
                parts = parts[1:]
            if parts:
                candidate = f"@{parts[0].lstrip('@')}"
    return _normalize_telegram_peer(candidate)


def classify_telegram_entity(entity: Any) -> dict[str, Any]:
    """Describe a Telethon entity without guessing from the t.me URL shape."""
    class_name = type(entity).__name__.lower()
    username = str(getattr(entity, "username", None) or "").strip() or None
    entity_id = str(getattr(entity, "id", None) or "").strip() or None
    title = str(getattr(entity, "title", None) or "").strip()

    if class_name.startswith("user") or hasattr(entity, "bot"):
        first_name = str(getattr(entity, "first_name", None) or "").strip()
        last_name = str(getattr(entity, "last_name", None) or "").strip()
        entity_type = "bot" if bool(getattr(entity, "bot", False)) else "user"
        return {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "username": username,
            "title": " ".join(part for part in (first_name, last_name) if part),
            "signal_source_eligible": False,
            "recipient_eligible": entity_type == "user",
        }

    if class_name.startswith("channel") or any(
        hasattr(entity, attribute) for attribute in ("broadcast", "megagroup", "gigagroup")
    ):
        if bool(getattr(entity, "megagroup", False)):
            entity_type = "megagroup"
        elif bool(getattr(entity, "gigagroup", False)):
            entity_type = "gigagroup"
        elif bool(getattr(entity, "broadcast", False)):
            entity_type = "broadcast_channel"
        else:
            entity_type = "channel"
        return {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "username": username,
            "title": title,
            "signal_source_eligible": True,
            "recipient_eligible": False,
        }

    if class_name.startswith("chat"):
        return {
            "entity_type": "group_chat",
            "entity_id": entity_id,
            "username": username,
            "title": title,
            "signal_source_eligible": True,
            "recipient_eligible": False,
        }

    return {
        "entity_type": "unknown",
        "entity_id": entity_id,
        "username": username,
        "title": title,
        "signal_source_eligible": False,
        "recipient_eligible": False,
    }


async def _inspect_telegram_entity_async(auth_data: dict[str, Any], reference: str) -> dict[str, Any]:
    raw_reference = str(reference or "").strip()
    normalized = _normalize_entity_reference(raw_reference)
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
                "reference": raw_reference,
                **route_info,
            }
        entity = await asyncio.wait_for(client.get_entity(normalized), timeout=REQUEST_TIMEOUT_SEC)
        return {
            "status": "ok",
            "reference": raw_reference,
            **classify_telegram_entity(entity),
            **route_info,
        }
    finally:
        await client.disconnect()


async def _fetch_recent_messages_async(
    auth_data: dict[str, Any],
    peer: str,
    *,
    after_message_id: Any = None,
    limit: int = 20,
) -> dict[str, Any]:
    raw_peer = str(peer or "").strip()
    normalized = _normalize_telegram_peer(raw_peer)
    safe_limit = max(1, min(int(limit or 20), 100))
    try:
        min_message_id = int(str(after_message_id or "").strip()) if str(after_message_id or "").strip() else 0
    except Exception:
        min_message_id = 0

    client = await _connect_client(auth_data)
    try:
        route_info = getattr(client, "_localos_route_info", None) or {
            "route_kind": "unknown",
            "route_label": "unknown",
            "route_target": "unknown",
        }
        if not await client.is_user_authorized():
            return {"status": "not_authorized", "peer": raw_peer, "messages": [], **route_info}

        messages = await asyncio.wait_for(
            client.get_messages(normalized, limit=safe_limit, min_id=max(0, min_message_id)),
            timeout=REQUEST_TIMEOUT_SEC,
        )
        result_messages: list[dict[str, Any]] = []
        for message in reversed(messages):
            message_id = getattr(message, "id", None)
            try:
                if min_message_id and int(message_id or 0) <= min_message_id:
                    continue
            except Exception:
                pass
            message_date = _normalize_datetime_utc(getattr(message, "date", None))
            result_messages.append(_message_payload(message, message_date))
        return {"status": "ok", "peer": raw_peer, "messages": result_messages, **route_info}
    finally:
        await client.disconnect()


def _reaction_key(reaction: Any) -> str:
    value = getattr(reaction, "emoticon", None)
    if value:
        return str(value)
    document_id = getattr(reaction, "document_id", None)
    if document_id:
        return f"custom:{document_id}"
    return "other"


def _message_payload(message: Any, message_date: datetime | None = None) -> dict[str, Any]:
    reactions: dict[str, int] = {}
    reactions_total = 0
    reaction_results = getattr(getattr(message, "reactions", None), "results", None) or []
    for item in reaction_results:
        count = int(getattr(item, "count", 0) or 0)
        reactions[_reaction_key(getattr(item, "reaction", None))] = count
        reactions_total += count
    replies_count = int(getattr(getattr(message, "replies", None), "replies", 0) or 0)
    media = getattr(message, "media", None)
    media_type = None
    if media is not None:
        media_type = type(media).__name__.replace("MessageMedia", "").lower() or "media"
    normalized_date = message_date or _normalize_datetime_utc(getattr(message, "date", None))
    edited_at = _normalize_datetime_utc(getattr(message, "edit_date", None))
    return {
        "id": getattr(message, "id", None),
        "text": str(getattr(message, "message", None) or getattr(message, "text", None) or "").strip(),
        "date": normalized_date.isoformat() if normalized_date else None,
        "sender_id": getattr(getattr(message, "from_id", None), "user_id", None)
        or getattr(getattr(message, "from_id", None), "channel_id", None),
        "out": bool(getattr(message, "out", False)),
        "views": int(getattr(message, "views", 0) or 0),
        "forwards": int(getattr(message, "forwards", 0) or 0),
        "replies_count": replies_count,
        "reactions_total": reactions_total,
        "reactions": reactions,
        "media_type": media_type,
        "edited_at": edited_at.isoformat() if edited_at else None,
    }


async def _list_dialogs_async(auth_data: dict[str, Any], limit: int = 300) -> dict[str, Any]:
    client = await _connect_client(auth_data)
    try:
        if not await client.is_user_authorized():
            return {"status": "not_authorized", "dialogs": []}
        dialogs = await asyncio.wait_for(
            client.get_dialogs(limit=max(1, min(int(limit or 300), 500))),
            timeout=max(REQUEST_TIMEOUT_SEC, 30),
        )
        result: list[dict[str, Any]] = []
        for dialog in dialogs:
            entity = getattr(dialog, "entity", None)
            if entity is None or bool(getattr(dialog, "is_user", False)):
                continue
            username = str(getattr(entity, "username", None) or "").strip()
            result.append(
                {
                    "telegram_chat_id": str(getattr(entity, "id", None) or getattr(dialog, "id", "")),
                    "title": str(getattr(dialog, "title", None) or getattr(entity, "title", None) or "Telegram"),
                    "telegram_username": username or None,
                    "visibility": "public" if username else "private",
                    "source_type": "channel" if bool(getattr(dialog, "is_channel", False)) else "chat",
                    "unread_count": int(getattr(dialog, "unread_count", 0) or 0),
                }
            )
        return {"status": "ok", "dialogs": result}
    finally:
        await client.disconnect()


async def _fetch_message_page_async(
    auth_data: dict[str, Any],
    peer: str,
    *,
    before_message_id: Any = None,
    before_date: Any = None,
    limit: int = 100,
) -> dict[str, Any]:
    raw_peer = str(peer or "").strip()
    normalized = _normalize_telegram_peer(raw_peer)
    try:
        offset_id = int(str(before_message_id or "").strip()) if str(before_message_id or "").strip() else 0
    except Exception:
        offset_id = 0
    offset_date = _normalize_datetime_utc(before_date)
    client = await _connect_client(auth_data)
    try:
        if not await client.is_user_authorized():
            return {"status": "not_authorized", "peer": raw_peer, "messages": []}
        messages = await asyncio.wait_for(
            client.get_messages(
                normalized,
                limit=max(1, min(int(limit or 100), 100)),
                offset_id=max(0, offset_id),
                offset_date=offset_date,
            ),
            timeout=max(REQUEST_TIMEOUT_SEC, 30),
        )
        payloads = [_message_payload(message) for message in messages]
        return {"status": "ok", "peer": raw_peer, "messages": payloads}
    finally:
        await client.disconnect()


def list_dialogs(auth_data: dict[str, Any], limit: int = 300) -> dict[str, Any]:
    return asyncio.run(_list_dialogs_async(auth_data, limit=limit))


def fetch_message_page(
    auth_data: dict[str, Any],
    peer: str,
    *,
    before_message_id: Any = None,
    before_date: Any = None,
    limit: int = 100,
) -> dict[str, Any]:
    return asyncio.run(
        _fetch_message_page_async(
            auth_data,
            peer,
            before_message_id=before_message_id,
            before_date=before_date,
            limit=limit,
        )
    )


def send_code(auth_data: dict[str, Any]) -> dict[str, Any]:
    return asyncio.run(_send_code_async(auth_data))


def confirm_code(auth_data: dict[str, Any], code: str, password: str = "") -> dict[str, Any]:
    return asyncio.run(_confirm_code_async(auth_data, code, password=password))


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


def fetch_recent_messages(
    auth_data: dict[str, Any],
    peer: str,
    *,
    after_message_id: Any = None,
    limit: int = 20,
) -> dict[str, Any]:
    return asyncio.run(
        _fetch_recent_messages_async(
            auth_data,
            peer,
            after_message_id=after_message_id,
            limit=limit,
        )
    )


def inspect_telegram_entity(auth_data: dict[str, Any], reference: str) -> dict[str, Any]:
    return asyncio.run(_inspect_telegram_entity_async(auth_data, reference))
