"""restore client ownership for partnership workstreams

Revision ID: 20260714_002
Revises: 20260714_001
Create Date: 2026-07-14 23:30:00.000000
"""

from alembic import op


revision = "20260714_002"
down_revision = "20260714_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        WITH room_owner AS (
            SELECT DISTINCT ON (sr.lead_id::text)
                sr.lead_id::text AS lead_id,
                sr.business_id::text AS client_business_id
            FROM sales_rooms sr
            WHERE sr.mode = 'partner_search'
              AND sr.business_id IS NOT NULL
            ORDER BY sr.lead_id::text, sr.updated_at DESC
        ),
        card_owner AS (
            SELECT DISTINCT ON (pc.lead_id::text)
                pc.lead_id::text AS lead_id,
                pc.business_id::text AS client_business_id
            FROM partnership_partner_cards pc
            WHERE pc.lead_id IS NOT NULL
              AND pc.business_id IS NOT NULL
            ORDER BY pc.lead_id::text, pc.updated_at DESC
        ),
        desired_owner AS (
            SELECT
                ws.id AS workstream_id,
                COALESCE(room_owner.client_business_id, card_owner.client_business_id) AS client_business_id
            FROM lead_workstreams ws
            LEFT JOIN room_owner ON room_owner.lead_id = ws.lead_id
            LEFT JOIN card_owner ON card_owner.lead_id = ws.lead_id
            WHERE ws.workstream_type = 'client_partnership'
        )
        UPDATE lead_workstreams ws
        SET client_business_id = desired_owner.client_business_id,
            updated_at = NOW()
        FROM desired_owner
        WHERE ws.id = desired_owner.workstream_id
          AND desired_owner.client_business_id IS NOT NULL
          AND ws.client_business_id IS DISTINCT FROM desired_owner.client_business_id
          AND NOT EXISTS (
              SELECT 1
              FROM lead_workstreams existing
              WHERE existing.lead_id = ws.lead_id
                AND existing.workstream_type = 'client_partnership'
                AND existing.client_business_id = desired_owner.client_business_id
                AND existing.id <> ws.id
          )
        """
    )


def downgrade():
    pass
