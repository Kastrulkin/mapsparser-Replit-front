"""add independent lead workstreams

Revision ID: 20260714_001
Revises: 20260711_001
Create Date: 2026-07-14 12:00:00.000000
"""

from alembic import op


revision = "20260714_001"
down_revision = "20260711_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS lead_workstreams (
            id UUID PRIMARY KEY,
            lead_id TEXT NOT NULL REFERENCES prospectingleads(id) ON DELETE CASCADE,
            workstream_type TEXT NOT NULL,
            client_business_id TEXT REFERENCES businesses(id) ON DELETE CASCADE,
            status TEXT NOT NULL DEFAULT 'unprocessed',
            selected_channel TEXT,
            next_action_at TIMESTAMPTZ,
            last_contact_at TIMESTAMPTZ,
            last_contact_channel TEXT,
            last_contact_comment TEXT,
            created_by TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_lead_workstreams_type
                CHECK (workstream_type IN ('localos_sales', 'client_partnership')),
            CONSTRAINT ck_lead_workstreams_client
                CHECK (
                    (workstream_type = 'localos_sales' AND client_business_id IS NULL)
                    OR (workstream_type = 'client_partnership' AND client_business_id IS NOT NULL)
                )
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_lead_workstreams_localos
        ON lead_workstreams (lead_id)
        WHERE workstream_type = 'localos_sales'
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_lead_workstreams_client
        ON lead_workstreams (lead_id, client_business_id)
        WHERE workstream_type = 'client_partnership'
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_lead_workstreams_client_status
        ON lead_workstreams (client_business_id, status, updated_at DESC)
        """
    )

    for table_name in (
        "outreachmessagedrafts",
        "outreachsendqueue",
        "sales_rooms",
        "lead_timeline_events",
    ):
        op.execute(
            f"""
            ALTER TABLE {table_name}
            ADD COLUMN IF NOT EXISTS workstream_id UUID REFERENCES lead_workstreams(id) ON DELETE SET NULL
            """
        )
        op.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_{table_name}_workstream
            ON {table_name} (workstream_id)
            """
        )

    op.execute(
        """
        INSERT INTO lead_workstreams (
            id, lead_id, workstream_type, client_business_id, status,
            selected_channel, next_action_at, last_contact_at,
            last_contact_channel, last_contact_comment, created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            l.id,
            'localos_sales',
            NULL,
            COALESCE(NULLIF(l.pipeline_status, ''), 'unprocessed'),
            l.selected_channel,
            l.next_action_at,
            l.last_contact_at,
            l.last_contact_channel,
            l.last_contact_comment,
            COALESCE(l.created_at, NOW()),
            COALESCE(l.updated_at, l.created_at, NOW())
        FROM prospectingleads l
        WHERE COALESCE(l.intent, 'client_outreach') NOT IN ('partnership', 'partnership_outreach')
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO lead_workstreams (
            id, lead_id, workstream_type, client_business_id, status,
            selected_channel, next_action_at, last_contact_at,
            last_contact_channel, last_contact_comment, created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            l.id,
            'client_partnership',
            l.business_id,
            COALESCE(NULLIF(l.pipeline_status, ''), 'unprocessed'),
            l.selected_channel,
            l.next_action_at,
            l.last_contact_at,
            l.last_contact_channel,
            l.last_contact_comment,
            COALESCE(l.created_at, NOW()),
            COALESCE(l.updated_at, l.created_at, NOW())
        FROM prospectingleads l
        JOIN businesses b ON b.id = l.business_id
        WHERE COALESCE(l.intent, 'client_outreach') IN ('partnership', 'partnership_outreach')
        ON CONFLICT DO NOTHING
        """
    )

    op.execute(
        """
        UPDATE outreachmessagedrafts d
        SET workstream_id = (
            SELECT candidate.id
            FROM lead_workstreams candidate
            WHERE candidate.lead_id = d.lead_id
            ORDER BY
                CASE
                    WHEN COALESCE((d.learning_note_json ->> 'intent'), '') IN ('partnership', 'partnership_outreach')
                         AND candidate.workstream_type = 'client_partnership' THEN 0
                    WHEN COALESCE((d.learning_note_json ->> 'intent'), '') NOT IN ('partnership', 'partnership_outreach')
                         AND candidate.workstream_type = 'localos_sales' THEN 0
                    ELSE 1
                END,
                candidate.created_at ASC
            LIMIT 1
        )
        WHERE d.workstream_id IS NULL
          AND EXISTS (
              SELECT 1
              FROM lead_workstreams candidate
              WHERE candidate.lead_id = d.lead_id
          )
        """
    )
    op.execute(
        """
        UPDATE outreachsendqueue q
        SET workstream_id = d.workstream_id
        FROM outreachmessagedrafts d
        WHERE q.draft_id = d.id
          AND q.workstream_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE sales_rooms sr
        SET workstream_id = (
            SELECT candidate.id
            FROM lead_workstreams candidate
            WHERE candidate.lead_id = sr.lead_id
              AND (
                  (sr.mode = 'partner_search' AND candidate.workstream_type = 'client_partnership'
                       AND candidate.client_business_id = sr.business_id::text)
                  OR (sr.mode = 'client_search' AND candidate.workstream_type = 'localos_sales')
              )
            ORDER BY candidate.created_at ASC
            LIMIT 1
        )
        WHERE sr.workstream_id IS NULL
          AND EXISTS (
              SELECT 1
              FROM lead_workstreams candidate
              WHERE candidate.lead_id = sr.lead_id
                AND (
                    (sr.mode = 'partner_search' AND candidate.workstream_type = 'client_partnership'
                         AND candidate.client_business_id = sr.business_id::text)
                    OR (sr.mode = 'client_search' AND candidate.workstream_type = 'localos_sales')
                )
          )
        """
    )


def downgrade():
    for table_name in (
        "lead_timeline_events",
        "sales_rooms",
        "outreachsendqueue",
        "outreachmessagedrafts",
    ):
        op.execute(f"DROP INDEX IF EXISTS idx_{table_name}_workstream")
        op.execute(f"ALTER TABLE {table_name} DROP COLUMN IF EXISTS workstream_id")
    op.execute("DROP INDEX IF EXISTS idx_lead_workstreams_client_status")
    op.execute("DROP INDEX IF EXISTS uq_lead_workstreams_client")
    op.execute("DROP INDEX IF EXISTS uq_lead_workstreams_localos")
    op.execute("DROP TABLE IF EXISTS lead_workstreams")
