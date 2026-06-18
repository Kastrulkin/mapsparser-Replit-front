"""add sales room proposal review

Revision ID: 20260618_001
Revises: 20260617_002
Create Date: 2026-06-18 14:30:00.000000
"""

from alembic import op


revision = "20260618_001"
down_revision = "20260617_002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS sales_room_proposal_versions (
            id UUID PRIMARY KEY,
            room_id UUID NOT NULL REFERENCES sales_rooms(id) ON DELETE CASCADE,
            version_no INTEGER NOT NULL,
            body_text TEXT NOT NULL,
            created_by_name TEXT,
            created_by_contact TEXT,
            metadata_json JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (room_id, version_no)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_sales_room_proposal_versions_room
        ON sales_room_proposal_versions (room_id, version_no DESC)
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS sales_room_proposal_suggestions (
            id UUID PRIMARY KEY,
            room_id UUID NOT NULL REFERENCES sales_rooms(id) ON DELETE CASCADE,
            version_id UUID REFERENCES sales_room_proposal_versions(id) ON DELETE SET NULL,
            suggestion_type TEXT NOT NULL DEFAULT 'replace',
            selection_text TEXT NOT NULL,
            selection_start INTEGER,
            selection_end INTEGER,
            replacement_text TEXT,
            comment_text TEXT,
            author_name TEXT,
            author_contact TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            resolved_by_name TEXT,
            resolved_by_contact TEXT,
            resolved_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_sales_room_proposal_suggestions_room_status
        ON sales_room_proposal_suggestions (room_id, status, created_at DESC)
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_sales_room_proposal_suggestions_room_status")
    op.execute("DROP TABLE IF EXISTS sales_room_proposal_suggestions")
    op.execute("DROP INDEX IF EXISTS idx_sales_room_proposal_versions_room")
    op.execute("DROP TABLE IF EXISTS sales_room_proposal_versions")
