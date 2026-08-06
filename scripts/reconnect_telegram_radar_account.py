#!/usr/bin/env python3
"""Replace a revoked Telegram radar session without exposing stored API keys."""

from __future__ import annotations

import argparse
import json

from database_manager import DatabaseManager
from core.telegram_userbot import confirm_code, load_userbot_account, send_code, update_userbot_session


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--account-id", required=True)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--request-code", action="store_true")
    action.add_argument("--code", default="")
    parser.add_argument("--password", default="")
    return parser.parse_args()


def _masked_phone(value: object) -> str:
    digits = "".join(character for character in str(value or "") if character.isdigit())
    return f"+***{digits[-4:]}" if len(digits) >= 4 else "hidden"


def main() -> None:
    args = _arguments()
    database = DatabaseManager()
    cursor = database.conn.cursor()
    try:
        auth_data = load_userbot_account(cursor, account_id=args.account_id)
        if not auth_data:
            raise RuntimeError("telegram_account_not_found")
        if args.request_code:
            for key in (
                "session_string",
                "pending_session_string",
                "phone_code_hash",
                "authorization_status",
                "status",
            ):
                auth_data.pop(key, None)
            result = send_code(auth_data)
        else:
            result = confirm_code(auth_data, args.code, password=args.password)
        auth_data.update({key: value for key, value in result.items() if value is not None})
        if result.get("status") == "authorized":
            for key in ("phone_code_hash", "pending_session_string", "authorization_status"):
                auth_data.pop(key, None)
        update_userbot_session(cursor, args.account_id, auth_data)
        database.conn.commit()
        print(json.dumps({
            "status": result.get("status"),
            "phone": _masked_phone(auth_data.get("phone")),
            "authorized": result.get("status") in {"authorized", "already_authorized"},
            "password_required": result.get("status") == "password_required",
        }, ensure_ascii=False))
    except Exception:
        database.conn.rollback()
        raise
    finally:
        cursor.close()
        database.close()


if __name__ == "__main__":
    main()
