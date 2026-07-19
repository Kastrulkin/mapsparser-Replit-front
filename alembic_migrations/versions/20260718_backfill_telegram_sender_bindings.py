"""backfill outreach sender bindings for existing Telegram radar accounts

Revision ID: 20260718_001
Revises: 20260717_001
Create Date: 2026-07-18 16:30:00.000000
"""

from alembic import op


revision = "20260718_001"
down_revision = "20260717_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        INSERT INTO outreach_sender_accounts (
            id, scope_type, business_id, owner_user_id, channel,
            external_account_id, status, capabilities_json,
            sender_identity, display_name, outreach_enabled,
            permission_changed_by, permission_changed_at,
            created_at, updated_at
        )
        SELECT
            gen_random_uuid(), 'business', account.business_id, NULL, 'telegram',
            account.id, 'connected',
            jsonb_build_object(
                'direct_send', TRUE,
                'reply_sync', TRUE,
                'backfilled_from_radar', TRUE
            ),
            NULL, COALESCE(NULLIF(account.display_name, ''), 'Telegram-аккаунт'),
            COALESCE(permission.outreach_enabled, FALSE),
            permission.changed_by, COALESCE(permission.updated_at, NOW()),
            NOW(), NOW()
        FROM externalbusinessaccounts account
        LEFT JOIN telegram_account_permissions permission
          ON permission.account_id = account.id
        WHERE account.source = 'telegram_app'
          AND account.is_active = TRUE
          AND account.business_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1
              FROM outreach_sender_accounts sender
              WHERE sender.scope_type = 'business'
                AND sender.business_id = account.business_id
                AND sender.channel = 'telegram'
                AND sender.external_account_id = account.id
          )
        """
    )


def downgrade():
    # Bindings may acquire approved campaign history after deployment. Preserve
    # them on downgrade rather than deleting sender identity or audit history.
    pass
