"""
Unified channel routing policy for business communications.
"""
from __future__ import annotations

import json
import os
from datetime import datetime

from auth_encryption import decrypt_auth_data
from core.channel_delivery import (
    mask_phone,
    normalize_phone,
    resolve_maton_api_url,
    send_maton_bridge_message,
    send_telegram_bot_message,
    send_whatsapp_waba_message,
)


def _load_table_columns(cursor) -> set[str]:
    rows = cursor.fetchall() or []
    cols = set()
    for row in rows:
        if hasattr(row, "keys"):
            value = row.get("column_name")
        else:
            value = row[0] if row else None
        if value:
            cols.add(str(value).lower())
    return cols


def _query_table_columns(cursor, table_name: str) -> set[str]:
    cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = %s
        """,
        (str(table_name).lower(),),
    )
    return _load_table_columns(cursor)


def load_business_channel_context(cursor, business_id: str, *, global_telegram_bot_token: str = "") -> dict | None:
    business_id = str(business_id or "").strip()
    if not business_id:
        return None

    business_cols = _query_table_columns(cursor, "businesses")
    user_cols = _query_table_columns(cursor, "users")
    select_parts = ["b.id", "b.name", "b.owner_id"]
    for col in ("telegram_bot_token", "waba_phone_id", "waba_access_token", "whatsapp_phone", "whatsapp_verified"):
        if col in business_cols:
            select_parts.append(f"b.{col}")
        else:
            select_parts.append(f"NULL AS {col}")
    for col, alias in (("telegram_id", "owner_telegram_id"), ("email", "owner_email"), ("name", "owner_name")):
        if col in user_cols:
            select_parts.append(f"u.{col} AS {alias}")
        else:
            select_parts.append(f"NULL AS {alias}")

    cursor.execute(
        f"""
        SELECT {", ".join(select_parts)}
        FROM businesses b
        LEFT JOIN users u ON u.id = b.owner_id
        WHERE b.id = %s
        LIMIT 1
        """,
        (business_id,),
    )
    row = cursor.fetchone()
    if not row:
        return None

    if hasattr(row, "keys"):
        ctx = dict(row)
    else:
        cols = [d[0] for d in cursor.description]
        ctx = dict(zip(cols, row))
    ctx["global_telegram_bot_token"] = str(global_telegram_bot_token or "").strip()
    ctx["whatsapp_phone"] = normalize_phone(ctx.get("whatsapp_phone"))
    ctx["telegram_bot_token"] = str(ctx.get("telegram_bot_token") or "").strip()
    ctx["waba_phone_id"] = str(ctx.get("waba_phone_id") or "").strip()
    ctx["waba_access_token"] = str(ctx.get("waba_access_token") or "").strip()
    ctx["owner_telegram_id"] = str(ctx.get("owner_telegram_id") or "").strip()
    ctx["owner_email"] = str(ctx.get("owner_email") or "").strip()
    ctx["owner_name"] = str(ctx.get("owner_name") or "").strip()
    ctx["whatsapp_verified"] = bool(ctx.get("whatsapp_verified"))
    ctx["maton_api_key"] = ""
    ctx["maton_api_url"] = resolve_maton_api_url()
    ctx["maton_bridge_enabled"] = str(os.getenv("MATON_BRIDGE_ENABLED", "") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )

    ext_cols = _query_table_columns(cursor, "externalbusinessaccounts")
    ctx["maton_connected"] = False
    if {"business_id", "source"}.issubset(ext_cols):
        select_parts = ["id"]
        if "auth_data_encrypted" in ext_cols:
            select_parts.append("auth_data_encrypted")
        else:
            select_parts.append("NULL AS auth_data_encrypted")
        is_active_expr = "COALESCE(is_active, TRUE)" if "is_active" in ext_cols else "TRUE"
        order_parts = []
        if "updated_at" in ext_cols:
            order_parts.append("updated_at DESC NULLS LAST")
        if "created_at" in ext_cols:
            order_parts.append("created_at DESC NULLS LAST")
        order_sql = ", ".join(order_parts) if order_parts else "id DESC"
        cursor.execute(
            f"""
            SELECT {", ".join(select_parts)}
            FROM externalbusinessaccounts
            WHERE business_id = %s
              AND source = 'maton'
              AND {is_active_expr}
            ORDER BY {order_sql}
            LIMIT 1
            """,
            (business_id,),
        )
        row = cursor.fetchone()
        ctx["maton_connected"] = row is not None
        if row:
            row_dict = dict(row) if hasattr(row, "keys") else {"auth_data_encrypted": row[1] if len(row) > 1 else None}
            auth_data_encrypted = str(row_dict.get("auth_data_encrypted") or "").strip()
            if auth_data_encrypted:
                plain_auth = decrypt_auth_data(auth_data_encrypted) or ""
                plain_auth = plain_auth.strip()
                if plain_auth:
                    try:
                        parsed = json.loads(plain_auth)
                        if isinstance(parsed, dict):
                            ctx["maton_api_key"] = str(parsed.get("api_key") or "").strip()
                    except Exception:
                        ctx["maton_api_key"] = plain_auth
    return ctx


def build_channel_statuses(ctx: dict | None) -> list[dict]:
    ctx = ctx or {}
    owner_telegram_id = str(ctx.get("owner_telegram_id") or "").strip()
    telegram_bot_token = str(ctx.get("telegram_bot_token") or "").strip()
    global_bot_token = str(ctx.get("global_telegram_bot_token") or "").strip()
    whatsapp_phone = normalize_phone(ctx.get("whatsapp_phone"))
    whatsapp_verified = bool(ctx.get("whatsapp_verified"))
    waba_phone_id = str(ctx.get("waba_phone_id") or "").strip()
    waba_access_token = str(ctx.get("waba_access_token") or "").strip()
    maton_connected = bool(ctx.get("maton_connected"))
    maton_api_key = str(ctx.get("maton_api_key") or "").strip()
    maton_api_url = str(ctx.get("maton_api_url") or "").strip()
    maton_bridge_enabled = bool(ctx.get("maton_bridge_enabled"))
    maton_ready = bool(maton_api_key and maton_api_url and maton_bridge_enabled)
    maton_has_key = bool(maton_api_key)

    return [
        {
            "channel_id": "telegram_owner_global",
            "label": "Telegram владельца (глобальный бот)",
            "provider": "telegram",
            "configured": bool(global_bot_token and owner_telegram_id),
            "testable": bool(global_bot_token and owner_telegram_id),
            "status": "ready" if (global_bot_token and owner_telegram_id) else "not_configured",
            "detail": (
                "Глобальный бот может отправлять служебные сообщения владельцу."
                if (global_bot_token and owner_telegram_id)
                else "Нужны TELEGRAM_BOT_TOKEN и telegram_id владельца."
            ),
            "target": owner_telegram_id or None,
        },
        {
            "channel_id": "telegram_owner_business_bot",
            "label": "Telegram владельца (бот бизнеса)",
            "provider": "telegram",
            "configured": bool(telegram_bot_token and owner_telegram_id),
            "testable": bool(telegram_bot_token and owner_telegram_id),
            "status": "ready" if (telegram_bot_token and owner_telegram_id) else "not_configured",
            "detail": (
                "Брендированный бот бизнеса может писать владельцу."
                if (telegram_bot_token and owner_telegram_id)
                else "Нужны telegram_bot_token бизнеса и telegram_id владельца."
            ),
            "target": owner_telegram_id or None,
        },
        {
            "channel_id": "whatsapp_owner",
            "label": "WhatsApp владельца / бизнеса (WABA)",
            "provider": "whatsapp",
            "configured": bool(waba_phone_id and waba_access_token and whatsapp_phone),
            "testable": bool(waba_phone_id and waba_access_token and whatsapp_phone and whatsapp_verified),
            "status": (
                "ready"
                if (waba_phone_id and waba_access_token and whatsapp_phone and whatsapp_verified)
                else "verification_required"
                if (waba_phone_id and waba_access_token and whatsapp_phone)
                else "not_configured"
            ),
            "detail": (
                "WABA настроен и номер подтверждён."
                if (waba_phone_id and waba_access_token and whatsapp_phone and whatsapp_verified)
                else "Номер сохранён, но ещё не верифицирован."
                if (waba_phone_id and waba_access_token and whatsapp_phone)
                else "Нужны waba_phone_id, waba_access_token и whatsapp_phone."
            ),
            "target": mask_phone(whatsapp_phone) or None,
        },
        {
            "channel_id": "maton_bridge",
            "label": "Maton.ai bridge",
            "provider": "maton",
            "configured": maton_has_key,
            "testable": maton_ready,
            "status": (
                "ready"
                if maton_ready
                else "bridge_disabled"
                if maton_connected and maton_has_key
                else "not_configured"
            ),
            "detail": (
                "Maton.ai подключён и готов к outbound-отправке."
                if maton_ready
                else "API-ключ Maton.ai сохранён, но outbound bridge выключен. Нужны MATON_BRIDGE_ENABLED=1 и MATON_API_URL."
                if (maton_connected and maton_has_key)
                else "Нужен API-ключ Maton.ai в интеграциях."
            ),
            "target": "maton.ai" if maton_has_key else None,
        },
    ]


def get_routing_plan(ctx: dict | None, *, preferred_provider: str = "telegram") -> list[dict]:
    by_id = {item["channel_id"]: item for item in build_channel_statuses(ctx)}
    provider = str(preferred_provider or "telegram").strip().lower()
    orders = {
        "telegram": [
            "telegram_owner_business_bot",
            "telegram_owner_global",
            "whatsapp_owner",
            "maton_bridge",
        ],
        "whatsapp": [
            "whatsapp_owner",
            "telegram_owner_business_bot",
            "telegram_owner_global",
            "maton_bridge",
        ],
        "maton": [
            "maton_bridge",
            "telegram_owner_business_bot",
            "telegram_owner_global",
            "whatsapp_owner",
        ],
    }
    selected_order = orders.get(provider, orders["telegram"])
    plan = []
    for channel_id in selected_order:
        item = dict(by_id.get(channel_id) or {})
        if not item:
            continue
        item["preferred"] = item.get("provider") == provider
        item["fallback_order"] = len(plan) + 1
        item["eligible"] = bool(item.get("testable"))
        plan.append(item)
    return plan


def dispatch_with_routing(
    ctx: dict | None,
    text: str,
    *,
    preferred_provider: str = "telegram",
    force_channel_id: str | None = None,
) -> dict:
    ctx = ctx or {}
    message = str(text or "").strip()
    if not message:
        return {"success": False, "error": "message is empty", "attempts": [], "selected_channel_id": ""}

    plan = get_routing_plan(ctx, preferred_provider=preferred_provider)
    attempts: list[dict] = []
    selected_channel = str(force_channel_id or "").strip()
    if selected_channel:
        plan = [item for item in plan if item.get("channel_id") == selected_channel]

    for item in plan:
        channel_id = str(item.get("channel_id") or "")
        if not item.get("eligible"):
            attempts.append(
                {
                    "channel_id": channel_id,
                    "provider": item.get("provider"),
                    "success": False,
                    "skipped": True,
                    "reason": "not_eligible",
                }
            )
            continue

        result = {"success": False, "error": "unsupported channel"}
        if channel_id == "telegram_owner_business_bot":
            result = send_telegram_bot_message(
                ctx.get("telegram_bot_token"),
                ctx.get("owner_telegram_id"),
                message,
            )
        elif channel_id == "telegram_owner_global":
            result = send_telegram_bot_message(
                ctx.get("global_telegram_bot_token"),
                ctx.get("owner_telegram_id"),
                message,
            )
        elif channel_id == "whatsapp_owner":
            result = send_whatsapp_waba_message(
                ctx.get("waba_phone_id"),
                ctx.get("waba_access_token"),
                ctx.get("whatsapp_phone"),
                message,
            )
        elif channel_id == "maton_bridge":
            result = send_maton_bridge_message(
                ctx.get("maton_api_key"),
                message,
                target_channel="auto",
                business_id=ctx.get("id"),
                business_name=ctx.get("name"),
                owner_telegram_id=ctx.get("owner_telegram_id"),
                whatsapp_phone=ctx.get("whatsapp_phone"),
                metadata={
                    "preferred_provider": preferred_provider,
                    "channel_id": channel_id,
                },
            )

        attempt = {
            "channel_id": channel_id,
            "provider": item.get("provider"),
            "success": bool(result.get("success")),
            "status_code": result.get("status_code"),
            "error": str(result.get("error") or ""),
            "unsupported": bool(result.get("unsupported")),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        attempts.append(attempt)
        if attempt["success"]:
            return {
                "success": True,
                "selected_channel_id": channel_id,
                "selected_provider": item.get("provider"),
                "attempts": attempts,
            }
        if selected_channel:
            break

    return {
        "success": False,
        "selected_channel_id": selected_channel,
        "selected_provider": "",
        "attempts": attempts,
        "error": "All eligible channels failed",
    }
