"""Classify operational business and network contexts.

Revision ID: 20260814_001
Revises: 20260813_003
"""

from alembic import op


revision = "20260814_001"
down_revision = "20260813_003"
branch_labels = None
depends_on = None


CLIENT_BUSINESS_IDS = (
    "360b90ef-cf2b-4eb4-acd4-a8524e4600ae",  # Органика
    "533c1300-8a54-43a8-aa1f-69a8ed9c24ba",  # Оливер
    "97f44bd2-5f24-45b7-b7c3-dfd14d494eba",  # Intellectum
    "761b0d73-bd35-4f20-9501-2fac1e822f1c",  # Каток
    "edbd961a-273f-4f15-836e-33aacc0aa0e3",  # Riderra
    "aafc48df-58fd-4de5-9fd6-11cf2cd9a73a",  # HighSpeed and Go
    "94b955f4-100d-43c0-8160-dda6db5876ed",  # Массаж тела и лица
    "a544c42b-dca1-450f-a1c0-cce97f52e8d2",  # Transfer Ofis
    "ac19d7c3-53eb-4bc2-9dbe-d41a062864b4",  # Alternativ Taxi
    "38a11c0e-6eea-4fdc-90d6-66f21af9adce",  # Новамед
    "0c9021f3-9755-41be-a0ff-ea12e711fb0f",  # WaterLand
)

CLIENT_NETWORK_IDS = (
    "ab26362f-9d63-4025-b721-9a8cb29015ef",  # Весёлая расчёска
    "55602996-cc00-4f1e-b017-38fa3b4d5965",  # Кафе Кебаб
    "a65a56c3-26a4-5921-a894-d36eb142ff72",  # Шансик
)

INTERNAL_BUSINESS_IDS = ("localos-platform-telegram-radar",)
DEMO_NETWORK_IDS = ("d8d0aac7-696a-504a-93a6-15ab43c8a8dd",)


def _quoted(values):
    return ", ".join("'" + value.replace("'", "''") + "'" for value in values)


def upgrade():
    op.execute("ALTER TABLE businesses ADD COLUMN IF NOT EXISTS entity_group TEXT")
    op.execute("ALTER TABLE networks ADD COLUMN IF NOT EXISTS entity_group TEXT")

    # The current production inventory is authoritative: unlisted legacy rows are
    # leads/observations, not customer workspaces.
    op.execute("UPDATE businesses SET entity_group = 'lead'")
    op.execute("UPDATE networks SET entity_group = 'lead'")
    op.execute(
        f"UPDATE businesses SET entity_group = 'client' WHERE id IN ({_quoted(CLIENT_BUSINESS_IDS)})"
    )
    op.execute(
        f"UPDATE networks SET entity_group = 'client' WHERE id IN ({_quoted(CLIENT_NETWORK_IDS)})"
    )
    op.execute(
        f"UPDATE businesses SET entity_group = 'client' WHERE network_id IN ({_quoted(CLIENT_NETWORK_IDS)})"
    )
    op.execute(
        f"UPDATE businesses SET entity_group = 'internal' WHERE id IN ({_quoted(INTERNAL_BUSINESS_IDS)})"
    )
    op.execute(
        f"UPDATE networks SET entity_group = 'demo' WHERE id IN ({_quoted(DEMO_NETWORK_IDS)})"
    )
    op.execute(
        f"UPDATE businesses SET entity_group = 'demo' WHERE network_id IN ({_quoted(DEMO_NETWORK_IDS)})"
    )

    op.execute("ALTER TABLE businesses ALTER COLUMN entity_group SET DEFAULT 'lead'")
    op.execute("ALTER TABLE businesses ALTER COLUMN entity_group SET NOT NULL")
    op.execute("ALTER TABLE networks ALTER COLUMN entity_group SET DEFAULT 'lead'")
    op.execute("ALTER TABLE networks ALTER COLUMN entity_group SET NOT NULL")
    op.execute("CREATE INDEX IF NOT EXISTS idx_businesses_entity_group_active ON businesses(entity_group, is_active)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_networks_entity_group ON networks(entity_group)")

    # Reconcile approvals whose TTL elapsed before the runtime learned to expire
    # them during reads. They cannot be confirmed anymore.
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.action_requests') IS NOT NULL
               AND to_regclass('public.action_approvals') IS NOT NULL THEN
                UPDATE action_requests request
                SET status = 'expired', updated_at = NOW()
                FROM action_approvals approval
                WHERE approval.action_id = request.action_id
                  AND request.status = 'pending_human'
                  AND approval.expires_at <= NOW();

                UPDATE action_approvals
                SET status = 'expired', resolved_at = COALESCE(resolved_at, NOW()),
                    decision_reason = COALESCE(decision_reason, 'ttl expired during context reconciliation')
                WHERE status = 'pending_human'
                  AND expires_at <= NOW();
            END IF;
        END
        $$
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_networks_entity_group")
    op.execute("DROP INDEX IF EXISTS idx_businesses_entity_group_active")
    op.execute("ALTER TABLE networks DROP COLUMN IF EXISTS entity_group")
    op.execute("ALTER TABLE businesses DROP COLUMN IF EXISTS entity_group")
