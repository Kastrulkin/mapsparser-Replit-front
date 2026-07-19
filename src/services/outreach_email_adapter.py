from __future__ import annotations

import imaplib
import ipaddress
import base64
import hashlib
import json
import os
import smtplib
import socket
import ssl
from datetime import datetime, timedelta, timezone
from email import policy
from email.message import EmailMessage, Message
from email.parser import BytesParser
from email.utils import format_datetime, getaddresses, make_msgid, parsedate_to_datetime
from typing import Any

from auth_encryption import decrypt_auth_data
from cryptography.fernet import Fernet, InvalidToken


SUPPORTED_SECURITY = {"ssl", "starttls"}
DEFAULT_SYNC_LOOKBACK_DAYS = 30
EMAIL_CREDENTIAL_PREFIX = "localos-outreach-email-v1:"


class EmailAdapterError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


def _email_credential_cipher() -> Fernet:
    secret = os.getenv("OUTREACH_EMAIL_SECRET_KEY", "").strip()
    if len(secret) < 32:
        raise EmailAdapterError(
            "outreach_email_secret_missing",
            "OUTREACH_EMAIL_SECRET_KEY must contain at least 32 characters",
        )
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_mailbox_config(config: dict[str, Any]) -> str:
    normalized = normalize_mailbox_config(config)
    payload = json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))
    token = _email_credential_cipher().encrypt(payload.encode("utf-8")).decode("ascii")
    return f"{EMAIL_CREDENTIAL_PREFIX}{token}"


def _text(value: Any) -> str:
    return str(value or "").strip()


def normalize_email(value: Any) -> str:
    normalized = _text(value).lower()
    if (
        not normalized
        or normalized.count("@") != 1
        or any(character.isspace() for character in normalized)
    ):
        return ""
    local_part, domain = normalized.rsplit("@", 1)
    if not local_part or not domain or domain.startswith(".") or domain.endswith("."):
        return ""
    try:
        ascii_domain = domain.encode("idna").decode("ascii")
    except UnicodeError:
        return ""
    if len(local_part) > 64 or len(ascii_domain) > 253:
        return ""
    return f"{local_part}@{ascii_domain}"


def _port(value: Any, default: int) -> int:
    try:
        parsed = int(value or default)
    except (TypeError, ValueError) as exc:
        raise ValueError("mail_port_invalid") from exc
    if parsed < 1 or parsed > 65535:
        raise ValueError("mail_port_invalid")
    return parsed


def normalize_mailbox_config(payload: dict[str, Any]) -> dict[str, Any]:
    email_address = normalize_email(payload.get("email") or payload.get("sender_identity"))
    if not email_address:
        raise ValueError("sender_email_invalid")
    smtp_host = _text(payload.get("smtp_host")).lower().rstrip(".")
    imap_host = _text(payload.get("imap_host")).lower().rstrip(".")
    if not smtp_host or not imap_host:
        raise ValueError("smtp_and_imap_hosts_required")
    smtp_security = _text(payload.get("smtp_security") or "starttls").lower()
    imap_security = _text(payload.get("imap_security") or "ssl").lower()
    if smtp_security not in SUPPORTED_SECURITY or imap_security not in SUPPORTED_SECURITY:
        raise ValueError("mail_security_must_be_ssl_or_starttls")
    username = _text(payload.get("username") or email_address)
    password = _text(payload.get("password"))
    if not username or not password:
        raise ValueError("mailbox_credentials_required")
    return {
        "email": email_address,
        "display_name": _text(payload.get("display_name"))[:200],
        "username": username,
        "password": password,
        "smtp_host": smtp_host,
        "smtp_port": _port(payload.get("smtp_port"), 465 if smtp_security == "ssl" else 587),
        "smtp_security": smtp_security,
        "imap_host": imap_host,
        "imap_port": _port(payload.get("imap_port"), 993 if imap_security == "ssl" else 143),
        "imap_security": imap_security,
        "imap_folder": _text(payload.get("imap_folder") or "INBOX")[:255] or "INBOX",
    }


def public_mail_host_addresses(host: str, port: int) -> list[str]:
    if os.getenv("OUTREACH_EMAIL_ALLOW_PRIVATE_HOSTS", "0").strip().lower() in {
        "1", "true", "yes", "on",
    }:
        return []
    normalized_host = _text(host).lower().rstrip(".")
    if normalized_host in {"localhost", "localhost.localdomain"}:
        raise EmailAdapterError("mail_host_not_public", "Mail host must be public")
    try:
        addresses = {
            item[4][0]
            for item in socket.getaddrinfo(normalized_host, port, type=socket.SOCK_STREAM)
            if item and item[4]
        }
    except socket.gaierror as exc:
        raise EmailAdapterError("mail_host_unresolvable", "Mail host cannot be resolved", retryable=True) from exc
    if not addresses:
        raise EmailAdapterError("mail_host_unresolvable", "Mail host cannot be resolved", retryable=True)
    for raw_address in addresses:
        address = ipaddress.ip_address(raw_address)
        if not address.is_global:
            raise EmailAdapterError("mail_host_not_public", "Mail host resolves to a non-public address")
    return sorted(addresses)


def _smtp_connection(config: dict[str, Any], *, timeout: int) -> smtplib.SMTP:
    public_mail_host_addresses(config["smtp_host"], int(config["smtp_port"]))
    context = ssl.create_default_context()
    if config["smtp_security"] == "ssl":
        client = smtplib.SMTP_SSL(
            config["smtp_host"], int(config["smtp_port"]), timeout=timeout, context=context,
        )
    else:
        client = smtplib.SMTP(config["smtp_host"], int(config["smtp_port"]), timeout=timeout)
        client.ehlo()
        client.starttls(context=context)
        client.ehlo()
    client.login(config["username"], config["password"])
    return client


def _imap_connection(config: dict[str, Any], *, timeout: int) -> imaplib.IMAP4:
    public_mail_host_addresses(config["imap_host"], int(config["imap_port"]))
    context = ssl.create_default_context()
    if config["imap_security"] == "ssl":
        client = imaplib.IMAP4_SSL(
            config["imap_host"], int(config["imap_port"]), ssl_context=context, timeout=timeout,
        )
    else:
        client = imaplib.IMAP4(config["imap_host"], int(config["imap_port"]), timeout=timeout)
        client.starttls(ssl_context=context)
    client.login(config["username"], config["password"])
    return client


def _close_smtp(client: smtplib.SMTP | None) -> None:
    if not client:
        return
    try:
        client.quit()
    except Exception:
        try:
            client.close()
        except Exception:
            pass


def _close_imap(client: imaplib.IMAP4 | None) -> None:
    if not client:
        return
    try:
        client.logout()
    except Exception:
        try:
            client.shutdown()
        except Exception:
            pass


def classify_email_exception(exc: Exception) -> EmailAdapterError:
    lowered = _text(exc).lower()
    if isinstance(exc, EmailAdapterError):
        return exc
    if isinstance(exc, (smtplib.SMTPAuthenticationError, imaplib.IMAP4.error)) and any(
        token in lowered for token in ("auth", "login", "credential", "password")
    ):
        return EmailAdapterError("email_auth_invalid", "Mailbox authorization failed")
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        return EmailAdapterError("email_recipient_rejected", "Recipient address was rejected")
    if isinstance(exc, smtplib.SMTPSenderRefused):
        return EmailAdapterError("email_sender_rejected", "Sender address was rejected")
    if isinstance(exc, (TimeoutError, socket.timeout, ConnectionError, OSError)):
        return EmailAdapterError("email_transport_failed", "Mailbox connection failed", retryable=True)
    if any(token in lowered for token in ("rate limit", "too many", "temporarily unavailable", "try again")):
        return EmailAdapterError("email_temporary_failure", "Mailbox provider temporarily rejected the request", retryable=True)
    return EmailAdapterError("email_provider_failed", "Mailbox provider request failed", retryable=True)


def preflight_mailbox(config: dict[str, Any], *, timeout: int = 15) -> dict[str, Any]:
    smtp_client = None
    imap_client = None
    try:
        smtp_client = _smtp_connection(config, timeout=timeout)
        imap_client = _imap_connection(config, timeout=timeout)
        status, _data = imap_client.select(config.get("imap_folder") or "INBOX", readonly=True)
        if _text(status).upper() != "OK":
            raise EmailAdapterError("email_imap_folder_unavailable", "IMAP folder is unavailable")
        return {
            "ready": True,
            "sender_identity": config["email"],
            "capabilities": {
                "direct_send": True,
                "reply_sync": True,
                "provider": "native_smtp_imap",
            },
        }
    except Exception as exc:
        raise classify_email_exception(exc) from exc
    finally:
        _close_imap(imap_client)
        _close_smtp(smtp_client)


def load_mailbox_config(sender_account: dict[str, Any]) -> dict[str, Any]:
    encrypted = _text(sender_account.get("auth_data_encrypted"))
    if encrypted.startswith(EMAIL_CREDENTIAL_PREFIX):
        token = encrypted[len(EMAIL_CREDENTIAL_PREFIX):]
        try:
            decrypted = _email_credential_cipher().decrypt(token.encode("ascii")).decode("utf-8")
        except (InvalidToken, UnicodeError, ValueError) as exc:
            raise EmailAdapterError(
                "email_credentials_invalid",
                "Mailbox credentials cannot be decrypted with the configured outreach key",
            ) from exc
    else:
        decrypted = decrypt_auth_data(encrypted)
    if not decrypted:
        raise EmailAdapterError("email_credentials_missing", "Mailbox credentials are unavailable")
    try:
        payload = json.loads(decrypted)
    except (TypeError, ValueError) as exc:
        raise EmailAdapterError("email_credentials_invalid", "Mailbox credentials are invalid") from exc
    if not isinstance(payload, dict):
        raise EmailAdapterError("email_credentials_invalid", "Mailbox credentials are invalid")
    return normalize_mailbox_config(payload)


def send_email(
    sender_account: dict[str, Any],
    *,
    recipient: str,
    subject: str,
    body: str,
    idempotency_key: str,
    timeout: int = 20,
) -> dict[str, Any]:
    recipient_email = normalize_email(recipient)
    if not recipient_email:
        raise EmailAdapterError("email_recipient_invalid", "Recipient email is invalid")
    config = load_mailbox_config(sender_account)
    message = EmailMessage()
    display_name = _text(config.get("display_name"))
    message["From"] = f"{display_name} <{config['email']}>" if display_name else config["email"]
    message["To"] = recipient_email
    message["Subject"] = _text(subject)[:200] or "Короткий вопрос"
    message["Date"] = format_datetime(datetime.now(timezone.utc))
    domain = config["email"].rsplit("@", 1)[1]
    message_id = make_msgid(domain=domain)
    message["Message-ID"] = message_id
    message["X-LocalOS-Idempotency-Key"] = _text(idempotency_key)[:200]
    message.set_content(_text(body))
    client = None
    submission_started = False
    try:
        client = _smtp_connection(config, timeout=timeout)
        submission_started = True
        refused = client.send_message(message, from_addr=config["email"], to_addrs=[recipient_email])
        if refused:
            raise EmailAdapterError("email_recipient_rejected", "Recipient address was rejected")
        return {
            "success": True,
            "provider_name": "native_email",
            "provider_account_id": str(sender_account.get("id") or ""),
            "provider_message_id": message_id,
            "recipient_kind": "email",
            "recipient_value": recipient_email,
        }
    except Exception as exc:
        classified = classify_email_exception(exc)
        if submission_started and classified.code not in {
            "email_recipient_rejected",
            "email_sender_rejected",
        }:
            raise EmailAdapterError(
                "email_send_uncertain",
                "Mailbox connection changed after send started; manual delivery check required",
                retryable=False,
            ) from exc
        raise classified from exc
    finally:
        _close_smtp(client)


def _message_body(message: Message) -> str:
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_disposition() == "attachment":
                continue
            if part.get_content_type() == "text/plain":
                try:
                    return _text(part.get_content())[:10000]
                except Exception:
                    continue
        return ""
    try:
        return _text(message.get_content())[:10000]
    except Exception:
        payload = message.get_payload(decode=True)
        return payload.decode(message.get_content_charset() or "utf-8", errors="replace")[:10000] if payload else ""


def _message_datetime(raw_value: Any) -> datetime | None:
    if not raw_value:
        return None
    try:
        parsed = parsedate_to_datetime(_text(raw_value))
    except (TypeError, ValueError, OverflowError):
        return None
    if not parsed.tzinfo:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def fetch_replies(
    sender_account: dict[str, Any],
    *,
    since_at: datetime | None = None,
    limit: int = 100,
    timeout: int = 20,
) -> list[dict[str, Any]]:
    config = load_mailbox_config(sender_account)
    sync_since = since_at or datetime.now(timezone.utc) - timedelta(days=DEFAULT_SYNC_LOOKBACK_DAYS)
    safe_limit = max(1, min(int(limit or 100), 500))
    client = None
    try:
        client = _imap_connection(config, timeout=timeout)
        status, _data = client.select(config.get("imap_folder") or "INBOX", readonly=True)
        if _text(status).upper() != "OK":
            raise EmailAdapterError("email_imap_folder_unavailable", "IMAP folder is unavailable")
        since_token = sync_since.astimezone(timezone.utc).strftime("%d-%b-%Y")
        status, data = client.uid("search", None, "SINCE", since_token)
        if _text(status).upper() != "OK":
            raise EmailAdapterError("email_imap_search_failed", "IMAP search failed", retryable=True)
        raw_ids = data[0].split() if data and data[0] else []
        replies: list[dict[str, Any]] = []
        for raw_uid in raw_ids[-safe_limit:]:
            status, fetched = client.uid("fetch", raw_uid, "(RFC822)")
            if _text(status).upper() != "OK" or not fetched:
                continue
            raw_message = next(
                (item[1] for item in fetched if isinstance(item, tuple) and len(item) > 1 and isinstance(item[1], bytes)),
                None,
            )
            if not raw_message:
                continue
            message = BytesParser(policy=policy.default).parsebytes(raw_message)
            occurred_at = _message_datetime(message.get("Date"))
            if occurred_at and occurred_at < sync_since - timedelta(days=1):
                continue
            from_addresses = [normalize_email(address) for _name, address in getaddresses(message.get_all("From", []))]
            normalized_from = next((address for address in from_addresses if address), "")
            uid = raw_uid.decode("ascii", errors="ignore") if isinstance(raw_uid, bytes) else _text(raw_uid)
            references = " ".join(message.get_all("References", []))
            replies.append({
                "provider_event_id": f"email:{sender_account.get('id')}:{uid}"[:255],
                "mailbox_uid": uid,
                "message_id": _text(message.get("Message-ID"))[:255] or None,
                "in_reply_to": _text(message.get("In-Reply-To"))[:1000] or None,
                "references": references[:4000] or None,
                "from_email": normalized_from or None,
                "subject": _text(message.get("Subject"))[:500],
                "body": _message_body(message),
                "auto_submitted": _text(message.get("Auto-Submitted"))[:100],
                "precedence": _text(message.get("Precedence"))[:100],
                "occurred_at": occurred_at or datetime.now(timezone.utc),
            })
        return replies
    except Exception as exc:
        raise classify_email_exception(exc) from exc
    finally:
        _close_imap(client)
