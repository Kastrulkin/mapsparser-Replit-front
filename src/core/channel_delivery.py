"""
Low-level channel delivery helpers for test sends and health checks.
"""
from __future__ import annotations

import json
import os
import urllib.error as urllib_error
import urllib.request as urllib_request


def mask_phone(phone: str | None) -> str:
    digits = "".join(ch for ch in str(phone or "") if ch.isdigit())
    if not digits:
        return ""
    if len(digits) <= 4:
        return "*" * len(digits)
    return f"{'*' * max(len(digits) - 4, 0)}{digits[-4:]}"


def normalize_phone(phone: str | None) -> str:
    raw = str(phone or "").strip()
    if not raw:
        return ""
    normalized = "".join(ch for ch in raw if ch.isdigit() or ch == "+")
    if normalized and not normalized.startswith("+"):
        normalized = f"+{normalized}"
    return normalized


def send_telegram_bot_message(bot_token: str | None, chat_id: str | None, text: str) -> dict:
    bot_token = str(bot_token or "").strip()
    chat_id = str(chat_id or "").strip()
    if not bot_token:
        return {"success": False, "error": "TELEGRAM_BOT_TOKEN is not configured"}
    if not chat_id:
        return {"success": False, "error": "telegram_id is empty"}

    try:
        payload = json.dumps(
            {
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": True,
            }
        ).encode("utf-8")
        req = urllib_request.Request(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib_request.urlopen(req, timeout=10) as resp:
            status = int(getattr(resp, "status", 500))
            return {"success": 200 <= status < 300, "status_code": status}
    except urllib_error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="ignore")
        except Exception:
            body = str(e)
        return {"success": False, "status_code": int(getattr(e, "code", 500)), "error": body or str(e)}
    except (urllib_error.URLError, TimeoutError) as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def send_whatsapp_waba_message(
    phone_id: str | None,
    access_token: str | None,
    to_phone: str | None,
    text: str,
) -> dict:
    phone_id = str(phone_id or "").strip()
    access_token = str(access_token or "").strip()
    to_phone = normalize_phone(to_phone)
    if not phone_id:
        return {"success": False, "error": "waba_phone_id is not configured"}
    if not access_token:
        return {"success": False, "error": "waba_access_token is not configured"}
    if not to_phone:
        return {"success": False, "error": "whatsapp_phone is empty"}

    try:
        payload = json.dumps(
            {
                "messaging_product": "whatsapp",
                "to": to_phone,
                "type": "text",
                "text": {"body": text},
            }
        ).encode("utf-8")
        req = urllib_request.Request(
            f"https://graph.facebook.com/v20.0/{phone_id}/messages",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}",
            },
            method="POST",
        )
        with urllib_request.urlopen(req, timeout=10) as resp:
            status = int(getattr(resp, "status", 500))
            return {"success": 200 <= status < 300, "status_code": status}
    except urllib_error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="ignore")
        except Exception:
            body = str(e)
        return {"success": False, "status_code": int(getattr(e, "code", 500)), "error": body or str(e)}
    except (urllib_error.URLError, TimeoutError) as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def resolve_maton_api_url() -> str:
    direct = str(os.getenv("MATON_API_URL", "") or "").strip()
    if direct:
        return direct
    base = str(os.getenv("MATON_API_BASE_URL", "") or "").strip().rstrip("/")
    path = str(os.getenv("MATON_API_SEND_PATH", "/v1/messages/send") or "").strip()
    if not base:
        return ""
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{base}{path}"


def send_maton_bridge_message(
    api_key: str | None,
    text: str,
    *,
    target_channel: str | None = None,
    business_id: str | None = None,
    business_name: str | None = None,
    owner_telegram_id: str | None = None,
    telegram_handle: str | None = None,
    whatsapp_phone: str | None = None,
    metadata: dict | None = None,
) -> dict:
    api_key = str(api_key or "").strip()
    if not api_key:
        return {"success": False, "error": "maton api key is not configured"}

    url = resolve_maton_api_url()
    if not url:
        return {"success": False, "error": "MATON_API_URL is not configured"}

    try:
        payload = json.dumps(
            {
                "channel": str(target_channel or "auto").strip() or "auto",
                "message": {"text": text},
                "business": {
                    "id": str(business_id or "").strip() or None,
                    "name": str(business_name or "").strip() or None,
                },
                "recipient": {
                    "telegram_id": str(owner_telegram_id or "").strip() or None,
                    "telegram_handle": str(telegram_handle or "").strip().lstrip("@") or None,
                    "phone": normalize_phone(whatsapp_phone) or None,
                },
                "metadata": metadata or {},
            }
        ).encode("utf-8")
        req = urllib_request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "X-API-Key": api_key,
            },
            method="POST",
        )
        with urllib_request.urlopen(req, timeout=12) as resp:
            status = int(getattr(resp, "status", 500))
            body = ""
            try:
                body = resp.read().decode("utf-8", errors="ignore")
            except Exception:
                body = ""
            return {
                "success": 200 <= status < 300,
                "status_code": status,
                "response_excerpt": body[:500] if body else "",
            }
    except urllib_error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="ignore")
        except Exception:
            body = str(e)
        return {
            "success": False,
            "status_code": int(getattr(e, "code", 500)),
            "error": body or str(e),
        }
    except (urllib_error.URLError, TimeoutError) as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": str(e)}
