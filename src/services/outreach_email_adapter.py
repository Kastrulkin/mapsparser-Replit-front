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
import re
import time
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
DEFAULT_COMPLETE_SYNC_MESSAGE_LIMIT = 5000
COMPLETE_REPLY_MAILBOX_ROLES = ("all", "spam", "trash")
EMAIL_CREDENTIAL_PREFIX = "localos-outreach-email-v1:"


class EmailAdapterError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        stage: str | None = None,
        provider_status: int | None = None,
        provider_reason: str | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.stage = stage
        self.provider_status = provider_status
        self.provider_reason = provider_reason


EMAIL_ERROR_STAGES = {
    "smtp_connect", "smtp_auth", "imap_connect", "imap_auth", "imap_folder",
}
EMAIL_PROVIDER_REASONS = {
    "authentication_rejected",
    "connection_failed",
    "connection_timeout",
    "dns_unresolvable",
    "folder_unavailable",
    "host_not_public",
    "provider_rejected",
    "temporarily_unavailable",
    "tls_failed",
}


def email_error_public_details(exc: Exception) -> dict[str, Any]:
    """Return allowlisted diagnostics without provider text or credentials."""
    stage = getattr(exc, "stage", None)
    provider_status = getattr(exc, "provider_status", None)
    provider_reason = getattr(exc, "provider_reason", None)
    details: dict[str, Any] = {}
    if stage in EMAIL_ERROR_STAGES:
        details["stage"] = stage
    if (
        isinstance(provider_status, int)
        and not isinstance(provider_status, bool)
        and 100 <= provider_status <= 599
    ):
        details["provider_status"] = provider_status
    if provider_reason in EMAIL_PROVIDER_REASONS:
        details["provider_reason"] = provider_reason
    transport_reasons = {"connection_failed", "connection_timeout", "tls_failed"}
    if provider_reason in transport_reasons and stage in {"smtp_connect", "smtp_auth"}:
        details["next_action"] = "Проверьте SMTP-сервер, порт и режим защиты SSL/STARTTLS."
        return details
    if provider_reason in transport_reasons and stage in {"imap_connect", "imap_auth"}:
        details["next_action"] = "Проверьте IMAP-сервер, порт и режим защиты SSL/STARTTLS."
        return details
    next_actions = {
        "smtp_auth": "Проверьте логин и пароль приложения в настройках почтового сервиса.",
        "imap_auth": "Проверьте логин и пароль приложения в настройках почтового сервиса.",
        "smtp_connect": "Проверьте SMTP-сервер, порт и режим защиты SSL/STARTTLS.",
        "imap_connect": "Проверьте IMAP-сервер, порт и режим защиты SSL/STARTTLS.",
        "imap_folder": "Проверьте, что IMAP включён и папка INBOX доступна.",
    }
    if stage in next_actions:
        details["next_action"] = next_actions[stage]
    return details


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
    client = None
    try:
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
    except Exception as exc:
        _close_smtp(client)
        raise classify_email_exception(exc, stage="smtp_connect") from None
    try:
        client.login(config["username"], config["password"])
    except Exception as exc:
        _close_smtp(client)
        raise classify_email_exception(exc, stage="smtp_auth") from None
    return client


def _imap_connection(config: dict[str, Any], *, timeout: int) -> imaplib.IMAP4:
    client = None
    try:
        public_mail_host_addresses(config["imap_host"], int(config["imap_port"]))
        context = ssl.create_default_context()
        if config["imap_security"] == "ssl":
            client = imaplib.IMAP4_SSL(
                config["imap_host"], int(config["imap_port"]), ssl_context=context, timeout=timeout,
            )
        else:
            client = imaplib.IMAP4(config["imap_host"], int(config["imap_port"]), timeout=timeout)
            client.starttls(ssl_context=context)
    except Exception as exc:
        _close_imap(client)
        raise classify_email_exception(exc, stage="imap_connect") from None
    try:
        client.login(config["username"], config["password"])
    except Exception as exc:
        _close_imap(client)
        raise classify_email_exception(exc, stage="imap_auth") from None
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


def classify_email_exception(
    exc: Exception,
    *,
    stage: str | None = None,
) -> EmailAdapterError:
    lowered = _text(exc).lower()
    if isinstance(exc, EmailAdapterError):
        if exc.stage or stage not in EMAIL_ERROR_STAGES:
            return exc
        resolved_stage = exc.stage or (stage if stage in EMAIL_ERROR_STAGES else None)
        reason_by_code = {
            "mail_host_unresolvable": "dns_unresolvable",
            "mail_host_not_public": "host_not_public",
            "email_imap_folder_unavailable": "folder_unavailable",
        }
        return EmailAdapterError(
            exc.code,
            _email_error_message(exc.code, resolved_stage),
            retryable=exc.retryable,
            stage=resolved_stage,
            provider_status=exc.provider_status,
            provider_reason=exc.provider_reason or reason_by_code.get(exc.code),
        )
    explicit_auth_stage = (
        (stage == "smtp_auth" and isinstance(exc, smtplib.SMTPAuthenticationError))
        or (
            stage == "imap_auth"
            and isinstance(exc, imaplib.IMAP4.error)
            and not isinstance(exc, imaplib.IMAP4.abort)
        )
    )
    inferred_auth = isinstance(exc, (smtplib.SMTPAuthenticationError, imaplib.IMAP4.error)) and any(
        token in lowered for token in ("auth", "login", "credential", "password")
    )
    if explicit_auth_stage or inferred_auth:
        auth_stage = stage if explicit_auth_stage else (
            "smtp_auth" if isinstance(exc, smtplib.SMTPAuthenticationError) else "imap_auth"
        )
        return EmailAdapterError(
            "email_auth_invalid",
            _email_error_message("email_auth_invalid", auth_stage),
            stage=auth_stage,
            provider_status=_smtp_status(exc),
            provider_reason="authentication_rejected",
        )
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        return EmailAdapterError("email_recipient_rejected", "Recipient address was rejected")
    if isinstance(exc, smtplib.SMTPSenderRefused):
        return EmailAdapterError("email_sender_rejected", "Sender address was rejected")
    if isinstance(exc, ssl.SSLError):
        return EmailAdapterError(
            "email_transport_failed",
            _email_error_message("email_transport_failed", stage),
            retryable=True,
            stage=stage,
            provider_reason="tls_failed",
        )
    if isinstance(exc, (
        TimeoutError,
        socket.timeout,
        ConnectionError,
        OSError,
        smtplib.SMTPServerDisconnected,
        imaplib.IMAP4.abort,
    )):
        reason = "connection_timeout" if isinstance(exc, (TimeoutError, socket.timeout)) else "connection_failed"
        return EmailAdapterError(
            "email_transport_failed",
            _email_error_message("email_transport_failed", stage),
            retryable=True,
            stage=stage,
            provider_reason=reason,
        )
    if any(token in lowered for token in ("rate limit", "too many", "temporarily unavailable", "try again")):
        return EmailAdapterError(
            "email_temporary_failure",
            _email_error_message("email_temporary_failure", stage),
            retryable=True,
            stage=stage,
            provider_status=_smtp_status(exc),
            provider_reason="temporarily_unavailable",
        )
    return EmailAdapterError(
        "email_provider_failed",
        _email_error_message("email_provider_failed", stage),
        retryable=True,
        stage=stage,
        provider_status=_smtp_status(exc),
        provider_reason="provider_rejected",
    )


def _smtp_status(exc: Exception) -> int | None:
    status = getattr(exc, "smtp_code", None)
    return status if isinstance(status, int) and not isinstance(status, bool) else None


def _email_error_message(code: str, stage: str | None) -> str:
    if code == "email_auth_invalid" and stage == "smtp_auth":
        return "Сервер отправки отклонил вход (SMTP)."
    if code == "email_auth_invalid" and stage == "imap_auth":
        return "Сервер входящей почты отклонил вход (IMAP)."
    if code == "email_imap_folder_unavailable" or stage == "imap_folder":
        return "IMAP подключён, но папка INBOX недоступна."
    if stage == "smtp_connect":
        return "Не удалось установить защищённое соединение с SMTP."
    if stage == "imap_connect":
        return "Не удалось установить защищённое соединение с IMAP."
    if code == "email_temporary_failure":
        return "Почтовый провайдер временно отклонил проверку."
    if code == "email_auth_invalid":
        return "Почтовый провайдер не принял логин или пароль приложения."
    return "Почтовый провайдер не завершил проверку подключения."


def preflight_mailbox(config: dict[str, Any], *, timeout: int = 15) -> dict[str, Any]:
    smtp_client = None
    imap_client = None
    try:
        smtp_client = _smtp_connection(config, timeout=timeout)
        imap_client = _imap_connection(config, timeout=timeout)
        try:
            status, _data = imap_client.select(config.get("imap_folder") or "INBOX", readonly=True)
        except Exception as exc:
            raise classify_email_exception(exc, stage="imap_folder") from None
        if _text(status).upper() != "OK":
            raise EmailAdapterError(
                "email_imap_folder_unavailable",
                "IMAP подключён, но папка INBOX недоступна.",
                stage="imap_folder",
                provider_reason="folder_unavailable",
            )
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
        raise classify_email_exception(exc) from None
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


def _gmail_mailbox_name(raw_line: bytes) -> str:
    line = raw_line.decode("utf-8", errors="replace").strip()
    match = re.search(r'\)\s+"(?:[^"\\]|\\.)*"\s+("(?:[^"\\]|\\.)*"|\S+)\s*$', line)
    if not match:
        raise EmailAdapterError("email_sent_label_unavailable", "Gmail mailbox list could not be parsed")
    value = match.group(1)
    if value.startswith('"') and value.endswith('"'):
        value = value[1:-1].replace(r'\"', '"').replace(r'\\', '\\')
    return value


def _imap_mailbox_argument(mailbox: str) -> str:
    """Return one safe IMAP mailbox argument, quoting non-atom names."""
    value = _text(mailbox)
    if not value or any(character in value for character in ("\x00", "\r", "\n")):
        raise EmailAdapterError("email_imap_folder_unavailable", "IMAP mailbox name is invalid")
    if re.search(r'[\s"\\]', value):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return value


def _apply_gmail_sent_label(
    config: dict[str, Any],
    *,
    message_id: str,
    label_name: str,
    timeout: int,
) -> dict[str, Any]:
    """Apply one existing Gmail label to one exact sent message."""
    normalized_label = _text(label_name)
    if not normalized_label or any(character in normalized_label for character in ('"', "\r", "\n")):
        raise EmailAdapterError("email_sent_label_invalid", "Gmail sent label is invalid")
    client = None
    try:
        client = _imap_connection(config, timeout=timeout)
        capabilities = {
            value.decode("ascii", errors="ignore").upper() if isinstance(value, bytes) else str(value).upper()
            for value in client.capabilities
        }
        if "X-GM-EXT-1" not in capabilities:
            raise EmailAdapterError("email_sent_label_unavailable", "Gmail label extension is unavailable")
        status, data = client.list()
        if _text(status).upper() != "OK":
            raise EmailAdapterError("email_sent_label_unavailable", "Gmail mailbox list is unavailable")
        lines = [item for item in (data or []) if isinstance(item, bytes)]
        sent_names = [_gmail_mailbox_name(line) for line in lines if b"\\Sent" in line]
        label_names = [_gmail_mailbox_name(line) for line in lines]
        if len(sent_names) != 1 or normalized_label not in label_names:
            raise EmailAdapterError("email_sent_label_unavailable", "Gmail Sent mailbox or label is unavailable")
        status, _ = client.select(_imap_mailbox_argument(sent_names[0]), readonly=False)
        if _text(status).upper() != "OK":
            raise EmailAdapterError("email_sent_label_unavailable", "Gmail Sent mailbox is unavailable")
        matched: list[str] = []
        for _attempt in range(10):
            status, result = client.uid("search", None, "X-GM-RAW", f'"rfc822msgid:{message_id}"')
            if _text(status).upper() != "OK":
                raise EmailAdapterError("email_sent_label_unavailable", "Gmail sent message lookup failed")
            matched = _text(result[0] if result else "").split()
            if matched:
                break
            time.sleep(0.25)
        if len(matched) != 1:
            raise EmailAdapterError("email_sent_label_message_not_found", "Sent message was not found for labeling")
        status, _ = client.uid("store", matched[0], "+X-GM-LABELS", f'("{normalized_label}")')
        if _text(status).upper() != "OK":
            raise EmailAdapterError("email_sent_label_failed", "Gmail label could not be applied")
        return {"status": "labeled", "label": normalized_label}
    finally:
        _close_imap(client)


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
        result = {
            "success": True,
            "provider_name": "native_email",
            "provider_account_id": str(sender_account.get("id") or ""),
            "provider_message_id": message_id,
            "recipient_kind": "email",
            "recipient_value": recipient_email,
        }
        capabilities = (
            sender_account.get("capabilities_json")
            if isinstance(sender_account.get("capabilities_json"), dict)
            else {}
        )
        sent_label = _text(capabilities.get("sent_label"))
        if sent_label:
            try:
                result["sent_label"] = _apply_gmail_sent_label(
                    config,
                    message_id=message_id,
                    label_name=sent_label,
                    timeout=timeout,
                )
            except Exception as label_error:
                classified_label_error = classify_email_exception(label_error)
                result["sent_label"] = {
                    "status": "warning",
                    "label": sent_label,
                    "reason_code": classified_label_error.code,
                }
        return result
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


def mailbox_identity_fingerprint(sender_account: dict[str, Any]) -> str:
    """Bind a sync receipt to the currently configured non-secret IMAP identity."""
    config = load_mailbox_config(sender_account)
    declared_identity = normalize_email(sender_account.get("sender_identity"))
    if declared_identity and declared_identity != config["email"]:
        raise EmailAdapterError(
            "email_sender_identity_mismatch",
            "Connected sender identity does not match the mailbox configuration",
        )
    identity = {
        "version": 1,
        "provider": "native_smtp_imap",
        "email": config["email"],
        "username": _text(config.get("username")),
        "imap_host": config["imap_host"],
        "imap_port": int(config["imap_port"]),
        "imap_security": config["imap_security"],
        "inbox_folder": config.get("imap_folder") or "INBOX",
    }
    encoded = json.dumps(identity, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def normalize_recipient_scope(recipient_emails: list[str]) -> list[str]:
    normalized: set[str] = set()
    for value in recipient_emails:
        recipient = normalize_email(value)
        if not recipient:
            raise EmailAdapterError(
                "email_imap_recipient_scope_invalid",
                "Reply sync recipient scope contains an invalid email address",
            )
        normalized.add(recipient)
    if not normalized:
        raise EmailAdapterError(
            "email_imap_recipient_scope_missing",
            "Reply sync requires at least one authorized recipient",
        )
    return sorted(normalized)


def email_recipient_hashes(recipient_emails: list[str]) -> list[str]:
    return [
        hashlib.sha256(f"email:{recipient}".encode("utf-8")).hexdigest()
        for recipient in normalize_recipient_scope(recipient_emails)
    ]


def email_recipient_scope_fingerprint(
    sender_account: dict[str, Any],
    recipient_emails: list[str],
) -> str:
    return email_recipient_scope_fingerprint_from_hashes(
        sender_account,
        email_recipient_hashes(recipient_emails),
    )


def email_recipient_scope_fingerprint_from_hashes(
    sender_account: dict[str, Any],
    recipient_hashes: list[str],
) -> str:
    sender_id = _text(sender_account.get("id"))
    scope_type = _text(sender_account.get("scope_type"))
    business_id = _text(sender_account.get("business_id")) or None
    if not sender_id or scope_type not in {"platform", "business"}:
        raise EmailAdapterError(
            "email_sender_scope_invalid",
            "Email sender scope is unavailable",
        )
    if (scope_type == "platform" and business_id) or (scope_type == "business" and not business_id):
        raise EmailAdapterError(
            "email_sender_scope_invalid",
            "Email sender scope does not match its business binding",
        )
    normalized_hashes = sorted(set(recipient_hashes))
    if (
        not normalized_hashes
        or len(normalized_hashes) != len(recipient_hashes)
        or any(not re.fullmatch(r"[0-9a-f]{64}", value) for value in normalized_hashes)
    ):
        raise EmailAdapterError(
            "email_imap_recipient_scope_invalid",
            "Reply sync recipient hashes are invalid",
        )
    scope = {
        "version": 1,
        "sender_account_id": sender_id,
        "sender_scope_type": scope_type,
        "sender_business_id": business_id,
        "recipient_hashes": normalized_hashes,
    }
    encoded = json.dumps(scope, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _sent_mailbox(client: imaplib.IMAP4) -> str:
    status, data = client.list()
    if _text(status).upper() != "OK":
        raise EmailAdapterError("email_sent_label_unavailable", "Sent mailbox list is unavailable")
    lines = [item for item in (data or []) if isinstance(item, bytes)]
    names = [_gmail_mailbox_name(line) for line in lines if b"\\Sent" in line]
    if len(names) != 1:
        raise EmailAdapterError("email_sent_label_unavailable", "Sent mailbox is unavailable")
    return names[0]


def _special_use_mailbox(client: imaplib.IMAP4, flag: bytes) -> str:
    status, data = client.list()
    if _text(status).upper() != "OK":
        raise EmailAdapterError("email_imap_folder_unavailable", "IMAP mailbox list is unavailable")
    lines = [item for item in (data or []) if isinstance(item, bytes)]
    names = [_gmail_mailbox_name(line) for line in lines if flag in line.split(b")", 1)[0]]
    if len(names) != 1:
        raise EmailAdapterError("email_imap_folder_unavailable", "Required IMAP folder is unavailable")
    return names[0]


def complete_reply_mailbox_roles(sender_account: dict[str, Any], *, timeout: int = 20) -> list[str]:
    """Require every special-use folder needed for a complete scoped reply proof."""
    config = load_mailbox_config(sender_account)
    client = None
    try:
        client = _imap_connection(config, timeout=timeout)
        _special_use_mailbox(client, b"\\All")
        _special_use_mailbox(client, b"\\Junk")
        _special_use_mailbox(client, b"\\Trash")
        return list(COMPLETE_REPLY_MAILBOX_ROLES)
    finally:
        _close_imap(client)


def _imap_response_number(client: imaplib.IMAP4, name: str) -> int:
    _code, values = client.response(name)
    raw_value = values[0] if values else None
    try:
        decoded_value = raw_value.decode("ascii", errors="strict") if isinstance(raw_value, bytes) else _text(raw_value)
        value = int(decoded_value)
    except (TypeError, ValueError):
        value = 0
    if name == "UIDVALIDITY" and value < 1:
        raise EmailAdapterError(
            "email_imap_uidvalidity_missing",
            "IMAP folder UIDVALIDITY is unavailable",
        )
    if name == "UIDNEXT" and value < 1:
        raise EmailAdapterError(
            "email_imap_uidnext_missing",
            "IMAP folder UIDNEXT is unavailable",
        )
    return value


def _imap_status_number(client: imaplib.IMAP4, mailbox: str, name: str) -> int:
    status, values = client.status(_imap_mailbox_argument(mailbox), f"({name})")
    raw_value = next((value for value in (values or []) if isinstance(value, bytes)), b"")
    match = re.search(rb"(?:^|[ (])" + name.encode("ascii") + rb"\s+(\d+)(?:[ )]|$)", raw_value, re.I)
    value = int(match.group(1)) if _text(status).upper() == "OK" and match else 0
    if name == "UIDVALIDITY" and value < 1:
        raise EmailAdapterError(
            "email_imap_uidvalidity_missing",
            "IMAP folder UIDVALIDITY is unavailable",
        )
    if name == "UIDNEXT" and value < 1:
        raise EmailAdapterError(
            "email_imap_uidnext_missing",
            "IMAP folder UIDNEXT is unavailable",
        )
    return value


def _imap_internal_datetime(metadata: bytes) -> datetime:
    match = re.search(rb'INTERNALDATE "([^"]+)"', metadata)
    raw_value = match.group(1).decode("ascii", errors="strict") if match else None
    parsed = _message_datetime(raw_value)
    if not parsed:
        raise EmailAdapterError(
            "email_imap_message_parse_failed",
            "IMAP message INTERNALDATE could not be parsed",
        )
    return parsed


def _normalized_imap_message(
    sender_account: dict[str, Any],
    *,
    mailbox: str,
    uid: str,
    raw_message: bytes,
    internal_at: datetime,
) -> dict[str, Any]:
    try:
        message = BytesParser(policy=policy.default).parsebytes(raw_message)
        from_addresses = [
            normalize_email(address)
            for _name, address in getaddresses(message.get_all("From", []))
        ]
        to_addresses = [
            normalize_email(address)
            for _name, address in getaddresses(message.get_all("To", []))
        ]
        references = " ".join(message.get_all("References", []))
        body = _message_body(message)
        dsn = _delivery_status_details(message)
    except Exception as exc:
        raise EmailAdapterError(
            "email_imap_message_parse_failed",
            "IMAP message could not be parsed",
        ) from exc
    event_prefix = f"email:{sender_account.get('id')}"
    mailbox_suffix = "" if mailbox == "inbox" else f":{mailbox}"
    return {
        "provider_event_id": (
            f"{event_prefix}{mailbox_suffix}:{uid}"
        )[:255],
        "mailbox_uid": uid,
        "mailbox": mailbox,
        "message_id": _text(message.get("Message-ID"))[:255] or None,
        "in_reply_to": _text(message.get("In-Reply-To"))[:1000] or None,
        "references": references[:4000] or None,
        "from_email": next((address for address in from_addresses if address), "") or None,
        "to_emails": [address for address in to_addresses if address],
        "subject": _text(message.get("Subject"))[:500],
        "body": body,
        "auto_submitted": _text(message.get("Auto-Submitted"))[:100],
        "precedence": _text(message.get("Precedence"))[:100],
        "is_delivery_status_notification": bool(dsn["is_dsn"]),
        "dsn_recipient_emails": dsn["recipient_emails"],
        "dsn_original_message_ids": dsn["original_message_ids"],
        "dsn_classification": dsn["classification"],
        "occurred_at": _message_datetime(message.get("Date")) or internal_at,
        "mailbox_internal_at": internal_at,
    }


def _dsn_recipient(value: Any) -> str:
    raw_value = _text(value)
    if ";" in raw_value:
        raw_value = raw_value.split(";", 1)[1]
    parsed = getaddresses([raw_value])
    return next((normalize_email(address) for _name, address in parsed if normalize_email(address)), "")


def _delivery_status_details(message: Message) -> dict[str, Any]:
    recipients = {
        normalize_email(address)
        for _name, address in getaddresses(message.get_all("X-Failed-Recipients", []))
        if normalize_email(address)
    }
    original_message_ids: set[str] = set()
    actions: set[str] = set()
    statuses: set[str] = set()
    is_dsn = (
        message.get_content_type() == "multipart/report"
        and _text(message.get_param("report-type")).lower() == "delivery-status"
    ) or bool(recipients)
    for part in message.walk():
        if part.get_content_type() == "message/delivery-status":
            is_dsn = True
            blocks = part.get_payload()
            if not isinstance(blocks, list):
                blocks = []
            for block in blocks:
                if not isinstance(block, Message):
                    continue
                for field in ("Final-Recipient", "Original-Recipient"):
                    for value in block.get_all(field, []):
                        recipient = _dsn_recipient(value)
                        if recipient:
                            recipients.add(recipient)
                actions.update(_text(value).lower() for value in block.get_all("Action", []) if _text(value))
                statuses.update(_text(value).lower() for value in block.get_all("Status", []) if _text(value))
                original_message_ids.update(
                    _text(value).lower()
                    for value in block.get_all("Original-Message-ID", [])
                    if _text(value)
                )
        elif part.get_content_type() == "message/rfc822":
            embedded = part.get_payload()
            if not isinstance(embedded, list):
                embedded = []
            for original in embedded:
                if not isinstance(original, Message):
                    continue
                recipients.update(
                    normalize_email(address)
                    for _name, address in getaddresses(original.get_all("To", []))
                    if normalize_email(address)
                )
                if _text(original.get("Message-ID")):
                    original_message_ids.add(_text(original.get("Message-ID")).lower())
    permanent = "failed" in actions or any(status.startswith("5") for status in statuses)
    temporary = "delayed" in actions or any(status.startswith("4") for status in statuses)
    return {
        "is_dsn": is_dsn,
        "recipient_emails": sorted(recipients),
        "original_message_ids": sorted(original_message_ids),
        "classification": (
            "permanent_delivery_failure"
            if permanent
            else "temporary_delivery_failure"
            if temporary
            else "system_acknowledgement"
            if is_dsn
            else None
        ),
    }


def _header_scope_kind(
    raw_headers: bytes,
    recipient_emails: list[str],
    *,
    mailbox: str,
) -> str | None:
    try:
        headers = BytesParser(policy=policy.default).parsebytes(raw_headers, headersonly=True)
        from_addresses = {
            normalize_email(address)
            for _name, address in getaddresses(headers.get_all("From", []))
        }
        to_addresses = {
            normalize_email(address)
            for _name, address in getaddresses(headers.get_all("To", []))
        }
    except Exception as exc:
        raise EmailAdapterError(
            "email_imap_message_parse_failed",
            "IMAP message headers could not be parsed",
        ) from exc
    if mailbox == "sent" and to_addresses.intersection(recipient_emails):
        return "recipient"
    if mailbox != "sent" and from_addresses.intersection(recipient_emails):
        return "recipient"
    from_local_parts = {
        address.split("@", 1)[0]
        for address in from_addresses
        if "@" in address
    }
    content_type = headers.get_content_type()
    report_type = _text(headers.get_param("report-type")).lower()
    if (
        bool(headers.get_all("X-Failed-Recipients", []))
        or (content_type == "multipart/report" and report_type == "delivery-status")
        or bool(from_local_parts.intersection({"mailer-daemon", "postmaster"}))
    ):
        return "dsn"
    return None


def fetch_complete_mailbox_window(
    sender_account: dict[str, Any],
    *,
    mailbox: str,
    since_at: datetime,
    until_at: datetime,
    max_messages: int = DEFAULT_COMPLETE_SYNC_MESSAGE_LIMIT,
    recipient_emails: list[str] | None = None,
    timeout: int = 20,
) -> dict[str, Any]:
    """Fetch every UID in one bounded IMAP window or fail without a complete result."""
    if mailbox not in {"inbox", "sent", "all", "spam", "trash"}:
        raise ValueError("mailbox_role_invalid")
    window_start = since_at.astimezone(timezone.utc)
    window_end = until_at.astimezone(timezone.utc)
    if window_end < window_start:
        raise ValueError("mailbox_window_invalid")
    safe_max_messages = min(max(0, int(max_messages)), 20000)
    normalized_recipient_emails = (
        normalize_recipient_scope(recipient_emails or [])
        if mailbox in COMPLETE_REPLY_MAILBOX_ROLES
        or (mailbox in {"inbox", "sent"} and recipient_emails)
        else []
    )
    config = load_mailbox_config(sender_account)
    client = None
    try:
        client = _imap_connection(config, timeout=timeout)
        if mailbox == "sent":
            folder = _sent_mailbox(client)
        elif mailbox == "all":
            folder = _special_use_mailbox(client, b"\\All")
        elif mailbox == "spam":
            folder = _special_use_mailbox(client, b"\\Junk")
        elif mailbox == "trash":
            folder = _special_use_mailbox(client, b"\\Trash")
        else:
            folder = config.get("imap_folder") or "INBOX"
        status, _data = client.select(_imap_mailbox_argument(folder), readonly=True)
        if _text(status).upper() != "OK":
            raise EmailAdapterError("email_imap_folder_unavailable", "IMAP folder is unavailable")
        uidvalidity = _imap_response_number(client, "UIDVALIDITY")
        high_watermark_uid = _imap_response_number(client, "UIDNEXT") - 1
        raw_ids: list[bytes] = []
        if high_watermark_uid > 0:
            since_token = window_start.strftime("%d-%b-%Y")
            criteria = ["UID", f"1:{high_watermark_uid}", "SINCE", since_token]
            status, data = client.uid("search", None, *criteria)
            if _text(status).upper() != "OK":
                raise EmailAdapterError("email_imap_search_failed", "IMAP search failed", retryable=True)
            raw_ids = sorted(
                set(data[0].split() if data and data[0] else []),
                key=lambda value: int(value),
            )
        if len(raw_ids) > safe_max_messages:
            raise EmailAdapterError(
                "email_imap_window_limit_exceeded",
                "IMAP window exceeds the complete-sync safety limit",
            )
        messages: list[dict[str, Any]] = []
        header_checked_uid_count = 0
        matched_uid_count = 0
        fetched_uid_count = 0
        body_checked_uid_count = 0
        for raw_uid in raw_ids:
            status, header_result = client.uid(
                "fetch",
                raw_uid,
                "(UID INTERNALDATE BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT AUTO-SUBMITTED CONTENT-TYPE X-FAILED-RECIPIENTS)])",
            )
            if _text(status).upper() != "OK" or not header_result:
                raise EmailAdapterError(
                    "email_imap_fetch_failed",
                    "IMAP message header fetch failed before the window was complete",
                    retryable=True,
                )
            header_record = next(
                (
                    item
                    for item in header_result
                    if isinstance(item, tuple)
                    and len(item) > 1
                    and isinstance(item[0], bytes)
                    and isinstance(item[1], bytes)
                ),
                None,
            )
            if not header_record:
                raise EmailAdapterError(
                    "email_imap_fetch_failed",
                    "IMAP message headers were unavailable before the window was complete",
                    retryable=True,
                )
            header_checked_uid_count += 1
            internal_at = _imap_internal_datetime(header_record[0])
            uid = raw_uid.decode("ascii", errors="strict") if isinstance(raw_uid, bytes) else _text(raw_uid)
            if not uid.isdigit() or int(uid) > high_watermark_uid:
                raise EmailAdapterError(
                    "email_imap_uid_invalid",
                    "IMAP returned an invalid UID inside the bounded window",
                )
            if internal_at < window_start or internal_at > window_end:
                continue
            scope_kind = (
                _header_scope_kind(
                    header_record[1],
                    normalized_recipient_emails,
                    mailbox=mailbox,
                )
                if normalized_recipient_emails
                else "unscoped"
            )
            if not scope_kind:
                continue
            status, body_result = client.uid("fetch", raw_uid, "(UID INTERNALDATE BODY.PEEK[])")
            if _text(status).upper() != "OK" or not body_result:
                raise EmailAdapterError(
                    "email_imap_fetch_failed",
                    "IMAP message body fetch failed before the window was complete",
                    retryable=True,
                )
            body_record = next(
                (
                    item
                    for item in body_result
                    if isinstance(item, tuple)
                    and len(item) > 1
                    and isinstance(item[0], bytes)
                    and isinstance(item[1], bytes)
                ),
                None,
            )
            if not body_record:
                raise EmailAdapterError(
                    "email_imap_fetch_failed",
                    "IMAP message body was unavailable before the window was complete",
                    retryable=True,
                )
            body_checked_uid_count += 1
            message = _normalized_imap_message(
                sender_account,
                mailbox=mailbox,
                uid=uid,
                raw_message=body_record[1],
                internal_at=internal_at,
            )
            if scope_kind == "recipient":
                body_scope_matches = (
                    bool(set(message.get("to_emails") or []).intersection(normalized_recipient_emails))
                    if mailbox == "sent"
                    else message.get("from_email") in normalized_recipient_emails
                )
                if not body_scope_matches:
                    raise EmailAdapterError(
                        "email_imap_recipient_scope_mismatch",
                        "IMAP message body changed outside the authorized recipient scope",
                    )
            elif scope_kind == "dsn":
                dsn_recipients = set(message.get("dsn_recipient_emails") or [])
                if not message.get("is_delivery_status_notification") or not dsn_recipients:
                    raise EmailAdapterError(
                        "email_imap_dsn_scope_unverified",
                        "A potential delivery-status message could not be tied to an original recipient",
                    )
                if not dsn_recipients.intersection(normalized_recipient_emails):
                    continue
            matched_uid_count += 1
            fetched_uid_count += 1
            messages.append(message)
        if _imap_status_number(client, folder, "UIDVALIDITY") != uidvalidity:
            raise EmailAdapterError(
                "email_imap_uidvalidity_changed",
                "IMAP folder changed while the bounded window was being read",
                retryable=True,
            )
        return {
            "messages": messages,
            "folder": {
                "role": mailbox,
                "name": folder,
                "uidvalidity": uidvalidity,
                "high_watermark_uid": high_watermark_uid,
                "candidate_uid_count": len(raw_ids),
                "header_checked_uid_count": header_checked_uid_count,
                "matched_uid_count": matched_uid_count,
                "fetched_uid_count": fetched_uid_count,
                "body_checked_uid_count": body_checked_uid_count,
                "window_message_count": len(messages),
                "recipient_scope_count": len(normalized_recipient_emails),
            },
        }
    except Exception as exc:
        raise classify_email_exception(exc) from exc
    finally:
        _close_imap(client)


def fetch_mailbox_messages(
    sender_account: dict[str, Any],
    *,
    mailbox: str,
    since_at: datetime | None = None,
    limit: int = 100,
    timeout: int = 20,
) -> list[dict[str, Any]]:
    """Read normalized Inbox/Sent envelopes without enumerating unrelated mailboxes."""
    config = load_mailbox_config(sender_account)
    sync_since = since_at or datetime.now(timezone.utc) - timedelta(days=DEFAULT_SYNC_LOOKBACK_DAYS)
    safe_limit = max(1, min(int(limit or 100), 500))
    client = None
    try:
        client = _imap_connection(config, timeout=timeout)
        folder = _sent_mailbox(client) if mailbox == "sent" else config.get("imap_folder") or "INBOX"
        status, _data = client.select(_imap_mailbox_argument(folder), readonly=True)
        if _text(status).upper() != "OK":
            raise EmailAdapterError("email_imap_folder_unavailable", "IMAP folder is unavailable")
        since_token = sync_since.astimezone(timezone.utc).strftime("%d-%b-%Y")
        status, data = client.uid("search", None, "SINCE", since_token)
        if _text(status).upper() != "OK":
            raise EmailAdapterError("email_imap_search_failed", "IMAP search failed", retryable=True)
        raw_ids = data[0].split() if data and data[0] else []
        messages: list[dict[str, Any]] = []
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
            to_addresses = [normalize_email(address) for _name, address in getaddresses(message.get_all("To", []))]
            uid = raw_uid.decode("ascii", errors="ignore") if isinstance(raw_uid, bytes) else _text(raw_uid)
            references = " ".join(message.get_all("References", []))
            event_prefix = f"email:{sender_account.get('id')}"
            messages.append({
                "provider_event_id": (
                    f"{event_prefix}:{uid}" if mailbox == "inbox" else f"{event_prefix}:sent:{uid}"
                )[:255],
                "mailbox_uid": uid,
                "mailbox": mailbox,
                "message_id": _text(message.get("Message-ID"))[:255] or None,
                "in_reply_to": _text(message.get("In-Reply-To"))[:1000] or None,
                "references": references[:4000] or None,
                "from_email": next((address for address in from_addresses if address), "") or None,
                "to_emails": [address for address in to_addresses if address],
                "subject": _text(message.get("Subject"))[:500],
                "body": _message_body(message),
                "auto_submitted": _text(message.get("Auto-Submitted"))[:100],
                "precedence": _text(message.get("Precedence"))[:100],
                "occurred_at": occurred_at or datetime.now(timezone.utc),
            })
        return messages
    except Exception as exc:
        raise classify_email_exception(exc) from exc
    finally:
        _close_imap(client)


def fetch_replies(
    sender_account: dict[str, Any],
    *,
    since_at: datetime | None = None,
    limit: int = 100,
    timeout: int = 20,
) -> list[dict[str, Any]]:
    return fetch_mailbox_messages(
        sender_account,
        mailbox="inbox",
        since_at=since_at,
        limit=limit,
        timeout=timeout,
    )
