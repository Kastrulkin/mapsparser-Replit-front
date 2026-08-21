"""Allow website section analytics events.

Revision ID: 20260821_001
Revises: 20260820_002
"""

from alembic import op


revision = "20260821_001"
down_revision = "20260820_002"
branch_labels = None
depends_on = None


_BASE_EVENT_TYPES = (
    "'session_start', 'page_view', 'scroll_depth', 'click', "
    "'outbound_click', 'form_start', 'form_submit', 'heartbeat', 'page_leave'"
)


def upgrade():
    op.execute("ALTER TABLE web_events DROP CONSTRAINT IF EXISTS chk_web_event_type")
    op.execute(
        "ALTER TABLE web_events ADD CONSTRAINT chk_web_event_type "
        f"CHECK (event_type IN ({_BASE_EVENT_TYPES}, 'section_view', 'section_engagement'))"
    )


def downgrade():
    op.execute("ALTER TABLE web_events DROP CONSTRAINT IF EXISTS chk_web_event_type")
    op.execute(
        "ALTER TABLE web_events ADD CONSTRAINT chk_web_event_type "
        f"CHECK (event_type IN ({_BASE_EVENT_TYPES})) NOT VALID"
    )
