#!/usr/bin/env python3
"""
Minimal LocalOS owner Telegram bot (no external telegram SDK).

Supports:
- /start <bind_token>  -> verifies bind token via LocalOS API
- /help                -> usage and onboarding text
"""

import os
import time
import requests

TELEGRAM_BOT_TOKEN = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
API_BASE_URL = (os.getenv("API_BASE_URL") or "http://app:8000").strip().rstrip("/")
POLL_TIMEOUT_SEC = int(os.getenv("TELEGRAM_POLL_TIMEOUT_SEC", "25"))
RETRY_SLEEP_SEC = float(os.getenv("TELEGRAM_RETRY_SLEEP_SEC", "2"))


def _api_url(method: str) -> str:
    return f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"


def send_message(chat_id: int | str, text: str) -> None:
    try:
        requests.post(
            _api_url("sendMessage"),
            json={"chat_id": chat_id, "text": text},
            timeout=20,
        )
    except Exception as exc:
        print(f"❌ sendMessage failed: {exc}")


def verify_bind_token(bind_token: str, telegram_id: str) -> tuple[bool, str]:
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/telegram/bind/verify",
            json={"token": bind_token, "telegram_id": telegram_id},
            timeout=20,
        )
        data = response.json() if response.content else {}
        if response.status_code == 200 and data.get("success"):
            user = data.get("user") or {}
            return True, (
                "✅ Привязка выполнена.\n"
                f"Пользователь: {user.get('name') or '—'}\n"
                f"Email: {user.get('email') or '—'}\n\n"
                "Теперь можно использовать LocalOS из Telegram."
            )
        err = str(data.get("error") or f"HTTP {response.status_code}")
        return False, f"❌ Не удалось привязать аккаунт: {err}"
    except Exception as exc:
        return False, f"❌ Ошибка проверки токена: {exc}"


def help_text() -> str:
    return (
        "🤖 LocalOS Bot\n\n"
        "Этот бот нужен для управления возможностями LocalOS из Telegram.\n\n"
        "Как подключить:\n"
        "1) LocalOS → Настройки → Интеграции.\n"
        "2) Сгенерируйте код привязки Telegram владельца.\n"
        "3) Отправьте сюда: /start <код>\n\n"
        "Команды:\n"
        "/start - старт / привязка\n"
        "/help - справка"
    )


def handle_message(msg: dict) -> None:
    text = str(msg.get("text") or "").strip()
    if not text:
        return
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    user = msg.get("from") or {}
    telegram_id = str(user.get("id") or "")
    if not chat_id or not telegram_id:
        return

    if text.startswith("/help"):
        send_message(chat_id, help_text())
        return

    if text.startswith("/start"):
        parts = text.split(maxsplit=1)
        bind_token = parts[1].strip() if len(parts) > 1 else ""
        if not bind_token:
            send_message(
                chat_id,
                "👋 Это бот LocalOS.\n\n"
                "Чтобы связать аккаунт, отправьте:\n"
                "/start <код_привязки>\n\n"
                "Код берётся в LocalOS: Настройки → Интеграции.",
            )
            return
        ok, text_out = verify_bind_token(bind_token, telegram_id)
        send_message(chat_id, text_out)
        return


def poll_loop() -> None:
    if not TELEGRAM_BOT_TOKEN:
        print("⚠️ TELEGRAM_BOT_TOKEN not set; exiting.")
        return

    print("🤖 LocalOS owner bot started (long polling)")
    offset = None
    while True:
        try:
            payload = {
                "timeout": POLL_TIMEOUT_SEC,
                "allowed_updates": ["message"],
            }
            if offset is not None:
                payload["offset"] = offset
            resp = requests.get(_api_url("getUpdates"), params=payload, timeout=POLL_TIMEOUT_SEC + 10)
            data = resp.json() if resp.content else {}
            if not data.get("ok"):
                print(f"⚠️ getUpdates not ok: {data}")
                time.sleep(RETRY_SLEEP_SEC)
                continue
            for update in data.get("result") or []:
                update_id = update.get("update_id")
                if isinstance(update_id, int):
                    offset = update_id + 1
                msg = update.get("message")
                if msg:
                    handle_message(msg)
        except Exception as exc:
            print(f"⚠️ polling error: {exc}")
            time.sleep(RETRY_SLEEP_SEC)


if __name__ == "__main__":
    poll_loop()
