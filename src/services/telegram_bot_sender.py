"""Outcome-aware Telegram bot send helpers shared by workers and capabilities."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Callable

from core.telegram_network import telegram_urlopen


def send_telegram_message_result(
    chat_id: str,
    text: str,
    reply_markup: dict[str, Any] | None = None,
    *,
    include_outcome: bool = False,
    urlopen: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    def classified(result: dict[str, Any], outcome: str) -> dict[str, Any]:
        return {**result, "publish_outcome": outcome} if include_outcome else result

    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    normalized_chat_id = str(chat_id or "").strip()
    if not token or not normalized_chat_id:
        return classified({"success": False, "message_id": 0, "reason_code": "telegram_not_configured"}, "not_attempted")
    try:
        request_payload: dict[str, Any] = {
            "chat_id": normalized_chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        if isinstance(reply_markup, dict) and reply_markup:
            request_payload["reply_markup"] = reply_markup
        request = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=json.dumps(request_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        open_url = urlopen or telegram_urlopen
        with open_url(request, timeout=10) as response:
            status = int(getattr(response, "status", 500))
            raw = response.read()
            data = json.loads(raw.decode("utf-8")) if raw else {}
            result = data.get("result") if isinstance(data, dict) else {}
            message_id = int(result.get("message_id") or 0) if isinstance(result, dict) else 0
            accepted = 200 <= status < 300 and bool(data.get("ok"))
            success = accepted
            outcome = "confirmed" if accepted and message_id > 0 else (
                "rejected" if 400 <= status < 500 or (200 <= status < 300 and data.get("ok") is False) else "uncertain"
            )
            return classified({"success": success, "message_id": message_id, "reason_code": ""}, outcome)
    except urllib.error.HTTPError as error:
        return classified(
            {"success": False, "message_id": 0, "reason_code": type(error).__name__},
            "rejected" if 400 <= int(error.code or 0) < 500 else "uncertain",
        )
    except (urllib.error.URLError, TimeoutError) as error:
        return classified({"success": False, "message_id": 0, "reason_code": type(error).__name__}, "uncertain")
    except Exception as error:
        return classified({"success": False, "message_id": 0, "reason_code": type(error).__name__}, "uncertain")
