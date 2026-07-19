from __future__ import annotations

import uuid
from typing import Any


DEFAULT_PERMISSIONS = {
    "radar_enabled": True,
    "outreach_enabled": False,
}


def _row_dict(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}
    return dict(row)


def ensure_permissions(cursor: Any, account_id: str) -> dict[str, Any]:
    cursor.execute(
        """
        INSERT INTO telegram_account_permissions (
            account_id, radar_enabled, outreach_enabled, radar_consented_at,
            created_at, updated_at
        ) VALUES (%s, TRUE, FALSE, NOW(), NOW(), NOW())
        ON CONFLICT (account_id) DO NOTHING
        """,
        (account_id,),
    )
    return get_permissions(cursor, account_id)


def get_permissions(cursor: Any, account_id: str) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT account_id, radar_enabled, outreach_enabled,
               radar_consented_at, outreach_consented_at, changed_by,
               created_at, updated_at
        FROM telegram_account_permissions
        WHERE account_id = %s
        """,
        (account_id,),
    )
    row = cursor.fetchone()
    if not row:
        return {"account_id": account_id, **DEFAULT_PERMISSIONS}
    result = _row_dict(row)
    result["account_id"] = str(result.get("account_id") or account_id)
    return result


def get_account_context(cursor: Any, account_id: str) -> dict[str, Any] | None:
    cursor.execute(
        """
        SELECT a.id AS account_id, a.business_id, a.is_active, a.display_name,
               p.radar_enabled, p.outreach_enabled,
               p.radar_consented_at, p.outreach_consented_at, p.updated_at
        FROM externalbusinessaccounts a
        LEFT JOIN telegram_account_permissions p ON p.account_id = a.id
        WHERE a.id = %s AND a.source = 'telegram_app'
        """,
        (account_id,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    result = _row_dict(row)
    result["radar_enabled"] = bool(
        result.get("radar_enabled") if result.get("radar_enabled") is not None else True
    )
    result["outreach_enabled"] = bool(result.get("outreach_enabled") or False)
    result["is_active"] = bool(result.get("is_active"))
    return result


def assert_account_access(
    cursor: Any,
    account_id: str,
    *,
    business_id: str | None,
    scope_type: str,
    capability: str,
) -> tuple[bool, str, dict[str, Any] | None]:
    context = get_account_context(cursor, account_id)
    if not context or not context.get("is_active"):
        return False, "sender_account_missing", context
    account_business_id = str(context.get("business_id") or "")
    if scope_type == "business" and account_business_id != str(business_id or ""):
        return False, "sender_tenant_mismatch", context
    if scope_type == "platform" and business_id:
        return False, "sender_scope_mismatch", context
    binding_business_id = business_id if scope_type == "business" else None
    cursor.execute(
        """
        SELECT id
        FROM outreach_sender_accounts
        WHERE external_account_id = %s
          AND channel = 'telegram'
          AND scope_type = %s
          AND COALESCE(business_id, '') = COALESCE(%s, '')
          AND status = 'connected'
        LIMIT 1
        """,
        (account_id, scope_type, binding_business_id),
    )
    if not cursor.fetchone():
        return False, "sender_scope_mismatch", context
    permission_key = "radar_enabled" if capability == "radar" else "outreach_enabled"
    if not context.get(permission_key):
        return False, f"{capability}_permission_required", context
    return True, "ready", context


def sync_sender_binding(
    cursor: Any,
    account_id: str,
    *,
    owner_user_id: str | None,
    scope_type: str = "business",
) -> str:
    context = get_account_context(cursor, account_id)
    if not context:
        raise ValueError("Telegram account not found")
    business_id = context.get("business_id") if scope_type == "business" else None
    outreach_enabled = bool(context.get("outreach_enabled"))
    sender_id = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO outreach_sender_accounts (
            id, scope_type, business_id, owner_user_id, channel,
            external_account_id, status, capabilities_json, outreach_enabled,
            permission_changed_by, permission_changed_at, created_at, updated_at
        ) VALUES (
            %s, %s, %s, %s, 'telegram', %s, 'connected',
            jsonb_build_object('direct_send', TRUE, 'reply_sync', TRUE), %s,
            %s, NOW(), NOW(), NOW()
        )
        ON CONFLICT (
            scope_type, (COALESCE(business_id, '')), channel,
            (COALESCE(external_account_id, sender_identity, ''))
        ) DO UPDATE SET
            owner_user_id = COALESCE(EXCLUDED.owner_user_id, outreach_sender_accounts.owner_user_id),
            status = 'connected',
            capabilities_json = EXCLUDED.capabilities_json,
            outreach_enabled = EXCLUDED.outreach_enabled,
            permission_changed_by = EXCLUDED.permission_changed_by,
            permission_changed_at = NOW(),
            updated_at = NOW()
        RETURNING id
        """,
        (
            sender_id, scope_type, business_id, owner_user_id, account_id,
            outreach_enabled, owner_user_id,
        ),
    )
    row = cursor.fetchone()
    return str(row[0] if not hasattr(row, "keys") else row["id"])


def _pause_telegram_work(cursor: Any, account_id: str, reason_code: str) -> None:
    cursor.execute(
        """
        UPDATE outreach_campaign_touches t
        SET status = 'paused',
            delivery_json = COALESCE(t.delivery_json, '{}'::jsonb)
                || jsonb_build_object('pause_reason', %s, 'paused_at', NOW()),
            updated_at = NOW()
        FROM outreach_sender_accounts s
        WHERE t.sender_account_id = s.id
          AND s.external_account_id = %s
          AND t.channel = 'telegram'
          AND t.status IN ('draft', 'approved', 'scheduled', 'queued')
        """,
        (reason_code, account_id),
    )
    cursor.execute(
        """
        UPDATE outreach_campaigns c
        SET status = 'paused', stop_reason = %s, updated_at = NOW()
        WHERE c.status IN ('approved', 'active')
          AND EXISTS (
              SELECT 1
              FROM outreach_campaign_touches t
              JOIN outreach_sender_accounts s ON s.id = t.sender_account_id
              WHERE t.campaign_id = c.id
                AND s.external_account_id = %s
                AND t.status = 'paused'
          )
        """,
        (reason_code, account_id),
    )
    cursor.execute(
        """
        UPDATE outreachsendqueue q
        SET delivery_status = 'paused',
            error_text = %s || ': Telegram sender permission was revoked',
            updated_at = NOW()
        FROM outreach_sender_accounts s
        WHERE q.sender_account_id = s.id
          AND s.external_account_id = %s
          AND q.channel = 'telegram'
          AND q.delivery_status IN ('queued', 'retry')
        """,
        (reason_code, account_id),
    )


def update_permissions(
    cursor: Any,
    account_id: str,
    *,
    radar_enabled: bool | None,
    outreach_enabled: bool | None,
    changed_by: str | None,
    reason_code: str = "user_settings",
) -> dict[str, Any]:
    current = ensure_permissions(cursor, account_id)
    next_radar = bool(current.get("radar_enabled")) if radar_enabled is None else bool(radar_enabled)
    next_outreach = bool(current.get("outreach_enabled")) if outreach_enabled is None else bool(outreach_enabled)
    cursor.execute(
        """
        UPDATE telegram_account_permissions
        SET radar_enabled = %s,
            outreach_enabled = %s,
            radar_consented_at = CASE
                WHEN %s AND NOT radar_enabled THEN NOW() ELSE radar_consented_at END,
            outreach_consented_at = CASE
                WHEN %s AND NOT outreach_enabled THEN NOW() ELSE outreach_consented_at END,
            changed_by = %s,
            updated_at = NOW()
        WHERE account_id = %s
        """,
        (next_radar, next_outreach, next_radar, next_outreach, changed_by, account_id),
    )
    context = get_account_context(cursor, account_id)
    if not context:
        raise ValueError("Telegram account not found")
    cursor.execute(
        """
        INSERT INTO telegram_account_permission_events (
            id, account_id, business_id, radar_enabled, outreach_enabled,
            reason_code, changed_by, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        """,
        (
            str(uuid.uuid4()),
            account_id,
            context.get("business_id"),
            next_radar,
            next_outreach,
            reason_code,
            changed_by,
        ),
    )
    cursor.execute(
        """
        UPDATE outreach_sender_accounts
        SET outreach_enabled = %s,
            permission_changed_by = %s,
            permission_changed_at = NOW(),
            updated_at = NOW()
        WHERE external_account_id = %s
          AND channel = 'telegram'
          AND status = 'connected'
        """,
        (next_outreach, changed_by, account_id),
    )
    cursor.execute(
        """
        SELECT id FROM outreach_sender_accounts
        WHERE external_account_id = %s
          AND channel = 'telegram'
          AND status = 'connected'
        """,
        (account_id,),
    )
    sender_rows = cursor.fetchall()
    for sender_row in sender_rows:
        sender_id = sender_row[0] if not hasattr(sender_row, "keys") else sender_row["id"]
        cursor.execute(
            """
            INSERT INTO outreach_sender_account_events (
                id, sender_account_id, event_type, actor_id, payload_json, created_at
            ) VALUES (
                %s, %s, 'permission_changed', %s,
                jsonb_build_object(
                    'radar_enabled', %s,
                    'outreach_enabled', %s,
                    'reply_sync_enabled', %s,
                    'reason_code', %s
                ), NOW()
            )
            """,
            (
                str(uuid.uuid4()), sender_id, changed_by, next_radar,
                next_outreach, next_outreach, reason_code,
            ),
        )
    if bool(current.get("radar_enabled")) and not next_radar:
        cursor.execute(
            """
            UPDATE knowledge_sources
            SET sync_status = 'idle', next_sync_at = NULL, updated_at = NOW()
            WHERE account_id = %s AND source_type = 'telegram'
            """,
            (account_id,),
        )
        cursor.execute(
            """
            UPDATE telegram_opportunity_sources
            SET is_active = FALSE, needs_attention_reason = 'radar_permission_revoked', updated_at = NOW()
            WHERE account_id = %s
            """,
            (account_id,),
        )
    if bool(current.get("outreach_enabled")) and not next_outreach:
        _pause_telegram_work(cursor, account_id, "sender_permission_revoked")
    return get_permissions(cursor, account_id)


def disconnect_account(cursor: Any, account_id: str, *, changed_by: str | None) -> None:
    update_permissions(
        cursor,
        account_id,
        radar_enabled=False,
        outreach_enabled=False,
        changed_by=changed_by,
        reason_code="account_disconnected",
    )
    _pause_telegram_work(cursor, account_id, "sender_account_disconnected")
    cursor.execute(
        "UPDATE externalbusinessaccounts SET is_active = FALSE, updated_at = NOW() WHERE id = %s",
        (account_id,),
    )
    cursor.execute(
        "UPDATE outreach_sender_accounts SET status = 'disabled', outreach_enabled = FALSE, updated_at = NOW() WHERE external_account_id = %s",
        (account_id,),
    )
