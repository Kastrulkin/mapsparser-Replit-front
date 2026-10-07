"""Pin the current approved program independently of editable blueprint metadata."""
from alembic import op

revision = "20260906_007"
down_revision = "20260906_006"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE agent_blueprints ADD COLUMN IF NOT EXISTS compiled_approved_version_id TEXT")
    # Historical approvals are not automatically activated. An explicit new
    # preview/approval is required before admission under the new contract.


def downgrade():
    # Preserve approvals and run history when rolling application code back.
    pass
