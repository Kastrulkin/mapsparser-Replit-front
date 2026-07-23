from __future__ import annotations

import uuid
from typing import Any

from psycopg2.extras import Json

from services.outreach_email_adapter import (
    encrypt_mailbox_config,
    normalize_mailbox_config,
    preflight_mailbox,
)
from services.outreach_vk_adapter import (
    ensure_vk_outreach_config,
    encrypt_vk_outreach_config,
    preflight_vk_sender,
    verify_vk_community_access,
)
from services.vk_oauth_service import oauth_token_expiry


def _dict(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}
    return dict(row)


def _record_sender_event(
    cursor: Any,
    *,
    sender_account_id: str,
    event_type: str,
    actor_id: str | None,
    payload: dict[str, Any] | None = None,
) -> None:
    cursor.execute(
        """
        INSERT INTO outreach_sender_account_events (
            id, sender_account_id, event_type, actor_id, payload_json, created_at
        ) VALUES (%s, %s, %s, %s, %s, NOW())
        """,
        (str(uuid.uuid4()), sender_account_id, event_type, actor_id, Json(payload or {})),
    )


def _record_sender_recovery(
    cursor: Any,
    sender_account_id: str,
    *,
    actor_id: str | None,
    provider_code: str = "native_email",
) -> None:
    cursor.execute(
        """
        INSERT INTO outreach_sender_health_events (
            id, sender_account_id, event_type, severity, provider_code,
            metrics_json, occurred_at, created_at
        ) VALUES (%s, %s, 'recovered', 'info', %s, %s, NOW(), NOW())
        """,
        (str(uuid.uuid4()), sender_account_id, provider_code, Json({"actor_id": actor_id})),
    )
    cursor.execute(
        """
        UPDATE outreach_sender_accounts
        SET health_status = 'healthy', health_score = 100,
            health_reason = NULL, health_metrics_json = '{}'::jsonb,
            health_changed_at = CASE
                WHEN health_status <> 'healthy' THEN NOW()
                ELSE health_changed_at
            END,
            last_health_event_at = NOW(), reply_sync_error = NULL,
            updated_at = NOW()
        WHERE id = %s
        """,
        (sender_account_id,),
    )


def safe_sender_payload(sender: dict[str, Any]) -> dict[str, Any]:
    capabilities = sender.get("capabilities_json") or {}
    if not isinstance(capabilities, dict):
        capabilities = {}
    return {
        "id": str(sender.get("id") or ""),
        "scope_type": sender.get("scope_type"),
        "business_id": sender.get("business_id"),
        "owner_user_id": sender.get("owner_user_id"),
        "channel": sender.get("channel"),
        "sender_identity": sender.get("sender_identity"),
        "display_name": sender.get("display_name"),
        "status": sender.get("status"),
        "outreach_enabled": bool(sender.get("outreach_enabled")),
        "reply_sync_enabled": bool(sender.get("outreach_enabled") and capabilities.get("reply_sync")),
        "capabilities": capabilities,
        "health_status": sender.get("health_status"),
        "health_score": sender.get("health_score"),
        "health_reason": sender.get("health_reason"),
        "permission_changed_at": sender.get("permission_changed_at"),
        "last_reply_sync_at": sender.get("last_reply_sync_at"),
        "reply_sync_error": sender.get("reply_sync_error"),
        "created_at": sender.get("created_at"),
        "updated_at": sender.get("updated_at"),
    }


def list_sender_accounts(
    cursor: Any,
    *,
    scope_type: str,
    business_id: str | None,
) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT id, scope_type, business_id, owner_user_id, channel,
               sender_identity, display_name, status, outreach_enabled,
               capabilities_json, health_status, health_score, health_reason,
               permission_changed_at, last_reply_sync_at, reply_sync_error,
               created_at, updated_at
        FROM outreach_sender_accounts
        WHERE scope_type = %s
          AND COALESCE(business_id, '') = COALESCE(%s, '')
        ORDER BY status = 'connected' DESC, channel, updated_at DESC
        """,
        (scope_type, business_id),
    )
    return [safe_sender_payload(_dict(row)) for row in cursor.fetchall()]


def load_sender_account(cursor: Any, sender_account_id: str, *, for_update: bool = False) -> dict[str, Any]:
    cursor.execute(
        f"""
        SELECT * FROM outreach_sender_accounts
        WHERE id = %s
        {"FOR UPDATE" if for_update else ""}
        """,
        (sender_account_id,),
    )
    return _dict(cursor.fetchone())


def _pause_sender_work(cursor: Any, sender_account_id: str, reason_code: str) -> None:
    cursor.execute(
        """
        UPDATE outreach_campaign_touches
        SET status = 'paused', preflight_reason = %s,
            delivery_json = COALESCE(delivery_json, '{}'::jsonb)
                || jsonb_build_object('pause_reason', %s, 'paused_at', NOW()),
            updated_at = NOW()
        WHERE sender_account_id = %s
          AND status IN ('draft', 'approved', 'scheduled', 'queued')
        """,
        (reason_code, reason_code, sender_account_id),
    )
    cursor.execute(
        """
        UPDATE outreach_campaigns campaign
        SET status = 'paused', stop_reason = %s,
            needs_attention_reason = %s, updated_at = NOW()
        WHERE campaign.status IN ('approved', 'active')
          AND EXISTS (
              SELECT 1 FROM outreach_campaign_touches touch
              WHERE touch.campaign_id = campaign.id
                AND touch.sender_account_id = %s
                AND touch.status = 'paused'
          )
        """,
        (reason_code, reason_code, sender_account_id),
    )
    cursor.execute(
        """
        UPDATE outreachsendqueue
        SET delivery_status = 'paused', error_text = %s,
            preflight_reason = %s, updated_at = NOW()
        WHERE sender_account_id = %s
          AND delivery_status IN ('queued', 'retry')
        """,
        (reason_code, reason_code, sender_account_id),
    )


def connect_email_sender(
    cursor: Any,
    *,
    scope_type: str,
    business_id: str | None,
    owner_user_id: str | None,
    mailbox_payload: dict[str, Any],
    outreach_enabled: bool,
) -> dict[str, Any]:
    config = normalize_mailbox_config(mailbox_payload)
    preflight = preflight_mailbox(config)
    encrypted = encrypt_mailbox_config(config)
    cursor.execute(
        """
        SELECT * FROM outreach_sender_accounts
        WHERE scope_type = %s
          AND COALESCE(business_id, '') = COALESCE(%s, '')
          AND channel = 'email'
          AND sender_identity = %s
        FOR UPDATE
        """,
        (scope_type, business_id, config["email"]),
    )
    current = _dict(cursor.fetchone())
    sender_id = str(current.get("id") or uuid.uuid4())
    capabilities = {
        **(preflight.get("capabilities") or {}),
        "smtp_security": config["smtp_security"],
        "imap_security": config["imap_security"],
    }
    if current:
        cursor.execute(
            """
            UPDATE outreach_sender_accounts
            SET owner_user_id = COALESCE(%s, owner_user_id),
                sender_identity = %s, display_name = %s,
                auth_data_encrypted = %s, status = 'connected',
                capabilities_json = %s, outreach_enabled = %s,
                permission_changed_by = %s, permission_changed_at = NOW(),
                reply_sync_error = NULL, updated_at = NOW()
            WHERE id = %s
            RETURNING *
            """,
            (
                owner_user_id, config["email"], config.get("display_name") or None,
                encrypted, Json(capabilities), bool(outreach_enabled), owner_user_id, sender_id,
            ),
        )
    else:
        cursor.execute(
            """
            INSERT INTO outreach_sender_accounts (
                id, scope_type, business_id, owner_user_id, channel,
                sender_identity, display_name, auth_data_encrypted,
                status, capabilities_json, outreach_enabled,
                permission_changed_by, permission_changed_at,
                created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, 'email', %s, %s, %s,
                'connected', %s, %s, %s, NOW(), NOW(), NOW()
            )
            RETURNING *
            """,
            (
                sender_id, scope_type, business_id, owner_user_id,
                config["email"], config.get("display_name") or None, encrypted,
                Json(capabilities), bool(outreach_enabled), owner_user_id,
            ),
        )
    sender = _dict(cursor.fetchone())
    _record_sender_event(
        cursor,
        sender_account_id=sender_id,
        event_type="connected",
        actor_id=owner_user_id,
        payload={
            "channel": "email",
            "sender_identity": config["email"],
            "scope_type": scope_type,
            "business_id": business_id,
            "outreach_enabled": bool(outreach_enabled),
            "reply_sync_enabled": True,
            "reconnected": bool(current),
        },
    )
    _record_sender_event(
        cursor,
        sender_account_id=sender_id,
        event_type="preflight_succeeded",
        actor_id=owner_user_id,
        payload={"direct_send": True, "reply_sync": True},
    )
    _record_sender_recovery(cursor, sender_id, actor_id=owner_user_id)
    sender = load_sender_account(cursor, sender_id)
    return safe_sender_payload(sender)


def connect_vk_sender(
    cursor: Any,
    *,
    scope_type: str,
    business_id: str | None,
    owner_user_id: str | None,
    token_payload: dict[str, Any],
    device_id: str,
    verification: dict[str, Any],
) -> dict[str, Any]:
    user_id = str(verification.get("user_id") or "").strip()
    if not user_id:
        raise ValueError("vk_identity_missing")
    config = {
        "access_token": str(token_payload.get("access_token") or "").strip(),
        "refresh_token": str(token_payload.get("refresh_token") or "").strip() or None,
        "expires_in": token_payload.get("expires_in"),
        "expires_at": oauth_token_expiry(token_payload.get("expires_in")),
        "device_id": str(device_id or "").strip() or None,
        "user_id": user_id,
        "screen_name": verification.get("screen_name"),
        "connected_at": verification.get("verified_at"),
    }
    encrypted = encrypt_vk_outreach_config(config)
    capabilities = verification.get("capabilities") or {}
    cursor.execute(
        """
        SELECT * FROM outreach_sender_accounts
        WHERE scope_type = %s
          AND COALESCE(business_id, '') = COALESCE(%s, '')
          AND channel = 'vk'
          AND sender_identity = %s
        FOR UPDATE
        """,
        (scope_type, business_id, user_id),
    )
    current = _dict(cursor.fetchone())
    sender_id = str(current.get("id") or uuid.uuid4())
    if current:
        cursor.execute(
            """
            UPDATE outreach_sender_accounts
            SET owner_user_id = COALESCE(%s, owner_user_id),
                sender_identity = %s, display_name = %s,
                auth_data_encrypted = %s, status = 'connected',
                capabilities_json = %s, outreach_enabled = FALSE,
                permission_changed_by = %s, permission_changed_at = NOW(),
                reply_sync_error = NULL, updated_at = NOW()
            WHERE id = %s
            RETURNING *
            """,
            (
                owner_user_id, user_id, verification.get("display_name"),
                encrypted, Json(capabilities), owner_user_id, sender_id,
            ),
        )
    else:
        cursor.execute(
            """
            INSERT INTO outreach_sender_accounts (
                id, scope_type, business_id, owner_user_id, channel,
                sender_identity, display_name, auth_data_encrypted,
                status, capabilities_json, outreach_enabled,
                permission_changed_by, permission_changed_at,
                created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, 'vk', %s, %s, %s,
                'connected', %s, FALSE, %s, NOW(), NOW(), NOW()
            )
            RETURNING *
            """,
            (
                sender_id, scope_type, business_id, owner_user_id,
                user_id, verification.get("display_name"), encrypted,
                Json(capabilities), owner_user_id,
            ),
        )
    cursor.fetchone()
    _record_sender_event(
        cursor,
        sender_account_id=sender_id,
        event_type="connected",
        actor_id=owner_user_id,
        payload={
            "channel": "vk",
            "sender_identity": user_id,
            "scope_type": scope_type,
            "business_id": business_id,
            "outreach_enabled": False,
            "reply_sync_enabled": True,
            "reconnected": bool(current),
        },
    )
    _record_sender_event(
        cursor,
        sender_account_id=sender_id,
        event_type="preflight_succeeded",
        actor_id=owner_user_id,
        payload={"direct_send": True, "reply_sync": True, "messages_sent": 0},
    )
    _record_sender_recovery(
        cursor, sender_id, actor_id=owner_user_id, provider_code="vk_user_api",
    )
    return safe_sender_payload(load_sender_account(cursor, sender_id))


def connect_vk_community_sender(
    cursor: Any,
    *,
    scope_type: str,
    business_id: str | None,
    owner_user_id: str | None,
    community_reference: str,
    access_token: str,
) -> dict[str, Any]:
    verification = verify_vk_community_access(access_token, community_reference)
    group_id = str(verification.get("group_id") or "").strip()
    if not group_id:
        raise ValueError("vk_group_identity_missing")
    sender_identity = f"community:{group_id}"
    config = {
        "access_token": str(access_token or "").strip(),
        "account_kind": "community",
        "group_id": group_id,
        "screen_name": verification.get("screen_name"),
        "connected_at": verification.get("verified_at"),
    }
    encrypted = encrypt_vk_outreach_config(config)
    capabilities = verification.get("capabilities") or {}
    cursor.execute(
        """
        SELECT * FROM outreach_sender_accounts
        WHERE scope_type = %s
          AND COALESCE(business_id, '') = COALESCE(%s, '')
          AND channel = 'vk'
          AND sender_identity = %s
        FOR UPDATE
        """,
        (scope_type, business_id, sender_identity),
    )
    current = _dict(cursor.fetchone())
    sender_id = str(current.get("id") or uuid.uuid4())
    if current:
        cursor.execute(
            """
            UPDATE outreach_sender_accounts
            SET owner_user_id = COALESCE(%s, owner_user_id),
                display_name = %s, auth_data_encrypted = %s,
                status = 'connected', capabilities_json = %s,
                outreach_enabled = FALSE, permission_changed_by = %s,
                permission_changed_at = NOW(), reply_sync_error = NULL,
                updated_at = NOW()
            WHERE id = %s
            RETURNING *
            """,
            (
                owner_user_id, verification.get("display_name"), encrypted,
                Json(capabilities), owner_user_id, sender_id,
            ),
        )
    else:
        cursor.execute(
            """
            INSERT INTO outreach_sender_accounts (
                id, scope_type, business_id, owner_user_id, channel,
                sender_identity, display_name, auth_data_encrypted,
                status, capabilities_json, outreach_enabled,
                permission_changed_by, permission_changed_at,
                created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, 'vk', %s, %s, %s,
                'connected', %s, FALSE, %s, NOW(), NOW(), NOW()
            )
            RETURNING *
            """,
            (
                sender_id, scope_type, business_id, owner_user_id,
                sender_identity, verification.get("display_name"), encrypted,
                Json(capabilities), owner_user_id,
            ),
        )
    cursor.fetchone()
    _record_sender_event(
        cursor,
        sender_account_id=sender_id,
        event_type="connected",
        actor_id=owner_user_id,
        payload={
            "channel": "vk",
            "account_kind": "community",
            "group_id": group_id,
            "profile_url": verification.get("profile_url"),
            "display_name": verification.get("display_name"),
            "scope_type": scope_type,
            "business_id": business_id,
            "outreach_enabled": False,
            "reply_sync_enabled": True,
            "reconnected": bool(current),
        },
    )
    _record_sender_event(
        cursor,
        sender_account_id=sender_id,
        event_type="preflight_succeeded",
        actor_id=owner_user_id,
        payload={"direct_send": True, "reply_sync": True, "messages_sent": 0},
    )
    _record_sender_recovery(
        cursor, sender_id, actor_id=owner_user_id, provider_code="vk_community_api",
    )
    return safe_sender_payload(load_sender_account(cursor, sender_id))


def preflight_email_sender(cursor: Any, sender_account_id: str, *, actor_id: str | None) -> dict[str, Any]:
    sender = load_sender_account(cursor, sender_account_id)
    if not sender or sender.get("channel") != "email":
        raise LookupError("Email sender not found")
    try:
        from services.outreach_email_adapter import load_mailbox_config

        result = preflight_mailbox(load_mailbox_config(sender))
    except Exception as exc:
        _record_sender_event(
            cursor,
            sender_account_id=sender_account_id,
            event_type="preflight_failed",
            actor_id=actor_id,
            payload={"error_code": getattr(exc, "code", "email_preflight_failed")},
        )
        raise
    _record_sender_event(
        cursor,
        sender_account_id=sender_account_id,
        event_type="preflight_succeeded",
        actor_id=actor_id,
        payload={"direct_send": True, "reply_sync": True},
    )
    _record_sender_recovery(cursor, sender_account_id, actor_id=actor_id)
    return result


def preflight_vk_sender_account(cursor: Any, sender_account_id: str, *, actor_id: str | None) -> dict[str, Any]:
    sender = load_sender_account(cursor, sender_account_id)
    if not sender or sender.get("channel") != "vk":
        raise LookupError("VK sender not found")
    try:
        _config, refreshed_encrypted = ensure_vk_outreach_config(sender)
        if refreshed_encrypted:
            cursor.execute(
                """
                UPDATE outreach_sender_accounts
                SET auth_data_encrypted = %s, updated_at = NOW()
                WHERE id = %s
                """,
                (refreshed_encrypted, sender_account_id),
            )
            sender["auth_data_encrypted"] = refreshed_encrypted
        result = preflight_vk_sender(sender)
    except Exception as exc:
        _record_sender_event(
            cursor,
            sender_account_id=sender_account_id,
            event_type="preflight_failed",
            actor_id=actor_id,
            payload={"error_code": getattr(exc, "code", "vk_preflight_failed")},
        )
        raise
    _record_sender_event(
        cursor,
        sender_account_id=sender_account_id,
        event_type="preflight_succeeded",
        actor_id=actor_id,
        payload={"direct_send": True, "reply_sync": True, "messages_sent": 0},
    )
    capabilities = sender.get("capabilities_json") or {}
    provider_code = capabilities.get("provider") if isinstance(capabilities, dict) else None
    _record_sender_recovery(
        cursor,
        sender_account_id,
        actor_id=actor_id,
        provider_code=str(provider_code or "vk_user_api"),
    )
    return result


def change_sender_permission(
    cursor: Any,
    sender_account_id: str,
    *,
    outreach_enabled: bool,
    actor_id: str | None,
) -> dict[str, Any]:
    sender = load_sender_account(cursor, sender_account_id, for_update=True)
    if not sender:
        raise LookupError("Sender account not found")
    if sender.get("status") != "connected" and outreach_enabled:
        raise ValueError("Reconnect the sender account before enabling outreach")
    capabilities = sender.get("capabilities_json") or {}
    if outreach_enabled and (
        not isinstance(capabilities, dict)
        or not capabilities.get("direct_send")
        or not capabilities.get("reply_sync")
    ):
        raise ValueError("Direct send and reply sync are required")
    cursor.execute(
        """
        UPDATE outreach_sender_accounts
        SET outreach_enabled = %s, permission_changed_by = %s,
            permission_changed_at = NOW(), updated_at = NOW()
        WHERE id = %s
        RETURNING *
        """,
        (bool(outreach_enabled), actor_id, sender_account_id),
    )
    updated = _dict(cursor.fetchone())
    _record_sender_event(
        cursor,
        sender_account_id=sender_account_id,
        event_type="permission_changed",
        actor_id=actor_id,
        payload={
            "outreach_enabled": bool(outreach_enabled),
            "reply_sync_enabled": bool(outreach_enabled),
        },
    )
    if not outreach_enabled:
        _pause_sender_work(cursor, sender_account_id, "sender_permission_revoked")
    return safe_sender_payload(updated)


def disconnect_sender(cursor: Any, sender_account_id: str, *, actor_id: str | None) -> dict[str, Any]:
    sender = load_sender_account(cursor, sender_account_id, for_update=True)
    if not sender:
        raise LookupError("Sender account not found")
    _pause_sender_work(cursor, sender_account_id, "sender_account_disconnected")
    cursor.execute(
        """
        UPDATE outreach_sender_accounts
        SET status = 'disabled', outreach_enabled = FALSE,
            auth_data_encrypted = CASE WHEN channel IN ('email', 'vk') THEN NULL ELSE auth_data_encrypted END,
            permission_changed_by = %s, permission_changed_at = NOW(),
            updated_at = NOW()
        WHERE id = %s
        RETURNING *
        """,
        (actor_id, sender_account_id),
    )
    updated = _dict(cursor.fetchone())
    _record_sender_event(
        cursor,
        sender_account_id=sender_account_id,
        event_type="disconnected",
        actor_id=actor_id,
        payload={"channel": sender.get("channel")},
    )
    return safe_sender_payload(updated)
